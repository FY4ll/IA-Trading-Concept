"""
MOTEUR DE PRÉDICTION (08/10/2026) -- ÉTUDE, ne touche à rien de ce qui tourne (ni modèles, ni config, ni src/).

Idée : au lieu d'apprendre par essais et erreurs (récompense), l'IA apprend à partir de MILLIONS d'exemples
corrigés. Pour chaque bougie M15 de chaque marché (or, euro/dollar, dollar/yen, S&P 500, livre/dollar, et leurs
versions INVERSÉES), on calcule ce qu'aurait donné un ACHAT et une VENTE à l'ouverture suivante, avec un stop à
k x ATR et un objectif à 2 x le stop (horizon 24 h) : +2 R si l'objectif est touché avant le stop, -1 R si le stop
est touché d'abord (si les deux dans la même bougie : le stop, par prudence), sinon le résultat à l'échéance --
coûts déduits. Un réseau (GRU sur les 32 dernières bougies x 200 variables d'AUREXIS) apprend à prédire ces deux
résultats. On ne trade que si la prédiction est nettement favorable.

Périodes (identiques à AUREXIS) : apprentissage avant le 03/11/2021 ; validation 11/2021 -> 05/2023 (moitié A pour
choisir le seuil, moitié B pour le juger) ; JEU SOUS CLÉ 06/2023 -> aujourd'hui, regardé UNE SEULE FOIS à la fin.

Mémoire : variables écrites sur disque en float16 (data/moteur_prediction/), un marché à la fois, attente si la
mémoire libre de Windows passe sous 1,5 Go (l'entraînement d'AUREXIS reste prioritaire).

    python scripts/moteur_prediction.py [--k 2] [--rebuild]          (cwd = code/)
Écrit reports/moteur_prediction.json et models/moteur_prediction/net.pt.
"""
import argparse, ctypes, gc, json, os, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import yaml

TRAIN_END = pd.Timestamp("2021-11-03")
WARMUP, CHUNK, W, H = 20000, 100_000, 32, 96     # chauffe ~200 jours : moyennes longues D1/H4 complètes
OUT = os.path.join("data", "moteur_prediction")
RISK = 0.005                       # risque par trade pour les courbes de capital (comme la taille d'AUREXIS)


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def free_commit_gb() -> float:
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 1e9


def wait_memory(min_gb=1.5):
    t0 = time.time()
    while free_commit_gb() < min_gb and time.time() - t0 < 1800:
        time.sleep(20)


# ----------------------------------------------------------------------------- données
def market_list(cfg):
    from src.aurexis_data import DEFAULT_MARKETS
    from src.multi_timeframe import discover_files
    mm = cfg.get("multi_market") or {}
    markets = dict(mm.get("markets") or DEFAULT_MARKETS)
    gold = discover_files(cfg["data"]["folder"]).get("M15")
    jobs = [("XAUUSD", gold, False)] + [(s, p, False) for s, p in markets.items()]
    jobs += [("XAUUSD", gold, True)] + [(s, p, True) for s, p in markets.items()]
    return jobs


def build_frame(name, m15, cols, ctx, cross, fred):
    """Variables d'AUREXIS par morceaux de CHUNK bougies (chauffe WARMUP) pour limiter la mémoire."""
    from src.aurexis_data import build_market_frame
    from src.trading_env import TradingEnv
    parts, n = [], len(m15)
    for s in range(WARMUP, n, CHUNK):
        wait_memory()
        sl = m15.iloc[s - WARMUP: s + CHUNK].reset_index(drop=True)
        df = build_market_frame(name, sl, ctx, cross, fred=fred, toolbox=any(c.startswith("tb_") for c in cols))
        df = df.iloc[WARMUP:].reset_index(drop=True)
        df[cols] = df[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0).astype("float32")
        keep = df[["time", "open", "high", "low", "close", TradingEnv.ATR_RAW_COLUMN]].copy()
        keep.columns = ["time", "open", "high", "low", "close", "atr"]
        parts.append((keep, df[cols].to_numpy(np.float32)))
        del df, sl
        gc.collect()
    raw = pd.concat([p[0] for p in parts], ignore_index=True)
    X = np.concatenate([p[1] for p in parts])
    return raw, X


def build_dataset(cfg, cols, ctx):
    from src.aurexis_data import load_m15, mirror_m15, _mirror_neutral
    from src.features import Z_SCORE_CLIP
    data_cfg = cfg["data"]
    cross = data_cfg.get("cross_asset_folder") or os.path.join(
        os.path.dirname(os.path.abspath(data_cfg.get("folder", "."))), "cross_asset")
    fred = None
    try:
        from src.fundamental_feed import AutoFundamentalFeed
        fred = getattr(AutoFundamentalFeed(cfg), "_fred", None)
    except Exception as e:
        log(f"macro indisponible ({type(e).__name__}) : variables macro à zéro")
    os.makedirs(OUT, exist_ok=True)
    neutral_idx = [cols.index(c) for c in _mirror_neutral(cols)]
    metas, total = [], 0
    xpath = os.path.join(OUT, "X.f16")
    with open(xpath, "wb") as fx:
        for sym, path, mirror in market_list(cfg):
            name = f"{sym} miroir" if mirror else sym
            t0 = time.time()
            m15 = load_m15(path)
            m15 = m15[m15["time"] >= pd.Timestamp("2010-01-01")].reset_index(drop=True)
            if mirror:
                m15 = mirror_m15(m15)
            raw, X = build_frame(name, m15, cols, ctx, cross, fred)
            del m15
            tr = (raw["time"] < TRAIN_END).to_numpy()
            if tr.sum() < 10_000:
                log(f"{name} : trop peu de bougies d'apprentissage -- ignoré")
                continue
            mu = X[tr].mean(0)
            sd = X[tr].std(0) + 1e-8
            X = np.clip((X - mu) / sd, -Z_SCORE_CLIP, Z_SCORE_CLIP)
            if mirror and neutral_idx:
                X[:, neutral_idx] = 0.0
            X.astype(np.float16).tofile(fx)
            np.savez(os.path.join(OUT, f"raw_{len(metas)}.npz"), time=raw["time"].to_numpy().astype("datetime64[m]"),
                     **{c: raw[c].to_numpy(np.float64) for c in ["open", "high", "low", "close", "atr"]})
            metas.append({"name": name, "start": total, "n": len(raw), "mirror": mirror,
                          "first": str(raw["time"].iloc[0]), "last": str(raw["time"].iloc[-1])})
            total += len(raw)
            log(f"{name} : {len(raw)} bougies ({metas[-1]['first'][:10]} -> {metas[-1]['last'][:10]}) "
                f"en {time.time() - t0:.0f} s")
            del raw, X
            gc.collect()
    json.dump({"markets": metas, "total": total, "n_features": len(cols)},
              open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8"), indent=1)


# ----------------------------------------------------------------------------- étiquettes
def labels(o, h, l, c, atr, k, cost_rel):
    """Résultat en R d'un achat et d'une vente à l'ouverture suivante (stop k x ATR, objectif 2 x stop)."""
    n = len(c)
    Rl, Rs = np.full(n, np.nan), np.full(n, np.nan)
    El, Es = np.zeros(n, np.int32), np.zeros(n, np.int32)
    t = np.arange(n - H - 1)
    entry = o[t + 1]
    risk = k * atr[t]
    ok = np.isfinite(risk) & (risk > 0) & np.isfinite(entry)
    t, entry, risk = t[ok], entry[ok], risk[ok]
    cost = cost_rel * entry / risk
    for side in (1, -1):
        stop, tp = entry - side * risk, entry + side * 2 * risk
        R = np.full(len(t), np.nan)
        E = np.full(len(t), H, np.int32)
        done = np.zeros(len(t), bool)
        for j in range(1, H + 1):
            idx = t + j
            hit_sl = (l[idx] <= stop) if side == 1 else (h[idx] >= stop)
            hit_tp = (h[idx] >= tp) if side == 1 else (l[idx] <= tp)
            new = ~done & (hit_sl | hit_tp)
            R[new & hit_sl] = -1.0
            R[new & ~hit_sl & hit_tp] = 2.0
            E[new] = j
            done |= new
        R[~done] = np.clip(side * (c[t[~done] + H] - entry[~done]) / risk[~done], -1.0, 2.0)
        R -= cost
        if side == 1:
            Rl[t], El[t] = R, E
        else:
            Rs[t], Es[t] = R, E
    return Rl, Rs, El, Es


# ----------------------------------------------------------------------------- réseau
def make_net(n_features, hidden=128, dropout=0.1):
    import torch.nn as nn

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.gru = nn.GRU(n_features, hidden, batch_first=True)
            self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(hidden + n_features, hidden), nn.ReLU(),
                                      nn.Dropout(dropout), nn.Linear(hidden, 2))

        def forward(self, x):
            _, hN = self.gru(x)
            return self.head(torch_cat(hN[-1], x[:, -1]))
    return Net()


def torch_cat(a, b):
    import torch
    return torch.cat([a, b], dim=1)


def batches(X, idx, bs):
    off = np.arange(-W + 1, 1)
    for a in range(0, len(idx), bs):
        b = idx[a:a + bs]
        yield b, np.asarray(X[b[:, None] + off[None, :]], dtype=np.float32)


def predict(net, X, idx, dev, bs=2048):
    """`net` : un réseau ou une liste (vote : moyenne des prédictions)."""
    import torch
    nets = net if isinstance(net, list) else [net]
    for n_ in nets:
        n_.eval()
    out = np.zeros((len(idx), 2), np.float32)
    with torch.no_grad():
        for k_, (b, xb) in enumerate(batches(X, idx, bs)):
            xt = torch.as_tensor(xb, device=dev)
            out[k_ * bs:k_ * bs + len(b)] = np.mean([n_(xt).float().cpu().numpy() for n_ in nets], axis=0)
    return out


# ----------------------------------------------------------------------------- simulation
def simulate(times, pl, ps, Rl, Rs, El, Es, tau, sides=("long", "short")):
    """Trades sans chevauchement sur un marché : on prend le côté le plus favorable s'il dépasse le seuil."""
    trades, i, n = [], 0, len(times)
    while i < n:
        best, side = -9.0, 0
        if "long" in sides and pl[i] > tau and np.isfinite(Rl[i]):
            best, side = pl[i], 1
        if "short" in sides and ps[i] > tau and ps[i] > best and np.isfinite(Rs[i]):
            side = -1
        if side == 0:
            i += 1
            continue
        R, e = (Rl[i], El[i]) if side == 1 else (Rs[i], Es[i])
        trades.append((times[min(n - 1, i + e)], float(R), side))
        i += e + 1
    return trades


def summarize(trades, start, end):
    from src.ftmo_metrics import prop_firm_summary
    if not trades:
        return {"n": 0}
    R = np.array([t[1] for t in trades])
    sides = np.array([t[2] for t in trades])
    days = pd.bdate_range(start, end)
    daily = pd.Series(0.0, index=days)
    for t, r, _ in trades:
        d = pd.Timestamp(t).normalize()
        if d in daily.index:
            daily[d] += r * RISK
    pf = prop_firm_summary(daily.to_numpy(), n_sims=1000)
    out = {"n": int(len(R)), "R_moyen": float(R.mean()), "gagnants": float((R > 0).mean()),
           "t_stat": float(R.mean() / (R.std() + 1e-9) * np.sqrt(len(R))),
           "achats": int((sides == 1).sum()), "ventes": int((sides == -1).sum()),
           "R_achats": float(R[sides == 1].mean()) if (sides == 1).any() else None,
           "R_ventes": float(R[sides == -1].mean()) if (sides == -1).any() else None,
           "mois_median": pf.get("monthly_median"), "baisse_max": pf.get("max_drawdown"),
           "challenge_ftmo": pf.get("challenge_pass"), "verification_ftmo": pf.get("verification_pass"),
           "rendement_total": pf.get("total_return")}
    return out


# ----------------------------------------------------------------------------- principal
def main():
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=float, default=2.0)
    ap.add_argument("--h", type=int, default=96, help="horizon en bougies M15")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--hidden", type=int, default=128)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--noise", type=float, default=0.0)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--ensemble", type=int, default=1)
    ap.add_argument("--tag", default="")
    ap.add_argument("--load", action="store_true", help="réutilise les cerveaux sauvegardés (pas de réentraînement)")
    a = ap.parse_args()
    global H
    H = a.h
    torch.set_num_threads(3)
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    meta = json.load(open(os.path.join("models", "champion_AUREXIS", "meta.json"), encoding="utf-8"))
    cols, ctx = meta["feature_columns"], meta["context_timeframes"]
    from src.lockbox_gate import resolve_lockbox_start
    LOCK = resolve_lockbox_start(cfg)
    VAL_END = LOCK - pd.Timedelta(hours=48)
    VAL_MID = TRAIN_END + (VAL_END - TRAIN_END) / 2
    if a.rebuild or not os.path.exists(os.path.join(OUT, "meta.json")):
        log("construction des données (un marché à la fois)...")
        build_dataset(cfg, cols, ctx)
    dm = json.load(open(os.path.join(OUT, "meta.json"), encoding="utf-8"))
    F = dm["n_features"]
    X = np.memmap(os.path.join(OUT, "X.f16"), dtype=np.float16, mode="r", shape=(dm["total"], F))

    # étiquettes + index par période
    log(f"étiquettes (stop {a.k} x ATR, objectif 2 x stop, {H / 4:.0f} h)...")
    per = []
    tr_idx, va_idx = [], []
    for mi, mk in enumerate(dm["markets"]):
        r = np.load(os.path.join(OUT, f"raw_{mi}.npz"))
        cost_rel = 0.0002 if mk["name"].startswith("XAUUSD") else 0.0001
        Rl, Rs, El, Es = labels(r["open"], r["high"], r["low"], r["close"], r["atr"], a.k, cost_rel)
        times = pd.to_datetime(r["time"])
        ok = np.isfinite(Rl) & np.isfinite(Rs)
        ok[:W] = False
        g = mk["start"] + np.arange(mk["n"])
        tr = ok & (times < TRAIN_END - pd.Timedelta(hours=48))
        va = ok & (times >= TRAIN_END) & (times < VAL_MID)      # arrêt de l'apprentissage : moitié A seulement
        per.append({"mk": mk, "times": times, "Rl": Rl, "Rs": Rs, "El": El, "Es": Es, "g": g, "ok": ok})
        tr_idx.append(g[tr][::2])
        va_idx.append(g[va])
        log(f"  {mk['name']:14s} apprentissage {tr.sum():7d} | validation {va.sum():6d} | "
            f"achat toujours {np.nanmean(Rl[tr]):+.3f} R, vente toujours {np.nanmean(Rs[tr]):+.3f} R")
    tr_idx = np.concatenate(tr_idx)
    va_all = np.concatenate(va_idx)
    Y = np.full((dm["total"], 2), np.nan, np.float32)
    for p in per:
        Y[p["g"], 0], Y[p["g"], 1] = p["Rl"], p["Rs"]

    # apprentissage
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    loss_fn = torch.nn.HuberLoss(delta=1.0)
    rng = np.random.default_rng(0)
    va_s = rng.choice(va_all, min(150_000, len(va_all)), replace=False)

    def train_one(seed):
        torch.manual_seed(seed)
        r_ = np.random.default_rng(seed)
        net = make_net(F, a.hidden, a.dropout).to(dev)
        opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-3)
        best, best_state, patience = 1e9, None, 0
        for ep in range(a.epochs):
            net.train()
            perm = r_.permutation(tr_idx)
            t0, tot = time.time(), 0.0
            for k_, (b, xb) in enumerate(batches(X, perm, 1024)):
                xb = torch.as_tensor(xb, device=dev)
                if a.noise > 0:
                    xb = xb + a.noise * torch.randn_like(xb)
                yb = torch.as_tensor(Y[b], device=dev)
                loss = loss_fn(net(xb), yb)
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                opt.step()
                tot += float(loss)
            pv = predict(net, X, va_s, dev)
            d = np.abs(pv - Y[va_s])
            vloss = float(np.mean(np.where(d < 1, 0.5 * d ** 2, d - 0.5)))
            corr_l = float(np.corrcoef(pv[:, 0], Y[va_s, 0])[0, 1])
            corr_s = float(np.corrcoef(pv[:, 1], Y[va_s, 1])[0, 1])
            log(f"  cerveau {seed} passe {ep + 1} : erreur apprentissage {tot / (k_ + 1):.4f} | validation {vloss:.4f} | "
                f"lien prédiction/réalité achat {corr_l:+.3f} vente {corr_s:+.3f} ({time.time() - t0:.0f} s)")
            if vloss < best - 1e-4:
                best, patience = vloss, 0
                best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
            else:
                patience += 1
                if patience >= 2:
                    break
        net.load_state_dict(best_state)
        return net, best_state

    log(f"apprentissage sur {len(tr_idx)} exemples ({dev}), contrôle sur {len(va_s)}, {a.ensemble} cerveau(x)")
    if a.load:
        states = torch.load(os.path.join("models", "moteur_prediction", f"net{a.tag}.pt"))
        states = states if isinstance(states, list) else [states]
        trained = []
        for s_ in states:
            n_ = make_net(F, a.hidden, a.dropout).to(dev)
            n_.load_state_dict(s_)
            trained.append((n_, s_))
        log(f"{len(trained)} cerveau(x) rechargé(s)")
    else:
        trained = [train_one(s) for s in range(a.ensemble)]
    net = [n_ for n_, _ in trained]
    pv = predict(net, X, va_s, dev)
    log(f"vote des {len(net)} cerveaux : lien prédiction/réalité achat {np.corrcoef(pv[:, 0], Y[va_s, 0])[0, 1]:+.3f} "
        f"vente {np.corrcoef(pv[:, 1], Y[va_s, 1])[0, 1]:+.3f}")
    best_state = [s for _, s in trained]
    os.makedirs(os.path.join("models", "moteur_prediction"), exist_ok=True)
    torch.save(best_state, os.path.join("models", "moteur_prediction", f"net{a.tag}.pt"))

    # validation : choix du seuil sur la moitié A (marchés réels), jugement sur la moitié B
    pred_cache = {}

    def run(period_lo, period_hi, tau, real_only):
        res, alltr = {}, []
        for p in per:
            if real_only and p["mk"]["mirror"]:
                continue
            m = p["ok"] & (p["times"] >= period_lo) & (p["times"] < period_hi)
            if m.sum() < 1000:
                continue
            idx = np.where(m)[0]
            key = (p["mk"]["name"], str(period_lo), str(period_hi))
            if key not in pred_cache:
                pred_cache[key] = predict(net, X, p["g"][idx], dev)
            pr = pred_cache[key]
            trades = simulate(p["times"][idx], pr[:, 0], pr[:, 1], p["Rl"][idx], p["Rs"][idx],
                              p["El"][idx], p["Es"][idx], tau)
            res[p["mk"]["name"]] = summarize(trades, period_lo, period_hi)
            res[p["mk"]["name"]].update(toujours_acheter=float(np.nanmean(p["Rl"][idx])),
                                        toujours_vendre=float(np.nanmean(p["Rs"][idx])))
            if not p["mk"]["mirror"]:
                alltr += trades
        res["ENSEMBLE (marchés réels)"] = summarize(sorted(alltr), period_lo, period_hi)
        return res

    # SEUILS RELATIFS (08/10) : le réseau prédit un résultat moyen légèrement négatif partout (coûts) ; on trade
    # ses MEILLEURES situations : seuils = quantiles de sa meilleure prédiction (achat ou vente) sur la validation A.
    best_pred = np.maximum(pv[:, 0], pv[:, 1])
    quantiles = [0.80, 0.90, 0.95, 0.98, 0.99, 0.995]
    taus = [float(np.quantile(best_pred, q)) for q in quantiles]
    log("seuils (meilleures situations) : " + ", ".join(f"top {100 * (1 - q):.1f} % = {t_:+.3f}" for q, t_ in zip(quantiles, taus)))
    choice = {}
    for tau in taus:
        s = run(TRAIN_END, VAL_MID, tau, True)["ENSEMBLE (marchés réels)"]
        choice[tau] = s
        log(f"  seuil {tau:+.3f} (validation A) : {s.get('n', 0)} trades, {s.get('R_moyen', 0):+.3f} R/trade, "
            f"t {s.get('t_stat', 0):+.1f}")
    tau = max(taus, key=lambda t: choice[t].get("t_stat", -99) if choice[t].get("n", 0) >= 100 else -99)
    log(f"seuil retenu : {tau}")
    report = {"k_atr": a.k, "seuil": tau, "periodes": {"apprentissage_fin": str(TRAIN_END.date()),
              "validation_B": [str(VAL_MID.date()), str(VAL_END.date())], "sous_cle": str(LOCK.date())},
              "choix_seuil": {str(k): v for k, v in choice.items()},
              "validation_B": run(VAL_MID, VAL_END, tau, False)}
    log("validation B (jamais utilisée pour régler) :")
    for k_, v in report["validation_B"].items():
        log(f"  {k_:26s} {v.get('n', 0):5d} trades | {v.get('R_moyen', 0):+.3f} R | achats {v.get('achats', 0)} "
            f"({(v.get('R_achats') or 0):+.3f}) ventes {v.get('ventes', 0)} ({(v.get('R_ventes') or 0):+.3f})")
    # jeu sous clé : une seule fois
    report["sous_cle"] = run(LOCK, pd.Timestamp.now(), tau, False)
    log("JEU SOUS CLÉ (06/2023 -> aujourd'hui, regardé une seule fois) :")
    for k_, v in report["sous_cle"].items():
        log(f"  {k_:26s} {v.get('n', 0):5d} trades | {v.get('R_moyen', 0):+.3f} R | gagnants {v.get('gagnants', 0):.0%} | "
            f"achats {v.get('achats', 0)} ventes {v.get('ventes', 0)} | mois médian {(v.get('mois_median') or 0):+.2%} | "
            f"baisse max {(v.get('baisse_max') or 0):.1%} | challenge FTMO {(v.get('challenge_ftmo') or 0):.0%} | "
            f"repère toujours acheter {(v.get('toujours_acheter') or 0):+.3f} R / vendre {(v.get('toujours_vendre') or 0):+.3f} R")
    report["reglages"] = vars(a)
    json.dump(report, open(os.path.join("reports", f"moteur_prediction{a.tag}.json"), "w", encoding="utf-8"),
              indent=1, default=str)
    log("TERMINÉ")


if __name__ == "__main__":
    main()

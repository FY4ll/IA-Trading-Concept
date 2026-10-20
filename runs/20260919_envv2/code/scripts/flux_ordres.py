"""
FLUX DES ORDRES (08/10/2026) -- ÉTUDE : l'information des COTATIONS (chaque changement de prix acheteur/vendeur,
avec les volumes disponibles des deux côtés -- source gratuite Dukascopy) prédit-elle le mouvement suivant de l'or
mieux que les bougies ? Ne touche à rien de ce qui tourne.

1. Télécharge les cotations heure par heure (reprise automatique, cache data/flux_ordres/<SYM>/<AAAA-MM-JJ>.npz).
2. Fabrique, par bougie de 15 min, des mesures du flux : déséquilibre acheteurs/vendeurs (règle du tick et
   volumes affichés), déséquilibre du carnet (volume au prix vendeur vs acheteur), flux d'ordres de Cont
   (variation des volumes aux meilleurs prix), activité, écart de prix acheteur/vendeur, volatilité réalisée.
3. Mesure le LIEN (corrélation de rang) entre chaque mesure et le mouvement des 15 min / 1 h / 4 h suivantes,
   sur une période de DÉCOUVERTE puis sur une période de CONFIRMATION différente ; mêmes mesures pour des
   indicateurs de bougies classiques (repère). Un vrai signal doit garder le même sens et rester net sur les deux.

    python scripts/flux_ordres.py --sym XAUUSD --discover 2022-01-03 2022-03-31 --confirm 2022-04-01 2022-06-30
Écrit reports/flux_ordres_<SYM>.json.
"""
import argparse, json, lzma, os, struct, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import requests

POINT = {"XAUUSD": 1e-3, "EURUSD": 1e-5, "USDJPY": 1e-3, "GBPUSD": 1e-5, "USA500IDXUSD": 1e-3}
CACHE = os.path.join("data", "flux_ordres")
_s = requests.Session()
_s.headers["User-Agent"] = "Mozilla/5.0"


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def fetch_hour(sym, d, h, tries=6):
    url = f"https://datafeed.dukascopy.com/datafeed/{sym}/{d.year:04d}/{d.month - 1:02d}/{d.day:02d}/{h:02d}h_ticks.bi5"
    for k in range(tries):
        try:
            r = _s.get(url, timeout=60)
            if r.status_code == 404 or (r.status_code == 200 and not r.content):
                return np.zeros((0, 5))
            if r.status_code != 200:
                raise IOError(f"HTTP {r.status_code}")
            raw = lzma.decompress(r.content)
            n = len(raw) // 20
            a = np.frombuffer(raw[:n * 20], dtype=np.dtype([("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"),
                                                            ("av", ">f4"), ("bv", ">f4")]))
            p = POINT.get(sym, 1e-3)
            t = (pd.Timestamp(d).value // 10**6 + h * 3_600_000 + a["ms"].astype(np.int64))
            return np.column_stack([t, a["ask"] * p, a["bid"] * p, a["av"], a["bv"]]).astype(np.float64)
        except Exception:
            time.sleep(5 * (k + 1))
    return None


def fetch_day(sym, d):
    path = os.path.join(CACHE, sym, f"{d}.npz")
    if os.path.exists(path):
        return np.load(path)["t"]
    hours = [fetch_hour(sym, d, h) for h in range(24)]
    if any(x is None for x in hours):
        return None                                   # jour incomplet : pas mis en cache, retenté plus tard
    t = np.concatenate(hours) if hours else np.zeros((0, 5))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, t=t)
    return t


def ticks(sym, start, end):
    days = [d for d in pd.date_range(start, end).date if d.weekday() != 5]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(lambda d: fetch_day(sym, d), days))
    for _ in range(2):                                # rattrapage des jours refusés
        miss = [i for i, r in enumerate(res) if r is None]
        if not miss:
            break
        time.sleep(30)
        for i in miss:
            res[i] = fetch_day(sym, days[i])
    miss = [str(days[i]) for i, r in enumerate(res) if r is None]
    arr = np.concatenate([r for r in res if r is not None and len(r)])
    log(f"{sym} {start} -> {end} : {len(arr):,} cotations en {(time.time() - t0) / 60:.1f} min"
        f"{' -- jours manquants ' + str(miss) if miss else ''}")
    return arr


# ----------------------------------------------------------------------------- mesures par bougie de 15 min
def bars(arr):
    df = pd.DataFrame(arr, columns=["t", "ask", "bid", "av", "bv"])
    df["time"] = pd.to_datetime(df["t"].astype(np.int64), unit="ms")
    df = df.sort_values("time").reset_index(drop=True)
    mid = (df["ask"] + df["bid"]) / 2
    dmid = mid.diff().fillna(0.0)
    df["sign"] = np.sign(dmid)                         # règle du tick : hausse = pression acheteuse
    df["sign"] = df["sign"].replace(0, np.nan).ffill().fillna(0.0)
    df["spread"] = (df["ask"] - df["bid"]) / mid
    db, da = df["bid"].diff(), df["ask"].diff()
    bv, av, bv0, av0 = df["bv"], df["av"], df["bv"].shift(), df["av"].shift()
    # flux d'ordres de Cont, Kukanov & Stoikov (2014) aux meilleurs prix
    df["ofi"] = ((db >= 0) * bv - (db <= 0) * bv0 - (da <= 0) * av + (da >= 0) * av0).fillna(0.0)
    df["depth_imb"] = (df["bv"] - df["av"]) / (df["bv"] + df["av"] + 1e-9)
    df["lr"] = np.log(mid).diff().fillna(0.0)
    df["vol_signed"] = df["sign"] * (df["av"] + df["bv"]) / 2
    df["vol"] = (df["av"] + df["bv"]) / 2
    g = df.set_index("time").resample("15min", label="left", closed="left")
    b = pd.DataFrame({
        "mid": g["ask"].last().add(g["bid"].last()) / 2,
        "n_ticks": g["sign"].count(),
        "tick_imb": g["sign"].mean(),
        "vol_imb": g["vol_signed"].sum() / (g["vol"].sum() + 1e-9),
        "ofi": g["ofi"].sum(),
        "depth_imb": g["depth_imb"].mean(),
        "spread": g["spread"].mean(),
        "spread_max": g["spread"].max(),
        "rv": np.sqrt((df.set_index("time")["lr"] ** 2).resample("15min", label="left", closed="left").sum()),
    })
    b = b[b["n_ticks"] > 20].copy()
    b["ret"] = np.log(b["mid"]).diff()
    # normalisations causales (fenêtre glissante de 96 bougies = 24 h)
    roll = lambda s: s.rolling(96, min_periods=24)
    b["ofi_z"] = b["ofi"] / (roll(b["ofi"].abs()).mean() + 1e-9)
    b["activite"] = np.log(b["n_ticks"] / roll(b["n_ticks"]).mean())
    b["ecart_rel"] = b["spread"] / roll(b["spread"]).median() - 1
    b["ecart_pic"] = b["spread_max"] / roll(b["spread"]).median() - 1
    b["vol_rel"] = b["rv"] / roll(b["rv"]).mean() - 1
    b["ofi_4"] = b["ofi_z"].rolling(4).sum()
    b["tick_imb_4"] = b["tick_imb"].rolling(4).mean()
    b["depth_imb_4"] = b["depth_imb"].rolling(4).mean()
    b["flux_x_activite"] = b["ofi_z"] * np.exp(b["activite"].clip(-3, 3))
    # repères « bougies » classiques
    b["rep_ret_1"] = b["ret"]
    b["rep_ret_4"] = np.log(b["mid"]).diff(4)
    b["rep_ret_16"] = np.log(b["mid"]).diff(16)
    for hz in (1, 4, 16):
        b[f"fut_{hz}"] = np.log(b["mid"]).shift(-hz) - np.log(b["mid"])
    return b


FLUX = ["tick_imb", "vol_imb", "ofi_z", "depth_imb", "activite", "ecart_rel", "ecart_pic", "vol_rel",
        "ofi_4", "tick_imb_4", "depth_imb_4", "flux_x_activite"]
REPERES = ["rep_ret_1", "rep_ret_4", "rep_ret_16"]


def ic_table(b):
    out = {}
    for f in FLUX + REPERES:
        row = {}
        for hz in (1, 4, 16):
            d = b[[f, f"fut_{hz}"]].dropna().iloc[::hz]          # sans chevauchement
            if len(d) < 200:
                continue
            ic = float(d[f].rank().corr(d[f"fut_{hz}"].rank()))
            row[f"{hz}"] = {"lien": ic, "t": ic * np.sqrt(len(d)), "n": len(d)}
        out[f] = row
    return out


def model_test(bd, bc):
    """Petit modèle linéaire (moindres carrés régularisés) appris sur la découverte, jugé sur la confirmation."""
    res = {}
    for hz in (1, 4, 16):
        cols = FLUX + REPERES
        A = bd[cols + [f"fut_{hz}"]].dropna()
        C = bc[cols + [f"fut_{hz}"]].dropna()
        mu, sd = A[cols].mean(), A[cols].std() + 1e-12
        Xa, Xc = ((A[cols] - mu) / sd).clip(-5, 5).to_numpy(), ((C[cols] - mu) / sd).clip(-5, 5).to_numpy()
        ya = A[f"fut_{hz}"].to_numpy() / A[f"fut_{hz}"].std()
        w = np.linalg.solve(Xa.T @ Xa + 50 * len(cols) * np.eye(len(cols)), Xa.T @ ya)
        pc = Xc @ w
        Cn = C.iloc[::hz]
        pcn = pc[::hz]
        ic = float(pd.Series(pcn).rank().corr(pd.Series(Cn[f"fut_{hz}"].to_numpy()).rank()))
        # rendement d'une règle simple : suivre le signe de la prédiction (coût 0,02 % par position)
        pos = np.sign(pcn)
        gain = pos * Cn[f"fut_{hz}"].to_numpy() - 0.0002 * (np.abs(np.diff(np.concatenate([[0], pos]))))
        res[f"{hz}"] = {"lien_confirmation": ic, "t": ic * np.sqrt(len(Cn)), "n": len(Cn),
                        "gain_moyen_pct": float(gain.mean() * 100), "gain_total_pct": float(gain.sum() * 100),
                        "poids": dict(zip(cols, map(float, w)))}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sym", default="XAUUSD")
    ap.add_argument("--discover", nargs=2, default=["2022-01-03", "2022-03-31"])
    ap.add_argument("--confirm", nargs=2, default=["2022-04-01", "2022-06-30"])
    a = ap.parse_args()
    bd = bars(ticks(a.sym, *a.discover))
    bc = bars(ticks(a.sym, *a.confirm))
    log(f"bougies : découverte {len(bd)}, confirmation {len(bc)}")
    icd, icc = ic_table(bd), ic_table(bc)
    log("LIEN avec le mouvement suivant (corrélation de rang ; t > 2 = net)   découverte | confirmation")
    for f in FLUX + REPERES:
        parts = []
        for hz in ("1", "4", "16"):
            d, c = icd.get(f, {}).get(hz), icc.get(f, {}).get(hz)
            if d and c:
                same = "=" if np.sign(d["lien"]) == np.sign(c["lien"]) else "x"
                parts.append(f"{int(hz) * 15:4d} min : {d['lien']:+.3f} (t {d['t']:+.1f}) | {c['lien']:+.3f} (t {c['t']:+.1f}) {same}")
        log(f"  {f:16s} " + "  ||  ".join(parts))
    mt = model_test(bd, bc)
    log("MODÈLE appris sur la découverte, jugé sur la confirmation :")
    for hz, r in mt.items():
        log(f"  horizon {int(hz) * 15} min : lien {r['lien_confirmation']:+.3f} (t {r['t']:+.1f}, {r['n']} cas) | "
            f"gain moyen {r['gain_moyen_pct']:+.4f} % par position, total {r['gain_total_pct']:+.2f} % (coûts déduits)")
    json.dump({"sym": a.sym, "decouverte": a.discover, "confirmation": a.confirm, "lien_decouverte": icd,
               "lien_confirmation": icc, "modele": mt},
              open(os.path.join("reports", f"flux_ordres_{a.sym}.json"), "w", encoding="utf-8"), indent=1)
    log("TERMINÉ")


if __name__ == "__main__":
    main()

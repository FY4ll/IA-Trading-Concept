"""
JUGE DE SETUPS (06/10/2026) -- recherche, lecture seule.

Chaque heure du passé, on simule des setups long ET short (stop 1,5 ou 3 ATR M15, objectif 1,5 ou 2,5 R, entrée à
l'ouverture suivante, horizon 2 jours, stop prioritaire si les deux sont touchés dans la même bougie, coûts inclus)
et on enregistre leur résultat en R. Un modèle (gradient boosting) apprend P(objectif avant stop | contexte).
L'IA ne prend un trade que si l'espérance estimée p x RR - (1 - p) - coût dépasse un seuil choisi sur la validation,
une seule position à la fois.

Test final sur la LOCKBOX (jamais vue), comparé à : tous les setups, et "toujours acheteur" (l'or a doublé).

    python scripts/setup_judge_research.py            (cwd = code/)  -> reports/setup_judge.json
"""
import json, os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np, pandas as pd, yaml
from sklearn.ensemble import HistGradientBoostingClassifier

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--step", type=int, default=4)          # 4 = une décision possible par heure (M15)
_ap.add_argument("--horizon", type=int, default=192)     # 192 = 2 jours de bougies M15
_ap.add_argument("--stops", default="1.5,3.0")           # x ATR M15
_ap.add_argument("--rrs", default="1.5,2.5")
_ap.add_argument("--tag", default="")
ARGS = _ap.parse_args()
STEP, HORIZON = ARGS.step, ARGS.horizon
STOPS = tuple(float(x) for x in ARGS.stops.split(","))
RRS = tuple(float(x) for x in ARGS.rrs.split(","))
EMBARGO = HORIZON + 50


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def label(df, idx, atr, tc):
    """Résultats en R de chaque (bougie, sens, stop, RR) + index de sortie."""
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(df)
    rows = []
    for t in idx:
        if t + 2 >= n or not np.isfinite(atr[t]) or atr[t] <= 0:
            continue
        e = o[t + 1]
        end = min(n, t + 1 + HORIZON)
        hh, ll, cc = h[t + 1:end], l[t + 1:end], c[t + 1:end]
        for m in STOPS:
            risk = m * atr[t]
            cost_r = tc * e / risk
            for d in (1, -1):
                sl = e - d * risk
                sl_hit = (ll <= sl) if d > 0 else (hh >= sl)
                i_sl = int(np.argmax(sl_hit)) if sl_hit.any() else 10 ** 9
                for rr in RRS:
                    tp = e + d * rr * risk
                    tp_hit = (hh >= tp) if d > 0 else (ll <= tp)
                    i_tp = int(np.argmax(tp_hit)) if tp_hit.any() else 10 ** 9
                    if i_sl == 10 ** 9 and i_tp == 10 ** 9:
                        r, win, ex = (cc[-1] - e) * d / risk, 0, len(cc) - 1
                    elif i_sl <= i_tp:
                        r, win, ex = -1.0, 0, i_sl
                    else:
                        r, win, ex = rr, 1, i_tp
                    rows.append((t, d, m, rr, r - cost_r, win, t + 1 + ex, cost_r))
    return pd.DataFrame(rows, columns=["t", "dir", "stop", "rr", "R", "win", "exit_t", "cost_r"])


def build_xy(df, lab, feats):
    X = df[feats].to_numpy(np.float32)[lab["t"].to_numpy()]
    extra = lab[["dir", "stop", "rr"]].to_numpy(np.float32)
    return np.hstack([X, extra])


def simulate(lab, exp_r, thr, times, risk_pcts=(0.0025, 0.005)):
    """Une position à la fois : à chaque heure, le meilleur setup si son espérance > thr."""
    lab = lab.assign(er=exp_r)
    best = lab.sort_values("er", ascending=False).drop_duplicates("t").sort_values("t")
    best = best[best["er"] > thr]
    taken, busy_until = [], -1
    for r in best.itertuples():
        if r.t <= busy_until:
            continue
        taken.append(r)
        busy_until = r.exit_t
    tr = pd.DataFrame(taken)
    out = {"n_trades": int(len(tr))}
    if not len(tr):
        return out, tr
    R = tr["R"].to_numpy()
    out.update(avg_R=float(R.mean()), win_rate=float((R > 0).mean()), long_share=float((tr["dir"] > 0).mean()),
               sum_R=float(R.sum()))
    thirds = np.array_split(R, 3)
    out["thirds_avg_R"] = [float(x.mean()) if len(x) else None for x in thirds]
    from src.ftmo_metrics import prop_firm_summary
    days = pd.to_datetime(times[tr["exit_t"].clip(upper=len(times) - 1).to_numpy()]).normalize()
    months = max(1.0, (pd.to_datetime(times[-1]) - pd.to_datetime(times[0])).days / 30.4)
    for rp in risk_pcts:
        eq = np.cumprod(1 + rp * R)
        dd = float(-(eq / np.maximum.accumulate(eq) - 1).min())
        daily = pd.Series(rp * R, index=days).groupby(level=0).sum()
        all_days = pd.bdate_range(days.min(), days.max())
        daily = daily.reindex(all_days, fill_value=0.0)
        out[f"risk_{rp}"] = {"return": float(eq[-1] - 1), "monthly": float(eq[-1] ** (1 / months) - 1),
                             "max_dd": dd, "worst_day": float(daily.min()),
                             "ftmo_challenge": prop_firm_summary(daily.to_numpy()).get("challenge_pass")}
    return out, tr


def main():
    from src.lockbox_gate import build_eval_frames
    from src.trading_env import TradingEnv
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    meta = json.load(open("models/champion_AUREX/meta.json", encoding="utf-8"))
    tc = float(cfg["environment"]["transaction_cost"])
    t0 = time.time()
    vis, lock, start = build_eval_frames("AUREX", cfg, meta)
    vis, lock = vis.reset_index(drop=True), lock.reset_index(drop=True)
    log(f"données : visible {len(vis)} bougies, lockbox {len(lock)} (depuis {start.date()}) {time.time() - t0:.0f}s")

    feats = [f for f in meta["feature_columns"] if f in vis.columns]
    corr = vis[feats + ["close"]].iloc[::20].corr(method="spearman")["close"].abs()
    drift = [f for f in feats if corr.get(f, 0) > 0.6]
    feats = [f for f in feats if f not in drift]
    log(f"variables : {len(feats)} (retirées car liées au niveau du prix : {drift})")

    atr_col = TradingEnv.ATR_RAW_COLUMN
    lab_v = label(vis, np.arange(300, len(vis) - 2, STEP), vis[atr_col].to_numpy(float), tc)
    lab_l = label(lock, np.arange(300, len(lock) - 2, STEP), lock[atr_col].to_numpy(float), tc)
    log(f"setups étiquetés : visible {len(lab_v)}, lockbox {len(lab_l)} ; R moyen brut visible "
        f"{lab_v['R'].mean():+.3f}, lockbox {lab_l['R'].mean():+.3f}")

    # 1) validation interne : apprend sur les 70 % anciens, choisit le seuil sur les 30 % récents
    cut = int(len(vis) * 0.7)
    tr_m = lab_v["exit_t"] < cut - EMBARGO
    va_m = lab_v["t"] >= cut
    params = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=400,
                  l2_regularization=1.0, early_stopping=False, random_state=0)
    clf = HistGradientBoostingClassifier(**params).fit(build_xy(vis, lab_v[tr_m], feats), lab_v.loc[tr_m, "win"])
    lv = lab_v[va_m].reset_index(drop=True)
    p = clf.predict_proba(build_xy(vis, lv, feats))[:, 1]
    er = p * lv["rr"] - (1 - p) - lv["cost_r"]
    vt = vis["time"].to_numpy()
    grid = {}
    for thr in (0.0, 0.05, 0.1, 0.15, 0.2, 0.3):
        res, _ = simulate(lv, er.to_numpy(), thr, vt)
        grid[thr] = res
        log(f"validation seuil {thr:.2f} : {res.get('n_trades')} trades, R moyen {res.get('avg_R', float('nan')):+.3f}, "
            f"tiers {res.get('thirds_avg_R')}")
    ok = {k: v for k, v in grid.items() if v.get("n_trades", 0) >= 150 and v.get("avg_R", -1) > 0}
    thr = max(ok, key=lambda k: ok[k]["avg_R"] * np.sqrt(ok[k]["n_trades"])) if ok else 0.1
    log(f"seuil retenu : {thr}")

    # 2) test final lockbox : apprend sur tout le visible, jamais touché la lockbox
    full_m = lab_v["exit_t"] < len(vis) - EMBARGO
    clf2 = HistGradientBoostingClassifier(**params).fit(build_xy(vis, lab_v[full_m], feats), lab_v.loc[full_m, "win"])
    p2 = clf2.predict_proba(build_xy(lock, lab_l, feats))[:, 1]
    er2 = (p2 * lab_l["rr"] - (1 - p2) - lab_l["cost_r"]).to_numpy()
    lt = lock["time"].to_numpy()
    res_judge, trades = simulate(lab_l, er2, thr, lt)
    # références : tous les setups (sans juge), et toujours acheteur (meilleure config long, connue a posteriori)
    res_all, _ = simulate(lab_l, np.zeros(len(lab_l)) + np.random.default_rng(0).random(len(lab_l)) * 1e-6, -1.0, lt)
    longs = {}
    for m in STOPS:
        for rr in RRS:
            sel = (lab_l["dir"] > 0) & (lab_l["stop"] == m) & (lab_l["rr"] == rr)
            r_, _ = simulate(lab_l[sel], np.ones(sel.sum()), 0.0, lt)
            longs[f"long_{m}atr_{rr}R"] = r_
    best_long = max(longs.items(), key=lambda kv: kv[1].get("avg_R", -9))
    judge_long_only = trades[trades["dir"] > 0]["R"].mean() if len(trades) else None
    judge_short_only = trades[trades["dir"] < 0]["R"].mean() if len(trades) else None
    out = {"lockbox_start": str(start.date()), "threshold": thr, "features": feats, "dropped_drift": drift,
           "validation_grid": {str(k): v for k, v in grid.items()}, "lockbox_judge": res_judge,
           "lockbox_judge_long_avgR": judge_long_only, "lockbox_judge_short_avgR": judge_short_only,
           "lockbox_all_setups": res_all, "lockbox_always_long_best": {best_long[0]: best_long[1]},
           "lockbox_always_long": longs}
    os.makedirs("reports", exist_ok=True)
    json.dump(out, open(f"reports/setup_judge{ARGS.tag}.json", "w", encoding="utf-8"), indent=1, default=str)
    log("LOCKBOX juge :", json.dumps(res_judge, default=str))
    log("LOCKBOX juge longs / shorts R moyen :", judge_long_only, judge_short_only)
    log("LOCKBOX sans juge :", json.dumps(res_all, default=str))
    log("LOCKBOX toujours acheteur (meilleure config) :", best_long[0], json.dumps(best_long[1], default=str))
    log(f"total {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

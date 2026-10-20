"""
Recherche du CERVEAU DE MARCHÉ (src/market_brain.py) -- validation honnête, configurations
et règle de décision fixées AVANT les résultats.

    python scripts/brain_research.py            (cwd = code/)

Walk-forward annuel (fenêtre croissante, purge de l'horizon), deux périodes rapportées
séparément : 2012 -> 2023-04 ("avant lockbox") et 2023-05 -> aujourd'hui ("lockbox").
Comparaison à volatilité égale (10 %/an) avec : achat permanent, SMA20/50, SMA50/200, momentum 60 j.
Règle VALIDÉ : sur les DEUX périodes, AUC > 0.5 et Sharpe >= achat permanent et >= SMA20/50.
Écrit reports/brain_research.md/json et enregistre chaque configuration comme expérience.
"""
import json, os, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import yaml

from src import market_brain as mb
from src import research_engine as re_

HORIZON = 10
LOCKBOX = pd.Timestamp("2023-05-01")
SETS = {"technique": mb.TECH_FEATURES, "macro+marchés": mb.MACRO_FEATURES + mb.CROSS_FEATURES,
        "tout": mb.TECH_FEATURES + mb.MACRO_FEATURES + mb.CROSS_FEATURES}
KINDS = ["logit", "gbm"]


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    m = y.notna() & p.notna()
    return float(roc_auc_score(y[m], p[m])) if m.sum() > 50 and y[m].nunique() == 2 else float("nan")


def brier(y, p):
    m = y.notna() & p.notna()
    return float(((p[m] - y[m]) ** 2).mean()), float(((y[m].mean() - y[m]) ** 2).mean())


def split(s: pd.Series, start, end=None):
    s = s[s.index >= start]
    return s[s.index < end] if end is not None else s


def main():
    t0 = time.time()
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    gold = mb.load_gold_daily(cfg)
    gold = gold[gold.index < gold.index.max()]          # la bougie du jour est incomplète
    state = mb.add_target(mb.build_daily_state(gold, mb.load_fred(), mb.load_cross(cfg)), HORIZON)
    close = state["close"]
    start = pd.Timestamp("2012-01-01")
    periods = {"avant_lockbox": (start, LOCKBOX), "lockbox": (LOCKBOX, None)}

    base_pos = {
        "achat_permanent": pd.Series(1.0, index=close.index),
        "sma20_50": np.sign(close.rolling(20).mean() - close.rolling(50).mean()),
        "sma50_200_long": (close.rolling(50).mean() > close.rolling(200).mean()).astype(float),
        "momentum_60j": np.sign(close.pct_change(60)),
    }
    res = {"horizon": HORIZON, "baselines": {}, "configs": {}}
    for name, pos in base_pos.items():
        r = mb.backtest_daily(close, pos)
        res["baselines"][name] = {p: mb.perf(split(r, a, b)) for p, (a, b) in periods.items()}

    for set_name, feats in SETS.items():
        feats = [f for f in feats if f in state.columns]
        for kind in KINDS:
            key = f"{kind}|{set_name}"
            pred = mb.walk_forward(state, feats, kind, HORIZON, first_test_year=2012)
            p = pred["p_up"].reindex(state.index)
            entry = {"features": feats, "periods": {}}
            for per, (a, b) in periods.items():
                pp, yy = split(p, a, b), split(state["y"], a, b)
                bs, bs0 = brier(yy, pp)
                ls = mb.backtest_daily(close, mb.positions_from_proba(p))
                lo = mb.backtest_daily(close, mb.positions_from_proba(p, long_only=True))
                entry["periods"][per] = {"auc": auc(yy, pp), "brier": bs, "brier_base_rate": bs0,
                                         "hit": float(((pp > 0.5) == (yy > 0.5))[yy.notna() & pp.notna()].mean()),
                                         "long_short": mb.perf(split(ls, a, b)),
                                         "long_only": mb.perf(split(lo, a, b))}
            ok_ls = ok_lo = True
            for per in periods:
                e = entry["periods"][per]
                bh = res["baselines"]["achat_permanent"][per]["sharpe"]
                sm = res["baselines"]["sma20_50"][per]["sharpe"]
                good_auc = e["auc"] > 0.5
                ok_ls &= good_auc and e["long_short"]["sharpe"] >= max(bh, sm)
                ok_lo &= good_auc and e["long_only"]["sharpe"] >= max(bh, sm)
            entry["validated_long_short"], entry["validated_long_only"] = bool(ok_ls), bool(ok_lo)
            res["configs"][key] = entry
            re_.record({"kind": "experiment", "style": "BRAIN", "type": "market_brain",
                        "params": {"model": kind, "features": set_name, "horizon": HORIZON},
                        "question": f"Le cerveau ({kind}, moteurs {set_name}) bat-il l'achat permanent et la "
                                    f"tendance SMA20/50 à risque égal, hors échantillon ?",
                        "method": "walk-forward annuel purgé 2012->2023-04 puis lockbox 2023-05->, vol cible 10 %",
                        "decision_rule": "AUC > 0.5 et Sharpe >= max(achat permanent, SMA20/50) sur les 2 périodes",
                        "results": entry["periods"],
                        "conclusion": "VALIDÉ" if (ok_ls or ok_lo) else "REJETÉ"})
            print(f"{key:28s} AUC {entry['periods']['avant_lockbox']['auc']:.3f}/{entry['periods']['lockbox']['auc']:.3f} "
                  f"Sharpe L/S {entry['periods']['avant_lockbox']['long_short']['sharpe']:.2f}/"
                  f"{entry['periods']['lockbox']['long_short']['sharpe']:.2f} "
                  f"L {entry['periods']['avant_lockbox']['long_only']['sharpe']:.2f}/"
                  f"{entry['periods']['lockbox']['long_only']['sharpe']:.2f} "
                  f"-> {'VALIDÉ' if ok_ls or ok_lo else 'rejeté'}", flush=True)

    # thèse du jour (logit, tous moteurs, entraîné sur tout l'historique étiqueté)
    feats = [f for f in SETS["tout"] if f in state.columns]
    train = state[state["y"].notna()]
    m = mb.make_model("logit").fit(train[feats], train["y"])
    today = state.iloc[-1]
    p_today = float(m.predict_proba(today[feats].to_frame().T)[:, 1][0])
    expl = mb.explain_logit(m, today, feats)
    res["today"] = {"date": str(state.index[-1].date()), "p_up": p_today, "explanation": expl,
                    "thesis": mb.thesis_text(p_today, expl, HORIZON)}
    coefs = m.steps[2][1].coef_[0]
    res["learned_drivers"] = sorted(((f, float(c)) for f, c in zip(feats, coefs)), key=lambda t: -abs(t[1]))

    L = [f"# Cerveau de marché : recherche ({time.strftime('%Y-%m-%d %H:%M')}, horizon {HORIZON} j)", "",
         "Vol cible 10 %/an pour toutes les stratégies. Périodes : avant lockbox 2012 -> 2023-04, lockbox 2023-05 -> aujourd'hui.", "",
         "| Stratégie | Sharpe avant | Sharpe lockbox | DD lockbox | Challenge FTMO lockbox |", "|---|---|---|---|---|"]
    for n, b in res["baselines"].items():
        L.append(f"| {n} | {b['avant_lockbox']['sharpe']:.2f} | {b['lockbox']['sharpe']:.2f} | "
                 f"{b['lockbox']['max_drawdown']:.1%} | {b['lockbox']['prop_firm'].get('challenge_pass', 0):.0%} |")
    for k, e in res["configs"].items():
        for mode in ("long_short", "long_only"):
            a, b = e["periods"]["avant_lockbox"][mode], e["periods"]["lockbox"][mode]
            L.append(f"| cerveau {k} {mode} | {a['sharpe']:.2f} | {b['sharpe']:.2f} | {b['max_drawdown']:.1%} | "
                     f"{b['prop_firm'].get('challenge_pass', 0):.0%} |")
    L += ["", "| Config | AUC avant | AUC lockbox | Brier avant (base) | validé L/S | validé long |", "|---|---|---|---|---|---|"]
    for k, e in res["configs"].items():
        a, b = e["periods"]["avant_lockbox"], e["periods"]["lockbox"]
        L.append(f"| {k} | {a['auc']:.3f} | {b['auc']:.3f} | {a['brier']:.4f} ({a['brier_base_rate']:.4f}) | "
                 f"{'oui' if e['validated_long_short'] else 'non'} | {'oui' if e['validated_long_only'] else 'non'} |")
    L += ["", "## Ce que le cerveau a appris (logit, tous moteurs, poids standardisés)", ""]
    L += [f"- {mb.LABELS_FR.get(f, f)} : {c:+.3f}" for f, c in res["learned_drivers"][:12]]
    L += ["", f"## Thèse du {res['today']['date']}", "", res["today"]["thesis"], "",
          f"Durée : {(time.time() - t0) / 60:.1f} min."]
    with open("reports/brain_research.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    with open("reports/brain_research.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

"""
Backtest du TRADER (src/trader/) sur l'or M15, règles d'évaluation fixées AVANT les résultats.

    python scripts/trader_backtest.py [--start 2008-01-01]        (cwd = code/)

  1. Développement 2010-01-01 -> 2023-04-30 : statistiques par setup ; le playbook ne garde que
     les setups à espérance > 0 avec >= 100 trades (apprentissage du trader).
  2. Période jamais vue 2023-05-01 -> aujourd'hui : test UNIQUE du playbook retenu.
     VALIDÉ si >= 100 trades, espérance >= +0,10R, profit factor >= 1,10 (cahier des charges §69).
  3. Stress des coûts (spread x1,5 et x2), probabilité FTMO (risque 0,5 % puis 1 % par trade).
Écrit reports/trader_backtest.md/json, enregistre l'expérience dans le registre de recherche.
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import yaml

from src.trader import chart, playbook, engine
from src.ftmo_metrics import prop_firm_summary
from src import research_engine as re_

DEV = (pd.Timestamp("2010-01-01"), pd.Timestamp("2023-05-01"))
LOCK = (pd.Timestamp("2023-05-01"), None)


def period(t, a, b):
    et = pd.to_datetime(t["entry_time"])
    m = et >= a
    if b is not None:
        m &= et < b
    return t[m]


def fmt(s):
    if not s.get("n"):
        return "0 trade"
    pf = f"{s['profit_factor']:.2f}" if s.get("profit_factor") else "n/a"
    return (f"{s['n']} trades | gain {s['win_rate']:.0%} | {s['avg_R']:+.3f}R/trade | total {s['total_R']:+.1f}R | "
            f"PF {pf} | DD {s['max_dd_R']:.1f}R | t={s['t_stat'] or 0:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2008-01-01")
    args = ap.parse_args()
    t0 = time.time()
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    m15 = chart.load_m15(cfg, args.start)
    m15 = m15[m15.index < m15.index.max().normalize()]          # journée en cours exclue
    ch = chart.build_chart(m15)
    sig = playbook.detect(ch)
    print(f"graphique prêt : {len(ch)} bougies M15, {int((sig['setup'] != '').sum())} signaux bruts "
          f"({(time.time() - t0) / 60:.1f} min)", flush=True)
    trades, skipped = engine.run(ch, sig)
    days = pd.DatetimeIndex(sorted(set(ch.index.normalize())))
    res = {"skipped": skipped, "rules": {k: (list(v) if isinstance(v, tuple) else v) for k, v in engine.RULES.items()}}
    L = [f"# Backtest du trader ({time.strftime('%Y-%m-%d %H:%M')})", "",
         "Or M15, heure serveur, entrée à l'ouverture suivante, spread 0,30 $ + slippage 0,05 $ par jambe, "
         "risque 0,5 % par trade, gestion : moitié à 1R + break-even, stop suiveur M15, sortie avant la fin de journée.", ""]

    dev, lock = period(trades, *DEV), period(trades, *LOCK)
    L.append("## 1. Développement 2010 -> 2023-04 (tous les setups)")
    keep = []
    res["dev"] = {}
    for s in playbook.SETUPS:
        st = engine.stats(dev[dev["setup"] == s]) if len(dev) else {"n": 0}
        res["dev"][s] = st
        ok = st.get("n", 0) >= 100 and st.get("avg_R", -1) > 0
        if ok:
            keep.append(s)
        L.append(f"- **{playbook.NAMES_FR[s]}** : {fmt(st)} -> {'GARDÉ' if ok else 'écarté'}")
    res["dev"]["all"] = engine.stats(dev)
    L.append(f"- tous setups : {fmt(res['dev']['all'])}")
    L.append(f"\nPlaybook retenu : {', '.join(playbook.NAMES_FR[s] for s in keep) or 'AUCUN setup'}")
    res["playbook"] = keep

    L.append("\n## 2. Période jamais vue 2023-05 -> aujourd'hui (test unique du playbook retenu)")
    verdict = "NON VALIDÉ"
    if keep:
        tr_keep, _ = engine.run(ch, sig, enabled=set(keep))
        lk = period(tr_keep, *LOCK)
        st = engine.stats(lk)
        res["lockbox"] = st
        ok = st.get("n", 0) >= 100 and st.get("avg_R", -1) >= 0.10 and (st.get("profit_factor") or 0) >= 1.10
        verdict = "VALIDÉ" if ok else "NON VALIDÉ"
        L.append(f"- playbook retenu : {fmt(st)} -> **{verdict}**")
        for s in keep:
            L.append(f"  - {playbook.NAMES_FR[s]} : {fmt(engine.stats(lk[lk['setup'] == s]))}")
        lock_days = days[days >= LOCK[0]]
        for risk in (0.005, 0.01):
            dr = engine.daily_returns(lk.assign(pct=lk["R"] * risk), lock_days)
            pf = prop_firm_summary(dr.to_numpy(), n_sims=2000)
            res[f"prop_firm_{risk}"] = pf
            L.append(f"- risque {risk:.1%}/trade : rendement {pf.get('total_return', 0):+.1%}, DD {pf.get('max_drawdown', 0):.1%}, "
                     f"pire jour {pf.get('worst_day', 0):+.2%}, médiane mensuelle {pf.get('monthly_median') or 0:+.1%}, "
                     f"Challenge FTMO {pf.get('challenge_pass', 0):.0%}, Vérification {pf.get('verification_pass', 0):.0%}")
        L.append("\n### Stress des coûts (période jamais vue)")
        for mult in (1.5, 2.0):
            tr_s, _ = engine.run(ch, sig, rules={"spread": 0.30 * mult, "slippage": 0.05 * mult}, enabled=set(keep))
            L.append(f"- coûts x{mult:g} : {fmt(engine.stats(period(tr_s, *LOCK)))}")
        L.append("\n### Par année (playbook retenu, toutes périodes)")
        yr = tr_keep.assign(y=pd.to_datetime(tr_keep["entry_time"]).dt.year)
        for y, g in yr.groupby("y"):
            s = engine.stats(g)
            L.append(f"- {y} : {s['n']} trades, {s['avg_R']:+.3f}R/trade, total {s['total_R']:+.1f}R")
        L.append("\n### Exemples de notes du trader (derniers trades)")
        for _, tr in tr_keep.tail(6).iterrows():
            L.append(f"- {tr['entry_time']:%Y-%m-%d %H:%M} -> {tr['exit_reason']} ({tr['R']:+.2f}R). {tr['note']}")
        tr_keep.to_csv("reports/trader_trades.csv", index=False)
    L.append("\n## Entrées refusées par la discipline du trader (tous setups)")
    L += [f"- {k} : {v}" for k, v in sorted(skipped.items(), key=lambda kv: -kv[1])]
    L.append(f"\nVERDICT : **{verdict}** -- durée {(time.time() - t0) / 60:.1f} min.")
    res["verdict"] = verdict
    re_.record({"kind": "experiment", "style": "TRADER", "type": "trader_playbook",
                "params": {"rules": res["rules"], "playbook": keep},
                "question": "Le trader codé (4 setups price action, gestion 1R/BE/suiveur) a-t-il un avantage hors échantillon ?",
                "method": "backtest M15 événementiel, dev 2010->2023-04 pour choisir les setups, test unique 2023-05->",
                "decision_rule": ">= 100 trades, >= +0,10R/trade, PF >= 1,10 sur la période jamais vue",
                "results": {"dev": res["dev"], "lockbox": res.get("lockbox")}, "conclusion": verdict})
    with open("reports/trader_backtest.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    with open("reports/trader_backtest.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

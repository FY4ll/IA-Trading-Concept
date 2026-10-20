"""
Rapport par régime + baselines + expériences de filtres d'ouverture (05/10/2026).

    python scripts/regime_report.py H1 H1T H1X [--no-adopt]       (cwd = code/)

Pour chaque champion : rejoue le modèle sur la période d'AVANT la lockbox et sur la lockbox,
ventile les trades par régime/volatilité à l'entrée, compare aux baselines (buy & hold,
tendance SMA20/50), puis teste les filtres d'ouverture candidats (pré-enregistrés ci-dessous
+ hypothèses "regime_filter" ouvertes dans reports/research_journal.jsonl) en REJOUANT le
modèle avec le filtre. Chaque test est enregistré comme expérience (jamais effacée) ; un
filtre n'est adopté (data/research_adopted.json, lu par src/market_gate.py) que si la règle
de décision fixée à l'avance (research_engine.filter_decision) est satisfaite.
Écrit reports/regime_report.json et reports/regime_report.md.
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import yaml

from src import lockbox_analysis as la, research_engine as re_
from src.market_regime import regime_series
from src.lockbox_gate import baseline_metrics, eval_env_kwargs

PREREGISTERED = [{"block_vol_classes": ["EXTREME"]}, {"block_vol_classes": ["HIGH", "EXTREME"]}]


def _mask(regimes, filt):
    m = np.zeros(len(regimes), dtype=bool)
    if filt.get("block_vol_classes"):
        m |= regimes["vol_class"].isin(filt["block_vol_classes"]).to_numpy()
    if filt.get("block_regimes"):
        m |= regimes["regime"].isin(filt["block_regimes"]).to_numpy()
    return m


def _fmt(s):
    pf = s.get("prop_firm") or {}
    ch = f"{pf['challenge_pass']:.0%}" if "challenge_pass" in pf else "n/a"
    wd = f"{pf['worst_day']:+.1%}" if "worst_day" in pf else "n/a"
    return (f"Sharpe {s['sharpe']:.2f} | rendement {s['total_return']:+.1%} | DD {s['max_drawdown']:.1%} | "
            f"{s['n_trades']} trades | Challenge FTMO {ch} | pire jour {wd}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("styles", nargs="+")
    ap.add_argument("--config", default="../run_config_A.yaml")
    ap.add_argument("--no-adopt", action="store_true")
    ap.add_argument("--only-hypotheses", action="store_true",
                    help="ne teste que les hypothèses ouvertes du registre (lancement automatique)")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    report, md = {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "styles": {}}, []
    md.append(f"# Rapport par régime et expériences de filtres ({report['generated_at']})\n")
    open_hyps = [h for h in re_.open_hypotheses() if h.get("type") == "regime_filter"]

    for st in args.styles:
        t0 = time.time()
        res = {"periods": {}, "experiments": []}
        base, regimes_by_period = {}, {}
        for period in ("pre_lockbox", "lockbox"):
            rep = la.replay(st, cfg, period)
            gen = rep["meta"].get("generation")
            regs = regime_series(rep["raw"])
            regimes_by_period[period] = regs
            base[period] = la.summary(rep)
            res["periods"][period] = {"base": base[period], "by_regime": la.by_regime(rep, regs)}
            if period == "lockbox":
                meta = rep["meta"]
                res["baselines"] = baseline_metrics(rep["raw"], eval_env_kwargs(st, cfg, meta)["transaction_cost"])
        md.append(f"\n## {st}\n")
        for period in ("pre_lockbox", "lockbox"):
            md.append(f"- **{period}** : {_fmt(base[period])}")
        for name, b in res["baselines"].items():
            pf = b.get("prop_firm") or {}
            md.append(f"- baseline **{name}** (lockbox) : Sharpe {b['sharpe']:.2f} | rendement {b['total_return']:+.1%} | "
                      f"DD {b['max_drawdown']:.1%} | Challenge FTMO {pf.get('challenge_pass', 0):.0%}")
        br = res["periods"]["lockbox"]["by_regime"]
        md.append("\n| Lockbox, entrée en | trades | gain % | rendement moyen |\n|---|---|---|---|")
        for key in ("vol_class", "regime"):
            for g, s in sorted(br[key].items()):
                md.append(f"| {key}={g} | {s['n']} | {s['win_rate']:.0%} | {s['avg_ret']:+.3%} |")

        filters = [] if args.only_hypotheses else list(PREREGISTERED)
        for h in open_hyps:
            if h.get("style") == st and h["params"] not in filters:
                filters.append(h["params"])
        best = None
        for filt in filters:
            out = {}
            for period in ("pre_lockbox", "lockbox"):
                rep_f = la.replay(st, cfg, period, block_mask=_mask(regimes_by_period[period], filt))
                out[period] = la.summary(rep_f)
            ok, why = re_.filter_decision(base, out)
            exp = re_.record({
                "kind": "experiment", "style": st, "type": "regime_filter", "params": filt,
                "question": f"Le filtre d'ouverture {filt} améliore-t-il {st} hors échantillon ?",
                "method": "rejeu du champion avec le filtre appliqué comme en live, avant-lockbox puis lockbox",
                "decision_rule": "Sharpe >= base sur les 2 périodes, DD <= base + 1 pt, Challenge FTMO >= base - 2 pts",
                "generation": gen,
                "results": {"base": base, "filter": out}, "conclusion": "ACCEPTÉ" if ok else "REJETÉ", "reason": why})
            res["experiments"].append({"filter": filt, "accepted": ok, "reason": why, "results": out, "id": exp["id"]})
            md.append(f"\n- filtre `{json.dumps(filt)}` : **{'ACCEPTÉ' if ok else 'REJETÉ'}** ({why})")
            for period in ("pre_lockbox", "lockbox"):
                md.append(f"  - {period} : {_fmt(out[period])}")
            if ok and (best is None or out["lockbox"]["sharpe"] > best[1]["lockbox"]["sharpe"]):
                best = (filt, out, exp["id"])
            for h in open_hyps:
                if h.get("style") == st and h.get("params") == filt:
                    re_.record({"id": h["id"], "kind": "hypothesis", "status": "tested",
                                "conclusion": "ACCEPTÉ" if ok else "REJETÉ", "experiment_id": exp["id"]})
        if best and not args.no_adopt:
            re_.adopt_filter(st, best[0], best[2])
            md.append(f"\n**Filtre adopté pour {st} : {json.dumps(best[0])}** (expérience {best[2]}).")
        res["adopted"] = best[0] if best and not args.no_adopt else None
        report["styles"][st] = res
        print(f"[{st}] terminé en {(time.time() - t0) / 60:.1f} min ; adopté : {res['adopted']}", flush=True)

    report["n_experiments_total"] = re_.n_experiments()
    md.append(f"\nExpériences enregistrées au total : {report['n_experiments_total']}.")
    os.makedirs("reports", exist_ok=True)
    with open(os.path.join("reports", "regime_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, default=str)
    with open(os.path.join("reports", "regime_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

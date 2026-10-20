"""
Le trader découvre ses setups tout seul (src/trader/discovery.py).

    python scripts/trader_discover.py            (cwd = code/)

Règles fixées AVANT les résultats :
  entraînement 2010-2018 : setups de 1 à 3 conditions x 2 directions x 8 sorties, signaux sans
    chevauchement ; candidats = >= 150 trades, espérance >= +0,05R, top 300 par t-stat ;
  validation 2019 -> 2023-04 : t >= 2,5, espérance >= +0,05R, >= 60 trades, >= 60 % d'années
    positives ; doublons (signaux trop communs) retirés ;
  portefeuille : setups validés, un trade à la fois, priorité au meilleur t de validation,
    arrêt de la journée à -3R ; test UNIQUE sur 2023-05 -> : VALIDÉ si >= 100 trades,
    >= +0,10R/trade et profit factor >= 1,10 (cahier des charges §69).
Écrit reports/trader_discovery.md/json et data/trader_playbook.json (setups validés).
"""
import json, os, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import yaml

from src.trader import chart, discovery as dv
from src.ftmo_metrics import prop_firm_summary
from src import research_engine as re_

TRAIN = ("2010-01-01", "2019-01-01")
VAL = ("2019-01-01", "2023-05-01")
LOCK = ("2023-05-01", None)


def pmask(index, a, b):
    m = index >= pd.Timestamp(a)
    return m & (index < pd.Timestamp(b)) if b else m


def portfolio(ch, rules, outcomes, risk_pct=0.005, day_stop_R=-3.0):
    """Un trade à la fois ; à chaque bougie libre, le premier setup (par priorité) qui se déclenche."""
    n = len(ch)
    fire = np.full(n, -1, dtype=np.int32)
    for j in range(len(rules) - 1, -1, -1):           # le plus prioritaire écrase
        fire[rules[j]["mask"]] = j
    days = ch.index.normalize().to_numpy()
    trades, i, day, dayR = [], 0, None, 0.0
    while i < n - 1:
        if days[i] != day:
            day, dayR = days[i], 0.0
        j = fire[i]
        if j >= 0 and dayR > day_stop_R:
            R, held = outcomes[rules[j]["okey"]]
            if np.isfinite(R[i]):
                trades.append({"time": ch.index[i], "rule": rules[j]["name"], "R": float(R[i])})
                dayR += R[i]
                i += int(held[i]) + 1
                continue
        i += 1
    t = pd.DataFrame(trades)
    if len(t):
        t["pct"] = t["R"] * risk_pct
    return t


def tstats(t):
    if len(t) == 0:
        return {"n": 0}
    R = t["R"].to_numpy()
    w, lo = R[R > 0].sum(), -R[R <= 0].sum()
    cum = np.cumsum(R)
    return {"n": int(len(R)), "avg_R": float(R.mean()), "win": float((R > 0).mean()),
            "total_R": float(R.sum()), "pf": float(w / lo) if lo > 0 else None,
            "t": float(R.mean() / (R.std(ddof=1) / np.sqrt(len(R)))) if len(R) > 1 and R.std() > 0 else None,
            "max_dd_R": float((cum - np.maximum.accumulate(np.r_[0, cum])[1:]).min())}


def main():
    t0 = time.time()
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    m15 = chart.load_m15(cfg, "2008-06-01")
    m15 = m15[m15.index < m15.index.max().normalize()]
    ch = chart.build_chart(m15)
    P = dv.predicates(ch)
    years = ch.index.year.to_numpy()
    tr, va, lk = (pmask(ch.index, *TRAIN), pmask(ch.index, *VAL), pmask(ch.index, *LOCK))
    outcomes = {}
    for d in (1, -1):
        for (k, m, T) in dv.TEMPLATES:
            outcomes[(d, k, m, T)] = dv.bracket_outcomes(ch, k, m, T, d, with_held=True)
    print(f"{len(P)} observations, {len(outcomes)} sorties pré-calculées ({(time.time() - t0) / 60:.1f} min)", flush=True)

    cands, n_tested = [], 0
    for combo in dv.enumerate_rules(P):
        base = np.logical_and.reduce([P[x][1] for x in combo])
        if (base & tr).sum() < 150:
            continue
        thinned = {T: dv.thin(base, T) for T in (8, 32)}
        for (d, k, m, T), (R, _) in outcomes.items():
            mk = thinned[T]
            n_tested += 1
            s = dv.rule_stats(R, mk & tr)
            if s.get("n", 0) >= 150 and s["avg_R"] >= 0.05:
                cands.append((s["t"], combo, (d, k, m, T), s))
    cands.sort(key=lambda x: -x[0])
    print(f"{n_tested} setups testés, {len(cands)} candidats en entraînement ({(time.time() - t0) / 60:.1f} min)", flush=True)

    validated, seen = [], []
    for t_tr, combo, okey, s_tr in cands[:300]:
        d, k, m, T = okey
        base = np.logical_and.reduce([P[x][1] for x in combo])
        mk = dv.thin(base, T)
        R = outcomes[okey][0]
        s_va = dv.rule_stats(R, mk & va, years)
        if not (s_va.get("n", 0) >= 60 and s_va["t"] >= 2.5 and s_va["avg_R"] >= 0.05 and s_va.get("years_pos", 0) >= 0.6):
            continue
        dup = any((mk & va & o).sum() > 0.5 * min((mk & va).sum(), (o & va).sum()) for o in seen)
        if dup:
            continue
        seen.append(mk)
        name = (f"{'ACHAT' if d > 0 else 'VENTE'} si " + " + ".join(combo)
                + f" | stop {k} ATR H1, objectif {m}R, max {T * 15} min")
        validated.append({"name": name, "combo": list(combo), "dir": d, "k": k, "m": m, "T": T,
                          "okey": okey, "mask": mk, "train": s_tr, "val": s_va})
    validated.sort(key=lambda r: -r["val"]["t"])
    print(f"{len(validated)} setups validés ({(time.time() - t0) / 60:.1f} min)", flush=True)

    res = {"n_tested": n_tested, "n_candidates": len(cands), "validated": [
        {k: v for k, v in r.items() if k not in ("mask", "okey")} for r in validated]}
    L = [f"# Le trader découvre ses setups ({time.strftime('%Y-%m-%d %H:%M')})", "",
         f"{len(P)} observations élémentaires, {n_tested} setups testés en entraînement (2010-2018), "
         f"{len(cands)} candidats, {len(validated)} confirmés en validation (2019 -> 2023-04). "
         "Coûts : spread 0,30 $ + slippage 0,05 $ par jambe.", ""]
    for r in validated:
        L.append(f"- {r['name']} -- entraînement {r['train']['n']} trades {r['train']['avg_R']:+.3f}R (t={r['train']['t']:.1f}) ; "
                 f"validation {r['val']['n']} trades {r['val']['avg_R']:+.3f}R (t={r['val']['t']:.1f})")
    verdict = "NON VALIDÉ"
    if validated:
        port = portfolio(ch, validated, outcomes)
        pt = pd.to_datetime(port["time"])
        segs = {"entraînement": port[(pt >= TRAIN[0]) & (pt < TRAIN[1])], "validation": port[(pt >= VAL[0]) & (pt < VAL[1])],
                "jamais vu (2023-05 ->)": port[pt >= LOCK[0]]}
        L.append("\n## Portefeuille (un trade à la fois, risque 0,5 %/trade)")
        for nm, seg in segs.items():
            s = tstats(seg)
            res[f"portfolio_{nm}"] = s
            if s["n"]:
                ndays = max(1, len(set(pd.to_datetime(seg["time"]).dt.normalize())))
                L.append(f"- {nm} : {s['n']} trades ({s['n'] / max(1, (pd.to_datetime(seg['time']).max() - pd.to_datetime(seg['time']).min()).days / 7):.1f}/semaine), "
                         f"{s['avg_R']:+.3f}R/trade, gain {s['win']:.0%}, total {s['total_R']:+.1f}R, PF {s['pf'] or 0:.2f}, "
                         f"DD {s['max_dd_R']:.1f}R, t={s['t'] or 0:.2f}")
        lk_t = segs["jamais vu (2023-05 ->)"]
        s = tstats(lk_t)
        ok = s["n"] >= 100 and s.get("avg_R", -1) >= 0.10 and (s.get("pf") or 0) >= 1.10
        verdict = "VALIDÉ" if ok else "NON VALIDÉ"
        days = pd.DatetimeIndex(sorted(set(ch.index[lk].normalize())))
        for risk in (0.005, 0.01):
            dr = lk_t.assign(d=pd.to_datetime(lk_t["time"]).dt.normalize()).groupby("d")["R"].sum() * risk
            pf = prop_firm_summary(dr.reindex(days, fill_value=0).to_numpy(), n_sims=2000)
            res[f"prop_firm_{risk}"] = pf
            L.append(f"- jamais vu, risque {risk:.1%} : rendement {pf.get('total_return', 0):+.1%}, DD {pf.get('max_drawdown', 0):.1%}, "
                     f"pire jour {pf.get('worst_day', 0):+.2%}, mois médian {pf.get('monthly_median') or 0:+.1%}, "
                     f"Challenge FTMO {pf.get('challenge_pass', 0):.0%}")
        L.append("\n### Par setup sur la période jamais vue")
        for name, g in lk_t.groupby("rule"):
            s2 = tstats(g)
            L.append(f"- {name} : {s2['n']} trades, {s2['avg_R']:+.3f}R")
        with open("data/trader_playbook.json", "w", encoding="utf-8") as f:
            json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M"), "verdict": verdict,
                       "rules": [{k: v for k, v in r.items() if k not in ("mask", "okey")} for r in validated]},
                      f, indent=1, ensure_ascii=False)
    L.append(f"\nVERDICT (test unique sur la période jamais vue) : **{verdict}** -- {(time.time() - t0) / 60:.1f} min.")
    res["verdict"] = verdict
    re_.record({"kind": "experiment", "style": "TRADER", "type": "setup_discovery",
                "params": {"n_observations": len(P), "templates": dv.TEMPLATES},
                "question": "Le trader peut-il découvrir seul des setups qui gagnent hors échantillon ?",
                "method": "énumération 1-3 conditions, entraînement 2010-2018, validation 2019-2023-04, test unique 2023-05->",
                "decision_rule": "portefeuille >= 100 trades, >= +0,10R/trade, PF >= 1,10 sur la période jamais vue",
                "n_tests": n_tested, "results": {k: v for k, v in res.items() if k.startswith("portfolio")},
                "conclusion": verdict})
    with open("reports/trader_discovery.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str, ensure_ascii=False)
    with open("reports/trader_discovery.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

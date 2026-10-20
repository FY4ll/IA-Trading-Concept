"""
Évalue le champion d'un style sur la LOCKBOX (données jamais vues) et applique la porte -- lecture seule,
ne modifie aucun modèle. Écrit reports/lockbox_<style>.json.

    python scripts/lockbox_check_style.py AUREX            (cwd = code/)
"""
import json, os, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml


def main(style: str):
    from src.lockbox_gate import evaluate_on_lockbox, gate_decision
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    d = os.path.join("models", f"champion_{style}")
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    stats = json.load(open(os.path.join(d, "norm_stats.json"), encoding="utf-8"))
    t0 = time.time()
    m = evaluate_on_lockbox(style, cfg, os.path.join(d, "agent"), meta, stats)
    ok, why = gate_decision(m, cfg["validation"]["lockbox_gate"], None)
    m["gate_ok"], m["gate_reason"], m["generation"] = ok, why, meta.get("generation")
    json.dump(m, open(os.path.join("reports", f"lockbox_{style}.json"), "w", encoding="utf-8"), indent=1, default=str)
    pf = m.get("prop_firm") or {}
    print(f"{style} gén {meta.get('generation')} sur la lockbox ({m['lockbox_start']} ->) : Sharpe {m['sharpe']:.2f}, "
          f"rendement {m['total_return']:+.1%}, DD {m['max_drawdown']:.1%}, {m['n_trades']} trades, "
          f"coûts x2 {m.get('stress_return', float('nan')):+.1%}, tiers {[round(x, 3) for x in m.get('thirds_returns', [])]}, "
          f"Challenge FTMO {pf.get('challenge_pass', 0):.0%} -> porte {'OK' if ok else 'REFUSÉE : ' + why} "
          f"({(time.time() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "AUREX")

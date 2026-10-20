"""
Simulateur FTMO 100k : probabilité de réussir le Challenge (+10 %) puis la Vérification (+5 %) avec les
limites FTMO (perte max 5 %/jour, 10 % au total, sur le capital initial), en rééchantillonnant par blocs
les rendements journaliers de la lockbox d'un style (données jamais vues à l'entraînement).

    python scripts/ftmo_sim.py H1 H1T H1X            (cwd = code/)

Les règles FTMO sont à revérifier sur leur site. Le risque par trade (live.max_risk_pct_per_trade) est celui
de la config ; l'option --scale multiplie les rendements pour tester d'autres tailles de position.
"""
import argparse, json, os, sys
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DAILY_LIMIT, TOTAL_LIMIT = 0.05, 0.10
TARGETS = {"challenge": 0.10, "verification": 0.05}


def lockbox_daily_returns(style: str, cfg: dict) -> pd.Series:
    import src.backtester as bt
    from src import lockbox_gate as lg
    mdir = os.path.join("models", f"champion_{style}")
    meta = json.load(open(os.path.join(mdir, "meta.json"), encoding="utf-8"))
    stats = json.load(open(os.path.join(mdir, "norm_stats.json"), encoding="utf-8"))
    captured = []
    real = bt.run_episode

    def spy(agent, env, *a, **k):
        out = real(agent, env, *a, **k)
        captured.append(out)
        return out

    bt.run_episode = spy
    try:
        c2 = json.loads(json.dumps(cfg))
        c2.setdefault("validation", {}).setdefault("lockbox_gate", {})["stress_cost_multiplier"] = 0
        lg.evaluate_on_lockbox(style, c2, os.path.join(mdir, "agent"), meta, stats)
    finally:
        bt.run_episode = real
    env = captured[0]
    eq = np.asarray(env.equity_curve, dtype=float)
    times = pd.to_datetime(env.df["time"]).reset_index(drop=True) if "time" in env.df.columns else None
    n = min(len(eq), len(times)) if times is not None else len(eq)
    if times is None:
        raise RuntimeError("colonne time absente de l'env")
    s = pd.Series(eq[-n:], index=times.iloc[-n:].to_numpy())
    daily = s.groupby(s.index.normalize()).last()
    return daily.pct_change().dropna()


def simulate(rets: np.ndarray, target: float, n_sims: int, horizon_days: int, block: int, rng) -> dict:
    wins = daily_breach = total_breach = timeout = 0
    days_to_pass = []
    n = len(rets)
    for _ in range(n_sims):
        bal, peak_ok, day = 1.0, True, 0
        outcome = "timeout"
        while day < horizon_days:
            i = rng.integers(0, max(1, n - block))
            for r in rets[i:i + block]:
                day += 1
                if r <= -DAILY_LIMIT:
                    outcome = "daily"; break
                bal *= (1 + r)
                if bal <= 1 - TOTAL_LIMIT:
                    outcome = "total"; break
                if bal >= 1 + target:
                    outcome = "win"; break
                if day >= horizon_days:
                    break
            if outcome != "timeout":
                break
        if outcome == "win":
            wins += 1; days_to_pass.append(day)
        elif outcome == "daily":
            daily_breach += 1
        elif outcome == "total":
            total_breach += 1
        else:
            timeout += 1
    return {"pass": wins / n_sims, "daily_breach": daily_breach / n_sims, "total_breach": total_breach / n_sims,
            "timeout": timeout / n_sims, "median_days": float(np.median(days_to_pass)) if days_to_pass else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("styles", nargs="+")
    ap.add_argument("--config", default="../run_config_A.yaml")
    ap.add_argument("--sims", type=int, default=4000)
    ap.add_argument("--horizon", type=int, default=120, help="jours de trading max par phase")
    ap.add_argument("--block", type=int, default=5)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--daycap", type=float, default=0.0, help="coupe-circuit : perte journalière plafonnée (ex 0.025)")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    rng = np.random.default_rng(7)
    for st in args.styles:
        try:
            r = lockbox_daily_returns(st, cfg).to_numpy() * args.scale
            if args.daycap > 0:
                r = np.maximum(r, -args.daycap)
        except Exception as e:
            print(f"[{st}] indisponible : {e}")
            continue
        print(f"\n=== {st} : {len(r)} jours de lockbox | rendement moyen/jour {r.mean():+.3%} | pire jour {r.min():+.2%} "
              f"| jours < -2 % : {(r < -0.02).sum()} | jours < -5 % : {(r <= -DAILY_LIMIT).sum()}")
        c = np.cumprod(1 + r); dd = (c / np.maximum.accumulate(c) - 1).min()
        print(f"    drawdown max historique lockbox : {dd:.1%} | rendement total {c[-1] - 1:+.1%}")
        m = np.array([np.prod(1 + r[i:i + 21]) - 1 for i in range(0, len(r) - 20, 21)])
        print(f"    mois de 21 j : médiane {np.median(m):+.1%} | moyenne {m.mean():+.1%} | mois >= +8 % : {(m >= 0.08).mean():.0%} "
              f"| mois < 0 : {(m < 0).mean():.0%} ({len(m)} mois)")
        for phase, tgt in TARGETS.items():
            res = simulate(r, tgt, args.sims, args.horizon, args.block, rng)
            md = f"{res['median_days']:.0f} j" if res["median_days"] else "n/a"
            print(f"    {phase:12s} (+{tgt:.0%}) : réussite {res['pass']:.0%} | échec jour -5 % {res['daily_breach']:.0%} "
                  f"| échec total -10 % {res['total_breach']:.0%} | non atteint en {args.horizon} j {res['timeout']:.0%} | médiane {md}")


if __name__ == "__main__":
    main()

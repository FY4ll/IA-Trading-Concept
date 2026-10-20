"""
ftmo_metrics.py
================
Mesures "prop firm" partagées (05/10/2026) entre scripts/ftmo_sim.py et la porte
lockbox (src/lockbox_gate.py) : probabilité de réussir le Challenge FTMO 100k
(+10 %) et la Vérification (+5 %) avant une perte de 5 % sur un jour ou de 10 %
au total, par rééchantillonnage par blocs des rendements JOURNALIERS d'une
courbe d'équité ; pire jour, drawdown, rendement mensuel.

Les règles FTMO sont à revérifier sur leur site (elles peuvent changer).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

DAILY_LIMIT, TOTAL_LIMIT = 0.05, 0.10
TARGETS = {"challenge": 0.10, "verification": 0.05}


def daily_returns(equity, times) -> pd.Series:
    """Rendements journaliers d'une courbe d'équité alignée (en fin) sur `times`."""
    eq = np.asarray(equity, dtype=float)
    t = pd.to_datetime(pd.Series(times)).reset_index(drop=True)
    n = min(len(eq), len(t))
    s = pd.Series(eq[-n:], index=t.iloc[-n:].to_numpy())
    daily = s.groupby(s.index.normalize()).last()
    return daily.pct_change().dropna()


def simulate(rets: np.ndarray, target: float, n_sims: int = 2000, horizon_days: int = 120,
             block: int = 5, rng=None) -> dict:
    rng = rng if rng is not None else np.random.default_rng(7)
    rets = np.asarray(rets, dtype=float)
    n = len(rets)
    if n == 0:
        return {"pass": 0.0, "daily_breach": 0.0, "total_breach": 0.0, "timeout": 1.0, "median_days": None}
    wins = daily_breach = total_breach = timeout = 0
    days_to_pass = []
    for _ in range(n_sims):
        bal, day = 1.0, 0
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


def prop_firm_summary(rets, n_sims: int = 2000, seed: int = 7) -> dict:
    """Résumé prop firm d'une série de rendements journaliers."""
    r = np.asarray(rets, dtype=float)
    if len(r) < 20:
        return {"n_days": int(len(r))}
    c = np.cumprod(1 + r)
    months = np.array([np.prod(1 + r[i:i + 21]) - 1 for i in range(0, len(r) - 20, 21)])
    rng = np.random.default_rng(seed)
    ch = simulate(r, TARGETS["challenge"], n_sims, rng=rng)
    ve = simulate(r, TARGETS["verification"], n_sims, rng=rng)
    return {
        "n_days": int(len(r)), "worst_day": float(r.min()), "days_below_2pct": int((r < -0.02).sum()),
        "max_drawdown": float((c / np.maximum.accumulate(c) - 1).min()), "total_return": float(c[-1] - 1),
        "monthly_median": float(np.median(months)) if len(months) else None,
        "months_ge_8pct": float((months >= 0.08).mean()) if len(months) else None,
        "challenge_pass": ch["pass"], "challenge_daily_breach": ch["daily_breach"],
        "challenge_total_breach": ch["total_breach"], "verification_pass": ve["pass"],
    }

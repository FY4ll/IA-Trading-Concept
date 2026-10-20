"""Note d'examen « argent FTMO » (09/10/2026) : la taille n'est plus punie tant qu'on reste loin des murs, le casino
reste perdant, et l'examen juge un compte qui trade TOUS les marchés en même temps."""
from __future__ import annotations
import types

import numpy as np
import pandas as pd
import pytest

from src.note_argent import (note_portefeuille, note_run, simulate_portfolio, monthly_return, run_daily_returns,
                             wall_penalty, DEFAULTS, DEATH_NOTE)


def _strategy(seed=0, n=250, mean=0.00015, vol=0.004):
    return np.random.default_rng(seed).normal(mean, vol, n)


def test_bigger_size_with_an_edge_gets_a_better_note():
    """L'ancien défaut : à stratégie égale, grossir faisait TOUJOURS baisser la note. Une IA timide qui a un avantage
    est maintenant mieux notée en jouant une taille raisonnable."""
    base = {f"M{i}": _strategy(i) for i in range(6)}
    timid = {k: 0.25 * v for k, v in base.items()}
    nt, nr = note_portefeuille(timid), note_portefeuille(base)
    assert nr["mensuel"] == pytest.approx(4 * nt["mensuel"])
    assert nr["note"] > nt["note"] + 1.0


def test_casino_size_is_punished_by_ftmo_failures():
    base = {f"M{i}": _strategy(i) for i in range(6)}
    for k in (4, 8):
        casino = note_portefeuille({m: k * v for m, v in base.items()})
        assert casino["echec"] > 0.5
        assert casino["note"] < note_portefeuille(base)["note"] - 1.0, "même avantage : le casino est moins bien noté"


def test_without_an_edge_size_is_never_rewarded():
    flat = {f"M{i}": _strategy(i, mean=0.00005) for i in range(6)}
    notes = [note_portefeuille({m: k * v for m, v in flat.items()})["note"] for k in (0.25, 1, 4)]
    assert notes[0] > notes[1] > notes[2]

def test_tiny_ai_gets_almost_nothing():
    tiny = {f"M{i}": 0.05 * _strategy(i) for i in range(6)}
    n = note_portefeuille(tiny)
    assert n["reussite"] == 0.0 and abs(n["note"]) < 0.3


def test_many_small_markets_add_up_on_one_account():
    """« Quelques % sur tous les marchés » : 8 marchés modestes ensemble réussissent bien plus souvent qu'un seul."""
    markets = {f"M{i}": _strategy(i, mean=0.0003, vol=0.003) for i in range(8)}
    one = simulate_portfolio([markets["M0"]])
    together = simulate_portfolio(list(markets.values()))
    assert together["pass"] > one["pass"] + 0.2
    assert note_portefeuille(markets)["note"] > note_portefeuille({"M0": markets["M0"]})["note"]


def test_single_market_simulation_agrees_with_the_reference_ftmo_simulator():
    from src.ftmo_metrics import simulate
    r = _strategy(3, mean=0.0015, vol=0.008)
    ref = simulate(r, 0.10, 2000, rng=np.random.default_rng(1))["pass"]
    new = simulate_portfolio([r], n_sims=2000, seed=1)["pass"]
    assert new == pytest.approx(ref, abs=0.06)


def test_mirror_markets_are_not_part_of_the_account():
    r = _strategy(1)
    n = note_portefeuille({"EURUSD": r, "EURUSD miroir": -r})
    assert n["n_marches"] == 1 and n["mensuel"] == pytest.approx(monthly_return(r))


def test_drawdown_is_only_punished_near_the_walls():
    assert wall_penalty(0.03, DEFAULTS) == 0.0 and wall_penalty(0.059, DEFAULTS) == 0.0
    assert wall_penalty(0.08, DEFAULTS) == pytest.approx(25 * 0.02)
    base = {f"M{i}": _strategy(i) for i in range(4)}
    assert note_portefeuille(base, crisis_drawdown=0.08)["note"] < note_portefeuille(base, crisis_drawdown=0.03)["note"]


def test_quick_exam_note_death_and_size():
    r = _strategy(2)
    assert note_run(2 * r, 0.03) > note_run(r, 0.015), "la taille ne fait plus baisser la note"
    assert note_run(r, 0.11) == DEATH_NOTE, "mort FTMO au total = note minimale"
    assert note_run(np.r_[r, -0.06], 0.03) == DEATH_NOTE, "mort FTMO sur un jour = note minimale"
    assert note_run(8 * r, 0.09) < note_run(r, 0.015), "casino sur le petit examen : près des murs, moins bien noté"


def test_run_daily_returns_reads_the_equity_curve_by_day():
    eq = [100.0] + [100.0] * 95 + [101.0] * 96 + [99.99] * 96
    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=len(eq), freq="15min")})
    env = types.SimpleNamespace(equity_curve=eq, window_size=1)
    r = run_daily_returns(env, df)
    assert r == pytest.approx([0.01, -0.01], abs=1e-9)


def _mk(close, freq="h"):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"time": pd.date_range("2024-01-01", periods=len(close), freq=freq), "open": close,
                         "high": close * 1.0005, "low": close * 0.9995, "close": close, "f": 0.0})


def test_full_and_quick_exam_use_the_account_note(tmp_path):
    """Branchement réel dans l'examen : le score du candidat EST la note du compte tous marchés (or + marchés réels,
    miroirs exclus), l'ancienne note reste visible, et le petit examen utilise la même formule."""
    import src.continuous_trainer as ct
    rng = np.random.default_rng(4)
    gold = _mk(100 * np.cumprod(1 + rng.normal(0.0001, 0.002, 2400)))
    eur = _mk(1.1 * np.cumprod(1 + rng.normal(0, 0.001, 800)))
    env_kwargs = dict(window_size=5, initial_balance=10000, transaction_cost=0.0, reward_type="pnl",
                      drawdown_penalty=0.0, max_position=1, feature_columns=["f"])
    base = {"train_df": gold.iloc[:1200].reset_index(drop=True), "val_df": gold.iloc[1200:].reset_index(drop=True),
            "env_kwargs": env_kwargs, "hyperparams": {"n_steps": 64, "batch_size": 16},
            "warm_start_path": None, "timesteps": 64, "generation": 1, "style": "H1", "slot": 0,
            "context_timeframes": [], "eval_windows": 1, "fitness_metric": "sortino",
            "extra_val": [("EURUSD", eur), ("EURUSD miroir", eur)], "note_argent": {"n_sims": 300}}
    out = ct._train_candidate_worker({**base, "out_path": str(tmp_path / "c1")})
    pf = out["metrics"]["portefeuille"]
    assert out["score"] == pytest.approx(pf["note"])
    assert pf["n_marches"] == 2 and set(pf["par_marche"]) == {"XAUUSD", "EURUSD"}, "or + EURUSD, sans le miroir"
    assert "note_classique" in out["metrics"]
    q = ct._train_candidate_worker({**base, "out_path": str(tmp_path / "c2"), "phase": 1,
                                    "quick_exam": [("tirage EURUSD", eur)]})
    from src.note_argent import note_run
    assert q["quick_score"] == pytest.approx(q["quick"][0]["score"])
    assert q["quick_score"] >= -10.0 and q["quick_score"] <= 10.0


def test_losers_are_still_ranked_no_floor():
    """Incident du 09/10 (cycle 396) : -5,9 %/mois et -8 %/mois étaient tous deux bloqués au plancher -10 -> égalité,
    le plus mauvais a pris la place du champion. Sans plancher, celui qui perd le moins a toujours la meilleure note."""
    a = {f"M{i}": _strategy(i, mean=-0.0025) for i in range(6)}       # ~ -3 %/mois au total
    b = {f"M{i}": _strategy(i, mean=-0.0035) for i in range(6)}       # ~ -4,4 %/mois
    assert note_portefeuille(a)["note"] > note_portefeuille(b)["note"]
    assert note_run(_strategy(1, mean=-0.004), 0.05) > note_run(_strategy(1, mean=-0.006), 0.07)
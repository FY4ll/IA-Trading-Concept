"""Examen tournant (09/10/2026) : une période différente à chaque cycle, jamais dans les 12 derniers mois cachés ;
le champion et les candidats d'un même cycle sont jugés sur la même période ; l'or de la période tirée remplace la
validation fixe dans le compte tous marchés."""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

import src.aurexis_data as ad

CFG = {"multi_market": {"selection": {"rotation": {"enabled": True, "from": "2023-01-01", "to": "2025-09-30",
                                                   "days": 105}}}}


def test_window_changes_each_cycle_and_stays_in_bounds():
    wins = {ad.rotation_window(CFG, seed=s) for s in range(200)}
    assert len(wins) > 50, "une période différente à chaque cycle"
    for w0, w1 in wins:
        assert w0 >= pd.Timestamp("2023-01-01") and w1 <= pd.Timestamp("2025-09-30")
        assert (w1 - w0).days == 105
    assert ad.rotation_window(CFG, seed=7) == ad.rotation_window(CFG, seed=7), "même tirage = même période"


def test_last_twelve_months_are_never_drawn():
    assert max(ad.rotation_window(CFG, seed=s)[1] for s in range(500)) <= pd.Timestamp("2025-09-30")


def test_rotation_off_by_default():
    assert ad.rotation_window({"multi_market": {"selection": {}}}, seed=1) is None


def test_old_periods_are_dropped_from_memory():
    ad._val_cache.clear()
    old = (("EURUSD", "p", 0, None, (), 1, False), pd.Timestamp("2023-01-01"), pd.Timestamp("2023-04-16"), 7000)
    ad._val_cache[old] = "ancien"
    ad.other_markets_val({"multi_market": {}}, ["f"], [], "2022-12-01", "2024-02-01", "2024-05-16", max_val_bars=7000)
    assert old not in ad._val_cache


def _mk(close, freq="h"):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"time": pd.date_range("2024-01-01", periods=len(close), freq=freq), "open": close,
                         "high": close * 1.0005, "low": close * 0.9995, "close": close, "f": 0.0})


def test_account_uses_the_drawn_gold_period_not_the_fixed_validation(tmp_path):
    import src.continuous_trainer as ct
    rng = np.random.default_rng(5)
    gold = _mk(100 * np.cumprod(1 + rng.normal(0.0001, 0.002, 2400)))
    gold_drawn = _mk(100 * np.cumprod(1 + rng.normal(0, 0.002, 600)))        # 25 jours seulement
    env_kwargs = dict(window_size=5, initial_balance=10000, transaction_cost=0.0, reward_type="pnl",
                      drawdown_penalty=0.0, max_position=1, feature_columns=["f"])
    spec = {"train_df": gold.iloc[:1200].reset_index(drop=True), "val_df": gold.iloc[1200:].reset_index(drop=True),
            "env_kwargs": env_kwargs, "hyperparams": {"n_steps": 64, "batch_size": 16}, "warm_start_path": None,
            "timesteps": 64, "generation": 1, "style": "H1", "slot": 0, "context_timeframes": [], "eval_windows": 1,
            "fitness_metric": "sortino", "extra_val": [("XAUUSD", gold_drawn)], "note_argent": {"n_sims": 200},
            "out_path": str(tmp_path / "c")}
    seen = {}
    real = ct.note_portefeuille

    def spy(market_rets, **kw):
        seen.update({k: len(v) for k, v in market_rets.items()})
        return real(market_rets, **kw)

    ct.note_portefeuille = spy
    try:
        out = ct._train_candidate_worker(spec)
    finally:
        ct.note_portefeuille = real
    assert out["metrics"]["portefeuille"]["n_marches"] == 1
    assert seen["XAUUSD"] <= 25, f"le compte a reçu {seen['XAUUSD']} jours : la validation fixe (50 j) au lieu de la période tirée (25 j)"

def test_two_periods_one_old_one_recent():
    cfg = {"multi_market": {"selection": {"rotation": {**CFG["multi_market"]["selection"]["rotation"], "windows": 2}}}}
    mid = pd.Timestamp("2023-01-01") + (pd.Timestamp("2025-09-30") - pd.Timestamp("2023-01-01")) / 2
    for s in range(100):
        (a0, a1), (b0, b1) = ad.rotation_windows(cfg, seed=s)
        assert pd.Timestamp("2023-01-01") <= a0 and a1 <= mid + pd.Timedelta(days=1)
        assert mid - pd.Timedelta(days=1) <= b0 and b1 <= pd.Timestamp("2025-09-30")
    assert len(ad.rotation_windows(CFG, seed=1)) == 1, "par défaut : une seule période"


def test_note_is_the_worse_of_the_two_periods(tmp_path):
    """Être bon sur UNE période ne suffit plus : la note retenue est celle de la moins bonne."""
    import src.continuous_trainer as ct
    rng = np.random.default_rng(6)
    gold = _mk(100 * np.cumprod(1 + rng.normal(0.0001, 0.002, 2400)))
    good = _mk(100 * np.cumprod(1 + rng.normal(0.0006, 0.002, 900)))
    bad = _mk(100 * np.cumprod(1 + rng.normal(-0.0006, 0.002, 900)))
    env_kwargs = dict(window_size=5, initial_balance=10000, transaction_cost=0.0, reward_type="pnl",
                      drawdown_penalty=0.0, max_position=1, feature_columns=["f"])
    spec = {"train_df": gold.iloc[:1200].reset_index(drop=True), "val_df": gold.iloc[1200:].reset_index(drop=True),
            "env_kwargs": env_kwargs, "hyperparams": {"n_steps": 64, "batch_size": 16}, "warm_start_path": None,
            "timesteps": 64, "generation": 1, "style": "H1", "slot": 0, "context_timeframes": [], "eval_windows": 1,
            "fitness_metric": "sortino", "extra_val": [("XAUUSD", good), ("XAUUSD p2", bad)],
            "note_argent": {"n_sims": 200}, "out_path": str(tmp_path / "c")}
    out = ct._train_candidate_worker(spec)
    pf = out["metrics"]["portefeuille"]
    assert [p["periode"] for p in pf["periodes"]] == [1, 2]
    assert out["score"] == pytest.approx(min(p["note"] for p in pf["periodes"]))

"""Frais par marché (09/10/2026) : chaque marché paie SES frais (avant : le coût calibré sur l'or partout, ~2x trop
cher sur les grandes devises), l'or garde le coût de référence, l'IA ne voit jamais cette colonne."""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

from src.aurexis_data import cost_round_trip, add_cost_column, combine_segments, reference_cost
from src.trading_env import TradingEnv


def test_costs_per_market_and_mirrors():
    assert cost_round_trip("EURUSD") < cost_round_trip("EURGBP") < cost_round_trip("XAGUSD") < cost_round_trip("NATGAS")
    assert cost_round_trip("EURUSD miroir") == cost_round_trip("EURUSD")
    assert cost_round_trip("INCONNU") is None
    cfg = {"multi_market": {"cost_round_trip": {"EURUSD": 0.00004}}}
    assert cost_round_trip("EURUSD", cfg) == 0.00004, "frais mesurés (config) prioritaires"


def test_reference_cost_reads_the_style_override():
    cfg = {"environment": {"transaction_cost": 0.0002, "style_overrides": {"AUREXIS": {"transaction_cost": 0.00006}}},
           "multi_market": {"styles": ["AUREXIS"]}}
    assert reference_cost(cfg) == 0.00006
    df = add_cost_column(pd.DataFrame({"close": [1.0, 2.0]}), "EURUSD", reference_cost(cfg))
    assert df["cost_multiplier"].iloc[0] == pytest.approx(0.00010 / 0.00006)
    assert add_cost_column(pd.DataFrame({"close": [1.0]}), "INCONNU", 0.00006)["cost_multiplier"].iloc[0] == 1.0


def test_gold_segment_gets_reference_cost_when_others_have_their_own():
    gold = pd.DataFrame({"time": pd.date_range("2024", periods=3, freq="15min"), "close": 1.0, "f": 0.0})
    eur = gold.assign(cost_multiplier=np.float32(0.8))
    out = combine_segments(gold, [eur], cols=["f"])
    assert list(out["cost_multiplier"]) == pytest.approx([1.0] * 3 + [0.8] * 3)


def test_the_simulator_charges_each_market_its_own_cost():
    n = 60
    close = np.full(n, 100.0)
    base = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=n, freq="15min"), "open": close,
                         "high": close, "low": close, "close": close, "f": 0.0})

    def cost_of_round_trip(name):
        df = add_cost_column(base.copy(), name, 0.00012)
        env = TradingEnv(df, window_size=5, feature_columns=["f"], transaction_cost=0.00012, reward_type="pnl",
                         session_spread_enabled=False)
        env.reset(); env.step(2); env.step(1)
        return 1.0 - env.balance / env.initial_balance

    eur, gas = cost_of_round_trip("EURUSD"), cost_of_round_trip("NATGAS")
    assert eur == pytest.approx(0.00010, rel=1e-6)
    assert gas == pytest.approx(0.00180, rel=1e-6)

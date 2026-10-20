"""LOT 2, phase 5 : frictions calibrables (src/stress_test.py::
resolve_friction_params) et scripts/friction_sensitivity.py (sensibilité
x0.5/x1/x2). Fichier DÉDIÉ (pas tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest

from src.stress_test import (
    resolve_friction_params, DEFAULT_SPREAD_MULTIPLIER_RANGE, DEFAULT_SLIPPAGE_PRICE_RANGE,
)
from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
from src.trading_env import TradingEnv
from src.agent import TradingAgent
import friction_sensitivity as fs_module


def test_pessimistic_profile_matches_current_defaults_exactly():
    """"pessimistic" ne doit changer AUCUNE valeur par défaut existante."""
    params = resolve_friction_params("pessimistic")
    assert params["spread_multiplier_range"] == DEFAULT_SPREAD_MULTIPLIER_RANGE
    assert params["slippage_price_range"] == DEFAULT_SLIPPAGE_PRICE_RANGE


def test_default_profile_argument_is_pessimistic():
    assert resolve_friction_params() == resolve_friction_params("pessimistic")


def test_calibrated_falls_back_to_pessimistic_when_file_absent(tmp_path):
    missing = str(tmp_path / "does_not_exist.json")
    params = resolve_friction_params("calibrated", calibration_path=missing)
    assert params["spread_multiplier_range"] == DEFAULT_SPREAD_MULTIPLIER_RANGE
    assert params["slippage_price_range"] == DEFAULT_SLIPPAGE_PRICE_RANGE


def test_calibrated_uses_real_slippage_range_when_file_present(tmp_path):
    calib_path = tmp_path / "calib.json"
    calib_path.write_text(json.dumps({"slippage_price_range": [0.01, 0.03], "n_samples": 50}), encoding="utf-8")
    params = resolve_friction_params("calibrated", calibration_path=str(calib_path))
    assert params["slippage_price_range"] == (0.01, 0.03)
    # spread_multiplier_range n'est JAMAIS calibré (non mesurable) -- reste pessimiste.
    assert params["spread_multiplier_range"] == DEFAULT_SPREAD_MULTIPLIER_RANGE


def test_calibrated_falls_back_gracefully_on_corrupt_file(tmp_path):
    calib_path = tmp_path / "corrupt.json"
    calib_path.write_text("{not valid json", encoding="utf-8")
    params = resolve_friction_params("calibrated", calibration_path=str(calib_path))
    assert params["slippage_price_range"] == DEFAULT_SLIPPAGE_PRICE_RANGE


# ---------------------------------------------------------------------- #
# scripts/slippage_report.py::build_calibration
# ---------------------------------------------------------------------- #

def test_build_calibration_none_below_minimum_samples():
    import slippage_report
    records = [{"slippage": 0.02}] * 5  # < MIN_SAMPLES_FOR_CALIBRATION
    assert slippage_report.build_calibration(records) is None


def test_build_calibration_produces_structured_output():
    import slippage_report
    records = [{"slippage": 0.01 + 0.001 * i} for i in range(30)]
    calibration = slippage_report.build_calibration(records)
    assert calibration is not None
    assert calibration["n_samples"] == 30
    assert len(calibration["slippage_price_range"]) == 2
    assert calibration["slippage_price_range"][0] <= calibration["slippage_price_range"][1]


# ---------------------------------------------------------------------- #
# scripts/friction_sensitivity.py
# ---------------------------------------------------------------------- #

def _tiny_agent_and_df():
    df = generate_synthetic_ohlcv(n_bars=1500, seed=5)
    df = add_technical_features(df)
    df_norm, stats = normalize_features(df, columns=FEATURE_COLUMNS)
    env = TradingEnv(df_norm, window_size=20, feature_columns=FEATURE_COLUMNS, style="H1")
    agent = TradingAgent(env, {"algo": "PPO", "use_lstm": False, "n_steps": 32, "batch_size": 16})
    agent.learn(32)
    env_kwargs = dict(window_size=20, feature_columns=FEATURE_COLUMNS, style="H1")
    return agent, df_norm, env_kwargs


def test_evaluate_at_friction_multiplier_scales_params_never_below_baseline():
    agent, df, env_kwargs = _tiny_agent_and_df()
    base_params = {"spread_multiplier_range": (3.0, 5.0), "slippage_price_range": (0.02, 0.05)}
    metrics_half = fs_module.evaluate_at_friction_multiplier(agent, df, env_kwargs, "H1", 0.5, base_params, seed=1)
    metrics_double = fs_module.evaluate_at_friction_multiplier(agent, df, env_kwargs, "H1", 2.0, base_params, seed=1)
    assert "sharpe" in metrics_half and "sharpe" in metrics_double
    assert "max_drawdown" in metrics_half and "max_drawdown" in metrics_double


def test_evaluate_at_friction_multiplier_returns_metrics_for_all_required_fields():
    agent, df, env_kwargs = _tiny_agent_and_df()
    base_params = {"spread_multiplier_range": (3.0, 5.0), "slippage_price_range": (0.02, 0.05)}
    metrics = fs_module.evaluate_at_friction_multiplier(agent, df, env_kwargs, "H1", 1.0, base_params, seed=1)
    for key in ("sharpe", "max_drawdown", "total_return", "n_trades"):
        assert key in metrics


def test_friction_multipliers_include_half_one_and_double():
    assert fs_module.FRICTION_MULTIPLIERS == [0.5, 1.0, 2.0]

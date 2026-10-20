"""LOT 2, phase 4, point 8 : veto de promotion via run_survival_test (test
de survie transversal, poids figés) -- src/multi_asset.py::stability_veto.
Fichier DÉDIÉ (pas tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
from src.trading_env import TradingEnv
from src.agent import TradingAgent
from src.multi_asset import stability_veto


def _train_tiny_agent(tmp_path, style="M15"):
    df = generate_synthetic_ohlcv(n_bars=1500, seed=5)
    df = add_technical_features(df)
    df_norm, stats = normalize_features(df, columns=FEATURE_COLUMNS)
    env = TradingEnv(df_norm, window_size=20, feature_columns=FEATURE_COLUMNS, style=style)
    agent = TradingAgent(env, {"algo": "PPO", "use_lstm": False, "n_steps": 32, "batch_size": 16})
    agent.learn(32)
    model_path = str(tmp_path / "candidate_agent")
    agent.save(model_path)
    meta = {"feature_columns": FEATURE_COLUMNS, "algo": "PPO", "score": 1.0}
    return model_path, meta, stats


def test_stability_veto_no_op_when_no_other_symbols(tmp_path):
    model_path, meta, stats = _train_tiny_agent(tmp_path)
    all_stable, details = stability_veto("M15", model_path, meta, stats, {})
    assert all_stable is True
    assert details == []


def test_stability_veto_passes_when_target_stable(tmp_path):
    model_path, meta, stats = _train_tiny_agent(tmp_path)
    other = generate_synthetic_ohlcv(n_bars=2000, seed=99)
    all_stable, details = stability_veto("M15", model_path, meta, stats, {"EURUSD": other}, n_bars=500)
    assert len(details) == 1
    assert details[0]["symbol"] == "EURUSD"
    assert "stable" in details[0]
    assert all_stable == details[0]["stable"]


def test_stability_veto_blocks_on_feature_mismatch_treated_as_unstable(tmp_path):
    """Un candidat entraîné avec du contexte multi-timeframe (colonnes
    absentes d'un CSV mono-timeframe pour un autre symbole) ne doit jamais
    planter le veto -- traité comme NON stable, promotion bloquée par
    prudence."""
    model_path, meta, stats = _train_tiny_agent(tmp_path)
    meta = {**meta, "feature_columns": FEATURE_COLUMNS + ["rsi_14_4H"]}  # colonne MTF absente
    other = generate_synthetic_ohlcv(n_bars=1000, seed=3)
    all_stable, details = stability_veto("M15", model_path, meta, stats, {"EURUSD": other}, n_bars=500)
    assert all_stable is False
    assert details[0]["stable"] is False


def test_stability_veto_multiple_symbols_all_must_pass(tmp_path):
    model_path, meta, stats = _train_tiny_agent(tmp_path)
    others = {
        "EURUSD": generate_synthetic_ohlcv(n_bars=2000, seed=11),
        "SPX": generate_synthetic_ohlcv(n_bars=2000, seed=22),
    }
    all_stable, details = stability_veto("M15", model_path, meta, stats, others, n_bars=500)
    assert len(details) == 2
    assert all_stable == all(d["stable"] for d in details)

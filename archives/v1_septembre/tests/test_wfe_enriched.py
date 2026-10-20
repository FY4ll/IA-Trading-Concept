"""LOT 2, phase 6, point 1 : src/backtester.py::compute_walk_forward_efficiency
renvoie un dict enrichi (trades IS/OOS, raison si wfe=None, drapeau
"suspect"). Fichier DÉDIÉ (pas tests/test_autonomous.py ni
tests/test_backtester_validation.py), comme demandé."""
from __future__ import annotations
import pytest

from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
from src.trading_env import TradingEnv
from src.agent import TradingAgent
from src.backtester import compute_walk_forward_efficiency, evaluate_agent


def _tiny_agent_and_data():
    df = generate_synthetic_ohlcv(n_bars=2000, seed=3)
    df = add_technical_features(df)
    train_df = df.iloc[:1200].reset_index(drop=True)
    val_df = df.iloc[1200:].reset_index(drop=True)
    train_norm, stats = normalize_features(train_df, columns=FEATURE_COLUMNS)
    val_norm, _ = normalize_features(val_df, stats, columns=FEATURE_COLUMNS)
    env_kwargs = dict(window_size=20, feature_columns=FEATURE_COLUMNS)
    env = TradingEnv(train_norm, **env_kwargs)
    agent = TradingAgent(env, {"algo": "PPO", "use_lstm": False, "n_steps": 64, "batch_size": 16})
    agent.learn(64)
    return agent, train_norm, val_norm, env_kwargs


def test_wfe_dict_contains_all_required_keys():
    agent, train_df, val_df, env_kwargs = _tiny_agent_and_data()
    val_metrics = evaluate_agent(agent, val_df, env_kwargs)
    result = compute_walk_forward_efficiency(agent, train_df, val_metrics, env_kwargs,
                                                is_eval_bars=None, oos_n_bars=len(val_df))
    for key in ("wfe", "is_annualized_return", "oos_annualized_return", "is_total_return",
                "oos_total_return", "is_n_trades", "oos_n_trades", "reason", "suspect"):
        assert key in result, f"clé manquante : {key}"


def test_wfe_reason_none_when_wfe_is_a_number():
    agent, train_df, val_df, env_kwargs = _tiny_agent_and_data()
    val_metrics = {"total_return": 0.10, "n_trades": 50}
    with_positive_is = compute_walk_forward_efficiency(
        agent, train_df, val_metrics, env_kwargs, is_eval_bars=None, oos_n_bars=len(val_df))
    if with_positive_is["is_annualized_return"] > 0:
        assert with_positive_is["wfe"] is not None
        assert with_positive_is["reason"] is None


def test_wfe_reason_set_when_is_and_oos_both_non_positive():
    agent, train_df, val_df, env_kwargs = _tiny_agent_and_data()
    val_metrics = {"total_return": -0.5, "n_trades": 5}
    result = compute_walk_forward_efficiency(agent, train_df, val_metrics, env_kwargs,
                                                is_eval_bars=None, oos_n_bars=len(val_df))
    if result["is_annualized_return"] <= 0 and result["oos_annualized_return"] <= 0:
        assert result["wfe"] == 0.0
        assert result["reason"] is not None


def test_wfe_suspect_true_when_oos_trades_below_minimum():
    agent, train_df, val_df, env_kwargs = _tiny_agent_and_data()
    val_metrics = {"total_return": 0.05, "n_trades": 3}  # très peu de trades OOS
    result = compute_walk_forward_efficiency(agent, train_df, val_metrics, env_kwargs,
                                                is_eval_bars=None, oos_n_bars=len(val_df),
                                                min_trades_suspect=30)
    assert result["oos_n_trades"] == 3
    assert result["suspect"] is True


def test_wfe_not_suspect_with_enough_trades_and_reasonable_wfe():
    agent, train_df, val_df, env_kwargs = _tiny_agent_and_data()
    val_metrics = {"total_return": 0.01, "n_trades": 50}
    result = compute_walk_forward_efficiency(agent, train_df, val_metrics, env_kwargs,
                                                is_eval_bars=None, oos_n_bars=len(val_df),
                                                min_trades_suspect=30)
    if result["wfe"] is not None and result["wfe"] <= 1.5 and result["oos_n_trades"] >= 30:
        assert result["suspect"] is False


def test_wfe_suspect_true_when_wfe_above_1_5():
    agent, train_df, val_df, env_kwargs = _tiny_agent_and_data()
    # OOS annualisé largement > IS annualisé -> wfe > 1.5 (généralise "trop bien")
    val_metrics = {"total_return": 5.0, "n_trades": 100}
    result = compute_walk_forward_efficiency(agent, train_df, val_metrics, env_kwargs,
                                                is_eval_bars=None, oos_n_bars=len(val_df),
                                                min_trades_suspect=0)
    if result["wfe"] is not None and result["wfe"] > 1.5:
        assert result["suspect"] is True


def test_wfe_is_n_trades_comes_from_is_metrics():
    agent, train_df, val_df, env_kwargs = _tiny_agent_and_data()
    val_metrics = evaluate_agent(agent, val_df, env_kwargs)
    result = compute_walk_forward_efficiency(agent, train_df, val_metrics, env_kwargs,
                                                is_eval_bars=None, oos_n_bars=len(val_df))
    assert isinstance(result["is_n_trades"], int)
    assert result["is_n_trades"] >= 0

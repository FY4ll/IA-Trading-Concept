"""L'évaluation accélérée (src/fast_eval.py) doit donner EXACTEMENT les mêmes décisions et la même
courbe d'équité que l'évaluation pas à pas d'origine (backtester.run_episode)."""
from __future__ import annotations
import time

import numpy as np
import pytest

from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
from src.trading_env import TradingEnv
from src.agent import TradingAgent
from src.fast_eval import run_episode_fast, supported


def run_episode(agent, env):
    """Boucle pas à pas D'ORIGINE (référence) -- backtester.run_episode utilise désormais la voie rapide."""
    obs, _ = env.reset()
    done = False
    while not done:
        obs, _, term, trunc, _ = env.step(agent.predict(obs, deterministic=True))
        done = term or trunc
    return env


def _setup(n_bars=3000):
    df = add_technical_features(generate_synthetic_ohlcv(n_bars=n_bars, seed=11))
    df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]
    df["time"] = __import__("pandas").date_range("2024-01-01", periods=len(df), freq="15min")
    dfn, _ = normalize_features(df, columns=FEATURE_COLUMNS)
    kw = dict(window_size=50, initial_balance=10000, transaction_cost=0.0002, reward_type="risk_adjusted",
              drawdown_penalty=2.0, max_position=1, feature_columns=FEATURE_COLUMNS, learn_stop_loss=True,
              atr_stop_loss=True, learn_take_profit=True, take_profit_rr_buckets=[1.0, 2.0],
              learn_order_type=True, limit_offsets_atr=[0.0, 0.25, 0.5], max_stops_per_day=2,
              trader_state=True, style="AUREX")
    agent = TradingAgent(TradingEnv(dfn, **kw), {"n_steps": 128, "batch_size": 32, "ent_coef": 0.05})
    agent.learn(256)
    return dfn, kw, agent


def test_fast_eval_identical_decisions_and_equity():
    dfn, kw, agent = _setup()
    e1 = TradingEnv(dfn, **kw)
    assert supported(agent, e1)
    e1 = run_episode(agent, e1)
    e2 = run_episode_fast(agent, TradingEnv(dfn, **kw))
    assert len(e1.trade_log) == len(e2.trade_log), "même nombre de trades"
    np.testing.assert_allclose(e1.equity_curve, e2.equity_curve, rtol=1e-9, atol=1e-6)
    assert e1.n_limit_orders == e2.n_limit_orders


def test_fast_eval_is_faster():
    dfn, kw, agent = _setup(n_bars=4000)
    t0 = time.perf_counter(); run_episode(agent, TradingEnv(dfn, **kw)); slow = time.perf_counter() - t0
    t0 = time.perf_counter(); run_episode_fast(agent, TradingEnv(dfn, **kw)); fast = time.perf_counter() - t0
    print(f"pas à pas {slow:.2f}s, accéléré {fast:.2f}s, x{slow / fast:.1f}")
    assert fast < slow


def test_gpu_relecture_matches_cpu(monkeypatch):
    """10/10 : relecture des fenêtres sur la carte graphique quand le réseau vit sur le processeur -- même résultat
    (à 1e-4 près) que sur le processeur ; ignoré si aucune carte n'est visible (suite de tests sans carte)."""
    import numpy as np
    import pytest
    import torch
    if not torch.cuda.is_available():
        pytest.skip("pas de carte graphique visible")
    from src.fast_eval import precompute_lstm

    class Ex:
        lstm = torch.nn.LSTM(input_size=12, hidden_size=64, batch_first=True)
    fv = np.random.default_rng(0).normal(size=(700, 12)).astype(np.float32)
    monkeypatch.setenv("FAST_EVAL_GPU", "0")
    cpu = precompute_lstm(Ex, fv, 20)
    monkeypatch.setenv("FAST_EVAL_GPU", "1")
    gpu = precompute_lstm(Ex, fv, 20)
    assert gpu.device.type == "cpu", "résultat rendu au processeur (la tête de décision y vit)"
    assert float((gpu - cpu).abs().max()) < 1e-4

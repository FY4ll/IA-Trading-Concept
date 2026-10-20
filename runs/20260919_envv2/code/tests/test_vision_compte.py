"""VISION DU COMPTE (11/10/2026, point 3) : AUREXIS voit la baisse du compte et la part du budget prise par les autres
positions, et vit à l'entraînement les règles du vrai compte (frein, refus au-delà du budget). Greffe sans perte."""
import numpy as np
import pandas as pd
import pytest
import torch

from src.trading_env import TradingEnv

KW = dict(window_size=5, feature_columns=["f"], learn_stop_loss=True, stop_loss_buckets=[0.01, 0.02],
          atr_stop_loss=False, learn_take_profit=True, take_profit_rr_buckets=[1.0, 3.0], learn_trade_management=True,
          risk_sizing_pct=0.005, learn_position_size=True, transaction_cost=0.0)


def _df(n=300, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.002, n))
    return pd.DataFrame({"time": pd.date_range("2025-01-06", periods=n, freq="15min"), "open": close,
                         "high": close * 1.001, "low": close * 0.999, "close": close,
                         "f": rng.normal(size=n).astype("float32")})


BUY_1PCT = [2, 0, 0, 0, 3]          # achat, stop 1 %, objectif 1R, rien, risque 1 %


def test_two_new_inputs_only_for_the_account_style():
    off, on = TradingEnv(_df(), **KW), TradingEnv(_df(), **KW, account_state=True)
    assert on.EXTRA_DIM == off.EXTRA_DIM + 2 and on._get_obs().shape[0] == off._get_obs().shape[0] + 2
    on.live_state = {"account_dd": 0.06, "other_risk_share": 0.75}
    assert on._get_obs()[-2:] == pytest.approx([1.2, 0.75]), "baisse x20, part du budget"


def test_full_budget_refuses_the_opening_closing_still_allowed():
    env = TradingEnv(_df(), **KW, account_state=True)
    env.reset()
    env.live_state = {"account_dd": 0.0, "other_risk_share": 0.8}          # 3,2 % pris : 1 % ne passe plus
    env.step(BUY_1PCT)
    assert env.position == 0 and env.n_budget_refused == 1
    env.live_state = {"account_dd": 0.0, "other_risk_share": 0.5}          # 2 % pris : 1 % passe
    env.step(BUY_1PCT)
    assert env.position == 1 and env._trade_risk == pytest.approx(0.01)
    env.live_state = {"account_dd": 0.0, "other_risk_share": 1.0}
    env.step([1, 0, 0, 0, 3])                                              # fermer reste permis
    assert env.position == 0


def test_brake_halves_risk_and_budget_below_5pct():
    env = TradingEnv(_df(), **KW, account_state=True)
    env.reset()
    env.live_state = {"account_dd": 0.06, "other_risk_share": 0.3}         # 1,2 % pris, budget freiné 2 %
    env.step(BUY_1PCT)
    assert env.position == 1 and env._trade_risk == pytest.approx(0.005), "risque divisé par deux"
    env.step([1, 0, 0, 0, 3])
    env.live_state = {"account_dd": 0.06, "other_risk_share": 0.4}         # 1,6 % + 0,5 % > 2 %
    env.step(BUY_1PCT)
    assert env.position == 0


def test_simulated_other_positions_reproducible_in_exam_random_in_training():
    a, b = TradingEnv(_df(), **KW, account_state=True), TradingEnv(_df(), **KW, account_state=True)
    a.reset(); b.reset()
    sa, sb = [], []
    for _ in range(100):
        a.step([1, 0, 0, 0, 0]); b.step([1, 0, 0, 0, 0])
        sa.append(a._get_obs()[-1]); sb.append(b._get_obs()[-1])
    assert sa == sb and 0.0 <= min(sa) and max(sa) <= 1.0 and np.std(sa) > 0, "même examen = mêmes valeurs"
    t = TradingEnv(_df(), **KW, account_state=True, randomize_start=True)
    firsts = set()
    for s in range(5):
        t.reset(seed=s)
        firsts.add(round(float(t._get_obs()[-1]), 6))
    assert len(firsts) > 1, "chaque partie d'entraînement a ses propres autres positions"


def test_graft_keeps_decisions_identical():
    from src.agent import TradingAgent
    from src.network_growth import add_extra_inputs
    df = _df()
    old_env = TradingEnv(df, **KW)
    new_env = TradingEnv(df, **KW, account_state=True)
    hp = {"n_steps": 64, "batch_size": 16, "lstm_hidden_size": 16, "device": "cpu"}
    agent = TradingAgent(old_env, hp)
    old_env.reset(); new_env.reset()
    steps = range(10, 120)
    ref = []
    for s in steps:
        old_env.current_step = s
        ref.append(np.asarray(agent.predict(old_env._get_obs(), deterministic=True)).tolist())
    add_extra_inputs(agent, new_env, hp)
    assert agent.model.policy.features_extractor.extra_dim == old_env.EXTRA_DIM + 2
    rng = np.random.default_rng(3)
    for s, r in zip(steps, ref):
        new_env.current_step = s
        new_env.live_state = {"account_dd": float(rng.uniform(0, 0.1)), "other_risk_share": float(rng.uniform(0, 1))}
        assert np.asarray(agent.predict(new_env._get_obs(), deterministic=True)).tolist() == r
    w = agent.model.policy.features_extractor.head[0].weight
    assert torch.count_nonzero(w[:, -2:]) == 0, "nouvelles connexions à zéro au départ"

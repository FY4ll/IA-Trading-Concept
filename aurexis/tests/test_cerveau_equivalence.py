"""PREUVE de l'étape 2 (partie cerveau) : le nouveau simulateur joue EXACTEMENT la même partie que Run A (mêmes
gains, mêmes récompenses, mêmes observations), et le champion actuel prend EXACTEMENT les mêmes décisions."""
import os
import sys

import numpy as np
import pytest

STAGE = r"C:\Users\utilisateur\AppData\Local\Temp\claude\c--Users-utilisateur-Documents-Test-IA\f09ed3b3-c164-4391-9e5e-8ecc4a192738\scratchpad\code_stage"
CHAMPION = r"C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code\models\champion_AUREXIS\agent"
KW = dict(window_size=50, transaction_cost=0.00009, reward_type="risk_adjusted_v3", drawdown_penalty=2.0,
          learn_stop_loss=True, atr_stop_loss=True, learn_take_profit=True, take_profit_rr_buckets=[1.0, 1.5, 2.0, 3.0],
          learn_order_type=True, limit_offsets_atr=[0.0, 0.25, 0.5], max_stops_per_day=2, trader_state=True,
          daily_loss_halt_pct=0.025, prop_penalty_coef=0.5, prop_soft_loss_pct=0.015, learn_trade_management=True,
          be_trigger_r=0.5, trail_r=1.0, risk_sizing_pct=0.005, max_leverage=10.0, style="AUREXIS")


@pytest.fixture(scope="module")
def marche():
    from aurexis.donnees import marches, reserve
    from aurexis.vision.fabrique import construire
    m15 = reserve.lire("EURUSD", marches.source("EURUSD")).tail(6000).reset_index(drop=True)
    df = construire("EURUSD", m15, ["M30", "H1", "H4", "D1", "W1", "MN1"], None)
    import json
    cols = json.load(open(os.path.join(os.path.dirname(CHAMPION), "meta.json"), encoding="utf-8"))["feature_columns"]
    for c in cols:                                 # variables macro absentes ici -> neutres
        if c not in df.columns:
            df[c] = 0.0
    df = df.iloc[3000:].reset_index(drop=True)
    df[cols] = ((df[cols] - df[cols].mean()) / (df[cols].std() + 1e-8)).clip(-5, 5).fillna(0.0).astype("float32")
    return df, cols


@pytest.fixture(scope="module")
def ancien():
    if STAGE not in sys.path:
        sys.path.append(STAGE)
    import src.trading_env as old_env
    import src.agent as old_agent
    return old_env, old_agent


@pytest.mark.parametrize("reward", ["risk_adjusted_v3", "trade_r"])
def test_meme_partie_jouee(marche, ancien, reward):
    from aurexis.cerveau.simulateur import TradingEnv
    df, cols = marche
    kw = {**KW, "reward_type": reward, "feature_columns": cols}
    a, b = ancien[0].TradingEnv(df, **kw), TradingEnv(df, **kw)
    a.reset(seed=3)
    b.reset(seed=3)
    rng = np.random.default_rng(11)
    ra, rb, oa, ob = [], [], [], []
    for _ in range(2500):
        act = a.action_space.sample() if False else np.array([rng.integers(n) for n in a.action_space.nvec])
        o1, r1, t1, _, _ = a.step(act)
        o2, r2, t2, _, _ = b.step(act)
        ra.append(r1); rb.append(r2); oa.append(o1); ob.append(o2)
        if t1 or t2:
            break
    assert np.array_equal(np.asarray(a.equity_curve), np.asarray(b.equity_curve))
    assert np.array_equal(np.asarray(ra), np.asarray(rb)) and np.array_equal(np.asarray(oa), np.asarray(ob))
    assert len(a.trade_log) == len(b.trade_log) > 10


def test_champion_memes_decisions(marche, ancien):
    from aurexis.cerveau.agent import TradingAgent
    from aurexis.cerveau.simulateur import TradingEnv
    df, cols = marche
    kw = {**KW, "feature_columns": cols}
    ea, eb = ancien[0].TradingEnv(df, **kw), TradingEnv(df, **kw)
    ga = ancien[1].TradingAgent.load(CHAMPION, ea, {"algo": "PPO", "device": "cpu"})
    gb = TradingAgent.load(CHAMPION, eb, {"algo": "PPO", "device": "cpu"})
    oa, _ = ea.reset(seed=1)
    ob, _ = eb.reset(seed=1)
    for _ in range(300):
        x, _ = ga.model.predict(oa, deterministic=True)
        y, _ = gb.model.predict(ob, deterministic=True)
        assert np.array_equal(x, y)
        oa, _, ta, _, _ = ea.step(x)
        ob, _, tb, _, _ = eb.step(y)
        if ta or tb:
            break

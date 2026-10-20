"""COMPTE PARTAGÉ À L'ENTRAÎNEMENT (11/10/2026) : les parties jouées en parallèle tradent UN compte -- marchés
différents aux mêmes dates, budget de risque pris par ses propres positions, baisse du compte entier, nouveau
challenge à -9 % ou +10 %."""
import numpy as np
import pandas as pd
import pytest

from src.shared_account import SharedAccount
from src.trading_env import TradingEnv

KW = dict(window_size=5, feature_columns=["f"], learn_stop_loss=True, stop_loss_buckets=[0.01, 0.02],
          atr_stop_loss=False, learn_take_profit=True, take_profit_rr_buckets=[1.0, 3.0], learn_trade_management=True,
          risk_sizing_pct=0.005, learn_position_size=True, transaction_cost=0.0, account_state=True,
          account_shared=True, randomize_start=True)
BUY_1PCT = [2, 0, 0, 0, 3]


def _multi(n_markets=6, n=400, seed=0):
    rng = np.random.default_rng(seed)
    parts = []
    for m in range(n_markets):
        close = 100 * np.cumprod(1 + rng.normal(0, 0.001, n))
        parts.append(pd.DataFrame({"time": pd.date_range("2025-01-06", periods=n, freq="15min"), "open": close,
                                   "high": close * 1.001, "low": close * 0.999, "close": close,
                                   "f": rng.normal(size=n).astype("float32"), "segment_id": m}))
    return pd.concat(parts, ignore_index=True)


def test_account_math_budget_drawdown_and_new_challenge():
    a = SharedAccount(3)
    a.join(0, 1.0); a.join(1, 1.0); a.join(2, 1.0)
    a.update(0, 1.0, 0.01); a.update(1, 1.0, 0.02)
    assert a.view(2) == pytest.approx((0.0, 0.75)) and a.view(0)[1] == pytest.approx(0.5), "budget pris par les autres"
    a.update(0, 0.97, 0.0)
    assert a.view(1)[0] == pytest.approx(0.03), "baisse du compte ENTIER"
    a.join(0, 1.0)
    assert a.equity() == pytest.approx(0.97), "le résultat d'une partie finie reste acquis au compte"
    a.update(1, 0.94, 0.0)                                                  # compte à 0,91 : mur des -9 %
    assert a.restarts["mur"] == 1 and a.equity() == pytest.approx(1.0) and a.peak == 1.0
    a.update(1, 0.94 * 1.10, 0.0)
    assert a.restarts["objectif"] == 1, "+10 % : challenge réussi, nouveau compte"


def test_parallel_games_fill_one_budget():
    df = _multi()
    envs = [TradingEnv(df, **KW) for _ in range(5)]
    envs[0].link_account(envs)
    for i, e in enumerate(envs):
        e.reset(seed=i)
    assert len({e._market for e in envs}) == 5, "chaque partie joue un marché différent"
    for e in envs:
        e.step(BUY_1PCT)
    opened = [e.position != 0 for e in envs]
    assert sum(opened) == 4 and sum(e.n_budget_refused for e in envs) == 1, "4 x 1 % = budget plein, le 5e refusé"
    assert envs[4]._get_obs()[-1] == pytest.approx(1.0), "elle VOIT que ses autres positions ont pris le budget"


def test_starts_are_aligned_on_the_other_games_clock():
    df = _multi()
    envs = [TradingEnv(df, **KW) for _ in range(3)]
    envs[0].link_account(envs)
    envs[0].reset(seed=1); envs[1].reset(seed=2)
    for _ in range(30):
        envs[0].step([1, 0, 0, 0, 0]); envs[1].step([1, 0, 0, 0, 0])
    envs[2].reset(seed=3)
    gap = abs(envs[2]._time_at() - envs[2]._shared.clock(2))
    assert gap <= pd.Timedelta("15min").value, "nouveau départ calé sur l'horloge des autres parties"


def test_games_are_cut_to_keep_clocks_close():
    df = _multi()
    envs = [TradingEnv(df, **{**KW, "account_episode_bars": 20}) for _ in range(2)]
    envs[0].link_account(envs)
    envs[0].reset(seed=0)
    for k in range(20):
        _, _, term, trunc, _ = envs[0].step([1, 0, 0, 0, 0])
    assert trunc and not term


def test_agent_links_its_parallel_games_and_exam_envs_stay_alone():
    from src.agent import TradingAgent
    df = _multi()
    env = TradingEnv(df, **KW)
    agent = TradingAgent(env, {"n_steps": 32, "batch_size": 16, "lstm_hidden_size": 16, "device": "cpu", "n_envs": 3})
    games = agent.model.get_env().envs
    assert len(games) == 3 and all(g._shared is games[0]._shared for g in games) and games[0]._shared is not None
    assert [g._slot for g in games] == [0, 1, 2]
    agent.model.learn(64)                                                   # l'apprentissage tourne avec le compte
    solo = TradingEnv(df, **{**KW, "account_shared": False, "randomize_start": False})
    assert solo._shared is None, "examens et direct : jamais de compte partagé"

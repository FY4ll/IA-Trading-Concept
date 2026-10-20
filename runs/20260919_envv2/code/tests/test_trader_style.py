"""Tests du TRADER (05/10/2026) : ordres limite/marché appris dans TradingEnv, vision complète sans
information future, style reconnu."""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

from src.data_loader import generate_synthetic_ohlcv
from src.trading_env import TradingEnv


def _env(df, **kw):
    base = dict(window_size=10, initial_balance=10000, transaction_cost=0.0, reward_type="risk_adjusted",
                drawdown_penalty=0.0, max_position=1, feature_columns=["f"], learn_stop_loss=True,
                stop_loss_buckets=[0.01], atr_stop_loss=False, learn_take_profit=True,
                take_profit_rr_buckets=[50.0], learn_order_type=True, limit_offsets_atr=[0.0, 0.5])
    base.update(kw)
    return TradingEnv(df, **base)


def _df(n=40, low_next=None):
    close = np.full(n, 100.0)
    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=n, freq="15min"),
                       "open": close, "high": close + 0.5, "low": close - 0.5, "close": close, "f": 0.0,
                       "atr_14": 2.0})
    df[TradingEnv.ATR_RAW_COLUMN] = 2.0
    return df


def test_action_space_has_order_type_dimension():
    env = _env(_df())
    assert list(env.action_space.nvec) == [3, 1, 1, 2]
    env2 = _env(_df(), learn_order_type=False)
    assert list(env2.action_space.nvec) == [3, 1, 1], "sans l'option, H1T/H1XT gardent leur espace d'action"


def test_limit_not_reached_means_no_entry_and_market_fills():
    df = _df()
    env = _env(df)
    env.reset()
    env.current_step = 15
    # limite d'achat à 0,5 ATR (1 $) sous 100 : la bougie suivante descend seulement à 99,5 -> pas remplie
    env.step(np.array([2, 0, 0, 1]))
    assert env.position == 0 and env.n_limit_orders == 1 and env.n_limit_filled == 0
    env.step(np.array([2, 0, 0, 0]))          # ordre au marché : entrée à l'ouverture suivante
    assert env.position == 1 and env.entry_price == pytest.approx(100.0)


def test_limit_reached_fills_at_limit_price():
    df = _df()
    df.loc[16, "low"] = 98.0                   # la bougie suivante descend à 98 -> limite à 99 remplie
    env = _env(df)
    env.reset()
    env.current_step = 15
    env.step(np.array([2, 0, 0, 1]))
    assert env.position == 1 and env.n_limit_filled == 1
    assert env.entry_price == pytest.approx(99.0), "remplie au prix limite, sans slippage"


def test_trader_vision_has_no_lookahead():
    from src.trader.vision import add_trader_vision, TV_COLUMNS
    raw = generate_synthetic_ohlcv(n_bars=6000, seed=5)
    raw["time"] = pd.date_range("2024-01-01 01:00", periods=len(raw), freq="15min")
    raw = raw[raw["time"].dt.dayofweek < 5].reset_index(drop=True)
    full = add_trader_vision(raw)
    part = add_trader_vision(raw.iloc[:3000])
    a = full[TV_COLUMNS].iloc[:3000].to_numpy()
    b = part[TV_COLUMNS].to_numpy()
    np.testing.assert_allclose(a, b, atol=1e-9, err_msg="une variable de vision change quand on ajoute le futur")
    assert np.isfinite(full[TV_COLUMNS].to_numpy()).all()


def test_news_time_conversion_and_features():
    from src.trader.vision import _utc_to_server, _event_features
    # NFP 09/10/2026 12:30 UTC = 08:30 New York (heure d'été) = 15:30 heure serveur (NY + 7 h)
    srv = _utc_to_server(pd.Series(["2026-10-09T12:30:00"]))
    assert srv.iloc[0] == pd.Timestamp("2026-10-09 15:30")
    ev = srv.to_numpy(dtype="datetime64[ns]")
    now = pd.Series(pd.to_datetime(["2026-10-09 15:00", "2026-10-09 09:30", "2026-10-09 16:00", "2026-10-12 12:00"]))
    f = _event_features(now, ev)
    assert f["tv_ev_window"].tolist() == [1.0, 0.0, 1.0, 0.0]
    assert f["tv_ev_to_next"].iloc[1] == pytest.approx(6 / 72)
    assert f["tv_ev_today"].iloc[1] == 1.0 and f["tv_ev_today"].iloc[3] == 0.0


def test_trader_state_dims_and_tracking():
    df = _df(60)
    env = _env(df, trader_state=True, max_stops_per_day=2)
    base = _env(df)
    assert env.observation_space.shape[0] == base.observation_space.shape[0] + 3
    env.reset()
    env.current_step = 15
    env.step(np.array([2, 0, 0, 0]))
    env.step(np.array([2, 0, 0, 0]))
    env.step(np.array([2, 0, 0, 0]))
    assert env._bars_in_pos == 3
    obs = env._get_obs()
    assert obs[-1] == pytest.approx(3 / 96)
    env.live_state = {"stops_today": 1, "day_pnl": -0.01, "bars_in_position": 48}
    obs = env._get_obs()
    assert obs[-3:].tolist() == pytest.approx([0.5, -0.2, 0.5])


def test_live_decision_sees_real_position(tmp_path, monkeypatch):
    """L'IA doit voir sa position MT5 réelle (avant le 05/10 l'environnement live était toujours à plat)."""
    from src.demo_trader import _StyleRuntime
    df = _df(80)
    env_kwargs = dict(window_size=10, initial_balance=10000, transaction_cost=0.0, reward_type="risk_adjusted",
                      drawdown_penalty=0.0, max_position=1, learn_stop_loss=True, stop_loss_buckets=[0.01],
                      atr_stop_loss=False, learn_take_profit=True, take_profit_rr_buckets=[50.0])
    seen = {}

    class Agent:
        def predict(self, obs, deterministic=True):
            seen["obs"] = obs
            return np.array([1, 0, 0])

        def predict_proba(self, obs):
            return {"short": 0.1, "flat": 0.8, "long": 0.1}

    import src.demo_trader as dt
    monkeypatch.setattr(dt, "_build_live_dataframe", lambda *a, **k: df.copy())
    monkeypatch.setattr(dt, "normalize_features", lambda d, stats, columns=None: (d, stats))
    rt = _StyleRuntime()
    rt.agent, rt.stats, rt.feature_columns = Agent(), {}, ["f"]
    rt.mtf_config = {"primary_timeframe": "M15", "context_timeframes": []}
    rt.decide(None, None, 80, None, 5, env_kwargs,
              live_position={"direction": -1, "price_open": 101.0, "sl": 103.0, "tp": 95.0})
    extra = seen["obs"][-5:]
    assert extra[0] == -1.0, "position réelle vendeuse visible"
    assert extra[1] == pytest.approx((100.0 - 101.0) / 101.0 * -1), "gain latent réel visible"
    assert extra[4] == pytest.approx(2.0 / 101.0), "distance du stop réel visible"


def test_intraday_markets_aligned_without_lookahead():
    from src.trader.vision import _intraday_features
    idx = pd.date_range("2024-01-02 01:00", periods=300, freq="15min")
    eur = pd.Series(1.10 + np.cumsum(np.random.default_rng(1).normal(0, 1e-4, 300)), index=idx)
    gold_close = pd.Series(idx + pd.Timedelta(minutes=15))          # clôtures des bougies de l'or
    f = _intraday_features(gold_close, {"eur": eur})
    r1 = eur.pct_change() / eur.pct_change().rolling(96, min_periods=30).std()
    # à la clôture de la bougie i de l'or, on voit le rendement de la bougie i de l'EURUSD (déjà close), pas i+1
    assert f["tv_eur_r1"].iloc[200] == pytest.approx(r1.iloc[200])
    assert (f["tv_spx_r1"] == 0).all(), "marché absent -> neutre"
    late = _intraday_features(pd.Series([idx[-1] + pd.Timedelta(hours=5)]), {"eur": eur})
    assert np.isnan(late["tv_eur_r1"].iloc[0]), "donnée trop ancienne (> 2 h) -> pas utilisée"


def test_style_trader_base_timeframe():
    from src.style_utils import base_timeframe
    assert base_timeframe("AUREX") == "M15" and base_timeframe("TRADER") == "M15" and base_timeframe("H1XT") == "H1" and base_timeframe("H1") == "H1"

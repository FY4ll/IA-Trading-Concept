"""
test_take_profit_live.py
========================
Style "H1T" (H1 + take-profit appris) : correspondance style -> timeframe de données, réglages
d'espace d'action propres au style en démo, et champ `tp` des ordres MT5.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.style_utils import base_timeframe
from src.demo_trader import _style_env_kwargs, TIMEFRAME_HIERARCHY
from src.mt5_connector import MT5Connector
from src.trading_env import TradingEnv


def test_base_timeframe():
    assert base_timeframe("H1T") == "H1"
    assert base_timeframe("H1") == "H1"
    assert base_timeframe("M30") == "M30"
    assert base_timeframe("H4") == "H4"
    assert base_timeframe(None) is None


def test_style_env_kwargs_only_takes_action_space_keys():
    cfg = {"environment": {"style_overrides": {"H1T": {"learn_take_profit": True, "drawdown_penalty": 2.0,
                                                        "take_profit_rr_buckets": [1.0, 2.0]}}}}
    base = {"learn_stop_loss": True, "drawdown_penalty": 0.5}
    out = _style_env_kwargs(cfg, "H1T", base)
    assert out["learn_take_profit"] is True and out["take_profit_rr_buckets"] == [1.0, 2.0]
    assert out["drawdown_penalty"] == 0.5
    assert _style_env_kwargs(cfg, "H1", base) is base


def test_h1t_env_uses_h1_buckets_and_has_tp_dimension():
    import numpy as np, pandas as pd
    n = 200
    df = pd.DataFrame({"close": np.linspace(100, 110, n), "open": np.linspace(100, 110, n),
                       "high": np.linspace(101, 111, n), "low": np.linspace(99, 109, n), "f": np.zeros(n)})
    e1 = TradingEnv(df, feature_columns=["f"], style="H1", learn_stop_loss=True, window_size=10)
    e2 = TradingEnv(df, feature_columns=["f"], style="H1T", learn_stop_loss=True, learn_take_profit=True,
                    window_size=10)
    assert e2.stop_loss_buckets == e1.stop_loss_buckets
    assert list(e1.action_space.nvec) == [3, len(e1.stop_loss_buckets)]
    assert list(e2.action_space.nvec) == [3, len(e1.stop_loss_buckets), 4]


class _Info:
    digits = 2


class _FakeMt5:
    def symbol_info(self, symbol):
        return _Info()


def _connector():
    c = MT5Connector.__new__(MT5Connector)
    c._mt5 = _FakeMt5()
    c.symbol = "XAUUSD"
    return c


def test_take_profit_field_long_and_short():
    c = _connector()
    assert c._take_profit_field(4000.0, 1, 0.01, 2.0) == {"tp": 4080.0}
    assert c._take_profit_field(4000.0, -1, 0.01, 2.0) == {"tp": 3920.0}


def test_take_profit_field_absent_without_rr_or_stop():
    c = _connector()
    assert c._take_profit_field(4000.0, 1, 0.01, None) == {}
    assert c._take_profit_field(4000.0, 1, None, 2.0) == {}


def _stop_cap_env(max_stops):
    import numpy as np, pandas as pd
    n = 120
    close = np.full(n, 100.0)
    low = np.full(n, 99.9)
    low[30:] = 90.0  # chaque bougie touche tout stop long
    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=n, freq="h"), "close": close,
                       "open": close, "high": close + 0.1, "low": low, "f": np.zeros(n)})
    return TradingEnv(df, feature_columns=["f"], style="H1T", learn_stop_loss=True, learn_take_profit=True,
                      atr_stop_loss=False, window_size=10, max_stops_per_day=max_stops)


def _open_count_after_stops(max_stops):
    env = _stop_cap_env(max_stops)
    env.reset()
    env.current_step = 30
    for _ in range(15):
        env.step([2, 0, 0])
    return len(env.trade_log)


def test_max_stops_per_day_blocks_reopening_same_day():
    assert _open_count_after_stops(1) < _open_count_after_stops(0)


def test_max_stops_per_day_disabled_by_default():
    assert _stop_cap_env(0)._day_id is None


def test_hierarchy_knows_h1t():
    assert TIMEFRAME_HIERARCHY["H1T"] > TIMEFRAME_HIERARCHY["H1"]

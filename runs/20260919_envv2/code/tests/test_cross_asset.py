"""Phase 2 : variables hors XAUUSD (style H1X) -- anti-look-ahead, nombre de lignes, valeurs neutres."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pandas as pd

from src.cross_asset import add_cross_asset_features, X_COLUMNS, has_cross_columns
from src.style_utils import base_timeframe


def _hourly(n_days=60):
    t = pd.date_range("2024-01-01", periods=n_days * 24, freq="h")
    return pd.DataFrame({"time": t, "close": 1.0})


def _daily_close(n_days=60, jump_day=40):
    idx = pd.date_range("2024-01-01", periods=n_days, freq="D")
    s = pd.Series(100.0, index=idx)
    s.iloc[jump_day:] = 150.0
    return s


def test_style_regex():
    assert base_timeframe("H1X") == "H1" and base_timeframe("H1T") == "H1" and base_timeframe("H1") == "H1"
    assert base_timeframe("M30X") == "M30"


def test_rows_preserved_and_columns_added():
    df = _hourly()
    out = add_cross_asset_features(df, fred=None, daily_provider=lambda s: _daily_close())
    assert len(out) == len(df)
    assert all(c in out.columns for c in X_COLUMNS)
    assert not out[X_COLUMNS].isna().any().any()
    assert has_cross_columns(out.columns) and not has_cross_columns(["close", "rsi"])


def test_no_look_ahead_daily_jump_visible_only_next_day():
    df = _hourly()
    out = add_cross_asset_features(df, fred=None, daily_provider=lambda s: _daily_close(jump_day=40))
    jump_date = pd.Timestamp("2024-01-01") + pd.Timedelta(days=40)
    dates = pd.to_datetime(out["time"]).dt.normalize()
    day_of = out[dates == jump_date]
    day_after = out[dates == jump_date + pd.Timedelta(days=1)]
    assert (day_of["x_EURUSD_ret1"] == 0).all()
    assert (day_after["x_EURUSD_ret1"] > 0.4).all()


def _boom(symbol):
    raise RuntimeError("source indisponible")


def test_missing_sources_are_neutral():
    out = add_cross_asset_features(_hourly(), fred=None, daily_provider=None)
    assert (out[X_COLUMNS] == 0).all().all()
    out2 = add_cross_asset_features(_hourly(), fred=None, daily_provider=_boom)
    assert (out2[X_COLUMNS] == 0).all().all()

"""
cross_asset.py
==============
Variables HORS XAUUSD pour les styles "X" (ex: H1X) : l'IA voit aussi, en plus de l'or,
  - d'autres marchés (EURUSD = proxy dollar, USDJPY = yen/risk, XAGUSD = argent) via leurs
    bougies QUOTIDIENNES (rendement 1 j / 5 j et position vs moyenne 20 j) ;
  - les séries macro FRED prises une par une (taux réel, dollar large, VIX, breakeven) :
    z-score 20 obs. et variation sur 5 obs.

ANTI-LOOK-AHEAD : chaque valeur journalière est décalée d'une bougie (la bougie H1 du jour J ne
voit que ce qui était clos avant J). Mêmes formules en entraînement (CSV quotidiens) et en démo
(bougies D1 MT5). Une source absente donne 0.0 (neutre) -- jamais d'exception ni de ligne perdue.
"""
from __future__ import annotations
import logging
import os
import time

import numpy as np
import pandas as pd

log = logging.getLogger("cross_asset")

CROSS_SYMBOLS = ["EURUSD", "USDJPY", "XAGUSD"]
FRED_IDS = ["DFII10", "DTWEXBGS", "VIXCLS", "T10YIE"]

X_COLUMNS = ([f"x_{s}_{k}" for s in CROSS_SYMBOLS for k in ("ret1", "ret5", "z20")]
             + [f"x_{f}_{k}" for f in FRED_IDS for k in ("z20", "chg5")])


def has_cross_columns(columns) -> bool:
    return any(str(c).startswith("x_") for c in (columns or []))


def _asset_daily_features(close: pd.Series, symbol: str) -> pd.DataFrame:
    close = close.sort_index()
    roll = close.rolling(20, min_periods=10)
    out = pd.DataFrame({
        f"x_{symbol}_ret1": close.pct_change(1),
        f"x_{symbol}_ret5": close.pct_change(5),
        f"x_{symbol}_z20": (close - roll.mean()) / (roll.std(ddof=0) + 1e-12),
    }, index=close.index)
    return out.shift(1)


def _fred_daily_features(fred) -> pd.DataFrame | None:
    from src.fred_feed import _fetch_history, HIST_START
    days = pd.date_range(HIST_START, pd.Timestamp.today().normalize() + pd.Timedelta(days=1), freq="D")
    cols = {}
    for sid in FRED_IDS:
        s = _fetch_history(fred, sid)
        if len(s) < 30:
            continue
        roll = s.rolling(20, min_periods=10)
        z = ((s - roll.mean()) / (roll.std(ddof=0) + 1e-12)).replace([np.inf, -np.inf], np.nan)
        cols[f"x_{sid}_z20"] = z.reindex(days).ffill().shift(1)
        cols[f"x_{sid}_chg5"] = (z - z.shift(5)).reindex(days).ffill().shift(1)
    return pd.DataFrame(cols, index=days) if cols else None


def _align_daily(df_dates: pd.Series, daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily[~daily.index.duplicated(keep="last")].sort_index()
    return daily.reindex(pd.DatetimeIndex(df_dates), method="ffill")


def add_cross_asset_features(df: pd.DataFrame, fred=None, daily_provider=None) -> pd.DataFrame:
    """Ajoute X_COLUMNS à `df` (colonne 'time' requise). `daily_provider(symbol)` -> pd.Series
    des clôtures D1 (index = date) ou None. Même nombre de lignes qu'en entrée."""
    df = df.copy()
    dates = pd.to_datetime(df["time"]).dt.normalize()
    frames = []
    if daily_provider is not None:
        for sym in CROSS_SYMBOLS:
            try:
                close = daily_provider(sym)
            except Exception as exc:
                log.warning(f"Données quotidiennes {sym} indisponibles ({exc}) -> variables neutres.")
                continue
            if close is None or len(close) < 30:
                continue
            frames.append(_align_daily(dates, _asset_daily_features(close.astype(float), sym)).reset_index(drop=True))
    if fred is not None:
        try:
            fd = _fred_daily_features(fred)
            if fd is not None:
                frames.append(_align_daily(dates, fd).reset_index(drop=True))
        except Exception as exc:
            log.warning(f"Séries FRED indisponibles ({exc}) -> variables neutres.")
    feats = pd.concat(frames, axis=1) if frames else pd.DataFrame(index=range(len(df)))
    df = df.reset_index(drop=True)
    for col in X_COLUMNS:
        df[col] = (feats[col].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
                   if col in feats.columns else 0.0)
    return df


# ---------------------------------------------------------------- sources ---
def csv_path(folder: str, symbol: str) -> str:
    return os.path.join(folder, f"{symbol}_D1.csv")


def csv_daily_provider(folder: str):
    def provider(symbol: str):
        path = csv_path(folder, symbol)
        if not os.path.exists(path):
            return None
        d = pd.read_csv(path, parse_dates=["time"])
        return d.set_index(d["time"].dt.normalize())["close"]
    return provider


def mt5_daily_provider(connector, n_bars: int = 150):
    def provider(symbol: str):
        d = connector.get_symbol_bars(symbol, "D1", n_bars)
        return d.set_index(d["time"].dt.normalize())["close"]
    return provider


def refresh_daily_csv(folder: str, max_age_hours: float = 20.0, n_bars: int = 6000) -> None:
    """Met à jour les CSV quotidiens depuis le terminal MT5 (best-effort : jamais d'exception)."""
    os.makedirs(folder, exist_ok=True)
    stale = [s for s in CROSS_SYMBOLS if not os.path.exists(csv_path(folder, s))
             or time.time() - os.path.getmtime(csv_path(folder, s)) > max_age_hours * 3600]
    if not stale:
        return
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return
        for sym in stale:
            mt5.symbol_select(sym, True)
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, n_bars)
            if rates is None or len(rates) < 100:
                continue
            d = pd.DataFrame(rates)
            d["time"] = pd.to_datetime(d["time"], unit="s")
            d[["time", "close"]].to_csv(csv_path(folder, sym), index=False)
            log.info(f"Variables croisées : {sym} D1 mis à jour ({len(d)} bougies, jusqu'au {d['time'].iloc[-1].date()}).")
    except Exception as exc:
        log.warning(f"Mise à jour des bougies quotidiennes croisées impossible ({exc}).")

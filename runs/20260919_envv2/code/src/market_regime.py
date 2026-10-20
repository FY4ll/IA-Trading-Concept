"""
market_regime.py
=================
Régime de marché EXPLICITE (05/10/2026, vision "Autonomous Trader V1", §6-8) :
tendance (TREND_UP / TREND_DOWN / RANGE / TRANSITION / UNKNOWN), classe de
volatilité (LOW / NORMAL / HIGH / EXTREME) et structure de marché (HH/HL/LH/LL).

Calcul déterministe sur les seules bougies déjà présentes dans le DataFrame
(jamais de valeur future). Deux formes :
  - detect_regime(df)  : l'état à la DERNIÈRE bougie (décision live) ;
  - regime_series(df)  : une ligne par bougie (backtests, rapports par régime).

Ce module n'est PAS une feature d'observation de l'IA (les modèles entraînés
ne changent pas) : il sert au journal de décision, aux rapports par régime et
au filtre de marché hors de portée de l'IA (src/market_gate.py).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

TREND_UP, TREND_DOWN, RANGE, TRANSITION, UNKNOWN = "TREND_UP", "TREND_DOWN", "RANGE", "TRANSITION", "UNKNOWN"
VOL_LOW, VOL_NORMAL, VOL_HIGH, VOL_EXTREME = "LOW", "NORMAL", "HIGH", "EXTREME"

DEFAULTS = {
    "er_window": 48,        # ~2 jours en H1
    "trend_er": 0.30,       # efficacité >= 0.30 -> tendance
    "range_er": 0.15,       # efficacité < 0.15 -> range
    "vol_lookback": 500,    # ~1 mois de bougies H1 pour le percentile de volatilité
    "vol_low": 0.20, "vol_high": 0.80, "vol_extreme": 0.97,
    "swing_k": 3,           # pivot = plus haut/bas de k bougies de chaque côté
}


def _atr_pct(df: pd.DataFrame) -> pd.Series:
    if "atr_pct" in df.columns:
        return df["atr_pct"].astype(float)
    if "atr_14" in df.columns:
        return (df["atr_14"] / df["close"]).astype(float)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift()).abs(),
                    (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    return (tr.rolling(14).mean() / df["close"]).astype(float)


def efficiency_ratio(close: pd.Series, n: int) -> pd.Series:
    """Kaufman : |déplacement net sur n| / somme des |déplacements| -- 1 = ligne droite, 0 = bruit."""
    net = close.diff(n).abs()
    path = close.diff().abs().rolling(n).sum()
    return (net / path.replace(0, np.nan)).fillna(0.0)


def _vol_class(p: float, cfg: dict) -> str:
    if p is None or not np.isfinite(p):
        return UNKNOWN
    if p >= cfg["vol_extreme"]:
        return VOL_EXTREME
    if p >= cfg["vol_high"]:
        return VOL_HIGH
    if p < cfg["vol_low"]:
        return VOL_LOW
    return VOL_NORMAL


def _trend_label(er: float, direction: float, cfg: dict) -> str:
    if er is None or not np.isfinite(er):
        return UNKNOWN
    if er >= cfg["trend_er"]:
        return TREND_UP if direction > 0 else TREND_DOWN
    if er < cfg["range_er"]:
        return RANGE
    return TRANSITION


def swing_structure(high: np.ndarray, low: np.ndarray, k: int = 3) -> dict:
    """Compare les deux derniers pivots CONFIRMÉS (k bougies de chaque côté, donc jamais la
    bougie en cours) : HH/LH pour les hauts, HL/LL pour les bas."""
    n = len(high)
    sh, sl = [], []
    for i in range(k, n - k):
        if high[i] == max(high[i - k:i + k + 1]):
            sh.append((i, float(high[i])))
        if low[i] == min(low[i - k:i + k + 1]):
            sl.append((i, float(low[i])))
    out = {"swing_high": sh[-1][1] if sh else None, "swing_low": sl[-1][1] if sl else None,
           "highs": None, "lows": None, "structure": UNKNOWN}
    if len(sh) >= 2:
        out["highs"] = "HH" if sh[-1][1] > sh[-2][1] else "LH"
    if len(sl) >= 2:
        out["lows"] = "HL" if sl[-1][1] > sl[-2][1] else "LL"
    if out["highs"] and out["lows"]:
        if out["highs"] == "HH" and out["lows"] == "HL":
            out["structure"] = "BULLISH"
        elif out["highs"] == "LH" and out["lows"] == "LL":
            out["structure"] = "BEARISH"
        else:
            out["structure"] = "MIXED"
    return out


def detect_regime(df: pd.DataFrame, cfg: dict | None = None) -> dict:
    """État de marché à la dernière bougie de `df` (colonnes open/high/low/close, atr_14 optionnel)."""
    c = {**DEFAULTS, **(cfg or {})}
    n = c["er_window"]
    if df is None or len(df) < n + 2 or "close" not in df.columns:
        return {"regime": UNKNOWN, "vol_class": UNKNOWN, "structure": UNKNOWN}
    close = df["close"].astype(float).reset_index(drop=True)
    er = float(efficiency_ratio(close, n).iloc[-1])
    direction = float(close.iloc[-1] - close.iloc[-1 - n])
    atrp = _atr_pct(df).reset_index(drop=True)
    window = atrp.iloc[-c["vol_lookback"]:].dropna()
    vol_pct = float((window <= window.iloc[-1]).mean()) if len(window) >= 50 else float("nan")
    tail = df.iloc[-200:]
    sw = swing_structure(tail["high"].to_numpy(float), tail["low"].to_numpy(float), c["swing_k"]) \
        if {"high", "low"} <= set(df.columns) else {"structure": UNKNOWN}
    out = {
        "regime": _trend_label(er, direction, c),
        "vol_class": _vol_class(vol_pct, c),
        "vol_percentile": None if not np.isfinite(vol_pct) else round(vol_pct, 4),
        "efficiency_ratio": round(er, 4),
        "atr_pct": float(atrp.iloc[-1]) if np.isfinite(atrp.iloc[-1]) else None,
        **sw,
    }
    if "atr_14" in df.columns:
        out["atr"] = float(df["atr_14"].iloc[-1])
    return out


def regime_series(df: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """Régime et classe de volatilité pour CHAQUE bougie (fenêtres glissantes, sans futur)."""
    c = {**DEFAULTS, **(cfg or {})}
    n = c["er_window"]
    close = df["close"].astype(float)
    er = efficiency_ratio(close, n)
    direction = close.diff(n)
    atrp = _atr_pct(df)
    vol_pct = atrp.rolling(c["vol_lookback"], min_periods=50).rank(pct=True)
    regime = np.where(er >= c["trend_er"], np.where(direction > 0, TREND_UP, TREND_DOWN),
                      np.where(er < c["range_er"], RANGE, TRANSITION))
    regime = np.where(direction.isna(), UNKNOWN, regime)
    vp = vol_pct.to_numpy()
    vol = np.full(len(df), UNKNOWN, dtype=object)
    ok = np.isfinite(vp)
    vol[ok] = VOL_NORMAL
    vol[ok & (vp < c["vol_low"])] = VOL_LOW
    vol[ok & (vp >= c["vol_high"])] = VOL_HIGH
    vol[ok & (vp >= c["vol_extreme"])] = VOL_EXTREME
    return pd.DataFrame({"regime": regime, "vol_class": vol, "efficiency_ratio": er.to_numpy(),
                         "vol_percentile": vp}, index=df.index)

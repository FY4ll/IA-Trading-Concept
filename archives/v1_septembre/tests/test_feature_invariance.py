"""LOT 2, phase 4, point 1 : audit d'invariance des features (dépendance au
niveau de prix ou à l'échelle de volatilité) -- condition nécessaire avant
tout entraînement multi-actifs (mélanger XAUUSD ~2000$ et un instrument à
~1.0 sans conversion rendrait les features incohérentes d'un actif à
l'autre). Fichier DÉDIÉ (pas tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, FEATURE_COLUMNS


def _scaled_ohlcv(scale: float, seed: int) -> pd.DataFrame:
    """Même dynamique relative (mêmes rendements en %), mais un niveau de
    prix totalement différent -- simule "un autre instrument" sans avoir
    besoin de vraies données EURUSD/SPX (voir src/multi_asset.py, même
    absence de données réelles documentée)."""
    df = generate_synthetic_ohlcv(n_bars=2000, seed=seed)
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col] * scale
    return df


def test_atr_pct_is_scale_invariant_across_price_levels():
    """atr_pct (remplace atr_14 brut dans FEATURE_COLUMNS, LOT 2 phase 4) ne
    doit PAS dépendre du niveau de prix -- même série de rendements à deux
    échelles de prix différentes -> mêmes valeurs d'atr_pct."""
    cheap = add_technical_features(_scaled_ohlcv(1.0, seed=11))
    expensive = add_technical_features(_scaled_ohlcv(2000.0, seed=11))
    n = min(len(cheap), len(expensive))
    assert np.allclose(cheap["atr_pct"].to_numpy()[:n], expensive["atr_pct"].to_numpy()[:n], rtol=1e-6), \
        "atr_pct doit être identique quel que soit le niveau de prix absolu (même dynamique relative)"


def test_raw_atr_14_still_in_price_units_unconverted():
    """atr_14 (colonne brute, PAS dans FEATURE_COLUMNS) doit rester en
    UNITÉS DE PRIX -- nécessaire tel quel pour TradingEnv.ATR_RAW_COLUMN
    (stop-loss en multiples d'ATR, jamais une fraction sans dimension)."""
    cheap = add_technical_features(_scaled_ohlcv(1.0, seed=11))
    expensive = add_technical_features(_scaled_ohlcv(2000.0, seed=11))
    n = min(len(cheap), len(expensive))
    # atr_14 DOIT différer d'environ le même facteur d'échelle (2000x) --
    # contrairement à atr_pct, il porte l'information de prix absolu.
    ratio = expensive["atr_14"].to_numpy()[:n] / cheap["atr_14"].to_numpy()[:n]
    assert np.allclose(ratio, 2000.0, rtol=0.05)


def test_atr_pct_not_atr_14_is_the_observation_feature():
    assert "atr_pct" in FEATURE_COLUMNS
    assert "atr_14" not in FEATURE_COLUMNS


@pytest.mark.parametrize("col", [
    "return_1", "log_return", "rsi_14", "macd", "macd_signal", "bb_pct",
    "trend_signal", "adx_14", "volatility_regime",
])
def test_already_scale_invariant_features_unaffected_by_price_level(col):
    """Les features déjà normalisées par construction (rendements, ratios
    déjà divisés par le prix, oscillateurs bornés) doivent rester identiques
    quel que soit le niveau de prix -- confirme qu'aucune conversion
    supplémentaire n'est nécessaire pour elles (voir commentaire d'audit
    dans src/trading_env.py::ATR_STOP_MULTIPLIERS_BY_STYLE et
    src/features.py)."""
    cheap = add_technical_features(_scaled_ohlcv(1.0, seed=11))
    expensive = add_technical_features(_scaled_ohlcv(2000.0, seed=11))
    n = min(len(cheap), len(expensive))
    assert np.allclose(cheap[col].to_numpy()[:n], expensive[col].to_numpy()[:n], rtol=1e-4, atol=1e-6), \
        f"{col} devrait déjà être invariant au niveau de prix"


def test_volatility_10_is_return_based_already_scale_relative():
    """volatility_10 = std des RENDEMENTS (pas du prix brut) -- déjà une
    mesure relative, invariante au niveau de prix par construction (pas de
    conversion supplémentaire nécessaire, contrairement à atr_14)."""
    cheap = add_technical_features(_scaled_ohlcv(1.0, seed=11))
    expensive = add_technical_features(_scaled_ohlcv(2000.0, seed=11))
    n = min(len(cheap), len(expensive))
    assert np.allclose(cheap["volatility_10"].to_numpy()[:n], expensive["volatility_10"].to_numpy()[:n],
                         rtol=1e-4, atol=1e-8)


def test_context_indicators_already_scale_invariant():
    """src/multi_timeframe.py::_compute_context_indicators n'a AUCUNE feature
    en unités de prix brutes (pas d'équivalent atr_14 dans le contexte MTF) --
    confirmé directement, rien à convertir là."""
    from src.multi_timeframe import _compute_context_indicators, CONTEXT_INDICATOR_SUFFIXES
    assert not any("atr" in c.lower() for c in CONTEXT_INDICATOR_SUFFIXES), \
        "aucun indicateur de contexte ne doit porter une valeur en unités de prix brutes"

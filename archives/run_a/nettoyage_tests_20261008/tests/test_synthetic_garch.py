"""
tests/test_synthetic_garch.py
==============================
Couvre `src.data_loader.generate_synthetic_ohlcv_garch` (GARCH(1,1) codé à
la main + innovations Student-t standardisées) sur ses DEUX propriétés
quantitatives revendiquées :
  1. leptokurtose (queues épaisses) : l'excès de kurtosis des rendements
     doit être clairement positif, nettement au-dessus d'un contrôle
     gaussien iid généré avec `rng.normal`.
  2. clustering de volatilité : l'autocorrélation des rendements AU CARRÉ
     au lag 1 doit être significativement positive -- signature classique
     du clustering (une gaussienne iid aurait cette autocorrélation proche
     de 0).

Vérifie aussi le contrat de colonnes (identique à `generate_synthetic_ohlcv`
et `load_kaggle_ohlcv_csv`) et la cohérence OHLC de base.
"""
import numpy as np
import pandas as pd

from src.data_loader import generate_synthetic_ohlcv_garch, generate_synthetic_ohlcv


def _excess_kurtosis(x: np.ndarray) -> float:
    x = x - x.mean()
    m2 = np.mean(x ** 2)
    m4 = np.mean(x ** 4)
    return m4 / (m2 ** 2) - 3.0  # kurtosis de Fisher (0 = gaussien)


def _autocorr_lag1(x: np.ndarray) -> float:
    x = x - x.mean()
    num = np.sum(x[:-1] * x[1:])
    den = np.sum(x ** 2)
    return num / den if den > 1e-12 else 0.0


def test_column_contract_matches_existing_generator():
    df = generate_synthetic_ohlcv_garch(n_bars=2000, seed=1)
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert len(df) == 2000
    assert df["close"].gt(0).all()
    # Cohérence OHLC : high >= max(open, close), low <= min(open, close)
    assert (df["high"] >= df[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1) + 1e-9).all()
    assert pd.api.types.is_datetime64_any_dtype(df["time"])


def test_leptokurtosis_clearly_above_gaussian_control():
    n = 20000
    df = generate_synthetic_ohlcv_garch(n_bars=n, seed=7)
    returns = df["close"].pct_change().dropna().to_numpy()

    rng = np.random.default_rng(7)
    gaussian_control = rng.normal(0, returns.std(), size=n - 1)

    garch_excess_kurt = _excess_kurtosis(returns)
    gaussian_excess_kurt = _excess_kurtosis(gaussian_control)

    assert garch_excess_kurt > 1.0, (
        f"excès de kurtosis GARCH trop faible : {garch_excess_kurt:.3f} (attendu > 1.0)"
    )
    assert garch_excess_kurt > gaussian_excess_kurt, (
        f"excès de kurtosis GARCH ({garch_excess_kurt:.3f}) devrait dépasser nettement "
        f"le contrôle gaussien ({gaussian_excess_kurt:.3f})"
    )


def test_volatility_clustering_significant_positive_autocorr_of_squared_returns():
    n = 20000
    df = generate_synthetic_ohlcv_garch(n_bars=n, seed=3, alpha=0.08, beta=0.90)
    returns = df["close"].pct_change().dropna().to_numpy()
    squared = returns ** 2

    ac1 = _autocorr_lag1(squared)
    assert ac1 > 0.05, f"autocorrélation lag-1 des rendements au carré trop faible : {ac1:.4f} (attendu > 0.05)"

    # Contrôle : une série gaussienne iid n'a quasiment aucun clustering.
    rng = np.random.default_rng(3)
    gaussian_control = rng.normal(0, returns.std(), size=n - 1)
    ac1_gaussian = _autocorr_lag1(gaussian_control ** 2)
    assert ac1 > ac1_gaussian


def test_stationarity_parameters_validated_and_tunable():
    """alpha+beta<1 (stationnarité) reste le défaut, mais les paramètres
    sont bien overridables -- vérifie juste que la fonction tourne avec des
    valeurs custom raisonnables sans exploser (variance ne diverge pas)."""
    df = generate_synthetic_ohlcv_garch(n_bars=3000, seed=2, omega=2e-8, alpha=0.05, beta=0.85, dof=6.0)
    returns = df["close"].pct_change().dropna()
    assert np.isfinite(returns).all()
    assert returns.abs().max() < 1.0  # pas d'explosion numérique délirante


def test_dof_must_exceed_two():
    import pytest
    with pytest.raises(ValueError):
        generate_synthetic_ohlcv_garch(n_bars=100, dof=2.0)


def test_does_not_modify_or_break_existing_generator():
    """Garde-fou : generate_synthetic_ohlcv (existant) doit rester intact et
    fonctionner exactement comme avant, cette fonctionnalité étant ajoutée
    SANS toucher à l'existant."""
    df = generate_synthetic_ohlcv(n_bars=500, seed=42)
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert len(df) == 500

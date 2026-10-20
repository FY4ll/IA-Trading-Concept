"""
tests/test_macro_shocks.py
============================
Couvre `src.stress_test.inject_macro_shocks` :
  - sans `event_timestamps` (proxy statistique) : une fraction FAIBLE mais
    non nulle des bougies est flaguée (multiplicateur > 1.0) -- proxy
    d'événements RARES, pas un déclenchement massif.
  - avec `event_timestamps` explicites : flague exactement les bougies les
    plus proches de ces timestamps.
  - contrat de colonnes : `cost_multiplier` >= 1.0 partout, à 1.0 par
    défaut ; `slippage_price_offset` >= 0.0 partout, à 0.0 par défaut ;
    copie du DataFrame d'entrée (jamais de mutation en place).
"""
import numpy as np
import pandas as pd

from src.stress_test import inject_macro_shocks


def _make_df_with_two_extreme_spikes(n=300, spike_idx=(50, 200)):
    """Bruit de rendement normal (petit), sauf à `spike_idx` où le
    rendement ET le volume sont des outliers marqués -- construction
    déterministe pour tester le proxy statistique sans dépendre du hasard
    d'un générateur synthétique complet."""
    rng = np.random.default_rng(0)
    returns = rng.normal(0, 0.0004, n)
    for i in spike_idx:
        returns[i] = 0.05  # +5% sur une seule bougie -- outlier extrême
    close = 100.0 * np.cumprod(1 + returns)
    open_ = np.roll(close, 1)
    open_[0] = close[0]

    volume = rng.integers(100, 1000, n).astype(float)
    for i in spike_idx:
        volume[i] = 50000.0  # pic de volume marqué

    return pd.DataFrame({
        "time": pd.date_range("2023-01-01", periods=n, freq="h"),
        "open": open_,
        "high": np.maximum(open_, close) * 1.001,
        "low": np.minimum(open_, close) * 0.999,
        "close": close,
        "volume": volume,
    })


def test_returns_copy_never_mutates_input():
    df = _make_df_with_two_extreme_spikes()
    original = df.copy(deep=True)
    result = inject_macro_shocks(df, seed=1)
    pd.testing.assert_frame_equal(df, original)
    assert result is not df


def test_column_contract_defaults():
    df = _make_df_with_two_extreme_spikes()
    result = inject_macro_shocks(df, seed=1)
    assert "cost_multiplier" in result.columns
    assert "slippage_price_offset" in result.columns
    assert (result["cost_multiplier"] >= 1.0).all()
    assert (result["slippage_price_offset"] >= 0.0).all()
    # Valeurs par défaut respectées là où rien n'est flagué.
    unflagged = result[result["cost_multiplier"] == 1.0]
    assert (unflagged["slippage_price_offset"] == 0.0).all()


def test_proxy_flags_some_but_not_most_candles():
    df = _make_df_with_two_extreme_spikes(n=300, spike_idx=(50, 200))
    result = inject_macro_shocks(df, seed=1)
    flagged_frac = (result["cost_multiplier"] > 1.0).mean()
    assert flagged_frac > 0.0, "au moins une bougie devrait être flaguée par le proxy"
    assert flagged_frac < 0.10, f"le proxy devrait flaguer une fraction FAIBLE de bougies, obtenu {flagged_frac:.2%}"

    # Les deux pics injectés (retour extrême + volume extrême simultanés)
    # doivent faire partie des bougies flaguées.
    flagged_idx = set(result.index[result["cost_multiplier"] > 1.0])
    assert 50 in flagged_idx
    assert 200 in flagged_idx


def test_proxy_multiplier_and_slippage_within_configured_ranges():
    df = _make_df_with_two_extreme_spikes()
    spread_range = (3.0, 5.0)
    slippage_range = (0.02, 0.05)
    result = inject_macro_shocks(df, spread_multiplier_range=spread_range,
                                  slippage_price_range=slippage_range, seed=1)
    flagged = result[result["cost_multiplier"] > 1.0]
    assert (flagged["cost_multiplier"] >= spread_range[0]).all()
    assert (flagged["cost_multiplier"] <= spread_range[1]).all()
    assert (flagged["slippage_price_offset"] >= slippage_range[0]).all()
    assert (flagged["slippage_price_offset"] <= slippage_range[1]).all()


def test_no_volume_column_falls_back_to_return_only():
    df = _make_df_with_two_extreme_spikes().drop(columns=["volume"])
    result = inject_macro_shocks(df, seed=1)
    flagged_idx = set(result.index[result["cost_multiplier"] > 1.0])
    # Sans volume, le critère retombe sur le rendement seul -- les deux
    # pics extrêmes doivent toujours être détectés.
    assert 50 in flagged_idx
    assert 200 in flagged_idx


def test_trivial_all_zero_volume_treated_as_absent():
    df = _make_df_with_two_extreme_spikes()
    df["volume"] = 0.0
    result = inject_macro_shocks(df, seed=1)
    flagged_idx = set(result.index[result["cost_multiplier"] > 1.0])
    assert 50 in flagged_idx
    assert 200 in flagged_idx


def test_explicit_event_timestamps_flag_nearest_candles():
    n = 200
    df = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": np.linspace(1900, 1950, n),
        "high": np.linspace(1900, 1950, n) + 1,
        "low": np.linspace(1900, 1950, n) - 1,
        "close": np.linspace(1900, 1950, n),
        "volume": np.full(n, 500.0),
    })
    event_ts = [
        df["time"].iloc[30] + pd.Timedelta(minutes=20),   # devrait tomber sur la bougie 30
        df["time"].iloc[120],                              # exactement la bougie 120
    ]
    result = inject_macro_shocks(df, event_timestamps=event_ts, seed=2)
    flagged_idx = set(result.index[result["cost_multiplier"] > 1.0])

    assert flagged_idx == {30, 120}
    # Rien d'autre ne doit être flagué : source = calendrier explicite, pas le proxy.
    assert (result.loc[~result.index.isin(flagged_idx), "cost_multiplier"] == 1.0).all()


def test_missing_time_column_raises_with_explicit_events():
    df = _make_df_with_two_extreme_spikes().drop(columns=["time"])
    import pytest
    with pytest.raises(ValueError):
        inject_macro_shocks(df, event_timestamps=[pd.Timestamp("2023-01-01")])

"""
tests/test_leakage_shuffle.py
===============================
Test UNITAIRE RAPIDE (aucun entraînement de modèle -- doit rester bien en
dessous de la seconde) pour `src.stress_test.shuffle_target_relative_to_features`,
la sonde de détection de fuite de données par "target shuffling" (voir sa
docstring pour le raisonnement complet). Vérifie :
  - longueur et colonnes préservées.
  - l'alignement change réellement (les colonnes prix décalées diffèrent de
    l'original à un t donné, pour l'offset effectivement tiré).
  - aucun NaN introduit.
  - déterminisme avec seed, et non-déterminisme sans seed fixe (offsets
    différents selon l'appel -- pas strictement testé mais l'offset != 0
    est vérifié).

Le script diagnostique complet (entraînement + walk-forward sur données
mélangées vs réelles) vit séparément dans scripts/leakage_shuffle_test.py --
volontairement PAS dans la suite pytest rapide (entraînement RL = minutes,
pas millisecondes).
"""
import numpy as np
import pandas as pd

from src.stress_test import shuffle_target_relative_to_features, _PRICE_COLS


def _make_df(n=500, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.1, n)
    return pd.DataFrame({
        "time": pd.date_range("2022-01-01", periods=n, freq="h"),
        "open": open_,
        "high": np.maximum(open_, close) + 0.2,
        "low": np.minimum(open_, close) - 0.2,
        "close": close,
        "volume": rng.integers(100, 5000, n),
        "rsi_14": rng.normal(50, 10, n),  # colonne "feature" arbitraire
    })


def test_preserves_length_and_columns():
    df = _make_df()
    result = shuffle_target_relative_to_features(df, seed=1)
    assert len(result) == len(df)
    assert list(result.columns) == list(df.columns)


def test_alignment_actually_changes():
    df = _make_df()
    result = shuffle_target_relative_to_features(df, seed=1)
    # Les colonnes PRIX doivent différer de l'original à (au moins la
    # plupart) des positions t -- l'alignement a bien été cassé.
    for col in _PRICE_COLS:
        assert not np.allclose(result[col].to_numpy(), df[col].to_numpy())


def test_non_price_columns_untouched():
    df = _make_df()
    result = shuffle_target_relative_to_features(df, seed=1)
    pd.testing.assert_series_equal(result["volume"], df["volume"])
    pd.testing.assert_series_equal(result["rsi_14"], df["rsi_14"])
    pd.testing.assert_series_equal(result["time"], df["time"])


def test_no_nans_introduced():
    df = _make_df()
    result = shuffle_target_relative_to_features(df, seed=1)
    assert not result.isna().any().any()


def test_circular_shift_preserves_column_values_as_a_set():
    """Un décalage CIRCULAIRE ne perd ni n'ajoute aucune valeur -- seule la
    POSITION change (contrairement à un shift avec NaN en bord, ou à un
    shuffle qui casserait l'autocorrélation propre de la colonne)."""
    df = _make_df()
    result = shuffle_target_relative_to_features(df, seed=1)
    for col in _PRICE_COLS:
        np.testing.assert_array_almost_equal(
            np.sort(result[col].to_numpy()), np.sort(df[col].to_numpy())
        )


def test_deterministic_with_seed():
    df = _make_df()
    a = shuffle_target_relative_to_features(df, seed=99)
    b = shuffle_target_relative_to_features(df, seed=99)
    pd.testing.assert_frame_equal(a, b)


def test_offset_never_zero_even_across_many_seeds():
    df = _make_df(n=50)
    for seed in range(30):
        result = shuffle_target_relative_to_features(df, seed=seed)
        assert not result["close"].equals(df["close"])


def test_single_row_or_empty_returns_copy_without_error():
    df = _make_df(n=1)
    result = shuffle_target_relative_to_features(df, seed=1)
    assert len(result) == 1
    df_empty = df.iloc[0:0]
    result_empty = shuffle_target_relative_to_features(df_empty, seed=1)
    assert len(result_empty) == 0


def test_does_not_mutate_input():
    df = _make_df()
    original = df.copy(deep=True)
    shuffle_target_relative_to_features(df, seed=1)
    pd.testing.assert_frame_equal(df, original)

"""
tests/test_purge_embargo.py
============================
Couvre l'ajout de purge/embargo à `src.data_loader.chronological_split`
(standard institutionnel Marcos López de Prado, "Advances in Financial
Machine Learning") :
  - comportement par défaut (purge_bars=0, embargo_bars=0) strictement
    inchangé par rapport à l'ancien découpage -- rétrocompatibilité totale.
  - avec purge/embargo actifs, un VRAI trou (en nombre de lignes) apparaît
    entre la fin d'un split et le début du suivant.
  - le nombre total de lignes diminue exactement du nombre de lignes
    purgées/embargoées.
  - aucun chevauchement ni duplication de lignes entre splits.

Utilise une colonne "marker" = np.arange(n) plutôt que l'index (remis à
zéro par `reset_index(drop=True)` dans chaque split) pour pouvoir comparer
la position D'ORIGINE des lignes conservées dans chaque split.
"""
import numpy as np
import pandas as pd

from src.data_loader import chronological_split


def _make_df(n=1000):
    return pd.DataFrame({
        "time": pd.date_range("2020-01-01", periods=n, freq="h"),
        "marker": np.arange(n),
        "open": np.linspace(100, 200, n),
        "high": np.linspace(100, 200, n) * 1.001,
        "low": np.linspace(100, 200, n) * 0.999,
        "close": np.linspace(100, 200, n),
        "volume": np.ones(n),
    })


def test_default_behavior_unchanged():
    """purge_bars=0, embargo_bars=0 (défaut) doit produire EXACTEMENT le
    même résultat que l'appel à 2 arguments d'origine."""
    df = _make_df(1000)
    train_a, val_a, test_a = chronological_split(df, 0.7, 0.2)
    train_b, val_b, test_b = chronological_split(df, 0.7, 0.2, purge_bars=0, embargo_bars=0)

    pd.testing.assert_frame_equal(train_a, train_b)
    pd.testing.assert_frame_equal(val_a, val_b)
    pd.testing.assert_frame_equal(test_a, test_b)

    # Comportement historique explicite : découpage contigu, sans trou.
    # Bornes recalculées avec la MÊME formule que la fonction (pas des
    # constantes codées en dur) : 0.7 + 0.2 n'est pas exactement 0.9 en
    # float64, un détail d'arithmétique déjà présent dans l'implémentation
    # d'origine, pas introduit par purge/embargo -- ce test vérifie la
    # NON-RÉGRESSION de ce comportement existant, pas une valeur idéalisée.
    n = 1000
    expected_train_end = int(n * 0.7)
    expected_val_end = int(n * (0.7 + 0.2))
    assert len(train_a) == expected_train_end
    assert len(val_a) == expected_val_end - expected_train_end
    assert len(test_a) == n - expected_val_end
    assert train_a["marker"].iloc[-1] == expected_train_end - 1
    assert val_a["marker"].iloc[0] == expected_train_end
    assert val_a["marker"].iloc[-1] == expected_val_end - 1
    assert test_a["marker"].iloc[0] == expected_val_end


def test_purge_and_embargo_create_a_genuine_gap():
    """Avec purge_bars/embargo_bars > 0, l'écart entre le dernier marker de
    train et le premier marker de val (et pareil pour val/test) doit être
    strictement supérieur à 1 (l'écart "sans trou" du comportement par
    défaut) -- et correspondre exactement à purge_bars + embargo_bars."""
    df = _make_df(1000)
    purge, embargo = 10, 5
    train, val, test = chronological_split(df, 0.7, 0.2, purge_bars=purge, embargo_bars=embargo)

    gap_train_val = val["marker"].iloc[0] - train["marker"].iloc[-1]
    gap_val_test = test["marker"].iloc[0] - val["marker"].iloc[-1]

    # +1 car un écart de 1 (bougies consécutives) correspond à AUCUN trou.
    assert gap_train_val == purge + embargo + 1
    assert gap_val_test == purge + embargo + 1
    assert gap_train_val > 1
    assert gap_val_test > 1


def test_total_row_count_decreases_by_expected_amount():
    df = _make_df(1000)
    purge, embargo = 15, 8
    train0, val0, test0 = chronological_split(df, 0.7, 0.2)
    train1, val1, test1 = chronological_split(df, 0.7, 0.2, purge_bars=purge, embargo_bars=embargo)

    total0 = len(train0) + len(val0) + len(test0)
    total1 = len(train1) + len(val1) + len(test1)

    # 2 frontières (train/val et val/test), chacune retire purge (avant) +
    # embargo (après) = purge_bars + embargo_bars bougies.
    expected_removed = 2 * (purge + embargo)
    assert total0 - total1 == expected_removed


def test_no_overlap_or_duplication_across_splits():
    df = _make_df(1000)
    train, val, test = chronological_split(df, 0.7, 0.2, purge_bars=12, embargo_bars=6)

    markers_train = set(train["marker"])
    markers_val = set(val["marker"])
    markers_test = set(test["marker"])

    assert markers_train.isdisjoint(markers_val)
    assert markers_val.isdisjoint(markers_test)
    assert markers_train.isdisjoint(markers_test)

    # Chaque marker conservé n'apparaît qu'une seule fois au total.
    all_markers = list(train["marker"]) + list(val["marker"]) + list(test["marker"])
    assert len(all_markers) == len(set(all_markers))

    # Chaque split reste trié chronologiquement (ordre préservé, pas mélangé).
    assert list(train["marker"]) == sorted(train["marker"])
    assert list(val["marker"]) == sorted(val["marker"])
    assert list(test["marker"]) == sorted(test["marker"])


def test_reset_index_and_three_dataframes_returned():
    df = _make_df(500)
    result = chronological_split(df, 0.6, 0.2, purge_bars=5, embargo_bars=3)
    assert len(result) == 3
    for split in result:
        assert isinstance(split, pd.DataFrame)
        assert list(split.index) == list(range(len(split)))


def test_never_raises_when_purge_embargo_empties_a_split():
    """Un réglage agressif de purge/embargo qui dépasse la taille d'un split
    ne doit JAMAIS lever d'exception -- le split concerné devient simplement
    vide (0 ligne), comportement documenté explicitement dans la docstring."""
    df = _make_df(100)
    train, val, test = chronological_split(df, 0.7, 0.2, purge_bars=1000, embargo_bars=1000)
    assert len(train) == 0
    assert len(val) == 0
    assert len(test) == 0
    # Toujours des DataFrames avec les bonnes colonnes, jamais None/exception.
    assert list(train.columns) == list(df.columns)


def test_embargo_only_no_purge():
    """embargo_bars seul (purge_bars=0) doit quand même créer un trou (côté
    tête de val/test uniquement)."""
    df = _make_df(1000)
    train, val, test = chronological_split(df, 0.7, 0.2, purge_bars=0, embargo_bars=7)
    assert val["marker"].iloc[0] - train["marker"].iloc[-1] == 7 + 1
    assert test["marker"].iloc[0] - val["marker"].iloc[-1] == 7 + 1


def test_purge_only_no_embargo():
    """purge_bars seul (embargo_bars=0) doit quand même créer un trou (côté
    queue de train/val uniquement)."""
    df = _make_df(1000)
    train, val, test = chronological_split(df, 0.7, 0.2, purge_bars=9, embargo_bars=0)
    assert val["marker"].iloc[0] - train["marker"].iloc[-1] == 9 + 1
    assert test["marker"].iloc[0] - val["marker"].iloc[-1] == 9 + 1

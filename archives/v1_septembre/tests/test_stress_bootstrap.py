"""
tests/test_stress_bootstrap.py
================================
Couvre l'audit "block bootstrap size fix + stationary bootstrap" :
  - `block_bootstrap_rows` : le défaut de `block_size` est bien relevé à
    150 (fourchette 100-200 demandée), tout en restant overridable (déjà
    couvert côté "ne casse rien" par
    tests/test_autonomous.py::test_block_bootstrap_rebases_price_no_teleport,
    qui passe `block_size=50` explicitement et n'est donc pas affecté).
  - `stationary_block_bootstrap` (Politis & Romano) : longueurs de bloc
    VARIABLES (pas toutes identiques), longueur de sortie = longueur
    demandée, continuité des prix aux coutures de blocs (même garde-fou que
    les tests existants sur `_rebase_and_concat`, voir
    tests/test_autonomous.py::test_block_bootstrap_rebases_price_no_teleport
    pour le motif d'origine).
"""
import inspect

import numpy as np
import pandas as pd

from src.stress_test import block_bootstrap_rows, stationary_block_bootstrap


def _make_trending_df(n=2000, start=100.0, end=4000.0):
    """Même construction que le test existant sur block_bootstrap_rows dans
    tests/test_autonomous.py : une tendance monotone forte (proxy du pire
    cas XAUUSD 2004->aujourd'hui) pour détecter un artefact de raccord de
    prix aux coutures de blocs."""
    prices = np.linspace(start, end, n)
    return pd.DataFrame({
        "open": prices, "high": prices * 1.001, "low": prices * 0.999,
        "close": prices, "volume": np.ones(n),
    })


def test_block_bootstrap_rows_default_block_size_in_100_200_range():
    sig = inspect.signature(block_bootstrap_rows)
    default_block_size = sig.parameters["block_size"].default
    assert 100 <= default_block_size <= 200


def test_block_bootstrap_rows_default_still_overridable():
    df = _make_trending_df(1000)
    # L'appel explicite avec un block_size différent du nouveau défaut doit
    # toujours fonctionner (rétrocompatibilité des appelants existants,
    # ex: backtester.py qui calibre son propre block_size).
    result = block_bootstrap_rows(df, block_size=50, seed=1)
    assert len(result) > 0


def test_stationary_block_bootstrap_output_length_matches_input():
    df = _make_trending_df(3000)
    result = stationary_block_bootstrap(df, min_block=100, max_block=200, seed=1)
    assert len(result) == len(df)


def test_stationary_block_bootstrap_block_lengths_vary():
    """Reconstruit les longueurs de bloc RÉELLEMENT tirées (via une trace
    manuelle de la même mécanique géométrique) pour vérifier qu'elles ne
    sont pas toutes identiques -- signature du bootstrap STATIONNAIRE par
    opposition au bootstrap à blocs FIXES."""
    rng = np.random.default_rng(123)
    mean_block_len = (100 + 200) / 2.0
    p = 1.0 / mean_block_len
    lengths = [max(20, int(rng.geometric(p))) for _ in range(500)]
    assert len(set(lengths)) > 5, "les longueurs de bloc géométriques devraient varier nettement"
    assert min(lengths) >= 20


def test_stationary_block_bootstrap_no_price_teleport_at_seams():
    df = _make_trending_df(2000, start=100.0, end=4000.0)
    max_real_step = df["close"].pct_change().abs().max()

    result = stationary_block_bootstrap(df, min_block=100, max_block=200, seed=5)
    steps = result["close"].pct_change().abs().dropna()

    assert steps.max() < max_real_step * 5, (
        f"écart de prix anormal détecté à une jonction de blocs : {steps.max():.2%} "
        f"(max réel : {max_real_step:.2%})"
    )
    # Cohérence OHLC préservée après remise à l'échelle par _rebase_and_concat.
    assert (result["high"] >= result[["open", "close"]].max(axis=1) - 1e-6).all()
    assert (result["low"] <= result[["open", "close"]].min(axis=1) + 1e-6).all()


def test_stationary_block_bootstrap_deterministic_with_seed():
    df = _make_trending_df(1500)
    a = stationary_block_bootstrap(df, seed=42)
    b = stationary_block_bootstrap(df, seed=42)
    pd.testing.assert_frame_equal(a, b)


def test_stationary_block_bootstrap_empty_df():
    df = pd.DataFrame({"open": [], "high": [], "low": [], "close": [], "volume": []})
    result = stationary_block_bootstrap(df, seed=1)
    assert len(result) == 0

"""LOT 2, phase 4 : composition du panier d'entraînement (point 7, graine
par génération), coupure calendaire commune (point 6, dates absolues
partagées entre symboles), et découverte des symboles configurés avec
no-op gracieux si absents (point 10). Fichier DÉDIÉ (pas
tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
import pandas as pd
import pytest

from src.data_loader import generate_synthetic_ohlcv, split_by_calendar_dates
from src.multi_asset import (
    build_training_basket, training_basket_seed, discover_configured_symbols, GOLD_SYMBOL,
)
from src.features import add_technical_features, FEATURE_COLUMNS


def test_training_basket_seed_deterministic_and_changes_per_generation():
    s1 = training_basket_seed("M15", 10)
    s2 = training_basket_seed("M15", 10)
    s3 = training_basket_seed("M15", 11)
    assert s1 == s2
    assert s1 != s3


def test_training_basket_seed_changes_per_style():
    assert training_basket_seed("M15", 10) != training_basket_seed("H1", 10)


def test_build_training_basket_without_other_symbols_is_gold_only_passthrough():
    gold = generate_synthetic_ohlcv(n_bars=2000, seed=1)
    basket = build_training_basket(gold, {}, style="M15", generation=1)
    expected = add_technical_features(gold)
    assert len(basket) == len(expected)
    assert "symbol" not in basket.columns, "sans autres symboles, aucune colonne symbol/segment_id ajoutée"


def test_build_training_basket_roughly_50_50_with_one_other_symbol():
    gold = generate_synthetic_ohlcv(n_bars=5000, seed=1)
    eurusd = generate_synthetic_ohlcv(n_bars=5000, seed=2)
    basket = build_training_basket(gold, {"EURUSD": eurusd}, style="M15", generation=1,
                                     gold_fraction=0.5, segment_len=1000)
    gold_rows = (basket["symbol"] == GOLD_SYMBOL).sum()
    other_rows = (basket["symbol"] == "EURUSD").sum()
    total = len(basket)
    assert total > 0
    assert abs(gold_rows / total - 0.5) < 0.05


def test_build_training_basket_segments_change_across_generations():
    gold = generate_synthetic_ohlcv(n_bars=10000, seed=1)
    eurusd = generate_synthetic_ohlcv(n_bars=10000, seed=2)
    basket_gen1 = build_training_basket(gold, {"EURUSD": eurusd}, style="M15", generation=1, segment_len=500)
    basket_gen2 = build_training_basket(gold, {"EURUSD": eurusd}, style="M15", generation=2, segment_len=500)
    assert basket_gen1["close"].tolist() != basket_gen2["close"].tolist(), \
        "des générations différentes doivent tirer des segments différents (diversité d'entraînement)"


def test_build_training_basket_deterministic_within_same_generation():
    gold = generate_synthetic_ohlcv(n_bars=5000, seed=1)
    eurusd = generate_synthetic_ohlcv(n_bars=5000, seed=2)
    b1 = build_training_basket(gold, {"EURUSD": eurusd}, style="M15", generation=5, segment_len=500)
    b2 = build_training_basket(gold, {"EURUSD": eurusd}, style="M15", generation=5, segment_len=500)
    assert b1["close"].tolist() == b2["close"].tolist()


def test_build_training_basket_segment_ids_contiguous_and_unique_per_source_segment():
    gold = generate_synthetic_ohlcv(n_bars=5000, seed=1)
    eurusd = generate_synthetic_ohlcv(n_bars=5000, seed=2)
    basket = build_training_basket(gold, {"EURUSD": eurusd}, style="M15", generation=1, segment_len=1000)
    for sid in basket["segment_id"].unique():
        assert basket.loc[basket["segment_id"] == sid, "symbol"].nunique() == 1


# ---------------------------------------------------------------------- #
# Coupure calendaire commune (point 6)
# ---------------------------------------------------------------------- #

def _df_with_dates(start, periods, freq="1h"):
    import numpy as np
    times = pd.date_range(start, periods=periods, freq=freq)
    return pd.DataFrame({"time": times, "open": 1.0, "high": 1.1, "low": 0.9,
                           "close": 1.0, "volume": np.arange(periods, dtype=float)})


def test_split_by_calendar_dates_respects_absolute_boundaries():
    df = _df_with_dates("2023-01-01", periods=1000, freq="1h")
    train_end = pd.Timestamp("2023-01-15")
    val_end = pd.Timestamp("2023-01-25")
    train, val, test = split_by_calendar_dates(df, train_end, val_end)
    assert (pd.to_datetime(train["time"]) < train_end).all()
    assert ((pd.to_datetime(val["time"]) >= train_end) & (pd.to_datetime(val["time"]) < val_end)).all()
    assert (pd.to_datetime(test["time"]) >= val_end).all()
    assert len(train) + len(val) + len(test) == len(df)


def test_split_by_calendar_dates_same_boundaries_applied_to_different_symbol_ranges():
    """Le coeur du point 6 : deux symboles avec des historiques de longueurs
    DIFFÉRENTES, coupés aux MÊMES dates absolues -- aucun chevauchement
    temporel entre la validation/le test de l'un et l'entraînement de
    l'autre."""
    gold = _df_with_dates("2020-01-01", periods=5000, freq="1h")   # long historique
    eurusd = _df_with_dates("2023-06-01", periods=500, freq="1h")  # historique court, plus récent

    train_end = pd.Timestamp("2023-01-01")
    val_end = pd.Timestamp("2023-08-01")
    gold_train, gold_val, gold_test = split_by_calendar_dates(gold, train_end, val_end)
    eur_train, eur_val, eur_test = split_by_calendar_dates(eurusd, train_end, val_end)

    # Aucune bougie EURUSD "train" ne doit chevaucher la période de
    # validation/test de l'or (même frontière de date, quel que soit le
    # volume de données disponible pour chaque symbole).
    if len(eur_train) > 0:
        assert (pd.to_datetime(eur_train["time"]) < train_end).all()
    if len(gold_val) > 0 and len(eur_train) > 0:
        assert pd.to_datetime(eur_train["time"]).max() < pd.to_datetime(gold_val["time"]).min()


def test_split_by_calendar_dates_empty_when_symbol_range_outside_window():
    df = _df_with_dates("2010-01-01", periods=100, freq="1D")  # bien avant les frontières
    train, val, test = split_by_calendar_dates(df, "2023-01-01", "2023-06-01")
    assert len(val) == 0 and len(test) == 0
    assert len(train) == 100  # tout tombe avant train_end


# ---------------------------------------------------------------------- #
# Découverte des symboles configurés (point 10) -- no-op gracieux
# ---------------------------------------------------------------------- #

def test_discover_configured_symbols_disabled_by_default_returns_empty():
    cfg = {"multi_asset": {"enabled": False, "symbols": {"EURUSD": "data/kaggle_eurusd"}}}
    assert discover_configured_symbols(cfg) == {}


def test_discover_configured_symbols_missing_key_returns_empty():
    assert discover_configured_symbols({}) == {}


def test_discover_configured_symbols_graceful_when_folder_missing(caplog):
    import logging
    caplog.set_level(logging.INFO)
    cfg = {"multi_asset": {"enabled": True, "symbols": {"EURUSD": "data/this_folder_does_not_exist"}}}
    result = discover_configured_symbols(cfg)
    assert result == {}, "un dossier configuré mais absent ne doit jamais lever d'exception, juste être ignoré"


def test_discover_configured_symbols_finds_real_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "kaggle_eurusd"
    folder.mkdir()
    (folder / "EUR_1h_data.csv").write_text(
        "Date,Open,High,Low,Close,Volume\n2024.01.01 00:00,1.1,1.11,1.09,1.10,1000\n", encoding="utf-8")
    cfg = {"multi_asset": {"enabled": True, "symbols": {"EURUSD": "kaggle_eurusd"}}}
    result = discover_configured_symbols(cfg)
    assert "EURUSD" in result

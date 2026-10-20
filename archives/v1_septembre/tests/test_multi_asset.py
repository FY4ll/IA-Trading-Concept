"""Tests pour src/multi_asset.py (audit institutionnel, section 4 --
validation cross-asset). Aucune vraie donnée multi-actifs n'existe encore
dans ce dépôt (voir docstring du module) : les tests utilisent des données
SYNTHÉTIQUES (seeds différentes = substitut à "des symboles différents")."""
from __future__ import annotations
import numpy as np

from src.data_loader import generate_synthetic_ohlcv
from src.multi_asset import build_mixed_basket_dataset, discover_symbol_folder, load_symbol_ohlcv


def test_build_mixed_basket_combines_segments_from_each_symbol():
    symbol_dfs = {
        "XAUUSD": generate_synthetic_ohlcv(n_bars=5000, seed=1),
        "EURUSD": generate_synthetic_ohlcv(n_bars=5000, seed=2),
        "SPX": generate_synthetic_ohlcv(n_bars=5000, seed=3),
    }
    combined, boundaries = build_mixed_basket_dataset(symbol_dfs, segment_len=1000, seed=0)

    assert len(combined) == 3000, "3 segments de 1000 bougies attendus"
    assert boundaries == [0, 1000, 2000]
    assert list(combined.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert not combined[["open", "high", "low", "close"]].isna().any().any(), "aucun NaN attendu"


def test_build_mixed_basket_rebases_price_no_absurd_jump_at_segment_boundary():
    symbol_dfs = {
        "XAUUSD": generate_synthetic_ohlcv(n_bars=3000, seed=10),  # prix ~100
        "EURUSD": generate_synthetic_ohlcv(n_bars=3000, seed=20),  # prix ~100 (même générateur)
    }
    combined, boundaries = build_mixed_basket_dataset(symbol_dfs, segment_len=1000, seed=1)

    # Au raccord (frontière du 2e segment), le OPEN du nouveau segment doit
    # être mis à l'échelle pour repartir du CLOSE du segment précédent --
    # pas de saut de prix artificiel.
    boundary = boundaries[1]
    prev_close = combined.iloc[boundary - 1]["close"]
    new_open = combined.iloc[boundary]["open"]
    assert abs(new_open - prev_close) / prev_close < 0.01, \
        f"saut de prix trop grand au raccord : close={prev_close}, open suivant={new_open}"


def test_build_mixed_basket_handles_symbol_shorter_than_segment_len():
    symbol_dfs = {
        "XAUUSD": generate_synthetic_ohlcv(n_bars=5000, seed=1),
        "TINY": generate_synthetic_ohlcv(n_bars=200, seed=2),  # plus court que segment_len
    }
    combined, boundaries = build_mixed_basket_dataset(symbol_dfs, segment_len=1000, seed=0)
    # XAUUSD contribue 1000, TINY contribue son historique entier (200)
    assert len(combined) == 1200
    assert boundaries == [0, 1000]


def test_build_mixed_basket_empty_input_returns_empty_dataframe():
    combined, boundaries = build_mixed_basket_dataset({}, segment_len=1000)
    assert len(combined) == 0
    assert boundaries == []


def test_build_mixed_basket_skips_empty_dataframe_for_one_symbol():
    import pandas as pd
    symbol_dfs = {
        "XAUUSD": generate_synthetic_ohlcv(n_bars=2000, seed=1),
        "EMPTY": pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"]),
    }
    combined, boundaries = build_mixed_basket_dataset(symbol_dfs, segment_len=1000, seed=0)
    assert len(combined) == 1000  # seul XAUUSD contribue
    assert boundaries == [0]


def test_build_mixed_basket_deterministic_with_seed():
    symbol_dfs = {
        "XAUUSD": generate_synthetic_ohlcv(n_bars=5000, seed=1),
        "EURUSD": generate_synthetic_ohlcv(n_bars=5000, seed=2),
    }
    combined1, _ = build_mixed_basket_dataset(symbol_dfs, segment_len=1000, seed=42)
    combined2, _ = build_mixed_basket_dataset(symbol_dfs, segment_len=1000, seed=42)
    assert combined1["close"].tolist() == combined2["close"].tolist()


def test_discover_symbol_folder_returns_none_for_missing_folder():
    assert discover_symbol_folder("data/this_folder_does_not_exist") is None


def test_discover_symbol_folder_finds_csv(tmp_path):
    folder = tmp_path / "kaggle_eurusd"
    folder.mkdir()
    csv_path = folder / "EUR_1h_data.csv"
    csv_path.write_text("Date,Open,High,Low,Close,Volume\n2024.01.01 00:00,1.1,1.11,1.09,1.10,1000\n",
                         encoding="utf-8")
    found = discover_symbol_folder(str(folder))
    assert found == str(csv_path)


def test_load_symbol_ohlcv_reads_generic_csv(tmp_path):
    csv_path = tmp_path / "test.csv"
    csv_path.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "2024.01.01 00:00,1.10,1.11,1.09,1.105,1000\n"
        "2024.01.01 01:00,1.105,1.115,1.10,1.11,1200\n",
        encoding="utf-8",
    )
    df = load_symbol_ohlcv(str(csv_path))
    assert len(df) == 2
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]

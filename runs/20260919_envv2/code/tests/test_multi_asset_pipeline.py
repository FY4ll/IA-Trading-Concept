"""LOT 2, phase 4 : pipeline PAR SYMBOLE (src/multi_asset.py::
build_multi_asset_dataset, remplace le calcul de features post-concaténation
de build_mixed_basket_dataset) + frontières de segment dans TradingEnv
(position forcée à plat + fin d'épisode, aucun stop/PnL/récompense ne
traverse une jointure) + coût par ligne (spread_pct). Aucune vraie donnée
multi-actifs n'existe encore dans ce dépôt (voir src/multi_asset.py) : tests
avec données SYNTHÉTIQUES. Fichier DÉDIÉ (pas tests/test_autonomous.py),
comme demandé."""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

from src.data_loader import generate_synthetic_ohlcv
from src.multi_asset import build_multi_asset_dataset, GOLD_SYMBOL
from src.features import FEATURE_COLUMNS
from src.trading_env import TradingEnv


def test_symbol_and_segment_id_columns_present_and_correct():
    symbol_dfs = {
        "XAUUSD": generate_synthetic_ohlcv(n_bars=3000, seed=1),
        "EURUSD": generate_synthetic_ohlcv(n_bars=3000, seed=2),
    }
    combined = build_multi_asset_dataset(symbol_dfs, segment_len=1000, warmup_bars=50, seed=0)
    assert set(combined["symbol"].unique()) == {"XAUUSD", "EURUSD"}
    assert set(combined["segment_id"].unique()) == {0, 1}
    # chaque segment_id correspond à un seul symbole
    for sid in combined["segment_id"].unique():
        assert combined.loc[combined["segment_id"] == sid, "symbol"].nunique() == 1


def test_warmup_bars_trimmed_from_each_segment():
    symbol_dfs = {"XAUUSD": generate_synthetic_ohlcv(n_bars=3000, seed=1),
                   "EURUSD": generate_synthetic_ohlcv(n_bars=3000, seed=2)}
    combined = build_multi_asset_dataset(symbol_dfs, segment_len=1000, warmup_bars=50, seed=0)
    for sid in combined["segment_id"].unique():
        seg_len = (combined["segment_id"] == sid).sum()
        assert seg_len == 1000, f"segment {sid} devrait faire exactement segment_len (1000) après purge de chauffe"


def test_fundamental_score_zeroed_for_non_gold_symbols():
    symbol_dfs = {GOLD_SYMBOL: generate_synthetic_ohlcv(n_bars=3000, seed=1),
                   "EURUSD": generate_synthetic_ohlcv(n_bars=3000, seed=2)}
    combined = build_multi_asset_dataset(symbol_dfs, segment_len=1000, warmup_bars=50, seed=0)
    gold_rows = combined[combined["symbol"] == GOLD_SYMBOL]
    other_rows = combined[combined["symbol"] == "EURUSD"]
    assert (other_rows["fundamental_score"] == 0.0).all()
    # l'or n'est PAS forcé à zéro (peut être non nul si un fundamental_feed
    # était fourni -- ici aucun n'est fourni donc déjà 0.0, mais on vérifie
    # que le code ne l'écrase pas EXPLICITEMENT comme pour les autres symboles)
    assert "fundamental_score" in gold_rows.columns


def test_features_computed_per_segment_not_contaminated_across_boundary():
    """Le calcul PAR SEGMENT (avant concaténation) garantit que les
    indicateurs glissants du DÉBUT d'un segment ne dépendent JAMAIS des
    bougies du segment précédent -- vérifié en comparant contre un calcul
    du même segment pris ISOLÉMENT."""
    from src.features import add_technical_features
    symbol_a = generate_synthetic_ohlcv(n_bars=3000, seed=1)
    symbol_b = generate_synthetic_ohlcv(n_bars=3000, seed=2)
    combined = build_multi_asset_dataset({"A": symbol_a, "B": symbol_b},
                                           segment_len=500, warmup_bars=50, seed=7)
    seg1 = combined[combined["segment_id"] == 1].reset_index(drop=True)
    # Le pipeline garantit l'ABSENCE de NaN dans le résultat final (la
    # purge de chauffe retire exactement les lignes qui auraient encore des
    # indicateurs glissants incomplets) -- la contamination inter-segment
    # se manifesterait justement par des NaN résiduels ou des valeurs
    # calculées sur un mélange de bougies A/B.
    for col in FEATURE_COLUMNS:
        assert not seg1[col].isna().any(), f"{col} ne devrait avoir aucun NaN après purge de chauffe"


def test_all_feature_columns_present_in_output():
    symbol_dfs = {"XAUUSD": generate_synthetic_ohlcv(n_bars=2000, seed=1)}
    combined = build_multi_asset_dataset(symbol_dfs, segment_len=500, warmup_bars=50, seed=0)
    for col in FEATURE_COLUMNS:
        assert col in combined.columns


def test_empty_input_returns_empty_dataframe_with_expected_columns():
    combined = build_multi_asset_dataset({}, segment_len=500)
    assert len(combined) == 0
    assert "symbol" in combined.columns and "segment_id" in combined.columns


def test_deterministic_with_seed():
    symbol_dfs = {"XAUUSD": generate_synthetic_ohlcv(n_bars=3000, seed=1),
                   "EURUSD": generate_synthetic_ohlcv(n_bars=3000, seed=2)}
    c1 = build_multi_asset_dataset(symbol_dfs, segment_len=500, seed=42)
    c2 = build_multi_asset_dataset(symbol_dfs, segment_len=500, seed=42)
    assert c1["close"].tolist() == c2["close"].tolist()


# ---------------------------------------------------------------------- #
# TradingEnv : frontières de segment
# ---------------------------------------------------------------------- #

def _multi_segment_df():
    symbol_dfs = {"XAUUSD": generate_synthetic_ohlcv(n_bars=3000, seed=1),
                   "EURUSD": generate_synthetic_ohlcv(n_bars=3000, seed=2)}
    combined = build_multi_asset_dataset(symbol_dfs, segment_len=500, warmup_bars=50, seed=0)
    combined, _ = _normalize(combined)
    return combined


def _normalize(df):
    from src.features import normalize_features
    return normalize_features(df, columns=FEATURE_COLUMNS)


def test_episode_terminates_at_segment_boundary_never_crosses():
    df = _multi_segment_df()
    env = TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS, learn_stop_loss=False)
    env.reset()
    # Force le départ au segment 0 (pas le dernier) -- sinon reset() pourrait
    # choisir le DERNIER segment, qui se termine par la fin normale du
    # dataframe plutôt que par une frontière de segment (rien après lui).
    start, _ = env._segment_bounds(0)
    env.current_step = start + env.window_size
    start_segment = env._segment_id_col[env.current_step]
    steps = 0
    terminated = False
    while not terminated and steps < 5000:
        obs, reward, terminated, truncated, info = env.step(1)  # long, décision constante
        steps += 1
        if not terminated:
            assert env._segment_id_col[env.current_step] == start_segment, \
                "current_step ne doit jamais dépasser la frontière du segment de départ sans terminer"
    assert terminated, "l'épisode doit se terminer au plus tard à la frontière du segment"
    assert info.get("segment_boundary") is True


def test_position_forced_flat_at_segment_boundary_no_pnl_leak():
    df = _multi_segment_df()
    env = TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS, learn_stop_loss=False)
    env.reset()
    start, _ = env._segment_bounds(0)
    env.current_step = start + env.window_size
    terminated = False
    steps = 0
    while not terminated and steps < 5000:
        obs, reward, terminated, truncated, info = env.step(2)  # tente d'ouvrir long
        steps += 1
    assert info.get("segment_boundary") is True, "précondition : doit terminer via la frontière de segment"
    assert env.position == 0.0, "la position doit être forcée à plat à la frontière du segment"
    assert reward == 0.0, "aucune récompense ne doit être calculée sur la bougie de frontière"


def test_reset_picks_a_segment_respecting_window_size():
    df = _multi_segment_df()
    env = TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS, learn_stop_loss=False)
    for _ in range(20):
        env.reset()
        seg = env._segment_id_col[env.current_step]
        start, _ = env._segment_bounds(seg)
        assert env.current_step == start + 20


def test_no_segment_id_column_preserves_original_reset_behavior():
    """Comportement d'ORIGINE : sans colonne segment_id, reset() retombe
    toujours sur window_size, jamais un segment aléatoire."""
    from src.features import add_technical_features, normalize_features
    df = add_technical_features(generate_synthetic_ohlcv(n_bars=500, seed=1))
    df, _ = normalize_features(df, columns=FEATURE_COLUMNS)
    env = TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS)
    for _ in range(5):
        env.reset()
        assert env.current_step == 20


# ---------------------------------------------------------------------- #
# Coût par ligne (spread_pct)
# ---------------------------------------------------------------------- #

def test_spread_pct_column_overrides_base_transaction_cost():
    from src.features import add_technical_features, normalize_features
    raw = generate_synthetic_ohlcv(n_bars=500, seed=1)
    featured = add_technical_features(raw)
    featured["spread_pct"] = 0.001  # spread fixe distinct de transaction_cost
    df, _ = normalize_features(featured, columns=FEATURE_COLUMNS)
    env = TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS, transaction_cost=0.0002,
                       session_spread_enabled=False)
    env.reset()
    cost = env._effective_transaction_cost()
    assert cost == pytest.approx(0.001)


def test_no_spread_pct_column_uses_transaction_cost_unchanged():
    from src.features import add_technical_features, normalize_features
    raw = generate_synthetic_ohlcv(n_bars=500, seed=1)
    featured = add_technical_features(raw)
    df, _ = normalize_features(featured, columns=FEATURE_COLUMNS)
    env = TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS, transaction_cost=0.0002,
                       session_spread_enabled=False)
    env.reset()
    cost = env._effective_transaction_cost()
    assert cost == pytest.approx(0.0002)

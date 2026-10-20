"""Tests pour le scénario de stress GARCH (audit institutionnel, section 1,
"Modélisation non linéaire de la Volatilité") -- voir src/stress_test.py::
garch_stress_dataset et son câblage dans
src/backtester.py::evaluate_agent_walkforward. Fichier DÉDIÉ (pas
tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.features import FEATURE_COLUMNS, normalize_features
from src.stress_test import garch_stress_dataset, GARCH_STRESS_SUPPORTED_PRIMARY_TFS
from src.backtester import evaluate_agent_walkforward, evaluate_agent


def _fake_stats(columns):
    """Stats de normalisation factices (moyenne 0, écart-type 1) -- suffit
    pour ces tests, qui ne vérifient pas la valeur numérique exacte après
    normalisation, seulement la présence/le contrat des colonnes."""
    return {c: (0.0, 1.0) for c in columns}


class _RandomAgent:
    """Agent factice : action aléatoire valide sur l'espace d'action de
    l'environnement fourni -- suffisant pour exercer le pipeline
    d'évaluation sans dépendre d'un vrai entraînement RL (lent)."""
    def __init__(self, action_space):
        self.action_space = action_space

    def predict(self, obs, deterministic=True):
        return self.action_space.sample()


def test_unsupported_primary_tf_returns_none_m15():
    """M15 : la série de base GARCH est à fréquence horaire fixe -- ne peut
    jamais représenter honnêtement un style plus fin que H1."""
    result = garch_stress_dataset(
        primary_tf="M15", context_tfs=["H1", "H4"], feature_columns=FEATURE_COLUMNS,
        stats=_fake_stats(FEATURE_COLUMNS), n_primary_bars=100, seed=1,
    )
    assert result is None


def test_unsupported_primary_tf_returns_none_m30():
    result = garch_stress_dataset(
        primary_tf="M30", context_tfs=["H1"], feature_columns=FEATURE_COLUMNS,
        stats=_fake_stats(FEATURE_COLUMNS), n_primary_bars=100, seed=1,
    )
    assert result is None


def test_unsupported_context_tf_returns_none():
    """H1 primaire (supporté) mais un contexte M30 (non supporté) demandé --
    doit refuser plutôt que de fusionner partiellement en silence."""
    result = garch_stress_dataset(
        primary_tf="H1", context_tfs=["M30", "H4"], feature_columns=FEATURE_COLUMNS,
        stats=_fake_stats(FEATURE_COLUMNS), n_primary_bars=100, seed=1,
    )
    assert result is None


def test_supported_primary_tfs_documented_set():
    assert GARCH_STRESS_SUPPORTED_PRIMARY_TFS == {"H1", "H4", "D1", "W1", "MN1"}


def test_h1_primary_no_context_produces_valid_dataset():
    result = garch_stress_dataset(
        primary_tf="H1", context_tfs=[], feature_columns=FEATURE_COLUMNS,
        stats=_fake_stats(FEATURE_COLUMNS), n_primary_bars=200, seed=42,
    )
    assert result is not None
    assert len(result) >= 200
    for col in FEATURE_COLUMNS:
        assert col in result.columns, f"colonne '{col}' manquante -- contrat de colonnes rompu"
    assert not result[FEATURE_COLUMNS].isna().any().any(), "aucun NaN attendu après add_technical_features+dropna"


def test_h4_primary_with_d1_context_produces_valid_dataset():
    feature_columns = FEATURE_COLUMNS + [
        "D1_trend_signal", "D1_rsi_14", "D1_macd_diff", "D1_bb_pct", "D1_volatility_10",
    ]
    result = garch_stress_dataset(
        primary_tf="H4", context_tfs=["D1", "W1", "MN1"], feature_columns=feature_columns,
        stats=_fake_stats(feature_columns), n_primary_bars=100, seed=7,
    )
    assert result is not None
    for col in feature_columns:
        assert col in result.columns


def test_d1_primary_with_w1_mn1_context_produces_valid_dataset():
    feature_columns = FEATURE_COLUMNS + [
        "W1_trend_signal", "W1_rsi_14", "W1_macd_diff", "W1_bb_pct", "W1_volatility_10",
        "MN1_trend_signal", "MN1_rsi_14", "MN1_macd_diff", "MN1_bb_pct", "MN1_volatility_10",
    ]
    result = garch_stress_dataset(
        primary_tf="D1", context_tfs=["W1", "MN1"], feature_columns=feature_columns,
        stats=_fake_stats(feature_columns), n_primary_bars=60, seed=3,
    )
    assert result is not None
    for col in feature_columns:
        assert col in result.columns


def test_normalization_uses_provided_stats_not_refit():
    """Vérifie que la normalisation utilise bien les stats FOURNIES (jamais
    réajustées sur la série synthétique elle-même) -- des stats artificielles
    (moyenne 999) doivent se retrouver dans le résultat."""
    fake_stats = {c: (999.0, 1.0) for c in FEATURE_COLUMNS}
    result = garch_stress_dataset(
        primary_tf="H1", context_tfs=[], feature_columns=FEATURE_COLUMNS,
        stats=fake_stats, n_primary_bars=150, seed=1,
    )
    assert result is not None
    # z-score avec une moyenne de référence de 999 sur des données dont la vraie moyenne est proche
    # de 0 -> valeurs très négatives, PLAFONNÉES à -Z_SCORE_CLIP depuis le 21/09 (normalize_features).
    # Une normalisation réajustée sur la série elle-même donnerait au contraire une moyenne ~0.
    from src.features import Z_SCORE_CLIP
    assert (result["return_1"] == -Z_SCORE_CLIP).all()


def test_deterministic_with_seed():
    r1 = garch_stress_dataset(primary_tf="H1", context_tfs=[], feature_columns=FEATURE_COLUMNS,
                                stats=_fake_stats(FEATURE_COLUMNS), n_primary_bars=100, seed=123)
    r2 = garch_stress_dataset(primary_tf="H1", context_tfs=[], feature_columns=FEATURE_COLUMNS,
                                stats=_fake_stats(FEATURE_COLUMNS), n_primary_bars=100, seed=123)
    pd.testing.assert_series_equal(r1["close"].reset_index(drop=True), r2["close"].reset_index(drop=True))


def test_garch_params_overrides_are_applied():
    """dof/alpha/beta doivent bien être transmis à generate_synthetic_ohlcv_garch
    (spy) -- pas silencieusement ignorés."""
    with patch("src.data_loader.generate_synthetic_ohlcv_garch", wraps=__import__(
            "src.data_loader", fromlist=["generate_synthetic_ohlcv_garch"]).generate_synthetic_ohlcv_garch) as spy:
        garch_stress_dataset(
            primary_tf="H1", context_tfs=[], feature_columns=FEATURE_COLUMNS,
            stats=_fake_stats(FEATURE_COLUMNS), n_primary_bars=100, seed=1,
            dof=7.0, alpha=0.1, beta=0.85,
        )
        assert spy.called
        _, kwargs = spy.call_args
        assert kwargs["dof"] == 7.0
        assert kwargs["alpha"] == 0.1
        assert kwargs["beta"] == 0.85


# --------------------------------------------------------------------- #
# Câblage dans evaluate_agent_walkforward (chemin d'évaluation walk-forward)
# --------------------------------------------------------------------- #

def _build_real_df(n_bars=3000, seed=1):
    from src.data_loader import generate_synthetic_ohlcv
    from src.features import add_technical_features
    df = add_technical_features(generate_synthetic_ohlcv(n_bars=n_bars, seed=seed))
    df, stats = normalize_features(df, columns=FEATURE_COLUMNS)
    return df, stats


def test_evaluate_agent_walkforward_calls_garch_generator_when_enabled():
    """Critère de test explicitement demandé : un cycle réel avec garch
    activé appelle bien le générateur (spy)."""
    from src.trading_env import TradingEnv
    df, stats = _build_real_df()
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       feature_columns=FEATURE_COLUMNS)
    probe_env = TradingEnv(df, **env_kwargs)
    agent = _RandomAgent(probe_env.action_space)

    with patch("src.data_loader.generate_synthetic_ohlcv_garch", wraps=__import__(
            "src.data_loader", fromlist=["generate_synthetic_ohlcv_garch"]).generate_synthetic_ohlcv_garch) as spy:
        metrics = evaluate_agent_walkforward(
            agent, df, env_kwargs, n_windows=2, timeframe="H1",
            garch_stress=True, garch_context_tfs=[], garch_stats=stats,
        )
    assert spy.called, "generate_synthetic_ohlcv_garch doit être appelé quand garch_stress=True"
    stress_names = {w["stress"] for w in metrics.get("stress_windows", [])}
    assert "garch" in stress_names, "un scénario 'garch' doit apparaître dans stress_windows"


def test_evaluate_agent_walkforward_garch_disabled_by_default_no_call():
    """Comportement d'ORIGINE inchangé quand garch_stress n'est pas activé
    (défaut False) -- aucun appel au générateur, aucune entrée 'garch'."""
    from src.trading_env import TradingEnv
    df, stats = _build_real_df()
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       feature_columns=FEATURE_COLUMNS)
    probe_env = TradingEnv(df, **env_kwargs)
    agent = _RandomAgent(probe_env.action_space)

    with patch("src.data_loader.generate_synthetic_ohlcv_garch") as spy:
        metrics = evaluate_agent_walkforward(agent, df, env_kwargs, n_windows=2, timeframe="H1")
    assert not spy.called
    stress_names = {w["stress"] for w in metrics.get("stress_windows", [])}
    assert "garch" not in stress_names


def test_evaluate_agent_walkforward_garch_enabled_but_missing_context_or_stats_is_noop():
    """garch_stress=True SANS garch_context_tfs/garch_stats fournis (ex:
    ancien appelant qui n'a pas encore été mis à jour) -- ne doit jamais
    lever d'exception, simplement ne rien ajouter."""
    from src.trading_env import TradingEnv
    df, stats = _build_real_df()
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       feature_columns=FEATURE_COLUMNS)
    probe_env = TradingEnv(df, **env_kwargs)
    agent = _RandomAgent(probe_env.action_space)

    metrics = evaluate_agent_walkforward(agent, df, env_kwargs, n_windows=2, timeframe="H1",
                                           garch_stress=True)  # ni garch_context_tfs ni garch_stats
    stress_names = {w["stress"] for w in metrics.get("stress_windows", [])}
    assert "garch" not in stress_names


def test_evaluate_agent_walkforward_garch_unsupported_timeframe_gracefully_skipped():
    """garch_stress=True sur un style M15 (non supporté) : aucune exception,
    juste absent de stress_windows (même garde-fou que les autres scénarios)."""
    from src.trading_env import TradingEnv
    df, stats = _build_real_df()
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       feature_columns=FEATURE_COLUMNS)
    probe_env = TradingEnv(df, **env_kwargs)
    agent = _RandomAgent(probe_env.action_space)

    metrics = evaluate_agent_walkforward(agent, df, env_kwargs, n_windows=2, timeframe="M15",
                                           garch_stress=True, garch_context_tfs=[], garch_stats=stats)
    stress_names = {w["stress"] for w in metrics.get("stress_windows", [])}
    assert "garch" not in stress_names

"""Tests pour le chargeur de calendrier macro réel (audit institutionnel,
section 3 -- voir src/stress_test.py::load_macro_events_csv, câblé dans
inject_macro_shocks et evaluate_agent_walkforward). Fichier DÉDIÉ (pas
tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
import pandas as pd
import pytest

from src.stress_test import load_macro_events_csv, inject_macro_shocks
from src.data_loader import generate_synthetic_ohlcv


def test_loads_valid_csv_with_comments_skipped(tmp_path):
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "# ceci est un commentaire, doit être ignoré\n"
        "timestamp_utc,event_type\n"
        "2024-01-05T13:30:00,NFP\n"
        "2024-01-11T13:30:00,CPI\n",
        encoding="utf-8",
    )
    events = load_macro_events_csv(str(csv_path))
    assert len(events) == 2
    assert all(isinstance(e, pd.Timestamp) for e in events)
    assert events[0] == pd.Timestamp("2024-01-05T13:30:00")


def test_missing_timestamp_column_raises_value_error(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("date,type\n2024-01-01,CPI\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_macro_events_csv(str(csv_path))


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_macro_events_csv("data/this_file_does_not_exist_xyz.csv")


def test_example_file_loads_correctly_and_is_clearly_placeholder():
    """Le fichier fourni data/macro_events_example.csv doit se charger sans
    erreur (format valide) ET ses event_type doivent être clairement
    marqués comme des placeholders, jamais un vrai calendrier."""
    events = load_macro_events_csv("data/macro_events_example.csv")
    assert len(events) >= 1
    raw = pd.read_csv("data/macro_events_example.csv", comment="#")
    assert (raw["event_type"] == "EXAMPLE_PLACEHOLDER").all(), \
        "le fichier d'exemple fourni ne doit contenir QUE des event_type explicitement placeholder"
    # Année 2000 : loin de toute donnée de marché réelle utilisée par ce
    # projet (dataset Kaggle XAUUSD 2004-2026) -- confirme que ces dates ne
    # peuvent pas être confondues avec un vrai historique.
    assert all(e.year == 2000 for e in events)


def test_inject_macro_shocks_flags_candles_nearest_loaded_events(tmp_path):
    csv_path = tmp_path / "events.csv"
    df = generate_synthetic_ohlcv(n_bars=500, seed=1)
    # Choisit un timestamp EXACTEMENT sur une bougie existante -- doit être
    # flaguée avec une distance nulle.
    target_time = df.iloc[250]["time"]
    csv_path.write_text(f"timestamp_utc,event_type\n{target_time.isoformat()},CPI\n", encoding="utf-8")

    events = load_macro_events_csv(str(csv_path))
    result = inject_macro_shocks(df, event_timestamps=events, seed=1)

    assert result.loc[250, "cost_multiplier"] > 1.0
    assert result.loc[250, "slippage_price_offset"] > 0.0
    # Les autres bougies (loin de l'événement) doivent rester neutres.
    assert result.loc[0, "cost_multiplier"] == 1.0
    assert result.loc[499, "cost_multiplier"] == 1.0


def test_evaluate_agent_walkforward_passes_macro_event_timestamps_through(tmp_path):
    """Vérifie le câblage bout en bout : macro_event_timestamps fourni à
    evaluate_agent_walkforward doit bien atteindre inject_macro_shocks (spy)."""
    from unittest.mock import patch
    from src.trading_env import TradingEnv
    from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
    from src.backtester import evaluate_agent_walkforward

    df = add_technical_features(generate_synthetic_ohlcv(n_bars=3000, seed=2))
    df, _ = normalize_features(df, columns=FEATURE_COLUMNS)
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       feature_columns=FEATURE_COLUMNS)

    class _RandomAgent:
        def __init__(self, action_space):
            self.action_space = action_space
        def predict(self, obs, deterministic=True):
            return self.action_space.sample()

    probe_env = TradingEnv(df, **env_kwargs)
    agent = _RandomAgent(probe_env.action_space)
    events = [df.iloc[100]["time"]]

    # IMPORTANT : backtester.py fait `from src.stress_test import inject_macro_shocks`
    # (liaison locale au moment de l'import) -- patcher src.stress_test.inject_macro_shocks
    # ne toucherait PAS ce nom déjà lié dans src.backtester ; il faut patcher
    # à l'endroit où la fonction est UTILISÉE (src.backtester), pas où elle
    # est DÉFINIE (classique piège de unittest.mock).
    with patch("src.backtester.inject_macro_shocks", wraps=__import__(
            "src.stress_test", fromlist=["inject_macro_shocks"]).inject_macro_shocks) as spy:
        evaluate_agent_walkforward(agent, df, env_kwargs, n_windows=2, timeframe="H1",
                                     stress_test=True, macro_event_timestamps=events)
    assert spy.called
    _, kwargs = spy.call_args
    assert kwargs["event_timestamps"] == events


def test_none_macro_event_timestamps_preserves_original_proxy_behavior():
    """Comportement d'origine : macro_event_timestamps=None (défaut) ->
    inject_macro_shocks retombe sur son proxy statistique, jamais d'erreur."""
    from src.trading_env import TradingEnv
    from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
    from src.backtester import evaluate_agent_walkforward

    df = add_technical_features(generate_synthetic_ohlcv(n_bars=3000, seed=3))
    df, _ = normalize_features(df, columns=FEATURE_COLUMNS)
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       feature_columns=FEATURE_COLUMNS)

    class _RandomAgent:
        def __init__(self, action_space):
            self.action_space = action_space
        def predict(self, obs, deterministic=True):
            return self.action_space.sample()

    probe_env = TradingEnv(df, **env_kwargs)
    agent = _RandomAgent(probe_env.action_space)
    metrics = evaluate_agent_walkforward(agent, df, env_kwargs, n_windows=2, timeframe="H1", stress_test=True)
    stress_names = {w["stress"] for w in metrics.get("stress_windows", [])}
    assert "macro_shock" in stress_names

"""ENV_VERSION (LOT 2, phase 1) : un modèle entraîné sous une version
d'environnement différente ne doit jamais être chargé pour l'inférence ni
réutilisé comme warm start. Fichier DÉDIÉ (pas tests/test_autonomous.py),
comme demandé."""
from __future__ import annotations
import json
import os
import pytest

from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
from src.trading_env import TradingEnv, ENV_VERSION, env_version_matches, EnvVersionMismatch
from src.agent import TradingAgent


def _small_env():
    df = generate_synthetic_ohlcv(n_bars=200, seed=1)
    df = add_technical_features(df)
    df, _ = normalize_features(df, columns=FEATURE_COLUMNS)
    return TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS)


def _save_agent_with_meta(tmp_path, subdir, env_version):
    d = tmp_path / subdir
    d.mkdir()
    agent = TradingAgent(_small_env(), {"n_steps": 32, "batch_size": 16, "device": "cpu"})
    model_path = str(d / "agent")
    agent.save(model_path)
    meta = {"generation": 1, "score": 1.0, "feature_columns": FEATURE_COLUMNS, "algo": "PPO"}
    if env_version is not None:
        meta["env_version"] = env_version
    with open(d / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return model_path


def test_env_version_matches_true_when_equal():
    assert env_version_matches({"env_version": ENV_VERSION}) is True


def test_env_version_matches_false_when_different():
    assert env_version_matches({"env_version": ENV_VERSION - 1}) is False


def test_env_version_matches_false_when_key_absent():
    """meta.json d'avant l'introduction du mécanisme (version 1 implicite) --
    rejeté dès qu'ENV_VERSION > 1, sans cas particulier."""
    assert env_version_matches({}) is (ENV_VERSION == 1)


def test_tradingagent_load_refuses_mismatched_env_version(tmp_path):
    model_path = _save_agent_with_meta(tmp_path, "bad", env_version=ENV_VERSION - 1)
    with pytest.raises(EnvVersionMismatch):
        TradingAgent.load(model_path, _small_env(), {"algo": "PPO"})


def test_tradingagent_load_succeeds_with_matching_env_version(tmp_path):
    model_path = _save_agent_with_meta(tmp_path, "good", env_version=ENV_VERSION)
    loaded = TradingAgent.load(model_path, _small_env(), {"algo": "PPO"})
    assert loaded is not None


def test_tradingagent_load_succeeds_when_meta_absent(tmp_path):
    """Comportement d'ORIGINE préservé : pas de meta.json -> pas de blocage."""
    d = tmp_path / "no_meta"
    d.mkdir()
    agent = TradingAgent(_small_env(), {"n_steps": 32, "batch_size": 16, "device": "cpu"})
    model_path = str(d / "agent")
    agent.save(model_path)
    loaded = TradingAgent.load(model_path, _small_env(), {"algo": "PPO"})
    assert loaded is not None


def test_warm_start_skipped_silently_on_env_version_mismatch(tmp_path, caplog):
    import logging
    caplog.set_level(logging.INFO)
    model_path = _save_agent_with_meta(tmp_path, "warmsource", env_version=ENV_VERSION - 1)
    fresh_agent = TradingAgent(_small_env(), {"n_steps": 32, "batch_size": 16, "device": "cpu"},
                                warm_start_model_path=model_path)
    assert fresh_agent is not None  # ne plante jamais, retombe sur un agent neuf
    assert any("Warm start refusé" in r.message for r in caplog.records)


def test_warm_start_succeeds_on_matching_env_version(tmp_path, caplog):
    import logging
    caplog.set_level(logging.INFO)
    model_path = _save_agent_with_meta(tmp_path, "warmsource_ok", env_version=ENV_VERSION)
    TradingAgent(_small_env(), {"n_steps": 32, "batch_size": 16, "device": "cpu"},
                 warm_start_model_path=model_path)
    assert any("Warm start réussi" in r.message for r in caplog.records)


def test_scan_eligible_styles_excludes_wrong_env_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import _scan_eligible_styles
    from src.continuous_trainer import _champion_meta, _champion_stats

    os.makedirs("models/champion_M15", exist_ok=True)
    meta = {"generation": 1, "score": 1.0, "passes_validation": True,
            "feature_columns": FEATURE_COLUMNS, "primary_timeframe": "M15",
            "context_timeframes": [], "env_version": ENV_VERSION - 1}
    with open(_champion_meta("M15"), "w", encoding="utf-8") as f:
        json.dump(meta, f)
    with open(_champion_stats("M15"), "w", encoding="utf-8") as f:
        json.dump({}, f)

    cfg = {"data": {"timeframe_pool": ["M15"]}, "live": {"ensemble": True}}
    assert _scan_eligible_styles(cfg) == []


def test_scan_eligible_styles_includes_matching_env_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import _scan_eligible_styles
    from src.continuous_trainer import _champion_meta, _champion_stats

    os.makedirs("models/champion_M15", exist_ok=True)
    meta = {"generation": 1, "score": 1.0, "passes_validation": True,
            "feature_columns": FEATURE_COLUMNS, "primary_timeframe": "M15",
            "context_timeframes": [], "env_version": ENV_VERSION}
    with open(_champion_meta("M15"), "w", encoding="utf-8") as f:
        json.dump(meta, f)
    with open(_champion_stats("M15"), "w", encoding="utf-8") as f:
        json.dump({}, f)

    cfg = {"data": {"timeframe_pool": ["M15"]}, "live": {"ensemble": True}}
    eligible = _scan_eligible_styles(cfg)
    assert len(eligible) == 1 and eligible[0]["style"] == "M15"


def test_style_runtime_maybe_reload_blocks_wrong_env_version(monkeypatch):
    from src.demo_trader import _StyleRuntime

    rt = _StyleRuntime()
    entry = {"style": "M15", "meta": {"env_version": ENV_VERSION - 1, "updated_at": 123}}
    # Aucun des arguments suivants ne doit être touché -- le garde-fou doit
    # renvoyer avant toute tentative de reconstruction/chargement.
    rt.maybe_reload(entry, connector=None, fundamental_feed=None, n_bars_needed=100,
                     n_bars_context=100, memory=None, memory_top_k=5, env_kwargs={})
    assert rt.agent is None
    assert rt.last_loaded_at is None

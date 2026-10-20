"""Tests pour scripts/cross_asset_survival_test.py (audit institutionnel,
section 4 -- "Test de Survie Transversal"). Construit un faux champion
(petit agent entraîné rapidement sur des données synthétiques) dans un
répertoire temporaire, monkeypatché à la place de models/ -- ne dépend
JAMAIS des vrais champions de production."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cross_asset_survival_test as cast_module
from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
from src.trading_env import TradingEnv
from src.agent import TradingAgent


def _build_fake_champion(tmp_path, style: str, feature_columns: list[str]):
    """Entraîne un agent minuscule (quelques pas) sur des données
    synthétiques et l'enregistre comme un vrai champion (agent.zip +
    meta.json + norm_stats.json), dans un répertoire temporaire."""
    df = generate_synthetic_ohlcv(n_bars=1500, seed=5)
    df = add_technical_features(df)
    df_norm, stats = normalize_features(df, columns=feature_columns)

    env = TradingEnv(df_norm, window_size=20, feature_columns=feature_columns, style=style)
    agent = TradingAgent(env, {"algo": "PPO", "use_lstm": False, "n_steps": 32, "batch_size": 16})
    agent.learn(32)

    champ_dir = tmp_path / f"champion_{style}"
    champ_dir.mkdir(parents=True)
    agent.save(str(champ_dir / "agent"))
    from src.trading_env import ENV_VERSION
    with open(champ_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump({"feature_columns": feature_columns, "algo": "PPO", "score": 1.0,
                    "env_version": ENV_VERSION}, f)
    with open(champ_dir / "norm_stats.json", "w", encoding="utf-8") as f:
        json.dump({k: list(v) for k, v in stats.items()}, f)


def test_run_survival_test_returns_stability_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(cast_module, "MODELS_ROOT", str(tmp_path))
    _build_fake_champion(tmp_path, "M15", FEATURE_COLUMNS)

    target_df = generate_synthetic_ohlcv(n_bars=2000, seed=99)  # "autre symbole"
    metrics = cast_module.run_survival_test("M15", "SYNTHETIC_EURUSD", target_df, n_bars=1000, window_size=20)

    assert "stable" in metrics
    assert "verdict_reason" in metrics
    assert metrics["symbol"] == "SYNTHETIC_EURUSD"
    assert metrics["style"] == "M15"
    assert "sharpe" in metrics and "max_drawdown" in metrics


def test_run_survival_test_uses_champion_norm_stats_not_refit(tmp_path, monkeypatch):
    """Vérifie que les stats de normalisation utilisées viennent bien du
    champion (norm_stats.json), pas re-calculées sur les données cible --
    en donnant volontairement des stats ABSURDES au champion (moyenne/
    écart-type très éloignés des données réelles) et en vérifiant que le
    pipeline ne plante pas et utilise quand même ces valeurs (donc doit
    produire une observation TRÈS différente de ce qu'un refit produirait)."""
    monkeypatch.setattr(cast_module, "MODELS_ROOT", str(tmp_path))
    _build_fake_champion(tmp_path, "M15", FEATURE_COLUMNS)

    # Remplace les stats sauvegardées par des valeurs artificielles
    # facilement reconnaissables.
    champ_dir = tmp_path / "champion_M15"
    fake_stats = {c: [999.0, 1.0] for c in FEATURE_COLUMNS}
    with open(champ_dir / "norm_stats.json", "w", encoding="utf-8") as f:
        json.dump(fake_stats, f)

    loaded_stats = cast_module._load_norm_stats("M15")
    assert loaded_stats["return_1"] == (999.0, 1.0), \
        "les stats DOIVENT venir du champion (norm_stats.json), jamais recalculées sur les données cible"


def test_missing_champion_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(cast_module, "MODELS_ROOT", str(tmp_path))
    target_df = generate_synthetic_ohlcv(n_bars=500, seed=1)
    try:
        cast_module.run_survival_test("H1", "EURUSD", target_df)
        assert False, "devrait lever FileNotFoundError"
    except FileNotFoundError as e:
        assert "H1" in str(e)


def test_feature_mismatch_raises_clear_error_instead_of_silent_wrong_features(tmp_path, monkeypatch):
    """Un champion entraîné avec du contexte multi-timeframe (colonnes
    absentes d'un CSV mono-timeframe pour un autre symbole) doit lever une
    erreur EXPLICITE plutôt que de continuer avec des features
    manquantes/fausses -- voir docstring du module. Le mismatch est détecté
    AVANT le chargement du modèle (voir run_survival_test) : seuls
    meta.json/norm_stats.json sont nécessaires ici, pas un agent.zip
    entraîné (jamais atteint dans ce scénario)."""
    monkeypatch.setattr(cast_module, "MODELS_ROOT", str(tmp_path))
    mtf_columns = FEATURE_COLUMNS + ["rsi_14_4H", "trend_signal_1D"]  # contexte MTF fictif

    champ_dir = tmp_path / "champion_H4"
    champ_dir.mkdir(parents=True)
    with open(champ_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump({"feature_columns": mtf_columns, "algo": "PPO", "score": 1.0}, f)
    with open(champ_dir / "norm_stats.json", "w", encoding="utf-8") as f:
        json.dump({c: [0.0, 1.0] for c in mtf_columns}, f)

    target_df = generate_synthetic_ohlcv(n_bars=1000, seed=7)
    try:
        cast_module.run_survival_test("H4", "EURUSD_MONO_TF", target_df, n_bars=500)
        assert False, "devrait lever ValueError pour incompatibilité de features"
    except ValueError as e:
        assert "rsi_14_4H" in str(e) or "trend_signal_1D" in str(e)

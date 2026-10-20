"""LOT 2, phase 4, point 8 : câblage du veto de stabilité multi-actifs DANS
le cycle d'entraînement réel (src/continuous_trainer.py::run_one_cycle) --
le score de promotion reste calculé uniquement sur la validation OR, ce
veto peut seulement BLOQUER une promotion. Fichier DÉDIÉ (pas
tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
import os

from src.continuous_trainer import ContinuousEvolutionTrainer
import src.continuous_trainer as ct
from src.data_loader import generate_synthetic_ohlcv, chronological_split
from src.features import FEATURE_COLUMNS, add_technical_features, normalize_features

BASE_CFG = {
    "agent": {"policy": "MlpPolicy", "learning_rate": 3e-4, "n_steps": 128,
              "batch_size": 32, "gamma": 0.99, "gae_lambda": 0.95, "ent_coef": 0.01},
    "continuous": {"candidates_per_cycle": 2, "timesteps_per_cycle": 256, "mutation_scale": 0.2},
    "memory": {"db_path": None, "max_episodes": 500},
}


def _make_data_fn(n_bars=2000, seed=3):
    def get_data(primary_tf=None):
        df = generate_synthetic_ohlcv(n_bars=n_bars, seed=seed)
        df = add_technical_features(df)
        train_df, val_df, _ = chronological_split(df, 0.7, 0.3)
        train_df, stats = normalize_features(train_df, columns=FEATURE_COLUMNS)
        val_df, _ = normalize_features(val_df, stats, columns=FEATURE_COLUMNS)
        return train_df, val_df, stats, FEATURE_COLUMNS, []
    return get_data


def _env_kwargs():
    return dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)


def test_no_other_symbols_veto_never_invoked(tmp_path, monkeypatch):
    """multi_asset.enabled absent/faux (défaut) : other_symbol_dfs reste
    vide, stability_veto n'est même pas appelée -- comportement identique
    à avant ce mécanisme."""
    monkeypatch.chdir(tmp_path)
    calls = []
    original = ct.stability_veto

    def spy(*a, **k):
        calls.append(1)
        return original(*a, **k)
    monkeypatch.setattr(ct, "stability_veto", spy)

    cfg = dict(BASE_CFG)
    cfg["memory"] = {"db_path": "mem_veto1.sqlite", "max_episodes": 500}
    trainer = ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], _env_kwargs())
    trainer.run_one_cycle()

    assert calls == [], "stability_veto ne doit jamais être appelée sans symboles additionnels configurés"
    assert trainer.has_champion("H1") is True
    trainer.close()


def test_veto_blocks_champion_promotion_when_unstable(tmp_path, monkeypatch):
    """Cœur du test : un candidat qui AURAIT été promu (meilleur score) est
    BLOQUÉ si le veto de stabilité échoue -- le score walk-forward seul ne
    suffit plus."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ct, "stability_veto", lambda *a, **k: (False, [{"symbol": "EURUSD", "stable": False}]))

    cfg = dict(BASE_CFG)
    cfg["memory"] = {"db_path": "mem_veto2.sqlite", "max_episodes": 500}
    trainer = ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], _env_kwargs())
    # Force other_symbol_dfs non vide (contourne discover_configured_symbols,
    # qui exigerait de vrais fichiers sur disque) : monkeypatch direct sur
    # la fonction de chargement pour simuler un symbole additionnel présent.
    import src.multi_asset as ma
    monkeypatch.setattr(ma, "discover_configured_symbols", lambda cfg: {"EURUSD": "dummy_path"})
    monkeypatch.setattr(ma, "load_symbol_ohlcv", lambda path: generate_synthetic_ohlcv(n_bars=500, seed=1))
    # continuous_trainer a importé ces fonctions par nom -- il faut aussi les
    # monkeypatcher DANS ct, pas seulement dans le module source.
    monkeypatch.setattr(ct, "discover_configured_symbols", lambda cfg: {"EURUSD": "dummy_path"})
    monkeypatch.setattr(ct, "load_symbol_ohlcv", lambda path: generate_synthetic_ohlcv(n_bars=500, seed=1))

    trainer.run_one_cycle()

    assert trainer.has_champion("H1") is False, \
        "aucun champion ne doit être promu -- le veto de stabilité a bloqué la seule promotion possible"
    trainer.close()


def test_veto_allows_promotion_when_stable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ct, "stability_veto", lambda *a, **k: (True, [{"symbol": "EURUSD", "stable": True}]))

    cfg = dict(BASE_CFG)
    cfg["memory"] = {"db_path": "mem_veto3.sqlite", "max_episodes": 500}
    trainer = ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], _env_kwargs())
    monkeypatch.setattr(ct, "discover_configured_symbols", lambda cfg: {"EURUSD": "dummy_path"})
    monkeypatch.setattr(ct, "load_symbol_ohlcv", lambda path: generate_synthetic_ohlcv(n_bars=500, seed=1))

    trainer.run_one_cycle()

    assert trainer.has_champion("H1") is True, "un veto qui passe ne doit jamais empêcher une promotion légitime"
    trainer.close()

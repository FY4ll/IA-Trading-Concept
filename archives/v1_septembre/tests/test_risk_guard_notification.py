"""LOT 2 (suite), 22/09 : demande explicite de l'utilisateur ("plus jamais")
après un mouvement H4 réel (-0.93%) passé inaperçu -- le filet de sécurité
indépendant (src/risk_guard.py, `anomaly_scale`) détectait déjà ce genre de
mouvement (il lit directement la dernière bougie récupérée, jamais sujet au
décalage de fenêtre de l'agent -- voir tests/test_live_decision_freshness.py
pour ce bug-là), mais ne faisait que journaliser un `log.warning` : rien
n'avertissait proactivement l'utilisateur en (quasi) temps réel. Corrigé en
câblant `send_alert` sur les TRANSITIONS de `_StyleRuntime.guard_active`
(début d'anomalie -> notifie une fois ; fin d'anomalie -> notifie une fois ;
anomalie qui persiste plusieurs cycles -> silence, pas de spam).

Seuil de NOTIFICATION (`risk_guard_notify_z_threshold`, 2.5 par défaut)
DÉLIBÉRÉMENT séparé et plus bas que le seuil de RÉDUCTION D'EXPOSITION
(`risk_guard_z_threshold`, 4.0 par défaut) : le mouvement réel du 22/09 qui a
déclenché cette demande n'aurait PAS forcément franchi z=4.0 (pas assez
extrême statistiquement pour justifier une réduction de risque), mais
mérite quand même d'être porté à la connaissance de l'utilisateur."""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

from src.data_loader import generate_synthetic_ohlcv


def _flat_series(n_bars, seed, jump_last=None):
    df = generate_synthetic_ohlcv(n_bars=n_bars, seed=seed)
    if jump_last is not None:
        # Un saut sur la TOUTE DERNIÈRE bougie -- bien plus grand que le
        # bruit habituel de generate_synthetic_ohlcv, pour déclencher
        # anomaly_scale de façon fiable et déterministe.
        last_close = df["close"].iloc[-1]
        new_close = last_close * (1 + jump_last)
        df.loc[df.index[-1], ["close", "high"] if jump_last > 0 else ["close", "low"]] = new_close
    return df


def _train_and_deploy_tiny_champion(env_kwargs):
    import json
    from src.trading_env import TradingEnv, ENV_VERSION
    from src.agent import TradingAgent
    from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
    from src.continuous_trainer import DEMO_DIR, DEMO_MODEL, DEMO_META, DEMO_STATS

    df = generate_synthetic_ohlcv(n_bars=1000, seed=1)
    df = add_technical_features(df)
    df, stats = normalize_features(df, columns=FEATURE_COLUMNS)
    env = TradingEnv(df, feature_columns=FEATURE_COLUMNS, **env_kwargs)
    agent = TradingAgent(env, {"n_steps": 64, "batch_size": 16})
    agent.learn(64)

    os.makedirs(DEMO_DIR, exist_ok=True)
    agent.save(DEMO_MODEL)
    with open(DEMO_META, "w") as f:
        json.dump({
            "generation": 0, "score": 5.0, "updated_at": 123.0,
            "primary_timeframe": "H1", "context_timeframes": [],
            "feature_columns": FEATURE_COLUMNS, "env_version": ENV_VERSION,
        }, f)
    with open(DEMO_STATS, "w") as f:
        json.dump({k: list(v) for k, v in stats.items()}, f)


def _make_fake_connector(series_by_cycle, call_count):
    class FakeMTFConnector:
        def connect(self):
            pass

        def is_demo_account(self):
            return True

        def close_orphan_positions(self, recognized_styles):
            return []

        def get_open_positions_by_style(self, recognized_styles):
            return {}

        def get_latest_bars(self, timeframe, n_bars):
            idx = min(call_count["n"], len(series_by_cycle) - 1)
            call_count["n"] += 1
            return series_by_cycle[idx]

        def send_order(self, target_position, stop_pct=None, **kwargs):
            pass

    return FakeMTFConnector()


def test_risk_guard_notifies_only_on_anomaly_transitions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import run_demo_trading_loop
    import src.notifier as notifier_module

    alerts = []
    monkeypatch.setattr(notifier_module, "send_alert",
                         lambda cfg, subject, message: alerts.append((subject, message)))

    # Séries retournées par le faux connecteur, cycle par cycle : calme,
    # calme, ANOMALIE (saut de +25% sur la dernière bougie, franchit LES
    # DEUX seuils), ANOMALIE (persiste), calme (retour à la normale).
    series_by_cycle = [
        _flat_series(1000, seed=1),
        _flat_series(1000, seed=1),
        _flat_series(1000, seed=1, jump_last=0.25),
        _flat_series(1000, seed=1, jump_last=0.25),
        _flat_series(1000, seed=1),
    ]
    call_count = {"n": 0}

    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    _train_and_deploy_tiny_champion(env_kwargs)

    cfg = {"live": {"dry_run": True, "poll_seconds": 0, "allow_real_account": False,
                     "risk_guard": True, "risk_guard_z_threshold": 4.0,
                     "risk_guard_notify_z_threshold": 2.5},
           "notifications": {"enabled": True, "channel": "ntfy"},
           "fundamental": {"enabled": False}, "data": {"n_bars_context": 500},
           "market_hours": {"enabled": False}}
    fake = _make_fake_connector(series_by_cycle, call_count)
    run_demo_trading_loop(cfg, env_kwargs, connector=fake, max_iterations=5)

    subjects = [s for s, _ in alerts]
    activations = [s for s in subjects if "Mouvement de marché notable" in s]
    deactivations = [s for s in subjects if "Marché redevenu normal" in s]
    assert len(activations) == 1, f"une seule notification attendue au DÉBUT de l'anomalie (cycle 3), obtenu {subjects}"
    assert len(deactivations) == 1, f"une seule notification attendue au RETOUR à la normale (cycle 5), obtenu {subjects}"


def test_risk_guard_notifies_without_reducing_exposure_below_action_threshold(tmp_path, monkeypatch):
    """Coeur du découplage des deux seuils : un mouvement franchissant le
    seuil de NOTIFICATION (2.5) mais PAS celui de RÉDUCTION D'EXPOSITION
    (4.0, volontairement laissé haut ici) doit quand même déclencher une
    alerte -- sans toucher à l'exposition envoyée à MT5. Exactement le cas
    réel du 22/09 : un mouvement "notable" mais pas assez extrême
    statistiquement pour que le filet de sécurité intervienne sur le risque."""
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import run_demo_trading_loop
    from src.risk_guard import anomaly_scale
    import src.notifier as notifier_module

    alerts = []
    monkeypatch.setattr(notifier_module, "send_alert",
                         lambda cfg, subject, message: alerts.append((subject, message)))

    # Calibre un saut "moyen" dont le z-score dépasse 2.5 mais reste < 8.0
    # (seuil de réduction volontairement mis très haut dans ce test pour
    # isoler le comportement de notification pure).
    calm = _flat_series(1000, seed=3)
    moderate = _flat_series(1000, seed=3, jump_last=0.005)
    scale_check, info_check = anomaly_scale(moderate, lookback=200, z_threshold=8.0)
    assert scale_check == 1.0, "précondition du test : ce mouvement ne doit PAS franchir le seuil de réduction (8.0)"
    assert max(info_check["last_return_z"], info_check["last_vol_z"]) > 2.5, \
        "précondition du test : ce mouvement DOIT franchir le seuil de notification (2.5)"

    series_by_cycle = [calm, moderate]
    call_count = {"n": 0}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    _train_and_deploy_tiny_champion(env_kwargs)

    cfg = {"live": {"dry_run": True, "poll_seconds": 0, "allow_real_account": False,
                     "risk_guard": True, "risk_guard_z_threshold": 8.0,
                     "risk_guard_notify_z_threshold": 2.5},
           "notifications": {"enabled": True, "channel": "ntfy"},
           "fundamental": {"enabled": False}, "data": {"n_bars_context": 500},
           "market_hours": {"enabled": False}}
    fake = _make_fake_connector(series_by_cycle, call_count)
    run_demo_trading_loop(cfg, env_kwargs, connector=fake, max_iterations=2)

    subjects_and_messages = alerts
    activations = [(s, m) for s, m in subjects_and_messages if "Mouvement de marché notable" in s]
    assert len(activations) == 1, f"attendu 1 notification malgré l'absence de réduction d'exposition, obtenu {alerts}"
    assert "facteur 1.00" in activations[0][1], \
        f"l'exposition ne doit PAS avoir été réduite (facteur 1.00 attendu) : {activations[0][1]}"

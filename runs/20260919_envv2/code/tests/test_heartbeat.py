"""Tests pour le heartbeat / détection de perte de connexion MT5 (audit
institutionnel, section 5) -- voir src/demo_trader.py::run_demo_trading_loop
et MT5Connector.seconds_since_last_success/measure_round_trip_ms. Fichier
DÉDIÉ (pas tests/test_autonomous.py), comme demandé.

Critères de test explicitement demandés :
  - coupure avec position -> 1 alerte
  - coupure sans position -> 0 alerte
  - coupure prolongée -> toujours 1 (pas de spam)
  - retour -> 1 alerte de rétablissement
"""
from __future__ import annotations
from unittest.mock import patch

import src.demo_trader as demo_trader_module


class _FakeConnector:
    """Connecteur factice minimal : `seconds_since_last_success` consomme une
    SÉQUENCE de valeurs (une par appel, une par cycle de la boucle) --
    permet de simuler une coupure puis un rétablissement au fil des cycles.
    `positions_by_style` peut aussi être une séquence (une par cycle) ou un
    dict fixe réutilisé à chaque cycle."""

    def __init__(self, stale_sequence, positions_by_style=None, rtt=None):
        self._stale_sequence = list(stale_sequence)
        self._positions_by_style = positions_by_style if positions_by_style is not None else {}
        self._rtt = rtt

    def connect(self):
        pass

    def close_orphan_positions(self, recognized_styles):
        return []

    def seconds_since_last_success(self):
        if self._stale_sequence:
            return self._stale_sequence.pop(0)
        return 0.0  # frais par défaut une fois la séquence épuisée

    def get_open_positions_by_style(self, recognized_styles):
        if isinstance(self._positions_by_style, list):
            return self._positions_by_style.pop(0) if self._positions_by_style else {}
        return self._positions_by_style

    def measure_round_trip_ms(self):
        return self._rtt


_BASE_CFG = {
    "live": {"dry_run": True, "poll_seconds": 0, "allow_real_account": False,
              "timeframe_pool": ["H1"], "heartbeat_timeout_s": 5.0},
    "data": {"timeframe_pool": ["H1"]},
    "fundamental": {"enabled": False},
    "market_hours": {"enabled": False},
    "memory": {},
    "notifications": {"enabled": True},
}
_ENV_KWARGS = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                    reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)


def test_outage_with_open_position_sends_exactly_one_alert(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = _FakeConnector(stale_sequence=[10.0], positions_by_style={"H1": {"direction": 1}})
    with patch("src.notifier.send_alert") as mock_alert:
        demo_trader_module.run_demo_trading_loop(_BASE_CFG, _ENV_KWARGS, connector=conn, max_iterations=1)
    connection_alerts = [c for c in mock_alert.call_args_list if "connexion" in c.kwargs.get("subject", c.args[1] if len(c.args) > 1 else "").lower()]
    assert len(connection_alerts) == 1


def test_outage_without_open_position_sends_no_alert(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = _FakeConnector(stale_sequence=[10.0, 10.0], positions_by_style={})
    with patch("src.notifier.send_alert") as mock_alert:
        demo_trader_module.run_demo_trading_loop(_BASE_CFG, _ENV_KWARGS, connector=conn, max_iterations=2)
    connection_alerts = [c for c in mock_alert.call_args_list
                          if "connexion" in str(c).lower() or "connection" in str(c).lower()]
    assert len(connection_alerts) == 0


def test_prolonged_outage_still_sends_only_one_alert(tmp_path, monkeypatch):
    """Coupure prolongée sur 5 cycles consécutifs -- une seule alerte au
    total, pas une par cycle (pas de spam)."""
    monkeypatch.chdir(tmp_path)
    conn = _FakeConnector(stale_sequence=[10.0] * 5, positions_by_style={"H1": {"direction": 1}})
    with patch("src.notifier.send_alert") as mock_alert:
        demo_trader_module.run_demo_trading_loop(_BASE_CFG, _ENV_KWARGS, connector=conn, max_iterations=5)
    connection_alerts = [c for c in mock_alert.call_args_list
                          if "connexion mt5" in str(c).lower()]
    assert len(connection_alerts) == 1, \
        f"attendu exactement 1 alerte sur une coupure prolongée, obtenu {len(connection_alerts)}"


def test_recovery_after_outage_sends_one_recovery_alert(tmp_path, monkeypatch):
    """Coupure (1 alerte) PUIS rétablissement (1 alerte de rétablissement,
    distincte) -- 2 alertes au total, de sujets différents."""
    monkeypatch.chdir(tmp_path)
    # cycle 1 : coupure (10s, seuil 5s) avec position -> alerte + cycle sauté
    # cycle 2 : rétablie (1s, sous le seuil) -> alerte de rétablissement
    conn = _FakeConnector(stale_sequence=[10.0, 1.0],
                            positions_by_style={"H1": {"direction": 1}})
    with patch("src.notifier.send_alert") as mock_alert:
        demo_trader_module.run_demo_trading_loop(_BASE_CFG, _ENV_KWARGS, connector=conn, max_iterations=2)

    subjects = [str(c) for c in mock_alert.call_args_list]
    outage_alerts = [s for s in subjects if "alerte perte de connexion" in s.lower()]
    recovery_alerts = [s for s in subjects if "rétablie" in s.lower()]
    assert len(outage_alerts) == 1
    assert len(recovery_alerts) == 1


def test_no_outage_no_recovery_alert_when_always_fresh(tmp_path, monkeypatch):
    """Jamais de coupure -- jamais d'alerte de connexion ni de rétablissement."""
    monkeypatch.chdir(tmp_path)
    conn = _FakeConnector(stale_sequence=[0.5, 0.5, 0.5], positions_by_style={"H1": {"direction": 1}})
    with patch("src.notifier.send_alert") as mock_alert:
        demo_trader_module.run_demo_trading_loop(_BASE_CFG, _ENV_KWARGS, connector=conn, max_iterations=3)
    subjects = [str(c) for c in mock_alert.call_args_list]
    assert not any("connexion" in s.lower() for s in subjects)


def test_missing_heartbeat_method_never_raises_and_no_outage_detected(tmp_path, monkeypatch):
    """Connecteur sans seconds_since_last_success (ex: vieux faux connecteur
    de test) -- comportement d'origine inchangé, jamais d'exception."""
    monkeypatch.chdir(tmp_path)

    class _MinimalConnector:
        def connect(self):
            pass
        def close_orphan_positions(self, recognized_styles):
            return []
        def get_open_positions_by_style(self, recognized_styles):
            return {}

    with patch("src.notifier.send_alert") as mock_alert:
        demo_trader_module.run_demo_trading_loop(_BASE_CFG, _ENV_KWARGS, connector=_MinimalConnector(),
                                                    max_iterations=1)
    assert not mock_alert.called


def test_round_trip_ms_logged_in_live_status(tmp_path, monkeypatch):
    """measure_round_trip_ms() doit être appelé et sa valeur transmise à
    write_live_status -- seulement observable quand au moins un cycle
    atteint write_live_status (nécessite un style éligible, sinon la boucle
    revient avant), donc on vérifie ici juste que measure_round_trip_ms EST
    appelé pendant un cycle normal (pas de coupure)."""
    monkeypatch.chdir(tmp_path)
    conn = _FakeConnector(stale_sequence=[0.1], positions_by_style={}, rtt=42.5)
    with patch.object(conn, "measure_round_trip_ms", wraps=conn.measure_round_trip_ms) as spy:
        demo_trader_module.run_demo_trading_loop(_BASE_CFG, _ENV_KWARGS, connector=conn, max_iterations=1)
    assert spy.called

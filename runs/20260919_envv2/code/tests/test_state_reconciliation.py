"""Tests pour src/state_reconciliation.py -- audit institutionnel, section 5
("Module de Réconciliation des États"). Vérifie que la mémoire interne d'un
style (son tracker, voir src/demo_trader.py::_LiveMemoryTracker) est
réalignée sur la réalité MT5 en cas de divergence, avec alerte, et qu'un
état déjà cohérent ne déclenche rien."""
from __future__ import annotations
from unittest.mock import patch

from src.state_reconciliation import reconcile_state


class _FakeTracker:
    def __init__(self, entry_exposure=0.0, entry_price=None):
        self.entry_exposure = entry_exposure
        self.entry_price = entry_price
        self.entry_context = "some_context"


class _FakeRuntime:
    def __init__(self, entry_exposure=0.0, entry_price=None):
        self.tracker = _FakeTracker(entry_exposure, entry_price)


class _FakeConnector:
    def __init__(self, positions_by_style: dict):
        self._positions = positions_by_style
        self.calls = 0

    def get_open_positions_by_style(self, recognized_styles):
        self.calls += 1
        return {s: p for s, p in self._positions.items() if s in recognized_styles}


def test_no_discrepancy_when_states_match():
    rt = _FakeRuntime(entry_exposure=1.0, entry_price=2000.0)
    conn = _FakeConnector({"M15": {"ticket": 1, "direction": 1, "volume": 0.1, "price_open": 2000.0, "profit": 5.0}})
    cfg = {"notifications": {"enabled": False}}

    with patch("src.notifier.send_alert") as mock_alert:
        discrepancies = reconcile_state(conn, cfg, {"M15": rt})

    assert discrepancies == []
    mock_alert.assert_not_called()
    assert rt.tracker.entry_exposure == 1.0  # inchangé


def test_no_discrepancy_when_both_flat():
    rt = _FakeRuntime(entry_exposure=0.0, entry_price=None)
    conn = _FakeConnector({})
    cfg = {"notifications": {"enabled": False}}
    discrepancies = reconcile_state(conn, cfg, {"M15": rt})
    assert discrepancies == []


def test_detects_and_corrects_stop_loss_hit_at_broker_without_ai_knowing():
    """Scénario exact du cahier des charges : un stop-loss a sauté chez le
    broker mais l'IA ne l'a pas enregistré -- mémoire interne croit une
    position LONGUE ouverte, MT5 ne montre plus rien (à plat)."""
    rt = _FakeRuntime(entry_exposure=1.0, entry_price=2000.0)
    conn = _FakeConnector({})  # plus aucune position réelle
    cfg = {"notifications": {"enabled": False}}

    with patch("src.notifier.send_alert") as mock_alert:
        discrepancies = reconcile_state(conn, cfg, {"M15": rt})

    assert len(discrepancies) == 1
    assert discrepancies[0]["style"] == "M15"
    assert discrepancies[0]["broker_direction"] is None
    mock_alert.assert_called_once()
    # ALIGNEMENT sur la réalité du broker (à plat) :
    assert rt.tracker.entry_exposure == 0.0
    assert rt.tracker.entry_price is None
    assert rt.tracker.entry_context is None


def test_detects_and_corrects_restart_with_unknown_open_position():
    """Scénario "redémarrage pendant qu'une position réelle était ouverte" :
    tracker fraîchement créé (à plat, comme au démarrage), mais MT5 montre
    une position SHORT réelle ouverte."""
    rt = _FakeRuntime(entry_exposure=0.0, entry_price=None)
    conn = _FakeConnector({"H4": {"ticket": 42, "direction": -1, "volume": 0.05,
                                    "price_open": 2500.0, "profit": -3.0}})
    cfg = {"notifications": {"enabled": False}}

    with patch("src.notifier.send_alert") as mock_alert:
        discrepancies = reconcile_state(conn, cfg, {"H4": rt})

    assert len(discrepancies) == 1
    assert discrepancies[0]["broker_ticket"] == 42
    assert discrepancies[0]["kind"] == "reprise_apres_redemarrage"
    # 05/10/2026 : une reprise après redémarrage est NORMALE -- réalignement, mais plus d'alerte "divergence".
    mock_alert.assert_not_called()
    assert rt.tracker.entry_exposure == -1.0
    assert rt.tracker.entry_price == 2500.0


def test_direction_mismatch_still_alerts():
    rt = _FakeRuntime(entry_exposure=1.0, entry_price=2000.0)
    conn = _FakeConnector({"H1": {"ticket": 9, "direction": -1, "volume": 0.1, "price_open": 2010.0, "profit": 0.0}})
    with patch("src.notifier.send_alert") as mock_alert:
        d = reconcile_state(conn, {"notifications": {"enabled": False}}, {"H1": rt})
    assert d[0]["kind"] == "direction_contraire"
    mock_alert.assert_called_once()


def test_detects_direction_mismatch_even_when_both_have_a_position():
    """Cas plus subtil : les deux croient qu'une position est ouverte, mais
    dans des DIRECTIONS opposées -- doit quand même être détecté."""
    rt = _FakeRuntime(entry_exposure=1.0, entry_price=2000.0)  # interne : LONG
    conn = _FakeConnector({"M15": {"ticket": 7, "direction": -1, "volume": 0.1,
                                     "price_open": 2010.0, "profit": 0.0}})  # broker : SHORT
    cfg = {"notifications": {"enabled": False}}

    discrepancies = reconcile_state(conn, cfg, {"M15": rt})
    assert len(discrepancies) == 1
    assert rt.tracker.entry_exposure == -1.0
    assert rt.tracker.entry_price == 2010.0


def test_uses_provided_broker_positions_without_extra_mt5_call():
    """Quand `broker_positions` est déjà fourni par l'appelant (voir
    demo_trader.py, qui réutilise `open_by_style` déjà récupéré ce cycle),
    aucun appel MT5 supplémentaire ne doit être fait."""
    rt = _FakeRuntime(entry_exposure=0.0, entry_price=None)
    conn = _FakeConnector({"M15": {"ticket": 1, "direction": 1, "volume": 0.1,
                                     "price_open": 2000.0, "profit": 0.0}})
    cfg = {"notifications": {"enabled": False}}

    reconcile_state(conn, cfg, {"M15": rt}, broker_positions={"M15": {
        "ticket": 1, "direction": 1, "volume": 0.1, "price_open": 2000.0, "profit": 0.0}})

    assert conn.calls == 0, "ne doit PAS rappeler get_open_positions_by_style si broker_positions est fourni"


def test_empty_runtimes_returns_empty_without_calling_connector():
    conn = _FakeConnector({})
    cfg = {"notifications": {"enabled": False}}
    discrepancies = reconcile_state(conn, cfg, {})
    assert discrepancies == []
    assert conn.calls == 0


def test_connector_failure_returns_empty_list_never_raises():
    class _FailingConnector:
        def get_open_positions_by_style(self, recognized_styles):
            raise RuntimeError("MT5 indisponible")

    rt = _FakeRuntime(entry_exposure=1.0, entry_price=2000.0)
    cfg = {"notifications": {"enabled": False}}
    discrepancies = reconcile_state(_FailingConnector(), cfg, {"M15": rt})
    assert discrepancies == []
    assert rt.tracker.entry_exposure == 1.0  # jamais modifié si la lecture MT5 échoue

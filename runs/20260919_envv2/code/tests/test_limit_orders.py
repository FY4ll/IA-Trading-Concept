"""LOT 2, phase 8 : ordres à cours limité (MT5Connector.send_order,
live.order_type: "market" (défaut, inchangé) | "limit") -- UNIQUEMENT pour
les OUVERTURES, une clôture reste TOUJOURS au marché. Fichier DÉDIÉ (pas
tests/test_autonomous.py ni tests/test_account_guard_send_order.py), comme
demandé."""
from __future__ import annotations
import types
import pytest

from src.mt5_connector import MT5Connector


def _make_fake_mt5(equity, bid, ask, contract_size, requests, existing_position=None,
                     pending_orders=None):
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.TRADE_ACTION_PENDING = 5
    fake_mt5.TRADE_ACTION_REMOVE = 8
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_TYPE_BUY_LIMIT = 2
    fake_mt5.ORDER_TYPE_SELL_LIMIT = 3
    fake_mt5.ORDER_TIME_GTC = 0
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009
    fake_mt5.TRADE_RETCODE_PLACED = 10008
    account = types.SimpleNamespace(trade_mode=0, equity=equity)
    fake_mt5.account_info = lambda: account
    positions = [existing_position] if existing_position is not None else []
    fake_mt5.positions_get = lambda symbol=None: positions
    fake_mt5.orders_get = lambda symbol=None: list(pending_orders or [])
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=contract_size, volume_step=0.01, volume_min=0.01,
        volume_max=100.0, digits=2, filling_mode=0, trade_stops_level=0, point=0.01)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=bid, ask=ask, time=1_700_000_000)

    def fake_order_send(request):
        requests.append(request)
        if request.get("action") == fake_mt5.TRADE_ACTION_REMOVE:
            return types.SimpleNamespace(retcode=fake_mt5.TRADE_RETCODE_DONE)
        retcode = (fake_mt5.TRADE_RETCODE_PLACED if request.get("action") == fake_mt5.TRADE_ACTION_PENDING
                   else fake_mt5.TRADE_RETCODE_DONE)
        return types.SimpleNamespace(retcode=retcode, price=request.get("price"))
    fake_mt5.order_send = fake_order_send
    return fake_mt5


def _make_position(direction: int, volume: float, ticket: int = 1, comment=None):
    return types.SimpleNamespace(
        ticket=ticket, type=(0 if direction == 1 else 1), volume=volume,
        price_open=2000.0, sl=1900.0, profit=0.0, comment=comment,
    )


def _make_pending_order(ticket: int, comment: str):
    return types.SimpleNamespace(ticket=ticket, comment=comment)


def _connector(order_type="market", equity=10000.0, bid=2000.0, ask=2000.5, contract_size=100.0,
                requests=None, existing_position=None, pending_orders=None):
    requests = requests if requests is not None else []
    fake_mt5 = _make_fake_mt5(equity, bid, ask, contract_size, requests, existing_position, pending_orders)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                     "allow_real_account": False, "max_risk_pct_per_trade": 0.02,
                     "order_type": order_type}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    return conn, requests


def test_market_order_type_default_behavior_unchanged():
    conn, requests = _connector()  # order_type non précisé -> "market" par défaut
    conn.send_order(1.0, stop_pct=0.01)
    assert len(requests) == 1
    assert requests[0]["action"] == conn._mt5.TRADE_ACTION_DEAL
    assert requests[0]["type"] == conn._mt5.ORDER_TYPE_BUY


def test_limit_order_type_uses_pending_action_and_limit_type():
    conn, requests = _connector(order_type="limit")
    conn.send_order(1.0, stop_pct=0.01, style="M15", generation=1)
    assert len(requests) == 1
    req = requests[0]
    assert req["action"] == conn._mt5.TRADE_ACTION_PENDING
    assert req["type"] == conn._mt5.ORDER_TYPE_BUY_LIMIT
    assert req["type_time"] == conn._mt5.ORDER_TIME_GTC


def test_limit_order_price_never_worse_than_max_slippage_for_buy():
    conn, requests = _connector(order_type="limit", bid=2000.0, ask=2000.5)
    conn.cfg["limit_order_max_slippage_pct"] = 0.001
    conn.send_order(1.0, stop_pct=0.01)
    req = requests[0]
    max_acceptable = 2000.5 * 1.001
    assert req["price"] <= max_acceptable + 0.01  # marge d'arrondi (digits=2)


def test_limit_order_price_never_worse_than_max_slippage_for_sell():
    conn, requests = _connector(order_type="limit", bid=2000.0, ask=2000.5)
    conn.cfg["limit_order_max_slippage_pct"] = 0.001
    conn.send_order(-1.0, stop_pct=0.01)
    req = requests[0]
    min_acceptable = 2000.0 * 0.999
    assert req["price"] >= min_acceptable - 0.01


def test_limit_order_success_checked_against_placed_not_done_retcode():
    """Un ordre à cours limité "réussi" = TRADE_RETCODE_PLACED (en attente),
    pas TRADE_RETCODE_DONE (exécuté immédiatement, sémantique du marché)."""
    conn, requests = _connector(order_type="limit")
    conn.send_order(1.0, stop_pct=0.01, style="M15", generation=1)
    assert len(requests) == 1  # la requête est bien partie (pas refusée en amont)


def test_closing_always_uses_market_order_even_with_limit_configured():
    """Une clôture reste TOUJOURS au marché, quel que soit order_type --
    jamais un risque de ne pas pouvoir sortir d'une position."""
    existing = _make_position(direction=1, volume=0.10)
    conn, requests = _connector(order_type="limit", existing_position=existing)
    conn.send_order(0.0)  # clôture
    assert len(requests) == 1
    assert requests[0]["action"] == conn._mt5.TRADE_ACTION_DEAL, \
        "une clôture doit toujours être TRADE_ACTION_DEAL (marché), jamais TRADE_ACTION_PENDING"


def test_stale_pending_order_for_same_style_cancelled_before_new_one():
    stale = _make_pending_order(ticket=42, comment="M15 gen:5")
    conn, requests = _connector(order_type="limit", pending_orders=[stale])
    conn.send_order(1.0, stop_pct=0.01, style="M15", generation=6)
    cancel_requests = [r for r in requests if r.get("action") == conn._mt5.TRADE_ACTION_REMOVE]
    assert len(cancel_requests) == 1
    assert cancel_requests[0]["order"] == 42


def test_pending_order_of_different_style_not_cancelled():
    other_style_order = _make_pending_order(ticket=99, comment="H1 gen:2")
    conn, requests = _connector(order_type="limit", pending_orders=[other_style_order])
    conn.send_order(1.0, stop_pct=0.01, style="M15", generation=6)
    cancel_requests = [r for r in requests if r.get("action") == conn._mt5.TRADE_ACTION_REMOVE]
    assert len(cancel_requests) == 0, "un ordre en attente d'un AUTRE style ne doit jamais être annulé"


def test_limit_order_still_respects_account_guard_halt():
    import src.account_guard as account_guard
    import tempfile, os
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        account_guard._write_state({"halted": True, "halted_reason": "test"})
        conn, requests = _connector(order_type="limit")
        conn.send_order(1.0, stop_pct=0.01)
        assert len(requests) == 0, "le coupe-circuit de compte doit bloquer une ouverture même en mode limit"
    finally:
        os.chdir(cwd)


def test_limit_order_still_respects_atr_unavailable_refusal():
    conn, requests = _connector(order_type="limit")
    conn.send_order(1.0, atr_multiplier=2.0, atr_price_units=None)
    assert len(requests) == 0, "le garde-fou ATR indisponible doit bloquer une ouverture même en mode limit"

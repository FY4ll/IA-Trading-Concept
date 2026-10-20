"""Tests pour le disjoncteur de compte câblé DIRECTEMENT dans
MT5Connector.send_order (audit institutionnel, section 5 -- défense en
profondeur, second filet indépendant de la vérification par cycle dans
src/demo_trader.py::run_demo_trading_loop). Fichier DÉDIÉ (pas
tests/test_autonomous.py), comme demandé.

Critères de test explicitement demandés :
  - halted + ouverture -> refusé
  - halted + fermeture -> passe
  - non halted -> comportement inchangé
"""
from __future__ import annotations
import types

import src.account_guard as account_guard
from src.mt5_connector import MT5Connector


def _make_fake_mt5(equity: float, bid: float, ask: float, contract_size: float,
                     requests: list, existing_position=None):
    """`existing_position` : None (à plat) ou un objet position factice
    (type/volume/ticket) pour simuler une position déjà ouverte."""
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    account = types.SimpleNamespace(trade_mode=0, equity=equity)
    fake_mt5.account_info = lambda: account
    positions = [existing_position] if existing_position is not None else []
    fake_mt5.positions_get = lambda symbol=None: positions
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=contract_size, volume_step=0.01, volume_min=0.01,
        volume_max=100.0, digits=2, filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=bid, ask=ask, time=1_700_000_000)

    def fake_order_send(request):
        requests.append(request)
        return types.SimpleNamespace(retcode=10009, price=request.get("price"))
    fake_mt5.order_send = fake_order_send
    return fake_mt5


def _make_position(direction: int, volume: float, ticket: int = 1):
    return types.SimpleNamespace(
        ticket=ticket, type=(0 if direction == 1 else 1), volume=volume,
        price_open=2000.0, sl=1900.0, profit=0.0, comment=None,
    )


def test_halted_blocks_new_opening(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    account_guard._write_state({"halted": True, "halted_reason": "drawdown total"})

    requests = []
    fake_mt5 = _make_fake_mt5(equity=10000.0, bid=2000.0, ask=2000.0, contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(1.0, stop_pct=0.01)  # ouverture depuis plat

    assert len(requests) == 0, "aucun ordre ne doit être envoyé à MT5 quand le compte est halted"


def test_halted_allows_closing_existing_position(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    account_guard._write_state({"halted": True, "halted_reason": "drawdown total"})

    requests = []
    existing = _make_position(direction=1, volume=0.10)
    fake_mt5 = _make_fake_mt5(equity=10000.0, bid=2000.0, ask=2000.0, contract_size=100.0,
                                requests=requests, existing_position=existing)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(0.0)  # fermeture -- cible plate

    assert len(requests) == 1, "la fermeture doit passer MÊME quand le compte est halted"
    assert requests[0]["type"] == fake_mt5.ORDER_TYPE_SELL  # clôture d'un long = vente


def test_halted_blocks_increase_via_reversal(tmp_path, monkeypatch):
    """Un retournement (long -> short) repasse par la branche OUVERTURE
    (fermeture de l'ancien PUIS ouverture du nouveau, voir send_order) --
    la fermeture de l'ancien doit passer, mais la RÉOUVERTURE dans le sens
    opposé doit être refusée si le compte est halted."""
    monkeypatch.chdir(tmp_path)
    account_guard._write_state({"halted": True, "halted_reason": "drawdown total"})

    requests = []
    existing = _make_position(direction=1, volume=0.10)
    fake_mt5 = _make_fake_mt5(equity=10000.0, bid=2000.0, ask=2000.0, contract_size=100.0,
                                requests=requests, existing_position=existing)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(-1.0, stop_pct=0.01)  # retournement long -> short

    assert len(requests) == 0, \
        "un retournement (fermeture+réouverture) doit être ENTIÈREMENT refusé quand halted " \
        "(la réouverture ne doit jamais être envoyée)"


def test_not_halted_behavior_unchanged(tmp_path, monkeypatch):
    """Aucun état halted (comportement d'origine) -- l'ouverture doit passer normalement."""
    monkeypatch.chdir(tmp_path)
    # pas d'appel à account_guard._write_state -- aucun fichier d'état, is_halted() doit renvoyer False

    requests = []
    fake_mt5 = _make_fake_mt5(equity=10000.0, bid=2000.0, ask=2000.0, contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(1.0, stop_pct=0.01)

    assert len(requests) == 1, "sans halt, l'ouverture doit être envoyée normalement (comportement d'origine)"


def test_halted_blocks_even_in_dry_run(tmp_path, monkeypatch):
    """Le refus s'applique aussi en dry-run (placé AVANT la branche dry-run
    dans send_order) -- cohérent/observable même sans compte réel engagé."""
    monkeypatch.chdir(tmp_path)
    account_guard._write_state({"halted": True, "halted_reason": "perte quotidienne"})

    requests = []
    fake_mt5 = _make_fake_mt5(equity=10000.0, bid=2000.0, ask=2000.0, contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": True, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(1.0, stop_pct=0.01)

    assert len(requests) == 0

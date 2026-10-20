"""Tests pour les ajouts d'infrastructure live de src/mt5_connector.py (audit
institutionnel, section 5/6) qui ne sont pas déjà couverts par les tests
existants de tests/test_autonomous.py : routage asynchrone (send_order_async),
heartbeat (_mark_success/seconds_since_last_success), latence réseau
(measure_round_trip_ms), et journal d'exécution/slippage (_log_execution)."""
from __future__ import annotations
import json
import types

from src.mt5_connector import MT5Connector, EXECUTION_LOG_PATH, LATENCY_CACHE_PATH


def _make_fake_mt5_with_account(equity: float, bid: float, ask: float, contract_size: float,
                                  requests: list, retcode: int = 10009, fill_price: float | None = None):
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
    fake_mt5.positions_get = lambda symbol=None: []
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=contract_size, volume_step=0.01, volume_min=0.01,
        volume_max=100.0, digits=2, filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=bid, ask=ask, time=1_700_000_000)

    def fake_order_send(request):
        requests.append(request)
        actual_fill = fill_price if fill_price is not None else request.get("price")
        return types.SimpleNamespace(retcode=retcode, price=actual_fill)
    fake_mt5.order_send = fake_order_send
    return fake_mt5


def test_send_order_async_returns_future_matching_sync_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    requests = []
    fake_mt5 = _make_fake_mt5_with_account(equity=10000.0, bid=2000.0, ask=2000.0,
                                             contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    future = conn.send_order_async(1.0, stop_pct=0.01)
    result = future.result(timeout=5)
    assert result is None  # send_order ne retourne rien explicitement (comportement d'origine)
    assert len(requests) == 1, "l'ordre doit avoir été réellement envoyé via le worker dédié"


def test_heartbeat_updated_on_successful_calls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_mt5 = _make_fake_mt5_with_account(equity=10000.0, bid=2000.0, ask=2000.0,
                                             contract_size=100.0, requests=[])
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": True, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    stale_before = conn.seconds_since_last_success()
    assert stale_before >= 0
    equity = conn.get_account_equity()
    assert equity == 10000.0
    assert conn.seconds_since_last_success() < stale_before + 1.0, \
        "get_account_equity() réussi doit rafraîchir le heartbeat"


def test_measure_round_trip_ms_returns_positive_value_and_writes_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_mt5 = _make_fake_mt5_with_account(equity=10000.0, bid=2000.0, ask=2000.0,
                                             contract_size=100.0, requests=[])
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": True, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    elapsed = conn.measure_round_trip_ms()
    assert elapsed is not None and elapsed >= 0.0
    with open(LATENCY_CACHE_PATH, encoding="utf-8") as f:
        cached = json.load(f)
    assert cached["symbol"] == "XAUUSD"
    assert "round_trip_ms" in cached


def test_measure_round_trip_ms_returns_none_on_failure_never_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": True, "allow_real_account": False}}
    conn = MT5Connector(cfg)

    class BrokenMT5:
        def symbol_info_tick(self, symbol):
            raise RuntimeError("connexion perdue")
    conn._mt5 = BrokenMT5()

    assert conn.measure_round_trip_ms() is None


def test_log_execution_writes_structured_record_with_slippage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    requests = []
    # prix demandé (ask=2000.0) vs rempli (2000.5) -- slippage positif attendu
    fake_mt5 = _make_fake_mt5_with_account(equity=10000.0, bid=1999.5, ask=2000.0,
                                             contract_size=100.0, requests=requests, fill_price=2000.5)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(1.0, stop_pct=0.01, style="M15", generation=42)

    with open(EXECUTION_LOG_PATH, encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == 1
    record = lines[0]
    assert record["style"] == "M15"
    assert record["requested_price"] == 2000.0
    assert record["filled_price"] == 2000.5
    assert abs(record["slippage"] - 0.5) < 1e-9
    assert record["retcode"] == 10009


def test_log_execution_never_written_in_dry_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_mt5 = _make_fake_mt5_with_account(equity=10000.0, bid=2000.0, ask=2000.0,
                                             contract_size=100.0, requests=[])
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": True, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(1.0, stop_pct=0.01, style="M15")
    import os
    assert not os.path.exists(EXECUTION_LOG_PATH), \
        "aucun ordre réel envoyé en dry-run -- rien à journaliser"

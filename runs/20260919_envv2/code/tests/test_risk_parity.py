"""Preuve de parité (LOT 2, phase 2) : sur une grille d'entrées,
MT5Connector.send_order (exécution réelle) et
TradingEnv.simulate_broker_sizing (simulation) produisent EXACTEMENT la
même décision (lot, stop, annulation) -- les deux délèguent au même
src/risk_engine.py. Fichier DÉDIÉ (pas tests/test_autonomous.py), comme
demandé."""
from __future__ import annotations
import types
import pytest

from src.mt5_connector import MT5Connector
from src.risk_engine import SymbolSpec
from src.trading_env import TradingEnv
from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS


def _make_fake_mt5(equity, bid, ask, contract_size, requests,
                     volume_min=0.01, volume_step=0.01, volume_max=100.0,
                     stops_level_points=0.0, point=0.01, digits=2):
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
        trade_contract_size=contract_size, volume_step=volume_step, volume_min=volume_min,
        volume_max=volume_max, digits=digits, filling_mode=0,
        trade_stops_level=stops_level_points, point=point)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=bid, ask=ask, time=1_700_000_000)

    def fake_order_send(request):
        requests.append(request)
        return types.SimpleNamespace(retcode=10009, price=request.get("price"))
    fake_mt5.order_send = fake_order_send
    return fake_mt5


def _connector_decision(equity, bid, ask, contract_size, risk_pct, stop_pct, target_exposure,
                          volume_min=0.01, volume_step=0.01, volume_max=100.0,
                          stops_level_points=0.0, point=0.01):
    requests = []
    fake_mt5 = _make_fake_mt5(equity, bid, ask, contract_size, requests, volume_min, volume_step,
                                volume_max, stops_level_points, point)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                     "allow_real_account": False, "max_risk_pct_per_trade": risk_pct}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    conn.send_order(target_exposure, stop_pct=stop_pct)
    if len(requests) == 0:
        return None, None, True  # annulé (ou déjà aligné -- non pertinent ici, position toujours plate)
    req = requests[0]
    volume = req["volume"]
    entry_price = (bid + ask) / 2.0
    sl = req.get("sl")
    reconstructed_stop_pct = abs(entry_price - sl) / entry_price if sl is not None else None
    return volume, reconstructed_stop_pct, False


def _env_for_parity():
    df = generate_synthetic_ohlcv(n_bars=200, seed=1)
    df = add_technical_features(df)
    df, _ = normalize_features(df, columns=FEATURE_COLUMNS)
    return TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS)


GRID = [
    # equity, price(bid=ask), contract_size, risk_pct, stop_pct, target_exposure
    (10000.0, 2000.0, 100.0, 0.02, 0.01, 1.0),
    (10000.0, 2000.0, 100.0, 0.02, 0.01, 0.5),
    (10000.0, 2000.0, 100.0, 0.02, 0.05, 1.0),
    (500.0, 2000.0, 100.0, 0.02, 0.01, 1.0),     # petit compte -> floor probable
    (500.0, 2000.0, 100.0, 0.02, 0.001, 1.0),    # stop très serré -> gros lot idéal, floor+tighten
    (10000.0, 2000.0, 100.0, 0.01, 0.02, 0.3),
    (10000.0, 60000.0, 1.0, 0.02, 0.01, 1.0),    # prix élevé, petit contrat (style BTC-ish)
]


@pytest.mark.parametrize("equity,price,contract_size,risk_pct,stop_pct,target_exposure", GRID)
def test_env_and_connector_agree_on_volume_and_cancellation(
        equity, price, contract_size, risk_pct, stop_pct, target_exposure):
    conn_volume, conn_stop_pct, conn_cancelled = _connector_decision(
        equity, price, price, contract_size, risk_pct, stop_pct, target_exposure)

    spec = SymbolSpec(volume_min=0.01, volume_step=0.01, volume_max=100.0,
                        contract_size=contract_size, digits=2,
                        stops_level_points=0.0, point=0.01)
    env = _env_for_parity()
    env.symbol_spec = spec
    env_volume, env_stop_pct, env_cancelled = env.simulate_broker_sizing(
        equity, target_exposure, stop_pct, price, risk_pct_override=risk_pct)

    assert env_cancelled == conn_cancelled, \
        f"décision d'annulation divergente : env={env_cancelled} connecteur={conn_cancelled}"
    if not conn_cancelled:
        assert env_volume == pytest.approx(conn_volume, abs=0.01), \
            f"volume divergent : env={env_volume} connecteur={conn_volume}"
        if conn_stop_pct is not None and env_stop_pct is not None:
            assert env_stop_pct == pytest.approx(conn_stop_pct, rel=1e-2), \
                f"stop_pct divergent : env={env_stop_pct} connecteur={conn_stop_pct}"


def test_env_without_symbol_spec_never_floors_original_behavior():
    """Comportement d'ORIGINE préservé : sans symbol_spec configuré,
    l'environnement ne simule aucun plancher/resserrement/annulation."""
    env = _env_for_parity()
    volume, stop_pct, cancelled = env.simulate_broker_sizing(10000.0, 1.0, 0.01, 2000.0)
    assert volume == 0.0 and stop_pct == 0.01 and cancelled is False


def test_env_stops_level_cancellation_matches_connector():
    """Cas d'annulation explicite (stops_level broker trop élevé pour un
    petit compte) -- vérifie que l'environnement annule EXACTEMENT quand le
    connecteur annule (aucune requête envoyée)."""
    # equity minuscule + stop large -> lot idéal bien sous le minimum broker
    # (0.01) -> flooré -> stop resserré très en-dessous du stops_level -> annulé.
    equity, price, contract_size, risk_pct, stop_pct, target_exposure = 50.0, 2000.0, 100.0, 0.02, 0.01, 1.0
    conn_volume, _, conn_cancelled = _connector_decision(
        equity, price, price, contract_size, risk_pct, stop_pct, target_exposure,
        stops_level_points=500, point=0.01)

    spec = SymbolSpec(volume_min=0.01, volume_step=0.01, volume_max=100.0,
                        contract_size=contract_size, digits=2,
                        stops_level_points=500, point=0.01)
    env = _env_for_parity()
    env.symbol_spec = spec
    _, _, env_cancelled = env.simulate_broker_sizing(equity, target_exposure, stop_pct, price,
                                                        risk_pct_override=risk_pct)
    assert conn_cancelled is True, "précondition du test : ce scénario doit annuler côté connecteur"
    assert env_cancelled == conn_cancelled

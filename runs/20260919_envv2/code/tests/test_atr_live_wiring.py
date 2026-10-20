"""LOT 2, phase 3 : corrige un écart entraînement/live réel -- demo_trader.py
décodait auparavant TOUJOURS le bucket choisi par l'agent via la table
STATIQUE en %, même quand l'entraînement utilisait des buckets ATR
dynamiques (actifs par défaut, config/autonomous.yaml: atr_stop_loss: true).
Vérifie : (1) demo_trader transmet le MULTIPLE choisi (pas une distance déjà
résolue), (2) MT5Connector résout ce multiple via risk_engine (même formule
que TradingEnv), (3) aucune ouverture si l'ATR est requis mais indisponible,
sans jamais bloquer une fermeture. Fichier DÉDIÉ (pas tests/test_autonomous.py),
comme demandé."""
from __future__ import annotations
import types
import json
import pytest

from src.data_loader import generate_synthetic_ohlcv
from src.mt5_connector import MT5Connector
from src.risk_engine import atr_stop_distance_pct, ATR_STOP_PCT_FLOOR, ATR_STOP_PCT_CEILING


def _make_fake_mt5(equity, bid, ask, contract_size, requests, existing_position=None):
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
        volume_max=100.0, digits=2, filling_mode=0, trade_stops_level=0, point=0.01)
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


def _connector(equity=10000.0, bid=2000.0, ask=2000.0, contract_size=100.0,
                requests=None, existing_position=None):
    requests = requests if requests is not None else []
    fake_mt5 = _make_fake_mt5(equity, bid, ask, contract_size, requests, existing_position)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                     "allow_real_account": False, "max_risk_pct_per_trade": 0.02}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    return conn, requests


def test_send_order_resolves_atr_multiplier_to_stop_pct_via_risk_engine():
    conn, requests = _connector()
    conn.send_order(1.0, atr_multiplier=2.0, atr_price_units=5.0)
    assert len(requests) == 1
    expected_stop_pct = atr_stop_distance_pct(5.0, 2.0, 2000.0, ATR_STOP_PCT_FLOOR, ATR_STOP_PCT_CEILING)
    expected_sl = round(2000.0 * (1 - expected_stop_pct), 2)
    assert requests[0]["sl"] == pytest.approx(expected_sl, abs=0.01)


def test_send_order_explicit_stop_pct_ignored_when_atr_multiplier_given():
    """Source unique : un multiple ATR fourni prend TOUJOURS la main, même
    si un stop_pct explicite est aussi passé (jamais les deux mélangés)."""
    conn, requests = _connector()
    conn.send_order(1.0, stop_pct=0.5, atr_multiplier=0.5, atr_price_units=5.0)
    assert len(requests) == 1
    tiny_expected_pct = atr_stop_distance_pct(5.0, 0.5, 2000.0, ATR_STOP_PCT_FLOOR, ATR_STOP_PCT_CEILING)
    tiny_expected_sl = round(2000.0 * (1 - tiny_expected_pct), 2)
    assert requests[0]["sl"] == pytest.approx(tiny_expected_sl, abs=0.01), \
        "le stop envoyé doit venir de l'ATR (petit), pas du stop_pct=0.5 explicite (énorme)"


def test_send_order_refuses_opening_when_atr_required_but_unavailable():
    conn, requests = _connector()
    conn.send_order(1.0, atr_multiplier=2.0, atr_price_units=None)
    assert len(requests) == 0, "aucune ouverture ne doit partir si l'ATR requis est indisponible"


def test_send_order_atr_unavailable_never_blocks_closing():
    existing = _make_position(direction=1, volume=0.10)
    conn, requests = _connector(existing_position=existing)
    conn.send_order(0.0, atr_multiplier=2.0, atr_price_units=None)
    assert len(requests) == 1, "une fermeture ne doit JAMAIS être bloquée, même si l'ATR est indisponible"
    assert requests[0]["type"] == conn._mt5.ORDER_TYPE_SELL


def test_send_order_without_atr_multiplier_behaves_as_before():
    """Comportement d'ORIGINE préservé : sans atr_multiplier (None, défaut),
    stop_pct explicite est utilisé tel quel -- aucun changement pour les
    appelants qui ne connaissent pas encore ce mécanisme."""
    conn, requests = _connector()
    conn.send_order(1.0, stop_pct=0.01)
    assert len(requests) == 1
    expected_sl = round(2000.0 * (1 - 0.01), 2)
    assert requests[0]["sl"] == pytest.approx(expected_sl, abs=0.01)


def test_demo_trader_forwards_atr_multiplier_end_to_end(tmp_path, monkeypatch):
    """Câblage complet, à travers la VRAIE boucle de démo : quand le stop ATR
    est actif (défaut), decide() doit transmettre un MULTIPLE (pas un
    stop_pct déjà résolu en %) jusqu'à send_order."""
    monkeypatch.chdir(tmp_path)
    from src.multi_timeframe import fuse_mtf_frames
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
    from src.continuous_trainer import DEMO_DIR, DEMO_MODEL, DEMO_META, DEMO_STATS
    from src.demo_trader import run_demo_trading_loop

    class FakeMTFConnector:
        def __init__(self):
            self.orders = []  # liste de dicts (target, stop_pct, atr_multiplier, atr_price_units)
        def connect(self):
            pass
        def is_demo_account(self):
            return True
        def close_orphan_positions(self, recognized_styles):
            return []
        def get_open_positions_by_style(self, recognized_styles):
            return {}
        def get_latest_bars(self, timeframe, n_bars):
            seed = {"H1": 1, "H4": 2, "D1": 3}.get(timeframe, 0)
            return generate_synthetic_ohlcv(n_bars=n_bars, seed=seed)
        def send_order(self, target_position, stop_pct=None, atr_multiplier=None,
                        atr_price_units=None, **kwargs):
            self.orders.append({"target": target_position, "stop_pct": stop_pct,
                                  "atr_multiplier": atr_multiplier, "atr_price_units": atr_price_units})

    buckets = [0.02]
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       learn_stop_loss=True, stop_loss_buckets=buckets, atr_stop_loss=True)

    dfs = {"H1": generate_synthetic_ohlcv(n_bars=1000, seed=1),
           "H4": generate_synthetic_ohlcv(n_bars=500, seed=2),
           "D1": generate_synthetic_ohlcv(n_bars=500, seed=3)}
    df, mtf_cols = fuse_mtf_frames(dfs, "H1", ["H4", "D1"])
    df = add_technical_features(df)
    df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]
    all_cols = FEATURE_COLUMNS + mtf_cols
    df_norm, stats = normalize_features(df, columns=all_cols)

    env = TradingEnv(df_norm, feature_columns=all_cols, **env_kwargs)
    agent = TradingAgent(env, {"n_steps": 64, "batch_size": 16})
    agent.learn(64)

    import os
    os.makedirs(DEMO_DIR, exist_ok=True)
    agent.save(DEMO_MODEL)
    from src.trading_env import ENV_VERSION
    with open(DEMO_META, "w") as f:
        json.dump({
            "generation": 0, "score": 5.0, "updated_at": 123.0,
            "primary_timeframe": "H1", "context_timeframes": ["H4", "D1"],
            "feature_columns": all_cols, "env_version": ENV_VERSION,
        }, f)
    with open(DEMO_STATS, "w") as f:
        json.dump({k: list(v) for k, v in stats.items()}, f)

    cfg = {"live": {"dry_run": True, "poll_seconds": 0, "allow_real_account": False},
           "fundamental": {"enabled": False}, "data": {"n_bars_context": 500},
           "market_hours": {"enabled": False}}
    fake = FakeMTFConnector()
    run_demo_trading_loop(cfg, env_kwargs, connector=fake, max_iterations=2)

    assert len(fake.orders) == 2
    for order in fake.orders:
        if order["target"] == 0:
            assert order["atr_multiplier"] is None and order["stop_pct"] is None
        else:
            assert order["atr_multiplier"] is not None, \
                "avec atr_stop_loss actif, decide() doit transmettre un MULTIPLE, pas un stop_pct déjà résolu"
            from src.trading_env import TradingEnv as _TE
            assert order["atr_multiplier"] in _TE.ATR_STOP_MULTIPLIERS_BY_STYLE["H1"], \
                "le multiple transmis doit venir d'ATR_STOP_MULTIPLIERS_BY_STYLE"
            assert order["stop_pct"] is None, "stop_pct ne doit PAS être pré-résolu quand l'ATR est actif"
            assert order["atr_price_units"] is not None, \
                "l'ATR live construit par _build_live_dataframe doit être disponible ici"

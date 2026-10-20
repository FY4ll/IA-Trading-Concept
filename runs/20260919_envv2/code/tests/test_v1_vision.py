"""Tests de la vision "Autonomous Trader V1" intégrée à Run A le 05/10/2026 : régime de marché,
filtre de marché (news/spread/données/régime), journal de décision traçable, exécution vérifiée,
synchronisation des trades, rollback, recherche, diagnostic, mesures prop firm, porte lockbox."""
from __future__ import annotations
import json
import os
import types
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from src.data_loader import generate_synthetic_ohlcv


# --- régime de marché ----------------------------------------------------------------------------------
def _ohlc(close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999, "close": close})


def test_regime_trend_up_and_range():
    from src.market_regime import detect_regime, TREND_UP, RANGE, TREND_DOWN
    up = _ohlc(np.linspace(100, 130, 600))
    assert detect_regime(up)["regime"] == TREND_UP
    down = _ohlc(np.linspace(130, 100, 600))
    assert detect_regime(down)["regime"] == TREND_DOWN
    rng = np.random.default_rng(0)
    noise = _ohlc(100 + np.cumsum(rng.choice([-1, 1], 600)) * 0.0 + rng.normal(0, 0.5, 600))
    assert detect_regime(noise)["regime"] == RANGE


def test_regime_volatility_extreme_on_spike():
    from src.market_regime import detect_regime
    df = _ohlc(np.full(600, 100.0))
    df["atr_14"] = 1.0
    df.loc[len(df) - 1, "atr_14"] = 10.0
    assert detect_regime(df)["vol_class"] == "EXTREME"


def test_regime_series_has_no_lookahead():
    from src.market_regime import regime_series
    df = generate_synthetic_ohlcv(n_bars=900, seed=4)
    full = regime_series(df)
    part = regime_series(df.iloc[:700])
    assert (full["regime"].iloc[:700].to_numpy() == part["regime"].to_numpy()).all()
    assert (full["vol_class"].iloc[:700].to_numpy() == part["vol_class"].to_numpy()).all()


def test_swing_structure_bullish():
    from src.market_regime import swing_structure
    x = np.arange(200)
    price = 100 + 0.1 * x + 3 * np.sin(x / 5)
    out = swing_structure(price + 0.5, price - 0.5, k=3)
    assert out["highs"] == "HH" and out["lows"] == "HL" and out["structure"] == "BULLISH"


# --- filtre de marché ----------------------------------------------------------------------------------
def _calendar(tmp_path, events):
    from src.market_gate import NewsCalendar
    return NewsCalendar(cache_path=str(tmp_path / "cal.json"), fetcher=lambda: events)


def test_news_blackout_window(tmp_path):
    from src.market_gate import find_blackout
    t = datetime(2026, 10, 9, 12, 30, tzinfo=timezone.utc)
    ev = [{"time_utc": t.isoformat(), "country": "USD", "impact": "High", "title": "NFP"},
          {"time_utc": t.isoformat(), "country": "JPY", "impact": "High", "title": "BOJ"}]
    assert find_blackout(ev, t - timedelta(minutes=29), ["USD"], ["High"], 30, 15)["title"] == "NFP"
    assert find_blackout(ev, t + timedelta(minutes=14), ["USD"], ["High"], 30, 15) is not None
    assert find_blackout(ev, t + timedelta(minutes=16), ["USD"], ["High"], 30, 15) is None
    assert find_blackout(ev, t - timedelta(minutes=31), ["USD"], ["High"], 30, 15) is None


def test_news_calendar_unavailable_is_explicit(tmp_path):
    from src.market_gate import NewsCalendar, NEWS_UNAVAILABLE, NEWS_OK

    def boom():
        raise ConnectionError("hors ligne")
    cal = NewsCalendar(cache_path=str(tmp_path / "c.json"), fetcher=boom)
    cal.refresh_if_needed()
    assert cal.status() == NEWS_UNAVAILABLE, "pas de données ne doit jamais signifier 'pas de news'"
    ok = _calendar(tmp_path, [{"date": "2026-10-09T08:30:00-04:00", "country": "USD", "impact": "High", "title": "NFP"}])
    ok.refresh_if_needed()
    assert ok.status() == NEWS_OK
    assert ok.events()[0]["time_utc"].startswith("2026-10-09T12:30")


class _GateConn:
    def __init__(self, spread_pct=0.0001, active=True):
        self.spread_pct, self.active = spread_pct, active

    def get_current_spread_pct(self):
        return self.spread_pct

    def is_symbol_active(self, staleness_minutes=10):
        return self.active


def _gate_cfg(**kw):
    g = {"enabled": True, "news": {"enabled": False}, "max_spread_atr_ratio": 0.15, "stale_minutes": 10}
    g.update(kw)
    return {"live": {"market_gate": g}}


def test_market_gate_spread_stale_and_regime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.market_gate import MarketGate
    df = pd.DataFrame({"close": [2000.0], "atr_14": [10.0]})
    gate = MarketGate(_gate_cfg())
    assert gate.check_opening(df, _GateConn(spread_pct=0.0001), {"vol_class": "NORMAL"}) == []
    assert gate.check_opening(df, _GateConn(spread_pct=0.002), {})[0].startswith("spread_high")  # 4$ = 0.4 ATR
    assert gate.check_opening(df, _GateConn(active=False), {})[0].startswith("data_stale")
    gate2 = MarketGate(_gate_cfg(block_vol_classes=["EXTREME"]))
    assert gate2.check_opening(df, _GateConn(), {"vol_class": "EXTREME"}) == ["regime_filter:vol=EXTREME"]


def test_market_gate_uses_research_adopted_filter_per_style(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.market_gate import MarketGate
    from src.research_engine import adopt_filter
    adopt_filter("H1", {"block_vol_classes": ["HIGH"]}, "exp1")
    df = pd.DataFrame({"close": [2000.0], "atr_14": [10.0]})
    gate = MarketGate(_gate_cfg())
    assert gate.check_opening(df, _GateConn(), {"vol_class": "HIGH"}, style="H1") == ["regime_filter:vol=HIGH"]
    assert gate.check_opening(df, _GateConn(), {"vol_class": "HIGH"}, style="H1T") == []


def test_market_gate_news_unavailable_policy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.market_gate import MarketGate, NewsCalendar

    def boom():
        raise ConnectionError()
    cal = NewsCalendar(cache_path=str(tmp_path / "c.json"), fetcher=boom)
    allow = MarketGate(_gate_cfg(news={"enabled": True, "on_unavailable": "allow"}), calendar=cal)
    block = MarketGate(_gate_cfg(news={"enabled": True, "on_unavailable": "block"}), calendar=cal)
    assert allow.check_opening(None, None, {}) == []
    assert block.check_opening(None, None, {}) == ["news_data_unavailable"]
    assert allow.news_context()["news_status"] == "NEWS_DATA_UNAVAILABLE"


# --- journal de décision -------------------------------------------------------------------------------
def test_classify_action_and_wait_reason():
    from src.decision_journal import classify_action, wait_reason
    assert classify_action(0, 0) == "WAIT"
    assert classify_action(0, 1) == "OPEN_LONG" and classify_action(0, -0.5) == "OPEN_SHORT"
    assert classify_action(1, 1) == "HOLD" and classify_action(1, 0) == "CLOSE" and classify_action(-1, 1) == "REVERSE"
    assert wait_reason("WAIT", 1.0, ["news_blackout:USD NFP"], None) == "news_blackout:USD NFP"
    assert wait_reason("WAIT", 0.0, [], {"long": 0.2, "short": 0.1, "flat": 0.7}).startswith("model_flat")
    assert wait_reason("CLOSE", 0.0, [], None) == "model_exit"
    assert wait_reason("OPEN_LONG", 1.0, [], None) is None


def test_journal_roundtrip_and_stats(tmp_path):
    from src.decision_journal import DecisionJournal, summarize_r
    j = DecisionJournal(str(tmp_path / "j.sqlite"))
    did = j.record_decision({"style": "H1", "generation": 5, "action": "WAIT", "wait_reason": "cooldown",
                             "block_reasons": ["cooldown"], "final_target": 0.0})
    j.record_execution({"decision_id": did, "style": "H1", "leg": "open", "position_ticket": 77, "risk_usd": 100.0})
    assert j.decision(did)["wait_reason"] == "cooldown"
    assert j.opening_execution(77)["decision_id"] == did
    assert j.wait_reason_stats("2000-01-01")[0]["reason"] == "cooldown"
    s = summarize_r([{"r_multiple": r, "net_profit": r * 100} for r in (1, -1, 2, -1, 1)])
    assert s["n_r"] == 5 and s["avg_r"] == pytest.approx(0.4) and s["profit_factor"] == pytest.approx(2.0)


# --- exécution vérifiée et trades clôturés ---------------------------------------------------------------
def _fake_mt5_with_positions():
    mt5 = types.SimpleNamespace(ACCOUNT_TRADE_MODE_DEMO=0, TRADE_ACTION_DEAL=1, ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1,
                                ORDER_FILLING_FOK=0, ORDER_FILLING_IOC=1, ORDER_FILLING_RETURN=2,
                                TRADE_RETCODE_DONE=10009, DEAL_ENTRY_IN=0, DEAL_REASON_SL=4, DEAL_REASON_EXPERT=3)
    account = types.SimpleNamespace(trade_mode=0, equity=10000.0)
    mt5.account_info = lambda: account
    positions = []
    mt5.positions_get = lambda symbol=None: list(positions)
    mt5.symbol_info = lambda s: types.SimpleNamespace(trade_contract_size=100.0, volume_step=0.01, volume_min=0.01,
                                                      volume_max=100.0, digits=2, filling_mode=0,
                                                      trade_stops_level=0, point=0.01)
    mt5.symbol_info_tick = lambda s: types.SimpleNamespace(bid=2000.0, ask=2000.0, time=1_700_000_000)

    def order_send(req):
        if "position" not in req:
            positions.append(types.SimpleNamespace(ticket=555, type=req["type"], volume=req["volume"] / 2,
                                                   price_open=2000.5, sl=req.get("sl", 0.0), tp=req.get("tp", 0.0),
                                                   profit=0.0, comment=req.get("comment"), time=1, time_msc=1))
        return types.SimpleNamespace(retcode=10009, price=2000.5, order=555, volume=req["volume"] / 2)
    mt5.order_send = order_send
    return mt5


def test_send_order_reports_verified_partial_fill(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector
    conn = MT5Connector({"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                                  "allow_real_account": False, "max_risk_pct_per_trade": 0.02}})
    conn._mt5 = _fake_mt5_with_positions()
    conn.send_order(1.0, stop_pct=0.01, style="H1", generation=3)
    rep = conn.last_order_report
    assert rep["action"] == "sent"
    leg = rep["legs"][-1]
    assert leg["verified"] == 1 and leg["position_ticket"] == 555
    assert leg["price_filled"] == 2000.5 and leg["adverse_slippage"] == pytest.approx(0.5)
    assert "partiel" in leg["note"], "un remplissage partiel doit être détecté sur l'état MT5 réel"
    assert leg["risk_usd"] == pytest.approx(abs(2000.5 - leg["sl_actual"]) * leg["volume_filled"] * 100.0)
    conn.send_order(1.0, stop_pct=0.01, style="H1", generation=3)
    assert conn.last_order_report["action"] in ("aligned", "sent")


def test_get_closed_positions_and_trade_sync(tmp_path):
    from src.mt5_connector import MT5Connector
    from src.constants import MAGIC_NUMBER
    from src.decision_journal import DecisionJournal
    from src.trade_sync import sync_closed_trades
    conn = MT5Connector({"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False}})
    mt5 = _fake_mt5_with_positions()
    D = lambda **k: types.SimpleNamespace(magic=MAGIC_NUMBER, symbol="XAUUSD", commission=-1.0, swap=0.0, **k)
    T = 1_760_000_000
    mt5.history_deals_get = lambda a, b: [
        D(position_id=9, entry=0, type=0, volume=0.1, price=2000.0, time=T + 1000, time_msc=1000, profit=0.0,
          comment="H1 gen:7", reason=3),
        D(position_id=9, entry=1, type=1, volume=0.1, price=2020.0, time=T + 5000, time_msc=5000, profit=200.0,
          comment="", reason=3)]
    mt5.history_orders_get = lambda position=None: [types.SimpleNamespace(sl=1990.0, tp=0.0)]
    mt5.TIMEFRAME_M5 = 5
    mt5.copy_rates_range = lambda *a: np.array(
        [(T + 900, 2005.0, 1995.0), (T + 1200, 2030.0, 1998.0), (T + 6000, 2100.0, 1900.0)],
        dtype=[("time", "i8"), ("high", "f8"), ("low", "f8")])
    conn._mt5 = mt5
    closed = conn.get_closed_positions(0)
    assert closed[0]["style"] == "H1" and closed[0]["generation"] == 7 and closed[0]["sl"] == 1990.0
    j = DecisionJournal(str(tmp_path / "j.sqlite"))
    j.record_decision({"decision_id": "d1", "style": "H1", "regime": "TREND_UP", "vol_class": "HIGH"})
    j.record_execution({"decision_id": "d1", "leg": "open", "position_ticket": 9, "risk_usd": 100.0})
    new = sync_closed_trades(j, conn)
    t = new[0]
    assert t["net_profit"] == pytest.approx(198.0) and t["r_multiple"] == pytest.approx(1.98)
    assert t["regime_at_entry"] == "TREND_UP" and t["mfe_r"] == pytest.approx(3.0) and t["mae_r"] == pytest.approx(0.5)
    assert sync_closed_trades(j, conn) == [], "un trade déjà synchronisé ne doit pas être dupliqué"


# --- rollback live -------------------------------------------------------------------------------------
def _losing_trades(j, style, gen, n, r=-1.0, start=0):
    for i in range(n):
        rr = r + (0.05 if i % 2 else -0.05)
        j.upsert_trade({"position_id": start + i, "style": style, "generation": gen, "r_multiple": rr,
                        "net_profit": rr * 100, "close_time": f"2026-10-05 {i % 24:02d}:00:00"})


def test_rollback_reduce_then_suspend_and_monotone(tmp_path):
    from src.decision_journal import DecisionJournal
    from src import live_rollback as lr
    j = DecisionJournal(str(tmp_path / "j.sqlite"))
    cfg = {"enabled": True}
    path = str(tmp_path / "rb.json")
    _losing_trades(j, "H1", 10, 16, r=-0.4)
    st = lr.update(j, "H1", 10, cfg, path=path)
    assert st["stage"] == "REDUCE" and st["risk_scale"] == 0.5
    _losing_trades(j, "H1", 10, 12, r=-0.4, start=100)
    st = lr.update(j, "H1", 10, cfg, path=path)
    assert st["stage"] == "SUSPEND", "aucune génération antérieure validée -> suspension"
    # une nouvelle génération repart de zéro
    assert lr.update(j, "H1", 11, cfg, path=path) is None


def test_rollback_to_previous_validated_generation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.decision_journal import DecisionJournal
    from src import live_rollback as lr
    d = tmp_path / "models" / "champion_H1T" / "history" / "gen_8"
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"passes_validation": True, "lockbox": {"sharpe": 0.6}}))
    (d / "agent.zip").write_text("x")
    (d / "norm_stats.json").write_text("{}")
    j = DecisionJournal(str(tmp_path / "j.sqlite"))
    _losing_trades(j, "H1T", 12, 30, r=-0.5)
    st = lr.update(j, "H1T", 12, {"enabled": True}, path=str(tmp_path / "rb.json"))
    assert st["stage"] == "ROLLBACK" and st["rollback_to"] == 8


# --- recherche -----------------------------------------------------------------------------------------
def test_research_hypotheses_dedup_and_adoption_guard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src import research_engine as re_
    diag = {"styles": {"H1": {"flags": ["inactivity"], "live_by_regime": {},
                              "live_by_vol_class": {"HIGH": {"n": 12, "avg_r": -0.6}}}}}
    new = re_.generate_hypotheses(diag)
    keys = {h["key"] for h in new}
    assert keys == {"H1:vol:HIGH", "H1:inactivity"}
    assert re_.generate_hypotheses(diag) == [], "pas de doublon d'hypothèse ouverte"
    with pytest.raises(ValueError):
        re_.adopt_filter("H1", {"max_risk_pct_per_trade": 0.05}, "x")  # la recherche ne touche jamais au risque
    base = {"pre_lockbox": {"sharpe": 1.0, "max_drawdown": 0.2}, "lockbox": {"sharpe": 0.6, "max_drawdown": 0.3}}
    good = {"pre_lockbox": {"sharpe": 1.1, "max_drawdown": 0.2}, "lockbox": {"sharpe": 0.7, "max_drawdown": 0.25}}
    bad = {"pre_lockbox": {"sharpe": 1.2, "max_drawdown": 0.2}, "lockbox": {"sharpe": 0.5, "max_drawdown": 0.25}}
    assert re_.filter_decision(base, good)[0] is True
    assert re_.filter_decision(base, bad)[0] is False, "doit s'améliorer sur les DEUX périodes"


# --- diagnostic, prop firm, porte lockbox ---------------------------------------------------------------
def test_psi_detects_shift():
    from src.diagnostics import psi
    rng = np.random.default_rng(1)
    a = rng.normal(0, 1, 5000)
    assert psi(a, rng.normal(0, 1, 2000)) < 0.05
    assert psi(a, rng.normal(1.5, 1, 2000)) > 0.25


def test_ftmo_simulate_extremes():
    from src.ftmo_metrics import simulate, prop_firm_summary
    assert simulate(np.full(100, 0.01), 0.10, n_sims=200)["pass"] == 1.0
    assert simulate(np.full(100, -0.06), 0.10, n_sims=200)["daily_breach"] == 1.0
    s = prop_firm_summary(np.r_[np.full(60, 0.004), -0.03], n_sims=200)
    assert s["worst_day"] == pytest.approx(-0.03) and s["days_below_2pct"] == 1


def test_gate_decision_prop_firm_and_baseline_criteria():
    from src.lockbox_gate import gate_decision
    m = {"sharpe": 0.6, "max_drawdown": 0.2, "total_return": 0.3, "n_trades": 300,
         "prop_firm": {"challenge_pass": 0.40}, "baselines": {"trend_sma20_50": {"sharpe": 0.8}}}
    ok, _ = gate_decision(m, {}, None)
    assert ok, "sans les nouvelles clés, la porte se comporte comme avant"
    ok, why = gate_decision(m, {"min_ftmo_challenge_pass": 0.5}, None)
    assert not ok and "Challenge FTMO" in why
    ok, why = gate_decision(m, {"ftmo_max_drop_vs_incumbent": 0.05}, {"sharpe": 0.5, "n_trades": 300,
                                                                       "prop_firm": {"challenge_pass": 0.5}})
    assert not ok and "champion actuel" in why
    ok, why = gate_decision(m, {"require_beat_trend_baseline": True}, None)
    assert not ok and "baseline" in why


def test_baseline_metrics_buy_hold():
    from src.lockbox_gate import baseline_metrics
    df = generate_synthetic_ohlcv(n_bars=3000, seed=2)
    b = baseline_metrics(df, 0.0002)
    assert b["buy_hold"]["total_return"] == pytest.approx(df["close"].iloc[-1] / df["close"].iloc[0] - 1)
    assert "trend_sma20_50" in b and "prop_firm" in b["buy_hold"]


# --- boucle live de bout en bout avec supervision ---------------------------------------------------------
def test_demo_loop_with_supervisor_blocks_and_journals(tmp_path, monkeypatch):
    """Boucle de démo réelle avec journal + filtre de marché actifs : un filtre qui bloque toutes les
    classes de volatilité transforme toute ouverture en WAIT journalisé avec sa raison, sans jamais
    envoyer d'ouverture."""
    monkeypatch.chdir(tmp_path)
    from src.multi_timeframe import fuse_mtf_frames
    from src.trading_env import TradingEnv, ENV_VERSION
    from src.agent import TradingAgent
    from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
    from src.continuous_trainer import DEMO_DIR, DEMO_MODEL, DEMO_META, DEMO_STATS
    from src.demo_trader import run_demo_trading_loop
    from src.decision_journal import DecisionJournal

    class FakeConn:
        def __init__(self):
            self.orders = []
            self.last_order_report = None
        def connect(self): pass
        def is_demo_account(self): return True
        def close_orphan_positions(self, recognized_styles): return []
        def get_open_positions_by_style(self, recognized_styles): return {}
        def get_latest_bars(self, timeframe, n_bars):
            return generate_synthetic_ohlcv(n_bars=n_bars, seed={"H1": 1, "H4": 2, "D1": 3}.get(timeframe, 0))
        def get_current_spread_pct(self): return 0.0001
        def is_symbol_active(self, staleness_minutes=10): return True
        def send_order(self, target, **kw):
            self.orders.append(target)
            self.last_order_report = {"action": "none", "legs": []}

    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                      reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    dfs = {"H1": generate_synthetic_ohlcv(n_bars=1000, seed=1), "H4": generate_synthetic_ohlcv(n_bars=500, seed=2),
           "D1": generate_synthetic_ohlcv(n_bars=500, seed=3)}
    df, mtf_cols = fuse_mtf_frames(dfs, "H1", ["H4", "D1"])
    df = add_technical_features(df)
    df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]
    cols = FEATURE_COLUMNS + mtf_cols
    dfn, stats = normalize_features(df, columns=cols)
    env = TradingEnv(dfn, feature_columns=cols, **env_kwargs)
    agent = TradingAgent(env, {"n_steps": 64, "batch_size": 16})
    agent.learn(64)
    os.makedirs(DEMO_DIR, exist_ok=True)
    agent.save(DEMO_MODEL)
    with open(DEMO_META, "w") as f:
        json.dump({"generation": 0, "score": 5.0, "updated_at": 1.0, "primary_timeframe": "H1",
                   "context_timeframes": ["H4", "D1"], "feature_columns": cols, "env_version": ENV_VERSION}, f)
    with open(DEMO_STATS, "w") as f:
        json.dump({k: list(v) for k, v in stats.items()}, f)

    all_classes = ["LOW", "NORMAL", "HIGH", "EXTREME", "UNKNOWN"]
    cfg = {"live": {"dry_run": True, "poll_seconds": 0, "allow_real_account": False,
                    "market_gate": {"enabled": True, "news": {"enabled": False}, "block_vol_classes": all_classes}},
           "journal": {"enabled": True, "db_path": "data/j.sqlite"},
           "fundamental": {"enabled": False}, "data": {"n_bars_context": 500}, "market_hours": {"enabled": False}}
    fake = FakeConn()
    run_demo_trading_loop(cfg, env_kwargs, connector=fake, max_iterations=3)

    assert all(o == 0 for o in fake.orders), "aucune ouverture ne doit passer le filtre"
    rows = DecisionJournal("data/j.sqlite").query("SELECT * FROM decisions")
    assert len(rows) == 3
    for r in rows:
        assert r["action"] == "WAIT" and r["regime"] is not None
        assert r["wait_reason"].startswith(("regime_filter", "model_flat"))
    if any(r["raw_target"] != 0 for r in rows):
        assert any(r["wait_reason"].startswith("regime_filter") for r in rows)


def test_pending_limit_order_sent_once_when_broker_answers_done(tmp_path, monkeypatch):
    """Bug réel du 06/10/2026 : le courtier répond 10009 (DONE) à un ordre limite bien posé ; l'ancien test
    « != PLACED » le renvoyait une 2e fois -> deux positions AUREX identiques."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector
    conn = MT5Connector({"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                                  "allow_real_account": False, "max_risk_pct_per_trade": 0.0025}})
    mt5 = _fake_mt5_with_positions()
    mt5.TRADE_ACTION_PENDING, mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT = 5, 2, 3
    mt5.ORDER_TIME_GTC, mt5.ORDER_TIME_SPECIFIED, mt5.TRADE_RETCODE_PLACED = 0, 2, 10008
    mt5.orders_get = lambda **k: []
    sent = []

    def order_send(req):
        sent.append(req)
        return types.SimpleNamespace(retcode=10009, price=0.0, order=900 + len(sent), volume=req["volume"])
    mt5.order_send = order_send
    conn._mt5 = mt5
    conn.send_order(1.0, stop_pct=0.01, style="AUREX", generation=253, limit_offset_price=3.0)
    pending = [r for r in sent if r.get("action") == 5]
    assert len(pending) == 1, "un ordre limite accepté ne doit jamais être renvoyé"
    assert conn.last_order_report["action"] == "limit_placed"


@pytest.mark.parametrize("keep", [True, False])
def test_open_position_keeps_its_size_when_budget_changes(tmp_path, monkeypatch, keep):
    """Une position ouverte dans le même sens n'est plus refermée/rouverte quand le budget change (option
    live.keep_open_position_size) ; sans l'option, comportement d'origine (redimensionnement)."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector
    conn = MT5Connector({"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                                  "allow_real_account": False, "max_risk_pct_per_trade": 0.02,
                                  "keep_open_position_size": keep}})
    mt5 = _fake_mt5_with_positions()
    sent = []
    held = types.SimpleNamespace(ticket=7, type=0, volume=0.50, price_open=1990.0, sl=1970.0, tp=0.0, profit=50.0,
                                 comment="H1 gen:3", time=1, time_msc=1, magic=20260911, symbol="XAUUSD")
    mt5.positions_get = lambda symbol=None, **k: [held]
    mt5.orders_get = lambda **k: []
    mt5.order_send = lambda req: sent.append(req) or types.SimpleNamespace(retcode=10009, price=2000.0, order=8,
                                                                          volume=req["volume"])
    conn._mt5 = mt5
    conn.send_order(1.0, stop_pct=0.01, style="H1", generation=3, risk_pct_override=0.0025)
    if keep:
        assert sent == [] and conn.last_order_report["action"] == "aligned"
    else:
        assert sent, "sans l'option, la position est redimensionnée (comportement d'origine)"

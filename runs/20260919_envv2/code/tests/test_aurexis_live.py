"""AUREXIS en direct « à blanc » (09/10/2026) : le compte fictif doit se comporter exactement comme le compte réel --
stops avant objectifs, frais, murs FTMO qui ferment tout, budget de risque cumulé, gestion du stop qui ne fait que se
resserrer, état qui survit d'un passage à l'autre."""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

from src.aurexis_live import PaperBook, decode, START_EQUITY


def _bars(rows, start="2026-10-09 10:00"):
    t = pd.date_range(start, periods=len(rows), freq="15min")
    return pd.DataFrame({"time": t, "high": [r[0] for r in rows], "low": [r[1] for r in rows]})


def test_stop_hit_before_target_when_both_touched():
    b = PaperBook()
    b.open("EURUSD", +1, 100.0, 0.01, 2.0, 0.005, "t0")
    b.follow_bars("EURUSD", _bars([(102.5, 98.5)]), cost=0.0)          # la même bougie touche stop ET objectif
    assert "EURUSD" not in b.positions and b.trades[-1]["raison"] == "stop"
    assert b.equity == pytest.approx(START_EQUITY * (1 - 0.005)), "perte = le risque choisi (0,5 %)"


def test_target_and_costs():
    b = PaperBook()
    b.open("EURUSD", -1, 100.0, 0.01, 2.0, 0.0025, "t0")
    b.follow_bars("EURUSD", _bars([(100.5, 99.5), (99.0, 97.9)]), cost=0.0001)
    t = b.trades[-1]
    assert t["raison"] == "objectif"
    assert t["resultat_compte"] == pytest.approx(0.02 * 0.25 - 0.0001 * 0.25), "2 x le risque, moins les frais"


def test_walls_close_everything_like_the_real_account():
    b = PaperBook()
    b.new_day("2026-10-09")
    b.equity = START_EQUITY * 0.954
    assert b.check_walls() == "jour"
    b.new_day("2026-10-10")
    assert b.check_walls() is None, "le mur du jour se lève le lendemain"
    b.equity = START_EQUITY * 0.90
    assert b.check_walls() == "total"


def test_cumulative_risk_budget_like_the_real_profile():
    b = PaperBook()
    for i in range(8):
        assert b.can_open(0.005)
        b.open(f"M{i}", +1, 100.0, 0.01, None, 0.005, "t0")
    assert not b.can_open(0.005), "4 % de risque cumulé atteint : plus d'ouverture"
    assert b.open_risk() == pytest.approx(0.04)


def test_brake_halves_risk_and_budget_below_5pct_from_peak():
    from src.aurexis_live import brake_factor
    assert brake_factor(96_000, 100_000) == 1.0 and brake_factor(94_900, 100_000) == 0.5
    b = PaperBook()
    b.open("X", +1, 100.0, 0.01, None, 0.06, "t0")
    b.follow_bars("X", _bars([(100.5, 98.9)]), cost=0.0)                # stop : -6 %
    assert b.brake() == 0.5 and b.peak_equity == pytest.approx(START_EQUITY)
    for i in range(4):
        assert b.can_open(0.01 * b.brake())                           # 1 % freiné = 0,5 % ; budget 2 %
        b.open(f"M{i}", +1, 100.0, 0.01, None, 0.005, "t0")
    assert not b.can_open(0.005), "budget réduit de moitié par le frein"
    assert PaperBook(b.to_state()).peak_equity == b.peak_equity, "le plus haut survit d'un passage à l'autre"


def _t(m, o, c, risk, res):
    return {"marche": m, "ouvert": pd.Timestamp(o), "ferme": pd.Timestamp(c), "risque": risk, "resultat": res}


def test_replay_account_refuses_beyond_the_risk_budget():
    from src.aurexis_live import replay_account
    tr = [_t(f"M{i}", "2025-10-01 10:00", "2025-10-01 12:00", 0.01, 0.01) for i in range(6)]
    r = replay_account(tr, brake=False)
    assert r["trades_pris"] == 4 and r["trades_refuses"] == 2, "4 % de risque cumulé au maximum"
    assert r["compte"] == pytest.approx(1.01 ** 4 - 1)
    tr.append(_t("M9", "2025-10-01 12:00", "2025-10-01 13:00", 0.01, 0.01))
    assert replay_account(tr, brake=False)["trades_pris"] == 5, "à heure égale, la clôture libère le budget d'abord"


def test_replay_account_brake_and_walls():
    from src.aurexis_live import replay_account
    tr = [_t("A", "2025-10-01 10:00", "2025-10-01 11:00", 0.01, -0.03),
          _t("B", "2025-10-01 11:30", "2025-10-01 12:00", 0.01, -0.03),      # -6 % : sous le frein
          _t("C", "2025-10-02 10:00", "2025-10-02 11:00", 0.01, 0.02)]
    sans, avec = replay_account(tr, brake=False), replay_account(tr, brake=True)
    assert sans["compte"] == pytest.approx(0.97 * 0.97 * 1.02 - 1)
    assert avec["compte"] == pytest.approx(0.97 * 0.97 * 1.01 - 1), "frein : risque et résultat x 0,5"
    mur = [_t("A", "2025-10-01 10:00", "2025-10-01 11:00", 0.01, -0.05),
           _t("B", "2025-10-01 12:00", "2025-10-01 13:00", 0.01, 0.02),       # même jour, mur atteint : refusé
           _t("C", "2025-10-02 10:00", "2025-10-02 11:00", 0.01, 0.02)]       # le lendemain : repris
    r = replay_account(mur, brake=False)
    assert r["trades_pris"] == 2 and r["trades_refuses"] == 1
    assert r["baisse_max"] == pytest.approx(0.05)


def test_trade_log_records_the_opening_bar():
    from src.trading_env import TradingEnv
    n = 200
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 0.1, n))
    df = pd.DataFrame({"time": pd.date_range("2025-10-01", periods=n, freq="15min"), "open": close, "high": close + 0.2,
                       "low": close - 0.2, "close": close, "f": rng.normal(size=n).astype("float32")})
    env = TradingEnv(df, window_size=10, feature_columns=["f"], learn_stop_loss=True, stop_loss_buckets=[0.01, 0.02],
                     atr_stop_loss=False, learn_take_profit=True, take_profit_rr_buckets=[1.0, 3.0],
                     learn_trade_management=True, risk_sizing_pct=0.005, learn_position_size=True)
    env.reset()
    opens = []
    for k in range(80):
        before = env.position
        env.step([2 if (k // 10) % 2 == 0 else 1, 1, 0, 0, 1])          # 10 bougies achat, 10 bougies à plat...
        if before == 0 and env.position != 0:
            opens.append(env.current_step)
    assert len(env.trade_log) >= 2, "au moins deux trades fermés"
    for t in env.trade_log:
        assert t["open_step"] is not None and t["open_step"] <= t["step"] + 1
    assert [t["open_step"] for t in env.trade_log] == opens[:len(env.trade_log)], "ouverture = bougie d'exécution"


def test_stop_management_only_tightens():
    b = PaperBook()
    b.open("X", +1, 100.0, 0.01, None, 0.005, "t0")
    b.manage("X", 1, 100.2)                                            # gain 0,2 R < 0,5 R : rien
    assert b.positions["X"].stop == pytest.approx(99.0)
    b.manage("X", 1, 100.6)                                            # gain 0,6 R : break-even
    assert b.positions["X"].stop == pytest.approx(100.05)
    b.manage("X", 2, 100.5)                                            # suiveur à 1 R : 99,5 < 100,05 -> ignoré
    assert b.positions["X"].stop == pytest.approx(100.05)


def test_state_survives_between_passes():
    b = PaperBook()
    b.open("X", -1, 50.0, 0.02, 1.5, 0.0025, "t0")
    b.new_day("2026-10-09")
    c = PaperBook(b.to_state())
    assert c.positions["X"].direction == -1 and c.day == "2026-10-09" and c.equity == b.equity


def test_decode_uses_the_environment_itself():
    from src.trading_env import TradingEnv
    n = 120
    close = np.linspace(100, 101, n)
    df = pd.DataFrame({"time": pd.date_range("2026-01-05", periods=n, freq="15min"), "open": close, "high": close + .1,
                       "low": close - .1, "close": close, "f": 0.0})
    env = TradingEnv(df, window_size=5, feature_columns=["f"], learn_stop_loss=True, stop_loss_buckets=[0.01, 0.02],
                     atr_stop_loss=False, learn_take_profit=True, take_profit_rr_buckets=[1.0, 3.0],
                     learn_trade_management=True, risk_sizing_pct=0.005, learn_position_size=True)
    env.reset(); env.current_step = n - 1
    d = decode(env, [2, 1, 1, 2, 3])
    assert d == {"direction": 1, "stop_pct": 0.02, "tp_mult": 3.0, "manage": 2, "risk": 0.01}


class _FakeConn:
    def __init__(self, symbol, positions=1):
        self.symbol, self.orders, self.positions = symbol, [], positions

    def send_order(self, target, **kw):
        self.orders.append((target, kw))

    def close_all_positions(self, reason=""):
        n, self.positions = self.positions, 0
        return {"closed": [{}] * n, "failed": []}


def test_demo_sends_the_ai_decision_with_its_risk_stop_and_target():
    from src.aurexis_live import demo_execute
    c = _FakeConn("EURUSD")
    demo_execute(c, -1, {"stop_pct": 0.004, "tp_mult": 3.0, "risk": 0.0025}, generation=399)
    target, kw = c.orders[-1]
    assert target == -1.0 and kw["style"] == "AUREXIS" and kw["risk_pct_override"] == 0.0025
    assert kw["stop_pct"] == 0.004 and kw["take_profit_rr"] == 3.0
    demo_execute(c, 0, {})
    assert c.orders[-1][0] == 0.0, "à plat = fermer la position d'AUREXIS sur ce symbole"


def test_demo_breaker_closes_every_symbol():
    from src.aurexis_live import demo_breaker
    conns = {s: _FakeConn(s, positions=2) for s in ("EURUSD", "US500Cash", "JP225Cash")}
    assert demo_breaker(conns) == 6 and all(c.positions == 0 for c in conns.values())

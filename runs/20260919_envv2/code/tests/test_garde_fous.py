"""LES TROIS OUTILS ET LEURS GARDE-FOUS (09/10/2026) -- chaque faille possible a son test :
taille choisie par l'IA, règles FTMO à l'entraînement (mort / bonus), récompense en argent (pas de « petites positions
pour toucher la récompense »), chance FTMO dans la note d'examen, coupe-circuit qui ferme réellement les positions."""
from __future__ import annotations
import json
import types

import numpy as np
import pandas as pd
import pytest

from src.trading_env import TradingEnv


def _df(close, start="2024-01-01", freq="15min"):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"time": pd.date_range(start, periods=len(close), freq=freq), "open": close,
                         "high": close * 1.0001, "low": close * 0.9999, "close": close, "f": 0.0})


def _env(close, **kw):
    base = dict(window_size=5, initial_balance=10000, transaction_cost=0.0, reward_type="trade_argent",
                drawdown_penalty=0.0, max_position=1, feature_columns=["f"])
    base.update(kw)
    return TradingEnv(_df(close), **base)


def _sized_env(close, **kw):
    """Environnement d'AUREXIS : stop + objectif + gestion + TAILLE choisie (dernière dimension)."""
    base = dict(learn_stop_loss=True, stop_loss_buckets=[0.01], atr_stop_loss=False, learn_take_profit=True,
                take_profit_rr_buckets=[50.0], learn_trade_management=True, risk_sizing_pct=0.0025,
                learn_position_size=True)
    base.update(kw)
    return _env(close, **base)


# ---------------------------------------------------------------- 1. la taille choisie par l'IA
def test_size_is_the_last_action_and_sets_the_risk():
    env = _sized_env(np.full(60, 100.0))
    assert list(env.action_space.nvec) == [3, 1, 1, 3, 4]
    assert env._idx_manage == 3 and env._idx_size == 4, "positions nommées, la taille en dernier"
    sizes = []
    for bucket in range(4):
        env.reset()
        env.step([2, 0, 0, 0, bucket])
        sizes.append(env._size)
    # stop à 1 % : taille = risque / 1 % -> 0,1 / 0,25 / 0,5 / 1
    assert sizes == pytest.approx([0.1, 0.25, 0.5, 1.0])


def test_without_the_size_tool_nothing_changes():
    env = _sized_env(np.full(60, 100.0), learn_position_size=False)
    assert list(env.action_space.nvec) == [3, 1, 1, 3]
    env.reset()
    env.step([2, 0, 0, 0])
    assert env._size == pytest.approx(0.25), "risque fixe risk_sizing_pct comme avant"


def test_management_is_read_at_its_own_position_not_the_last():
    """Avant : la gestion lisait action[-1] ; avec la taille en dernier elle aurait lu la taille."""
    close = np.r_[np.full(10, 100.0), np.linspace(100, 103, 30)]
    env = _sized_env(close)
    env.reset()
    env.step([2, 0, 0, 0, 3])                        # achat, gestion 0, taille max
    stop0 = env.stop_price
    for _ in range(20):
        env.step([2, 0, 0, 0, 3])                    # gestion 0 = ne rien toucher, malgré taille=3
    assert env.stop_price == stop0 and env.n_be == 0 and env.n_trail == 0
    for _ in range(3):
        env.step([2, 0, 0, 2, 0])                    # gestion 2 = stop suiveur
    assert env.n_trail >= 1


# ---------------------------------------------------------------- 2. pas de « crack head » : la récompense en argent
def _one_trade_reward(bucket):
    close = np.r_[np.full(8, 100.0), np.linspace(100, 101, 10), np.full(10, 101.0)]
    env = _sized_env(close)
    env.reset()
    total = 0.0
    for a in [[2, 0, 0, 0, bucket]] * 12 + [[1, 0, 0, 0, bucket]] * 3:
        total += env.step(a)[1]
    assert len(env.trade_log) == 1
    return total


def test_micro_position_earns_micro_reward():
    small, big = _one_trade_reward(0), _one_trade_reward(3)
    assert big > 0 and small > 0
    assert (big + 0.02) / (small + 0.02) == pytest.approx(10.0, rel=0.02), "récompense proportionnelle à l'argent"


def test_farming_micro_trades_is_a_losing_game():
    """50 allers-retours minuscules sur un marché plat : chaque trade coûte, aucun ne rapporte."""
    env = _sized_env(np.full(200, 100.0), transaction_cost=0.0002)
    env.reset()
    total = 0.0
    for _ in range(50):
        total += env.step([2, 0, 0, 0, 0])[1]
        total += env.step([1, 0, 0, 0, 0])[1]
    assert len(env.trade_log) == 50
    assert total < -50 * 0.02 + 1e-9, "au moins le coût fixe par trade, jamais un gain"


def test_reward_counts_fees_and_fixed_cost():
    env = _sized_env(np.full(60, 100.0), transaction_cost=0.001)
    env.reset()
    env.step([2, 0, 0, 0, 3])
    r = env.step([1, 0, 0, 0, 3])[1]
    t = env.trade_log[-1]
    assert t["risk"] == pytest.approx(0.01) and t["cost_pct"] > 0
    assert r == pytest.approx((t["pnl_pct"] - t["cost_pct"]) / 0.005 - 0.02)


# ---------------------------------------------------------------- 3. FTMO à l'entraînement : la mort et le bonus
def test_death_at_minus_5_percent_in_the_day():
    close = np.r_[np.full(8, 100.0), np.linspace(100, 90, 30)]      # -10 % dans la même matinée
    env = _env(close, reward_type="pnl", ftmo_rules=True)
    env.reset()
    for _ in range(40):
        _, r, term, _, info = env.step(2)
        if term:
            break
    assert info.get("ftmo") == "mort" and term
    assert r <= -20.0 + 1e-6
    assert info["equity"] / 10000 - 1 <= -0.05 and info["equity"] / 10000 - 1 > -0.07, "arrêtée au mur, pas après"
    assert env.ftmo_events["mort"] == 1


def test_death_at_minus_10_percent_overall_even_without_a_bad_day():
    days = 6
    per_day = 96
    close = np.concatenate([np.linspace(100 * 0.97 ** d, 100 * 0.97 ** (d + 1), per_day) for d in range(days)])
    close = np.r_[np.full(8, 100.0), close]
    env = _env(close, reward_type="pnl", ftmo_rules=True)
    env.reset()
    worst_day = 0.0
    for _ in range(len(close)):
        _, r, term, _, info = env.step(2)
        worst_day = min(worst_day, env._day_pnl())
        if term:
            break
    assert info.get("ftmo") == "mort"
    assert info["equity"] <= 9000 + 1e-6
    assert worst_day > -0.05, "aucune journée à -5 % : c'est bien la perte totale qui tue"


def test_success_bonus_at_plus_10_percent_realised():
    close = np.r_[np.full(8, 100.0), np.linspace(100, 115, 30), np.full(10, 115.0)]
    env = _env(close, reward_type="pnl", ftmo_rules=True)
    env.reset()
    for _ in range(31):
        _, _, term, _, info = env.step(2)
        assert not term, "un gain latent ne compte pas : FTMO juge le solde"
    _, r, term, _, info = env.step(1)                               # on encaisse
    assert term and info.get("ftmo") == "reussite" and r >= 5.0


def test_rules_are_off_by_default_so_exams_play_full_periods():
    close = np.r_[np.full(8, 100.0), np.linspace(100, 80, 30), np.full(10, 80.0)]
    env = _env(close, reward_type="pnl")
    env.reset()
    term, n = False, 0
    while not term:
        _, _, term, _, info = env.step(2)
        n += 1
    assert "ftmo" not in info and n == len(close) - 2 - 5


def test_casino_loses_more_than_calm_trading():
    """Même hasard, même politique au hasard : à 1 % de risque (casino) la somme des récompenses est bien pire qu'à
    0,1 % -- les morts FTMO coûtent plus que ce que rapportent les réussites."""
    rng = np.random.default_rng(3)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.003, 6000))

    def play(bucket):
        env = _sized_env(close, stop_loss_buckets=[0.003], ftmo_rules=True, transaction_cost=0.0001)
        pol = np.random.default_rng(11)
        env.reset()
        total = 0.0
        for _ in range(5000):
            a = [int(pol.integers(0, 3)), 0, 0, 0, bucket]
            _, r, term, _, _ = env.step(a)
            total += r
            if term:
                env.reset()
        return total, dict(env.ftmo_events)

    calm, ev_calm = play(0)
    casino, ev_casino = play(3)
    assert ev_casino["mort"] > ev_calm["mort"]
    assert casino < calm


# ---------------------------------------------------------------- 4. la chance FTMO dans la note d'examen
def _fake_run(daily_rets):
    eq = 10000 * np.r_[1.0, np.cumprod(1 + np.asarray(daily_rets))]
    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=len(eq), freq="D")})
    return types.SimpleNamespace(equity_curve=list(eq), window_size=1), df


def test_exam_rewards_reasonable_size_not_tiny_nor_casino():
    from src.continuous_trainer import ftmo_chance
    rng = np.random.default_rng(5)
    good = rng.normal(0.003, 0.006, 250)                  # une IA qui gagne, taille raisonnable
    tiny = good * 0.1                                     # LA MÊME IA, positions 10x plus petites
    casino = rng.normal(0.0, 0.035, 250)                  # une IA qui joue gros au hasard
    t_good = ftmo_chance(*_fake_run(good))
    t_tiny = ftmo_chance(*_fake_run(tiny))
    t_casino = ftmo_chance(*_fake_run(casino))
    assert t_good["pass"] > 0.5 and t_good["term"] > 0.3
    assert t_tiny["pass"] == 0.0 and t_tiny["term"] == pytest.approx(0.0), "minuscule = ne réussit jamais"
    assert t_casino["term"] < 0, "casino = échoue plus qu'il ne réussit"
    assert t_good["term"] > t_tiny["term"] > t_casino["term"]


def test_too_short_run_gets_no_bonus():
    from src.continuous_trainer import ftmo_chance
    assert ftmo_chance(*_fake_run([0.05] * 5))["term"] == 0.0


def test_worker_applies_rules_to_training_only_and_adds_ftmo_to_the_note(tmp_path, monkeypatch):
    import src.continuous_trainer as ct
    made = []

    class Spy(TradingEnv):
        def __init__(self, df, **kw):
            made.append(dict(kw))
            super().__init__(df, **kw)

    monkeypatch.setattr(ct, "TradingEnv", Spy)
    rng = np.random.default_rng(1)
    close = 100 * np.cumprod(1 + rng.normal(0.0001, 0.002, 2400))
    df = _df(close, freq="h")
    env_kwargs = dict(window_size=5, initial_balance=10000, transaction_cost=0.0, reward_type="pnl",
                      drawdown_penalty=0.0, max_position=1, feature_columns=["f"])
    spec = {"train_df": df.iloc[:1200].reset_index(drop=True), "val_df": df.iloc[1200:].reset_index(drop=True),
            "env_kwargs": env_kwargs, "hyperparams": {"n_steps": 64, "batch_size": 16},
            "warm_start_path": None, "timesteps": 64, "out_path": str(tmp_path / "cand"),
            "generation": 1, "style": "H1", "slot": 0, "context_timeframes": [], "eval_windows": 1,
            "fitness_metric": "sortino",
            "train_env_kwargs": {"ftmo_rules": True, "reward_type": "trade_argent"}, "ftmo_weight": 1.0}
    out = ct._train_candidate_worker(spec)
    train = [k for k in made if k.get("randomize_start")]
    others = [k for k in made if not k.get("randomize_start")]
    assert train and all(k.get("ftmo_rules") and k["reward_type"] == "trade_argent" for k in train)
    assert others and not any(k.get("ftmo_rules") for k in others), "l'examen joue sans règle d'entraînement"
    assert "ftmo" in out["metrics"] and set(out["metrics"]["ftmo"]) >= {"pass", "breach", "term"}


# ---------------------------------------------------------------- 5. le coupe-circuit ferme vraiment
def _fake_mt5(positions, sent, retcode=10009, demo=True):
    m = types.SimpleNamespace(ACCOUNT_TRADE_MODE_DEMO=0, TRADE_ACTION_DEAL=1, TRADE_ACTION_REMOVE=8,
                              ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1, ORDER_FILLING_FOK=0, ORDER_FILLING_IOC=1,
                              ORDER_FILLING_RETURN=2, TRADE_RETCODE_DONE=10009)
    m.account_info = lambda: types.SimpleNamespace(trade_mode=0 if demo else 2, equity=9500.0)
    m.positions_get = lambda symbol=None: list(positions)
    m.orders_get = lambda symbol=None: []
    m.symbol_info = lambda symbol: types.SimpleNamespace(trade_contract_size=100.0, volume_step=0.01, volume_min=0.01,
                                                        volume_max=100.0, digits=2, filling_mode=0,
                                                        trade_stops_level=0, point=0.01)
    m.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=1999.0, ask=2001.0, time=1_700_000_000)

    def send(req):
        sent.append(req)
        return types.SimpleNamespace(retcode=retcode)
    m.order_send = send
    return m


def _conn(positions, sent, dry_run=False, **kw):
    from src.mt5_connector import MT5Connector
    conn = MT5Connector({"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": dry_run,
                                  "allow_real_account": False, "max_risk_pct_per_trade": 0.0025}})
    conn._mt5 = _fake_mt5(positions, sent, **kw)
    return conn


def _pos(ticket, direction, volume=0.5, profit=-120.0):
    return types.SimpleNamespace(ticket=ticket, type=0 if direction > 0 else 1, volume=volume, profit=profit,
                                 price_open=2000.0, sl=1990.0, comment="AUREX")


def test_connector_closes_every_open_position_with_the_opposite_order():
    sent = []
    conn = _conn([_pos(1, +1), _pos(2, -1, 0.2)], sent)
    res = conn.close_all_positions()
    assert [r["position"] for r in sent] == [1, 2]
    assert sent[0]["type"] == 1 and sent[0]["price"] == 1999.0, "un achat se ferme par une vente au prix vendeur"
    assert sent[1]["type"] == 0 and sent[1]["volume"] == 0.2
    assert len(res["closed"]) == 2 and not res["failed"]


def test_refused_close_is_reported_for_retry():
    sent = []
    res = _conn([_pos(1, +1)], sent, retcode=10018).close_all_positions()   # 10018 = marché fermé
    assert res["failed"] and not res["closed"]


def test_never_sends_real_orders_in_simulation_or_on_a_real_account():
    sent = []
    _conn([_pos(1, +1)], sent, dry_run=True).close_all_positions()
    _conn([_pos(1, +1)], sent, demo=False).close_all_positions()
    assert sent == []


def test_tripped_guard_closes_positions_and_a_blip_does_not(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import src.account_guard as ag
    import src.demo_trader as dt
    alerts = []
    monkeypatch.setattr("src.notifier.send_alert", lambda cfg, subject, message: alerts.append(message))
    cfg = {"live": {"symbol": "XAUUSD", "max_account_drawdown_pct": 0.09, "total_drawdown_mode": "static",
                    "daily_loss_enabled": True, "daily_loss_max_pct": 0.045}}

    class Conn:
        def __init__(self, equity):
            self.equity, self.calls = equity, 0
        def get_account_equity(self):
            return self.equity
        def close_all_positions(self, reason=""):
            self.calls += 1
            return {"closed": [{"ticket": 1, "volume": 0.5, "profit": -4600.0}], "failed": []}

    c = Conn(100000.0)
    assert ag.check(c, cfg) is True
    c.equity = None                                     # blip de connexion : bloqué mais pas déclenché
    assert ag.check(c, cfg) is False
    assert dt.guard_close_positions(c, cfg) is None and c.calls == 0
    c.equity = 95400.0                                  # -4,6 % dans la journée : au-delà de 4,5 %
    assert ag.check(c, cfg) is False and ag.is_halted()
    res = dt.guard_close_positions(c, cfg)
    assert c.calls == 1 and res["closed"]
    assert alerts and "fermé 1 position" in alerts[-1]
    state = json.load(open(ag.STATE_PATH, encoding="utf-8"))
    assert state["halted_reason"] == "perte quotidienne"


def test_demo_loop_calls_the_closing_breaker():
    """Le branchement dans la boucle : chaque tour où le coupe-circuit bloque appelle la fermeture."""
    import inspect
    import src.demo_trader as dt
    src_loop = inspect.getsource(dt.run_demo_trading_loop)
    i = src_loop.index("if not account_guard_check(connector, cfg):")
    assert "guard_close_positions(connector, cfg)" in src_loop[i:i + 600]


def test_ftmo_profile_walls_sit_just_inside_ftmo_limits():
    import yaml
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "config" / "risk_profiles" / "ftmo_ai.yaml"
    prof = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert prof["daily_loss"]["enabled"] and 0.04 <= prof["daily_loss"]["max_pct"] < 0.05
    assert prof["total_drawdown"]["mode"] == "static" and 0.08 <= prof["total_drawdown"]["max_pct"] < 0.10

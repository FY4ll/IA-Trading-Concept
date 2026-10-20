"""Robustesse (06/10/2026) : règles FTMO dans l'apprentissage, décisions sur bougies clôturées, familles
exclusives, période récente de la lockbox."""
from __future__ import annotations
import json
import os
import types

import numpy as np
import pandas as pd
import pytest

from src.data_loader import generate_synthetic_ohlcv
from src.trading_env import TradingEnv


def _env(close, **kw):
    n = len(close)
    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=n, freq="15min"), "open": close,
                       "high": np.asarray(close) + 0.01, "low": np.asarray(close) - 0.01, "close": close, "f": 0.0})
    base = dict(window_size=5, initial_balance=10000, transaction_cost=0.0, reward_type="risk_adjusted",
                drawdown_penalty=0.0, max_position=1, feature_columns=["f"])
    base.update(kw)
    return TradingEnv(df, **base)


def test_daily_halt_blocks_new_positions_after_loss_until_next_day():
    close = np.r_[np.full(10, 100.0), np.linspace(100, 96, 10), np.full(80, 96.0)]  # -4 % dans la journée
    env = _env(close, daily_loss_halt_pct=0.025)
    env.reset()
    env.current_step = 8
    env.step(2)                                       # achat
    for _ in range(12):
        env.step(2)                                   # la position perd ~4 %
    env.step(1)                                       # sortie (toujours permise)
    assert env.position == 0
    assert env._day_pnl() <= -0.025
    env.step(2)                                       # nouvelle ouverture refusée : coupe-circuit du jour
    assert env.position == 0
    # le lendemain (96 bougies M15 plus tard) l'ouverture redevient possible
    env2 = _env(np.r_[close, np.full(120, 96.0)], daily_loss_halt_pct=0.025)
    env2.reset(); env2.current_step = 8
    for a in [2] * 13 + [1]:
        env2.step(a)
    while pd.Timestamp(env2.df["time"].iloc[env2.current_step]).normalize() == pd.Timestamp("2024-01-01"):
        env2.step(1)
    env2.step(2)
    assert env2.position == 1


def test_prop_penalty_only_beyond_soft_limit():
    close = np.r_[np.full(10, 100.0), np.linspace(100, 97, 20), np.full(20, 97.0)]
    base = _env(close)
    pen = _env(close, prop_penalty_coef=1.0, prop_soft_loss_pct=0.015)
    for e in (base, pen):
        e.reset(); e.current_step = 8
    r_base, r_pen = [], []
    for _ in range(25):
        r_base.append(base.step(2)[1]); r_pen.append(pen.step(2)[1])
    diff = np.array(r_base) - np.array(r_pen)
    assert diff[:3].max() == pytest.approx(0.0, abs=1e-12), "aucune pénalité tant que la perte du jour < 1,5 %"
    assert diff.max() > 0, "pénalité au-delà de -1,5 % sur la journée"


def _mgmt_env(close):
    return _env(close, learn_stop_loss=True, stop_loss_buckets=[0.01], atr_stop_loss=False, learn_take_profit=True,
                take_profit_rr_buckets=[50.0], learn_trade_management=True)


def test_trade_management_break_even_and_trailing_only_tighten():
    close = np.r_[np.full(10, 100.0), np.linspace(100, 101.5, 10), np.full(10, 101.5), np.full(10, 100.8)]
    env = _mgmt_env(close)
    assert list(env.action_space.nvec) == [3, 1, 1, 3]
    env.reset(); env.current_step = 8
    env.step(np.array([2, 0, 0, 0]))                       # achat à 100, stop 99 (R = 1)
    assert env.stop_price == pytest.approx(99.0)
    env.step(np.array([2, 0, 0, 1]))                       # break-even demandé trop tôt (gain < 0,5R) : refusé
    assert env.stop_price == pytest.approx(99.0)
    while env.current_step < 19:
        env.step(np.array([2, 0, 0, 0]))
    env.step(np.array([2, 0, 0, 1]))                       # gain >= 0,5R -> stop à break-even (+0,05R)
    assert env.stop_price == pytest.approx(100.05)
    env.step(np.array([2, 0, 0, 2]))                       # suiveur : 101.5 - 1R = 100.5
    assert env.stop_price == pytest.approx(100.5)
    while env.current_step < 31:
        env.step(np.array([2, 0, 0, 0]))
    env.step(np.array([2, 0, 0, 2]))                       # prix 100.8 : suiveur à 99.8 = élargirait -> refusé
    assert env.position == 0 or env.stop_price == pytest.approx(100.5)
    assert env.n_be == 1 and env.n_trail >= 1


def test_graft_management_keeps_decisions():
    from src.agent import TradingAgent
    from src.network_growth import add_action_dim
    import torch
    df_close = np.r_[np.linspace(100, 110, 300)]
    old_env = _env(df_close, learn_stop_loss=True, stop_loss_buckets=[0.01, 0.02], atr_stop_loss=False,
                   learn_take_profit=True, take_profit_rr_buckets=[1.0, 2.0])
    new_env = _env(df_close, learn_stop_loss=True, stop_loss_buckets=[0.01, 0.02], atr_stop_loss=False,
                   learn_take_profit=True, take_profit_rr_buckets=[1.0, 2.0], learn_trade_management=True)
    agent = TradingAgent(old_env, {"n_steps": 64, "batch_size": 16})
    agent.learn(64)
    old_env.reset(); new_env.reset()
    ref = []
    for s in range(10, 60):
        old_env.current_step = s
        ref.append(np.asarray(agent.predict(old_env._get_obs(), deterministic=True)).tolist())
    n_old = agent.model.policy.action_net.weight.shape[0]
    add_action_dim(agent, new_env, {"n_steps": 64, "batch_size": 16})
    with torch.no_grad():
        agent.model.policy.action_net.weight[n_old:, :] = 0.0
        agent.model.policy.action_net.bias[n_old:] = torch.tensor([3.0, 0.0, 0.0])
    for i, s in enumerate(range(10, 60)):
        new_env.current_step = s
        a = np.asarray(agent.predict(new_env._get_obs(), deterministic=True)).tolist()
        assert a[:-1] == ref[i] and a[-1] == 0


def test_trader_note_reads_like_a_trader():
    from src.trader.notes import build_note
    row = pd.Series({"tv_bias_h4": 1.0, "tv_h1_struct": 1.0, "tv_range_h1": 0.0, "tv_d_pdl": 0.4, "tv_d_ash": -2.0,
                     "tv_ev_to_next": 6 / 72, "tv_eur_r4": 1.6})
    n = build_note("OPEN_LONG", row, {"vol_class": "NORMAL"}, {"day_pnl": 0.004, "stops_today": 0}, limit_offset=3.2)
    assert n.startswith("ACHAT par ordre LIMITE (3.20 $ du prix)")
    for s in ("biais H4 haussier", "structure H1 haussière", "plus bas d'hier à 0.4 ATR sous le prix",
              "prochaine news majeure dans 6 h", "dollar faible", "journée +0.40 %"):
        assert s in n, s
    w = build_note("WAIT", None, None, None, wait_reason="news_blackout:USD NFP")
    assert w == "ATTEND -- raison : news_blackout:USD NFP."


def test_drop_forming_bar():
    from src.demo_trader import _drop_forming_bar
    bars = pd.DataFrame({"time": pd.to_datetime(["2026-10-06 10:00", "2026-10-06 10:15", "2026-10-06 10:30"])})
    conn = types.SimpleNamespace(symbol="XAUUSD", _mt5=types.SimpleNamespace(
        symbol_info_tick=lambda s: types.SimpleNamespace(time=int(pd.Timestamp("2026-10-06 10:37").timestamp()))))
    out = _drop_forming_bar(bars, conn, "M15")
    assert list(out["time"].dt.strftime("%H:%M")) == ["10:00", "10:15"], "la bougie 10:30 est en formation"
    conn._mt5.symbol_info_tick = lambda s: types.SimpleNamespace(time=int(pd.Timestamp("2026-10-06 10:45").timestamp()))
    assert len(_drop_forming_bar(bars, conn, "M15")) == 3, "à 10:45 la bougie 10:30 est clôturée"


def test_live_history_enough_after_dropping_forming_bar(tmp_path, monkeypatch):
    """Régression 06/10/2026 : avec la bougie en formation retirée, l'historique live doit encore dépasser la
    fenêtre d'observation (sinon IndexError à la création de l'environnement de décision)."""
    from src.features import add_technical_features
    import src.demo_trader as dt
    window = 50
    import inspect
    src_code = inspect.getsource(dt.run_demo_trading_loop)
    margin = int(src_code.split('env_kwargs["window_size"] + ')[1].split()[0])
    raw = generate_synthetic_ohlcv(n_bars=window + margin, seed=3).iloc[:-1]     # bougie en formation retirée
    assert len(add_technical_features(raw)) > window + 1


def test_lockbox_last_third_rule():
    from src.lockbox_gate import gate_decision
    m = {"sharpe": 0.6, "max_drawdown": 0.2, "total_return": 0.3, "n_trades": 300, "thirds_returns": [0.2, 0.15, -0.03]}
    assert gate_decision(m, {}, None)[0], "sans la clé, comportement d'origine"
    ok, why = gate_decision(m, {"min_last_third_return": 0.0}, None)
    assert not ok and "dernier tiers" in why


def _demo_setup(tmp_path, monkeypatch, cfg_live, open_positions, decide_target=1.0):
    """Boucle de démo réelle, décision forcée à `decide_target`, faux connecteur."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as dt
    from src.trading_env import ENV_VERSION
    for style in ("H1", "H1T"):
        d = tmp_path / "models" / f"champion_{style}"
        d.mkdir(parents=True)
        (d / "meta.json").write_text(json.dumps({"generation": 1, "score": 1.0, "updated_at": 1.0,
                                                  "primary_timeframe": style, "context_timeframes": [],
                                                  "feature_columns": ["f"], "env_version": ENV_VERSION,
                                                  "passes_validation": True}))
        (d / "norm_stats.json").write_text("{}")
    calls = {"decide": 0}

    def fake_reload(self, entry, *a, **k):
        if self.mtf_config is None:
            self.mtf_config = {"primary_timeframe": entry["style"], "context_timeframes": []}
            self.meta = entry["meta"]

    def fake_decide(self, *a, **k):
        calls["decide"] += 1
        return decide_target, None, None, None, None

    monkeypatch.setattr(dt._StyleRuntime, "maybe_reload", fake_reload)
    monkeypatch.setattr(dt._StyleRuntime, "decide", fake_decide)
    now = {"t": pd.Timestamp("2026-10-06 10:05")}

    class Conn:
        symbol = "XAUUSD"
        def __init__(self):
            self.orders = []
            self.risks = {}
            self._mt5 = types.SimpleNamespace(symbol_info_tick=lambda s: types.SimpleNamespace(time=int(now["t"].timestamp())))
        def connect(self): pass
        def close_orphan_positions(self, recognized_styles): return []
        def get_open_positions_by_style(self, recognized_styles): return dict(open_positions)
        def get_latest_bars(self, tf, n):
            end = now["t"].floor("h")
            return pd.DataFrame({"time": pd.date_range(end=end, periods=n, freq="h")})
        def send_order(self, target, **kw):
            self.orders.append((kw.get("style"), target))
            self.risks[kw.get("style")] = kw.get("risk_pct_override")

    cfg = {"live": {"dry_run": True, "poll_seconds": 0, **cfg_live}, "fundamental": {"enabled": False},
           "data": {"timeframe_pool": ["H1", "H1T"], "n_bars_context": 10}, "market_hours": {"enabled": False}}
    env_kwargs = dict(window_size=5, initial_balance=10000, transaction_cost=0.0, reward_type="risk_adjusted",
                      drawdown_penalty=0.0, max_position=1)
    return dt, cfg, env_kwargs, Conn(), calls, now


def test_one_decision_per_closed_bar(tmp_path, monkeypatch):
    dt, cfg, ek, conn, calls, now = _demo_setup(tmp_path, monkeypatch, {"decide_on_closed_bars": True}, {})
    dt.run_demo_trading_loop(cfg, ek, connector=conn, max_iterations=3)       # même heure -> 1 décision/style
    assert calls["decide"] == 2
    now["t"] = pd.Timestamp("2026-10-06 11:01")                               # nouvelle bougie H1 clôturée
    dt.run_demo_trading_loop(cfg, ek, connector=conn, max_iterations=1)
    assert calls["decide"] == 4


def test_exclusive_group_blocks_second_position(tmp_path, monkeypatch):
    held = {"H1": {"ticket": 1, "direction": 1, "volume": 0.1, "price_open": 100.0, "sl": 99.0, "profit": 0.0}}
    dt, cfg, ek, conn, calls, now = _demo_setup(
        tmp_path, monkeypatch, {"exclusive_groups": [["H1", "H1T"]]}, held)
    dt.run_demo_trading_loop(cfg, ek, connector=conn, max_iterations=1)
    sent = dict(conn.orders)
    assert sent.get("H1T") == 0.0, "H1T ne doit pas ouvrir : H1 (même famille) a déjà une position"
    assert sent.get("H1") == 1.0, "H1 garde sa position"


def test_incumbent_reevaluated_each_cycle(tmp_path, monkeypatch):
    """Le score mémorisé du champion est une barre périmée (maximum d'une mesure passée) : avec
    `reevaluate_incumbent`, il est rejoué poids figés sur les données du cycle et les candidats sont
    comparés à ce score frais. Ici le champion ne vaut plus que 0,5 : un candidat à 2,0 doit passer,
    alors qu'il aurait été refusé face au 3,0 mémorisé."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct
    from src.features import FEATURE_COLUMNS, add_technical_features, normalize_features
    from src.data_loader import chronological_split

    def get_data(primary_tf=None):
        df = add_technical_features(generate_synthetic_ohlcv(n_bars=2000, seed=3))
        tr, va, _ = chronological_split(df, 0.7, 0.3)
        tr, st = normalize_features(tr, columns=FEATURE_COLUMNS)
        va, _ = normalize_features(va, st, columns=FEATURE_COLUMNS)
        return tr, va, st, FEATURE_COLUMNS, []

    cfg = {"agent": {"policy": "MlpPolicy", "learning_rate": 3e-4, "n_steps": 128, "batch_size": 32,
                     "gamma": 0.99, "gae_lambda": 0.95, "ent_coef": 0.01},
           "continuous": {"candidates_per_cycle": 1, "timesteps_per_cycle": 128, "mutation_scale": 0.2,
                          "parallel_workers": 1, "reevaluate_incumbent": True,
                          "min_trades_for_confident_score": 1},
           "memory": {"db_path": "mem.sqlite", "max_episodes": 500},
           "validation": {"min_sharpe_to_go_live": 50.0, "max_drawdown_allowed": 0.20}}
    ek = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002, reward_type="risk_adjusted",
              drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, get_data, ["H1"], ek)
    sharpes = iter([3.0, 0.5, 2.0])          # cycle 1 : candidat ; cycle 2 : champion réévalué, puis candidat

    def metrics(agent, df, env_kwargs, n_windows=3, **kw):
        return {"total_return": 0.1, "sharpe": next(sharpes), "max_drawdown": 0.0,
                "win_rate": 0.5, "profit_factor": 1.5, "n_trades": 50}

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=metrics):
        trainer.run_one_cycle()
        assert trainer.champion_score["H1"] == pytest.approx(3.0)
        trainer.run_one_cycle()
    assert trainer.champion_score["H1"] == pytest.approx(2.0), "le candidat bat le champion réévalué"
    meta = json.load(open(ct._champion_meta("H1"), encoding="utf-8"))
    assert meta["score"] == pytest.approx(2.0)
    journal = [json.loads(l) for l in open(os.path.join("reports", "experiment_journal.jsonl"), encoding="utf-8")]
    assert [e["kind"] for e in journal] == ["control", "incumbent", "control"]
    trainer.close()


@pytest.mark.parametrize("stop_idx", [0, 1])
def test_risk_sizing_every_stop_costs_the_same_risk(stop_idx):
    """Taille au risque (prop firm) : stop à 1 % ou à 2 %, une sortie au stop coûte 0,5 % de l'équité
    -- comme en réel. Sans taille au risque, elle coûte la distance du stop (1 % ou 2 %)."""
    n = 30
    df = pd.DataFrame({"open": [100.0] * n, "high": [100.0] * n, "low": [100.0] * n, "close": [100.0] * n,
                       "volume": [1.0] * n})
    df.loc[6, "low"] = 97.5
    results = {}
    for risk in (0.0, 0.005):
        env = TradingEnv(df, window_size=3, feature_columns=["close"], learn_stop_loss=True,
                         stop_loss_buckets=[0.01, 0.02], atr_stop_loss=False, transaction_cost=0.0,
                         risk_sizing_pct=risk)
        env.reset()
        while env.current_step < 7:
            env.step(np.array([2, stop_idx]))
            if env.trade_log:
                break
        assert env.trade_log and env.trade_log[0]["stopped_out"]
        results[risk] = env.balance / env.initial_balance - 1.0
    stop = [0.01, 0.02][stop_idx]
    assert results[0.0] == pytest.approx(-stop, abs=1e-9)
    assert results[0.005] == pytest.approx(-0.005, abs=1e-9)


def test_risk_sizing_reverts_to_flat_size_and_caps_leverage():
    df = pd.DataFrame({"open": [100.0] * 10, "high": [100.0] * 10, "low": [100.0] * 10, "close": [100.0] * 10,
                       "volume": [1.0] * 10})
    env = TradingEnv(df, window_size=3, feature_columns=["close"], learn_stop_loss=True,
                     stop_loss_buckets=[0.0001], atr_stop_loss=False, transaction_cost=0.0,
                     risk_sizing_pct=0.01, max_leverage=10.0)
    assert env.size_for_stop(0.0001) == 10.0
    assert env.size_for_stop(0.02) == pytest.approx(0.5)
    assert env.size_for_stop(None) == 1.0
    env.reset()
    env.step(np.array([2, 0]))
    assert env._size == 10.0
    env.step(np.array([1, 0]))           # retour à plat
    assert env._size == 1.0


def test_style_risk_cap_limits_budget(tmp_path, monkeypatch):
    dt, cfg, ek, conn, calls, now = _demo_setup(
        tmp_path, monkeypatch, {"max_risk_pct_per_trade": 0.01, "max_risk_pct_by_style": {"H1T": 0.0035}}, {})
    dt.run_demo_trading_loop(cfg, ek, connector=conn, max_iterations=1)
    assert conn.risks["H1T"] == pytest.approx(0.0035), "plafond de risque du style appliqué"
    assert conn.risks["H1"] > 0.0035, "les autres styles gardent leur budget"

def test_incumbent_becomes_eligible_on_fresh_streak_and_is_removed_after(tmp_path, monkeypatch):
    """Un champion promu sous le seuil devient éligible démo s'il passe les MÊMES seuils 3 cycles de suite sur
    sa mesure fraîche, et en est retiré après 3 échecs de suite. Aucun seuil abaissé."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct
    from src.features import FEATURE_COLUMNS, add_technical_features, normalize_features
    from src.data_loader import chronological_split

    def get_data(primary_tf=None):
        df = add_technical_features(generate_synthetic_ohlcv(n_bars=2000, seed=3))
        tr, va, _ = chronological_split(df, 0.7, 0.3)
        tr, st = normalize_features(tr, columns=FEATURE_COLUMNS)
        va, _ = normalize_features(va, st, columns=FEATURE_COLUMNS)
        return tr, va, st, FEATURE_COLUMNS, []

    cfg = {"agent": {"policy": "MlpPolicy", "learning_rate": 3e-4, "n_steps": 128, "batch_size": 32,
                     "gamma": 0.99, "gae_lambda": 0.95, "ent_coef": 0.01},
           "continuous": {"candidates_per_cycle": 1, "timesteps_per_cycle": 128, "mutation_scale": 0.2,
                          "parallel_workers": 1, "reevaluate_incumbent": True, "incumbent_eligibility_streak": 3,
                          "min_trades_for_confident_score": 1},
           "memory": {"db_path": "mem.sqlite", "max_episodes": 500},
           "validation": {"min_sharpe_to_go_live": 2.0, "max_drawdown_allowed": 0.20,
                          "min_generations_before_demo": 0}}
    ek = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002, reward_type="risk_adjusted",
              drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, get_data, ["H1"], ek)
    # cycle 1 : premier champion à 1,0 (sous le seuil 2,0) ; cycles 2-4 : champion rejoué à 2,5, candidat à 0,5 ;
    # cycles 5-7 : champion rejoué à 1,5 (sous le seuil), candidat à 0,4
    sharpes = iter([1.0] + [2.5, 0.5] * 3 + [1.5, 0.4] * 3)

    def metrics(agent, df, env_kwargs, n_windows=3, **kw):
        return {"total_return": 0.1, "sharpe": next(sharpes), "max_drawdown": 0.0,
                "win_rate": 0.5, "profit_factor": 1.5, "n_trades": 50}

    def eligible():
        return json.load(open(ct._champion_meta("H1"), encoding="utf-8")).get("passes_validation")

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=metrics):
        trainer.run_one_cycle()
        assert not eligible()
        trainer.run_one_cycle(); trainer.run_one_cycle()
        assert not eligible(), "2 réussites seulement"
        trainer.run_one_cycle()
        assert eligible(), "3 réussites de suite sur mesure fraîche -> éligible"
        trainer.run_one_cycle(); trainer.run_one_cycle()
        assert eligible()
        trainer.run_one_cycle()
        assert not eligible(), "3 échecs de suite -> retiré"
    trainer.close()


def test_only_trading_styles_can_open_others_manage_their_position(tmp_path, monkeypatch):
    """live.trading_styles = [H1T] : H1 (éligible mais non autorisé) n'ouvre plus rien ; s'il a déjà une position,
    il reste dans la boucle pour la gérer (position_only), jamais fermée d'office."""
    import src.demo_trader as dt0
    dt, cfg, ek, conn, calls, now = _demo_setup(tmp_path, monkeypatch, {"trading_styles": ["H1T"]}, {})
    assert [e["style"] for e in dt._scan_eligible_styles(cfg)] == ["H1T"]
    dt.run_demo_trading_loop(cfg, ek, connector=conn, max_iterations=1)
    assert dict(conn.orders) == {"H1T": 1.0}, "seul H1T ouvre"
    held = {"H1": {"ticket": 1, "direction": 1, "volume": 0.1, "price_open": 100.0, "sl": 99.0, "profit": 0.0}}
    extra = dt0._position_only_entries(cfg, {"H1T"}, held)
    assert [e["style"] for e in extra] == ["H1"] and extra[0]["position_only"]


@pytest.mark.parametrize("d1, expected", [(-0.002, 0.0), (0.002, 1.0)])
def test_trend_discipline_blocks_new_entry_against_d1(tmp_path, monkeypatch, d1, expected):
    """Pas de nouvel achat quand la tendance D1 est baissière (live.trend_discipline) ; autorisé si haussière."""
    dt, cfg, ek, conn, calls, now = _demo_setup(tmp_path, monkeypatch,
                                                {"trading_styles": ["H1T"], "trend_discipline": {"H1T": "D1_trend_signal"}}, {})
    style_df = pd.DataFrame({"time": [now["t"]], "close": [100.0], "D1_trend_signal": [d1]})
    monkeypatch.setattr(dt._StyleRuntime, "decide", lambda self, *a, **k: (1.0, None, None, None, style_df))
    dt.run_demo_trading_loop(cfg, ek, connector=conn, max_iterations=1)
    assert dict(conn.orders).get("H1T") == expected


def test_blocked_entry_is_not_recorded_as_open_position(tmp_path, monkeypatch):
    """Bug du 07/10/2026 : un achat bloqué par la discipline de tendance était noté comme position ouverte dans la
    mémoire interne -> fausse alerte « position fermée chez le broker » à chaque cycle. La mémoire suit la décision
    FINALE."""
    dt, cfg, ek, conn, calls, now = _demo_setup(tmp_path, monkeypatch,
                                                {"trading_styles": ["H1T"], "trend_discipline": {"H1T": "D1_trend_signal"}}, {})
    style_df = pd.DataFrame({"time": [now["t"]], "close": [100.0], "D1_trend_signal": [-0.002]})
    seen = {}

    def fake_decide(self, *a, **k):
        self._tracker_pending = (100.0, np.zeros(1, dtype=np.float32), None)
        seen["rt"] = self
        return 1.0, None, None, None, style_df
    monkeypatch.setattr(dt._StyleRuntime, "decide", fake_decide)
    dt.run_demo_trading_loop(cfg, ek, connector=conn, max_iterations=1)
    assert dict(conn.orders).get("H1T") == 0.0
    assert seen["rt"].tracker.entry_exposure == 0.0, "l'achat bloqué ne doit pas être noté comme position ouverte"

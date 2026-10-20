"""AUREXIS (06/10/2026) : entraînement multi-marchés."""
import numpy as np
import pandas as pd
import pytest

from src.data_loader import generate_synthetic_ohlcv
from src.trading_env import TradingEnv


def _m15(n=400, start="2024-01-01"):
    t = pd.date_range(start, periods=n, freq="15min")
    close = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.1, n))
    return pd.DataFrame({"time": t, "open": close, "high": close + 0.2, "low": close - 0.2, "close": close,
                         "volume": 1.0})


def test_resample_ohlcv_h1_and_day():
    from src.aurexis_data import resample_ohlcv
    m15 = _m15()
    h1 = resample_ohlcv(m15, "H1")
    first = m15.iloc[:4]
    assert h1["time"].iloc[0] == first["time"].iloc[0]
    assert h1["open"].iloc[0] == first["open"].iloc[0] and h1["close"].iloc[0] == first["close"].iloc[3]
    assert h1["high"].iloc[0] == first["high"].max() and h1["low"].iloc[0] == first["low"].min()
    assert len(resample_ohlcv(m15, "D1")) == 5          # 400 bougies M15 = 4 jours + 4 h


def test_combine_segments_keeps_only_env_columns_and_ids():
    from src.aurexis_data import combine_segments
    gold = _m15(100).assign(f1=1.0, f2=2.0, spread_pct=0.0001, junk="x")
    other = _m15(80, "2023-01-01").assign(f1=3.0, f2=4.0)
    out = combine_segments(gold, [other], cols=["f1", "f2"])
    assert list(out["segment_id"].unique()) == [0, 1] and len(out) == 180
    assert "junk" not in out.columns and "spread_pct" not in out.columns, "colonne absente d'un marché -> retirée"
    assert out[["f1", "f2", "close"]].isna().sum().sum() == 0
    assert combine_segments(gold, [], cols=["f1"]) is gold


def test_env_draws_random_starts_inside_every_market():
    a = generate_synthetic_ohlcv(n_bars=3000, seed=1).assign(segment_id=0)
    b = generate_synthetic_ohlcv(n_bars=1000, seed=2).assign(segment_id=1)
    df = pd.concat([a, b], ignore_index=True)
    env = TradingEnv(df, window_size=10, feature_columns=["close"], randomize_start=True, transaction_cost=0.0)
    starts, segs = [], []
    for i in range(300):
        env.reset(seed=i)
        starts.append(env.current_step)
        segs.append(int(df["segment_id"].iloc[env.current_step]))
        # la fenêtre d'observation ne déborde jamais sur le marché précédent
        assert df["segment_id"].iloc[env.current_step - 10] == segs[-1]
    assert set(segs) == {0, 1}
    assert 0.6 < segs.count(0) / len(segs) < 0.9, "tirage au prorata de la taille du marché (3000 vs 1000)"
    assert len(set(starts)) > 200, "départs au hasard DANS le marché, pas toujours au début"


def test_env_without_random_start_keeps_segment_start():
    a = generate_synthetic_ohlcv(n_bars=500, seed=1).assign(segment_id=0)
    b = generate_synthetic_ohlcv(n_bars=500, seed=2).assign(segment_id=1)
    env = TradingEnv(pd.concat([a, b], ignore_index=True), window_size=10, feature_columns=["close"])
    for i in range(20):
        env.reset(seed=i)
        assert env.current_step in (10, 510)


def test_aurexis_is_an_m15_named_style():
    from src.style_utils import base_timeframe
    assert base_timeframe("AUREXIS") == "M15"


def test_sharpe_delta_reward_runs_past_50_bars():
    """Bug du 06/10/2026 : la récompense sharpe_delta plantait (49 vs 50 éléments) dès 51 bougies."""
    df = generate_synthetic_ohlcv(n_bars=300, seed=4)
    env = TradingEnv(df, window_size=10, feature_columns=["close"], reward_type="sharpe_delta", transaction_cost=0.0)
    env.reset()
    for i in range(120):
        _, r, term, _, _ = env.step(2 if i % 7 else 0)
        assert np.isfinite(r)
        if term:
            break


def test_memory_query_many_matches_single_queries():
    """Recherche en mémoire groupée (07/10/2026) : mêmes souvenirs retrouvés qu'avec une recherche par bougie."""
    from src.memory_features import MemoryQuery
    rng = np.random.default_rng(3)
    snap = (rng.normal(0, 1, (800, 30)).astype(np.float32), rng.normal(0, 0.01, 800), rng.uniform(0, 0.1, 800))
    mq = MemoryQuery(snap, top_k=5)
    X = rng.normal(0, 1, (300, 30)).astype(np.float32)
    many = mq.query_many(X, chunk=64)
    single = np.array([mq.query(x) for x in X])
    assert np.allclose(many, single, atol=1e-6)


def test_env_memory_cache_gives_same_episode():
    """Rejeu complet avec la mémoire pré-calculée = rejeu bougie par bougie (mêmes trades, même capital)."""
    from src.backtester import run_episode
    df = generate_synthetic_ohlcv(n_bars=800, seed=5)
    rng = np.random.default_rng(1)
    snap = (rng.normal(0, 1, (200, 1)).astype(np.float32), rng.normal(0, 0.01, 200), rng.uniform(0, 0.1, 200))
    curves = []
    for pre in (False, True):
        env = TradingEnv(df, window_size=10, feature_columns=["close"], memory_snapshot=snap, transaction_cost=0.0)
        if pre:
            env.precompute_memory()
        env.reset()
        for i in range(400):
            _, _, term, _, _ = env.step(2 if (i // 7) % 2 else 1)
            if term:
                break
        curves.append(np.asarray(env.equity_curve))
    assert np.allclose(curves[0], curves[1])


def test_parallel_games_are_independent_and_learn():
    """Parties en parallèle (n_envs) : chaque copie a son propre état et son propre départ au hasard, l'apprentissage
    tourne, les données du marché sont partagées (pas de copie mémoire)."""
    from src.agent import TradingAgent
    df = generate_synthetic_ohlcv(n_bars=3000, seed=2)
    env = TradingEnv(df, window_size=10, feature_columns=["close"], randomize_start=True)
    hp = {"n_steps": 256, "batch_size": 64, "n_epochs": 1, "lstm_hidden_size": 16, "net_arch": [16], "n_envs": 4,
          "device": "cpu"}
    agent = TradingAgent(env, hp)
    envs = agent.model.get_env().envs
    assert agent.n_envs == 4 and len(envs) == 4
    assert all(e._feature_values is env._feature_values for e in envs), "données partagées"
    starts = []
    for e in envs:
        e.reset()
        starts.append(e.current_step)
    assert len(set(starts)) > 1, "départs au hasard différents"
    envs[0].step(2)
    assert envs[1].position == 0, "l'état d'une partie ne touche pas les autres"
    agent.learn(512)
    assert agent.model.num_timesteps >= 512 and agent.model.n_steps == 64


def test_mirror_market_turns_rises_into_falls():
    """Marché miroir (07/10/2026) : chaque hausse devient une baisse de même ampleur, bougies cohérentes."""
    from src.aurexis_data import mirror_m15
    m = _m15(500)
    mm = mirror_m15(m)
    r, rm = np.log(m["close"]).diff().dropna(), np.log(mm["close"]).diff().dropna()
    assert np.allclose(rm.to_numpy(), -r.to_numpy())
    assert (mm["high"] >= mm[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (mm["low"] <= mm[["open", "close"]].min(axis=1) + 1e-9).all()
    assert np.isclose(mm["close"].iloc[0], m["close"].iloc[0])


def test_mirror_of_a_later_slice_matches_training_level():
    """Examen sur un marché inversé : une tranche ultérieure, inversée avec le niveau de l'entraînement, donne
    exactement les mêmes prix que l'inversion de l'historique complet."""
    from src.aurexis_data import mirror_m15
    m = _m15(500)
    k = float(m["close"].iloc[0]) ** 2
    full = mirror_m15(m)
    part = mirror_m15(m.iloc[300:].reset_index(drop=True), k)
    assert np.allclose(part["close"].to_numpy(), full["close"].iloc[300:].to_numpy())
    assert np.allclose(part["high"].to_numpy(), full["high"].iloc[300:].to_numpy())


def test_multi_market_score_mixes_gold_and_other_markets():
    """Sélection multi-marchés (07/10/2026) : score = poids x or + (1 - poids) x moyenne des autres marchés,
    chaque note bornée, un marché en erreur compte comme la pire note sans faire tomber le candidat."""
    from src.agent import TradingAgent
    from src.continuous_trainer import _multi_market_score
    kw = {"window_size": 10, "feature_columns": ["close"], "transaction_cost": 0.0}
    env = TradingEnv(generate_synthetic_ohlcv(n_bars=600, seed=1), **kw)
    agent = TradingAgent(env, {"n_steps": 64, "batch_size": 32, "n_epochs": 1, "lstm_hidden_size": 8,
                               "net_arch": [8], "device": "cpu"})
    markets = [("A", generate_synthetic_ohlcv(n_bars=600, seed=2)), ("B", generate_synthetic_ohlcv(n_bars=600, seed=3)),
               ("CASSÉ", generate_synthetic_ohlcv(n_bars=600, seed=4).drop(columns=["close"]))]
    spec = {"extra_val": markets, "env_kwargs": kw, "style": "AUREXIS", "extra_val_gold_weight": 0.25,
            "extra_val_score_clip": 3.0}
    metrics = {}
    score = _multi_market_score(agent, spec, 1.0, metrics, "sortino")
    per = {p["market"]: p for p in metrics["markets"]}
    assert set(per) == {"A", "B", "CASSÉ"} and per["CASSÉ"]["score"] == -3.0 and "error" in per["CASSÉ"]
    assert all(-3.0 <= p["score"] <= 3.0 for p in per.values())
    others = np.mean([p["score"] for p in per.values()])
    assert np.isclose(metrics["markets_score"], others) and metrics["gold_score"] == 1.0
    assert np.isclose(score, 0.25 * 1.0 + 0.75 * others)

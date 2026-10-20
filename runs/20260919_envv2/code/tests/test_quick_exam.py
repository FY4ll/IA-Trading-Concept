"""Petit examen tiré au hasard + mélangeur logique + examen en deux temps (08/10/2026)."""
import numpy as np
import pandas as pd
import pytest

from src.data_loader import generate_synthetic_ohlcv


def _m15(days=30, seed=0):
    t = pd.date_range("2022-01-03", periods=days * 96, freq="15min")
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.001, len(t))
    r[500] = 0.03                                         # une vraie grosse bougie
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[100.0], close[:-1]]) * np.exp(rng.normal(0, 0.0002, len(t)))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.0005, len(t))))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.0005, len(t))))
    return pd.DataFrame({"time": t, "open": open_, "high": high, "low": low, "close": close, "volume": 1.0})


def test_mixer_builds_a_logical_market():
    from src.aurexis_data import mix_days
    src = _m15()
    mixed = mix_days(src, np.random.default_rng(1))
    assert mixed is not None and abs(len(mixed) - len(src)) <= 96
    lr_src = np.abs(np.diff(np.log(src["close"].to_numpy())))
    lr_mix = np.abs(np.diff(np.log(mixed["close"].to_numpy())))
    assert lr_mix.max() <= lr_src.max() + 1e-9, "aucune bougie plus forte que la plus forte bougie réelle"
    assert (mixed["high"] >= mixed[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (mixed["low"] <= mixed[["open", "close"]].min(axis=1) + 1e-9).all()
    assert (mixed["close"] > 0).all() and mixed["time"].is_monotonic_increasing
    assert set(mixed["time"].dt.normalize()) <= set(src["time"].dt.normalize()), "même calendrier"
    assert not np.allclose(mixed["close"].to_numpy()[:2000], src["close"].to_numpy()[1:2001]), "vraiment mélangé"
    again = mix_days(src, np.random.default_rng(1))
    assert np.allclose(again["close"], mixed["close"]), "reproductible pour un même tirage"


def test_two_stage_exam_keeps_only_candidates_close_to_champion(tmp_path, monkeypatch):
    import src.continuous_trainer as ct
    from src.data_loader import chronological_split
    from src.features import FEATURE_COLUMNS, add_technical_features, normalize_features
    monkeypatch.chdir(tmp_path)

    def get_data(primary_tf=None):
        d = add_technical_features(generate_synthetic_ohlcv(n_bars=1500, seed=3))
        tr, va, _ = chronological_split(d, 0.7, 0.3)
        tr, st = normalize_features(tr, columns=FEATURE_COLUMNS)
        va, _ = normalize_features(va, st, columns=FEATURE_COLUMNS)
        return tr, va, st, FEATURE_COLUMNS, []
    _, va, _, _, _ = get_data()
    get_data.extra_val = {"H1": [("A", va)]}
    get_data.quick_exam = {"H1": [("tirage A 01/01/2022 (42 j)", va.iloc[:300]), ("mélangé A", va.iloc[100:400])]}
    cfg = {"agent": {"policy": "MlpPolicy", "learning_rate": 3e-4, "n_steps": 64, "batch_size": 32,
                     "gamma": 0.99, "gae_lambda": 0.95, "ent_coef": 0.01},
           "continuous": {"candidates_per_cycle": 3, "timesteps_per_cycle": 64, "parallel_workers": 1,
                          "reevaluate_incumbent": True},
           "multi_market": {"selection": {"enabled": True}, "quick_exam": {"enabled": True, "margin": -99.0,
                                                                            "keep_best": 1}},
           "memory": {"db_path": "mem.sqlite", "max_episodes": 500}}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                      reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, get_data, ["H1"], env_kwargs)
    trainer.run_one_cycle()                               # crée le champion
    calls = []
    real = ct.ContinuousEvolutionTrainer._run_pool

    def spy(specs, mw):
        calls.append([("p1" if s.get("phase") == 1 else "p2", bool(s.get("eval_only")), bool(s.get("skip_learn")))
                      for s in specs])
        return real(specs, mw)
    monkeypatch.setattr(ct.ContinuousEvolutionTrainer, "_run_pool", staticmethod(spy))
    trainer.run_one_cycle()
    trainer.close()
    assert len(calls) == 2
    assert calls[0] == [("p1", True, False)] + [("p1", False, False)] * 3, "temps 1 : champion + 3 candidats"
    # marge impossible (-99) : seul le meilleur candidat (keep_best=1) passe au temps 2, avec le champion
    assert sorted(calls[1]) == sorted([("p2", True, False), ("p2", False, True)])

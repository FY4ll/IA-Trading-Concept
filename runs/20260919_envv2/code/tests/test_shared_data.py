"""Données d'entraînement partagées sur le disque (08/10/2026) : mêmes résultats, une seule copie en mémoire."""
import os
import pickle

import numpy as np
import pandas as pd

from src.data_loader import generate_synthetic_ohlcv
from src.trading_env import TradingEnv


def _df(n=1500, seed=3):
    df = generate_synthetic_ohlcv(n_bars=n, seed=seed)
    rng = np.random.default_rng(seed)
    for i in range(50):
        df[f"f{i}"] = rng.normal(0, 1, n).astype("float32")
    df["segment_id"] = (np.arange(n) // 700).astype(np.int64)
    return df


def test_shared_frame_is_small_to_send_and_reads_identical_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.shared_data import share_frame
    df = _df()
    cols = [f"f{i}" for i in range(50)]
    sf = share_frame(df, cols, tag="t")
    assert os.path.exists(sf.path) and len(sf) == len(df)
    small, arr = sf.load()
    assert np.array_equal(np.asarray(arr), df[cols].to_numpy(np.float32))
    assert not arr.flags.writeable, "lecture seule"
    assert not set(cols) & set(small.columns), "les variables ne voyagent plus avec la copie"
    assert len(pickle.dumps(sf)) < len(pickle.dumps(df)) / 2
    assert share_frame(df, cols, tag="t").path == sf.path, "même contenu -> même fichier, pas réécrit"


def test_env_on_shared_data_plays_exactly_the_same_episode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.shared_data import share_frame
    df = _df()
    cols = [f"f{i}" for i in range(50)]
    small, arr = share_frame(df, cols, tag="t").load()
    curves = []
    for env in (TradingEnv(df, window_size=10, feature_columns=cols, transaction_cost=0.0002),
                TradingEnv(small, window_size=10, feature_columns=cols, transaction_cost=0.0002, feature_array=arr)):
        obs, _ = env.reset(seed=1)
        obs_list = [obs]
        for i in range(500):
            obs, _, term, trunc, _ = env.step(2 if (i // 9) % 3 == 0 else (0 if (i // 9) % 3 == 1 else 1))
            obs_list.append(obs)
            if term or trunc:
                break
        curves.append((np.asarray(env.equity_curve), np.asarray(obs_list)))
    assert np.allclose(curves[0][0], curves[1][0]) and np.allclose(curves[0][1], curves[1][1])


def test_real_cycle_trains_on_shared_data(tmp_path, monkeypatch):
    """Vrai cycle miniature avec données partagées : le fichier est créé et l'entraînement va jusqu'au bout."""
    import glob
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
    cfg = {"agent": {"policy": "MlpPolicy", "learning_rate": 3e-4, "n_steps": 64, "batch_size": 32,
                     "gamma": 0.99, "gae_lambda": 0.95, "ent_coef": 0.01},
           "continuous": {"candidates_per_cycle": 2, "timesteps_per_cycle": 64, "parallel_workers": 1,
                          "reevaluate_incumbent": True, "shared_train_data": True, "shared_min_rows": 0},
           "memory": {"db_path": "mem.sqlite", "max_episodes": 500}}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                      reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, get_data, ["H1"], env_kwargs)
    trainer.run_one_cycle()
    trainer.run_one_cycle()
    trainer.close()
    assert glob.glob(os.path.join("data", "partage", "train_H1_*.f32"))
    assert os.path.exists(ct._champion_model("H1") + ".zip")

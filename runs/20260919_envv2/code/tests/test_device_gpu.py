"""10/10/2026 : un cerveau qui a appris sur la carte graphique se recharge dans un programme qui la cache (examen du
jour, AUREXIS à blanc, verdict des 12 mois) -- vérifié dans un VRAI processus séparé sans carte visible."""
from __future__ import annotations
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest


def _env():
    from src.trading_env import TradingEnv
    n = 300
    close = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.1, n))
    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=n, freq="15min"), "open": close,
                       "high": close + .1, "low": close - .1, "close": close, "f": 0.0})
    return TradingEnv(df, window_size=5, feature_columns=["f"])


def test_model_saved_on_gpu_reloads_without_gpu(tmp_path):
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("pas de carte graphique visible pour créer le modèle")
    from src.agent import TradingAgent
    a = TradingAgent(_env(), {"n_steps": 64, "batch_size": 16, "device": "cuda"})
    a.learn(64)
    a.save(str(tmp_path / "agent"))
    code = ("import sys; sys.path.insert(0, %r)\n"
            "import tests.test_device_gpu as t\n"
            "from src.agent import TradingAgent\n"
            "ag = TradingAgent.load(%r, t._env(), {'algo': 'PPO'})\n"
            "print(str(ag.model.device))\n") % (os.getcwd(), str(tmp_path / "agent"))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={**os.environ, "CUDA_VISIBLE_DEVICES": "-1"}, cwd=os.getcwd())
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().endswith("cpu")

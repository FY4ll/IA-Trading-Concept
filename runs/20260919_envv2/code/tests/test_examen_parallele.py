"""ACCÉLÉRATION DES CYCLES (12/10/2026) : les périodes d'examen sont construites par plusieurs processus en parallèle.
Les données doivent être EXACTEMENT les mêmes qu'à la suite (seule la vitesse change)."""
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

import src.aurexis_data as ad


def _market_csv(path, seed, n=9000):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.001, n))
    pd.DataFrame({"time": pd.date_range("2024-01-01", periods=n, freq="15min"), "open": close,
                  "high": close * 1.001, "low": close * 0.999, "close": close, "volume": 1.0}).to_csv(path, index=False)


def test_parallel_exam_frames_are_identical(tmp_path):
    cols = ["return_1", "rsi_14", "atr_pct"]
    stats = {c: (0.0, 1.0) for c in cols}
    args = []
    for i, mirror in enumerate([False, True, False]):
        p = tmp_path / f"M{i}.csv"
        _market_csv(p, i)
        args.append((f"M{i}", str(p), mirror, 1.0, stats, cols, [], str(tmp_path), None,
                     pd.Timestamp("2024-02-15"), pd.Timestamp("2024-04-01"), 7000, 0.0002, {}))
    seq = [ad._build_exam_frame(a) for a in args]
    with ProcessPoolExecutor(max_workers=2) as pool:
        par = list(pool.map(ad._build_exam_frame, args))
    for (f1, m1), (f2, m2) in zip(seq, par):
        assert m1 == m2
        assert f1 is not None and f1.equals(f2), "même période, mêmes données, au bit près"
    assert seq[1][0]["close"].tolist() != seq[0][0]["close"].tolist(), "chaque marché a ses propres données"

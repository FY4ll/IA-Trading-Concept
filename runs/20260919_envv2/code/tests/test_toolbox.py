"""Boîte à outils du trader (07/10/2026) : aucune information du futur, colonnes stables, valeurs finies."""
import numpy as np
import pandas as pd
import pytest


def _m15(n=12000, seed=1):
    t = pd.date_range("2024-01-01", periods=n, freq="15min")
    rng = np.random.default_rng(seed)
    c = 2000 + np.cumsum(rng.normal(0, 1.0, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 1.0, n)
    l = np.minimum(o, c) - rng.uniform(0, 1.0, n)
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": rng.uniform(50, 150, n)})


def test_toolbox_never_uses_the_future():
    """Le calcul à la bougie i doit être identique qu'on dispose ou non des bougies suivantes."""
    from src.trader.toolbox import add_toolbox
    df = _m15()
    full = add_toolbox(df)
    cols = [c for c in full.columns if c.startswith("tb_")]
    for cut in (9000, 10500):
        part = add_toolbox(df.iloc[:cut].reset_index(drop=True))
        a, b = full[cols].iloc[cut - 1].to_numpy(float), part[cols].iloc[cut - 1].to_numpy(float)
        bad = [c for c, x, y in zip(cols, a, b) if not (np.isclose(x, y, atol=1e-6) or (np.isnan(x) and np.isnan(y)))]
        assert not bad, f"fuite du futur dans : {bad}"


def test_toolbox_columns_stable_and_finite_at_the_end():
    from src.trader.toolbox import add_toolbox, toolbox_columns, has_toolbox_columns
    out = add_toolbox(_m15(seed=2))
    cols = [c for c in out.columns if c.startswith("tb_")]
    assert cols == toolbox_columns() and len(cols) >= 80
    tail = out[cols].iloc[-200:]
    assert np.isfinite(tail.to_numpy()).all(), [c for c in cols if not np.isfinite(tail[c]).all()]
    assert (tail.abs() <= 10).all().all()
    assert has_toolbox_columns(cols) and not has_toolbox_columns(["rsi_14"])

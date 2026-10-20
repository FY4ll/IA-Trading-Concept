"""Vision des tendances de fond (09/10/2026) : jamais d'information du jour même, sens correct (hausse / baisse /
marché inversé), historique complet utilisé même quand la tranche de bougies est courte."""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

from src.trend_vision import TREND_COLUMNS, add_trend_vision, daily_closes, trend_table


def _m15(daily_prices, start="2020-01-01"):
    """Bougies M15 (4 par jour, pour aller vite) suivant des clôtures quotidiennes données."""
    rows = []
    for i, p in enumerate(daily_prices):
        d = pd.Timestamp(start) + pd.Timedelta(days=i)
        for h in range(4):
            rows.append((d + pd.Timedelta(hours=6 * h), p))
    t, c = zip(*rows)
    return pd.DataFrame({"time": t, "close": c})


def test_never_uses_the_same_day():
    rng = np.random.default_rng(0)
    p = 100 * np.cumprod(1 + rng.normal(0.001, 0.01, 400))
    base = trend_table(daily_closes(_m15(p)))
    p2 = p.copy(); p2[-1] *= 1.5                                  # choc sur le DERNIER jour
    moved = trend_table(daily_closes(_m15(p2)))
    pd.testing.assert_frame_equal(base.iloc[:-1], moved.iloc[:-1])
    assert np.allclose(base.iloc[-1].to_numpy(), moved.iloc[-1].to_numpy(), equal_nan=True), \
        "la valeur du dernier jour ne dépend que de la veille et avant"


def test_direction_and_mirror():
    rng = np.random.default_rng(1)
    up = 100 * np.cumprod(1 + rng.normal(0.002, 0.005, 400))
    t_up = trend_table(daily_closes(_m15(up))).iloc[-1]
    assert t_up["tdf_signe"] == 1.0 and all(t_up[c] > 0 for c in ("tdf_1m", "tdf_3m", "tdf_6m", "tdf_12m"))
    mirrored = 100.0 ** 2 / up                                     # marché miroir : hausse -> baisse
    t_dn = trend_table(daily_closes(_m15(mirrored))).iloc[-1]
    assert t_dn["tdf_signe"] == -1.0 and all(t_dn[c] < 0 for c in ("tdf_1m", "tdf_3m", "tdf_6m", "tdf_12m"))
    assert all(abs(t_up[c]) <= 5 for c in TREND_COLUMNS)


def test_full_history_reaches_short_slices():
    rng = np.random.default_rng(2)
    p = 100 * np.cumprod(1 + rng.normal(0.002, 0.005, 400))
    full = _m15(p)
    short = full.tail(40).reset_index(drop=True).copy()          # 10 jours seulement
    alone = add_trend_vision(short.copy())
    assert (alone["tdf_12m"] == 0).all(), "sans historique : neutre (0), jamais inventé"
    with_hist = add_trend_vision(short.copy(), daily_closes(full))
    assert (with_hist["tdf_12m"] > 0).all() and (with_hist["tdf_signe"] == 1).all()


def test_market_frames_receive_trend_columns(tmp_path):
    from src.aurexis_data import build_market_frame
    from src.data_loader import generate_synthetic_ohlcv
    m15 = generate_synthetic_ohlcv(n_bars=3000, seed=3)
    m15["time"] = pd.date_range("2022-01-03", periods=len(m15), freq="15min")
    df = build_market_frame("EURUSD", m15, [], None)
    assert all(c in df.columns for c in TREND_COLUMNS)


def test_trend_stats_can_be_saved_as_json():
    """Incident du 09/10 18h20 : variables en float32 -> statistiques en float32 -> l'enregistrement de la fiche du
    nouveau champion plantait (Object of type float32 is not JSON serializable) et coupait norm_stats.json."""
    import json
    from src.features import normalize_features
    rng = np.random.default_rng(4)
    df = add_trend_vision(_m15(100 * np.cumprod(1 + rng.normal(0.001, 0.01, 400))))
    _, stats = normalize_features(df, columns=TREND_COLUMNS)
    json.dumps({k: list(v) for k, v in stats.items()})          # ne doit pas lever d'erreur

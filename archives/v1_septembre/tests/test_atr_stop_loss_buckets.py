"""LOT 2, phase 3 : remplace tests/test_stop_loss_buckets.py comme test
PRIMAIRE des distances de stop -- le stop ATR dynamique est désormais actif
par défaut (config/autonomous.yaml: atr_stop_loss: true), les buckets
statiques de test_stop_loss_buckets.py ne couvrent plus que le chemin de
repli (voir ce fichier pour l'explication complète). Vérifie
ATR_STOP_MULTIPLIERS_BY_STYLE (valeurs par style, dérivées de la médiane
ATR/prix historique réelle -- voir le commentaire dans src/trading_env.py)
et _compute_atr_stop_loss_buckets (résolution multiple -> % via
risk_engine)."""
from __future__ import annotations
import numpy as np
import pytest

from src.trading_env import TradingEnv
from src.risk_engine import atr_stop_distance_pct, ATR_STOP_PCT_FLOOR, ATR_STOP_PCT_CEILING
from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features


def _df_with_atr(n_bars=200, seed=3):
    return add_technical_features(generate_synthetic_ohlcv(n_bars=n_bars, seed=seed))


def _make_env(style, **overrides):
    df = generate_synthetic_ohlcv(n_bars=200, seed=7)
    kwargs = dict(window_size=20, feature_columns=["close"], learn_stop_loss=True, style=style)
    kwargs.update(overrides)
    return TradingEnv(df, **kwargs)


@pytest.mark.parametrize("style", ["M15", "M30", "H1", "H4", "D1"])
def test_every_style_has_exactly_5_atr_multipliers_same_cardinality_as_static_buckets(style):
    assert len(TradingEnv.ATR_STOP_MULTIPLIERS_BY_STYLE[style]) == \
        len(TradingEnv.STOP_LOSS_BUCKETS_BY_STYLE[style]) == 5


@pytest.mark.parametrize("style", ["M15", "M30", "H1", "H4", "D1"])
def test_atr_multipliers_strictly_increasing_per_style(style):
    """Chaque style a sa PROPRE échelle (dérivée de la médiane ATR/prix
    historique réelle, voir src/trading_env.py) -- toujours strictement
    croissante (bucket i+1 = stop plus large que bucket i)."""
    multipliers = TradingEnv.ATR_STOP_MULTIPLIERS_BY_STYLE[style]
    assert multipliers == sorted(multipliers) and len(set(multipliers)) == 5


def test_atr_multipliers_differ_by_style_not_a_single_shared_scale():
    """Contrairement à l'échelle unique d'origine (jugée trop serrée pour
    les timeframes courtes après mesure sur l'historique réel), chaque style
    a maintenant sa PROPRE échelle."""
    m15 = TradingEnv.ATR_STOP_MULTIPLIERS_BY_STYLE["M15"]
    d1 = TradingEnv.ATR_STOP_MULTIPLIERS_BY_STYLE["D1"]
    assert m15 != d1
    assert max(m15) > max(d1), "M15 a besoin de multiples BEAUCOUP plus larges que D1 (ATR/prix bien plus petit)"


def test_compute_atr_stop_loss_buckets_matches_risk_engine_formula():
    env = _make_env("H1", raw_atr=[5.0] * 200)
    env.reset()
    price = float(env._close[env.current_step])
    buckets = env._compute_atr_stop_loss_buckets(price)
    expected = [atr_stop_distance_pct(5.0, m, price, ATR_STOP_PCT_FLOOR, ATR_STOP_PCT_CEILING)
                for m in env.atr_stop_multipliers]
    assert buckets == expected


def test_atr_buckets_floor_and_ceiling_still_enforced():
    env = _make_env("H1", raw_atr=[1e-9] * 200)  # ATR quasi nul
    env.reset()
    price = float(env._close[env.current_step])
    buckets = env._compute_atr_stop_loss_buckets(price)
    assert all(b == pytest.approx(ATR_STOP_PCT_FLOOR) for b in buckets)

    env2 = _make_env("H1", raw_atr=[1e6] * 200)  # ATR aberrant
    env2.reset()
    price2 = float(env2._close[env2.current_step])
    buckets2 = env2._compute_atr_stop_loss_buckets(price2)
    assert all(b == pytest.approx(ATR_STOP_PCT_CEILING) for b in buckets2)


def test_atr_multipliers_truncated_or_repeated_to_match_explicit_bucket_count():
    """Cardinalité alignée sur `stop_loss_buckets` explicite (comportement
    préexistant, revérifié après le passage aux valeurs par style)."""
    env = _make_env("M15", stop_loss_buckets=[0.001, 0.002])  # 2 buckets seulement
    assert len(env.atr_stop_multipliers) == 2
    assert env.atr_stop_multipliers == TradingEnv.ATR_STOP_MULTIPLIERS_BY_STYLE["M15"][:2]


def test_no_opening_when_atr_required_but_unavailable():
    """LOT 2, phase 3, point 2 : atr_stop_loss=True et "atr_14" dans
    feature_columns (ATR REQUIS) mais aucune source d'ATR fournie
    (_atr_price_units() -> None à chaque pas) -- aucune ouverture ne doit
    jamais avoir lieu, quelle que soit l'action choisie."""
    df = _df_with_atr()
    env = TradingEnv(df, window_size=20, feature_columns=["close", "atr_pct"],
                       learn_stop_loss=True, atr_stop_loss=True, style="H1")
    # Pas de raw_atr fourni ET pas de colonne atr_14_raw -> ATR indisponible
    # à CHAQUE pas, alors que "atr_pct" est bien dans feature_columns (requis).
    env.reset()
    for _ in range(50):
        obs, reward, term, trunc, info = env.step([2, 0])  # tente d'ouvrir LONG, bucket 0
        assert env.position == 0.0, "aucune position ne doit jamais s'ouvrir sans ATR disponible"
        if term or trunc:
            break


def test_existing_position_not_force_closed_when_atr_becomes_unavailable():
    """Une position DÉJÀ ouverte (pendant que l'ATR était disponible) n'est
    jamais forcée à zéro par le seul fait que l'ATR devient indisponible --
    seule une NOUVELLE ouverture/un retournement est bloqué(e). On maintient
    ensuite la MÊME direction (jamais un nouveau "changement"), ce qui ne
    doit jamais être annulé par le garde-fou."""
    df = _df_with_atr()
    n = len(df)
    split = n // 2
    raw_atr = np.array([5.0] * split + [np.nan] * (n - split))
    env = TradingEnv(df, window_size=20, feature_columns=["close", "atr_pct"],
                       learn_stop_loss=True, atr_stop_loss=True, style="H1", raw_atr=raw_atr)
    env.reset()
    while env.current_step < split - 5 and env.position == 0.0:
        env.step([2, 0])
    assert env.position != 0.0, "précondition : doit avoir pu ouvrir pendant que l'ATR était disponible"
    pos_before = env.position
    for _ in range(5):
        # Répète la MÊME direction (aucun "changement" au sens de step()) --
        # ne doit jamais être annulé par le garde-fou ATR, qui ne bloque que
        # les changements vers une exposition non nulle.
        direction_idx = 2 if pos_before > 0 else 0
        env.step([direction_idx, 0])
        if env.position == 0.0:
            break  # un stop-loss a pu se déclencher -- pas ce qui est testé ici
    assert env.position == pos_before, \
        "le garde-fou ATR ne doit jamais fermer une position déjà ouverte, seulement bloquer une nouvelle ouverture"


def test_flat_target_never_blocked_by_missing_atr():
    """Une action qui NE change RIEN (rester flat) n'est jamais affectée par
    le garde-fou ATR (il ne concerne que les OUVERTURES)."""
    df = _df_with_atr()
    env = TradingEnv(df, window_size=20, feature_columns=["close", "atr_pct"],
                       learn_stop_loss=True, atr_stop_loss=True, style="H1")
    env.reset()
    obs, reward, term, trunc, info = env.step([1, 0])  # flat
    assert env.position == 0.0
    assert np.isfinite(reward)

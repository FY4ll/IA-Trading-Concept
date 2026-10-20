"""
test_stop_loss_buckets.py
==========================
Vérifie que TradingEnv utilise des buckets de stop-loss STATIQUES (% fixe du
prix) par défaut DIFFÉRENCIÉS PAR STYLE (`style` passé via env_kwargs, voir
ContinuousEvolutionTrainer._run_cycle qui l'injecte dans style_env_kwargs) :
un scalp M15/M30 doit rester sur des distances resserrées, un swing D1 sur
des distances larges -- le mélange des deux (buckets identiques pour tous
les styles) est le bug corrigé ici.

STATUT (LOT 2, phase 3) : ces buckets % restent le CHEMIN DE REPLI --
`config/autonomous.yaml: atr_stop_loss: true` (défaut) fait du stop ATR
dynamique le mécanisme PRIMAIRE en production, ce fichier n'exerce donc plus
le chemin réellement emprunté par défaut. Conservé car le repli statique
reste un comportement réel et testé (ATR indisponible, ou `atr_stop_loss:
false` explicite) -- voir tests/test_atr_stop_loss_buckets.py pour le
mécanisme désormais primaire (ATR_STOP_MULTIPLIERS_BY_STYLE).
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pandas as pd

from src.trading_env import TradingEnv
from src.data_loader import generate_synthetic_ohlcv


def _make_env(style, **overrides):
    df = generate_synthetic_ohlcv(n_bars=200, seed=7)
    kwargs = dict(window_size=20, feature_columns=["close"], learn_stop_loss=True, style=style)
    kwargs.update(overrides)
    return TradingEnv(df, **kwargs)


def test_m15_and_m30_use_tight_buckets():
    for style in ("M15", "M30"):
        env = _make_env(style)
        assert env.stop_loss_buckets == [0.003, 0.005, 0.008, 0.012, 0.02]


def test_h1_and_h4_use_medium_buckets():
    for style in ("H1", "H4"):
        env = _make_env(style)
        assert env.stop_loss_buckets == [0.005, 0.01, 0.02, 0.03, 0.05]


def test_d1_uses_wide_buckets():
    env = _make_env("D1")
    assert env.stop_loss_buckets == [0.01, 0.02, 0.04, 0.07, 0.10]


def test_d1_cannot_choose_bucket_below_0_01():
    env = _make_env("D1")
    assert min(env.stop_loss_buckets) >= 0.01, (
        "un stop D1 ne doit jamais pouvoir être plus serré que 1% -- sinon "
        "il se déclenche sur du simple bruit de marché avant que le "
        "mouvement swing attendu ait le temps de se dessiner."
    )


def test_m15_cannot_choose_bucket_above_0_02():
    env = _make_env("M15")
    assert max(env.stop_loss_buckets) <= 0.02, (
        "un stop M15 ne doit jamais dépasser 2% -- sinon un scalp encaisse "
        "un drawdown démesuré par rapport à l'amplitude réelle de sa "
        "timeframe avant de se déclencher."
    )


def test_explicit_stop_loss_buckets_override_style_default():
    env = _make_env("D1", stop_loss_buckets=[0.001])
    assert env.stop_loss_buckets == [0.001], (
        "des buckets explicites doivent toujours prévaloir sur le défaut "
        "par style -- rétrocompatibilité avec les appels existants."
    )


def test_unknown_or_missing_style_falls_back_to_generic_default():
    env = _make_env(None)
    assert env.stop_loss_buckets == [0.005, 0.01, 0.02, 0.03, 0.05]

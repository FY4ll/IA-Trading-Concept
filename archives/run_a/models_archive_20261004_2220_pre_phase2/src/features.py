"""
features.py
===========
Transforme les données OHLCV brutes en un jeu de caractéristiques (features)
que l'agent peut utiliser pour "observer" l'état du marché.

On combine :
  - le comportement du prix (rendements, volatilité, momentum)
  - des indicateurs techniques classiques (RSI, MACD, bandes de Bollinger, ATR)
  - une place réservée pour des données fondamentales / news (voir add_fundamental_placeholder)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import ta


def add_technical_features(df: pd.DataFrame, fundamental_feed=None,
                            refresh_fundamental: bool = True) -> pd.DataFrame:
    df = df.copy()
    df["return_1"] = df["close"].pct_change()
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))
    df["volatility_10"] = df["return_1"].rolling(10).std()

    df["rsi_14"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd() / df["close"]
    df["macd_signal"] = macd.macd_signal() / df["close"]

    bb = ta.volatility.BollingerBands(df["close"])
    df["bb_pct"] = bb.bollinger_pband()

    # atr_14 reste en UNITÉS DE PRIX brutes (dollars pour l'or) -- nécessaire
    # tel quel pour TradingEnv.ATR_RAW_COLUMN (stop-loss en multiples d'ATR,
    # voir autonomous_agent.py/demo_trader.py qui copient cette colonne HORS
    # normalisation). atr_pct (LOT 2, phase 4, audit multi-actifs) est la
    # version SANS UNITÉ (fraction du prix) utilisée comme FEATURE
    # D'OBSERVATION à la place -- un ATR brut de "5" signifie des choses
    # totalement différentes pour l'or (~2000$, donc ~0.25%) et pour l'EURUSD
    # (~1.1, donc énorme) : mélanger des segments multi-actifs SANS cette
    # conversion rendrait l'observation incohérente d'un actif à l'autre.
    df["atr_14"] = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14
    ).average_true_range()
    df["atr_pct"] = df["atr_14"] / df["close"]

    df["sma_20"] = df["close"].rolling(20).mean()
    df["sma_50"] = df["close"].rolling(50).mean()
    df["trend_signal"] = (df["sma_20"] - df["sma_50"]) / df["close"]

    # RÉGIME DE MARCHÉ : donne à l'agent un signal explicite sur le TYPE de
    # marché actuel, plutôt que de lui laisser le déduire indirectement des
    # indicateurs bruts.
    #   - adx_14 (force de tendance) : haut = marché directionnel (les
    #     styles swing sont généralement favorisés), bas = marché en range
    #     (plus favorable au scalping/retournement).
    #   - volatility_regime : position de la volatilité récente par rapport
    #     à sa propre moyenne sur 50 bougies (z-score, même fenêtre que
    #     sma_50 ci-dessus pour rester cohérent) -- détecte les changements
    #     de régime de volatilité (calme -> agité) même quand le niveau
    #     absolu de volatilité diffère selon la timeframe/l'époque. Une
    #     fenêtre plus longue (200+) serait plus lisse mais consommerait
    #     trop d'historique de warmup sur les petits jeux de données/styles
    #     à faible nombre de bougies (D1...).
    df["adx_14"] = ta.trend.ADXIndicator(
        df["high"], df["low"], df["close"], window=14
    ).adx()
    vol_mean = df["volatility_10"].rolling(50).mean()
    vol_std = df["volatility_10"].rolling(50).std()
    df["volatility_regime"] = (df["volatility_10"] - vol_mean) / (vol_std + 1e-8)

    df = add_fundamental_features(df, fundamental_feed, refresh_fundamental)
    df = df.dropna().reset_index(drop=True)
    return df


def add_fundamental_features(df: pd.DataFrame, fundamental_feed=None,
                              refresh: bool = True) -> pd.DataFrame:
    """Ajoute le score fondamental (news + calendrier économique) réel,
    auto-alimenté par `src/fundamental_feed.py`, aligné bougie par bougie.

    Si aucun `fundamental_feed` n'est fourni (fonctionnalité désactivée dans
    config/autonomous.yaml), ou si toutes les sources échouent, on retombe sur un score
    neutre à 0.0 : le pipeline ne casse jamais pour autant.
    """
    if fundamental_feed is None:
        df["fundamental_score"] = 0.0
        return df
    try:
        df["fundamental_score"] = fundamental_feed.align_to_bars(df, refresh=refresh)
    except Exception:
        df["fundamental_score"] = 0.0
    return df


FEATURE_COLUMNS = [
    "return_1", "log_return", "volatility_10", "rsi_14", "macd", "macd_signal",
    "bb_pct", "atr_pct", "trend_signal", "adx_14", "volatility_regime", "fundamental_score",
]


Z_SCORE_CLIP = 5.0


def normalize_features(df: pd.DataFrame, stats: dict | None = None, columns=None):
    """Normalise (z-score) les colonnes de features.
    Si `stats` est fourni (moyenne/écart-type calculés sur le train), on les
    réutilise pour val/test -> évite toute fuite d'information.
    `columns` permet de normaliser un jeu de colonnes différent du défaut
    (utilisé pour la fusion multi-timeframe, où il y a plus de colonnes).

    PLAFOND À ±Z_SCORE_CLIP (trouvé le 21/09 : `fundamental_score` était
    CONSTANT pendant tout l'entraînement -- flux RSS des banques centrales en
    échec permanent, retombé sur le même score neutre à chaque fois -- donc
    son écart-type appris valait quasiment 0 (seul le plancher `+1e-8`
    ci-dessous). Le réseau n'a rien pu apprendre de cette feature à
    l'entraînement (constante -> toujours normalisée à 0, aucun signal), mais
    en LIVE, une valeur réelle même infime différente de cette constante
    explosait après division par un écart-type quasi nul (observé :
    z-score de 21 millions sur M30) -- une seule entrée numériquement
    aberrante pouvant déstabiliser toute la décision du réseau. Le clip
    élimine cette explosion SANS changer ce que les modèles déjà entraînés
    ont appris (une feature constante à l'entraînement donnait déjà un
    z-score de 0, largement dans [-5, 5] -- aucun retraining nécessaire),
    tout en bornant aussi les lectures réellement extrêmes mais légitimes
    (ex: tendance mensuelle inhabituelle) plutôt que de les laisser
    dominer numériquement l'observation.
    """
    columns = list(columns) if columns is not None else FEATURE_COLUMNS
    df = df.copy()
    if stats is None:
        stats = {c: (df[c].mean(), df[c].std() + 1e-8) for c in columns}
    for c in columns:
        mean, std = stats[c]
        df[c] = ((df[c] - mean) / std).clip(-Z_SCORE_CLIP, Z_SCORE_CLIP)
    return df, stats

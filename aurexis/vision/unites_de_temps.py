# Repris de Run A (src/multi_timeframe.py) le 08/10/2026 pour l'architecture v3 -- calculs IDENTIQUES (prouvé par
# tests/test_vision_equivalence.py). Toute modification doit garder ce test vert.
"""
multi_timeframe.py
===================
Construit un jeu de données UNIQUE où chaque bougie de la timeframe
"primaire" (celle sur laquelle l'agent décide et trade réellement) est
enrichie du CONTEXTE d'autres timeframes plus larges (ex: une bougie H1
"voit" aussi où en sont la tendance/le momentum en H4, D1, W1, MN1).

Point CRITIQUE anti-fuite d'information :
  Pour chaque timeframe de contexte, on utilise UNIQUEMENT les indicateurs
  de la DERNIÈRE bougie déjà CLÔTURÉE au moment de la bougie primaire (on
  décale d'un cran avant la fusion). Sans ce décalage, l'agent "verrait"
  une bougie H4/D1 encore en train de se former, ce qui est une fuite du
  futur vers le passé (data leakage) — exactement ce que le principe de
  "validation temporelle" de la vision du projet interdit.

Utilisation typique :
    from aurexis.vision.unites_de_temps import discover_files, build_mtf_dataset
    files = discover_files("data/kaggle_gold")
    df = build_mtf_dataset(files, primary_tf="H1", context_tfs=["H4","D1","W1","MN1"])
"""
from __future__ import annotations
import os
import re
import glob
import logging
import pandas as pd
import ta

from aurexis.donnees.reserve import lire_csv_ohlcv as load_kaggle_ohlcv_csv

log = logging.getLogger("multi_timeframe")

# Motifs de recherche de fichiers par timeframe, insensibles à la casse.
# Couvre les conventions de nommage les plus courantes (dont le dataset
# Kaggle "XAUUSD Gold Price Historical Data" : XAU_1m_data.csv, XAU_5m_data.csv, ...)
# Motifs de recherche de fichiers par timeframe, insensibles à la casse.
# Couvre les conventions de nommage les plus courantes (dont le dataset
# Kaggle "XAUUSD Gold Price Historical Data" : XAU_1m_data.csv, XAU_5m_data.csv, ...)
#
# IMPORTANT : on exige que chaque token soit délimité (début/fin de nom,
# "_", "-", "."). Un simple "\b" (limite de mot regex) ne fonctionne PAS
# entre un chiffre/lettre et un underscore (les deux sont des caractères
# de mot en regex), ce qui faisait échouer la détection de fichiers comme
# "XAU_1H_data.csv" ou "XAU_4H_data.csv". Cette exigence de délimiteur
# résout aussi naturellement l'ambiguïté "1m" (minute) vs "1mo"/"1M" (mois) :
# "1m" ne matche plus à l'intérieur de "1mo" puisque le caractère qui suit
# ("o") n'est pas un délimiteur.
_DELIM_BEFORE = r"(?:^|[_\-\.])"
_DELIM_AFTER = r"(?:$|[_\-\.]|data)"

TF_TOKENS = {
    "M1":  ["1m", "1min", "m1"],
    "M5":  ["5m", "5min", "m5"],
    "M15": ["15m", "15min", "m15"],
    "M30": ["30m", "30min", "m30"],
    "H1":  ["1h", "h1", "60m"],
    "H4":  ["4h", "h4", "240m"],
    "D1":  ["1d", "d1", "daily"],
    "W1":  ["1w", "w1", "weekly"],
    "MN1": ["1mo", "1mn", "mn1", "monthly", "1month"],
}

# Ordre des timeframes du plus fin au plus large, utile pour trier/valider
TF_ORDER = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]

# Durée approximative en minutes de chaque timeframe, utilisée pour VÉRIFIER
# (pas juste deviner) qu'un fichier a bien été associé au bon label -- car
# "1m" (minute) et "1M"/"1Mo" (mois) sont ambigus une fois le nom de fichier
# mis en minuscule, et une mauvaise association ruinerait silencieusement
# l'entraînement.
TIMEFRAME_MINUTES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240,
    "D1": 1440, "W1": 10080, "MN1": 43200,
}

CONTEXT_INDICATOR_SUFFIXES = ["trend_signal", "rsi_14", "macd_diff", "bb_pct", "volatility_10"]


def verify_timeframe_assignment(files: dict, sample_rows: int = 3000) -> dict:
    """Vérifie, à partir des DONNÉES elles-mêmes (pas juste du nom de
    fichier), que chaque fichier associé à une timeframe a bien un espacement
    temporel médian cohérent avec cette timeframe. Retourne un rapport
    {tf: {"file", "expected_minutes", "observed_minutes", "ok"}} à afficher
    à l'utilisateur -- essentiel pour détecter une confusion "1m" (minute)
    vs "1M"/"1Mo" (mois), qui est LA source d'erreur classique de ce dataset.
    """
    report = {}
    for tf, path in files.items():
        try:
            # nrows=sample_rows évite de charger un fichier entier (le
            # dataset Kaggle XAUUSD 1m fait plusieurs centaines de Mo) juste
            # pour estimer l'espacement temporel entre bougies.
            raw = load_kaggle_ohlcv_csv(path, nrows=sample_rows)
            deltas = raw["time"].diff().dropna().dt.total_seconds() / 60.0
            observed = float(deltas.median()) if len(deltas) else float("nan")
        except Exception as e:
            report[tf] = {"file": path, "error": str(e)}
            continue
        expected = TIMEFRAME_MINUTES[tf]
        # tolérance large (weekends/jours fériés faussent la médiane pour D1/W1/MN1)
        ok = expected * 0.3 <= observed <= expected * 3.5 if observed == observed else False
        report[tf] = {
            "file": os.path.basename(path), "expected_minutes": expected,
            "observed_minutes": round(observed, 2) if observed == observed else None,
            "ok": ok,
        }
    return report


def discover_files(folder: str) -> dict:
    """Scanne un dossier et associe automatiquement chaque timeframe connue
    au fichier CSV correspondant, par correspondance de motif délimité sur
    le nom de fichier. Retourne {"H1": "data/kaggle_gold/XAU_1h_data.csv", ...}.
    Utilisez ensuite `verify_timeframe_assignment` pour confirmer que
    l'association est cohérente avec les données réelles.
    """
    csv_files = glob.glob(os.path.join(folder, "*.csv"))
    found = {}
    for tf in TF_ORDER:
        for f in csv_files:
            name = os.path.basename(f).lower()
            for token in TF_TOKENS[tf]:
                pattern = _DELIM_BEFORE + re.escape(token) + _DELIM_AFTER
                if re.search(pattern, name):
                    found.setdefault(tf, f)
                    break
            if tf in found:
                break
    return found


def _compute_context_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule un petit jeu d'indicateurs condensés (pas la fenêtre
    complète) pour une timeframe utilisée comme CONTEXTE. On garde peu
    d'indicateurs par timeframe pour que l'espace d'observation de l'agent
    reste raisonnable même avec plusieurs timeframes de contexte."""
    df = df.copy()
    sma_20 = df["close"].rolling(20).mean()
    sma_50 = df["close"].rolling(50).mean()
    df["trend_signal"] = (sma_20 - sma_50) / df["close"]
    df["rsi_14"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["macd_diff"] = (macd.macd() - macd.macd_signal()) / df["close"]
    df["bb_pct"] = ta.volatility.BollingerBands(df["close"]).bollinger_pband()
    df["volatility_10"] = df["close"].pct_change().rolling(10).std()
    return df[["time"] + CONTEXT_INDICATOR_SUFFIXES]


def build_mtf_dataset(files: dict, primary_tf: str, context_tfs: list[str],
                       max_bars: int | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Construit le dataset fusionné multi-timeframe À PARTIR DE FICHIERS CSV
    (ex: le dataset Kaggle XAUUSD). Charge chaque fichier puis délègue la
    fusion à `fuse_mtf_frames` (réutilisée telle quelle pour fusionner des
    données récupérées EN DIRECT depuis MT5 -- voir demo_trader.py).

    Retourne (df, mtf_feature_columns) où `mtf_feature_columns` liste les
    colonnes de contexte ajoutées (ex: "H4_trend_signal", "D1_rsi_14", ...),
    à combiner avec FEATURE_COLUMNS (features de la timeframe primaire)
    pour construire l'environnement.
    """
    if primary_tf not in files:
        raise ValueError(f"Fichier introuvable pour la timeframe primaire '{primary_tf}'. "
                          f"Timeframes détectées : {list(files.keys())}")

    dfs = {primary_tf: load_kaggle_ohlcv_csv(files[primary_tf])}
    if max_bars:
        dfs[primary_tf] = dfs[primary_tf].tail(max_bars).reset_index(drop=True)

    for tf in context_tfs:
        if tf == primary_tf or tf not in files:
            if tf not in files:
                log.warning(f"Timeframe de contexte '{tf}' demandée mais aucun fichier trouvé -> ignorée.")
            continue
        dfs[tf] = load_kaggle_ohlcv_csv(files[tf])

    return fuse_mtf_frames(dfs, primary_tf, context_tfs)


def fuse_mtf_frames(dfs: dict, primary_tf: str, context_tfs: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Logique de fusion PURE (sans I/O), réutilisable avec n'importe quelle
    source de DataFrames OHLCV (fichiers CSV Kaggle chargés à l'avance, ou
    bougies récupérées en direct depuis MT5). `dfs` est un dict
    {timeframe_label: DataFrame OHLCV}.

    Anti-fuite d'information : chaque timeframe de contexte est décalée
    d'une bougie (on n'utilise que la dernière bougie déjà CLÔTURÉE).
    """
    if primary_tf not in dfs:
        raise ValueError(f"DataFrame introuvable pour la timeframe primaire '{primary_tf}'. "
                          f"Disponibles : {list(dfs.keys())}")

    df_primary = dfs[primary_tf]
    mtf_columns = []
    for tf in context_tfs:
        if tf == primary_tf or tf not in dfs:
            continue
        if TF_ORDER.index(tf) <= TF_ORDER.index(primary_tf):
            log.warning(f"'{tf}' n'est pas plus large que la timeframe primaire '{primary_tf}' "
                        f"-> ignorée comme contexte (voir README, section multi-timeframe).")
            continue

        ctx_feats = _compute_context_indicators(dfs[tf])

        # DÉCALAGE ANTI-FUITE : on utilise la bougie de contexte précédente
        # (déjà clôturée), jamais celle qui contient/chevauche l'instant présent.
        ctx_feats = ctx_feats.sort_values("time").reset_index(drop=True)
        ctx_feats[CONTEXT_INDICATOR_SUFFIXES] = ctx_feats[CONTEXT_INDICATOR_SUFFIXES].shift(1)

        renamed = {c: f"{tf}_{c}" for c in CONTEXT_INDICATOR_SUFFIXES}
        ctx_feats = ctx_feats.rename(columns=renamed)

        df_primary = pd.merge_asof(
            df_primary.sort_values("time"), ctx_feats.sort_values("time"),
            on="time", direction="backward",
        )
        mtf_columns.extend(renamed.values())
        log.info(f"Contexte '{tf}' fusionné sur la primaire '{primary_tf}' "
                 f"({len(renamed)} colonnes ajoutées).")

    df_primary[mtf_columns] = df_primary[mtf_columns].ffill().fillna(0.0)
    return df_primary, mtf_columns

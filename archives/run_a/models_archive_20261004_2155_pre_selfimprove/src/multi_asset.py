"""
multi_asset.py
===============
Infrastructure pour le protocole de validation croisée MULTI-ACTIFS (audit
institutionnel, section 4) : "Un Alpha robuste est universel. Si un modèle
ne fonctionne strictement que sur le XAUUSD, c'est qu'il a mémorisé le bruit
spécifique de l'Or."

ÉTAT DES DONNÉES (19/09) : ce module fournit l'infrastructure GÉNÉRIQUE
(chargement multi-symbole, construction d'un panier mixte décorrélé) --
AUCUNE donnée EURUSD/USDJPY/S&P500 n'existe encore dans ce dépôt (seul
`data/kaggle_gold/` est fourni). Chaque fonction ici est testée avec des
données SYNTHÉTIQUES (voir src/data_loader.py::generate_synthetic_ohlcv,
avec des seeds différentes comme substitut à "des symboles différents") en
attendant que de vraies données multi-actifs soient ajoutées -- voir
scripts/cross_asset_survival_test.py et scripts/build_mixed_basket.py pour
les outils prêts à l'emploi dès que ces données existeront.

CONVENTION DE DOSSIER (même schéma que `data/kaggle_gold/`, voir
src/data_loader.py) : un nouveau symbole se dépose dans son propre dossier,
ex. `data/kaggle_eurusd/`, avec un ou plusieurs CSV OHLCV (n'importe quel
format que `load_kaggle_ohlcv_csv` sait déjà lire -- Kaggle, export MT4/MT5,
etc., séparateur et colonnes auto-détectés).
"""
from __future__ import annotations
import glob
import os
import logging

import numpy as np
import pandas as pd

from src.data_loader import load_kaggle_ohlcv_csv
from src.stress_test import _rebase_and_concat
from src.features import add_technical_features, FEATURE_COLUMNS

log = logging.getLogger("multi_asset")

# Symbole "de référence" du projet -- seul symbole pour lequel le score
# fondamental (news/calendrier économique) a un sens (voir
# src/fundamental_feed.py, calibré sur l'or) : mis à zéro pour tout autre
# symbole (LOT 2, phase 4, point 5) plutôt que de laisser un signal fondé sur
# des news de l'or influencer un segment EURUSD/SPX.
GOLD_SYMBOL = "XAUUSD"


def discover_configured_symbols(cfg: dict) -> dict[str, str]:
    """Résout les symboles additionnels configurés (LOT 2, phase 4, point 10)
    en un dict {symbole: chemin_du_fichier}, en ne gardant QUE ceux dont le
    dossier existe réellement et contient au moins un CSV -- un dossier
    configuré mais absent/vide est journalisé clairement (pas une erreur) et
    simplement ignoré, jamais un crash : `multi_asset.enabled` peut rester
    `true` en configuration même avant que les vraies données n'arrivent, le
    système retombe alors silencieusement sur un fonctionnement OR SEUL.

    Format config attendu :
        multi_asset:
          enabled: true
          symbols:
            EURUSD: "data/kaggle_eurusd"
            SPX: "data/kaggle_spx"
    """
    multi_asset_cfg = cfg.get("multi_asset") or {}
    if not multi_asset_cfg.get("enabled", False):
        return {}
    configured = multi_asset_cfg.get("symbols") or {}
    resolved = {}
    for symbol, folder in configured.items():
        path = discover_symbol_folder(folder)
        if path is None:
            log.info(f"[multi-actifs] symbole '{symbol}' configuré (dossier '{folder}') mais introuvable/vide "
                      f"-- ignoré pour ce cycle, fonctionnement OR SEUL pour ce symbole.")
            continue
        resolved[symbol] = path
    return resolved


def discover_symbol_folder(folder: str) -> str | None:
    """Retourne le chemin d'UN fichier OHLCV trouvé dans `folder`, ou None si
    le dossier n'existe pas ou est vide -- cas d'usage SIMPLE (une seule
    timeframe par symbole), délibérément DIFFÉRENT de
    `src/multi_timeframe.py::discover_files` qui gère PLUSIEURS timeframes
    DU MÊME symbole : le protocole de validation croisée n'a besoin ici que
    d'UNE série de prix par symbole additionnel, pas d'une fusion
    multi-timeframe complète pour chacun. Si plusieurs CSV sont présents
    (ex: plusieurs timeframes déposées par habitude), retourne le premier
    trouvé par ordre alphabétique -- déterministe, mais l'appelant qui veut
    une timeframe précise devrait plutôt passer le chemin du fichier
    directement à `load_symbol_ohlcv`."""
    if not os.path.isdir(folder):
        return None
    candidates = sorted(glob.glob(os.path.join(folder, "*.csv")))
    return candidates[0] if candidates else None


def load_symbol_ohlcv(path: str) -> pd.DataFrame:
    """Charge un CSV OHLCV pour un symbole -- enveloppe fine autour de
    `src.data_loader.load_kaggle_ohlcv_csv` (déjà générique, ne fait aucune
    hypothèse liée à l'Or) : existe dans CE module pour la lisibilité/la
    découvrabilité de l'API multi-actifs, pas pour dupliquer sa logique."""
    return load_kaggle_ohlcv_csv(path)


def build_multi_asset_dataset(symbol_dfs: dict[str, pd.DataFrame], feature_columns: list[str] | None = None,
                                segment_len: int = 2000, warmup_bars: int = 50,
                                seed: int | None = None) -> pd.DataFrame:
    """Pipeline PAR SYMBOLE (LOT 2, phase 4, point 2 -- remplace l'ancienne
    approche de `build_mixed_basket_dataset`, qui calculait les features sur
    le dataframe déjà concaténé, un gap documenté dans sa propre docstring) :
    pour chaque symbole, calcule les features TECHNIQUES séparément (jamais
    sur le dataframe combiné), tire un segment contigu, purge les
    `warmup_bars` premières bougies (les indicateurs glissants ont besoin de
    cet historique pour être fiables -- purgées APRÈS calcul des features,
    jamais avant), ajoute les colonnes "symbol"/"segment_id", PUIS concatène
    (avec raccord de niveau de prix, voir `_rebase_and_concat` -- ne
    recalcule jamais un indicateur déjà calculé, ce qui est sans risque ici
    car toutes les features de `feature_columns` sont déjà invariantes au
    niveau de prix, voir tests/test_feature_invariance.py).

    "segment_id" (entier, 0-indexé par segment tiré) permet à TradingEnv de
    détecter les frontières et de ne jamais laisser un stop/PnL/récompense
    traverser une jointure entre deux symboles (voir TradingEnv, kwarg
    `segment_id_column`). "symbol" n'est PAS une feature d'observation --
    retiré avant construction de TradingEnv (voir `feature_columns`
    n'incluant ni l'un ni l'autre), utile seulement pour diagnostic/filtrage
    (EpisodicMemory, promotion sur la validation OR uniquement).

    Le score fondamental (`fundamental_score`) est mis à ZÉRO pour tout
    symbole différent de GOLD_SYMBOL (LOT 2, phase 4, point 5) : calibré sur
    des news spécifiques à l'or, un signal non nul sur un autre symbole
    serait trompeur, pas neutre.
    """
    rng = np.random.default_rng(seed)
    cols = list(feature_columns) if feature_columns is not None else FEATURE_COLUMNS
    segments = []
    for segment_idx, (symbol, raw_df) in enumerate(symbol_dfs.items()):
        if len(raw_df) == 0:
            log.warning(f"[multi-actifs] symbole '{symbol}' : dataframe vide, ignoré.")
            continue
        featured = add_technical_features(raw_df)
        if symbol != GOLD_SYMBOL and "fundamental_score" in featured.columns:
            featured["fundamental_score"] = 0.0
        n = len(featured)
        if n <= warmup_bars:
            log.warning(f"[multi-actifs] symbole '{symbol}' : {n} bougies après calcul des features, "
                        f"trop peu pour purger {warmup_bars} bougies de chauffe -- symbole ignoré.")
            continue
        target_len = segment_len + warmup_bars
        start = 0 if n <= target_len else int(rng.integers(0, n - target_len))
        segment = featured.iloc[start:start + target_len].reset_index(drop=True)
        segment = segment.iloc[warmup_bars:].reset_index(drop=True)
        if len(segment) == 0:
            continue
        segment["symbol"] = symbol
        segment["segment_id"] = segment_idx
        segments.append(segment)

    if not segments:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume", "symbol", "segment_id"] + cols)

    missing = [c for c in cols if c not in segments[0].columns]
    if missing:
        raise ValueError(f"Colonnes de features manquantes après add_technical_features : {missing}")

    return _rebase_and_concat(segments)


def training_basket_seed(style: str, generation: int) -> int:
    """Graine STABLE ET REPRODUCTIBLE pour le tirage des segments
    d'entraînement du panier multi-actifs (LOT 2, phase 4, point 7) --
    change à CHAQUE génération (contrairement à _stress_seed_for_style dans
    continuous_trainer.py, stable PAR STYLE pour comparer un candidat au
    même scénario adversarial) : ici on VEUT au contraire une diversité de
    segments d'un cycle à l'autre pour ne pas mémoriser une seule
    combinaison de segments. zlib.crc32 (jamais hash() -- randomisé par
    processus en Python 3, instable entre workers spawnés)."""
    import zlib
    return zlib.crc32(f"{style}_{generation}".encode()) & 0x7FFFFFFF


def build_training_basket(gold_df: pd.DataFrame, other_symbol_dfs: dict[str, pd.DataFrame],
                            style: str, generation: int, gold_fraction: float = 0.5,
                            segment_len: int = 2000, warmup_bars: int = 50) -> pd.DataFrame:
    """Panier d'ENTRAÎNEMENT (LOT 2, phase 4, point 7) : environ
    `gold_fraction` (50% par défaut) de bougies d'or, le reste réparti à
    parts égales entre les symboles de `other_symbol_dfs` -- graine
    `training_basket_seed(style, generation)`, donc les segments tirés
    CHANGENT à chaque génération (contrairement à la validation, qui doit
    rester FIXE d'une génération à l'autre pour que le score de promotion
    soit comparable dans le temps -- voir la constante `seed=0` conseillée
    pour un appel de validation, jamais `training_basket_seed`).

    Sans `other_symbol_dfs` (dict vide -- cas normal tant qu'aucune vraie
    donnée EURUSD/SPX n'est présente, voir discover_configured_symbols),
    retourne le dataset OR SEUL inchangé (features calculées, pas de
    colonnes symbol/segment_id ajoutées) -- comportement IDENTIQUE à
    l'entraînement mono-actif actuel."""
    if not other_symbol_dfs:
        return add_technical_features(gold_df)

    seed = training_basket_seed(style, generation)
    n_others = len(other_symbol_dfs)
    other_fraction = (1.0 - gold_fraction) / n_others if n_others else 0.0
    symbol_dfs = {GOLD_SYMBOL: gold_df, **other_symbol_dfs}
    fractions = {GOLD_SYMBOL: gold_fraction, **{s: other_fraction for s in other_symbol_dfs}}
    # segment_len PAR SYMBOLE, proportionnel à sa fraction cible du panier
    # total (garde `segment_len` comme taille de référence du panier
    # complet, pas par symbole individuel).
    total_target = segment_len
    per_symbol_dfs = {}
    for symbol, df in symbol_dfs.items():
        per_symbol_dfs[symbol] = df
    lens = {s: max(1, int(round(total_target * frac))) for s, frac in fractions.items()}
    combined_parts = []
    for symbol, df in per_symbol_dfs.items():
        part = build_multi_asset_dataset({symbol: df}, segment_len=lens[symbol],
                                           warmup_bars=warmup_bars, seed=seed + hash(symbol) % 1000)
        combined_parts.append(part)
    non_empty = [p for p in combined_parts if len(p) > 0]
    if not non_empty:
        return add_technical_features(gold_df)
    combined = _rebase_and_concat(non_empty)
    # segment_id réattribué de façon CONTIGUË sur le panier combiné final
    # (chaque appel à build_multi_asset_dataset ci-dessus recommençait à 0).
    offset = 0
    new_ids = np.zeros(len(combined), dtype=np.int64)
    pos = 0
    for part in non_empty:
        local_ids = part["segment_id"].to_numpy()
        remap = {old: offset + i for i, old in enumerate(sorted(set(local_ids)))}
        new_ids[pos:pos + len(part)] = [remap[v] for v in local_ids]
        offset += len(remap)
        pos += len(part)
    combined["segment_id"] = new_ids
    return combined


def stability_veto(style: str, model_path: str, meta: dict, stats: dict,
                     other_symbol_dfs: dict[str, pd.DataFrame], n_bars: int = 6000) -> tuple[bool, list[dict]]:
    """VETO DE PROMOTION (LOT 2, phase 4, point 8) : fait tourner le
    candidat, poids FIGÉS (jamais réentraîné), sur chaque symbole de
    `other_symbol_dfs` via scripts/cross_asset_survival_test.py::
    run_survival_test -- retourne (tous_stables, détails_par_symbole).

    Le SCORE de promotion reste calculé UNIQUEMENT sur la validation OR
    (voir continuous_trainer.py, inchangé) : ce veto n'ajoute JAMAIS de
    points, il peut seulement BLOQUER une promotion dont la courbe de
    capital s'effondre sur un autre symbole (voir run_survival_test,
    seuil de stabilité 30% de drawdown max -- pas de rentabilité exigée).

    Sans `other_symbol_dfs` (dict vide -- cas normal tant qu'aucune vraie
    donnée n'est présente), retourne (True, []) -- AUCUN veto, comportement
    IDENTIQUE à avant ce mécanisme. Une erreur sur un symbole donné (ex:
    colonnes de features manquantes, voir _check_feature_compatibility)
    est journalisée et traitée comme NON stable pour CE symbole -- jamais
    une exception qui remonterait jusqu'au cycle d'entraînement."""
    if not other_symbol_dfs:
        return True, []
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / "scripts"))
    from cross_asset_survival_test import run_survival_test

    details = []
    all_stable = True
    for symbol, df in other_symbol_dfs.items():
        try:
            result = run_survival_test(style, symbol, df, n_bars=n_bars,
                                         model_path=model_path, meta=meta, stats=stats)
            details.append(result)
            if not result["stable"]:
                all_stable = False
                log.warning(f"[veto multi-actifs] style '{style}' : instable sur '{symbol}' "
                            f"({result['verdict_reason']}) -- promotion bloquée.")
        except Exception as e:
            log.warning(f"[veto multi-actifs] style '{style}' sur '{symbol}' : test impossible "
                        f"({type(e).__name__}: {e}) -- traité comme instable (promotion bloquée) "
                        f"par prudence plutôt que silencieusement ignoré.")
            details.append({"symbol": symbol, "stable": False, "verdict_reason": f"erreur : {e}"})
            all_stable = False
    return all_stable, details


def build_mixed_basket_dataset(symbol_dfs: dict[str, pd.DataFrame], segment_len: int = 2000,
                                 seed: int | None = None) -> tuple[pd.DataFrame, list[int]]:
    """PANIER MIXTE DÉCORRÉLÉ (audit institutionnel, section 4, "Entraînement
    sur Panier Mixte") : construit un dataset combiné en concaténant, pour
    CHAQUE symbole de `symbol_dfs` (ex: {"XAUUSD": df1, "EURUSD": df2,
    "SPX": df3}), un segment CONTIGU de `segment_len` bougies tiré à un
    endroit ALÉATOIRE de son historique -- force l'entraînement à extraire
    des invariants structurels du prix plutôt que de mémoriser le bruit
    spécifique d'un seul instrument.

    Retourne `(combined_df, segment_boundaries)` où `segment_boundaries` est
    la liste des index de DÉBUT de chaque segment dans `combined_df` (utile
    à un futur appelant, ex. continuous_trainer.py, qui voudrait normaliser
    les features PAR SEGMENT plutôt que sur l'ensemble concaténé -- voir
    note ci-dessous).

    RACCORD DE PRIX ENTRE SEGMENTS (réutilise `_rebase_and_concat`, voir
    src/stress_test.py) : IMPORTANT -- contrairement à son usage d'origine
    (raccorder deux époques du MÊME symbole, où le raccord a un sens réel :
    "le marché de l'or a continué depuis ce niveau"), raccorder le niveau de
    prix entre des ACTIFS DIFFÉRENTS (or ~2000-4000$, EURUSD ~1.0-1.2,
    indice actions ~4000-6000) n'a AUCUNE signification économique -- il n'y
    a pas de "taux de change" cohérent entre eux. Ce raccord n'est fait ICI
    QUE pour éviter qu'un saut de prix artificiel (une bougie à 1.1 suivie
    d'une bougie à 2400) ne domine le calcul naïf d'un indicateur qui
    regarderait au-delà des frontières de segment (ex: une moyenne mobile
    calculée sur tout `combined_df` avant re-découpage). RECOMMANDATION
    (pour l'intégration future dans continuous_trainer.py) : calculer les
    features techniques et la normalisation z-score SÉPARÉMENT sur chaque
    segment (voir `segment_boundaries` retourné) AVANT toute concaténation,
    plutôt que sur `combined_df` dans son ensemble -- le signal
    d'apprentissage recherché ici est dans les FEATURES normalisées
    (schémas relatifs, invariants d'un actif à l'autre), jamais dans le
    niveau de prix absolu.

    Un symbole plus court que `segment_len` utilise l'intégralité de son
    historique disponible (avec un avertissement journalisé), plutôt que de
    lever une exception.
    """
    rng = np.random.default_rng(seed)
    segments = []
    for symbol, df in symbol_dfs.items():
        n = len(df)
        if n == 0:
            log.warning(f"[panier mixte] symbole '{symbol}' : dataframe vide, ignoré.")
            continue
        if n <= segment_len:
            log.warning(f"[panier mixte] symbole '{symbol}' : historique ({n} bougies) plus court que "
                        f"segment_len ({segment_len}) -- utilise l'intégralité de l'historique disponible.")
            segment = df.reset_index(drop=True)
        else:
            start = int(rng.integers(0, n - segment_len))
            segment = df.iloc[start:start + segment_len].reset_index(drop=True)
        segments.append(segment)

    if not segments:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"]), []

    segment_boundaries = []
    offset = 0
    for s in segments:
        segment_boundaries.append(offset)
        offset += len(s)

    combined = _rebase_and_concat(segments)
    return combined, segment_boundaries

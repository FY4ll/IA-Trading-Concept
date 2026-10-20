"""
cross_asset_survival_test.py
==============================
TEST DE SURVIE TRANSVERSAL (audit institutionnel, section 4, "Sans
Réentraînement") : charge les poids optimisés d'un champion XAUUSD déjà
entraîné (voir models/champion_<style>/) et le fait tourner DIRECTEMENT
(sans la moindre mise à jour de poids) sur les données d'un AUTRE symbole
(EURUSD, USDJPY...) sur ~6000 bougies.

OBJECTIF (cité du cahier des charges) : "L'IA n'a pas besoin d'être
hyper rentable ici, mais sa courbe de capital doit rester stable. Ce test
valide la robustesse intrinsèque de votre gestion des risques." -- ce script
reporte donc en priorité la STABILITÉ (drawdown maximal, absence
d'effondrement) plutôt que le rendement brut.

ÉTAT DES DONNÉES (19/09) : aucune donnée EURUSD/USDJPY/S&P500 n'existe
encore dans ce dépôt. Utilisez `--synthetic-demo` pour exécuter le script
de bout en bout avec des données synthétiques (voir
src/data_loader.py::generate_synthetic_ohlcv) en attendant -- dès qu'un
vrai historique est disponible, déposez son/ses CSV dans un dossier dédié
(ex: data/kaggle_eurusd/, même convention que data/kaggle_gold/) et utilisez
`--symbol-folder`/`--symbol-name`.

LIMITATION IMPORTANTE (feature_columns) : le meta.json d'un champion
enregistre EXACTEMENT les colonnes de features sur lesquelles il a été
entraîné -- si ce champion utilise un contexte multi-timeframe (colonnes
comme "rsi_14_4H", "trend_signal_1D"), un CSV mono-timeframe pour le nouveau
symbole ne peut PAS fournir ces colonnes, et ce script s'arrête avec un
message d'erreur explicite plutôt que de continuer avec des features
manquantes/incorrectes (voir `_check_feature_compatibility`) -- un test
"transversal" silencieusement construit sur des features fausses ne
prouverait rien.

Lancement :
  python scripts/cross_asset_survival_test.py --synthetic-demo --style M15
  python scripts/cross_asset_survival_test.py --style M15 \\
      --symbol-folder data/kaggle_eurusd --symbol-name EURUSD --n-bars 6000
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.multi_asset import discover_symbol_folder, load_symbol_ohlcv
from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, normalize_features
from src.trading_env import TradingEnv
from src.agent import TradingAgent
from src.backtester import run_episode, compute_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CROSS-ASSET] [%(name)s] %(message)s")
log = logging.getLogger("cross_asset_survival_test")

MODELS_ROOT = "models"


def _champion_paths(style: str) -> tuple[str, str, str]:
    d = f"{MODELS_ROOT}/champion_{style}"
    return f"{d}/agent", f"{d}/meta.json", f"{d}/norm_stats.json"


def _load_champion_meta(style: str) -> dict:
    _, meta_path, _ = _champion_paths(style)
    if not Path(meta_path).exists():
        raise FileNotFoundError(
            f"Aucun champion trouvé pour le style '{style}' ({meta_path} introuvable) -- "
            f"vérifiez que l'entraînement continu a déjà produit un champion pour ce style."
        )
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f)


def _load_norm_stats(style: str) -> dict:
    _, _, stats_path = _champion_paths(style)
    with open(stats_path, encoding="utf-8") as f:
        raw = json.load(f)
    # Sérialisées comme des listes [mean, std] (voir continuous_trainer.py) --
    # reconverties en tuples pour normalize_features.
    return {k: tuple(v) for k, v in raw.items()}


def _check_feature_compatibility(champion_feature_columns: list[str], available_columns: set[str]) -> list[str]:
    """Retourne la liste des colonnes MANQUANTES (vide = compatible). Un
    champion entraîné avec du contexte multi-timeframe (colonnes comme
    "rsi_14_4H") ne peut pas être testé équitablement sur un CSV
    mono-timeframe qui ne les fournit pas -- voir docstring du module."""
    return [c for c in champion_feature_columns if c not in available_columns]


def run_survival_test(style: str, symbol_name: str, target_df, n_bars: int = 6000,
                       window_size: int = 50, model_path: str | None = None,
                       meta: dict | None = None, stats: dict | None = None) -> dict:
    """Cœur testable du script (voir tests/test_cross_asset_survival.py) --
    `target_df` est déjà un DataFrame OHLCV brut (colonnes time/open/high/
    low/close/volume) pour le symbole cible, quelle que soit sa source
    (réelle ou synthétique).

    `model_path`/`meta`/`stats` (LOT 2, phase 4, point 8) : quand fournis,
    remplacent le chargement par défaut depuis `models/champion_<style>/`
    (voir _champion_paths) -- permet de tester un CANDIDAT pas encore promu
    champion (veto de promotion, voir src/multi_asset.py::stability_veto),
    sans jamais avoir à l'écrire d'abord à l'emplacement du champion. `None`
    (défaut) = comportement D'ORIGINE inchangé (charge le champion déjà
    promu de ce style).

    Retourne un dict avec les métriques (voir src.backtester.compute_metrics)
    PLUS un verdict de stabilité explicite (`stable`, `verdict_reason`).
    """
    if meta is None:
        meta = _load_champion_meta(style)
    if stats is None:
        stats = _load_norm_stats(style)
    feature_columns = meta["feature_columns"]
    if model_path is None:
        model_path, _, _ = _champion_paths(style)

    df = target_df.tail(n_bars).reset_index(drop=True) if len(target_df) > n_bars else target_df
    if len(df) < n_bars:
        log.warning(f"'{symbol_name}' : seulement {len(df)} bougies disponibles (moins que les "
                    f"{n_bars} demandées) -- test effectué sur l'historique disponible en entier.")

    df = add_technical_features(df)  # pas de fondamental pour un symbole hors XAUUSD ici (score neutre)

    missing = _check_feature_compatibility(feature_columns, set(df.columns))
    if missing:
        raise ValueError(
            f"Le champion '{style}' a été entraîné avec {len(feature_columns)} colonnes de features, "
            f"dont {len(missing)} absentes des données de '{symbol_name}' (contexte multi-timeframe "
            f"manquant) : {missing}. Un test transversal équitable nécessite soit (a) des fichiers "
            f"multi-timeframe pour '{symbol_name}' (comme data/kaggle_gold/, voir "
            f"src/multi_timeframe.py), soit (b) un champion entraîné SANS contexte multi-timeframe pour "
            f"cette comparaison. Aucune valeur n'a été substituée silencieusement."
        )

    # RÉUTILISE LES STATS DE NORMALISATION DU CHAMPION (jamais réajustées sur
    # les données du nouveau symbole) -- c'est ce qui fait de ce test un
    # vrai "sans réentraînement" : le modèle voit des features normalisées
    # exactement comme il les a apprises, pas re-calibrées pour l'avantager.
    df_norm, _ = normalize_features(df, stats=stats, columns=feature_columns)

    env = TradingEnv(df_norm, window_size=window_size, feature_columns=feature_columns, style=style)
    agent = TradingAgent.load(model_path, env, {"algo": meta.get("algo", "PPO")})
    env = run_episode(agent, env)
    metrics = compute_metrics(env, timeframe=style)

    # VERDICT DE STABILITÉ (voir docstring du module -- pas la rentabilité) :
    # seuil repris de la pratique courante (au-delà, un drawdown est
    # généralement considéré comme un effondrement, pas une fluctuation
    # normale) -- volontairement plus permissif que
    # `validation.max_drawdown_allowed` (20% sur l'instrument D'ORIGINE),
    # puisqu'on ne s'attend PAS à ce que ce test soit aussi bon que sur
    # l'instrument d'entraînement, seulement qu'il ne s'effondre pas.
    stable = metrics["max_drawdown"] <= 0.30
    metrics["stable"] = stable
    metrics["verdict_reason"] = (
        f"drawdown maximal {metrics['max_drawdown']:.1%} "
        f"{'sous' if stable else 'AU-DESSUS DE'} le seuil de stabilité (30%)"
    )
    metrics["symbol"] = symbol_name
    metrics["style"] = style
    metrics["n_bars_tested"] = len(df_norm)
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--style", default="M15", help="Style/timeframe du champion à tester (ex: M15, H1, D1).")
    parser.add_argument("--symbol-folder", default=None,
                         help="Dossier contenant le(s) CSV OHLCV du symbole cible (ex: data/kaggle_eurusd).")
    parser.add_argument("--symbol-name", default=None, help="Nom du symbole cible (ex: EURUSD).")
    parser.add_argument("--n-bars", type=int, default=6000, help="Nombre de bougies à tester (défaut : 6000).")
    parser.add_argument("--synthetic-demo", action="store_true",
                         help="Utilise des données synthétiques (pas de dépendance à un vrai CSV) pour "
                              "démontrer/tester le script de bout en bout.")
    args = parser.parse_args()

    if args.synthetic_demo:
        log.info("Mode --synthetic-demo : données synthétiques utilisées à la place d'un vrai symbole "
                  "(aucune donnée EURUSD/USDJPY/S&P500 réelle n'est encore disponible dans ce dépôt).")
        target_df = generate_synthetic_ohlcv(n_bars=args.n_bars + 500, seed=999)
        symbol_name = "SYNTHETIC"
    else:
        if not args.symbol_folder or not args.symbol_name:
            parser.error("--symbol-folder et --symbol-name sont requis sans --synthetic-demo.")
        csv_path = discover_symbol_folder(args.symbol_folder)
        if csv_path is None:
            parser.error(
                f"Aucun CSV trouvé dans '{args.symbol_folder}'. Déposez-y un ou plusieurs fichiers OHLCV "
                f"(même format que data/kaggle_gold/, séparateur/colonnes auto-détectés)."
            )
        log.info(f"Chargement de '{csv_path}' pour le symbole '{args.symbol_name}'...")
        target_df = load_symbol_ohlcv(csv_path)
        symbol_name = args.symbol_name

    try:
        metrics = run_survival_test(args.style, symbol_name, target_df, n_bars=args.n_bars)
    except (FileNotFoundError, ValueError) as e:
        log.error(str(e))
        sys.exit(1)

    log.info(f"=== Résultat : champion '{args.style}' sur '{symbol_name}' "
             f"({metrics['n_bars_tested']} bougies testées) ===")
    log.info(f"  Rendement total : {metrics['total_return']:+.2%}")
    log.info(f"  Sharpe : {metrics['sharpe']:.2f} | Sortino : {metrics.get('sortino', float('nan')):.2f}")
    log.info(f"  Drawdown maximal : {metrics['max_drawdown']:.2%}")
    log.info(f"  Nombre de trades : {metrics['n_trades']}")
    log.info(f"  VERDICT : {'STABLE' if metrics['stable'] else 'INSTABLE'} -- {metrics['verdict_reason']}")


if __name__ == "__main__":
    main()

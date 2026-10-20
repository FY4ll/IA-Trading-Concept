"""
build_mixed_basket.py
=======================
Démonstration/prévisualisation du PANIER MIXTE DÉCORRÉLÉ (audit
institutionnel, section 4, "Entraînement sur Panier Mixte") -- construit un
dataset combiné à partir des symboles configurés ci-dessous et affiche un
résumé, en attendant l'intégration complète dans le cycle d'entraînement
continu (src/continuous_trainer.py) une fois que de vraies données
multi-actifs existent.

ÉTAT DES DONNÉES (19/09) : seul XAUUSD (data/kaggle_gold/) est disponible
dans ce dépôt. Ce script SAUTE gracieusement tout symbole dont le dossier
configuré n'existe pas -- avec un seul symbole présent, le résultat ne peut
PAS tester la décorrélation multi-actifs (c'est un panier "mixte" d'un seul
actif), mais le script reste exécutable de bout en bout pour vérifier que
l'infrastructure fonctionne.

Pour ajouter un symbole : déposez son/ses CSV dans le dossier correspondant
ci-dessous (SYMBOL_FOLDERS), même convention que data/kaggle_gold/.

Lancement : python scripts/build_mixed_basket.py
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.multi_asset import discover_symbol_folder, load_symbol_ohlcv, build_mixed_basket_dataset
from src.features import add_technical_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PANIER-MIXTE] [%(name)s] %(message)s")
log = logging.getLogger("build_mixed_basket")

# À ÉTENDRE au fur et à mesure que des données multi-actifs sont ajoutées --
# voir docstring du module pour la convention de dossier.
SYMBOL_FOLDERS = {
    "XAUUSD": "data/kaggle_gold",
    "EURUSD": "data/kaggle_eurusd",
    "SPX": "data/kaggle_spx",
}

SEGMENT_LEN = 2000
OUTPUT_PATH = "data/mixed_basket_preview.csv"


def main():
    symbol_dfs = {}
    for symbol, folder in SYMBOL_FOLDERS.items():
        csv_path = discover_symbol_folder(folder)
        if csv_path is None:
            log.warning(f"'{symbol}' : aucun CSV trouvé dans '{folder}' -- ignoré pour cet aperçu.")
            continue
        log.info(f"'{symbol}' : chargement de '{csv_path}'...")
        symbol_dfs[symbol] = load_symbol_ohlcv(csv_path)

    if not symbol_dfs:
        log.error("Aucun symbole disponible -- rien à construire.")
        sys.exit(1)
    if len(symbol_dfs) < len(SYMBOL_FOLDERS):
        log.warning(f"Seulement {len(symbol_dfs)}/{len(SYMBOL_FOLDERS)} symbole(s) configuré(s) trouvé(s) "
                    f"({sorted(symbol_dfs.keys())}) -- le résultat ne teste pas encore la décorrélation "
                    f"multi-actifs complète.")

    combined, boundaries = build_mixed_basket_dataset(symbol_dfs, segment_len=SEGMENT_LEN, seed=42)
    log.info(f"Panier mixte construit : {len(combined)} bougies au total, "
             f"{len(boundaries)} segment(s) (frontières : {boundaries}).")

    combined_with_features = add_technical_features(combined)
    log.info(f"Features techniques calculées : {len(combined_with_features)} bougies utilisables "
             f"(après suppression des lignes de warmup NaN).")

    combined_with_features.to_csv(OUTPUT_PATH, index=False)
    log.info(f"Aperçu sauvegardé dans '{OUTPUT_PATH}' -- INSPECTION MANUELLE recommandée avant toute "
             f"utilisation en entraînement (voir docstring de build_mixed_basket_dataset : normaliser "
             f"idéalement PAR SEGMENT, pas sur l'ensemble concaténé).")


if __name__ == "__main__":
    main()

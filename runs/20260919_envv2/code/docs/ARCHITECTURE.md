# Architecture cible — AUREXIS v3 (plan du 08/10/2026)

## Pourquoi
Un mois d'ajouts au coup par coup : 8 styles d'IA successifs, 16 500 lignes dans 57 modules (8 morts), 4 fichiers
géants (entraînement 1 966 lignes, connecteur MT5 1 652, trading 1 503, simulateur 1 322), 38 scripts, une
configuration de 1 500 lignes, 775 dossiers de projet dont l'essentiel en archives. Plus personne (ni l'utilisateur,
ni Claude) ne voit d'un coup d'œil comment l'ensemble tient. Objectif : **une seule IA, une seule méthode, un seul
juge, un seul chemin du marché à l'ordre**, chaque pièce avec un rôle et un seul.

## Principes
0. **Une intelligence artificielle qui apprend, pas un robot à règles.** L'IA apprend seule quand entrer, dans quel
   sens, où sortir et sur quels marchés. Aucune règle de trading écrite à la main dans le chemin de décision (la
   « discipline de tendance » de l'ancien AUREX n'existe pas dans v3). Seules les limites FTMO (perte du jour, perte
   totale, taille des positions) sont fixes, comme protection du compte.
   **Univers = tous les marchés FTMO** (devises, métaux, indices, énergies, cryptos) ; chaque marché s'ouvre quand
   l'IA y réussit l'examen.
1. **Une couche = un rôle.** Une couche n'appelle que celle du dessous. Aucun « style » historique.
2. **Le même code à l'entraînement et en direct** (données, vision, simulateur) : ce que l'IA apprend est exactement
   ce qu'elle voit en réel.
3. **Un seul juge orienté FTMO**, identique pour sélectionner, autoriser un marché et décider d'un challenge.
4. **Chaque marché s'ouvre séparément** quand l'IA y réussit l'examen (or, S&P 500, bitcoin…), avec un plafond
   de risque commun au compte.
5. **Configuration courte** (< 200 lignes), sans historique en commentaires (l'historique va dans `docs/JOURNAL.md`).
6. **La recherche reste à part** (`recherche/`) : rien n'entre en production sans examen réussi.

## Arborescence cible (dossier neuf `Test_IA/aurexis/`)
```
aurexis/
  config.yaml                 réglages (marchés, risque FTMO, entraînement, notifications)
  lancer.py                   point d'entrée unique : trader | entrainer | examiner | etat
  donnees/      (1) sources.py (MT5, Dukascopy, FRED) · reserve.py (un format par marché, mise à jour auto)
  vision/       (2) indicateurs.py · trader.py (niveaux, structure, outils) · normalisation.py
  cerveau/      (3) simulateur.py (positions, stops, objectifs, coûts, taille au risque) · politique.py (LSTM)
                    apprentissage.py (une seule méthode + une seule récompense) · memoire.py (souvenirs par IA)
  juge/         (4) examen.py (petit examen tiré au sort + examen complet multi-marchés + activité minimale)
                    selection.py (évolution, veines, champion, autorisation par marché)
  execution/    (5) courtier.py (MT5, ordres) · risque.py (règles FTMO, tailles, plafonds jour/total)
                    decideur.py (boucle : un marché autorisé -> une décision par bougie) · narrateur.py
  surveillance/ (6) journal.py (décisions, trades) · gardien.ps1 · rapport.py (bilans dans la conversation)
  recherche/       études hors production (moteur de prédiction, flux des ordres, devises…)
  tests/           un fichier par couche + tests d'équivalence avec l'ancien système
  modeles/         champion/, veines/, historique/ (rien d'autre)
```

## Ce qu'on garde (repris et simplifié) / ce qui part
| Couche | Repris de Run A | Abandonné |
|---|---|---|
| 1 Données | `aurexis_data` (chargement, miroirs, mélangeur), `live_data_feed`, `fred_feed`, `fetch_dukascopy` | fichiers Kaggle M15 (remplacés par Dukascopy/MT5), `fundamental_feed`/`finbert_sentiment` (aucun apport mesuré) |
| 2 Vision | `features`, `multi_timeframe`, `trader/vision`, `trader/toolbox`, `cross_asset` | `trader/chart`, `trader/engine`, `trader/playbook`, `trader/discovery`, `market_brain` |
| 3 Cerveau | `trading_env` (sans les options mortes), `policy_networks`, `agent`, `fast_eval`, `memory_features`, `episodic_memory`, `shared_data` | styles H1/H1T/H1X/H1XT/TRADER/M30/H4/D1, GARCH, `network_growth` (-> recherche) |
| 4 Juge | `_multi_market_score`, `_two_stage_exam`, veines, activité minimale, `ftmo_metrics`, `lockbox_gate` (seuils) | `backtester` multi-fenêtres historique en double, `multi_asset` (veto remplacé par l'examen multi-marchés), WFE, `lockbox_analysis` |
| 5 Exécution | `mt5_connector` (ordres, stops, limites — allégé), `risk_profile`, `account_guard`, `risk_guard`, `live_narrator`, `state_reconciliation` | hiérarchie entre styles, coordination/conflits, familles exclusives, rollback par style, 15 anciennes règles |
| 6 Surveillance | `decision_journal`, `trade_sync`, `notifier`, `watchdog.ps1`, `scripts/progression_aurexis.py` | tableaux de bord, rapports HTML |

## Étapes (le système actuel continue de tourner jusqu'à la bascule)
0. **Rangement (fait le 08/10)** : archives regroupées dans `Test_IA/archives/` ; racine propre.
1. **Couches 1-2** : réserve de données unique + vision. *Preuve* : mêmes 200 variables, valeur pour valeur, que
   l'ancien système sur l'or et 3 autres marchés. **FAIT le 08/10 22h10** : `aurexis/donnees/` (catalogue de
   46 marchés FTMO, réserve .npz, inversion, mélangeur, FRED) + `aurexis/vision/` (indicateurs, unités de temps,
   vision du trader, boîte à outils, macro, fabrique) ; `aurexis/tests/test_vision_equivalence.py` : 6/6 identiques
   (or, euro-dollar, bitcoin, DAX, S&P 500 inversé, mélangeur). Reste : mise à jour automatique de la réserve
   (Dukascopy + MT5 en direct), chemins de cache relatifs de `vision/trader.py` à rendre absolus.
2. **Couches 3-4** : simulateur + juge. *Preuve* : le champion actuel obtient la même note à l'examen dans les deux
   systèmes (à 1 % près).
3. **Couche 5 en démo à blanc** sur tous les marchés, à côté de l'ancien système (aucun ordre).
4. **Bascule** : le nouveau système entraîne AUREXIS ; AUREX passe dans la couche 5 (or) ; l'ancien Run A s'arrête.
   Critère : 48 h de démo à blanc sans écart de décision avec l'ancien système sur l'or.

## Règles de travail
- Toute nouvelle idée : dire dans quelle couche elle entre, sinon elle ne se fait pas.
- Un changement = un test qui le prouve + une mesure avant/après.
- Les résultats de recherche négatifs sont notés dans `docs/JOURNAL.md` (pour ne pas refaire).

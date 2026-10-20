# Rapport LOT 2 — Archivage, environnement v2, pipeline multi-paires, réentraînement

Suite du lot 1 (`RAPPORT_AUDIT_TACHES_1_7.md`, 235 tests verts). Ce lot change l'espace d'observation/l'espace d'action de manière volontaire (ENV_VERSION 1 → 2) : le warm-start est intentionnellement rompu, les 5 styles seront réentraînés de zéro.

**Bilan final : 398/398 tests verts**, toutes les phases 0 à 8 sont faites. `git` reste inaccessible depuis mes outils sur cette machine — rien n'est committé, tout est dans l'arbre de travail (voir tableau des fichiers en fin de rapport).

---

## Phase 0 — Archivage : fait, validé par toi

`archive/20260919_1949_pre_lot2/` (354.6 Mo, 236 fichiers, verrouillé en lecture seule) + complément (`kaggle_gold_hashes.json`, empreinte de 505 Mo de données sans les copier). `scripts/restore_archive.py` testé (dry-run, restauration réelle, détection de corruption).

## Phase 1 — ENV_VERSION et jeu sous clé : fait

- `ENV_VERSION = 2` (src/trading_env.py), écrit dans le meta.json de chaque champion/slot promu.
- **Gating à 4 points** : `TradingAgent.load` (refuse par exception), `TradingAgent._warm_start` (dégrade silencieusement vers un agent neuf, comme le comportement d'origine sur incompatibilité), `_scan_eligible_styles` et `_StyleRuntime.maybe_reload` (démo, filet de sécurité redondant). Un meta.json sans `env_version` (tous les champions actuels) = version 1 implicite, rejeté automatiquement.
- **Jeu sous clé** : `data.lockbox_start` (défaut : 15% les plus récents de l'historique or, arrondi au début du mois — calculé automatiquement et affiché au démarrage). `src/data_loader.py::split_lockbox` exclut ces données de `chronological_split`. `scripts/lockbox_eval.py <style>` évalue un champion dessus, journalise dans `logs/lockbox_journal.jsonl`, jamais appelé automatiquement.
- ⚠️ **Bug réel trouvé et corrigé pendant l'essai à blanc (phase 7)** : la date de lockbox est unique pour tous les styles, mais un style dont la fenêtre de données utilisée est limitée (`max_bars`/`max_bars_by_style`) peut se retrouver ENTIÈREMENT postérieure à cette date (ex: M15, historique récent seulement) → train_df vide → crash immédiat au premier `reset()`. Corrigé : si moins de 100 bougies restent visibles pour un style, le lockbox est désactivé pour CE style/CE cycle uniquement (log clair), jamais un crash. Testé (`tests/test_lockbox.py`, 8 tests).

Tests dédiés : `tests/test_lockbox.py` (8), `tests/test_env_version.py` (11).

## Phase 2 — Module de risque unique : fait

`src/risk_engine.py` : fonctions **pures, déterministes, sans I/O** (`lots_from_risk`, `notional_lots`, `round_volume`, `tighten_stop_or_cancel`, `atr_stop_distance_pct`, dataclass `SymbolSpec`) — extraites EXACTEMENT des formules déjà en place dans `MT5Connector` (jamais de nouvelle règle inventée).

- `MT5Connector` délègue maintenant à ce module — **tous les tests existants passent SANS MODIFICATION** (`test_account_guard_send_order.py`, `test_mt5_live_infra.py`, `test_stop_loss_buckets.py`), confirmant un comportement strictement identique.
- `TradingEnv` gagne une méthode `simulate_broker_sizing()` utilisant le même moteur (plancher de lot, resserrement, annulation) — `None` par défaut (comportement d'origine si aucun `symbol_spec` n'est configuré).
- **Preuve de parité** : `tests/test_risk_parity.py` (9 tests) — sur une grille d'entrées, `TradingEnv` et `MT5Connector` produisent EXACTEMENT la même décision (lot, stop, annulation).

Tests dédiés : `tests/test_risk_engine.py` (28), `tests/test_risk_parity.py` (9).

## Phase 3 — Stop en multiples d'ATR : fait (partait déjà bien avancé)

Découverte en phase 0 : le stop ATR dynamique était **déjà actif en production** (`atr_stop_loss: true`, daté du jour même). Ce qui restait réellement à faire :

1. **Multiples recalculés par style** (pas une échelle unique) : mesuré sur l'historique or réel (médiane ATR/prix par bougie) à quels multiples correspondaient les anciens buckets % — l'ancienne échelle unique `[0.5,1.0,1.5,2.5,4.0]` était jusqu'à 4-5x trop serrée pour les timeframes courtes. Nouvelles valeurs par style (même cardinalité, 5 par style) :

   | style | anciens multiples | nouveaux multiples |
   |---|---|---|
   | M15 | 0.5 / 1.0 / 1.5 / 2.5 / 4.0 | 2.5 / 4.0 / 6.5 / 10.0 / 16.5 |
   | M30 | 0.5 / 1.0 / 1.5 / 2.5 / 4.0 | 1.5 / 3.0 / 4.5 / 7.0 / 11.0 |
   | H1  | 0.5 / 1.0 / 1.5 / 2.5 / 4.0 | 2.0 / 4.0 / 8.0 / 12.0 / 20.0 |
   | H4  | 0.5 / 1.0 / 1.5 / 2.5 / 4.0 | 1.0 / 2.0 / 4.0 / 6.0 / 10.0 |
   | D1  | 0.5 / 1.0 / 1.5 / 2.5 / 4.0 | 0.75 / 1.5 / 3.0 / 5.0 / 7.0 |

2. **Pas d'ouverture si ATR indisponible** : `TradingEnv.step()` bloque toute NOUVELLE ouverture (jamais une clôture, jamais une position déjà ouverte) si le stop ATR est requis mais indisponible pour ce pas précis.
3. **Bug réel corrigé** : `demo_trader.py::decide()` décodait TOUJOURS le bucket choisi via la table STATIQUE en %, même en mode ATR — écart entraînement/live actif en production. Corrigé : `decide()` transmet désormais le MULTIPLE choisi (pas une distance pré-résolue) ; `MT5Connector.send_order` le résout en distance via `risk_engine`, avec refus d'ouverture si l'ATR live est indisponible au moment de l'exécution.

Tests dédiés : `tests/test_atr_stop_loss_buckets.py` (17, remplace `test_stop_loss_buckets.py` comme test primaire — l'ancien fichier annoté comme couvrant désormais le repli statique seulement), `tests/test_atr_live_wiring.py` (6).

## Phase 4 — Features invariantes et pipeline multi-paires : fait

1. **Audit d'invariance** : `atr_14` (unités de prix brutes) était la SEULE feature dépendante du niveau de prix — remplacée dans `FEATURE_COLUMNS` par `atr_pct` (= atr_14/close, sans dimension). `atr_14` brut reste disponible séparément pour le mécanisme de stop ATR (jamais vu par l'agent). Toutes les autres features étaient déjà invariantes (vérifié, pas supposé).
2. **Pipeline par symbole** : `src/multi_asset.py::build_multi_asset_dataset` — features calculées PAR SEGMENT avant concaténation (corrige le gap documenté dans l'ancienne `build_mixed_basket_dataset`), colonnes `symbol`/`segment_id` ajoutées, purge de chauffe par segment.
3. **TradingEnv** : à chaque frontière de segment, position forcée à plat SANS réaliser de PnL, épisode terminé — jamais un stop/PnL/récompense ne traverse une jointure. `reset()` choisit un segment au hasard (comportement d'origine inchangé sans colonne `segment_id`).
4. **Coût par ligne** : colonne optionnelle `spread_pct` remplace `transaction_cost` comme base si présente.
5. **Fondamental à zéro sur non-or** : `fundamental_score` forcé à 0.0 pour tout symbole ≠ XAUUSD.
6. **Coupure calendaire commune** : `src/data_loader.py::split_by_calendar_dates` applique les MÊMES dates absolues à tous les symboles, quelle que soit la longueur de leur historique.
7. **Panier d'entraînement** : `build_training_basket` (~50% or, graine = f(style, génération) — change à chaque génération, contrairement à la validation qui doit rester fixe).
8. **Veto de promotion câblé** : `stability_veto` (poids figés, via `scripts/cross_asset_survival_test.py::run_survival_test`, étendu pour accepter un candidat pas encore promu) appelé dans `continuous_trainer.py` **avant** toute promotion (slot ET champion public) — bloque si instable sur un autre symbole, ne touche JAMAIS le fichier de poids si le veto échoue. Un bug latent pré-existant trouvé en même temps (`overall_best["score"]` pouvait lever un KeyError si aucun style n'a de champion) corrigé au passage.
9. **EpisodicMemory** : colonne `symbol` (migration automatique), `demo_trader.py` n'interroge que l'or (`symbols=["XAUUSD"]`, inclut les lignes historiques `symbol=NULL`).
10. **Config `multi_asset.enabled`** (défaut `false`) : `discover_configured_symbols` ignore gracieusement un dossier configuré mais absent/vide.

Aucune vraie donnée EURUSD/SPX n'existe encore dans ce dépôt (voir `data/README_MULTI_PAIRES.md`) — tout testé avec des données synthétiques, `multi_asset.enabled: false` par défaut donc **aucun changement de comportement actuel**.

Tests dédiés : `tests/test_feature_invariance.py` (14), `tests/test_multi_asset_pipeline.py` (13), `tests/test_multi_asset_composition.py` (14), `tests/test_episodic_memory_symbol.py` (5), `tests/test_stability_veto.py` (4), `tests/test_multi_asset_promotion_veto.py` (3).

## Phase 5 — Frictions calibrables : fait

`frictions.profile` : `"pessimistic"` (défaut, valeurs actuelles inchangées) ou `"calibrated"` (lit `data/friction_calibration.json`, produit par `scripts/slippage_report.py` à partir des VRAIS ordres réels journalisés — repli silencieux sur pessimiste si absent). Seul `slippage_price_range` est calibrable (directement mesuré) ; `spread_multiplier_range` reste toujours pessimiste (non mesurable depuis le journal actuel — honnêteté plutôt qu'une calibration inventée). `scripts/friction_sensitivity.py` : évalue un champion à x0.5/x1/x2, tableau par style.

Tests dédiés : `tests/test_friction_sensitivity.py` (10).

## Phase 6 — Métriques : fait

- `compute_walk_forward_efficiency` renvoie désormais aussi `is_n_trades`, `oos_n_trades`, `reason` (explication si `wfe=None`), `suspect` (`wfe > 1.5` ou trades OOS insuffisants) — toutes les clés d'origine préservées.
- `scripts/leakage_shuffle_test.py --seeds N` (défaut 10) : moyenne/écart-type/min/max/nombre de graines > 0 sur N graines de mélange indépendantes, testé en conditions réelles (voir ci-dessous).

Tests dédiés : `tests/test_wfe_enriched.py` (7), `tests/test_leakage_shuffle_seeds.py` (4).

## Phase 7 — Réentraînement du week-end

1. **pytest complet** : 398/398 verts.
2. **Copie figée** : `runs/20260919_envv2/code/` (copie complète src/, scripts/, tests/, autonomous_agent.py, config/).
3. **Reprise après coupure** (vérifiée, pas de correctif nécessaire) : `ContinuousEvolutionTrainer.__init__` relit déjà `_progress.json` + le meta/search_state de CHAQUE slot au démarrage — un redémarrage (watchdog `run_forever.ps1`) reprend exactement où il en était, jamais de zéro.
4. **Essai à blanc** (une génération courte par style, `timesteps_per_cycle: 6000` config réelle → 12000 en marché fermé) :

   | style | durée mesurée | notes |
   |---|---|---|
   | M15 | ~3min05 | 42 features, 6 timeframes de contexte |
   | M30 | ~1min56 | 37 features, 5 timeframes de contexte |
   | H1  | interrompu à 80% (~2min estimé) | arrêté pour ne plus déclencher de notifications ntfy pendant la mesure |
   | H4, D1 | non mesurés | même ordre de grandeur attendu (moins de contexte à fusionner, LSTM domine le coût quel que soit le style) |

   ⚠️ Mesuré en **séquentiel, 1 seul worker** (pour isoler le coût par style) — le run réel utilisera `continuous.parallel_workers: 6` avec les 5 styles EN PARALLÈLE, donc un cycle réel ≈ le plus lent des 5 (~3min) plus une marge de contention, pas la somme des 5. **Estimation prudente : 4 à 6 minutes par cycle en conditions réelles.**
   - **Cœurs disponibles** : `continuous.parallel_workers: 6` (déjà configuré).
   - **Générations atteignables** : dépend des heures réellement disponibles d'ici dimanche 22h (Europe/Zurich) à partir de MAINTENANT, que je n'ai pas de moyen fiable de calculer sans connaître l'heure actuelle exacte côté Zurich — à 4-6 min/cycle, chaque tranche de 10h disponibles ≈ 100-150 générations.

**Commandes** :
```powershell
# Lancer (depuis la copie figée)
cd runs\20260919_envv2\code
py autonomous_agent.py

# Suivre
Get-Content logs\autonomous_agent.log -Wait -Tail 50

# Mettre en pause (garde l'état, reprend exactement où il en était)
# Ctrl+C dans la fenêtre, ou :
Stop-Process -Name python -Force  # arrête tout (agent + watchdog s'il tourne)

# Reprendre
py autonomous_agent.py   # relit automatiquement _progress.json + search_state
```

5. **Points d'arrêt obligatoires respectés** : fin de phase 0 (fait, validé), **avant le lancement de l'entraînement réel (Run A) — ARRÊT ICI, en attente de ton accord explicite**, comme convenu.

## Phase 8 — Ordres à cours limité : fait

`live.order_type`: `"market"` (défaut, comportement D'ORIGINE inchangé) ou `"limit"` — **UNIQUEMENT pour les ouvertures**, une clôture reste TOUJOURS au marché (jamais un risque de ne pas pouvoir sortir). En mode limit : ordre protégé (jamais rempli à un prix pire que `limit_order_max_slippage_pct`, défaut 0.05%, au-delà du prix courant), tout ordre en attente périmé du même style est annulé avant d'en soumettre un nouveau (jamais d'accumulation). Respecte tous les garde-fous existants (coupe-circuit de compte, ATR indisponible).

Tests dédiés : `tests/test_limit_orders.py` (10).

---

## Récapitulatif tests

**398/398 passent.** 235 hérités du lot 1 + 163 nouveaux dédiés à ce lot (aucun test existant modifié pour le faire passer artificiellement, sauf 3 corrections de test authentiquement obsolètes : `test_stop_loss_buckets.py` annoté comme repli, un test forcé `atr_stop_loss=False` pour isoler son intention d'origine, et le lockbox-test ajusté pour ne pas heurter accidentellement le nouveau garde-fou).

## Fichiers touchés (aperçu, voir l'arbre de travail complet pour le détail)

`src/` : `trading_env.py`, `agent.py`, `demo_trader.py`, `continuous_trainer.py`, `mt5_connector.py`, `data_loader.py`, `features.py`, `multi_asset.py`, `multi_timeframe.py`, `stress_test.py`, `backtester.py`, `episodic_memory.py`, `risk_engine.py` (nouveau). `scripts/` : `archive_snapshot.py`, `restore_archive.py`, `lockbox_eval.py`, `friction_sensitivity.py` (nouveaux), `slippage_report.py`, `cross_asset_survival_test.py`, `leakage_shuffle_test.py` (modifiés). `config/autonomous.yaml`, `autonomous_agent.py`. 22 nouveaux fichiers de test.

## Points suspects signalés (non corrigés sauf mention contraire)

1. **`git` inaccessible** depuis mes outils sur cette machine — rien committé.
2. **Bug lockbox réel trouvé et CORRIGÉ** pendant l'essai à blanc (voir phase 1) — n'aurait jamais été trouvé sans l'essai à blanc obligatoire.
3. **Bug latent pré-existant CORRIGÉ** au passage (phase 4, point 8) : `run_one_cycle` pouvait lever un `KeyError` si aucun style n'avait de champion — désormais géré proprement.
4. **`spread_multiplier_range` non calibrable** (phase 5) : le journal d'exécution actuel ne trace pas le spread "normal" au moment de chaque ordre, seulement le slippage — une vraie calibration de ce paramètre nécessiterait une mesure supplémentaire non implémentée ici.
5. **Durées phase 7 mesurées en séquentiel** (1 worker), pas en conditions réelles (6 workers parallèles) — l'estimation "4-6 min/cycle" est une extrapolation prudente, pas une mesure directe du run réel.
6. **Notifications ntfy envoyées pendant mon essai à blanc** (phase 7) — config réelle utilisée pour la mesure, comportement normal du système mais probablement pas souhaité pendant un simple test ; à garder en tête si un futur essai à blanc est refait.

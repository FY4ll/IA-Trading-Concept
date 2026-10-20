# Idée « Trading GPT — Autonomous Trader V1 » et faisabilité dans Run A

Noté le 05/10/2026. Source : cahier des charges en 92 sections fourni par l'utilisateur
(mission, architecture, intelligence de marché, LLM, décision, risque, exécution MT5,
mémoire, apprentissage, recherche autonome, champion/challenger, validation, rapport final).

## L'idée en résumé

Une IA de trading autonome connectée à MT5 qui tourne en boucle :
OBSERVER → COMPRENDRE → RAISONNER → DÉCIDER → PROTÉGER LE CAPITAL → EXÉCUTER → SURVEILLER
→ APPRENDRE → DIAGNOSTIQUER → CHERCHER → CRÉER UN CHALLENGER → VALIDER → PROMOUVOIR OU REJETER.

Principes clés :
- Un profit de backtest n'est pas un edge réel. Pour être promu, il faut survivre aux coûts,
  au slippage, au hors-échantillon, au walk-forward, à Monte Carlo, à la perturbation des
  paramètres et à un nombre de trades suffisant.
- Un `MarketState` structuré (multi-timeframe, structure HH/HL/LH/LL, régime, volatilité,
  fondamentaux, news, prédictions, incertitude, compte) dont toute décision découle.
- Un LLM qui raisonne sur des preuves structurées (thèse, preuves pour/contre, invalidation)
  mais n'a jamais accès direct aux ordres. S'il échoue, la décision est WAIT.
- WAIT est une vraie décision, avec une raison, et des statistiques.
- Un moteur de risque indépendant qui peut refuser, et un kill switch.
- Une exécution vérifiée : intention → risque → envoi → lecture de l'état MT5 → réconciliation → enregistrement.
- Une traçabilité complète en SQLite (decision_id → état → features → prédiction → LLM → risque → ordre → résultat).
- Un apprentissage qui distingue « bon trade / mauvais résultat » de « mauvaise décision ».
- Une recherche autonome : observation → hypothèse → expérience → challenger → validation → promotion ou rejet.
- Des tests de valeur ajoutée : baselines (buy & hold, tendance simple), ablation par composant,
  QUANT seul contre QUANT + LLM.
- Des lois intouchables : l'IA ne peut modifier ni ses limites de risque, ni le kill switch,
  ni les portes de validation, ni l'historique.
- Statut final honnête : V1 COMPLETE / EDGE VALIDATED, EDGE NOT VALIDATED, ou INCOMPLETE.

## Ce que Run A fait déjà

| Section de l'idée | Dans Run A aujourd'hui |
|---|---|
| Exécution MT5, SL/TP, taille calculée par le risque, arrondi qui ne dépasse pas le risque (§20, §22) | `mt5_connector.py`, `demo_trader.py` |
| MT5 comme source de vérité, réconciliation (§24, §62) | `state_reconciliation.py` |
| Limites dures et disjoncteurs hors de portée de l'IA (§21, §50, §56, §89) | `account_guard.py` avec le profil `ftmo_ai` (perte du jour 2,5 %, drawdown 9 %), `risk_guard.py`, `risk_engine.py`, max 1 stop par jour sur H1T |
| Multi-timeframe sans fuite (§5) | `multi_timeframe.py` (H4/D1/W1/MN1 fusionnés sur H1) |
| Fondamentaux avec délai de publication (§9) | `fred_feed.py`, `cross_asset.py` (H1X, H1XT) |
| News et sentiment (§10) | Flux RSS + FinBERT local (`fundamental_feed.py`, `finbert_sentiment.py`), uniquement en direct |
| Champion/challenger, holdout final jamais optimisé (§32, §34) | Pool de styles, 3 candidats par style et par cycle, porte lockbox (données depuis 2023-05) |
| Walk-forward, stress des coûts (§35, §46) | `backtester.py`, `stress_test.py`, lockbox avec coûts x2 et tiers négatifs |
| Monte Carlo (§45) | `scripts/ftmo_sim.py` (bootstrap par blocs, probabilité de passer le Challenge FTMO) |
| Mémoire (§26, §27) | `episodic_memory.py` (SQLite), `reliability_tracker.py` |
| Journal d'expériences (§63, §64) | `experiment_journal.py` (`reports/experiment_journal.jsonl`) |
| Auto-amélioration contrôlée (§31) | Recherche des paramètres de récompense (phase 1), nouvelles variables (phase 2, H1X) |
| Pas de mélange de modèles pendant un trade | Un nouveau champion attend la clôture de la position ouverte |

## Faisable dans Run A par ajouts ciblés (classé par impact prop-firm)

1. **Kill switch de marché et filtre news haute importance (§21, §17).** Pas d'entrée autour de NFP/CPI/FOMC
   (calendrier déjà configuré via `calendar_url`), et blocage si le spread est anormal ou si les données
   sont périmées. C'est directement utile pour les règles FTMO sur le trading des news.
2. **Journal de décision traçable (§17, §26, §58, §67).** Une table SQLite `decisions` avec decision_id,
   features clés, sortie du modèle, verdict du risque, ordre, prix voulu contre prix réel, slippage, latence,
   résultat, MFE et MAE. Elle permet de répondre à « pourquoi ce trade ? » et de compter les WAIT avec leur raison.
3. **Moteur de régime explicite et performance par régime (§7, §8, §40).** TREND_UP/DOWN, RANGE, HIGH/LOW_VOL,
   calculé à chaque décision, avec des résultats lockbox et démo ventilés par régime. Il pourrait aussi servir
   de filtre hors de l'IA (pas d'entrée en volatilité EXTREME).
4. **Baselines dans la porte lockbox (§42).** Comparer chaque champion au buy & hold de l'or et à une tendance
   simple. C'est essentiel ici : l'or a fortement monté sur la lockbox, et H1, H1T et H1X sont souvent tous
   acheteurs en même temps.
5. **Probabilité FTMO comme critère de la porte (§45, §71).** Intégrer `ftmo_sim` (probabilité du Challenge,
   pire jour, part des mois à +8 %) dans `lockbox_gate.py` plutôt que de le lancer à la main.
6. **Diagnostic automatique (§29, §48, §72).** Dérive des features (PSI), écart entre le démo et la lockbox,
   taux de WAIT anormal, sur-trading. Il alimente le rapport du dimanche.
7. **Rollback automatique (§52, §73).** Si un champion se dégrade en démo, réduire son budget puis revenir au
   champion précédent (les archives existent déjà, il manque le déclencheur).
8. **Recherche autonome, phase 3 (§30).** Générer des hypothèses à partir des diagnostics (par exemple
   « perte en HIGH_VOL → challenger avec filtre de volatilité ») et les écrire dans le journal avec
   question, hypothèse et conclusion.

## Mis en place dans Run A le 05/10/2026 (trading seul, entraînement gelé en `--no-train`)

Archive avant modification : `runs/20260919_envv2/code/models_archive_20261005_1345_pre_v1vision/`.

| Point | Module | État |
|---|---|---|
| 1. Filtre news / spread / données | `src/market_gate.py` | Actif : news USD fort impact 30 min avant à 15 min après, spread > 0,15 ATR, pas de cotation depuis 10 min. Bloque uniquement les ouvertures. |
| 2. Journal de décision traçable | `src/decision_journal.py`, `src/live_supervisor.py` | Actif : `data/decision_journal.sqlite` (décisions, raisons des WAIT, exécutions relues sur MT5, trades avec R/MFE/MAE et régime d'entrée). |
| 3. Moteur de régime | `src/market_regime.py` | Actif : TREND_UP/DOWN, RANGE, TRANSITION, volatilité LOW…EXTREME, structure HH/HL/LH/LL. |
| 4. Baselines dans la porte | `src/lockbox_gate.py` | Calculées à chaque évaluation lockbox. Critère `require_beat_trend_baseline` codé mais coupé (voir résultats). |
| 5. Probabilité FTMO dans la porte | `src/ftmo_metrics.py`, `src/lockbox_gate.py` | Actif pour les futurs candidats : un candidat ne peut pas faire perdre plus de 3 points de Challenge FTMO au champion en place. |
| 6. Diagnostic automatique | `src/diagnostics.py` | Actif chaque jour : `reports/diagnostics.md`. |
| 7. Rollback automatique | `src/live_rollback.py` | Actif : REDUCE (risque x0,5) puis SUSPEND ou ROLLBACK vers une génération antérieure validée. Monotone. |
| 8. Recherche autonome | `src/research_engine.py`, `scripts/regime_report.py` | Actif : hypothèses issues du diagnostic, expériences hebdomadaires en processus séparé, registre `reports/research_journal.jsonl`, filtres adoptés dans `data/research_adopted.json`. |

Tableau de bord HTML et serveur de réglages supprimés à la demande de l'utilisateur. Ce serveur écrasait les limites FTMO au démarrage (perte du jour 3 % au lieu de 2,5 %, drawdown 15 % au lieu de 9 %), problème corrigé du même coup.

### Premiers résultats (lockbox 2023-05 → 2026, rejeu des champions)

- **Baselines** : le buy & hold de l'or fait Sharpe 1,15, +109 %, DD 28,8 %, Challenge FTMO 65 %. La tendance SMA20/50 fait Sharpe 0,81, DD 20 %, Challenge 56 %. Les champions H1, H1T et H1X font Sharpe 0,66 à 0,74 et Challenge 49 à 53 %. Ils ne battent pas encore ces baselines simples : c'est la priorité de recherche n° 1.
- **H1X** : Sharpe −0,13 sur les 2,5 ans d'avant la lockbox, contre +0,74 sur la lockbox. Son avantage dépend de la période, et la lockbox a servi à le sélectionner.
- **Filtre adopté** : pour H1X, pas d'ouverture en volatilité EXTREME. Il améliore les deux périodes (lockbox : Sharpe 0,74 → 0,85, DD 28,4 → 25,7 %, Challenge 53 → 57 %). Les 5 autres filtres testés ont été rejetés par la règle fixée à l'avance.
- **Par régime (lockbox)** : les entrées en RANGE et en volatilité EXTREME sont négatives pour les 3 styles. Les entrées en TRANSITION sont les meilleures.
- **Dérive** : la volatilité des 30 derniers jours est très au-dessus de celle de la lockbox (PSI atr_pct 2,3).

## Faisable, mais gros chantier

- **Couche LLM de raisonnement (§14, §15, §44).** Elle demande une clé API et un coût par décision.
  Limite importante : un LLM connaît déjà les prix et les news historiques, donc un backtest de ses
  décisions est contaminé (fuite du futur). La seule mesure honnête de QUANT contre QUANT + LLM est en
  avant : papier ou démo, plusieurs semaines. Le LLM pourrait commencer comme veto (WAIT) plutôt que
  comme décideur.
- **Modèles supervisés et calibrés (§11, §13).** LightGBM ou régression logistique sur une cible
  « TP avant SL », avec calibration Platt ou isotone, comme nouveau style challenger jugé par la même
  porte lockbox. Il faut installer scikit-learn et lightgbm (absents aujourd'hui). La calibration
  s'applique mal au PPO actuel.
- **Spécialistes par régime avec un orchestrateur (§77, §78).**
- **Structure de marché HH/HL/LH/LL et niveaux (§6)** comme nouvelles variables (style à la H1X).
- **Refonte complète en dépôt `TradingAI/` (§82).** Mieux vaut migrer module par module pendant que
  Run A continue de trader, plutôt que tout réécrire d'un coup.

## Limites réelles

- Il n'existe pas d'historique local des news horodatées à la disponibilité. Les news ne peuvent donc pas être
  validées en backtest, seulement en direct. Il faut le signaler explicitement (NEWS_DATA_UNAVAILABLE)
  plutôt que de supposer « pas de news ».
- Les données macro révisées peuvent être remplacées par les vintages ALFRED (même API FRED) pour éviter
  d'utiliser une valeur révisée comme si elle était connue à l'époque.
- L'historique H1 réel de MT5 ne commence qu'en 2024 environ (Kaggle pour l'historique long), et la
  lockbox couvre environ 3,4 ans : l'échantillon hors-échantillon reste limité.
- Toute modification de `src/` impose d'arrêter l'entraînement, d'archiver, de modifier, de relancer
  et de vérifier.

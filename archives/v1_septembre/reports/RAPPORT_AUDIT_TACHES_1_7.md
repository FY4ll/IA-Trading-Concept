# Rapport final — Câblage des pièces non connectées (tâches 1-7)

Bot de trading RL live (XAUUSD, MT5, `dry_run: false`). Aucune modification du format d'observation ni de l'espace d'action. Suite pytest complète en vert à chaque étape (voir §Pytest final).

**Contrainte opérationnelle non résolue** : `git` reste inaccessible depuis mes outils sur cette machine (déjà constaté lors d'une session précédente). Aucun commit n'a donc été fait par moi — tout est dans l'arbre de travail, non committé. Comme certains fichiers (`continuous_trainer.py`, `demo_trader.py`) ont été touchés par plusieurs tâches successives, un découpage automatique et propre en "un commit par tâche" n'est plus possible après coup sans l'outil git. Je documente ci-dessous quels fichiers appartiennent à quelle tâche pour que tu puisses committer toi-même, soit en un seul commit global, soit en plusieurs via `git add -p`.

---

## Tâche 1 — Mesures (aucun code écrit, comme demandé)

### 1a. Leakage shuffle test
Commande : `py scripts\leakage_shuffle_test.py --timesteps 6000 --bars 6000`

```
Score REEL    = -2.231 (sharpe=-1.960, n_trades=96)
Score MELANGE = -0.047 (sharpe=0.094,  n_trades=189)
VERDICT: PASS   (score mélangé ≤ 0)
```

⚠️ **À signaler** : ce script n'entraîne **pas** les champions réels — il entraîne un agent-sonde neuf (PPO sans LSTM, ~4000 pas par défaut) à chaque exécution, par conception explicite de son propre docstring. Ce n'est pas un bug, mais ça veut dire que le "PASS" ci-dessus valide l'absence de fuite sur la méthodologie de fabrication des données, pas sur les champions actuellement en production. Je n'ai rien modifié (tâche 1 = mesure seule).

### 1b. Walk-Forward Efficiency (WFE) des champions actuels
`compute_walk_forward_efficiency` activé sur une évaluation réelle de chaque champion (config réelle : `eval_windows`, `wfe_is_eval_bars`).

| Style | WFE | Sharpe | Sortino | Max DD | n_trades |
|---|---|---|---|---|---|
| M15 | **None** (IS≤0, OOS>0) | 4.12 | 3.81 | 3.13% | 234 |
| M30 | **None** (IS≤0, OOS>0) | 0.99 | 1.53 | 7.55% | 518 |
| H1  | **None** (IS≤0, OOS>0) | 2.07 | 1.92 | 20.61% | 542 |
| H4  | **1.524** (≥0.5 OK) | 1.20 | 1.73 | 18.99% | 213 |
| D1  | **3.802** (≥0.5 OK) | 1.62 | 2.44 | 20.50% | 69 |

⚠️ **À signaler en priorité** : le critère d'acceptation demandé (WFE ≥ 0.5) n'est **évaluable que sur 2 styles sur 5** (H4, D1). Pour M15/M30/H1, le rendement in-sample mesuré est ≤ 0 alors que le rendement out-of-sample est positif — le ratio WFE est mathématiquement indéfini (`None`) dans ce cas, ce n'est pas une erreur de calcul mais un cas documenté de la fonction. Concrètement : la performance OOS de ces 3 champions est bonne (sharpe positifs, DD modérés) mais ne peut pas être caractérisée par le ratio WFE tel que défini ici. Je ne l'ai pas retenu comme un "échec" du critère, mais comme une limite de la métrique à connaître avant de s'y fier pour juger ces 3 styles.

---

## Tâche 2 — GARCH : fait

Scénario de stress GARCH(1,1) câblé comme 5ᵉ scénario dans `evaluate_agent_walkforward`, activable par config, désactivé par défaut (comportement actuel du champion inchangé).

- Config ajoutée (`config/autonomous.yaml`) :
  ```yaml
  stress_test:
    garch:
      enabled: false
      dof: 5.0
      alpha: 0.08
      beta: 0.90
  ```
- Supporté uniquement pour H1/H4/D1/W1/MN1 (M15/M30 exclus : la série de base de `generate_synthetic_ohlcv_garch` est à fréquence horaire fixe, on ne peut pas l'suréchantillonner honnêtement en 15/30 min). Renvoie `None` proprement si non supporté, jamais de crash.
- Fichiers touchés : `src/stress_test.py`, `src/backtester.py`, `src/continuous_trainer.py`, `config/autonomous.yaml`.
- Tests dédiés : `tests/test_garch_stress.py` (**14 tests**, tous verts) — TF non supportés, construction H1/H4/D1, normalisation avec stats fournies (jamais refit), déterminisme par seed de style, câblage activé/désactivé (spy), gestion des absences de contexte/stats.

## Tâche 3 — Heartbeat : fait

- Config ajoutée : `live.heartbeat_timeout_s: 5.0`.
- Dans `run_demo_trading_loop` : alerte critique unique par épisode de panne (pas de spam) si position ouverte ET `seconds_since_last_success() > seuil`, + alerte de reprise. `measure_round_trip_ms` loggé dans `write_live_status`. Aucune clôture automatique (alerte seule, comme demandé).
- Fichiers touchés : `src/demo_trader.py`, `config/autonomous.yaml`.
- Tests dédiés : `tests/test_heartbeat.py` (**7 tests**, tous verts) — panne+position→1 alerte, panne sans position→0, panne prolongée→toujours 1 seule, reprise→1 alerte de reprise, plus 2 cas limites (jamais de panne, méthode absente sur un faux connecteur).

⚠️ **À signaler** : la prémisse de la tâche ("`seconds_since_last_success` n'a aucun appelant") était **fausse** — un appel existait déjà via `getattr(connector, "seconds_since_last_success", None)`, ajouté lors d'une session antérieure. Graphify (analyse statique AST) ne peut pas résoudre ce dispatch dynamique, d'où l'angle mort. Je n'ai pas réécrit le bloc depuis zéro, je l'ai complété (seuil configurable, anti-spam, alerte de reprise, RTT dans le status).

## Tâche 4 — Coupe-circuit dans le connecteur : fait

- En tête de `MT5Connector.send_order` : si `account_guard.is_halted()` et que l'ordre ouvre/augmente une exposition (`target_direction != 0 and volume > 0`) → refus loggé via `_log_execution`, retour immédiat. Une clôture n'est **jamais** bloquée (même règle que `_cumulative_exposure_refusal`).
- Comportement par défaut du live **change** ici volontairement (règle de sécurité explicite des tâches 3/4).
- Import local (`from src.account_guard import is_halted`) — pas de cycle d'import créé, vérifié.
- Fichiers touchés : `src/mt5_connector.py`.
- Tests dédiés : `tests/test_account_guard_send_order.py` (**5 tests**, tous verts) — halte+ouverture→refusé, halte+clôture→passe, halte+renversement→bloqué, pas de halte→inchangé, halte bloque même en dry-run.

## Tâche 5 — Calendrier macro : fait

- Nouveau chargeur `load_macro_events_csv(path)` (colonne `timestamp_utc` requise, erreur explicite sinon) alimentant l'argument `event_timestamps` déjà existant de `inject_macro_shocks`.
- Config : `stress_test.macro_events_csv: null` (défaut = comportement proxy actuel inchangé).
- Fichier fourni : `data/macro_events_example.csv` — dates 2000 placeholder, `event_type=EXAMPLE_PLACEHOLDER` partout, en-tête expliquant que ce ne sont **pas** des dates réelles (aucune date CPI/NFP/FOMC inventée présentée comme réelle, comme demandé).
- Fichiers touchés : `src/stress_test.py`, `src/backtester.py`, `src/continuous_trainer.py`, `config/autonomous.yaml`, `data/macro_events_example.csv` (nouveau).
- Tests dédiés : `tests/test_macro_events_csv.py` (**7 tests**, tous verts) — CSV avec commentaires, colonne manquante, fichier manquant, chargement réel du fichier d'exemple, câblage vers `inject_macro_shocks` (spy), `None`→comportement proxy préservé.

## Tâche 6 — Nettoyage tests (conditionné au vert des tâches 1-5, obtenu) : fait

- `DummyMonkeypatch` (dupliqué 3×) fusionné en une seule définition dans `tests/conftest.py`, importée par `test_autonomous.py`, `test_fred_feed.py`, `test_fundamental_feed.py`.
- `.graphifyignore` ajouté (`tests/`), graphe régénéré :
  ```powershell
  & "$env:USERPROFILE\.local\bin\graphify.exe" . --code-only --no-viz
  & "$env:USERPROFILE\.local\bin\graphify.exe" cluster-only "C:\Users\utilisateur\Documents\Test_IA"
  ```
  1034 → 571 nœuds (472 nœuds de tests exclus, confirmé).

---

## Pytest final (toutes tâches 1-7 confondues)

```
235 passed in 125.26s
```
(199 tests avant cette session + 36 nouveaux tests dédiés : 14+7+5+7+3. Aucune régression, aucun test existant modifié pour le faire passer artificiellement.)

---

## Tâche 7 — Code mort et optimisation (enchaîné automatiquement, comme validé)

### 7.A — Code mort : **rien n'est supprimé**

Méthodologie appliquée aux 11 candidats désignés : preuve requise = (1) vulture confiance ≥ 80 **ET** (2) grep sans appelant hors définition/tests **ET** (3) coverage à 0 ligne exécutée hors tests propres.

| Candidat | Vulture ≥80 | Appelant réel (grep) | Verdict |
|---|---|---|---|
| `get_bars_range`, `get_open_position_info`, `get_current_spread_pct`, `is_symbol_active`, `allow_real_account`, `status_summary`, `has_champion`, `risk_profile.load_risk_profile`, legacy `send_order` sans style, `_notional_lots` | — | Oui, appelants de prod trouvés | **Conservé** (échoue déjà au critère 2) |
| `MT5Connector.disconnect` | **60%** (< seuil 80) | Non (tests seulement) | **Conservé** (échoue au critère 1, le plus proche des 11) |
| `account_guard.reset` | Non flaggé du tout | Non (tests seulement) | **Conservé** (échoue au critère 1) |

Décision confirmée par toi : **règle stricte, rien ne qualifie** → aucun `coverage run` nécessaire (déjà disqualifié en amont), aucune suppression, aucun commit pour cette sous-tâche. `src/finbert_sentiment.py` et `scripts/pilot_m15_v3.py` non traités plus avant (hors du triage strict des 11 candidats nommés ; `pilot_m15_v3.py` reste une proposition d'archivage à valider séparément si souhaité, non fait).

### 7.B — Duplication : factorisée, comportement préservé

- `src/io_utils.py` (nouveau) : `read_json_safe()` + `JsonCacheMixin`.
- `_read_json` (`continuous_trainer.py`, `dashboard.py`) et `_read_json_safe` (`demo_trader.py`) : vérifiés identiques (fichier manquant → `{}`, JSON corrompu → `{}`), remplacés par un simple appel à `read_json_safe`.
- `_load_cache`/`_save_cache`/`_warn_once` (`FredFeed`, `AutoFundamentalFeed`) : **divergence réelle trouvée** — `FredFeed` a `default=None` et un suffixe de warning différent d'`AutoFundamentalFeed` (`default={}`). Factorisé via `JsonCacheMixin` avec `default` et `suffix` en paramètres **obligatoires** (pas de défaut Python) pour forcer chaque site d'appel à préserver explicitement son comportement d'origine — aucune uniformisation silencieuse.
- Fichiers touchés : `src/io_utils.py` (nouveau), `src/continuous_trainer.py`, `src/demo_trader.py`, `src/dashboard.py`, `src/fred_feed.py`, `src/fundamental_feed.py`.
- Pas de nouveaux tests dédiés distincts (refactor comportement-préservé, couvert par la suite existante + les 235 tests verts).

### 7.C — Performance : mesuré avant/après, un seul changement retenu (validé : cycle d'entraînement uniquement)

Profilage `run_demo_trading_loop` (1 itération) : **123 ms total**, aucun poste > 5%, rien à optimiser (confirmé, pas de rapport avant/après nécessaire pour cette partie).

Profilage `run_one_cycle` (1 cycle complet) — AVANT :
```
Total : 18.891 s
pandas.core.internals.managers.fast_xs (accès .iloc ligne par ligne) :
  1.806 s cumulés sur 11199 appels ≈ 9.6% du temps total → au-dessus du seuil de 5%
```

**Optimisation appliquée** (`src/trading_env.py`) : pré-extraction en `__init__` de 7 tableaux numpy (`_open`, `_high`, `_low`, `_close`, `_cost_multiplier_col`, `_slippage_price_offset_col`, `_atr_raw_col`) remplaçant les accès `.iloc[i][col]` répétés dans `_effective_transaction_cost`, `_atr_price_units`, `_log_trade`, `step()` (prix, stop-loss, remplissage).

AVANT/APRÈS :
```
AVANT : fast_xs = 1.806s / 18.891s ≈ 9.6% — 4e poste le plus coûteux (tottime)
APRÈS : fast_xs absent du top 15 (tottime) — éliminé du profil
```
Note méthodologique : le temps total "après" (28.0s) n'est pas directement comparable au temps "avant" (18.9s) en valeur absolue, car les 6 workers du processus de production live (`autonomous_agent.py`) tournaient en concurrence CPU pendant la mesure "après". La preuve retenue est donc la disparition du poste ciblé du classement des postes chauds (`fast_xs` : présent et 4e à 9.6% avant → absent du top 15 après), pas le delta de temps total brut.

**Preuve d'identité numérique** (exigence absolue du mandat : sortie numériquement identique) :
- `tests/test_trading_env_perf.py` (**3 tests**, tous verts) : égalité `np.allclose(rtol=1e-9)` + égalité stricte à des index précis entre tableaux pré-extraits et accès `.iloc` d'origine ; prix de trades enregistrés cohérents avec le dataframe source sur 800 pas d'actions aléatoires ; reproductibilité bit-à-bit de deux épisodes identiques.
- Tests préexistants à valeurs attendues codées en dur (`test_stop_loss_buckets.py`, 2 tests de `test_autonomous.py` sur le stop-loss) ré-exécutés : inchangés, verts — auraient cassé sur le moindre écart.

Pas de test de non-régression automatisé sur le **temps** ajouté (décision confirmée : le bilan chiffré ci-dessus suffit, un seuil de temps serait fragile sur une machine qui partage son CPU avec le système de production live).

Fichiers touchés : `src/trading_env.py`, `tests/test_trading_env_perf.py` (nouveau).

---

## Récapitulatif fichiers touchés (toutes tâches)

| Fichier | Tâche(s) |
|---|---|
| `src/stress_test.py` | 2, 5 |
| `src/backtester.py` | 2, 5 |
| `src/continuous_trainer.py` | 2, 5, 7B |
| `src/demo_trader.py` | 3, 7B |
| `src/mt5_connector.py` | 4 |
| `src/dashboard.py` | 7B |
| `src/fred_feed.py` | 7B |
| `src/fundamental_feed.py` | 7B |
| `src/trading_env.py` | 7C |
| `src/io_utils.py` (nouveau) | 7B |
| `config/autonomous.yaml` | 2, 3, 5 |
| `data/macro_events_example.csv` (nouveau) | 5 |
| `tests/conftest.py` (nouveau) | 6 |
| `tests/test_garch_stress.py` (nouveau, 14 tests) | 2 |
| `tests/test_heartbeat.py` (nouveau, 7 tests) | 3 |
| `tests/test_account_guard_send_order.py` (nouveau, 5 tests) | 4 |
| `tests/test_macro_events_csv.py` (nouveau, 7 tests) | 5 |
| `tests/test_trading_env_perf.py` (nouveau, 3 tests) | 7C |
| `tests/test_autonomous.py`, `tests/test_fred_feed.py`, `tests/test_fundamental_feed.py` | 6 |
| `.graphifyignore` (nouveau) | 6 |

**Hors périmètre respecté** : `send_order_async` toujours non câblé, pas de VPS/latence, pas de FOK/IOC, pas de refactor de `MT5Connector` au-delà du bloc du coupe-circuit, `pilot_m15_v3.py`/`v4.py` non touchés, pas de données cross-asset.

## Points suspects signalés (non corrigés, comme demandé)

1. **Tâche 1a** : `leakage_shuffle_test.py` n'évalue pas les champions réels mais un agent-sonde neuf à chaque run — le "PASS" ne couvre que la méthode de fabrication des données, pas les champions en prod actuellement.
2. **Tâche 1b** : le critère d'acceptation "WFE ≥ 0.5" est **indéfini** (None) pour 3 champions sur 5 (M15, M30, H1) car leur rendement in-sample mesuré est ≤ 0 — pas une erreur, mais le critère demandé ne peut littéralement pas trancher pour ces 3 styles malgré des performances OOS correctes.
3. **Tâche 3** : la prémisse "aucun appelant" pour `seconds_since_last_success` était fausse — un appel dynamique (`getattr`) existait déjà d'une session antérieure, invisible à l'analyse statique de graphify.
4. **Tâche 7.A** : `MT5Connector.disconnect` est le candidat le plus proche de la suppression (vulture à 60%, aucun appelant de prod trouvé) mais reste sous le seuil strict de 80% retenu — à surveiller si un futur ménage de code mort est refait.
5. **Opérationnel** : `git` reste inaccessible depuis mes outils sur cette machine — aucun commit fait, tout dans l'arbre de travail non committé (voir tableau ci-dessus pour committer toi-même par tâche si souhaité).

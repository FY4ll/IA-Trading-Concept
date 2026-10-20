# Autonomous Trading Agent

Une IA de trading qui **apprend son propre comportement** par renforcement,
mémorise ses expériences, et évolue de génération en génération — plutôt
qu'une stratégie fixe codée à la main.

```
Observer -> Décider -> Agir -> Mesurer -> Mémoriser -> Évoluer -> Recommencer
```

**Ce projet ne contient qu'une seule IA et qu'un seul point d'entrée.**
Il n'y a pas de scripts d'entraînement séparés, pas de config alternative,
pas de mode "manuel" — tout passe par `autonomous_agent.py`, pour éviter
tout conflit entre plusieurs pipelines ou plusieurs modèles.

```bash
pip install -r requirements.txt
python autonomous_agent.py
```

C'est la seule commande à connaître. Les données (dataset Kaggle XAUUSD,
2004-2026) sont déjà incluses dans `data/kaggle_gold/` : rien à
télécharger ni à préparer.

---

## 1. Ce que fait cette commande

Une seule commande démarre **deux boucles qui tournent en parallèle,
indéfiniment** :

1. **Évolution continue** (thread arrière-plan, ne s'arrête jamais) :
   - récupère les données les plus fraîches (fusion multi-timeframe) ;
   - fait progresser **plusieurs styles de trading EN PARALLÈLE** — un par
     timeframe primaire du pool configuré (`data.timeframe_pool`, ex: M15
     pour du scalping, H1, H4, D1 pour du swing), chacun avec son propre
     contexte multi-timeframe dérivé automatiquement (voir section 3) ;
   - pour chaque style, jamais de redémarrage à zéro : chaque cycle
     réutilise les poids déjà appris (*warm start*) et les fait continuer
     à apprendre sur les données récentes, avec plusieurs variantes
     d'hyperparamètres mutées entraînées **en parallèle** (un processus
     séparé par candidat, tous styles confondus) ;
   - un style ne progresse que si une de ses variantes fait **strictement
     mieux** sur une validation à jour (donc jamais de régression).
2. **Trading en démo** (boucle principale) : utilise en permanence le
   **meilleur style actuel, tous confondus** (voir section 2 ci-dessous)
   pour décider, sur le compte MT5 de démonstration déjà connecté dans
   votre terminal. Dès qu'une meilleure version validée est promue —
   éventuellement d'un AUTRE style que le précédent, si le marché change
   de régime — elle est **rechargée à chaud**, sans interrompre le trading.

Pour ne laisser tourner que l'apprentissage, sans démo (par exemple le
temps de laisser le système constituer un premier historique de
performance) :
```bash
python autonomous_agent.py --no-demo
```

---

## 2. Sélectivité : un agent médiocre n'est JAMAIS envoyé en démo

Le système distingue deux notions, volontairement séparées :

- **Champion technique, PAR STYLE** (`models/champion_<TF>/`, ex:
  `champion_M15/`, `champion_H1/`...) : sert uniquement de point de départ
  pour continuer l'apprentissage de CE style cycle après cycle (warm
  start). Peut être promu même avec des métriques encore mauvaises — c'est
  normal, surtout au tout début : son seul rôle est de faire progresser
  l'entraînement de sa lignée, pas de trader.
- **Champion démo** (`models/demo_champion/`, UNIQUE, tous styles
  confondus) : repli historique, utilisé UNIQUEMENT quand `live.ensemble:
  false`, ou tant qu'aucun style ne passe encore individuellement la
  validation (voir "Ensemble multi-styles" ci-dessous). Il n'est promu que
  si le meilleur candidat, TOUS STYLES CONFONDUS, EN PLUS de battre le
  champion démo actuel, **passe aussi** les seuils définis dans
  `config/autonomous.yaml -> validation` :
  ```yaml
  validation:
    min_sharpe_to_go_live: 1.0
    max_drawdown_allowed: 0.20
    min_generations_before_demo: 20   # exige au moins 20 cycles d'entraînement avant la démo
  ```
  Un style avec un Sharpe négatif reste ainsi utilisé pour continuer son
  apprentissage, mais **ne sera jamais envoyé en démo** tant qu'aucun
  style ne dépasse ces seuils. `min_generations_before_demo` évite en plus
  qu'un style passe les seuils "par chance" dès les tout premiers cycles
  (sur une petite fenêtre de validation) et parte en démo trop tôt :
  montez cette valeur (50, 100...) si vous voulez encore plus de
  robustesse avant de faire confiance au système.

Au démarrage, le programme attend explicitement qu'un **champion démo**
existe (pas juste "un champion") avant de lancer le trading en démo, avec
un message d'attente périodique qui précise où en est l'entraînement de
chaque style.

---

## 3. Un "vrai trader" : plusieurs styles en parallèle, du scalping au swing

```yaml
data:
  timeframe_pool: ["M15", "H1", "H4", "D1"]
```

Chaque timeframe listée devient une **lignée entraînée en parallèle** :
- `M15` (scalping) voit un contexte de M30/H1/H4/D1/W1/MN1 ;
- `H1` (intraday) voit un contexte de H4/D1/W1/MN1 ;
- `H4` (swing intraday) voit un contexte de D1/W1/MN1 ;
- `D1` (swing) voit un contexte de W1/MN1.

Le contexte de chaque style est dérivé **automatiquement** : toutes les
timeframes disponibles strictement plus larges que la primaire choisie —
inutile de le configurer à la main pour chaque style. Chaque lignée a sa
propre mémoire de warm start (`models/champion_<TF>/`) car un style
scalping et un style swing n'observent pas le même nombre de features et
ne peuvent donc pas partager les mêmes poids.

**Ensemble multi-styles (`live.ensemble: true`, par défaut)** : dès que
PLUSIEURS styles passent individuellement les seuils de qualité en même
temps, la décision de démo n'est plus "un seul gagnant" mais une **moyenne
pondérée** (par score) de leurs positions cibles respectives, ce qui donne
une exposition CONTINUE plutôt qu'un simple -1/0/1 :
```
[demo_trader] Décision ensemble (2 style(s) éligible(s)) : D1=+1 (poids=0.65), H4=-1 (poids=0.35) -> exposition finale = +0.30
```
Le mécanisme intéressant : quand les styles éligibles sont d'accord sur la
direction, l'exposition finale reste proche de ±1 (position pleine) ; quand
ils sont en désaccord, elle se rapproche naturellement de 0 -- la taille de
la position reflète donc la CONFIANCE de l'ensemble, pas juste sa direction.
Ce n'est jamais figé : si le marché change de régime, les poids (et donc
l'exposition) se réajustent au cycle suivant. Avec `live.ensemble: false`,
ou tant qu'aucun style ne passe encore individuellement la validation, le
système retombe sur l'ancien comportement "un seul gagnant"
(`models/demo_champion/`) :
```
[demo_trader] Décision ensemble (1 style(s) éligible(s)) : H4=+1 (poids=1.00) -> exposition finale = +1.00
```

Ajustez le pool selon vos préférences (`data.timeframe_pool` accepte
n'importe quelle combinaison parmi M1, M5, M15, M30, H1, H4, D1, W1, MN1
présente dans vos CSV) — un pool plus large explore plus de styles mais
multiplie le nombre total de candidats par cycle (voir section 5).

---

## 4. Pourquoi les candidats d'un même cycle peuvent sembler très inégaux (et comment c'est corrigé)

Il est normal d'observer, sur une même génération, des candidats affichant
des rendements très éloignés (ex: 30% vs 130%). En cause : le rendement
d'une évaluation se compose de façon **multiplicative** sur tout l'épisode
de validation (potentiellement plus d'un an de bougies H1). Sur un
historique avec un mouvement de fond marqué (l'or est passé sous les 2000$
à plus de 4900$ dans le dataset fourni), un candidat qui "attrape" ce
mouvement par chance voit ses gains s'enchaîner en cascade sur le reste de
l'épisode — ce qui peut faire passer de la chance pour de la compétence.

**Correction apportée** : chaque candidat est évalué sur **plusieurs
fenêtres temporelles indépendantes** (`continuous.eval_windows: 3` par
défaut), chacune repartant du solde initial, puis les métriques sont
moyennées — le drawdown agrégé prend le **pire** des fenêtres (jamais une
moyenne qui le diluerait). Un candidat doit être bon sur plusieurs
morceaux de marché différents pour obtenir un bon score, pas sur un seul
coup de chance. Les logs de chaque cycle affichent maintenant le détail
par fenêtre pour que vous puissiez le vérifier vous-même :
```
candidat 1: sharpe=41.41 drawdown=0.83% return=3.86% score=41.393
  (détail par fenêtre : return=3.1%/sharpe=31.5, return=3.0%/sharpe=27.9, return=5.4%/sharpe=64.8)
```
Montez `eval_windows` à 4-5 dans `config/autonomous.yaml` pour encore plus
de robustesse (au prix d'un signal un peu plus court par fenêtre).

---

## 5. Sécurité : jamais d'argent réel envoyé automatiquement

- À la connexion, le système **vérifie auprès de MT5** si le compte est un
  compte de démonstration (`ACCOUNT_TRADE_MODE_DEMO`).
- Si ce n'est **pas** un compte démo, tous les ordres sont **forcés en
  dry-run** (rien n'est envoyé), quoi que vous ayez mis dans
  `live.dry_run` — sauf si vous activez explicitement
  `live.allow_real_account: true`, ce que ce projet déconseille pour un
  système qui tourne sans supervision.
- `live.dry_run: true` reste le réglage par défaut même sur un compte
  démo confirmé : les décisions sont calculées et journalisées, mais
  aucun ordre n'est envoyé tant que vous ne passez pas `dry_run: false`
  vous-même, en connaissance de cause.

### Secrets de notification (SMTP / webhook) hors du YAML

Les identifiants du canal d'alerte (voir `notifications` dans
`config/autonomous.yaml`, section 5 aussi via `src/notifier.py`) peuvent être
fournis par variable d'environnement plutôt qu'en clair dans le YAML — la
variable d'environnement est **prioritaire** si elle est définie et non
vide, sinon le champ YAML correspondant sert de repli (comportement
d'origine inchangé si aucune variable n'est définie) :

| Variable d'environnement    | Remplace le champ YAML       |
|------------------------------|-------------------------------|
| `NOTIFIER_SMTP_HOST`         | `notifications.smtp_host`     |
| `NOTIFIER_SMTP_USER`         | `notifications.smtp_user`     |
| `NOTIFIER_SMTP_PASSWORD`     | `notifications.smtp_password` |
| `NOTIFIER_TO_EMAIL`          | `notifications.to_email`      |
| `NOTIFIER_WEBHOOK_URL`       | `notifications.webhook_url`   |
| `NOTIFIER_NTFY_TOPIC`        | `notifications.ntfy_topic`    |
| `NOTIFIER_NTFY_SERVER`       | `notifications.ntfy_server`   |

Exemple (PowerShell, avant de lancer `python autonomous_agent.py`) :

```powershell
$env:NOTIFIER_SMTP_PASSWORD = "votre-mot-de-passe-application"
```

---

## 6. Débit d'entraînement (parallélisme CPU, GPU, réseau plus grand)

La config livrée est calée sur un **Intel i7-10700 (8 cœurs/16 threads) +
RTX 2060**, avec 4 styles dans le pool par défaut :

```yaml
agent:
  device: "cpu"            # voir explication ci-dessous : le GPU n'aide pas ici
  net_arch: [256, 256]      # réseau plus grand que le défaut SB3 ([64, 64])

continuous:
  candidates_per_cycle: 2    # candidats testés PAR STYLE (x4 styles = 8 au total par cycle)
  parallel_workers: 8         # candidats entraînés SIMULTANÉMENT, tous styles confondus (vos 8 coeurs)
  timesteps_per_cycle: 16000    # apprentissage supplémentaire par candidat et par cycle
```

- **`candidates_per_cycle` s'applique PAR STYLE** : avec 4 styles dans
  `data.timeframe_pool`, le nombre total de candidats entraînés à chaque
  cycle est `candidates_per_cycle × 4`. Si un cycle vous semble trop long,
  réduisez ce nombre ou retirez un style du pool plutôt que de monter
  `parallel_workers` au-delà de vos cœurs physiques.
- **Parallélisme réel entre candidats** : chaque candidat d'un cycle
  s'entraîne dans son **propre processus** (voir `src/continuous_trainer.py`),
  tous styles confondus. C'est le levier qui a le plus d'impact sur le
  nombre de générations calculées par heure. Plafonné automatiquement au
  nombre de cœurs disponibles ; mettez `parallel_workers: 1` pour revenir
  à un entraînement séquentiel.
- **Répartition automatique des threads CPU** : PyTorch essaie par défaut
  de réquisitionner TOUS les cœurs pour ses propres calculs, même à
  l'intérieur d'un seul processus. Le système calcule automatiquement
  combien de threads allouer à chaque processus candidat (cœurs
  disponibles ÷ workers actifs) pour éviter que plusieurs processus ne se
  marchent dessus — rien à régler ici.
- **Pourquoi `device: "cpu"` malgré un GPU disponible** : stable-baselines3
  le dit lui-même dans sa documentation — pour un réseau `MlpPolicy` de
  cette taille, le temps perdu à transférer les données entre CPU et GPU
  dépasse le gain de calcul. Le GPU redeviendrait intéressant avec un
  réseau beaucoup plus gros (`net_arch: [512, 512]` ou plus) entraîné SEUL
  (`parallel_workers: 1`, `device: "cuda"`) plutôt qu'en petits réseaux
  parallèles.
- **Pour aller plus loin** : montez `candidates_per_cycle` (par style) ou
  `timesteps_per_cycle` à 25000-30000. Surveillez l'usage CPU réel
  (gestionnaire des tâches) : si tous les threads logiques plafonnent à
  100% en continu sans marge pour MT5 et le reste de votre système,
  redescendez d'un cran.

### Suivi de progression pendant les cycles

Chaque candidat journalise sa progression périodiquement (tous les 20% du
nombre de pas à effectuer), avec une étiquette identifiant le cycle, le
style et le candidat concerné :
```
[gen 12 | H4 #1] : 3200/16000 pas (20%)
[gen 12 | H4 #1] : 6400/16000 pas (40%)
```
Aucun message lié au GPU/CPU n'est plus journalisé au démarrage de chaque
candidat (c'était bruyant avec plusieurs processus en parallèle et sans
valeur ajoutée passé le premier constat).

---

## 7. Heures de marché et anti-surapprentissage

### Volume de données adapté aux heures de marché XAUUSD

```yaml
data:
  max_bars: 40000                # volume utilisé pendant les heures de marché OUVERTES
  max_bars_market_closed: 0       # 0 = ILLIMITÉ pendant la FERMETURE du marché (week-end)

market_hours:
  enabled: true
  close_weekday: 4   # vendredi (0=lundi ... 6=dimanche)
  close_hour: 21       # 21h UTC (~17h New York)
  open_weekday: 6       # dimanche
  open_hour: 21
```

Le marché XAUUSD suit les sessions Forex : fermé du vendredi soir au
dimanche soir. Pendant cette fermeture, rien ne presse et aucune décision
de trading en direct ne sollicite le CPU — le système reconstruit alors
le dataset de chaque style avec **beaucoup plus d'historique** (voire
l'intégralité de ce qui est disponible avec `max_bars_market_closed: 0`).
Les logs indiquent l'état à chaque cycle :
```
Marché XAUUSD : FERMÉ (week-end) -> volume de données étendu pour ce cycle.
```
**Attention avec des timeframes fines dans le pool** (M15, M5, M1) :
"illimité" peut représenter plusieurs centaines de milliers de bougies,
donc des cycles de week-end nettement plus longs qu'en semaine (voulu,
mais bon à savoir). Préférez un nombre concret (ex: `150000`) à `0` si
vous voulez un volume "généreux mais borné" plutôt que réellement illimité.
Ajustez `market_hours` si votre broker a des horaires différents, ou
mettez `enabled: false` pour toujours utiliser `data.max_bars`.

### Suivi anti-surapprentissage

L'évolution continue tourne à l'infini par conception — le garde-fou "un
candidat n'est promu que s'il fait STRICTEMENT mieux" empêche déjà toute
régression. En complément, le nombre de cycles consécutifs sans la
moindre amélioration est suivi et journalisé :
```yaml
continuous:
  overfitting_patience_cycles: 15
```
Au-delà de ce seuil, un avertissement explicite apparaît dans les logs
pour signaler un plateau (signe possible de sur-apprentissage des données
disponibles), sans jamais arrêter le système ni annuler le dernier bon
champion :
```
[!] Aucune amélioration depuis 15 cycles (meilleur score jamais atteint : 2.410).
    L'entraînement continue indéfiniment (c'est voulu)...
```
Ce compteur persiste entre deux lancements du programme
(`models/_progress.json`).

---

## 8. Les données

Le dataset Kaggle XAUUSD (9 fichiers, 2004-2026 : 1m/5m/15m/30m/1H/4H/1D/1W/1M)
est fourni directement dans `data/kaggle_gold/`. Le système fusionne
plusieurs échelles de temps :
- la timeframe **primaire** (`data.primary_timeframe`, H1 par défaut) :
  celle sur laquelle l'agent décide et trade réellement ;
- le **contexte** de timeframes plus larges (`data.context_timeframes`,
  H4/D1/W1/MN1 par défaut) : tendance/momentum de fond, fusionné bougie
  par bougie sans jamais utiliser une bougie de contexte pas encore
  clôturée (anti-fuite d'information).

**Pour la démo**, les CSV Kaggle sont figés dans le temps (utiles pour
l'entraînement, pas pour décider *aujourd'hui*) : le système récupère
donc les timeframes de contexte **en direct depuis MT5** et les fusionne
de la même façon qu'à l'entraînement.

**Pour changer d'instrument** : remplacez les CSV dans `data/kaggle_gold/`
par vos propres fichiers (même convention de nommage : le nom de fichier
doit contenir un motif reconnaissable comme `1h`, `4h`, `1d`, `1w`,
`1month`...), ou pointez `data.folder` dans `config/autonomous.yaml` vers
un autre dossier. Le format attendu est un CSV avec des colonnes
Date/Open/High/Low/Close/Volume (séparateur `,` ou `;` détecté
automatiquement).

Adaptez aussi `live.symbol` dans `config/autonomous.yaml` au nom exact
utilisé par **votre courtier** (souvent `"XAUUSD"`, parfois `"GOLD"` ou
`"XAUUSD.m"` — vérifiez dans le Market Watch de votre terminal MT5).

---

## 9. Architecture du projet

```
trading_ai/
├── config/autonomous.yaml     <- CONFIGURATION UNIQUE (tous les réglages sont ici)
├── data/kaggle_gold/          <- 9 CSV XAUUSD (2004-2026), inclus, prêts à l'emploi
├── src/
│   ├── data_loader.py          <- chargement des CSV (+ générateur synthétique pour les tests)
│   ├── multi_timeframe.py      <- fusion de plusieurs timeframes (fichiers CSV ET données live MT5)
│   ├── market_hours.py         <- détection heures de marché XAUUSD (volume de données adapté)
│   ├── fundamental_feed.py     <- auto-alimentation fondamentale : news RSS + calendrier économique
│   ├── features.py             <- indicateurs techniques + score fondamental
│   ├── trading_env.py          <- l'environnement (Gymnasium) : l'agent y "vit"
│   ├── episodic_memory.py      <- mémoire persistante (SQLite) des trades passés
│   ├── memory_features.py      <- traduit la mémoire épisodique en signal d'observation (k plus proches voisins)
│   ├── policy_networks.py      <- extracteur LSTM : l'agent parcourt réellement la séquence temporelle
│   ├── agent.py                <- wrapper PPO (stable-baselines3), device/réseau/progression configurables
│   ├── evolution.py            <- mutation des hyperparamètres entre générations
│   ├── continuous_trainer.py   <- ÉVOLUTION CONTINUE : plusieurs styles en parallèle, champion démo unique,
│   │                               candidats entraînés en parallèle (un processus chacun), suivi anti-plateau
│   ├── demo_trader.py          <- boucle de trading en démo, style relu dynamiquement à chaque rechargement
│   ├── backtester.py           <- métriques Sharpe / drawdown / profit factor, évaluation walk-forward
│   └── mt5_connector.py        <- pont vers un terminal MetaTrader5 déjà connecté (+ garde-fou démo)
├── autonomous_agent.py         <- POINT D'ENTRÉE UNIQUE
├── tests/
│   ├── test_multi_timeframe.py    <- détection/fusion des timeframes
│   ├── test_fundamental_feed.py   <- auto-alimentation fondamentale
│   └── test_autonomous.py         <- évolution continue, styles multiples, heures de marché, anti-plateau,
│                                      parallélisme, garde-fous démo
└── requirements.txt
```

### Modèles produits par le système (un par style + un champion démo unique)

```
models/
├── champion_M15/        <- meilleur agent "technique" du style M15 (scalping)
├── champion_H1/         <- idem pour H1
├── champion_H4/         <- idem pour H4
├── champion_D1/         <- idem pour D1 (swing)
│     (chacun : agent.zip, meta.json, norm_stats.json)
├── demo_champion/       <- LE seul modèle utilisé en démo : le meilleur style du moment
│     (agent.zip, meta.json -- inclut primary_timeframe/context_timeframes/feature_columns
│      pour que demo_trader.py sache reconstruire l'environnement exact -- , norm_stats.json)
└── _progress.json       <- suivi anti-surapprentissage (génération, meilleur score, plateau)
```



| Principe de la vision              | Implémentation concrète |
|---|---|
| Machine Learning / Deep Learning   | Agent PPO (`stable-baselines3`) dans `src/agent.py`, réseau récurrent LSTM (`src/policy_networks.py`) qui parcourt réellement la séquence temporelle |
| Environnement simulé               | `src/trading_env.py`, évalué sur historique avant tout usage réel |
| Mémoire épisodique EXPLOITÉE       | `src/episodic_memory.py` (base SQLite persistante) + `src/memory_features.py` : le pnl/drawdown moyen des situations passées similaires est injecté directement dans l'observation de l'agent (entraînement ET démo) |
| Détection de régime de marché       | `adx_14` (force de tendance) et `volatility_regime` (changement de régime de volatilité) dans `src/features.py` |
| Ensemble multi-styles pondéré       | `src/demo_trader.py` : décision de démo = moyenne pondérée par score de tous les styles éligibles, exposition réduite naturellement en cas de désaccord (voir section 3) |
| Évolution / sélection              | `src/continuous_trainer.py` : warm start + mutation + sélection à chaque cycle, candidats en parallèle |
| Reward basé sur risque, pas juste le taux de gain | `reward_type: risk_adjusted` dans `trading_env.py` (pénalise le drawdown) |
| Données de marché + fondamentales  | `src/multi_timeframe.py` (prix, plusieurs échelles) + `src/fundamental_feed.py` (news + calendrier) |
| Validation temporelle              | `chronological_split()` + validation à chaque cycle, aucun mélange passé/futur |

---

## 10. Installation

```bash
git clone <ce dépôt>   # ou décompressez l'archive fournie
cd trading_ai
pip install -r requirements.txt
```

Sur Windows, avec un terminal MetaTrader5 déjà installé et connecté à un
compte **démo** :
```bash
pip install MetaTrader5
python autonomous_agent.py
```

Sans MT5 installé (par exemple pour laisser tourner l'entraînement seul,
sans démo) :
```bash
python autonomous_agent.py --no-demo
```

---

## 11. Tests

```bash
pytest tests/ -v
```

Isolation par test (`pytest>=8.0`, voir `requirements.txt`) : chaque test
tourne indépendamment des autres (répertoire temporaire dédié via `tmp_path`,
`monkeypatch` restauré automatiquement en fin de test) -- un test qui plante
n'empêche jamais les suivants de s'exécuter, et vous obtenez toujours un
décompte pass/fail complet en un seul passage. L'ancien lancement direct
(`python tests/test_autonomous.py`) reste possible en dépannage (bloc
`if __name__ == "__main__"` conservé dans chaque fichier) mais n'est plus la
méthode recommandée : une exception dans un seul test y arrêtait tout le
script et laissait le reste non vérifié.

Ces trois fichiers couvrent : la détection et la fusion des timeframes, la
résilience de l'auto-alimentation fondamentale (jamais de crash même sans
réseau), et le cœur du système autonome (évolution continue, warm start,
entraînement parallèle des candidats, garde-fous de sélectivité démo,
sécurité du connecteur MT5).

---

## 12. Avertissement

Ce projet est un **cadre technique de recherche et développement**. Les
performances passées (y compris en backtest) ne garantissent aucun résultat
futur. Le trading avec de l'argent réel comporte un risque de perte en
capital. Testez longuement en dry-run / compte démo avant tout compte réel,
et ne dépassez jamais un capital que vous êtes prêt à perdre.

---

## 13. Pistes avancées (toutes désactivées par défaut, sans impact tant que non activées)

- **Population évolutive** (`continuous.population_size`, défaut `1`) :
  chaque style peut faire évoluer plusieurs lignées indépendantes en
  parallèle au lieu d'une seule, chacune avec son propre agent/score/
  recherche adaptative. Coût : multiplie le nombre de candidats par cycle
  par cette valeur -- mesurez l'impact sur la durée d'un cycle avant de
  monter au-delà de 1.
- **Stress-test adversarial** (`continuous.stress_test`, défaut `false`) :
  ajoute 2 scénarios construits à partir de vrais morceaux de marché
  réarrangés (blocs réordonnés, sous-ensemble haute volatilité -- voir
  `src/stress_test.py`) à l'évaluation de chaque candidat, pour tester sa
  robustesse au-delà des fenêtres walk-forward classiques.
- **Filet de sécurité indépendant** (`live.risk_guard`, défaut `true`) :
  une règle statistique (pas un réseau appris, voir `src/risk_guard.py`)
  réduit l'exposition en démo si les dernières bougies connues sortent
  statistiquement de l'ordinaire, quelle que soit la décision de l'agent.
- **Sizing continu** (`agent.algo: "SAC"` ou `"TD3"`, défaut `"PPO"`) :
  au lieu d'une position discrète (short/flat/long), l'agent apprend
  directement l'INTENSITÉ de sa position (ex: 0.3 = position partielle).
  Change l'algorithme RL entier (hors-politique, mémoire de replay) --
  comparez d'abord aux résultats obtenus avec PPO avant de basculer un
  déploiement dessus.

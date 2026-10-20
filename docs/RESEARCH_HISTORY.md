# Historique des recherches — IA de trading (15/09/2026 → 20/10/2026)

Compilé le 20/10/2026, en lecture seule, à partir de : `CLAUDE.md`, la mémoire du projet
(`C:\Users\utilisateur\.claude\projects\c--Users-utilisateur-Documents-Test-IA\memory\*.md`), `collapsar/docs/*`,
les `rapport.md` de `collapsar/vie/`, `archive/magnetar/`, `etudes/2026-10-20_*`, `reports/*.md`, les manifestes
d'archives et le journal git. Le registre ligne par ligne est dans `etudes/REGISTRE_IDEES.csv` (105 idées).

**Légende des sources**
- **[F]** = chiffre lu dans un fichier de résultats qui existe (rapport, json, csv).
- **[R]** = rapporté seulement (mémoire, `CLAUDE.md` ou `REPRISE.md`) : aucun fichier de résultats retrouvé.
- « Jumeau » = mêmes moments, mêmes stops et tailles, sens tiré à pile ou face. « Force » = écart ÷ incertitude
  (preuve en général à partir de 3). R = gain d'un trade en multiples de son risque, frais compris.
- Chemins relatifs à `C:\Users\utilisateur\Documents\Test_IA\` ; `RA/` = `runs/20260919_envv2/code/`.

Journal git (12 commits) : `d7664b7` 11/09 commit initial ; `795cac3`, `b9621f7` 17/09 mise en ligne de la v1 ;
puis 20/10 : `cb7877f` état final de MAGNETAR, `6e45681` archivage + création de `core/`, `90b2168` revérification
des anciens agents, `7221734`/`62a26e7` plan figé couche 1, `6e3604d` correctif de mesure, `b053fa9` résultat couche 1
perception, `c8f6aa6`/`30526b6` tendance de fond (plan figé puis résultat + défaut déclaré).

---

## Phase 1 — v1 : un agent par unité de temps (15/09 → 19/09)

- **Quoi** : un agent (mémoire courte + apprentissage par renforcement) par unité M15, M30, H1, H4, D1, or seul,
  évolution par générations (208 générations au compteur, ~200 par style). Démo réelle sur petit compte.
- **Chiffres** : Sharpe 1,4 à 7,5 et +23 % à +140 % sur une tranche de validation **qui servait aussi à choisir**
  (pas hors échantillon ; Sharpe D1/H4 gonflé ×5/×2,5 par une erreur de calcul). Démo réelle : **-6,2 % en 33 h**,
  11 trades perdants sur 11 le 17/09 au soir. [F] `etudes/2026-10-20_agents_par_unite/RAPPORT.md`,
  `archives/v1_septembre/models/_progress.json`, `archives/v1_septembre/reports/RAPPORT_AUDIT_TACHES_1_7.md`.
- **Audit du 19/09** (7 tâches) : test de fuite « réussi » mais fait sur un agent-sonde, pas sur les champions. [F]
  `archives/v1_septembre/reports/RAPPORT_AUDIT_TACHES_1_7.md`.
- **Verdict** : négatif (apprentissage par cœur de la validation).

## Phase 2 — Run A (19/09 → 13/10)

### 2.1 Évolution par styles (19/09 → 01/10)
- Environnement v2 (stop en ATR, plusieurs paires, période gardée de côté) [F] `archives/v1_septembre/reports/RAPPORT_LOT2.md`.
- 5 styles relancés de zéro. Remise à zéro le 23/09 (génération 413, score H1 aberrant de 247) et le 01/10
  (génération 844, 814 cycles sans progrès, meilleur score aberrant 92,1). [F] `archives/run_a/reports_archive_20261001_1800_pre_fundamental_reset/`.
- **Verdict** : négatif (plateau, scores sans sens).

### 2.2 Styles H1, H1T, H1X, H1XT, M30, H4 (04/10 → 05/10)
- Période gardée de côté = 06/2023 → 10/2026 (consultée de nombreuses fois, donc pas vraiment neuve).
- **H1T** (objectif de gain appris) g229 : Sharpe 0,67, +37,8 %, FTMO simulé 49 %. **H1X** (+17 variables hors or :
  devises, argent, taux réels, dollar, VIX) g215 : Sharpe 0,76, baisse 27,6 %, FTMO simulé 60 %. **H1XT** : 0,394,
  jamais éligible [R]. M30 (à plat 75 % du temps) et H4 retirés.
- Simulateur FTMO : H1 53 %, H1T 46 %, H1X 60 % de réussite simulée [R] (résultat seulement affiché, `RA/scripts/ftmo_sim.py`).
- Repère : l'or simplement acheté et gardé fait **+109 %, Sharpe 1,15, FTMO 65 %** sur la même période → les styles
  ne battent pas l'achat simple. [F] `RA/reports/regime_report.md`, `RA/reports/diagnostics.md`.
- Revérification du 20/10 (jamais vu + jumeau) : H1 g838 -0,32 ± 0,20 %/mois sur le jumeau, H1T +0,30 ± 0,30,
  H1X -0,21 ± 0,23, H4 g65 aucun trade, M30 g67 -0,02. [F] `etudes/2026-10-20_agents_par_unite/RAPPORT.md`.
- **Verdict** : négatif.

### 2.3 Recherches annexes du 05/10 au 07/10 (toutes négatives)
| Idée | Essais | Chiffres clés | Source |
|---|---|---|---|
| Vision « Trading GPT V1 » (filtres de régime) | 6 filtres | 1 gardé (Sharpe 0,74 → 0,85), 5 rejetés | [F] `RA/reports/research_journal.jsonl`, `docs/IDEE_TRADING_GPT_V1.md` |
| Cerveau de marché quotidien (macro FRED) | 6 | pouvoir de tri 0,48-0,52 (hasard = 0,5) | [F] `RA/reports/brain_research.md` |
| Trader à règles (action des prix) | 4 + 7 variantes | -0,15 à -0,26 R ; rien même sans frais | [F] `RA/reports/trader_backtest.md`, `trader_variants.md` |
| Découverte automatique de schémas | 105 744 | 416 retenus, **0 confirmé** en 2019-04/2023 | [F] `RA/reports/trader_discovery.md` |
| Juge de schémas M15 / longue durée | 2 | +0,06 R ; +0,19 R battu par « toujours acheter » +0,30 R | [F] `RA/reports/setup_judge*.json` |
| Suivi de tendance journalier, 5 marchés | 2 | cassure +0,23 puis -0,21 R ; repli +0,07 puis +0,01 R | [F] `RA/reports/trend_trader.md` |
| Test d'information (macro, COT, marchés liés) | inconnu | rien de stable ; COT t = -2,5 puis s'inverse | [F] `RA/reports/info_test.md` |
| Boîte à outils 86 indicateurs + cerveau 512 | 1 | validation 1,06 mais Sharpe 0,24 sur la période gardée | [R] mémoire |
| Auto-amélioration des réglages de récompense | inconnu | aucun gain net | [F] `RA/reports/experiment_journal.jsonl` |

### 2.4 AUREX (05/10 → 13/10) — la seule IA qui a tradé en démo
- IA M15 qui voit toutes les unités, ordres au marché ou limite, gestion du trade. Champion **génération 253**.
- Période gardée de côté : +42 %, Sharpe 1,06-1,08, baisse 12,1 %, 812 trades, encore +20 % à frais doublés
  [F] `RA/reports/lockbox_AUREX.json`. Taille au risque : 0,5 % → +54 %, FTMO 48 % ; 1 % → +91 %, baisse 32,6 %
  [F] `RA/reports/r_sizing_AUREX.json`.
- **Mais** : 812 achats sur 812. Avantage seulement sur l'or 2023-26 (+0,131 R) ; or 2010-18 : -0,009 R
  [F] `RA/reports/aurex_judge.json`. Juge des trades inutile (gardés +0,125 R, rejetés +0,137 R).
- Règle « pas d'achat contre la tendance journalière » : 2010-18 +0,030 R, baisse 23,7 % → 7,3 %, mise en démo le 07/10
  [F] `RA/logs/judge_trend.txt` → **positif non prouvé** (seul résultat utile de Run A).
- Revérification du 20/10 : **-0,37 %/mois sur 2010-2017** ; avance +0,39 sur le jumeau due au seul penchant acheteur.
  [F] `etudes/2026-10-20_agents_par_unite/resultats/AUREX.json`.
- Arrêté le 13/10 00h55, solde démo <solde démo> [R] `CLAUDE.md`.
- **Verdict** : négatif (penchant acheteur sur un or en hausse).

### 2.5 AUREXIS — multi-marchés (06/10 → 13/10)
- Une seule IA sur l'or + 5, puis 22 (dont 11 marchés « miroirs » inversés pour apprendre à vendre), puis ~45 marchés
  FTMO. **~290 cycles** (265 → ~557, 2 à 7 candidats par cycle ; 255 notés dans `RA/reports/carnet_marches.json`).
  Repartie de zéro le 08/10 (cycle 341).
- 07/10, examen marché par marché : EURUSD -29 %, USDJPY -17 %, US500 +0,2 % (le marché +85 %), or miroir -44 %
  [F] `RA/reports/aurexis_marches.json`.
- Entraînements longs r1-r15 : l'IA finit par ne plus trader ; r14 Sharpe 0,98 mais -2,3 % à frais doublés
  [F] `RA/reports/long_AUREXIS.json`.
- Récompense trade par trade (3 essais) : meilleur -0,239 contre -0,397, puis inactivité [F] `RA/reports/examen_trade_r.json`.
- Veines (4 lignées) : toutes mortes [R]. Trois outils + note « argent FTMO » : la 1re note favorisait le « casino » [R].
- 09/10, **12 mois cachés** (10/2025 → 10/2026), génération 391 : compte **-79 %**, 32 marchés sur 36 perdants,
  99 % de 352 challenges ratés [F] `RA/reports/prediction_12_mois.json`. Leçon : une période d'examen fixe fabrique
  des IA adaptées à cette période → examen tournant (105 jours tirés entre 01/2023 et 09/2025).
- Professeur tendance (imitation) : 12 mois cachés -20 % (la règle seule +6,4 %) [F] `RA/reports/prediction_12_mois_professeur.json`.
- Vision des tendances (veine PROF_0910) : cycle 399 +1,24 puis +1,92 %/mois à l'examen [F]
  `RA/reports/prediction_12_mois_champion399.json` ; mais en **compte fidèle** sur 12 mois cachés : g408 -7,2 %,
  g424 -2,6 %, g445 -9,3 %, g503 -4,8 %, g539 -8,1 % → **aucun champion positif** [F] `RA/reports/verdict_12_mois_historique.json`.
- **Verdict** : négatif.

### 2.6 Moteurs et sources d'information (08/10)
| Idée | Essais | Chiffres | Verdict | Source |
|---|---|---|---|---|
| Moteur de prédiction supervisé (2,54 M lignes, 10 marchés) | 3 | +0,033 à +0,065 R, FTMO 4-26 %, lien 0,015-0,046 | positif non prouvé (faible, moins bien qu'AUREX) | [F] `RA/reports/moteur_prediction*.json` |
| Flux d'ordres Dukascopy (or, 28,6 M cotations) | inconnu | aucun signe stable | négatif | [F] `RA/reports/flux_ordres_XAUUSD.json` |
| Portage + tendance, 7 grandes devises | 3 | portage -3,8 %/an, combiné -4,3 %/an (2014-21) | négatif | [F] `RA/reports/moteur_devises.json` |
| Repère tendance de fond 36 marchés (10 %/an de volatilité) | 1 | +0,53 %/mois 2018-25, Sharpe 0,46, baisse 19 % | positif non prouvé | [R] `CLAUDE.md` §5 (script de brouillon introuvable) |

## Phase 3 — COLLAPSAR (12/10 → 16/10)

Idée : « un enfant devant un graphique MT5 », un trader humain numérique, seules les limites FTMO imposées
(`collapsar/docs/CONCEPTION.md`).

### 3.1 Arbres, racines et écoles (13/10 → 14/10)
| Idée | Essais | Chiffres | Source |
|---|---|---|---|
| Arbre 1 : racines 2018 → mi-2022, 47 marchés | inconnu | 69-99 % de sens juste sur les années apprises, **52 %** ailleurs | [F] `collapsar/docs/CONCEPTION.md` §13, `collapsar/archives/2026-10-16_vie/arbre1_13oct_2018-2022` |
| École classe 1 + « tenir son avis » | inconnu | sans miroir -2,15 %/mois, 73 % de murs ; avant frais +1,8 %/mois, après frais négatif | [F] CONCEPTION §13, `archives/2026-10-16_vie/resultats_racine_vie/` |
| École par avis | inconnu | gain brut ≈ écart payé (~40 changements/mois), net ≤ 0 | [R] `memory/new-child-ai-project.md` |
| Arbre 2 : racines 2010-2019 (2 ans contre 10 ans d'historique) | 6 | **50,2 % contre 50,9 %** (mémoire) ou 49,9 contre 50,5 % (CONCEPTION) ; plafond ~50,8 % | [F] `collapsar/archives/2026-10-16_pistes/vie/experience_donnees.json` |
| École A3, grand examen (192 challenges, 12 marchés) | 1 | +0,00 %/mois, 0 % de murs | [F] `archives/2026-10-16_vie/resultats_racine_vie/grand_examen_20261014_*.json` |
| Arbre 3 « vision du trader » (aucun menu de coups) | 4 | -7,8 puis -1,0 / +0,03 / -0,7 % du risque ; années apprises +85 à +97 % contre -3 à -5 % ; verdict rapide -0,17 %/mois | [F] `archives/2026-10-16_vie/arbre3_14oct`, `verdict_rapide_*.json` |
| Expériences de vision (par cœur, vue 49 nombres, simple, semaine) | 7 | apprend la **date** par cœur ; semaine -0,28 / +0,36 / +0,49 %/mois, instable | [F] `archives/2026-10-16_pistes/vie/experience_*.json` |
| Annonces économiques | inconnu | 1re version +0,17 à +0,82 %/mois = **fuite** (heures fausses) ; heures justes : -1 % sur 3 mois cachés | [F] `archives/2026-10-16_vie/resultats_racine_vie/examen_annonces_*.json` |
| École « elle choisit quand revenir regarder » | 3 | 1er élève paralysé, 3e ~-0,05 %/mois | [R] `collapsar/docs/REPRISE.md` §6 bis |
| **École des mille mondes** (marchés inventés à lois cachées) | 906 leçons | faux euro : appris +3,31, jamais vu -0,95 %/mois ; meilleur élève +0,10 %/mois, force 1,1, 0 challenge | [F] `collapsar/vie/ecole_mondes/controles.jsonl`, `collapsar/vie/note_collapsar_corrigee/rapport.md` |

Nombre total de mondes inventés : jamais écrit (~6 par leçon → quelques milliers, estimation).
**Verdict de la phase** : négatif. Les racines plafonnent à ~51 % de sens juste ; l'école apprend par cœur.

### 3.2 Science, maîtres et méthodes de trader (15/10)
| Idée | Essais | Chiffres | Source |
|---|---|---|---|
| Tendance 60 jours, 23 marchés, 2010-2019 | inconnu | sans frais +0,39 / +0,41, avec frais -0,15 / -0,09 %/mois | [F] `archives/2026-10-16_pistes/vie/mesures_science_2010_2019.json` |
| Tendance sans la nuit (43 marchés) | 3 | avant frais +0,08 ; après -0,20 / -0,26 | [F] `archives/2026-10-16_pistes/vie/tendance_sans_nuit.json` |
| Maîtres (Paul Wei, gTrade, Ostium, Hyperliquid ; 14 902 traders examinés) | inconnu | imitation 59 % puis 46 % (par cœur) ; leur avantage = être du bon côté de la tendance | [F] `collapsar/vie/ecole_maitres/persistance.json` |
| Foule Ostium (16 marchés) | 1 | suit le passé (force +7), n'annonce rien (force -1,1) | [R] REPRISE §6 septies |
| Cassure de l'ouverture de New York | 18 | cachée 2024-26 : Nasdaq +0,009 R, S&P -0,115 R, or -0,082 R | [F] `collapsar/vie/orb/cachee.json` |
| **Laboratoire SMC** (or, Nasdaq, S&P, euro) | 366 | tout INUTILE ou FAIBLE ; seul candidat -0,047 R sur la cachée | [F] `reports/Laboratoire SMC.md` |
| Multi-unités du chef (zone H4, entrée M15) | 72 | +0,27 R puis -0,40 à -0,49 R en 2022-23 | [F] `collapsar/docs/SMC_MULTI_UT.md` |
| Cascade indicateur zones supply and demand | 22 | médiane -1,16 R, 28 % de gagnants | [F] `collapsar/docs/CASCADE_ZONES.md` |
| Zones gigognes | 8 | +0,30 R grâce à **un** trade à +817 R, médiane -1,2 R | [F] NONO_CASCADE avenant 1 |
| Stop minimum (plancher) | 6 | ~0 R | [F] NONO_CASCADE avenant 2 |
| Stratégie du chef sur la cachée 2024-26 + 4 filtres de tendance | 5 | -0,27 R (4 marchés), -0,34 R (45) ; avec la tendance -0,43 à -0,84 R | [F] `collapsar/vie/smc/cachee_strategie_chef.json` |

Famille SMC / zones du chef au 15/10 : 366 + 72 + 22 + 8 + 6 = **474 variantes cumulées** (seuil de preuve
relevé à 3,51). ⚠️ Tous ces chiffres de zones sont antérieurs à la découverte du **défaut d'heures** (16/10, §3.4).

### 3.3 Pistes des chercheurs-testeurs (nuit du 15 au 16/10, règles `collapsar/docs/BRIEF_PISTES.md`)
Réfutées puis rangées le 16/10 (`collapsar/archives/2026-10-16_pistes/MANIFESTE.txt` : 16 pistes + 11 expériences) :
| Piste | Essais | Chiffres | Source [F] |
|---|---|---|---|
| Bande de bruit (Zarattini 2024) + second avis | 2 | +0,00 / +0,91 / **-0,26 %/mois** (cachée) | `collapsar/vie/bande_bruit/cachee.json` |
| Bande de bruit, 7 autres indices | inconnu | rien même avant frais | `archives/2026-10-16_pistes/vie/pistes/bande_monde` |
| Tendance + moment d'entrée | 12 | -0,51 à -1,93 %/mois (nuits FTMO 3-13 %/an) | `.../pistes/tendance_timing/rapport.md` |
| Paires de valeur | 10 | +0,1 %/mois, force 2,3 | `.../pistes/paires_valeur` |
| Effets d'heure / calendrier (dont « l'or monte en Asie ») | 12 | ensemble -2,9 %/mois ; or-Asie mort après correction d'heure | `.../pistes/calendrier_horaires` |
| Achat des creux des indices / v2 / ingénierie du challenge | 11 + 4 + 11 | effet réel mais krachs simultanés ; espérance -273 à -540 € par challenge | `.../pistes/indices_creux`, `creux_v2`, `ingenierie_challenge` |
| Tendance crypto de plusieurs jours | 12 | nuits 30 %/an, espérance -540 € | `.../pistes/crypto_tendance/rapport.md` |
| Cassure sur indices, 14 cryptos, devises, fausse cassure | inconnu + 12 + 6 | perd même avant frais | `.../pistes/cassure_autres`, `cassure_devises`, `fausse_cassure_devises` |
| Réaction au milieu des zones | inconnu | 38 % (ses zones) contre 39 % (fausses zones) | `.../pistes/zones_milieu` |

### 3.4 Pistes du 16/10 encore actives (`collapsar/vie/pistes/*/rapport.md`, toutes [F])
| Piste | Essais | Chiffres | Verdict |
|---|---|---|---|
| Bitcoin dans la journée | 8 | règle retenue D1 (force 3,71) s'effondre en 2022-23 | négatif |
| **Cassure 24 h du bitcoin (C2)** | 2 sur 8 | cachée 2024-26 : +1,11 %/mois (frais 0,01 %), +0,42 (0,1 %) ; 71 % de challenges contre 10 % aux jumeaux ; force 2,10 < 3 ; 2025 négatif ; **avec la commission FTMO ~+0,5 %/mois** | positif non prouvé (démo Tradeco depuis le 16/10 00h43) |
| Cassure v3 (8 améliorations) | 14 | BTC+ETH +1,48 %/mois (années vues) ; **groupe B en échec** | positif non prouvé |
| COLLAPSAR choisit la taille de la cassure | 2 | lien prévu/réel ≈ 0 | négatif |
| Zones du chef sur cryptos | 4 | groupe B jamais vu +0,26 R, force 1,9 | positif non prouvé |
| Compte FTMO zones du chef | 1 | +0,15 %/mois, espérance -469 € | négatif (trop lent) |
| Combinaisons SMC apprises | 48 | cryptos -1,14 %/mois ; fausses zones font mieux | négatif |
| Compte combiné cassure + zones | 3 | +0,66 %/mois, +2 826 € par challenge (années vues) | positif non prouvé |
| **Contre la foule (C1)**, Binance | 11 | force 4,5 / 3,3 / 3,5 (information réelle) ; après frais FTMO +1,76 / +0,88 / **+0,06** %/mois, baisse 37-55 % | positif non prouvé (tué par les frais FTMO) |
| Contre la foule sur devises (CFTC) | 6 | -0,49 à -2,62 %/mois | négatif |
| Trois briques simulées ensemble | 1 | 2024-26 +0,19 %/mois, -371 € | négatif |
| C1 chez HyroTrader | 12 | +1,06 %/mois si 70 % d'ordres faiseurs (non mesuré) | positif non prouvé |
| Peur lue dans les options (VIX) | 9 | +0,31 / +0,23 / +0,33 %/mois, 53 trades en 15 ans | positif non prouvé (inutilisable seul) |
| École crypto n°1 | 109 leçons | -1,06 %/mois | négatif |
| École crypto n°2 (C1/C2 sous les yeux) | 638 leçons | cachée +0,06 %/mois (C2 seule +0,60) | positif non prouvé |
| Zones déjà touchées (2e/3e contact) | 30 | -0,34 à +0,16 R | négatif |

**Audit du juge (16/10)** [F] `collapsar/vie/audit/rapport.md` : heures lues en microsecondes au lieu de
nanosecondes (zones confirmées ~166 jours trop tard) ; force non pesée par la taille ; frais ×1,25 pessimistes ;
commission crypto oubliée (optimiste). Après réparation :
- **Verdict des zones** (71 lignes) : une seule tient, cryptos H4 ancienne traduction, +0,22 R, force 2,5, compte
  +0,31 %/mois mais 23 mois par challenge [F] `collapsar/vie/pistes/verdict_zones_corrige/rapport.md`.
- **Note de COLLAPSAR** : +0,1 à +0,2 %/mois, meilleure version (école crypto n°2) +0,13 à +0,46 %/mois, force ≤ 1,7
  [F] `collapsar/vie/note_collapsar_corrigee/rapport.md`.

## Phase 4 — École de la précision : HYPERNOVA puis MAGNETAR (16/10 → 20/10)

### 4.1 HYPERNOVA (~66 marchés) et ses études
- Arbre : zones gigognes, stop derrière la structure, sortie 80/20, l'IA choisit tout. **1 000 générations × 4 branches**
  (ordre : au moins 1 000). Essais 3 et 100 générations : -0,54 et -0,23 %/mois sur 2024-25 [F] `collapsar/vie/hypernova_essai*/rapport.md`.
- Génération 1000 : sélection +0,19 %/mois ; **contrôle 01/2024-09/2025 -0,15 %/mois** (jumeau -0,19), avance
  +0,04 ± 0,12, R -0,004. Plateau vers 330-391, yeux de la foule greffés à la 391 (les périodes ne concordent pas
  entre le rapport et la mémoire). [F] `archive/magnetar/vie/hypernova/rapport.md`.
| Étude | Essais | Chiffres | Source [F] |
|---|---|---|---|
| Juger un trade (6,4 M candidats) | 1 | 10 % du haut -0,019 R ; fausses zones -0,025 R | `archive/magnetar/vie/hypernova/juge_trade/rapport.md` |
| Direction + précision | 43 cases | aucune case positive sur 2023 et 2024-25 | `.../hypernova/direction/rapport.md` |
| Logique inversée | 18 | +0,033 puis +0,008 R (force 0,3) | `.../hypernova/logique_inversee/rapport.md` |
| Mouvements du jour | 255 cases | -0,13 / -0,13 / -0,12 R ; même en connaissant le sens, peu à gagner | `.../hypernova/mouvements/rapport.md` |
| Yeux du monde (GPR, EPU, VIX, OVX, GVZ) | 1 000 cases | -0,01 / +0,11 / -0,05 R | `.../hypernova/monde/rapport.md` |
| Avis sur les marchés (43 informations) | 7 | ne bat pas « les marchés montent un peu » | `.../hypernova/avis/rapport.md` |
| Mémoire des situations (or, plus proches voisins) | 9 | trading -0,006 R | `collapsar/vie/memoire/rapport.md` |
| Cerveau de mouche (Stonkfly) | 0 | jamais lancé (refusé) | `collapsar/vie/stonkfly/rapport.md` (inconclusif) |

### 4.2 MAGNETAR (or seul, 18/10 → 20/10)
- Un seul cerveau décide tout sur l'or réel + « retourné ». **285 générations × 4 branches** [F] `archive/magnetar/README.md`.
- Génération 250 : sélection -0,06 %/mois (jumeau -0,52) ; **contrôle 01/2024-09/2025 -0,52 %/mois** (jumeau -0,70),
  avance +0,18 ± 0,58, 0 % de trades à 5R ou plus, 97 % d'achats [F] `archive/magnetar/vie/arbre_or/rapport.md`.
| Essai | Essais | Chiffres | Verdict | Source [F] |
|---|---|---|---|---|
| Forcer à tenir (contrefactuel) | 6 sorties | main +0,025 R, meilleure +0,027 R | négatif | `archive/magnetar/vie/arbre_or/contrefactuel/rapport.md` |
| Stops serrés + branche S | 1 | -0,003 R sur le jumeau (le +0,131 R venait d'un tri biaisé) | négatif | `.../arbre_or/precision/rapport.md` |
| Tendance F2 + stop suiveur G2 + examen tournant | 3 | G2 +0,52 ± 0,67 sur 2024-25 | inconclusif | `.../arbre_or/trois_changements/rapport.md` |
| Mentor à règles + apprentie | 2 | mentor -0,14 %/mois, 86 % de challenges morts d'inactivité | négatif | `.../arbre_or/mentor/rapport.md` |
| Maîtres MQL5 (Gold Reaper) | 3 | Gold Reaper force 4,5, FTMO simulé +2,6 %/mois | **prouvé, mais c'est un tiers** | `collapsar/vie/maitres_mql5/rapport.md` |
| Imitation de Gold Reaper | 1 | ouvre comme lui 14 % du temps | inconclusif (en pause) | `.../arbre_or/gold_reaper/rapport.md` |
| Règle Gold Reaper reconstruite | 1 | -4,9 % du risque par décision, 2 ans gagnants sur 9 | négatif | `collapsar/vie/etude_gold_reaper/rapport.md` |
| Maîtres Synthetix (1 799 traders) | inconnu | aucun à force ≥ 3 | négatif | `collapsar/vie/maitres_synthetix/rapport.md` |
| Positions COT sur l'or | 27 | force max 1,0 (seuil 3,80) | négatif | `collapsar/vie/cot_or/rapport.md` |
| Scalping de l'or (3 méthodes publiées) | 5 | -0,06 à -0,47 R ; frais 0,8-2 $/once | négatif | `collapsar/vie/scalping_or/rapport.md` |

**Audit du 20/10, génération 282** [F] `archive/magnetar/vie/arbre_or/audit_manques/rapport.md` :
- gain réel **resté vers -0,1 %/mois de la génération 1 à 282** ; l'écart au jumeau grandissait parce que le jumeau baissait ;
- avant frais un trade vaut +0,02 R, les frais en coûtent 0,07 R ;
- juge contaminé (26 blocs d'examen sur 28 déjà appris) et examen qui ne tourne plus ;
- note qui récompense « perdre moins que le hasard » ;
- apprentissage éteint (vitesse au plancher) ;
- ordres limites « parqués » bloquant les ouvertures (92 % des vrais trades au marché) ;
- boucle de l'apprentie ;
- ni annonces, ni niveaux de trader ;
- taille tout ou rien.

Conclusion de l'audit : aucun réglage ne fera gagner tant qu'aucune information ne donne le sens au-dessus des frais.
→ MAGNETAR archivé le 20/10 (tag `magnetar-final`).

## Phase 5 — Cerveau modulaire (20/10)
Architecture « zones du cerveau » sur l'or seul, une couche à la fois, chaque couche jugée hors échantillon contre le
jumeau [R] `memory/cerveau-modulaire.md`. Plans figés et commités AVANT chaque test.
| Étude | Essais | Chiffres | Verdict | Source [F] |
|---|---|---|---|---|
| Revérification des anciens agents par unité (v1 + Run A) | 11 agents (4 à 6 jumeaux chacun) | aucun ne choisit le sens mieux que pile ou face sur du jamais vu ; AUREX -0,37 %/mois en 2010-17 | négatif | `etudes/2026-10-20_agents_par_unite/RAPPORT.md` |
| Couche 1 perception : zones codées à la main (D1/H4/H1/M15) | 16 comparaisons (4 unités × 2 mesures × 2 juges) | test verrouillé 2018 → 13/10/2026 : rien ne bat un juge ; M15 avec gestion -0,48 R/trade ; 1er lancement biaisé (+0,39) corrigé (+0,13 ± 0,10) | négatif | `etudes/2026-10-20_couche1_perception/RAPPORT.md` |
| Couche 1 tendance de fond (N = 1/3/6/12 mois) | 24 (4 N × 6 marchés) | or N=3 +0,61 ± 0,24 sur pile ou face mais jamais mieux que l'acheteur permanent ; 1 marché sur 5 positif ; 60-95 % des challenges morts d'inactivité ; défaut du plan (taille figée) déclaré | négatif | `etudes/2026-10-20_couche1_tendance/RAPPORT.md` |

## Documents de recherche (lectures, pas d'essai de stratégie)
- `reports/Études de marché pour COLLAPSAR.md` (14/10) : l'agitation se prévoit, la direction résiste ; 65 % de
  452 anomalies publiées ne se reproduisent pas ; 74-89 % des comptes CFD perdent.
- `reports/Risque agitation et tendance courte.md` (15/10) : petite mesure maison (agitation du quart d'heure suivant
  prévisible à 58-69 %) ; sans avantage, ~24 % de réussite FTMO avec frais ; FTMO interdit les « IA non autorisées ».
- `reports/Vivre de son IA de trading.md` (18/10) : viser ~1 %/mois ; 8-10 %/mois sans précédent documenté.
- `research_notes/` : notes brutes (foule devises, conditions FTMO crypto, firmes crypto, daytrading rentable, sources de maîtres…).

---

## Leçons
1. **Aucune idée ne bat le hasard, de façon prouvée et après frais FTMO, sur des données jamais vues.** Seul avantage
   prouvé trouvé : celui d'un trader extérieur (Gold Reaper), que nous n'avons pas su reproduire.
2. Les « bons résultats » venaient de trois pièges : données déjà vues (validation qui sert à choisir, période gardée
   de côté consultée souvent), **penchant acheteur sur un or en hausse**, et un jumeau qui perd plutôt qu'une IA qui gagne.
3. **Les frais** mangent les petits avantages (C1, scalping, M15 : 0,07 à 0,6 R par trade) ; plus on trade petit et
   souvent, pire c'est. Les nuits FTMO tuent les tendances longues.
4. Les cerveaux libres (Run A, COLLAPSAR, HYPERNOVA, MAGNETAR) **apprennent par cœur** leurs années (et même la date) ;
   plus de générations n'a jamais fait monter le gain réel.
5. Erreurs de mesure trouvées tard et lourdes de conséquences : heures µs/ns, bougie d'entrée, fuite d'heure des
   annonces, tri « fermés à la main », taille figée des années. **Figer le plan avant le test** (pratique du 20/10) les attrape.
6. Seuls signes positifs mais non prouvés : cassure 24 h du bitcoin, contre la foule (information réelle, frais
   trop lourds), zones du chef sur cryptos H4, peur des options, tendance de fond multi-marchés (~+0,5 %/mois).
7. La règle FTMO des 30 jours sans trade tue les stratégies lentes.

## Ce qui n'a jamais été testé (mentionné explicitement dans les sources)
- `collapsar/docs/SCALPING_QUI_MARCHE.md` :
  - suivre la tendance née d'une annonce 30-60 min après ;
  - flux de fin de séance de l'or (clôture à terme 13h30 New York) ;
  - retour vers le prix moyen pondéré par les volumes ;
  - niveaux ronds pour placer stop et objectif.
  (Ses méthodes A, B et C ont été testées le 20/10 : toutes négatives.)
- Recherche « daytrading rentable » :
  - bouclier de volatilité ;
  - tendance de fond + entrée dans la journée (sous cette forme) ;
  - mondes inventés calqués sur les lois réelles ;
  - bande de bruit comme moment d'entrée d'une position longue.
- Contre la foule :
  - C1 sur devises avec l'historique OANDA (jeton jamais obtenu) ;
  - C1 réel à coûts de bourse ou CME (seulement estimé).
- Zones et briques :
  - étude de la réaction des zones demandée le 15/10 (« pas lancée ») ;
  - « 2e fois au milieu » non vérifié ;
  - groupe B de la fausse cassure jamais ouvert ;
  - un couple de briques de l'ingénierie du challenge ;
  - l'or dans l'achat des creux.
- Gold Reaper : greffe jamais faite.
- Écart réel du bitcoin chez FTMO aux heures pleines : jamais relevé.
- Historique réel des trades du chef : jamais reçu.
- Couche 1 tendance : correction « taille recalculée chaque jour » proposée, non lancée.

## Totaux (registre `etudes/REGISTRE_IDEES.csv`)
- **105 idées / familles** :
  - 88 négatives ;
  - 11 positives non prouvées ;
  - 5 inconclusives ;
  - 1 « prouvée » (Gold Reaper, un tiers).
- **Essais connus : 117 504**. Ce total contient les 105 744 schémas de la découverte automatique (I010) ; **sans eux : 11 760**.
- **16 idées** ont un nombre d'essais « inconnu ».
- Attention : les unités ne sont pas homogènes. Le total additionne des générations (v1 1 040, Run A 844,
  HYPERNOVA 4 000, MAGNETAR 1 140), des cycles (AUREXIS 290), des leçons (mille mondes 906, écoles crypto 747),
  des variantes et des cases. C'est un ordre de grandeur, pas un compte exact de candidats entraînés.

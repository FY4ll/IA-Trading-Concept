# CARTE de COLLAPSAR — où est quoi (16/10/2026 soir, après le rangement)

Tout se lance depuis `Test_IA` : `venv_gpu\Scripts\python.exe -u -m collapsar.<dossier>.<programme>`.
Tests : `$env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\Scripts\python.exe -m pytest collapsar/tests -q`.
L'histoire complète et les chiffres : `docs/REPRISE.md` (bloc « ÉTAT AU 16/10 SOIR » en tête).

## 1. Ce qui tourne (surveillé par la tâche Windows « TestIA_CollapsarGardien », `surveillance/gardien.ps1`, toutes les 10 min)

| Programme | Rôle | État / journal | Arrêt volontaire |
|---|---|---|---|
| `direct.bitcoin_cassure` | démo Tradeco : cassure 24 h du bitcoin (numéro 16102027) | `vie/direct/bitcoin_cassure.json`, `vie/logs/bitcoin_cassure.txt` | créer `vie/direct/BITCOIN_ARRET` |
| `direct.chef_zones` | démo Tradeco : zones gigognes du chef sur BTC/ETH (16102028) | `vie/direct/chef_zones.json` | `vie/direct/CHEF_ARRET` |
| `direct.foule_blanc` | suivi à blanc « contre la foule » C1 (aucun ordre) | `vie/direct/foule_blanc.json`, `vie/direct/foule_historique/` | `vie/direct/FOULE_ARRET` |
| `direct.blanc` | démo à blanc de l'élève des mille mondes (leçon 748), recopie Tradeco selon `vie/direct/mode.json` | `vie/direct/blanc.json` | `vie/direct/ARRET` |
| `ecole.controleur_mondes` | contrôleur de l'école des mille mondes | `vie/ecole_mondes/` | (tuer le processus) |
| `maitres.gtrade`, `maitres.ostium` | collecteurs des trades publics (gTrade, Ostium) | `Test_IA/data/maitres/gtrade/`, `.../ostium/` | (tuer le processus) |
| `donnees.foule_devises boucle` | collecteur foule devises (gTrade + CFTC), sans tâche Windows | `data/foule_devises/direct/` | `data/foule_devises/direct/ARRET` |
| `surveillance.releve_ecarts seance` | relevé des écarts MT5 15h30-22h00 | `vie/ecarts/`, `vie/releves/` | s'arrête seul |
| `ecole.precision.coeur --generations 1000` | arbre HYPERNOVA (école de la précision, ~66 marchés) | `vie/hypernova/` (journal `logs/coeur_foule.txt`) | `vie/hypernova/ARRET` (pause : `PAUSE`) |
| `ecole.precision.arbre_or --generations 1000` | ARBRE DE L'OR (18/10, nom provisoire MAGNETAR = ligne `nom:` de `ecole/precision/reglages_or.yaml`) : même cœur qu'HYPERNOVA, l'or seul réel + retourné, examen 2023 sur l'or, graine copiée de la cime d'HYPERNOVA (`ecole/precision/graine.py`) ; rapport : `arbre_or --rapport`. **18/10 soir : STOP SUIVEUR** derrière la structure (`ecole/precision/suiveur.py`, réglage `mains.suiveur` de `reglages_or.yaml`, éteint pour HYPERNOVA ; greffé sans perte le 18/10 18h12, sauvegarde `vie/arbre_or/sauvegardes/avant_suiveur_*`, retour arrière `arbre_or --defaire-suiveur` ; branche « laisse_courir » ; testé `tests/test_suiveur.py`, empreinte d'HYPERNOVA `tests/donnees/empreinte_hypernova.npz`) | `vie/arbre_or/` (journaux `logs/coeur_*.txt`, `rapport.md`) | `vie/arbre_or/ARRET` (pause : `PAUSE`) |

**19/10 nuit (ordre du chef de projet) : LE MENTOR ET SON APPRENTIE** (`ecole/precision/mentor.py`, plan FIGÉ avant
mesure `vie/arbre_or/mentor/plan_fige.md`, mesures `mentor/mesure_v1.json`, imitation `mentor/apprentie.pt|.json`,
`mentor/accord_periodes_neuves.json`, rapport `mentor/rapport.md`). Le mentor = programme fixe dans les gestes des mains :
décision à la clôture des bougies de 4 h, sens = tendances 20/60/120 j d'accord, ordre limite au bord proche de la zone
4 h puis 1 h touchée + réagie, stop derrière (<= 0,4 agitation), 0,5 %, laisser courir, suiveur « 4 h après +1R ».
Mesure : `python -m collapsar.ecole.precision.mentor mesurer` (juge habituel ; le mentor joue via `mentor_a_l_examen`,
rien de changé dans jeu.py). Apprentie = UNE branche née de la cime symétrique N2 (symétrie, stops proches, journal
gardés) + yeux de la tendance, suiveur après +1R, REGARDS PLUS ESPACÉS (8 h, 1 jour : `cerveau.REGARDS_LONGS`, inerte
sans eux) ; imitation (`mentor preparer`), puis dans l'arbre « récompense en laisse » (`mentor.apprendre_en_laisse`,
appelé par coeur.py si le tempérament a `mentor` ; laisse = 0,8^(générations depuis la naissance)) ; jeunesse propre de
12 générations (tempérament `jeunesse`). Marque `[APPRENTIE laisse x, accord du geste y %]` sur la ligne de génération.
Greffe (arbre arrêté, ARRET) : `mentor appliquer --apprentie ... --mere N2 --code-avant ...` ; retour arrière :
`mentor retirer` (la branche seule) ou `mentor defaire` (vie d'avant, `sauvegardes/avant_mentor_*`). Tests
`tests/test_mentor.py`. Essai sur copie : `vie/essais/mentor_20261019/`.

**19/10 nuit (accord explicite du chef de projet) : MAGNETAR = UNE BRANCHE AU CERVEAU SYMÉTRIQUE**
(`ecole/precision/symetrie.py`, branche N2 « symetrique » née de la cime D2 après la génération 260, L2 archivée ;
sauvegarde complète `vie/arbre_or/sauvegardes/avant_symetrique_20261019_202052/` (vie + code d'avant)). Achat et vente
jugés par les MÊMES neurones : vue miroir de la situation (zones demande <-> offre, sommets <-> creux, clôtures et
tendances de signe inversé, position / ordre inversés, journal achat <-> vente, foule et tendance de fond retournées ;
involution exacte) ; acheter = tête « acheter » sur x, vendre = la même tête sur miroir(x), rien / fermer / délai /
valeur = moyenne des deux lectures ; paramètres d'une vente = mêmes têtes lues sur miroir(x). Aucun poids de plus
(mêmes poids que la cime ; mot `symetrique` dans le tempérament ; `cerveau.regler_symetrie`). Ligne de génération : la
branche est marquée `[SYMÉTRIQUE]` (part d'achats et R achats / ventes par côté : `tournant.texte_cotes`, comme les
autres). Preuves : `vie/arbre_or/symetrique/preuves.json` ; tests `tests/test_symetrie.py` ; empreintes HYPERNOVA,
MAGNETAR et des vraies branches identiques. Essai : `vie/essais/symetrique_20261019/`. Retour arrière (arbre arrêté,
ARRET en place, `$env:COLLAPSAR_PRECISION_REGLAGES=...reglages_or.yaml`) : `python -m collapsar.ecole.precision.symetrie
retirer` (la branche seule archivée, l'arbre continue) ou `... symetrie defaire` (vie d'avant la greffe,
`sauvegardes/avant_symetrique_*`) ; le code reste inerte sans le mot `symetrique` dans un tempérament.

**19/10 soir (accord du chef de projet : « alloue-lui plus de ressources » + « elle doit vivre les deux mondes ») :
MAGNETAR SEULE SUR LA MACHINE = JUGE PLUS SÛR + LES DEUX SENS.** Réglages `reglages_or.yaml` : `carte_max_go` 1,25 -> 3,0 ;
`ecole.comptes` 512 -> 640 ; `ecole.apprentissage_apparie` (`jeu.Lecon` : moitié des comptes sur l'or réel, moitié sur
le même or retourné aux mêmes départs) ; `examen_tournant` : `blocs_par_generation` 16 -> 28 (tous), `parties_par_bloc: 8`
(chaque bloc joué 8 fois sur d'autres comptes : le hasard de son jeu pesait plus que la différence entre blocs),
`graine_par_generation`, `note_cotes: moins_bon` (note de sélection = moyenne du côté le moins bon, or réel / retourné ;
écarts de coupe bloc par bloc sur ce côté, `jeu.comparer` ; garde-fou anti-casino sur le pire côté ; passage
`note_cotes.json` : notes d'avant mises de côté). Résultats séparés réel / retourné : ligne de génération
(`tournant.texte_cotes`) et rapport (`rapport._cotes`). Bruit de l'écart entre deux branches : ± 0,5-0,7 -> ± 0,2.
Sauvegarde `vie/arbre_or/sauvegardes/avant_ressources_20261019_1647/` (vie + `code_avant`). Retour arrière : ARRET, attendre
la fin ; recopier `code_avant/ecole_precision/reglages_or.yaml` (le nouveau code est inerte sans ces réglages) et, pour
les niveaux d'avant, `vie/arbre.json`, `cime.pt`, `derniers_examens.json`, `branches/` de la sauvegarde ; effacer
`vie/arbre_or/note_cotes.json` ; retirer ARRET, relancer. Tests `tests/test_trois_changements.py` (parties, graine, apparié,
note du côté le moins bon, passage). Essai : `vie/essais/ressources_19oct/`.

**19/10 après-midi (accord du chef de projet) : MAGNETAR = TROIS CHANGEMENTS** (`ecole/precision/trois_changements.py`,
rapport `vie/arbre_or/trois_changements/rapport.md`, preuves `preuves.json`, bruit `mesure_bruit.json`) :
1. YEUX DE LA TENDANCE DE FOND sur UNE branche « tendance » née de la cime (`ecole/precision/tendance.py` : 20/60/120 j
   signe / force / pente, accord, position dans la fourchette 60 j, sans futur, inversée sur l'or retourné ; réglage
   `yeux.tendance` ; 12 entrées en dernier, poids à zéro, décisions identiques prouvées) ;
2. STOP SUIVEUR APRÈS +1R sur UNE branche « suiveur_1r » née de la cime (`suiveur.py` options 1 h / 4 h / 1 agitation,
   `simulateur.py` sv_1r / sv_ag ; réglages `mains.suiveur_1r*` ; tête `suiv1r` à zéro + penchant calibré ~70 %) ;
3. EXAMEN TOURNANT pour tout l'arbre (`ecole/precision/tournant.py`, section `examen_tournant` de `reglages_or.yaml` :
   28 blocs de 61 jours 2010-2023 jamais appris (marges 7 j), 16 tirés par génération, or réel + retourné, jumeau ;
   apprentissage jusqu'à fin 2023 hors blocs ; contrôle 2024-2025 inchangé). Mesure de la tenue (`selection.mesurer_tenue`).
Branches : cime A2 intacte, « tendance », « suiveur_1r », D2 (meilleure des autres) ; X et E2 archivées. Sauvegarde
complète `vie/arbre_or/sauvegardes/avant_tendance_suiveur_tournant_20261019_1350/` (vie + code d'avant). Retour arrière :
`trois_changements defaire`. Tests `tests/test_trois_changements.py` ; empreintes `empreinte_magnetar comparer | swing |
nouveautes` identiques ; HYPERNOVA inchangé.

**19/10 nuit (accord du chef de projet) : MAGNETAR = COMPTE SWING + JOURNAL + PEUR CORRIGÉE.** Réglages
`reglages_or.yaml` : `mains.compte: swing` (plus de fermeture forcée avant les pauses ni le week-end, ordres gardés, nuit
payée au passage de minuit même si la position se ferme à l'ouverture suivante, écart du lundi subi au prix d'ouverture,
aucune nouvelle position dans les 2 h avant une pause > 2 h ; `univers.regles_compte`, `simulateur.pas_comptes`),
`selection.mesurer_sorties` (sorties à la main / stop / objectif / forcées, part gardée le week-end, dans l'examen).
Branches : cime J intacte, G (meilleure des autres), N « journal » (née de J, greffe `journal_trading greffer --nouvelle`),
O « sans_peur » (née de J, `ecole/precision/peur.py` : peur seulement près des murs et sous le plus haut solde réalisé
du jour ; autre option `fermeture_r` en réglage) ; E et M archivées (`archives/`). Sauvegarde complète :
`vie/arbre_or/sauvegardes/avant_swing_journal_peur_20261019_0019/` (vie + code d'avant). Tests `tests/test_swing_peur.py`,
empreintes `tests/empreinte_magnetar.py` (« comparer » = règles Swing mises à part, identique au 18/10 ; « swing »).
HYPERNOVA inchangé (empreinte identique).

**18/10 nuit : JOURNAL DE TRADING de MAGNETAR préparé, NON greffé** (`ecole/precision/journal_trading.py`, carnet façon MT5
par compte : onglet Trade + Historique, délai `fermeture` par défaut ou `lendemain`, 159 entrées à zéro sur UNE branche ;
logs `vie/arbre_or/journal_trades/`, dessin d'un trade `journal_dessin`, résumé `journal_analyse` ; tests
`tests/test_journal_trading.py`, empreinte `tests/empreinte_magnetar.py` ; greffe prête : `ecole/precision/greffer_journal_magnetar.ps1`
(retour : `-Defaire`) ; essai sur copie `vie/essais/journal_or_18oct/`).

`vie/ARRET` est en place EXPRÈS : il empêche le gardien de relancer l'ancien arbre (`arbre.coeur`). Ne pas l'enlever.

## 2. Le code, dossier par dossier

| Dossier | Rôle | Notes |
|---|---|---|
| `donnees/` | lire les marchés (Dukascopy, minute, HistData), calendrier MetaTrader, taux d'intérêt, foule Binance / devises | heures en nanosecondes depuis l'audit du 16/10 |
| `mains/` | **simulateur fidèle FTMO** : un compte 100 000 $, fiches des marchés, frais (`frais_ftmo.py`), nuits (`nuit.py`), horloge | réparé le 16/10 (chantier C : frais sans x 1,25, nuits FTMO, levier Swing) |
| `juge/` | examens et note « avantage sur le hasard » (`note.py`, `examen_humain.py`) | |
| `yeux/` | ce que COLLAPSAR voit : graphique, faits (séances, annonces), vue d'ensemble | |
| `cerveau/` | les cerveaux (`humain.py` = trader humain numérique, `trader.py`, `agent.py`) | |
| `ecole/` | les écoles : mille mondes (`lancer_mondes`, `controleur_mondes`), regard (`regard.py`), crypto 1 et 2 (`crypto_monde`, `crypto2_monde`) | **nouvelle école « de la précision » en construction** (autre agent) |
| `mondes/` | générateur des mille mondes (marchés inventés à lois cachées) | |
| `strategies/` | `cassure.py` : moteur de la cassure C2 / v3 (utilisé par les écoles crypto) | cache dans `vie/cassure_v3/` |
| `regarder/` | mesures et laboratoires | |
| `regarder/smc/` | indicateur du chef traduit (`zones supply and demand.py` fidèle au Pine, `zones supply and demand.py` ancienne), zones gigognes, laboratoire SMC | |
| `regarder/pistes/` | pistes ENCORE UTILES (démos, références, ou importées par les tests) | voir §3 |
| `direct/` | les démos en direct (Tradeco) et suivis à blanc ; `tradeco.py` = les mains sur MetaTrader | |
| `maitres/` | traders réels (gTrade, Ostium, Hyperliquid) : collecte, imitation, persistance du talent | |
| `surveillance/` | gardien, téléphone, carnet de bord, images, relevés d'écarts | |
| `audit/` | les 8 programmes de l'audit du juge (16/10) | rapport `vie/audit/rapport.md` |
| `arbre/` | l'ancien arbre (arbres 1-3), **arrêté** ; gardé car le gardien et des tests le citent | |
| `tests/` | 165 tests (tous verts le 16/10 soir, ~5 min) | |
| `docs/` | `REPRISE.md` (fiche de reprise), `CONCEPTION.md`, `BRIEF_PISTES.md`, définitions SMC figées, `zones supply and demand.pine` (code original du chef), cette carte | |
| `reports/` | `Recherche daytrading rentable.md` | autres rapports à `Test_IA/reports/`, notes de recherche à `Test_IA/research_notes/` |
| `archives/` | pistes et restes rangés (voir §5) | |

## 3. Les pistes restées en place (code `regarder/pistes/<nom>.py`, résultats `vie/pistes/<nom>/rapport.md`)

| Piste | Pourquoi elle reste |
|---|---|
| `verdict_zones_corrige` | **verdict de référence** des zones du chef avec le juge corrigé (16/10 soir) |
| `zones_retouchees`, `zones_retouchees_v7` | moteur des zones utilisé par le verdict (traduction fidèle + heures corrigées) |
| `chef_crypto`, `chef_compte_ftmo` | stratégie du chef sur cryptos ; utilisée par la démo `direct.chef_zones` et le verdict |
| `bitcoin_cassure`, `bitcoin_journee`, `cassure_v3` | règles de la démo cassure BTC ; `cassure_v3` = référence des écoles crypto |
| `crypto_flux`, `crypto_flux_compte` | C1 « contre la foule » ; utilisés par `direct.foule_blanc` et les écoles crypto |
| `compte_combine`, `trois_briques` | comptes FTMO combinés (cassure + zones + C1) : meilleure estimation mesurée |
| `hyrotrader` | C1 à coûts de Bourse (décision à prendre avec le chef) |
| `peur_options` | petite brique indépendante positive (fin d'inversion du VIX) |
| `foule_devises` | en attente d'un jeton OANDA démo (seul vrai test de C1 sur les devises) |
| `smc_combinaisons` | piste réfutée, mais importée par `tests/test_frais_audit.py` |
| `foule_hypernova` | mesure avant greffe des YEUX DE LA FOULE d'HYPERNOVA (17/10) : rapport `vie/hypernova/foule/mesure.md` ; yeux `ecole/precision/foule.py` (éteints par défaut ; greffe : `python -m collapsar.ecole.precision.foule greffer`, arbre arrêté) |
| `direction_hypernova` | DIRECTION + PRÉCISION (17/10) : sources de direction sans futur `ecole/precision/direction.py` (tendance 20/60/120 j, C2, C1 ; testé `tests/test_direction.py`) appliquées aux 6,4 M candidats du juge + jumeau de la piste du juge ; rapport `vie/hypernova/direction/rapport.md` : aucune case à 2R positive, pas de greffe |
| `mouvements` | MOUVEMENTS DU JOUR (18/10) : gâteau du jour, continuation, ses zones rebond / cassure avec STOP SUIVEUR sans plafond (`trade_suiveur` = moteur de l'arbre + suiveur, testé `tests/test_mouvements.py`) ; rapport `vie/hypernova/mouvements/rapport.md` : non (contrôle 2024-25 déjà fait) |
| `monde` | YEUX DU MONDE (18/10) : risque géopolitique (GPR), incertitude (EPU), peur Cboe (VIX, VVIX, OVX, GVZ) lus par `donnees/monde.py` (données `Test_IA/data/monde/`, valeur du jour J utilisée à J+1 08h00 serveur) ; rapport `vie/hypernova/monde/rapport.md` : le GPR ne donne pas le sens, combinaison tendance + monde + ses zones ~0 R ; seule régularité : pétrole en baisse le lendemain d'un saut du VIX (confirmée, pas prouvée). Yeux `ecole/precision/monde.py` (36 valeurs, éteints par défaut ; greffe : `python -m collapsar.ecole.precision.monde greffer`, arbre arrêté ; testé `tests/test_monde.py`) |
| `avis_execution` | L'AVIS SUR LES MARCHÉS (18/10) : cerveau d'avis `ecole/precision/avis.py` (sens + conviction calibrée + 3 raisons, 66 marchés, 1 / 5 / 20 j, commande `avis matin --v2 [--date]`, modèles de l'essai 3 = années glissantes `vie/hypernova/avis/modeles_v2.pkl`) ; exécution sur ses zones `regarder/pistes/avis_execution.py` ; rapport `vie/hypernova/avis/rapport.md` : aucun sens propre au-delà de « les marchés montent », calibré honnêtement il dit « rien » ; testé `tests/test_avis.py` |
| `memoire_situations` | MÉMOIRE DES SITUATIONS sur l'or (18/10) : 121 000 moments (clôtures d'heure 2004-2025, 20 nombres « ce que voit un trader ») + ce qui a suivi (72 h), barrière anti-triche (suite connue 5 j avant), test piège ; rapport `vie/memoire/rapport.md` : petit signal sur les gros mouvements non prouvé, pas de sens au-delà de la tendance 60 j, trading ~0 R ; testé `tests/test_memoire_situations.py` ; rien greffé à MAGNETAR |
| `juge_trade` | école « JUGER UN TRADE » d'HYPERNOVA (17/10) : `ecole/precision/juge_trade.py`, vie `vie/hypernova/juge_trade/` (exemples, juges, `rapport.md`) ; aucun avantage après frais sur 2024-25 ; greffe prête, éteinte (`juge_trade greffer --dossier <arbre arrêté>`) |

## 4. Les résultats de référence (à lire en premier)

| Sujet | Fichier |
|---|---|
| Audit du juge (défauts trouvés, corrections) | `vie/audit/rapport.md` |
| Verdict des zones du chef, juge corrigé | `vie/pistes/verdict_zones_corrige/rapport.md` |
| Nouvelle note de COLLAPSAR, juge réparé | `vie/note_collapsar_corrigee/rapport.md` |
| École crypto n° 2 (meilleure version de COLLAPSAR) | `vie/ecole_crypto2/rapport.md` |
| Cassure du bitcoin | `vie/pistes/bitcoin_cassure/rapport.md`, `vie/pistes/bitcoin_journee/rapport.md` |
| Contre la foule (C1) | `vie/pistes/crypto_flux/rapport.md` |
| Laboratoire SMC (avant la correction des heures : chiffres faux) | `Test_IA/reports/Laboratoire SMC.md` |

## 5. Les archives (rien n'est effacé ; chaque déplacement est noté dans un MANIFESTE.txt)

| Archive | Contenu |
|---|---|
| `archives/2026-10-16_pistes/` | 16 pistes réfutées (code + résultats) et 11 expériences des 13-15/10 (annonces, par cœur, semaine, vue d'ensemble…) |
| `archives/2026-10-16_vie/` | arbres 1 et 3, essais de l'arbre 3, anciens avis, essai des mille mondes, vieux résultats des écoles de l'arbre |
| `Test_IA/archives/` | ancien projet (v1, Run A), sauvegardes zip de collapsar (avant ORB, avant SMC), `2026-10-16_racine/` |

Pour remettre un élément : le redéplacer à l'ancien chemin écrit dans le manifeste.

## 6. Ce qui est dans `vie/` (l'état vivant)
`direct/` (démos), `logs/` (journaux de tous les programmes), `ecole*` (élèves et contrôles de chaque école),
`pistes/` (résultats des pistes en place), `audit/`, `note_collapsar_corrigee/`, `cache/` (cache des données, se refait
seul), `smc/` (laboratoire SMC), `avis/` (ancienne école par avis), `arbre2_14oct/` (yeux greffés, cités par
`reglages.yaml`), `images/` (envoyées sur le téléphone), `ecarts/`, `releves/`, `bande_bruit/`, `orb/`, `cassure_v3/`.

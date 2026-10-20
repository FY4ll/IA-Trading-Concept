# Mentors fiables pour COLLAPSAR — recherche du 19/10/2026

But : trouver des traders **fiables** (style proche du chef de projet : repérer des zones, stop serré derrière une
structure, laisser courir les gros mouvements, positions de quelques heures à quelques jours), surtout sur l'or,
dont on peut obtenir **chaque trade, légalement**, et des **jeux de données de vrais trades** fiables.
Recherche en lecture seule : aucune inscription, aucun téléchargement interdit. Complète
`research_notes/Sources de maitres/sources.md` (15/10) et `docs/MAITRES_A_TELECHARGER.md`.

Rappel unique : aucun trader ci-dessous n'est garanti gagnant à l'avenir ; un bon passé peut être de la chance.

---

## 0. En bref

| Constat | Conséquence |
|---|---|
| Aucune source ne donne à la fois : argent réel vérifié + 3 ans + style « zones / swing » sur l'or + trades complets téléchargeables légalement. | Il faut combiner deux ou trois sources. |
| Les données les plus **impossibles à truquer** sont celles des échanges sur chaîne publique (Ostium, gTrade, Synthetix, Hyperliquid). Le projet a déjà Ostium et gTrade. | Source n°1 pour le volume ; mais peu d'historique (≤ 2-3 ans) et beaucoup de joueurs à gros levier. |
| Mesuré aujourd'hui sur Ostium : 8 003 traders d'or, **79 % des trades d'or durent moins de 4 h** (moitié < 22 min). Seuls 50 traders ont ≥ 30 trades, durée moitié ≥ 4 h, sur ≥ 6 mois ; **0** avec ≥ 100 trades sur 12 mois. | Les vrais « swing » sur l'or sont rares ; et presque tous les gagnants ont surtout ACHETÉ pendant la hausse 2024-26. |
| La source la plus **honnête et régulée** est Darwinex (courtier sous autorité britannique, conditions d'usage interne permises). Mais le détail public ne donne ni sens ni prix de chaque trade. | Bon pour CHOISIR des mentors (durée, régularité) ; le détail exact se demande au trader. |
| Myfxbook, FX Blue, MQL5, eToro, cTrader Copy : accès automatique ou entraînement d'IA **interdits** par leurs règlements (Myfxbook nous renvoie même un refus d'accès). | Usage possible seulement : regarder à la main, puis **demander l'accord écrit** du trader. |
| Voie la plus propre pour avoir les trades exacts d'un bon trader humain : **son accord** (export de son historique MT5, ou mot de passe « investisseur » en lecture seule). | Écrire à 5-10 candidats choisis (section 6). |

---

## 1. Les critères de fiabilité (appliqués partout dans ce document)

| # | Critère | Pourquoi | Comment le vérifier |
|---|---|---|---|
| 1 | **Argent réel vérifié par un tiers** (courtier ou chaîne publique) | Une démo ou un compte « simulé » ne subit ni la peur ni les vrais glissements de prix. | Badge du courtier, compte régulé, ou trades inscrits sur la chaîne. Attention : « Darwinex Zero » = capital virtuel en conditions réelles, pas de l'argent réel. |
| 2 | **Au moins 2-3 ans continus** | En moins d'un an, la chance domine (mesuré le 15/10 : les « maîtres » choisis sur peu de trades perdent ensuite). | Date de début, pas de trou de plusieurs mois. |
| 3 | **Pas de martingale ni de grille** | Ces méthodes gagnent souvent… jusqu'au jour où elles sautent. | Signes : taux de réussite > 80-90 %, perte moyenne bien plus grosse que le gain moyen, ajouts de positions en perte, baisse max minuscule puis effondrement. |
| 4 | **Baisse maximale modérée** (idéalement < 15-20 %) | FTMO coupe à -10 % ; au-delà de 25 %, c'est un joueur. | Courbe du compte (pas seulement la courbe « solde »). |
| 5 | **Durée moyenne des trades ≥ plusieurs heures** | Le chef rejette les « coupeurs de 2 $ ». | Durée moyenne ET médiane (une moyenne peut cacher 90 % de trades de 5 minutes). |
| 6 | **Gain moyen nettement supérieur aux frais** | Sinon l'avantage disparaît chez FTMO (leçon du 16/10 sur le bitcoin). | Gain moyen par trade / (écart + commission). Viser ≥ 5 fois les frais. |
| 7 | **Historique trade par trade accessible légalement** | Sans ça, rien à apprendre ; et le projet refuse tout ce que le règlement interdit. | Export autorisé, API officielle, données publiques de la chaîne, ou accord écrit du trader. |
| 8 | (ajouté) **Gagne dans les deux sens** | Sur 2024-26, acheter l'or suffisait pour « gagner » : ce n'est pas un talent. | Part des achats ; résultat des ventes à part. |

---

## 2. Jeux de données fiables de vrais trades (classés par fiabilité)

### 2.1 Échanges sur chaîne publique (le plus fiable : chaque trade est inscrit, vérifiable, non effaçable)

Avantage commun : **impossible à truquer**, morts compris (aucun biais des survivants), accès libre sans compte.
Piège commun : non régulé, prix venant d'un « oracle » (proche du marché, pas identique à FTMO), traders souvent issus
de la crypto, **levier énorme**, petits comptes ; une personne peut avoir plusieurs adresses.

| Plateforme | Marchés hors crypto | Profondeur | Accès légal / coût | Déjà au projet ? | Piège principal |
|---|---|---|---|---|---|
| **Ostium** (chaîne Arbitrum) | Or (le 1er marché : 244 000 ordres), argent, pétrole, euro, yen, S&P 500, Nasdaq, DAX, Nikkei… | 08/2024 → aujourd'hui (~2 ans) | Index public officiel (adresse dans le paquet officiel `ostium-python-sdk`), gratuit, sans clé | **OUI** : 748 724 ordres, ~14 900 traders, `data/maitres/ostium/ordres.csv` | Historique court ; gagnants = acheteurs d'or pendant la hausse |
| **gTrade** (Gains Network ; Polygon, Arbitrum, Base) | 9 paires de devises, or, argent, pétrole, cuivre, indices | Plateforme depuis 2021-22 ; nos fichiers : 05/2024 → 10/2026 (120 adresses, 3 060 lignes sur l'or) | API publique officielle sans clé (`backend-global.gains.trade`) ; les anciens trades (2022-23) se relisent sur la chaîne | **OUI** (`data/maitres/gtrade/`) | Levier jusqu'à 250x sur l'or ; peu d'adresses collectées |
| **Synthetix « perps »** (chaîne Optimism, via Kwenta, Polynomial…) | **Or (XAU), argent (XAG)**, euro, livre, dollar australien | **Mesuré le 19/10** : or, argent, euro ouverts le 12/04/2022 (V1), livre et dollar australien le 09/02/2023 (V2) ; **marchés retirés en juillet 2024** (SCCP-2127 ; dernier trade d'or 09/07/2024) ; le 25/08/2025 = fin de toute la plateforme | Événements de la chaîne lus directement (point d'accès public officiel d'Optimism, sans clé) ; index Kwenta éteints | **OUI** (`data/maitres/synthetix/`, `maitres/synthetix.py`, rapport `vie/maitres_synthetix/rapport.md`) | **Très peu de trafic** : 2 426 trades d'or, 1 101 traders, aucun ≥ 100 trades → aucun mentor (🔴) |
| **Hyperliquid** (marchés « HIP-3 » de trade.xyz) | Or, argent, platine, pétrole, S&P 500 (licence officielle), Nasdaq-100, actions US | Seulement depuis ~10/2025 (~1 an) | API publique officielle ; 10 000 dernières exécutions par trader ; archive complète payée au transfert | OUI (2 Go, surtout crypto) | Trop court pour juger un trader sur 2-3 ans |
| **Avantis / Veranta** (chaîne Base) | Devises, or, matières premières | ~2024 → | API publique (historique par adresse) | NON (découverte des traders difficile) | Peu de traders trouvables |
| **Lighter** (Ethereum) | Or, argent, devises, actions (depuis 2025-26) | < 1 an | API officielle | NON | Trop récent |
| **Injective Helix** | Or, argent, pétrole, euro, livre, 111 actions | RWA depuis début 2025 | Chaîne publique | NON | Récent ; surtout actions |

**Comment repérer les traders durables sur ces chaînes** (règles à appliquer dans `maitres/juge.py`) :
1. ≥ 100 trades fermés ET ≥ 12 mois d'activité (le 15/10 : seuls « ≥ 200 trades et force > 3 » ont tenu ensuite).
2. Durée médiane ≥ 4 h (pas seulement la moyenne).
3. Levier médian ≤ 20x (au-delà, c'est un joueur ; on ramène tout à une taille FTMO de toute façon).
4. Gain dans les **deux sens** : résultat des ventes séparé de celui des achats.
5. Pas de liquidation ; pertes coupées par un stop (la chaîne dit si la sortie vient d'un stop, d'un objectif ou
   d'une fermeture à la main).
6. Juger sur une période **après** le choix (sinon on choisit de la chance).

**Mesure faite aujourd'hui sur l'or d'Ostium** (script de travail, chiffres arrondis ; « mis » = marge déposée, « net »
= argent rendu moins marge, frais compris ; fermetures partielles approchées) :

| Adresse (Arbitrum) | Trades or | Durée médiane | Levier | Mois actifs | Part d'achats | Mis → net | Avis |
|---|---|---|---|---|---|---|---|
| 0x95465e180697879cdd127b210c4830a16e3f96e4 | 66 | 73 h | 20x | 16 | 65 % | 184 k$ → +254 k$ | Le plus proche du profil swing ; trop peu de trades |
| 0xa3a025110603e3418a3ffc8e76fdf75e654e71b7 | 96 | 50 h | 6x | 7,5 | **27 %** (vend surtout) | 2,7 M$ → +202 k$ (+7 %) | Gagne en VENDANT l'or en hausse : intéressant, à suivre |
| 0xfc6c87872c300c9af1594458491961f9f0c0116c | 63 | 216 h | 10x | 11 | 79 % | 753 k$ → +198 k$ | Tient des jours ; surtout acheteur |
| 0x0dc03ef72117f46414c24076438a306b05544841 | 61 | 129 h | 24x | 17 | 92 % | 14 k$ → +2 k$ | Durable mais acheteur quasi pur |
| 0xde978326c24e62a1fcb0fe2d5aeee6c8ddfd3a22 | 267 | 4,3 h | 100x | 13 | 18 % | 10 k$ → +6,8 k$ | Beaucoup de trades, vend souvent ; levier de joueur |

Bilan : sur 8 003 traders d'or, **50** passent « ≥ 30 trades, durée médiane ≥ 4 h, ≥ 6 mois » (33 gagnants),
**10** passent « ≥ 50 trades sur ≥ 12 mois », **aucun** « ≥ 100 trades, ≥ 6 h, ≥ 12 mois ». La plupart des
gagnants ont acheté 80 à 100 % du temps : ils ont surtout profité de la hausse de l'or.

### 2.2 Jeux de données officiels ou académiques

| Source | Ce que c'est | Fiabilité | Profondeur | Accès / coût | Piège principal |
|---|---|---|---|---|---|
| **CFTC — rapport hebdomadaire des positions** (« Commitments of Traders »), or du COMEX (code 088691) | Positions totales par grande famille : producteurs, banques, **fonds spéculatifs** (« managed money »), petits porteurs | Excellente (régulateur américain) | Depuis 1986 (détail par famille depuis 2006), chaque semaine | Gratuit, public : https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm (archives : …/HistoricalCompressed/index.htm) | **Pas de trades individuels** : la loi interdit à la CFTC de publier les positions d'une personne. Information de contexte, pas un mentor. Déjà essayé en 2025-26 (« positions COT : aucun avantage »). |
| **AMF (France) — étude sur le Forex des particuliers** (2014, ~15 000 clients, 2009-2012) | 89 % des particuliers ont perdu | Excellente | 4 ans | Rapport public gratuit (site amf-france.org) | Chiffres agrégés, pas de trades |
| **ESMA / courtiers européens** : « X % des comptes perdent » | Obligation légale d'afficher la part de clients perdants (souvent 70-85 %) | Bonne | Mise à jour trimestrielle | Public | Agrégé ; rappel que la foule perd |
| **Études universitaires sur données de courtiers** (Barber-Odean : 78 000 comptes ; Taïwan ; courtier Forex « OANDA » ; réseau social myForexBook étudié par Heimer) | Trades réels de dizaines de milliers de particuliers | Excellente | Plusieurs années | **Privé** : accès par accord de recherche universitaire | Inaccessible pour nous ; surtout actions |
| **Championnat du monde de trading « Robbins »** (argent réel, depuis 1983 ; L. Williams +11 376 % en 1987, A. Unger 4 fois champion) | Concours en argent réel, contrôlé | Bonne pour le classement | Annuel | Classements publics (https://www.ireallytrade.com/halloffame) | **Aucun trade publié** ; rendements de concours = levier extrême |
| **Concours de courtiers / Myfxbook / Dukascopy** | Classements et parfois trades | Faible | Courte | Variable | Presque toujours en **démo** : exclus |

### 2.3 Plateformes à relevés audités (détail en section 3)

| Plateforme | Fiabilité | Trade par trade d'autrui ? | Accès automatique permis ? | Coût | Piège principal |
|---|---|---|---|---|---|
| **Darwinex** | **La meilleure** : courtier régulé (FCA Royaume-Uni n° 586466, CNMV Espagne) | Partiel : par trade = heure d'ouverture, durée, rendement, risque, **marché** (jeu « LOSS_AVERSION »), mais **ni sens ni prix** | **Oui pour usage interne** (conditions de l'API, art. 3.2) avec un compte | Compte gratuit ; données brutes par serveur de fichiers (compte réel peut-être exigé, à vérifier) | Depuis 2024, beaucoup de DARWIN viennent de « Darwinex Zero » = **capital virtuel** ; rendements affichés **recalculés** à un risque fixe (6,5 %/mois), pas ceux du compte brut |
| **Collective2** | Moyenne : résultats officiellement « hypothétiques » ; marque « trade son propre système » = connexion directe au courtier | **Oui** (pages publiques + API officielle : ouverture, fermeture, sens, quantité, prix moyens, pire prix pendant le trade) | API officielle seulement, à faible cadence ; aspiration interdite ; usage IA : demander par écrit | Clé API gratuite avec un compte | Sur l'or : toutes les stratégies trouvées sont mortes ou dangereuses (section 3.2) |
| **Myfxbook** | Moyenne : « historique vérifié » = conforme aux données du courtier ; mais leurs propres conditions disent « information non vérifiée » | Visible à la main sur les comptes publics | **Non** (reproduction interdite ; leur site refuse même nos lectures automatiques) ; leur API ne lit que SES propres comptes | Gratuit | Vitrine de vendeurs de robots ; démo et réel mélangés |

---

## 3. Source par source, avec profils candidats

### 3.1 Darwinex — la plus fiable, à utiliser pour CHOISIR les mentors

- **Public sans compte** : rendement, rendement annuel, date d'ouverture, **durée moyenne des trades**, nombre de
  trades, part de gagnants, famille de marchés, pseudonyme du trader. Les pages `https://www.darwinex.com/invest/<CODE>`
  se lisent ; la baisse maximale et la répartition par marché (part d'or) ne s'affichent qu'avec un compte.
- **Avec un compte gratuit** : filtres de l'explorateur (marché, durée, ancienneté), API « DARWIN Info » (cotations
  et notes de tous les DARWIN), et sur demande le serveur de fichiers « Raw DARWIN data » : un dossier par DARWIN
  ayant existé (morts compris), 100 derniers trades par jour avec heure, durée, gain, risque, levier, et marché
  pour certains jeux. Avec le marché + l'heure + la durée + le signe du gain, on peut **retrouver le sens** d'un trade
  en le comparant à nos prix (à tester).
- **Règles** : conditions de l'API, art. 3.2 : usage « for your internal purposes » permis, sans revente ni partage ;
  art. 3.3 : pas de données sur des personnes identifiables. Entraîner notre IA privée = usage interne.
- **Coût** : gratuit pour regarder ; un compte réel serait exigé pour le serveur de fichiers (à vérifier).

Profils lus aujourd'hui sur les pages publiques (marchés : « devises, indices, matières premières », **part d'or
inconnue sans compte**) :

| DARWIN | Trader | Lien | Ancienneté | Rendement | Par an | Durée moyenne | Trades | Gagnants | Avis |
|---|---|---|---|---|---|---|---|---|---|
| LSP | @winneryu | https://www.darwinex.com/invest/LSP | ouvert depuis 10/2023, 3 ans | +97 % | +25 % | 24 h 36 | 845 | 52 % | **Meilleur profil swing trouvé** ; 131 investisseurs, 2,3 M$ ; 9 allocations Darwinex d'affilée. Vérifier part d'or et compte réel/virtuel |
| TGVF | @JorgeTrader333 | https://www.darwinex.com/invest/TGVF | 03/2024, 2,5 ans | +55 % | +19 % | 5 h 50 | 2 507 | 43 % | Plus grosse allocation Darwinex (850 k€) ; 43 % de gagnants = laisse courir les gains |
| VRN | @Sebasviamonte | https://www.darwinex.com/invest/VRN | 12/2024, 2,5 ans | +34 % | +12 % | 39 h 27 | 514 | 51 % | Style plusieurs jours ; à vérifier |
| ENCD | @alexruizfx | https://www.darwinex.com/invest/ENCD | 07/2025, 1,5 an | +28 % | +18 % | 35 h 19 | 2 264 | 46 % | Trop court (< 2 ans) |
| PQQD | @Rehan | https://www.darwinex.com/invest/PQQD | 04/2025, 1,5 an | +18 % | +12 % | 13 h 44 | 6 632 | 56 % | Trop court ; beaucoup de trades |
| LVS | @VPSEnry | https://www.darwinex.com/invest/LVS.4.20 | depuis 04/2016, ~10-13 ans | +67 % | +4 % | 21 h 31 | 47 154 | 63 % | Très long (compte réel de l'ancien Darwinex) mais 47 000 trades : probablement un robot, possible grille → vérifier |
| JKJF | @aljaroma | https://www.darwinex.com/invest/JKJF | 12/2025, 1 an | +12 % | +12 % | 27 h 20 | 1 619 | **79 %** | ⚠️ baisse max -0,96 % + 79 % de gagnants = signe typique de grille ; à exclure sauf preuve contraire |

À faire avec un compte : filtrer « or ≥ 50 % des trades, durée moyenne ≥ 6 h, ancienneté ≥ 3 ans, compte réel
(pas Darwinex Zero), baisse max ≤ 20 % » ; écrire aux 5-10 premiers (messagerie Darwinex).

### 3.2 Collective2 — accès légal clair, mais rien de bon sur l'or

- Public : la page de chaque stratégie montre la liste des trades ; API officielle v4
  (`GetStrategyHistoricalClosedTrades`, `SearchStrategies` avec filtre vivante/morte et « trade son propre système »).
- Fiabilité : résultats déclarés « hypothétiques » ; seule la marque « trade son propre système » (connexion directe
  au courtier) prouve de l'argent réel.
- Règles : conditions du 27/03/2026 : pas d'aspiration du contenu payant, pas d'accès automatique qui surcharge ;
  passer par l'API, lentement, et demander par écrit l'usage « entraîner une IA privée ».
- Stratégies or/métaux examinées aujourd'hui (toutes **rejetées**) :

| Stratégie | Lien | Âge | Durée moy. | Chiffres | Pourquoi rejetée |
|---|---|---|---|---|---|
| Gold and Silver (Obstract) | https://collective2.eu/details-list/150565426 | 21 mois | 5,1 jours | +56 %/an, baisse max **44 %**, 88 % de gagnants, perte moyenne 8 444 $ contre gain moyen 1 718 $ | Piège classique : garde les pertes, encaisse vite les gains |
| Metal Detector (Ronzy) | https://collective2.eu/details/139331088 | morte depuis 01/2023 | 18,7 h | baisse max 100 % | Morte, simulée |
| Goldvantage Pro | https://collective2.eu/details/151319237 | 18 mois | 14,7 h | baisse max 100 %, 38 trades | Robot, simulé |
| BLACKSEA GOLD | https://collective2.eu/details/153222042 | morte | 37 min | -71 % | Simulée, morte |

  Utilité restante : chercher par l'API les contrats à terme or/indices avec « trade son propre système », vivants,
  ≥ 3 ans (non trouvé par recherche web ; à tester avec une clé gratuite).

### 3.3 Myfxbook — à regarder à la main seulement

- Badges : « historique vérifié » (Myfxbook relit l'historique chez le courtier plusieurs fois par jour) et
  « privilèges de trading vérifiés » (le déclarant a le mot de passe maître). Les deux ensemble = le minimum.
- Règles : leurs conditions (https://www.myfxbook.com/terms) : « reproduction is prohibited », information « not
  verified in any way » ; API = ses propres comptes, 50 dernières opérations. Notre lecture automatique est refusée
  par le site (code 403) : **ne pas insister**.
- Ce que donne la recherche sur l'or : presque uniquement des **vendeurs de robots** (« Dark Gold » : +6 914 % mais
  baisse max 51 % ; « AI Gold Scalper » ; « Gold AI Trading System » en démo). Exactement les vitrines que le chef
  rejette. Aucun profil manuel swing sur l'or solide trouvé.
- Usage possible : repérer à la main un compte réel, ≥ 3 ans, les deux badges, puis **écrire au trader**.

### 3.4 eToro — à regarder, pas à utiliser pour entraîner

- Régulé (CySEC, FCA…), argent réel, profils publics (note de risque de 1 à 10, gains mensuels).
- Règles : conditions de l'API du 17/02/2026, art. 1.7 : interdit d'utiliser leur contenu « to train, fine-tune, or
  ground any model » ; 1.8 : pas d'aspiration ni de base de données séparée. **Exclu pour l'entraînement.**
- Exemple de profil matières premières/métaux : Zhou Ji Cheng (@fcqxzjc), sur eToro depuis fin 2017, passé d'un style
  risqué à un style prudent (https://www.etoro.com/people/fcqxzjc). Seulement pour inspiration humaine, ou avec son
  accord direct pour ses relevés.

### 3.5 cTrader Copy, FX Blue, ZuluTrade, MQL5

| Source | Fiabilité | Règle d'accès | Verdict |
|---|---|---|---|
| cTrader Copy (Spotware) | Comptes réels chez des courtiers régulés ; onglet « Historique » public | Conditions, section 17 : aucun programme ni script d'extraction sans accord écrit | Seulement avec accord écrit de Spotware ou du trader |
| FX Blue | Leurs mots : un compte « vérifié » « can still be falsified » | Robots et scripts interdits ; usage commercial interdit | Exclu |
| ZuluTrade | Variable ; pas d'API publique trouvée | Conditions non trouvées | Non approfondi |
| MQL5 Signals | Réel ou démo ; surtout des robots | Art. 3.7 : tout accès automatique interdit | Export manuel par l'utilisateur seulement (`MAITRES_A_TELECHARGER.md`) ; vitrines rejetées par le chef |

### 3.6 Traders de sociétés de financement (FTMO, The5ers…)

Comptes **simulés** ; les sociétés publient des classements et des montants versés, jamais les trades. Quelques
traders publient captures ou certificats de paiement : rien de vérifiable trade par trade. **Exclu**, sauf accord
direct d'un trader qui exporte son historique MT5.

### 3.7 « Grands traders » ayant publié leurs vrais trades

| Trader | Ce qui est publié | Style | Fiabilité | Accès légal | Avis |
|---|---|---|---|---|---|
| **Peter Brandt** (Factor Trading, depuis 1981) | Livre « Diary of a Professional Commodity Trader » (Wiley, 2011) : journal de ses trades de 2009 sur 21 semaines, chaque trade avec graphique et raisonnement ; métaux, devises, matières premières | **Très proche du chef** : figures du graphique, stop serré derrière la structure, on laisse courir, trades de jours à semaines | Bonne mais à nuancer : un forum signale qu'il a dû remplacer « audité » par « attesté » pour ses chiffres anciens | Acheter le livre, recopier à la main pour étude privée (pas de diffusion) | **Meilleur mentor « humain » pour le style** ; petit nombre de trades (~dizaines) |
| Paul Wei (BitMEX, depuis 2020) | Tous ses trades, publiés par lui pour étude | Bitcoin | Bonne | Déjà téléchargé (`data/maitres/coolish/`) | Référence actuelle, mais crypto |
| Tom Hougaard (indices DAX, Dow) | Trades en direct sur Telegram, tableaux de résultats sur son site | Journée (1-2 h), ajoute à ses gagnants | Déclaratif (pas de tiers) | Lecture | Pas swing, pas vérifié par un tiers |
| Larry Williams, Andrea Unger (concours Robbins) | Résultats finaux seulement | Contrats à terme | Bonne pour le résultat | — | Aucun trade publié |

---

## 4. Les pièges (à rappeler à chaque choix)

1. **Comptes sélectionnés** : on ne voit que les survivants ; ceux qui ont sauté ont disparu (sauf sur la chaîne et
   le serveur Darwinex, qui gardent les morts).
2. **Démo ou capital virtuel** présentés comme réels (Myfxbook mélange ; Darwinex Zero est virtuel ; FTMO simulé).
3. **Gros levier** : un +200 % en un an avec 100x de levier = un joueur chanceux.
4. **Martingale / grille** : 80-95 % de gagnants, perte moyenne 4-5 fois le gain moyen (cas « Gold and Silver »).
5. **Biais de tendance** : sur l'or 2024-26, acheter suffisait ; exiger des gains en vente aussi.
6. **Moyenne trompeuse** de la durée : regarder la médiane.
7. **Rendements recalculés** (Darwinex) ≠ rendement réel du compte.
8. **Choisir et juger sur la même période** = choisir de la chance (déjà mesuré le 15/10).

---

## 5. Plan concret proposé (avis, pas encore fait — accord du chef requis)

| Ordre | Action | Coût | Ce que ça donne |
|---|---|---|---|
| 1 | Appliquer les critères de la section 2.1 à **Ostium + gTrade** déjà collectés, marché par marché (or, argent, indices, devises), et suivre les ~50 « swing » d'Ostium **en direct** à partir d'aujourd'hui (jugement sur l'avenir, pas le passé) | Gratuit, déjà en place | Petite liste de mentors honnêtes, jugés sans tricher |
| 2 | Ajouter **Synthetix sur Optimism** (or, argent, devises, ~2022 → 08/2025, jeu complet figé) en relisant les événements publics de la chaîne | Gratuit (quelques heures de lecture lente) | Seule source sur chaîne avec ~2-3 ans d'or, morts compris |
| 3 | Ouvrir un compte Darwinex (gratuit) pour filtrer « or, ≥ 3 ans, durée ≥ 6 h, compte réel » et tester le serveur de fichiers | Gratuit | Liste des traders humains les plus sérieux du marché régulé |
| 4 | **Écrire à 5-10 traders** retenus (Darwinex LSP / TGVF / VRN, comptes Myfxbook à deux badges) : « IA privée, sans diffusion ; pouvez-vous nous confier l'export MT5 ou un accès en lecture seule ? » | Gratuit | Trades exacts (sens, prix, stop) d'humains vérifiés |
| 5 | Recopier à la main le journal 2009 de Peter Brandt (livre acheté) | ~30 € | Exemples de raisonnement « zones / structure / laisser courir », très proches du chef |

---

## Sources principales

- Darwinex : pages publiques `https://www.darwinex.com/invest/<CODE>` ; conditions de l'API
  https://darwinex.com/cs/legal/darwin-api-conditions ; données brutes https://help.darwinex.com/raw-darwin-data-user-guide ;
  API https://github.com/darwinex/darwinexapis ; DarwinIA déc. 2025 https://www.darwinexzero.com/blog/results-of-darwinia-in-december-2025
- Collective2 : https://collective2.eu/leaderboard ; https://api-docs.collective2.com/ ; pages des stratégies citées
- Myfxbook : https://www.myfxbook.com/help/?p=300 (vérification) ; https://www.myfxbook.com/terms ; https://www.myfxbook.com/api
- eToro : https://www.etoro.com/blog/market-insights/passion-and-hard-work-meet-popular-investor-zhou-ji-cheng ;
  conditions API 17/02/2026 (voir `research_notes/Sources de maitres/sources.md`)
- Synthetix : https://sips.synthetix.io/sips/sip-295 ; https://docs.synthetix.io/trading/legacy (fermeture 25/08/2025) ;
  https://blog.synthetix.io/22-new-synthetix-perp-futures-market-are-now-live/
- Échanges sur chaîne : https://defiprime.com/tokenized-metals-onchain-2026 ; https://cryptobriefing.com/injective-nearly-half-markets-tokenized-assets/ ;
  https://apidocs.lighter.xyz/docs/get-started ; https://docs.gains.trade
- CFTC : https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
- Concours Robbins : https://www.ireallytrade.com/halloffame
- Peter Brandt : https://www.peterlbrandt.com/about-us/ ; livre Wiley 2011 (référence Wiley 0470521457) ;
  discussion sur ses chiffres https://elitetrader.com/et/threads/information-about-peter-brandt.320673/
- Tom Hougaard : https://optionstradingiq.com/trader-tom/

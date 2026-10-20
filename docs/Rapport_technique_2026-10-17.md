# Construire un trader artificiel : un mois de recherche sur une IA de trading autonome

*Document de synthèse, état au 17 octobre 2026. Il couvre le travail fait du 16 septembre au 17 octobre 2026.*

---

## Résumé

Ce projet cherche à construire, sur un seul PC personnel, une **intelligence artificielle de trading qui apprend par
elle-même**. Elle doit être capable de passer l'épreuve d'une société de financement de traders (FTMO, compte de
100 000 $) puis d'en tirer un revenu. Le porteur du projet, trader discrétionnaire, a formulé l'ambition ainsi :
**« un humain dans une machine »**. Il ne veut pas d'un robot qui applique des règles, mais d'un trader numérique qui
voit le graphique, décide, place ses stops, gère ses positions, avec la discipline qu'un humain n'a pas.

En un mois, quatre générations de systèmes ont été construites et éprouvées :
1. un agent d'apprentissage par renforcement sur l'or, avec une sélection évolutionnaire ;
2. son extension à 45 marchés ;
3. une architecture « en arbre » inspirée de l'entraînement par population ;
4. une école centrée sur le placement du stop par la structure du marché.

En parallèle, une soixantaine de pistes ont été testées, des méthodes publiées comme des stratégies de traders, avec
un protocole d'évaluation volontairement strict.

Le constat principal est sans ambiguïté. **Sur les horizons courts (de quelques minutes à quelques jours), une fois
les vrais coûts payés, presque rien ne bat le hasard de façon stable.** Les rares avantages mesurés sont réels mais
petits : la tendance de fond, la cassure journalière du bitcoin, le positionnement « contre la foule » sur les cryptos.
Ce sont souvent les frais du courtier qui les font disparaître. Le système actuel a appris le *geste* du trader
(entrer sur une zone, stop derrière une structure, viser loin) sans encore produire de gain par trade. La piste en
cours lui apprend d'abord à *juger* un trade sur des millions d'exemples, avant de lui apprendre à agir.

---

## Avant-propos : comment ce travail a été fait

Par honnêteté, il faut dire clairement qui a fait quoi.

**Le porteur du projet n'a pas écrit le code.** Le code, les expériences, les mesures et la rédaction des rapports
(ce document compris) ont été réalisés par un assistant de programmation à base d'IA, Claude (Anthropic), utilisé
dans l'outil Claude Code, **sous sa direction**.

Son rôle a été celui d'un **chef d'orchestre**, pas celui d'un client qui demande « construis-moi tout et rends-moi
riche » :
- **l'idée de départ et la vision** : un trader humain dans une machine, qui découvre seul le trading devant un
  graphique, sans règles imposées hormis la protection du compte ;
- **les grands choix de conception** : liberté d'action totale, croissance en arbre plutôt qu'en cycles, note alignée
  sur la réussite du challenge, « l'asymétrie par la précision » (section 6) ;
- **les décisions à chaque étape** : quelles pistes explorer, lesquelles arrêter, quand recentrer le travail ;
- **les recadrages** : refuser que le projet devienne un robot à règles ou une simple automatisation de sa propre
  stratégie, exiger la logique du trader avant les chiffres, renforcer les bases avant d'ajouter des sources ;
- **sa propre méthode de trading**, apportée comme matière d'étude et mesurée sans complaisance.

L'assistant a proposé des pistes, écrit et testé le code, mesuré, et rapporté les résultats tels qu'ils étaient,
y compris quand ils contredisaient les attentes du porteur du projet. Il a aussi commis des erreurs : des horodatages
mal lus, une fuite d'information dans un calendrier, une commission oubliée. Elles ont été trouvées par les contrôles
et l'audit décrits en section 2.

**Il faut distinguer l'outil du résultat.** L'assistant a servi d'outil de développement et de recherche. L'IA de
trading elle-même est faite maison : elle tourne en local et ne fait appel à aucun modèle de langage pour décider de
ses trades.

Le porteur du projet a préféré le dire plutôt que de s'attribuer un travail qu'il n'a pas codé lui-même. L'idée, la
direction et les décisions sont les siennes ; l'exécution technique a été faite avec l'aide d'une IA.

---

## 1. Motivation

### 1.1 Le problème humain
Le porteur du projet trade lui-même. Il utilise des zones d'offre et de demande, des imbrications entre unités de
temps et des objectifs lointains. Il juge que sa méthode fonctionne, mais qu'il « se gère mal » : émotions, manque de
discipline, fatigue. L'idée de départ découle directement de ce constat. Une machine n'a ni peur ni avidité et applique
sa gestion à chaque trade. Si un humain qui fait du trading à la journée peut en vivre, une machine bien construite
devrait faire au moins aussi bien.

### 1.2 Le cadre économique : les sociétés de financement
Les sociétés comme FTMO prêtent un capital fictif puis réel (par exemple 100 000 $) à qui réussit une épreuve :
- **phase 1** : +10 % ;
- **phase 2** : +5 % ;
- **à tout moment** : ne jamais perdre plus de 5 % sur une journée ni plus de 10 % au total.

Le trader garde ensuite environ 80 % des gains. Ce cadre façonne tout le projet :
- **l'objectif n'est pas de maximiser le rendement mais de passer l'épreuve sans toucher les murs**, puis de produire
  un rendement régulier ;
- les seules règles « dures » acceptées dans le système sont ces limites de sécurité du compte ;
- tout se mesure en probabilité de réussite d'un challenge simulé, à côté du gain mensuel.

Ordre de grandeur utile : avec 4 comptes de 100 000 $ à +2,5 % par mois et 80 % de part, le revenu serait d'environ
8 000 $ par mois. Il n'est donc pas nécessaire de faire 10 % par mois pour en vivre. Il faut en revanche un avantage
réel, même petit, répété sur beaucoup de trades.

### 1.3 Les choix de principe
- **Une IA qui apprend, pas un robot à règles.** Les indicateurs sont des informations que l'IA voit, jamais des
  déclencheurs du type « si le RSI touche 30, acheter ».
- **Fait maison.** Aucune API d'IA externe (pas de grand modèle de langage appelé pour décider). Tout tourne en local.
- **Honnêteté de la mesure.** Ne jamais annoncer un résultat qui n'a pas été vérifié sur des données jamais vues, avec
  les vrais coûts.
- **Liberté d'action maximale.** L'IA doit pouvoir faire tout ce qu'un humain fait devant MetaTrader 5 : choisir le
  marché, le sens, la taille, le stop, l'objectif, les ordres en attente, le moment de revenir regarder, ou ne rien
  faire.

### 1.4 Les contraintes matérielles
- Un PC Windows, 16 Go de mémoire vive, une carte graphique GTX 1060 de 6 Go.
- Données gratuites ou publiques :
  - Dukascopy (bougies de 15 minutes et horaires, 45 marchés, depuis 2003-2010) ;
  - Kaggle et HistData (or, indices, euro-dollar à la minute) ;
  - Binance (cryptos et données de positionnement des contrats à terme) ;
  - FRED (taux d'intérêt) et CBOE (indices de volatilité) ;
  - le calendrier économique de MetaTrader.
- Un compte démo réel chez un courtier (Tradeco, MetaTrader 5) pour les essais en direct.

---

## 2. Méthode d'évaluation

C'est la partie la plus importante du projet. La plupart des « stratégies gagnantes » qu'on trouve en ligne
disparaissent quand on les mesure correctement. Le protocole s'est durci au fil des erreurs.

### 2.1 Séparation temporelle stricte
Chaque série de données est découpée dans le temps : apprentissage, sélection et contrôle. Un bloc de **12 mois cachés**
(octobre 2025 à octobre 2026) n'est jamais chargé par aucun programme. Ces périodes sont écrites dans un seul fichier
de réglages, avec des assertions qui refusent de démarrer si la règle est violée.

Les périodes « cachées » des pistes individuelles sont protégées par un fichier verrou. Elles ne peuvent être ouvertes
qu'une seule fois, sur une méthode figée à l'avance.

### 2.2 Le jumeau au hasard
Comparer un système à zéro ne suffit pas : en marché haussier, n'importe quel acheteur gagne. Chaque système est
donc comparé à son **jumeau**, qui fait exactement les mêmes gestes (même moment, même taille, même type d'ordre, même
stop) mais tire le **sens** à pile ou face. L'avantage, c'est l'écart avec ce jumeau. La **force** est cet écart divisé
par son incertitude, ce qui revient à une statistique t.

### 2.3 Correction des essais multiples
Quand on essaie N variantes, la meilleure gagne par chance. Le seuil de preuve retenu est
`max(3, sqrt(2·ln N))` : par exemple 3,5 pour 460 variantes testées sur la même période.

### 2.4 Un simulateur fidèle aux conditions FTMO
- frais par marché, mesurés en écart de prix et en commission ;
- commission crypto de 0,0325 % par côté ;
- frais de nuit séparés à l'achat et à la vente, avec la nuit triple au bon jour (mercredi pour devises et métaux,
  vendredi pour indices, énergie et cryptos) ;
- levier du compte ;
- murs à -5 % par jour (minuit de Prague) et -10 % au total, contrôlés au **pire moment** de chaque bougie ;
- règle d'inactivité de 30 jours et minimum de 4 jours de trading ;
- stop et objectif touchés dans la même bougie : on compte le stop ;
- un trou de prix est payé à l'ouverture.

### 2.5 Les contrôles de vérité
Chaque moteur doit passer trois contrôles :
- **une stratégie tricheuse**, qui connaît le futur, doit gagner énormément ;
- **le hasard** doit perdre exactement les frais ;
- **acheter et garder** doit redonner le prix moins les frais, au centime près.

### 2.6 Audit indépendant
Le 16/10, un audit complet du juge (programmes réécrits de zéro) a trouvé trois vraies erreurs :
- **une grave** : la bibliothèque de données lisait les horodatages en microsecondes alors que le code comptait en
  nanosecondes. Les zones d'une stratégie étaient « confirmées » des mois trop tard sur les marchés à la minute ;
- **deux pessimistes** : la force n'était pas pondérée par la taille, et les séances incomplètes étaient bouchées à
  plat.

L'audit a aussi relevé des frais gonflés de 25 % par prudence alors que le glissement réel mesuré était nul. Tout a été
corrigé et recalculé. Chaque défaut a reçu un test pour qu'il ne revienne pas, et la suite automatique compte
aujourd'hui environ 190 tests.

**Leçon :** un bogue de données peut fabriquer ou détruire une stratégie. Il faut vérifier les horodatages événement
par événement, en comparant deux sources, avant tout test d'argent.

---

## 3. Première génération : apprentissage par renforcement sur l'or (septembre - début octobre)

### 3.1 Architecture
- **Agent** : PPO (Proximal Policy Optimization) avec mémoire LSTM, via la bibliothèque stable-baselines3.
- **Observation** : 50 bougies de 15 minutes et une centaine de variables techniques.
- **Entraînement continu** : des cycles d'évolution. Des candidats sont entraînés en parallèle, comparés au champion
  réévalué sur les mêmes données, et promus s'ils font mieux.
- **Juge final** : un jeu de données « sous clé » à partir de 05/2023.
- **En direct** : trading démo sur MetaTrader 5 avec des coupe-circuits FTMO hors de portée de l'IA, un journal des
  décisions et des notifications sur téléphone.

### 3.2 Résultats
Le meilleur agent a fait **+42 % sur la période sous clé** (2023-2026), avec une chance de réussir le challenge simulée
à environ 40-50 %. L'analyse a cependant montré que :
- il achetait dans **100 % des cas** (812 achats sur 812 trades sous clé) ;
- son avantage n'existait **que sur la hausse de l'or 2023-2026** : -0,009 R par trade sur l'or 2010-2018 ;
- sur les autres marchés, il était proche de zéro.

C'était un acheteur de creux porté par une tendance, pas une compétence robuste.

### 3.3 Ce que cette phase a appris
| Constat | Détail |
|---|---|
| Les longs entraînements PPO finissent par **ne plus trader** | Plusieurs fonctions de récompense essayées (pénalité de baisse, gain pur, ratio de Sharpe incrémental) : effondrement vers l'inaction, ou trading frénétique perdant |
| La qualité venait de la **sélection**, pas de l'apprentissage | Sans le filtre évolutionnaire, l'entraînement dérive |
| Les configurations de livre (balayage de liquidité, cassure puis retour, retracement dans la tendance, retour au milieu du range) n'ont **aucun avantage** sur l'or | Toutes négatives sur 2010-2023 (-0,15 à -0,26 R par trade) ; avant frais, c'est du pile ou face |
| Un « cerveau macro » (taux réels, dollar, volatilité) | Taux de réussite 0,48-0,52 sur des années jamais vues, donc rien |
| Un moteur de prédiction supervisé sur 2,5 millions de situations | Corrélation 3-4 %, trop faible après frais |
| Le flux d'ordres Dukascopy (28 millions de cotations sur l'or) | Rien de stable |
| Une période d'examen **fixe** | Fabrique des IA adaptées à cette période. Un champion à +0,8 %/mois sur son examen était perdant sur 32 marchés sur 36 dans les 12 mois suivants. D'où l'examen tournant, tiré au hasard à chaque cycle |
| La seule source d'avantage mesurée | **La tendance de fond** : environ +0,5 %/mois sur 36 marchés de 2018 à 2025 avec des frais réalistes, baisse maximale d'environ 19 % |

### 3.4 Extension multi-marchés
Le même principe a été étendu à 45 marchés, avec des « marchés miroirs » (séries inversées) pour apprendre à vendre.
Les ajouts :
- une récompense en argent ;
- la taille de position choisie par l'IA ;
- les règles FTMO pendant l'entraînement (la mort de la partie au mur) ;
- une note « argent FTMO » qui combine la réussite simulée du challenge et le gain mensuel.

Le système est resté négatif ou nul après frais.

**Diagnostic de fin de phase :** le système avait dérivé vers une « machine à tester des stratégies » : 205
indicateurs humains, des menus de 5 stops et 4 objectifs, des règles ajoutées après chaque échec. Avec une décision
toutes les 15 minutes et une récompense à chaque bougie, il était **structurellement enfermé dans le court terme**, là
où le bruit et les frais dominent. Ces systèmes ont été arrêtés le 13/10.

---

## 4. Deuxième génération : « l'enfant devant le graphique » (12 - 15 octobre)

### 4.1 Conception
Le principe a été repensé à partir de la vision d'origine : un enfant devant un graphique, à qui personne n'explique
rien, et qui découvre seul qu'on peut acheter, vendre, couper une perte, laisser courir un gain. La conception
emprunte deux recettes connues :

1. **Regarder, puis agir** (la recette des grands modèles de langage) :
   - un étage de *préentraînement auto-supervisé* : prévoir la suite du graphique sur plusieurs horizons, corrigé par
     le marché lui-même ;
   - puis un étage d'*apprentissage par renforcement* sur un simulateur fidèle.
2. **Un arbre qui pousse en continu** (proche du *Population Based Training* de DeepMind) :
   - un seul processus « cœur » qui ne s'arrête jamais ;
   - plusieurs **branches** (cerveaux) qui apprennent à tour de rôle, chacune avec son tempérament (ses
     hyperparamètres) ;
   - un jardinier qui donne plus de temps de calcul aux branches qui progressent, fait naître des copies mutées de la
     meilleure, fusionne les poids de deux bonnes branches (comme les *model soups*) et coupe les faibles ;
   - la **cime** est la championne ;
   - des **portes** successives : compte à blanc, puis démo réelle, puis compte FTMO (cette dernière ouverte par un
     humain).

### 4.2 Résultats de l'étage « regarder »
| Expérience | Résultat |
|---|---|
| Prévoir le sens (de 1 h à 1 mois), 47 marchés | **~50,8 %** de sens juste sur des années jamais vues. À 1 jour et 1 semaine, c'est pire que « répondre toujours pareil » ; seuls « 1 h quand il est sûr » (53 %) et « 1 mois quand il est sûr » (56-57 %) battent leur repère |
| 2 ans contre 10 ans d'historique | 50,2 % contre 50,9 % : plus de données aide, mais très peu |
| Apprentissage par cœur | Sur ses années d'apprentissage : 69-99 % de sens juste. Sur des années vierges : 52 % |
| Vision « trader » (le cerveau évalue n'importe quel trade décrit librement : sens, stop, objectif) | Corrélation prévu/réel d'environ 1 % hors frais, environ 0 sur le sens |

**L'ennemi principal identifié : l'apprentissage par cœur.** Les réseaux convolutifs de 500 000 à 700 000 connexions
reconnaissent chaque moment de leurs années d'apprentissage et récitent la suite : +40 à +97 % du risque par trade sur
les années apprises, zéro sur les années vierges. Les situations réellement indépendantes sont bien moins nombreuses
qu'on le croit, environ 100 000 et pas 8 millions, parce que des bougies voisines partagent le même avenir.

Cet apprentissage par cœur a aussi expliqué les comportements extrêmes de l'école. Quand ses yeux « voyaient
l'avenir » à l'entraînement, l'IA misait gros (le casino). Quand ils redevenaient normaux, elle n'osait plus rien
(la paralysie).

### 4.3 Un signal trop faible pour l'apprentissage par renforcement
Le bruit d'une récompense par bougie est environ **400 fois plus fort** que l'avantage espéré par bougie. Avec un
avantage nul, l'agent converge rationnellement vers « ne presque rien faire » : zéro mur et zéro gain. Le système
était sain mais ne gagnait rien. Un grand examen sur 192 challenges (2023 à 09/2025) a donné +0,00 %/mois et 0 % de
murs.

### 4.4 L'école des mille mondes
Pour échapper à l'unique histoire du marché réel, l'IA a été entraînée dans des **marchés synthétiques** générés à la
volée. Chaque monde a des lois cachées tirées au hasard : tendances qui durent des semaines, agitation en vagues,
changements de régime, retour à la moyenne, sauts d'annonces, facteur commun entre marchés, et beaucoup de mondes sans
aucun avantage. Le générateur reproduit les faits stylisés connus des marchés réels.

L'image de départ était celle d'un joueur de poker qui apprend à repérer l'avantage avant d'y aller.

- **Test de vérité**, sur un faux marché à tendance cachée : l'école a trouvé l'avantage (+0,54 %/mois sur des
  périodes jamais vues), puis l'a appris par cœur (+3,3 % sur l'histoire apprise, -0,95 % hors d'elle). Chaque monde
  ne doit donc servir qu'une seule leçon.
- **Sur les vrais marchés** après 800 leçons : toujours environ zéro contre le hasard.

### 4.5 Informations nouvelles plutôt que meilleure vue des prix
Comme les prix seuls ne donnaient rien, des informations externes ont été testées :
- **Calendrier économique.** Un premier avantage spectaculaire (+28 à +54 % de challenges réussis) venait d'une
  **fuite d'information** : le jeu de données public mettait la publication de l'inflation américaine la veille au
  soir, donc la fenêtre de test contenait déjà la vraie annonce. Avec les heures vérifiées de MetaTrader, la méthode
  figée a été jugée une seule fois sur les 12 mois cachés : -1 % en 3 mois. Elle est morte.
- **Traders « maîtres »** (historiques publics : 748 000 ordres de la plateforme Ostium, Paul Wei sur BitMEX,
  Hyperliquid, gTrade). Le talent ne persiste que chez ceux qui ont au moins 200 trades et une force supérieure à 3 :
  11 sur 14 900. Leur avantage vient d'**être du bon côté d'une grande tendance et d'y rester**, pas du choix fin du
  moment d'entrée. Les traders durables tiennent longtemps et tradent peu.
- **La foule de la plateforme Ostium** : elle suit les 5 derniers jours mais n'annonce rien pour la suite.

---

## 5. La chasse à l'avantage (15 - 16 octobre)

Faute d'avantage trouvé par l'IA elle-même, une série de pistes a été testée avec le protocole de la section 2, en
parallèle, par des agents de recherche indépendants. Le but : trouver ce que le marché paie réellement, pour savoir
quoi donner à voir à l'IA.

### 5.1 Méthodes publiées et effets connus
| Piste | Résultat après frais |
|---|---|
| Cassure de l'ouverture de New York (range des N premières minutes) | Négative sur la période cachée (Nasdaq +0,009 R, S&P -0,115 R, or -0,082 R) |
| « Bande de bruit » à la journée (Zarattini, Aziz et Barbon 2024) sur indices et or | Avantage réel AVANT frais, le premier avantage dans la journée mesuré par le projet (force 2,7 à 3,9). Sur la période cachée, -0,26 %/mois. Un trade par jour paie trop de frais |
| Tendance de fond avec entrée réglée dans le temps | Morte : les frais de nuit FTMO (3 à 13 %/an) dépassent le gain |
| Retour à la moyenne des paires de devises croisées | +0,1 %/mois, trop petit |
| Effets de calendrier (fin de mois, séances, fixings) | Tous morts sauf « l'or monte pendant la séance asiatique » (force 3,45 sur des années vierges 2004-2009), mort après correction d'une heure de décalage dans les données et frais |
| Achat des creux sur indices américains | Réel (force 4,5 / 1,5 / 3,4) mais les krachs arrivent sur tous les indices en même temps, et le résultat est nul en compte challenge |
| Fin de l'inversion du VIX (achat S&P 10 jours) | Positif sur 3 périodes (+0,2 à +0,3 %/mois) mais 3-4 trades par an |
| **Cassure 24 h du bitcoin** (clôture horaire au-delà du plus haut ou du plus bas des 24 h, sortie le soir) | **Seul candidat qui a tenu sur sa période cachée** (+1,1 %/mois sur 2024-2026 avec des frais bas, 71 % de challenges réussis contre 10 % pour les jumeaux). Avec la vraie commission crypto FTMO, l'avantage est divisé par environ 2. Propre au bitcoin et à l'ether, il échoue sur les autres cryptos. En démo réelle depuis le 16/10 |

### 5.2 La méthode du porteur du projet
Sa méthode a été traduite fidèlement depuis le code source de son indicateur TradingView :
- **définition d'une zone** : une bougie opposée, un écart de prix laissé ouvert, puis une cassure de structure ;
- **zones imbriquées** de la journalière jusqu'aux 3 minutes ;
- **entrée** au milieu de la plus petite zone ;
- **stop** derrière la zone ;
- **sorties** par tiers ou 80/20, jusqu'à la zone opposée.

| Mesure | Résultat |
|---|---|
| Ses zones contre des zones placées au hasard à même distance | Réaction du prix de 38 % contre 39 % ; ses zones sont un peu moins traversées (+0,1 R) |
| Concepts combinés appris par machine (écart de prix ouvert, cassure, balayage, 6 placements de stop, 8 sorties) sur des centaines de milliers de contacts | Aucune combinaison ne gagne au contrôle |
| Système complet, avec le juge corrigé, 71 variantes | Une seule tient sur les 3 périodes : cryptos, départ 4 h, **+0,22 R par trade, force 2,5** (sous le seuil de 3). En compte FTMO : +0,3 %/mois, 23 mois médians pour réussir un challenge |
| Traduction fidèle de l'indicateur, toutes unités | Ne gagne nulle part après frais (+0,09 à -0,30 R) |
| Fréquence | L'indicateur seul donne 0,2 trade par semaine sur 4 indices, contre 4-5 déclarés par le trader. Ses trades réels dépendent donc de son jugement et d'autres outils, impossibles à reproduire sans son historique |

L'avantage de la méthode, quand il existe, vient des **gros trades qui courent** (un profil de suiveur de tendance),
pas du contact avec la zone lui-même.

### 5.3 L'information la plus forte : « contre la foule »
Binance publie la part des comptes acheteurs sur ses contrats à terme crypto. La règle testée : **quand cette part
est à son plus haut de 90 jours, vendre pour 24 h ; à son plus bas, acheter.** Résultats :
- **avant frais** : +2,4 à +3,7 %/mois sur 3 jeux de données indépendants, force ≥ 3 sur chacun. C'est la seule
  information du projet qui a passé le seuil de preuve plusieurs fois ;
- **après les frais FTMO** (commission crypto, nuits à 30 %/an), elle tombe à +0,06 à +1,76 %/mois selon la période ;
- à coûts de Bourse avec des ordres limites (par exemple une société de financement adossée à Bybit), elle resterait
  vers +1 %/mois.
- Mesurée avec le juge corrigé sur 2022-2023 : force 3,4 à pleine taille, avec une baisse maximale de 44 %. Il faut
  donc réduire fortement la taille, et elle se dégrade avec des entrées par ordre limite.

### 5.4 Synthèse de la chasse
Le meilleur compte FTMO mesuré honnêtement combine la cassure du bitcoin et de l'ether avec la méthode de zones sur
les cryptos : environ +0,66 %/mois sur 2022-2026, avec une espérance par challenge légèrement positive. **Ce n'est pas
de quoi vivre.** Le facteur limitant n'est pas toujours l'absence d'avantage brut, mais **le coût d'exécution**. Les
frais FTMO sur les cryptos (environ 0,066 % aller-retour pour le bitcoin, plus 30 %/an de frais de nuit) mangent des
avantages réels.

---

## 6. Troisième génération : l'arbre et l'asymétrie par la précision (16 - 17 octobre)

### 6.1 L'idée
Le porteur du projet a résumé la logique du trader discrétionnaire en une phrase : **l'asymétrie par la précision.**
- La grande zone (journalière, 4 heures) donne la direction et la **destination**.
- On descend dans les zones imbriquées jusqu'au point exact où l'idée devient fausse.
- Le stop se met juste derrière ce point. Il est donc petit, et le même mouvement vaut alors 10 fois le risque au lieu
  de 2.
- On encaisse une partie à un premier objectif, on remonte le stop à l'entrée, le reste court.

Cette logique n'est **pas codée comme une règle**. Elle définit ce que l'IA *voit* et ce que ses *mains* peuvent
exprimer. L'IA décide elle-même quand et comment s'en servir.

### 6.2 Construction
| Élément | Contenu |
|---|---|
| **Ce qu'elle voit** | Les zones vivantes de 7 unités de temps (journalière à 3 minutes) : distance au prix en unités d'agitation, hauteur, âge, déjà touchée ou non, a réagi ou non, imbriquée dans une plus grande. Aussi les sommets et creux confirmés, la tendance par unité, les 8 dernières clôtures sur 4 unités, l'agitation, le coût d'un aller-retour, l'heure, les séances, son compte. Tout est calculé sans regarder le futur (test : le calcul coupé à l'instant t est identique au calcul complet) |
| **Ce qu'elle choisit** | Rien, acheter ou vendre ; au marché ou par ordre limite sur une zone ; le stop derrière une zone ou un sommet/creux, plus une marge ; la destination ; la part encaissée à l'objectif 1 (0, 50 ou 80 %) ; le risque (0,1 à 2 %) ; la durée de l'ordre ; quand revenir regarder (15 min à 4 h) ; fermer ou annuler |
| **Monde** | 66 marchés (19 cryptos, or, Nasdaq, S&P 500 et euro à la minute, 43 autres marchés FTMO). Un simulateur FTMO réécrit pour aller vite, identique au centime près au simulateur de référence |
| **Récompense** | L'argent net du compte. Mourir à un mur coûte très cher, ne rien faire ne coûte rien |
| **Note de sélection** | Réussite rapide du challenge, gain mensuel **au-dessus de son jumeau au hasard**, pénalité des morts et des baisses |
| **Arbre** | Un cœur continu (données et caches chargés une fois), 4 branches à tempéraments différents (patiente, vise loin, active, logique du porteur du projet). À chaque génération, chaque branche apprend un tour, puis toutes passent le même examen ; la meilleure se divise, la plus faible est coupée et archivée |
| **Cadence** | Environ 3 minutes par génération sur la GTX 1060, objectif 1 000 générations. Reprise automatique après un arrêt, surveillance par une tâche Windows, images et rapports sur téléphone |

### 6.3 Résultats jusqu'à la génération 450
| Génération | Gain par mois de la cime | Jumeau au hasard | Gain moyen par trade | Trades par mois |
|---|---|---|---|---|
| 1 | -0,51 % | -0,46 % | -0,032 R | 48 |
| 100 | -0,10 % | -0,20 % | ~0 | 36 |
| 330 | +0,07 % | -0,07 % | ~0 | 13 |
| 450 (avec la foule) | +0,13 % (sélection) / -0,24 % (contrôle) | -0,05 / -0,28 % | -0,001 / -0,008 R | 36-40 |

Ce que l'IA a appris seule :
- **le geste du trader** : 81 à 93 % de ses entrées sont des ordres limites sur une de ses zones, 91 % de ses stops
  sont derrière une zone, et elle vise en moyenne 4,6 à 5 fois son risque ;
- **la sélectivité** : elle n'est en position que 8 à 15 % du temps ;
- **le respect des murs** : quasiment aucune mort à l'examen.

Ce qu'elle n'a pas appris : **la qualité**. Un trade vaut toujours environ 0 R en moyenne, et l'avance sur le jumeau
vue à l'examen de sélection ne tient pas sur la période de contrôle. Ce résultat rejoint celui de la mesure directe :
les zones donnent un bon cadre pour placer un stop, mais pas, à elles seules, un avantage sur la direction.

### 6.4 Greffe de la foule
À la génération 391, les branches ont reçu les « yeux de la foule » : 19 variables Binance (part des acheteurs et sa
place dans ses fourchettes, financement, positions ouvertes, flux d'acheteurs et vendeurs pressés, écart entre contrat
perpétuel et comptant). La greffe se fait **sans perte** : les poids des nouvelles entrées démarrent à zéro, et les
décisions identiques avant et après la greffe sont vérifiées.

Comme ces données n'existent que depuis fin 2020, les périodes ont été décalées : apprentissage jusqu'à fin 2022,
sélection sur 2023, contrôle de 2024 à 09/2025. Une leçon sur deux se passe dans l'époque où la foule existe. Après
60 générations, aucun effet mesurable sur le gain par trade.

---

## 7. Ce que le projet a établi

### 7.1 Sur les marchés
1. **L'agitation se prévoit, la direction presque pas.** 58 à 80 % de la variance de l'agitation s'explique sur nos
   données. La direction plafonne à environ 51 % sur les horizons de 1 h à 1 semaine.
2. **La tendance de fond est la seule source robuste et générale**, mais elle est faible : environ +0,5 %/mois sur un
   panier de marchés, avec des baisses de près de 20 %. Elle a aussi largement disparu à court terme sur les devises et
   les indices depuis 2009.
3. **Les avantages courts existent, mais sont locaux et fragiles** (cassure du bitcoin, bande de bruit, position de la
   foule crypto). Ils sont souvent du même ordre que les frais.
4. **Les coûts décident de tout.** Ce sont l'écart de prix, la commission, les frais de nuit, et le nombre
   d'allers-retours. Un trade par jour sur un indice coûte plus que l'avantage dans la journée mesuré. Les frais de
   nuit FTMO tuent le portage de tendance.
5. **Les concepts populaires** (zones d'offre et de demande, blocs d'ordres, écarts de prix laissés ouverts, cassures
   de structure, configurations de livre) ne battent pas des zones placées au hasard. Leur intérêt réel est de
   **placer un stop à un endroit qui a du sens**.
6. Chez les traders qui gagnent durablement, l'avantage vient de la **conviction de fond tenue longtemps**, pas du
   moment précis d'entrée.

### 7.2 Sur l'apprentissage automatique appliqué au trading
1. **L'apprentissage par cœur est l'ennemi numéro un.** Le marché ne fournit qu'une seule histoire, avec peu de
   situations indépendantes. Tout réseau assez gros finit par la réciter. Remèdes partiels : petits cerveaux, marchés
   miroirs, marchés synthétiques, séparation temporelle stricte, et surtout un contrôle sur des années jamais vues.
2. **L'apprentissage par renforcement seul ne trouve pas un avantage petit.** Le rapport signal sur bruit d'une
   récompense en argent est trop faible. Les agents dérivent vers le casino ou la paralysie. La sélection par
   population stabilise mais ne crée pas d'avantage.
3. **La liberté ne crée pas d'avantage.** Donner à l'IA tous les gestes d'un trader est nécessaire pour qu'elle puisse
   exploiter un avantage. Mais si l'information n'en contient pas, la liberté ne sert qu'à mieux limiter les pertes.
4. **Les bogues de mesure produisent des résultats spectaculaires** : horodatages mal lus, calendrier décalé, témoin
   mal placé. Le premier réflexe face à un bon résultat doit être d'en chercher la fuite.

### 7.3 Sur la méthode
- Figer la définition d'une stratégie **avant** de la tester, et l'écrire dans un document daté.
- N'ouvrir une période cachée qu'une seule fois, sur une méthode figée.
- Juger contre un jumeau au hasard, jamais contre zéro.
- Compter les variantes essayées et relever le seuil de preuve en conséquence.
- Vérifier en direct : les démos réelles sont le seul juge qui ne peut pas avoir été vu.

---

## 8. Où en est le projet, et la suite

### 8.1 Ce qui tourne au 17/10/2026
- L'arbre d'apprentissage, vers 1 000 générations, avec les yeux de la foule.
- En démo réelle (courtier Tradeco) : la cassure du bitcoin et la méthode de zones sur le bitcoin et l'ether.
- Un suivi « à blanc » de la règle « contre la foule » sur les cryptos, avec deux comptes fictifs (coûts FTMO et coûts
  de Bourse).
- Des collecteurs de données (positions de traders, foule devises) et un relevé des écarts de prix en séance.

### 8.2 La piste en cours : apprendre à juger un trade avant d'apprendre à trader
Le diagnostic de la section 6 vient du signal : sur une partie entière, un bon trade se perd parmi des centaines de
décisions. La prochaine étape renverse l'ordre, comme un trader qui a vu des milliers de graphiques avant de savoir
reconnaître une bonne occasion :
1. générer **des millions de trades candidats** sur 2010-2022, exprimés comme les gestes de l'IA (entrée sur une
   zone, stop derrière une structure, destination), et calculer leur résultat réel frais compris : a-t-il atteint 2R
   avant son stop ?
2. entraîner un **juge supervisé** qui estime la probabilité d'atteindre 1R, 2R ou 3R et le gain attendu. Les gagnants
   à 2R et plus sont mis en avant, puis les probabilités sont recalibrées pour rester honnêtes ;
3. mesurer si les trades qu'il classe parmi les meilleurs atteignent 2R **plus d'une fois sur trois**, le seuil de
   rentabilité avec un objectif à 2R, sur 2023 puis sur 2024-2025. Comparer avec des candidats posés sur de fausses
   zones ;
4. seulement si c'est le cas, donner cet avis à l'arbre, qui apprendra à choisir et à gérer.

Ce passage du renforcement pur à un **préentraînement supervisé sur la valeur des actions** est la recette classique
quand la récompense est rare et bruitée.

**Premier résultat (17/10 au soir).** Le juge a été entraîné sur 6,4 millions de candidats, dont un quart de témoins
posés sur de fausses zones. Ses probabilités sont bien calibrées : dans son meilleur dixième, 32 % de trades à 2R
prévus et 32 % observés. Mais sur 2024-2025, même son meilleur 1 % reste juste sous le seuil de rentabilité : 26,7 %
de trades à 2R pour 27,3 % nécessaires, soit -0,014 R par trade. Il passe de -0,06 R à -0,02 R en évitant surtout les
trades trop chers en frais (stops trop serrés), et les témoins sur de fausses zones font presque aussi bien. **Les
zones elles-mêmes n'apportent donc pas d'information sur la direction, ce qui confirme les mesures directes.**

Une seule case positive, à vérifier contre un jumeau au hasard avant d'y croire : le meilleur 1 % du juge sans les
données de la foule, joué jusqu'à sa destination, fait +0,16 R en 2023 comme en 2024-2025. Mais ce sont uniquement des
achats pendant la hausse des cryptos, et c'est une case parmi une centaine regardées.

**Suite (17/10 dans la nuit) : direction prouvée + précision.** Cette case a été testée contre son jumeau : son gain
vient des jours de hausse des cryptos, et acheter n'importe quel trade du même marché le même jour fait aussi bien.
Deux combinaisons ont ensuite été jugées, avec 65 cases figées à l'avance et un seuil de preuve de 3 :
- **garder les trades de zone dont le sens suit une direction prouvée** (tendance de fond, cassure du bitcoin, foule
  crypto) : les directions trient vraiment, puisque aller contre elles coûte de -0,12 à -0,16 R par trade. Mais être
  du bon côté ne ramène qu'à l'équilibre (foule crypto : 17,3 % de trades à 2R pour 17,0 % nécessaires), et de
  fausses zones filtrées dans le même sens font pareil ;
- **inverser la logique** : le signal choisit le moment et le sens, la structure ne place que le stop. La meilleure
  variante choisie sur 2020-2023 (contre la foule, stop derrière le dernier creux ou sommet 1 h / 4 h, objectif 3R,
  sortie à 24 h) bat son jumeau mais ne garde que +0,008 R par trade après frais en 2024-2025 (force 0,3). Un stop à
  distance fixe fait aussi bien que le stop placé sur la structure.

Conclusion à ce stade : **le placement du stop par la structure ne crée pas d'avantage.** Il faut une source de
direction dont l'avance sur le hasard dépasse nettement les frais, d'au moins +0,1 R par trade. Aucune n'a été
trouvée dans les conditions de coûts FTMO.

### 8.3 Questions ouvertes
- **Savoir fondamental** (taux, inflation, calendrier, différentiels de rendement) : volontairement reporté. On renforce
  d'abord les bases, et on n'ajoute une source que si la précédente a montré son effet.
- **Lieu d'exécution** : plusieurs avantages mesurés survivent à des coûts de Bourse mais pas aux coûts FTMO sur les
  cryptos. Le choix de la société de financement fait partie de la stratégie.
- **Règles d'usage** : FTMO interdit tout logiciel ou IA qui « donne un avantage déloyal », plus de 2 000 requêtes par
  jour, et les changements brusques de taille. Il faut une confirmation écrite avant de payer un challenge.
- **Objectif chiffré** : l'ambition de départ (8 à 10 % par mois) dépasse de loin ce que les meilleurs gérants
  obtiennent durablement (1 à 3 % par mois). Un objectif réaliste est de passer le challenge avec un avantage réel et
  de produire 1 à 3 % par mois sur plusieurs comptes financés.

---

## Annexe A — Correspondance des termes

| Terme du projet | Terme technique |
|---|---|
| Regarder puis agir | Préentraînement auto-supervisé, puis ajustement par apprentissage par renforcement |
| L'arbre, les branches, la cime | *Population Based Training* asynchrone ; exploitation et exploration (copie de la meilleure branche puis mutation) ; élitisme |
| Fusion de branches | *Model merging* / moyenne de poids (*model soups*) |
| Greffe sans perte | Agrandissement de l'entrée avec des poids nuls (dans l'esprit de *Net2Net*) |
| Jumeau au hasard | Placebo apparié sur le sens, test par permutation |
| Force | Statistique t de l'écart au placebo |
| Période cachée, verrou | Jeu de test scellé, évaluation unique |
| Examen tournant | Validation sur fenêtres tirées au hasard (*walk-forward* aléatoire) |
| Marchés miroirs | Augmentation de données par inversion de la série |
| Mille mondes | *Domain randomization* sur des marchés synthétiques (dans l'esprit de la main robotique d'OpenAI et de TabPFN) |
| Juger un trade | Modèle de valeur des actions supervisé, *meta-labeling* |
| R | Gain d'un trade exprimé en multiples du risque pris |

## Annexe B — Pile technique
- Python 3.11, PyTorch (CUDA), stable-baselines3 (première génération), NumPy, pandas, numba, scikit-learn.
- MetaTrader 5 (paquet Python officiel) pour les prix et ordres en démo ; un programme MQL5 pour exporter le
  calendrier économique.
- Tâches planifiées Windows pour la surveillance et la relance automatique ; notifications par ntfy.
- Environ 190 tests automatisés : moteurs de simulation, absence de futur, frais, reprise après arrêt, greffes.

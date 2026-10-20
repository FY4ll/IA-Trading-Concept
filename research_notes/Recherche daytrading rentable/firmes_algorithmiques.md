# D'où vient l'avantage des firmes algorithmiques intraday, et ce qui reste accessible à un particulier sur MT5 / FTMO

Notes de recherche (15/10/2026). Cadre : particulier, CFD via MetaTrader 5, bougies 1 min / 15 min, ~1 s de latence,
règles FTMO. Chaque fait a sa source ; les déductions sont dans « Inferences » ; ce qui n'a pas pu être vérifié est
dans « Gaps ».

## Question 1 — Rentabilité publiée des firmes à haute fréquence, teneurs de marché et fonds quantitatifs court terme

### Takeaway
L'avantage des firmes à haute fréquence est réel et énorme en qualité (rapport rendement/risque de 4 à 9 et plus, une
seule journée perdante sur ~1 238 chez Virtu avant sa cotation) mais il vient de la VITESSE relative et de la
capture de l'écart achat/vente, et il est concentré « le gagnant prend tout » chez les plus rapides. Ce n'est pas un
avantage de prévision exploitable à 1 seconde de latence.

### Cited Findings
- Étude Baron, Brogaard, Hagströmer, Kirilenko (« Risk and return in high-frequency trading », JFQA 2019, données
  du régulateur américain des contrats à terme) : la firme à haute fréquence médiane obtient un rapport
  rendement/risque annualisé de 4,3 et un rendement anormal (alpha à quatre facteurs) de 22,02 %/an — [CFTC (version de travail)](https://www.cftc.gov/idc/groups/public/@economicanalysis/documents/file/oce_riskandreturn0414.pdf) ; [IDEAS/RePEc JFQA 2019](https://ideas.repec.org/a/cup/jfinqa/v54y2019i03p993-1024_00.html)
- Même étude : les firmes « agressives » (qui prennent la liquidité) gagnent en moyenne 122,1 %/an, rapport
  rendement/risque 4,29, alpha 90,67 % — [ai-CIO, résumé de l'étude](https://ai-cio.com/news/high-frequency-trading-winner-takes-all)
- Même étude : les différences de latence RELATIVE expliquent de grandes différences de performance ; une firme qui
  gagne des rangs de vitesse grâce à une amélioration de colocation voit sa performance s'améliorer ; la vitesse aide
  par deux canaux : information de très courte durée et gestion du risque ; elle sert à la tenue de marché comme à
  l'arbitrage entre marchés ; les revenus s'accumulent durablement chez les meilleurs (« le gagnant prend tout ») — [CFTC](https://www.cftc.gov/idc/groups/public/@economicanalysis/documents/file/oce_riskandreturn0414.pdf) ; [ai-CIO](https://ai-cio.com/news/high-frequency-trading-winner-takes-all)
- Menkveld (« High Frequency Trading and the New-Market Makers », Journal of Financial Markets 2013) : un grand
  teneur de marché à haute fréquence sur Chi-X gagne 0,88 € brut par transaction = +1,55 € sur l'écart (frais
  déduits) − 0,68 € de perte de « positionnement » (le prix bouge contre son stock) ; capital engagé ~2,05 M€ par
  action ; rapport rendement/risque annualisé 9,35 — [Tinbergen Institute](https://www.tinbergen.nl/discussion-paper/5443/11-076-2-high-frequency-trading-and-the-new-market-makers) ; [PDF](https://c.mql5.com/forextsd/forum/102/high_frequency_trading_and_the_new-market_makers.pdf)
- Virtu (teneur de marché coté) : prospectus de cotation 2014 — « une seule journée de trading perdante » sur 1 238
  jours, attribuée à sa gestion du risque en temps réel — [Hedge Fund Alpha](https://hedgefundalpha.com/news/virtu-financial-ipo-2/) ; [Finance Magnates](https://financemagnates.com/institutional-forex/technology/virtu-financials-ipo-becomes-a-bright-spark-in-the-doom-gloom-affecting-the-industry)
- Virtu, rapport annuel 2024 (10-K) : revenu net de trading ajusté 1 597,7 M$ (+32 %), soit 6,4 M$ par jour en
  moyenne (4,8 M$ en 2023) — [SEC, 10-K 2024](https://www.sec.gov/Archives/edgar/data/1592386/000159238625000055/virt-20241231.htm)
- XTX Markets (teneur de marché algorithmique, très présent sur les devises) : bénéfice net 2024 record de
  1,28 Md£ (835 M£ en 2023), revenus 2,74 Md£ — [Finance Magnates](https://www.financemagnates.com/forex/xtx-markets-posts-50-profit-jump-to-128-billion-on-trading-surge) ; [Global Trading](https://www.globaltrading.net/?p=38009)
- Citadel Securities : 9,7 Md$ de revenu net de trading en 2024 (+55 %) ; Jane Street estimée à ~20 Md$ de revenus
  de trading 2024 (estimation d'analystes, non publiée officiellement) — [Finance Magnates](https://www.financemagnates.com/forex/xtx-markets-posts-50-profit-jump-to-128-billion-on-trading-surge) ; [Business Today](https://www.businesstoday.in/amp/markets/stocks/story/jane-street-how-a-low-profile-company-is-outearning-some-of-wall-streets-biggest-players-449350-2024-10-09)
- Renaissance Medallion (fonds quantitatif court terme fermé aux extérieurs) : reconstitution de G. Zuckerman, 1988-2018
  : +66,1 %/an avant frais, +39,1 %/an après frais — [Wealth Management](https://www.wealthmanagement.com/alternative-investments/jim-simons-built-the-best-hedge-fund-ever) ; [Advisor Perspectives](https://www.advisorperspectives.com/articles/2019/12/09/was-renaissances-success-luck-or-skill-and-was-it-behind-trumps-victory)

### Inferences
- Ces firmes gagnent PEU par transaction (moins d'un euro sur Chi-X) mais sur des millions de transactions, avec
  un stock tenu quelques secondes ; leur qualité vient de la loi des grands nombres + vitesse, pas d'une prévision
  à 15 minutes. Un particulier qui fait quelques transactions par jour ne peut pas reproduire ce profil.
- Le chiffre clé pour COLLAPSAR : chez Menkveld, la tenue de marché PERD sur le mouvement du prix (−0,68 €) ; tout
  son gain vient de l'écart encaissé. Sur un CFD, le particulier PAIE cet écart : il est de l'autre côté de cette
  source d'avantage.
- Medallion est la preuve qu'un avantage statistique court terme hors vitesse pure existe, mais avec des centaines de
  chercheurs, des données de toute nature, des frais d'exécution minimaux et une capacité volontairement plafonnée.

### Gaps
- Je n'ai pas pu extraire du texte intégral de l'étude CFTC (PDF illisible par l'outil) les chiffres de gain par
  contrat, le temps moyen de détention et la part des 10 premières firmes ; seuls les chiffres du résumé sont cités.
- Pas de chiffres publics fiables pour Jump, Two Sigma ou les fonds « tendance » à modèles courts (intraday CTAs) ;
  Two Sigma et Jump ne publient pas leurs résultats.
- Pas de nombre de journées perdantes publié par Virtu dans le 10-K 2024 (le « 1 sur 1 238 » date de 2014).

## Question 2 — Déséquilibre du carnet d'ordres et du flux d'ordres : force et vitesse de disparition du signal

### Takeaway
Le déséquilibre du flux d'ordres au meilleur prix explique très bien la variation de prix SIMULTANÉE et prédit le
prix sur quelques secondes ; le pouvoir prédictif disparaît après quelques changements du prix médian (horizons
typiques 3 à 10 s, au mieux quelques dizaines de secondes). Sur des bougies de 1 minute ou 15 minutes, sans carnet
d'ordres et avec 1 s de latence : non accessible.

### Cited Findings
- Cont, Kukanov, Stoikov (« The price impact of order book events », Journal of Financial Econometrics 2014) : sur de
  courts intervalles, les variations de prix sont principalement dues au déséquilibre du flux d'ordres au meilleur
  achat/vente ; relation linéaire dont la pente est inversement proportionnelle à la profondeur du marché ; résultat
  stable selon les échelles de temps — [arXiv 1011.6402](https://arxiv.org/abs/1011.6402) ; [HAL](https://hal.sorbonne-universite.fr/hal-00937055)
- Le déséquilibre du carnet a un fort pouvoir prédictif sur exactement les 2 prochains changements du prix médian,
  puis il tombe presque à zéro — [arXiv 1707.01167](https://arxiv.org/pdf/1707.01167)
- Horizons de prévision les plus précis : 3 à 10 secondes pour les actions étudiées ; agrégé sur de brefs intervalles,
  le lien reste fort surtout dans les dizaines de secondes — [arXiv 1803.05690](https://arxiv.org/pdf/1803.05690) ; [TU Delft](https://repository.tudelft.nl/file/File_86f90b81-c139-4680-a0d0-848dcd4e3994)
- Sur les devises, Evans et Lyons (2002) : relation positive et linéaire entre le déséquilibre des transactions d'une
  JOURNÉE et le rendement du jour (flux d'ordres interbancaires, donnée non disponible au particulier) ; sur le
  contrat à terme DAX, rendement d'une fenêtre de 5 min = fonction concave du déséquilibre des transactions de la
  MÊME fenêtre (Kempf et Korn 1999) — [TU Delft (revue de littérature)](https://repository.tudelft.nl/file/File_86f90b81-c139-4680-a0d0-848dcd4e3994)

### Inferences
- Les relations sur 5 min ou à la journée sont surtout CONTEMPORAINES (le flux explique le prix de la même période),
  pas prédictives : utiles pour comprendre, pas pour gagner après coup.
- MT5 chez un courtier de CFD : pas de volumes réels, pas de carnet (vérifié dans ce projet chez Tradeco). Le seul
  proxy est le « volume de ticks » (nombre de cotations) : il mesure l'activité, pas le sens du flux.
- Rappel interne du projet : l'essai sur le flux d'ordres Dukascopy de l'or (28,6 M cotations) n'a « rien de
  stable » donné — cohérent avec la littérature (signal de quelques secondes, invisible en bougies 15 min).

### Gaps
- R² exact de Cont-Kukanov-Stoikov par échelle de temps non extrait (texte intégral non lu).
- Pas d'étude trouvée mesurant précisément le déséquilibre sur les DEVISES au comptant à l'horizon 1 minute.

## Question 3 — Arbitrage statistique court terme, paires, et décalages entre marchés (contrats à terme -> CFD, indices -> devises, or -> dollar)

### Takeaway
La formation du prix se fait sur les contrats à terme (bons du Trésor, indices, EUR/USD), et les décalages entre
marchés liés se mesurent en MILLISECONDES (E-mini en avance de ~5 ms sur le bon du Trésor à 10 ans). Ces décalages
sont exploités par les firmes colocalisées ; vus à 1 s de latence et en bougies de 1 min, ils ont disparu. L'arbitrage
de paires/co-intégration intraday reste théoriquement possible, mais les frais de CFD (deux écarts payés) le rendent
très difficile.

### Cited Findings
- La découverte du prix sur le Trésor américain, les actions et l'EUR/USD a lieu principalement sur les CONTRATS À
  TERME plutôt que sur le comptant — [Liberty Street Economics (Fed de New York)](https://libertystreeteconomics.newyorkfed.org/?p=683) ; [Unicatt, modèle multi-actifs](https://publires.unicatt.it/it/publications/high-frequency-lead-lag-effects-and-cross-asset-linkages-a-multi-/)
- Le marché E-mini S&P 500 précède le marché comptant du Trésor à 10 ans avec un décalage d'environ +5 millisecondes — [Liberty Street Economics](https://libertystreeteconomics.newyorkfed.org/?p=683)
- Les études de décalage entre actifs couvrent des décalages de quelques microsecondes à une minute ; l'information du
  prix et du déséquilibre du carnet d'un actif aide à prévoir le prix médian d'un autre actif lié — [Université de Francfort (mémoires sur les décalages ultra-haute fréquence)](https://www.efinance.wiwi.uni-frankfurt.de/en/teaching/master-theses/selection-of-completed-theses/lead-lag-structures-in-ultra-high-frequency-trading.html) ; [Unicatt](https://publires.unicatt.it/it/publications/high-frequency-lead-lag-effects-and-cross-asset-linkages-a-multi-/)
- L'étude Baron et al. classe l'arbitrage entre marchés parmi les stratégies où la vitesse relative fait la
  différence — [ai-CIO](https://ai-cio.com/news/high-frequency-trading-winner-takes-all)

### Inferences
- Un CFD sur indice (US500, GER40) est un prix DÉRIVÉ du contrat à terme ou du comptant, cotés par le courtier :
  quand le CFD « retarde » le contrat à terme, c'est soit de quelques millisecondes (pris par les firmes), soit un
  défaut du flux de prix du courtier — exploiter ce dernier est exactement ce que FTMO interdit (voir Q4).
- Paires/co-intégration intraday sur CFD (ex. US500 contre US100, EUR/USD contre GBP/USD) : deux écarts + commission à
  chaque aller-retour ; les écarts de prix intraday entre actifs liés sont du même ordre que ces frais. Verdict
  partiel : seulement à l'horizon de plusieurs heures/jours, pas en scalping.
- Les liens or/dollar, indices/yen existent mais à 1 min ils sont contemporains (mêmes nouvelles, même minute), pas
  décalés : ils servent de « contexte » (régime de marché), pas de signal d'entrée.

### Gaps
- Pas d'étude trouvée quantifiant un décalage exploitable à l'échelle de la MINUTE entre contrats à terme et CFD de
  courtier de détail.
- Pas de chiffres publiés de rendement net pour l'arbitrage de paires intraday sur CFD.

## Question 4 — Spécificités du courtier / FTMO : formation du prix des CFD, frais, latence, pratiques interdites

### Takeaway
FTMO interdit noir sur blanc d'exploiter des erreurs ou retards de prix, les outils « ultra-rapides » ou une IA qui
donnerait un « avantage déloyal », plus de 2 000 requêtes serveur par jour, et le trading de trous de cotation
autour des grandes nouvelles. Les frais (5 $ par lot sur les devises, écarts) rendent le scalping de quelques points
structurellement perdant.

### Cited Findings
- FTMO interdit d'« utiliser des stratégies qui exploitent des erreurs de nos services, comme des erreurs d'affichage
  des prix ou des retards de leur mise à jour » — [FTMO (page « Forbidden trading practices », version OANDA-FTMO)](https://ftmo.oanda.com/forbidden-trading-practices/)
- FTMO interdit d'« utiliser tout logiciel, intelligence artificielle, outil ultra-rapide ou saisie massive de
  données qui pourrait manipuler, abuser ou vous donner un avantage déloyal » — [FTMO](https://ftmo.oanda.com/forbidden-trading-practices/)
- Robots/EA interdits s'ils rendent le compte « hyperactif » : plus de 2 000 requêtes serveur par jour — [FTMO](https://ftmo.oanda.com/forbidden-trading-practices/) ; certains résumés tiers ajoutent un plafond de 200 ordres ouverts simultanés — [PickMyTrade (tiers)](https://blog.pickmytrade.io/what-ea-are-banned-on-ftmo/)
- Trading de trous de cotation interdit « quand des nouvelles mondiales majeures, événements macroéconomiques ou
  résultats d'entreprises sont programmés » ou « deux heures ou moins avant la fermeture d'un marché » — [FTMO](https://ftmo.oanda.com/forbidden-trading-practices/)
- Interdits aussi : positions opposées simultanées à but manipulatoire (sauf sur un seul compte) ; stratégies qui
  répartissent artificiellement le profit sur plusieurs jours sans répartir le risque ; accès d'un tiers au compte — [FTMO](https://ftmo.oanda.com/forbidden-trading-practices/)
- Résumés tiers : le « tick scalping » (gains au tick exploitant flux de prix ou latence) et l'arbitrage de latence
  entre fournisseurs de cotations sont qualifiés de pratiques « toxiques » ; un scalper ordinaire tenant des minutes
  n'est pas visé — [PickMyTrade](https://blog.pickmytrade.io/what-ea-are-banned-on-ftmo/) ; [Pro-Tix (autre société, mêmes principes)](https://pro-tix.help.center/article/1028-what-trading-styles-and-strategies-are-permitted)
- Frais FTMO (source tiers) : 5 $ par lot sur les devises, pas de commission sur les indices, 0,0014 % du volume sur
  les métaux, 0,001 % sur l'énergie — [cTrader, fiche FTMO](https://ctrader.com/prop-firms/ftmo) (non vérifié sur ftmo.com)
- Repère d'écart sur EUR/USD chez un courtier « brut » compétitif : 0,1 point en moyenne (Pepperstone Razor) — [Pepperstone](https://pepperstone.com/en-ae/markets/forex/eur-cad)

### Inferences
- Coût d'un aller-retour EUR/USD (5 $/lot ≈ 0,5 point + écart ~0,1-0,2 point) ≈ 0,6-0,7 point, soit ~0,006 % du prix :
  sur un objectif de 3-5 points (scalping 1 min), les frais mangent 15-25 % du gain brut ; sur un mouvement de 20-40
  points (bougies 15 min, plusieurs heures), 2-3 %. Plus l'horizon est long, plus un petit avantage survit aux frais.
- L'arbitrage de latence contre le flux de démo d'une société de financement est (1) interdit, (2) ne génère pas
  d'argent réel transférable (comptes simulés), (3) vaut exclusion et confiscation des gains.
- La clause « IA … avantage déloyal » est ambiguë pour COLLAPSAR : déjà notée dans la mémoire du projet ; à faire
  confirmer PAR ÉCRIT par FTMO avant tout paiement.

### Gaps
- Page officielle ftmo.com des pratiques interdites introuvable à l'adresse testée (erreur 404) ; citée via le
  domaine FTMO-OANDA. Écarts typiques réels FTMO par marché non trouvés (à mesurer directement sur MT5).

## Question 5 — Avantages intraday réalistes pour un participant lent

### Takeaway
Les effets qui survivent à 1 s de latence et en bougies 1-15 min sont des effets de FLUX lents et documentés : élan de
fin de séance lié à la couverture des vendeurs d'options (plus de 60 contrats à terme, 1974-2020), retournements
autour du fixing des devises de 16h Londres, saisonnalité horaire de la volatilité. Leur taille est petite et
certains s'affaiblissent après publication : ils servent surtout de FILTRES (quand trader, quelle taille) plutôt
que de machines à gains.

### Cited Findings
- Élan intraday du marché (Gao, Han, Li, Zhou, JFE 2018) : le rendement de la 1re demi-heure du S&P 500 prédit celui
  de la dernière demi-heure (1993-2013) ; plus fort les jours volatils, à fort volume, de récession et de nouvelles
  macro ; présent sur 10 autres fonds indiciels très traités — [Alpha Architect](https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/) ; [WUSTL](https://profiles.wustl.edu/en/publications/market-intraday-momentum/)
- Quand la volatilité de la 1re demi-heure est élevée, la 1re + 12e demi-heure prédisent la dernière avec un R² de
  0,048 (4,8 %) — [CXO Advisory](https://cxoadvisory.com/calendar-effects/first-and-last-half-hours-of-trading-linked)
- Mise en garde : une étude hors échantillon trouve que la prévisibilité (version « rendement de la nuit -> dernière
  demi-heure ») DISPARAÎT sur la période récente — [CXO Advisory](https://cxoadvisory.com/?p=25481) ; [Harbourfront Quant](https://harbourfrontquant.substack.com/p/does-intraday-momentum-exist-in-stock)
- International : élan intraday significatif dans 12 marchés développés sur 16 (Li, Sakkas, Urquhart) — [Reading (version acceptée)](https://reading-9.eprints-hosting.org/95566/1/Accepted-Version.pdf)
- Baltussen, Da, Lammers, Martens (JFE 2021) : sur plus de 60 contrats à terme (actions, obligations, matières
  premières, devises), 1974-2020, le rendement des 30 dernières minutes est prédit positivement par le reste de la
  journée ; effet se retourne dans les jours suivants ; lié à la couverture des positions courtes en options (teneurs
  de marché d'options, fonds indiciels à effet de levier) qui doivent acheter quand ça monte et vendre quand ça
  baisse — [IDEAS/RePEc](https://ideas.repec.org/a/eee/jfinec/v142y2021i1p377-403.html) ; [PDF Notre-Dame](https://www3.nd.edu/~zda/intramom.pdf)
- Fixing des devises WM/Reuters 16h Londres (Evans, 21 devises, une décennie) : variations avant et après le fixing
  extraordinairement volatiles et fortement anticorrélées, surtout le DERNIER jour de bourse du mois — [MPRA 81583](https://mpra.ub.uni-muenchen.de/81583)
- Krohn, Mueller, Whelan : retournements prolongés autour des grands fixings — le dollar s'apprécie avant le fixing et
  se déprécie après ; dérives de plusieurs heures de chaque côté ; présent chaque jour de la semaine, chaque mois et
  chacune des 20 années de l'échantillon — [AEA 2020](https://benny.aeaweb.org/conference/2020/preliminary/paper/2dedYfDH)
- Elaut, Frömmel, Lampaert (Journal of Financial Markets 2018) : élan intraday sur le marché des changes (RUB/USD),
  séparant transactions informées et fourniture de liquidité — [Unisg (références)](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)

### Inferences
- Carte des sources d'avantage et verdict pour un particulier MT5 / FTMO (synthèse de toutes les questions) :

| Source d'avantage | Horizon | Taille connue | Infrastructure nécessaire | Verdict MT5/FTMO |
|---|---|---|---|---|
| Vitesse / arbitrage de latence | microsecondes-millisecondes | rapport rendement/risque 4+, gagnant prend tout | colocation, flux directs | NON accessible (et interdit par FTMO) |
| Tenue de marché / capture de l'écart | secondes | ~0,9 €/transaction, millions de transactions | accès direct au marché, ordres passifs, remises | NON (le particulier paie l'écart) |
| Flux d'ordres / déséquilibre du carnet | 3-10 s, quelques dizaines de s | fort mais éphémère | carnet complet, données de transactions | NON (pas de carnet sur MT5 CFD) |
| Décalages entre marchés liés | ms à < 1 min | exploité par les rapides | flux multiples synchronisés | NON à 1 min ; seulement comme contexte |
| Arbitrage de paires intraday | heures-jours | non chiffré sur CFD | données propres, frais bas | PARTIEL (horizons longs seulement) |
| Élan / retournement court terme | 30 min - séance | R² ~1-5 %, affaibli récemment | bougies 1-30 min | PARTIEL (filtre plus que moteur) |
| Flux de couverture d'options (fin de séance) | dernière 1/2 h | significatif sur 60+ contrats | bougies, heure de clôture des contrats | PARTIEL (indices, devises majeures) |
| Fixing 16h Londres / fin de mois | heures autour du fixing | systématique sur 20 ans (taille non extraite) | bougies 1-15 min, calendrier | PARTIEL à ACCESSIBLE (attention frais) |
| Fenêtres d'événements (nouvelles) | minutes | volatilité forte, trous de cotation | calendrier économique | PARTIEL (trading de trous interdit FTMO ; éviter = protection) |
| Taille selon la volatilité, filtres de régime, horaires | toute | réduit les baisses (pas de gain direct) | bougies, calcul simple | ACCESSIBLE — c'est là que se joue la survie FTMO |
| Tendance de fond (jours-mois) | jours-semaines | +0,5 %/mois mesuré dans ce projet (2018-2025) | bougies journalières | ACCESSIBLE (seule source mesurée en interne) |

- Pour un concours FTMO (−5 %/jour, −10 % total) les effets « filtres » (quand ne pas trader, taille selon la
  volatilité, éviter les nouvelles et les fins de séance de faible liquidité) protègent la partie ; les effets « flux
  lents » (fin de séance, fixing) sont les seuls candidats intraday à un petit avantage brut.

### Gaps
- Taille en points de base des effets fixing et fin de séance après frais de CFD non extraite (textes intégraux non lus).
- Aucune étude trouvée sur la saisonnalité horaire appliquée spécifiquement aux CFD de détail.

## Question 6 — Stratégies intraday systématiques accessibles au particulier avec de longs résultats réels

### Takeaway
Les preuves sur les particuliers sont accablantes : à Taïwan moins de 1 % des « day traders » sont durablement
rentables ; au Brésil 97 % de ceux qui persistent plus de 300 jours perdent. Les plateformes de copie (Collective2,
Darwinex) ont peu de stratégies intraday avec de longues histoires vérifiables ; les plus brillantes meurent souvent
(effet de levier, doublement de mise).

### Cited Findings
- Barber, Lee, Liu, Odean (Taïwan, plus de 360 000 day traders) : plus de 80 % perdent ; moins de 1 % sont rentables
  de façon prévisible et répétée ; sur 6 mois typiques, moins de 20 % gagnent après frais — [Berkeley (article)](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf) ; [CXO Advisory](https://www.cxoadvisory.com/individual-investing/do-day-traders-make-money/)
- Chague, De-Losso, Giovannetti (« Day trading for a living? », Brésil, contrats à terme sur indice, débutants
  2013-2015) : 97 % de ceux qui ont persisté plus de 300 jours ont perdu ; 1,1 % gagnent plus que le salaire minimum,
  0,5 % plus qu'un salaire de guichetier de banque — [FGV](https://repositorio.fgv.br/items/e87d04fc-4b4c-4a56-ab5a-1c84c1afde1b/full) ; [Quantpedia](https://vvv.quantpedia.com/?p=4771)
- Collective2 (témoignages de forum, pas de statistique officielle) : la plupart des stratégies « perdent un peu, puis
  encore un peu » et ne sont plus mises à jour ; les étoiles filantes partagent levier élevé ou doublement de mise ;
  peu de longues histoires — [Elite Trader](https://elitetrader.com/et/threads/c2-strategies-comments.306417/post-4462187)
- Darwinex : un indice maison (« INDX ») annoncé à +260 % depuis 2020 avec −12,3 % de baisse max ; baisse max médiane
  des DARWIN primés −5,5 % (fourchette −0,96 % à −23,8 %) — [Traders Union (source tierce, non vérifiée)](https://tradersunion.com/news/brokers-news/show/1250805-darwinia-results-highlight-global/) ; Darwinex récompense désormais la DURÉE de l'historique — [TheGodFunded](https://thegodfunded.com/en/news/changes-in-the-darwinia-silver-rating-bonus-for-duration-of-the-track-record)

### Inferences
- Le modèle Darwinex/FTMO (sélection des rares survivants parmi des milliers) ressemble à de la sélection a posteriori :
  un bon résultat isolé ne prouve pas un avantage ; seule une longue histoire hors échantillon compte — exactement la
  discipline des « 12 mois cachés » du projet.
- Ordre de grandeur réaliste pour un système intraday de particulier qui survit : quelques % par an au-dessus des
  frais, avec des baisses de 5-20 %, loin des 8 %/mois visés ; les firmes qui font beaucoup mieux le font par la
  vitesse et l'écart, inaccessibles.

### Gaps
- Pas de statistiques officielles de survie/rendement des stratégies INTRADAY sur Collective2 ou Darwinex (données
  publiques par stratégie, mais aucune étude agrégée trouvée).
- Le chiffre « INDX +260 % » vient d'un site tiers ; à vérifier sur darwinex.com avant usage.

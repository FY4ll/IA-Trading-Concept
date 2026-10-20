# Tendances, momentum et finance comportementale (sous- et sur-réaction) sur les marchés liquides de type CFD

Notes de recherche (14/10/2026). Périmètre : devises (grandes paires et croisées), or et argent, indices actions,
pétrole, bitcoin/cryptos ; horizons de 15 minutes à quelques semaines (positions fermées avant le week-end).
Convention : « [ÉVALUÉ PAR LES PAIRS] » = article publié dans une revue à comité de lecture ; « [DOCUMENT DE
TRAVAIL] » = version non publiée ou pré-publication ; « [INDUSTRIE] » = données/opinions de sociétés de gestion ou
de banques (non évaluées par les pairs) ; « [OPINION] » = avis. Les chiffres extraits directement du PDF de l'article
sont signalés « (lu dans le PDF) ».

---

## Q1. Momentum de série temporelle (« suivre la tendance ») : preuves d'origine, horizons, coûts, performance depuis 2012, horizons courts et intrajournaliers

### Takeaway
Le suivi de tendance « classique » (signe du rendement des 1 à 12 derniers mois, positions dimensionnées par la
volatilité, réajustement mensuel, des dizaines de marchés en même temps) est l'une des régularités les mieux
documentées de la finance (1880-2016), mais : (a) l'effet est faible marché par marché (ratio de Sharpe moyen ≈ 0,4
par marché) et ne devient fort (≈ 0,8-1,1) que grâce à la diversification sur ~60 marchés ; (b) depuis 2009-2010 les
fonds de tendance réels ont nettement moins gagné (≈ +1,6 %/an en moyenne 2010-2018 contre +9,2 %/an 2000-2009) ;
(c) l'effet documenté vit surtout à des horizons de 1 à 12 mois, alors que le seul effet « tendance » bien documenté à
l'échelle de la journée est le momentum intrajournalier (première partie de séance → dernière demi-heure), au pouvoir
prédictif minuscule (R² ≈ 1-2 %).

### Cited Findings
**Moskowitz, Ooi & Pedersen (2012), « Time Series Momentum », Journal of Financial Economics 104, 228-250 [ÉVALUÉ PAR LES PAIRS]**
- 58 contrats à terme liquides (indices actions, devises, matières premières, obligations) ; données dès janvier 1965,
  résultats principaux sur janvier 1985 – décembre 2009 (lu dans le PDF) — [MOP 2012, PDF](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Régressions empilées par décalage mensuel : les 12 décalages les plus récents ont tous un coefficient positif (9 sur 12
  significatifs) ; au-delà, majorité de coefficients négatifs = « continuation la première année, puis retournements
  plus faibles sur les 4 années suivantes », même schéma dans chaque classe d'actifs (lu dans le PDF) — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Stratégie de référence : signe du rendement sur 12 mois, conservation 1 mois, chaque position dimensionnée à 40 %
  de volatilité annuelle anticipée ; portefeuille équipondéré ≈ 12 %/an de volatilité. Les 58 contrats ont un rendement
  de tendance positif, 52 significatifs au seuil de 5 % (lu dans le PDF) — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Portefeuille diversifié : ratio de Sharpe « supérieur à 1 » par an, ≈ 2,5 fois celui du marché actions ; alpha
  ≈ 1,58 %/mois par rapport aux facteurs actions classiques, encore 1,09 %/mois (t = 5,40) après le facteur momentum
  transversal « partout » d'Asness-Moskowitz-Pedersen. Sur 1966-1985 (hors échantillon) Sharpe ≈ 1,1. Chiffres
  **bruts** (avant coûts de transaction) : le Sharpe par instrument de la figure 2 est explicitement « gross » (lu dans le PDF) — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Robustesse : effet significatif « particulièrement quand les périodes d'observation et de conservation sont de 12 mois
  ou moins » (lu dans le PDF) — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Comportement en crise (« sourire ») : meilleurs gains lors des plus forts mouvements des actions (haut ou bas) ; gros
  gains octobre-décembre 2008, mais pertes au 3e trimestre 2008 et fortes pertes mars-mai 2009 : « la fin d'une crise
  constitue un brusque retournement de tendance qui génère des pertes » (lu dans le PDF) — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Positions des spéculateurs (données CFTC 1986-2009) : les spéculateurs accumulent des positions dans le sens de la
  tendance jusqu'à la date de formation puis réduisent ; les auteurs concluent que les spéculateurs profitent des
  tendances au détriment des « hedgers » (couvreurs) (lu dans le PDF) — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)

**Hurst, Ooi & Pedersen (2017), « A Century of Evidence on Trend-Following Investing », Journal of Portfolio Management (automne 2017) [ÉVALUÉ PAR LES PAIRS, revue de praticiens ; auteurs d'AQR]**
- 67 marchés (29 matières premières, 11 indices actions, 15 obligations, 12 paires de devises), janvier 1880 – décembre
  2016 ; combinaison équipondérée de signaux 1 mois, 3 mois et 12 mois, réajustement mensuel, cible de volatilité 10 %/an (lu dans le PDF) — [Hurst et al. 2017, PDF](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)
- Coûts : estimations propriétaires 2012 par classe d'actifs (impact de marché + commissions), supposées 2 fois plus
  élevées en 1993-2002 et 6 fois plus élevées en 1880-1992 ; coûts de « roulement » des contrats NON inclus ;
  frais simulés 2 % de gestion + 20 % de performance (lu dans le PDF) — [Hurst et al. 2017](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)
- Chiffres de la version de travail 2013 (1880-2013, après coûts simulés) : 14,9 %/an avant frais de gestion, 11,2 %/an
  après frais 2/20, volatilité 9,7 %, Sharpe après frais 0,77, corrélation 0,00 aux actions US et -0,04 aux obligations ;
  positif dans chaque décennie ; décennie 2000-2013 : 11,3 % avant frais, 7,9 % après, Sharpe 0,62 ; meilleure
  décennie 1970-79 (Sharpe 1,70), plus faible 1910-19 (Sharpe 0,13) (lu dans le PDF) — [Hurst et al., version 2013](https://www.trendfollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf).
  Note : la version publiée 2017 (1880-2016) contient un tableau équivalent que je n'ai pas pu extraire du PDF.
- Sharpe moyen marché par marché ≈ 0,4 (brut de frais et de coûts) ; chaque signal (1, 3, 12 mois) est positif dans
  chaque décennie ; avec un mois de retard d'exécution, la performance « se détériore, surtout pour les signaux courts » (lu dans le PDF) — [Hurst et al. 2017](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)
- Positif dans 8 des 10 pires baisses d'un portefeuille 60/40 depuis 1880 (durée moyenne de ces baisses ≈ 15 mois) ;
  mauvaise performance attendue lors des krachs très rapides (exemple : 1987) ; pertes allant jusqu'à 25 % lors de ses
  propres pires baisses ; moins bon quand les corrélations entre marchés sont élevées (fin 2008 – mi-2014, « risk-on /
  risk-off ») (lu dans le PDF) — [Hurst et al. 2017](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)

**Critique statistique : Huang, Li, Wang & Zhou (2020), « Time Series Momentum: Is It There? », Journal of Financial Economics 135(3), 774-794 [ÉVALUÉ PAR LES PAIRS]**
- Régressions actif par actif : « peu de preuves » de momentum de série temporelle, en échantillon comme hors
  échantillon ; le t de la régression empilée de MOP paraît grand mais reste sous les valeurs critiques obtenues par
  rééchantillonnage (bootstrap) — [résumé SUFE](https://academicnewsletter.sufe.edu.cn/info/355816) ; [discussion](https://buttondown.com/mdickens/archive/contra-time-series-momentum-is-it-there/)
- Une autre critique (Kim, Tse & Wald) attribue une grande partie des gains au dimensionnement par la volatilité plutôt
  qu'au signal de tendance (mentionnée, détails non vérifiés dans cette session) — [Quantpedia](https://quantpedia.com/deconstructing-the-time-series-momentum-strategy/)

**Performance réelle des fonds de tendance depuis la publication [INDUSTRIE]**
- Indice SG Trend, moyenne annuelle : 2000-2009 = +9,2 %/an au total (dont ≈ 2,9 % de rémunération du cash, soit
  ≈ +6,3 % au-delà du cash) ; 2010-2018 = +1,6 %/an (≈ 0,4 % cash, ≈ +1,2 % au-delà) (lu dans le PDF) — [AQR, « You Can't Always Trend When You Want », 2019](https://www.belmontinvestments.com/cimg/file/articles/53/pdf/190425aqrtrendfollowing.pdf)
- Explication d'AQR [OPINION d'un gérant intéressé] : la faiblesse 2010-2018 viendrait de « moins de grands mouvements »
  sur les marchés, pas d'une perte de capacité à transformer les tendances en gains — [AQR 2019](https://www.belmontinvestments.com/cimg/file/articles/53/pdf/190425aqrtrendfollowing.pdf)
- 2009-2013 : SG Trend ≈ -1,8 % ; 2014 : +19,7 % ; 2011 et 2018 = années perdantes pour la majorité des membres
  (marchés « en dents de scie ») — résumé d'un moteur de recherche dont la page d'origine n'a pas été identifiée avec
  certitude (candidats : [Man Group](https://www.man.com/insights/is-this-time-different), [Man Group 2](https://www.man.com/insights/deep-dive-trend-following)) : À VÉRIFIER avant usage ; 2014 +19,7 % et 2022 +27,35 % (meilleure année depuis le lancement en 2000) — [The Full FX](https://thefullfx.com/?p=3378)
- 2023 : ≈ -3 % — [Top Traders Unplugged](https://www.toptradersunplugged.com/trend-following-performance-report-january-2025-2/) (chiffre exact 2024 non trouvé)
- 2025 : -4,9 % en avril, -9,3 % depuis le début de l'année à fin avril, alors que l'indice des négociateurs court terme
  (SG Short-Term Traders) n'était qu'à -0,9 % (lu dans le PDF) — [SG, « CTA Industry Update », mai 2025](https://content.sgmarkets.com/CTA_UPDATE_KEEPING_UP_WITH_THE_TRENDFOLLOWERS_2025) ;
  année 2025 terminée à ≈ +2,4 % (décembre +1,92 %) — [Top Traders Unplugged](https://www.toptradersunplugged.com/?p=20381)
- SG : depuis 2007 l'indice se comporte comme des modèles plus LENTS (moyennes mobiles 20 jours / 60 à 300 jours) ;
  depuis 2008 les modèles longs ont en moyenne mieux rendu que les rapides ; les rapides ont gagné en 2020 (Covid) ;
  dispersion entre fonds ≈ 15 points par an malgré une corrélation moyenne de 0,78 ; encours ≈ 340 milliards $ (lu dans le PDF) — [SG mai 2025](https://content.sgmarkets.com/CTA_UPDATE_KEEPING_UP_WITH_THE_TRENDFOLLOWERS_2025)

**Devises spécifiquement**
- Neely, Weller & Ulrich (2009), JFQA 44(2), 467-488 [ÉVALUÉ PAR LES PAIRS] : les règles techniques (filtres, moyennes
  mobiles) étaient réellement rentables dans les années 1970-1980 sur les devises, mais ces opportunités avaient
  **disparu au début des années 1990** ; les règles moins étudiées ont décliné aussi — [IDEAS](https://ideas.repec.org/a/cup/jfinqa/v44y2009i02p467-488_09.html)
- Menkhoff, Sarno, Schmeling & Schrimpf (2012), « Currency Momentum Strategies », JFE 106(3), 660-684 [ÉVALUÉ PAR LES
  PAIRS] : écart jusqu'à 10 %/an entre devises gagnantes et perdantes (momentum TRANSVERSAL, pas de série temporelle),
  partiellement expliqué par les coûts (environ un tiers des gains selon un résumé secondaire), fortes « limites à
  l'arbitrage » — [résumé SUFE](https://academicnewsletter.sufe.edu.cn/info/356851) ; [City Univ.](https://openaccess.city.ac.uk/3296)

**Horizons courts et intrajournaliers [ÉVALUÉ PAR LES PAIRS]**
- Gao, Han, Li & Zhou (2018), « Market Intraday Momentum », JFE : FNB S&P 500 (SPY) 1993-2013 ; le rendement de la
  première demi-heure (mesuré depuis la clôture de la veille) prédit celui de la dernière demi-heure ; plus fort les jours
  volatils, à fort volume, en récession et les jours de grandes annonces macro ; présent dans 10 autres FNB — [WUSTL](https://profiles.wustl.edu/en/publications/market-intraday-momentum/)
- Chiffres de la version de travail (déc. 2015) : R² = 1,6 % (première demi-heure seule), 2,6 % avec l'avant-dernière
  demi-heure ; R² hors échantillon 1,2 % (1,8 % combiné) ; stratégie « signe de la première demi-heure » : 6,67 %/an,
  écart-type 6,19 %, Sharpe 1,08 (contre 0,29 pour l'achat-conservation) ; « reste significatif après coûts » selon les
  auteurs, coûts devenus plus faibles après la décimalisation de 2001 (lu dans le PDF ; les chiffres publiés peuvent
  différer légèrement) — [Gao et al., version de travail](https://c.mql5.com/forextsd/forum/173/intraday_momentum_-_the_first_half-hour_return_predicts_the_last_half-hour_return.pdf)
- Baltussen, Da, Lammers & Martens (2021), « Hedging Demand and Market Intraday Momentum », JFE 142, 377-403 : plus de
  60 contrats à terme (actions, obligations, matières premières, devises), décembre 1974 – mai 2020 ; le rendement du
  reste de la journée (clôture précédente → 30 min avant clôture) prédit les 30 dernières minutes ; **l'effet se
  retourne les jours suivants** ; Sharpe annualisé de 0,87 à 1,73 par classe d'actifs ; plus faible pour matières
  premières et devises (prédiction hors échantillon positive et significative pour seulement ~40-50 % des contrats) ;
  cause proposée : couverture « gamma » des teneurs de marché d'options et rééquilibrage des FNB à levier (lu dans le PDF) — [Baltussen et al. 2021, PDF](https://www3.nd.edu/~zda/intramom.pdf)
- Elaut, Frömmel & Lampaert (2018), Journal of Financial Markets 37, 35-51 : momentum intrajournalier sur RUB/USD
  (première demi-heure → dernière demi-heure), surtout pendant la crise — [IDEAS](https://ideas.repec.org:443/a/eee/finmar/v37y2018icp35-51.html)
- Li, Sakkas & Urquhart (« Intraday Time Series Momentum: Global Evidence and Links to Market Characteristics ») : 16
  marchés développés, effet significatif en et hors échantillon dans la plupart des pays, plus fort quand la liquidité est
  faible et la volatilité forte — [SSRN auteur](https://papers.ssrn.com/author=3577769)
- Cryptos : Liu & Tsyvinski (2021), « Risks and Returns of Cryptocurrency », Review of Financial Studies 34(6),
  2689-2727 : fort momentum de série temporelle (une hausse du bitcoin sur une semaine tend à se prolonger la semaine
  suivante) ; mesures d'attention des investisseurs prédictives — [IDEAS](https://ideas.repec.org/a/oup/rfinst/v34y2021i6p2689-2727..html) ; [Cointelegraph](https://cointelegraph.com/news/yale-research-proposes-factors-for-crypto-price-prediction)

### Inferences
- Pour une IA qui ne garde pas de positions le week-end et vise 15 min à quelques semaines, l'essentiel de la preuve
  académique (1-12 mois, réajustement mensuel) **n'est pas directement exploitable** : la tendance de fond peut servir de
  « contexte » (direction privilégiée), pas de moteur de gains rapides. Cela rejoint la leçon interne du projet (seule
  source d'avantage mesurée = tendance de fond).
- Ordre de grandeur réaliste : Sharpe ≈ 0,4 par marché isolé. À 10 %/an de volatilité, cela donne ≈ +4 %/an, soit
  ≈ +0,3 %/mois sur UN marché ; il faut diversifier sur des dizaines de marchés peu corrélés pour approcher un Sharpe de
  0,8-1 — ce qui colle avec le repère interne du projet (+0,4 à +0,5 %/mois sur 36 marchés avec frais).
- Le passage de +9,2 %/an (2000-2009) à +1,6 %/an (2010-2018) chez de vrais professionnels montre qu'un effet très bien
  documenté peut rester faible pendant 10 ans : un examen court (quelques mois) ne peut pas distinguer un vrai talent de
  tendance d'un mauvais régime.
- Le momentum intrajournalier est un effet de fin de séance lié à des marchés à horaires (actions, obligations) ; sur
  des marchés 24 h (devises au comptant, cryptos, or) la « dernière demi-heure » n'a pas le même sens. Effet plus faible
  sur devises et matières premières, et il se retourne ensuite : rien de cela n'est une tendance « qu'on suit ».
- Les Sharpe intrajournaliers (≈ 1) sont calculés avec des coûts de contrats à terme ou de FNB très liquides ; un écart
  CFD typique (or ≈ 0,25 $) mangerait une part importante d'un gain moyen de quelques points de base par jour.

### Gaps
- Tableau des rendements annuels exacts de l'indice SG Trend 2012-2024 (années 2012, 2013, 2015-2021, 2024) non
  trouvé en source primaire lisible (SG publie un rapport mensuel réservé aux clients).
- Tableau chiffré de la version publiée 2017 de Hurst et al. (1880-2016) : non extrait (le PDF n'en donnait pas le texte) ;
  seuls les chiffres de la version 2013 sont vérifiés.
- Pas de source trouvée mesurant si le momentum intrajournalier de Gao et al. a faibli APRÈS 2013 (publication).
- Pas d'étude évaluée par les pairs trouvée sur le momentum de série temporelle à 1-4 semaines spécifiquement sur l'or,
  l'argent ou le pétrole en CFD, après écarts réels.

---

## Q2. Krachs du momentum et momentum géré par la volatilité

### Takeaway
Le momentum (surtout transversal, sur actions) subit des krachs rares mais énormes, typiquement au REBOND qui suit une
forte baisse quand la volatilité est au plus haut ; réduire l'exposition quand la volatilité récente du momentum monte
élimine en grande partie ces krachs et double à peu près le ratio de Sharpe dans les études publiées. Pour le suivi de
tendance multi-actifs, l'équivalent est la perte au moment des retournements de fin de crise (mars-mai 2009).

### Cited Findings
- Daniel & Moskowitz (2016), « Momentum Crashes », JFE (décembre 2016), données 1927-2013 [ÉVALUÉ PAR LES PAIRS] : les
  krachs surviennent dans les états de « panique », après des baisses de marché et quand la volatilité culmine, au moment
  où le marché rebondit ; une stratégie dynamique qui prévoit moyenne et variance du momentum « double environ l'alpha et
  le ratio de Sharpe » ; résultat valable sur plusieurs périodes, marchés internationaux et autres classes d'actifs — [NBER w20439](https://www.nber.org/papers/w20439)
- Ordres de grandeur : juin-août 1932, le portefeuille momentum perd ≈ 91 % ; 2009, plus de 73 % en trois mois ; les
  krachs viennent surtout de la forte hausse des anciens perdants (bêta > 3 après les baisses) — [Alpha Architect](https://alphaarchitect.com/avoiding-momentum-crashes/)
- Barroso & Santa-Clara (2015), « Momentum Has Its Moments », JFE (avril 2015) [ÉVALUÉ PAR LES PAIRS] : le risque du
  momentum varie fortement et se prévoit ; le gérer « élimine pratiquement les krachs et double presque le ratio de
  Sharpe » — [ETF.com](https://www.etf.com/node/94292.md) ; [UCP](https://ciencia.ucp.pt/en/publications/momentum-has-its-moments/)
- Suivi de tendance multi-actifs : pertes au 3e trimestre 2008 et fortes pertes mars-mai 2009 (fin de crise = retournement
  brusque) ; mauvais lors des krachs très rapides type 1987 — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf) ; [Hurst et al. 2017](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)
- 2025 : les suiveurs de tendance (SG Trend) perdent -9,3 % de janvier à avril 2025 lors de retournements soudains avec
  hausse de volatilité, quand les stratégies court terme résistent (-0,9 %) [INDUSTRIE] — [SG mai 2025](https://content.sgmarkets.com/CTA_UPDATE_KEEPING_UP_WITH_THE_TRENDFOLLOWERS_2025)

### Inferences
- Pour l'IA (compte FTMO, mur à -5 %/jour et -10 % au total), le danger principal d'un comportement « tendance » n'est
  pas la moyenne mais la queue : un retournement brutal après une phase de panique. Une taille de position qui baisse
  quand la volatilité monte est l'outil le mieux documenté contre ce risque (et elle est compatible avec « l'IA choisit
  sa taille » : c'est quelque chose qu'elle peut découvrir si la récompense punit les queues de pertes).
- Les chiffres de krach (-73 %, -91 %) concernent un portefeuille long-court d'actions individuelles, pas un suivi de
  tendance sur contrats à terme : ne pas les transposer tels quels aux CFD.

### Gaps
- Chiffres exacts de Barroso & Santa-Clara (Sharpe avant/après, aplatissement) non vérifiés (page SSRN bloquée).
- Pas de mesure trouvée des « krachs » du momentum de série temporelle à horizon de jours/semaines sur devises, or ou
  cryptos.

---

## Q3. Explications comportementales : sur-réaction, sous-réaction, théorie des perspectives

### Takeaway
Les théories comportementales classiques prédisent toutes la même forme : sous-réaction à court/moyen terme (d'où la
tendance) puis sur-réaction à plus long terme (d'où un retour partiel), ce qui est exactement le profil mesuré par MOP
sur les contrats à terme (continuation ≈ 12 mois puis retournement partiel). Ce sont des modèles théoriques ; les tests
directs portent surtout sur les actions individuelles.

### Cited Findings
- De Bondt & Thaler (1985), « Does the Stock Market Overreact? », Journal of Finance 40(3) [ÉVALUÉ PAR LES PAIRS] :
  portefeuilles des 35 plus grands perdants et 35 plus grands gagnants de la Bourse de New York sur 3 ans ; les perdants
  battent les gagnants d'environ 24,6 % sur les 36 mois suivants (perdants : +19,6 % au-dessus du marché) — [Alpha Architect](https://alphaarchitect.com/quantitative-momentum-research-long-term-return-reversal/)
- Barberis, Shleifer & Vishny (1998), « A Model of Investor Sentiment », JFE 49(3), 307-343 : modèle où le
  conservatisme (mise à jour trop lente) produit la sous-réaction aux nouvelles et l'heuristique de représentativité
  (voir un « motif » dans une série de bonnes nouvelles) produit la sur-réaction — [NBER w5926](https://www.nber.org/papers/w5926)
- Daniel, Hirshleifer & Subrahmanyam (1998), Journal of Finance 53(6) : excès de confiance dans l'information privée +
  attribution biaisée (succès = mon talent, échec = malchance) → autocorrélations positives à court terme (momentum) et
  négatives à long terme, excès de volatilité — [Univ. du Michigan](https://deepblue.lib.umich.edu/handle/2027.42/35542?show=full)
- Hong & Stein (1999), « A Unified Theory of Underreaction, Momentum Trading and Overreaction », Journal of Finance
  54(6) : « observateurs de nouvelles » qui reçoivent l'information progressivement → sous-réaction ; « négociateurs de
  momentum » qui la suivent avec des règles simples → sur-réaction à long terme — [Stein, Harvard](https://stein.scholars.harvard.edu/publications/unified-theory-underreaction-momentum-trading-and-overreaction-asset-markets) ; [NBER w6324](https://ideas.repec.org/p/nbr/nberwo/6324.html)
- Test sur contrats à terme : après une tendance positive (ou négative) sur 12 mois, les prix continuent environ un an
  puis se retournent PARTIELLEMENT ; les auteurs y voient à la fois sous-réaction initiale et sur-réaction retardée,
  compatibles avec DHS (1998) et BSV (1998) (lu dans le PDF) — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Autres sources de tendance avancées par AQR [OPINION] : ancrage, comportement grégaire, intervenants sans but de
  profit (banques centrales qui lissent les devises, couvertures d'entreprises) — [Hurst et al. 2017](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)
- Prix Nobel d'économie 2002 : Daniel Kahneman (moitié du prix, avec Vernon Smith) « pour avoir intégré des apports de
  la recherche psychologique dans la science économique, en particulier sur le jugement humain et la décision en
  incertitude » ; ses travaux ont donné la théorie des perspectives (Kahneman & Tversky, Econometrica, 1979) — [nobelprize.org](https://www.nobelprize.org/prizes/economic-sciences/2002/kahneman/)

### Inferences
- Ces théories donnent un « pourquoi » plausible aux tendances, mais aucune ne dit à quel horizon précis (15 min ? 3
  jours ?) l'effet existe sur un marché donné : cet horizon doit être mesuré, pas supposé.
- Le profil « continuation puis retour partiel » implique qu'une IA qui apprend sur les prix bruts devrait découvrir à
  la fois de suivre ET de se méfier des mouvements déjà très étendus ; ce n'est pas contradictoire.

### Gaps
- Je n'ai pas trouvé de test direct de ces théories à l'échelle intrajournalière sur devises/or/indices.
- Le texte officiel exact de la page « summary » du Nobel 2002 n'a pas pu être lu (erreur d'accès) ; citation reprise
  de la page Kahneman du même site.

---

## Q4. Négociateurs à rétroaction positive (De Long, Shleifer, Summers & Waldmann 1990)

### Takeaway
Modèle théorique : si une partie des investisseurs achète parce que le prix a monté, des spéculateurs rationnels ont
intérêt à acheter AVANT eux (« monter dans le train tôt ») plutôt qu'à corriger le prix, ce qui amplifie les écarts au
juste prix. Les preuves empiriques directes sur les marchés de contrats à terme vont plutôt dans un sens nuancé.

### Cited Findings
- De Long, Shleifer, Summers & Waldmann (1990), « Positive Feedback Investment Strategies and Destabilizing Rational
  Speculation », Journal of Finance 45(2), 379-395 [ÉVALUÉ PAR LES PAIRS] : quand les investisseurs « bruit » suivent
  des stratégies à rétroaction positive (acheter quand le prix monte, vendre quand il baisse), il peut être rentable pour
  les spéculateurs rationnels d'acheter avant la demande de ces investisseurs ; davantage de spéculateurs rationnels peut
  alors AUGMENTER la volatilité autour de la valeur fondamentale — [IDEAS](https://ideas.repec.org/a/bla/jfinan/v45y1990i2p379-95.html)
- MOP (2012) citent la rétroaction positive (De Long et al. 1990 ; Hong & Stein 1999) comme cause possible de
  sur-réaction ; mais dans les données CFTC, les spéculateurs « ne continuent pas à s'empiler dans la tendance avec
  retard » ; si sur-réaction il y a, elle viendrait plutôt des couvreurs (lu dans le PDF) — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Mécanisme mécanique proche, mesuré : la couverture « gamma » des teneurs de marché d'options et le rééquilibrage des
  FNB à levier obligent à acheter dans la hausse / vendre dans la baisse en fin de séance (rééquilibrage des FNB à levier
  ≈ 16,8 % du volume de clôture un jour à 1 % de variation, 50,2 % un jour à 5 %, février 2009) (lu dans le PDF) — [Baltussen et al. 2021](https://www3.nd.edu/~zda/intramom.pdf)
- Attention des particuliers : épisodes d'achats massifs par les utilisateurs de Robinhood suivis de rendements anormaux
  moyens de -3 % sur 5 jours (-6 % pour les épisodes extrêmes), ≈ -5 % sur le mois suivant — Barber, Huang, Odean &
  Schwarz (2022), Journal of Finance — [résumé de recherche web ; WUSTL](https://profiles.wustl.edu/en/publications/attention-induced-trading-and-returns-evidence-from-robinhood-use/)

### Inferences
- Pour l'IA : la rétroaction positive crée des mouvements qui se prolongent PUIS se retournent ; « arriver tôt » est la
  seule façon d'en profiter, et arriver tard (après la foule) est exactement le profil perdant des particuliers.
- Les flux mécaniques (options, FNB à levier) concernent surtout les indices actions US en fin de séance : pertinent
  pour les CFD sur indices (US500, US30), beaucoup moins pour les devises.

### Gaps
- Pas de mesure trouvée de la part des négociateurs à rétroaction positive sur les CFD devises/or/cryptos.

---

## Q5. Effet de disposition (vendre les gagnants trop tôt, garder les perdants trop longtemps) et lien avec le momentum

### Takeaway
L'effet de disposition est l'un des biais les mieux mesurés chez les particuliers ; théoriquement et empiriquement (sur
actions), il freine l'intégration des nouvelles dans les prix (sous-réaction), ce qui est une explication du momentum.
Les réseaux sociaux l'aggravent (mesuré sur des négociateurs de devises).

### Cited Findings
- Shefrin & Statman (1985), « The Disposition to Sell Winners Too Early and Ride Losers Too Long: Theory and Evidence »,
  Journal of Finance 40(3), 777-790 : nomment l'effet ; composantes : aversion aux pertes, comptabilité mentale par
  rapport au prix d'achat, évitement du regret, maîtrise de soi — [Wikipédia (synthèse)](https://en.wikipedia.org/wiki/Disposition_effect) ; [Alpha Architect](https://alphaarchitect.com/2014/06/behavioral-bias-bingo-disposition-effect/)
- Odean (1998), « Are Investors Reluctant to Realize Their Losses? », Journal of Finance : 10 000 comptes d'un courtier à
  prix réduit, 1987-1993 ; proportion de gains réalisés 0,148 contre proportion de pertes réalisées 0,098 — [synthèse secondaire, EarnForex](https://www.earnforex.com/guides/disposition-to-keep-losses-and-cut-winners)
  (chiffres classiques, source secondaire non académique).
- Grinblatt & Han (2005), « Prospect Theory, Mental Accounting, and Momentum », JFE 78(2), 311-339 : une mesure des
  plus-values latentes agrégées (« surplomb de plus-values ») semble être la variable clé du momentum ; une fois
  contrôlée, les rendements passés ne prédisent plus les rendements futurs (actions US) — [IDEAS](https://ideas.repec.org/a/eee/jfinec/v78y2005i2p311-339.html)
- Frazzini (2006), « The Disposition Effect and Underreaction to News », Journal of Finance 61(4), 2017-2046 : la dérive
  après annonce est la plus forte quand plus-values latentes et nouvelle ont le même signe ; une stratégie fondée sur cet
  effet donne des alphas mensuels de plus de 200 points de base (actions, fonds communs) — [IDEAS](https://ideas.repec.org/a/bla/jfinan/v61y2006i4p2017-2046.html) ; [AQR](https://www.aqr.com/Insights/Research/Journal-Article/The-Disposition-Effect-and-the-UnderReaction-to-News)
- Heimer (2016), « Peer Pressure: Social Interaction and the Disposition Effect », Review of Financial Studies :
  négociateurs particuliers (plateforme de « trading social » liée à des courtiers de devises) ; l'accès au réseau social
  **double presque** l'effet de disposition ; les négociateurs connectés développent des niveaux corrélés de ce biais — [Cleveland Fed WP 16-18](https://www.clevelandfed.org/publications/working-paper/2016/wp-1618-peer-pressure-social-interaction-and-the-disposition-effect)

### Inferences
- Pour l'IA : une récompense qui juge chaque coup sur son résultat final (pas sur « avoir encaissé un petit gain ») est
  ce qui évite d'apprendre le biais humain. L'idée de départ de COLLAPSAR (« une perte n'est pas forcément mauvaise »)
  est cohérente avec cette littérature : couper vite les perdants et laisser courir les gagnants est l'inverse du biais.
- Le lien disposition → momentum est prouvé sur actions individuelles (prix d'achat de référence connu) ; sur devises et
  matières premières, la notion de « prix d'achat moyen de la foule » est plus floue : effet non démontré là.

### Gaps
- Pas de preuve trouvée que l'effet de disposition génère du momentum mesurable sur devises, or, indices ou cryptos.
- Article original d'Odean (1998) non lu directement (chiffres via source secondaire).

---

## Q6. Retour à court terme (jours à semaines) contre momentum à moyen terme sur contrats à terme et devises

### Takeaway
La preuve est plus mince et plus fragile qu'à 1-12 mois : retournements hebdomadaires documentés sur contrats à terme
(dont devises) surtout dans des sous-groupes (fort volume), qui disparaissent avec des coûts modestes ; momentum
intrajournalier qui se retourne les jours suivants ; momentum hebdomadaire documenté sur cryptos. Il n'y a pas de règle
universelle « court terme = retour, moyen terme = tendance » valable pour tous les marchés.

### Cited Findings
- Wang & Yu (2004, « Trading Activity and Price Reversals in Futures Markets », Journal of Banking & Finance selon
  Quantpedia ; année/revue non vérifiées ici) : 24 contrats à terme US (4 devises, 5 financiers, 8 agricoles, 7 matières
  premières), 1983-2000 ; acheter les plus fortes baisses de la semaine (et vendre les plus fortes hausses) parmi les
  contrats à fort volume et faible intérêt ouvert : ≈ 29,6 %/an, volatilité 31,4 %, Sharpe 0,82 ; reste rentable avec
  0,10 % de coût par transaction mais **≈ 0,16 % efface les gains** — [Quantpedia](https://quantpedia.com/strategies/short-term-reversal-with-futures)
- Retournement après le momentum intrajournalier : le pouvoir prédictif sur la dernière demi-heure « se retourne les
  jours suivants » (60+ contrats, 1974-2020) (lu dans le PDF) — [Baltussen et al. 2021](https://www3.nd.edu/~zda/intramom.pdf)
- 1-12 mois puis retournement partiel la 2e année (contrats à terme, 1985-2009) — [MOP 2012](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Signaux 1 mois (le plus court testé par Hurst et al.) : positifs dans chaque décennie depuis 1880 mais les plus
  sensibles au retard d'exécution (lu dans le PDF) — [Hurst et al. 2017](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)
- Cryptos : momentum hebdomadaire (continuation semaine → semaine) — [Liu & Tsyvinski 2021, IDEAS](https://ideas.repec.org/a/oup/rfinst/v34y2021i6p2689-2727..html)
- Une source secondaire signale qu'en matières premières on observe plutôt un momentum à court terme qu'un retournement,
  contrairement aux actions (étude KAIST, non lue : lien inaccessible) — [résumé de recherche web](https://dspace.kaist.ac.kr/handle/10203/276677)

### Inferences
- À l'horizon visé (heures à semaines), les deux forces (continuation et retour) coexistent et dépendent du marché, du
  volume et du régime ; une IA qui choisit librement ses coups doit pouvoir apprendre les deux, et le juge doit compter
  les coûts réels : la fenêtre « 0,10 % rentable / 0,16 % perdant » montre qu'un écart CFD peut faire basculer un effet
  hebdomadaire de positif à nul.

### Gaps
- Pas d'étude évaluée par les pairs trouvée, lue en source primaire, sur le retour à 1 jour – 1 mois sur les grandes
  paires de devises au comptant, l'or ou le pétrole, après coûts récents (après 2010).
- Article KAIST et article Wang & Yu non lus en source primaire.

---

## Q7. Comportement des particuliers : excès de transactions, levier, part des perdants

### Takeaway
Les preuves sont massives et concordantes : la grande majorité des particuliers actifs perd de l'argent, d'autant plus
qu'ils négocient souvent ; moins de 1 % des négociateurs à la journée gagnent de façon durable ; 74-89 % des comptes CFD
de particuliers perdent dans l'UE ; le levier élevé aggrave les pertes.

### Cited Findings
- Barber & Odean (2000), « Trading Is Hazardous to Your Wealth », Journal of Finance 55(2), 773-806 : 66 465 ménages,
  courtier à prix réduit, 1991-1996 ; les plus actifs gagnent 11,4 %/an contre 17,9 % pour le marché ; ménage moyen
  16,4 %/an, rotation de 75 % du portefeuille par an ; explication : excès de confiance — [IDEAS](https://ideas.repec.org/a/bla/jfinan/v55y2000i2p773-806.html) ; [Berkeley](https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/Individual_Investor_Performance_Final.pdf)
- Barber, Lee, Liu & Odean (Taïwan, 1992-2006, toutes les transactions de la Bourse) : ≈ 360 000 particuliers font du
  « day trading » chaque année en moyenne ; ≈ 13 % sont bénéficiaires après frais dans une année typique, mais **moins de
  1 % (≈ 1 000) surperforment de façon prévisible** ; les 500 meilleurs de l'année précédente gagnent 49,5 points de base
  par jour avant frais et 28,1 après ; les classés sous les 10 000 premiers perdent ≈ 5,7 points de base par jour
  (> 15 points de % par an) ; les pertes agrégées des particuliers taïwanais dépassent 2 % du PIB par an (1995-1999) (lu
  dans le PDF, version de travail « Day Trading Skill », 2011) — [Berkeley, PDF](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf)
- Chague, De-Losso & Giovannetti (2019, « Day Trading for a Living? », document de travail FGV/SSRN) : 19 646
  personnes ayant commencé le « day trading » sur le mini-contrat Ibovespa en 2013-2015 ; parmi celles qui ont persisté
  plus de 300 jours, **97 % ont perdu de l'argent** ; 1,1 % ont gagné plus que le salaire minimum brésilien, 0,5 % plus
  que le salaire de départ d'un guichetier de banque ; aucune preuve d'apprentissage — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101) ; [FGV](https://repositorio.fgv.br/items/e87d04fc-4b4c-4a56-ab5a-1c84c1afde1b/full)
- ESMA (mars 2018) : selon des études de plusieurs pays de l'UE, 74 % à 89 % des comptes de particuliers perdent sur les
  CFD, pertes moyennes de 1 600 € à 29 000 € par client ; mesures : levier plafonné, interdiction de perdre plus que la
  mise, avertissements obligatoires — [ESMA](https://www.esma.europa.eu/node/84933)
- Heimer (Cleveland Fed WP 14-33, 2014 ; publié ensuite avec Simsek, publication non vérifiée ici) : le plafond de levier
  imposé par Dodd-Frank aux particuliers américains en devises **réduit les pertes moyennes par transaction**, même
  ajustées du risque, comparé à leurs homologues européens non plafonnés chez les mêmes courtiers ; privés de levier, ils
  négocient plus les jours de forte volatilité (« transfert de risque ») ; les plus confiants en profitent le plus — [Cleveland Fed](https://www.clevelandfed.org/en/newsroom-and-events/publications/working-papers/2014-working-papers/wp-1433-can-leverage-constraints-help-investors.aspx) ; [Ohio State PDF](https://files.fisher.osu.edu/department-finance/public/leverage_constraints_profitability_and_risk-shifting_evidence_from_the_introduction_of_dodd-frank.pdf)
- Robinhood : achats groupés guidés par l'attention suivis de rendements négatifs (≈ -5 % sur le mois) — [Barber et al. 2022, WUSTL](https://profiles.wustl.edu/en/publications/attention-induced-trading-and-returns-evidence-from-robinhood-use/)

### Inferences
- Le rival réel de l'IA n'est pas « le marché efficient » mais aussi cette masse de perdants : leurs biais (disposition,
  achat après hausse, sur-négociation) sont une source possible d'avantage, mais les chiffres de Taïwan montrent que
  même les meilleurs perdent ≈ 40 % de leur avantage brut en frais. Pour COLLAPSAR, peu de coups et des coûts réels
  dans le juge sont non négociables.
- Plafonner le levier aide les humains : c'est un argument pour que la taille choisie par l'IA reste sous les murs FTMO
  avec une marge, et pour juger la régularité plutôt que le gain maximal.

### Gaps
- Pas de source primaire chiffrée trouvée sur l'augmentation du levier APRÈS des pertes (« se refaire ») chez les
  particuliers en CFD ; seule la preuve indirecte de Heimer (transfert de risque) est disponible.
- Pas de statistique publique fiable trouvée sur le taux de réussite des challenges de sociétés de financement (« prop
  firms ») type FTMO.

---

## Q8. Déformations dans les contenus des réseaux sociaux et des formations au trading

### Takeaway
La recherche mesure surtout les effets (influenceurs majoritairement « anti-talentueux », formations promettant de vivre
du day trading alors que 97 % perdent, biais aggravé par les réseaux) ; la description des déformations typiques
elle-même relève surtout de l'observation et de l'opinion, à présenter comme telle.

### Cited Findings
- Kakhbod, Kazempour, Livdan & Schürhoff (« Finfluencers », Swiss Finance Institute WP 23-30) : sur StockTwits, 28 % des
  influenceurs financiers ont un vrai talent (+2,6 %/mois de rendement anormal), 16 % aucun, **56 % un talent négatif**
  (-2,3 %/mois) ; les anti-talentueux ont PLUS d'abonnés et plus d'influence ; faire l'inverse de leurs conseils rapporte
  1,2 %/mois hors échantillon — [SFI](https://sfi.ch/de/publications/n-23-30-finfluencers) ; [AEA 2025](https://www.aeaweb.org/conference/2025/program/paper/i3ry3n4t)
- Chague et al. : contrairement à ce qu'affirment les vendeurs de formations, il est « pratiquement impossible » de
  vivre du day trading (97 % de perdants parmi les persévérants) — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)
- Heimer (2016, RFS) : le réseau social de trading double presque l'effet de disposition — [Cleveland Fed](https://www.clevelandfed.org/publications/working-paper/2016/wp-1618-peer-pressure-social-interaction-and-the-disposition-effect)
- Les études sérieuses du suivi de tendance précisent : coûts estimés « avec beaucoup d'incertitude », coûts de roulement
  exclus, résultats « hypothétiques », Sharpe moyen ≈ 0,4 par marché, performance dégradée si exécution retardée (lu
  dans le PDF) — [Hurst et al. 2017](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)

**[OPINION — à présenter comme observation, non comme fait mesuré]** Déformations courantes, comparées aux faits ci-dessus :
- « Suis la tendance » sur UN marché, en minutes, avec des règles fixes (croisement de moyennes, RSI) : les preuves
  portent sur 1-12 mois, des dizaines de marchés et une taille ajustée à la volatilité ; sur les devises les règles
  techniques simples ont cessé de fonctionner au début des années 1990 (Neely et al. 2009).
- Résultats montrés sans frais ni écart, sur des périodes choisies : un coût de 0,16 % par transaction suffit à effacer
  un effet hebdomadaire documenté (Wang & Yu).
- Récits de « l'argent intelligent » (« smart money ») qui « piège » les particuliers et dont on pourrait lire les traces
  sur le graphique : je n'ai trouvé aucune étude évaluée par les pairs validant ces méthodes ; la seule « trace » mesurée
  de grands acteurs est indirecte (positions CFTC des spéculateurs, couverture gamma de fin de séance).
- Taux de réussite élevés mis en avant sans l'espérance : le suivi de tendance gagne en général moins d'une fois sur deux
  et vit de quelques grands mouvements (cf. AQR 2019 : dépend de la taille des mouvements).

### Inferences
- Pour un rapport à l'utilisateur : chaque idée « de réseau social » doit être confrontée à quatre questions : quel
  horizon ? combien de marchés ? après quels coûts ? sur quelle période jamais vue ?
- Les chiffres des influenceurs (56 % anti-talentueux, plus suivis) suggèrent que la popularité d'une méthode n'est pas
  un indice de sa valeur, voire un signal contraire.

### Gaps
- Aucune étude évaluée par les pairs trouvée qui mesure spécifiquement les méthodes « smart money / concepts
  institutionnels » diffusées sur YouTube/TikTok.
- Pas de source trouvée sur le contenu des formations « prop firm » elles-mêmes.

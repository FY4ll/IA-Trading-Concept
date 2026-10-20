# Le trading très court terme qui marche vraiment (l'or d'abord)

Recherche sur internet du 20/10/2026, en lecture seule (aucune inscription, rien téléchargé). Pour COLLAPSAR, compte
FTMO « Swing » : écart de l'or ~0,25-0,40 $ par once, nuits ~5 %/an à l'achat, murs -5 %/jour et -10 % au total.

Étiquettes : 🟢 = avantage réel mesuré par plusieurs sources indépendantes ET qui passe les frais FTMO de l'or ;
🟡 = avantage réel mais mince, fragile, ou qui ne sert que de filtre ; 🔴 = piège, mort après frais, ou interdit par FTMO.

Rien ici ne garantit un gain : ce sont des pistes à tester, pas des résultats.

---

## 0. En une minute

1. **La règle qui décide de tout : le gain moyen d'un trade doit valoir au moins 5 à 10 fois les frais.** Sur l'or chez
   FTMO, un aller-retour coûte ~0,30-0,60 $ par once (écart + glissement). Il faut donc viser **un gain moyen brut de
   3 $ par once ou plus**, donc tenir de 15 min à quelques heures avec des objectifs de plusieurs dollars. Gold Reaper
   (gain moyen ~5 $/once) est dans cette zone : les frais y prennent ~6-12 % du gain. Les petits « grattages » de
   0,3 à 1 $ par once meurent tous à cause des frais.
2. **Ce qui a un historique réel et long : la cassure de niveaux de prix (plus haut / plus bas de la veille, de la séance,
   de l'heure) par ordres à l'avance, avec un vrai stop, peu de trades par jour, et des gagnants qu'on laisse courir.**
   C'est la famille de Gold Reaper et des stratégies d'or d'Andrea Unger (gardées hors échantillon depuis 2018).
3. **Ce qui est réel mais trop mince pour vivre seul :** l'or monte en Asie et baisse en Occident (très long historique),
   l'élan de la journée sur les indices (Gao, Zarattini), les niveaux ronds, les réactions aux annonces.
   À utiliser comme **filtres ou sens préféré**, pas comme trade seul.
4. **Les pièges :** grille, martingale, objectifs minuscules avec 75-90 % de réussite, retour à la moyenne de nuit,
   « smart money » non mesuré, arbitrage de vitesse, ouverture en pleine annonce (interdit chez FTMO).
5. **À tester sur nos données de l'or à la minute (2015 → 09/2025) :** (A) cassure du plus haut/bas de la veille
   avec stop de structure et stop suiveur ; (B) cassure de la boîte asiatique à l'ouverture de Londres, règles d'un
   tiers reprises telles quelles ; (C) faux cassure du plus haut/bas de la veille (retour à l'intérieur), qui est la
   version mesurable de la « chasse aux stops ». Détails et pièges en section 5.

---

## 1. La règle des frais : le juge de paix

| Exemple réel | Gain moyen brut par trade | Frais FTMO aller-retour (~0,30-0,60 $/once) | Part mangée |
|---|---|---|---|
| Gold Reaper (signal MQL5, tenue 15 min - 2 h 30) | ~5 $/once | 0,30-0,60 $ | **6-12 %** -> survit |
| Unger, cassure plus haut/bas de séance (or, 5 min) | 230 $/contrat = **2,30 $/once** | | **13-26 %** -> survit de justesse |
| Unger, contre-tendance « faux cassure de la veille » | 100-135 $/contrat = **1,0-1,35 $/once** | | **22-60 %** -> très fragile |
| Rejet sur les niveaux ronds de 20 $ | **0,33 $/once** | | **> 100 %** -> mort |
| Cassure de la boîte asiatique (400 variantes testées) | +0,035 R | | mort |

(Un contrat d'or à terme = 100 onces, d'où la division par 100.)

Sources : [Unger, cassure plus haut/bas](https://ungeracademy.com/blog/gold-futures-trading-strategies-supertrend-and-high-low-breakout-techniques-usd80-000-gained-in-2023-and-2024),
[Unger, contre-tendance sur l'or](https://ungeracademy.com/blog/intraday-strategies-on-gold-that-trade-against-the-trend-or-or-rules-performance),
[niveaux de 20 $ sur l'or](https://www.mql5.com/en/blogs/post/775454),
[400 variantes testées sur l'or](https://www.mql5.com/en/blogs/post/777404).

**Phrase clé d'un testeur sérieux (400 variantes, 2016-2026, vrais écarts) : « la plupart des idées dans la journée
valent zéro avant frais ; les frais les rendent négatives ».** Le même auteur rejoue le papier « cassure des
5 premières minutes » (Zarattini et Aziz) sur 5 indices en CFD, 2015-2026 : l'avantage brut est retrouvé
(+0,05 à +0,13 R par trade) mais **net de frais, aucun indice n'est différent de zéro et 4 sur 5 sont négatifs**
([réplication](https://www.mql5.com/en/blogs/post/776235)). Nos propres pistes du 16/10 disent la même chose : bande de
bruit morte avec les frais FTMO, « l'or monte en Asie » mort après frais (`docs/REPRISE.md`).

**Commission sur l'or chez FTMO : à vérifier sur la fiche du symbole.** La plupart des sources disent « aucune
commission sur les métaux » ([Propvator](https://propvator.com/blog/ftmo-trading-conditions/)), d'autres citent
0,0014 % du volume ([Investing.com](https://investing.com/brokers/reviews/ftmo)), soit ~0,06 $/once par côté à 4 000 $.
Si c'est vrai, les frais montent de 0,1 $/once par aller-retour.

---

## 2. Inventaire des familles

### 2.1 🟢 Cassure de niveaux (plus haut/bas de la veille, de la séance, niveaux journaliers / 4 h / 1 h)

- **Preuve :**
  - **Gold Reaper** (Wim Schrynemakers, Profalgo) : cassures de niveaux de support/résistance sur plusieurs échelles
    (d'après un testeur : stratégies 1-3 sur niveaux journaliers, 4 sur 4 h, 5-8 sur 1 h), ordres placés à l'avance,
    stop et objectif fixés dès l'entrée, stop suiveur, ni grille ni martingale
    ([fiche](https://newyorkcityservers.com/blog/the-gold-reaper-review), [essai de casse](https://www.mql5.com/en/blogs/post/776719)).
    Signal public +309 % depuis 2024, baisse 16,9 % ; notre fiche : signal 2265877, 895 trades, 72 % gagnants,
    facteur de profit 2,33, baisse 17 % (`docs/MAITRES_A_TELECHARGER.md`).
  - **Andrea Unger** (4 fois champion du monde de trading) : cassure des plus haut/bas de séance sur l'or à terme,
    bougies de 5 min, 2010 → 2024 : ~388 000 $ par contrat, **trade moyen 230 $ (2,30 $/once)**, baisse max 31 410 $,
    **hors échantillon depuis 2018** ([source](https://ungeracademy.com/blog/gold-futures-trading-strategies-supertrend-and-high-low-breakout-techniques-usd80-000-gained-in-2023-and-2024)).
    Autre stratégie : ordres stop au-dessus du plus haut de la séance précédente, posés quelques heures après
    l'ouverture, fermeture en fin de journée ([source](https://ungeracademy.com/?p=8656)).
  - Le fond scientifique : les ordres stop s'entassent juste au-delà des niveaux visibles et des chiffres ronds ; quand
    le prix les touche, ils déclenchent des **cascades** (le mouvement s'accélère et dure plus longtemps que la réaction
    aux ordres de prise de bénéfice) ([Osler, Réserve fédérale de New York](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf)).
- **Taille de l'avantage :** modeste. Gold Reaper : en réel, un compte analysé montre 72 % de gagnants, gain moyen
  20,94 $ contre perte moyenne 51,10 $, facteur de profit 1,08 seulement, et **des baisses réelles de 30-41 % sur
  certains comptes alors que le test sur l'historique annonçait 12,4 %** ([source](https://newyorkcityservers.com/blog/the-gold-reaper-review)).
  Un testeur indépendant trouve le test sur vrais ticks en léger recul (78 % -> 71 % de gagnants) mais sans effondrement
  ([source](https://www.mql5.com/en/blogs/post/776719)).
- **Frais :** passe (gain moyen 2-5 $/once).
- **Durée de vie :** la seule famille avec des historiques réels de plusieurs années sur l'or. Mais une partie du
  gain vient de la hausse de l'or 2023-2026 (voir piège « jumeau au hasard », section 4).
- **FTMO :** compatible (peu de trades, ordres à l'avance, pas d'exploitation de cotation).

### 2.2 🟡 Cassure de la boîte asiatique à l'ouverture de Londres

- **Règles publiées** ([source](https://www.mql5.com/en/blogs/post/777540)) : boîte = plus haut/plus bas de
  03h00 à 08h00 heure serveur ; à 08h00, ordre d'achat au-dessus et de vente en dessous (petit tampon), le premier
  touché annule l'autre ; une seule entrée par jour ; boîte ignorée si < 0,30 % ou > 1,60 % du prix ; stop de l'autre
  côté de la boîte, plafonné à 0,6 % du prix ; objectif 2,5 R ; stop à l'entrée à 1,5 R ; tout fermé à 21h00 serveur.
- **Résultats :** 01/2023 → 09/2026, vrais ticks chez **deux courtiers** : facteur de profit 1,38 et 1,37, ~715 trades,
  ~49 % gagnants, baisse max 17-19 % à 1 % de risque (11 % à 0,5 %) ; **année 2026 jamais vue : 1,61 sur 157 trades**.
  Ce qui n'a pas marché : stop serré dans la boîte, boîtes de toute taille, tenir au-delà de New York, objectif 5 R.
- **Mais :** le testeur aux 400 variantes trouve **+0,035 R seulement** pour les « boîtes asiatiques » sur 2016-2026,
  et note que beaucoup de cassures de l'or perdaient en 2016-2021 avant de marcher en 2022-2026
  ([source](https://www.mql5.com/en/blogs/post/777404)). Les testeurs disent aussi : « plus la fenêtre horaire est fine,
  plus vite l'avantage s'use » ([source](https://www.mql5.com/en/blogs/post/774275)).
- **Verdict :** à tester, mais en s'attendant à un résultat qui dépend de la période.

### 2.3 🟡 Élan de la journée (« la force appelle la force ») — Gao et al., Zarattini et al.

- **Preuve académique solide sur les indices :** la première demi-heure (depuis la clôture de la veille) prédit la
  dernière demi-heure, SPY 1993-2013 ([Gao, Han, Li, Zhou](https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/)) ;
  confirmé sur **60 contrats à terme (actions, obligations, matières premières, devises), 1974-2020**, avec une cause :
  les teneurs de marché d'options et les fonds à levier qui se couvrent dans le sens du prix
  ([Baltussen et al.](https://ideas.repec.org/a/eee/jfinec/v142y2021i1p377-403.html)). Sur l'or à terme (Chine), la
  première demi-heure prédit les demi-heures suivantes, plus fort quand l'agitation est forte
  ([Zhou et al.](https://acfr.aut.ac.nz/__data/assets/pdf_file/0008/686816/4a-Z-Ivy-Zhou.pdf)).
- **Version praticien :** Zarattini, Aziz, Barbon, « bande de bruit » sur SPY : on entre quand le prix sort de la zone
  du mouvement habituel depuis l'ouverture, stop suiveur ; 2007-2024 : 19,6 %/an net de commissions, mais **sans
  glissement** ([papier](https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/),
  [résumé](https://quantifiedstrategies.substack.com/p/systematic-intraday-trend-following)).
- **Pour nous :** testé le 16/10 avec les frais FTMO : mort ; et sur 7 autres indices : rien même avant frais
  (`docs/REPRISE.md`). L'or au comptant tourne presque 24 h : il n'a pas de vraie « ouverture » ni de vraie
  « clôture », donc la mécanique des couvertures de fin de séance y est plus floue.
- **Verdict :** 🔴 comme trade seul chez FTMO, 🟡 comme information (sens de la journée).

### 2.4 🔴 Cassure des 5 premières minutes sur actions « en jeu » (Zarattini, Barbon, Aziz)

Très bons chiffres sur 7 000 actions américaines 2016-2023 ([papier](https://concretumgroup.com/a-profitable-day-trading-strategy-for-the-u-s-equity-market/)),
mais : actions individuelles non disponibles comme ça chez FTMO, hypothèses irréalistes (pas d'écart, pas de glissement,
[CXO](https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy)), et
**net zéro sur indices en CFD** ([réplication](https://www.mql5.com/en/blogs/post/776235)).

### 2.5 🟡 Retour à la moyenne dans la journée (prix moyen pondéré par les volumes, bandes, faux cassures)

- **Faux cassure du plus haut/bas de la veille** (le prix dépasse le niveau puis revient à l'intérieur -> on joue le
  retour) : Unger, or à terme, bougies de 5-15 min, fermé le soir, **hors échantillon depuis 2018**, trade moyen
  100-135 $/contrat (= 1,0-1,35 $/once), net de frais et glissement des contrats à terme
  ([source](https://ungeracademy.com/blog/intraday-strategies-on-gold-that-trade-against-the-trend-or-or-rules-performance)).
  Une autre stratégie de retournement sur l'or gagne le concours Unger d'août 2025 ([source](https://ungeracademy.com/?p=8581)).
  -> Réel, mais **le gain par once est 2 à 4 fois trop petit pour l'écart FTMO**, sauf à viser plus loin.
- **Prix moyen pondéré par les volumes :** nos CFD n'ont pas de vrais volumes (seulement le nombre de cotations) : la
  ligne n'est qu'une approximation. Aucune étude sérieuse trouvée qui montre un gain net sur l'or.
- **Retour à la moyenne de nuit** (les « scalpeurs de nuit ») : Night Hunter Pro, référence du genre, +215 % de 2020 à
  début 2023 puis **plat et agité depuis 2023**, baisse max ~30 % ; objectifs de 5-20 points détruits par l'écart qui
  s'élargit à la bascule de minuit ([source](https://newyorkcityservers.com/blog/night-hunter-pro-review)).
- **Verdict :** 🟡 pour la faux cassure (à tester avec objectifs plus lointains), 🔴 pour le grattage de nuit.

### 2.6 🟡 (filtre) / 🔴 (trade) Réaction aux annonces (emploi américain, inflation, banque centrale)

- **Preuve :** réaction rapide et forte, surtout l'emploi américain à 8h30 New York ; l'essentiel se fait dans les
  10 premières minutes ; 15 min après une déception sur l'emploi, l'or monte de 3,66 $ en moyenne, baisse de 1,68 $
  après une bonne surprise ([études](https://mountainscholar.org/handle/10217/206884),
  [FXStreet](https://www.fxstreet.com/analysis/us-march-nonfarm-payrolls-preview-analyzing-golds-reaction-to-nfp-surprises-202203310915)).
  Après la banque centrale américaine, l'ajustement de l'or dure plus de 5 minutes
  ([étude](https://pure.kfupm.edu.sa/en/publications/how-do-the-gold-intra-day-returns-and-volatility-react-to-monetar/)).
- **Frais :** l'écart de l'or peut sauter de quelques dizaines de cents à **plusieurs dollars pendant quelques
  secondes** (exemple : 2 $ à une publication d'inflation) ([source](https://www.mql5.com/en/blogs/post/773690)).
- **FTMO :** la règle « trading sur trous » **interdit d'ouvrir des positions pendant les annonces majeures programmées**
  ([règles FTMO](https://ftmo.com/en/forbidden-trading-practices/)). Le compte Swing est exempté du blocage de
  2 minutes autour des annonces, mais pas des pratiques interdites. Zone grise -> à éviter.
- **Verdict :** 🔴 comme trade à la publication ; 🟢 comme **filtre** (ne rien ouvrir de 15 min avant à 15 min après) ;
  « suivre la tendance née d'une annonce 30-60 min après » reste une idée non prouvée.

### 2.7 🔴 (signal) / 🟢 (placement) Niveaux ronds

- Test sur 50 000 bougies horaires de l'or (2018-2026) avec tirages au hasard de contrôle : à l'approche d'un niveau de
  20 $ avec élan, le prix est un peu plus souvent repoussé (51-55 % contre 50 %), **recul moyen 0,33-0,38 $**, zone
  d'effet ~1 $ ; le prix cale en général **1 $ avant** le niveau. Conclusion de l'auteur : « à peu près nul avant
  glissement » avec un écart de 0,20-0,35 $ ([source](https://www.mql5.com/en/blogs/post/775454)).
- Les études académiques trouvent un entassement des ordres aux chiffres ronds, mais un effet « barrière » discuté
  ([dépôt académique](https://ray.yorksj.ac.uk/id/eprint/1438/1/The%20Gap%20Psychological%20Barriers%20in%20Gold%20and%20Silver%20Prices.pdf)).
- **Usage utile :** placer l'objectif ~1 $ AVANT un rond, et le stop pas juste derrière un rond (là où les stops
  s'entassent, Osler).

### 2.8 🔴 « Chasse aux stops », « liquidité », méthodes « smart money »

- Le mécanisme existe (Osler : stops entassés, cascades). Mais **les recettes populaires ne passent pas les mesures** :
  « smart money » / offre-demande : -0,10 à -0,23 R par trade ; robot libre « vides de prix » : -0,13 R alors qu'il
  annonçait +48,7 % en 6 mois ([source](https://www.mql5.com/en/blogs/post/777404)). Notre piste du 16/10 : « faible,
  sans valeur pratique » sur or/indices/devises (`vie/pistes/smc_combinaisons/rapport.md`).
- La seule version mesurable et honnête = la **faux cassure d'un niveau clair** (2.5), testée comme règle fixe.

### 2.9 🟡 Saisonnalité horaire de l'or (« l'or monte en Asie, baisse en Occident »)

- **Preuve longue :** acheter au fixing de l'après-midi de Londres (15h) et revendre au fixing du matin (10h30) aurait
  transformé 100 $ en 112 274 $ de 1970 à 2024 ; l'inverse : 100 $ -> 6,97 $ ([FXStreet / Ed Steer](https://www.fxstreet.com/analysis/a-strange-dichotomy-gold-up-on-the-year-in-asian-markets-down-big-in-the-west-202607131959)).
  Premier semestre 2026 (Conseil mondial de l'or) : +12,9 % pendant les heures asiatiques, -15 % pendant les heures
  américaines, -1,3 % en Europe. Le fonds or GLD : presque tout le gain se fait hors séance américaine, la séance
  elle-même est à plat sur 20 ans ([Quantified Strategies](https://quantifiedstrategies.substack.com/p/a-quantitative-look-at-the-gold-overnight)).
  Mémoire universitaire (Copenhague, 2019) : courbe « en chapeau », gain en heures orientales ; **avant frais
  ratio rendement/risque jusqu'à 1,61, après frais en dessous du simple achat** ([CBS](https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/)).
  Unger exploite la même idée sur l'or à terme (vente la nuit européenne, achat l'après-midi new-yorkais)
  ([source](https://ungeracademy.com/?p=6611)).
- **Pour nous :** testé le 16/10 (entrée 19h New York, sortie 8h Londres) : force 2,9 / 1,4 / 3,45 contre le hasard,
  mais **mort après frais FTMO** (`docs/REPRISE.md`).
- **Attention aux fixings :** les chutes au fixing de l'après-midi (2004-2013) étaient liées à des soupçons de
  manipulation ([Abrantes-Metz](https://www.stern.nyu.edu/experience-stern/news/prof-rosa-abrantes-metz-on-london-s-gold-rate-fix.md)) ;
  le fixing est devenu une enchère électronique en 03/2015 : ne pas compter sur cet effet après 2015.
- **Verdict :** 🟡 comme **sens préféré** d'une cassure (2.1), pas comme trade seul.

### 2.10 🟡 Flux de fin de séance

Réel sur les contrats à terme (dernière demi-heure, Baltussen) mais l'or au comptant n'a qu'une pause de 1 h
(17h-18h New York) ; la clôture de l'or à terme new-yorkais (13h30 New York) est un repère possible, non mesuré pour
le CFD. Les règles FTMO interdisent d'ouvrir **dans les 2 h avant une fermeture de marché d'au moins 2 h** (donc le
vendredi soir) ([règles FTMO](https://ftmo.com/en/forbidden-trading-practices/)).

### 2.11 🔴 Microstructure, cotation à cotation, vitesse

Carnet d'ordres absent chez nous, et FTMO interdit l'exploitation des retards ou erreurs de cotation, les outils
« ultra-rapides » et les robots à plus de 2 000 requêtes/jour ([règles FTMO](https://ftmo.com/en/forbidden-trading-practices/)).
Les études sur les règles techniques de l'or à haute fréquence : avec les réglages classiques, **aucune capacité à
prédire** ; seulement des réglages longs, un peu, sur l'or ([Batten et al.](https://ideas.repec.org/a/eee/intfin/v52y2018icp102-113.html)).
Sur 7 846 règles dans la journée, **aucune ne survit** à la correction pour le nombre de règles essayées
([Marshall, Cahan](https://www.cxoadvisory.com/technical-trading/does-technical-trading-work-with-commodity-futures/)).

### 2.12 🔴 Grille, martingale, moyenne à la baisse

Waka Waka, record de la grille (70+ mois gagnants depuis 2018) : baisse > 40 % début 2024 sur le compte du
vendeur, comptes d'utilisateurs **vidés** ([source](https://newyorkcityservers.com/blog/waka-waka-ea-review)). Sur l'or,
les signaux de robots à « récupération » disparaissent de MQL5 (comptes effacés = sautés)
([source](https://newyorkcityservers.com/blog/goldwave-ea-mt5-review)). Incompatible avec le mur de -5 %/jour.

---

## 3. Les robots de l'or « qui marchent » : points communs et pièges

### Ce qu'ont en commun ceux qui ont un historique réel long
| Principe | Exemple |
|---|---|
| Un vrai stop à chaque trade, posé dès l'entrée | Gold Reaper, Unger, cassure Asie-Londres |
| Entrées par **ordres posés à l'avance sur un niveau visible** (plus haut/bas, boîte) | idem |
| Peu de trades par jour (souvent 1 par stratégie et par jour) | cassure Asie-Londres : 1/jour |
| Gain moyen par once **≥ 2-5 $** (5-10 fois l'écart) | Gold Reaper ~5 $, Unger 2,30 $ |
| Gagnants qu'on laisse courir (stop suiveur, stop à l'entrée vers 1,5 R, objectif 2-3 R) | Gold Reaper jusqu'à +155 $ |
| Plusieurs stratégies sur plusieurs échelles (journalier, 4 h, 1 h) | Gold Reaper : 8-9 stratégies |
| Sortie avant la nuit ou avant la fin de New York (frais de nuit, trous) | cassure Asie-Londres : fermé à 21h serveur |
| Coupe-circuit de perte du jour réglé sous la limite de la société | Gold Reaper : arrêt de survie, arrêt dur |
| Testé chez **deux courtiers** et sur une période jamais vue | cassure Asie-Londres |

### Pièges communs chez ceux qui sautent
| Piège | Signe | Source |
|---|---|---|
| Grille / martingale / récupération | courbe trop lisse, puis compte vidé, signal effacé | [Waka Waka](https://newyorkcityservers.com/blog/waka-waka-ea-review) |
| Objectif minuscule, stop large, 75-90 % de réussite | un robot à 76 % de gagnants **perdait** (stop 1,2 pour objectif 0,35 : il fallait 77 %) | [400 variantes](https://www.mql5.com/en/blogs/post/777404) |
| Test sur l'historique trop beau | Gold Reaper : 12,4 % de baisse au test, 30-41 % en réel | [revue](https://newyorkcityservers.com/blog/the-gold-reaper-review) |
| Hausse de l'or prise pour du talent | un robot gratuit à +0,21 R ; des entrées au hasard avec les mêmes sorties : +0,14 R | [400 variantes](https://www.mql5.com/en/blogs/post/777404) |
| Écart variable ignoré | gagnant chez un courtier, perdant chez un autre ; 68 % de réussite au test, 41 % en réel | [testeur](https://www.mql5.com/en/blogs/post/774275), [forum MQL5](https://www.mql5.com/en/blogs/post/776693) |
| Fiche du symbole différente d'un courtier à l'autre | valeur du point fausse -> positions **10 fois trop grosses** | [cassure Asie-Londres](https://www.mql5.com/en/blogs/post/777540) |
| Usure d'une fenêtre horaire très fine | scalpeurs de nuit plats depuis 2023 | [Night Hunter](https://newyorkcityservers.com/blog/night-hunter-pro-review) |
| Stratégies « différentes » qui perdent ensemble | Gold Reaper : stratégies 6 et 7 perdent ensemble 3 jours de perte sur 4 | [essai de casse](https://www.mql5.com/en/blogs/post/776719) |
| Noms copiés | plusieurs produits « Gold Reaper » de vendeurs différents (dont un robot de moyennes mobiles) | [MQL5](https://www.mql5.com/en/market/product/161775) |

---

## 4. Durable ou mourant : ce qui fait la différence

1. **Le rapport gain moyen / frais.** Au-dessus de 5-10 : un écart qui double ne tue pas la méthode. En dessous de 3 :
   un changement de courtier, d'heure ou d'agitation la tue. C'est le premier chiffre à regarder.
2. **La source de l'avantage.** Durable = un comportement humain ou une obligation (ordres stop entassés au-delà des
   niveaux, couvertures dans le sens du prix, demande physique asiatique). Mourant = un défaut de la machine (cotation
   en retard, écart mal réglé, flux lent) : interdit chez FTMO et disparaît au changement de courtier.
3. **Pas besoin d'être servi à un prix précis.** Les méthodes qui exigent d'être servies à un prix limite exact
   (grattage de 0,3 $) sont servies surtout quand le prix part contre elles. Les ordres stop sur cassure souffrent
   d'un glissement, mais il est petit devant un gain de 3-5 $.
4. **Des fenêtres larges, pas une minute magique.** « Plus la fenêtre est fine, plus vite l'avantage s'use. »
5. **Assez de trades et deux moitiés.** « 30 trades en 25 ans, c'est une histoire, pas une preuve. » Gagner sur les
   deux moitiés de l'historique, en hausse ET en baisse de l'or, chez deux sources de prix.
6. **Battre un jumeau au hasard** (même heure, mêmes sorties, sens tiré au sort) : sinon c'est la tendance de l'or qui
   paie, pas la méthode.
7. **Compter tous les essais.** Plus on essaie de réglages, plus un hasard ressemble à un avantage ; seuil exigeant
   (le testeur aux 400 variantes exige une force de 3,3 au lieu de 2).

---

## 5. Recommandation : 3 méthodes à tester honnêtement (or à la minute, 02/2015 → 09/2025)

Règles écrites ici AVANT tout test. Juge habituel du projet (jumeau au hasard, frais FTMO, challenges simulés), découpe
2015-2020 / 2021-2023 / 2024-09/2025 ouverte une seule fois. Risque 0,3-0,5 % par trade (le testeur Asie-Londres
conseille 0,3-0,4 % pour un mur de -10 %).

### A. 🟢 (à confirmer) Cassure du plus haut / plus bas de la veille, gagnants qui courent — famille Gold Reaper / Unger
- **Jour** = de 18h New York à 17h New York (journée de l'or). Niveaux : plus haut H et plus bas B de la journée d'hier.
- **Ordres** : achat stop à H + tampon, vente stop à B - tampon, tampon = 5 % de la moyenne des écarts haut-bas des
  14 derniers jours (A14). Actifs de **08h00 Londres à 12h00 New York**. Le premier exécuté n'annule pas l'autre, mais
  au plus **1 trade par sens et par jour**.
- **Pas d'entrée si** : le prix a déjà dépassé le niveau avant 08h00 Londres ; annonce majeure dans les 15 min
  (emploi, inflation, banque centrale américaine) ; écart du moment > 2 fois son habitude ; vendredi après 14h New York.
- **Stop** : 0,35 x A14 de l'autre côté du niveau d'entrée (stop « de structure », jamais dans le bruit).
- **Sortie** : stop à l'entrée quand le gain atteint 1 R ; puis stop suiveur à 0,5 x A14 du meilleur prix ;
  sinon tout fermé à **16h45 New York** (avant la pause, aucune nuit payée).
- **Variante unique décidée d'avance** : mêmes règles avec les niveaux de la séance asiatique au lieu de la veille.
  Et une version « sens préféré » : seulement les achats en Asie / ventes en Europe, pour mesurer le biais horaire (2.9).
- **Chiffre à surveiller** : gain moyen brut par once (doit dépasser 3 $ à l'échelle des prix de 2025).

### B. 🟡 Cassure de la boîte asiatique à l'ouverture de Londres — règles d'un tiers, reprises sans les toucher
- Règles exactes du testeur ([source](https://www.mql5.com/en/blogs/post/777540)) : boîte 03h00-08h00 serveur ;
  ordres de part et d'autre à 08h00, le premier exécuté annule l'autre, 1 trade/jour ; boîte ignorée si < 0,30 % ou
  > 1,60 % du prix ; stop de l'autre côté plafonné à 0,6 % ; objectif 2,5 R ; stop à l'entrée à 1,5 R ; fermeture
  21h00 serveur. **Son serveur est probablement à l'heure d'Europe de l'Est (GMT+2/+3)**, donc boîte ~01h-06h Londres
  et fermeture ~14h New York : vérifier l'heure (ouverture de Londres = 08h Londres) et l'écrire avant de tester.
- Intérêt : règles fixées par quelqu'un d'autre, déjà testées chez deux courtiers et sur 2026 jamais vu -> notre test
  sur 2015-2022 est une vraie période vierge pour cette règle. Prédiction honnête : le testeur aux 400 variantes trouve
  presque rien sur 2016-2021, donc s'attendre à un résultat faible avant 2022.

### C. 🟡 Faux cassure du plus haut / plus bas de la veille (la « chasse aux stops » mesurable) — famille Unger contre-tendance
- Mêmes niveaux H et B que A. **Vente** : le prix dépasse H d'au moins le tampon (stops déclenchés), puis une bougie de
  15 min **clôture de nouveau sous H** -> vente au marché à l'ouverture de la bougie suivante. **Achat** symétrique sous B.
- Fenêtre : 08h00 Londres -> 12h00 New York ; 1 trade par sens et par jour ; mêmes filtres d'annonces et d'écart que A.
- **Stop** : au-delà de l'extrême atteint pendant le dépassement + tampon. **Objectif** : le milieu de la journée
  d'hier, mais **seulement si l'objectif est à au moins 3 fois les frais aller-retour** (sinon pas de trade) ;
  stop à l'entrée à 1 R ; fermeture 16h45 New York.
- Pourquoi : Unger le garde hors échantillon depuis 2018 sur l'or à terme, mais à 1-1,35 $/once ; la règle « objectif
  au moins 3 fois les frais » sert à voir si une version plus ambitieuse passe l'écart FTMO. A et C sont des jumeaux
  inverses : si les deux sont faibles, le niveau de la veille ne porte pas d'information.

### Les pièges à éviter dans le test
1. **Heures.** Fichier `data/kaggle_gold/XAU_1m_data.csv` : heure serveur = New York + 7 h, mais **New York + 6 h avant
   06/2011** (déjà corrigé dans `regarder/pistes/or_asie_2004.py`). Vérifier chaque année que la grosse minute des jours
   d'emploi américain tombe à 8h30 New York. Londres et New York ne changent pas d'heure le même jour (2-3 semaines
   de décalage par an) : convertir chaque fenêtre dans SON fuseau. Le fichier s'arrête au 12/09/2025.
2. **Écart variable.** Le fichier n'a pas d'écart : le modéliser par heure (plus large de 17h à 19h New York, le lundi
   à l'ouverture, autour des annonces : x3 à x10 pendant quelques minutes). Choisir d'avance comment ramener l'écart au
   prix de l'époque (en % du prix, comme `mains/frais_ftmo.py`) ET refaire le test avec l'écart fixe en dollars
   d'aujourd'hui (0,40 $) : une méthode qui ne survit qu'à l'une des deux est fragile.
3. **Glissement.** Ordres stop servis au pire de la minute qui touche le niveau + 0,10 $ (0,30 $ près des annonces) ;
   stops de protection pareil. Si le stop et l'objectif sont tous deux touchés dans la même minute : **compter le stop**.
4. **Prix de vente / prix d'achat.** Le fichier est probablement un seul prix : un achat sort au prix de vente, donc
   payer l'écart complet à chaque aller-retour, des deux côtés.
5. **La hausse de l'or.** De ~1 060 $ à ~3 600 $ sur la période : regarder achats et ventes à part, battre le jumeau
   au hasard, et rejouer sur l'or « retourné » (miroir).
6. **Règles FTMO dans le simulateur.** Perte du jour comptée sur le compte flottant ; pas d'ouverture pendant les
   annonces majeures (règle « trous ») ni dans les 2 h avant le week-end ; frais de nuit si on dépasse 17h New York ;
   vérifier la commission métaux sur la fiche du symbole (0 ou ~0,0014 %).
7. **Compter les essais.** A (2 variantes), B (1), C (1) = 4 essais au total, écrits ici. Tout réglage ajouté après
   avoir vu un résultat = un essai de plus, à déclarer.

---

## Sources principales
- Règles FTMO, pratiques interdites : https://ftmo.com/en/forbidden-trading-practices/
- Osler, ordres stop et cascades (Réserve fédérale de New York) : https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf
- Gao, Han, Li, Zhou, élan de la journée : https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/
- Baltussen et al., élan de la journée sur 60 contrats à terme : https://ideas.repec.org/a/eee/jfinec/v142y2021i1p377-403.html
- Zarattini, Aziz, Barbon, bande de bruit SPY : https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/
- Zarattini, Barbon, Aziz, cassure des 5 premières minutes : https://concretumgroup.com/a-profitable-day-trading-strategy-for-the-u-s-equity-market/
- Réplication nette de frais sur 5 indices en CFD : https://www.mql5.com/en/blogs/post/776235
- 400 variantes testées sur l'or : https://www.mql5.com/en/blogs/post/777404
- Pourquoi les tests sur l'or flattent : https://www.mql5.com/en/blogs/post/774275
- Cassure Asie-Londres, deux courtiers : https://www.mql5.com/en/blogs/post/777540
- Niveaux ronds de 20 $ sur l'or : https://www.mql5.com/en/blogs/post/775454
- Séances de l'or et annonces : https://www.mql5.com/en/blogs/post/773690
- Gold Reaper, revue et essai de casse : https://newyorkcityservers.com/blog/the-gold-reaper-review , https://www.mql5.com/en/blogs/post/776719
- Unger Academy, or : https://ungeracademy.com/blog/gold-futures-trading-strategies-supertrend-and-high-low-breakout-techniques-usd80-000-gained-in-2023-and-2024 ,
  https://ungeracademy.com/blog/intraday-strategies-on-gold-that-trade-against-the-trend-or-or-rules-performance , https://ungeracademy.com/?p=6611 , https://ungeracademy.com/?p=8656
- L'or en Asie / en Occident : https://www.fxstreet.com/analysis/a-strange-dichotomy-gold-up-on-the-year-in-asian-markets-down-big-in-the-west-202607131959 ,
  https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/ , https://quantifiedstrategies.substack.com/p/a-quantitative-look-at-the-gold-overnight
- Prix d'ouverture trompeurs (fonds de mines d'or) : https://quantpedia.com/dangers-of-relying-on-ohlc-prices-the-case-of-overnight-drift-in-gdx-etf/
- Règles techniques de l'or à haute fréquence : https://ideas.repec.org/a/eee/intfin/v52y2018icp102-113.html
- Annonces et métaux : https://mountainscholar.org/handle/10217/206884
- Grilles et scalpeurs de nuit : https://newyorkcityservers.com/blog/waka-waka-ea-review , https://newyorkcityservers.com/blog/night-hunter-pro-review

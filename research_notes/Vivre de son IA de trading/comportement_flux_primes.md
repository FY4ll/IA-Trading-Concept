# Avantages issus du comportement, des flux forcés et des primes de risque (état 2024-2026, trader algorithmique particulier sur CFD / FTMO)

Note de méthode : 19 recherches/lectures web (18/10/2026). Tout chiffre ci-dessous porte sa source. Ce qui vient de ma
mémoire sans source vérifiée est rangé en « Lacunes » ou signalé « non vérifié ». Coûts FTMO de référence fournis par
le demandeur : EURUSD ~0,006 % aller-retour, indices US/or ~0,008-0,012 %, crypto ~0,066 % + ~30 %/an de portage de
nuit ; portage indices/devises 1,5-4 %/an.

## 1. Comportement : positionnement de la foule, sentiment, sur/sous-réaction, retour à la moyenne court, nuit contre jour, loterie crypto

### Takeaway
Les effets « comportementaux » utilisables avec des données gratuites sont réels mais petits et instables : le contre-pied
de la foule des particuliers (sentiment courtier) est surtout documenté par des praticiens, pas par une littérature
académique solide récente ; le retour à la moyenne court sur indices (RSI(2) de Connors) survit mais s'est nettement
affaibli et ne bat plus l'achat-conservation ; l'effet « tout le gain vient la nuit » est en partie un artefact du fonds
SPY et ne tient pas sur la sous-période la plus récente.

### Cited Findings
**Contre-pied de la foule (sentiment courtier IG / OANDA / Myfxbook)**
- Principe pratiquant : les données de courtiers donnent le % de particuliers acheteurs/vendeurs par paire ; la majorité
  aurait tort la plupart du temps, et un retournement de la foule dans le sens d'une tendance longue signale
  l'épuisement — [TradingView, script « Retail Forex Sentiment Fear/Greed »](https://www.tradingview.com/scripts/sentimentindex/)
- Exemple d'usage public : IG montrait 73,65 % de clients vendeurs sur USD/JPY (ratio 2,80/1), lu comme signal
  contrarien haussier ; la source précise elle-même que c'est une « théorie de marché » qui ne produit pas toujours de
  profit — [DailyFX, mai 2024](https://www.dailyfx.com/news/forex-japanese-yen-sentiment-analysis-outlook-usd-jpy-eur-jpy-gbp-jpy-20240523.html)
- Aucune étude académique récente (2020-2026) chiffrant un rendement net du contre-pied du sentiment courtier n'est
  ressortie de mes recherches (voir Lacunes). Le projet a déjà mesuré en interne « C1 contre la foule » : information la
  plus forte, mais tuée par les frais FTMO (CLAUDE.md du projet, 16/10/2026).

**Taux de financement crypto (« funding ») / positionnement des contrats perpétuels**
- He, Manela, Ross, von Wachter, « Fundamentals of Perpetual Futures » (version juin 2024) : les écarts entre perpétuels
  et prix de non-arbitrage sont bien plus grands qu'en devises, ils bougent ensemble entre cryptos et **diminuent avec
  le temps** ; une stratégie simple d'arbitrage donne de grands ratios rendement/risque même pour un investisseur payant
  les frais Binance les plus élevés — [arXiv 2212.06888](https://arxiv.org/abs/2212.06888v6)
- Ce résultat porte sur un arbitrage perpétuel contre comptant (deux jambes), pas sur un signal directionnel ; un CFD
  FTMO ne permet pas d'encaisser le funding (le portage FTMO est un coût fixe ~30 %/an) — inférence, voir plus bas.

**Retour à la moyenne court sur indices (« acheter le creux en tendance », RSI(2) de Connors)**
- Le RSI(2) de Connors a « survécu plus de 17 ans hors échantillon » ; sur le S&P 500, oct. 2016 → oct. 2026, +18,1 %
  au total sur la décennie, **très en dessous de l'achat-conservation** ; 2020 = 2 trades perdants, -12,2 % ; meilleure
  année 2022 (+10,4 %, 5 gagnants sur 7) — [Backtrex, RSI(2) sur S&P 500](https://backtrex.com/en/backtests/connors-rsi-2-sp-500)
- Mécanisme : après quelques fortes journées de baisse dans une tendance haussière, les jours suivants tendent à
  rebondir ; le filtre 200 jours garde le côté de la tendance — [Backtrex](https://backtrex.com/en/backtests/connors-rsi-2-sp-500)

**Rendement de nuit contre rendement de séance (indices US)**
- Sur ~30 ans, 1 $ dans SPY de l'ouverture à la clôture -> 1,20 $ ; tenu seulement la nuit -> 17,27 $ ; depuis 2000,
  nuit seule +129,15 %, séance seule -1,89 % — [Advisor Perspectives / CXO (résumés)](https://www.advisorperspectives.com/articles/2025/03/11/working-night-shift-still)
- Mise en garde récente : l'effet « tout le gain vient la nuit » serait un phénomène du fonds SPY, pas de l'indice S&P 500
  calculé ; la supériorité de la nuit est « assez constante mais ne tient pas sur la sous-période la plus récente » —
  [CXO Advisory](https://www.cxoadvisory.com/?p=27932) ; [FXStreet, août 2025](https://www.fxstreet.com/analysis/who-is-getting-action-at-night-202508190629)

**Loterie / attention en crypto, momentum de week-end**
- Étude 2020 → oct. 2025 sur 8 grandes cryptos : le momentum temporel a donné ~31,96 %/an (brut) —
  [journals.vu.lt, « Momentum Trading in Cryptocurrencies »](https://www.journals.vu.lt/BATP/en/article/download/44540/42590/138419)
- Les tendances crypto persistent typiquement 30 à 40 jours, et le momentum temporel est surtout présent quand le marché
  monte — [AUT, Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)

### Inferences
- Sentiment courtier : signal gratuit (IG, Myfxbook publics) mais son horizon utile est de plusieurs jours ; sur FTMO le
  portage devises (1,5-4 %/an ≈ 0,004-0,011 %/nuit) plus l'écart (0,006 %) restent petits face à un mouvement de 0,3-0,5 %
  sur quelques jours. Le problème mesuré par le projet (frais qui tuent C1) suggère que le signal avait été exploité à
  trop haute fréquence ou sur des marchés chers (crypto 0,066 %) : à retester sur horizon plus long et marchés bon marché.
- RSI(2) : sur US500 CFD, ~5-10 trades/an, coût ~0,01 % + 3-5 nuits de portage (~0,02-0,05 %) par trade : coût
  négligeable, mais l'avantage lui-même a fondu (rendement < achat-conservation sur 2016-2026). Pièce de diversification
  au mieux, pas un moteur.
- Nuit contre séance : si l'effet est propre au fonds SPY et a disparu récemment, il ne doit pas être exploité sur un CFD
  indice (qui suit le contrat à terme, pas SPY) — et le portage de nuit FTMO coûte précisément la nuit.

### Gaps
- Aucune étude académique 2020-2026 trouvée chiffrant le contre-pied du sentiment courtier (IG/OANDA/Myfxbook) net de
  frais ; idem pour le ratio acheteurs/vendeurs Binance et les « petits spéculateurs » du rapport COT (non cherché faute
  de budget de recherche). Mémoire non vérifiée : les travaux sur les traders particuliers en devises (ex. Heimer & Simon)
  montrent qu'ils perdent en moyenne, mais cela ne prouve pas un contre-pied rentable après frais.
- Sentiment des nouvelles / attention (Google Trends, nouvelles) : non couvert, aucune source récupérée.
- Effet « funding » directionnel (funding extrême -> retournement) : pas de chiffre net trouvé.

## 2. Flux forcés : fin/début de mois, rééquilibrages, fonds à effet de levier, couverture gamma des teneurs de marché d'options, échéances, fixing de Londres, fins de trimestre

### Takeaway
Les flux forcés sont la famille la mieux expliquée mécaniquement (l'acheteur/vendeur n'a pas le choix) : l'effet de
tournant de mois sur le S&P 500 tient encore jusqu'à fin 2024 ; la fin de séance est poussée par le rééquilibrage des
fonds à effet de levier (effet ~2 fois plus fort que la couverture gamma) et par la couverture des teneurs de marché
quand leur gamma est négatif ; les flux de fin de mois en devises au fixing de 16h Londres sont documentés mais
s'inversent en moins d'une minute — inutilisable sur CFD.

### Cited Findings
**Tournant du mois (turn-of-the-month, indices)**
- S&P 500, 1980 → T3 2024 : acheter à la clôture de la veille du dernier jour du mois, vendre à la clôture du 3e jour du
  mois suivant ; détenir 4 jours/mois donne un rendement annuel seulement 0,89 point inférieur à celui de tous les autres
  jours réunis — [CXO Advisory, persistance et robustesse](https://www.cxoadvisory.com/calendar-effects/turn-of-the-month-effect-persistence-and-robustness) ;
  [ETF Trends](https://www.etftrends.com/etf-strategist-channel/turn-month-effect/)
- « Calendar Anomalies in Stock Index Futures » : le tournant du mois dans les contrats à terme S&P 500 est le **seul** effet
  calendaire statistiquement et économiquement significatif et persistant ; une étude 2014 le retrouve dans 19 pays sur 20 —
  [ETF Trends / CXO (citations)](https://www.etftrends.com/etf-strategist-channel/turn-month-effect/)

**Rééquilibrage des fonds à effet de levier et couverture gamma (fin de séance)**
- Baltussen, Da, Lammers, Martens (JFE 2021, « Hedging demand and market intraday momentum ») : la couverture gamma des
  teneurs de marché d'options entraîne le momentum intra-journalier ; dans de nombreux contrats à terme, le momentum de
  fin de journée se concentre sur les jours de gamma négatif des teneurs de marché (notamment S&P 500) —
  [JFE 142 (2021) PDF](https://academicweb.nd.edu/~zda/intramom.pdf) ; [ResearchGate](https://www.researchgate.net/publication/351315710_Hedging_demand_and_market_intraday_momentum)
- Gamma agrégé fortement négatif (positif) rapporté au volume -> momentum (retournement) de fin de journée significatif ;
  l'effet du rééquilibrage des fonds à effet de levier est **environ deux fois** celui de la pression gamma : un écart-type
  de rééquilibrage = magnitude des rendements de fin de journée multipliée par 4,31 —
  [Beckmeyer et al., « Leveraged ETFs, Option Market Imbalances, and End-of-Day Price Dynamics »](https://portal.northernfinanceassociation.org/viewp.php?n=2240036708) ;
  [version Saint-Gall](https://alexandria.unisg.ch/server/api/core/bitstreams/5a99db31-0d37-4f86-9502-8cb0f3bff4fe/content)
- Rééquilibrage de fin de journée des produits VIX : impact boursier documenté (Journal of Banking & Finance 2025) —
  [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0378426625001761)
- Options 0DTE : Cboe a publié une étude « 0DTE Index Options and Market Volatility: How Large is Their Impact? » (titre
  seulement récupéré ; conclusion non lue) — [Cboe PDF](https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf)

**Fixing WM/Reuters 16h Londres et fin de mois en devises**
- Les flux de rééquilibrage de couverture de change sont récurrents, prévisibles, concentrés dans les dernières heures du
  mois avant le fixing de 16h ; souvent pilotés par des modèles à seuils fixes — [investingLive (ex-ForexLive)](https://investinglive.com/Education/!/how-month-end-rebalancing-works-20191128)
- Les variations avant/après fixing sont extraordinairement volatiles et fortement autocorrélées négativement, surtout le
  dernier jour du mois ; petit retournement dans la **minute** qui suit le fixing de 16h —
  [Evans, NYU Stern (2015)](https://pages.stern.nyu.edu/~jh4/SternMicroMtg/Old/SternMicroMtg2015/Papers/4ExEvans.pdf) ;
  [Norges Bank, « The WMR fix and its impact on currency markets »](https://www.norges-bank.no/contentassets/619c8b75e1ed4ba691e8ad6a006855e6/39-panagiotou---the-wmr-fix-and-its-impact-on-currency-markets-.pdf)

### Inferences
- Tournant du mois sur US500 CFD FTMO : 4 jours de détention ≈ 0,01 % d'écart + ~4 nuits de portage (4 %/an × 4/365 ≈
  0,044 %) ≈ 0,055 % de coût par mois. Le gain moyen historique du tournant de mois n'a pas été récupéré (lacune), mais
  l'effet ne vaut que si le gain moyen sur 4 jours dépasse nettement ~0,06 % ; c'est essentiellement une exposition
  « marché acheteur » concentrée sur 4 jours, pas une couverture contre la baisse.
- Fin de séance US (dernière demi-heure) : coût FTMO ~0,01 % par aller-retour intra-journalier, sans portage : la famille
  « fin de séance poussée par fonds à levier + gamma » est compatible avec les coûts FTMO. Le gamma exact (GEX) est
  payant (SpotGamma, SqueezeMetrics) ; un substitut gratuit est la direction de la séance jusqu'à 15h30 New York (les
  fonds à levier rééquilibrent dans le sens du mouvement du jour).
- Fixing devises : l'effet dure moins d'une minute et le prix y est très volatil : hors de portée d'un particulier sur
  CFD (latence, écart élargi). À écarter.

### Gaps
- Rééquilibrages d'indices (S&P, Russell), échéances mensuelles d'options (OPEX), effets 0DTE 2023-2026, fin de trimestre
  des fonds de pension (actions/obligations), ventes fiscales de fin d'année : aucune source chiffrée récupérée dans le
  budget de recherche. La plupart concernent des actions individuelles ou la clôture du marché au comptant, peu adaptés
  aux CFD.
- Preuve de persistance 2022-2026 spécifique pour l'effet fin de séance (fonds à levier) : non trouvée.

## 3. Primes de risque : suivi de tendance, portage (carry), prime de volatilité, primes propres aux cryptos, momentum intra-journalier

### Takeaway
Le suivi de tendance reste la prime la plus solide sur longue période, mais ses résultats récents sont maigres :
indice SG Trend +27,3 % en 2022, ~-3 % en 2023, rattrapage modeste en 2024, +2,39 % en 2025 (après -9,3 % en avril),
pour un rendement annuel moyen de ~5,3 % depuis 2000 et une baisse maximale de 20,6 %. Le momentum intra-journalier sur
indice US (méthode « bruit » de Zarattini-Aziz-Barbon) affiche le meilleur rapport rendement/risque publié (1,33 net,
2007-2024) et est compatible avec les coûts FTMO ; en crypto, le suivi de tendance intra-journalier tient (rapport ~1,6
brut, effet ouverture Asie du lundi plus fort depuis mi-2020) mais les résultats nets sont beaucoup plus faibles.

### Cited Findings
**Suivi de tendance / momentum temporel (multi-marchés, gestionnaires « CTA »)**
- SG Trend Index : +27,3 % en 2022 (meilleure performance) — [Hedgeweek](https://www.hedgeweek.com/trend-followers-turn-leaders-ctas-deliver-record-returns-2022/) ;
  2023 : perte de près de 3 % — [The Full FX / Hedgeweek (résumé de recherche)](https://thefullfx.com/year-end-drop-fails-to-dampen-stellar-2022-for-trend-followers/) ;
  2024 : corrélation moyenne entre membres de l'indice 0,78 mais écart de résultats de près de 15 points —
  [SG, « CTA Update: Keeping up with the trend followers 2025 »](https://content.sgmarkets.com/CTA_UPDATE_KEEPING_UP_WITH_THE_TRENDFOLLOWERS_2025)
- 2025 : SG Trend -4,89 % en avril (cumul annuel -9,33 %), cumul -7,56 % fin août, puis rattrapage ; année finie à
  **+2,39 %** (SG Trend), +2,81 % (BTOP50), +1,78 % (indice TTU), contre +17,89 % pour le S&P 500 dividendes compris —
  [Top Traders Unplugged, rapport décembre 2025](https://www.toptradersunplugged.com/trend-following-performance-report-december-2025/) ;
  [rapport avril 2025](https://www.toptradersunplugged.com/trend-following-performance-report-april-2025/) ;
  [The Full FX](https://thefullfx.com/ctas-tough-start-to-2025-continues/)
- Depuis 2000 : SG Trend rendement annuel composé 5,33 %, baisse max 20,61 % ; TTU 7,43 % / 20,93 % ; BTOP50 4,08 % /
  15,94 % ; S&P 500 7,98 % / 50,95 % ; 2025 qualifiée d'« année de transition », baromètre de tendance tombé à 36 —
  [TTU décembre 2025](https://www.toptradersunplugged.com/trend-following-performance-report-december-2025/)
- Hurst, Ooi, Pedersen (AQR, « A Century of Evidence on Trend-Following Investing ») : suivi de tendance rentable depuis
  1880 ; dernière mise à jour trouvée 2017 (données à fin 2016) — [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing?aqrPDF=1) ;
  [PDF](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)
- Données multi-actifs 2005 → mars 2025 : tendance/momentum rapport rendement/risque 0,65-0,80 sur actions et obligations ;
  portage 0,20-0,70 — [Resonanz Capital, « Style Premia: Are They Still Relevant? »](https://resonanzcapital.com/insights/style-premia-are-they-still-relevant)

**Portage (carry) en devises**
- Août 2024 : la hausse de taux de la Banque du Japon (0,10 % -> 0,25 % le 31/07) a déclenché un dénouement massif ;
  ~40 000 milliards de yens (~250 Md$) de positions de portage ; USD/JPY de 162 à 142 en 3 semaines ; les portages
  devises ont été durement touchés — [BIS Bulletin n°90](https://www.bis.org/publ/bisbull90.htm) ;
  [The Full FX](https://thefullfx.com/?p=5176)
- Le portage peso/yen est devenu perdant à l'été 2024 puis de nouveau rentable à partir de mi-2025 ; les spéculateurs
  ont entièrement dénoué leurs positions dans la première quinzaine d'août et étaient acheteurs nets depuis fin 2024 —
  [Banque de France, « Carry trades and volatility risk »](https://www.banque-france.fr/en/publications-and-statistics/publications/carry-trades-and-volatility-risk)

**Prime de volatilité (VIX)**
- La courbe des contrats à terme VIX est en « contango » (pente montante) ~85 % des jours de 1990 à 2025 ; une stratégie
  qui module l'exposition aux produits VIX selon la prime attendue et la pente de la courbe, dimensionnée par le niveau du
  VIX, a obtenu un rapport rendement/risque de 0,729 de janv. 2016 à juil. 2026 —
  [QuantConnect, « Harvesting the volatility risk premium with a dual VIX signal »](https://www.quantconnect.com/research/21143/harvesting-the-volatility-risk-premium-with-a-dual-vix-signal/) ;
  [eco3min](https://eco3min.fr/en/vix-backwardation-contango-volatility-term-structure/)
- Risque de queue : le 5 août 2024, VIX +42 points jusqu'à 65 (un des trois plus grands pics de son histoire avec 2008 et
  2020), Nikkei -12,4 %, S&P 500 -3 % — [BNP Paribas AM](https://www.bnpparibas-am.com/en-sk/front-of-mind/black-monday-5-august-2024-deja-vu-on-5-february-2018/) ;
  février 2018 : le produit inverse XIV passe de 1,9 Md$ à 63 M$ en une séance — [BloombergQuint](https://www.bloombergquint.com/markets/the-day-the-vix-doubled-tales-of-volmageddon)

**Momentum intra-journalier sur indices**
- Gao, Han, Li, Zhou (JFE 2018) : SPY 1993-2013, le rendement de la première demi-heure prédit celui de la dernière ;
  plus fort les jours volatils, à fort volume, en récession et les jours de nouvelles macro ; présent sur 10 autres ETF —
  [PDF](https://c.mql5.com/forextsd/forum/173/intraday_momentum_-_the_first_half-hour_return_predicts_the_last_half-hour_return.pdf) ;
  [WUSTL](https://profiles.wustl.edu/en/publications/market-intraday-momentum/)
- Zarattini, Aziz, Barbon, « Beat the Market » (SFI 24-97, nov. 2024) : entrée dès qu'il y a déséquilibre anormal (prix
  sortant d'une « zone de bruit »), stops suiveurs dynamiques ; SPY 2007 → début 2024 : +1 985 % net de frais, 19,6 %/an,
  rapport rendement/risque 1,33 ; tests sur régimes de volatilité et gamma des teneurs de marché —
  [SFI](https://www.sfi.ch/de/publications/n-24-97-beat-the-market-an-effective-intraday-momentum-strategy-for-s-p500-etf-spy) ;
  [Concretum](https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/) ;
  4e place Quantpedia Awards 2025 — [Univ. Saint-Gall](https://fsi.unisg.ch/de/newsdetail/news/quantpedia-awards-2025-fsis-barbon-and-team-secure-4th-place-with-intraday-momentum-strategy/)
- Le momentum intra-journalier n'existe que si le gamma des teneurs de marché est négatif et se renforce quand il l'est
  davantage — [JFE 2021, Baltussen et al.](https://academicweb.nd.edu/~zda/intramom.pdf)

**Primes crypto (tendance, intra-journalier, cassure)**
- Concretum, « Seasonality in Bitcoin Intraday Trend Trading » (2018-2025) : ensemble de modèles de tendance haute
  fréquence acheteur/vendeur à 20 %/an de volatilité cible ; rapport rendement/risque **brut** ~1,6 contre ~0,8 pour la
  détention de bitcoin à volatilité ciblée ; rendement concentré à partir de dimanche ~19h New York pendant ~24 h
  (ouverture Asie du lundi), effet « nettement plus prononcé » après mi-2020 ; aucun résultat net de frais publié —
  [Concretum](https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/)
- Test sur données réelles d'échanges 2017 → mi-2025 : tendance crypto à 10 % de volatilité cible ≈ **6,3 %/an** après
  frais et glissement — [Summitward (source secondaire)](https://summitward.com/learn/crypto-trend-following)
- Momentum temporel intra-journalier du bitcoin documenté (Reading, article accepté 2021) —
  [Centaur Reading](https://centaur.reading.ac.uk/100181/3/21Sep2021Bitcoin%20Intraday%20Time-Series%20Momentum.R2.pdf)
- Écarts perpétuels/comptant (base du portage « funding ») en diminution dans le temps —
  [He et al. 2024](https://arxiv.org/abs/2212.06888v6)

### Inferences
- Tendance multi-marchés : sur 2023-2025, les indices professionnels ont fait ~0 à +3 %/an : un trader FTMO qui
  copierait « la tendance de fond » doit s'attendre à des années plates et à des baisses de 10-20 % (incompatible avec la
  limite FTMO -10 % à volatilité professionnelle ; il faut viser ~5-8 %/an de volatilité). Cohérent avec le repère
  interne du projet (+0,5 %/mois sur 2018-2025, baisse max 19 %).
- Momentum intra-journalier US500 : c'est le candidat le plus compatible FTMO (aucun portage de nuit, coût ~0,01 % par
  aller-retour, signal gratuit à partir des barres minute). Le rendement net de 19,6 %/an de l'article inclut un effet de
  levier et le coût SPY ; sur CFD, refaire le test avec 0,01 % par aller-retour et le décalage de l'heure de séance.
- Bitcoin : l'effet « ouverture Asie du lundi » de Concretum est cohérent avec la cassure 24 h que le projet fait tourner
  en démo depuis le 16/10 ; avec 0,066 % aller-retour et 30 %/an de portage (~0,08 %/nuit), le passage de brut à net
  coûte cher (cf. ~6,3 %/an net en ciblage 10 %). Ne garder que des détentions de moins de 24 h ou très sélectives.
- Prime de volatilité : FTMO ne propose pas d'options ni le VIX en CFD (à vérifier) ; utilisable seulement comme
  **information** (pente VIX/VIX3M, gratuite sur Cboe) pour réduire la taille en régime inversé, pas comme prime à vendre.
- Portage devises : sur CFD, le portage FTMO est rogné par la marge du courtier (1,5-4 %/an) ; en G10 les écarts de taux
  2025-2026 sont faibles, la prime nette restante est probablement proche de zéro, avec risque de queue type août 2024.

### Gaps
- Chiffres exacts SG Trend / SG CTA 2024 (année complète) non récupérés (seulement « rattrapage »).
- Persistance après publication de Gao-Han-Li-Zhou (2014-2026) : aucune source trouvée.
- Résultats 2024-2026 d'un indice de portage G10 (ex. indice Deutsche Bank G10 Carry) : non récupérés.
- Performance nette du « funding carry » crypto en 2024-2026 : non trouvée.
- Mise à jour AQR post-2022 de « A Century of Evidence » : non trouvée (dernière : 2017).

## 4. Combiner de petits avantages peu corrélés : Sharpe 1+ ? rendement mensuel à risque modéré ?

### Takeaway
Les sources montrent qu'un mélange de primes (tendance, portage, valeur, volatilité) améliore le rapport rendement/risque,
mais les chiffres « proches de 1,3 » sont des projections avant frais ; en réel 2018-2025, les fonds de primes diversifiées
ont fait « modérément bien » et un simple portefeuille actions/obligations a fait mieux sur 5 ans. À 8 % de volatilité
annuelle, un rapport de 0,5-1 correspond à environ +0,3 à +0,7 %/mois.

### Cited Findings
- Projection d'un portefeuille multi-primes à faible exposition au marché : ~10 % de rendement excédentaire, 8 % de
  volatilité, rapport rendement/risque ~1,3 **avant frais de gestion** ; tendance 0,65-0,80, portage 0,20-0,70 sur
  2005-2025 ; les primes « restent robustes » même après le dénouement 2018-2020 —
  [Resonanz Capital](https://resonanzcapital.com/insights/style-premia-are-they-still-relevant)
- Sur 5 ans de faible volatilité et actions fortes, les fonds de primes alternatives ont fait « modérément bien », mais un
  portefeuille équilibré sans diversifiants a fait mieux en absolu et en rendement/risque —
  [Cambridge Associates](https://www.cambridgeassociates.com/en-eu/insight/alternative-risk-premia-a-diversifying-option-for-investors-euro-edition/)
- Exemples de briques individuelles avec un rapport ≥ 1 publiés : momentum intra-journalier SPY 1,33 net
  ([SFI](https://www.sfi.ch/de/publications/n-24-97-beat-the-market-an-effective-intraday-momentum-strategy-for-s-p500-etf-spy)) ;
  tendance intra-journalière bitcoin ~1,6 brut ([Concretum](https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/)) ;
  prime de volatilité VIX à double signal 0,73 ([QuantConnect](https://www.quantconnect.com/research/21143/harvesting-the-volatility-risk-premium-with-a-dual-vix-signal/))

### Inferences
- Calcul simple : rendement mensuel ≈ (rapport annuel × volatilité annuelle) / 12. Avec 8 %/an de volatilité (prudent pour
  la limite FTMO -10 %) : rapport 0,5 -> ~0,33 %/mois ; 1,0 -> ~0,67 %/mois ; 1,5 -> 1 %/mois. Atteindre +10 % pour le
  challenge en quelques mois exige soit un rapport > 2, soit une volatilité qui met la limite -10 % en danger.
- Deux briques intra-journalières (US500 momentum, bitcoin tendance/cassure) + une brique tendance de fond multi-marchés +
  un filtre de régime (pente VIX) sont les plus compatibles coûts FTMO ; si corrélation ~0 et rapport ~0,7 chacune, le
  mélange approcherait ~1,2 (formule √n × rapport moyen) — à vérifier par test, les corrélations montent en crise.
- Les flux forcés (tournant de mois, fin de séance) servent de « réglage du moment » plutôt que de stratégies seules.

### Gaps
- Aucune série réelle (non simulée) trouvée d'un particulier/petit fonds combinant ces signaux sur CFD avec rapport ≥ 1
  en 2022-2026.
- Corrélations mesurées entre momentum intra-journalier, tendance de fond et tendance crypto : non trouvées.

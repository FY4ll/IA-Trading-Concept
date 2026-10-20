# Méthodes concrètes des traders intrajournaliers professionnels — et ce qui est mesuré

Notes de recherche (15/10/2026). Classement des preuves : **PROUVÉ** (test indépendant ou académique, frais compris, hors échantillon), **PLAUSIBLE** (mécanisme documenté ou test partiel, mais pas d'avantage net démontré pour un particulier), **MARKETING** (affirmations de formateurs / sites de vente sans méthode vérifiable).
Remarque générale : beaucoup de sites qui « testent » des méthodes (backtrex, thortradecopier, fortunly, track360…) sont des agrégateurs commerciaux ; leurs chiffres sont signalés comme tels.

## 1. Lecture du flux d'ordres (carnet, bande, « footprint », delta, absorption) — formation en salle de marché

### Takeaway
C'est le cœur de la formation des salles professionnelles (SMB Capital sur actions, Axia Futures sur contrats à terme), mais je n'ai trouvé AUCUNE mesure indépendante de sa rentabilité ; et elle exige le vrai volume échangé et le carnet d'ordres d'une Bourse centralisée, que les CFD forex/or de MetaTrader n'ont pas (seulement un « volume de ticks » = nombre de changements de prix chez le courtier).

### Cited Findings
- SMB Capital = salle de trading new-yorkaise qui forme des débutants ; son école propose un programme de « lecture de la bande » en 6 modules pour déterminer le flux d'ordres sur les actions traitées, et un programme « Winning Trader » de 20 stratégies avec placement possible en salle — [SMB Training](https://smbtraining.com/) ; [NexusFi, fiche SMB](https://nexusfi.com/d/education/smb-training/)
- Axia Futures : école de contrats à terme avec salle de trading, « Career Programme » de 6 semaines centré sur flux d'ordres et profil de volume, société mère régulée FCA — [NexusFi, fiche Axia](https://nexusfi.com/d/education/axia-futures/)
- Forex : marché décentralisé, donc seul le volume de ticks est disponible ; les contrats à terme montrent le vrai volume car centralisés. Le volume de ticks ne voit pas un gros volume échangé à un seul prix (compté comme 1 tick) et diffère d'un courtier à l'autre selon les fournisseurs de liquidité — [EarnForex, guide du volume de ticks](https://www.earnforex.com/guides/tick-volume-in-forex) ; [Trading Wyckoff](https://tradingwyckoff.com/en/tick-volume-vs-real-volume/)
- Une étude de praticien (Caspar Marney, ex-HSBC) annonce ~90 % de corrélation entre le volume de ticks et le volume réellement échangé sur EUR/USD, GBP/USD, USD/JPY, EUR/CHF (corrélation significative surtout en horaire et au-delà) — [étude FXVolume (PDF)](https://c.mql5.com/forextsd/forum/145/fxvolume_tick_volume_vs_real_volume_study_1.pdf) ; [Finance Magnates](https://directory.financemagnates.com/forex-brokers/fp-markets/what-is-forex-trade-volume)

### Inferences
- Le volume de ticks reproduit à peu près « l'activité » (combien ça bouge), pas qui achète et qui vend. Le delta (achats agressifs moins ventes agressives), l'absorption, le « footprint » et la lecture du carnet sont donc **impossibles** à reproduire fidèlement sur des CFD forex/or/indices de MetaTrader. Seuls les profils de volume « à peu près » (répartition de l'activité par niveau de prix) restent possibles avec le volume de ticks.
- Statut : **PLAUSIBLE pour des humains entraînés sur Bourses centralisées, non prouvé**. Les salles de formation ne publient pas de taux de réussite audité de leurs élèves.

### Gaps
- Aucun chiffre public vérifiable sur la proportion de stagiaires SMB / Axia / Jigsaw qui deviennent rentables. Je n'ai pas cherché Jigsaw en détail.
- Pas trouvé d'étude académique testant « l'absorption » ou le delta cumulé comme signal de trading.

## 2. Profil de volume / « market profile » (zone de valeur, prix le plus échangé), VWAP, plus haut/bas de la veille, plage d'ouverture, « balance initiale »

### Takeaway
La cassure de la plage d'ouverture a des tests sérieux : un avantage AVANT frais existe sur les indices, mais une réplication indépendante sur 5 indices en CFD (2015-2026) le trouve nul ou négatif APRÈS écart et glissement. La « balance initiale » et le « market profile » de Dalton n'ont que des statistiques de praticiens, sans test académique trouvé.

### Cited Findings
- Zarattini, Barbon, Aziz (février 2024, « A Profitable Day Trading Strategy For The U.S. Equity Market ») : cassure de la plage des 5 premières minutes, appliquée aux actions à volume anormal du jour (« Stocks in Play ») — [CXO Advisory](https://www.cxoadvisory.com/individual-investing/intraday-trading-of-overactive-stocks-via-opening-range-breakout/)
- Réplication indépendante (Timon-Pascal Krueger, blog MQL5) de la cassure de la plage d'ouverture sur 5 indices (Nasdaq, S&P 500, Dow, DAX, FTSE) de janvier 2015 à juin 2026, ~2 900 séances par marché. Le papier d'origine affichait 24 % de trades gagnants et +0,13 R par trade (33 %/an sur QQQ avec levier 4) mais comptait la commission sans écart ni glissement et sans période hors échantillon. Brut répliqué : Nasdaq +0,131 R (23,2 % gagnants), S&P +0,119 R, Dow +0,048 R, DAX +0,116 R, FTSE +0,050 R. **Net de frais : Nasdaq +0,002 R, S&P -0,081 R, Dow -0,081 R, DAX -0,038 R, FTSE -0,079 R** ; frais supposés (écart + glissement) : Nasdaq 2,5 points, S&P 0,8, Dow 4,0, DAX 2,5, FTSE 1,5. Conclusion de l'auteur : l'avantage directionnel est de la taille de l'écart sur un compte CFD — [MQL5 blog, réplication ORB](https://www.mql5.com/en/blogs/post/776235)
- Holmberg, Lönnbark, Lundström (Umeå, document de travail n° 845) : sur le pétrole brut (contrats à terme), la cassure de la plage d'ouverture donne des rendements significativement supérieurs à zéro et un taux de réussite supérieur à un jeu équitable (chiffres non lus : résumé seulement) — [SWOPEC](https://swopec.hhs.se/umnees/abs/umnees0845.htm)
- Zarattini, Aziz, Barbon (« Beat the Market », SPY, 2007 → début 2024) : suivre la tendance dès qu'un déséquilibre anormal sort d'une « zone de bruit » intrajournalière, avec stops suiveurs dynamiques ; **+1 985 % au total net de frais, 19,6 %/an, ratio rendement/risque 1,33** ; 4e place des Quantpedia Awards 2025 — [Concretum Group](https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/) ; [SFI](https://www.sfi.ch/de/publications/n-24-97-beat-the-market-an-effective-intraday-momentum-strategy-for-s-p500-etf-spy) ; [Université de Saint-Gall](https://fsi.unisg.ch/de/newsdetail/news/quantpedia-awards-2025-fsis-barbon-and-team-secure-4th-place-with-intraday-momentum-strategy/)
- Balance initiale = plage de la première heure de la séance de New York (9h30-10h30 heure de New York), notion de Peter Steidlmayer (market profile). Statistiques de praticiens non vérifiées : prix qui casse et tient hors de la plage des 30 premières minutes atteint 1 fois la plage en extension dans >60 % des cas ; retour au milieu de la balance initiale 65-75 % des jours ; une balance initiale large réduit la probabilité d'une journée d'extension, étroite l'augmente — [Steady Turtle Trading (praticien)](https://steady-turtle-preview.on-forge.com/knowledge/initial-balance-trading-strategy) ; [TradingView, IB Statistical Mapping](https://www.tradingview.com/script/2iuvi66N-Initial-Balance-Statistical-Mapping/)

### Inferences
- **Cassure de plage d'ouverture : PLAUSIBLE (avantage brut réel et répliqué), mais non rentable en CFD une fois l'écart payé** sur le seul indice testé de façon indépendante. Elle ne vaut que si les frais par trade sont nettement plus bas que ~0,1 R (donc stop large par rapport à l'écart, ou contrats à terme).
- **Suivi de tendance intrajournalier sur indice (« Beat the Market ») : PLAUSIBLE-fort** (papier sérieux, frais inclus, 17 ans), mais sur SPY (action cotée, frais très faibles) ; pas trouvé de réplication indépendante sur CFD.
- « Market profile », VWAP, plus haut/bas de la veille : utilisés par tous les praticiens comme **repères** (où sont les autres participants), rarement comme règles testées. Les statistiques « 65-75 % » proviennent de vendeurs d'outils : **MARKETING jusqu'à preuve du contraire**.
- Pour un CFD MetaTrader : la plage d'ouverture, les plus haut/bas de la veille et de la nuit, le VWAP « approché » par le volume de ticks sont calculables ; le profil de volume exact ne l'est pas.

### Gaps
- Pas pu lire le papier de Zarattini & Aziz sur le VWAP (QQQ) ni celui d'Holmberg en entier (chiffres).
- Aucun test académique trouvé du livre de Dalton « Mind over Markets » (types de journées, zone de valeur).

## 3. Trading par séances (ouverture de Londres, de New York, chevauchement, cassure de la plage asiatique) ; « chasse aux stops » / balayage de liquidité

### Takeaway
Le seul fondement académique solide du « balayage de liquidité » est Osler (Réserve fédérale de New York) : les stops se regroupent juste au-delà des chiffres ronds et déclenchent des cascades de prix rapides. En revanche les méthodes « ICT / Smart Money » n'ont aucun test publié relu par des pairs, et la cassure Londres de la plage asiatique sur EUR/USD ressort perdante sur 10 ans dans un test commercial.

### Cited Findings
- Osler : les ordres stop de vente se regroupent juste SOUS les chiffres ronds, les stops d'achat juste AU-DESSUS ; ils créent des achats/ventes en cascade (« price cascades ») ; les tendances du change sont anormalement rapides quand le cours atteint ces niveaux — [NY Fed Staff Report 150](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.html) ; [NY Fed Staff Report 125](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.html) ; [Osler, Stop-loss orders and price cascades](https://icmaif.soc.uoc.gr/Year/8conf/docs/Osler-Price%20Cascades-03-03.doc)
- ICT / Smart Money Concepts : pas d'avantage démontré, aucun test relu par des pairs ; le test le plus systématique (prépublication non relue, 2026) trouve que les balayages de liquidité annoncent une **continuation**, l'inverse de la lecture « retournement » enseignée — [ThorTradeCopier (agrégateur)](https://thortradecopier.com/blog/does-ict-smart-money-concepts-work)
- Site commercial backtrex : affirme un test de 1 247 trades sur EUR/USD et or 2019-2024 (balayage + déplacement + retour dans un « trou de valeur ») avec facteur de profit 1,71 hors échantillon — méthode et frais non vérifiables — [Backtrex](https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results)
- Même site : cassure de Londres sur EUR/USD du 02/10/2016 au 01/10/2026 = -28 % au total (-3,2 %/an), baisse max -31,4 %, 36,3 % de gagnants, facteur de profit 0,87, 1 230 trades — [Backtrex, London breakout EUR/USD](https://backtrex.com/en/backtests/london-breakout-eur-usd)
- Praticien MQL5 : une stratégie de cassure sur EUR/USD gagne entre 8h et 17h (heure de Londres) et rend presque tout la nuit ; la fin d'après-midi new-yorkaise et l'heure du changement de jour sont les plus vides et les plus chères (écarts multipliés) — [MQL5 blog, Londres vs Tokyo](https://www.mql5.com/en/blogs/post/774527)

### Inferences
- **Concentration des stops près des chiffres ronds et accélérations : PROUVÉ (mécanisme)**. L'utiliser pour gagner de l'argent (anticiper la cascade ou le retour) : **non prouvé**.
- **ICT / Smart Money / « kill zones » : MARKETING** (les chiffres positifs viennent d'un vendeur d'outil ; la seule étude systématique contredit la lecture enseignée).
- **Cassure Londres de la plage asiatique : non rentable** dans le seul test trouvé (commercial, donc à prendre avec prudence).
- Fait robuste : l'activité et les écarts dépendent fortement de l'heure ; un trader humain concentre son travail sur Londres et New York.

### Gaps
- Pas d'étude académique trouvée sur la rentabilité des cassures d'ouverture de Londres / New York sur le forex ou l'or.

## 4. Trading des annonces économiques par un humain

### Takeaway
Je n'ai pas trouvé, dans le temps imparti, de mesure de la rentabilité d'un humain qui trade les annonces ; le seul résultat lié est que la tendance intrajournalière (1re demi-heure → dernière demi-heure) est plus forte les jours d'annonces macroéconomiques.

### Cited Findings
- La prévisibilité « 1re demi-heure → dernière demi-heure » est plus forte les jours volatils, à fort volume, en récession et les jours d'annonces macroéconomiques majeures — [Alpha Architect](https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/) ; [WUSTL, Market intraday momentum](https://profiles.wustl.edu/en/publications/market-intraday-momentum/)

### Inferences
- La réaction immédiate (premières secondes) appartient aux machines ultra-rapides ; un humain ne peut au mieux qu'exploiter la suite (continuation de la journée). Statut : **PLAUSIBLE pour la continuation, non mesuré pour le reste**. Sur CFD, les écarts s'élargissent fortement à l'annonce.

### Gaps
- Pas de source trouvée sur un humain ou un fonds qui publie un historique vérifié de trading d'annonces ; pas lu Andersen-Bollerslev (« Micro effects of macro announcements »).

## 5. Retour à la moyenne contre tendance en intrajournalier ; journées de tendance contre journées de range

### Takeaway
La preuve académique la plus solide en intrajournalier va du côté de la TENDANCE sur les indices : le rendement de la 1re demi-heure prédit celui de la dernière demi-heure (Gao-Han-Li-Zhou, JFE 2018), et le suivi de tendance intrajournalier sur SPY (Concretum) tient sur 17 ans. Les tests massifs de règles techniques « tout venant » en intrajournalier ne trouvent rien après correction du « sur-ajustement ».

### Cited Findings
- Gao, Han, Li, Zhou (Journal of Financial Economics, 2018), SPY 1993-2013 : acheter si la 1re demi-heure monte, vendre si elle baisse, position sur la dernière demi-heure : **6,67 %/an, ratio rendement/risque 1,08 contre 0,29 pour l'achat-conservation** ; existe aussi sur 10 autres fonds cotés très échangés ; expliqué par le rééquilibrage tardif et les informés tardifs — [Alpha Architect](https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/) ; [WUSTL](https://profiles.wustl.edu/en/publications/market-intraday-momentum/)
- Marshall, Cahan, Cahan (Journal of Empirical Finance 2008) : 7 846 règles (filtres, moyennes mobiles, supports/résistances, cassures de canal, volume) sur SPDR en 5 minutes, 2002-2003 ; avant correction, 42 règles significatives à 1 % et 163 à 5 % (cassures de canal les meilleures) ; **après correction du biais de fouille des données : aucune des 7 846 règles n'est rentable** — [CXO Advisory](https://cxoadvisory.com/technical-trading/technical-analysis-anathema-to-the-academic-world) ; [IDEAS/RePEc](https://ideas.repec.org/a/eee/empfin/v15y2008i2p199-210.html)
- Neely & Weller (2003) : règles techniques intrajournalières sur le change (programme génétique et modèle linéaire optimisé) : **aucun rendement excédentaire hors échantillon une fois les frais réalistes et les heures de trading pris en compte**, malgré des régularités stables découvertes — [Neely & Weller, JIMF](https://gpbib.cs.ucl.ac.uk/gp-html/neely_2003_JIMF.html) ; [RePEc](https://ideas.repec.org/p/fip/fedlwp/1999-016.html)
- Hsu, Taylor, Wang (Journal of International Economics 2016), 21 195 règles sur 30 devises, 1971-09/2015 : prévisibilité réelle, mais **pour les grandes devises, quelques règles fiables dans les années 1980 et aucune depuis 1992-1996** ; émergentes plus persistantes (10 sur 21 prévisibles) ; hors échantillon 2012-2015 : ratio rendement/risque moyen 0,55 émergentes, 0,03 à 0,54 grandes devises ; écart moyen 0,045 % (grandes) et 0,21 % (émergentes) par sens — [CXO Advisory](https://cxoadvisory.com/technical-trading/updated-comprehensive-long-term-test-of-technical-currency-trading) ; [WUSTL](https://profiles.wustl.edu/en/publications/technical-trading-is-it-still-beating-the-foreign-exchange-market/)

### Inferences
- **Tendance intrajournalière sur indices boursiers : PROUVÉ (académique, frais faibles)**, gain modeste ; transposition aux CFD d'indices non testée ici.
- **Règles techniques intrajournalières génériques (actions, change) : réfutées** après frais et correction du sur-ajustement ; les avantages techniques sur grandes devises ont disparu depuis les années 1990 (décroissance après publication / apprentissage du marché).
- Classement journée de tendance / journée de range par l'ouverture ou la balance initiale : utilisé par les praticiens (Dalton), non testé académiquement dans ce que j'ai trouvé.

### Gaps
- Pas de source académique trouvée sur le retour à la moyenne intrajournalier rentable après frais sur forex/or.
- Revue Park & Irwin (2007) non lue dans cette session.

## 6. Témoignages vérifiables (Market Wizards, championnats) et réalité statistique des day traders

### Takeaway
Les grandes bases de données complètes (Taiwan, Brésil) montrent que moins de 1 % des day traders sont rentables de façon prévisible ; les gagnants de championnats existent (Robbins World Cup) mais sur des comptes petits, courts et très risqués, ce qui ne prouve pas une méthode reproductible.

### Cited Findings
- Barber, Lee, Liu, Odean (Taiwan, données complètes 1992-2006, ~360 000 day traders) : **moins de 1 % gagnent de façon prévisible et régulière après frais** ; 84,3 % perdent (médiane -8,7 %) ; les 500 meilleurs gagnent 61,3 points de base/jour avant frais (37,9 après) ; plus de 75 % abandonnent en moins de 2 ans ; 74 % du volume vient de traders ayant un historique de pertes ; 97 % devraient perdre à l'avenir — [CXO Advisory](https://www.cxoadvisory.com/individual-investing/do-day-traders-make-money/) ; [Barber et al. (PDF Berkeley)](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf)
- Chague, De-Losso, Giovannetti (Brésil, mini-contrats Ibovespa, tous les débutants 2013-2015, 19 646 personnes) : **97 % de ceux qui persistent plus de 300 jours perdent** ; 1,1 % gagnent plus que le salaire minimum, 0,5 % plus qu'un guichetier de banque ; le meilleur gagne 310 $/jour avec un écart-type de 2 560 $ ; aucun signe d'apprentissage — [SSRN « Day Trading for a Living? »](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101) ; [FGV](https://repositorio.fgv.br/items/e87d04fc-4b4c-4a56-ab5a-1c84c1afde1b/full)
- Robbins World Cup (contrats à terme, compte réel) : Andrea Unger seul quadruple vainqueur (672 % en 2008, 115 % en 2009, 240 % en 2010) ; Michael Cook 250 % (2007) et 366 % (2014) ; Larry Williams détient le plus gros gain historique — [Unger Academy](https://ungeracademy.com/blog/the-ultimate-guide-to-joining-the-world-cup-trading-championships-tips-from-a-4-time-winner) ; [MoneyShow](https://moneyshow.com/expert/4b59bbbbde6848cc95f06815f24557c2) ; [iReallyTrade, palmarès](https://www.ireallytrade.com/halloffame)

### Inferences
- Les gains de championnat (centaines de %) supposent une prise de risque incompatible avec les règles FTMO (-5 %/jour, -10 % au total). Gagner un concours parmi des centaines de participants est aussi en partie un effet de sélection.
- Le petit groupe gagnant de Taiwan (« top 500 ») montre qu'une compétence existe, mais rare.

### Gaps
- Pas eu le temps de rassembler les entretiens « Market Wizards » des traders court terme (Marty Schwartz, Linda Raschke, Tom Baldwin…) avec sources ; le chiffre « 11 376 % » de Larry Williams (1987) n'a pas été confirmé dans les résultats.
- Pas de source sur Steenbarger.

## 7. Gestion du risque des traders financés et statistiques des sociétés de financement

### Takeaway
Les chiffres publiés ou relayés indiquent ~5-14 % de réussite aux challenges (FTMO ~9-10 %) et seulement ~7 % des participants qui touchent un paiement ; le paiement moyen ≈ 4 % de la taille du compte. Je n'ai pas trouvé de source primaire fiable sur le profil « gagnants » (taux de réussite × gain/perte) des traders financés.

### Cited Findings
- Taux de réussite des challenges 5-14 % selon la société, 12,3 % sur les programmes suivis par Track360 (2025-2026) ; FTMO ~9-10 % ; Topstep : 16,8 % des « Trading Combines » réussis en 2025 (mais 51,8 % des participants ont réussi au moins une fois) ; Earn2Trade 8,89 % ; seuls ~7 % des traders touchent un paiement (45 % de ceux qui réussissent) ; 33 % des comptes financés Topstep payés ; paiement moyen ≈ 4 % du compte ; partage des gains annoncé 80-90 % en 2026 — [Track360 (agrégateur)](https://track360.io/blog/prop-trading-industry-statistics-2026) ; [The Prop Firm Guide (agrégateur)](https://thepropfirmguide.com/prop-firm-statistics/) ; [TradeInformer sur les finances de FTMO](https://www.tradeinformer.com/prop-weekly/what-ftmo-tells-us-about-prop-firm-finances)
- Exemple de structure gagnante publiée : la cassure de plage d'ouverture a 20-24 % de trades gagnants pour +0,05 à +0,13 R par trade brut — c'est-à-dire petit taux de réussite et gros gains (tendance) — [MQL5 blog, réplication ORB](https://www.mql5.com/en/blogs/post/776235)

### Inferences
- Pour un compte FTMO, le danger principal n'est pas l'absence de méthode mais le budget de perte : avec ~0,1 R d'avantage brut, l'écart CFD suffit à tout annuler (section 2). Donc les frais par trade (en R) sont LE critère qui sépare une méthode testable d'une méthode perdante.
- Les règles courantes chez les professionnels (stop journalier, risque fixe par trade en R, arrêt après plusieurs pertes) sont des protections de compte cohérentes avec FTMO, mais je n'ai pas de source mesurant qu'elles augmentent la rentabilité.

### Gaps
- Pas de source primaire (FTMO, Topstep) consultée directement : les chiffres viennent d'agrégateurs ; à prendre comme ordres de grandeur.
- Pas trouvé de données sur les règles de risque typiques (0,25-1 %/trade, -2 %/jour…) des traders financés rentables avec une source vérifiable.
- Kevin Davey et Quantified Strategies non consultés (tests de méthodes de détail).

## 8. Synthèse : tableau de classement

| Méthode | Données nécessaires | Dispo sur CFD MetaTrader ? | Statut de preuve |
|---|---|---|---|
| Lecture du carnet / bande / delta / absorption | Vrai volume + carnet (Bourse centralisée) | Non | Plausible pour humains formés, aucune mesure publique |
| Profil de volume / market profile | Volume par prix | Approché (volume de ticks) | Repère de praticien, pas de test |
| Plage d'ouverture (cassure) | Prix | Oui | Avantage brut répliqué (+0,05 à +0,13 R) ; **net ≈ 0 ou négatif en CFD** |
| Tendance intrajournalière indice (1re → dernière demi-heure ; Concretum) | Prix | Oui | **Prouvé (académique, SPY)**, non répliqué en CFD |
| Balance initiale / types de journée (Dalton) | Prix | Oui | Statistiques de vendeurs d'outils |
| Cassure Londres de la plage asiatique | Prix | Oui | Perdante sur EUR/USD 10 ans (test commercial) |
| Concentration des stops aux chiffres ronds (Osler) | Prix | Oui | **Mécanisme prouvé**, exploitation non prouvée |
| ICT / Smart Money / balayages | Prix | Oui | Marketing ; seule étude systématique contredit la théorie |
| Règles techniques intrajournalières génériques | Prix | Oui | **Réfutées** après frais (Marshall 2008, Neely-Weller 2003, Hsu 2016 pour grandes devises) |
| Trading d'annonces (humain) | Calendrier + prix | Oui | Non mesuré |

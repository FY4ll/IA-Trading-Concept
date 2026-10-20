# Sociétés de financement de traders (« prop firms ») 2025-2026 pour une IA de trading suisse/française, et ce que font les traders financés qui durent

Notes de recherche du 18/10/2026. Toutes les règles changent souvent (plusieurs changements en septembre-octobre 2026) : chaque règle est datée quand la source le permet. « Non vérifié » = une seule source secondaire, ou source en contradiction.

## A. Quelles sociétés acceptent une IA / un programme automatique, et à quelles conditions ?

### Takeaway
FTMO reste la plus solide et autorise les programmes maison, mais sa clause « logiciel / intelligence artificielle donnant un avantage déloyal » est floue et elle plafonne à 400 000 $ par trader OU par stratégie. Depuis 2026, plusieurs grandes sociétés ont fermé la porte aux programmes (FundedNext au-delà de 50 000 $ en CFD depuis septembre 2026, Apex et Take Profit Trader en contrats à terme) ; les plus claires pour un programme maison sont FTMO (CFD et contrats à terme), E8 Markets (CFD), The5ers (CFD, code source à soi), Breakout/Kraken et HyroTrader (crypto), et côté contrats à terme Lucid, MyFundedFutures, FundedNext Futures, FTMO Futures.

### Cited Findings

**FTMO (Tchéquie ; règles CFD)**
- Règles officielles 2 étapes : objectif 10 % puis 5 %, perte du jour max 5 % du capital initial calculée depuis le solde de minuit (heure de Prague), violée si les « equity » (valeur en cours, positions ouvertes comprises) passent dessous ; perte max STATIQUE 10 % du capital initial ; au moins 4 jours de trading ; pas de règle de régularité en 2 étapes — [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/)
- 1 étape : objectif 10 %, perte du jour 3 %, perte max 10 % SUIVEUSE en fin de journée (plus haut solde de clôture moins 10 %, ne descend jamais, remise à zéro après un retrait), pas de minimum de jours ; règle de régularité (« le meilleur jour ne doit pas dépasser 50 % du gain total ») pour les comptes commandés à partir du 12/10/2026 (une autre source dit 05/10/2026) — [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/) ; [Recherche, résumé tradetanto/jptradingcapital](https://tradetanto.com/learn/ftmo-rules-evaluation-process)
- Contradiction : un article de février 2026 indique pour le 1 étape une perte max de 6 % — [TheTrustedProp, 06/02/2026](https://thetrustedprop.com/blogs/ftmo-1-step-challenge-simply-explained) ; la page officielle actuelle dit 10 % suiveuse. Retenir la page officielle (règle probablement changée en 2026).
- Prix 1 étape (février 2026) : 10 k = 155 €, 25 k = 250 €, 50 k = 345 €, 100 k = 540 €, 200 k = 1 080 € ; frais remboursés avec la première récompense ; partage 80 %, 90 % via le plan d'agrandissement ; premier retrait après deux semaines — [TheTrustedProp](https://thetrustedprop.com/blogs/ftmo-1-step-challenge-simply-explained). Fourchette de prix 79-499 € citée ailleurs pour le 2 étapes (non vérifié, probablement ancien) — [PickMyTrade](https://blog.pickmytrade.trade/best-prop-firms-algo-trading-bots-2026/)
- Plafond : « la somme des comptes, tous produits confondus, est limitée à 400 000 $ par trader OU PAR STRATÉGIE (avant agrandissement) » = 320 000 € = 320 000 CHF ; nombre de comptes illimité ; suspension si un trading « identique ou très semblable » est détecté sur plusieurs comptes au-delà du plafond, y compris copié d'une même source ; plafond relevé par le « Premium Programme » — [FTMO FAQ, modifiée le 30/09/2026](https://ftmo.com/en/faq/how-many-accounts-can-i-have/)
- Pratiques interdites (page modifiée le 12/10/2026), citations exactes : « use any software, artificial intelligence, ultra-high-speed tools, or mass data entry that might manipulate, abuse, or give you an unfair advantage » ; robots/EA rendant le compte « hyperactif » : « more than 2,000 server requests per day » ; pratique des écarts d'ouverture : ouvrir des positions quand des nouvelles macro majeures / résultats d'entreprises sont prévus, ou « two hours or less before a relevant financial market is closed for at least two hours » ; interdiction de laisser un tiers accéder au compte ; positions opposées entre comptes à but manipulateur ; répartir artificiellement le gain sur plusieurs jours — [FTMO Forbidden Trading Practices](https://ftmo.com/en/forbidden-trading-practices/)
- Un résumé secondaire ajoute « plus de 200 ordres ouverts en même temps » comme seuil d'hyperactivité (non retrouvé mot pour mot sur la page officielle) — [PickMyTrade blog](https://blog.pickmytrade.io/what-ea-are-banned-on-ftmo/)
- Frais : environ 3 $ par lot aller-retour sur devises, pas de commission sur métaux, indices, énergies ; 0,0325 % par côté sur cryptos ; nouveaux contrats « roulants » sans échéance sur US500/US100/US30/USOIL depuis le 30/01/2026, avec frais de nuit (triple le mercredi) ; effet de levier 1:100 (compte Normal), environ 1:30 compte « Swing » — [Propvator, conditions FTMO](https://propvator.com/blog/ftmo-trading-conditions/) (secondaire, cohérent avec la commission crypto 0,0325 % déjà constatée dans le projet)
- FTMO Futures : programmes automatiques explicitement autorisés, programme d'un tiers = risque de refus, serveur distant (VPS) autorisé, limites de nombre d'ordres via l'interface ; 119-139 $/mois pour 50 k (FAQ du 09/04/2026) — [Prop-memo, septembre 2026](https://prop-memo.com/en/articles/futures-prop-firms-automation-2026-09)
- Santé : chiffre d'affaires 2025 = 422,4 M$ (+31 %), résultat brut d'exploitation 75 M$, 1,27 million de commandes payées, 1,40 million d'inscriptions, ~80 % du chiffre fait par des clients qui reviennent, 4,8/5 sur Trustpilot (48 000 avis) ; rachat du courtier régulé OANDA pour 421,9 M$ (fin décembre 2025) — [FX News Group, 08/09/2026](https://fxnewsgroup.com/forex-news/retail-forex/ftmo-2025-revenues-rise-31-to-422m-paid-422m-for-oanda/)
- Paiements aux traders 2025 = 176,3 M$ (non vérifié, résumé d'un article TradeInformer) — [TradeInformer](https://tradeinformer.com/?p=14593) ; « plus de 450 M$ » cumulés depuis le début selon la direction — [Finance Magnates, 06/01/2026](https://financemagnates.com/forex/prop-firm-match-tracked-about-325-million-in-payouts-to-traders-in-2025)

**The5ers (Israël ; CFD)**
- High Stakes : objectif 8 % puis 5 % (Classic) ou 10 % (New), perte du jour 5 %, perte max 10 %, au moins 3 jours gagnants par phase, pas de limite de temps ; 10 % puis 20 % des frais deviennent des crédits non retirables, 70 % des frais remboursables avec le premier paiement — [Recherche : propfirmbridge / traderssecondbrain](https://propfirmbridge.com/education/the5ers-high-stakes-review-new-classic-prices-rules-bridge)
- Programmes autorisés si le trader possède le code source ; interdits : copier les signaux d'un autre, cueillette de quelques points, arbitrage de latence, haute fréquence, émulateurs — [Recherche The5ers rules](https://lunefi.com/blog/the5ers-rules) ; détection d'un « même programme » entre comptes — [NewYorkCityServers](https://newyorkcityservers.com/blog/best-prop-firms-ea-trading)
- The5ers Futures : « Algorithmic trading strictly forbidden » — [Prop-memo](https://prop-memo.com/en/articles/futures-prop-firms-automation-2026-09)
- Pays exclus : liste de sanctions + quelques pays d'Afrique/Asie + Israël ; ni la France ni la Suisse n'y figurent — [SurgeFunded, pays The5ers](https://www.surgefunded.com/the5ers-supported-and-restricted-countries/) (secondaire)

**FundedNext (Émirats ; CFD + contrats à terme)**
- Septembre 2026 : pour les comptes CFD de 50 000 $ et plus, trading MANUEL obligatoire, aucun programme automatique (challenge et compte financé) ; en dessous de 50 000 $, programmes permis sur MT4/MT5 seulement avec une option payante ; interdits sur cTrader et Match-Trader ; confirmé le 27/09/2026 — [Recherche, prop-memo / propfirmbriefing](https://prop-memo.com/en/firms/fundednext)
- FundedNext Futures : programmes autorisés (challenge et compte financé), haute fréquence, grille, arbitrage de latence interdits (aide du 09/04/2026) — [Prop-memo](https://prop-memo.com/en/articles/futures-prop-firms-automation-2026-09)
- Plus gros payeur suivi par Prop Firm Match en 2025 : 107,8 M$ (CFD) + 46,9 M$ (contrats à terme) — [Finance Magnates](https://financemagnates.com/forex/prop-firm-match-tracked-about-325-million-in-payouts-to-traders-in-2025)

**FundingPips (Émirats ; CFD)**
- Programmes d'un tiers seulement pour gérer les trades / le risque ; programme fait soi-même = automatisation complète permise avec preuve de propriété ; interdits : haute fréquence, latence, cueillette de points, écarts d'ouverture, « bombardement » du serveur — [PickMyTrade, FundingPips](https://blog.pickmytrade.io/fundingpips-review-rules-payouts-automation/) (secondaire)
- 97,1 M$ payés en 2025 (Prop Firm Match) — [Finance Magnates](https://financemagnates.com/forex/prop-firm-match-tracked-about-325-million-in-payouts-to-traders-in-2025) ; 4,5/5 sur plus de 64 000 avis Trustpilot — [Recherche Trustpilot FundingPips](https://www.trustpilot.com/review/fundingpips.com)

**E8 Markets (États-Unis ; CFD)**
- Programmes permis (y compris doublement des mises), une seule stratégie par personne, limite 2 000 requêtes et 2 000 positions par jour, stratégie « 100 % unique à vous » ; nouvelles : interdit 5 min avant/après une annonce majeure sur compte financé ; objectif 8 %, perte du jour 4-5 %, perte max 8 % — [NewYorkCityServers](https://newyorkcityservers.com/blog/best-prop-firms-ea-trading) ; [EAFunded](https://www.eafunded.com/firms/e8-markets) ; [PickMyTrade tableau](https://blog.pickmytrade.trade/best-prop-firms-algo-trading-bots-2026/)
- E8 Futures : programmes et outils d'IA interdits, haute fréquence = plus de 300 trades/jour (16/08/2026) — [Prop-memo](https://prop-memo.com/en/articles/futures-prop-firms-automation-2026-09)
- ~19 M$ payés en 2025 — [Finance Magnates](https://financemagnates.com/forex/prop-firm-match-tracked-about-325-million-in-payouts-to-traders-in-2025)

**Blue Guardian, Alpha Capital, autres CFD**
- Blue Guardian : objectif 9 % (phase 1), perte du jour 4 %, perte max 6 %, 3 jours gagnants, 85 % (90 % en option), paiement tous les 14 jours ; programmes autorisés en CFD, semi-automatique seulement en contrats à terme ; 149-999 $ — [Recherche Blue Guardian](https://propfirmtrader.com/prop-firm/blue-guardian) ; [PickMyTrade](https://blog.pickmytrade.trade/best-prop-firms-algo-trading-bots-2026/)
- FunderPro : programmes faits soi-même seulement — [PickMyTrade](https://blog.pickmytrade.trade/best-prop-firms-algo-trading-bots-2026/)
- The Trading Pit : programmes personnels, VPS permis, jusqu'à 5 comptes — [Prop-memo](https://prop-memo.com/en/articles/futures-prop-firms-automation-2026-09)
- Alpha Capital : 5 % jour / 10 % max cités ; politique sur les programmes NON TROUVÉE — [Propsurvivalengine](https://propsurvivalengine.com/compare/alpha-capital-group-vs-blue-guardian)

**Crypto**
- Breakout (racheté par Kraken, finalisé le 04/09/2025) : 1 étape objectif 9/10/12 %, 2 étapes 5 % + 10 %, perte du jour 3-4 %, perte max 6 % statique, pas de minimum de jours, pas de limite de temps, 80 % (90 % en option), paiement à la demande, levier 5:1 BTC/ETH, 2:1 autres, 62 paires, jusqu'à 200 000 $ — [Kraken Learn, 29/04/2026](https://www.kraken.com/learn/breakout-vs-hyrotrader) ; [BusinessWire](https://www.businesswire.com/news/home/20250904012956/en/Kraken-Completes-Major-Acquisition-of-Breakout-to-Offer-Prop-Trading-to-Clients-Globally) ; programmes permis, interdits : haute fréquence, latence, couverture entre comptes, copie de signaux — [Recherche velotrade/edgeable](https://velotrade.com/blog/algo-bot-trading-crypto-prop-firm)
- HyroTrader (sur Bybit) : 70 % puis +5 % tous les 4 mois jusqu'à 90 %, 2 étapes 10 % + 5 %, perte du jour 4-5 % suiveuse, perte max 10 % statique, stop OBLIGATOIRE sous 5 minutes, 10-15 jours minimum, retrait max 5 % du solde, jusqu'à 1 M USDT, 700+ paires — [Kraken Learn](https://www.kraken.com/learn/breakout-vs-hyrotrader) (source concurrente, à recouper). Programmes via clé d'interface Bybit, MAIS l'article 10.2(e) des conditions interdit les programmes « sauf permission expresse dans les règles de trading », qui n'en parlent pas : CONTRADICTION à faire confirmer par écrit — [Recherche edgeable / sizeprop](https://edgeable.app/perpetuals/perp-prop-firms/)
- Crypto Fund Trader : programmes permis ; interdits haute fréquence, cueillette, arbitrage, programmes « sur les nouvelles », stratégies entre comptes — [Recherche CFT](https://cryptofundtrader.com/evaluation-rules/)

**Contrats à terme (États-Unis, marché CME)** — état septembre 2026 — [Prop-memo, 28 sociétés](https://prop-memo.com/en/articles/futures-prop-firms-automation-2026-09)
- Automatique complet permis : Lucid (copieurs permis ; alerte si >50 % du gain vient de trades tenus ≤5 s), FTMO Futures, FundedNext Futures, MyFundedFutures (« réglages à vous », réouvert le 23/07/2025), BluSky (interdit « exploitation par IA »), Funded Futures Network.
- Programme maison sous conditions : Topstep (via l'interface TopstepX, +29 $/mois, VPS/VPN/serveurs distants INTERDITS, pas d'interface sur compte réel ; 49 $/mois + 149 $ d'activation pour 50 k), Tradeify (vidéo en direct de vous lançant le code sur votre PC), Bulenox (outils personnels seulement, +100 $/mois si logiciel tiers), TradeDay (VPS interdit).
- INTERDIT : Apex Trader Funding (« No Automation or Algorithm Usage allowed » sur tous les comptes, confirmé 21/09/2026 ; changement par rapport à mai), Take Profit Trader (06/03/2026), The5ers Futures, E8 Futures, Elite Trader Funding (reprise des gains sur 12 mois en cas de violation), Alpha Futures (semi-automatique seulement).
- Contradiction : PickMyTrade indique « Apex : programmes permis (sauf anciens comptes) » — [PickMyTrade](https://blog.pickmytrade.trade/best-prop-firms-algo-trading-bots-2026/) ; Prop-memo (plus récent, 21/09/2026) dit interdit. Retenir « interdit » jusqu'à vérification.
- Coût d'un micro-contrat S&P 500 (MES) aller-retour : 1,22 $ chez Topstep et chez Interactive Brokers (dont 0,70 $ de frais de bourse CME), 0,72 $ chez MetroTrade ; 0,80-1,50 $ en général — [Recherche PickMyTrade / NexusFi](https://blog.pickmytrade.io/ibkr-api-cost-every-charge-itemised-2026/) ; [Topstep, frais](https://help.topstep.com/en/articles/8284213-what-are-the-commissions-and-fees-in-the-trading-combine-and-express-funded-account)

**Réputation, fermetures, régulation**
- Février 2024 : MetaQuotes (MT4/MT5) retire les licences de sociétés servant des clients américains ou sans courtier en règle ; 80 à 100 sociétés fermées entre février 2024 et fin 2025 — [Recherche dealpropfirm / thepropfirmguide](https://thepropfirmguide.com/prop-firms-that-shut-down/)
- True Forex Funds : licence MetaQuotes retirée (synchronisation via un prestataire tiers), faillite déclarée le 14/05/2024, ~1,2 M$ dus à ~300 traders — [FX News Group](https://fxnewsgroup.com/forex-news/retail-forex/exclusive-prop-trading-firm-true-forex-funds-shut-down-by-metaquotes-move/) ; [Medium/OFP](https://medium.com/@OFPFunding/true-forex-funds-ceases-operations-due-to-financial-insolvency-cb2f5143dc59)
- The Funded Trader : pause le 28/03/2024, >2 M$ de paiements refusés reconnus ; SurgeTrader fermé le 24/05/2024 — [Recherche thepropfirmguide](https://thepropfirmguide.com/prop-firms-that-shut-down/)
- MyForexFunds : poursuite de l'autorité américaine des marchés à terme (CFTC, 2023) rejetée définitivement le 13/05/2025, la CFTC condamnée à ~3,1 M$ pour mauvaise foi (preuve à décharge cachée) — [DeSilva Law](https://www.desilvalawoffices.com/articles/blog/2025/may/cftc-case-dismissed-my-forex-funds-controversy-h/) ; retour annoncé en 2026 (non vérifié) — [JoinProp](https://joinprop.com/prop-news/myforexfunds-returns-after-two-years-of-silence-as-cftc-case-gets-dismissed/)
- FundingTicks se retire après baisse des partages et nouvelles limites — [Finance Magnates](https://www.financemagnates.com/forex/following-profit-cuts-and-trading-limits-prop-firm-fundingticks-begins-winding-down/) ; YRM Prop a arrêté de vendre mi-septembre 2026, paiements retardés — [Prop-memo](https://prop-memo.com/en/articles/futures-prop-firms-automation-2026-09)

**Pays (Suisse / France)**
- FTMO publie un plafond en CHF (320 000 CHF), signe que la Suisse est servie — [FTMO FAQ](https://ftmo.com/en/faq/how-many-accounts-can-i-have/)
- Certaines sociétés de contrats à terme excluent la France et/ou la Suisse (listes PropFirmMatch, page bloquée à la lecture) — [PropFirmMatch Suisse](https://propfirmmatch.com/prop-firm-lists/restricted-countries/switzerland) ; [PropFirmMatch France](https://propfirmmatch.com/futures/prop-firm-lists/restricted-countries/france) ; MyFundedFutures a suspendu plus de 20 pays (liste non lue) — [Finance Magnates via TradingView](https://vn.tradingview.com/news/financemagnates%3A751fbec6b094b%3A0-prop-firm-myfundedfutures-overhauls-affiliate-program-and-suspends-over-20-countries)

### Inferences
- Tableau de synthèse (à partir des sources ci-dessus ; « ? » = non trouvé) :

| Société | Marchés | Programme maison | Perte jour / perte max | Partage | Remarque clé |
|---|---|---|---|---|---|
| FTMO 2 étapes | CFD (devises, métaux, indices, énergies, crypto) | Oui, mais clause « IA / avantage déloyal », 2 000 requêtes/jour | 5 % / 10 % statique | 80→90 % | 400 k$ max par trader OU stratégie ; frais remboursés |
| FTMO 1 étape | idem | idem | 3 % / 10 % suiveuse fin de journée | 80→90 % | règle de régularité 50 % depuis oct. 2026 |
| The5ers High Stakes | CFD | Oui si code source à soi | 5 % / 10 % | ? | 70 % des frais rendus |
| FundedNext CFD | CFD | Seulement < 50 k$, option payante (sept. 2026) | selon offre | jusqu'à 95 % | gros payeur 2025 |
| FundingPips | CFD | Maison seulement, preuve | ? | ? | 4,5/5 Trustpilot |
| E8 Markets | CFD | Oui, 2 000 requêtes/jour, unique | 4-5 % / 8 % | 80→100 % | nouvelles interdites ±5 min en financé |
| Blue Guardian | CFD | Oui (CFD) | 4 % / 6 % | 85-90 % | paiement 14 jours |
| Breakout (Kraken) | crypto | Oui (pas haute fréquence) | 3-4 % / 6 % statique | 80-90 % | levier 5:1 seulement |
| HyroTrader (Bybit) | crypto | Ambigu (contrat vs règles) | 4-5 % suiveuse / 10 % | 70→90 % | stop obligatoire sous 5 min |
| FTMO Futures | CME | Oui, VPS permis | ? | ? | 119-139 $/mois |
| Topstep | CME | Oui via interface payante, pas de VPS | suiveuse | 100 % des premiers 10 k$ | mieux documenté en chiffres |
| Apex / Take Profit Trader | CME | NON (2026) | suiveuse | — | à écarter |
| Tradeify | CME | Maison, vidéo de lancement | ? | ? | contraignant |

- Seules FTMO et E8 donnent un seuil chiffré (2 000 requêtes/jour) ; une IA qui décide une fois par bougie de 15 min sur quelques dizaines de marchés reste très loin de ce seuil. La phrase « logiciel, intelligence artificielle… avantage déloyal » vise surtout la manipulation et la vitesse, mais elle laisse FTMO juge : d'où l'intérêt de demander une confirmation écrite avant de payer (déjà noté dans la mémoire du projet).
- Les sociétés de contrats à terme ne sont pas « meilleures » par principe pour une IA : la moitié interdisent l'automatique en 2026, et Topstep interdit les serveurs distants (le PC doit rester allumé chez soi, ce qui est le cas du projet). Avantage réel : frais transparents (~1 $ aller-retour par micro-contrat) et marché centralisé ; inconvénient : la perte max suiveuse.
- Pour une IA qui trade le bitcoin : la commission FTMO 0,0325 %/côté (0,065 % aller-retour) est le principal frein mesuré dans le projet ; Breakout et HyroTrader passent par de vrais carnets d'ordres (Kraken/Bybit) mais leurs frais n'ont pas été trouvés dans les sources lues.

### Gaps
- Pas pu lire les listes de pays exclus (PropFirmMatch bloqué, erreur 403) : vérifier France/Suisse société par société dans les conditions officielles.
- Prix FTMO 2 étapes 2026 et détail du plan d'agrandissement (+25 % tous les 4 mois ?) non confirmés sur page officielle lue.
- Frais de trading Breakout / HyroTrader / Crypto Fund Trader non trouvés.
- Politique d'Alpha Capital Group sur les programmes non trouvée ; prix et règles de Tradeify, Take Profit Trader et Apex non détaillés.
- Aucune note Trustpilot récente lue pour The5ers, E8, Blue Guardian, Topstep.

## B. Statistiques publiées : réussite, paiements, et ce qui distingue les traders qui durent

### Takeaway
Ordre de grandeur cohérent entre sources : environ 1 trader sur 7 passe l'examen et environ 1 sur 14 touche au moins un paiement, d'en moyenne ~4 % de la taille du compte ; Topstep est la seule grande société qui publie des chiffres officiels détaillés. Aucune source solide ne prouve un « profil type » du trader qui dure (risque, durée de détention) : ce sont surtout des conseils.

### Cited Findings
- Étude FPFX Tech (fournisseur technique de 10 sociétés) : 300 000 comptes, 100 000 traders ; 14 % passent, ~45 % de ceux-là sont payés, donc 7 % de tous les traders touchent un paiement ; paiement moyen ≈ 4 % de la taille du compte (4 000 $ sur 100 000 $) ; un trader dépense en moyenne ~800 $ en examens (environ 3 examens) — [Finance Magnates](https://financemagnates.com/forex/analysis/exclusive-only-7-of-300000-prop-trading-accounts-achieved-payouts)
- Topstep, chiffres officiels 2025 : 16,8 % des examens démarrés réussis ; 51,8 % des PERSONNES passent au moins une fois ; 33,3 % des personnes en compte financé reçoivent un paiement ; 0,71 % appelés en compte réel (dénominateurs différents, non combinables ; contradiction entre sources sur la base des 0,71 % : « des comptes financés » ou « de tous ») — [TradersSecondBrain, vérifié 22/09/2026](https://traderssecondbrain.com/guides/prop-firm-pass-rate) ; [Recherche Topstep](https://tradecovex.com/guides/how-many-combines-passed-express-topstep-2025)
- Take Profit Trader : 36,22 % des examens réussis en 2025 ; Earn2Trade : 8,89 % ; MyFundedFutures : 19,97 % passent, 39,2 % des financés touchent au moins un paiement ; Apex : 828 M$ versés cumulés depuis 2022 — [QuantVPS, octobre 2026](https://www.quantvps.com/blog/prop-firm-statistics)
- Fintokei : ~40 % des financés payés, paiement moyen ~4 473 € (non vérifié, résumé de recherche) — [QuantVPS / recherche](https://www.quantvps.com/blog/prop-firm-statistics)
- FTMO ne publie aucun taux de réussite ; les « ~10 % » ou « 7 % des réussites payées » qui circulent sont des estimations sans méthode reproductible — [TradersSecondBrain](https://traderssecondbrain.com/guides/prop-firm-pass-rate) ; [CoinLaw](https://coinlaw.io/ftmo-statistics/)
- Ensemble du secteur suivi par Prop Firm Match : 325 M$ versés en 2025 (sans FTMO ni The5ers) — [Finance Magnates, 06/01/2026](https://financemagnates.com/forex/prop-firm-match-tracked-about-325-million-in-payouts-to-traders-in-2025)
- Modèle économique : FTMO 1,27 million de commandes payées en 2025, ~80 % du chiffre vient de clients qui RACHÈTENT — [FX News Group](https://fxnewsgroup.com/forex-news/retail-forex/ftmo-2025-revenues-rise-31-to-422m-paid-422m-for-oanda/) ; paiements ≈ 176 M$ (non vérifié) soit ~42 % du chiffre (un résumé dit 55 % : contradiction) — [TradeInformer](https://tradeinformer.com/?p=14593)
- FTMO conseille au maximum 1 à 1,5 % de risque par position — [FTMO blog](https://ftmo.com/en/blog/how-much-should-you-risk-on-one-trade/)
- Analyse FTMO (20/01/2023, seulement 3 traders) : le plus « propre » = 11 trades en deux semaines, positions de plusieurs jours, stop systématique, rapport gain/risque 5,17, 63,6 % de gagnants ; le moins propre = 6 trades/jour, renforçait ses pertes, pas toujours de stop — [FTMO blog](https://ftmo.com/en/blog/ftmo-traders-analysis-less-is-sometimes-more/)
- FTMO surveille certains comportements (titre de l'article) — [FTMO blog](https://ftmo.com/en/blog/why-ftmo-monitors-certain-patterns-in-trading-behaviour/)
- Mise en garde : « aucune base de données reproductible ne montre que ceux qui passent risquent 0,5-1 %, font 3,2 trades/jour ou utilisent 60-80 % du temps » — [TradersSecondBrain](https://traderssecondbrain.com/guides/prop-firm-pass-rate)

### Inferences
- Le modèle des sociétés vit des RACHATS d'examens (80 % du chiffre FTMO) ; les paiements sont une fraction du chiffre. Un trader rentable leur coûte de l'argent : d'où les plafonds (400 k$), les règles de régularité, les interdictions de copie, et le resserrement des programmes automatiques en 2026.
- Les rares traits observés (peu de trades, stop toujours, détention de plusieurs heures/jours, 1 % de risque max) collent avec ce que le projet a mesuré : la tendance de fond et les tenues longues sont la seule source d'avantage, la sur-activité tue (frais).

### Gaps
- Pas de statistique officielle FTMO, The5ers, FundedNext sur le taux de réussite ou le paiement moyen.
- Pas d'étude sérieuse sur la durée de vie d'un compte financé ni sur le style des traders payés plusieurs fois.
- Fichiers fuités de The Funded Trader (2023) non retrouvés.

## C. Le calcul d'affaires : vaut-il la peine d'acheter des examens avec un petit avantage, et de multiplier les comptes ?

### Takeaway
Simulation maison (FTMO 2 étapes, 100 k$, frais 600 $ remboursés au 1er paiement, 80 %, 12 mois financés) : avec +1 %/mois réel et une volatilité de compte de 10 %/an, ~83 % de réussite et ~9 400 $ nets attendus par examen la première année ; avec +0,5 %/mois, ~4 400 $. Mais on ne peut pas multiplier : FTMO plafonne à 400 k$ par stratégie, et des copies du même programme meurent ensemble.

### Cited Findings
- Coût moyen observé par trader ~800 $ (≈3 examens), paiement moyen ≈ 4 % du compte — [Finance Magnates / FPFX](https://financemagnates.com/forex/analysis/exclusive-only-7-of-300000-prop-trading-accounts-achieved-payouts)
- FTMO : 400 000 $ max au total « par trader ou par stratégie », suspension en cas de trading identique ou très semblable sur plusieurs comptes au-delà — [FTMO FAQ](https://ftmo.com/en/faq/how-many-accounts-can-i-have/)
- E8 : une seule stratégie par personne — [NewYorkCityServers](https://newyorkcityservers.com/blog/best-prop-firms-ea-trading) ; The5ers : détection d'un même programme — [même source](https://newyorkcityservers.com/blog/best-prop-firms-ea-trading)
- Frais FTMO remboursés avec la première récompense — [TheTrustedProp](https://thetrustedprop.com/blogs/ftmo-1-step-challenge-simply-explained)
- Simulation (script `scratchpad/ev_challenge.py`, 20 000 tirages par cas, rendements journaliers indépendants « en cloche », règles FTMO 2 étapes : -5 %/jour, -10 % statique, objectifs 10 % puis 5 %, ≥4 jours, 24 mois max par phase ; financé : retrait mensuel 80 % du gain puis retour au capital initial ; aucun frais en plus de ceux déjà dans le rendement) :

| Gain/mois | Volatilité/an | Passe les 2 phases | ≥1 paiement | Gain net moyen/examen (12 mois) | Mois médian pour passer | Encore en vie à 12 mois |
|---|---|---|---|---|---|---|
| 0 % | 5 % | 7,6 % | 6,3 % | -370 $ | 24,8 | 7 % |
| 0 % | 10 % | 28 % | 23 % | +976 $ | 13,2 | 16 % |
| 0 % | 20 % | 32 % | 22 % | +2 015 $ | 4,1 | 4 % |
| 0,5 % | 5 % | 67 % | 65 % | +3 596 $ | 21,2 | 67 % |
| 0,5 % | 10 % | 59 % | 53 % | +4 377 $ | 12,6 | 44 % |
| 0,5 % | 20 % | 41 % | 30 % | +3 512 $ | 4,0 | 6 % |
| 1 % | 5 % | 99 % | 98 % | +9 800 $ | 13,8 | 99 % |
| 1 % | 10 % | 83 % | 80 % | +9 415 $ | 10,6 | 73 % |
| 1 % | 20 % | 49 % | 39 % | +5 689 $ | 4,0 | 10 % |
| 2 % | 10 % | 99 % | 98 % | +19 573 $ | 6,7 | 97 % |

(Calcul maison, pas une source extérieure.)

### Inferences
- Un avantage nul donne un gain moyen positif dans la simulation : c'est l'effet « option gratuite » (on encaisse 80 % des hausses, la société porte les pertes). Dans la réalité, ce cadeau est mangé par les écarts/commissions (un trader sans avantage a un rendement NÉGATIF après frais), par la règle de régularité (1 étape) et par les refus de paiement ; ne pas en tirer d'espoir. Les chiffres FPFX (7 % payés) montrent la réalité moyenne.
- Avec +0,5 à +1 %/mois, la bonne volatilité est basse (5-10 %/an) : passer prend 10 à 20 mois (objectif 10 % + 5 %). Monter le risque pour passer plus vite fait chuter la survie (à 20 %/an, 90 % des comptes morts en un an). L'objectif de 10 % est donc le vrai mur pour un petit avantage, pas les pertes max.
- Un compte FTMO 100 k$ à +1 %/mois rapporte ~800 $/mois au trader ; le plafond de 400 k$ par stratégie limite à ~3 200 $/mois pour +1 %/mois (avant plan d'agrandissement). Plusieurs sociétés (FTMO + The5ers + E8…) multiplient le plafond, mais avec le MÊME programme toutes les copies chutent le même jour : aucune diversification, une mauvaise série tue tous les comptes ensemble (seuls les frais d'examen à racheter sont « perdus » ; aucune dette). Pour réduire ce risque : décaler les dates de départ, varier les tailles de risque, ou faire tourner des stratégies réellement différentes (et vérifier que chaque société accepte la même stratégie ailleurs).
- Le repère du projet (+0,5 %/mois mesuré pour la tendance de fond multi-marchés 2018-2025) correspond à la ligne « 0,5 %/mois » : rentable en moyenne, mais lent (plus d'un an pour passer à 5 %/an de volatilité).

### Gaps
- Simulation simplifiée : pas de queues épaisses, pas de séries de pertes corrélées, pas de règles de nouvelles / week-end, pas de plan d'agrandissement, retrait mensuel au lieu de bi-mensuel.
- Aucune source publique sur le nombre de traders FTMO réellement au plafond de 400 k$ ou sur les suspensions pour « stratégie identique ».
- Pas de chiffre sur la position des sociétés si une même IA est utilisée par une seule personne chez plusieurs sociétés en même temps (aucune règle ne l'interdit explicitement dans les sources lues, sauf FTMO pour le plafond interne).

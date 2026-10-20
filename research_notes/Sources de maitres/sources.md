# Sources de « maîtres » (historiques réels de traders, trade par trade) — recherche du 15/10/2026

But : trouver des historiques RÉELS et VÉRIFIÉS de traders (chaque trade : heure, marché, sens, taille, prix
d'entrée/sortie, stop/objectif si possible, gain/perte) sur des marchés NON crypto (devises, or/argent, indices,
pétrole), obtenus LÉGALEMENT (API officielle ou téléchargement permis), pour servir d'exemples à imiter.

Légende fiabilité : « réglementé » = courtier/plateforme sous autorité financière ; « inforgeable » = inscrit sur
une chaîne publique (personne ne peut le truquer) ; « simulé » = exécution fictive aux prix du marché.

---------------------------------------------------------------------------------------------------------------

## 1. Tableau de synthèse

| Source | Trade par trade public ? | Fiabilité | Marchés non crypto | Accès légal pour nous | Verdict |
|---|---|---|---|---|---|
| Collective2 (API v4) | OUI (ouverture/fermeture, sens, quantité, prix moyens, gain, pire prix pendant le trade) | Simulé (« hypothétique ») sauf sous-ensemble « trade son propre système » | Contrats à terme (S&P, or, pétrole…), devises, actions, options | API officielle documentée, clé gratuite ; conditions : pas de « scraping » du contenu payant | **Meilleur candidat non crypto** (à vérifier : accès aux trades des stratégies d'autrui avec une clé simple) |
| gTrade / Ostium / Avantis (chaînes Arbitrum, Base, Polygon) | OUI, y compris stop et objectif, levier | Inforgeable, non réglementé | Devises (9 paires gTrade), or, argent, pétrole, cuivre, indices (7 sur gTrade) | Données publiques de la chaîne + API publiques sans clé | **Très bon** (données honnêtes, mais traders « crypto » à fort levier) |
| Hyperliquid HIP-3 (trade.xyz) | OUI (exécutions avec sens ouverture/fermeture, gain réalisé, frais) | Inforgeable, non réglementé | Or, argent, platine, pétrole WTI, S&P 500 (licence officielle S&P), Nasdaq-100, actions US | API publique documentée + archive S3 (téléchargement payé par le demandeur) | **Très bon en volume** (192 000+ traders) mais seulement ~1 an d'historique |
| Darwinex (FTP « Raw DARWIN data » + API Info) | PARTIEL : par trade = heure d'ouverture, durée, rendement, risque, levier (sans marché ni sens) ; par jour et par marché = nombre de positions, gagnantes/perdantes, durées | **Réglementé FCA (Royaume-Uni) + CNMV**, comptes réels (Darwinex Zero = capital virtuel en conditions réelles) | Devises, or, indices, pétrole (CFD), + futures via IBKR | Compte Darwinex ; conditions de l'API : usage interne AUTORISÉ | **Le plus honnête et le plus propre juridiquement, mais pas le détail complet** |
| cTrader Copy (Spotware) | OUI sur le site (onglet Historique : chaque opération de clôture) | Comptes réels chez courtiers réglementés (Pepperstone, IC Markets…) | Devises, or, indices, pétrole | **Interdit sans accord écrit** (conditions du site, section 17) | Possible seulement avec permission écrite de Spotware |
| eToro (API publique 2026) | NON pour l'historique d'autrui (seulement positions OUVERTES en direct + statistiques) | Réglementé (CySEC, FCA, ASIC…) | Actions, indices, matières premières, devises | **Interdit d'entraîner un modèle** (conditions 17/02/2026) | Exclu |
| Myfxbook | API = SES PROPRES comptes uniquement, 50 dernières opérations | « Information non vérifiée » selon leurs propres conditions | Devises, or, indices | Reproduction interdite | Exclu |
| FX Blue | Relevés publics sur le site | Même « vérifié » peut être faux (leurs mots) | Devises, or, indices | Robots/scripts interdits | Exclu (sauf permission écrite) |
| MQL5 Signals | Historique derrière connexion | Comptes MT4/MT5 réels ou démo | Devises, or, indices | Article 3.7 : tout accès automatisé interdit | Exclu (confirmé) |
| ZuluTrade, NAGA, DupliTrade | Pages de profils, pas d'API publique trouvée | Variable | Devises surtout | Rien d'autorisé trouvé | Exclu (non approfondi) |
| Sociétés de financement (FTMO, The5ers, E8…) | Non (classements et statistiques globales seulement) | Comptes démo/simulés | Tout | Rien de public trade par trade | Exclu |
| Données universitaires/régulateurs (Barber-Odean, Taïwan, Brésil, CFTC) | Non publiques | Excellente | Actions surtout | CFTC : divulgation interdite par la loi (section 8 du CEA) | Exclu |
| Championnat du monde de trading (Robbins) | Résultats finaux seulement | Comptes réels | Futures/devises | Pas de journaux de trades publiés | Exclu |

---------------------------------------------------------------------------------------------------------------

## 2. Détail par source (avec citations)

### 2.1 Collective2 (C2) — États-Unis
- **Ce qui est public** : la page de chaque stratégie montre la liste des trades (dates, symbole, sens, quantité,
  gain). Vérifié sur une page publique (https://collective2.eu/details/97362027) : « 180+ trades … visible »
  sans connexion.
- **API officielle v4** (https://api-docs.collective2.com/ ; référence : https://c2-api.redocly.app/apis/general/swagger) :
  - `GET https://api4-general.collective2.com/Strategies/GetStrategyHistoricalClosedTrades?StrategyId=…`
    « Returns the historical closed trades of the strategy … Non-paginated endpoint. » Champs : OpenDate,
    CloseDate, AvgOpenFillPrice, AvgCloseFillPrice, OpenedQuantity, OpenSide (1=achat, 2=vente), ProfitLoss,
    Commission, MaxDrawdown + MaxDrawdown_WorstPrice (pire prix pendant le trade), symbole avec type
    (stock, option, future, forex), bourse (MIC), échéance, multiplicateur.
  - `SearchStrategies` (filtre SecurityType = FUT / FOR / CS / OPT, champ IsAlive = stratégie vivante ou morte,
    IsTradeOwnSystem), `GetLeaderBoard`, `GetStrategyHistoricalDailyEquity`, `GetStrategyDetails`.
  - Clé : « Any Collective2 user can create an API4 key » via https://collective2.com/apikey
    (https://trade.collective2.com/c2-api.html). Authentification `Authorization: Bearer <clé>`.
  - **À VÉRIFIER** : la documentation ne dit pas si une clé simple lit les trades de stratégies dont on n'est pas
    abonné (seul `PersonId` est réservé aux administrateurs). Premier test à faire avec une clé gratuite.
- **Fiabilité** : résultats **simulés** : « These results are based on simulated or hypothetical performance
  results … do not represent actual trading. » C2 interdit d'effacer ou modifier un signal après coup (registre
  non truquable a posteriori). Sous-ensemble « Trades-Own-Strategy » = le gérant trade réellement chez un courtier,
  mais « must still be regarded as purely hypothetical ». Pas de stop/objectif dans les trades clos (seulement
  dans les ordres actifs).
- **Survivants** : `SearchStrategies` expose IsAlive → on peut a priori inclure les stratégies mortes (à vérifier).
- **Volume** : nombre de stratégies non publié (incertain ; plusieurs milliers probables, dont beaucoup sur
  actions/options). Historique : plateforme active depuis ~2001.
- **Conditions** (https://collective2.eu/terms-of-service, en vigueur au 27/03/2026) : interdit de « use bots,
  scripts, or other automated means to access the Service in a manner that burdens or disrupts it » et de
  « scrape, copy, resell, or redistribute paid strategy content or other protected material except as expressly
  allowed » ; section 9 : « you may not copy, modify, distribute, license, sell, reverse engineer, or create
  derivative works ». Rien sur l'apprentissage automatique. → Utiliser **uniquement l'API officielle**, à faible
  cadence, sans rien redistribuer, et **demander par écrit** à C2 (support) si l'usage « entraîner une IA privée »
  est accepté.

### 2.2 gTrade (Gains Network), Ostium, Avantis — échanges sur chaîne publique, marchés « réels » (devises, or…)
- **Ce qui est public** : tout. Chaque ouverture/fermeture est une transaction publique, avec sens, levier, prix
  d'entrée/sortie, **stop et objectif**, gain/perte, adresse du portefeuille (pseudonyme).
- **gTrade** : 9 paires de devises (levier 10x à 1000x), or, argent, cuivre, pétrole WTI, platine
  (https://docs.gains.trade/gtrade-leveraged-trading/asset-classes/commodities.md), 7 indices.
  API publique **sans clé** : `GET https://backend-global.gains.trade/api/personal-trading-history/{adresse}?chainId=42161`
  (« Returns paginated trading history for one wallet », sécurité = aucune), `…/api/trading-history/{24h|48h|72h}`
  (tous les trades récents), `…/leaderboard`. Chaînes : Arbitrum (42161), Base (8453), Polygon (137).
  Historique : depuis 2021-2022 sur Polygon (date exacte du lancement des devises : à vérifier).
- **Ostium** (Arbitrum) : devises, or, pétrole, cuivre, indices, actions ; « $50B+ traded by 26K+ users » ; dit
  détenir > 50 % des positions ouvertes sur l'or « sur chaîne ». Données via sous-graphe (adresse publiée par un
  tiers, à vérifier dans https://docs.ostium.io) ou lecture directe des événements de la chaîne.
- **Avantis** (Base) : devises, matières premières, actions ; service « history (closed/all trade history, PnL
  aggregates) » sur api.avantisfi.com (source : https://docs.base.org/agents/plugins/native/avantis).
- **Fiabilité** : inforgeable (la chaîne fait foi), aucun survivant caché (tous les portefeuilles, morts compris).
  Limites : non réglementé ; prix venant d'oracles (proches du marché mais pas identiques à FTMO) ; traders souvent
  « crypto », levier énorme, petits comptes ; un trader = une adresse (une personne peut en avoir plusieurs).
- **Conditions** : les données de la chaîne sont publiques ; les API publiques sont documentées pour être appelées
  par programme. Voie la plus propre : relire les événements de la chaîne par un nœud public (aucune condition
  d'un site n'intervient). Conditions d'usage des API de chaque projet : non lues en détail (à vérifier).

### 2.3 Hyperliquid — marchés HIP-3 (trade.xyz)
- **Marchés** : or, argent, platine, palladium, pétrole WTI, maïs, blé, **S&P 500 (licence officielle S&P Dow
  Jones Indices depuis le 18/03/2026)**, Nasdaq-100 (XYZ100), grandes actions US. « $130B+ cumulative trading
  volume across 192,000+ traders since its October 2025 launch » (https://nansen.ai/post/what-is-hip-3-hyperliquid,
  https://pm.wiki/…/trade-xyz). Pas de devises trouvées.
- **Détail** : `POST https://api.hyperliquid.xyz/info` type `userFills` / `userFillsByTime` : champs coin
  (ex. « xyz:XYZ100 »), px, sz, side, time, **dir (Open Long / Close Short…)**, **closedPnl**, fee. Limites :
  « at most 2000 fills per response », « only the 10000 most recent fills are available » par utilisateur ;
  `historicalOrders` (ordres, dont stops/objectifs) : 2000 plus récents.
  (https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)
- **Archive complète** : seau S3 `hl-mainnet-node-data` (`node_fills_by_block`, anciennement `node_fills`) =
  toutes les exécutions avec adresses ; « requester-pays » (on paie le transfert) ; « There is no guarantee of
  timely updates and data may be missing. » (https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data)
- **Limite de débit** : 1200 « poids »/minute par IP, userFills coûte 20 + 1 par 20 lignes.
- **Fiabilité** : inforgeable, sans survivants cachés ; mais ~1 an d'historique seulement, cotation 24h/24 7j/7,
  traders crypto. Conditions d'utilisation d'Hyperliquid sur la réutilisation : non trouvées (à vérifier) ;
  l'API et le seau S3 sont publiés officiellement pour cet usage.

### 2.4 Darwinex (Tradeslide Trading Tech, Londres) — réglementé FCA (FRN 586466) et CNMV
- **API Info DARWIN** : cotations historiques des DARWIN (courbe de valeur normalisée en risque de chaque
  stratégie) et notes (https://github.com/darwinex/darwinexapis : « DARWIN Info API - access the entire universe
  of DARWIN quotes and scores »). Jeton sur darwinex.com/data/darwin-api.
- **FTP « Raw DARWIN data »** (https://help.darwinex.com/raw-darwin-data-user-guide) : « a folder for each DARWIN
  ever listed on the DARWIN Exchange » (→ morts compris, pas de biais des survivants), cotations à la seconde, et
  ~30 jeux de données dont :
  - TRADE_CONSISTENCY : jusqu'à 100 trades clos par jour, « Open time. Duration. Return. VaR. Leverage » ;
  - DURATION_CONSISTENCY : par position, heure de début, durée, gain brut, risque, levier ;
  - POSITIONS / TRADES : par jour et **par marché** : nombre de trades, gagnants/perdants, rentabilité, durées ;
  - MARKET_CORRELATION : par marché, positions acheteuses/vendeuses consécutives ;
  - OPEN_STRATEGY / CLOSE_STRATEGY : effet d'avoir ouvert/fermé plus tôt ou plus tard.
  → **Il manque** le marché et le sens au niveau de chaque trade, et les prix exacts : pas de vrai trade par trade.
  Accès : se connecter au compte Darwinex → « Historical Tick Data » → « Request FTP Access » (compte réel requis
  selon une source secondaire : à vérifier).
- **Fiabilité** : la meilleure trouvée (courtier réglementé, comptes réels ; Darwinex Zero = compte virtuel de
  100 000 $ « under real market conditions, including slippage, spreads, swaps, and commissions »).
  « €682.53 million has been invested in trader strategies » ; > 10 000 traders (sources secondaires).
- **Conditions de l'API** (https://d139oolcsxoepg.cloudfront.net/static_content/legal/FCA/darwin-api-conditions.pdf),
  article 3.2 : « You may only use such Darwinex Data for your internal purposes or within your Application and
  will not disclose, sell or transfer any Darwinex Data without our prior written consent. » ; 3.3 : interdiction
  d'utiliser des données sur des personnes identifiables. → **Usage interne (entraîner notre IA privée) permis**,
  sans redistribution. Les conditions du FTP ne sont pas précisées dans le guide (à vérifier).

### 2.5 cTrader Copy (Spotware)
- Page publique de chaque stratégie : « The History tab lists all the closing deals of the strategy »
  (https://help.ctrader.com/ctrader-copy/account-and-strategy-page/) ; comptes réels chez des courtiers réglementés.
- Pas d'export ni d'API pour les comptes d'autrui : l'API ouverte ne lit que les comptes autorisés par leur
  propriétaire (https://help.ctrader.com/open-api/terms-of-use/).
- Conditions du site (https://ctrader.com/terms-of-use, section 17) : « Users shall not develop or use any
  third-party applications that interact with the Website without cTrader's prior written consent, including any
  scripts designed to scrape or extract data from the Website. » → seulement avec **accord écrit** de Spotware.

### 2.6 eToro (API publique, 2026)
- Lit d'autres utilisateurs : portefeuille **ouvert** en direct (heure et prix d'ouverture, sens, levier, stop,
  objectif), statistiques, gains mensuels/annuels ; **pas** l'historique des trades clos d'autrui
  (https://api-portal.etoro.com/llms.txt). Compte vérifié requis, gratuit, 60 requêtes/60 s.
- **Conditions** (« Builders' Economy », 17/02/2026, https://www.etoro.com/wp-content/uploads/2026/03/Master_eToro_Builders_Economy_Terms_17-Feb-2026-clean_R.pdf) :
  1.7 interdit de « use Licensed Content or AI-generated outputs to train, fine-tune, or ground any model » ;
  1.8 interdit de « scrape, bulk-download, cache, redistribute … or create separate databases from Licensed
  Content ». → **Exclu** pour l'imitation.

### 2.7 Myfxbook
- API (https://www.myfxbook.com/api, v1.38 du 19/10/2025) : « The API allows access to personal information
  only. » ; get-history « limited to the last 50 transactions ».
- Conditions (https://www.myfxbook.com/terms) : « The information on this website is not verified in any way. » ;
  « Reproduction is prohibited by law. » ; « Unauthorized use of this website may lead to a claim for damages
  and/or be a criminal offence. » → **Exclu.**

### 2.8 FX Blue
- Conditions (https://www.fxblue.com/about/terms) : interdit de « Use any automated means, including without
  limitation, agents, robots, scripts, or spiders, to access, monitor, copy or harvest data » ; « any sort of
  commercial use of the Information is strictly prohibited without FX Blue's prior written permission » ; sur les
  comptes « vérifiés » : ils « can still be falsified » car « it is impossible for anyone outside the broker … to
  be 100% certain whether an account is demo or real ». → **Exclu** (sauf permission écrite).

### 2.9 MQL5 Signals (confirmé)
- https://www.mql5.com/en/about/terms, 3.7 : « You agree not to access the website www.mql5.com through any
  automated means, including use of scripts, crawlers, or similar technologies. » → **Exclu.**

### 2.10 Autres (non retenus)
- ZuluTrade (> 90 000 « leaders »), NAGA, DupliTrade (« over a dozen audited strategy providers ») : aucune API
  publique ni autorisation trouvée ; non approfondi.
- Sociétés de financement (FTMO…) : statistiques globales et classements, analyses dans l'espace client
  personnel ; comptes simulés ; pas de trades publics.
- CFTC : « the Commission is prohibited under Section 8 of the CEA from publicly disclosing any person's
  positions, transactions » ; seul le rapport COT (agrégé) est public.
- Barber-Odean (78 000 comptes Schwab 1991-1996), Taïwan, Brésil : jeux privés, accès par accord de recherche.
- FXCM « Trade Tape » : flux d'ordres agrégé des clients (payant), pas par trader.
- Championnat Robbins : seulement les classements finaux.
- Échanges crypto sur chaîne dYdX v4, GMX, Drift, Aevo, Vertex : essentiellement des cryptos (non vérifié
  marché par marché) → hors sujet.

---------------------------------------------------------------------------------------------------------------

## 3. Classement final (fiabilité x volume x marchés non crypto x accès légal)

1. **Collective2 (API v4)** — le seul vrai « trade par trade » sur futures S&P/or/pétrole et devises par une
   API officielle. Défaut : résultats simulés. Prochaine étape : créer un compte gratuit, générer une clé sur
   https://collective2.com/apikey, tester `SearchStrategies?SecurityType=FUT` puis
   `GetStrategyHistoricalClosedTrades` sur une stratégie non abonnée ; écrire au support pour confirmer l'usage
   « entraînement d'une IA privée, sans redistribution ». Filtrer de préférence « Trades Own System ».
2. **gTrade + Ostium + Avantis (sur chaîne)** — détail complet avec stop et objectif, inforgeable, gratuit, sans
   compte. Prochaine étape : `https://backend-global.gains.trade/api/leaderboard` pour repérer les adresses, puis
   `personal-trading-history/{adresse}?chainId=42161` (et 8453, 137) ; filtrer sur devises/or/pétrole/indices ;
   pour Ostium, prendre le sous-graphe officiel dans docs.ostium.io. Cadence lente.
3. **Hyperliquid HIP-3** — énorme volume sur or, argent, S&P 500, Nasdaq, pétrole (~1 an). Prochaine étape :
   télécharger `s3://hl-mainnet-node-data/node_fills_by_block/` (compte AWS, frais de transfert à notre charge,
   estimer le volume avant) et garder les marchés « xyz:… » ; sinon `userFillsByTime` pour une liste d'adresses.
4. **Darwinex** — la source la plus honnête (FCA, comptes réels, tous les DARWIN depuis le début) et la seule dont
   les conditions autorisent clairement l'usage interne ; mais détail partiel. Prochaine étape : ouvrir un compte,
   « Request FTP Access », vérifier si un compte réel financé est exigé ; utiliser POSITIONS/TRADES/
   TRADE_CONSISTENCY comme « professeurs de comportement » (durées, rythme, gestion du risque) et les cotations
   pour choisir les bons maîtres.
5. **cTrader Copy** — vrais comptes réglementés, opération par opération ; seulement après **accord écrit** de
   Spotware (écrire à Spotware/cTrader en expliquant l'usage privé).
6. **Voie « consentement direct »** (non listée plus haut) : demander à des traders (forums, FTMO, Darwinex) de
   nous confier leur historique MT5 exporté ou un mot de passe « investisseur » en lecture seule. Légal, réel,
   exactement nos marchés, mais petit volume.

## 4. Mise en pratique (15/10/2026 matin)
- **Ostium : FAIT.** Sous-graphe public officiel (adresse dans le paquet officiel `ostium-python-sdk`, config.py ;
  aucune clé) -> `collapsar/maitres/ostium.py` : 748 288 ordres 08/2024 -> 10/2026, ~14 900 traders, nos marchés
  seulement (devises, or, argent, pétrole, indices). C'est la meilleure source non crypto obtenue.
- **Avantis = renommé Veranta** (paquet `veranta-sdk`) : `GET https://api.veranta.xyz/v2/history/trade-history/
  {adresse}/{page à partir de 1}/{nombre}` donne l'historique complet d'un trader (marché, sens, levier, stop,
  objectif, gains bruts/nets, frais). Mais la découverte des traders est pauvre : classement public = 10 traders
  (crypto, levier x900) ; `recent-trades/{marché}` sans adresse. Il faudrait relire les événements de la chaîne
  Base. Source secondaire, non branchée.
- gTrade (boucle 3 h) et Hyperliquid (aperçu en cours) : branchés au format commun.

Avertissement général : sur toutes ces sources, la grande majorité des traders perdent ; il faudra choisir les
« maîtres » sur des périodes non vues, avec frais réels, sinon l'IA imitera de la chance.

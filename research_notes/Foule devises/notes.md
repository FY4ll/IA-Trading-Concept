# Foule devises : historiques du positionnement des particuliers (16/10/2026)

But : trouver un HISTORIQUE téléchargeable légalement de la part des clients particuliers acheteurs / vendeurs sur
devises, or, argent, indices, pétrole (même idée que C1 de crypto_flux, mais sur des marchés bon marché chez FTMO).
Règle suivie : aucune condition d'utilisation contournée ; pas de « grattage » de pages web quand le site l'interdit ;
pas de jeu de données « recopié » par un tiers sans droit.

## Tableau de synthèse

| Source | Marchés | Historique | Pas | Accès | Conditions | Verdict |
|---|---|---|---|---|---|---|
| Dukascopy « SWFX Sentiment Index » | ~40 paires, or, 13 devises | **Aucun** téléchargeable : le gadget ne montre que maintenant / 6 h / 1 j / 5 j ; l'interface JForex qui donnait l'historique est **abandonnée** (« deprecated, returns null ») | 30 min | Gratuit, sans compte (page web et gadget) | **Robots interdits** sans accord écrit | Exclu (historique et collecte automatique) |
| IG Client Sentiment | Devises, indices, matières premières | **Aucun** (valeur actuelle seulement ; DailyFX, qui publiait des graphiques, a fermé) | Direct | Interface officielle `/clientsentiment` avec un compte IG (démo) + clé | Usage personnel via l'interface officielle | Pas d'historique ; collecte possible SI le chef ouvre un compte IG démo |
| Myfxbook Community Outlook | ~ 80 symboles | **Aucun** dans l'interface (valeur actuelle) | Direct | Interface officielle `get-community-outlook.json` après connexion avec un compte Myfxbook | « Reproduction is prohibited » ; grattage interdit ; mélange comptes démo + réels | Pas d'historique ; collecte possible SI le chef fournit un compte |
| FXSSI | Devises, or, indices (agrège plusieurs courtiers) | Historique seulement dans l'offre payante (indicateurs MT4/MT5) | 20 min | Payant | Pas de téléchargement brut | Exclu (payant, pas de fichier) |
| FXCM « SSI » | 32 marchés (devises, or, argent, pétrole, indices) | **1 mois d'exemple gratuit** (janvier 2018, testé : 394 164 lignes EURUSD 01/01 -> 01/02/2018) ; historique complet depuis 2009 = **payant** (api@fxcm.com) | 1 min | `sampledata.fxcorporate.com/sentiment/<SYM>.csv.gz` | « personal use », CLUF FXCM | Exemple trop court ; historique à acheter |
| OANDA livre des positions | ~ 30 marchés (devises, or, argent, indices) | Instantanés passés via le paramètre `time` de `/v3/instruments/<X>/positionBook` (profondeur non documentée publiquement ; exemples de 2017) ; les anciens « ratios historiques » (labs v1) | 20 min | **Compte OANDA + jeton** (compte réel pour certains outils ; démo à vérifier) | Usage personnel | **Meilleure piste d'historique** mais impossible sans compte |
| Saxo (positionnement clients) | Devises, indices | Aucun | Direct | Page web / compte | — | Exclu |
| Darwinex | — | Pas de positionnement agrégé publié | — | — | — | Exclu |
| **CFTC « Engagements des traders » (positions non déclarables = petits spéculateurs)** | Contrats à terme : euro, livre, yen, franc, dollar canadien, australien, néo-zélandais, or, argent, pétrole WTI, S&P 500, Nasdaq, Dow, Nikkei, obligations | **Depuis 1986** (fichiers annuels gratuits) | Hebdomadaire (photo du mardi, publiée le vendredi 15h30 New York, parfois lundi ; retards pendant les fermetures de l'État américain 2013, 2018-19, 2025) | `https://www.cftc.gov/files/dea/history/deacot<AN>.zip` | Données publiques de l'État américain, libres | **Seule source légale longue** ; mais ce sont les petits traders des contrats à terme, PAS les clients CFD des courtiers |

## Détails et citations
- Dukascopy, interface JForex `IDataService` : `getFXSentimentIndex(Instrument, long time)` et
  `getFXSentimentIndex(Instrument, Period, from, to)` « Deprecated … returns null » ; seule reste la dernière valeur
  (https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/IDataService.html).
- Dukascopy, conditions (https://www.dukascopy.com/swiss/english/legal-pages/terms-of-use/) : « You shall not use or
  attempt to use any 'scraper,' 'robot,' 'bot,' 'spider,' 'data mining,' … to access, acquire, copy, or monitor any
  portion of the WEBSITE … without the prior express written consent of DUKASCOPY. » -> pas de collecte automatique,
  même par le gadget (le gadget interroge `/v1/sentiments/instruments`, champs LAST / SIX_HOURS / ONE_DAY / FIVE_DAYS).
- FXCM (https://github.com/fxcm/MarketData) : exemple d'un mois « for personal use and abides by our EULA » ; colonnes
  DateTime (heure de New York), Symbol, Name (SSIHist, LongAmountK, ShortAmountK…), Value.
- Myfxbook : conditions https://www.myfxbook.com/terms (« Reproduction is prohibited by law ») ; interface
  https://www.myfxbook.com/api : `login.json` puis `get-community-outlook.json?session=…` (longPercentage,
  shortPercentage, longPositions, shortPositions, avgLongPrice…). Les « grattoirs » sans connexion vendus en ligne
  contournent les conditions -> exclus.
- IG : `GET /clientsentiment/{marketId}` (longPositionPercentage, shortPositionPercentage), compte + clé d'interface ;
  aucune route historique.
- OANDA : `GET /v3/instruments/{instrument}/positionBook?time=…` (photo la plus proche de l'heure demandée, toutes
  les 20 min) ; nécessite un jeton de compte. OANDA Japon : historique du carnet visible dans un indicateur MT4/MT5
  pour clients (15 min ou 5 min selon le niveau).
- CFTC : fichiers « Legacy, futures only » annuels ; colonnes « Nonreportable Positions-Long (All) » et
  « -Short (All) » (positions trop petites pour être déclarées = petits spéculateurs, souvent des particuliers).
  Heure : photo du mardi, publiée le vendredi 15h30 (New York), le lundi si jour férié ; fermetures de l'État
  (10/2013, 12/2018-01/2019, 10-11/2025) : publications rattrapées des semaines plus tard.
- Projet : l'ancien Run A notait déjà « positions COT : aucun avantage » (mais comme simple variable, pas en
  contre-pied des extrêmes des petits traders).

## Conclusion
1. **Aucune source gratuite et légale ne donne un historique >= 3 ans du positionnement des clients particuliers des
   courtiers CFD/devises.** Les historiques existent (FXCM depuis 2009, OANDA, FXSSI) mais sont payants ou réservés aux
   clients d'un compte.
2. La seule source longue, gratuite et libre est la **CFTC (petits spéculateurs des contrats à terme)** : un cousin
   hebdomadaire de l'information C1, testé dans `collapsar/regarder/pistes/foule_devises.py`.
3. Pour le vrai positionnement des particuliers : collecter en direct dès maintenant
   (`collapsar/donnees/foule_devises.py`), via les interfaces OFFICIELLES (IG, Myfxbook, OANDA) dès que le chef fournit
   un compte ; sans compte, seule la CFTC est collectable automatiquement.

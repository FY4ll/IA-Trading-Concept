# Recherche de « mentors » pour MAGNETAR — sources de vrais trades et de signal sur le sens de l'or

*Recherche faite le 19-20 octobre 2026. Tout ce qui n'a pas pu être confirmé est marqué « non vérifié ».*

---

## 0. Le verdict en 6 lignes

1. **Aucune source trouvée ne remplit TOUS tes critères à la fois** (argent réel vérifié + 2 ans + trade par trade + swing sur l'or + récupération légale automatique). Je ne vais pas faire semblant du contraire.
2. Les plateformes qui ont le meilleur détail par trade (FTMO, The5ers) sont **en argent simulé**. Celles qui ont de l'argent réel (FX Blue, cTrader Copy) **interdisent l'extraction**.
3. **La seule voie propre pour de vrais humains : l'accord direct du trader** (il t'envoie son relevé de courtier). Ton meilleur candidat reste LSP (@winneryu) chez Darwinex.
4. **Sur chaîne publique**, gTrade reste la meilleure source pour l'or. Son API officielle d'historique **par trader** indique en plus si chaque trade a été fermé par stop, par objectif ou par liquidation. À comparer avec ce que tu as déjà collecté.
5. **Pour le SENS de l'or**, aucune étude sérieuse ne montre un signal fort à quelques jours. Ce qui tient : le **suivi de tendance sur plusieurs mois** (prouvé sur un siècle, mais faible sur l'or seul) et les **variations hebdomadaires du positionnement des fonds (COT)**, effet modeste. Ces données sont téléchargées.
6. **Un « système transparent » respecte ton critère n°1 :** les règles des Turtles sont publiques et l'or COMEX faisait partie de leur portefeuille. Tu peux générer des milliers de trades « mentor » au style exact que tu veux (cassures, stop derrière la structure, gagnants laissés courir).

Légende : 🟢 fiable et utilisable · 🟡 utilisable avec réserves · 🔴 à rejeter (une phrase dit pourquoi)

---

## 1. Plateformes sur chaîne publique

### 🟢 Gains Network / gTrade (Polygon depuis 2021, puis Arbitrum, Base, ApeChain) — *déjà collecté de ton côté, mais voici mieux*
- **Ce qu'on obtient :** chaque action de trade, avec date, paire, adresse, sens (`long`), prix d'exécution, collatéral, levier, gain net et lien de transaction. Surtout, le champ `action` distingue `TradeClosedSL`, `TradeClosedTP`, `TradeClosedLIQ` et `TradeClosedMarket`.
- **Or :** XAU/USD = paire n°90 et XAG/USD = paire n°91 sur Arbitrum (vérifié en direct sur `https://backend-arbitrum.gains.trade/trading-variables`). Date d'ajout de l'or : non vérifiée. Volume cumulé sur l'or : environ 118 M$, dont environ 5,4 M$ sur les 30 derniers jours, d'après DefiLlama.
- **Accès (API officielle, publique, sans clé), documentation :** https://docs.gains.trade/developer/integrators/guides/history-endpoints-migration
  - Tous les traders, dernières 24 h seulement : `GET https://backend-global.gains.trade/api/trading-history/24h?chainId=42161` (137 = Polygon, 8453 = Base). Test réel : 1 463 événements, dont 37 sur l'or.
  - Historique complet d'**un** trader : `GET https://backend-global.gains.trade/api/personal-trading-history/{adresse}?chainId=42161&pair=XAU/USD&limit=1000`, avec `startDate`, `endDate` et une pagination par `cursor`.
  - Plusieurs traders d'un coup : `POST .../personal-trading-history/batch` et `.../stats`.
- **Clause d'accès :** aucune condition d'utilisation ni limite de requêtes trouvée dans la documentation de l'API. C'est une API publique documentée pour les intégrateurs. Rester raisonnable : 1 requête par seconde, mise en cache.
- **Coût :** gratuit.
- **Piège principal :** il n'existe pas de point d'accès « tout le monde, tout l'historique ». Il faut d'abord trouver les adresses, par la collecte quotidienne des 24 h ou par les événements de la chaîne, puis interroger chaque adresse. Beaucoup de scalpers à 100-250x. Le **niveau** du stop n'est pas dans l'historique, seulement le fait que la fermeture vient du stop. Pour le niveau, il faut lire les événements du contrat `GNSMultiCollatDiamond`. Les ouvertures et fermetures se rapprochent par (adresse, tradeIndex).
- **Spell Dune `gains_network.perpetual_trades` : inutilisable pour l'or** (Base seulement, depuis 2024, paires au-delà de la n°33 non nommées).

> **Mise à jour du 20.10.2026 : collecte faite** → `data\maitres\gtrade_api_personnelle\`.
> 196 adresses actives, 2 260 trades sur l'or et l'argent, de fin 2024 à aujourd'hui.
> - La foule perd au total (−272 000 $).
> - 4 traders swing gagnants, sans signe de martingale.
> - **Aucun n'a 2 ans d'historique**, et chacun n'a que 20 à 50 trades : ce sont des profils à surveiller, pas des maîtres.
> - L'API ne remonte pas avant fin 2024.

### 🔴 GMX v2 (Arbitrum, Avalanche) — *vérifié le 20.10.2026 : l'or n'existe que depuis le 23.01.2026 (« XAUT/USD »), et « GOLD/USD » depuis le 09.04.2026. Moins de 2 ans, donc rejeté. Pas besoin de compte Dune.*
- **Pour info, accès sans compte :** l'API publique GraphQL utilisée par le site de GMX, `https://gmx.squids.live/gmx-synthetics-arbitrum:prod/api/graphql` (table `positionChanges`). À reprendre en 2028 si l'or s'y développe.
- **Ce qu'on obtient :** ouvertures et réductions de position (heure, sens, prix, taille en $, gain), plus les ordres stop et objectif **avec leur prix de déclenchement**, via les tables Dune `gmx_v2_arbitrum.position_increase`, `position_decrease`, `order_created` et `order_executed` (vérifiées dans le dépôt spellbook).
- **Or :** marchés synthétiques « XAUT/USD (deprecated) », « XAUT.v2/USD » et « GOLD/USD ». L'or 24h/24 a été annoncé le 14.04.2026 (https://thedefiant.io/news/defi/gmx-rolls-out-24-7-gold-and-silver-trading). Date du premier marché sur l'or : non vérifiée.
- **Accès :** Dune. Conditions sur https://dune.com/terms : « You must not use bots, crawlers, scrapers, or other automated means to access or collect data ». Les requêtes publiques peuvent être « used, viewed, forked, and copied » avec crédit à l'auteur. L'export passe par l'API officielle payée en crédits. **Il faut un compte Dune**, donc c'est à toi de décider.
- **Coût :** offre gratuite de Dune avec crédits limités. Montant exact : non vérifié.
- **Piège principal :** historique court sur l'or, prix qui suit l'or tokenisé (XAUT) plutôt que l'or au comptant, et marché remplacé une fois (v1 vers v2).

### 🟡 dYdX v4
- **Ce qu'on obtient :** exécutions d'un trader sur PAXG-USD (or tokenisé), via l'indexeur public `https://indexer.dydx.trade/v4/fills?address=…&market=PAXG-USD`. Bougies présentes au moins depuis septembre 2024.
- **Piège principal :** le flux public ne semble pas donner les adresses (non vérifié), donc on ne peut pas trouver les bons traders. PAXG est peu liquide et n'a pas de stop visible.

### 🔴 Les autres
- **Tigris Trade** : le seul avec un spell Dune contenant le gain par trade (`tigris_trades_pnl`). Mais l'or n'est pas confirmé et la plateforme est probablement morte depuis 2024.
- **Vela** : l'or et l'activité ne sont pas vérifiés (dernière trace en avril 2024).
- **MUX, Unidex, Polynomial, Kwenta** : soit l'or n'est pas confirmé, soit ce sont des surcouches de Synthetix (déjà fait).
- **Level, Rage Trade, Drift, Perennial, Kiloex, Mycelium** : aucun marché or trouvé.
- **Avantis (Base)** : propose l'or, mais je n'ai trouvé ni API d'historique ni table Dune. À creuser plus tard, non vérifié.

---

## 2. Traders humains vérifiés

### 🟡 Darwinex — LSP (@winneryu) *(déjà identifié)*
- C'est toujours le meilleur profil connu : 3 ans, environ +25 %/an, trades d'environ 24 h, relevés audités.
- **Accès légal :** seulement avec l'accord du trader. → **Lui écrire** (voir modèle de message au § 6).
- Autre piste non vérifiée : le DARWIN **ZOU** (historique depuis le 03.01.2020). Ses instruments et son style sont inconnus, à regarder sur darwinex.com. Attention : dans « DarwinIA GOLD », « GOLD » est un niveau du programme d'allocation, pas le métal.

### 🟡 cTrader Copy (Spotware)
- **Ce qu'on obtient :** des stratégies **uniquement sur comptes réels** (FAQ officielle : « You can provide strategies only from live accounts »), avec rendement, courbe du capital et volume par actif. D'après un forum de 2019, l'historique montre les prix et heures d'entrée et de sortie. Détail actuel non vérifié.
- **Accès légal :** consultation manuelle uniquement. Conditions https://ctrader.com/terms-of-use : §17 interdit « any scripts designed to scrape or extract data from the Website », §14 interdit toute reproduction.
- **Piège principal :** les pages ne sont pas visibles par les moteurs de recherche. Il faut filtrer à la main dans l'application, puis contacter le fournisseur.

### 🟡 FX Blue
- **Ce qu'on obtient :** des relevés MT4/MT5 publics avec la liste des trades (heure, sens, prix, volume, stop et objectif).
- **Accès légal :** lecture manuelle seulement. Conditions https://www.fxblue.com/about/terms : « Any copying, distribution, storage or transmission… strictly prohibited without FX Blue's prior written permission ». Tout moyen automatique est aussi interdit.
- **Piège principal :** FX Blue reconnaît qu'un compte marqué « vérifié » peut être une démo sur un serveur réel.

### 🔴 À rejeter
- **FTMO / The5ers :** le meilleur journal par trade du lot (stop, objectif, pire et meilleur moment de chaque trade), mais **argent simulé** (« solely to a simulated trading environment »), et le journal n'est visible que par le trader. Seul usage possible : comportement, étiqueté « simulé ».
- **Bybit copy trading or et devises :** lancé le 20.01.2025, donc moins de 2 ans d'historique. L'or y est un jeton crypto.
- **Kinfo :** actions américaines et day traders.
- **ZuluTrade :** conditions introuvables, non vérifié, à lire avant tout usage.
- **Forex Peace Army :** les anciens relevés sur l'or trouvés sont de la grille ou martingale (environ 600 achats sans stop). Seul usage possible : exemples négatifs.
- **Robbins World Cup :** seuls les pourcentages annuels du podium sont publiés, sans aucun trade. Petits comptes à levier extrême.
- **Données universitaires de particuliers** (OANDA, Hayley & Marsh, myForexBook) : privées, impossibles à obtenir. Leur conclusion : les particuliers perdent en moyenne.
- **Kaggle :** aucun historique réel vérifiable, surtout des tests sur le passé.

**Je n'ai pas trouvé 5 à 10 traders nommés avec des chiffres vérifiés publiquement et un style swing sur l'or.** C'est la vraie limite de ce marché : les bons traders en argent réel ne publient pas leurs trades. Le § 6 donne la méthode pour en trouver toi-même et les contacter.

---

## 3. Sources qui pourraient aider à choisir le SENS de l'or

### 🟡 Positionnement des fonds (CFTC, rapport « Commitments of Traders » désagrégé) — **TÉLÉCHARGÉ**
- **Ce qu'on obtient :** positions longues et courtes des fonds spéculatifs, banques, producteurs et petits comptes sur l'or et l'argent du COMEX, une fois par semaine, de 2006 à 2026.
- **Accès légal :** agence fédérale américaine, donc domaine public (17 U.S.C. § 105). Téléchargement direct sur https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm
- **Preuves :**
  - Fan, Fernandez-Perez, Fuertes, Miffre, *Speculative Pressure* (2018) : signal utile en plus du suivi de tendance sur 84 marchés, mais irrégulier. https://www.cxoadvisory.com/?p=31911
  - Kang et al. : sur matières premières, la partie du mouvement de la semaine due aux fonds tend à **se retourner** la semaine suivante. https://lingnan.sysu.edu.cn/en/event/3656
  - Coyle, Gogolin, Kearney (2019), sur l'or : les extrêmes de spéculation aident la prévision. https://eprints.whiterose.ac.uk/140400
- **Piège principal :** les positions du mardi ne sortent que le **vendredi**. Il faut aligner sur la date de publication, sinon l'IA lit le futur. Utiliser les **variations** plutôt que les niveaux.

### 🟢 Suivi de tendance sur plusieurs mois (pas une source de données, une règle prouvée)
- **Preuves :**
  - Moskowitz, Ooi, Pedersen, *Time Series Momentum* (2012), sur 58 marchés dont l'or.
  - Hurst, Ooi, Pedersen, *A Century of Evidence on Trend-Following* (1880-2016) : https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing (PDF : https://fairmodel.econ.yale.edu/ec439/hurst.pdf)
- **Utilisation :** comme **filtre de sens** pour MAGNETAR : n'acheter que si l'or monte sur 3 à 12 mois, et inversement.
- **Piège principal :** l'avantage vient surtout de la diversification. Sur l'or seul, il est faible, avec des années plates. Le taux de réussite tourne autour de 35-45 %, et ce sont les gros gains qui paient, ce qui correspond à ton style.

### 🟡 Réserves du fonds GLD — **TÉLÉCHARGÉ** (usage privé uniquement)
- **Ce qu'on obtient :** tonnes d'or détenues chaque jour par le plus gros fonds sur l'or, de 2004 à 2026.
- **Accès :** https://www.spdrgoldshares.com/usa/historical-data/. Clause : « Reproduction or redistribution… expressly prohibited without prior written consent », donc **jamais dans ton outil pour traders**.
- **Piège principal :** aucune étude sérieuse ne montre que les flux précèdent le prix (ils le suivent probablement). Les données sont publiées le lendemain.

### 🟡 Taux réels et dollar (FRED) — **TÉLÉCHARGÉ**
- Le lien avec l'or était très fort jusqu'en 2021 (R² de 84 %), puis s'est presque effondré : 3 % en 2022-23, 7 % depuis 2024, à cause des achats des banques centrales. Source : https://www.rbcwealthmanagement.com/en-us/insights/golds-regime-change ; Erb & Harvey : https://www.nber.org/papers/w18706
- **Utilisation :** comme filtre de « régime » seulement, il ne donne pas le sens.

### 🔴 À rejeter (pour l'instant)
- **Sentiment des particuliers (IG, Dukascopy, OANDA) :** aucune étude ne valide le signal « contrarien » sur l'or, et une étude sur 2 000 clients OANDA trouve même l'inverse (Nolte & Nolte 2016). Surtout, il n'existe pas d'historique propre, donc pas de test possible.
- **Heure de la journée / saisonnalité :** un mémoire de master (CBS 2019) trouve un effet « hausse en séance asiatique », qui disparaît après les frais. Possible fouille de données.

---

## 4. Livres et systèmes transparents

### 🟢 Curtis Faith, *Way of the Turtle* (2007) — règles complètes et reproductibles
- **Règles :** entrée sur cassure du plus haut ou plus bas de 20 ou 55 jours ; volatilité N = moyenne du vrai range sur 20 jours ; stop à 2N ; sortie sur cassure inverse de 10 ou 20 jours ; 1 % de risque par N. L'or COMEX faisait partie du portefeuille.
- **Pourquoi c'est utile :** c'est exactement « stop derrière la structure, gagnants laissés courir », et tu peux produire **des milliers de trades mentor** sur ton XAUUSD dans ton simulateur FTMO, sans aucun problème légal.
- **Piège principal :** sur l'or seul, résultats modestes, avec des drawdowns longs. Respecter la règle des 10 % totaux de FTMO demande de réduire la taille.

### 🟡 Peter Brandt, *Diary of a Professional Commodity Trader* (Wiley, 2011)
- **Contenu :** journal réel de décembre 2009 à avril 2010 (21 semaines), avec relevé de trades mensuel aux chapitres 8 à 12, et un chapitre 6 « A Year Trading Gold ». Nombre exact de trades et présence de l'or dans le journal : non vérifiés. Extrait : https://content.e-bookshelf.de/media/reading/L-582133-9774659112.pdf
- **Comment l'extraire légalement :** acheter le livre et recopier les trades à la main dans un CSV pour toi seul. En Suisse, la LDA art. 19 al. 1 let. a autorise l'usage privé. Les dates et les prix sont des faits, pas des œuvres (art. 2). Interdit : publier, partager ou vendre ce fichier, ou l'utiliser dans un produit commercial.
- **Piège principal :** quelques dizaines de trades sur 5 mois. C'est utile pour apprendre la gestion du risque, **inutilisable pour entraîner une IA**.

---

## 5. Classement final — les 10 meilleures pistes et l'action concrète

| # | Source | Fiabilité | Prochaine action concrète |
|---|---|---|---|
| 1 | **Règles des Turtles sur ton XAUUSD** | 🟢 | **Fait (exemple)** : `data\maitres\turtles_or\`, 264 et 119 trades 2004-2026. ⚠️ Tout le gain vient des achats, porté par la hausse de l'or ; les ventes perdent. Relancer `turtles_or.py` sur tes bougies MT5, en journalier puis en H4. |
| 2 | **Filtre tendance 3-12 mois** | 🟢 | Ajouter à MAGNETAR une entrée « rendement de l'or sur 3, 6 et 12 mois » et tester sur tes années jamais vues si le choix du sens bat enfin le hasard. |
| 3 | **gTrade, historique par trader** | 🟡 | **Fait** : `data\maitres\gtrade_api_personnelle\`. Relancer `gtrade_collect.py` chaque jour pour accumuler des adresses, et suivre les 4 traders swing gagnants listés dans le LISEZMOI. |
| 4 | **COT CFTC (variations hebdo)** | 🟡 | Fichier `cftc_cot/cot_desagrege_or_comex.csv` : décaler au vendredi de publication, calculer la variation de `M_Money_Net` et tester comme entrée du choix de sens. |
| 5 | **LSP (@winneryu), Darwinex** | 🟡 | Lui écrire via sa page DARWIN ou son profil (modèle au § 6) pour lui demander l'export de son relevé de courtier. |
| 6 | **cTrader Copy (comptes réels)** | 🟡 | Dans l'appli, à la main : filtrer or, compte réel, âge ≥ 2 ans, durée moyenne ≥ 4 h. Noter 10 noms, puis leur écrire. |
| 7 | **Données de positionnement des particuliers (OANDA, Dukascopy)** | 🟡 | Pas d'historique : commencer à enregistrer maintenant, une fois par jour, pour pouvoir tester dans 6 à 12 mois. *(GMX a été retiré : l'or n'y existe que depuis 2026.)* |
| 8 | **Réserves GLD** | 🟡 | Fichier `spdr_gld/gld_reserves_quotidiennes.csv` : tester `variation_tonnes` décalée d'un jour comme variable secondaire. |
| 9 | **Taux réels et dollar (FRED)** | 🟡 | Fichiers `fred/*.csv` : à utiliser comme indicateur de régime (avant et après 2022), pas comme signal. |
| 10 | **Livre de Peter Brandt** | 🟡 | Acheter le livre (≈ 30-60 CHF, prix non vérifié) et recopier ses trades à la main. Usage : règles de gestion du risque, pas l'entraînement. |

**À ne plus creuser :** FTMO/The5ers (simulé), Bybit (trop récent), Kinfo, Robbins, Kaggle, données universitaires, sentiment des particuliers, Tigris, Level, Rage, Drift, MUX.

---

## 6. Contacter des traders : méthode et message type

**Où les trouver (consultation manuelle uniquement) :**
- Darwinex : page de chaque DARWIN.
- cTrader Copy : messagerie du fournisseur de stratégie.
- Pages FX Blue publiques : le trader indique souvent un réseau social.
- Profils X (Twitter) liés.

**Filtre avant d'écrire :**
- compte réel ;
- au moins 2 ans ;
- durée moyenne des trades d'au moins 4 h ;
- taux de réussite entre 35 et 65 % ;
- aucune hausse de taille après une perte.

**Message type (en anglais, la plupart sont anglophones) :**
> Hi, I'm an independent developer in Switzerland building a private research model on gold swing trading. Your verified track record (live account, 2+ years, multi-hour holds) is exactly the kind of disciplined trading I want to study. Would you be willing to share an export of your closed-trade history (MT4/MT5 or cTrader statement, CSV or HTML)? It would be used only for private research, never published or resold, and I can send you the full statistical analysis of your trades in return. Thanks for considering it.

**Avant d'offrir quoi que ce soit en argent, c'est à toi de décider.** Un des rapports de recherche suggérait 50-200 CHF par historique, mais je n'ai rien vérifié sur ce point.

---

## 7. Fichiers déjà téléchargés (dans `data\maitres\`)

| Dossier | Contenu | Période | Droit |
|---|---|---|---|
| `cftc_cot\` | positionnement hebdomadaire or et argent COMEX | 2006 → 13.10.2026 (1 062 semaines) | domaine public |
| `fred\` | taux réel 10 ans, dollar, volatilité de l'or, inflation attendue | 2003/2008 → 16.10.2026 | libre ; volatilité (CBOE) en usage privé |
| `spdr_gld\` | réserves quotidiennes du fonds GLD | 18.11.2004 → 16.10.2026 | **privé uniquement** |

| `gtrade_api_personnelle\` | 2 260 trades sur l'or et l'argent, 90 traders, classement + scripts | 21.10.2024 → 19.10.2026 | API publique, trades sur chaîne |
| `turtles_or\` | trades Turtles systèmes 1 et 2 sur prix de l'or approché + script | 2004 → 2026 | règles publiques ; prix GLD en usage privé |

Chaque dossier contient un `LISEZMOI.md` (origine, date, colonnes, piège de décalage temporel).

**Non téléchargé, et pourquoi :**
- GMX : l'or y est trop récent (2026).
- Dune : plus nécessaire.
- FX Blue, cTrader : extraction interdite.

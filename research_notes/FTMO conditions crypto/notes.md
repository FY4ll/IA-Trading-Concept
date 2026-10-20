# FTMO : conditions crypto, règles pour une IA, économie — recherche du 16/10/2026

Sources officielles ftmo.com en priorité. Attention : `ftmo.oanda.com` = FTMO US (autre entité, autres règles :
levier 1:4 sur le bitcoin, etc.) — NE PAS confondre avec FTMO international (ftmo.com).
Les écarts et les frais de nuit exacts ne sont publiés nulle part : ils se lisent dans MT5 (clic droit sur le
symbole > Spécification), à relever sur un essai gratuit FTMO.

## 1. Cryptos chez FTMO

**32 cryptos** depuis le 28/07/2025 (10 anciennes + 22 nouvelles), aucune modification crypto trouvée dans les
mises à jour 2026 (seulement des pas de prix MANUSD/NEOUSD/DOTUSD changés le 28/08/2026).

| Groupe | Symboles | Taille du contrat | Volume max par ordre |
|---|---|---|---|
| Anciennes (10) | BTCUSD (1), ETHUSD (10), ADAUSD (100 000), DOTUSD (10 000), DASHUSD (1 000), LTCUSD (100), XRPUSD (10 000) | voir () | 5 lots |
| | DOGEUSD (100 000), XMRUSD (100), NEOUSD (1 000) | voir () | 1 lot |
| Nouvelles (22) | BCHUSD, BNBUSD, SANUSD, SOLUSD, AVAUSD, LNKUSD, NERUSD, ALGUSD, ETCUSD, ICPUSD, AAVUSD, BARUSD, GALUSD, GRTUSD, IMXUSD, MANUSD, MKRUSD, VECUSD, XLMUSD, UNIUSD, FETUSD, XTZUSD | dans MT5 | 5 ou 1 |

Sources : [Trading Update 17/07/2025](https://ftmo.com/en/blog/trading-updates/trading-update-17-jul-2025/),
[FTMO Enhances Crypto Trading, 25/07/2025](https://ftmo.com/en/blog/ftmo-enhances-crypto-trading-new-instruments-and-better-spreads/).
Pas de TRX ni TON dans la liste officielle (un site tiers les cite à tort). AVAUSD = Avalanche, LNKUSD = Chainlink,
NERUSD = Near, SANUSD = Sandbox, BARUSD = probablement Band, GALUSD = Gala, VECUSD = VeChain (abréviations FTMO).

- **Commission : 0,0325 % par côté** (0,065 % aller-retour), + écart. Nouveau modèle d'écarts « plus serrés »
  depuis le 28/07/2025, sans chiffre publié (mêmes sources).
- **Levier crypto : 1:3,3 en compte Normal, 1:1 en compte Swing**
  ([FTMO, réponses aux questions](https://ftmo.com/en/blog/a-few-answers-to-your-questions/),
  [Swing](https://ftmo.com/en/faq/ftmo-swing-account-type/)). Pour comparer : devises 1:100 / 1:30 ; or 1:50 / 1:15
  depuis le 01/02/2026 ([Trading Update 02/02/2026](https://ftmo.com/en/blog/trading-updates/trading-update-2-feb-2026/)).
- **Heures : cryptos tradables aussi le week-end**, sauf fenêtres de maintenance (ex. samedi 17/10/2026 3h-5h et
  8h-12h heure serveur +3 : trading coupé) ([Trading Updates](https://ftmo.com/en/trading-updates/),
  [Symboles](https://ftmo.com/en/symbols/) : « les heures du week-end des cryptos peuvent varier selon la plateforme »).
- **Frais de nuit (swap)** : appliqués chaque nuit, triple le mercredi, pas de compte sans swap ; taux non publiés
  (spécification MT5). Ordre de grandeur chez les courtiers crypto CFD : 10-25 %/an du montant (FTMO US affiche 24 %) —
  à vérifier sur l'essai, c'est un coût majeur pour garder une position plusieurs jours.
- **Week-end** : pendant le challenge et la vérification, garder des positions le week-end est permis (Normal et
  Swing). Sur le **compte financé Normal**, obligation de **fermer avant toute coupure de marché de plus de 2 h**
  (week-end compris) ; le compte **Swing** n'a pas cette contrainte
  ([FAQ week-end, version FTMO US](https://ftmo.oanda.com/faq/do-i-have-to-close-my-positions-overnight-or-before-weekend),
  [Swing](https://ftmo.com/en/faq/ftmo-swing-account-type/)). Point à faire confirmer par écrit : les maintenances
  crypto du samedi (≥ 2 h) obligent-elles à fermer les cryptos en compte Normal financé ?

## 2. Règles qui touchent une IA automatique

Source principale : [Forbidden Trading Practices](https://ftmo.com/en/forbidden-trading-practices/) (modifiée le 12/10/2026).

| Règle | Contenu |
|---|---|
| Programmes automatiques | **Permis** (« algorithmic approaches and expert advisors », [1-Step vs 2-Step](https://ftmo.com/lp/ftmo-challenge-1-step-vs-2-step/)) |
| Clause IA | Interdit d'utiliser « tout logiciel, intelligence artificielle, outil ultra-rapide ou saisie de masse » qui **manipule, abuse ou donne un avantage déloyal** (vise l'exploitation de failles, pas l'IA en soi — à faire confirmer par écrit) |
| Requêtes serveur | **Max 2 000 requêtes/jour** par compte (ouvertures, modifications de stop, fermetures) |
| Annonces | Compte Normal financé : aucune exécution (y compris stop/objectif) **2 min avant / 2 min après** les annonces ciblées, seulement sur les symboles concernés ; Swing : aucune restriction ([FAQ news](https://ftmo.com/en/faq/can-i-trade-news/)) |
| Trading des écarts d'ouverture | Interdit de se positionner juste avant grosses annonces ou ≤ 2 h avant une longue fermeture pour jouer l'écart |
| Couverture entre comptes | Interdit : positions opposées sur le même instrument ou instruments très liés entre comptes (à soi ou à d'autres) |
| Copie | Interdit qu'un tiers trade le compte ; trades identiques sur plusieurs comptes = comptés ensemble dans le plafond de 400 000 $ ([FAQ comptes](https://ftmo.com/en/faq/how-many-accounts-can-i-have/)) |
| Taille | Interdit de prendre des tailles ou un nombre de positions « nettement plus grands ou plus petits » que son habitude (ex. grosse mise juste avant le paiement) |
| Cohérence | **2-Step : aucune règle de cohérence.** 1-Step : meilleure journée ≤ 50 % du gain total (règle de cohérence remplaçant la « meilleure journée » depuis le 05/10/2026). Compte Instant : ≤ 30 % ([Trading Objectives](https://ftmo.com/en/trading-objectives/)) |
| Répartir artificiellement | Interdit de répartir le gain sur plusieurs jours sans répartir le risque (pour contourner la cohérence) |

Objectifs ([Trading Objectives](https://ftmo.com/en/trading-objectives/), [Comparatif](https://ftmo.com/en/comparison-table/)) :
- 2-Step : +10 % puis +5 %, perte du jour max 5 %, perte totale max 10 % (fixe), 4 jours de trading min, pas de limite de temps.
- 1-Step : +10 %, perte du jour max **3 %**, perte totale 10 % **glissante** pendant le challenge, cohérence 50 %.

## 3. Économie

| Compte | 2-Step | 1-Step |
|---|---|---|
| 100 000 $ | **540 €** | 499 € |
| 200 000 $ | **1 080 €** | 999 € |

Prix relevés le 01/09/2026 par [proptradingvibes](https://proptradingvibes.com/blog/ftmo-account-sizes-pricing)
(la page officielle n'affiche que « dès 89 € / 79 € » ; promotions fréquentes : -20 % sur le 1-Step 100K en ce moment).
- **Remboursement** : 2-Step remboursé avec le 1er paiement ; 1-Step et Instant jamais
  ([FAQ](https://ftmo.com/en/faq/is-the-entry-fee-refunded-after-passing-ftmo-challenge-1-step/)).
- **Partage** : 2-Step **80 %** (90 % avec le plan de croissance ou le programme Premium) ; 1-Step et Instant **90 %**
  ([FAQ retrait](https://ftmo.com/en/faq/how-do-i-withdraw-my-profits/)).
- **Retraits** : à la demande dès le 14e jour après le 1er trade ; positions fermées ; traitement 1-2 + 1-2 jours ouvrés.
- **Plafond** : **400 000 $ par trader ou par stratégie**, tous comptes confondus (ex. 4 x 100K ou 2 x 200K), nombre de
  comptes illimité ([FAQ](https://ftmo.com/en/faq/how-many-accounts-can-i-have/)).
- **Plan de croissance** : +25 % du capital tous les 4 mois si **≥ +10 % net sur les 4 mois**, ≥ 2 paiements pris,
  solde positif ; partage passe à 90 % ; jusqu'à **2 000 000 $** au total
  ([Plan de croissance](https://ftmo.oanda.com/reward-growth-and-scaling-plan/), texte identique sur ftmo.com).
  => il faut **≥ 2,5 %/mois en moyenne** pour grandir : à 1-2 %/mois, le capital reste bloqué.

### Ce que touche le trader (avant impôts, gain mensuel régulier supposé)

| Gain/mois du compte | 100 000 $ à 80 % | 100 000 $ à 90 % | 400 000 $ à 80 % | 400 000 $ à 90 % (1-Step) | 2 000 000 $ à 90 % (inatteignable à ce rythme) |
|---|---|---|---|---|---|
| +1 % | 800 $ | 900 $ | 3 200 $ | 3 600 $ | 18 000 $ |
| +1,5 % | 1 200 $ | 1 350 $ | 4 800 $ | 5 400 $ | 27 000 $ |
| +2 % | 1 600 $ | 1 800 $ | 6 400 $ | 7 200 $ | 36 000 $ |

Pour atteindre 400 000 $ : 4 challenges 100K réussis (4 x 540 €, remboursés au 1er paiement en 2-Step). Attention :
4 comptes avec la même IA = mêmes trades = la règle des 400 000 $ s'applique à la stratégie.

## 4. Autres sociétés (comparaison)

| Société | Marchés | Prix ~100K | Règles clés | Partage / paiements | Programmes auto |
|---|---|---|---|---|---|
| **Topstep** (futures CME) | Micro Bitcoin MBT (0,1 BTC), Micro Ether MET ([produits](https://help.topstep.com/en/articles/8284206-when-and-what-products-can-i-trade)) | abonnement 49-229 $/mois selon formule | objectif 6 000 $, perte max 3 000 $ **glissante**, meilleur jour < 50 % | 90 % depuis le 12/01/2026 ([TradersPost](https://blog.traderspost.io/article/topstep-review)) | **Oui via l'API TopstepX** (haute fréquence interdite) ([API](https://help.topstep.com/en/articles/11187768-topstepx-api-access)) |
| **FTMO Futures** | futures | 169-199 $/mois (100K) | cohérence 40-50 % | 90 %, paiements tous les 4-5 jours ([FTMO Futures](https://ftmo.com/en/futures/how-it-works/)) | à vérifier |
| **Apex Trader Funding** (futures) | futures CME | ~590 $ + 119 $ d'activation | objectif 6 000 $, cohérence 50 %, 6 paiements max | 100 % | **Robots entièrement automatiques interdits** (2026) ([QuantVPS](https://www.quantvps.com/blog/apex-trader-funding-automated-trading-bots)) |
| **Kraken Prop** (ex-Breakout, lancé 27/05/2026) | 60+ cryptos en contrats perpétuels, levier 5x BTC/ETH, 2x autres | 5 000 à 200 000 $ | pas de cohérence, pas de limite de temps | 80 % -> 90 % -> 95 %, sous 24 h en USDC ([Kraken](https://www.kraken.com/gb/learn/best-crypto-prop-firms), [Yahoo](https://finance.yahoo.com/markets/crypto/articles/kraken-prop-inside-funded-trader-183521927.html)) | « aucune restriction de stratégie » (à vérifier) |
| **The5ers** High Stakes | CFD dont cryptos | 149 $ en promo (été 2026) | +10 % / +5 %, -5 %/jour, -10 % | 80 % -> 100 %, paiement tous les 15 jours, plafond 4 000 $ ([The5ers](https://the5ers.com/high-stakes/)) | non vérifié |
| **FundedNext** Stellar 2-Step | CFD dont cryptos | 549,99 $ | +8 % / +5 % | 80 % (21 j), 90 % à la demande ([FundedNext](https://fundednext.com/cfds/stellar-2-step)) | non vérifié |

Coûts crypto à comparer : FTMO CFD = 0,065 % aller-retour + écart + frais de nuit ; futures CME micro = commission fixe
par contrat, **pas de frais de nuit** mais coupure quotidienne d'1 h et pas de week-end.

## À demander à FTMO par écrit avant de payer
1. Une IA faite maison (apprentissage, décisions toutes les 15 min, < 2 000 requêtes/jour) est-elle acceptée ?
2. Compte Normal financé : faut-il fermer les cryptos avant les maintenances du samedi ?
3. Taux de frais de nuit des cryptos.

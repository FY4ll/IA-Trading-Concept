# Piste « chef_crypto » : la stratégie du chef de projet sur les cryptos (16/10/2026)

Code : `collapsar/regarder/pistes/chef_crypto.py` (cahier des charges dans l'en-tête, écrit avant les résultats).
Chiffres : `btc_eth.json`, `developpement.json`, `confirmation.json` (verrou : le groupe B a été ouvert une seule fois),
trades dans les `.csv`, journaux `journal_*.txt`.

## Ce qui a été testé, fidèlement
Sa méthode n'a pas été simplifiée : zones zones supply and demand (traduction exacte de son indicateur), zones gigognes (zone H4, puis la
plus petite zone dedans en descendant H1 -> M30 -> M15), entrée au milieu de la plus petite zone, stop derrière la zone
avec un minimum de 0,2 jour d'agitation, sorties par tiers (2 R, sommet H1, zone opposée). Le code du laboratoire est
appelé tel quel. Ce qui change : les frais des cryptos, **les frais de nuit** (30 %/an chez FTMO sur les cryptos,
absents du calcul précédent), les données (bougies Binance 7 jours sur 7, filtre commun du coordinateur) et le juge.

| Variante | Règle |
|---|---|
| V1 | Sa version figée « Gigogne H4 stop A plancher 0.2 » |
| V2 | La même avec départ H1 (cascade 3 de sa méthode) : la version à plus de trades |
| K1 | V1, seulement si la cassure 24 h est partie le même jour, dans le même sens, avant l'entrée |
| K2 | Cassure 24 h, seulement si elle sort d'une de ses zones H4 vivante, touchée dans les 24 h |

Frais par aller-retour : BTC 0,03 %, ETH 0,05 %, autres cryptos 0,05 %. Compte : risque 0,5 % par trade (exposition au
plus 1 fois le compte, levier crypto FTMO 1:1). Jumeau = mêmes moments, même taille, sens tiré à pile ou face.

## 1. Bitcoin et ether (déjà vus : pour information seulement)
- Contrôle de fidélité sur les données du projet : V1 = 85 trades sur BTC à +0,30 R (le coordinateur avait +0,31) et
  95 trades sur ETH à +0,30 R (+0,33). **Avec les frais de nuit : +0,22 et +0,18 R.**
- Sur les bougies Binance 7 jours sur 7, V1 tombe à 42 trades sur BTC (-0,14 R) et 80 sur ETH (-0,22 R). Les données
  du projet n'ont pas de week-end avant 2020 : les trous du week-end fabriquent des zones qui n'existent pas sur un
  graphique continu. Sur BTC, le gain venait surtout de 2020 (11 trades à +2,6 R).

| BTC + ETH, Binance | trades | R moyen | R médian | gagnants | force | %/mois |
|---|---|---|---|---|---|---|
| V1 sa version | 122 | -0,19 | -1,04 | 37 % | -0,5 | -0,11 |
| V2 départ H1 | 297 | -0,03 | -1,05 | 34 % | -0,2 | -0,03 |
| K1 | 45 | -0,35 | -1,04 | 33 % | -0,6 | -0,08 |
| K2 | 143 | +0,09 | -0,07 | 45 % | +1,4 | +0,06 |

## 2. Terrain neuf : 23 autres cryptos Binance
Groupe A (développement, 12) : ADA, ATOM, BCH, DOGE, EOS, FIL, LTC, NEAR, SOL, UNI, XLM, XRP.
Groupe B (confirmation, 11) : ALGO, AVAX, BNB, DOT, ETC, LINK, MATIC, POL, TRX, VET, XMR.

Développement (groupe A), toutes années, nuit comprise :

| Variante | trades | R moyen | avant 2022 | 2022 et après | force | %/mois | baisse max | challenges réussis / morts (jumeaux) |
|---|---|---|---|---|---|---|---|---|
| **V1 sa version** | 463 | **+0,29** | +0,08 | +0,36 | +2,5 | +0,65 | -16 % | 76 / 18 % (32 / 54 %) |
| V2 départ H1 | 1 510 | -0,04 | +0,04 | -0,06 | +0,6 | -0,25 | -51 % | 20 / 74 % (11 / 82 %) |
| K1 | 205 | +0,30 | **-0,10** | +0,44 | +2,1 | +0,32 | -14 % | 52 / 37 % (19 / 44 %) |
| K2 | 667 | -0,04 | -0,05 | -0,04 | -0,8 | -0,14 | -23 % | 0 / 74 % (2 / 46 %) |

Règle écrite d'avance : seule **V1, sa version figée**, est positive sur les deux moitiés -> retenue.

Confirmation (groupe B, une seule fois) : V1

| Période | trades | R moyen | R médian | gagnants | force | %/mois | baisse max | pire jour | challenges réussis / morts | jumeaux |
|---|---|---|---|---|---|---|---|---|---|---|
| avant 2022 | 111 | +0,24 | -1,03 | 32 % | +0,4 | +0,28 | -14 % | -1,5 % | 52 / 5 % | 8 / 19 % |
| 2022-2023 | 125 | +0,39 | -1,05 | 37 % | +1,5 | +0,99 | -8 % | -2,0 % | 27 / 0 % | 4 / 21 % |
| 2024-2026 | 167 | +0,18 | -1,05 | 39 % | +1,5 | +0,41 | -16 % | -2,1 % | 7 / 63 % | 3 / 44 % |
| **tout** | **403** | **+0,26** | -1,04 | 36 % | **+1,9** | +0,49 | -16 % | -2,1 % | 58 / 33 % | 16 / 70 % |

**Verdict de la règle : confirmée (positive, plus forte que son jumeau), mais pas prouvée (force 1,9 < 3).**

## Verdict
- Sur les cryptos, sa méthode figée tient debout là où les frais la tuaient ailleurs : +0,29 R sur le groupe A et
  +0,26 R sur le groupe B, jamais vu, nuit comprise. Les deux groupes ensemble : 866 trades, +0,28 R, force 3,1,
  +1,1 %/mois. C'est le résultat le plus encourageant de sa stratégie à ce jour, mais ce chiffre réuni a été regardé
  après coup : il ne vaut pas preuve.
- Son profil est celui d'un suiveur de tendance : 36 % de gagnants, perte médiane -1 R, gain qui vient de quelques
  grosses sorties à la zone opposée. **Sans ses 10 meilleurs trades, elle est à plat** (-0,10 R groupe A, -0,24 R
  groupe B). 2 trades du groupe A ont profité du krach éclair du 10/10/2025, gardé tel quel sur consigne (+24 R) :
  sans eux, le groupe A fait +0,24 R.
- Ce qui n'apporte rien : départ H1 (plus de trades, mais plus d'avantage et une baisse de 51 %), et les deux
  combinaisons avec la cassure 24 h (K1 négative avant 2022, K2 nulle).
- BTC et ETH eux-mêmes ne sont pas ses bons terrains sur des données 7 jours sur 7 (négatifs).
- Pour FTMO : en tradant 11 à 12 cryptos à 0,5 % de risque par trade, la baisse max atteint 16 % par groupe (30 %
  pour les 23 ensemble) : au-delà du mur de -10 %. Les challenges réussissent plus souvent que les jumeaux (58 % contre
  16 % sur le groupe B), mais 33 % meurent ; en 2024-2026 sur le groupe B, 63 % meurent.

## Ce qui manquerait
1. Trouver les cryptos réellement cotées chez FTMO (aujourd'hui BTC, ETH, LTC, XRP... ) : le terrain où elle gagne est
   celui des « autres » cryptos, pas toutes disponibles en CFD.
2. Une taille plus petite (0,25 % par trade) ou un plafond de positions ouvertes ensemble, à décider AVANT de regarder,
   pour ramener la baisse sous 10 %.
3. Le direct : c'est le seul juge neuf qui reste ; à suivre à blanc sur les cryptos disponibles chez FTMO.
4. Limite connue : en bougies de 15 min, la bougie d'entrée n'est pas suivie après le remplissage (comme dans le
   laboratoire) ; un trade ETH du 20/05/2024 perd ainsi -8 R d'un coup.

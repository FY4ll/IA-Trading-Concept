# Piste « chef_compte_ftmo » : un compte FTMO 100 000 $ qui applique la stratégie du chef de projet (16/10/2026)

Code : `collapsar/regarder/pistes/chef_compte_ftmo.py` (cahier des charges dans l'en-tête, écrit avant les résultats).
Chiffres : `resultats.json`, trades `trades_v1.csv`, journal `journal_compte.txt`, challenges départ par départ
`cache/challenges_*.npy`.

**À lire d'abord : toutes ces années ont déjà été vues pour V1** (piste chef_crypto, groupes A et B). Ce qui suit est
une **estimation de ce que donnerait un compte**, pas une preuve que la méthode gagne.

## Ce qui a été simulé
- **Sa méthode, sans rien changer** : V1 « Gigogne H4 stop A plancher 0.2 » (zones zones supply and demand H4, descente H1 -> M30 -> M15,
  entrée au milieu de la plus petite zone, stop derrière la zone, sorties par tiers 2 R / sommet H1 / zone opposée).
  Contrôle : la sortie recalculée ici donne exactement le même résultat que chef_crypto, trade par trade.
- **19 cryptos présentes chez FTMO et dans les données Binance** : BTC, ETH, ADA, DOT, LTC, XRP, DOGE, XMR, BCH, BNB,
  SOL, AVAX, LINK, NEAR, ALGO, ETC, XLM, UNI, VET (filtre Binance commun). 802 signaux de 2017 à 10/2026.
- **Frais FTMO** : commission 0,065 % + écart 0,03 % (BTC 0,0015 %), le tout x 1,25 = 0,12 % par aller-retour (plus de
  2 fois les 0,05 % de chef_crypto) ; nuits 30 %/an.
- **Compte Swing** (levier crypto 1:1), règles figées avant : **0,25 % du solde par trade, 4 positions au plus, 1 par
  crypto, arrêt du jour à -2 % (latent compris), risque divisé par 2 près du mur des -10 %.** Le compte est suivi bougie
  de 15 min par bougie de 15 min, au plus mauvais prix de chaque bougie (comme le compteur de FTMO).
- **Challenges** : un départ tous les 10 jours (332 départs), +10 % puis +5 %, mort à -5 % dans la journée ou -10 %,
  4 jours de trading minimum ; contre 20 jumeaux (mêmes moments, même taille, sens tiré à pile ou face). Puis compte
  financé 12 mois (retrait tous les 30 jours, 80 % pour le trader) et espérance d'un challenge à 540 €.

## Résultat principal : sa gestion (A), politique figée 0,25 % / 4 positions

| Période | trades/mois | gain %/mois | baisse max | pire jour | challenges réussis / morts / inachevés (jumeaux) | réussis en moins de 12 mois (jumeaux) | financé 12 mois : survie, gain/mois | espérance par challenge (jumeaux) | si abandon après 12 mois (jumeaux) |
|---|---|---|---|---|---|---|---|---|---|
| avant 2022 | 4,1 | -0,05 % | -10,8 % | -1,3 % | 68 / 0 / 32 % (6 / 90) | 13 % (1 %) | 100 %, +0,02 % | +8 € (-413) | -438 € (-531) |
| 2022-2023 | 8,2 | +0,51 % | -10,0 % | -1,8 % | 7 / 0 / 93 % (3 / 69) | 5 % (0 %) | 100 %, +0,00 % (5 cas) | -540 € (-326) | -540 € (-537) |
| 2024-2026 | 9,5 | +0,20 % | -12,0 % | -1,6 % | 8 / 0 / 92 % (2 / 14) | 8 % (1 %) | 100 %, +0,01 % (8 cas) | +84 € (-294) | -463 € (-513) |
| **tout** | **6,6** | **+0,15 %** | **-12,4 %** | **-1,8 %** | **36 / 0 / 64 %** (4 / 62) | **10 %** (1 %) | 100 %, +0,02 % | -9 € (-391) | **-469 €** (-529) |

Lecture : « baisse max » se mesure depuis le plus haut atteint ; partant de 100 000 $, le compte n'a jamais touché le mur
des -10 % ni une journée à -5 %. « Espérance » = moyenne des challenges dont l'issue est connue (les inachevés sont
exclus) ; la colonne « abandon après 12 mois » compte un challenge non réussi en 12 mois comme 540 € perdus (lecture
ajoutée après avoir vu le grand nombre d'inachevés ; ce n'est pas un réglage).

## En information (rien n'est choisi sur ces chiffres)

| Combinaison (toutes années) | gain %/mois | baisse max | pire jour | réussis / morts / inachevés (jumeaux) | en moins de 12 mois (jumeaux) | financé : survie, gain/mois | espérance (jumeaux) | abandon 12 mois (jumeaux) |
|---|---|---|---|---|---|---|---|---|
| A, 0,5 % / 6 positions | -0,03 % | -25,7 % | -3,5 % | 50 / 45 / 5 % (15 / 77) | 31 % (7 %) | 76 %, +0,23 % | +765 € (-307) | +481 € (-404) |
| B (80 % à 2 R, 20 % zone opposée, stop à l'entrée), 0,25 % / 4 | +0,12 % | -9,2 % | -1,8 % | 13 / 0 / 87 % (3 / 50) | 0 % (0 %) | 100 %, +0,00 % | -540 € (-429) | -540 € (-540) |
| B, 0,5 % / 6 positions | -0,03 % | -16,8 % | -2,3 % | 31 / 54 / 15 % (5 / 81) | 17 % (2 %) | 89 %, +0,32 % | +675 € (-457) | +153 € (-507) |

A, 0,5 % / 6 positions, par période : avant 2022 +763 € (abandon 12 mois), 2022-2023 +192 €, 2024-2026 +126 € ; mais
45 % des challenges meurent et le compte continu perd légèrement sur l'ensemble (-0,03 %/mois, baisse -26 %).

Par trade (sans les règles du compte), frais FTMO compris : **gestion A +0,19 R** (802 trades, 37 % de gagnants,
force 2,5 contre le jumeau ; +0,12 / +0,31 / +0,17 R selon la période) ; gestion B +0,11 R (force 2,8). Avec les frais
de chef_crypto (0,05 %), V1 faisait +0,28 R : les frais FTMO coûtent environ 0,1 R par trade.

## Verdict honnête
1. **Sa méthode garde l'avantage sur le hasard dans un vrai compte** : avec la même politique, les jumeaux meurent
   dans 62 % des challenges, son compte dans 0 %. Le compte est très sûr : pire jour -1,8 %, jamais près des -5 %.
2. **Mais avec 0,25 % par trade, il est trop lent pour FTMO** : +0,15 %/mois en moyenne, seulement 10 % des challenges
   réussis en moins d'un an (il faut en médiane 17 mois quand ça réussit), et le compte financé rapporte presque rien
   (+0,02 %/mois, environ 170 € par an pour le trader). Espérance réaliste (abandon après un an) : **-469 € par
   challenge** (jumeaux -529 €).
3. Doubler le risque (0,5 %, information) fait passer plus de challenges (31 % en moins d'un an) et donne une espérance
   positive estimée (+481 €), mais 45 % des challenges meurent et la baisse atteint 26 % : ce n'est pas une piste à
   régler sur ces années déjà vues (ce serait ajuster après coup).
4. Sa gestion « 80 % à 2 R » (B) coupe les grosses sorties à la zone opposée, qui font le gain de sa méthode : moins de
   baisse (-9 %), mais encore plus lente ; avec 0,25 %, aucun challenge réussi en moins d'un an.
5. Constat utile : la règle « 1 position par crypto » écarte une cinquantaine de signaux (46 avec la politique figée)
   qui valaient ensemble environ +38 R (mesuré sans plafond de 4 positions) : ses
   meilleurs trades arrivent souvent en série sur la même crypto pendant une forte tendance.

## Limites
- Années déjà vues (voir plus haut) ; prix Binance, pas ceux de FTMO ; écarts et nuits réels des cryptos FTMO non
  publiés (30 %/an supposé) ; 11 des 19 cryptos ne sont chez FTMO que depuis le 28/07/2025.
- Bougies de 15 min : le pire prix de chaque bougie est pris au même instant pour toutes les positions (prudent).
- Retraits du financé supposés possibles même avec des positions ouvertes ; 1 € = 1,116 $ (dernier cours EURUSD).

## Ce qui manquerait pour aller plus loin
1. **Le direct à blanc** sur les 19 cryptos avec la politique figée : c'est le seul juge neuf.
2. **Relever les vrais frais** (écart et nuit de chaque crypto) sur l'essai gratuit FTMO : 0,1 R de frais en plus ou en
   moins change tout à cette taille.
3. Si le chef de projet veut une autre taille de risque, la **décider avant** de regarder de nouvelles données (le direct),
   pas sur ce tableau.

# Piste « hyrotrader » : C1 seul, puis C1 + cassure C2, chez HyroTrader (compte 100 000 $, 2 étapes) — 16/10/2026

Code : `collapsar/regarder/pistes/hyrotrader.py` (cahier des charges dans l'en-tête, écrit AVANT les résultats).
Chiffres : `resultats.json` (12 comptes), `sensibilite.json` (ajout après lecture, information), journaux `journal.txt`,
`sortie.txt` ; challenges départ par départ `cache/challenges_*.npy` (vrai + 20 jumeaux).

**À lire d'abord : ESTIMATION sur des années déjà vues** (2020 -> 09/2026 ont servi à régler C1 et la cassure). Ce
n'est pas une preuve. Une seule liste fermée de 12 comptes a été calculée (2 stratégies x 2 coûts x 3 niveaux de
risque), tout est publié. Seul le direct jugera.

## 1. Règles HyroTrader relevées sur hyrotrader.com (16/10/2026)
| Règle | Valeur (2 étapes, 100 000 $) | Source |
|---|---|---|
| Objectifs | +10 % puis +5 %, au moins 5 jours de trading par étape, pas de limite de temps | page d'accueil |
| Perte du jour | 5 % du capital de départ (5 000 $), gains latents compris, remise à zéro 00h00 UTC. Version standard « suiveuse » = depuis le **plus haut du jour** ; version « fixe » (depuis le début du jour) = option payante « Swing ». **Attention : la page « comment est calculée la perte du jour » décrit la version fixe** : les deux pages se contredisent | FAQ règles |
| Perte totale | 10 % fixe (90 000 $) | page d'accueil, comparatifs |
| Perte réalisée d'un trade | au plus 3 % du capital de départ (contrôle manuel) ; stop non obligatoire | FAQ règles |
| Règle des 40 % | à l'examen seulement : un jour (trades fermés) compte pour au plus 40 % de l'objectif ; le surplus reste sur le compte mais ne compte pas | FAQ restrictions |
| Taille | valeur des positions <= 2 x le capital de départ ; altcoins de petite capitalisation <= 5 % | page « futures », FAQ |
| Robots | autorisés par API (pas de copie de signaux, pas de haute fréquence) | FAQ |
| Retraits | sur demande, toutes positions fermées, **au plus 5 % du capital par retrait ; le gain au-delà de 5 % non retiré n'est pas payé** | FAQ paiements |
| Partage | 80 % (jusqu'à 90 % « à la discrétion » de la société, non automatique) ; prix remboursé au 1er paiement | FAQ |
| Prix | 599 $ (comparatif 10/2026 ; 579 $ dans un article HyroTrader de 07/2026) | thetrustedprop, blog HyroTrader |
| Capital maximum | 200 000 $ par trader | comparatifs |
| Comptes | **100 % simulés** (« il n'y a jamais d'étape avec de l'argent réel ») | FAQ |

## 2. Ce qui a été simulé
- **Prix** : bougies de 15 min du **perpétuel** Binance (même instrument que Bybit), heure UTC ; **financement réel**
  payé ou reçu à chaque règlement ; filtre commun du coordinateur ; le krach réel du 10/10/2025 est gardé.
- **(A) C1 seul** sur les 25 cryptos de `data/binance/` (C1 existe pour le bitcoin depuis 10/2020, pour les autres
  depuis 01/2022) : au plus 8 positions, 5 dans le même sens, stop 1,5 x agitation du jour, sortie 24 h.
- **(B) C1 + cassure C2** (BTC, ETH, lundi -> vendredi, fermée à 23h45 serveur), moitié du risque chacune ; C1 au plus 6
  positions (4 dans le même sens), plafond total 8.
- **Coûts** (x 1,25 de glissement prudent) : (1) tout en preneur 0,055 %/côté ; (2) 70 % faiseur 0,02 % / 30 % preneur à
  l'entrée et à la sortie normale, preneur sur un stop ou un arrêt de sécurité (hypothèse optimiste : ordres faiseurs
  remplis au prix voulu).
- **Taille** : agitation visée 9 / 12 / 15 %/an, calée une fois sur l'agitation seulement (C1 sur 03/2022-02/2023, C2
  sur 2020-2021). Montants fixes en dollars. C1 : 0,19 / 0,26 / 0,32 % de risque par trade en (A) ; 0,17 / 0,22 / 0,28 %
  en (B), cassure c = 0,30 / 0,41 / 0,51 %.
- **Sécurité** : stop de chaque trade <= 2,5 % du capital, arrêt interne à -3 % depuis le plus haut du jour UTC, valeur
  ouverte <= 2 x le capital.
- **Lecture prudente du plus haut du jour** : chaque bougie, fonds au pire prix comparés au plus haut atteint avant,
  plus haut mis à jour au meilleur prix de la bougie.
- **Financé** : retrait tous les 7 jours si le gain dépasse 125 $ (plafonné à 5 000 $), le compte revient à 100 000 $ ;
  12 mois ; espérance = -599 $ + 599 $ remboursés au 1er paiement + 80 % des retraits.
- **Jumeaux** : 20 comptes identiques où le sens de chaque trade est tiré à pile ou face.
- Contrôle : les trades de la cassure tombent exactement sur la grille UTC (prix d'entrée identiques à 100 %).

## 3. Résumé (meilleurs comptes et comptes de référence)
| Compte | Période | %/mois | Baisse max | Challenges réussis / morts (jumeaux) | Réussis < 12 mois | Espérance par challenge (jumeaux) | Revenu 200 k$ durable |
|---|---|---|---|---|---|---|---|
| A, faiseur 70 %, 12 % | 2022-2023 | +1,46 % | -12,8 % | 63 / 37 % (0 / 90) | 44 % | +1 943 $ (-593) | +430 $/mois |
| A, faiseur 70 %, 12 % | 2024 -> 09/2026 | +0,97 % | -13,9 % | 36 / 33 % (0 / 76) | 22 % | +1 555 $ (-599) | +325 $/mois |
| A, faiseur 70 %, 15 % | 2022-2023 | +1,83 % | -16,4 % | 63 / 37 % (1 / 99) | 47 % | +3 870 $ (-579) | +900 $/mois |
| A, faiseur 70 %, 15 % | 2024 -> 09/2026 | +1,06 % | -17,4 % | 55 / 41 % (1 / 88) | 49 % | +4 449 $ (-563) | +881 $/mois |
| A, preneur, 12 % | 2024 -> 09/2026 | +0,54 % | -16,9 % | 31 / 47 % (0 / 83) | 9 % | -121 $ (-599) | -27 $/mois |
| B, faiseur 70 %, 12 % | 2022-2023 | +1,51 % | -11,9 % | 92 / 8 % (1 / 98) | 47 % | +4 077 $ (-586) | +524 $/mois |
| B, faiseur 70 %, 12 % | 2024 -> 09/2026 | +1,16 % | -15,4 % | 36 / 36 % (0 / 77) | 24 % | +1 725 $ (-587) | +321 $/mois |
| B, preneur, 12 % | 2024 -> 09/2026 | +0,52 % | -19,5 % | 1 / 79 % (0 / 84) | 0 % | -599 $ (-599) | -130 $/mois |

Comptes financés : **presque aucun ne vit 12 mois** dès 12 % d'agitation (survie 0 à 2 % sur 2022-2026) ; l'espérance
positive vient des retraits faits AVANT la mort. Deux causes : le krach du **10/10/2025** (-6,6 à -10,9 % depuis le plus
haut du jour en une journée : tous les comptes vivants ce jour-là meurent, l'arrêt interne à -3 % n'a pas le temps
d'agir sur des bougies de 15 min) et la baisse de 11/2025 à 05/2026 (-13 à -15 %) contre un mur fixe à 90 000 $ que les
retraits hebdomadaires ne laissent jamais s'éloigner.

## 4. Tableau complet (12 comptes x 3 périodes)
« Jours > 5 % » = jours où le compte continu aurait cassé la perte du jour suiveuse. Force = force contre le jumeau
(information, trades pris, sortie prévue). « Financé » = cas, survie 12 mois, gain mensuel (retraits / 100 000 / 12).
2020-2021 : (A) commence le 05/10/2020 avec le bitcoin seul (C1 n'existe pas avant), (B) le 30/01/2020.

|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A, preneur, niveau 9 % | 2020-2021 | +0,29 % | -0,9 % | -1,4 % | 0 | 2,3 / - | 98 / 0 % (0 / 78) | 0 / 0 / 0 % | 20 % (6 j) | 0 | -599 (-599) | -100 / - |
| A, preneur, niveau 9 % | 2022-2023 | +0,85 % | -11,0 % | -3,8 % | 0 | 4,8 / - | 21 / 15 % (0 / 96) | 0 / 0 / 18 % | 27 % (6 j) | 13, 23 %, 0,21 % | -133 (-599) | -21 / +344 |
| A, preneur, niveau 9 % | 2024 -> 09/2026 | +0,41 % | -12,7 % | -6,5 % | 1 | 3,6 / - | 6 / 47 % (0 / 74) | 0 / 0 / 0 % | 0 % (0 j) | 0 | -599 (-599) | -124 / - |
| A, faiseur 70 %, niveau 9 % | 2020-2021 | +0,31 % | -0,9 % | -1,4 % | 0 | 2,3 / - | 100 / 0 % (0 / 57) | 0 / 0 / 2 % | 7 % (0 j) | 1, 100 %, 1,39 % | -296 (-599) | -48 / +2 222 |
| A, faiseur 70 %, niveau 9 % | 2022-2023 | +1,17 % | -9,6 % | -3,8 % | 0 | 4,8 / - | 97 / 0 % (0 / 83) | 0 / 1 / 27 % | 35 % (54 j) | 20, 100 %, 0,86 % | +1 838 (-599) | +255 / +1 383 |
| A, faiseur 70 %, niveau 9 % | 2024 -> 09/2026 | +0,73 % | -10,4 % | -6,5 % | 1 | 3,6 / - | 31 / 30 % (0 / 66) | 0 / 0 / 6 % | 0 % (0 j) | 6, 0 %, 0,05 % | -537 (-599) | -117 / +78 |
| A, preneur, niveau 12 % | 2020-2021 | +0,39 % | -1,2 % | -1,9 % | 0 | 2,3 / - | 100 / 0 % (0 / 90) | 0 / 0 / 24 % | 45 % (3 j) | 11, 0 %, 0,96 % | +1 741 (-599) | +256 / +1 531 |
| A, preneur, niveau 12 % | 2022-2023 | +1,03 % | -14,6 % | -5,1 % | 1 | 4,8 / - | 48 / 47 % (0 / 98) | 0 / 3 / 33 % | 34 % (3 j) | 24, 0 %, 0,34 % | +642 (-599) | +148 / +546 |
| A, preneur, niveau 12 % | 2024 -> 09/2026 | +0,54 % | -16,9 % | -8,7 % | 1 | 3,7 / - | 31 / 47 % (0 / 83) | 0 / 0 / 9 % | 5 % (0 j) | 9, 0 %, 0,30 % | -121 (-599) | -27 / +478 |
| A, faiseur 70 %, niveau 12 % | 2020-2021 | +0,42 % | -1,2 % | -1,9 % | 0 | 2,3 / - | 100 / 0 % (0 / 76) | 0 / 0 / 33 % | 29 % (1 j) | 15, 0 %, 1,32 % | +3 719 (-599) | +517 / +2 107 |
| A, faiseur 70 %, niveau 12 % | 2022-2023 | +1,46 % | -12,8 % | -5,1 % | 1 | 4,8 / - | 63 / 37 % (0 / 90) | 1 / 16 / 44 % | 39 % (9 j) | 32, 0 %, 0,56 % | +1 943 (-593) | +430 / +889 |
| A, faiseur 70 %, niveau 12 % | 2024 -> 09/2026 | +0,97 % | -13,9 % | -8,7 % | 1 | 3,7 / - | 36 / 33 % (0 / 76) | 0 / 0 / 22 % | 28 % (6 j) | 22, 0 %, 0,60 % | +1 555 (-599) | +325 / +963 |
| A, preneur, niveau 15 % | 2020-2021 | +0,48 % | -1,5 % | -2,4 % | 0 | 2,3 / - | 100 / 0 % (1 / 96) | 0 / 0 / 35 % | 25 % (2 j) | 16, 0 %, 1,29 % | +3 913 (-599) | +545 / +2 062 |
| A, preneur, niveau 15 % | 2022-2023 | +1,30 % | -19,4 % | -6,4 % | 1 | 5,0 / - | 44 / 56 % (0 / 100) | 0 / 10 / 33 % | 47 % (17 j) | 24, 0 %, 0,65 % | +1 644 (-595) | +428 / +1 037 |
| A, preneur, niveau 15 % | 2024 -> 09/2026 | +0,53 % | -21,2 % | -10,9 % | 2 | 3,6 / - | 36 / 60 % (0 / 92) | 1 / 3 / 19 % | 43 % (16 j) | 19, 0 %, 0,46 % | +846 (-598) | +181 / +732 |
| A, faiseur 70 %, niveau 15 % | 2020-2021 | +0,52 % | -1,5 % | -2,4 % | 0 | 2,3 / - | 100 / 0 % (2 / 86) | 0 / 0 / 43 % | 14 % (1 j) | 20, 20 %, 1,94 % | +7 749 (-599) | +1 014 / +3 100 |
| A, faiseur 70 %, niveau 15 % | 2022-2023 | +1,83 % | -16,4 % | -6,4 % | 1 | 5,0 / - | 63 / 37 % (1 / 99) | 4 / 27 / 47 % | 49 % (9 j) | 34, 0 %, 0,94 % | +3 870 (-579) | +900 / +1 505 |
| A, faiseur 70 %, niveau 15 % | 2024 -> 09/2026 | +1,06 % | -17,4 % | -10,9 % | 2 | 3,6 / - | 55 / 41 % (1 / 88) | 2 / 15 / 49 % | 30 % (5 j) | 49, 2 %, 0,65 % | +4 449 (-563) | +881 / +1 034 |
| B, preneur, niveau 9 % | 2020-2021 | +0,37 % | -6,2 % | -4,7 % | 0 | 2,4 / 2,1 | 42 / 0 % (0 / 86) | 0 / 0 / 0 % | 48 % (20 j) | 0 | -599 (-599) | -100 / - |
| B, preneur, niveau 9 % | 2022-2023 | +0,88 % | -10,5 % | -3,5 % | 0 | 4,6 / 2,6 | 51 / 0 % (0 / 99) | 0 / 0 / 4 % | 64 % (64 j) | 3, 100 %, 0,36 % | -432 (-599) | -70 / +578 |
| B, preneur, niveau 9 % | 2024 -> 09/2026 | +0,38 % | -14,6 % | -4,9 % | 0 | 3,2 / 2,9 | 0 / 44 % (0 / 76) | 0 / 0 / 0 % | - | 0 | -599 (-599) | -102 / - |
| B, faiseur 70 %, niveau 9 % | 2020-2021 | +0,55 % | -5,4 % | -4,7 % | 0 | 2,4 / 2,1 | 92 / 0 % (0 / 72) | 0 / 0 / 4 % | 45 % (10 j) | 3, 100 %, 1,20 % | -89 (-599) | -14 / +1 913 |
| B, faiseur 70 %, niveau 9 % | 2022-2023 | +1,33 % | -9,6 % | -3,5 % | 0 | 4,6 / 2,6 | 100 / 0 % (0 / 90) | 1 / 7 / 48 % | 30 % (8 j) | 35, 100 %, 1,02 % | +4 375 (-598) | +537 / +1 629 |
| B, faiseur 70 %, niveau 9 % | 2024 -> 09/2026 | +0,86 % | -11,6 % | -4,9 % | 0 | 3,2 / 2,9 | 55 / 2 % (0 / 58) | 0 / 0 / 5 % | 43 % (33 j) | 5, 0 %, 0,19 % | -437 (-599) | -72 / +300 |
| B, preneur, niveau 12 % | 2020-2021 | +0,51 % | -8,1 % | -6,3 % | 1 | 2,4 / 2,1 | 4 / 76 % (0 / 99) | 0 / 0 / 4 % | 33 % (17 j) | 3, 0 %, 0,03 % | -579 (-599) | -128 / +47 |
| B, preneur, niveau 12 % | 2022-2023 | +0,92 % | -13,1 % | -4,7 % | 0 | 4,6 / 2,8 | 25 / 22 % (0 / 100) | 0 / 0 / 0 % | 69 % (130 j) | 0 | -599 (-596) | -106 / - |
| B, preneur, niveau 12 % | 2024 -> 09/2026 | +0,52 % | -19,5 % | -6,6 % | 1 | 3,2 / 2,9 | 1 / 79 % (0 / 84) | 0 / 0 / 0 % | 50 % (140 j) | 0 | -599 (-599) | -130 / - |
| B, faiseur 70 %, niveau 12 % | 2020-2021 | +0,76 % | -7,2 % | -6,3 % | 1 | 2,4 / 2,1 | 28 / 72 % (0 / 91) | 0 / 0 / 24 % | 65 % (19 j) | 17, 0 %, 0,20 % | -48 (-599) | -11 / +313 |
| B, faiseur 70 %, niveau 12 % | 2022-2023 | +1,51 % | -11,9 % | -4,7 % | 0 | 4,6 / 2,8 | 92 / 8 % (1 / 98) | 1 / 4 / 47 % | 49 % (47 j) | 34, 76 %, 0,98 % | +4 077 (-586) | +524 / +1 573 |
| B, faiseur 70 %, niveau 12 % | 2024 -> 09/2026 | +1,16 % | -15,4 % | -6,6 % | 1 | 3,2 / 2,9 | 36 / 36 % (0 / 77) | 0 / 6 / 24 % | 28 % (7 j) | 23, 0 %, 0,60 % | +1 725 (-587) | +321 / +961 |
| B, preneur, niveau 15 % | 2020-2021 | +0,57 % | -11,0 % | -7,9 % | 1 | 2,6 / 2,1 | 7 / 93 % (0 / 100) | 0 / 0 / 7 % | 100 % (8 j) | 5, 0 %, 0,21 % | -421 (-599) | -95 / +341 |
| B, preneur, niveau 15 % | 2022-2023 | +0,90 % | -19,4 % | -5,2 % | 1 | 4,4 / 2,8 | 4 / 95 % (0 / 100) | 1 / 4 / 4 % | 50 % (2 j) | 3, 0 %, 0,26 % | -480 (-594) | -158 / +418 |
| B, preneur, niveau 15 % | 2024 -> 09/2026 | +0,30 % | -25,0 % | -8,2 % | 1 | 2,5 / 2,9 | 0 / 83 % (0 / 90) | 0 / 0 / 0 % | - | 0 | -599 (-596) | -176 / - |
| B, faiseur 70 %, niveau 15 % | 2020-2021 | +0,88 % | -10,0 % | -7,9 % | 1 | 2,6 / 2,1 | 27 / 73 % (1 / 96) | 0 / 6 / 27 % | 68 % (15 j) | 19, 0 %, 0,34 % | +415 (-597) | +91 / +547 |
| B, faiseur 70 %, niveau 15 % | 2022-2023 | +1,64 % | -16,8 % | -5,2 % | 1 | 4,4 / 2,8 | 26 / 74 % (1 / 99) | 4 / 10 / 23 % | 47 % (19 j) | 17, 0 %, 0,46 % | +538 (-574) | +154 / +743 |
| B, faiseur 70 %, niveau 15 % | 2024 -> 09/2026 | +1,09 % | -20,2 % | -8,2 % | 1 | 2,5 / 2,9 | 24 / 58 % (3 / 82) | 0 / 12 / 17 % | 54 % (33 j) | 16, 0 %, 0,05 % | -399 (-544) | -104 / +81 |

Autres mesures : plafond de 8 positions jamais atteint (les plafonds propres de C1 refusent 16 000 à 28 000 signaux par
période) ; valeur ouverte jamais au-dessus de 2 x le capital ; **aucune perte de trade au-dessus de 3 %** ; arrêts
internes 0 à 20 par période. **C1 reçoit le financement en moyenne** (+0,004 à -0,05 %/mois payé : il vend quand la
foule achète) ; la cassure le paie (+0,06 à +0,10 %/mois en 2020-2021, presque rien ensuite). En 2024-2026, C1 gagne
+0,41 %/mois (preneur, 9 %) à +1,06 %/mois (faiseur, 15 %), alors qu'aux frais FTMO il perdait -0,15 %/mois
(trois_briques) : **chez HyroTrader, sans frais de nuit, C1 redevient positif.**

Règle des 40 % : elle ne fait jamais échouer, elle **retarde** 30 à 50 % des étapes réussies, de 1 à 20 jours en
moyenne selon les comptes (jusqu'à 130 jours pour les comptes lents en preneur).

## 5. Ajout après lecture (information seulement, aucun choix) : deux autres lectures des règles
Rejoué sans jumeaux. « Plus haut à la clôture » = plus haut du jour compté à la clôture des bougies (moins sévère) ;
« retrait à 5 % » = retirer seulement quand le gain atteint 5 % (la FAQ le suggère ; garde plus de coussin).

| Compte | Lecture des règles | Espérance $ 2020-2021 | 2022-2023 | 2024 -> 09/2026 | Survie financé 2022-2023 / 2024-2026 |
|---|---|---|---|---|---|
| A, preneur, niveau 9 % | cahier | -599 | -133 | -599 | 23 / - % |
| A, preneur, niveau 9 % | plus haut du jour à la clôture des bougies | -599 | -133 | -553 | 23 / 0 % |
| A, preneur, niveau 9 % | retrait seulement quand le gain atteint 5 % | -599 | -32 | -599 | 92 / - % |
| A, preneur, niveau 9 % | les deux | -599 | -32 | -599 | 92 / - % |
| A, faiseur 70 %, niveau 9 % | cahier | -296 | +1 838 | -537 | 100 / 0 % |
| A, faiseur 70 %, niveau 9 % | plus haut du jour à la clôture des bougies | -296 | +1 838 | -62 | 100 / 100 % |
| A, faiseur 70 %, niveau 9 % | retrait seulement quand le gain atteint 5 % | -325 | +1 324 | -599 | 100 / 0 % |
| A, faiseur 70 %, niveau 9 % | les deux | -325 | +1 324 | -168 | 100 / 100 % |
| A, preneur, niveau 12 % | cahier | +1 741 | +642 | -121 | 0 / 0 % |
| A, preneur, niveau 12 % | plus haut du jour à la clôture des bougies | +1 733 | +642 | +850 | 0 / 11 % |
| A, preneur, niveau 12 % | retrait seulement quand le gain atteint 5 % | +1 457 | +267 | -312 | 0 / 0 % |
| A, preneur, niveau 12 % | les deux | +1 457 | +582 | +298 | 21 / 11 % |
| A, faiseur 70 %, niveau 12 % | cahier | +3 719 | +1 943 | +1 555 | 0 / 0 % |
| A, faiseur 70 %, niveau 12 % | plus haut du jour à la clôture des bougies | +3 703 | +2 017 | +4 203 | 3 / 15 % |
| A, faiseur 70 %, niveau 12 % | retrait seulement quand le gain atteint 5 % | +2 640 | +1 327 | +926 | 0 / 0 % |
| A, faiseur 70 %, niveau 12 % | les deux | +2 640 | +1 382 | +2 573 | 3 / 59 % |
| A, preneur, niveau 15 % | cahier | +3 913 | +1 644 | +846 | 0 / 0 % |
| A, preneur, niveau 15 % | plus haut du jour à la clôture des bougies | +3 450 | +1 008 | +3 934 | 0 / 27 % |
| A, preneur, niveau 15 % | retrait seulement quand le gain atteint 5 % | +3 088 | +825 | +566 | 0 / 0 % |
| A, preneur, niveau 15 % | les deux | +2 392 | +636 | +3 169 | 0 / 27 % |
| A, faiseur 70 %, niveau 15 % | cahier | +7 749 | +3 870 | +4 449 | 0 / 2 % |
| A, faiseur 70 %, niveau 15 % | plus haut du jour à la clôture des bougies | +7 174 | +3 752 | +11 644 | 9 / 34 % |
| A, faiseur 70 %, niveau 15 % | retrait seulement quand le gain atteint 5 % | +6 270 | +2 784 | +3 667 | 0 / 2 % |
| A, faiseur 70 %, niveau 15 % | les deux | +6 270 | +2 886 | +10 535 | 9 / 34 % |
| B, preneur, niveau 9 % | cahier | -599 | -432 | -599 | 100 / - % |
| B, preneur, niveau 9 % | plus haut du jour à la clôture des bougies | -599 | -433 | -599 | 100 / - % |
| B, preneur, niveau 9 % | retrait seulement quand le gain atteint 5 % | -599 | -536 | -599 | 100 / - % |
| B, preneur, niveau 9 % | les deux | -599 | -536 | -599 | 100 / - % |
| B, faiseur 70 %, niveau 9 % | cahier | -89 | +4 375 | -437 | 100 / 0 % |
| B, faiseur 70 %, niveau 9 % | plus haut du jour à la clôture des bougies | -146 | +3 229 | -534 | 100 / 0 % |
| B, faiseur 70 %, niveau 9 % | retrait seulement quand le gain atteint 5 % | -141 | +3 590 | -354 | 100 / 40 % |
| B, faiseur 70 %, niveau 9 % | les deux | -173 | +2 505 | -526 | 100 / 0 % |
| B, preneur, niveau 12 % | cahier | -579 | -599 | -599 | - / - % |
| B, preneur, niveau 12 % | plus haut du jour à la clôture des bougies | -579 | -203 | -599 | 100 / - % |
| B, preneur, niveau 12 % | retrait seulement quand le gain atteint 5 % | -599 | -599 | -599 | - / - % |
| B, preneur, niveau 12 % | les deux | -599 | -284 | -599 | 100 / - % |
| B, faiseur 70 %, niveau 12 % | cahier | -48 | +4 077 | +1 725 | 76 / 0 % |
| B, faiseur 70 %, niveau 12 % | plus haut du jour à la clôture des bougies | +670 | +6 017 | +4 084 | 95 / 39 % |
| B, faiseur 70 %, niveau 12 % | retrait seulement quand le gain atteint 5 % | +427 | +3 363 | +950 | 82 / 0 % |
| B, faiseur 70 %, niveau 12 % | les deux | +1 042 | +5 328 | +3 283 | 98 / 39 % |
| B, preneur, niveau 15 % | cahier | -421 | -480 | -599 | 0 / - % |
| B, preneur, niveau 15 % | plus haut du jour à la clôture des bougies | -36 | -473 | -507 | 0 / 0 % |
| B, preneur, niveau 15 % | retrait seulement quand le gain atteint 5 % | -599 | -536 | -599 | 0 / - % |
| B, preneur, niveau 15 % | les deux | +114 | -473 | -599 | 0 / 0 % |
| B, faiseur 70 %, niveau 15 % | cahier | +415 | +538 | -399 | 0 / 0 % |
| B, faiseur 70 %, niveau 15 % | plus haut du jour à la clôture des bougies | +2 337 | +4 598 | +1 973 | 65 / 0 % |
| B, faiseur 70 %, niveau 15 % | retrait seulement quand le gain atteint 5 % | +299 | +486 | -599 | 0 / 0 % |
| B, faiseur 70 %, niveau 15 % | les deux | +2 044 | +3 878 | +886 | 65 / 0 % |

Lecture : **les résultats dépendent beaucoup de la façon dont la société mesure le plus haut du jour** (ex. A faiseur
15 % sur 2024-2026 : +4 449 $ dans le cahier, +11 644 $ si le plus haut est lu à la clôture) ; retirer seulement à 5 %
sauve parfois le compte financé mais rapporte en général moins (retraits plus tardifs, souvent perdus à la mort).

## 6. Verdict honnête
1. **Il y a de l'information** : les jumeaux ne réussissent que 0 à 3 % des challenges (les vrais comptes jusqu'à 100 %, mais
   0 à 7 % pour (B) en preneur),
   et les espérances des jumeaux sont toujours près de -599 $.
2. **Chez HyroTrader, C1 devient rentable sur 2024-2026** (sans nuit FTMO, financement reçu), mais **seulement si
   l'essentiel des ordres passe en faiseur** : en preneur (0,055 %/côté), les espérances sont négatives ou faibles sauf
   à 15 % d'agitation pour (A) (+846 $ sur 2024-2026). L'hypothèse « 70 % faiseur au même prix » est optimiste et
   n'est pas mesurée.
3. **(A) C1 seul fait mieux que (B) C1 + cassure** sur 2024-2026 à niveau égal en faiseur à 15 % ; (B) est meilleur
   à 9-12 % en 2022-2023. La cassure aide peu chez HyroTrader : ses frais preneur (elle sort au marché) la rognent.
4. **Les règles de HyroTrader sont dures pour ce genre de compte** : la perte du jour suiveuse (depuis le plus haut,
   gains latents compris) + le mur fixe à 90 000 $ + le retrait plafonné à 5 % (le surplus est perdu) font mourir
   presque tous les comptes financés dans l'année. Le meilleur compte (A, faiseur, 15 %) donne une espérance de
   +3 900 à +4 400 $ par challenge et ~+880 à +900 $/mois en régime durable avec 200 000 $ (2 comptes), sur des années
   déjà vues.
5. Les départs de challenge ne sont pas indépendants (un seul jour comme le 10/10/2025 tue tous les comptes vivants) :
   le nombre réel de cas est petit.

## 7. Risques propres à la société (à peser avant de payer)
- **Comptes 100 % simulés** : HyroTrader paie de sa poche ; rien ne garantit que ses prix, frais et financement collent
  à Bybit, ni qu'elle paiera.
- **Plaintes de mars 2026** : perte maximale abaissée de 10 % à 6 % sans prévenir sur certains comptes, refus de paiement
  au nom d'un « modèle de risque », bannissements Discord (propscorer, cryptoslate). Note Trustpilot ~4,1-4,4/5.
- **Aucune autorité de contrôle** (entités aux Émirats / Îles Vierges, paiements via la Slovaquie) ; revues manuelles
  « comportement de joueur » pouvant retirer des gains ; partage 90 % « à discrétion » ; règle des 3 % contrôlée à la main.
- **Pages de la FAQ contradictoires** sur la perte du jour (suiveuse ou fixe) : à faire confirmer PAR ÉCRIT, avec le prix
  de l'option « Swing » (perte du jour fixe), qui supprimerait l'essentiel des morts.
- Liste exacte des perpétuels proposés (XMR, VET, ALGO, EOS arrêté…) non vérifiée une par une.

## 8. Ce qui manquerait pour aller plus loin
1. **Mesurer en direct à blanc la part d'ordres faiseurs réellement remplis** (et le prix obtenu) : c'est la condition
   n°1 de rentabilité.
2. **Demander par écrit à HyroTrader** : type de perte du jour appliqué, prix de l'option Swing, règle exacte du retrait
   (surplus perdu ?), acceptation d'une IA par API, liste des marchés. Puis rejouer le cahier avec la règle confirmée.
3. Le direct à blanc de C1 seul (A) sur les prix Bybit pendant quelques mois : seul juge neuf.

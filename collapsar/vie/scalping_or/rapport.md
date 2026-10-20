# Scalping de l'or : les 3 méthodes de la recherche, testées honnêtement

Test du 20/10/2026, plan figé avant tout résultat (`plan_fige.md`). Or à la minute 01/2015 -> 12/09/2025, frais FTMO (écart relevé 0,46 $/once x facteur de l'heure, commission métaux, glissement), seuil de preuve 3,79 (1 305 cases jugées). Version de A choisie sur 2015-2020 : **A2** (plus grande force contre le jumeau).

## En bref
- **Aucune des 3 méthodes ne gagne d'argent, sur aucune période, avec aucun des frais testés** (modèle par heure,
  écart fixe 0,40 $, écart en % du prix, glissement « doux »). Le contrôle 2023-09/2025 (ouvert une seule fois) confirme.
- **Le gain brut est 3 à 30 fois trop petit** : 0,1 à 0,7 $/once par trade (1,1 $ au mieux à l'échelle de 2025), alors
  que les frais coûtent 0,8 à 2 $/once. La règle de la recherche demandait 3 $/once brut.
- **A (cassure de la veille ou de l'Asie) ne porte aucune information** : force contre le jumeau ~0 sur toutes les
  périodes. Le « sens imposé par l'heure » (ventes seules) n'aide pas.
- **B (boîte asiatique) porte une petite information réelle** : +0,09 R par trade de mieux que son jumeau, force 3,65 sur
  2015-09/2025 (seuil 3,79 : PAS prouvé), présente sur les 3 périodes (2,7 / 1,3 / 2,1), à l'achat ET à la vente (2,6 / 2,5)
  et sur l'or retourné : ce n'est pas la hausse de l'or. Mais brut +0,07 R contre 0,20 R de frais -> mort.
- **C (fausse cassure) : un peu d'information** (+0,07 R contre le jumeau, force 2,3), brut 0,3 $/once -> mort.
- Les challenges FTMO « réussis » viennent du hasard de challenges très longs (sans limite de temps) : toutes les
  méthodes perdent chaque mois en moyenne. Baisse max = compte jamais arrêté (pour mesurer, pas pour trader).

| Méthode | Verdict | Pourquoi |
|---|---|---|
| A (version choisie A2) | ⚪ bruit | aucune information, -0,17 à -0,28 R net |
| B boîte asiatique | ⚪ bruit (information presque 🟡) | force 3,65 < 3,79, net -0,06 à -0,17 R |
| C fausse cassure | ⚪ bruit | force 2,3, net -0,06 à -0,18 R |

**Pour MAGNETAR** : aucun mentor ici. Seule information à garder en tête : la sortie de la boîte asiatique (01h-06h
Londres) a un petit sens (continuation), trop petit pour un trade de journée ; elle ne servirait que comme ENTRÉE
(« où est le prix par rapport à la boîte asiatique et au plus haut/bas d'hier ») pour une IA qui tient assez longtemps
pour viser plusieurs dollars par once. Ne pas en faire une règle.

Notes : le fichier de l'or a été prolongé jusqu'au 10/2026 (trou après le 12/09/2025) : rien après 09/2025 n'est lu.
Le calendrier MT5 se décale d'1 h une fois par an (changement d'heure), les prix non (vérifié sur l'emploi américain).
Essais comptés : 5 versions (A1, A2, A3, B, C) ; les variantes de frais et de glissement ne sont pas des essais (mêmes
règles). Programme `collapsar/regarder/pistes/scalping_or.py`, tests `collapsar/tests/test_scalping_or.py` (8 verts).

## Verdict par période (frais modèle ; 🟢 prouvé / 🟡 prometteur / ⚪ bruit)

| Méthode | 2015-2020 | 2021-2022 | 2023-09/2025 | tout |
|---|---|---|---|---|
| A1 cassure veille | ⚪ -0,35 R, force -0,1 | ⚪ -0,34 R, force -1,0 | ⚪ -0,14 R, force +0,8 | ⚪ -0,29 R, force -0,1 |
| A2 cassure Asie | ⚪ -0,28 R, force +0,6 | ⚪ -0,17 R, force +0,4 | ⚪ -0,19 R, force -0,2 | ⚪ -0,24 R, force +0,5 |
| A3 ventes seules | ⚪ -0,47 R, force -0,9 | ⚪ -0,41 R, force -0,8 | ⚪ -0,09 R, force +1,3 | ⚪ -0,37 R, force -0,4 |
| B boîte asiatique | ⚪ -0,17 R, force +2,7 | ⚪ -0,09 R, force +1,3 | ⚪ -0,06 R, force +2,1 | ⚪ -0,12 R, force +3,6 |
| C fausse cassure | ⚪ -0,18 R, force +1,5 | ⚪ -0,06 R, force +1,1 | ⚪ -0,10 R, force +1,2 | ⚪ -0,14 R, force +2,3 |

## 2015-2020 (choix)

| | A1 | A2 | A3 | B | C |
|---|---|---|---|---|---|
| trades (par mois) | 498 (6,9) | 1535 (21,3) | 262 (3,6) | 934 (13,0) | 617 (8,6) |
| gain net / trade (R) | -0,35 | -0,28 | -0,47 | -0,17 | -0,18 |
| idem écart fixe 0,40 $ | -0,32 | -0,25 | -0,44 | -0,16 | -0,14 |
| idem glissement doux | -0,14 | -0,11 | -0,23 | -0,05 | -0,09 |
| idem écart en % (info) | -0,27 | -0,21 | -0,39 | -0,12 | -0,08 |
| or retourné (R) | -0,33 | -0,28 | -0,20 | -0,17 | -0,19 |
| gain net $/once | -1,80 | -1,50 | -2,62 | -1,10 | -0,52 |
| gain brut $/once | +0,14 | +0,23 | -0,52 | +0,36 | +0,28 |
| brut à l'échelle 3 200 $ | +0,25 | +0,49 | -1,23 | +0,89 | +0,59 |
| frais $/once | 1,94 | 1,73 | 2,10 | 1,46 | 0,80 |
| frais / gain brut | 1359 % | 752 % | brut <= 0 | 405 % | 289 % |
| gagnants | 32 % | 33 % | 27 % | 38 % | 38 % |
| gain moyen gagnant (R) | +1,12 | +1,10 | +1,09 | +1,15 | +1,10 |
| perte moyenne perdant (R) | -1,03 | -0,97 | -1,04 | -0,96 | -0,97 |
| trades >= 3R / >= 5R | 10 / 2 | 26 / 5 | 4 / 0 | 0 / 0 | 3 / 0 |
| force contre le jumeau | -0,07 | +0,56 | -0,86 | +2,72 | +1,52 |
| achats : R (force) | -0,21 (+0,8) | -0,25 (+0,7) | - (-) | -0,12 (+2,6) | -0,19 (+0,9) |
| ventes : R (force) | -0,47 (-0,9) | -0,31 (+0,1) | -0,47 (-0,9) | -0,22 (+1,3) | -0,18 (+1,2) |
| années gagnantes | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 |
| FTMO 0,5 % : gain/mois | -1,20 % | -3,03 % | -0,85 % | -1,11 % | -0,79 % |
| FTMO 0,5 % : pire jour | -3,99 % | -3,19 % | -2,17 % | -2,15 % | -2,06 % |
| FTMO 0,5 % : baisse max | 87,1 % | 219,4 % | 61,9 % | 81,2 % | 63,1 % |
| FTMO 0,5 % : réussis / morts / en cours | 0 / 60 / 12 | 0 / 66 / 6 | 0 / 59 / 13 | 0 / 68 / 4 | 0 / 61 / 11 |
| FTMO 0,5 % : jours pour +10 % | - | - | - | - | - |
| FTMO 1 % : gain/mois | -2,40 % | -6,05 % | -1,70 % | -2,23 % | -1,58 % |
| FTMO 1 % : pire jour | -7,97 % | -6,37 % | -4,33 % | -4,29 % | -4,13 % |
| FTMO 1 % : baisse max | 174,3 % | 438,8 % | 123,8 % | 162,4 % | 126,3 % |
| FTMO 1 % : réussis / morts / en cours | 0 / 67 / 5 | 2 / 69 / 1 | 0 / 67 / 5 | 2 / 68 / 2 | 6 / 60 / 6 |
| FTMO 1 % : jours pour +10 % | - | 22.5 | - | 54.0 | 77.5 |

## 2021-2022 (vérif.)

| | A1 | A2 | A3 | B | C |
|---|---|---|---|---|---|
| trades (par mois) | 185 (7,7) | 551 (23,0) | 103 (4,3) | 413 (17,2) | 238 (9,9) |
| gain net / trade (R) | -0,34 | -0,17 | -0,41 | -0,09 | -0,06 |
| idem écart fixe 0,40 $ | -0,32 | -0,15 | -0,39 | -0,07 | -0,05 |
| idem glissement doux | -0,17 | -0,07 | -0,19 | +0,01 | -0,01 |
| idem écart en % (info) | -0,30 | -0,13 | -0,37 | -0,05 | -0,02 |
| or retourné (R) | -0,33 | -0,18 | -0,23 | -0,09 | -0,08 |
| gain net $/once | -2,97 | -1,49 | -3,84 | -0,66 | -0,45 |
| gain brut $/once | -0,82 | +0,40 | -1,52 | +0,75 | +0,37 |
| brut à l'échelle 3 200 $ | -1,42 | +0,64 | -2,67 | +1,30 | +0,67 |
| frais $/once | 2,15 | 1,89 | 2,32 | 1,41 | 0,81 |
| frais / gain brut | brut <= 0 | 476 % | brut <= 0 | 188 % | 221 % |
| gagnants | 31 % | 37 % | 26 % | 36 % | 44 % |
| gain moyen gagnant (R) | +1,05 | +1,06 | +1,16 | +1,44 | +1,06 |
| perte moyenne perdant (R) | -0,97 | -0,90 | -0,97 | -0,96 | -0,95 |
| trades >= 3R / >= 5R | 2 / 1 | 10 / 2 | 2 / 1 | 0 / 0 | 2 / 0 |
| force contre le jumeau | -0,99 | +0,40 | -0,80 | +1,32 | +1,15 |
| achats : R (force) | -0,25 (-0,6) | -0,22 (-0,6) | - (-) | -0,21 (-0,4) | -0,00 (+1,0) |
| ventes : R (force) | -0,41 (-0,8) | -0,12 (+1,1) | -0,41 (-0,8) | +0,05 (+2,2) | -0,13 (+0,6) |
| années gagnantes | 0/2 | 0/2 | 0/2 | 0/2 | 1/2 |
| FTMO 0,5 % : gain/mois | -1,31 % | -1,96 % | -0,88 % | -0,75 % | -0,32 % |
| FTMO 0,5 % : pire jour | -1,53 % | -1,49 % | -1,16 % | -1,31 % | -1,57 % |
| FTMO 0,5 % : baisse max | 32,3 % | 50,3 % | 21,2 % | 30,3 % | 12,1 % |
| FTMO 0,5 % : réussis / morts / en cours | 0 / 16 / 8 | 0 / 20 / 4 | 0 / 14 / 10 | 1 / 17 / 6 | 1 / 1 / 22 |
| FTMO 0,5 % : jours pour +10 % | - | - | - | 76.0 | 136.0 |
| FTMO 1 % : gain/mois | -2,61 % | -3,91 % | -1,77 % | -1,50 % | -0,64 % |
| FTMO 1 % : pire jour | -3,07 % | -2,99 % | -2,33 % | -2,62 % | -3,15 % |
| FTMO 1 % : baisse max | 64,7 % | 100,6 % | 42,4 % | 60,5 % | 24,2 % |
| FTMO 1 % : réussis / morts / en cours | 0 / 20 / 4 | 2 / 19 / 3 | 0 / 16 / 8 | 6 / 16 / 2 | 8 / 10 / 6 |
| FTMO 1 % : jours pour +10 % | - | 21.0 | - | 38.0 | 81.5 |

## 2023-09/2025 (contrôle)

| | A1 | A2 | A3 | B | C |
|---|---|---|---|---|---|
| trades (par mois) | 239 (7,2) | 681 (20,6) | 114 (3,5) | 493 (14,9) | 283 (8,6) |
| gain net / trade (R) | -0,14 | -0,19 | -0,09 | -0,06 | -0,10 |
| idem écart fixe 0,40 $ | -0,12 | -0,17 | -0,08 | -0,05 | -0,08 |
| idem glissement doux | +0,01 | -0,09 | +0,05 | +0,02 | -0,03 |
| idem écart en % (info) | -0,11 | -0,16 | -0,07 | -0,04 | -0,06 |
| or retourné (R) | -0,15 | -0,18 | -0,20 | -0,06 | -0,09 |
| gain net $/once | -1,36 | -1,46 | -0,93 | -0,36 | -0,72 |
| gain brut $/once | +0,71 | +0,43 | +1,13 | +1,31 | +0,24 |
| brut à l'échelle 3 200 $ | +0,99 | +0,19 | +1,62 | +1,44 | +0,36 |
| frais $/once | 2,07 | 1,89 | 2,06 | 1,67 | 0,96 |
| frais / gain brut | 291 % | 444 % | 182 % | 128 % | 403 % |
| gagnants | 36 % | 36 % | 39 % | 40 % | 41 % |
| gain moyen gagnant (R) | +1,05 | +1,02 | +0,96 | +1,22 | +1,06 |
| perte moyenne perdant (R) | -0,82 | -0,87 | -0,76 | -0,93 | -0,92 |
| trades >= 3R / >= 5R | 6 / 0 | 13 / 1 | 2 / 0 | 0 / 0 | 5 / 0 |
| force contre le jumeau | +0,83 | -0,24 | +1,30 | +2,06 | +1,25 |
| achats : R (force) | -0,18 (-0,0) | -0,18 (+0,1) | - (-) | -0,05 (+1,9) | -0,07 (+1,0) |
| ventes : R (force) | -0,09 (+1,3) | -0,20 (-0,4) | -0,09 (+1,3) | -0,08 (+1,0) | -0,13 (+0,8) |
| années gagnantes | 0/3 | 0/3 | 1/3 | 2/3 | 1/3 |
| FTMO 0,5 % : gain/mois | -0,51 % | -1,95 % | -0,16 % | -0,48 % | -0,43 % |
| FTMO 0,5 % : pire jour | -1,04 % | -1,38 % | -1,04 % | -1,25 % | -2,26 % |
| FTMO 0,5 % : baisse max | 18,4 % | 71,7 % | 7,5 % | 23,4 % | 20,7 % |
| FTMO 0,5 % : réussis / morts / en cours | 0 / 14 / 19 | 0 / 14 / 19 | 0 / 0 / 33 | 14 / 6 / 13 | 0 / 18 / 15 |
| FTMO 0,5 % : jours pour +10 % | - | - | - | 331.0 | - |
| FTMO 1 % : gain/mois | -1,02 % | -3,90 % | -0,32 % | -0,96 % | -0,85 % |
| FTMO 1 % : pire jour | -2,09 % | -2,77 % | -2,07 % | -2,50 % | -4,51 % |
| FTMO 1 % : baisse max | 36,7 % | 143,4 % | 15,0 % | 46,7 % | 41,4 % |
| FTMO 1 % : réussis / morts / en cours | 0 / 26 / 7 | 8 / 21 / 4 | 0 / 9 / 24 | 17 / 13 / 3 | 4 / 22 / 7 |
| FTMO 1 % : jours pour +10 % | - | 31.0 | - | 77.0 | 118.5 |

## 2015-09/2025 (tout)

| | A1 | A2 | A3 | B | C |
|---|---|---|---|---|---|
| trades (par mois) | 922 (7,1) | 2767 (21,4) | 479 (3,7) | 1840 (14,3) | 1138 (8,8) |
| gain net / trade (R) | -0,29 | -0,24 | -0,37 | -0,12 | -0,14 |
| idem écart fixe 0,40 $ | -0,27 | -0,21 | -0,34 | -0,11 | -0,11 |
| idem glissement doux | -0,11 | -0,10 | -0,16 | -0,02 | -0,06 |
| idem écart en % (info) | -0,24 | -0,18 | -0,31 | -0,08 | -0,06 |
| or retourné (R) | -0,29 | -0,23 | -0,20 | -0,12 | -0,14 |
| gain net $/once | -1,92 | -1,49 | -2,48 | -0,80 | -0,56 |
| gain brut $/once | +0,10 | +0,31 | -0,34 | +0,71 | +0,29 |
| brut à l'échelle 3 200 $ | +0,11 | +0,44 | -0,86 | +1,14 | +0,55 |
| frais $/once | 2,02 | 1,80 | 2,14 | 1,51 | 0,84 |
| frais / gain brut | 2087 % | 578 % | brut <= 0 | 212 % | 294 % |
| gagnants | 33 % | 35 % | 30 % | 38 % | 40 % |
| gain moyen gagnant (R) | +1,09 | +1,07 | +1,06 | +1,23 | +1,08 |
| perte moyenne perdant (R) | -0,97 | -0,93 | -0,97 | -0,95 | -0,95 |
| trades >= 3R / >= 5R | 18 / 3 | 49 / 8 | 8 / 1 | 0 / 0 | 10 / 0 |
| force contre le jumeau | -0,08 | +0,48 | -0,41 | +3,65 | +2,26 |
| achats : R (force) | -0,21 (+0,3) | -0,23 (+0,3) | - (-) | -0,12 (+2,6) | -0,12 (+1,6) |
| ventes : R (force) | -0,37 (-0,4) | -0,25 (+0,4) | -0,37 (-0,4) | -0,13 (+2,5) | -0,15 (+1,6) |
| années gagnantes | 0/11 | 0/11 | 1/11 | 2/11 | 2/11 |
| FTMO 0,5 % : gain/mois | -1,04 % | -2,55 % | -0,68 % | -0,88 % | -0,61 % |
| FTMO 0,5 % : pire jour | -3,99 % | -3,19 % | -2,17 % | -2,15 % | -2,26 % |
| FTMO 0,5 % : baisse max | 136,1 % | 337,3 % | 88,4 % | 121,1 % | 83,2 % |
| FTMO 0,5 % : réussis / morts / en cours | 0 / 110 / 19 | 0 / 110 / 19 | 0 / 88 / 41 | 15 / 101 / 13 | 1 / 113 / 15 |
| FTMO 0,5 % : jours pour +10 % | - | - | - | 318.0 | 136.0 |
| FTMO 1 % : gain/mois | -2,08 % | -5,10 % | -1,36 % | -1,76 % | -1,22 % |
| FTMO 1 % : pire jour | -7,97 % | -6,37 % | -4,33 % | -4,29 % | -4,51 % |
| FTMO 1 % : baisse max | 272,1 % | 674,5 % | 176,8 % | 242,3 % | 166,4 % |
| FTMO 1 % : réussis / morts / en cours | 0 / 122 / 7 | 12 / 113 / 4 | 0 / 105 / 24 | 25 / 101 / 3 | 22 / 100 / 7 |
| FTMO 1 % : jours pour +10 % | - | 28.5 | - | 57.0 | 98.0 |

## Année par année (gain net moyen par trade en R, frais modèle)

| Année | A1 | A2 | A3 | B | C |
|---|---|---|---|---|---|
| 2015 | -0,40 | -0,30 | -0,50 | -0,10 | -0,23 |
| 2016 | -0,24 | -0,25 | -0,27 | -0,18 | -0,18 |
| 2017 | -0,69 | -0,45 | -0,92 | -0,19 | -0,38 |
| 2018 | -0,41 | -0,30 | -0,44 | -0,19 | -0,12 |
| 2019 | -0,16 | -0,27 | -0,34 | -0,16 | -0,10 |
| 2020 | -0,19 | -0,14 | -0,34 | -0,19 | -0,09 |
| 2021 | -0,36 | -0,21 | -0,37 | -0,08 | +0,00 |
| 2022 | -0,32 | -0,13 | -0,45 | -0,09 | -0,13 |
| 2023 | -0,09 | -0,37 | +0,02 | -0,26 | -0,14 |
| 2024 | -0,14 | -0,11 | -0,19 | +0,01 | -0,16 |
| 2025 | -0,22 | -0,00 | -0,15 | +0,03 | +0,05 |

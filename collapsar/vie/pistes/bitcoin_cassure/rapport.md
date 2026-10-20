# Piste « bitcoin cassure » (C2 et A3 figés) — période cachée ouverte UNE fois, 16/10/2026

Code : `collapsar/regarder/pistes/bitcoin_cassure.py` (en-tête écrit avant l'ouverture ; règles importées telles quelles
de `bitcoin_journee.py`). Verrou + tous les chiffres : `cachee.json` ; contrôle sur les périodes déjà vues : `essai.json`.

## Rappel
- 2 candidats choisis APRÈS avoir vu 2017-2021 et 2022-2023 parmi 8 -> seuil de preuve racine(2 ln 8) = 2,04 (brief
  commun : 3). Seul juge neuf : 2024-01 -> 2026-10.
- C2 : cassure du plus haut / plus bas des 24 dernières heures (regard à chaque heure pleine), sortie au milieu du canal
  ou 23h45 serveur. A3 : sens de 00h-12h serveur tenu de 12h à 23h45.
- Surcouche décidée avant l'ouverture : arrêt de la journée à -3 % du compte (perte latente comprise), plus de trade
  jusqu'au lendemain.
- Contrôle avant ouverture : la première version du code comptait le sens deux fois dans la force ; corrigé, les
  chiffres 2017-2023 sont alors identiques à `bitcoin_journee`.

## Verdict
**A3 : échec.** Elle est faible en période cachée (+0,56 %/mois à la cible 1 % et 0,01 % de frais), négative à 0,1 %
de frais, et sa force est de 0,9, sous le seuil. Elle meurt dans 47 à 62 % des challenges.
**C2 : elle tient, mais ce n'est pas une preuve.** Elle reste positive pour les 3 niveaux de frais : +1,1 %/mois à la
cible 1 % et 0,01 %, +0,95 % à 0,03 %, +0,4 % à 0,1 %. Elle réussit 71 % des challenges contre 10 % pour ses jumeaux.
Sa force pesée par la taille vaut 2,10 : elle passe tout juste le seuil 2,04, pas celui de 3. Sa force non pesée vaut
1,3. Son gain vient surtout de quelques jours : les 10 meilleurs jours font 30 % sur les 36 % de la période. 2025 est
négatif (-0,3 %/mois). Le compte financé ne rapporte que +4 % en moyenne sur 12 mois. La baisse max de 14 % dépasse
déjà le mur de -10 % d'un challenge qui démarrerait au mauvais moment (17 % de morts).
L'arrêt à -3 % sert : il ne change presque pas le gain, mais fait passer la survie du compte financé de 85 % à 91 %
(C2, cible 1 %) et ramène le pire point du jour de -3,6 % à -3,0 %. Il en a moins besoin que A3 (pire point -5,8 %
sans arrêt).

## Période cachée 2024-01 -> 2026-10 — C2 (636 trades)
| frais | cible | arrêt -3 % | %/mois | baisse max | pire jour / pire point | force / pesée | challenges réussis / morts | jumeaux | financé 12 mois : survie (gain moyen) / jumeaux | espérance € (jumeaux) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0,01 % | 0,5 % | sans = avec | +0,55 | -7,1 % | -1,7 / -1,8 % | 1,27 / 2,07 | 7 / 0 % | 1 / 17 % | 100 % (+2,4 %) / 91 % | -502 (-537) |
| 0,01 % | 1 % | sans | +1,09 | -14,3 % | -3,4 / -3,6 % | 1,27 / 2,07 | 67 / 21 % | 5 / 67 % | 85 % (+3,5 %) / 36 % | -180 (-516) |
| 0,01 % | 1 % | **avec** | **+1,11** | -13,9 % | -3,0 / -3,0 % | 1,29 / 2,10 | **71 / 17 %** | 10 / 51 % | **91 % (+4,2 %)** / 58 % | **-157** (-488) |
| 0,01 % | 1,5 % | sans | +1,60 | -21,6 % | -5,1 / -5,4 % | 1,27 / 2,07 | 58 / 38 % | 8 / 81 % | 43 % (+2,0 %) / 10 % | -225 (-496) |
| 0,01 % | 1,5 % | avec | +1,62 | -20,5 % | -3,0 / -3,0 % | 1,29 / 2,12 | 62 / 33 % | 13 / 68 % | 76 % (+5,3 %) / 36 % | -202 (-469) |
| 0,03 % | 0,5 % | sans = avec | +0,47 | -7,6 % | -1,7 / -1,8 % | 1,27 / 2,07 | 3 / 0 % | 0 / 23 % | 100 % (+1,4 %) / 87 % | -525 (-540) |
| 0,03 % | 1 % | sans | +0,94 | -15,2 % | -3,4 / -3,6 % | 1,27 / 2,07 | 68 / 19 % | 3 / 71 % | 85 % (+1,9 %) / 32 % | -172 (-524) |
| 0,03 % | 1 % | avec | +0,95 | -14,8 % | -3,0 / -3,0 % | 1,29 / 2,10 | 68 / 19 % | 5 / 57 % | 85 % (+2,1 %) / 51 % | -172 (-511) |
| 0,03 % | 1,5 % | sans | +1,37 | -23,0 % | -5,1 / -5,4 % | 1,27 / 2,07 | 61 / 35 % | 7 / 82 % | 43 % (+0,7 %) / 9 % | -210 (-504) |
| 0,03 % | 1,5 % | avec | +1,40 | -21,8 % | -3,0 / -3,0 % | 1,29 / 2,12 | 62 / 33 % | 9 / 73 % | 63 % (+2,4 %) / 29 % | -202 (-493) |
| 0,1 % | 0,5 % | sans = avec | +0,20 | -10,7 % | -1,7 / -1,8 % | 1,27 / 2,07 | 0 / 0 % | 0 / 44 % | 100 % (-2,0 %) / 67 % | -540 (-540) |
| 0,1 % | 1 % | sans | +0,40 | -21,4 % | -3,5 / -3,6 % | 1,27 / 2,07 | 10 / 40 % | 0 / 76 % | 54 % (-3,7 %) / 21 % | -488 (-539) |
| 0,1 % | 1 % | avec | +0,42 | -21,0 % | -3,0 / -3,0 % | 1,30 / 2,10 | 10 / 40 % | 1 / 72 % | 54 % (-3,7 %) / 30 % | -488 (-537) |
| 0,1 % | 1,5 % | sans | +0,56 | -33,0 % | -5,2 / -5,4 % | 1,27 / 2,07 | 47 / 49 % | 2 / 88 % | 30 % (-4,4 %) / 5 % | -285 (-531) |
| 0,1 % | 1,5 % | avec | +0,61 | -31,5 % | -3,0 / -3,0 % | 1,31 / 2,14 | 47 / 49 % | 2 / 84 % | 35 % (-4,3 %) / 12 % | -285 (-530) |

C2, cible 1 %, frais 0,01 %, avec arrêt :
- achats = +25,1 % du compte, ventes = +11,4 % ;
- par année : 2024 +1,53 %/mois, 2025 -0,31 %/mois, 2026 (jusqu'au 08/10) +2,40 %/mois ;
- 23 mois positifs sur 34 ; 47 % de trades gagnants ; exposition moyenne 0,4 x le compte.

## Période cachée — A3 (717 trades), résumé
| frais | cible | arrêt | %/mois | baisse max | pire point | force / pesée | challenges réussis / morts | jumeaux | financé : survie / jumeaux | espérance € |
|---|---|---|---|---|---|---|---|---|---|---|
| 0,01 % | 0,5 % | sans = avec | +0,28 | -7,7 % | -2,9 % | 0,93 / 0,98 | 42 / 0 % | 2 / 20 % | 100 % / 87 % | -315 |
| 0,01 % | 1 % | sans | +0,56 | -15,5 % | -5,8 % | 0,93 / 0,98 | 33 / 62 % | 13 / 71 % | 67 % / 38 % | -360 |
| 0,01 % | 1 % | avec | +0,59 | -16,3 % | -3,0 % | 0,93 / 1,04 | 33 / 47 % | 16 / 53 % | 74 % / 53 % | -360 |
| 0,03 % | 1 % | avec | +0,42 | -17,3 % | -3,0 % | 0,93 / 1,05 | 44 / 38 % | 11 / 58 % | 74 % / 48 % | -300 |
| 0,1 % | 1 % | avec | -0,17 | -27,3 % | -3,0 % | 0,94 / 1,05 | 22 / 65 % | 3 / 73 % | 41 % / 25 % | -420 |
| 0,01 % | 1,5 % | avec | +0,83 | -23,5 % | -3,0 % | 0,85 / 0,98 | 28 / 65 % | 21 / 66 % | 41 % / 34 % | -390 |

A3, cible 1 %, frais 0,01 %, avec arrêt :
- achats +9,5 %, ventes +10,1 % ;
- par année : 2024 -0,14 %/mois, 2025 -0,67 %/mois, 2026 +3,20 %/mois (un seul semestre, le premier de 2026, fait
  presque tout le gain) ;
- sans ses 10 meilleurs jours, A3 est perdante (-6,9 %).
Les lignes A3 non montrées ici (cibles 0,5 % et 1,5 % aux frais 0,03 % et 0,1 %, et les cas sans arrêt) sont dans
`cachee.json`.

## Défauts cherchés
- Les candidats ont été choisis après avoir vu 2017-2023 : seule la période cachée compte, et elle ne contient
  qu'environ 640 trades.
- Le gain de C2 est concentré : 10 jours sur environ 700 font 30 des 36 % du gain. Normal pour du suivi de tendance,
  mais un mauvais tirage de quelques jours change tout.
- 2025 est négatif pour C2 et pour A3 : il y a des années sans avantage.
- L'arrêt à -3 % est simulé au niveau exact (ou à l'ouverture de la bougie si le prix a sauté au-delà) : en réel,
  le glissement sur un bitcoin qui chute peut coûter un peu plus.
- Frais : l'écart de 1 $ relevé chez FTMO reste à confirmer. À 0,1 % par aller-retour, C2 ne gagne presque plus rien.
- Pas de samedi ni de dimanche, faute de données complètes : chez FTMO, le bitcoin cote 7 j/7.

## Ce qui manquerait
1. Mesurer l'écart réel BTCUSD chez FTMO aux heures pleines, pendant une semaine.
2. Démo « à blanc » de C2 avec l'arrêt -3 % et la cible 1 % : c'est le seul juge neuf restant.
3. C2 seule donne un compte financé qui rapporte peu (+4 %/an). Il faudrait la combiner à d'autres pistes non liées
   pour viser plus.

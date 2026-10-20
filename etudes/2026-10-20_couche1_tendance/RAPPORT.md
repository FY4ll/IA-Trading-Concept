# Couche 1 — Tendance de fond : résultat du test verrouillé (20/10/2026)

Plan : `PLAN_FIGE.md` (commit `c8f6aa6`) ; lancé une fois (`resultats/VERROU_TEST.json`) ; chiffres : `resultats/test.json`.

## ⚠️ Défaut du plan (le mien), trouvé en lisant les résultats
Le plan disait « taille fixée à l'ouverture, gardée jusqu'à la sortie ». Une position qui n'est pas stoppée peut alors
durer des années avec une taille d'une autre époque :
- acheteur permanent sur l'or : UN trade ouvert en 2017 (or ~1 250 $), jamais stoppé ; en 2026 l'or vaut 3 à 4 fois
  plus, donc le risque réel est ×3-4 -> « pire baisse 123 % » (la chute de début 2026 sur une position énorme) ;
- acheteur permanent sur le S&P 500 : stoppé en mars 2020, rentré le 24/03/2020 avec une taille MINUSCULE (volatilité
  du krach) gardée 6 ans -> -0,02 %/mois alors que l'indice a été multiplié par 2,5.
La condition 4 du chef de projet (taille ajustée à la volatilité) n'est donc pas tenue dans la durée : les baisses, les
pires jours et les challenges FTMO des positions longues sont faussés, et les comparaisons aussi (dans une moindre
mesure à risque égal). Aucun calcul n'est faux : c'est la règle figée qui ne mesure pas ce qui était demandé.

## Résultats tels quels (2018-2026), en %/mois de 100 000 $ (avantage ± incertitude par trimestres)

| marché | N | gain | gain / vol | pire baisse | pire jour | contre pile ou face | contre l'acheteur | à risque égal | challenge réussi / mur / inactivité |
|---|---|---|---|---|---|---|---|---|---|
| or | acheteur | +1,33 | 0,45 | 123 %* | | | | | 19 / 21 / 60 % |
| or | 1 | -0,14 | -0,15 | 41 % | -6,3 % | +0,12 ± 0,29 | -1,47 ± 0,81 | -0,58 ± 0,35 | 3 / 8 / 88 % |
| or | 3 | +0,38 | 0,36 | 30 % | -13,4 % | **+0,61 ± 0,24** | -0,95 ± 0,82 | -0,11 ± 0,35 | 3 / 5 / 90 % |
| or | 6 | +0,54 | 0,33 | 73 %* | -29 %* | +0,66 ± 0,37 | -0,79 ± 0,54 | -0,21 ± 0,31 | 7 / 10 / 82 % |
| or | 12 | +0,77 | 0,29 | 107 %* | -43 %* | +0,66 ± 0,52 | -0,56 ± 0,36 | -0,43 ± 0,34 | 13 / 20 / 67 % |

(*) faussé par le défaut ci-dessus.

Robustesse (même règles, avantage à risque égal sur l'acheteur permanent) :

| N | argent | S&P 500 | Nasdaq 100 | euro-dollar | dollar-yen | positifs | moyenne des 5 | robuste |
|---|---|---|---|---|---|---|---|---|
| 1 | -0,48 | -0,22 | -0,56 | +0,43 | -0,74 | 1 / 5 | -0,31 ± 0,21 | non |
| 3 | -0,76 | -0,24 | -0,71 | +0,39 | -0,25 | 1 / 5 | -0,31 ± 0,22 | non |
| 6 | -0,12 | -0,11 | -0,54 | +0,37 | -0,67 | 1 / 5 | -0,22 ± 0,22 | non |
| 12 | -0,17 | -0,18 | -0,64 | +0,27 | -0,60 | 1 / 5 | -0,26 ± 0,22 | non |

## Ce qui tient malgré le défaut
- Sur l'or, la tendance bat pile ou face (N = 3 : +0,61 ± 0,24) parce qu'elle est surtout acheteuse (66-75 % du
  temps) sur un or en hausse ; elle ne bat **jamais l'acheteur permanent**, ni en gain ni à risque égal, pour aucun N.
- Ailleurs, rien n'est robuste : positif sur 1 marché sur 5 seulement (l'euro-dollar, où l'acheteur perd).
- **FTMO : la règle des 30 jours sans ouvrir de trade tue 60 à 95 % des challenges** pour TOUS les N (une tendance
  ouvre 4 à 25 trades par an). Indépendant du défaut de taille.

## Correction proposée (non lancée : décision du chef de projet)
Taille recalculée chaque jour pour rester à 10 %/an de volatilité (achats / ventes partiels au passage, frais
compris), même stop, mêmes N, mêmes marchés, même période : un 2e regard déclaré sur 2018-2026.

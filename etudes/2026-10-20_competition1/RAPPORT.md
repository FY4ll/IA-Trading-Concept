# Compétition 1 — résultat (20/10/2026)

Plan : `PLAN_FIGE.md` (commit `d2c359d`, avant tout calcul). Lancée une fois (`resultats/VERROU.json`). COFFRE
2024 -> jamais chargé. Détail : `resultats/competition1.json`. %/mois de 100 000 $, frais FTMO compris ; avantage ±
incertitude (écart type des avantages mensuels / racine du nombre de mois).

| hypothèse | marché | 2012-2019 | 2020-2023 | 2012-2023 | contre le juge clé (2012-2023) | contre l'acheteur à risque égal | critères passés |
|---|---|---|---|---|---|---|---|
| N1 élan de la journée | S&P 500 | -0,46 | -0,33 | **-0,42** | pile ou face : -0,11 ± 0,07 | -0,54 | 1 / 6 |
| | Nasdaq 100 | -0,44 | -0,26 | -0,38 | -0,02 ± 0,07 | -0,53 | |
| | Dow Jones | -0,34 | -0,31 | -0,33 | -0,18 ± 0,07 | -0,37 | |
| N2 trou d'ouverture | S&P 500 | -0,67 | +0,07 | **-0,41** | pile ou face : -0,19 ± 0,17 | -0,72 | 1 / 6 |
| | Nasdaq 100 | -0,45 | -0,05 | -0,31 | -0,05 ± 0,16 | -0,66 | |
| | Dow Jones | -0,33 | +0,14 | -0,14 | -0,02 ± 0,18 | -0,25 | |
| N3 retournement des devises | 7 paires | -0,04 | -0,20 | **-0,09** | tirage des devises : **+0,30 ± 0,20** | (pile ou face : +0,29) | 2 / 6 |

## Ce que ça dit
- **N1 (Gao)** : la dernière demi-heure ne suit PAS le reste de la journée sur 2012-2023, sur aucun des 3 indices
  (légèrement pire que le hasard). Rejetée.
- **N2** : refermer le trou d'ouverture perd en 2012-2019 et ne gagne qu'un peu en 2020-2023 ; rien de stable. Rejetée.
- **N3** : un petit retournement d'une semaine à l'autre existe peut-être avant frais (+0,30 ± 0,20 %/mois sur le
  hasard, 1,5 fois l'incertitude, non prouvé), mais il est mangé par les frais (-0,09 %/mois) et porté surtout par le
  franc suisse et l'euro (3 devises sur 7 négatives). Rejetée.
- Les frais FTMO des indices (écart constant en points, donc plus cher en part du prix dans les années où l'indice
  valait moins) coûtent ~0,3 %/mois à une stratégie qui trade chaque jour à 10 %/an de volatilité.

Registre : I106 (N1), I107 (N2), I108 (N3), toutes « negatif ». 3 hypothèses, 7 marchés.

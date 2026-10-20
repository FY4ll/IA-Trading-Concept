# Compétition 2 — résultat (20/10/2026)

Plan : `PLAN_FIGE.md` (commit `f927aa6`, avant tout calcul ; essai à blanc 2012-2013 sur les comptes seulement). Lancée
une fois (`resultats/VERROU.json`). COFFRE 2024 -> jamais chargé. Détail : `resultats/competition2.json`. %/mois de
100 000 $, frais FTMO compris ; incertitude par trimestres.

| hypothèse | 2012(13)-2019 | 2020-2023 | total | contre le juge clé (total) | 2e juge | critères passés |
|---|---|---|---|---|---|---|
| M1 momentum relatif (11 marchés) | -0,46 | -0,36 | **-0,43** | tirage : +0,11 ± 0,34 | pile ou face : + | 2 / 6 |
| M2 modèle linéaire commun | +0,06 | -0,58 | **-0,17** | pile ou face : +0,25 ± 0,21 (2013-19 : +0,48 ± 0,23 ; 2020-23 : -0,16) | acheteur à risque égal : -0,08 | 2 / 6 |
| M3 volatilité gérée, S&P 500 | +0,53 | +0,30 | **+0,45** | montant constant à risque égal : -0,29 ± 0,30 | taille vol : -0,16 | 2 / 6 |
| M3 Nasdaq 100 | +0,53 | +0,44 | +0,50 | -0,04 ± 0,20 | -0,05 | |
| M3 or | -0,26 | +0,34 | -0,06 | -0,13 ± 0,18 | -0,03 | |

## Ce que ça dit
- **M1** : classer les marchés par leur élan relatif ne fait pas mieux que les tirer au hasard ; les devises perdent,
  les « autres » (or, indices) gagnent un peu (+0,40 sur le tirage) sans preuve. Rejetée.
- **M2** : le modèle commun voyait un petit signal sur 2013-2019 (+0,48 ± 0,23 sur pile ou face : 2 fois l'incertitude,
  à la limite) qui **disparaît sur 2020-2023** (-0,16) : exactement le cas d'un signal du passé qui ne tient pas.
  Rejetée.
- **M3** : gagne +0,45 %/mois sur le S&P 500 parce que c'est un acheteur d'indice ; gérer la taille par la variance fait
  MOINS bien qu'un montant constant au même risque (-0,29). Et il n'ouvre presque jamais (il réduit plus souvent qu'il
  n'agrandit) : incompatible avec la règle FTMO des 30 jours. Rejetée.

Registre : I109 (M1), I110 (M2), I111 (M3), « negatif ».

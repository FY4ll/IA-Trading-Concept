# Couche 1 — Perception par détecteurs codés à la main : résultat (20/10/2026)

Règles : `PLAN_FIGE.md` (figé et commité avant le test). Test verrouillé **2018-01-01 -> 2026-10-13**, lancé
deux fois en tout : le 1er lancement avait un biais de MESURE (avenant 1, `resultats/test_v1_biaise.json`), corrigé
puis relancé une seule fois (`resultats/VERROU_TEST_2.json`, commit `6e3604d`). Chiffres ci-dessous : 2e lancement.

## Combien de signaux

| unité | zones de son indicateur | confirmées par le volume | 1er contact qui réagit | bloquées par un FVG | sans zone opposée | avis | trades 2018-2026 |
|---|---|---|---|---|---|---|---|
| D1 | 313 | 121 | 28 | 10 | 6 | 12 | 5 |
| H4 | 1 541 | 610 | 94 | 36 | 32 | 26 | 8 |
| H1 | 5 433 | 2 163 | 383 | 113 | 62 | 208 | 61 |
| M15 | 22 201 | 9 462 | 1 755 | 553 | 141 | 1 061 | 381 |

(comptes sur toute l'histoire 2004-2026 sauf la dernière colonne)

## Test verrouillé 2018-2026

(a) = le sens seul (sortie fixe 20 bougies, en ATR) ; (b) = le signal + sa gestion (80 % à 2 R, reste vers la zone
opposée, en R). Gains après frais. Avantage ± incertitude ; il faut > 2 × l'incertitude pour battre un juge.

| unité | mesure | trades | achats | gain moyen | pile ou face | toujours acheteur | avantage sur pile ou face | avantage sur l'acheteur | verdict |
|---|---|---|---|---|---|---|---|---|---|
| D1 | a | 5 | 40 % | -2,35 ATR | -0,03 | +1,24 | -2,32 ± 0,87 | -3,58 ± 2,08 | trop peu de trades |
| D1 | b | 5 | 40 % | -0,54 R | +0,15 | -0,21 | -0,68 ± 0,60 | -0,32 ± 1,10 | trop peu de trades |
| H4 | a | 8 | 25 % | +1,28 ATR | -0,06 | +0,80 | +1,34 ± 1,68 | +0,48 ± 2,85 | trop peu de trades |
| H4 | b | 8 | 25 % | -0,14 R | -0,17 | -0,20 | +0,03 ± 0,47 | +0,06 ± 0,94 | trop peu de trades |
| H1 | a | 61 | 34 % | +0,71 ATR | -0,13 | +0,10 | +0,84 ± 0,58 | +0,61 ± 0,97 | ne bat aucun juge |
| H1 | b | 61 | 34 % | +0,05 R | -0,16 | -0,17 | +0,21 ± 0,19 | +0,22 ± 0,35 | ne bat aucun juge |
| M15 | a | 381 | 48 % | -0,08 ATR | -0,28 | -0,19 | +0,20 ± 0,25 | +0,11 ± 0,38 | ne bat aucun juge |
| M15 | b | 381 | 48 % | **-0,48 R** | -0,60 | -0,64 | +0,13 ± 0,10 | +0,16 ± 0,11 | ne bat aucun juge ; perd après frais |

Contrôle 2010-2017 (calculé après le test, rien n'a été réglé dessus) : aucun détecteur ne bat un juge non plus
(M15 b : -0,005 ± 0,085 sur pile ou face ; H1 b : -0,06 ± 0,33).

Frais : en M15 le stop est minuscule (~0,06 % du prix, ~1-2 $) : un aller-retour FTMO coûte ~0,6 R par trade ; en
H1 ~0,25 R ; en D1 ~0,05 R.

Le 1er lancement biaisé donnait en M15 (b) +0,39 ± 0,06 sur pile ou face (6 fois l'incertitude) : c'était le biais
de la bougie d'entrée. Corrigé : +0,13 ± 0,10.

## Verdict

**Rien ne bat les deux juges, ni même un seul.** Ni l'entrée (mesure a), ni l'entrée + la gestion (mesure b), sur
aucune unité, ni sur 2018-2026 ni sur 2010-2017. Le seul indice (M15 gestion, +0,13 R sur le hasard) n'est pas prouvé et
reste perdant après frais (-0,48 R par trade). En D1 et H4, la méthode complète (volume + 2e contact + FVG + zone
opposée) ne donne que 5 et 8 trades en 8,8 ans : impossible de juger.

Limite : c'est CETTE traduction en règles qui est mesurée ; l'œil du trader (choix du profil de volume visible, de ce
qu'est un « contact ») peut différer.

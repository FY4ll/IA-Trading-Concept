# Verdict final des zones du chef de projet, juge entièrement corrigé (16/10/2026, soir)

Code : `collapsar/regarder/pistes/verdict_zones_corrige.py` (cahier en tête, écrit avant les résultats).
Chiffres : `resultats.json` (71 lignes), `compte.json` (compte FTMO), `frais.json` (frais vérifiés), journaux `journal_*.txt`.
Tests : `collapsar/tests/test_verdict_zones.py` (6 tests, calculs à la main).

**Toutes ces années ont déjà été vues** (laboratoire SMC, chef_crypto, chef_compte_ftmo, zones_retouchees). Ce qui suit
est un constat avec le juge corrigé, pas une preuve. Aucune règle n'a été choisie sur 2024-2026 (le choix des lignes du
compte se fait sur les années avant 2024).

## 1. Frais réellement appliqués (vérifiés avant le calcul)

Plus aucun « x 1,25 » dans les moteurs des zones (`frais_ftmo.MARGE_PRUDENCE` = 1, `chef_compte_ftmo.GLISSEMENT` = 1).
Règle de chaque trade : entrée par ordre limite = demi-frais (x 1,16 pour le S&P et 1,07 pour le Nasdaq pendant la
1re heure de New York, mesuré) ; objectif = demi-frais ; stop = frais entiers (+0,5 fiche de glissement, mesuré) ; aucune
entrée au marché.

| Marché | aller-retour au prix d'aujourd'hui | au prix de juin 2019 | trade au stop | nuit achat / vente (%/an, 2026) | nuit triple |
|---|---|---|---|---|---|
| or | 0,0125 % | 0,037 % | 0,019 % | 5,3 / 0,4 | mercredi |
| S&P 500 | 0,0078 % | 0,022 % | 0,012 % | 5,7 / 2,1 | vendredi |
| euro-dollar | 0,006 % | 0,006 % | 0,009 % | 2,7 / -0,1 | mercredi |
| bitcoin (cryptos Binance) | **0,066 %** (commission 0,065 % + écart 0,001 %) | idem | 0,099 % | 30 / 30 | vendredi |
| ether | **0,090 %** | idem | 0,135 % | 30 / 30 | vendredi |
| ADA, SOL et autres cryptos | **0,096 %** | idem | 0,144 % | 30 / 30 | vendredi |

(L'écart est supposé constant en points : les années où le prix était bas coûtent plus cher en %.)

**Corrigé ce soir dans le moteur des zones** (`zones_retouchees.py`, signatures gardées, test ajouté) : les nuits des
marchés hors cryptos étaient comptées « au calendrier » (week-end = 3 nuits pour tous). Elles suivent maintenant FTMO :
triple le mercredi pour les devises et les métaux, le vendredi pour les indices et l'énergie, rien le samedi et le
dimanche (`nuits_ftmo`).

**Non corrigé, à signaler** : `chef_crypto.FRAIS` (bitcoin 0,03 %, ether 0,05 %) n'a toujours PAS la commission crypto.
Il n'est pas utilisé ici, mais `direct/chef_zones.py` s'en sert : je n'y ai pas touché (consigne « ne touche pas au
direct »). `chef_compte_ftmo.frais` compte 0,095 % pour l'ether au lieu de 0,090 % (un peu prudent, non utilisé ici).

## 2. Ligne par ligne

« R » = gain d'un trade en multiples du risque, après frais et nuits. « Force » = écart avec le jumeau qui prend le sens
inverse aux mêmes moments (3 = preuve). Stop = derrière la zone **avec le minimum de 0,2 jour d'agitation** (sa
pratique). « Avant » = chiffre déjà publié (frais x 1,25, nuits au calendrier). Moins de 30 trades : pas de conclusion.

### Or, Nasdaq, S&P 500, euro (minutes, graphique M3, 2015 -> 10/2026)

| ligne | trades | /semaine | gagnants | R moyen | médiane | force | avant 2022 / 2022-23 / 2024-26 | 2022 · 2023 · 2024 · 2025 · 2026 | avant |
|---|---|---|---|---|---|---|---|---|---|
| fidèle, zone D1 seule | 66 | 0,11 | 42 % | **+0,09** | -1,01 | +1,4 | -0,14 / +0,34 / +0,16 (28/19/19 tr) | trop peu | +0,08 |
| fidèle, zone H4 seule | 698 | 1,1 | 29 % | **-0,18** | -1,05 | -1,5 | -0,29 / +0,02 / -0,12 | -0,32 · +0,34 · -0,36 · +0,03 · -0,03 | -0,20 |
| fidèle, zone H1 seule | 3 372 | 5,5 | 31 % | **-0,17** | -1,07 | -0,9 | -0,24 / -0,12 / -0,05 | -0,16 · -0,07 · -0,12 · -0,08 · +0,08 | -0,20 |
| fidèle, zone M30 seule | 7 327 | 11,9 | 33 % | **-0,09** | -1,07 | +1,5 | -0,10 / -0,07 / -0,06 | -0,06 · -0,09 · -0,12 · -0,03 · -0,04 | -0,12 |
| fidèle, zone M15 seule | 16 232 | 26 | 32 % | **-0,16** | -1,07 | -1,8 | -0,18 / -0,12 / -0,13 | -0,18 · -0,06 · -0,09 · -0,24 · -0,07 | -0,19 |
| fidèle, zone M5 seule | 45 402 | 74 | 32 % | **-0,14** | -1,07 | -1,8 | -0,17 / -0,10 / -0,11 | -0,11 · -0,09 · -0,15 · -0,11 · -0,05 | non publié |
| fidèle, zone M3 seule | 99 307 | 162 | 32 % | **-0,14** | -1,07 | -1,6 | -0,17 / -0,09 / -0,10 | -0,05 · -0,13 · -0,12 · -0,09 · -0,10 | non publié |
| **pratique : gigogne D1** | 43 | 0,07 | 30 % | **-0,02** | -1,06 | +0,9 | trop peu (17/11/15) | trop peu | -0,05 |
| **pratique : gigogne H4** | 288 | 0,47 | 31 % | **-0,14** | -1,06 | +0,2 | -0,19 / +0,22 / -0,42 | +0,03 · +0,34 · -0,53 · -0,37 · -0,38 | -0,17 |
| **pratique : gigogne H1** | 1 013 | 1,7 | 30 % | **-0,12** | -1,07 | +0,3 | -0,29 / +0,16 / -0,02 | +0,07 · +0,26 · -0,04 · +0,03 · -0,03 | non publié |
| fidèle, gigogne M30 | 1 610 | 2,6 | 32 % | -0,10 | -1,07 | -0,2 | -0,10 / -0,17 / -0,03 | -0,10 · -0,23 · +0,05 · -0,04 · -0,10 | non publié |
| fidèle, gigogne M15 | 2 028 | 3,3 | 32 % | -0,14 | -1,07 | +0,2 | -0,17 / -0,17 / -0,06 | -0,27 · -0,07 · -0,17 · -0,27 · +0,36 | non publié |
| fidèle, gigogne M5 | 7 183 | 11,7 | 32 % | -0,14 | -1,07 | -0,1 | -0,15 / -0,04 / -0,19 | -0,02 · -0,05 · -0,25 · -0,25 · -0,05 | non publié |
| ancienne, gigogne D1 | 35 | 0,06 | 26 % | +0,02 | -1,06 | -0,2 | trop peu (11/8/16) | trop peu | +0,00 |
| ancienne, gigogne H4 | 234 | 0,38 | 29 % | **-0,01** | -1,07 | -0,2 | -0,15 / +0,57 / -0,30 | +1,05 · +0,19 · -0,59 · +0,08 · -0,36 | -0,03 |
| ancienne, gigogne H1 | 1 022 | 1,7 | 31 % | -0,14 | -1,07 | -0,5 | -0,30 / +0,05 / +0,00 | -0,05 · +0,17 · -0,05 · +0,03 · +0,05 | non publié |

### 19 cryptos FTMO (Binance, 08/2017 -> 10/2026)

| ligne | trades | /semaine | gagnants | R moyen | médiane | force | avant 2022 / 2022-23 / 2024-26 | 2022 · 2023 · 2024 · 2025 · 2026 | avant |
|---|---|---|---|---|---|---|---|---|---|
| fidèle, zone D1 seule | 444 | 0,9 | 34 % | **-0,03** | -1,04 | +1,3 | -0,01 / +0,17 / -0,22 | +0,14 · +0,19 · -0,33 · -0,30 · -0,02 | -0,04 |
| fidèle, zone H4 seule | 3 832 | 8,0 | 33 % | **-0,03** | -1,07 | +3,0 | -0,00 / +0,04 / -0,11 | +0,11 · -0,04 · +0,02 · -0,13 · -0,26 | -0,06 |
| fidèle, zone H1 seule | 16 231 | 34 | 32 % | **-0,12** | -1,08 | -1,4 | -0,07 / -0,13 / -0,14 | -0,15 · -0,12 · -0,08 · -0,12 · -0,24 | -0,14 |
| fidèle, zone M30 seule | 34 978 | 73 | 33 % | **-0,10** | -1,08 | +1,9 | -0,08 / -0,12 / -0,09 | -0,17 · -0,08 · -0,08 · -0,07 · -0,14 | -0,12 |
| fidèle, zone M15 seule | 77 456 | 162 | 33 % | **-0,12** | -1,09 | -1,5 | -0,11 / -0,15 / -0,10 | -0,13 · -0,17 · -0,08 · -0,07 · -0,17 | -0,14 |
| **pratique : gigogne D1** | 185 | 0,39 | 40 % | **+0,02** | -1,08 | +1,1 | -0,09 / -0,06 / +0,11 | -0,27 · +0,14 · -0,49 · -0,07 · +1,06 | -0,01 |
| **pratique : gigogne H4** | 822 | 1,7 | 33 % | **-0,08** | -1,08 | +0,9 | +0,01 / -0,10 / -0,14 | +0,12 · -0,31 · +0,11 · -0,09 · -0,55 | -0,11 |
| **pratique : gigogne H1** | 1 497 | 3,1 | 35 % | **+0,01** | -1,09 | +1,0 | +0,23 / +0,01 / -0,15 | -0,12 · +0,14 · -0,06 · -0,14 · -0,26 | non publié |
| fidèle, gigogne M30 | 1 828 | 3,8 | 34 % | -0,04 | -1,08 | +1,9 | -0,04 / -0,18 / +0,05 | -0,20 · -0,16 · -0,03 · -0,03 · +0,28 | non publié |
| **ancienne, gigogne D1** | 136 | 0,29 | 40 % | **+0,47** | -1,08 | +1,8 | +0,41 / +0,27 / +0,62 (31/40/65 tr) | +0,03 · +0,64 · +0,59 · -0,18 · +1,30 | +0,44 |
| **ancienne, gigogne H4** | 802 | 1,7 | 37 % | **+0,22** | -1,08 | +2,5 | +0,14 / +0,34 / +0,19 | +0,23 · +0,47 · +0,41 · +0,31 · -0,19 | +0,19 |
| ancienne, gigogne H1 | 2 581 | 5,4 | 32 % | -0,16 | -1,09 | -1,1 | -0,10 / -0,11 / -0,23 | -0,17 · -0,05 · -0,18 · -0,16 · -0,36 | -0,04 (*) |

(*) chiffre publié sur 12 cryptos seulement, frais sans commission : pas comparable.

### 47 marchés (15 min, 2015 -> 10/2026)

| ligne | trades | /semaine | gagnants | R moyen | médiane | force | avant 2022 / 2022-23 / 2024-26 | 2022 · 2023 · 2024 · 2025 · 2026 | avant |
|---|---|---|---|---|---|---|---|---|---|
| fidèle, zone D1 seule | 947 | 1,5 | 33 % | **-0,19** | -1,04 | -0,3 | -0,19 / -0,14 / -0,23 | -0,09 · -0,22 · -0,43 · -0,24 · -0,03 | -0,22 |
| fidèle, zone H4 seule | 7 216 | 11,7 | 31 % | **-0,25** | -1,07 | +0,9 | -0,20 / -0,24 / -0,32 | -0,27 · -0,21 · -0,34 · -0,33 · -0,28 | -0,29 |
| fidèle, zone H1 seule | 35 917 | 58 | 32 % | **-0,27** | -1,09 | +0,6 | -0,30 / -0,23 / -0,26 | -0,21 · -0,24 · -0,30 · -0,27 · -0,22 | -0,32 |
| fidèle, zone M30 seule | 82 720 | 135 | 31 % | **-0,27** | -1,09 | -0,1 | -0,25 / -0,22 / -0,33 | -0,17 · -0,28 · -0,34 · -0,31 · -0,34 | -0,32 |
| fidèle, zone M15 seule | 179 911 | 293 | 31 % | **-0,26** | -1,09 | -0,7 | -0,26 / -0,23 / -0,30 | -0,21 · -0,25 · -0,29 · -0,31 · -0,30 | -0,32 |
| **pratique : gigogne D1** | 376 | 0,61 | 34 % | **-0,22** | -1,09 | +1,9 | -0,19 / -0,25 / -0,24 | -0,05 · -0,50 · -0,88 · +0,28 · -0,33 | -0,28 |
| **pratique : gigogne H4** | 1 553 | 2,5 | 34 % | **-0,24** | -1,08 | +1,1 | -0,22 / -0,08 / -0,38 | -0,01 · -0,14 · -0,42 · -0,40 · -0,31 | -0,31 |
| **pratique : gigogne H1** | 4 334 | 7,1 | 32 % | **-0,30** | -1,09 | -0,6 | -0,31 / -0,23 / -0,33 | -0,15 · -0,30 · -0,24 · -0,35 · -0,42 | non publié |
| fidèle, gigogne M30 | 5 689 | 9,3 | 31 % | -0,28 | -1,09 | -0,6 | -0,22 / -0,40 / -0,32 | -0,38 · -0,42 · -0,30 · -0,25 · -0,41 | non publié |
| ancienne, gigogne D1 | 287 | 0,47 | 33 % | -0,33 | -1,09 | +1,7 | -0,45 / -0,10 / -0,36 | -0,20 · +0,04 · -0,95 · +0,20 · -0,47 | -0,39 |
| ancienne, gigogne H4 | 1 533 | 2,5 | 33 % | -0,25 | -1,09 | +0,9 | -0,19 / -0,06 / -0,48 | -0,18 · +0,05 · -0,45 · -0,50 · -0,48 | -0,31 |
| ancienne, gigogne H1 | 6 963 | 11,3 | 33 % | -0,25 | -1,09 | +0,1 | -0,26 / -0,16 / -0,30 | -0,04 · -0,28 · -0,29 · -0,29 · -0,32 | non publié |

**Sans le minimum de stop** (stop collé derrière la zone, traduction stricte), c'est bien pire partout : de -0,03 R (cryptos,
zone H4 seule) à -1,6 R par trade (zones M3 / M5 à la minute). Raison : le stop est si court que la seule demi-fiche
d'entrée coûte 0,1 à 0,6 R. Le minimum de 0,2 jour d'agitation est indispensable (détail dans `resultats.json`).

Ce que les corrections ont changé : chaque ligne gagne +0,00 à +0,07 R (frais sans le x 1,25, nuits FTMO). **Aucune ligne
ne passe de perdante à gagnante** (la seule qui change de signe, cryptos gigogne D1, passe de -0,01 à +0,02 R : zéro).
Les nombres de trades sont identiques au trade près aux chiffres publiés.

À noter : la zone H4 seule sur les cryptos a une force de 3,0 (3,6 sans le minimum de stop) : le sens choisi est un peu
meilleur que le sens inverse, mais cet écart (~0,03 R) est plus petit que les frais : R final -0,03.

## 3. Compte FTMO 100 000 $ (lignes choisies par la règle écrite avant : meilleur R avant 2024)

Lignes retenues : cryptos ancienne gigogne H4 (aussi sa version en démo), minutes ancienne gigogne H4, cryptos pratique
gigogne H1. 4 positions au plus, levier FTMO Swing (cryptos 1:1), fonds au plus mauvais prix de chaque bougie de 15 min.
Challenges : départ tous les 10 jours ; « réussis / morts » comptés parmi les challenges TERMINÉS.

| ligne | risque | %/mois (avant 2022 / 22-23 / 24-26) | %/mois tout | baisse max | challenges terminés : réussis / morts | inachevés | jumeaux réussis / morts | temps médian pour réussir | avant |
|---|---|---|---|---|---|---|---|---|---|
| cryptos, ancienne H4 | 0,25 % | +0,13 / +0,52 / +0,45 | **+0,31 %** | -11,7 % | **99 % / 1 %** (264) | 68 sur 332 | 29 % / 71 % | 23 mois | +0,15 %/mois, -12,4 %, 36/0/64 % (règles un peu différentes) |
| | 0,5 % | -0,06 / +0,07 / +0,08 | **+0,00 %** | -22,8 % | 45 % / 55 % (314) | 18 | 19 % / 81 % | 9 mois | -0,03 %/mois, -25,7 %, 50/45/5 % |
| or / indices / euro, ancienne H4 | 0,25 % | -0,05 / +0,36 / -0,17 | **-0,01 %** | -9,9 % | aucun terminé | 416 sur 416 | 36 % / 64 % | — | — |
| | 0,5 % | -0,10 / +0,69 / -0,34 | -0,02 % | -18,8 % | 39 % / 61 % (330) ; 2024-26 : 0 / 100 % | 86 | 34 % / 66 % | 26 mois | — |
| cryptos, pratique gigogne H1 | 0,25 % | +0,55 / +0,20 / **-0,81** | +0,04 % | -28,3 % | 44 % / 56 % (308) ; départs 2022-26 : 0 / 100 % | 23 | 16 % / 84 % | 21 mois | — |
| | 0,5 % | +0,92 / +0,04 / -1,54 | -0,06 % | -48,1 % | 28 % / 72 % (311) | 20 | 20 % / 80 % | 9 mois | — |

Pourquoi 0,5 % ne fait pas mieux que 0,25 % sur les cryptos : le levier crypto de FTMO est de 1:1 ; avec un stop moyen de
1,3 % du prix, une position à 0,5 % de risque occupe ~40 % du compte, et les bons trades, qui arrivent en série pendant
les fortes tendances, sont coupés faute de marge. Vérifié : sans limite de levier (4 positions au plus), la même ligne
ferait +81 % en 9 ans à 0,5 % (contre +0,5 % avec la limite) ; à 0,25 %, la limite ne coûte presque rien (+40 %).

## 4. Verdict en 3 phrases

1. Le juge corrigé ne change pas le fond : les frais et les nuits justes remontent chaque ligne de 0 à 0,07 R, aucune ne
   passe de perdante à gagnante, et sur 71 lignes une seule tient sur les trois périodes avec assez de trades :
   **l'ancienne traduction au départ H4 sur les cryptos (+0,22 R par trade, force 2,5, sous le seuil de preuve de 3)** ;
   le départ journalier (+0,47 R) va dans le même sens mais sur trop peu de trades.
2. **Son indicateur traduit fidèlement ne gagne nulle part après frais** : zones seules ou gigognes, toutes unités du
   journalier aux 3 minutes, sa pratique (gigogne D1 / H4 / H1 avec le minimum de stop) comprise, de +0,09 R (zone
   journalière seule sur or / indices / euro : 66 trades, négative avant 2022) à -0,30 R par trade ; sur l'or, les
   indices, l'euro et les 47 marchés, aucune ligne n'est positive sur les trois périodes.
3. En compte FTMO, la seule ligne qui tient fait +0,3 %/mois à 0,25 % de risque (challenges réussis dans 99 % des cas
   terminés, mais en 23 mois en médiane) et rien à 0,5 % à cause du levier crypto 1:1 : **pas de quoi vivre**, et ces
   années ont toutes déjà été vues.

## Limites
- Une sortie à l'intérieur d'une bougie de l'unité d'entrée (D1, H4…) est datée, pour le compte, à la 1re bougie de 15 min
  qui touche son prix ; le R du trade lui-même est celui du moteur des zones (contrôlé trade par trade contre chef_crypto.trade_tiers_heures : écart < 1e-11 R).
- Frais de nuit payés à la sortie de chaque tiers dans le compte (et non chaque soir) ; le pire point additionne les pires
  prix de toutes les positions comme s'ils arrivaient au même moment (prudent).
- Prix Binance pour les 19 cryptos (pas ceux de FTMO) ; écarts FTMO relevés à 03h34 serveur (heures creuses, plutôt
  larges).

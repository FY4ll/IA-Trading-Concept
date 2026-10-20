# Piste « zones_retouchees » : la stratégie du chef de projet sur des zones DÉJÀ TOUCHÉES (16/10/2026)

Code : `collapsar/regarder/pistes/zones_retouchees.py` (ancienne traduction de l'indicateur, cahier + avenants 1 à 5
dans l'en-tête) et `collapsar/regarder/pistes/zones_retouchees_v7.py` (traduction fidèle zones supply and demand, avenant 4).
Chiffres : `resultats_*.json` (`v7_` = traduction fidèle, `v7F2_` = détection calée sur la fréquence),
`frequence*.json`, `choix_frequence*.json`, `controle_v7.json`. Les calculs faits avant la correction des heures sont
gardés dans `avant_correction_heures/` (ne pas les utiliser).

Tous les chiffres sont après frais FTMO réels (écart relevé x 1,25 ; cryptos : commission 0,0325 %/côté + écart) et
frais de nuit. « R » = gain d'un trade en multiples du risque. « Force » = écart avec un jumeau qui prend le sens
inverse aux mêmes moments (au-dessus de 3,14 = preuve pour cette piste ; 3,64 pour tout le laboratoire).

---

## 0. À lire d'abord : trois corrections qui changent la lecture

**a) La traduction fidèle de son indicateur (zones supply and demand).** L'ancienne traduction effaçait une zone à la 1re clôture de
15 min au-delà du milieu ; dans son code Pine, c'est la clôture du graphique regardé (journalier, H4…). Ma version rapide
donne exactement les mêmes zones que `zones supply and demand.zones_graphique` (8 essais sur 2 marchés : identiques).
Conséquence découverte en comptant : **plus de la moitié des zones H4 naissent et meurent dans la même bougie** (la
bougie qui confirme la zone clôture déjà au-delà de son milieu) : sur son écran, elles n'apparaissent jamais. Dans
l'ancienne traduction, ces zones étaient « touchées » tout de suite : 80 % des « 1ers contacts » arrivaient dans la
1re bougie de 15 min, alors que le prix n'était jamais reparti (78 à 83 % des zones naissaient avec le prix déjà
dedans). Avec la traduction fidèle, le 1er contact arrive en médiane 5 à 12 h après la naissance au journalier.

**b) La correction des heures (audit du 16/10).** Seuls les 4 marchés à la minute étaient touchés : avant correction,
leurs trades étaient faux (sorties datées de 1970, R moyen absurde de +500). Cryptos et 47 marchés : identiques avant
et après (802 trades H4 cryptos à +0,193 R, 1 533 trades H4 sur les 47 marchés à -0,313 R, au trade près).

| V1 (ancienne traduction), toutes années | avant correction | après correction |
|---|---|---|
| 4 marchés à la minute, départ H4 | 564 trades, résultats faux | 234 trades, **-0,03 R** (frais du labo sans nuit : +0,06 R) |
| 4 marchés à la minute, départ D1 | 9 trades, faux | 35 trades, +0,00 R |
| 19 cryptos, H4 / D1 | +0,19 R / +0,44 R | identique |
| 47 marchés, H4 / D1 | -0,31 R / -0,39 R | identique |

**c) Le système (départ journalier ou H4, puis peaufinage).** Comme demandé, la condition « déjà touchée / a réagi à
l'entrée / au milieu » porte sur la GROSSE zone de départ (D1 ou H4) ; l'entrée se fait dans la plus petite zone
trouvée en descendant (D1 -> H4 -> H1 -> M30 -> M15, et M5 / M3 à la minute). **Au départ journalier, il y a souvent
trop peu de trades pour conclure** (nombres exacts dans les tableaux ; aucune conclusion sous 30 trades).

---

## 1. Diagnostic de fréquence (4 indices US500, US100, US30, GER40 ; 2024-2026 ; aucun gain regardé)

Il dit avoir « facilement 4-5 trades par semaine ». Le code en trouve beaucoup moins :

| trades V1 par semaine, 4 indices réunis | départ D1 | départ H4 | départ H1 | départ M30 |
|---|---|---|---|---|
| ancienne traduction | 0,05 | 0,30 | 1,12 | 2,14 |
| traduction fidèle | 0,08 | 0,22 | 0,66 | 0,94 |

Où se perdent les trades (traduction fidèle, départ H4, par semaine sur les 4 indices) :

| étape | nombre / semaine |
|---|---|
| zones H4 créées | 6,28 |
| … dont effacées dès leur bougie de naissance (jamais affichées) | ~3,6 |
| 1ers contacts du bord | 2,64 |
| **pas de zone plus petite dedans** (perte principale) | 1,92 |
| chaîne gigogne complète | 0,72 |
| milieu jamais atteint (effacement 0,12 ; fenêtre de 200 bougies 0,03) | 0,15 |
| remplies | 0,57 |
| **pas d'objectif 3 (zone opposée) à au moins 2 R** | 0,34 |
| trades | **0,22** |

L'exigence de cassure (BOS) n'est pas le frein : 70 % des figures « bougie opposée + FVG » la passent. Les 3 vrais
freins : zones mort-nées, « zone dans la zone », objectif 3 à 2 R minimum.

**Détection calée sur la fréquence** (liste fermée de 6 écrite avant, choix sur le SEUL nombre de trades, cible 4,5) :
traduction fidèle -> **F2 = départ H1, une zone suffit (pas besoin de zone plus petite dedans)** : 4,62 trades par
semaine ; ancienne traduction -> F4 (départ H1, effacement au bord opposé) : 3,57. Leurs résultats sont au § 2.

---

## 2. Le tableau principal : V1 / R2 / R3 / R2M / R2E / R2E-milieu (traduction fidèle)

R2 = 2e contact après une 1re réaction ; R3 = 3e contact ; R2M = 1er demi-tour au milieu ; R2E = 1er demi-tour à
l'entrée, ordre au bord de la petite zone ; R2E-milieu = même condition, ordre au milieu.
Colonnes : trades | gagnants | gain moyen d'un gagnant / perte moyenne | **moyenne de tous les trades** | trades >= 10 R |
force | R moyen par période (avant 2022 / 2022-2023 / 2024-2026).

### 19 cryptos FTMO (graphique d'entrée M15)

| règle | trades | gagnants | gagnant / perdant | **R moyen** | >= 10 R | force | par période |
|---|---|---|---|---|---|---|---|
| H4 V1 | 822 | 33 % | +2,02 / -1,18 | **-0,11** | 6 | +0,9 | -0,01 / -0,13 / -0,16 |
| H4 R2 | 359 | 33 % | +2,69 / -1,26 | **+0,05** | 6 | +1,0 | +0,93 / -0,15 / -0,31 |
| H4 R3 | 166 | 28 % | +2,80 / -1,31 | **-0,17** | 3 | -0,8 | +1,09 / -0,59 / -0,65 |
| H4 R2M | 124 | 32 % | +2,38 / -1,24 | **-0,07** | 2 | +0,6 | +0,79 / +0,04 / -0,58 |
| H4 R2E | 148 | 30 % | +3,04 / -1,22 | **+0,07** | 3 | +1,2 | +1,55 / -0,58 / -0,15 |
| H4 R2E-milieu | 136 | 33 % | +3,00 / -1,24 | **+0,16** | 3 | +1,3 | +1,44 / -0,37 / -0,02 |
| D1 V1 | 185 | 40 % | +1,82 / -1,23 | **-0,01** | 2 | +1,1 | -0,12 / -0,08 / +0,08 |
| D1 R2 | 68 | 34 % | +3,27 / -1,53 | +0,09 | 3 | +0,6 | 9 / 28 / 31 trades : pas de conclusion par période |
| D1 R3 / R2M / R2E / R2E-milieu | 35 / 18 / 27 / 26 | | | +0,36 / -1,12 / -0,14 / -0,21 | | | trop peu (sauf R3 : 35) |

### Or, Nasdaq, S&P 500, euro (minutes ; graphique d'entrée M3 — M5 donne la même image)

| règle | trades | gagnants | gagnant / perdant | **R moyen** | >= 10 R | force | par période |
|---|---|---|---|---|---|---|---|
| H4 V1 | 288 | 31 % | +1,99 / -1,12 | **-0,17** | 3 | +0,3 | -0,22 / +0,19 / -0,44 |
| H4 R2 | 127 | 26 % | +1,97 / -1,15 | **-0,34** | 0 | +0,0 | -0,39 / +0,06 / -0,64 |
| H4 R3 | 59 | 29 % | +0,91 / -1,20 | **-0,59** | 0 | -0,8 | -0,56 / -0,28 / -0,96 |
| H4 R2M | 46 | 24 % | +2,32 / -1,17 | **-0,34** | 0 | +0,1 | 21 / 13 / 12 trades |
| H4 R2E | 44 | 27 % | +1,31 / -1,19 | **-0,51** | 0 | -0,3 | 24 / 7 / 13 trades |
| H4 R2E-milieu | 41 | 22 % | +2,40 / -1,19 | **-0,40** | 0 | -0,2 | 22 / 7 / 12 trades |
| D1 V1 | 43 | 30 % | +2,46 / -1,14 | -0,05 | 1 | +0,9 | 17 / 11 / 15 trades : pas de conclusion par période |
| D1 R2 / R3 / R2M / R2E / R2E-milieu | **20 / 10 / 11 / 5 / 4** | | | +0,79 / -0,59 / -0,64 / +2,03 / +1,25 | | | **trop peu de trades : aucune conclusion** |

(Graphique d'entrée M5 : H4 V1 301 trades -0,19 R ; R2 130 -0,16 ; R3 61 -0,49 ; R2M 48 -0,16 ; R2E 44 -0,23 ;
R2E-milieu 42 -0,09 ; D1 V1 47 trades +0,06.)

### 47 marchés (graphique d'entrée M15)

| règle | trades | gagnants | gagnant / perdant | **R moyen** | >= 10 R | force | par période |
|---|---|---|---|---|---|---|---|
| H4 V1 | 1 553 | 34 % | +1,80 / -1,41 | **-0,31** | 13 | +1,1 | -0,29 / -0,13 / -0,44 |
| H4 R2 | 718 | 34 % | +1,92 / -1,44 | **-0,29** | 6 | +1,0 | -0,39 / -0,18 / -0,20 |
| H4 R3 | 325 | 32 % | +2,01 / -1,48 | **-0,35** | 3 | +0,3 | -0,42 / -0,52 / -0,09 |
| H4 R2M | 215 | 33 % | +1,83 / -1,32 | **-0,28** | 2 | +0,5 | -0,24 / -0,38 / -0,27 |
| H4 R2E | 298 | 36 % | +1,82 / -1,43 | **-0,26** | 1 | +1,0 | -0,47 / -0,14 / +0,01 |
| H4 R2E-milieu | 284 | 36 % | +2,02 / -1,48 | **-0,22** | 1 | +0,9 | -0,43 / -0,07 / +0,04 |
| D1 V1 | 376 | 34 % | +1,83 / -1,34 | **-0,28** | 3 | +1,8 | -0,24 / -0,31 / -0,32 |
| D1 R2 | 176 | 36 % | +1,69 / -1,63 | **-0,42** | 1 | +0,2 | -0,38 / -0,64 / -0,31 |
| D1 R3 / R2M / R2E / R2E-milieu | 101 / 65 / 62 / 62 | | | -0,38 / -0,44 / -0,46 / -0,52 | | | |

### Le même tableau avec l'ancienne traduction (pour comparer ; heures corrigées)

| R moyen, toutes années (trades) | V1 | R2 | R3 | R2M | R2E | R2E-milieu |
|---|---|---|---|---|---|---|
| cryptos, départ H4 | **+0,19** (802) | +0,06 (222) | +0,03 (89) | +0,03 (96) | +0,10 (136) | +0,20 (112) |
| cryptos, départ D1 | **+0,44** (136) | +0,30 (30) | (13) | (9) | (21) | (18) |
| 4 marchés minute, H4 | -0,03 (234) | -0,36 (54) | (18) | (24) | -0,25 (32) | (28) |
| 4 marchés minute, D1 | +0,00 (35) | (11) | (1) | (7) | (5) | (4) |
| 47 marchés, H4 | -0,31 (1 533) | -0,37 (460) | -0,44 (154) | -0,24 (179) | -0,37 (248) | -0,33 (216) |
| 47 marchés, D1 | -0,39 (287) | -0,94 (68) | (25) | -1,32 (30) | -0,47 (40) | -0,90 (35) |

(entre parenthèses sans R : moins de 30 trades, pas de conclusion)

### Détection calée sur la fréquence (F2, traduction fidèle : départ H1, ~4,6 trades/semaine sur les 4 indices)

| R moyen (trades) | V1 | R2 | R3 | R2M | R2E | R2E-milieu |
|---|---|---|---|---|---|---|
| 19 cryptos | -0,14 (15 991) | -0,15 (5 917) | -0,11 (3 161) | -0,18 (1 920) | -0,16 (2 343) | -0,15 (2 262) |
| 4 marchés minute (M3) | -0,20 (3 241) | -0,22 (1 212) | -0,27 (629) | -0,35 (352) | -0,15 (488) | -0,18 (469) |
| 47 marchés | -0,33 (35 432) | -0,33 (13 360) | -0,31 (7 064) | -0,31 (4 329) | -0,28 (4 938) | -0,31 (4 750) |

Avec autant de trades, le résultat est net : **plus de trades = plus de frais, et toujours perdant**, quelle que soit la
règle de contact. (Ancienne traduction, F4 : mêmes conclusions ; seule exception R2E à la minute +0,05 R sur 410 trades,
négative en 2024-2026.)

---

## 3. Mêmes zones : 1er contact contre 2e contact

Sur les zones de départ qui ont À LA FOIS un trade au 1er contact et un trade au 2e (lecture seulement : au 1er contact,
on ne sait pas encore que la zone sera retouchée) :

| traduction fidèle, départ H4 | zones | R moyen au 1er contact | R moyen au 2e contact |
|---|---|---|---|
| 19 cryptos | 211 | +0,63 | +0,03 |
| 4 marchés minute | 72 | +0,03 | -0,62 |
| 47 marchés | 409 | +0,23 | -0,28 |

Partout (et aussi avec l'ancienne traduction, et au départ journalier), **le 1er passage a mieux payé que le 2e sur les
mêmes zones**.

## 4. Condition sur la PETITE zone d'entrée (comparaison demandée)

Filtre des trades V1 selon le nombre de contacts déjà subis par la petite zone d'entrée. Traduction fidèle, départ H4 :
aucune version ne tient (cryptos : p-V1 « petite zone jamais touchée » +0,17 R sur 248 trades, mais -0,01 en 2024-2026 ;
p-R2 -0,22 ; p-R2M -0,39 ; p-R2E -0,27 ; 47 marchés : toutes entre -0,15 et -0,42 R ; minute : entre -0,18 et +0,01 R).
À signaler honnêtement : avec l'ANCIENNE traduction, cryptos départ H4, « petite zone jamais touchée » faisait +0,56 R
sur 353 trades, positif sur les 3 périodes, force 3,50 (au-dessus du seuil de la piste 3,14, sous celui du laboratoire
3,64) ; ça va à l'inverse de « zones déjà touchées », et ça disparaît avec la traduction fidèle (force 1,8) : piste
fragile, pas une preuve.

## 5. « R2 par unité » (chaque unité seule, entrée au milieu de la zone elle-même ; traduction fidèle)

| R moyen (trades) | contact 1 | contact 2 (zone qui a déjà résisté) | contact 2 avec une zone plus grande autour |
|---|---|---|---|
| **cryptos** D1 | -0,04 (444) | -0,06 (172) | — |
| H4 | -0,06 (3 832) | -0,04 (1 409) | -0,06 (48) |
| H1 | -0,14 (16 231) | -0,14 (5 944) | -0,03 (330) |
| M30 | -0,12 (34 978) | -0,10 (12 848) | -0,23 (1 156) |
| M15 | -0,14 (77 456) | -0,10 (29 204) | -0,10 (3 760) |
| **minute (M3)** D1 | +0,08 (66) | +0,09 (40) | — |
| H4 | -0,20 (698) | -0,20 (244) | (4) |
| H1 | -0,20 (3 372) | -0,22 (1 202) | -0,50 (57) |
| M30 | -0,12 (7 327) | -0,13 (2 727) | -0,20 (301) |
| M15 | -0,19 (16 232) | -0,15 (6 068) | -0,19 (723) |
| **47 marchés** D1 | -0,22 (947) | -0,22 (432) | — |
| H4 | -0,29 (7 216) | -0,32 (2 811) | -0,50 (95) |
| H1 | -0,32 (35 917) | -0,31 (13 354) | -0,44 (706) |
| M30 | -0,32 (82 720) | -0,28 (31 485) | -0,29 (3 493) |
| M15 | -0,32 (179 911) | -0,27 (68 426) | -0,29 (9 195) |

Le 2e contact est un peu moins mauvais que le 1er sur les petites unités (M30, M15) : le sens est légèrement meilleur
que le hasard (force jusqu'à +6,3 sur les 47 marchés M15), mais l'écart est de l'ordre de 0,05 R, bien plus petit que
les frais (~0,2-0,3 R par trade sur ces petites zones). La zone H1 de son exemple : -0,14 / -0,22 / -0,31 R au 2e contact.

---

## 6. Mesure directe des probabilités (sans les gains) — ses zones contre de fausses zones « témoin hasard »

Réaction = le prix s'éloigne d'une hauteur de zone au-delà du bord d'entrée avant de clôturer au-delà du bord opposé.
Ces probabilités sont identiques dans les deux traductions (même ensemble de zones, l'effacement n'intervient pas).
Format : ses zones / témoin (écart en z ; >= 3 = réel).

| | P(réaction au 1er contact) | P(revient une 2e fois \| a réagi) | **P(réaction au 2e \| a réagi au 1er)** | P(réaction 2e \| 1er au milieu) | P(réaction 2e \| 1er à l'entrée) | P(2e aussi au milieu \| 1er au milieu) | P(2e aussi à l'entrée \| 1er à l'entrée) |
|---|---|---|---|---|---|---|---|
| cryptos D1 | 29 / 30 % | 92 / 87 % | **60 / 51 %** (z 2,9) | 58 / 50 % | 60 / 52 % | 18 / 22 % | 49 / 33 % (z 2,1) |
| cryptos H4 | 28 / 30 % | 92 / 87 % | **58 /54 %** (z 3,0) | 59 / 55 % | 61 / 53 % (z 3,2) | 25 / 23 % | 43 / 42 % |
| cryptos H1 | 30 / 31 % | 92 / 88 % | **59 / 56 %** (z 5,7) | 59 / 56 % | 59 / 56 % | 23 / 23 % | 47 / 43 % |
| cryptos M15 | 35 / 35 % | 92 / 88 % | **59 / 55 %** (z 14,6) | 60 / 55 % | 60 / 56 % | 22 / 21 % | 40 / 39 % |
| minute D1 | 29 / 26 % | 92 / 90 % | 53 / 50 % (z 0,6) | 53 / 53 % | 52 / 44 % | 36 / 28 % | 48 / 30 % |
| minute H4 | 25 / 25 % | 93 / 90 % | 52 / 52 % (z 0,2) | 57 / 52 % | 49 / 50 % | 25 / 27 % | 42 / 48 % |
| minute H1 | 28 / 29 % | 91 / 89 % | 53 / 53 % (z -0,3) | 53 / 49 % | 54 / 54 % | 23 / 22 % | 46 / 47 % |
| minute M15 | 30 / 31 % | 91 / 89 % | 56 / 55 % (z 1,6) | 55 / 54 % | 57 / 55 % | 23 / 21 % | 46 / 44 % |
| 47 marchés D1 | 29 / 28 % | 94 / 92 % | 53 / 54 % (z -0,9) | 53 / 54 % | 54 / 52 % | 28 / 27 % | 46 / 45 % |
| 47 marchés H4 | 28 / 29 % | 93 / 91 % | 55 / 54 % (z 0,7) | 55 / 54 % | 57 / 54 % | 25 / 21 % (z 2,5) | 43 / 47 % |
| 47 marchés H1 | 31 / 32 % | 91 / 90 % | 57 / 57 % (z 2,1) | 57 / 56 % | 58 / 57 % | 22 / 23 % | 44 / 44 % |
| 47 marchés M15 | 35 / 36 % | 90 / 88 % | 58 / 57 % (z 7,0) | 59 / 57 % | 59 / 58 % | 21 / 21 % | 40 / 39 % |

(M30 : comme M15. Nombres de zones : de ~800 au journalier sur 4 marchés à ~460 000 en M15 sur 47 marchés.)

Profondeur du 1er demi-tour (ses zones ; témoin quasi identique) : à l'entrée 20-30 %, au milieu 19-30 %, profond
(> 0,65) 40-61 %. R moyen du trade au 2e contact selon cette profondeur (traduction fidèle, départ H4) : cryptos
entrée +0,16 / milieu -0,07 / profond +0,04 ; minute -0,40 / -0,34 / -0,28 ; 47 marchés -0,22 / -0,28 / -0,40.

Ce que ça dit, simplement :
- **« Si elle a résisté une 1re fois, elle résistera une 2e fois » : vrai, un peu.** Une zone qui a tenu tient de
  nouveau dans ~55-60 % des cas, mais une fausse zone posée au hasard au même endroit tient aussi dans ~50-57 % des cas.
  L'avantage propre à ses zones est de 0 à 9 points, net seulement sur les cryptos (toutes unités) et sur les petites
  unités (M30 / M15) des autres marchés ; nul sur l'or / indices / euro et sur les 47 marchés en H4 / journalier.
- **« Au milieu une 1re fois -> au milieu une 2e fois » : non.** Le 2e demi-tour se fait au milieu dans ~20-25 % des
  cas, comme pour les fausses zones. Un 1er demi-tour au milieu ne donne pas plus de chances de réaction ensuite qu'un
  demi-tour à l'entrée ou profond.
- **« Rebond juste à l'entrée = zone valide » : à peine.** Après un 1er rebond à l'entrée, la 2e réaction arrive dans
  49-61 % des cas (témoin 44-56 %) ; écart réel seulement sur cryptos H4 (z 3,2).
- Au 1er contact, ses zones ne réagissent pas plus que des boîtes au hasard (25-35 % des deux côtés).

## 7. Profil de volume (VRVP, information)

Résultats séparés selon que la zone est sur le point de contrôle, sur un nœud de fort volume, ou dans la zone de
valeur : **aucun effet stable**. Exemples (traduction fidèle, départ H4, R2) : cryptos, zone sur un nœud de fort volume
+0,32 R (193) contre -0,27 (166) sans ; mais 47 marchés : -0,46 (321) avec contre -0,16 (397) sans. Le point de
contrôle va dans un sens sur les cryptos et dans l'autre sur les 47 marchés. Détail : `resultats_v7_*.json`, clé `vrvp`.

---

## 8. Verdict honnête

1. **Attendre que la zone ait déjà été touchée (R2, R3) n'améliore pas sa stratégie**, ni au départ H4 ni au départ
   journalier, ni dans l'ancienne ni dans la traduction fidèle. Sur les mêmes zones, le 1er passage paie mieux que le 2e.
   Aucune des 6 règles ne « tient debout » (positive sur les 3 périodes) dans la traduction fidèle.
2. Les variantes « au milieu » (R2M) et « à l'entrée » (R2E, R2E-milieu) ne changent pas ce constat. La meilleure ligne
   (cryptos H4 R2E-milieu, +0,16 R sur 136 trades) vient d'avant 2022 (+1,44 R) et est négative ensuite.
3. Sa phrase « une zone qui a résisté résistera » est mesurablement un peu vraie (2e réaction 55-60 %), mais presque
   autant pour des boîtes posées au hasard : l'avantage propre à ses zones (0 à 9 points) est trop petit pour payer les
   frais, sauf peut-être sur les cryptos où il est le plus net.
4. **La fréquence** : le code fidèle ne voit que ~0,2 trade par semaine au départ H4 sur 4 indices, parce que la
   moitié des zones H4 meurent à leur naissance, que 3 contacts sur 4 n'ont pas de petite zone dedans, et que l'objectif
   3 à 2 R manque souvent. Pour atteindre ses 4-5 trades par semaine, il faut partir du H1 sans exiger de zone dans la
   zone : alors tout est perdant (-0,14 à -0,33 R par trade, des dizaines de milliers de trades).
5. La seule ligne positive solide reste celle déjà connue : **ancienne traduction, cryptos** (V1 H4 +0,19 R, V1 D1
   +0,44 R), années déjà vues. Elle ne se retrouve pas avec la traduction fidèle (-0,11 R / -0,01 R).

**Années déjà vues** : pour V1, toutes les années ont déjà été vues (laboratoire SMC 2015-2026 dont la période cachée
ouverte le 15/10 ; cryptos 2017-2026 dans chef_crypto et chef_compte_ftmo). R2, R3, R2M, R2E, R2E-milieu, les versions
« petite zone », « par unité », la traduction fidèle et le départ journalier avec plancher n'avaient jamais été
calculés : toutes leurs années sont neuves, mais ces règles ont été formulées après les résultats de V1 : il n'y a plus
de période vraiment cachée pour cette famille.

## 9. Ce qui manquerait pour aller plus loin

1. **Ses vrais trades** (captures ou relevé MT5 de quelques semaines, avec l'heure, la zone choisie, l'entrée, le stop et
   la sortie) : c'est le seul moyen de savoir QUELLES zones il prend, puisqu'à 4-5 trades par semaine il ne peut pas
   suivre la règle « zone dans la zone + objectif 3 à 2 R » telle que codée.
2. Vérifier sur son TradingView 2-3 cas précis de « zones mort-nées » (bougie de naissance qui clôture au-delà du
   milieu) : si elles ne s'affichent pas chez lui non plus, la traduction fidèle est confirmée sur ce point.
3. Si on poursuit : la seule mesure qui sort du hasard est la 2e réaction sur les cryptos ; une étude dédiée devrait
   chercher une sortie plus courte (les 2 R / sommet H1 / zone opposée ne sont pas faits pour un rebond de 55-60 %).

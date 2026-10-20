# LA MÉMOIRE DES SITUATIONS — l'or (rapport du 18/10/2026 22:14)

Mesure SANS IA. A = agitation (moyenne plus haut - plus bas des 14 derniers jours). Gros mouvement = au moins 3 A d'un côté dans les 72 h. Force = écart / incertitude (grappes = semaines). N = 1285 cases -> seuil de preuve 3.78.

## Conclusion (18/10/2026 22h15) — verdict au contrôle 01/2024 -> 09/2025 : NON sur les trois questions

**Ce qu'elle retient.** 121 348 moments de l'or (chaque clôture d'heure, 2004 -> 09/2025), chacun résumé en 20 nombres
(ses zones D1 / H4 / H1, tendances 1 / 5 / 20 / 60 j, structure, agitation, compression, peur GVZ, heure, mouvement
1 h / 4 h) avec ce qui a suivi sur 24 h et 72 h. Un gros mouvement (au moins 3 agitations en 72 h) arrive dans ~5 % des
moments, à toutes les époques.

**La barrière tient.** Mémoire honnête (suite connue 5 jours avant la question) : alerte « gros mouvement » juste dans
8 % des cas (base 5 %), sens juste 52 %. Mémoire qui triche (futur compris) : 46 % et 99 % de sens justes. L'écart
énorme prouve que la barrière est bien placée : sans elle, la mémoire « se souvient » de l'avenir.

| question (k retenu sur 2008-2021) | 2008-2021 | 2022-2023 | contrôle 2024-2025 | seuil 3,78 |
|---|---|---|---|---|
| (i) gros mouvements : alerte contre la base (k = 20) | +3,1 pts (force 2,4) | +5,8 pts (1,6) | +2,4 pts (0,8) | non |
| (ii) sens : contre les souvenirs au hasard (k = 50) | +1,6 pts (0,4) | +11,0 pts (1,4) | +16,3 pts (2,0) | non |
| (ii) sens : contre la tendance 60 j seule | -4,4 pts | -0,5 pts | -7,1 pts | perd |
| (iii) trading (k = 20), R moyen | -0,03 R | +0,17 R | -0,01 R | non |

- (i) Il y a un PETIT signal toujours du bon côté (aire 0,57-0,61 contre 0,49-0,51 au hasard et 0,53-0,54 pour la
  tendance seule) : la mémoire reconnaît un peu les moments où l'or va bouger loin. Trop faible pour être prouvé.
- (ii) Le sens : la mémoire ne fait pas mieux que « suivre la tendance 60 j » (qui donne 57-66 % de sens justes) ; elle
  bat les souvenirs au hasard seulement parce que ceux-ci répètent la pente passée de l'or (moins de hausses avant 2022).
- (iii) Trading quand elle est confiante (stop derrière la structure, stop suiveur 1 h, sans plafond, frais FTMO) : R
  moyen ~ 0, gros gains rares (>= 5R : 0,7 à 3 % des trades), ne bat pas le jumeau.

**Ancienne mémoire de Run A** : elle ne retenait que les trades de l'IA elle-même (au plus 5 000, 5 voisins), donc ses
souvenirs dépendaient de sa façon de trader et changeaient avec elle, sans barrière de temps. La nouvelle retient TOUT le
marché (121 000 moments, indépendants de l'IA), avec une barrière stricte : elle est plus honnête et plus riche, mais elle
non plus ne donne pas le sens.

**Pour MAGNETAR** : rien n'est prouvé, donc pas de nouveau sens à greffer maintenant. Si le chef de projet veut quand
même l'essayer, la seule partie qui porte un peu d'information est « probabilité d'un gros mouvement » (pas le sens) :
2 nombres (probabilité des 20 voisins, taux de base) ajoutés en DERNIER à ce qu'il voit, poids nuls au départ, mémoire
recalculée à chaque instant avec la même barrière (suite connue 5 jours avant), à l'entraînement comme en examen.

## Ce qu'elle retient (tous les souvenirs)

| période | moments | gros mouvements 72 h | dont à la hausse | gros en 24 h | avance moy. hausse / baisse 72 h | net 72 h |
|---|---|---|---|---|---|---|
| echauffement | 18776 | 5.6 % | 44 % | 0.3 % | 1.06 / 0.90 A | +0.22 A |
| choix | 80725 | 5.3 % | 46 % | 0.7 % | 0.96 / 0.95 A | +0.06 A |
| verification | 11794 | 5.5 % | 61 % | 0.6 % | 1.00 / 0.89 A | +0.05 A |
| controle | 9981 | 5.1 % | 72 % | 0.3 % | 1.12 / 0.78 A | +0.34 A |

## Test piège (2008-2021, 1 moment sur 4) : mémoire honnête contre mémoire qui triche

| k | honnête : taux pendant l'alerte ; écart (force) ; aire | triche : taux pendant l'alerte ; écart (force) ; aire | sens justes honnête / triche |
|---|---|---|---|
| 20 | 7.9 % ; +2.8 pts (+2.1) ; 0.560 | 45.9 % ; +40.8 pts (+18.0) ; 0.986 | 52.4 % / 98.7 % |
| 50 | 7.9 % ; +2.8 pts (+2.1) ; 0.580 | 37.4 % ; +32.3 pts (+14.7) ; 0.976 | 53.0 % / 97.6 % |
| 200 | 8.5 % ; +3.3 pts (+2.2) ; 0.601 | 33.8 % ; +28.7 pts (+11.9) ; 0.939 | 51.0 % / 94.6 % |

## Contrôle 01/2024 -> 09/2025 (une seule fois) — (i) gros mouvements : **non** ; (ii) sens : **non** ; (iii) trading : **non**

### (i) gros mouvements, k = 20 — 2008-2021 (choix)

| k | taux de base | alertes (part du temps) | gros mouvements pendant l'alerte | écart à la base (force) | au hasard : taux pendant ses alertes ; écart (force) | tendance 60 j : taux ; écart (force) | précision Brier (force) | aire mémoire / hasard / tendance |
|---|---|---|---|---|---|---|---|---|
| 20 | 5.2 % | 15.3 % | 8.2 % (base 5.1 %) | +3.1 pts (+2.4) | 6.0 % ; +2.3 pts (+1.5) | 7.0 % ; +1.3 pts (+0.8) | -9.44 ‰ (-7.2) | 0.566 / 0.496 / 0.525 |

### (i) gros mouvements, k = 20 — 2022-2023 (vérification)

| k | taux de base | alertes (part du temps) | gros mouvements pendant l'alerte | écart à la base (force) | au hasard : taux pendant ses alertes ; écart (force) | tendance 60 j : taux ; écart (force) | précision Brier (force) | aire mémoire / hasard / tendance |
|---|---|---|---|---|---|---|---|---|
| 20 | 5.3 % | 14.6 % | 11.1 % (base 5.3 %) | +5.8 pts (+1.6) | 5.1 % ; +6.0 pts (+1.5) | 9.7 % ; +1.4 pts (+0.3) | -7.99 ‰ (-2.1) | 0.613 / 0.493 / 0.527 |

### (i) gros mouvements, k = 20 — 01/2024 -> 09/2025 (contrôle, une seule fois)

| k | taux de base | alertes (part du temps) | gros mouvements pendant l'alerte | écart à la base (force) | au hasard : taux pendant ses alertes ; écart (force) | tendance 60 j : taux ; écart (force) | précision Brier (force) | aire mémoire / hasard / tendance |
|---|---|---|---|---|---|---|---|---|
| 20 | 5.4 % | 19.5 % | 7.8 % (base 5.4 %) | +2.4 pts (+0.8) | 5.1 % ; +2.7 pts (+0.8) | 7.4 % ; +0.4 pts (+0.1) | -13.48 ‰ (-3.5) | 0.581 / 0.506 / 0.536 |

### (ii) sens des gros mouvements, k = 50 — 2008-2021 (choix)

| k | gros mouvements (sens connu) ; dont hausse | la mémoire donne un sens | sens justes | contre 50 % (force) | au hasard : justes ; écart (force) | tendance 60 j : justes ; écart (force) |
|---|---|---|---|---|---|---|
| 50 | 4299 ; 46 % | 58 % | 52.5 % | +2.5 pts (+0.6) | 50.9 % ; +1.6 pts (+0.4) | 56.9 % ; -4.4 pts (-0.7) |

### (ii) sens des gros mouvements, k = 50 — 2022-2023 (vérification)

| k | gros mouvements (sens connu) ; dont hausse | la mémoire donne un sens | sens justes | contre 50 % (force) | au hasard : justes ; écart (force) | tendance 60 j : justes ; écart (force) |
|---|---|---|---|---|---|---|
| 50 | 647 ; 61 % | 63 % | 56.6 % | +6.6 pts (+0.6) | 45.5 % ; +11.0 pts (+1.4) | 57.1 % ; -0.5 pts (-0.0) |

### (ii) sens des gros mouvements, k = 50 — 01/2024 -> 09/2025 (contrôle, une seule fois)

| k | gros mouvements (sens connu) ; dont hausse | la mémoire donne un sens | sens justes | contre 50 % (force) | au hasard : justes ; écart (force) | tendance 60 j : justes ; écart (force) |
|---|---|---|---|---|---|---|
| 50 | 510 ; 72 % | 69 % | 58.4 % | +8.4 pts (+1.0) | 44.7 % ; +16.3 pts (+2.0) | 65.5 % ; -7.1 pts (-0.5) |

### (iii) trading sur ses souvenirs, k = 20 — 2008-2021 (choix)

| k | signaux (part du temps) | trades | trades / mois | gagnants | R moyen ± incertitude (force) | médiane | >= 5R / >= 10R | durée | jumeau : R ; avance (force) | compte 0,5 % : gain / mois ; baisse max ; réussis / morts ; jumeaux |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 6.9 % | 909 | 5.4 | 28 % | -0.031 ± 0.050 (-0.6) | -0.342 | 1.4 % / 0.3 % | 15 h | -0.020 ; -0.006 (-0.1) | -0.08 % ; 30.9 % ; 198 / 316 ; -0.07 % (56 % aussi bons) |

### (iii) trading sur ses souvenirs, k = 20 — 2022-2023 (vérification)

| k | signaux (part du temps) | trades | trades / mois | gagnants | R moyen ± incertitude (force) | médiane | >= 5R / >= 10R | durée | jumeau : R ; avance (force) | compte 0,5 % : gain / mois ; baisse max ; réussis / morts ; jumeaux |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 8.3 % | 132 | 5.5 | 36 % | +0.166 ± 0.142 (+1.2) | -0.201 | 3.0 % / 0.0 % | 18 h | -0.059 ; +0.113 (+1.0) | +0.46 % ; 5.6 % ; 11 / 0 ; +0.14 % (14 % aussi bons) |

### (iii) trading sur ses souvenirs, k = 20 — 01/2024 -> 09/2025 (contrôle, une seule fois)

| k | signaux (part du temps) | trades | trades / mois | gagnants | R moyen ± incertitude (force) | médiane | >= 5R / >= 10R | durée | jumeau : R ; avance (force) | compte 0,5 % : gain / mois ; baisse max ; réussis / morts ; jumeaux |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 9.4 % | 141 | 6.7 | 35 % | -0.006 ± 0.100 (-0.1) | -0.284 | 0.7 % / 0.0 % | 16 h | -0.095 ; +0.045 (+0.5) | -0.02 % ; 11.0 % ; 0 / 2 ; -0.17 % (26 % aussi bons) |

## Tous les k — 2008-2021 (choix)

| k | taux de base | alertes (part du temps) | gros mouvements pendant l'alerte | écart à la base (force) | au hasard : taux pendant ses alertes ; écart (force) | tendance 60 j : taux ; écart (force) | précision Brier (force) | aire mémoire / hasard / tendance |
|---|---|---|---|---|---|---|---|---|
| 20 | 5.2 % | 15.3 % | 8.2 % (base 5.1 %) | +3.1 pts (+2.4) | 6.0 % ; +2.3 pts (+1.5) | 7.0 % ; +1.3 pts (+0.8) | -9.44 ‰ (-7.2) | 0.566 / 0.496 / 0.525 |
| 50 | 5.2 % | 16.6 % | 8.1 % (base 5.1 %) | +3.0 pts (+2.3) | 5.2 % ; +2.9 pts (+2.0) | 7.8 % ; +0.3 pts (+0.2) | -4.35 ‰ (-4.3) | 0.586 / 0.490 / 0.533 |
| 200 | 5.2 % | 13.9 % | 8.6 % (base 5.2 %) | +3.5 pts (+2.3) | 4.7 % ; +4.0 pts (+1.6) | 9.2 % ; -0.6 pts (-0.2) | -0.59 ‰ (-0.8) | 0.603 / 0.487 / 0.540 |

| k | gros mouvements (sens connu) ; dont hausse | la mémoire donne un sens | sens justes | contre 50 % (force) | au hasard : justes ; écart (force) | tendance 60 j : justes ; écart (force) |
|---|---|---|---|---|---|---|
| 20 | 4299 ; 46 % | 38 % | 52.1 % | +2.1 pts (+0.5) | 51.7 % ; -0.4 pts (-0.1) | 56.2 % ; -4.1 pts (-0.6) |
| 50 | 4299 ; 46 % | 58 % | 52.5 % | +2.5 pts (+0.6) | 50.9 % ; +1.6 pts (+0.4) | 56.9 % ; -4.4 pts (-0.7) |
| 200 | 4299 ; 46 % | 87 % | 50.4 % | +0.4 pts (+0.1) | 50.1 % ; +0.0 pts (+0.0) | 58.6 % ; -8.2 pts (-1.5) |

| k | signaux (part du temps) | trades | trades / mois | gagnants | R moyen ± incertitude (force) | médiane | >= 5R / >= 10R | durée | jumeau : R ; avance (force) | compte 0,5 % : gain / mois ; baisse max ; réussis / morts ; jumeaux |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 6.9 % | 909 | 5.4 | 28 % | -0.031 ± 0.050 (-0.6) | -0.342 | 1.4 % / 0.3 % | 15 h | -0.020 ; -0.006 (-0.1) | -0.08 % ; 30.9 % ; 198 / 316 ; -0.07 % (56 % aussi bons) |
| 50 | 14.8 % | 1685 | 10.0 | 27 % | -0.117 ± 0.031 (-3.8) | -0.356 | 0.8 % / 0.1 % | 15 h | -0.014 ; -0.051 (-1.8) | -0.59 % ; 100.9 % ; 0 / 639 ; -0.32 % (98 % aussi bons) |
| 200 | 10.8 % | 1194 | 7.1 | 27 % | -0.105 ± 0.045 (-2.3) | -0.363 | 1.3 % / 0.3 % | 14 h | -0.014 ; -0.045 (-1.2) | -0.37 % ; 67.1 % ; 93 / 555 ; -0.22 % (89 % aussi bons) |

## Tous les k — 2022-2023 (vérification)

| k | taux de base | alertes (part du temps) | gros mouvements pendant l'alerte | écart à la base (force) | au hasard : taux pendant ses alertes ; écart (force) | tendance 60 j : taux ; écart (force) | précision Brier (force) | aire mémoire / hasard / tendance |
|---|---|---|---|---|---|---|---|---|
| 20 | 5.3 % | 14.6 % | 11.1 % (base 5.3 %) | +5.8 pts (+1.6) | 5.1 % ; +6.0 pts (+1.5) | 9.7 % ; +1.4 pts (+0.3) | -7.99 ‰ (-2.1) | 0.613 / 0.493 / 0.527 |
| 50 | 5.3 % | 16.7 % | 10.6 % (base 5.3 %) | +5.3 pts (+1.5) | 5.7 % ; +4.9 pts (+1.3) | 11.2 % ; -0.5 pts (-0.1) | -2.71 ‰ (-1.1) | 0.630 / 0.498 / 0.515 |
| 200 | 5.3 % | 13.4 % | 12.8 % (base 5.3 %) | +7.5 pts (+1.8) | 26.7 % ; -13.9 pts (-1.1) | 21.1 % ; -8.4 pts (-0.7) | +0.94 ‰ (+0.6) | 0.653 / 0.483 / 0.516 |

| k | gros mouvements (sens connu) ; dont hausse | la mémoire donne un sens | sens justes | contre 50 % (force) | au hasard : justes ; écart (force) | tendance 60 j : justes ; écart (force) |
|---|---|---|---|---|---|---|
| 20 | 647 ; 61 % | 45 % | 59.0 % | +9.0 pts (+0.7) | 48.0 % ; +16.2 pts (+1.4) | 61.4 % ; -2.4 pts (-0.2) |
| 50 | 647 ; 61 % | 63 % | 56.6 % | +6.6 pts (+0.6) | 45.5 % ; +11.0 pts (+1.4) | 57.1 % ; -0.5 pts (-0.0) |
| 200 | 647 ; 61 % | 88 % | 54.1 % | +4.1 pts (+0.4) | 46.2 % ; +8.0 pts (+0.9) | 56.5 % ; -2.3 pts (-0.2) |

| k | signaux (part du temps) | trades | trades / mois | gagnants | R moyen ± incertitude (force) | médiane | >= 5R / >= 10R | durée | jumeau : R ; avance (force) | compte 0,5 % : gain / mois ; baisse max ; réussis / morts ; jumeaux |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 8.3 % | 132 | 5.5 | 36 % | +0.166 ± 0.142 (+1.2) | -0.201 | 3.0 % / 0.0 % | 18 h | -0.059 ; +0.113 (+1.0) | +0.46 % ; 5.6 % ; 11 / 0 ; +0.14 % (14 % aussi bons) |
| 50 | 15.1 % | 218 | 9.1 | 37 % | +0.093 ± 0.101 (+0.9) | -0.177 | 2.3 % / 0.0 % | 18 h | -0.108 ; +0.100 (+1.3) | +0.42 % ; 7.2 % ; 4 / 0 ; -0.02 % (9 % aussi bons) |
| 200 | 9.9 % | 134 | 5.7 | 39 % | +0.254 ± 0.134 (+1.9) | -0.144 | 3.0 % / 0.7 % | 20 h | -0.269 ; +0.262 (+2.8) | +0.73 % ; 6.9 % ; 61 / 0 ; -0.05 % (0 % aussi bons) |

## LA MÉMOIRE DES SITUATIONS (or) — plan FIGÉ avant toute mesure (18/10/2026 22:07)

Mesure SANS IA sur l'or (XAUUSD, bougies de 15 min 2004 -> 09/2025, yeux de l'école de la précision `ecole/precision/structure.py`). Heure du serveur. A = agitation (moyenne plus haut - plus bas des 14 derniers jours terminés). Rien après 09/2025.

### 1. Les souvenirs

- Un moment = chaque clôture d'heure (bougie de 15 min qui finit à l'heure pile), A connue.
- Son vecteur (20 nombres, tout connu à la clôture, sans futur) : zone D1 demande ; zone D1 offre ; zone H4 demande ; zone H4 offre ; zone H1 demande ; zone H1 offre ; tendance 1 j ; tendance 5 j ; tendance 20 j ; tendance 60 j ; structure D1 ; structure H4 ; agitation / prix ; compression ; peur or GVZ (1 an) ; peur or GVZ (60 j) ; heure (sin) ; heure (cos) ; mouvement 1 h ; mouvement 4 h.
  Zones : distance du prix au bord proche de la zone de demande vivante la plus proche (dessous) et de la zone d'offre (dessus), en A, transformée log(1 + d) (dans la zone ou au-delà : d négatif borné à -2 ; aucune zone : log 21). Tendances : (prix - clôture d'il y a h jours) / (A x racine(h)), bornée +-6. Structure : (signe des 2 derniers sommets + signe des 2 derniers creux) / 2. Agitation : log(A / prix). Compression : log(agitation 3 j / agitation 14 j). GVZ : écart du niveau (log) à la moyenne de l'année et des 60 dernières valeurs, en écarts, valeur du jour J utilisée à J+1 08h00 (donnees/monde.py) ; absente (avant 2010) = 0. Heure : sinus / cosinus. Mouvement : (prix - prix 1 h / 4 h avant) / A.
- Mise à l'échelle : chaque nombre divisé par son écart-type sur l'échauffement (moments avant 2008-01-01), sauf GVZ, sinus et cosinus (déjà à l'échelle) ; distance = distance euclidienne simple.
- Ce qui a suivi : plus grande avance à la hausse (plus haut - prix) / A et à la baisse (prix - plus bas) / A sur 96 et 288 bougies de 15 min (24 h et 72 h de cotation) ; mouvement net (clôture - prix) / A ; GROS MOUVEMENT = au moins 3 A d'un côté sur 72 h ; son SENS = le côté atteint le premier (les deux dans la même bougie : sens inconnu).

### 2. Règle anti-triche (la même partout)

- Un souvenir n'entre dans la mémoire qu'à l'instant (clôture de la dernière bougie de ses 72 h) + 5 jours. Le moment présent et ses voisins (8 jours) n'y sont donc jamais.
- Une question n'est posée qu'avec au moins 2000 souvenirs, à partir de 2008-01-01.
- Test « sans futur » : vecteurs calculés sur des données coupées à t = calcul complet ; prévisions inchangées si on remplace la suite des souvenirs pas encore permis par n'importe quoi.
- TEST PIÈGE : la même mesure avec une mémoire qui triche (tous les moments, futur compris, sauf le moment lui-même), sur un moment sur 4 de la période de choix : elle doit être énormément meilleure.

### 3. La mesure

- Pour chaque moment : les k plus proches souvenirs (k = 20 / 50 / 200) ; probabilité d'un gros mouvement = part des voisins qui en ont eu un ; sens = majorité des sens de leurs gros mouvements.
- Repères : TAUX DE BASE (part des gros mouvements dans toute la mémoire permise à cet instant), SOUVENIRS AU HASARD (k souvenirs tirés au hasard dans la mémoire permise), TENDANCE 60 J SEULE (k plus proches voisins sur la seule tendance 60 j pour la probabilité ; signe de la tendance 60 j pour le sens).
- (i) gros mouvements : ALERTE = probabilité >= 2 x le taux de base ; taux réel des gros mouvements pendant les alertes contre le taux de base (écart en points, force) ; contre les alertes des souvenirs au hasard et de la tendance 60 j seule (même règle) ; gain de précision (Brier : (y - base)² - (y - mémoire)², tous les moments). Descriptif : aire sous la courbe (chance qu'un moment à gros mouvement ait une probabilité plus haute qu'un autre).
- (ii) sens : sur les moments qui ont VRAIMENT eu un gros mouvement de sens connu et où la mémoire donne un sens : part de sens justes contre 50 %, contre les souvenirs au hasard (même moments, apparié) et contre le signe de la tendance 60 j (apparié).
- (iii) trading : signal si alerte ET au moins 5 gros mouvements parmi les voisins ET au moins 67% du même sens ; entrée au marché à l'ouverture suivante dans ce sens ; stop derrière le dernier creux (achat) / sommet (vente) confirmé H1 + 0.1 A, sinon H4, risque entre 0.2 et 3 A et plus qu'un aller-retour de frais, sinon pas de trade ; stop suiveur H1 (nouveaux creux / sommets, regarder/pistes/mouvements.trade_suiveur = moteur de l'arbre), AUCUN objectif, 30 jours au plus, frais FTMO du 16/10, nuits, glissement du stop ; un trade à la fois. Contre le JUMEAU (sens retourné, même stop de l'autre côté) : avance = (R - R retourné) / 2. Mesures : trades / mois, gagnants, R moyen (force), part >= 5R / >= 10R. Compte FTMO 100 000 $ à 0.5 % par trade contre 200 jumeaux.
- Incertitudes : grappes = semaines (moments et trades d'une même semaine ensemble).

### Choix, jugement

- Choix sur 2008-2021 SEULEMENT : pour (i) le k de plus grande force de l'alerte contre la base ; pour (ii) le k de plus grande force contre les souvenirs au hasard ; pour (iii) le k de plus grande force du R moyen (au moins 100 trades). Vérification 2022-2023 (tous les k). Contrôle UNE fois 2024-2025 : les k retenus seulement.
- N = 1257 cases déjà jugées + 12 (i) + 9 (ii) + 7 (iii) = 1285 -> seuil de preuve max(3, racine(2 ln N)) = 3.78.
- (i) RÉELLE si l'écart alerte - base est > 0 sur les 3 périodes et sa force >= seuil au contrôle ; « au-delà de la tendance » si en plus elle bat la tendance 60 j seule au contrôle. (ii) RÉEL si le sens bat les souvenirs au hasard sur les 3 périodes avec force >= seuil au contrôle (même chose contre la tendance 60 j). (iii) PROUVÉ si R moyen > 0 sur les 3 périodes et force >= seuil au contrôle ; PROMETTEUR si > 0 sur les 3 avec force > 2 au contrôle ; sinon non.
- Si (i) ou (ii) est réel au contrôle : décrire (sans l'appliquer) le nouveau sens de MAGNETAR.

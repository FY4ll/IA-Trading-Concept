# LA MÉMOIRE DES SITUATIONS (or) — plan FIGÉ avant toute mesure (18/10/2026 22:07)

Mesure SANS IA sur l'or (XAUUSD, bougies de 15 min 2004 -> 09/2025, yeux de l'école de la précision `ecole/precision/structure.py`). Heure du serveur. A = agitation (moyenne plus haut - plus bas des 14 derniers jours terminés). Rien après 09/2025.

## 1. Les souvenirs

- Un moment = chaque clôture d'heure (bougie de 15 min qui finit à l'heure pile), A connue.
- Son vecteur (20 nombres, tout connu à la clôture, sans futur) : zone D1 demande ; zone D1 offre ; zone H4 demande ; zone H4 offre ; zone H1 demande ; zone H1 offre ; tendance 1 j ; tendance 5 j ; tendance 20 j ; tendance 60 j ; structure D1 ; structure H4 ; agitation / prix ; compression ; peur or GVZ (1 an) ; peur or GVZ (60 j) ; heure (sin) ; heure (cos) ; mouvement 1 h ; mouvement 4 h.
  Zones : distance du prix au bord proche de la zone de demande vivante la plus proche (dessous) et de la zone d'offre (dessus), en A, transformée log(1 + d) (dans la zone ou au-delà : d négatif borné à -2 ; aucune zone : log 21). Tendances : (prix - clôture d'il y a h jours) / (A x racine(h)), bornée +-6. Structure : (signe des 2 derniers sommets + signe des 2 derniers creux) / 2. Agitation : log(A / prix). Compression : log(agitation 3 j / agitation 14 j). GVZ : écart du niveau (log) à la moyenne de l'année et des 60 dernières valeurs, en écarts, valeur du jour J utilisée à J+1 08h00 (donnees/monde.py) ; absente (avant 2010) = 0. Heure : sinus / cosinus. Mouvement : (prix - prix 1 h / 4 h avant) / A.
- Mise à l'échelle : chaque nombre divisé par son écart-type sur l'échauffement (moments avant 2008-01-01), sauf GVZ, sinus et cosinus (déjà à l'échelle) ; distance = distance euclidienne simple.
- Ce qui a suivi : plus grande avance à la hausse (plus haut - prix) / A et à la baisse (prix - plus bas) / A sur 96 et 288 bougies de 15 min (24 h et 72 h de cotation) ; mouvement net (clôture - prix) / A ; GROS MOUVEMENT = au moins 3 A d'un côté sur 72 h ; son SENS = le côté atteint le premier (les deux dans la même bougie : sens inconnu).

## 2. Règle anti-triche (la même partout)

- Un souvenir n'entre dans la mémoire qu'à l'instant (clôture de la dernière bougie de ses 72 h) + 5 jours. Le moment présent et ses voisins (8 jours) n'y sont donc jamais.
- Une question n'est posée qu'avec au moins 2000 souvenirs, à partir de 2008-01-01.
- Test « sans futur » : vecteurs calculés sur des données coupées à t = calcul complet ; prévisions inchangées si on remplace la suite des souvenirs pas encore permis par n'importe quoi.
- TEST PIÈGE : la même mesure avec une mémoire qui triche (tous les moments, futur compris, sauf le moment lui-même), sur un moment sur 4 de la période de choix : elle doit être énormément meilleure.

## 3. La mesure

- Pour chaque moment : les k plus proches souvenirs (k = 20 / 50 / 200) ; probabilité d'un gros mouvement = part des voisins qui en ont eu un ; sens = majorité des sens de leurs gros mouvements.
- Repères : TAUX DE BASE (part des gros mouvements dans toute la mémoire permise à cet instant), SOUVENIRS AU HASARD (k souvenirs tirés au hasard dans la mémoire permise), TENDANCE 60 J SEULE (k plus proches voisins sur la seule tendance 60 j pour la probabilité ; signe de la tendance 60 j pour le sens).
- (i) gros mouvements : ALERTE = probabilité >= 2 x le taux de base ; taux réel des gros mouvements pendant les alertes contre le taux de base (écart en points, force) ; contre les alertes des souvenirs au hasard et de la tendance 60 j seule (même règle) ; gain de précision (Brier : (y - base)² - (y - mémoire)², tous les moments). Descriptif : aire sous la courbe (chance qu'un moment à gros mouvement ait une probabilité plus haute qu'un autre).
- (ii) sens : sur les moments qui ont VRAIMENT eu un gros mouvement de sens connu et où la mémoire donne un sens : part de sens justes contre 50 %, contre les souvenirs au hasard (même moments, apparié) et contre le signe de la tendance 60 j (apparié).
- (iii) trading : signal si alerte ET au moins 5 gros mouvements parmi les voisins ET au moins 67% du même sens ; entrée au marché à l'ouverture suivante dans ce sens ; stop derrière le dernier creux (achat) / sommet (vente) confirmé H1 + 0.1 A, sinon H4, risque entre 0.2 et 3 A et plus qu'un aller-retour de frais, sinon pas de trade ; stop suiveur H1 (nouveaux creux / sommets, regarder/pistes/mouvements.trade_suiveur = moteur de l'arbre), AUCUN objectif, 30 jours au plus, frais FTMO du 16/10, nuits, glissement du stop ; un trade à la fois. Contre le JUMEAU (sens retourné, même stop de l'autre côté) : avance = (R - R retourné) / 2. Mesures : trades / mois, gagnants, R moyen (force), part >= 5R / >= 10R. Compte FTMO 100 000 $ à 0.5 % par trade contre 200 jumeaux.
- Incertitudes : grappes = semaines (moments et trades d'une même semaine ensemble).

## Choix, jugement

- Choix sur 2008-2021 SEULEMENT : pour (i) le k de plus grande force de l'alerte contre la base ; pour (ii) le k de plus grande force contre les souvenirs au hasard ; pour (iii) le k de plus grande force du R moyen (au moins 100 trades). Vérification 2022-2023 (tous les k). Contrôle UNE fois 2024-2025 : les k retenus seulement.
- N = 1257 cases déjà jugées + 12 (i) + 9 (ii) + 7 (iii) = 1285 -> seuil de preuve max(3, racine(2 ln N)) = 3.78.
- (i) RÉELLE si l'écart alerte - base est > 0 sur les 3 périodes et sa force >= seuil au contrôle ; « au-delà de la tendance » si en plus elle bat la tendance 60 j seule au contrôle. (ii) RÉEL si le sens bat les souvenirs au hasard sur les 3 périodes avec force >= seuil au contrôle (même chose contre la tendance 60 j). (iii) PROUVÉ si R moyen > 0 sur les 3 périodes et force >= seuil au contrôle ; PROMETTEUR si > 0 sur les 3 avec force > 2 au contrôle ; sinon non.
- Si (i) ou (ii) est réel au contrôle : décrire (sans l'appliquer) le nouveau sens de MAGNETAR.

# Méthode du chef de projet avec SON indicateur (indicateur de zones d'offre et de demande (supply and demand)) — définition FIGÉE (15/10/2026, avant tout test)

Réponses du chef de projet au questionnaire : apparition = version prudente ; entrée = ligne du milieu ; stop = les
deux à comparer ; cascades = toutes à comparer. Mêmes données, frais prudents et juge à jumeau que
docs/SMC_DEFINITIONS.md (A, C, D) ; sans futur.

1. **Zone zones supply and demand** (traduction exacte du code Pine, pour une unité de temps donnée) : à la clôture de la bougie i,
   zone de DEMANDE si la bougie j = i-1 est rouge (clôture < ouverture), si plus bas(j) > plus haut(j-2) (FVG), et si
   clôture(i) > max(plus haut(i-4), plus haut(i-5)) (BOS) ; zone = [plus bas(j), plus haut(j)], milieu = moyenne.
   OFFRE : symétrique (bougie verte, plus haut(j) < plus bas(j-2), clôture(i) < min(plus bas(i-4), plus bas(i-5))).
   Version prudente : la zone n'existe qu'à la CLÔTURE de la bougie i (une bougie après la rouge).
   **Effacement** : à la première clôture de la petite unité (celle de l'entrée, = le graphique) au-delà du milieu.
2. **Cascade** : une zone zones supply and demand de l'unité de DIRECTION (X) vivante ; le prix touche son bord proche ; puis la
   PREMIÈRE zone zones supply and demand de l'unité d'ENTRÉE (Y), du même sens, confirmée APRÈS ce contact, dont le milieu est à
   l'intérieur de la zone X, et remplie avant l'effacement de X (au plus 200 bougies Y d'attente). Un trade par zone X.
   Paires (X -> Y) : cascade 1 = {D, H4} -> {M15, M5} ; cascade 2 = {D, H4} -> {M5, M3} ; cascade 3 = {H4, H1} ->
   {M15, M5} -> **8 paires distinctes** : D->M15, D->M5, D->M3, H4->M15, H4->M5, H4->M3, H1->M15, H1->M5.
3. **Entrée** : ordre limite au MILIEU de la zone Y (ouverture si la bougie ouvre déjà au-delà).
4. **Stop** (1 R = distance entrée -> stop A) :
   - **A** : bord opposé de la zone Y ± 0,2 × ATR(Y) ;
   - **B** : sortie à la première clôture d'une bougie Y au-delà du prix d'entrée (là où l'indicateur efface la zone),
     avec le stop A comme sécurité. Le jumeau suit la règle miroir.
5. **Sorties par tiers** (comme docs/SMC_MULTI_UT.md, sans point mort, qui ne changeait rien) : TP1 = 2 R ; TP2 = plus
   proche sommet / creux H1 confirmé entre TP1 et TP3 (sinon le milieu) ; TP3 = bord proche de la plus proche zone zones supply and demand
   OPPOSÉE de l'unité X, vivante à l'entrée ; trade ignoré s'il n'y a pas de TP3 au-delà de 2 R ; sortie après 30 jours.
6. **Marchés** : (a) or, Nasdaq, S&P 500, euro-dollar, à partir des minutes (toutes les paires) ; (b) les ~45 marchés,
   bougies de 15 minutes, paires dont l'entrée est en M15 seulement (D->M15, H4->M15, H1->M15 ; bougie d'entrée ignorée
   pour le trade et son jumeau). Chaque variante est jugée tous marchés du groupe réunis.
7. **Variantes** : (a) 8 paires × 2 stops = 16 ; (b) 3 × 2 = 6 -> 22. Total sur la période cachée : 438 + 22 = 460 ->
   **seuil = racine(2 ln 460) = 3,50**.
8. **Protocole** : choix 2015-2021 ; vérification 2022-2023 ; retenu si force ≥ 2 et gain > 0 sur 2015-2021, force > 0
   et gain > 0 sur 2022-2023 ; période cachée 2024-2026 une seule fois (verrou vie/smc/cachee_nono.json).

## Avenant 1 — ZONES GIGOGNES (15/10/2026, réponses du chef de projet, figé AVANT de lancer)
« Il faut des zones dans des zones : tu repères une zone en H4 ; s'il y a une plus petite zone dedans, tu la prends ;
tu redescends, etc. On prend la plus petite zone pour la plus grande précision. »
- Zone de départ (zones supply and demand, vivante) : **journalier** ou **H4** (les deux comparés). Le prix touche son bord proche à t.
- À l'instant t, on descend les unités (H1, M30, M15, M5, M3 ; jusqu'à M15 pour les 45 marchés) : à chaque unité, les
  zones zones supply and demand du même sens, vivantes à t, qui **chevauchent** la dernière zone retenue ; s'il y en a, on garde celle
  que le prix rencontre en premier (pour une demande : le plus haut bord haut), sinon on **saute** l'unité.
- Il faut **au moins 2 zones** (départ + 1) ; sinon pas de trade. Entrée : ordre limite au **milieu de la plus petite**
  zone retenue (au plus 200 bougies de son unité, avant l'effacement de la zone de départ et de la zone d'entrée).
- Effacement de toutes les zones : clôture au-delà de leur milieu sur la plus petite unité du groupe (M3 ou M15).
- Stops A / B, sorties par tiers, frais et jumeau : comme ci-dessus (TP3 = zone opposée de l'unité de DÉPART).
- Variantes : départ {D, H4} × stop {A, B} × groupe {4 marchés à la minute, 45 marchés} = **8**. Total sur la
  période cachée : 460 + 8 = 468 -> **seuil = racine(2 ln 468) = 3,51**. Même règle de retenue ; verrou
  vie/smc/cachee_gigogne.json.

## Avenant 2 — LES STOPS SONT-ILS TROP PETITS ? (15/10/2026, idée du chef de projet, figé AVANT de lancer)
« 100 pips de stop (10 $ sur l'or) ; il faut qu'il soit derrière une zone logique. »
- Mêmes trades que les zones gigognes (départ H4, stop A), même entrée au milieu de la plus petite zone.
- **Stop minimum** : si le stop derrière la zone est plus proche que p × ATR journalier (ATR du dernier jour complet),
  il est reculé à cette distance (toujours derrière la zone) ; p ∈ {0,10 ; 0,20 ; 0,30} (or à ~4 000 $ : ~5 $, ~10 $,
  ~15 $). 1 R, TP1 (2 R) et le seuil de TP3 (≥ 2 R) suivent le nouveau stop ; TP2 / TP3 inchangés.
- Variantes : 3 planchers × 2 groupes (4 marchés à la minute, 45 marchés) = **6**. Total : 468 + 6 = 474 ->
  **seuil = racine(2 ln 474) = 3,51**. Même règle de retenue ; verrou vie/smc/cachee_plancher.json.

## Avenant 3 — ÉVALUATION DES DERNIÈRES ANNÉES DEMANDÉE PAR LE CHEF DE PROJET (15/10/2026, figé AVANT)
« Cette stratégie est en place depuis 2022 : il faut la tester sur les dernières années. »
- UNE seule version, choisie d'avance comme la plus proche de sa pratique : « Gigogne H4 stop A plancher 0.2 »
  (zones zones supply and demand gigognes, départ H4, entrée au milieu de la plus petite zone, stop derrière la zone avec un minimum de
  0,2 ATR journalier ~ 100 pips sur l'or, TP1 2 R / TP2 / TP3 par tiers), sur les deux groupes (4 marchés à la minute,
  45 marchés). Évaluée UNE fois sur 2024-2026 (verrou vie/smc/cachee_strategie_chef.json), même si elle n'a pas passé
  la règle de retenue ; même seuil (3,51). Résultats aussi donnés année par année de 2022 à 2026.

# Stratégie personnelle MULTI-UNITÉS — définition FIGÉE (15/10/2026, d'après le chef de projet, AVANT tout test)

« Je cherchais en H4 et journalier puis je descendais pour trouver vraiment la bougie avant l'explosion de la zone ;
TP1 à 2 R pour rembourser mon risque, TP2 à une zone logique comme un CHoCH, TP3 à la prochaine zone d'offre / demande
selon le sens. »

Mêmes données, mêmes frais prudents, même juge à jumeau que docs/SMC_DEFINITIONS.md (A, C, D). Sans futur.

1. **Zone de fond** : zone d'offre / demande (base de 1 à 3 bougies ≤ 0,5 ATR, départ ≥ 2 ATR en ≤ 3 bougies) en **H4**
   ou en **journalier** (jour de New York), touchant le top 20 % du volume profile des 200 bougies précédentes
   (volume de cotation).
2. **Affinage (« la bougie avant l'explosion »)** : dans la petite unité (**M15** ou **M5**), entre le début de la base
   et la fin du départ de la zone de fond, la **dernière bougie opposée** (baissière pour une demande) suivie d'un
   départ ≥ 2 ATR (petite unité) en ≤ 3 bougies qui emmène le prix au-delà de la base de fond. Zone affinée = cette
   bougie (plus haut / plus bas), ramenée à l'intérieur de la zone de fond. Pas de bougie trouvée -> pas de trade.
3. **Entrée** : ordre limite au bord proche de la zone affinée, pendant le **1er contact** avec la zone de fond (le prix
   entre dans la zone de fond ; s'il en ressort de 0,5 ATR de fond sans toucher la zone affinée, l'occasion est
   perdue ; clôture au-delà de la zone de fond = zone morte). Pas de filtre FVG.
4. **Stop** : derrière la zone affinée + marge **0,2** ou **0,5** × ATR de la petite unité.
5. **Sorties, par tiers** :
   - **TP1** = 2 R (1/3 de la position) ;
   - **TP2** = le plus proche sommet (creux pour une vente) confirmé en H1 (fractal 2) au-delà de TP1 et en deçà de TP3
     — le niveau dont la cassure ferait un CHoCH ; sans sommet, milieu entre TP1 et TP3 (1/3) ;
   - **TP3** = bord de la plus proche zone opposée de FOND (même unité de fond) valide à l'entrée (1/3) ;
   - trade ignoré s'il n'y a pas de TP3 au-delà de 2 R ;
   - variante **point mort** : après TP1, le stop des 2 tiers restants passe au prix d'entrée (oui / non) ;
   - sortie de ce qui reste après 30 jours.
6. **Variantes** : fond {H4, journalier} × petite unité {M15, M5} × marge {0,2 ; 0,5} × point mort {oui, non} ×
   4 marchés = **64**. Total des variantes sur la période cachée : 366 + 64 = 430 -> **seuil = racine(2 ln 430) = 3,48**.
7. **Protocole** : choix 2015-2021, vérification 2022-2023 (retenu si force ≥ 2 et gain > 0 sur 2015-2021, force > 0
   et gain > 0 sur 2022-2023), période cachée 2024-2026 une seule fois (verrou vie/smc/cachee_multi.json).
   Limite honnête : 4e série de tests sur la même période cachée ; le juge final reste le direct ou l'historique
   réel du chef de projet.

## Avenant 1 — les ~45 marchés (15/10/2026, figé AVANT de lancer, demande du chef de projet)
- Marchés : tous ceux de nos données de 15 minutes (Dukascopy, ~45 marchés FTMO ; or = fichier de 15 min), même
  période 2015-2021 / 2022-2023 / 2024-2026. Volume = volume de cotation de ces données.
- Petite unité : **M15 seulement** (pas de minutes pour ces marchés). Fond : H4 et journalier. Marges 0,2 / 0,5. Point
  mort oui / non -> **8 variantes**, jugées **tous marchés réunis** (une variante = la méthode sur tous les marchés).
- Bougie d'entrée : sans minutes, on ne sait pas ce qui s'est passé avant le remplissage ; elle est donc IGNORÉE pour
  le trade ET pour son jumeau (suivi à partir de la bougie suivante). Même règle des deux côtés : pas de biais.
- Frais : fiche FTMO de chaque marché ; élargissement de l'ouverture de New York : 1,07 (US100), 1,16 (US500), 1,1
  pour les autres indices, 1,0 ailleurs.
- Variantes totales : 430 + 8 = 438 -> **seuil = racine(2 ln 438) = 3,49**. Retenue : mêmes règles (force ≥ 2 et gain
  > 0 sur 2015-2021 ; force > 0 et gain > 0 sur 2022-2023) ; période cachée une seule fois
  (verrou vie/smc/cachee_multi45.json).

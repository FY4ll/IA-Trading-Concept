# Couche 1 — PERCEPTION par détecteurs codés à la main : plan FIGÉ (20/10/2026, écrit AVANT toute mesure)

Ordre du chef de projet (20/10) : détecteurs tirés de sa méthode manuelle, un par unité (D1, H4, H1, M15), deux juges,
deux mesures, période de test verrouillée. Rien ci-dessous ne sera changé après avoir vu un résultat du test ; le
commit git qui contient ce fichier et le code fait foi (verrou : `resultats/VERROU_TEST.json` écrit au 1er lancement
du test, qui refuse un 2e lancement).

## Données et périodes
- Or (XAUUSD), bougies de 15 min Kaggle (heure du serveur MetaTrader), volume de cotation (ticks) ; D1, H4, H1
  fabriquées à partir des 15 min (`core.donnees.echelle`) ; historique de chauffe depuis 2004.
- **Mise au point : 2010-01-01 -> 2017-12-31** : seulement vérifier que le code fait ce qui est écrit (nombre de zones,
  de signaux, exemples). Aucune règle ni aucun réglage n'est changé selon un gain.
- **Test verrouillé : 2018-01-01 -> 2026-10-13**, lancé UNE fois. Un trade appartient à la période de son entrée.
- Les réglages viennent des définitions déjà figées le 15/10 (`collapsar/docs/SMC_DEFINITIONS.md` §E,
  `CASCADE_ZONES.md` §1-4) et des réponses du chef de projet ; aucun n'est ajusté ici.

## Le détecteur (le même pour chaque unité u ∈ {D1, H4, H1, M15}) — rien n'est appris
1. **Zone** (traduction exacte de son indicateur) : à la clôture de la bougie i, DEMANDE si la bougie j = i-1 est rouge,
   bas(j) > haut(j-2) et clôture(i) > max(haut(i-4), haut(i-5)) ; zone = [bas(j), haut(j)], milieu = moyenne. OFFRE
   symétrique. Effacée à la 1re clôture d'une bougie u au-delà du milieu (bougie i comprise). ATR = moyenne des 14
   dernières vraies étendues, à la bougie i.
2. **Confirmée par le profil de volume** : les 200 dernières bougies u jusqu'à i ; tranches de prix de 0,25 × ATR ;
   volume de chaque bougie réparti également sur les tranches qu'elle couvre ; zone gardée si elle touche une tranche du
   **top 20 %**. Confiance de l'avis = (rang de la plus forte tranche touchée - 0,80) / 0,20, entre 0 et 1.
3. **1er contact, jamais d'entrée** : 1re bougie u après i qui entre dans la zone (demande : bas ≤ haut de zone). Le
   contact doit RÉAGIR : une clôture u à au moins 0,5 × ATR au-delà du bord proche (demande : clôture ≥ haut + 0,5 ATR),
   avant l'effacement. Sinon, pas de signal.
4. **2e contact = entrée** : à la clôture de la bougie de réaction, ordre limite au **milieu** de la zone ; exécuté dès
   que le prix y revient (bougies de 15 min ; prix d'ouverture s'il ouvre déjà au-delà) ; valable 200 bougies u.
5. **Filtre FVG** : pas de signal si, au moment de poser l'ordre, il reste un FVG non comblé (de l'unité u, haussier ou
   baissier, taille ≥ 0,1 ATR) entièrement DERRIÈRE la zone (sous une demande, au-dessus d'une offre) à moins de
   1 × ATR de son bord. Le FVG qui fait partie du motif de la zone elle-même (entre j-2 et j, collé sous la zone) est
   exclu : sinon le filtre supprimerait toutes ses zones. FVG haussier en k : bas(k) > haut(k-2), comblé quand un bas
   ultérieur ≤ haut(k-2) ; baissier symétrique.
6. **Objectif** = bord proche de la plus proche zone OPPOSÉE (même unité, son indicateur, vivante au moment de poser
   l'ordre), au-delà de l'entrée. Pas de zone opposée = pas de signal.
7. **Stop** = bord opposé de la zone ± 0,2 × ATR. 1 R = distance entrée réelle -> stop (au moins la moitié de la
   distance prévue, pour le cas rare où le prix ouvre au-delà du stop à l'exécution).
8. **Avis émis** : sens (+1 achat / -1 vente), confiance (0-1), zone (haut, bas), entrée, stop, objectif, heure.
   Un trade par zone ; plusieurs zones peuvent donner des trades qui se chevauchent.

## Deux mesures (sur chaque trade exécuté)
- **(a) Le sens seul** : sortie fixe, la même pour tous : clôture 20 bougies u après l'entrée, sans stop ni objectif.
  Résultat en ATR (de la zone), après frais.
- **(b) Le signal + sa gestion** : stop ci-dessus ; à **+2 R, 80 % fermés** (sa pratique du 16/10) et stop remonté à
  l'entrée ; le reste va à l'objectif (zone opposée). Objectif à moins de 2 R : tout sort à l'objectif. Au plus 30 jours.
  Résultat en R après frais. Dans une même bougie de 15 min : le stop d'abord (prudence) ; la bougie d'entrée ne compte
  que pour le stop.
- Frais : écart FTMO de l'or ramené au prix de l'époque + commission (`core.ftmo.frais`), un aller-retour par trade.

## Avenant 1 — CORRECTIF DE MESURE (20/10/2026 03h25, après le 1er lancement du test)
En lisant le 1er lancement, un biais de MESURE a été trouvé (pas une règle du détecteur) : dans la bougie de 15 min où
l'ordre s'exécute, le stop était contrôlé sur toute la bougie ; or son plus haut / plus bas peut dater d'AVANT l'entrée
(un achat limite est exécuté quand le prix DESCEND jusqu'à l'entrée : le plus haut de la bougie est antérieur). Cela
« stoppait » à tort le jumeau inversé, surtout en M15 (stop ~1 $). Correctif : exécution et suivi sur les bougies
d'UNE MINUTE (`core.donnees.charger_minutes_or`), la minute d'entrée ne compte pour PERSONNE (ni signal ni juges).
Aucune règle de zone, de contact, de filtre, d'objectif ni de gestion ne change. Second et dernier lancement :
verrou `resultats/VERROU_TEST_2.json` ; le 1er lancement reste dans `resultats/test_v1_biaise.json`.

## Deux juges (mêmes trades, même entrée, même heure, mêmes distances de stop / 2 R / objectif, même sortie)
- **Jumeau pile ou face** : sens tiré au hasard. On calcule son espérance EXACTE : (trade + trade inversé) / 2.
- **Jumeau toujours acheteur** : le même trade en ACHAT (identique pour un signal d'achat ; inversé pour une vente) —
  neutralise la hausse de l'or.
- Avantage = moyenne (trade - juge) ; incertitude = écart type des moyennes mensuelles / racine du nombre de mois.
- **Bat un juge** si avantage > 2 × incertitude. **Avantage net** si bat les DEUX juges ET gain moyen > 0 après frais.
  16 comparaisons (4 unités × 2 mesures × 2 juges) : seuil prudent pour « prouvé » = racine(2 ln 16) = 2,35 ×
  l'incertitude, donné à côté.

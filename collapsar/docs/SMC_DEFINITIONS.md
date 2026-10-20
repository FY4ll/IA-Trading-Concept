# Laboratoire SMC — définitions FIGÉES (15/10/2026, écrites AVANT tout test)

Toutes les définitions sont **sans futur** : une information n'est utilisée qu'à partir de la clôture de la bougie
qui la confirme. Rien ici ne sera modifié après le début des tests (empreinte SHA-256 dans
`vie/smc/empreinte_definitions.txt`).

## A. Données et bougies
- Marchés : XAUUSD (fichier minute Kaggle, heure serveur − 7 h), NAS100 et US500 (HistData NSXUSD / SPXUSD), EURUSD
  (HistData). Heures de New York vérifiées (accord 95-99 % avec Dukascopy, été comme hiver).
- Unités de temps : M5, M15, H1, construites à partir des minutes, alignées sur l'horloge de New York.
- ATR = moyenne des 14 dernières « vraies étendues » (bougie comprise), connue à la clôture.
- **Volume** : HistData n'a pas de volume. On utilise le **volume de cotation (ticks)** : Dukascopy (bougies de 15 min
  de nos données, réparti à parts égales sur les 3 bougies de 5 min ; additionné pour H1) pour NAS100, US500 et
  EURUSD ; le volume du fichier minute pour l'or. Ce n'est **pas** le vrai volume échangé (les CFD et les devises
  n'ont pas de volume central).

## B. Concepts
1. **Sommet / creux** : fractal de N = 2 bougies (plus haut strictement au-dessus des 2 bougies avant et des 2 après) ;
   connu seulement à la clôture de la 2e bougie après.
2. **BOS / CHoCH** : clôture au-delà du dernier sommet (ou creux) confirmé. Si la structure précédente (sens de la
   dernière cassure) était dans le même sens -> **BOS** ; sinon (ou aucune) -> **CHoCH**.
3. **Order block (OB)** : haussier = dernière bougie baissière (clôture < ouverture) avant un départ où le plus haut des
   3 bougies suivantes dépasse sa clôture d'au moins **k = 2 × ATR** ; zone = [plus bas, plus haut] de cette bougie ;
   confirmé à la clôture de la bougie qui réalise le départ. Symétrique en baissier.
4. **FVG** : haussier à la bougie i si plus bas(i) > plus haut(i−2) ; zone = [plus haut(i−2), plus bas(i)] ; taille
   minimale 0,1 × ATR ; confirmé à la clôture de i. **Comblé** quand le prix traverse toute la zone.
   **Inverse FVG** : FVG haussier clôturé ensuite sous son bas -> zone baissière (et symétrique).
5. **Breaker block** : OB haussier invalidé par une clôture sous son bas -> zone baissière (vente au retour du prix
   dans la zone) ; symétrique.
6. **Balayage de liquidité** : mèche au-delà du plus haut (ou plus bas) de la séance de la veille (jour de New York)
   ou de **sommets égaux** (deux sommets confirmés à moins de 0,1 × ATR), et clôture revenue en deçà -> signal dans
   le sens du retour.
7. **Killzones** (filtres seulement, heure de New York) : Londres 2h-5h, New York 7h-10h.
   **Premium / discount** (filtre seulement) : moitié haute / basse du dernier couple sommet-creux confirmés ; achats
   seulement en discount, ventes seulement en premium.

## C. Règles de trade communes (concepts)
- **Zones** (OB, FVG, inverse FVG, breaker) : ordre limite au bord proche de la zone au **1er contact** après la
  confirmation ; stop au bord opposé ± **0,2 × ATR** ; objectif **2 R** ; sortie au plus tard **48 bougies** après
  l'entrée ; zone abandonnée si une clôture traverse le bord opposé avant le contact, ou après 500 bougies.
- **Signaux** (balayage, BOS, CHoCH) : entrée à l'ouverture de la bougie suivante dans le sens du signal ; stop au-delà
  de l'extrême de la bougie du signal ± 0,2 × ATR ; objectif 2 R ; sortie au plus tard 48 bougies.
- Dans une même bougie : entrée + stop -> perte ; stop + objectif -> perte (prudence).
- **Frais** (leçon de l'ORB) : fiche FTMO aller-retour (0,012 % indices et or, 0,006 % EURUSD) × élargissement à
  l'ouverture de New York (1re heure : NAS100 1,07, US500 1,16) ; + glissement d'une demi-fiche sur chaque stop
  touché et sur chaque entrée au marché ; ordre limite : sans glissement. Affichés : coût moyen en R et stop moyen en %
  du prix.

## D. Trois mesures par concept
1. **Réaction** : après le 1er contact (zone) ou le signal, le prix avance d'au moins 1 × ATR dans le sens attendu
   avant de clôturer au-delà du bord opposé (zone) ou de reculer de 1 × ATR (signal), dans les 48 bougies.
   Comparée à des **zones au hasard** : même marché, même période, même taille, même distance au prix et même côté, à
   un moment tiré au hasard (signaux : moments au hasard, même sens).
2. **Trade** : gain moyen en R après frais, part de gagnants, coût des frais en R, stop moyen en % du prix.
3. **Juge à jumeau** : même entrée, même distance de stop et d'objectif, même sortie, sens tiré à pile ou face ;
   écart = (R − R inverse) / 2 ; force = moyenne / écart type × racine(n).

## E. Stratégie personnelle (priorité 1)
- **Zone** d'offre / demande : base de 1 à 3 bougies (chacune d'étendue ≤ 0,5 × ATR) suivie d'un départ ≥ **k = 2 × ATR**
  (plus haut des 3 bougies suivantes − haut de la base, pour une demande) ; zone = [plus bas, plus haut] de la base.
- **Volume profile** : les **X = 200** dernières bougies avant la confirmation ; tranches de prix de 0,25 × ATR ; volume
  de chaque bougie réparti également sur les tranches qu'elle couvre ; zone retenue si elle touche une tranche du
  **top 20 %**.
- **Contact** : le prix entre dans la zone puis en ressort d'au moins **0,5 × ATR** dans le sens du rebond. Entrée par
  ordre limite au bord proche lors de la **1re, 2e ou 3e entrée** dans la zone (après 0, 1 ou 2 contacts réussis).
  Zone abandonnée à la première clôture au-delà du bord opposé.
- **Filtre FVG** : pas de trade s'il existe un FVG non comblé dont le bord le plus proche est à moins de **Y = 1 × ATR**
  derrière la zone (sous une demande, au-dessus d'une offre). Comparé avec et sans.
- **Stop** : derrière la zone + marge **0,2 × ATR** ou **0,5 × ATR** (deux variantes, plus les frais).
- **Objectif** : bord de la plus proche zone opposée (offre au-dessus d'un achat), valide au moment de l'entrée ; trade
  ignoré si gain / risque < **1,5** ou s'il n'y en a pas ; sortie au plus tard 500 bougies.

## F. Combinaisons (10 au maximum, listées avant les tests)
1. OB + FVG dans le départ + killzone New York
2. Balayage + FVG (entrée sur le 1er FVG dans le sens du retour, formé dans les 5 bougies)
3. OB + premium / discount
4. Breaker + killzone (Londres ou New York)
5. CHoCH + entrée sur FVG (1er FVG dans le sens du CHoCH, dans les 5 bougies)
6. Balayage + CHoCH (CHoCH dans le sens du retour, dans les 10 bougies)
7. FVG + killzone New York
8. OB dont le départ provoque un BOS
9. Zone personnelle (1er contact, sans filtre FVG, marge 0,2) + killzone New York
10. Inverse FVG + premium / discount

## G. Protocole et seuil de preuve
- Choix et apprentissage 2015-2021 ; vérification 2022-2023 ; **période cachée 2024-2026 évaluée une seule fois**, pour
  les seuls candidats retenus (verrou `vie/smc/cachee.json`).
- **Candidat retenu** : force ≥ 2 et gain > 0 R après frais sur 2015-2021, ET force > 0 et gain > 0 sur 2022-2023.
- **Variantes comptées** (période cachée commune) : ORB 18 + concepts 7 × 3 unités × 4 marchés = 84 + combinaisons
  10 × 12 = 120 + stratégie personnelle 3 contacts × 2 filtres × 2 marges × 12 = 144 -> **366**.
  **Seuil global = max(3 ; racine(2 ln 366)) = 3,44.**
- **Verdict** : PROUVÉ = force ≥ 3,44 et gain > 0 sur la période cachée ; FAIBLE = retenu mais non prouvé, ou
  réaction nettement supérieure au hasard sans gain ; INUTILE = sinon.

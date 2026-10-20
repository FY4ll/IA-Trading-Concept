# Plan figé — 3 méthodes courtes sur l'or (recherche `docs/SCALPING_QUI_MARCHE.md`, section 5)

**Figé le 20/10/2026 à 01h20 (heure de Paris), AVANT tout calcul de résultat d'une de ces règles.**
Avant ce gel, seules des vérifications de DONNÉES ont été faites (aucun gain, aucun trade calculé) : heures du fichier
(la plus grosse minute des jours d'emploi américain tombe à 8h30 New York chaque année 2014-2025, à la minute près ;
une fois par an le calendrier MT5 est décalé d'1 h, lui, pas les prix), minutes par jour (médiane 1 370 sur 1 380,
2 jours sur 2 761 sous 60 %), écarts Tradeco par heure (bougies de 5 min, 07/2025 -> 10/2026), règles de B relues
chez leur auteur (mql5.com/en/blogs/post/777540 : le tampon n'y est PAS chiffré, « petit »).
Programme : `collapsar/regarder/pistes/scalping_or.py` ; tests `collapsar/tests/test_scalping_or.py`.

## Données et heures
- `data/kaggle_gold/XAU_1m_data.csv`, heure du serveur = New York + 7 h (toute la période est après 06/2011).
  **Rien après le 30/09/2025** (le fichier a été prolongé jusqu'au 10/2026 : ces minutes ne sont jamais lues).
- Journée de l'or = de 18h New York (veille) à 17h New York. Jour gardé si >= 60 % de ses minutes.
- Chaque fenêtre est convertie dans SON fuseau (Londres, New York, Prague pour FTMO) jour par jour.
- A14 = moyenne des écarts haut-bas des 14 journées gardées précédentes.
- Prix du fichier = prix du milieu. Achat : on paie un demi-écart à l'entrée et à la sortie (écart complet par
  aller-retour). Commission métaux FTMO 0,0014 % du prix par aller-retour (`mains/frais_ftmo.py`, prudence).

## Frais (deux versions obligatoires + une pour information)
1. **Modèle par heure (version principale)** : écart FTMO relevé (`mains/frais_ftmo.py`, constant en dollars :
   ~0,46 $/once, relevé à 20h34 New York) x facteur de l'heure / facteur de 20h, facteurs = écart médian Tradeco par
   heure de New York / écart médian (bas plafonné à 1) : x2 de 16h à 19h New York (pause et réouverture, lundi compris),
   x1,08 de 19h à 01h et de 14h à 16h New York, x1 le reste (tableau `FACTEUR_HEURE` du programme). Annonces majeures : x5 de 2 min avant à 5 min après, x2 de 5 à 15 min après.
2. **Écart fixe 0,40 $/once** à toute heure (aucun facteur), même commission, même glissement.
3. (information seulement, ne compte pas) écart en part du prix (moins cher les années où l'or valait 1 100-2 000 $).
- **Glissement (version principale = règle de la recherche)** : ordre stop d'entrée servi au PIRE de la minute qui
  touche le niveau (plus haut pour un achat) + 0,10 $ (0,30 $ si annonce majeure à 15 min près) ; stop de protection
  pareil (plus bas de la minute - 0,10 $ pour un achat). Information : glissement « doux » (au niveau, ou à
  l'ouverture si trou, + 0,10 $). Ordres au marché : sans glissement ; objectifs (ordres limites) : servis au prix
  exact seulement si le prix dépasse l'objectif d'un demi-écart.
- Stop et objectif touchés dans la même minute = stop. Minute d'entrée : si le stop est touché aussi = stop.
  Stop à l'entrée / suiveur : mis à jour avec le plus haut (achat) d'une minute, actifs à partir de la minute suivante.
- Annonce majeure = calendrier MT5 du projet (`donnees/calendrier.py`, `_lire_mt5`), dollar américain, importance
  « forte » (3) + déclaration, projections, procès-verbal et conférence de presse de la banque centrale américaine.

## Les 5 versions jugées (4 essais de la recherche ; « sens imposé » compté en plus par prudence)
**A1 — cassure du plus haut / plus bas de la veille.** Niveaux H, B = journée de l'or d'hier. Achat stop à H + t, vente
stop à B - t, t = 0,05 x A14. Actifs de 08h00 Londres à 12h00 New York. Un trade par sens et par jour (l'un n'annule pas
l'autre ; les deux peuvent être ouverts ensemble). Pas d'entrée d'un côté si depuis 18h New York le prix a déjà
touché le niveau d'ordre (H + t ou B - t) avant 08h00 Londres. Pas d'entrée : annonce majeure à 15 min près (le côté
est alors fermé pour la journée), écart du moment > 2 x son habitude, vendredi après 14h New York, 2 h avant le week-end.
Stop = 0,35 x A14 de l'autre côté du niveau d'ordre (1 R = cette distance ; taille calculée dessus). Stop à
l'entrée quand le gain atteint 1 R, puis suiveur à 0,5 x A14 du meilleur prix (jamais sous l'entrée). Tout fermé à
16h45 New York (à l'ouverture de la première minute >= 16h45 ; jour férié : première minute disponible).
**A2 — même chose avec les niveaux de la séance asiatique** : H, B = plus haut / plus bas de 18h New York à 08h00 Londres
du jour même (la règle « déjà dépassé » devient sans objet).
**A3 — A1 avec le sens imposé par l'heure** : toute la fenêtre est en heures d'Europe / New York, où l'or baisse
d'après l'histoire (section 2.9) : seulement les VENTES de A1.
Choix de A (décidé d'avance) : la version de A1 / A2 de plus grande force contre son jumeau sur 2015-2020 (frais
modèle) est LA méthode A pour la vérification et le contrôle ; les autres restent affichées.
**B — boîte asiatique (règles du testeur, sans les toucher).** Heure du serveur du testeur = New York + 7 h (la
plupart des serveurs MT5, GMT+2/+3 ; c'est aussi celle de notre fichier) : boîte = 03h00-08h00 serveur (20h-01h New
York, 01h-06h Londres) ; à 08h00 serveur, achat stop au-dessus et vente stop en dessous, tampon = 0,02 % du prix
(non chiffré par l'auteur : choisi ici avant tout test, jamais réglé) ; le premier exécuté annule l'autre (les deux dans
la même minute : le plus proche de l'ouverture) ; 1 trade/jour ; boîte ignorée si < 0,30 % ou > 1,60 % du prix ; stop
de l'autre côté de la boîte, distance plafonnée à 0,6 % du prix ; objectif 2,5 R ; stop à l'entrée à 1,5 R ; tout fermé
à 21h00 serveur (14h New York). Règle FTMO ajoutée : pas d'exécution à 2 min d'une annonce majeure (le jour est alors
sans trade).
**C — fausse cassure de la veille.** Mêmes H, B, t que A1. Bougies de 15 min alignées sur l'heure de New York, dans la
fenêtre 08h00 Londres -> 12h00 New York. Vente : une bougie a dépassé H + t (depuis 08h00 Londres), puis une bougie
(la même ou une suivante) CLÔTURE sous H -> vente au marché à l'ouverture de la bougie suivante (avant 12h00 New York).
Stop = plus haut atteint depuis la première bougie de dépassement + t. Objectif = milieu de la veille (H + B) / 2,
seulement s'il est à au moins 3 x les frais aller-retour du moment (écart + commission + 0,10 $), sinon pas de trade.
Achat symétrique sous B. Stop à l'entrée à 1 R ; fermeture 16h45 New York. Un signal refusé (annonce, écart, objectif
trop proche, prix déjà au-delà du stop) ferme ce côté pour la journée.

## Juge
- **Jumeau au hasard** : même minute, même prix de référence, même glissement (contre lui), mêmes distances de stop
  et d'objectif, mêmes règles de sortie, sens opposé ; son espérance = moyenne des deux -> écart d = (R - R_inverse)/2 ;
  force = moyenne(d) / écart type(d) x racine(n).
- **Seuil de preuve** : max(3, racine(2 ln N)), N = 1 300 cases déjà jugées dans le projet + 5 versions = 1 305
  -> **3,79**.
- Achats et ventes séparés ; or retourné (prix K / prix, mêmes frais en part du prix) ; année par année.
- Compte FTMO 100 000 $ par méthode, risque 0,5 % et 1 % du capital de départ par trade (perte au stop), perte du
  jour comptée sur le pire flottant (somme des pires points des trades du jour, prudent), journée de Prague, murs
  -5 %/jour et -10 % au total = mort, +10 % (solde du soir) = réussi ; un challenge démarre chaque 1er jour de mois.

## Périodes
Choix des variantes : 2015-2020. Vérification : 2021-2022. **Contrôle : 01/2023 -> 09/2025, ouvert UNE fois**
(verrou `controle.json`). (La recherche proposait 2021-2023 / 2024-2025 ; la découpe du chef de mission est suivie.)

## Verdict décidé d'avance (frais modèle + glissement principal)
- Par période : 🟢 prouvé = R moyen net > 0 avec les DEUX frais (modèle et 0,40 $) ET force >= 3,79 ;
  🟡 prometteur = R moyen net > 0 (modèle) et force >= 2, ou force >= 3,79 avec R net <= 0 (information sans argent) ;
  ⚪ bruit = le reste.
- Par méthode : 🟢 si 🟢 en vérification ET au contrôle et R net > 0 sur 2015-2020 ; 🟡 si R net > 0 au contrôle et
  force >= 2 au contrôle ou sur toute la période ; ⚪ sinon.
- Aucun réglage ne sera changé après avoir vu un résultat ; toute autre version = un nouvel essai déclaré et compté.

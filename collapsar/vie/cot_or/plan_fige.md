# Plan figé — positionnement des fonds sur l'or (COT CFTC désagrégé, COMEX)

**Figé le 20/10/2026 à 00h57, AVANT tout calcul de résultat.** Rien ne sera changé après coup ; toute entorse sera
écrite dans le rapport.

## Question
Le positionnement des « fonds gérés » (M_Money) sur l'or COMEX annonce-t-il le SENS de l'or 1, 2 ou 4 semaines après
la publication ? Et cette info est-elle indépendante de la tendance de fond (60 jours) ?

## Données
- COT : `data/maitres/cftc_cot/cot_desagrege_or_comex.csv` (positions du mardi). Coupé à la date de positions
  2025-09-23 (dernière publiée avant fin 09/2025). Rien après n'est lu.
- Or : `data/kaggle_gold/XAU_1d_data.csv` (bougies journalières, heure du serveur = New York + 7 h), coupé au
  2025-09-30 inclus. Ouverture du jour = premier prix du jour serveur.

## Règle anti-triche (date où l'info devient connue)
- Publication normale : vendredi de la semaine des positions, 15h30 New York (= 22h30 serveur).
- Semaine avec un jour férié fédéral américain (du lundi de la semaine des positions au vendredi de publication) :
  publication supposée le LUNDI suivant 15h30 New York (mardi si ce lundi est férié). Prudent.
- Paralysies de l'État fédéral (rapports publiés en retard, rattrapage étalé) : positions du 2013-10-01 au 2013-11-19
  et du 2018-12-24 au 2019-03-05 EXCLUES (pas de signal ces semaines-là).
- Entrée = ouverture du premier jour de cotation STRICTEMENT après la publication (normalement le lundi).
- Sortie = ouverture du premier jour de cotation >= entrée + 7 x h jours calendaires, h = 1, 2, 4 semaines.
- Le signal d'une semaine n'utilise que les lignes COT <= cette semaine et les prix clôturés <= le mardi des positions
  (sauf la tendance 60 j : clôtures jusqu'à la veille de l'entrée, connues avant l'entrée).
- Test « sans futur » : (1) vérification automatique entrée > publication pour chaque ligne ; (2) 40 semaines tirées
  au hasard : signal recalculé avec un fichier COT coupé à cette semaine et des prix coupés avant l'entrée -> doit être
  identique ; (3) contrôle du piège : même signal contre le mouvement mardi -> entrée (fenêtre AVANT publication),
  pour montrer ce que la triche donnerait.

## Signaux (liste FERMÉE : 9)
Net = M_Money long - short ; OI = intérêt ouvert ; PL = long / (long + short) des fonds.
1. `V1` : (Net - Net 1 semaine avant) / OI.
2. `V4` : (Net - Net 4 semaines avant) / OI.
3. `P52` : rang en centile de Net/OI parmi les 52 dernières semaines (semaine courante comprise).
4. `P156` : idem sur 156 semaines.
5. `PL` : part longue des fonds (niveau).
6. `PS` : pression spéculative (Fan et al. 2018) = moyenne sur 52 semaines de PL.
7. `DIV` : divergence fonds / prix = z(V4) - z(r4), z calculés sur les 156 semaines passées, r4 = rendement de l'or
   du mardi 4 semaines avant au mardi des positions (clôtures).
8. `X52` : extrêmes : +1 si P52 <= 10 %, -1 si P52 >= 90 %, sinon 0.
9. `X156` : idem avec P156.
Kang et al. (« la part du mouvement due aux fonds se retourne ») = V1 lu dans le sens négatif : couvert par V1.

## Horizons : 1, 2, 4 semaines (rendement de l'or, ouverture d'entrée -> ouverture de sortie).

## Périodes (par date d'entrée ; la sortie doit aussi être <= 2025-09-30)
- Choix : 2006-06 -> 2019-12-31. Le SENS de chaque signal (suivre / contrer) est fixé ici (signe de la corrélation),
  ainsi que les seuils des tranches (quintiles) et la médiane qui sert au trade.
- Vérification : 2020-01-01 -> 2022-12-31.
- Contrôle : 2023-01-01 -> 2025-09-30, calculé UNE seule fois pour les 27 cases à la fois, verrou
  `controle.json` (s'il existe, on ne recalcule pas).

## Mesures (par case signal x horizon et par période)
1. Corrélation de rang (signal, rendement futur) ; force t avec correction des chevauchements (Newey-West, h retards).
2. Précision du sens par tranche (quintiles figés sur la période de choix ; X52/X156 : -1 / 0 / +1) contre le taux de
   base (% de semaines où l'or monte sur la période).
3. Contre la tendance seule : régression rendement = a + b . z(signal) + c . z(tendance 60 j) (z figés sur le choix),
   force t de b avec et sans la tendance -> l'info est-elle indépendante ? Repère : la tendance seule (même trade).
4. Contre des dates au hasard : 2 000 décalages circulaires du signal (décalage >= 52 semaines) -> part des décalages
   dont |corrélation| >= la vraie (valeur p).
5. Trade simple : entrée l'ouverture après publication, sens = sens figé x signe(signal - médiane du choix)
   (X52/X156 : seulement quand l'extrême est atteint), sortie à l'horizon ; frais FTMO de l'or
   (`mains/frais_ftmo.frais`, écart ramené au prix du jour + commission) + frais de nuit de l'époque
   (`mains/nuit.taux_nuit`, mercredi x 3), compte Swing (nuits et week-ends permis). Positions qui se chevauchent :
   h sous-comptes de 1/h chacun. Taille : agitation visée 10 %/an (taille = 10 % / agitation annualisée des 20 jours
   avant l'entrée, plafond 5 fois le compte). Gain %/mois après frais, pire baisse, force contre le JUMEAU (mêmes
   moments, même taille, sens tiré au hasard : force = moyenne (R - R inverse)/2 / écart type x racine(n), Newey-West),
   challenges FTMO simulés (`regarder/bande_bruit.challenge`, départ tous les 10 jours, pire point du jour) contre
   20 jumeaux.

## Seuil de preuve
Cases nouvelles : 9 signaux x 3 horizons x 2 mesures (corrélation, trade) = 54 ; avec ~1 300 cases déjà jugées dans
le projet, N = 1 354 -> seuil = max(3, racine(2 ln N)) = **3,80**.

## Étiquettes (figées)
- 🟢 prouvé : |force| >= 3,80 sur le choix (corrélation ou trade), même sens en vérification ET en contrôle avec
  force >= 1 dans chacune, trade après frais positif dans les deux, et force de b avec la tendance >= 2 sur le choix.
- 🟡 prometteur : |force| >= 2 sur le choix, et même sens en vérification ET en contrôle (trade après frais >= 0
  dans au moins l'une des deux).
- ⚪ bruit : le reste.
Donner à MAGNETAR seulement si 🟢, ou 🟡 indépendant de la tendance (force de b avec tendance >= 2 sur le choix).

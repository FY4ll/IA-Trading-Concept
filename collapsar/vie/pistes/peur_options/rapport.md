# Piste « peur_options » : la peur lue dans les marchés d'options pour trader les indices américains chez FTMO (16/10/2026)

Code : `collapsar/regarder/pistes/peur_options.py` (règles et liste fermée de 9 variantes écrites dans l'en-tête AVANT
tout résultat). Données : `data/cboe/` (voir `LISEZMOI.md`). Chiffres : `choix.json`, `verification.json`,
`cachee.json` (verrou : la période cachée a été ouverte UNE fois, pour la variante retenue), `lien_compte_combine.json`,
journal `journal.txt`.

## Ce qui a été fait
- **Données CBOE publiques et gratuites** : VIX, VIX9D, VIX3M, VIX6M, VVIX, SKEW (2011 -> 15/10/2026). Les ratios puts /
  calls ne sont publiés en fichier que jusqu'au 04/10/2019 : impossibles à vérifier après -> écartés.
- **Heure** : le VIX de clôture est arrêté à 16h15 New York ; une valeur du jour d n'est utilisée qu'à l'ouverture au
  comptant du jour de Bourse suivant (9h30 New York = 16h30 serveur), plus de 17 h après.
- **Marchés** : US500, US100, US30 (prix Dukascopy 15 min, même position sur les 3, taille sur l'agitation de 20 jours de
  chaque indice). Deux niveaux publiés : 10 % et 20 % d'agitation par an en position pleine.
- **Frais FTMO fidèles** (`frais_ftmo.frais` : écart relevé ramené au prix de l'époque, glissement x 1,25 compris) et
  **nuits payées** (`nuit.taux_nuit` : taux du dollar + 3,75 %/an, 3 nuits le week-end).
- **Juge** : choix sur 09/2011 -> 2019, vérification 2020-2023, période cachée 2024 -> 10/2026 ; chaque phase calculée
  sur des données coupées à sa fin. Deux témoins : le **jumeau** (sens à pile ou face) et **« acheter et garder » à la
  même exposition moyenne** (le vrai juge pour un signal acheteur : il doit battre la hausse générale). Seuil de preuve 3.

## Les 9 variantes sur la période de CHOIX (2011-2019, niveau 10 %)

| variante | trades | temps en position | gain %/mois après frais | « garder » même exposition | baisse max | pire jour | force contre jumeau | force contre « garder » |
|---|---|---|---|---|---|---|---|---|
| V1 courbe inversée (VIX > VIX3M) | 61 | 8 % | +0,07 | +0,04 | -5,2 % | -6,3 % | +0,4 | -0,2 |
| **V2 fin de l'inversion, achat 10 j** | 33 | 20 % | **+0,31** | +0,10 | -10,6 % | -2,7 % | +2,9 | **+1,4** |
| V3 inversion courte (VIX9D > VIX) | 79 | 52 % | +0,50 | +0,25 | -31,4 % | -7,0 % | +1,8 | +0,1 |
| V4 VIX tendu (Connors) | 43 | 5 % | -0,00 | +0,03 | -14,1 % | -5,5 % | +0,1 | -0,2 |
| V5 VIX haut + indice en baisse | 63 | 28 % | +0,39 | +0,13 | -13,5 % | -6,1 % | +1,0 | +0,1 |
| V6 prime de peur (VIX contre agitation réalisée) | 43 | 56 % | +0,20 | +0,16 | -17,7 % | -6,3 % | +1,4 | +0,8 |
| V7 VIX au plus haut de l'année | 21 | 23 % | +0,35 | +0,11 | -20,2 % | -6,2 % | +2,2 | +1,1 |
| V8 VVIX extrême | 50 | 23 % | +0,43 | +0,11 | -15,0 % | -7,7 % | +2,9 | +1,3 |
| V9 SKEW extrême -> vente | 36 | 38 % | **-0,67** | +0,18 | -63,6 % | -12,5 % | -1,9 | -2,1 |

Règle figée : la plus forte contre « garder » parmi les positives -> **V2 « fin de l'inversion »** (achat 10 jours à
l'ouverture qui suit la première clôture où le VIX repasse sous le VIX3M). Contrôle « un jour de retard » : +0,28
%/mois, force contre « garder » +1,6 : pas de trace d'information du futur.

## La variante retenue V2 sur les trois périodes

| période | niveau | trades | gain %/mois après frais (avant frais) | « garder » | baisse max | pire jour | force jumeau / « garder » | challenges réussis / morts / inactifs (jumeaux) | sans la règle d'inactivité : réussis / morts (jumeaux) |
|---|---|---|---|---|---|---|---|---|---|
| choix 2011-19 | 10 % | 33 | +0,31 (+0,36) | +0,10 | -10,6 % | -2,7 % | +2,9 / +1,4 | 0 / 0 / 99 % (0 / 0) | 46 / 1 % (13 / 26) |
| choix 2011-19 | 20 % | 33 | +0,61 (+0,72) | +0,19 | -21,2 % | -5,4 % | idem | 0 / 2 / 96 % (0 / 3) | 31 / 56 % (12 / 72) |
| vérif. 2020-23 | 10 % | 10 | +0,23 (+0,26) | +0,04 | -4,4 % | -2,3 % | +3,1 / +1,3 | 0 / 0 / 98 % (0 / 0) | 0 / 0 % (0 / 2) |
| vérif. 2020-23 | 20 % | 10 | +0,46 (+0,51) | +0,08 | -8,8 % | -4,5 % | idem | 0 / 0 / 98 % (0 / 0) | 12 / 0 % (3 / 25) |
| **cachée 2024-26** | 10 % | 10 | **+0,33** (+0,41) | +0,07 | -7,4 % | -3,1 % | +2,2 / +0,8 | 0 / 0 / 97 % (0 / 0) | 0 / 0 % (0 / 4) |
| **cachée 2024-26** | 20 % | 10 | **+0,67** (+0,82) | +0,14 | -14,9 % | -6,2 % | idem | 0 / 10 / 88 % (0 / 10) | 0 / 57 % (5 / 62) |

Lien jour par jour avec le compte « cassure + zones » (niveau 9 %) : **-0,09 (2017-19), -0,02 (2020-23), -0,00
(2024-26), -0,03 au total** : brique indépendante.

## Défauts cherchés
- Dates du VIX : ce sont bien celles de la séance (24/08/2015 = 40,74 ; 05/02/2018 = 37,32) ; les 5 pires jours de
  l'US500 coïncident tous avec un bond du VIX le même jour.
- **Jours fériés : le fichier du VIX a des lignes certains fériés américains depuis 2023** (04/07, Thanksgiving,
  obsèques Carter) : écartées par un calendrier NYSE recalculé.
- Bougie d'entrée à 16h30 serveur pour 86-99 % des jours (16h45 en 2012-2014 sur l'US500, données plus clairsemées).
- Un jour de retard ne détruit pas l'avantage (normal pour une position tenue 10 jours).

## Verdict honnête
1. **L'information des options existe, mais elle est petite.** La seule idée qui reste positive sur les trois périodes,
   après frais et nuits, c'est **acheter les indices quand la peur RETOMBE** (V2) : +0,2 à +0,3 %/mois au niveau 10 %
   en n'étant en position que 15-20 % du temps, 3 à 5 fois mieux que « garder » à la même exposition. Mais la force
   contre « garder » (1,4 / 1,3 / 0,8) n'atteint jamais le seuil de 3 : **non prouvé**, et seulement 3 à 4 trades par
   an (53 en 15 ans).
2. **Seule, elle ne passe aucun challenge FTMO** : 97-99 % des départs meurent par la règle « 30 jours sans trade » ;
   même sans cette règle, +0,3 %/mois est bien trop lent pour +10 %. À 20 %, une journée à -6 % en 2024-2026 tue 10 %
   des départs.
3. **Ce qui ne marche pas** : la courbe inversée elle-même (V1 : acheter PENDANT la panique ne bat pas « garder »), le
   « VIX tendu » de Connors (zéro), et **vendre quand le SKEW est haut (V9 : nettement perdant, -0,67 %/mois)** :
   le SKEW n'annonce pas les krachs.
4. **Usage possible** : brique d'appoint indépendante (lien -0,03) à ajouter au compte « cassure + zones », sur un autre
   marché (indices) et à d'autres moments. À part : V6 (prime de peur) et V8 (VVIX extrême) sont aussi positives en
   2020-2023 (information seulement, non retenues).

## Ce qui manquerait pour aller plus loin
1. Simuler le compte « cassure + zones + V2 » (même compte, mêmes murs) pour voir si V2 ajoute des challenges réussis :
   c'est sa seule vraie utilité. Les trois périodes sont maintenant vues : seul le direct à blanc jugerait.
2. Demander à FTMO si une position TENUE compte comme activité (règle des 30 jours) ; et relever les vrais frais de nuit
   des indices sur l'essai (V2 tient ~10 jours).
3. Ratios puts / calls après 2019 : il faudrait un relevé quotidien (non publié en fichier).

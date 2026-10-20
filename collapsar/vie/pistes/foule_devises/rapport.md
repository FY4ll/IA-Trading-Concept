# Piste « foule_devises » : la foule à contre-pied sur les marchés bon marché (16/10/2026)

Idée : refaire C1 de `crypto_flux` (la foule des comptes d'un seul côté -> jouer contre) sur devises, or, argent,
indices, pétrole, où les frais FTMO sont 5 à 15 fois plus bas que sur les cryptos.

## 1. Les historiques du positionnement des particuliers (détail : `research_notes/Foule devises/notes.md`)
| Source | Historique gratuit et légal ? | Pourquoi |
|---|---|---|
| Dukascopy (indice SWFX) | Non | Historique abandonné par Dukascopy (« returns null ») ; robots interdits sans accord écrit |
| IG (sentiment des clients) | Non | Valeur actuelle seulement, compte + clé nécessaires |
| Myfxbook (avis de la communauté) | Non | Valeur actuelle seulement, compte nécessaire ; reproduction interdite |
| FXCM (indice SSI) | Non | 1 mois d'exemple gratuit (01/2018) ; historique depuis 2009 payant |
| OANDA (livre des positions) | Pas sans compte | Photos passées lisibles avec un jeton OANDA : la meilleure piste d'historique |
| FXSSI, Saxo, Darwinex | Non | Payant ou pas publié |
| **CFTC, petits spéculateurs des contrats à terme** | **Oui, depuis 1986** | Données publiques de l'État américain, une photo par semaine |

**Verdict : aucune source gratuite et légale ne donne 3 ans d'historique du positionnement des clients particuliers
des courtiers.** La seule source longue est la CFTC. Elle compte les petits traders des contrats à terme, pas les
clients CFD des courtiers : c'est un cousin de l'information C1, pas la même. Je l'ai testée avec le juge habituel.

## 2. Test du cousin CFTC (code `collapsar/regarder/pistes/foule_devises.py`, règles écrites avant tout résultat)
- Donnée : part des petits acheteurs (positions non déclarables), photo du mardi. Je ne l'utilise que **7 jours
  après** (le mardi suivant à 00h00 serveur), alors qu'elle est publiée le vendredi ou le lundi. Les semaines de
  fermeture de l'État américain (2013, 2018-19, 2025) sont retirées : leurs photos ont été publiées très en retard.
  Fichier : `data/foule_devises/cot_petits.csv`.
- Décision chaque jour ouvré à 01h00 serveur, une position à la fois par marché, risque 0,5 % d'agitation par trade.
  Frais FTMO fidèles (`frais_ftmo.frais`) et nuits calendaires au taux de l'époque (`nuit.taux_nuit`).
- Marchés : 14 marchés avec un contrat CFTC. Groupe A (développement) = AUDUSD, GBPUSD, LIGHTCMDUSD, USA30IDXUSD,
  USATECHIDXUSD, USDCHF, XAGUSD. Groupe B (confirmation) = EURUSD, JPNIDXJPY, NZDUSD, USA500IDXUSD, USDCAD, USDJPY,
  XAUUSD.

### Développement (groupe A, 2010 -> 2023), les 6 variantes
| Variante | Trades | Gain %/mois après frais (sans frais) | Force (jour) | Baisse max* | Pire jour | Challenges réussis / morts (jumeaux) |
|---|---|---|---|---|---|---|
| V1 C1 à l'identique (90 j, sortie 24 h) | 7 624 | -1,97 (-0,21) | -0,8 (-0,8) | -345 % | -5,5 % | 6 / 93 % (2 / 95) |
| V2 fenêtre 30 j | 11 550 | -2,62 (+0,09) | +0,3 (+0,2) | -459 % | -6,8 % | 4 / 96 % (2 / 97) |
| V3 fenêtre 180 j | 5 872 | -1,44 (-0,06) | -0,3 (-0,3) | -251 % | -5,0 % | 4 / 90 % (1 / 94) |
| V4 sortie 3 jours | 3 771 | -0,86 (-0,19) | -1,2 (-1,1) | -157 % | -6,7 % | 1 / 89 % (3 / 90) |
| V5 sortie 5 jours | 2 249 | -0,49 (-0,04) | -0,4 (-0,3) | -103 % | -4,7 % | 0 / 78 % (1 / 86) |
| V6 seuil absolu > 70 % / < 30 % | 2 917 | -0,52 (+0,50) | +2,1 (+2,1) | -107 % | -6,0 % | 7 / 76 % (7 / 81) |

\* Somme des gains journaliers sans intérêts composés : au-delà de -10 %, le compte FTMO serait mort bien avant.

**Aucune variante ne passe** (il fallait un gain > 0 et une force >= 3). Comme prévu dans les règles, **le contrôle
2024-2026 et la confirmation sur le groupe B n'ont PAS été ouverts** (aucun verrou n'a été créé : ces années restent
neuves pour un futur test).

### Recherche du défaut (V6, la moins mauvaise)
- Même AVANT frais, l'avantage est presque nul : +0,035 % du prix par trade (+0,5 %/mois sans frais), alors que C1
  faisait +3,7 %/mois sans frais sur les cryptos.
- Photo utilisée 1 jour plus tôt (lundi) : force 2,5. Une semaine plus tard : 1,5. Sans la meilleure année : 2,0.
- Tout vient des ventes (force 2,2 ; achats 0,2). Par marché : franc suisse +24 %, livre +9 %, argent -113 %
  (l'argent coûte 0,12 % par trade chez FTMO et la foule y est presque toujours acheteuse > 70 %).

## Verdict honnête
- **La foule des petits traders des contrats à terme (CFTC) n'apporte rien** sur ces marchés : V1 (la règle C1
  telle quelle) perd même avant frais. Une photo par semaine, vieille de 7 à 13 jours au moment de trader, ne contient
  pas l'information « foule d'un seul côté maintenant » qui marchait sur les cryptos. Cela rejoint l'ancien constat de
  Run A (« positions COT : aucun avantage »).
- Le vrai test (clients particuliers des courtiers, toutes les heures) **reste à faire** : la donnée n'existe pas en
  historique gratuit. D'où le collecteur ci-dessous.

## 3. Collecteur en direct (lancé le 16/10/2026 à 04h53, heure de Paris)
`collapsar/donnees/foule_devises.py` (lecture seule, interfaces officielles seulement, aucun mot de passe affiché).
- Tourne en boucle toutes les heures (processus séparé ; arrêt : créer `data/foule_devises/direct/ARRET`).
  Fichiers `data/foule_devises/direct/<source>_<AAAA-MM>.csv`, journal `journal.txt`.
- **Sans compte (actif dès maintenant)** : gTrade (bourse sur chaîne publique, interface officielle sans clé) =
  comptes acheteurs / vendeurs et montants par marché, 20 lignes par heure ; CFTC retéléchargée chaque jour.
  Limite : la foule gTrade est **minuscule** (ex. 28 comptes sur l'or, 4 sur l'euro à 04h53) : utile surtout pour
  l'or, l'argent, le pétrole et les fonds indiciels.
- **Avec un compte (branchement prêt, rien à coder)** : Myfxbook (avis de la communauté), IG démo (sentiment des
  clients), OANDA (livre des positions). Accès à mettre en variables d'environnement ou dans
  `data/foule_devises/acces.json` (noms dans l'en-tête du fichier).
- Le processus de boucle ne redémarre pas seul après un redémarrage de Windows : une tâche planifiée
  (`... -m collapsar.donnees.foule_devises une_fois` toutes les heures) n'a pas été créée, elle demande l'accord du
  chef de projet.

## Ce qui manquerait pour aller plus loin
1. **Un jeton OANDA (compte démo gratuit, à ouvrir par le chef de projet)** : `python -m collapsar.donnees.foule_devises
   oanda_rattrapage 2017-01-01` relirait les photos passées du livre des positions (toutes les 20 min). Si OANDA les
   garde sur plusieurs années, c'est le **seul vrai test historique possible** de C1 sur les devises, gratuit et légal.
2. Sinon : acheter l'historique SSI de FXCM (depuis 2009, toutes les minutes, 32 marchés FTMO-compatibles), ou
   attendre 6 à 12 mois de collecte (Myfxbook / IG / gTrade) puis tester la règle C1 figée, sur données jamais vues.
3. La foule d'Ostium (chaîne publique, depuis 08/2024, `collapsar/maitres/foule.py`) existe déjà : moins de 3 ans,
   mais assez pour une seconde vérification plus tard.

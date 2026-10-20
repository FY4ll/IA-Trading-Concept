# Gold Reaper New V2 2 : sa logique décortiquée (20/10/2026)

Lecture seule. Programmes dans ce dossier : `analyse.py` (questions 1-4, `analyse.json`), `niveaux.py`, `niveaux2.py`,
`sorties.py`, `selection.py` (`selection.json`), `regle.py` (test figé, `test.json`), `diagnostic.py`
(`diagnostic.json`, fait APRÈS le test). Plan figé avant le test : `plan_fige.md` (20/10 01h04).
Bougies d'une minute de l'or : `data/kaggle_gold/XAU_1m_data.csv` (cache `or_m1_2014_2026.npz`).
Heures : serveur = New York + 7 h ; **Paris = serveur - 1 h**.
Unité : la **décision** = ouvertures du même sens à moins de 2 min (895 morceaux -> **397 décisions**).
Contexte d'entrée : seulement des bougies terminées avant la minute d'entrée.

## L'essentiel
| | Constat | Étiquette |
|---|---|---|
| Sens | Il trade **toujours dans le sens de la journée** : achat seulement si le prix est au-dessus de l'ouverture du jour, vente seulement en dessous (397 sur 397 ; son jumeau chez l'autre courtier : 99,2 %). Une seule règle prédit son sens à 99 % (contrôle croisé par mois) | 🟢 prouvé |
| Entrée | Il entre **pendant une poussée, au plus haut du jour** (achat) / au plus bas (vente) : 61 % au-delà de l'extrême du jour (cassé depuis 2 min en médiane), 80 % au-delà du plus haut / bas de la VEILLE, 91 % au-dessus de la dernière clôture (+1,65 $ médian) | 🟢 prouvé |
| Sorties | **Objectifs fixes en % du prix** : +0,33 %, +0,54 %, +0,71 % ; **stop** -0,50 % ou -0,75 à -0,86 % ; **stop remonté à l'entrée** (+0,02 %) quand le gain touche ~+0,2 % ; quelques morceaux laissés courir (jusqu'à +3 %) | 🟢 prouvé |
| Son avantage | Il est dans le **CHOIX** des cassures : il n'en prend qu'1 sur 5 environ. Ses entrées + nos sorties = +10,7 % du risque par décision ; notre règle sans ce choix = 0 | 🟢 prouvé (sur sa période) |
| Règle reconstruite sur 2015-2023 | -4,9 % du risque par décision après frais FTMO, 2 années sur 9 gagnantes, pas mieux que le hasard (21 % des jumeaux font aussi bien) | ⚪ bruit |

## 1. Quand entre-t-il ?
Fréquence : **3,9 décisions par semaine** (194 jours tradés sur 96 semaines) ; version 2024 : ~6 par semaine
(10/2024 -> 03/2025), version 2025-26 : ~2,9 par semaine.

| Séance (heure du serveur / Paris) | Décisions | Part |
|---|---|---|
| Asie (01h-10h / 00h-09h) | 130 | 33 % |
| Ouverture de Londres (10h-12h / 09h-11h) | 15 | 4 % |
| Londres (12h-15h30 / 11h-14h30) | 50 | 13 % |
| Ouverture de New York (15h30-17h30 / 14h30-16h30) | 103 | 26 % |
| New York soir (17h30-24h / 16h30-23h) | 99 | 25 % |

- Pics : **15h-18h serveur = 14h-17h Paris** (40 % des décisions : chiffres américains de 14h30 Paris et ouverture de
  Wall Street à 15h30 Paris) et **01h-04h serveur = minuit-3h Paris** (21 %). Son jumeau : mêmes heures.
- **Pas un robot d'annonces** : 2,3 % de ses entrées tombent 0-5 min après une annonce forte sur le dollar, contre
  1,8 % pour des minutes témoins à la même heure d'autres jours (0-60 min : 12,1 % contre 10,3 %). ⚪
- Jours : à peu près égaux (version 2024 : peu le lundi et le vendredi).
- Seconde d'entrée : 18 % dans les 5 premières secondes d'une minute (hasard 10 %) : léger penchant pour la clôture
  d'une bougie. 🟡

## 2. Dans quelle situation ?
Signe « dans son sens » : + = le prix est déjà allé dans le sens de son trade.

| Avant l'entrée | Dans son sens | Taille médiane : lui / témoin même heure |
|---|---|---|
| 5 min | 78 % | 1,5 $ / 1,5 $ |
| 15 min | 83 % | 3,6 $ / 2,6 $ |
| 60 min | 87 % | 9,0 $ / 5,1 $ |
| 4 h | 91 % | 17,5 $ / 9,9 $ |
| 1 jour | 92 % | 27 $ / 24 $ |
| 5 jours | 88 % | |
| 20 jours | 72 % | |
| Prix vs ouverture du jour | **100 %** | +26,7 $ (minimum +1,6 $) |

-> **Il suit l'élan, jamais le contre-pied**, et l'élan des 1 à 4 dernières heures est ~2 fois plus fort que d'habitude.

| Position (dans son sens, 1 = au plus haut pour un achat) | Médiane | Au-delà du range |
|---|---|---|
| Range de la veille | 1,19 | 80 % |
| Range du jour jusque-là | 1,01 | 61 % |
| Range d'Asie | 1,35 | 80 % |

-> **Cassure, jamais retour vers le milieu** (aucune entrée dans la moitié « contre lui » du range de la veille).
- Niveaux ronds (10, 50, 100 $) : aucun effet (distance médiane au multiple de 10 : 2,7 $ contre 2,6 $ au hasard). ⚪
- Agitation : il choisit les heures plus agitées que d'habitude pour cette journée (parmi les cassures possibles, il
  en prend 21 pour 1000 quand l'heure est très agitée, 2 pour 1000 quand elle est calme). 🟡
- Écart de prix : invisible dans les bougies d'une minute (non mesurable).

Ce qui le fait choisir parmi les ~22 « nouveaux plus hauts du jour dans le sens du jour » par semaine (`selection.py`,
taux de prise pour 1000 minutes candidates, moyenne 9) :

| Filtre | Pris pour 1000 |
|---|---|
| Au-delà du plus haut / bas de la veille : oui / non | 20 / 2 |
| Heure serveur 15h-18h / Asie 01h-06h | 22-28 / 2-8 |
| Écart à l'ouverture du jour ≥ 0,5 % / < 0,2 % | 13-17 / 1-3 |
| Élan de 4 h ≥ 0,6 % / < 0,2 % | 13-16 / 1-3 |

## 3. Comment sort-il ?
| | 2024 (avant 04/2025) | 2025-26 |
|---|---|---|
| Durée médiane d'un morceau | 90 min | 20 min |
| Morceaux gagnants | 67 % | 76 % |
| Gain médian / perte médiane ($ par once) | +5,4 / -1,6 | +8,8 / -11,2 |
| Moyenne par once | +2,2 $ | +5,3 $ |

Ce qu'on déduit (`sorties.py`) :
- **Objectifs en % du prix, pas en agitation** : les gains s'empilent à **+0,30-0,36 %** (155 morceaux), **+0,52-0,56 %**
  et **+0,70-0,72 %** (et +0,12 % dans la version 2025-26). Le gain médian reste à 0,31-0,34 % chaque trimestre alors
  que l'agitation de l'or a triplé (34 $ -> 125 $ par jour).
- **Stops** : -0,50 % (décisions à un morceau) ou -0,75 à -0,86 % (décisions à plusieurs morceaux) ; à peu près le même
  stop pour tous les morceaux d'une décision (écart moyen 0,12 %).
- **Stop à l'entrée** : 216 morceaux sortent entre 0 et +0,04 % ; leur meilleur point médian était +0,21 % -> le stop
  passe à l'entrée vers +0,2 %.
- Coupe rapide : ~120 morceaux fermés à la fin de la minute d'entrée avec une petite perte, mais pas de façon
  systématique (11-18 % des cas où la minute clôture contre lui). 🟡
- **Ses gros gagnants** (+40 à +155 $) : 27 morceaux au-delà de +0,75 %, gardés 19 h en médiane (des nuits entières).
  Par rapport à ses décisions perdantes, ils partent après un élan plus fort (4 h : +32 $ contre +18 $ ; 1 jour : +40 $
  contre +28 $), sur des journées 2 fois plus agitées (91 $ contre 46 $), plus souvent en Asie (13 sur 24), jamais
  dans les 5 min d'une annonce.

## 4. Le sens
| | Achats | Majorité | Régression | Arbre 1 niveau | Règle « sens du jour » |
|---|---|---|---|---|---|
| Tout (397) | 66 % | 66 % | 98,7 % | 99,0 % | 99 % |
| 2024 (135) | 79 % | 79 % | 100 % | 99,3 % | |
| 2025-26 (262) | 60 % | 60 % | 98,1 % | 98,9 % | |

Contrôle croisé par mois. L'arbre trouve seul : « prix > clôture de la veille -> achat, sinon vente ».
Différence de version : 2024 = mêmes règles mais trades longs (des heures), surtout des achats (l'or montait),
~6 par semaine ; 2025-26 = plus court, plus d'objectifs proches (+0,12 %, +0,33 %), ventes aussi fréquentes,
~3 par semaine. La logique d'entrée n'a pas changé (même sens du jour, mêmes cassures).

## 5. Synthèse et test
Hypothèse (figée dans `plan_fige.md` avant tout résultat) : à la clôture d'une minute entre 12h et 23h serveur, si le
prix est au-dessus de l'ouverture du jour, fait un nouveau plus haut du jour et dépasse le plus haut de la veille ->
achat (vente symétrique) ; 3 morceaux, objectifs +0,33 / +0,54 / +0,71 %, stop -0,75 %, stop à +0,02 % dès +0,18 % ;
une décision à la fois, une par jour et par sens. Frais FTMO de chaque époque + glissement d'un demi-écart sur les
sorties au stop, nuits FTMO, 0,5 % du compte risqué par décision.

| 2015-2023 (jamais tradé par lui) | Règle | Sens inverse | Jumeaux au hasard |
|---|---|---|---|
| Décisions (par semaine) | 1 555 (3,3) | 1 555 | mêmes instants |
| Décisions gagnantes | 44 % | 42 % | |
| Gain moyen par décision (% du risque) | **-4,9 %** | -6,9 % | -5,9 % (médiane) |
| Compte (0,5 % de risque) | -0,35 %/mois, baisse max 45 % | -0,5 %/mois | |
| Jumeaux aussi bons que la règle | | | **21 %** |
| Sans aucun frais | +1,4 % du risque (78 % gagnantes) | | |

Années : 2015 -9,2 ; 2016 -7,1 ; 2017 -7,6 ; 2018 -2,3 ; 2019 +0,5 ; 2020 -5,6 ; 2021 -6,1 ; 2022 -7,6 ;
2023 +1,6 (% du risque par décision). **2 années sur 9 gagnantes.** Sans filtre d'heures : -5,1 %, pareil.

**Verdict (décidé à l'avance) : ⚪ bruit.** La logique reconstruite ne tient pas hors de sa période. Avant frais, elle
fait à peine mieux que zéro ; les frais FTMO (0,047 % du prix par décision quand l'or valait 1 100-2 000 $) l'enterrent.

Diagnostic après coup (`diagnostic.py`, sur SA période 10/2024-10/2026, ne change pas le verdict) :

| | Décisions | Gain moyen (% du risque) |
|---|---|---|
| Ses vrais trades (frais FTMO) | 397 | +12,3 % |
| **Ses entrées + NOS sorties** | 366 | **+10,7 %** (67 % des semaines gagnantes) |
| Notre règle, toutes ses décisions | 307 | -0,5 % |
| ... celles qui tombent sur les siennes | 79 | +10,6 % |
| ... les autres | 228 | -4,4 % |

-> Les sorties sont bien reconstruites (elles redonnent ~90 % de son résultat). **Tout son avantage est dans le choix
des cassures** : parmi des cassures qui se ressemblent, il prend les bonnes, et ce filtre-là reste invisible (sans
doute un calcul interne du robot que nos variables simples ne voient pas).

## Pour la suite
1. Ne pas copier la règle simple : elle perd.
2. Piste concrète : apprendre SON CHOIX (lesquelles des ~22 cassures par semaine il prend) avec ses décisions d'avant
   10/2025 seulement, en donnant à COLLAPSAR la vue complète du marché, puis juger sur ses décisions d'après 10/2025
   et sur 2015-2023 avec les mêmes sorties (+0,33 / +0,54 / +0,71 %, stop -0,75 %, stop à l'entrée à +0,2 %).

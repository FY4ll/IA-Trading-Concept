# Plan figé — test de la logique reconstruite de Gold Reaper

**Figé le 20/10/2026 à 01h04 (heure de Paris), AVANT tout calcul de résultat sur 2015-2023.**
Aucun résultat de la règle n'a été calculé avant ce gel (ni sur 2015-2023, ni sur sa période). Le seul réglage fait
avant le gel : le nombre de signaux sur sa période (3,0 par semaine, lui 3,9) et le recouvrement avec ses décisions
(42 % de ses décisions prises dans nos heures sont retrouvées, même sens, à 30 min près). Les chiffres de la règle
viennent de SON comportement (analyse.json, sorties.py), jamais d'un résultat de marché.

## La règle (programme `regle.py`, paramètres `P`)
Heures du serveur (New York + 7 h ; Paris = serveur - 1 h). Décision prise à la CLÔTURE d'une bougie d'une minute,
entrée à l'ouverture de la minute suivante.

Entrée ACHAT (vente = symétrique) :
1. le prix est au-dessus de l'ouverture du jour (journée « verte ») ;
2. la minute vient de faire un nouveau plus haut du jour ;
3. le prix est au-dessus du plus haut de la veille ;
4. heure du serveur entre 12h00 et 22h59 (Paris 11h-22h) ;
5. une seule décision à la fois ; au plus une décision par jour et par sens.

Sortie : la position est coupée en 3 morceaux égaux.
- objectifs : +0,33 %, +0,54 %, +0,71 % du prix d'entrée (un par morceau) ;
- stop de départ : -0,75 % ;
- quand le gain atteint +0,18 %, le stop des morceaux restants passe à +0,02 % ;
- tout est fermé à la dernière bougie avant le week-end (pause de plus de 2 h) ;
- dans une même minute, le stop passe avant l'objectif (prudent).

Frais : frais FTMO de l'or à chaque époque (`mains/frais_ftmo.py`, écart constant en dollars : plus cher en part du
prix les années où l'or valait 1 100-2 000 $), un demi-écart de glissement en plus sur chaque sortie au stop / au
marché, nuits FTMO (`mains/nuit.py`, mercredi triple). Compte : 0,5 % du compte risqué par décision (perte au stop).

## Le test
Données : bougies d'une minute de l'or (`data/kaggle_gold/XAU_1m_data.csv`), 01/2015 → 12/2023 (années qu'il n'a
jamais tradées). Repères :
- **jumeaux au hasard** : mêmes instants d'entrée, mêmes sorties, sens tiré à pile ou face (200 tirages) ;
- sens inverse ;
- détail année par année.
Info seulement (ne compte pas pour le verdict) : la même règle sur sa période 10/2024 → 10/2026 ; la règle sans le
filtre d'heures (toutes heures) sur 2015-2023.

## Verdict décidé à l'avance
- 🟢 **la logique tient** : sur 2015-2023, gain moyen par décision > 0 APRÈS frais FTMO, ET mieux que 95 % des
  jumeaux au hasard, ET au moins 6 années sur 9 gagnantes.
- 🟡 **prometteur** : mieux que 95 % des jumeaux, mais gain après frais ≤ 0 ou moins de 6 années sur 9.
- ⚪ **bruit** : sinon.
Aucun réglage ne sera changé après avoir vu le résultat ; une autre version serait un NOUVEAU plan, daté.

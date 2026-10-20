# COLLAPSAR — document de conception

*Version 1 — 12/10/2026. Écrit avec le chef de projet, question par question. Rien n'est codé tant que ce document
n'est pas validé ; chaque élément de l'IA est re-validé par le chef de projet au moment de le construire.*

## 1. Le nom et l'idée

**COLLAPSAR** : une étoile géante qui s'effondre sur elle-même et donne naissance à un trou noir. L'ancien projet
(AUREX, AUREXIS) s'arrête là ; quelque chose de plus puissant en naît.

L'idée de départ du projet, retrouvée : **un enfant devant un graphique MT5.** Personne ne lui explique quoi faire.
Il découvre seul qu'on peut acheter et vendre, qu'un stop existe, qu'un gain est une bonne chose et qu'une perte
n'est pas forcément une mauvaise chose. À la fin, il doit **savoir tout faire comme un trader humain devant MT5, en
mieux.**

Ce n'est **pas** une machine à tester des stratégies, ni un robot à règles. Aucune règle de trading n'est écrite à
la main. **Les seules limites imposées sont celles de FTMO** (perte de 5 % sur un jour, perte de 10 % au total), comme
protection du compte.

## 2. Comment elle apprend : regarder, puis agir

Comme une IA de langage (lire beaucoup de texte en devinant la suite, puis apprendre par la récompense), et comme
un apprenti au travail (il regarde d'abord, il agit ensuite).

**Étage 1 — Regarder (exercices corrigés par le marché).** Son cerveau voit un graphique à un instant donné et
répond à des questions : ça va monter ou baisser dans les prochaines heures, jours, semaines ? Ça va s'agiter ? Ce
niveau va casser ? Quel aurait été le meilleur trade ici ? **La correction est la suite réelle du graphique.** Des
millions d'exercices sur 45 marchés et des années de données. Personne ne lui donne de méthode : le marché ne donne
que la bonne réponse. Elle y gagne des yeux qui comprennent ce qu'ils voient.

**Étage 2 — Agir (l'école).** Avec ces yeux, elle apprend à trader sur un simulateur fidèle, par essais et erreurs,
récompensée par l'argent de son compte. Voir l'école (section 5).

## 3. Ce qu'elle voit (ses yeux)

- **Toutes les échelles de temps** de 15 minutes au mois (15 min, 1 h, 4 h, jour, semaine, mois). La 1 minute et la
  5 minutes pourront être ajoutées plus tard (données à télécharger).
- **Tout ce que montre un graphique brut** : les bougies (ouverture, plus haut, plus bas, clôture), le volume quand
  il existe, les plus hauts et plus bas de la veille, de la semaine et du mois. **Aucun indicateur tout fait** (RSI,
  nuage…) : son cerveau peut les recalculer lui-même s'ils lui servent.
- **64 bougies par échelle**, comme la largeur d'un écran.
- **L'heure et le calendrier** : heure de la journée, jour de la semaine, sessions Asie / Europe / États-Unis.
- **Son compte** : ses positions, leur gain ou perte, la baisse du jour, ce qui reste avant les murs FTMO.
- **Tous les marchés FTMO à la fois**, pour comparer et trier (à partir de la classe 4).

## 4. Ce qu'elle peut faire (ses mains)

- **Acheter, vendre, ne rien faire**, et **combien** : une position par marché, qu'elle augmente, réduit, ferme en
  partie ou retourne.
- **Stop et objectif libres** : où elle veut, déplaçables, ou pas de stop du tout. Elle découvre seule leur utilité.
- **Ordres à l'avance** (limite et stop) **au prix qu'elle choisit**, valables le temps qu'elle décide.
- **Trier** : choisir sur quels marchés aller et lesquels ignorer.
- **Taille totalement libre** : aucun plafond par position. Seuls les murs FTMO protègent le compte.

Simulateur **fidèle à la réalité** : un ordre au marché paie l'écart de prix ; un ordre limite entre à un meilleur
prix mais peut ne pas être exécuté ; frais propres à chaque marché ; écarts du week-end.

**Construit le 13/10/2026 (`mains/`, 15 tests)** — décisions du chef de projet :
- **un seul compte de 100 000 $ pour tous les marchés**, sur une horloge commune, gains et pertes convertis en
  dollars ; ses yeux voient toutes ses positions, ses stops, ses ordres en attente, la baisse du jour, la distance aux
  murs et l'argent engagé (le défaut d'AUREXIS, qui ne voyait pas ses autres positions, est corrigé à la racine) ;
- **compte FTMO Normal** : levier 1:100 sur les devises (autres familles : valeurs prudentes à vérifier) ; **toutes les
  positions fermées avant une pause de plus de 2 h, week-end compris, dès l'école** (règle du compte financé) ;
- décision à la clôture, exécution à la bougie suivante ; stop et objectif touchés ensemble = le stop (pire cas) ;
  trou de prix = sortie au prix d'ouverture ; ordre limite seulement si le prix va au-delà ; argent engagé trop grand
  ou stop du mauvais côté = refusé comme MT5 ; pas de lot de 0,01 lot ; frais de nuit (triples le mercredi) ;
  murs FTMO exacts (minuit de Prague) contrôlés au pire moment de chaque bougie.
- Limite connue : les 2 minutes autour des grosses annonces (interdites en compte financé Normal) ne sont pas encore
  simulées (il faudra un calendrier des annonces).

## 5. L'école (étage 2)

La liberté est donnée **par étapes**, comme à l'école. On ne lui interdit rien ; on ajoute les outils au fur et à
mesure. Elle passe à la classe suivante seulement si elle a réussi l'examen de la sienne.

| Classe | Ce qu'elle a | Pour passer |
|---|---|---|
| 1 | **l'euro-dollar** seul ; toutes les échelles ; acheter / vendre / combien ; couper quand elle veut | gagner de façon stable sur des mois jamais vus de ce marché |
| 2 | les mains complètes : stop et objectif libres, ordres à l'avance | faire mieux qu'en classe 1 |
| 3 | plusieurs marchés, un par un : 5, puis 15, puis 45 | tenir sur des marchés jamais vus |
| 4 | tous les marchés en même temps : elle compare, trie et répartit son risque | battre la classe 3 sur le compte fidèle |

**Construit le 13/10/2026 (nuit, carte blanche du chef de projet)** — `ecole/`, `cerveau/agent.py`, `juge/` :
- elle entre à l'école avec **les yeux et le tronc de la cime des racines** ; à l'école, **ses yeux restent figés**
  (les racines continuent de les perfectionner ; l'école n'apprend que les mains) : 5 s par leçon au lieu de 30 à 100,
  et les récompenses très bruitées ne peuvent pas abîmer des yeux bien formés ;
- mains de la classe 1 : à chaque bougie, « garder ou changer » + position voulue (a³ x 100 x compte : fine près de
  zéro, jusqu'au levier maximum) ; 512 comptes jouent en même temps ; apprentissage PPO avec ses 3 horloges ;
- **miroir** : la moitié des parties se joue sur le marché retourné (chaque hausse devient une baisse). Constaté
  sans lui : elle devenait joueuse de casino (positions de 6 à 8 fois le compte, « vendre gros a payé » sur
  l'euro-dollar 2018-2022) : examen 2023-2025 = -2,15 %/mois, 27 % de challenges réussis, 73 % de murs ;
- contrôle sur juillet-décembre 2022 (QUAND agir est tiré au sort comme en vrai, la position est sa meilleure idée) ;
- **juge** : toutes les 100 leçons, 48 challenges d'un mois à des dates tirées au hasard sur 01/2023 -> 09/2025
  (autres dates à chaque examen) ; note = % réussis - % murs ; refuse de démarrer s'il voit un seul jour des mois
  cachés.

**Contre la paresse** (garder ses vieilles habitudes et ne jamais essayer les nouveaux outils) : chaque nouvel
outil démarre « allumé » (elle l'essaie souvent au début) ; un **carnet d'utilisation des outils** en pourcentages
(au marché, en limite, à l'avance, avec ou sans stop…) ; on distingue « jamais essayé » de « essayé et rejeté ».

## 6. Ce qu'elle apprend à aimer (sa récompense)

- **L'argent du compte à chaque bougie de 15 minutes**, positions ouvertes comprises : elle sent tout de suite
  qu'une perte grossit ou qu'un gain court. C'est ce qui lui fera découvrir seule qu'une petite perte coupée tôt vaut
  mieux qu'une grosse, et qu'une bonne position se garde.
- **Toucher un mur FTMO** (-5 % sur le jour, -10 % au total) : la partie s'arrête, **grosse punition**.
- **Réussir le challenge** (+10 %) : **bonus modéré**, plus petit que la punition (tout risquer pour réussir est
  perdant).
- **Plusieurs horloges dans la tête** : elle estime ce qui va se passer dans les prochaines heures, les prochains
  jours et les prochaines semaines, et choisit elle-même laquelle écouter. Elle peut faire du day trading et tenir une
  position de fond en même temps.
- **Rythme** : une décision possible à chaque bougie de 15 minutes ; « ne rien faire » est toujours permis.

## 7. Comment elle grandit : un arbre

**Pas de cycles. COLLAPSAR est un arbre qui pousse en continu**, jour et nuit, 100 % automatiquement, jusqu'à pousser
les portes du compte FTMO.

```
                 démo / FTMO
                     ▲
              ┌── la cime ──┐      ← la branche la plus forte (championne)
             /       │       \
       branche    fusion    branche    ← deux branches qui réussissent se rejoignent
          \       /     \      /
           branches qui explorent      ← épaisses si elles progressent, fines sinon
                     │
                   tronc               ← le cerveau commun
                     │
                  racines              ← l'étage « regarder » : exercices corrigés par le marché
```

| Phénomène | Ce que ça veut dire |
|---|---|
| **Racines** | l'étage « regarder ». Toutes les branches poussent du même tronc : mêmes yeux au départ. |
| **Les branches poussent** | chaque branche apprend en continu, avec son propre cerveau et son tempérament (curiosité, patience, vitesse d'apprentissage). Rien ne repart jamais de zéro. |
| **Elles s'épaississent** | le juge mesure chaque branche en permanence ; **celles qui progressent reçoivent plus de sève** (plus de temps d'entraînement sur la carte graphique), celles qui stagnent s'amincissent. |
| **Elles se rejoignent** | deux branches qui réussissent sont **fusionnées** en un seul cerveau (possible parce qu'elles viennent du même tronc). **La fusion n'est gardée que si elle fait mieux que les deux.** |
| **Elles bourgeonnent** | une branche forte fait naître une petite branche au tempérament légèrement modifié, qui part explorer. |
| **Elles meurent** | une branche trop longtemps fine est coupée et archivée, jamais effacée. |
| **La cime** | la branche la plus forte, après une période d'essai, est la championne. |

Le juge observe **en parallèle, sans interrompre la croissance**, comme un jardinier.

**Comment ça tourne dans la machine** : un seul programme qui ne s'arrête jamais (le cœur). À chaque **battement**
(15 minutes) : une branche tirée au sort selon sa sève s'entraîne, est notée sur une période jamais apprise, puis le
jardinier redistribue la sève, fait des bourgeons, tente des fusions, coupe. Tout est enregistré à chaque battement :
si la machine s'arrête, l'arbre reprend où il en était. **Nombre de places fixe** (4 branches vivantes, taille de la
machine) : ce qui grandit sans limite, c'est le savoir-faire, pas la taille.

**Règles ajoutées le 13/10 (avec le chef de projet)** : à chaque battement, **toutes les branches vivantes
s'entraînent**, chacune un temps proportionnel à sa sève (un bourgeon pousse dès sa naissance) ; **le niveau d'une
branche = la moyenne de ses 3 dernières notes** (une seule note est trop bruitée : la cime changeait pour 0,04 point,
et une branche saine avait été coupée sur une seule mauvaise note — elle a été ressuscitée).
Constaté : après environ 5 passages sur les exemples, une branche commence à apprendre par cœur (sa note baisse) ;
remède principal en cours : plus d'années d'historique (téléchargement 2010-2017 de 12 grands marchés).

**Journal de croissance dès le premier battement** (chaque note, sève, naissance, fusion, coupe, cime, porte) et
**deux images envoyées sur le téléphone matin (8h) et soir (20h)** : l'arbre qui pousse dans le temps (épaisseur =
sève, couleur = résultats, fourches = bourgeons, branches qui se rejoignent = fusions, croix = coupée, étoile = cime,
traits = portes franchies) et la courbe de progrès de la cime.

**Les portes qu'elle pousse d'elle-même :**

| Porte | S'ouvre quand | Automatique ? |
|---|---|---|
| 1. Compte à blanc (vrais prix, argent fictif) | la cime a tenu sa période d'essai et réussit les 12 mois cachés | oui |
| 2. Démo réelle (vrais ordres, compte démo) | le compte à blanc est positif sur la durée, avec de petites baisses | oui |
| 3. Compte FTMO | la démo réelle tient comme un vrai challenge | elle frappe, **le chef de projet ouvre** (argent réel et accès FTMO) |

## 8. Son juge

**Le juge honnête construit pour AUREXIS est repris**, recopié proprement. Ses mesures ne servent plus à éliminer des
candidats mais à **nourrir l'arbre** : distribuer la sève, décider des fusions, désigner la cime, ouvrir les portes.
Ce qu'il mesure :
- compte fidèle (tous les trades rejoués sur un seul compte, budget de risque, murs FTMO, frais réels) ;
- deux périodes d'examen tirées au hasard entre 2023 et 2025, à chaque examen ;
- période d'essai avant de devenir champion ;
- 12 mois cachés (octobre 2025 → aujourd'hui), jamais utilisés pour choisir : le verdict de vérité ;
- puis compte à blanc sur les vrais prix, puis démo réelle, puis FTMO.

**Règle d'honnêteté des données** : l'étage « regarder » et l'école n'utilisent **que des données d'avant 2023**.
Les périodes d'examen (2023 → septembre 2025) et les 12 mois cachés ne servent jamais à apprendre.

## 9. Ce qu'on suit (en pourcentages)

- le carnet d'utilisation des outils (section 5) ;
- les résultats de chaque examen : gain par mois, challenges réussis / ratés, plus forte baisse, trades refusés ;
- la progression de l'étage « regarder » : fait-elle mieux que le hasard sur des périodes jamais vues ?
- **un rapport complet sur COLLAPSAR à la fin du projet**, pour le chef de projet.

## 10. Où elle vit

- **Dossier neuf `Test_IA\collapsar\`**, séparé de Run A. On n'y recopie que ce qui est solide et testé (les données
  des marchés, le juge). Une pièce par rôle :

```
collapsar/
  docs/            ce document, le journal du projet, le rapport final
  donnees/         les marchés FTMO (bougies 15 min -> toutes les échelles), mise à jour
  yeux/            ce qu'elle voit : graphiques multi-échelles, calendrier, compte
  mains/           le simulateur fidèle : ordres, stops, objectifs, frais, positions
  cerveau/         son réseau de neurones et ses horloges
  regarder/        l'étage 1 : exercices corrigés par le marché
  ecole/           l'étage 2 : les classes, la récompense, l'apprentissage continu, les photos
  arbre/           le cœur (battements), le jardinier (sève, bourgeons, fusions, coupes), le journal de croissance
  juge/            l'examen honnête (repris d'AUREXIS)
  surveillance/    images de l'arbre, carnet des outils, statistiques, téléphone
  tests/           un fichier de tests par pièce
  vie/             ce que l'arbre produit en vivant : état, journal, cerveaux des branches, archives, images
```

- **AUREX et AUREXIS sont arrêtés** depuis le 13/10 00h55 (décision du chef de projet) : toute la machine est à
  COLLAPSAR.

## 11. Ordre de construction (chaque étape validée par le chef de projet)

1. Les **données** : les 45 marchés FTMO, toutes les échelles, avec la règle d'honnêteté (section 8).
2. Les **yeux** : le graphique multi-échelles, le calendrier, le compte.
3. Les **mains** : le simulateur fidèle, ordre par ordre, avec ses tests.
4. Le **cerveau** et ses horloges.
5. L'étage **regarder** : les exercices corrigés ; mesure « mieux que le hasard ? ».
6. L'**école**, classe 1 sur l'euro-dollar.
7. Le **juge** branché, le carnet des outils, les statistiques.
8. Classes 2, 3, 4 ; compte à blanc ; démo réelle.

## 12. Les défis, et comment on les relève

- **Le hasard des marchés** : un graphique est plus bruité qu'un texte. C'est pour ça que COLLAPSAR apprend d'abord à
  **comprendre** ce qu'elle voit (étage « regarder ») avant de trader : de meilleurs yeux, des décisions plus sûres.
- **La liberté totale** demande un long apprentissage : l'école par classes et la sélection naturelle sont faites pour
  qu'elle progresse vite et sans se perdre.
- **La preuve** : chaque progrès est mesuré par un juge honnête, jusqu'au marché réel. Quand COLLAPSAR passera ces
  étapes, on saura que c'est du solide.

**Objectif** : une IA de trading qui apprend seule, réussit le challenge FTMO et devient une source de revenu régulière.

## 13. Ce que COLLAPSAR nous a appris le 13/10/2026 (nuit et matinée en autonomie)

| Découverte | Preuve | Ce qu'on a changé |
|---|---|---|
| **Les racines apprennent par cœur leurs années** | justesse 69-99 % sur 2018-2022 (appris) contre 52 % sur des années jamais vues | les racines n'apprennent que 2018 → mi-2022 ; l'école s'entraîne sur 2010-2017, années vierges téléchargées ; trait « graphiques retournés » proposé à l'arbre |
| **C'était la cause du casino puis de la paralysie** | à l'entraînement, ses yeux « voyaient l'avenir » : elle jouait gros ; à l'examen, ses yeux redevenaient normaux | école sur années vierges ; avis mis à l'échelle sur bougies vierges |
| **L'avantage des racines est réel mais minuscule** | test de vérité : +1,8 %/mois avant frais en changeant 16 fois par jour, négatif après frais ; en TENANT ses positions, +0,25 %/mois par marché (test simplifié) | démonstration « tenir son avis » |
| **Sur le simulateur fidèle, cet avantage disparaît** | frais de nuit, fermetures forcées chaque nuit sur indices/énergie, murs : -0,16 à +0,03 %/mois (3 mois, 12 marchés) | frais recalés sur FTMO (commission 3 $/lot) ; horizon « 1 mois » ajouté aux racines (la tendance de fond est la seule source d'avantage jamais mesurée dans le projet) |
| **L'apprentissage par récompense seul ne trouve pas un avantage aussi petit** | bruit ~400 x plus fort que l'avantage par bougie : casino ou paralysie | d'abord imiter (son propre avis), puis s'améliorer en laisse ; avec un avantage nul, elle se réduit rationnellement à presque rien (0 mur, 0 perte) |
| **Le compte démo Tradeco ne ressemble pas à FTMO** | écarts fixes et larges (1,7 pip sur l'euro-dollar jour et nuit) | relevé arrêté ; à refaire sur l'essai gratuit FTMO |

**Où on en est :** un système qui fonctionne de bout en bout (yeux, arbre, mains fidèles, école, juge) et qui se
comporte sainement (ni casino ni paralysie, 0 mur), mais dont les yeux n'ont pas encore un avantage assez fort pour
battre les vrais frais. Le travail porte donc sur les racines : horizon 1 mois, graphiques retournés, plus d'années.

### Après-midi du 13/10 : un arbre neuf, une mesure fiable, tout l'historique

| Décision (validée par le chef de projet) | Pourquoi |
|---|---|
| **Racines : apprennent 2010 → 2019, notées sur 2020-2022 (3 ans)** | l'ancienne note sur 5 mois était trop bruitée (« répondre toujours pareil » battait les branches) : la cime était choisie presque au hasard |
| **Arbre 2 planté** (l'ancien archivé) | les anciennes branches avaient appris 2020-2022 par cœur |
| **Expérience décisive** : 2 ans vs 10 ans d'historique, 3 tirages chacun | 2 ans = 49,9 %, 10 ans = 50,5 % sur 3 ans jamais vus ; plus d'historique aide toujours ; vote de 3 cerveaux = aucun gain ; un même entraînement varie de ±0,4 point selon le hasard |
| **Porte automatique « observer → école »** (`arbre/portes.py`) | s'ouvre seule quand la cime ≥ 52 % ET que « tenir son avis » gagne après frais réels sur 2020-2022 (jamais l'examen) ; l'école se lance alors seule |
| **« Donne-lui tout »** : bougies horaires Dukascopy depuis 2003-2008 avant les 15 minutes (`donnees/telecharger_h1.py`, `data/fx_h1/`) | ses yeux voient toutes les échelles 1 h → mois sur ~20 ans ; la case 15 min est vide avant 2010 (elle le sait) ; MetaTrader (Tradeco) n'offre que H4+ depuis 2013 : moins que nos données |

### Nuit du 13 au 14/10 : la vision du trader (arbre 3)

| Constat / décision | Preuve / raison |
|---|---|
| **Les racines « sens / ampleur / agitation » plafonnent à ~50,8 %** | à 1 jour et 1 semaine, elles font MOINS bien que « répondre toujours pareil » ; seuls « 1 h quand elle est sûre » (53 %) et « 1 mois quand elle est sûre » (56-57 %) battent leur repère |
| **L'école A3 est saine mais ne gagne rien** | grand examen 192 challenges (2023 → 09/2025) : A3 +0,00 %/mois, 0 % de murs, baisse max 4,1 % ; la démonstration -0,29 %/mois, 14 % de murs |
| **Chef de projet : « pas de pile ou face, pas de menu »** | « un coup de folie je mets un stop de 1 500, elle doit pouvoir le faire » ; sinon « ça finit comme AUREXIS, un panneau d'affichage et des menus » |
| **Arbre 3 : les yeux évaluent N'IMPORTE QUEL coup** (`regarder/vision_trader.py`, `cerveau/trader.py`) | coup décrit librement (sens, stop d'un quart de bougie à 300 bougies ou aucun, objectif d'un tiers à 20 fois le risque ou aucun), tiré au hasard à chaque exercice ; corrigé par le vrai chemin du prix (stop compté si stop et objectif dans la même bougie, trou payé à l'ouverture, fermeture avant pause > 2 h, une semaine au plus), frais réels retirés ; yeux et tronc greffés de la cime de l'arbre 2 |
| **Note de l'arbre 3** | dans chaque situation de 2020-2022, elle choisit le coup au meilleur gain par rapport à son incertitude ; note = ce que ses 10 % de choix les plus sûrs ont VRAIMENT rapporté, frais compris, en % du risque. Repères : hasard -8,2 %, meilleur coup fixe choisi après coup +3,1 % |
| **Deux corrections la même nuit** | 1) « écart amorti » -> elle apprenait le résultat le plus fréquent (-1 pour un stop serré), pas le gain moyen ; 2) sans l'incertitude, parmi 108 coups estimés elle prenait toujours le billet de loterie surestimé par hasard (-7,8 à -13,9 %). Avec gain moyen + incertitude : -1,0 % puis +0,03 % dès les premiers battements, 50-55 % de coups gagnants, stops larges |
| **Porte de l'école coupée en mode trader** | l'école devra être rebranchée sur ces nouveaux yeux (choix continu du coup et de la taille) |

## 14. Lexique technique (les vrais noms de nos idées)

| Notre mot | Terme technique |
|---|---|
| Regarder puis agir | self-supervised pretraining puis reinforcement learning fine-tuning (la recette de ChatGPT) |
| L'arbre qui pousse sans cycles | Population Based Training asynchrone (DeepMind 2017) ; proche de la « ligue » d'AlphaStar |
| Battement | pas d'entraînement asynchrone + checkpoint |
| Tempérament | hyperparamètres (learning rate, batch size, dropout, weight decay) |
| Bourgeon | exploit & explore (copie de la meilleure + mutation des hyperparamètres) |
| Sève | allocation adaptative du calcul (roulette-wheel selection, proche de Hyperband / bandits) |
| Fusion | model merging / weight averaging (Model Soups 2022), permis par la linear mode connectivity |
| Coupe / cime | pruning, early stopping / élitisme, champion |
| Grandir sans fin | open-ended learning |
| Toutes les échelles, 64 bougies | entrée multi-timeframe, fenêtre glissante |
| Cadrage comme MT5 | normalisation par fenêtre des log-prix ; masque ; encodage cyclique de l'heure |
| Jamais une bougie pas fermée ; 10 jours d'écart | absence de look-ahead bias ; embargo / purging |
| Règle d'honnêteté | découpage temporel train / validation / test scellé |
| Le lecteur de graphique, le tronc | CNN 1D à poids partagés + embedding d'échelle ; MLP (LayerNorm, GELU, Dropout) |
| Les exercices | multi-task, multi-horizon forecasting : classification (cross-entropy), régression (Huber), volatilité (MSE) |
| Comment il apprend | descente de gradient par mini-lots, AdamW, gradient clipping |
| % bien devinés | directional accuracy contre une baseline naïve |
| L'école, l'argent à chaque bougie | curriculum learning ; récompense dense (mark-to-market) |
| Murs FTMO, horloges, anti-paresse | constrained RL ; têtes de valeur multi-horizons ; bonus d'exploration |
| Juge, portes | évaluation out-of-sample / walk-forward ; déploiement par étapes (paper trading, démo, réel) |
| Cerveau qui grandit (plus tard) | croissance de réseau qui conserve le savoir (Net2Net) |

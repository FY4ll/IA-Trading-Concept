# Audit indépendant du juge et des simulateurs — 16/10/2026

Programmes de l'audit : `collapsar/audit/` (t1 à t8). Résultats chiffrés : `collapsar/vie/audit/*.json` et `*.csv`.
Aucun fichier du projet n'a été modifié et aucun processus n'a été arrêté.

## En une phrase
**Les calculs de base du juge sont justes** : chaque moteur redonne au centime près le résultat calculé à la main,
la stratégie tricheuse gagne énormément, le hasard perd exactement les frais, et il n'y a aucune erreur de signe.
**Mais trois vraies erreurs rendent certains résultats trop pessimistes**. Une seule est grave : les heures lues en
microsecondes au lieu de nanosecondes dans le labo SMC. Les deux autres sont une « force » mal pondérée et les séances
trouées des indices. S'y ajoute une convention qui rend les chiffres petits sans être une erreur : la taille.
Avec une prudence de 0,25 % par trade, même une IA qui connaîtrait le bon sens de chaque trade du chef ne ferait que
+1,3 %/mois.

## Tableau des défauts

| # | Défaut | Où | Gravité | Sens | Ordre de grandeur mesuré |
|---|---|---|---|---|---|
| 1 | Les heures des données à la minute sont en **microsecondes** (pandas 3), le labo calcule en **nanosecondes**. Les zones sont donc « confirmées » des jours ou des mois trop tard (H4 : +166 jours, D1 : +2,7 ans). La bougie d'entrée n'est jamais suivie. | `smc/bougies.py` (bt), tous les calculs « 4 marchés (minutes) » de labo, multi, zones supply and demand, gigogne, strategie_chef ; multi45 (premier appel de `dm.charger` sans cache) | **GRAVE** | variable : **ce n'était pas la stratégie du chef qui était testée** | V1 du chef sur 4 marchés 2015-2023 : 455 trades à -0,08 R (force -1,1) avec l'erreur ; **corrigé : 161 trades à +0,22 R (force +0,6)**. Sur l'or : -0,51 R devient +0,25 R. Concepts du labo (EURUSD H1) : +0,03 R en moyenne une fois corrigé (jusqu'à 0,6 R) |
| 2 | **« Force » calculée sur le rendement brut NON pondéré par la taille**, alors que le compte prend une taille = cible / agitation. Les jours agités (petite taille) pèsent trop. | `bande_bruit.bilan`, `bitcoin_journee.bilan` | **Moyenne à grave** | **pessimiste** | Bitcoin C2 : force 1,6 → **3,1** (2017-21) et 1,2 → **2,6** (2022-23). C2 deviendrait candidate (force ≥ 3). La règle aurait pourtant gardé D1, plus régulière (1,72 contre 1,44), qui échoue en 2022-23 : la période cachée resterait fermée. B1 : -0,5 → 1,7 ; B2 : -0,1 → 2,1 ; C1 : 0,5 → 2,4 ; US500 bande de bruit : 1,5 → 2,4 |
| 3 | **Séances trouées gardées et bouchées « à plat »** : une séance est gardée dès 300 minutes sur 390. US500 : 6 % de minutes manquent, et 50 % des séances de 2017 sont trouées. | `orb.seances` → `bande_bruit`, `orb` | Moyenne | **pessimiste** | Trades US500 sur séances trouées : -0,023 % par trade, contre +0,022 % sur séances complètes. Gain brut moyen du projet 0,015 % au lieu de 0,022 %, soit environ **+2 %/an perdus** à la taille cible 1 % (+3,3 %/an dans ma réplique contre +1,4 %/an pour le projet, 2015-2021) |
| 4 | **Taille de présentation très petite.** Cible 1 % d'agitation par jour, soit la moitié de la taille du papier de la bande de bruit, et environ 0,3 fois le compte sur le bitcoin. Le chef a aussi 0,25 % de risque par trade pour environ 8 trades par mois. | tous les « %/mois cible 1 % » | (convention, pas une erreur) | rend les chiffres **petits** | Bande de bruit US500 2015-2023 à la taille du papier : **+15,5 %/an avant frais, +10,8 %/an** avec des frais FTMO réalistes, contre +4,4 %/an à cible 1 %. Plafond du compte du chef (P1) **avec le sens parfait de chaque trade : +1,26 %/mois** |
| 5 | Frais x 1,25 partout, plus une demi-fiche pour toute entrée au marché, plus le facteur d'ouverture, alors que le glissement réel mesuré au marché est nul (AUREX chez Tradeco, 11 ordres). Le relevé FTMO a été fait à 03h34 serveur, en heures creuses, quand les écarts sont larges. | fiches, noyaux._cout, frais_ftmo | Faible à moyenne | pessimiste | Or : modèle 0,015 % aller-retour contre 0,009 % chez Tradeco et 0,0125 % chez FTMO (heures creuses). US500 récent (2024-26) : fiche environ 1,5 à 2 fois le réel. Bande de bruit US500 : le x 1,25 seul coûte environ 1 %/an à cible 1 %. Les stops sont justes : glissement réel de 0,005 à 0,007 % contre 0,006 % dans le modèle |
| 6 | Les challenges « inachevés » (données finies avant la fin) comptent dans le % de réussite. FTMO n'a pourtant pas de limite de temps. | `bande_bruit.challenge`, `bitcoin_journee.challenge` | Faible (présentation) | pessimiste | 2022-2023, cible 1 % : 29 % « réussis » affichés, mais **100 % des challenges terminés sont réussis** (aucune mort). 2015-21 : 13 % affichés, contre 30 % parmi les terminés |
| 7 | Une année comptée comme 252 jours alors que le calendrier en donne 261 jours ouvrés (fériés compris). | `bande_bruit.bilan` | Faible | pessimiste | -3,4 % sur le %/an et le %/mois |
| 8 | Règle des -5 % du challenge de la bande de bruit jugée **sur la clôture du jour seulement** (les pertes latentes de la journée sont ignorées). | `bande_bruit.challenge` | Moyenne | **optimiste** | US500, cible 2 % : morts 48 % → **55 %**, réussites 40 % → **32 %**. Cible 3 % : morts 50 % → 54 %. Cible 1 % : aucun effet |
| 9 | Frais « a » (0,0015 %) et « b prudent » (0,01 %) du bitcoin **sans la commission crypto FTMO** de 0,065 % aller-retour. C'est pourtant la règle de retenue (b). | `bitcoin_journee.FRAIS` | Moyenne | **optimiste** | Le vrai frais est de 0,083 % (colonne « d » ≈ réalité). C2 : 1,84 → 1,43 %/mois à cible 1 % (ma réplique) |
| 10 | Mois du bitcoin = jours tradés / 261 x 12 : les jours sans données raccourcissent la durée. | `bitcoin_journee.bilan` | Faible | optimiste | +6,3 % sur le %/mois en 2017-21 (+0,7 % en 2022-23) |
| 11 | Frais de nuit modèle (taux + marge) contre le relevé FTMO : les achats sont trop chers et les ventes pas assez. L'horloge de l'école triple la nuit du **mercredi pour tous les marchés**, alors que FTMO triple le **vendredi** pour les indices, l'énergie et la crypto. | `mains/nuit.py`, `mains/horloge.py` | Faible | mixte | US500 achat 7,6 %/an (modèle) contre 5,7 % (relevé), vente -0,1 % contre +2,1 %. Or achat 7,8 % contre 5,3 %. Indices tenus le mercredi : 2 nuits de trop par semaine |
| 12 | Levier des fiches (devises 1:100, indices et métaux 1:30) supérieur au compte Swing mesuré (1:30 et 1:15). | `mains/fiches.py` (école) | Faible | optimiste | sans effet sur les pistes (tailles bien en dessous) |
| 13 | Le pire point de toutes les positions est additionné comme si tous arrivaient au même instant de la bougie. | chef_compte_ftmo, trois_briques | Négligeable | pessimiste | BTC + ETH : excès moyen de 0,01 % du montant par heure, 0,14 % dans les 1 % pires heures |
| 14 | Stop supposé touché avant l'objectif dans une même bougie. Ordre limite rempli au simple contact. | noyaux, zones supply and demand, chef_crypto | Négligeable | ≈ neutre | Refait à la minute (V1, 4 marchés, corrigé) : -0,02 R, 1,2 % des trades changent. 15 % des remplissages sont de simples contacts ; sans eux, R passe de +0,22 à +0,25 |
| 15 | Bougies manquantes bouchées par le dernier prix (bitcoin). | bitcoin_journee | Négligeable | — | 0,13 % des bougies des jours tradés |

## Ce qui est JUSTE (vérifié par le calcul)
**Acheter et garder.** Le moteur des zones (noyaux) redonne exactement le prix moins les frais :
- BTC 2018-2023 : +214,40 % ;
- or 2015-2023 : +73,76 % ;
- US500 2015-2023 : +130,86 % (écart avec le calcul à la main : 0).

Les autres moteurs redonnent aussi le calcul à la main exactement :
- `bande_bruit.journalier` : achat de chaque séance US500, +2,476 % ;
- `bitcoin_journee.journalier` : +265,63 %, pire point identique ;
- `chef_compte_ftmo.simuler` : 1 achat BTC à 100 % du 04/01 au 01/03/2021, 56 nuits, solde 139 590,26 $ comme à la main.

**Stratégie tricheuse** (le sens du résultat connu d'avance) :
- bande de bruit US500 : +62 %/an et 96 % de challenges réussis, contre +1,4 %/an pour la vraie ;
- C2 bitcoin : +551 % contre +72 % ;
- zones du chef (meilleur des deux sens) : +1,17 R par trade contre -0,08 R.

**Sens au hasard = -frais.**
- US500 : -5,12 %/an contre -5,14 % attendu ;
- NAS100 : -4,16 contre -4,25 ;
- or : -7,97 contre -8,11 ;
- C2 : -25,6 % contre -27,8 % attendu (écart type 31,7).

Côté zones, (R + R inverse)/2 est même un peu au-dessus de -frais (+0,02 à +0,15 R). Les conventions d'exécution ne
pénalisent donc pas.

**Marchés inventés.** Sur un marché à tendance connue, C2 gagne dans les deux sens :
- 3 ans à +80 %/an : force 1,9 ;
- 3 ans à -80 %/an : force 3,4 ;
- hasard pur : -frais.

Aucune erreur de signe. Les zones V1 PERDENT en tendance pure :
- tendance haussière (+40 %/an) : 87 % de ventes, -0,59 R ;
- tendance baissière (-40 %/an) : 92 % d'achats.

C'est leur nature : on entre au contact d'une zone, c'est-à-dire contre le mouvement en cours. Ce n'est pas une erreur
de programme. Sur le hasard pur, les zones donnent environ 0 avant frais (+0,17 et -0,23 R, 75 trades), et le moteur
à la bougie donne exactement le même résultat que le moteur à la minute.

**Frais.**
- `frais_ftmo.frais` = calcul à la main sur les 10 trades (BTC, ETH, or, US500, euro-dollar, deux dates chacun). Aucun
  frais n'est compté deux fois.
- Les nuits sont comptées seulement au passage de minuit serveur, avec le bon nombre : 7 cas testés, vendredi x 3
  (crypto), 7 nuits par semaine.
- Les frais crypto de chef_compte et trois_briques incluent bien la commission. L'euro-dollar (0,006 %) colle au réel
  (écart 0,0009 % + commission 0,005 %).

**Le compte.**
- Le levier annoncé est respecté : moyenne 1,34 à cible 1 %, 2,67 à 2 %, 3,28 à 3 % (plafond 4).
- Les montants de chef_compte sont bien plafonnés par la marge.
- Le %/mois de chef_compte et de trois_briques est composé sur les mois du calendrier : juste.

**Fidélité du direct.** Les rejeux du direct sont identiques au simulateur : 77 trades sur 77 (foule), 2 sur 2 (zones).

## Réplications indépendantes (code écrit de zéro)
**Bande de bruit S&P 500, 2015-2023**, à la taille du papier (cible 2 %, levier 4 au plus) :

| Frais | %/an | Régularité (gain/risque) |
|---|---|---|
| sans frais | +15,5 % | 1,35 |
| frais du papier | +12,7 % | |
| frais FTMO réalistes (~0,01 %) | +10,8 % | |
| fiche x 1,25 | +8,4 % | |

Le papier (Zarattini-Aziz-Barbon, SPY 2007-2024) donne 19,6 %/an et une régularité de 1,33. La régularité est la même.
Notre période n'a pas 2008, très bonne année pour cette méthode. Les années 2016, 2017 et 2019 sont plates ou
négatives, même avant frais : la méthode est réelle mais irrégulière.

**Cassure C2 du bitcoin.**
- Même nombre de trades (1 008).
- Gain brut par trade : 0,171 % (réplique) contre 0,173 % (projet).
- %/mois : 1,81 contre 1,84 au frais b, et 1,34 contre 1,37 à 0,1 %.
- Le projet est donc fidèle, sauf la force (défaut 2).

**V1 du chef sur l'or.**
- Zones zones supply and demand H4 comptées de zéro : 380 hausses et 299 baisses, identique au projet.
- Moteur de sortie refait à la minute : identique, sauf 1,2 % des trades.
- **Mais le défaut 1 changeait la stratégie** : 103 trades à -0,51 R (projet) contre 50 trades à +0,25 R (corrigé).

## Direct contre simulé
Aucun ordre COLLAPSAR n'a encore été exécuté : le compte Tradeco est toujours à <solde démo>, sans position.

Les seules vraies exécutions viennent de l'ancien AUREX sur l'or chez Tradeco :
- glissement à l'entrée au marché ≈ 0 (11 ordres) ;
- glissement aux stops de 0,005 à 0,007 % (4 stops) ;
- écart médian de 0,0093 %.

Le modèle est donc juste pour les stops, prudent pour les entrées.

## Pourquoi les pourcentages sont « microscopiques »
1. **La taille choisie** : cible 1 % et 0,25 % par trade. Avec ces tailles, même le sens parfait ne donne que
   +1,3 %/mois sur le compte du chef.
2. **Des frais réels du même ordre que l'avantage brut** : 0,015 % de frais pour 0,02 % de gain brut par trade sur la
   bande de bruit US500.
3. **Les défauts 1 à 3 ci-dessus**, qui enlèvent de l'ordre de 2 %/an à la bande de bruit, divisent par environ 2
   la force des règles bitcoin taillées à l'agitation, et faussaient complètement les zones du chef sur les marchés à
   la minute.

Corriger ne transformera pas ces pistes en machines à 8 %/mois. La bande de bruit et C2 retrouvent un avantage modeste
mais réel, d'environ 0,8 à 1,5 %/mois à des tailles compatibles FTMO, ce qui reste à confirmer sur la période cachée.

## Corrections proposées (NON appliquées)
1. **Défaut 1 :**
   - convertir les heures en nanosecondes dans `smc/bougies.minutes` et `donnees/histdata.charger`, et toujours dans
     `dm.charger` (aujourd'hui, le premier appel sans cache rend des µs et les suivants des ns, ce qui explique le
     calcul « non reproductible » du 15/10) ;
   - ajouter un test « bt et mt dans la même unité » ;
   - refaire labo, multi, multi45, zones supply and demand, gigogne et strategie_chef sur 2015-2023.

   Attention : leurs périodes cachées ont déjà été ouvertes avec la version fausse. Il faut décider avec le chef si on
   les rouvre, ce qui serait un second regard.
2. **Défaut 2 :** juger la force sur les gains journaliers du compte taillé, comme le fait déjà `crypto_flux`
   (force_jour), pas sur le rendement brut.
3. **Défaut 3 :** écarter les séances où plus de 5 % des minutes manquent, au lieu de les boucher à plat.
4. Publier les résultats aussi à la taille du papier ou du challenge (cible 2 %), avec le « plafond du tricheur ».
   Le chef verra alors ce que la taille permet.
5. Frais :
   - garder +0,5 fiche aux stops (mesuré) ;
   - enlever le x 1,25 et la demi-fiche des entrées au marché (glissement réel nul) ;
   - relever les écarts FTMO pendant la séance de New York, pas à 03h34 ;
   - ajouter la commission crypto dans les frais a et b du bitcoin.
6. Challenge de la bande de bruit : compter le pire point de la journée, comme le fait déjà `bitcoin_journee`.
   Afficher « réussis parmi les terminés » à côté des inachevés.
7. Durées : années du calendrier dans `bande_bruit.bilan`, mois du calendrier dans `bitcoin_journee.bilan`.
8. Nuits :
   - utiliser directement la table FTMO relevée, achat et vente séparés ;
   - dans l'horloge, mettre le triple du vendredi pour les indices, l'énergie et la crypto.

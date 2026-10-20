# Piste « bitcoin dans la journée » (BTCUSD, compte FTMO) — 16/10/2026

Code : `collapsar/regarder/pistes/bitcoin_journee.py` (règles et 8 variantes écrites dans l'en-tête AVANT les
résultats). Résultats : `apprentissage.json`, `choix.json`, `trades_apprentissage.csv`, `journal_apprentissage.txt`.

## Verdict honnête
**Aucune variante ne passe le juge. La période cachée (2024-01 -> 2026-10) n'a PAS été ouverte** (pas de `cachee.json`).
- La règle (écrite avant) retient la seule variante dont la force dépasse 3 sur 2017-2021 : **D1, l'heure magique
  publiée (acheter à 21h UTC, revendre à 23h UTC)**. Elle **s'effondre en 2022-2023** (-0,03 %/mois au frais prudent,
  0 % de challenges réussis, 83 % de morts). L'effet a disparu juste après sa publication (02/2022).
- L'élan « première demi-heure -> dernière demi-heure » (A1, A2) : **rien** (force ~0, perdant après frais).
- **Signal à suivre, mais NON prouvé** : les règles de suivi dans la journée — C2 (cassure du plus haut / plus bas des
  24 dernières heures, fermé avant minuit) et A3 (sens de la matinée 00h-12h serveur tenu jusqu'à 23h45) — sont
  positives sur les deux périodes, même au frais très prudent 0,03 % et même au frais de la fiche 0,1 % (C2 :
  +1,8 et +1,9 %/mois à la cible 1 %, challenges 68 % et 67 % réussis contre 16 % et 12 % pour les jumeaux). Mais
  leur force reste sous le seuil (1,6 puis 1,2 ; 2,6 à 3,1 si on pèse chaque trade par sa taille réelle), et elles
  n'ont pas été retenues par la règle : les juger maintenant sur la période cachée serait un second regard.

## Règles communes
- Journée = minuit -> 23h45 heure du serveur ; tout est fermé à 23h45 : jamais de frais de nuit (30 %/an).
- Lundi -> vendredi serveur seulement (les données n'ont pas de week-end avant 2020) ; journées avec >= 92 bougies.
- Taille : exposition = cible / agitation des 14 jours précédents, plafonnée à 1 x le compte (levier FTMO 1:1).
  Tableaux ci-dessous : cible 1 % d'agitation journalière (exposition moyenne ~0,3 x le compte).
- Frais par aller-retour : a = écart FTMO relevé 0,0012 % x 1,25 ; b = prudent 0,01 % (règle de retenue) ;
  c = très prudent 0,03 % ; d = fiche du projet 0,1 % (information).
- Challenge : -5 % dans la journée compté au plus bas des bougies de 15 min (perte latente comprise), -10 % au
  total, +10 % puis +5 % ; départ tous les 10 jours ; 20 jumeaux au sens tiré à pile ou face. Espérance = -540 € x
  (1 - part réussie), remboursement compris, gains du compte financé non comptés.

## Variantes (liste fermée)
| | Règle | Source |
|---|---|---|
| A1 | sens de 00h00-00h30 UTC -> tenu 23h30-24h00 UTC | Wen, Bouri, Xu, Zhao 2022 ; Gao, Han, Li, Zhou 2018 |
| A2 | sens de 00h00-00h30 serveur -> tenu 23h15-23h45 | même idée, journée serveur |
| A3 | sens de 00h00-12h00 serveur -> tenu 12h00-23h45 | « premières heures prédisent la fin » |
| B1 | bande de bruit, regard toutes les 30 min | Zarattini, Aziz, Barbon 2024 (réglages du papier) |
| B2 | bande de bruit, regard toutes les heures | idem |
| C1 | cassure du canal des 12 dernières heures, sortie au milieu du canal ou 23h45 | suivi de tendance horaire |
| C2 | idem, 24 heures | idem |
| D1 | achat 21h00 -> vente 23h00 UTC chaque jour | Padysak & Vojtko 2022 (Quantpedia), Gemini 2015-2022 |

## Choix 2017-05 -> 2021 (cible 1 %)
| | trades | %/mois a | %/mois b | %/mois c | %/mois d | baisse max (b) | pire jour / pire point (b) | force | challenges réussis / morts (b) | jumeaux | espérance € |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 905 | -0,08 | -0,12 | -0,21 | -0,55 | -6,9 % | -1,1 / -1,5 % | -1,44 | 0 / 0 % | 0 / 0 % | -540 |
| A2 | 1128 | +0,05 | -0,01 | -0,13 | -0,54 | -5,9 % | -3,9 / -3,9 % | +0,65 | 0 / 0 % | 0 / 4 % | -540 |
| A3 | 1147 | +1,51 | +1,46 | +1,33 | +0,91 | -13,6 % | -5,0 / -6,3 % | +1,97 | 56 / 18 % | 10 / 77 % | -239 |
| B1 | 3375 | +1,02 | +0,87 | +0,52 | -0,71 | -19,2 % | -3,7 / -3,9 % | -0,51 | 30 / 37 % | 10 / 78 % | -376 |
| B2 | 2203 | +1,26 | +1,17 | +0,94 | +0,13 | -17,2 % | -4,7 / -4,9 % | -0,06 | 38 / 12 % | 12 / 78 % | -333 |
| C1 | 1580 | +1,44 | +1,37 | +1,20 | +0,62 | -14,3 % | -3,0 / -3,2 % | +0,53 | 59 / 16 % | 13 / 75 % | -221 |
| C2 | 1008 | +1,89 | +1,84 | +1,74 | +1,37 | -13,0 % | -3,4 / -4,4 % | +1,62 | 68 / 5 % | 16 / 72 % | -174 |
| **D1** | 1545 | +0,69 | +0,62 | +0,46 | -0,11 | -5,9 % | -2,6 / -3,6 % | **+3,71** | 71 / 0 % | 3 / 11 % | -155 |

Retenue par la règle : **D1** (seule force >= 3 ; force sans la hausse du bitcoin : 3,12).

## Vérification 2022-2023 (cible 1 %)
| | trades | %/mois a | %/mois b | %/mois c | %/mois d | baisse max (b) | pire jour / pire point (b) | force | challenges réussis / morts (b) | jumeaux | espérance € |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 413 | -0,05 | -0,10 | -0,23 | -0,68 | -4,7 % | -1,7 / -2,0 % | -0,02 | 0 / 0 % | 0 / 0 % | -540 |
| A2 | 516 | -0,12 | -0,19 | -0,35 | -0,91 | -5,4 % | -1,0 / -1,1 % | -0,72 | 0 / 0 % | 0 / 0 % | -540 |
| A3 | 518 | +1,89 | +1,82 | +1,66 | +1,10 | -13,0 % | -4,1 / -4,6 % | +1,38 | 65 / 17 % | 8 / 62 % | -187 |
| B1 | 1663 | +2,09 | +1,87 | +1,36 | -0,44 | -13,5 % | -4,2 / -4,7 % | +1,25 | 62 / 13 % | 8 / 54 % | -208 |
| B2 | 1059 | +1,89 | +1,76 | +1,43 | +0,29 | -11,8 % | -4,9 / -5,5 % | +1,10 | 52 / 19 % | 12 / 49 % | -260 |
| C1 | 704 | +1,49 | +1,39 | +1,17 | +0,41 | -7,5 % | -4,4 / -5,6 % | +0,90 | 33 / 52 % | 11 / 65 % | -363 |
| C2 | 414 | +1,98 | +1,93 | +1,80 | +1,36 | -9,8 % | -1,7 / -1,9 % | +1,24 | 67 / 4 % | 12 / 60 % | -177 |
| **D1** | 696 | +0,06 | **-0,03** | -0,24 | -0,99 | -10,5 % | -2,0 / -5,2 % | +0,74 | **0 / 83 %** | 0 / 39 % | -540 |

## Période cachée 2024-01 -> 2026-10
**Non ouverte** : la variante retenue (D1) est négative en 2022-2023 au frais prudent.

## Défauts cherchés
- Regard de fin de journée : la sortie forcée à 23h45 est vérifiée par le code (aucune position ne reste ouverte).
- Heures : serveur = New York + 7 h ; UTC = serveur - 2 h (hiver de New York) ou - 3 h (été), calculé jour par jour.
  D1 en hiver traverse minuit serveur : coupé en deux trades (23h00-23h45 puis 00h00-01h00), frais payés deux fois.
- Rien n'est connu trop tôt : signaux pris sur des prix clôturés, taille calculée sur les 14 jours d'avant.
- D1 « toujours acheteur » profite de la hausse du bitcoin : force recalculée sans cette hausse = 3,12 (reste > 3),
  mais l'effet meurt en 2022-2023. Son pire point (-5,2 % dans une journée en 2023, exposition pleine un jour calme
  suivi d'une chute brutale) tue 83 % des challenges.
- Bande de bruit B1/B2 : perdante avant frais trade par trade, positive seulement grâce à la taille (plus gros les
  jours calmes) : effet de taille, pas d'avantage de sens prouvé.
- Données 2017-2019 : bitcoin Dukascopy peu actif, les vrais écarts de l'époque étaient bien plus larges (d'où le
  scénario d à 0,1 %) ; pas de samedi/dimanche avant 2020.
- Le -5 % FTMO se remet à zéro à minuit heure d'Europe centrale (= 01h00 serveur), ici compté de minuit à minuit
  serveur : petite approximation. Le minimum de 4 jours de trading n'est pas compté.

## Ce qui manquerait pour aller plus loin
1. Tester C2 et A3 comme NOUVELLE piste annoncée à l'avance (réglages figés tels quels, aucun changement), avec la
   décision du chef de projet d'ouvrir pour elles la période cachée une seule fois : c'est le seul vrai juge restant.
2. Mesurer l'écart BTCUSD réel FTMO à toutes les heures (surtout 12h et 23h45 serveur) pendant une semaine.
3. Ajouter le samedi et le dimanche (FTMO cote 7 j/7) avec des données qui les couvrent depuis 2017.
4. Pire point dans la journée proche de -5 % pour A3 / B2 / C1 à la cible 1 % : il faudrait un plafond de perte du
   jour (coupe-circuit à -3 %) avant toute démo.

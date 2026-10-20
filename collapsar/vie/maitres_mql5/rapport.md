# 3 maîtres MQL5 sur l'or : examen honnête (19/10/2026)

Programme : `collapsar/vie/maitres_mql5/analyse_mql5.py` (lecture seule), chiffres : `resultats.json`.
Seul l'or est examiné (4 trades sur d'autres marchés sont mis de côté).

## L'essentiel
- **Gold Reaper et Xauusd H1 sont LE MÊME ROBOT** : 88 % des trades de Xauusd H1 se retrouvent chez Gold Reaper
  (même sens, à environ 1 seconde près), et leurs résultats par jour se suivent à 83 %. On n'a donc que **2 maîtres
  différents**, pas 3. Bonne nouvelle quand même : deux comptes chez deux courtiers différents confirment les trades
  de Gold Reaper.
- **Les prix sont vrais** : 97 % des prix d'ouverture et 97 à 99,6 % des prix de fermeture tombent dans la vraie
  bougie d'une minute de l'or (Avalut : 90 % et 96 %). Les historiques ne sont pas inventés.
- **La peur du « 2 $ facile » ne tient pas** : la moitié des trades rapporte moins de 1,5 $ par once, c'est vrai,
  mais en moyenne il gagne 5 $ par once (avant frais) parce que les bons trades courent loin (jusqu'à +155 $).
  Les frais FTMO (0,52 $ par once) en prennent seulement 12 %.
- Aucune martingale, presque aucune grille. Par contre il ouvre **plusieurs positions d'un coup au même prix**
  (c'est une grosse position coupée en morceaux).

## 1. Martingale / grille

| | Gold Reaper | Xauusd H1 | Avalut |
|---|---|---|---|
| Taille plus grosse après une perte (après un gain) | 11 % (10 %) | 30 % (22 %) | 1 % (2 %) |
| Ouvert alors qu'une position du même sens est ouverte | 75 % | 77 % | 34 % |
| … au même prix (à 1 $ près) | 57 % | 59 % | 13 % |
| … à un prix pire (escalier contre le marché) | 5 % | 6 % | 3 % |
| Positions ouvertes en même temps (au plus) | 13 | 19 | 4 |
| Fermées ensemble (à 5 s près) | 36 % | 43 % | 13 % |
| Plus grosse perte ÷ gain médian | 11,6 fois | 23,5 fois | 5,7 fois |
| Part de toutes les pertes faite par les 5 pires | 10 % | 10 % | 9 % |
| Pire paquet de positions ÷ paquet gagnant médian | 6,5 fois | 19,5 fois | 8,1 fois |
| Mouvement par once : gain médian / perte médiane / pire | +7,9 / -7,1 / -59 $ | +7,9 / -11,4 / -101 $ | +12,3 / -25,2 / -89 $ |

Verdict : **pas de martingale** (sa taille en lots ne bouge pas après une perte : la petite hausse « par 1 000 $ »
vient de lots fixes sur un compte qui a baissé). **Pas de grille** (5 % seulement d'ajouts contre le marché).
Ses pertes ne cachent pas de catastrophe : les 5 pires ne font que 10 % de toutes les pertes. **Xauusd H1 empile
plus** (jusqu'à 19 positions, pire paquet = -18 % de son compte en octobre 2026) : c'est le même robot réglé plus
dangereux.

## 2. Frais FTMO à la place de ceux de son courtier

| | Gold Reaper | Xauusd H1 | Avalut |
|---|---|---|---|
| Mouvement médian d'un trade | 1,5 $ | 1,7 $ | 1,1 $ |
| Gain moyen par once, avant frais | 5,0 $ | 4,1 $ | 3,5 $ |
| Frais FTMO par once (écart + commission) | 0,52 $ | 0,52 $ | 0,52 $ |
| Nuits FTMO par once | 0,08 $ | 0,04 $ | 0,17 $ |
| Part du gain brut mangée : chez lui / chez FTMO | 5 % / 12 % | 8 % / 14 % | 15 % / 20 % |
| Frais qui annuleraient tout le gain | 4,9 $ par once | 4,1 $ | 3,4 $ |
| Trades gagnants : chez lui / FTMO / FTMO prudent | 72 / 67 / 64 % | 71 / 69 / 65 % | 54 / 53 / 52 % |
| Gain total sur 100 000 $ (taille du point 5) : chez lui / FTMO / prudent | +65 / +60 / +57 % | +62 / +58 / +54 % | +25 / +24 / +23 % |

« FTMO » : ses prix contiennent déjà l'écart de son courtier ; on lui rend un écart supposé (0,15 $ avec commission,
0,30 $ sans), on retire sa commission et ses nuits, on met les frais et les nuits FTMO de l'époque
(`mains/frais_ftmo.py`, `mains/nuit.py`, nuit triple le mercredi). « Prudent » : frais FTMO en plus de son écart.
Verdict : **les frais FTMO ne tuent personne** ; 2 à 8 trades gagnants sur 100 deviennent perdants, rien de plus.

## 3. Régularité (gains en % d'un compte FTMO de 100 000 $, taille du point 5)

Gold Reaper (25 mois, 20 gagnants, pire mois -3,1 %, meilleur +7,5 %)

| Période | Trades | Gagnants | Gain | Brut par once | Durée médiane | Achats |
|---|---|---|---|---|---|---|
| Avant 30/09/2025 | 487 | 65 % | +30,4 % | 3,6 $ | 50 min | 68 % |
| Après (mois cachés) | 408 | 70 % | +29,3 % | 6,3 $ | 17 min | 53 % |
| 2024 T4 | 100 | 60 % | +5,6 % | 2,3 $ | 57 min | 51 % |
| 2025 T1 | 159 | 54 % | +3,7 % | 1,5 $ | 155 min | 86 % |
| 2025 T2 | 106 | 85 % | +14,9 % | 7,9 $ | 17 min | 56 % |
| 2025 T3 | 122 | 65 % | +6,2 % | 3,9 $ | 48 min | 70 % |
| 2025 T4 | 106 | 62 % | +3,0 % | 2,6 $ | 15 min | 71 % |
| 2026 T1 | 88 | 75 % | +11,1 % | 11,6 $ | 15 min | 62 % |
| 2026 T2 | 115 | 71 % | +6,5 % | 4,9 $ | 18 min | 40 % |
| 2026 T3 | 84 | 75 % | +8,9 % | 9,5 $ | 18 min | 45 % |
| 2026 T4 (9 jours) | 15 | 53 % | -0,2 % | -1,0 $ | 69 min | 27 % |

Xauusd H1 (22 mois, 18 gagnants, pire mois -6,5 % = octobre 2026)

| Période | Trades | Gagnants | Gain | Brut par once | Durée médiane | Achats |
|---|---|---|---|---|---|---|
| Avant 30/09/2025 | 368 | 70 % | +22,7 % | 4,2 $ | 43 min | 72 % |
| Après | 639 | 68 % | +35,4 % | 4,1 $ | 12 min | 50 % |
| 2026 T4 (9 jours) | 16 | 38 % | -6,5 % | -15,8 $ | 57 min | 25 % |

Avalut (16 mois, 11 gagnants, pire mois -5,0 %)

| Période | Trades | Gagnants | Gain | Brut par once | Durée médiane | Achats |
|---|---|---|---|---|---|---|
| Avant 30/09/2025 | 58 | 62 % | +9,1 % | 7,6 $ | 309 min | 74 % |
| Après | 287 | 51 % | +15,2 % | 2,9 $ | 191 min | 66 % |
| 2025 T4 | 52 | 46 % | +8,0 % | 9,0 $ | 377 min | 79 % |
| 2026 T1 | 55 | 49 % | +6,7 % | 7,6 $ | 114 min | 53 % |
| 2026 T2 | 72 | 58 % | -3,8 % | -3,3 $ | 43 min | 50 % |
| 2026 T3 | 94 | 52 % | +5,0 % | 3,0 $ | 240 min | 76 % |

Même trader tout du long ? **Gold Reaper : oui, avec un changement de réglage début 2025** (au 1er trimestre 2025
trades de 2 h 30 et 86 % d'achats, puis à partir d'avril trades de 15 à 18 min, achats ET ventes). Mêmes heures
partout (15 h-18 h et 3 h-4 h du serveur). Aussi bon après le 30/09/2025 qu'avant. **Avalut : moins stable** (durées
de 43 min à 9 h selon le trimestre, un trimestre perdant) et presque toute son histoire est dans nos mois cachés.

## 4. Contre le hasard

| | Gold Reaper | Xauusd H1 | Avalut |
|---|---|---|---|
| Jumeau (même trade en sens inverse, frais FTMO) | -78 % | -76 % | -32 % |
| Semaines gagnantes | 73 % (sur 96) | 70 % (sur 91) | 53 % (sur 62) |
| Force par semaine (2 = sérieux, 3 et plus = très net) | 4,5 | 3,5 | 1,7 |
| Mois gagnants / force par mois | 80 % / 4,4 | 82 % / 3,3 | 69 % / 2,1 |
| Hasard aussi bon (heures tirées au sort, même sens, durée, taille : 2 000 essais) | 0 fois | 1 fois (0,05 %) | 42 fois (2,1 %) |
| Part du gain due à la hausse de l'or | 2 % | 0 % | 19 % |
| Gain FTMO des achats / des ventes | +31,5 / +28,1 % | +37,2 / +20,9 % | +21,0 / +3,2 % |

Verdict : Gold Reaper a un **vrai avantage**, qui ne vient pas de la hausse de l'or (il gagne autant en vendant).
Avalut : signal faible, il gagne surtout en achetant (ses ventes rapportent presque rien) ; 2 % de chance que le
hasard fasse aussi bien, c'est trop pour être sûr.

## 5. Challenges FTMO (100 000 $, taille calée pour que sa pire baisse fasse 8 %)

Taille : chaque trade garde sa part du compte de l'époque, puis tout est multiplié par un même réglage. Pire baisse et
murs comptés à la minute (bougies d'une minute de l'or, pessimiste). Un départ de challenge chaque jour où il trade ;
+10 % encaissés après au moins 4 jours de trading = réussi ; -5 % dans la journée (contre le solde de minuit à Prague)
ou -10 % au total = mort ; pas de limite de durée.

| | Gold Reaper | Xauusd H1 | Avalut |
|---|---|---|---|
| Lots sur 100 000 $ : médian / plus gros | 0,15 / 1,35 | 0,13 / 0,77 | 0,15 / 1,46 |
| Pire jour | -3,9 % | -6,5 % | -3,2 % |
| Gain moyen par mois | +2,6 % | +2,7 % | +1,6 % |
| Challenges terminés | 167 | 186 | 73 |
| Réussis / morts | 100 % / 0 % | 92 % / 8 % | 100 % / 0 % |
| … départs après le 30/09/2025 | 100 % / 0 % | 86 % / 14 % | 100 % / 0 % |
| Durée médiane pour faire +10 % | 125 jours | 85 jours | 111 jours |
| Réussis en moins de 30 jours / 60 jours | 1 % / 9 % | 3 % / 16 % | 0 % / 9 % |
| Taille calée sur AVANT 10/2025 seulement : pire baisse APRÈS | 3,9 % | 9,9 % | 34 % |

Verdict : à cette taille, Gold Reaper **ne meurt jamais** mais il est **lent** : environ 4 mois pour +10 %. Pour
aller plus vite il faut grossir la taille (+10 % en 2 mois = baisses vers 16 % : trop près du mur). Test le plus
honnête (dernière ligne) : taille choisie sur le passé seul, puis jouée sur les mois cachés → Gold Reaper tient
(baisse 3,9 %, +2,4 %/mois), Xauusd H1 dépasse 8 %, Avalut explose (trop peu d'histoire avant).

## 6. Verdict

| Trader | Verdict | Pourquoi | Mentor pour MAGNETAR ? |
|---|---|---|---|
| Gold Reaper New V2 2 | 🟢 fiable | Vrai avantage (hasard battu 2 000 fois sur 2 000), aussi bon dans les mois cachés, ni martingale ni grille, frais FTMO = 12 % du brut, prix confirmés par un 2e compte | **Oui, le seul candidat.** Mais seulement ses 487 trades d'avant 10/2025 pour apprendre (ils tombent dans notre période d'examen 2023-09/2025 : au chef de projet de trancher) ; les 408 d'après servent à le juger, jamais à entraîner |
| Xauusd H1 | 🟡 à surveiller | C'est le même robot, réglé plus gros et plus empilé : -18 % de son compte en octobre 2026, 14 % de challenges morts après 09/2025 ; dépôts presque chaque mois + 377 petits crédits la nuit (2 380 €, environ 16 % de ses gains) jamais expliqués | Non : copie de Gold Reaper, n'apporte rien de plus |
| Avalut Gold X1 | 🟡 à surveiller | Avantage faible (force 1,7 par semaine), gagne surtout grâce aux achats, un trimestre perdant, seulement 16 mois | Non : 58 trades seulement avant 10/2025, trop peu pour apprendre |

À savoir :
- Gold Reaper est un robot vendu sur MQL5 : beaucoup de comptes FTMO pourraient trader exactement pareil. FTMO peut
  refuser des trades identiques à ceux d'autres comptes : **à demander à FTMO par écrit** avant de s'en servir.
- Un historique MQL5 peut être le meilleur de plusieurs comptes (on ne voit pas les comptes abandonnés). Le 2e compte
  qui fait les mêmes trades limite ce risque pour Gold Reaper. Un gain passé ne garantit rien pour la suite.

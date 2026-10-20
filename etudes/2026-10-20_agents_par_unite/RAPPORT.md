# Les anciens agents par unité de temps : revérification honnête (20/10/2026)

## Où ils sont, comment ils marchaient

| génération | agents | où |
|---|---|---|
| projet v1 (15-17/09) | D1 g204, H4 g167, H1 g176, M30 g141, M15 g139 | git `b9621f7` : `models/champion_*` (copie aussi dans `archives/v1_septembre/`) |
| Run A (19/09-07/10) | H1 g838, H1T g229, H1X g215, H4 g65, M30 g67, AUREX g253 (M15) | `runs/20260919_envv2/code/models/champion_*` |

Chaque agent : un réseau (mémoire courte LSTM + PPO) qui voit les 50 dernières bougies de son unité, les unités plus
larges et des indicateurs ; il choisit vendre / rien / acheter + la taille du stop (H1T : + objectif ; AUREX : + objectif,
type d'ordre, gestion). Une position à la fois, or seul, frais 0,02 %.

## Leurs « bons résultats » d'origine

- v1 : Sharpe 1,4 à 7,5, +23 % à +140 % — mesurés sur la tranche de validation qui servait AUSSI à les choisir pendant
  ~200 générations : **pas hors échantillon** (et Sharpe du D1 / H4 gonflé ×5 / ×2,5 par une erreur de calcul).
- v1 en démo réelle : **-6,2 % en 33 h** (15-17/09) ; le 17/09 au soir, **11 trades sur 11 perdants**.
- Run A, période gardée de côté (06/2023 -> 10/2026) : +38 % à +54 % en 3,3 ans, contre **+109 à +112 %** pour l'or
  simplement acheté et gardé.

## Revérification : jamais vu + jumeau au hasard

Jumeau = la même IA, mêmes moments, mêmes stops / tailles, mais le sens de chaque ouverture tiré à pile ou face
(6 jumeaux Run A, 4 jumeaux v1). Gain en %/mois du compte ; avantage = IA - jumeaux, mois par mois.

| agent | période jamais vue | IA %/mois | jumeaux | avantage | achats |
|---|---|---|---|---|---|
| AUREX g253 | 2010 -> 2017 | **-0,37** | -0,76 | +0,39 ± 0,09 | 100 % |
| AUREX g253 | 06/2023 -> 10/2026 (*) | +0,86 | +0,61 | +0,26 ± 0,13 | 100 % |
| H1 g838 | 06/2023 -> 10/2026 | +0,81 | +1,13 | **-0,32 ± 0,20** | 68 % |
| H1T g229 | 06/2023 -> 10/2026 (*) | +0,99 | +0,69 | +0,30 ± 0,30 | 82 % |
| H1X g215 | 06/2023 -> 10/2026 (*) | +0,94 | +1,15 | -0,21 ± 0,23 | 60 % |
| H4 g65 | 06/2023 -> 10/2026 | 0 (aucun trade) | 0 | — | — |
| M30 g67 | 2010 -> 2013 | -0,06 | -0,04 | -0,02 ± 0,02 | 0 % |
| v1 H1 g176 | 2016 -> 02/2018 | +1,22 | +1,26 | -0,04 ± 0,14 | 73 % |
| v1 M30 g141 | 07/2019 -> 07/2021 | -0,17 | -0,33 | +0,16 ± 0,27 | 83 % |
| v1 M15 g139 | 06/2021 -> 06/2023 | -0,44 | -0,42 | -0,02 ± 0,08 | 86 % |
| v1 (tous) | 17/09 -> 13/10/2026 (4 semaines) | -2,9 à +1,0 | | aucun écart net | |

(*) période regardée pour les choisir à partir du 04/10 : pas tout à fait neuve. v1 D1 et H4 ont vu tout l'historique :
seules leurs 4 dernières semaines sont neuves (D1 : 0 trade).

Sur les périodes DÉJÀ VUES, plusieurs battaient un peu leur jumeau (v1 H1 +0,19 ± 0,07, v1 M30 +0,34 ± 0,18, H4 g65
+0,11 ± 0,04) : **l'avance disparaît dès qu'on passe au jamais vu.**

## Verdict

**C'était du surapprentissage, plus un penchant acheteur sur un or en hausse.** Aucun agent par unité ne choisit le
sens mieux que pile ou face sur des données jamais vues. Le seul écart net (AUREX) vient de ce qu'il achète 100 % du
temps : son jumeau, qui vend une fois sur deux, perd sur un or qui monte ; et AUREX lui-même perd de l'argent sur
2010-2017 (-0,37 %/mois).

Limites : v1 rejoué avec le code de l'époque mais la note « actualités » à 0 (aucun historique) ; les jumeaux gèrent
ensuite leur position avec la même IA, d'où un nombre de trades un peu différent.

Fichiers : `verifier.py` (Run A), `verifier_v1.py` (v1), `resultats/*.json`, `logs/`.

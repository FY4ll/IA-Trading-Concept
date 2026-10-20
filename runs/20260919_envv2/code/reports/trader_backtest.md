# Backtest du trader (2026-10-05 14:33)

Or M15, heure serveur, entrée à l'ouverture suivante, spread 0,30 $ + slippage 0,05 $ par jambe, risque 0,5 % par trade, gestion : moitié à 1R + break-even, stop suiveur M15, sortie avant la fin de journée.

## 1. Développement 2010 -> 2023-04 (tous les setups)
- **chasse aux stops** : 310 trades | gain 42% | -0.262R/trade | total -81.4R | PF 0.59 | DD -86.0R | t=-4.48 -> écarté
- **cassure-retest** : 1751 trades | gain 45% | -0.203R/trade | total -356.1R | PF 0.66 | DD -357.4R | t=-8.15 -> écarté
- **repli en tendance** : 1701 trades | gain 45% | -0.222R/trade | total -377.1R | PF 0.63 | DD -377.6R | t=-8.95 -> écarté
- **rejet en range** : 205 trades | gain 46% | -0.155R/trade | total -31.8R | PF 0.73 | DD -38.1R | t=-2.13 -> écarté
- tous setups : 3967 trades | gain 45% | -0.213R/trade | total -846.3R | PF 0.64 | DD -847.4R | t=-13.01

Playbook retenu : AUCUN setup

## 2. Période jamais vue 2023-05 -> aujourd'hui (test unique du playbook retenu)

## Entrées refusées par la discipline du trader (tous setups)
- hors heures : 11140
- pas de place : 4852
- quota du jour atteint : 2011
- stop trop large : 252
- stop trop serré : 5

VERDICT : **NON VALIDÉ** -- durée 0.1 min.

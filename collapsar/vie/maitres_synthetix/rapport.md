# Synthetix : y a-t-il de vrais traders fiables ? — 19-20/10/2026

## Verdict : 🔴 aucun mentor fiable sur Synthetix

La source est excellente (impossible à truquer, perdants compris), mais **le trafic sur l'or, l'argent et les devises
était minuscule** : 2 426 trades d'or en 2 ans, 1 101 traders, **aucun trader avec 100 trades d'or**, aucun « talent
qui dure » (≥ 200 trades et force > 3). Le seul compte qui bat le hasard est un programme rapide sur l'argent.

## 1. Source utilisée

| Point | Constat |
|---|---|
| Index publics (Kwenta sur The Graph, Satsuma) | **Éteints** (adresses mortes, vérifié le 19/10) |
| Source retenue | Les **événements de la chaîne Optimism** lus directement, point d'accès public officiel `mainnet.optimism.io` (gratuit, sans clé ; secours : `optimism.drpc.org`). Pause de 0,6 s entre demandes |
| Adresses des marchés | Fichier officiel `publish/deployed/mainnet-ovm/deployment.json` du paquet `synthetix` |
| Stops / objectifs | Synthetix n'en a pas ; Kwenta les tient en « ordres conditionnels » (son contrat d'événements, adresse dans le dépôt officiel `smart-margin`, `deploy-addresses/optimism.json`) : lus aussi |
| Dates réelles | Or, argent, euro : ouverts le **12/04/2022** (1re génération) ; livre, dollar australien : **09/02/2023** (2e génération). **Retirés en juillet 2024** (décision SCCP-2127 du 17/07/2024 ; dernier trade d'or : 09/07/2024). Le 25/08/2025 = fin de toute la plateforme, plus rien sur ces marchés depuis 2024 |

## 2. Ce qui a été collecté (`data/maitres/synthetix/`)

| Marché | Traders | Trades | Période | Durée médiane | < 4 h | Achats | Liquidés | Levier médian | Stop connu | Gain total |
|---|---|---|---|---|---|---|---|---|---|---|
| Or | 1 101 | 2 426 | 04/2022 → 07/2024 | 9,9 h | 44 % | 62 % | 4,5 % | 12x | 9 % | **-393 k$** |
| Argent | 411 | 1 442 | 04/2022 → 04/2024 | 3,6 h | 51 % | 70 % | 5,4 % | 10x | 8 % | -125 k$ |
| Euro | 571 | 1 465 | 04/2022 → 02/2024 | 6 min | 64 % | 57 % | 1,6 % | 21x | 6 % | -206 k$ |
| Livre | 112 | 255 | 02/2023 → 02/2024 | 2,1 h | 56 % | 60 % | 2,0 % | 25x | 11 % | -48 k$ |
| Dollar australien | 83 | 224 | 02/2023 → 01/2024 | 6,5 h | 45 % | 72 % | 1,8 % | 25x | 10 % | -39 k$ |
| **Total** | **1 799** | **5 812** | | | | | | | | **-810 k$** |

- 51 848 événements bruts (11 314 de la 1re génération, 40 534 de la 2e) + 3 819 ordres conditionnels Kwenta.
- 99 % de l'activité entre 04/2022 et 12/2023 ; presque rien en 2024 (71 trades au 1er trimestre).
- Sur l'or : les **acheteurs ont perdu 446 k$**, les vendeurs gagné 53 k$ (l'or a baissé en 2022 puis hésité).
- Taille typique : marge 415 $, position 6 800 $ : des petits comptes.
- Gain calculé par la marge (résultat du prix + financement + tous les frais) ; contrôle par les prix : écart médian 2,6 $.

## 3. Qui sont les vrais traders ?

| Filtre | Or | Tous marchés |
|---|---|---|
| Traders avec ≥ 10 trades | 28 | 78 |
| ≥ 30 trades | 7 | — |
| ≥ 100 trades | **0** | 2 (programmes rapides) |
| Durables (≥ 100 trades ou ≥ 6 mois, ≥ 30 trades, médiane ≥ 2 h, pas de martingale, ≤ 3 % liquidés) | 2 | 4 |
| Durables gagnants | 1 | 1 |
| Force > 3 (gain rapporté à la taille) | 0 | 0 |
| Talent qui dure (≥ 200 trades et force > 3) | **0** | **0** |
| Persistance (choisi sur la 1re moitié, jugé sur la 2de) | non mesurable (2 traders ≥ 60 trades) | non mesurable (9) |

Les 4 « durables » :

| Compte | Trades | Mois | Marchés | Durée méd. | Achats | Gagnants | Levier | Gain net | Force | Avis |
|---|---|---|---|---|---|---|---|---|---|---|
| 0xf62f46c5…c3b5 | 39 | 6 | or 35 | 4,6 h | 44 % | 59 % | 47x | +1 381 $ (dont ventes +1 173 $) | 1,0 (pas prouvé) | 🟡 seul profil intéressant : gagne surtout en VENDANT, ses moments valent mieux que son penchant (force 3,2) ; mais 39 trades et levier 47x |
| 0x24bd61c3…6492 | 45 | 6 | or 45 | 2,2 h | 87 % | 44 % | 25x | -4 864 $ | -0,8 | 🔴 acheteur perdant |
| 0x64669548…d7d4 | 31 | 7 | or, argent | 11,6 h | 84 % | 29 % | 31x | -62 $ | -1,0 | 🔴 |
| 0xf07c03d2…3e97 | 48 | 6 | dollar australien, or | 35 h | 71 % | 27 % | 5x | -4 367 $ | -1,5 | 🔴 swing mais perdant |

Seul compte au-dessus de 3 : **0x13201714…** (argent, 250 trades en 17 jours, médiane 34 min, 06-07/2022) :
probablement un programme qui profitait du retard du prix affiché (faiblesse connue de la 1re génération).
Pas un trader humain, impossible chez FTMO : **exclu**.

## 4. À retenir

- 🔴 Synthetix ne donne **aucun mentor** : trop peu de trafic hors crypto, traders occasionnels, gros levier.
- Utile quand même comme **« foule » sur l'or 2022-2024** (2 426 trades réels, 62 % d'achats, perdants nets) et comme
  rare source avec **stops connus** (9 % des trades d'or, 267 sorties sur stop).
- Toutes les données sont **avant 09/2025** : utilisables pour l'entraînement sans toucher les 12 mois cachés.
  Attention : 2023 → 07/2024 recoupe la période d'examen du juge (2023 → 09/2025).
- Une même personne peut avoir deux comptes (1re et 2e génération) : non fusionnés (gain de durée faible : la 1re
  génération ne compte que 1 880 trades).

## Fichiers

- Collecte : `collapsar/maitres/synthetix.py` (`python -m collapsar.maitres.synthetix` puis `... synthetix ordres`)
- Lecture au format commun : `collapsar.maitres.trades.lire_synthetix` (test : `tests/test_maitres.py`)
- Analyse : `collapsar/maitres/analyse_synthetix.py` -> `traders_or.csv`, `traders_hors_or.csv`, `traders_tout.csv`,
  `candidats.csv`, `resultats.json` (ce dossier)
- Données : `data/maitres/synthetix/evenements_{XAU,XAG,EUR,GBP,AUD}.csv`, `ordres_conditionnels.csv`, `etat*.json`

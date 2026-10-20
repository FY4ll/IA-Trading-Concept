# MAGNETAR (et HYPERNOVA) — archivé le 20/10/2026

**Décision du chef de projet (20/10/2026) : fin de l'IA unique qui fait tout.** Le projet repart sur une architecture
en modules spécialisés (« cerveau modulaire »). Ici : le code, les tests et l'état de l'école « de la précision »,
qui portait les deux arbres HYPERNOVA (~66 marchés) et MAGNETAR (l'or seul). Rien n'est effacé.

- État exact au moment de l'arrêt : **tag git `magnetar-final`**, branche **`archive/magnetar`** (commit `cb7877f`).
  Pour le refaire tourner : `git checkout magnetar-final` (les chemins `collapsar.ecole.precision...` y sont intacts).
- Ce dossier n'est **pas importable tel quel** (les modules s'appellent encore `collapsar.ecole.precision.*`).

## Ce qu'il y a ici

| dossier | contenu | d'où il vient |
|---|---|---|
| `ecole_precision/` | les 36 programmes de l'école : cœur de l'arbre (`coeur.py`), cerveau (`cerveau.py`), jeu / examen / jumeau (`jeu.py`), simulateur des stops (`simulateur.py`), vue (`vue.py`), examen tournant, symétrie, mentor, Gold Reaper, corrections graves, réglages (`reglages.yaml`, `reglages_or.yaml`) | `collapsar/ecole/precision/` |
| `pistes/` | 7 pistes qui dépendaient de l'école (avis, direction, foule, logique inversée, mémoire des situations, monde, mouvements) | `collapsar/regarder/pistes/` |
| `tests/` | 21 fichiers de tests + empreintes (`tests/donnees/*.npz`, `cime_magnetar_18oct.pt`, hors git) | `collapsar/tests/` |
| `vie/arbre_or/` | l'arbre MAGNETAR : branches, cime, journaux, rapports, **audit** (`audit_manques/rapport.md`), corrections graves, Gold Reaper (4,3 Go, hors git sauf les `.md`) | `collapsar/vie/arbre_or/` |
| `vie/hypernova/` | l'arbre HYPERNOVA, 1 000 générations terminées le 19/10 (11 Go, hors git sauf les `.md`) | `collapsar/vie/hypernova/` |

Les briques réutilisables ont été **copiées** (pas déplacées) dans `Test_IA/core/` et prouvées identiques
(`core/tests/test_core.py`) : simulateur FTMO, frais, nuits, données de l'or, jumeau au hasard, mains MetaTrader.

## Ce qu'il faisait

Un seul cerveau (réseau de neurones, ~1 Mo) qui regardait l'or comme un trader : zones d'offre et de demande de toutes
les unités (journalier -> 3 min), sommets / creux, agitation, heure ; et qui choisissait TOUT seul : rien / acheter /
vendre, au marché ou par ordre limite, stop derrière une structure, destination, part encaissée, risque (0,1 à 2 %),
quand revenir regarder. Apprentissage par renforcement dans un simulateur fidèle FTMO (murs -5 % / -10 %, frais, nuits,
levier, inactivité), sélection darwinienne de 4 branches par génération sur un « examen tournant » (challenges de
2 mois 2010-2023, or réel + or retourné), chaque branche comparée à son **jumeau au hasard** (mêmes gestes, sens à
pile ou face). Greffes successives (18-20/10) : stop suiveur, compte Swing, journal de trading, tendance de fond,
cerveau symétrique (N2), mentor + apprentie (P2), Gold Reaper (préparé, non greffé).

## Ses derniers résultats

| mesure | MAGNETAR | jumeau au hasard |
|---|---|---|
| génération 285 (20/10 01h37), cime Q2, examen 2010-2023 | -0,33 %/mois | -0,63 %/mois |
| contrôle 01/2024 -> 09/2025 (génération 250, jamais appris) | **-0,52 %/mois** | -0,70 %/mois |
| R moyen par trade (contrôle 2024-2025) | -0,077 R | -0,074 R |
| trades >= 5R (contrôle) | 0,0 % | 0,0 % |
| HYPERNOVA, génération 1 000 (19/10), examen | +0,19 %/mois | -0,14 %/mois |

Audit du 20/10 (`vie/arbre_or/audit_manques/rapport.md`) : son gain réel est resté vers **-0,1 %/mois de la
génération 1 à la 282** ; l'écart avec le jumeau a grandi parce que **le jumeau a baissé**, pas parce qu'elle a monté.
Avant frais, un trade valait +0,02 R ; les frais en coûtaient 0,07 R.

## Pourquoi on l'arrête

1. **Il ne bat pas nettement le jumeau au hasard** et il **perd de l'argent** sur les années jamais vues
   (2024-2025 : -0,52 %/mois) : son « avance » sur le hasard, c'est perdre un peu moins.
2. **Il coupe les gagnants trop tôt** : il visait loin (destination médiane 8,2 R) mais fermait vite (74 % à la main,
   durée médiane 1 h 15) ; 0,34 % des trades seulement passaient par +5 R ; aucun trade >= 5R sur 2024-2025.
3. **Une boîte noire qui fait tout** : quand il perdait, impossible de savoir qui s'était trompé (le sens ? l'entrée ?
   le stop ? la sortie ?). Le juge lui-même était contaminé (26 blocs d'examen sur 28 déjà appris), l'apprentissage
   s'était éteint (vitesse au plancher), et les greffes s'empilaient sans prouver d'effet.

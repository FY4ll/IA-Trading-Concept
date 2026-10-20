# Audit du projet (phase 0) — 20/10/2026

Fait = vérifié ce jour dans le dépôt ; rapporté = vu seulement dans la mémoire ou CLAUDE.md ; avis = recommandation.

## 1. État vérifié
| Point | Constat |
|---|---|
| Git | Branche `main`, propre (aucune modification en attente). 15 commits, dont 12 du 19-20/10. Tag `magnetar-final`, branche `archive/magnetar`. Distant GitHub `origin` : JAMAIS poussé depuis septembre (aucun envoi sans accord). git hors du chemin : `C:\Users\utilisateur\AppData\Local\GitHubDesktop\app-3.6.6\resources\app\git\cmd\git.exe`. |
| Ce qui suit git | Code (.py), docs (.md), réglages (.yaml), rapports, résultats chiffrés des études (.json) ; PAS les données, modèles, états vivants, ni les fichiers à clé (`.gitignore`). Aucune clé jamais commitée (vérifié). |
| Logiciels | Python 3.11.9 (pas 3.12), numpy 1.26.4, pandas 3.0.5, torch 2.5.1 + CUDA (GTX 1060), numba 0.68, scipy 1.17, scikit-learn, pydantic, MetaTrader5, stable-baselines3. Absents : polars, pyarrow, statsmodels (rien n'est ajouté sans besoin d'un test). |
| Ce qui tourne | `collapsar.direct.chef_zones` (zones du chef sur BTC/ETH, **ordres réels sur la démo Tradeco**), `collapsar.direct.foule_blanc` (suivi à blanc), `collapsar.donnees.foule_devises boucle` (collecte). Tâche Windows `TestIA_CollapsarGardien` active ; toutes les autres TestIA désactivées. MAGNETAR / HYPERNOVA : archivés, plus relancés. |
| Tests | `core` 9/9 ; `cerveau` 23/23 ; `collapsar` 179/179 ; Run A (`runs/20260919_envv2/code/tests`) 568 réussis, 2 ignorés ; **`aurexis/tests` : 6 échecs + 6 erreurs** (modules introuvables : la v3 commencée le 08/10 dépend de chemins rangés depuis ; code abandonné, non utilisé). |

## 2. Ce qui est réutilisable (vérifié)
- `core/` : données de l'or (15 min depuis 2004 + minutes), simulateur FTMO multi-comptes (murs, frais, nuits, levier,
  inactivité), taux, jumeau au hasard + comparaison appariée, mains MetaTrader démo seulement. Copies prouvées identiques
  aux originaux de COLLAPSAR.
- `cerveau/` : registre de modules (ajout sans toucher aux autres, un journal par module) ; perception : détecteurs de
  zones (D1/H4/H1/M15), tendance de fond (1/3/6/12 mois), hypothèses d'horaire ; mesure : trades sur 1 min avec deux
  juges, compte heure par heure (4 tailles), fenêtres de position (3 juges, règle FTMO des 2 h).
- Données : or Kaggle 15 min / 1 min 2004 -> 13/10/2026 (heure serveur, volume de cotation) ; ~45 marchés Dukascopy
  15 min (souvent depuis 2010-2013) ; taux d'intérêt mensuels ; conditions FTMO mesurées le 15/10 (compte d'essai Swing).
- Règles FTMO vérifiées sur les pages officielles : `docs/FTMO_REGLES_VERIFIEES.md`.

## 3. Défauts et hypothèses non vérifiées
| # | Constat | Gravité | Suite |
|---|---|---|---|
| 1 | **Écart de l'or** : UN seul relevé FTMO (15/10, 03h34, heure d'Asie), appliqué à toute heure et toute époque (ramené au prix). Aucune mesure FTMO de nuit, à l'ouverture, ni pendant une annonce. | moyenne | relever les écarts sur le compte d'essai FTMO à plusieurs heures (`collapsar/surveillance/releve_ecarts.py`) |
| 2 | **Glissement** : aucun sur les stops dans `cerveau/mesure` (prix du stop, ou ouverture si trou) ; ancien relevé : glissement réel ~0 au marché chez Tradeco (11 ordres). | faible-moyenne | sensibilité frais × 1,5 dans chaque test |
| 3 | **Taille figée des positions longues** (test de la tendance du 20/10). | corrigé | passe unique faite (`etudes/2026-10-20_taille_position`) ; taille « vol » par défaut |
| 4 | **Frais de nuit** : modèle taux d'intérêt de l'époque + marge relevée le 15/10 ; nuit triple des indices = vendredi (mesuré, non confirmé par FTMO). | moyenne | garder ; sensibilité |
| 5 | **Horaires de cotation** : les indices Dukascopy n'ont pas les heures de nuit en 2016-2019 (09:00-23:00 serveur) et ont des trous quotidiens de 6-12 h ; FTMO cote ~23 h / 24. Les heures exactes de séance FTMO ne sont pas relevées. | moyenne | prix lus aux instants (`fenetres.instants`) ; relever les séances FTMO |
| 6 | **Données de l'or prolongées après 09/2025** par le flux direct (Tradeco), autre source que Kaggle : possible saut de source. | faible | marquer ; ne pas mélanger sans le dire |
| 7 | **Règle d'inactivité FTMO (30 jours)** : confirmée pour Challenge / Vérification ; NON confirmée pour le compte financé. | — | déjà dans les mesures |
| 8 | **Pas de moteur de risque indépendant** dans `cerveau/` (les garde-fous existent seulement dans Run A et `collapsar/direct/tradeco.py`). | grave avant toute démo du cerveau | à construire quand un candidat existe (phase 3) |
| 9 | **Pas de registre d'expériences structuré** : études en dossiers + git + verrous ; registre des idées en cours (`etudes/REGISTRE_IDEES.csv`). | moyenne | registre unique (mission §15) |
| 10 | **Exécution MT5** : `core/mt5.py` ne distingue pas encore demandé / accepté / rempli / inconnu, pas de réconciliation. | grave avant démo du cerveau | phase 7 |
| 11 | `aurexis/` (v3 du 08/10) : tests cassés. | faible (abandonné) | archiver avec accord (> 10 fichiers ? non : 1 dossier) |

## 4. Risques de fuite ou de résultats trompeurs
- **Périodes déjà consommées** : l'or 2018-2026 (couche 1 zones + tendance + passe taille) ; 2024-2025 (contrôle de
  MAGNETAR, regardé souvent) ; les « 12 mois cachés » 10/2025-10/2026 (verdict d'AUREXIS) ; la lockbox de Run A
  (06/2023 ->) consultée de nombreuses fois. **Aucune période n'est vierge pour l'or** ; pour une hypothèse NEUVE,
  une période n'est « neuve » que pour elle (rien n'y a été choisi).
- **Sélection** : ~des milliers de variantes essayées au total (registre en cours) ; le 16/10, 12 effets de calendrier,
  des cassures, des creux, des paires... Le seuil de preuve doit tenir compte du nombre total d'essais.
- **Sans futur vérifié par test** dans `cerveau/` (zones, tendance, élan) ; Run A : lockbox contaminée par la porte.
- **Jumeaux** : biais de la bougie d'entrée trouvé et corrigé le 20/10 (minute d'entrée exclue) ; les rejeux par bougie
  de 15 min sans ce correctif (anciennes pistes) peuvent garder ce biais.

## 5. Le pas le plus sûr et le plus utile
1. Registre unique des idées (avec le nombre d'essais) -> choisir 3-5 hypothèses VRAIMENT neuves (le 1er plan de
   compétition reprenait 3 effets déjà testés le 16/10 : arrêté avant tout calcul).
2. Compétition 1 sur ces hypothèses, critères figés et commités, COFFRE 2024 -> fermé.
3. Moteur de risque indépendant + exécution MT5 réconciliée : seulement quand un candidat passe.

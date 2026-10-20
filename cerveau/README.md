# Le cerveau modulaire (20/10/2026)

Une IA de trading faite de modules spécialisés, inspirés des zones du cerveau, sur l'or (XAUUSD) seul. Construite
couche par couche ; chaque couche est mesurée sur des années jamais vues, contre deux juges (jumeau pile ou face,
jumeau toujours acheteur), avant de passer à la suivante.

| couche | rôle | état |
|---|---|---|
| perception (cortex) | un module par unité de temps émet un AVIS : sens, confiance 0-1, zone, entrée, stop, objectif | 1re version : détecteurs codés à la main (`perception/detecteur.py`) ; mesurés le 20/10 : aucun ne bat les juges (`etudes/2026-10-20_couche1_perception/RAPPORT.md`) |
| contexte / mémoire (hippocampe) | régime du marché, situations passées semblables | à faire |
| décision (arbitre) | pondère les avis ; v1 = vote pondéré simple | à faire |
| veto (amygdale) | règles dures non apprises : murs FTMO, écart anormal, grandes annonces | à faire |
| apprentissage (dopamine) | confiance de chaque module mise à jour après chaque trade | à faire |
| exécution (cervelet) | gestion de la position (partiel à 2 R, reste vers la zone opposée) | mesurée avec la perception (`mesure/trades.py`) |
| vigilance | agressivité selon la volatilité | à faire |

## Ajouter un module
1. Une classe qui hérite de `cerveau.socle.Module` (ou `ModulePerception`), avec un `nom` unique et sa `couche`.
2. `enregistrer(MonModule(...))` à la fin de son fichier. Rien d'autre ne change : les couches suivantes lisent
   `cerveau.socle.modules("perception")`.
3. Son journal : `self.journal()` (un fichier par module, pour savoir qui s'est trompé).

## Briques communes
`core/` : données de l'or, simulateur FTMO, jumeau, mains MetaTrader. Tests : `cerveau/tests`, `core/tests`.

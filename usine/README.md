# L'usine de recherche (20/10/2026, mission de fond §16)

Constat : 111 idées, ~117 500 essais, aucun avantage. Les idées tirées des SEULS PRIX sont épuisées. L'usine cherche de
nouvelles SOURCES d'information (données hors prix, gratuites, historisées, datées de leur PUBLICATION).

## Les rôles (sous-agents séparés : définitions dans `.claude/agents/`, un dossier et un journal chacun ici)
| rôle | fait | ne fait jamais | sortie |
|---|---|---|---|
| journaliste | cherche des hypothèses dans des données hors prix (COT, FRED, calendrier et surprises, flux des ETF or, saisonnalité d'événements) | tester, coder une règle, lire le COFFRE | `journaliste/fiches/F<n>.md` |
| scientifique | transforme une fiche en règles exactes + critères + protocole, vérifie la date de PUBLICATION des données, commit AVANT toute mesure | regarder un résultat | `etudes/<date>_<nom>/PLAN_FIGE.md` |
| travailleur | code le module de la règle + ses tests (sans futur), lance les calculs en arrière-plan | changer le plan, calculer le résultat final | `cerveau/perception/...`, tests |
| juge | applique le plan figé : juges au hasard, acheteur permanent, frais FTMO réels, règles FTMO vérifiées, correction pour le nombre total d'essais | voir autre chose que le plan et le code figés ; changer un critère | `etudes/.../resultats/`, `RAPPORT.md` |
| manager | tient le registre unique (`etudes/REGISTRE_IDEES.csv`), refuse toute idée déjà testée sans raison nouvelle et réfutable, fixe les priorités, résume chaque fournée | tester | `manager/fournees.md` |
| opérateur | seul à toucher le compte démo (hors position manuelle du chef de projet) : ne fait tourner que ce que le juge a validé ET qui a passé le COFFRE, avec le veto FTMO | compte réel (jamais), position manuelle du chef de projet | `operateur/journal.md` |

La session principale orchestre (lance les rôles, envoie le résumé sur le téléphone).

## Règles
- COFFRE 2024-01-01 -> 2026-10-13 fermé ; une ouverture par idée, sur accord du chef de projet, pour une idée qui a
  déjà passé le test.
- Fournées de 3 à 5 idées ; rapport après chaque fournée.
- **Deux fournées de suite sans rien : arrêt, et proposition d'un changement de terrain** (pas d'enchaînement).
- Seuils du juge : « prometteur » = avantage > 2 × incertitude (corrigé pour la fournée) ; « prouvé » = avantage >
  racine(2 ln N) × incertitude, N = nombre TOTAL d'essais du registre (≈ 117 500 -> ≈ 4,8 ; sans la découverte
  automatique de Run A, ≈ 11 800 -> ≈ 4,3).
- Toute donnée : utilisée à sa date de PUBLICATION (COT : publié le vendredi pour le mardi ; macro : date de sortie,
  pas le mois mesuré ; révisions : première publication si disponible, sinon décalage prudent déclaré).

## Fournées
`manager/fournees.md` (liste, décisions, résultats).

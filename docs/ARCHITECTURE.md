# Architecture (20/10/2026)

```
Test_IA/
├── core/            briques communes, testées (ne dépendent de rien d'autre)
│   ├── donnees.py     marchés (15 min, minutes de l'or, échelles, bornes d'honnêteté)
│   ├── ftmo/          simulateur fidèle FTMO (fiches, frais, nuits, horloge, comptes)
│   ├── jumeau.py      jumeau au hasard + comparaison appariée
│   ├── mt5.py         mains MetaTrader 5 (démo seulement)
│   └── taux.py        taux d'intérêt mensuels (frais de nuit de chaque époque)
├── cerveau/         le cerveau modulaire (README.md)
│   ├── socle.py       registre de modules par couche, avis, journal par module
│   ├── perception/    modules qui émettent des avis (zones, tendance, horaires)
│   ├── mesure/        avis -> trades -> juges (trades.py, compte.py, fenetres.py, juges.py)
│   └── tests/
├── etudes/          une étude = PLAN_FIGE.md + script + resultats/ + RAPPORT.md ; REGISTRE_IDEES.csv
├── docs/            audit, architecture, historique, protocole, règles FTMO vérifiées
├── collapsar/       ancienne IA (COLLAPSAR) : démos encore actives (direct/), pistes, rapports ; référence
├── archive/magnetar/  MAGNETAR + HYPERNOVA archivés (tag magnetar-final)
├── runs/ , archives/, aurexis/   Run A, projet v1, v3 abandonnée (référence)
└── data/            marchés (hors git)
```

## Couches du cerveau (état)
| couche | rôle | état |
|---|---|---|
| perception | avis : sens, confiance, zone, entrée, stop, objectif | modules codés à la main ; aucun n'a d'avantage prouvé |
| contexte / mémoire | régime, situations semblables | à faire (quand un test en a besoin) |
| décision | pondère les avis (v1 : vote) | à faire |
| veto (risque) | règles dures indépendantes du cerveau | **manquant** (requis avant toute démo du cerveau) |
| apprentissage | confiance par module | à faire |
| exécution | gestion de position + MT5 réconcilié | gestion mesurée hors ligne ; exécution réelle à faire |
| vigilance | agressivité selon la volatilité | taille selon la volatilité dans les mesures |

## Règles d'ingénierie
- Un module = un fichier, une couche, un nom unique, enregistré (`cerveau.socle.enregistrer`).
- Tout calcul de mesure a un test (sans futur, juges exacts, règles FTMO).
- Pas de nouvelle dépendance sans test qui en a besoin.

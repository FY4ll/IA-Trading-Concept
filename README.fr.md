# IA Trading Concept — recherche d'un avantage de trading par IA, avec validation stricte

*[English version](README.md)*

> ⚠️ Projet de recherche. Aucune stratégie de ce dépôt n'est rentable. Rien ici n'est un conseil d'investissement.

---

## Résultat

| | |
|---|---|
| Période de recherche | 15/09/2026 → 20/10/2026 |
| Idées testées | **111** (registre complet : [`etudes/REGISTRE_IDEES.csv`](etudes/REGISTRE_IDEES.csv)) |
| Variantes évaluées | environ **117 500** |
| Idées avec un avantage qui tient après frais, sur données jamais vues | **0** |
| Seule information réelle trouvée | positionnement « contre la foule » des comptes Binance (force ≥ 3 avant frais), annulé par les frais FTMO ([fiche](docs/FICHE_C1_CONTRE_LA_FOULE.md)) |

## Ce qui a été testé

| Approche | Méthode | Verdict sur données jamais vues |
|---|---|---|
| Agents par unité de temps (D1 → M15) | PPO + LSTM, sélection évolutionnaire | Pas mieux que pile ou face ; -6,2 % en 33 h en démo réelle |
| AUREX / AUREXIS | PPO, 45 marchés, marchés miroirs | Gain dû à 100 % d'achats sur un or haussier ; perd sur 2010-2017 |
| COLLAPSAR | préentraînement auto-supervisé, puis RL ; arbre de cerveaux (population-based training) ; marchés synthétiques | Sens juste ≈ 50,8 % ; ≈ 0 R par trade |
| Juge de trades supervisé | 6,4 M de trades candidats, probabilités calibrées | Meilleur 1 % : 26,7 % de trades à 2R pour 27,3 % requis |
| Zones d'offre et de demande (supply and demand) | règles figées : profil de volume, 2e contact, FVG, zone opposée | Aucune unité ne bat les deux juges ; M15 perd après frais |
| MAGNETAR | 4 cerveaux, entraînement par population | -0,52 %/mois contre -0,70 pour le jumeau : non significatif |
| Tendance de fond 1/3/6/12 mois | taille à volatilité constante | Ne bat jamais l'acheteur permanent ; non robuste sur 5 autres marchés |
| Compétitions 1 et 2 | élan de la journée, trou d'ouverture, retournement des devises, momentum relatif, modèle linéaire, volatilité gérée | 0 sur 6 |
| Pistes publiées et effets connus | cassure de l'ouverture NY, bande de bruit (Zarattini et al. 2024), effets de calendrier, achat des creux, cassure 24 h du bitcoin… | Toutes mortes après frais ou sur leur période cachée |

Détail complet : [`docs/RESEARCH_HISTORY.md`](docs/RESEARCH_HISTORY.md) et
[`docs/Rapport_technique_2026-10-17.md`](docs/Rapport_technique_2026-10-17.md).

## Protocole de validation

Le cœur du projet. Décrit en détail dans [`docs/VALIDATION_PROTOCOL.md`](docs/VALIDATION_PROTOCOL.md).

- **Plan figé avant le calcul.** Chaque test a un `PLAN_FIGE.md` commité dans git avant toute mesure.
- **Coffre scellé.** 2024-01-01 → 2026-10-13 n'est jamais chargé par la recherche (refus au niveau du chargeur de données).
- **Deux références obligatoires :**
  - un *jumeau* qui reproduit chaque geste (moment, taille, stop, type d'ordre) mais tire le sens au hasard
    (placebo apparié, plusieurs graines) ;
  - un *acheteur permanent* à volatilité constante.
- **Coûts réels FTMO :** écart, commission, frais de nuit par époque (nuit triple au bon jour), levier, murs -5 %/jour
  et -10 % au total contrôlés au pire moment de chaque bougie, inactivité de 30 jours. Règles vérifiées sur les pages
  officielles : [`docs/FTMO_REGLES_VERIFIEES.md`](docs/FTMO_REGLES_VERIFIEES.md).
- **Tests multiples :** seuil de force `max(3, sqrt(2·ln N))`, avec N = nombre total d'essais du registre.
- **Contrôles de vérité des moteurs :** une stratégie qui connaît le futur doit gagner énormément, le hasard doit perdre
  exactement les frais, acheter-et-garder doit redonner le prix moins les frais.

Bugs de mesure trouvés par ce protocole (et corrigés, avec un test chacun) : horodatages lus en microsecondes au lieu
de nanosecondes, publication de l'inflation américaine datée la veille dans une source publique (faux avantage
spectaculaire), frais de nuit oubliés sur 36 % des nuits, stop du jumeau déclenché par un prix antérieur à l'entrée.

## Constats

1. **L'apprentissage par cœur est le problème n° 1.** 69 à 99 % de sens juste sur les années apprises, 52 % sur des
   années vierges. Le marché n'offre qu'environ 100 000 situations indépendantes, pas des millions.
2. **Specification gaming.** Les agents RL optimisent le critère, pas l'intention : effondrement vers l'inaction quand
   la récompense est trop bruitée (bruit ≈ 400 × l'avantage par bougie), mise maximale quand le réseau a mémorisé
   l'avenir, achat systématique quand le marché monte.
3. **Battre zéro ne prouve rien.** Sur l'or 2018-2026, presque tout ce qui achète gagne ; seule la comparaison à
   l'acheteur permanent et au jumeau est informative.
4. **Les coûts décident.** Frais de nuit FTMO de 3 à 8 %/an sur l'or (≈ 30 %/an sur les cryptos) et règle d'inactivité
   tuent la plupart des petits avantages.
5. **L'agitation se prévoit, la direction presque pas.** 58 à 80 % de la variance de la volatilité est expliquée, la
   direction plafonne vers 51 %.

## Structure du dépôt

| Dossier | Contenu |
|---|---|
| [`core/`](core/) | Simulateur de compte FTMO, chargement des données, jumeau au hasard, taux, connexion MetaTrader 5 (démo) |
| [`cerveau/`](cerveau/) | Architecture modulaire (perception, mesure, juges), portefeuille multi-marchés, simulateur de challenge |
| [`etudes/`](etudes/) | Une étude = `PLAN_FIGE.md` + script + `resultats/` + `RAPPORT.md` ; registre unique des idées ; protocole de replay manuel |
| [`usine/`](usine/) | Pipeline de recherche par rôles (journaliste, scientifique, travailleur, juge, manager, opérateur) |
| [`docs/`](docs/) | Audit, architecture, historique, protocole, règles FTMO, sources des données |

### La branche `archive`

Pour garder `main` léger, les générations précédentes sont intactes sur la branche [`archive`](https://github.com/FY4ll/IA-Trading-Concept/tree/archive) :
`collapsar/` (3e génération : préentraînement, marchés synthétiques, arbre de cerveaux, audits), `archive/magnetar/`
(MAGNETAR, HYPERNOVA), `runs/`, `archives/`, `aurexis/` (premières générations), `atelier/`, `research_notes/` et
`reports/` (notes bibliographiques). Ce code est conservé pour mémoire et ne s'exécute pas toujours. Les chemins vers
ces dossiers dans la documentation et les rapports renvoient à cette branche. Dépendances en plus :
`requirements-archives.txt`.

## Reprendre le projet

La recherche s'est arrêtée le 20/10/2026. Tout ce qu'il faut pour la poursuivre sans l'auteur est dans
[`docs/HANDOVER.md`](docs/HANDOVER.md) (en anglais) : ce qui est actif ou archivé, la mise en place des données,
comment lancer une étude, les problèmes connus, les pistes ouvertes et un glossaire. Modèle d'étude :
[`docs/TEMPLATE_PLAN_FIGE.md`](docs/TEMPLATE_PLAN_FIGE.md).

Pour simplement tester une stratégie sur ton propre historique de trades : [ProveIt](https://github.com/FY4ll/ProveIt).

## Installation et tests

Environnement d'origine : Windows, Python 3.11, PyTorch CUDA, GTX 1060 6 Go, 16 Go de RAM.

```bash
python -m venv venv
venv\Scripts\activate          # Linux / macOS : source venv/bin/activate
pip install -r requirements.txt
pytest              # tests/ tourne sans données ; les tests qui ont besoin des données sont « skipped »
```

Les données de marché ne sont pas incluses (droits des fournisseurs). Sources et liens officiels :
[`docs/SOURCES_DES_DONNEES.md`](docs/SOURCES_DES_DONNEES.md) (Dukascopy, HistData, Binance, FRED, CBOE, calendrier
MetaTrader). Le simulateur attend un fichier `core/ftmo/conditions_ftmo.json` produit par votre propre relevé.

## Non inclus

Données de marché, modèles entraînés, états d'entraînement, journaux, accès et clés, conditions relevées chez les
courtiers, et le code d'un indicateur tiers de zones d'offre et de demande (les modules qui l'utilisaient ne
s'exécutent donc pas tels quels).

## Crédits

Conception, direction de la recherche et décisions : **F4ll_**. Code écrit avec l'assistant
[Claude Code](https://claude.com/claude-code) (Anthropic), utilisé comme outil de développement. Les modèles de trading
tournent en local et n'appellent aucun modèle de langage pour décider.

## Licence

[MIT](LICENSE)

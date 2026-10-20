# Cerveau de marché : recherche (2026-10-05 14:24, horizon 10 j)

Vol cible 10 %/an pour toutes les stratégies. Périodes : avant lockbox 2012 -> 2023-04, lockbox 2023-05 -> aujourd'hui.

| Stratégie | Sharpe avant | Sharpe lockbox | DD lockbox | Challenge FTMO lockbox |
|---|---|---|---|---|
| achat_permanent | 0.10 | 1.39 | 12.3% | 56% |
| sma20_50 | 0.41 | 0.72 | 13.3% | 37% |
| sma50_200_long | 0.01 | 1.25 | 11.9% | 46% |
| momentum_60j | 0.29 | 1.03 | 9.2% | 44% |
| cerveau logit|technique long_short | -0.11 | 0.82 | 6.5% | 3% |
| cerveau logit|technique long_only | -0.09 | 1.12 | 6.5% | 2% |
| cerveau gbm|technique long_short | -0.16 | 0.89 | 9.5% | 27% |
| cerveau gbm|technique long_only | -0.06 | 1.26 | 5.6% | 24% |
| cerveau logit|macro+marchés long_short | -0.22 | 1.15 | 9.9% | 31% |
| cerveau logit|macro+marchés long_only | -0.17 | 1.37 | 8.4% | 30% |
| cerveau gbm|macro+marchés long_short | 0.20 | 0.73 | 15.8% | 21% |
| cerveau gbm|macro+marchés long_only | 0.25 | 1.04 | 9.7% | 23% |
| cerveau logit|tout long_short | 0.20 | 1.04 | 13.4% | 29% |
| cerveau logit|tout long_only | 0.09 | 1.41 | 8.5% | 30% |
| cerveau gbm|tout long_short | 0.08 | 0.37 | 11.7% | 13% |
| cerveau gbm|tout long_only | 0.03 | 1.12 | 10.3% | 13% |

| Config | AUC avant | AUC lockbox | Brier avant (base) | validé L/S | validé long |
|---|---|---|---|---|---|
| logit|technique | 0.478 | 0.445 | 0.2648 (0.2496) | non | non |
| gbm|technique | 0.492 | 0.470 | 0.2771 (0.2496) | non | non |
| logit|macro+marchés | 0.502 | 0.569 | 0.2581 (0.2496) | non | non |
| gbm|macro+marchés | 0.492 | 0.503 | 0.2773 (0.2496) | non | non |
| logit|tout | 0.524 | 0.552 | 0.2651 (0.2496) | non | non |
| gbm|tout | 0.491 | 0.509 | 0.2842 (0.2496) | non | non |

## Ce que le cerveau a appris (logit, tous moteurs, poids standardisés)

- RSI 14 : +0.279
- taux réel US 10 ans : +0.257
- variation du taux Fed (3 mois) : -0.234
- écart à la moyenne 200 j : -0.233
- netteté de la tendance 1 mois : -0.206
- volatilité 1 mois : -0.201
- momentum 6 mois : +0.198
- expansion de volatilité : +0.189
- niveau de peur (VIX) : +0.188
- variation du taux réel (1 mois) : -0.142
- écart à la moyenne 50 j : -0.142
- momentum EURUSD (dollar faible si +) : +0.114

## Thèse du 2026-10-02

Biais HAUSSIER à 10 jours (probabilité de hausse 67%). Moteurs haussiers : taux réel US 10 ans, écart à la moyenne 200 j, netteté de la tendance 1 mois, recul depuis le plus haut annuel. Moteurs baissiers : variation du taux réel (1 mois), momentum 6 mois, RSI 14, momentum EURUSD (dollar faible si +).

Durée : 0.4 min.

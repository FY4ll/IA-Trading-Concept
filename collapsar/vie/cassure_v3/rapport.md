# Cassure crypto v3 : amélioration pas à pas (liste fermée du 16/10/2026)

Règles du juge : `collapsar/docs/CASSURE_AMELIORATION.md` (figé) ; précisions écrites avant les résultats dans l'en-tête de `collapsar/regarder/pistes/cassure_v3.py`. Moteur : `collapsar/strategies/cassure.py` (redonne exactement les trades de C2).

**Note** d'une période = R + C. R = rapport gain / risque moyen des marchés du développement (BTC, ETH et groupe A : ADAUSDT, ATOMUSDT, BCHUSDT, DOGEUSDT, EOSUSDT, FILUSDT, LTCUSDT, NEARUSDT, SOLUSDT, UNIUSDT, XLMUSDT, XRPUSDT), chacun seul à la cible choisie ; C = (challenges FTMO réussis - morts) / 100 sur le compte BTC + ETH. Une idée est gardée si la note 2017-2026 monte sans baisser sur aucune des deux moitiés (2017-2021, 2022-2026).

## Amélioration 1 ensemble de canaux — GARDÉE : ensemble 12-48 h
(jugée sur : développement)

| variante | note 2017-2026 | note 2017-2021 | note 2022-2026 | R 17-26 | compte %/mois | baisse max | challenges réussis / morts | jumeaux réussis / morts |
|---|---|---|---|---|---|---|---|---|
| actuel | +0.525 | +0.515 | +0.335 | +0.174 | +1.86 % | -22.4 % | 67 % / 32 % | 12 % / 81 % |
| ensemble 12-48 h | +0.724 | +0.730 | +0.554 | +0.188 | +1.74 % | -19.6 % | 76 % / 23 % | 1 % / 78 % |

## Amélioration 2 week-end — rejetée
(jugée sur : binance)

| variante | note 2017-2026 | note 2017-2021 | note 2022-2026 | R 17-26 | compte %/mois | baisse max | challenges réussis / morts | jumeaux réussis / morts |
|---|---|---|---|---|---|---|---|---|
| actuel | +0.684 | +0.676 | +0.427 | +0.058 | +1.71 % | -19.3 % | 80 % / 18 % | 0 % / 85 % |
| week-end | -0.379 | -0.161 | -0.358 | -0.161 | +0.95 % | -42.6 % | 38 % / 60 % | 0 % / 90 % |

## Amélioration 3 sortie — rejetée
(jugée sur : développement)

| variante | note 2017-2026 | note 2017-2021 | note 2022-2026 | R 17-26 | compte %/mois | baisse max | challenges réussis / morts | jumeaux réussis / morts |
|---|---|---|---|---|---|---|---|---|
| actuel | +0.724 | +0.730 | +0.554 | +0.188 | +1.74 % | -19.6 % | 76 % / 23 % | 1 % / 78 % |
| canal opposé N/2 | +0.691 | +0.713 | +0.540 | +0.231 | +1.66 % | -23.0 % | 72 % / 26 % | 0 % / 86 % |

## Amélioration 4 taille — GARDÉE : agitation 24 h
(jugée sur : développement)

| variante | note 2017-2026 | note 2017-2021 | note 2022-2026 | R 17-26 | compte %/mois | baisse max | challenges réussis / morts | jumeaux réussis / morts |
|---|---|---|---|---|---|---|---|---|
| actuel | +0.724 | +0.730 | +0.554 | +0.188 | +1.74 % | -19.6 % | 76 % / 23 % | 1 % / 78 % |
| agitation 24 h | +0.862 | +0.968 | +0.707 | +0.326 | +1.99 % | -17.9 % | 76 % / 23 % | 0 % / 78 % |

## Amélioration 5 arrêt du jour — rejetée
(jugée sur : développement)

| variante | note 2017-2026 | note 2017-2021 | note 2022-2026 | R 17-26 | compte %/mois | baisse max | challenges réussis / morts | jumeaux réussis / morts |
|---|---|---|---|---|---|---|---|---|
| actuel | +0.862 | +0.968 | +0.707 | +0.326 | +1.99 % | -17.9 % | 76 % / 23 % | 0 % / 78 % |
| arrêt -2 % | +0.931 | +1.266 | +0.526 | +0.295 | +1.99 % | -17.9 % | 81 % / 18 % | 0 % / 79 % |
| arrêt aucun | +0.777 | +0.835 | +0.673 | +0.325 | +1.99 % | -17.9 % | 72 % / 27 % | 0 % / 81 % |

## Amélioration 6 compte — rejetée
(jugée sur : développement)

| variante | note 2017-2026 | note 2017-2021 | note 2022-2026 | R 17-26 | compte %/mois | baisse max | challenges réussis / morts | jumeaux réussis / morts |
|---|---|---|---|---|---|---|---|---|
| actuel | +0.862 | +0.968 | +0.707 | +0.326 | +1.99 % | -17.9 % | 76 % / 23 % | 0 % / 78 % |
| BTC seul | +1.025 | +1.281 | +0.602 | +0.326 | +1.52 % | -13.3 % | 73 % / 3 % | 2 % / 66 % |

## Amélioration 8 risque du challenge — GARDÉE : cible 0.75 % + réduction
(jugée sur : développement)

| variante | note 2017-2026 | note 2017-2021 | note 2022-2026 | R 17-26 | compte %/mois | baisse max | challenges réussis / morts | jumeaux réussis / morts |
|---|---|---|---|---|---|---|---|---|
| actuel | +0.862 | +0.968 | +0.707 | +0.326 | +1.99 % | -17.9 % | 76 % / 23 % | 0 % / 78 % |
| cible 0.75 % | +1.139 | +1.295 | +0.850 | +0.331 | +1.48 % | -13.4 % | 87 % / 6 % | 0 % / 69 % |
| cible 0.75 % + réduction | +1.210 | +1.286 | +0.866 | +0.331 | +1.48 % | -13.4 % | 88 % / 0 % | 0 % / 46 % |
| cible 1.00 % + réduction | +1.079 | +1.273 | +0.941 | +0.326 | +1.99 % | -17.9 % | 85 % / 9 % | 0 % / 57 % |
| cible 1.25 % | +0.696 | +1.028 | +0.427 | +0.311 | +2.49 % | -22.9 % | 69 % / 30 % | 0 % / 83 % |
| cible 1.25 % + réduction | +1.043 | +1.298 | +0.781 | +0.311 | +2.49 % | -22.9 % | 82 % / 9 % | 0 % / 66 % |
| cible 1.50 % | +0.673 | +1.011 | +0.378 | +0.296 | +2.92 % | -26.9 % | 68 % / 31 % | 1 % / 87 % |
| cible 1.50 % + réduction | +0.845 | +1.072 | +0.579 | +0.296 | +2.92 % | -26.9 % | 73 % / 18 % | 1 % / 72 % |

## Version retenue

canaux 12/18/24/30/36/48 h ; lundi -> vendredi ; sortie milieu du canal ; agitation 24 heures ; arrêt du jour -3 % ; cible 0.75 % ; réduction près du mur ; compte BTC + ETH

| marché | période | trades | %/mois | rapport gain/risque | baisse max | force contre le jumeau |
|---|---|---|---|---|---|---|
| BTCUSD | 2017-2026 | 12720 | +1.14 % | +1.34 | -10.0 % | +10.8 |
| BTCUSD | 2017-2021 | 6172 | +1.71 % | +1.70 | -10.0 % | +9.1 |
| BTCUSD | 2022-2026 | 6548 | +0.61 % | +0.91 | -6.8 % | +5.9 |
| ETHUSD | 2017-2026 | 11930 | +0.57 % | +0.80 | -13.6 % | +9.8 |
| ETHUSD | 2017-2021 | 5351 | +0.38 % | +0.50 | -13.6 % | +7.4 |
| ETHUSD | 2022-2026 | 6579 | +0.74 % | +1.08 | -9.1 % | +6.5 |
| ADAUSDT | 2017-2026 | 11487 | +0.52 % | +0.79 | -11.2 % | +6.9 |
| ADAUSDT | 2017-2021 | 4735 | +1.07 % | +1.51 | -6.5 % | +7.5 |
| ADAUSDT | 2022-2026 | 6752 | +0.10 % | +0.17 | -11.2 % | +2.3 |
| ATOMUSDT | 2017-2026 | 10696 | -0.19 % | -0.31 | -31.2 % | -0.1 |
| ATOMUSDT | 2017-2021 | 3681 | -0.12 % | -0.19 | -15.5 % | +0.2 |
| ATOMUSDT | 2022-2026 | 7015 | -0.24 % | -0.38 | -21.5 % | -0.3 |
| BCHUSDT | 2017-2026 | 9209 | +0.07 % | +0.11 | -19.2 % | +2.3 |
| BCHUSDT | 2017-2021 | 2809 | -0.05 % | -0.07 | -12.2 % | +0.7 |
| BCHUSDT | 2022-2026 | 6400 | +0.13 % | +0.18 | -19.2 % | +2.3 |
| DOGEUSDT | 2017-2026 | 9255 | -0.02 % | -0.04 | -20.4 % | +1.2 |
| DOGEUSDT | 2017-2021 | 2859 | +0.21 % | +0.34 | -11.8 % | +1.7 |
| DOGEUSDT | 2022-2026 | 6396 | -0.14 % | -0.23 | -20.4 % | +0.3 |
| EOSUSDT | 2017-2026 | 8953 | +0.10 % | +0.14 | -31.4 % | +2.4 |
| EOSUSDT | 2017-2021 | 4415 | +0.68 % | +0.87 | -10.4 % | +4.7 |
| EOSUSDT | 2022-2026 | 4538 | -0.51 % | -0.88 | -31.4 % | -2.3 |
| FILUSDT | 2017-2026 | 7892 | +0.45 % | +0.65 | -8.0 % | +4.7 |
| FILUSDT | 2017-2021 | 1456 | +1.96 % | +2.19 | -3.8 % | +5.5 |
| FILUSDT | 2022-2026 | 6436 | +0.10 % | +0.15 | -8.0 % | +2.0 |
| LTCUSDT | 2017-2026 | 11789 | +0.15 % | +0.20 | -35.2 % | +3.0 |
| LTCUSDT | 2017-2021 | 5219 | +0.52 % | +0.67 | -16.1 % | +3.7 |
| LTCUSDT | 2022-2026 | 6570 | -0.17 % | -0.25 | -25.3 % | +0.4 |
| NEARUSDT | 2017-2026 | 8614 | +0.01 % | +0.02 | -19.8 % | +1.9 |
| NEARUSDT | 2017-2021 | 1677 | +0.13 % | +0.20 | -12.3 % | +1.9 |
| NEARUSDT | 2022-2026 | 6937 | -0.01 % | -0.02 | -19.8 % | +1.1 |
| SOLUSDT | 2017-2026 | 8994 | +0.03 % | +0.04 | -15.1 % | +1.8 |
| SOLUSDT | 2017-2021 | 2003 | +0.12 % | +0.20 | -9.9 % | +1.1 |
| SOLUSDT | 2022-2026 | 6991 | +0.00 % | +0.01 | -15.1 % | +1.4 |
| UNIUSDT | 2017-2026 | 8671 | -0.09 % | -0.14 | -24.8 % | +0.0 |
| UNIUSDT | 2017-2021 | 1756 | -0.14 % | -0.24 | -8.0 % | +0.0 |
| UNIUSDT | 2022-2026 | 6915 | -0.08 % | -0.12 | -18.1 % | +0.0 |
| XLMUSDT | 2017-2026 | 11466 | +0.14 % | +0.19 | -28.2 % | +3.1 |
| XLMUSDT | 2017-2021 | 4897 | +0.16 % | +0.22 | -14.6 % | +2.2 |
| XLMUSDT | 2022-2026 | 6569 | +0.13 % | +0.18 | -17.5 % | +2.1 |
| XRPUSDT | 2017-2026 | 10594 | +0.68 % | +0.83 | -12.9 % | +6.3 |
| XRPUSDT | 2017-2021 | 4390 | +1.01 % | +1.34 | -8.0 % | +6.8 |
| XRPUSDT | 2022-2026 | 6204 | +0.42 % | +0.50 | -12.9 % | +3.1 |

Compte FTMO BTC + ETH :

| période | %/mois | baisse max | pire jour | challenges réussis / morts | jumeaux | durée médiane (jours tradés) |
|---|---|---|---|---|---|---|
| 2017-2026 | +1.48 % | -13.4 % | -3.1 % | 88 % / 0 % | 0 % / 46 % | 216.0 |
| 2017-2021 | +1.82 % | -12.1 % | -3.1 % | 63 % / 0 % | 0 % / 51 % | 147.0 |
| 2022-2026 | +1.17 % | -13.4 % | -3.1 % | 77 % / 0 % | 0 % / 11 % | 303.5 |

Groupe B (confirmation) : PAS ENCORE OUVERT — `python -m collapsar.regarder.pistes.cassure_v3 confirmation`, une seule fois, à la demande du coordinateur.

Amélioration 7 (COLLAPSAR aux commandes) : laissée à l'autre agent ; `cassure_v3.faits_signaux(reglages)` rend pour chaque signal les faits connus à l'entrée.

Prudence : tout ce développement a déjà été regardé ; seul le groupe B et la démo diront si ces gains tiennent.

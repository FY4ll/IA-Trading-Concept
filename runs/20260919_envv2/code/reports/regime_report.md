# Rapport par régime et expériences de filtres (2026-10-05 13:52)


## H1

- **pre_lockbox** : Sharpe 0.75 | rendement +41.2% | DD 22.2% | 150 trades | Challenge FTMO 48% | pire jour -5.0%
- **lockbox** : Sharpe 0.66 | rendement +45.8% | DD 37.0% | 628 trades | Challenge FTMO 52% | pire jour -7.0%
- baseline **buy_hold** (lockbox) : Sharpe 1.15 | rendement +109.1% | DD 28.8% | Challenge FTMO 65%
- baseline **trend_sma20_50** (lockbox) : Sharpe 0.81 | rendement +64.2% | DD 20.0% | Challenge FTMO 56%

| Lockbox, entrée en | trades | gain % | rendement moyen |
|---|---|---|---|
| vol_class=EXTREME | 32 | 22% | -0.221% |
| vol_class=HIGH | 98 | 41% | +0.281% |
| vol_class=LOW | 195 | 25% | -0.065% |
| vol_class=NORMAL | 303 | 26% | +0.065% |
| regime=RANGE | 337 | 23% | -0.111% |
| regime=TRANSITION | 210 | 34% | +0.296% |
| regime=TREND_DOWN | 40 | 40% | +0.150% |
| regime=TREND_UP | 41 | 17% | -0.077% |

- filtre `{"block_vol_classes": ["EXTREME"]}` : **REJETÉ** (pre_lockbox : Sharpe 0.68 < base 0.75)
  - pre_lockbox : Sharpe 0.68 | rendement +35.5% | DD 22.2% | 116 trades | Challenge FTMO 47% | pire jour -5.0%
  - lockbox : Sharpe 0.69 | rendement +49.2% | DD 35.8% | 597 trades | Challenge FTMO 53% | pire jour -7.0%

- filtre `{"block_vol_classes": ["HIGH", "EXTREME"]}` : **REJETÉ** (pre_lockbox : Sharpe 0.65 < base 0.75; lockbox : Sharpe 0.60 < base 0.66)
  - pre_lockbox : Sharpe 0.65 | rendement +33.7% | DD 22.5% | 84 trades | Challenge FTMO 46% | pire jour -5.0%
  - lockbox : Sharpe 0.60 | rendement +39.2% | DD 36.1% | 508 trades | Challenge FTMO 53% | pire jour -7.0%

## H1T

- **pre_lockbox** : Sharpe 0.89 | rendement +48.7% | DD 24.3% | 173 trades | Challenge FTMO 51% | pire jour -3.7%
- **lockbox** : Sharpe 0.68 | rendement +38.3% | DD 29.2% | 479 trades | Challenge FTMO 49% | pire jour -6.2%
- baseline **buy_hold** (lockbox) : Sharpe 1.15 | rendement +109.1% | DD 28.8% | Challenge FTMO 65%
- baseline **trend_sma20_50** (lockbox) : Sharpe 0.81 | rendement +64.2% | DD 20.0% | Challenge FTMO 56%

| Lockbox, entrée en | trades | gain % | rendement moyen |
|---|---|---|---|
| vol_class=EXTREME | 24 | 38% | -0.352% |
| vol_class=HIGH | 100 | 30% | +0.173% |
| vol_class=LOW | 100 | 24% | -0.061% |
| vol_class=NORMAL | 255 | 33% | +0.115% |
| regime=RANGE | 271 | 27% | -0.032% |
| regime=TRANSITION | 134 | 37% | +0.221% |
| regime=TREND_DOWN | 61 | 38% | +0.047% |
| regime=TREND_UP | 13 | 23% | +0.637% |

- filtre `{"block_vol_classes": ["EXTREME"]}` : **REJETÉ** (pre_lockbox : Sharpe 0.81 < base 0.89)
  - pre_lockbox : Sharpe 0.81 | rendement +41.8% | DD 22.9% | 159 trades | Challenge FTMO 48% | pire jour -3.7%
  - lockbox : Sharpe 0.89 | rendement +54.2% | DD 23.9% | 469 trades | Challenge FTMO 52% | pire jour -6.2%

- filtre `{"block_vol_classes": ["HIGH", "EXTREME"]}` : **REJETÉ** (pre_lockbox : Sharpe 0.69 < base 0.89)
  - pre_lockbox : Sharpe 0.69 | rendement +33.5% | DD 21.2% | 135 trades | Challenge FTMO 43% | pire jour -5.0%
  - lockbox : Sharpe 0.79 | rendement +41.5% | DD 20.4% | 424 trades | Challenge FTMO 47% | pire jour -6.2%

## H1X

- **pre_lockbox** : Sharpe -0.13 | rendement -10.2% | DD 31.1% | 986 trades | Challenge FTMO 31% | pire jour -5.4%
- **lockbox** : Sharpe 0.74 | rendement +54.7% | DD 28.4% | 561 trades | Challenge FTMO 53% | pire jour -7.0%
- baseline **buy_hold** (lockbox) : Sharpe 1.15 | rendement +109.1% | DD 28.8% | Challenge FTMO 65%
- baseline **trend_sma20_50** (lockbox) : Sharpe 0.81 | rendement +64.2% | DD 20.0% | Challenge FTMO 56%

| Lockbox, entrée en | trades | gain % | rendement moyen |
|---|---|---|---|
| vol_class=EXTREME | 76 | 38% | -0.266% |
| vol_class=HIGH | 160 | 46% | +0.166% |
| vol_class=LOW | 33 | 27% | -0.046% |
| vol_class=NORMAL | 292 | 30% | +0.094% |
| regime=RANGE | 229 | 30% | -0.047% |
| regime=TRANSITION | 219 | 38% | +0.222% |
| regime=TREND_DOWN | 45 | 49% | +0.118% |
| regime=TREND_UP | 68 | 38% | -0.159% |

- filtre `{"block_vol_classes": ["EXTREME"]}` : **ACCEPTÉ** (toutes les conditions remplies)
  - pre_lockbox : Sharpe 0.01 | rendement -3.4% | DD 30.3% | 902 trades | Challenge FTMO 34% | pire jour -5.4%
  - lockbox : Sharpe 0.85 | rendement +66.9% | DD 25.7% | 494 trades | Challenge FTMO 57% | pire jour -7.0%

- filtre `{"block_vol_classes": ["HIGH", "EXTREME"]}` : **REJETÉ** (lockbox : drawdown 33.3% > base 28.4% + 1 pt)
  - pre_lockbox : Sharpe 0.39 | rendement +16.5% | DD 27.9% | 706 trades | Challenge FTMO 41% | pire jour -5.4%
  - lockbox : Sharpe 0.82 | rendement +60.6% | DD 33.3% | 356 trades | Challenge FTMO 57% | pire jour -7.0%

**Filtre adopté pour H1X : {"block_vol_classes": ["EXTREME"]}** (expérience a328a8969576).

Expériences enregistrées au total : 6.

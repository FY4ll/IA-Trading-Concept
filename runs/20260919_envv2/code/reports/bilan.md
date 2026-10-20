# Bilan du système (06/10/2026 11:52)

## Compte démo
- Équité **101 995.58 $**  solde 102 007.18 $
- H1T gen:229 : ACHAT 0.04 lot à 4155.15, stop 4124.52, objectif 4247.04, P&L -7.68 $
- H1 gen:838 : ACHAT 0.02 lot à 4155.19, stop 4091.43, objectif -, P&L -3.92 $
- Or : 4153.23

## Trades clôturés depuis 2026-10-06 00:00 : 5
- 2026-10-06 05:35:18 H1X : -346.28 $ (-1.02R, SL)
- 2026-10-06 06:00:52 H1 : -12.07 $ (-0.04R, IA)
- 2026-10-06 06:00:48 H1T : -33.48 $ (-0.10R, IA)
- 2026-10-06 12:01:38 H1T : +389.12 $ (+0.77R, IA)
- 2026-10-06 12:01:43 H1 : +143.52 $ (+0.29R, IA)

## Dernières décisions (heure UTC) et notes de trader
- 2026-10-06 09:01:46 H1X : ATTEND -- raison : exclusive_group:H1.
- 2026-10-06 09:01:43 H1 : garde sa position.
- 2026-10-06 09:01:40 H1T : garde sa position.
- 2026-10-06 09:00:59 H1X : ATTEND -- raison : exclusive_group:H1.
- 2026-10-06 09:00:58 H1 : garde sa position.
- 2026-10-06 09:00:57 H1T : garde sa position.
- 2026-10-06 08:00:12 H1X : ATTEND -- raison : exclusive_group:H1.
- 2026-10-06 08:00:09 H1 : garde sa position.

## Apprentissage d'AUREX
- Champion : génération 253, score 0.646, Sharpe 0.67, rendement validation +2.9%, drawdown 13.8%, 529 trades, éligible démo : non
- cycle 241 : 12 candidats, 1 positifs, meilleur score 0.355 (Sharpe 0.70, +3.2%, DD 21.4%)
- cycle 242 : 12 candidats, 3 positifs, meilleur score 0.265 (Sharpe 0.58, +2.9%, DD 21.2%)
- cycle 243 : 8 candidats, 0 positifs, meilleur score -0.096 (Sharpe 0.00, +0.0%, DD 0.0%, 0 trades)
- cycle 244 : 8 candidats, 0 positifs, meilleur score -0.091 (Sharpe 0.27, +1.4%, DD 20.4%, 337 trades)
- cycle 245 : 8 candidats, 2 positifs, meilleur score 0.434 (Sharpe 0.63, +3.2%, DD 22.3%, 15 trades)
- cycle 246 : 8 candidats, 0 positifs, meilleur score -0.091 (Sharpe 0.00, +0.0%, DD 0.0%, 0 trades)
- cycle 247 : 7 candidats, 0 positifs, meilleur score -0.701 (Sharpe -0.40, -0.6%, DD 10.0%, 1303 trades) -- champion rejoué : -0.010
- cycle 248 : 7 candidats, 1 positifs, meilleur score 0.119 (Sharpe 0.29, +0.7%, DD 10.9%, 241 trades) -- champion rejoué : -0.022
- cycle 249 : 7 candidats, 0 positifs, meilleur score -0.000 (Sharpe 0.46, +0.5%, DD 1.7%, 27 trades) -- champion rejoué : 0.093
- cycle 250 : 7 candidats, 2 positifs, meilleur score 0.079 (Sharpe 0.82, +1.0%, DD 4.5%, 89 trades) -- champion rejoué : 0.182
- cycle 251 : 7 candidats, 1 positifs, meilleur score 0.138 (Sharpe 0.28, +0.5%, DD 7.7%, 35 trades) -- champion rejoué : 0.182
- cycle 252 : 7 candidats, 1 positifs, meilleur score 0.158 (Sharpe 0.28, +0.5%, DD 7.1%, 40 trades) -- champion rejoué : 0.124
- cycle 253 : 7 candidats, 1 positifs, meilleur score 0.646 (Sharpe 0.67, +2.9%, DD 13.8%, 529 trades) -- champion rejoué : 0.110
- cycle 254 : 7 candidats, 0 positifs, meilleur score -0.405 (Sharpe -1.59, -0.9%, DD 3.1%, 119 trades) -- champion rejoué : 0.511
- cycle 255 : 7 candidats, 0 positifs, meilleur score -0.095 (Sharpe 0.00, +0.0%, DD 0.0%, 0 trades) -- champion rejoué : 0.789
- Lockbox (gén 253, depuis 2023-06-01) : Sharpe 1.06, +41.8%, DD 12.1%, 812 trades -> porte OK
- Lockbox en R : 803 trades, réussite 39%, +0.13 R/trade en moyenne
  - risque 0.25%/trade : +43% sur 40 mois, DD 5.4%, pire jour -0.8%, Challenge FTMO 14%
  - risque 0.50%/trade : +57% sur 40 mois, DD 11.5%, pire jour -1.6%, Challenge FTMO 46%
  - risque 1.00%/trade : +82% sur 40 mois, DD 25.0%, pire jour -3.2%, Challenge FTMO 64%

## Modifications appliquées
- 2026-10-06 06:25 config : OK : live.max_risk_pct_by_style AUREX 0.0035
- 2026-10-06 06:28 redémarré (logs stderr_0625.txt) : vivant=1, Traceback=0, warm starts réussis=8
- 2026-10-06 06:28 FIN
- 2026-10-06 10:23 attente des tests préparés (C:\Users\utilisateur\AppData\Local\Temp\claude\c--Users-utilisateur-Documents-Test-IA\f09ed3b3-c164-4391-9e5e-8ecc4a192738\scratchpad\stage_full_tests2.txt) et du cycle #255
- 2026-10-06 10:23 tests préparés : 463 passed in 1051.74s (0:17:31)
- 2026-10-06 11:01 config : OK : ftmo_ai per_trade 0.0025
- 2026-10-06 11:04 redémarré (logs stderr_1101.txt) : vivant=1, Traceback=0, warm starts réussis=8
- 2026-10-06 11:04 FIN

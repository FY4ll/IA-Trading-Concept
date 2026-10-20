# D'où viennent les données (aucune n'est republiée ici)

Le projet a utilisé uniquement des données publiques ou fournies par les plateformes. **Aucune donnée n'est incluse dans
ce dépôt** : elles appartiennent à leurs auteurs. Voici où les obtenir, sous leurs propres conditions d'utilisation.

## Prix de marché
| donnée | source | utilisée pour |
|---|---|---|
| Or (XAUUSD), bougies 1 min à 1 mois, 2004 -> 2026 | jeu de données Kaggle « XAUUSD » (9 fichiers 1m / 5m / 15m / 30m / 1H / 4H / 1D / 1W / 1M, séparateur « ; ») — chercher « XAUUSD gold historical data » sur https://www.kaggle.com/datasets (adresse exacte non notée dans le projet) | presque toutes les études sur l'or |
| ~45 marchés FTMO (devises, indices, métaux, énergies) en 15 min et 1 h | Dukascopy, flux historique public : https://www.dukascopy.com/swiss/english/marketwatch/historical/ (téléchargement par `runs/20260919_envv2/code/scripts/fetch_dukascopy.py`, `collapsar/donnees/telecharger_h1.py`) | marchés autres que l'or |
| Indices et euro-dollar à la minute | HistData : https://www.histdata.com/download-free-forex-historical-data/ (`collapsar/donnees/histdata.py`) | tests à la minute |
| Cryptos (comptant, contrats perpétuels, positions de la foule) | Binance, données publiques : https://data.binance.vision et https://fapi.binance.com/futures/data/ (`collapsar/donnees/binance_foule.py`) | pistes crypto, « contre la foule » |
| Cotations en direct | MetaTrader 5 (compte démo du courtier) | démo, relevés d'écarts |

## Données hors prix
| donnée | source |
|---|---|
| Taux d'intérêt, bilan de la Fed, compte du Trésor, pensions inversées | FRED / ALFRED (Réserve fédérale de Saint-Louis) : https://fred.stlouisfed.org (API : https://api.stlouisfed.org, clé gratuite personnelle) |
| Positions des opérateurs (COT, rapport « Traders in Financial Futures ») | CFTC : https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm |
| Dates et heures des décisions de la Fed | https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm et https://www.federalreserve.gov/monetarypolicy/fomchistorical.htm |
| Avoirs du fonds d'or GLD | SPDR Gold Shares : https://www.spdrgoldshares.com |
| Indices de peur (VIX, VVIX, OVX, GVZ) | Cboe : https://www.cboe.com/tradable_products/vix/vix_historical_data/ |
| Risque géopolitique (GPR), incertitude (EPU) | https://www.matteoiacoviello.com/gpr.htm , https://www.policyuncertainty.com |
| Calendrier économique | MetaTrader 5 (calendrier intégré) |
| Trades publics de plateformes sur chaîne (pistes « maîtres ») | gTrade https://docs.gains.trade , Hyperliquid https://api.hyperliquid.xyz , Ostium (sous-graphe public), Synthetix |

## Conditions de trading
Les conditions FTMO (écarts, frais de nuit, leviers) ont été relevées sur un compte d'essai FTMO avec MetaTrader 5 et ne
sont pas republiées. Les règles officielles : https://ftmo.com/en/trading-objectives/ et
https://ftmo.com/en/forbidden-trading-practices/ (résumé vérifié : `docs/FTMO_REGLES_VERIFIEES.md`). Le simulateur
(`core/ftmo/`) attend un fichier `core/ftmo/conditions_ftmo.json` produit par votre propre relevé.

## Retiré de cette copie publique
- les conditions de trading relevées chez FTMO et chez le courtier (données de ces sociétés) ;
- le code source Pine d'un indicateur de zones d'offre et de demande (supply and demand) et sa traduction fidèle en Python (code d'un tiers) : les modules qui
  l'importent ne s'exécutent donc pas tels quels ;
- les données de marché, modèles entraînés, états, journaux, accès et clés.

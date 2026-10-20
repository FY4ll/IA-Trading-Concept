# Convention pour déposer les données d'une nouvelle paire

Mis à jour après le LOT 2 (phase 4) : le pipeline multi-actifs est désormais
câblé (`src/multi_asset.py`, `continuous_trainer.py` — panier d'entraînement,
veto de stabilité par symbole) mais **désactivé par défaut**
(`multi_asset.enabled: false` dans `config/autonomous.yaml`) tant qu'il n'est
pas explicitement activé. Ce document reste la référence pour le FORMAT des
données déposées.

## Paires déjà présentes

| Paire | Dossier | Source | Licence | Période | Timeframes |
|---|---|---|---|---|---|
| XAUUSD (or) | `data/kaggle_gold/` | dataset Kaggle "XAUUSD Gold Price Historical Data" | voir Kaggle | 2004-2026 | M1 à MN1 |
| EURUSD | `data/kaggle_eurusd/` | [ejtraderLabs/historical-data](https://github.com/ejtraderLabs/historical-data) (GitHub) | Apache-2.0 | 2012-12-04 → 2022-03-04 (~9.25 ans) | M15, M30, H1, H4, D1 |
| GBPUSD | `data/kaggle_gbpusd/` | idem | Apache-2.0 | idem | idem |
| USDJPY | `data/kaggle_usdjpy/` | idem | Apache-2.0 | idem | idem |

EURUSD/GBPUSD/USDJPY : téléchargées le 19/09/2026 directement depuis
`raw.githubusercontent.com` (pas besoin de compte/API), chargement vérifié
avec `src/data_loader.py::load_kaggle_ohlcv_csv` et
`src/multi_timeframe.py::verify_timeframe_assignment` (toutes les
timeframes correctement détectées, aucun NaN). **Pas de M1/W1/MN1
disponibles pour ces 3 paires** (contrairement à l'or) : un style D1 sur
ces paires n'aura donc aucun contexte multi-timeframe plus large (W1/MN1),
ce que le pipeline gère déjà proprement (liste de contexte vide, pas
d'erreur) — juste moins de features que pour l'or.

**Autres paires disponibles à la même source** (non téléchargées, mêmes
caractéristiques) : AUDJPY, AUDUSD, EURCHF, EURGBP, EURJPY, GBPJPY, USDCAD,
USDCHF.

## 1. Un dossier par paire

`data/kaggle_<paire>/` (minuscules, sans espace), même schéma que
`data/kaggle_gold/`. **Ne mélange jamais deux instruments dans le même
dossier** (`discover_files` associe par motif de timeframe dans le nom de
fichier, sans distinguer l'instrument — un dossier partagé fait "gagner"
silencieusement le premier fichier trouvé par timeframe).

## 2. Un fichier CSV par timeframe

| Timeframe | Motifs reconnus dans le nom de fichier |
|---|---|
| M1  | `1m`, `1min`, `m1` |
| M5  | `5m`, `5min`, `m5` |
| M15 | `15m`, `15min`, `m15` |
| M30 | `30m`, `30min`, `m30` |
| H1  | `1h`, `h1`, `60m` |
| H4  | `4h`, `h4`, `240m` |
| D1  | `1d`, `d1`, `daily` |
| W1  | `1w`, `w1`, `weekly` |
| MN1 | `1mo`, `1mn`, `mn1`, `monthly`, `1month` |

## 3. Format du CSV

Le chargeur (`load_kaggle_ohlcv_csv`) est tolérant : séparateur `,`/`;`/tab
auto-détecté, colonnes OHLCV insensibles à la casse, volume optionnel
(0 si absent), horodatage en une colonne (`Date`/`Time`/`Datetime`) ou deux
colonnes séparées (format MT4/MT5).

## 4. Activer le multi-actifs (LOT 2, phase 4)

Dans `config/autonomous.yaml` :
```yaml
multi_asset:
  enabled: true
  symbols:
    EURUSD: "data/kaggle_eurusd"
    GBPUSD: "data/kaggle_gbpusd"
    USDJPY: "data/kaggle_usdjpy"
```
Un dossier configuré mais absent/vide est ignoré proprement (pas d'erreur,
voir `discover_configured_symbols`). Avec `enabled: false` (défaut), rien
ne change par rapport à l'entraînement or seul actuel.

## 5. Pour utiliser une seule paire à la place de l'or (comportement historique)

Change `data.folder` (ex: `"data/kaggle_eurusd"`) — **remplace**
l'instrument entraîné, ne s'ajoute pas à l'or. Différent du multi-actifs
ci-dessus (qui entraîne l'or ET les autres paires ensemble, dans un panier).

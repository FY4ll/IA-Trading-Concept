# Handover guide — taking over IA Trading Concept

This guide is for anyone who wants to continue, reuse or audit this project without its author. Read it before the
code. Most code comments and reports are in French; the glossary at the end maps the key terms.

## 1. Project status

- **Research stopped on 2026-10-20.** Nothing runs any more (no training, no live demo). The repository is a frozen
  record plus reusable tools.
- **Main result:** 111 ideas, ~117,500 variants, 0 edge that survives FTMO costs on unseen data
  (`etudes/REGISTRE_IDEES.csv`).
- **What is worth reusing:** the validation tooling (`core/`, `cerveau/mesure/`), the study discipline (`etudes/`), and
  the registry of failed ideas so you don't repeat them.
- **Standalone spin-off:** the judge, extracted as a simple tool for anyone's trade history:
  [ProveIt](https://github.com/FY4ll/ProveIt). If you only want to test a strategy, start there.

## 2. Map: what is active and what is archive

| Path | Status | Use it for |
|---|---|---|
| `core/` | **active, tested** | data loading (`donnees.py`), FTMO account simulator (`ftmo/`), random twin (`jumeau.py`), interest rates (`taux.py`), MT5 demo connector (`mt5.py`, Windows only) |
| `cerveau/` | **active, tested** | module registry (`socle.py`), perception modules, measurement: trades → judges (`mesure/`), multi-market portfolio |
| `etudes/` | **active** | one folder per study (frozen plan, script, results, report) + the idea registry + manual replay protocol |
| `tests/` | **active** | tests on synthetic data, no market data needed |
| `usine/` | design only | role-based research pipeline (journalist, scientist, worker, judge, manager, operator); never ran a full batch |
| `collapsar/` | archive, partly runnable | 3rd generation (pretraining, synthetic markets, tree of brains), audits, research tracks |
| `archive/magnetar/` | archive | MAGNETAR and HYPERNOVA |
| `runs/`, `archives/`, `aurexis/` | archive, not maintained | earlier generations; `aurexis` tests are known to be broken |
| `docs/` | reference | audit, architecture, research history, validation protocol, verified FTMO rules, data sources |
| `research_notes/`, `reports/` | reference | literature notes |

Rule of thumb: build on `core/` + `cerveau/` + `etudes/`. Read the rest, do not extend it.

## 3. Setting up the data

No market data is shipped. To run the data-dependent tests and the studies, provide:

| File | Format |
|---|---|
| `data/fx_intraday/<SYMBOL>_M15.csv` | 15-minute bars, columns `time,open,high,low,close,volume`, `time` parseable by pandas, **MetaTrader server time (New York + 7 h)** |
| `data/kaggle_gold/XAU_15m_data.csv` | gold 15-minute bars, `;` separator, columns `Date;Open;High;Low;Close;Volume`, date format `%Y.%m.%d %H:%M` |
| `data/kaggle_gold/XAU_1m_data.csv` | gold 1-minute bars, same format (only for minute-level studies) |
| `core/ftmo/conditions_ftmo.json` | measured broker spreads: `{"marches": {"<name>": {"ecart_pct": <spread in % of price>}}}`. Measure them yourself on a demo account; the author's file is not published (broker data) |

Sources and links: `docs/SOURCES_DES_DONNEES.md`. Swaps use monthly 3-month interest rates in
`data/taux/<CURRENCY>.csv`; `core/taux.py` downloads them from FRED with an API key read from the Run A config file
(`fred.api_key` in `runs/20260919_envv2/run_config_A.yaml`, git-ignored). Create that file with your own free FRED key,
or place the CSV files yourself. Never commit a key.

After setup, `pytest` should report fewer skipped tests. Tests that still skip need a dataset you did not provide.

## 4. Running a new study

1. Check `etudes/REGISTRE_IDEES.csv`: if the idea (or a close variant) is there, you need a new, falsifiable reason
   to test it again.
2. Create `etudes/<YYYY-MM-DD>_<name>/PLAN_FIGE.md` from [`docs/TEMPLATE_PLAN_FIGE.md`](TEMPLATE_PLAN_FIGE.md).
   **Commit it before computing anything.**
3. Write the script (`mesurer.py`), reusing `core.ftmo` for costs, `core.jumeau` / `cerveau.mesure.juges` for the
   benchmarks. Load data only up to 2023-12-31: the vault (2024-01-01 → 2026-10-13) stays closed.
4. Run it **once**. If you find a measurement bug afterwards, fix it, declare it in the plan as an amendment, and rerun
   once; keep both runs.
5. Write `RAPPORT.md` (numbers, uncertainty, verdict) and add a line to the registry, success or failure.

The protocol in full: `docs/VALIDATION_PROTOCOL.md`. Good examples: `etudes/2026-10-20_competition1/` and
`etudes/2026-10-20_couche1_tendance/`.

## 5. Known issues

- `aurexis/` tests fail (missing modules after a 2026-10-08 cleanup). Archived; do not fix unless you need it.
- The code of a third-party supply and demand indicator was removed for licensing reasons. Modules that imported it
  (`cerveau/perception/detecteur.py`, several `collapsar/regarder/` and `collapsar/audit/` scripts, `archive/magnetar/
  ecole_precision/structure.py`) do not run as is. Their reports remain valid as records.
- Some archived scripts still contain the author's Windows paths, anonymised as `C:\Users\utilisateur\...`: adapt
  them or use relative paths.
- `cerveau/` has no risk/veto layer yet: it is required before any live use of the brain.
- The FTMO simulator models FTMO Swing/Normal accounts as of October 2026. Prop-firm rules change: re-check
  `docs/FTMO_REGLES_VERIFIEES.md` against the official pages.
- The MT5 connector is demo-only by design. There is no code path to a real account, and there should not be one
  without a validated edge.

## 6. Open threads (where to pick up)

| Thread | State | File |
|---|---|---|
| Manual replay: does a human eye beat the twin? | protocol ready, 0 trades logged | `etudes/replay_manuel/PROTOCOLE.md` |
| Contrarian crowd positioning (Binance) | real signal before costs, needs an exchange-cost venue | `docs/FICHE_C1_CONTRE_LA_FOULE.md` |
| Non-price data (CFTC COT, FRED, ETF flows, macro surprises) | loaders started, no batch run | `cerveau/donnees_hors_prix/`, `usine/` |
| Volatility → direction link on gold (safe-haven effect) | idea only | — |
| Real FTMO costs at every hour | measurement script ready | `etudes/2026-10-20_frais_ftmo_reels/` |

## 7. Glossary (French → English)

| Term | Meaning |
|---|---|
| jumeau (au hasard) | random twin: same trades, direction drawn by coin flip |
| acheteur permanent | permanent buyer: buy-and-hold benchmark |
| coffre | vault: sealed final holdout, opened once per idea |
| plan figé | frozen plan: pre-registered study design |
| verrou | lock file proving a study ran once on a committed plan |
| registre | registry of every idea tested |
| force | t-statistic of the edge over a benchmark |
| frais de nuit | swaps / overnight financing |
| mur (du jour / total) | prop-firm loss limit (daily −5% / total −10%) |
| avis | opinion emitted by a perception module (direction, confidence, levels) |
| étude / rapport | study / report |
| sans futur | no look-ahead |
| chef de projet | project owner (the original author) |

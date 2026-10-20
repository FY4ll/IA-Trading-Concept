# IA Trading Concept — searching for a trading edge with AI, under strict validation

*[Version française](README.fr.md)*

Six weeks of research (Sept. 15 – Oct. 20, 2026) on a home-built trading AI for gold (XAUUSD) and other FTMO markets.
Every candidate was judged with pre-registered frozen plans, a sealed holdout, matched random-direction placebos, a
buy-and-hold benchmark, realistic prop-firm costs and multiple-testing correction.

**Result: 111 ideas and ~117,500 variants tested. None showed an edge that survives costs on unseen data.**

This repository is published as a **negative result** and as a **reusable validation framework**: a test bench to
check, honestly, whether a trading strategy is better than chance.

> ⚠️ Research project. No strategy in this repository is profitable. Nothing here is investment advice.

---

## Results

| | |
|---|---|
| Research period | 2026-09-15 → 2026-10-20 |
| Ideas tested | **111** (full registry, failures included: [`etudes/REGISTRE_IDEES.csv`](etudes/REGISTRE_IDEES.csv)) |
| Variants evaluated | ~**117,500** |
| Ideas with an edge that survives costs on unseen data | **0** |
| Only real information found | contrarian positioning of Binance accounts (t ≥ 3 before costs), killed by FTMO costs ([sheet](docs/FICHE_C1_CONTRE_LA_FOULE.md)) |

## What was tested

| Approach | Method | Verdict on unseen data |
|---|---|---|
| One agent per timeframe (D1 → M15) | PPO + LSTM, evolutionary selection | No better than a coin flip; −6.2% in 33 h on a live demo |
| AUREX / AUREXIS | PPO, 45 markets, mirrored markets | Gains came from buying 100% of the time in a rising gold market; loses on 2010-2017 |
| COLLAPSAR | self-supervised pretraining then RL; tree of brains (population-based training); synthetic markets | ≈ 50.8% correct direction; ≈ 0 R per trade |
| Supervised trade judge | 6.4 M candidate trades, calibrated probabilities | Top 1%: 26.7% of trades reach 2R vs 27.3% needed |
| Supply and demand zones | frozen rules: volume profile, 2nd touch, FVG, opposite zone | No timeframe beats both benchmarks; M15 loses after costs |
| MAGNETAR | 4 brains, population-based training | −0.52%/month vs −0.70 for its twin: not significant |
| Time-series momentum 1/3/6/12 months | volatility-targeted sizing | Never beats buy-and-hold; not robust on 5 other markets |
| Competitions 1 and 2 | intraday momentum, opening gap, FX reversal, relative momentum, linear model, managed volatility | 0 out of 6 |
| Published methods and known effects | NY opening-range breakout, noise-area momentum (Zarattini et al. 2024), calendar effects, buy-the-dip, Bitcoin 24 h breakout… | All dead after costs or on their holdout |

Details: [`docs/RESEARCH_HISTORY.md`](docs/RESEARCH_HISTORY.md) and
[`docs/Rapport_technique_2026-10-17.md`](docs/Rapport_technique_2026-10-17.md) (in French).

## Validation protocol

The core of the project, described in [`docs/VALIDATION_PROTOCOL.md`](docs/VALIDATION_PROTOCOL.md).

- **Frozen plan before computing.** Each test has a `PLAN_FIGE.md` committed to git before any measurement.
- **Sealed vault.** 2024-01-01 → 2026-10-13 is never loaded by research code (refused at the data-loader level).
- **Two mandatory benchmarks:**
  - a **random twin** that copies every action (timing, size, stop, order type) but draws the direction at random
    (matched placebo, several seeds) — [`core/jumeau.py`](core/jumeau.py);
  - a **permanent buyer** with constant volatility.
- **Real FTMO costs:** spread, commission, swaps by era (triple night on the right weekday), leverage, −5%/day and
  −10% total limits checked at the worst point of each bar, 30-day inactivity rule. Rules checked against the official
  pages: [`docs/FTMO_REGLES_VERIFIEES.md`](docs/FTMO_REGLES_VERIFIEES.md).
- **Multiple testing:** strength threshold `max(3, sqrt(2·ln N))`, N = total attempts in the registry.
- **Engine sanity checks:** a strategy that knows the future must win massively, randomness must lose exactly the
  costs, buy-and-hold must return the price minus costs.

Measurement bugs caught by this protocol (each fixed and covered by a test): timestamps read in microseconds instead
of nanoseconds; a US CPI release dated the evening before in a public dataset (a spectacular fake edge); swaps
missing on 36% of nights; a twin's stop triggered by a price printed before entry.

## Findings

1. **Memorization is problem #1.** 69–99% correct direction on training years, 52% on unseen years. Markets provide
   about 100,000 independent situations, not millions.
2. **Specification gaming.** RL agents optimize the metric, not the intent: they collapse into inaction when the
   reward is too noisy (noise ≈ 400× the per-bar edge), bet everything when the network has memorized the future, and
   always buy when the market rises.
3. **Beating zero proves nothing.** On gold 2018-2026 almost anything that buys makes money; only the comparison with
   the permanent buyer and the random twin is informative.
4. **Costs decide.** FTMO swaps of 3–8%/year on gold (≈ 30%/year on crypto) and the inactivity rule kill most small
   edges.
5. **Volatility is predictable, direction is not.** 58–80% of volatility variance is explained; direction tops out
   around 51%.

## Quick start

Developed on Windows, Python 3.11, PyTorch CUDA, GTX 1060 6 GB, 16 GB RAM.

```bash
git clone https://github.com/FY4ll/IA-Trading-Concept.git
cd IA-Trading-Concept
python -m venv venv
venv\Scripts\activate            # Linux / macOS: source venv/bin/activate
pip install -r requirements.txt  # + requirements-archives.txt for older generations
pytest                           # tests/ runs on synthetic data; tests needing market data are skipped
```

[`tests/test_protocole_sans_donnees.py`](tests/test_protocole_sans_donnees.py) shows the protocol on synthetic prices:
a cheater crushes its twin, a blind strategy does not, and "always buy" in a rising market shows no skill against
buy-and-hold.

Market data is not included (provider rights). Sources and official links:
[`docs/SOURCES_DES_DONNEES.md`](docs/SOURCES_DES_DONNEES.md) (Dukascopy, HistData, Binance, FRED, CBOE, MetaTrader
calendar). The simulator expects a `core/ftmo/conditions_ftmo.json` produced from your own broker measurements.

## Repository layout

| Folder | Content |
|---|---|
| [`core/`](core/) | FTMO account simulator, data loading, random twin, rates, MetaTrader 5 connector (demo) |
| [`cerveau/`](cerveau/) | Modular architecture (perception, measurement, judges), multi-market portfolio, challenge simulator |
| [`etudes/`](etudes/) | One study = `PLAN_FIGE.md` + script + `resultats/` + `RAPPORT.md`; idea registry; manual replay protocol |
| [`usine/`](usine/) | Role-based research pipeline (journalist, scientist, worker, judge, manager, operator) |
| [`collapsar/`](collapsar/) | 3rd generation: pretraining, synthetic-market school, tree, audits |
| [`archive/magnetar/`](archive/magnetar/), [`archives/`](archives/), [`runs/`](runs/), [`aurexis/`](aurexis/) | Earlier generations and their reports (archived, not always runnable) |
| [`docs/`](docs/) | Audit, architecture, history, protocol, FTMO rules, data sources |
| [`tests/`](tests/) | Tests that run without any data |

Most documentation and code comments are in **French**. Translations are welcome.

## Taking over the project

Research stopped on 2026-10-20. Everything needed to continue it without the author is in
[`docs/HANDOVER.md`](docs/HANDOVER.md): what is active vs archived, data setup, how to run a study, known issues,
open threads and a French → English glossary. Study template: [`docs/TEMPLATE_PLAN_FIGE.md`](docs/TEMPLATE_PLAN_FIGE.md).

To simply test a strategy on your own trade history, use the standalone judge
[ProveIt](https://github.com/FY4ll/ProveIt).

## Contributing

Contributions are welcome, especially new hypotheses run through the protocol, data download scripts, and
translations. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/GOOD_FIRST_ISSUES.md`](docs/GOOD_FIRST_ISSUES.md).

A negative result is a valid contribution: if your idea fails the protocol, it goes into the registry like the 111
others.

## Not included

Market data, trained models, training states, logs, credentials and keys, broker conditions, and the code of a
third-party supply and demand indicator (the modules that used it do not run as is).

## Credits

Design, research direction and decisions: **F4ll_**. Code written with the
[Claude Code](https://claude.com/claude-code) assistant (Anthropic), used as a development tool. The trading models
run locally and never call a language model to make decisions.

## License

[MIT](LICENSE)

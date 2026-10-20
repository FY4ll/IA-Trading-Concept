# Contributing

Thanks for your interest. This project is a **test bench for trading ideas**: the goal is not to make a strategy look
good, but to find out whether it is better than chance. Contributions in French or English are both fine.

## Ways to contribute

1. **Submit a hypothesis.** Open an issue with the *Hypothesis* template: the idea, the economic reason it could
   work, the data it needs, and why it is not already in [`etudes/REGISTRE_IDEES.csv`](etudes/REGISTRE_IDEES.csv).
2. **Run a hypothesis through the protocol** (see below) and open a pull request with the study, whatever the result.
3. **Infrastructure:** data download scripts, synthetic-data tests, faster simulation, packaging.
4. **Translations** of documents and reports from French to English.
5. **Bug reports**, especially anything that could leak future information into a test (look-ahead bias).

Good starting points: [`docs/GOOD_FIRST_ISSUES.md`](docs/GOOD_FIRST_ISSUES.md).

## The rules of a study

Every study lives in `etudes/<YYYY-MM-DD>_<name>/` and follows the protocol in
[`docs/VALIDATION_PROTOCOL.md`](docs/VALIDATION_PROTOCOL.md):

1. **Write `PLAN_FIGE.md` first** (frozen plan): exact rules, parameters, data, periods, benchmarks and acceptance
   criteria. **Commit it before running anything.** A plan cannot be changed after seeing a result; a new idea is a
   new study.
2. **No future information.** Every feature must be available at the simulated decision time, using the
   *publication* date of the data, not the measurement date. Add a test that truncates the data at time *t* and checks
   the signal is unchanged.
3. **Never touch the vault** (2024-01-01 → 2026-10-13). It is opened once per idea, only for ideas that already passed
   the test period.
4. **Compare against both benchmarks:** the random twin ([`core/jumeau.py`](core/jumeau.py), several seeds) and the
   permanent buyer. Beating zero is not enough.
5. **Use realistic costs** (spread, commission, swaps, FTMO limits) and report results after costs.
6. **Count your attempts.** Report how many variants you tried; the strength threshold is `max(3, sqrt(2·ln N))`.
7. **Write `RAPPORT.md`** with the numbers, uncertainties and verdict, and add a line to the registry.

**Negative results are welcome and are merged like positive ones.**

## Code

- Python 3.11, `pip install -r requirements.txt`, run `pytest` before opening a pull request.
- Tests in `tests/` must run without market data (use synthetic prices).
- Never commit data, models, credentials, broker account details or `.env` files.
- Keep changes small and focused; one study or one feature per pull request.

## Conduct

Be respectful and precise. Criticism of methods is welcome; criticism of people is not.

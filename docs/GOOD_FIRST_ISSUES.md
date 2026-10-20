# Good first issues

Ready-to-open issues for new contributors. Each one is small and self-contained.

## 1. Data download script for gold (Dukascopy)
Write `scripts/telecharger_or.py` that downloads XAUUSD 15-minute bars from Dukascopy (or another free source listed in
[`docs/SOURCES_DES_DONNEES.md`](SOURCES_DES_DONNEES.md)) into the format expected by `core/donnees.py`, so that the
skipped tests can run. *Skills: Python, HTTP, pandas.*

## 2. Example broker conditions file
Create `core/ftmo/conditions_ftmo.example.json` with clearly labelled **illustrative** spreads, and document how to
measure your own from a MetaTrader 5 demo account. *Skills: JSON, MetaTrader 5.*

## 3. Translate the validation protocol to English
Translate [`docs/VALIDATION_PROTOCOL.md`](VALIDATION_PROTOCOL.md) into `docs/VALIDATION_PROTOCOL.en.md`.
*Skills: French, English.*

## 4. More synthetic sanity tests
Extend [`tests/test_protocole_sans_donnees.py`](../tests/test_protocole_sans_donnees.py): e.g. show that testing 1,000
random strategies and keeping the best one produces a fake "edge" that the `max(3, sqrt(2·ln N))` threshold rejects.
*Skills: Python, statistics.*

## 5. Run a new hypothesis through the protocol
Pick an idea that is **not** in [`etudes/REGISTRE_IDEES.csv`](../etudes/REGISTRE_IDEES.csv) (for example a link between
predicted volatility and gold direction, as a safe-haven asset), write the frozen plan, and run it. Any result is a
valid contribution. *Skills: Python, finance basics.*

# <Study name> — frozen plan (written <YYYY-MM-DD>, BEFORE any measurement)

Commit this file before running anything. Never edit it after seeing a result: a change is an amendment (dated,
explained) or a new study.

## Question
One sentence.

## Hypothesis and mechanism
What should happen, and the economic reason (who loses money to whom).

## Not already tested because
Registry lines checked (`etudes/REGISTRE_IDEES.csv`), and what is different here.

## Data
Markets, frequency, source, **publication delay** of every non-price input.

## Periods
- Research: <start> → <end>
- Validation: <start> → <end>
- Vault (2024-01-01 → 2026-10-13): closed.

## Exact rules
Entry, exit, direction, size (default: volatility-targeted, 10%/year), stop, timing in MetaTrader server time.
No parameter is fitted on validation or vault data.

## Benchmarks
- Random twin (≥ 10 seeds).
- Permanent buyer (same market, same risk).
- Other if relevant (random timing, random asset).

## Costs
FTMO costs from `core.ftmo` (spread, commission, swaps by era). Sensitivity: spread × 1.5.

## Acceptance criteria
- Net gain > 0 on each period.
- Edge over each benchmark > threshold: max(2, sqrt(2·ln M)) × uncertainty, M = number of comparisons.
- Minimum number of observations: <n>, otherwise "inconclusive".
- Robustness markets: <list>.

## What would refute it
Concrete outcomes.

## Number of variants tried
<n> (count every variant, including abandoned ones).

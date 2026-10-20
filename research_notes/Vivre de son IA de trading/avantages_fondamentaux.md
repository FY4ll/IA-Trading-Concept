# Avantages "fondamentaux / information" encore vivants en 2024-2026 pour un trader particulier sur CFD (FTMO)

Note on sourcing: items marked [web] were read in this session (search snippet or fetched page). Items marked [bg] come from
well-known published papers cited from background knowledge; the link points to the primary paper but the page was NOT
re-read in this session, so numbers tagged [bg] should be double-checked before being quoted as exact.
Cost reference used throughout (given by the coordinator): FTMO round trip ~0.006 % EURUSD, ~0.008-0.012 % US indices/gold,
crypto ~0.066 % + ~30 %/yr overnight; FX/index swap markup ~1.5-4 %/yr.

## 1. Post-earnings announcement drift (PEAD), revisions drift — still present in large caps after 2015?

### Takeaway
No, not in large caps. The best current evidence (Martineau 2022; Subrahmanyam 2025 reconciliation) says PEAD has been
non-existent in large stocks since about 2006 and survives only in microcaps (bottom 20 % by size, ~3 % of market value) —
exactly the stocks that are NOT offered as CFDs at FTMO. Dead for this use case.

### Cited Findings
- Martineau, "Rest in Peace Post-Earnings Announcement Drift" (Critical Finance Review, 2022): in modern markets prices fully
  reflect earnings surprises on the announcement day; for large stocks PEAD has been non-existent since 2006, and it has only
  recently disappeared for microcaps. Mechanisms cited: decimalization, Reg NMS / high-frequency trading, algorithms parsing
  releases within seconds. [web] — [Martineau, CFR PDF](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf); [RePEc](https://ideas.repec.org/a/now/jnlcfr/104.00000122.html)
- Two 2025 papers claimed PEAD is alive: Dickerson, Julliard & Mueller (JFE, in press; ~18 quadrillion factor-model
  combinations, earnings drift remains a major factor) and Hirshleifer, Peng & Wang (RFS 2025; t-stat ~14). Neither excluded
  microcaps. [web] — [UCLA Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again)
- Subrahmanyam (2025 working paper) reconciles: excluding microcaps, the Dickerson et al. t-stat falls from 2.18 to 1.43
  (not significant); Hirshleifer et al. results "not robust" to size controls. Conclusion: PEAD only in microcaps (bottom 20th
  percentile of market cap, ~3 % of total market value). [web] — [UCLA Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again)
- General anomaly decay: McLean & Pontiff (JF 2016) find returns of published anomalies fall ~26 % out-of-sample and ~58 %
  post-publication (secondary sources quote "50 %" or "58 %"; sources disagree on the exact figure). [web, secondary] — [arXiv: Publication bias in asset pricing](https://arxiv.org/pdf/2209.13623); primary [bg]: [McLean-Pontiff SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623)
- Jensen, Kelly & Pedersen ("Is There a Replication Crisis in Finance?", JF 2023): ~85 % of factors replicate vs CAPM in US
  and global data; most hold up out-of-sample; Chen & Zimmermann find returns decay post-publication but stay positive. These
  are long-short, diversified, mostly small/mid-cap equity factors — not single large-cap CFD trades. [web] — [Evidence Investor](https://www.evidenceinvestor.com/post/is-there-a-replication-crisis-1)
- Hou, Xue & Zhang ("Replicating Anomalies", RFS 2020): with NYSE breakpoints / value weighting, 65 % of 452 anomalies fail
  t>1.96 (82 % at t>2.78); most failures are microcap-driven. [bg] — [NBER w23394](https://www.nber.org/papers/w23394)

### Inferences
- FTMO stock CFDs are mega/large caps (US/EU blue chips). PEAD, earnings-surprise and revision drift in that universe are
  either zero or too small to survive costs + overnight financing (holding period of PEAD = 20-60 days -> ~0.3-0.7 % financing
  per trade at 1.5-4 %/yr markup + rate).
- Analyst-revision and text-based surprise variants need paid data (I/B/E/S, transcripts) — not free. Any surviving edge is
  in small caps / cross-sectional portfolios of hundreds of names, both impossible at FTMO.
- Verdict: drop PEAD/revisions as a direct trading signal. At most, earnings-day volatility is information (avoid holding a
  stock CFD through earnings).

### Gaps
- No found study specifically on PEAD in the ~100 largest US stocks after 2015 with exact bp/trade; Martineau implies ~0.
- FTMO stock CFD exact commission/financing not verified this session.

## 2. Macro-surprise effects (CPI/NFP surprises, economic surprise indices) on FX, indices, gold: drift or immediate jump?

### Takeaway
The price impact of macro surprises is real and large, but it is absorbed within seconds-to-minutes; there is no robust
post-release drift tradable by a retail algorithm. Lower-frequency "surprise momentum" (economic surprise indices) has some
practitioner/academic support but mostly from bank-proprietary or pre-2015 evidence.

### Cited Findings
- Norges Bank Staff Memo 5/2026: relative inflation and monetary-policy news factors explain ~70-80 % of exchange-rate
  forecast-error variance, and exchange rates adjust IMMEDIATELY on release. [web] — [Norges Bank 2026](https://www.norges-bank.no/en/news-events/publications/Staff-Memo/2026/staff-memo-5-2026-macroeconomic-news/)
- Stavrakeva & Tang: macro surprises explain ~70 % of quarterly nominal FX changes and ~50 % of currency risk-premium
  variation (explanatory, contemporaneous — not predictive). [web, snippet] — [Fed IFDP](https://fedinprint.org/item/fedgif/36614/original)
- Only NFP, GDP advance and ISM manufacturing surprises produce economically significant and persistent price responses
  (intraday futures 1998-2007); other releases are small and transitory. [web, snippet] — [CXO Advisory summary](https://cxoadvisory.com/economic-indicators/which-economic-data-announcements-matter)
- Recent falsification study on Micro Nasdaq futures (2026): no persistent post-news drift once the initial spike bars are
  excluded after CPI/NFP and other major releases. [web, snippet] — [arXiv 2605.04004](https://arxiv.org/pdf/2605.04004)
- EURUSD around NFP (5-min bars 2009-2018): conditional pre-release drift (up before bullish prints, down before bearish) —
  i.e. it requires knowing the print; author concludes high noise, no tradable system. [web] — [Robot Wealth](https://robotwealth.com/exploiting-the-non-farm-payrolls-drift/)
- Economic-surprise momentum: growth surprises "consistently predict short-run returns" in equities/bonds/FX via momentum in
  surprises (thesis-level evidence); JP Morgan's proprietary EASI index claimed 8.2 %/yr over 5 years (2000s vendor claim, not
  independent). Another study: simple real-activity indices do almost as well as Citi's CESI; surprises mostly predict only
  direction. [web, snippets — weak sources] — [Erasmus thesis](https://thesis.eur.nl/pub/12870/Doganov,%20V.S.%20%28324535%29.pdf); [Risk.net JPM](https://www.risk.net/foreign-exchange/1505221/jp-morgan-chase-launches-short-term-fx-predictor); [M&G on surprise indices](https://www.mandg.com/investments/professional-investor/en-lu/insights/mandg-insights/latest-insights/2018/03/surprise-indices-a-reminder)

### Inferences
- Jump capture requires sub-second latency + paid consensus feeds; a retail CFD account (spread widening at release, slippage)
  cannot compete. FTMO also restricts trading around high-impact news on standard funded accounts (needs verification in the
  current FTMO rules — the project's memory notes mention FTMO restrictions on gap/news-type behaviour).
- What is usable: the surprise as a STATE variable (e.g., rolling sum of recent CPI/NFP surprises vs consensus, sign of
  economic-surprise index) feeding a multi-day FX/index model. Expected power is small; treat as a feature, not an edge.
- Free data: actual vs consensus is on free calendars (Investing.com/ForexFactory scrapes, FRED for actuals); Citi CESI is
  Bloomberg-only (not free).

### Gaps
- No rigorous post-2015 study found showing a multi-day drift after US CPI/NFP surprises in EURUSD, S&P or gold with
  net-of-cost numbers.

## 3. Rate expectations / 2-year yield differentials / policy divergence; carry and the dollar factor (2015-2026)

### Takeaway
Carry is the best-documented FX "fundamental" premium, but G10 carry made roughly nothing from 2008 until a revival in
2023-2026, has crash risk (Aug 2024 yen unwind), and at FTMO the swap markup (1.5-4 %/yr) eats most of a 2-4 % rate
differential. The 2-year-yield-differential signal is a strong CONTEMPORANEOUS driver, weaker as a predictor.

### Cited Findings
- Citi G10 carry index (long 5 highest-rate / short 5 lowest-rate, unlevered): just over +4 % YTD in 2026; "since the global
  financial crisis it hasn't made any money". Rate diffs May 2026: AUD/NOK >4 %, GBP just below 4 %, JPY <1 %, CHF 0 %.
  EURUSD 3-month implied vol 5.6 % (vs >12 % June 2022). [web] — [Reuters via MarketScreener, 2026](https://www.marketscreener.com/news/carry-on-trading-rate-based-g10-currency-bets-make-a-comeback-ce7f5bd2da8bf327)
- August 2024: hawkish BoJ shift -> yen surge wiped out carry trades in a quiet summer. [web] — [MarketScreener](https://www.marketscreener.com/news/carry-on-trading-rate-based-g10-currency-bets-make-a-comeback-ce7f5bd2da8bf327); [The Edge Malaysia](https://theedgemalaysia.com/node/815634)
- EM carry: Deutsche Bank EM carry index (21 currencies) +6.6 % in 2023 (best since 2017); MXN/JPY >40 % in 2023; Bloomberg
  8-EM carry gauge ~+22 % since end-2024 (helped by a weaker dollar). [web] — [itiger/Bloomberg](https://www-web.itiger.com/news/1160007483); [Hedgeweek](https://www.hedgeweek.com/hedge-funds-pile-into-currency-carry-trades-as-returns-hit-two-decade-high/)
- Banque de France note: carry returns are compensation for volatility/crash risk. [web, title] — [Banque de France](https://www.banque-france.fr/en/publications-and-statistics/publications/carry-trades-and-volatility-risk)
- US monetary-policy exposure: currencies more exposed to US policy surprises earn positive excess returns; long-short
  strategies on exposure indices earn significant returns after controlling for dollar, carry, momentum (Cambridge FX
  Initiative / Fulcrum; no Sharpe given in summary). [web] — [Fulcrum](https://fulcrumasset.com/insights/research/us-interest-rate-surprises-and-currency-returns/)
- Classic evidence [bg]: Lustig-Roussanov-Verdelhan dollar and carry factors explain cross-section of currency returns
  ([NBER w14082](https://www.nber.org/papers/w14082)); Koijen-Moskowitz-Pedersen-Vrugt "Carry" — carry predicts returns in
  all asset classes, diversified carry Sharpe ~0.8-1.0 historically ([NBER w19325](https://www.nber.org/papers/w19325));
  Daniel-Hodrick-Lu: G10 carry drawdowns large, dollar-neutral versions better ([NBER w20433](https://www.nber.org/papers/w20433)).

### Inferences
- FTMO/CFD carry math: long AUDJPY earns ~3.5-4 % gross differential; broker swap markup 1.5-4 %/yr -> net 0 to +2 %/yr,
  with crash risk and FTMO -5 %/day / -10 % walls. Holding carry multi-month is also in tension with a 30-day challenge
  horizon. Low priority, unless swaps on the specific FTMO pairs are measured and found close to interbank.
- Better use: rate-differential CHANGES (2-year yield spread momentum from free FRED / central-bank data) as a slow FX
  feature, combined with price trend (the only edge the project has measured). Evidence for predictive power at 1-4 weeks is
  plausible but not documented post-2015 in sources found here.

### Gaps
- No found free, recent (2015-2026) net-of-cost study of "2-year yield differential momentum" in G10 FX.
- Actual FTMO swap points per pair not measured in this session.

## 4. Central-bank meetings: pre-FOMC drift, announcement-day premium

### Takeaway
The unconditional pre-FOMC drift (Lucca-Moench: ~49 bp in 24 h before FOMC, 1994-2011) has essentially disappeared after
2015. A conditional version survives in the literature: drift appears mainly when implied volatility / variance risk premium is
high. Small number of events (8/year) -> statistically fragile.

### Cited Findings
- Kurov, Wolfe & Gilbert (extending sample to Dec 2019): pre-FOMC drift "essentially disappeared after 2015", both with and
  without press conferences. [web, snippet] — [Kurov-Wolfe-Gilbert SSRN page](https://papers.ssrn.com/author=3571041) (PDF link was 404 this session)
- Lucca & Moench (2015): large excess S&P returns in the 24 h before scheduled FOMC announcements, Sept 1994-March 2011. [web,
  snippet]; magnitude ~49 bp per event, accounting for a large share of the equity premium [bg] — [NY Fed SR512](https://www.newyorkfed.org/research/staff_reports/sr512.html)
- Martello & Ribeiro ("Pre-FOMC Announcement Relief"): drift ~109 bp when implied vol is above median vs ~9.7 bp below median;
  near zero or negative in the bottom 20 % of vol; implied variance falls ~103.5 bp before the meeting in high-vol regimes.
  Interpretation: drift = release of risk premium when uncertainty is high. [web] — [Quantpedia](https://quantpedia.com/fomc-equity-drift-occurs-in-periods-of-high-uncertainty/)
- Ignatieva & Ohashi (Applied Economics 2025): positive excess equity returns before FOMC-with-press-conference announcements,
  effect short-lived after disclosure; they report a profitable strategy (numbers not visible in abstract). [web] — [RePEc](https://ideas.repec.org/a/taf/applec/v57y2025i17p2021-2037.html)

### Inferences
- With FTMO index CFD costs (~0.01 % round trip) a 1-day long US500 before FOMC is cheap to test; but 8 events/year, and the
  unconditional mean since 2015 is ~0. A "only when VIX high" rule gives maybe 2-4 trades/year — irrelevant for monthly income,
  acceptable as a small feature (calendar flag + VIX level, both free).

### Gaps
- No exact post-2015 bp/event figure found in a fetched source; ECB/BoE/BoJ pre-meeting drifts not covered.

## 5. Commodities: EIA inventory surprises, COT positioning, seasonality, term structure / roll yield

### Takeaway
EIA surprises move oil immediately (~25 min) and then partially revert: no tradable drift for retail. COT hedging pressure
does not reliably predict returns (data to 2010). The strongest commodity predictors (carry/basis, basis-momentum) need the
futures curve — free-ish data exists but FTMO energy CFDs (and metals) give only one contract, so the signal can be used
for direction on a single CFD but roll yield itself is not "harvested" the same way.

### Cited Findings
- Intraday reaction to EIA crude inventory shocks lasts ~25 minutes; positive inventory surprise -> immediate price drop, then
  prices revert quickly. [web, snippet] — [Journal of Energy Markets / Risk.net](https://www.risk.net/journal-of-energy-markets/5728636/an-analysis-of-intraday-market-response-to-crude-oil-inventory-shocks)
- OLS understates impact (errors-in-variables from noisy expectations): corrected coefficients ~2x OLS. [web, snippet] — [Kurov et al., Noisy inventory announcements](https://www.skidmore.edu/economics/documents/NoisyInventoryAnnouncementsAndEnergyPrices.pdf)
- Announcement-day effect on futures and options, asymmetric response to positive vs negative surprises. [web, snippet] — [Ye & Karali AAEA 2015](https://ageconsearch.umn.edu/record/205595/files/AAEA_Ye_Karali-2015.pdf)
- COT: commercial hedgers net short in 25/28 markets, but trading against them does not reliably earn positive gross returns,
  and variations in hedging pressure do not predict returns (data through 2010). [web, snippet] — [CXO Advisory](https://www.cxoadvisory.com/commodity-futures/commodity-futures-investing-updates)
- Basis-momentum (Boons & Prado, JF 2019): strongest known predictor in cross-section and time series; 21 commodities since
  1959, high-minus-low ~18.4 %/yr in nearby returns and ~4.1 %/yr in spreading returns. Requires 1st and 2nd contract prices.
  [web] — [Boons & Prado PDF](https://4nations.albertjmenkveld.com/papers/boonsprado17.pdf)

### Inferences
- FTMO energy CFDs (WTI/Brent/natgas) are cash CFDs built on rolling futures; a single-asset time-series use of basis or
  basis-momentum is possible (free front/second-month data from CME settlement pages / EIA spot-futures), but the documented
  18 % is a cross-sectional long-short across 21 commodities — FTMO offers ~5-6 commodities (oil x2, gas, gold, silver, maybe
  others), so expect a fraction of that, with high noise.
- EIA trading = speed game, also inside FTMO news windows: not feasible.
- COT is weekly, free (CFTC), but evidence for predictive power is weak; usable only as context feature.

### Gaps
- No post-2015 out-of-sample study of basis-momentum found in this session.
- Commodity seasonality (natgas winter, gasoline driving season) evidence not collected — gap.

## 6. Equity index timing with fundamentals (valuation, revisions breadth, liquidity/Fed balance sheet) at monthly horizon

### Takeaway
Weak. The definitive replication (Goyal-Welch-Zafirov, RFS 2024) finds most published predictors fail out-of-sample;
aggregate earnings revisions have weak association with market returns; valuation works only at multi-year horizons.

### Cited Findings
- Goyal, Welch & Zafirov, "A Comprehensive 2022 Look at the Empirical Performance of Equity Premium Prediction" (RFS 37(11),
  2024): of 29 newer variables from 26 papers plus 17 originals, more than a third lose even in-sample significance; of the rest,
  half perform poorly out-of-sample; only a small number still work both ways. [web] — [SFI](https://sfi.ch/en/publications/a-comprehensive-2022-look-at-the-empirical-performance-of-equity-premium-prediction); [Welch page](https://ivo-welch.info/home/card-eqpredict.html)
- Aggregate analyst-forecast revisions: correlated with contemporaneous returns; very weak association between aggregate
  revisions and future market returns due to low commonality across firms; better at industry level (analyst underreaction to
  macro). [web, snippets] — [Penn State: Aggregate earnings expectations](https://pure.psu.edu/en/publications/aggregate-earnings-expectations-and-stock-market-behavior/); [RePEc Fin Markets 2016](https://ideas.repec.org/a/eee/finmar/v29y2016icp110-143.html)
- Gold vs real yields: correlation 84 % in 2005-2021, ~3 % in 2022-2023, ~7 % since 2024; central-bank buying >1,000 t/yr in
  2022-2024 vs ~473 t/yr in 2010-2021 -> the "fundamental" gold model broke in exactly the test window. [web] — [RBC Wealth Management](https://www.rbcwealthmanagement.com/en-us/insights/golds-regime-change); [Janus Henderson](https://www.janushenderson.com/hub/article/chart-to-watch-whats-behind-the-divergence-between-gold-and-real-treasury-yields/)

### Inferences
- Monthly index timing from fundamentals: expect R² of ~0-1 %/month; not a standalone edge. Fed balance sheet/liquidity:
  no rigorous OOS source found.
- Gold is a warning case: a 17-year 84 % relation went to ~0 — a fundamental model fitted pre-2022 would have been wrong
  in 2022-2026. Same structural-break risk applies to all macro links.

### Gaps
- No rigorous OOS study found on Fed balance sheet / net liquidity as an index timer.

## 7. Ranking: evidence × still alive × feasible on FTMO CFDs with free data

### Takeaway
None of the fundamental/information edges is a strong, alive, CFD-feasible standalone edge. Best ratios: (1) conditional
macro/policy features combined with trend (rate-differential momentum, surprise state, high-VIX pre-FOMC flag),
(2) carry ONLY if FTMO swaps are near fair, (3) commodity basis/basis-momentum as feature on oil. Dead or infeasible: PEAD,
revisions drift on large caps, EIA/NFP jump trading, COT, unconditional pre-FOMC drift, valuation timing.

### Cited Findings
| Edge | Evidence | Alive 2020-26? | CFD/free-data feasibility | Verdict |
|---|---|---|---|---|
| PEAD / revisions (large caps) | Strong historically, decayed | No in large caps since ~2006 ([Martineau](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf), [Subrahmanyam via UCLA](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again)) | Paid data, microcaps only | Dead |
| Macro-surprise drift (CPI/NFP) | Impact strong, drift weak | Adjustment immediate ([Norges Bank 2026](https://www.norges-bank.no/en/news-events/publications/Staff-Memo/2026/staff-memo-5-2026-macroeconomic-news/), [arXiv 2026](https://arxiv.org/pdf/2605.04004)) | Latency + news restrictions | Feature only |
| G10 carry | Strong long-run, crash-prone | ~0 from 2008 to 2022, revived 2023-26 ([MarketScreener](https://www.marketscreener.com/news/carry-on-trading-rate-based-g10-currency-bets-make-a-comeback-ce7f5bd2da8bf327)) | Swap markup 1.5-4 %/yr eats it | Only if swaps fair |
| US policy exposure (FX) | Academic, controls for carry/dollar | Not quantified | Free data (FRED, fed funds futures) | Promising feature, unproven |
| Pre-FOMC drift | Strong 1994-2011 | Gone after 2015 unconditional ([Kurov et al.](https://papers.ssrn.com/author=3571041)); conditional on high vol ([Quantpedia](https://quantpedia.com/fomc-equity-drift-occurs-in-periods-of-high-uncertainty/)) | Cheap on US500 CFD | 2-4 trades/yr, marginal |
| EIA inventories | Strong impact, ~25 min | Reverts ([Risk.net](https://www.risk.net/journal-of-energy-markets/5728636/an-analysis-of-intraday-market-response-to-crude-oil-inventory-shocks)) | Speed game | Infeasible |
| COT hedging pressure | Weak | No ([CXO](https://www.cxoadvisory.com/commodity-futures/commodity-futures-investing-updates)) | Free | Context only |
| Basis-momentum / carry (commodities) | Strong (18 %/yr L/S, since 1959) | Not verified post-2015 ([Boons-Prado](https://4nations.albertjmenkveld.com/papers/boonsprado17.pdf)) | Few commodities on FTMO | Feature on oil |
| Index valuation / revisions timing | Weak OOS | Mostly fails ([Goyal-Welch-Zafirov 2024](https://sfi.ch/en/publications/a-comprehensive-2022-look-at-the-empirical-performance-of-equity-premium-prediction)) | Free | Not an edge |

### Inferences
- Consistent with the project's own measurements (CLAUDE.md §5: macro, COT, linked markets = no edge; only trend of fond
  helped): the literature confirms information edges are either arbitraged to seconds (news) or slow risk premia (carry,
  basis) that are small after CFD financing and come with crashes.
- Realistic contribution of fundamentals: conditioning variables that change WHEN a trend/carry exposure is taken
  (high-uncertainty regime, policy divergence, surprise state), worth perhaps a few tenths of Sharpe at best — not a 8 %/month
  engine.
- Highest-value next check for the project: measure FTMO's actual swap points per pair (if near interbank, a trend-filtered
  carry basket on AUD/NZD/NOK/MXN vs JPY/CHF becomes testable on 2024-2026 data).

### Gaps
- No net-of-CFD-cost backtest of any of these edges for 2020-2026 found in public sources.
- FTMO news-trading rules and per-instrument swaps not verified in this session.

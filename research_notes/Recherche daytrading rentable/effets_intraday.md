# Documented intraday return effects: are they still alive after realistic costs (2018-2026)?

Scope note: these notes cover intraday momentum, opening-range breakouts, time-of-day patterns (equities, FX, gold, crypto), FX fixes, announcement effects, overnight vs intraday returns, intraday reversal and volatility timing. Numbers are quoted from the papers or replications. Where a number is computed by me (conversion to basis points per day, comparison with typical retail CFD spreads), it is in **Inferences**, not in Cited Findings. 1 bp = 0.01 %.

---

## 1. Market intraday momentum (first half-hour / rest-of-day predicts last half-hour)

### Takeaway
This is the best-documented intraday effect. It exists in 60+ futures markets from 1974 to 2020 and in 12 of 16 developed equity markets, and its usual explanation (option-dealer gamma hedging, leveraged-ETF rebalancing) is still around. But the raw "last half-hour" trade earns only about 1.7-2.7 bp per day on indices and commodities, and about 0.3 bp per day on currencies, before costs. Retail CFD spreads largely wipe that out. The surviving, cost-tolerant versions trade breakouts of a volatility band with trailing stops and volatility-scaled size (Zarattini et al.). Those versions report net Sharpe of about 1.2-1.3 on SPY through 2024, but an independent futures study on 2021-2025 data found no simple intraday-momentum signal that survives costs.

### Cited Findings
- **Gao, Han, Li, Zhou (JFE 2018)**: on SPY 1993-2013, the first half-hour return predicts the last half-hour return. Predictability is stronger on volatile days, high-volume days, recession days and macro-news days — [Monash repository / summary](https://researchmgt.monash.edu/ws/files/519509174/494419119_oa.pdf); [original working paper PDF](https://c.mql5.com/forextsd/forum/173/intraday_momentum_-_the_first_half-hour_return_predicts_the_last_half-hour_return.pdf)
- **International replication (Li, Sakkas, Urquhart, J. Financial Markets 2022)**: significant first-half-hour → last-half-hour predictability in 12 of 16 developed markets. Out-of-sample forecasting power holds "in most countries", but the effect is weaker in Asia-Pacific — [Reading eprints](https://reading-9.eprints-hosting.org/95566/1/Accepted-Version.pdf); [Nottingham repository](https://nottingham-repository.worktribe.com/OutputFile/5273196)
- **Baltussen, Da, Lammers, Martens (JFE 142, 2021, "Hedging demand and market intraday momentum")**: tested on 60+ futures (equities, bonds, commodities, currencies), 1974-2020. The return from the previous close to 30 minutes before the close (r_ROD) predicts the last half-hour return everywhere. The effect is present in both the 1974-1999 and 2000-2020 subsamples — [paper PDF, Notre Dame](https://academicweb.nd.edu/~zda/intramom.pdf); [EUR repository](https://pure.eur.nl/en/publications/hedging-demand-and-market-intraday-momentum/)
- Baltussen et al., Table 6, timing strategy η(r_ROD) (long or short in the last half-hour according to the sign of the rest-of-day return), equal-weighted per asset class, **gross of costs**:
  - Equity index futures: 6.86 %/yr, vol 3.96 %, Sharpe 1.73, success rate 55 %.
  - Bond futures: 2.16 %/yr, Sharpe 1.62.
  - Commodity futures (gold GC and crude CL are in the sample): 4.34 %/yr, vol 3.05 %, Sharpe 1.42.
  - Currency futures: 0.85 %/yr, vol 0.98 %, Sharpe 0.87.
  - Source: [paper PDF](https://academicweb.nd.edu/~zda/intramom.pdf)
- Baltussen et al. on costs: "we do not consider transaction costs… the strategy as presented might not be exploitable to many investors after accounting for transaction costs." In S&P 500 futures, a cost of one tick still leaves a positive net Sharpe ("a cost level faced commonly by advanced investors") — [paper PDF](https://academicweb.nd.edu/~zda/intramom.pdf)
- Baltussen et al. on persistence after the close: the predictive power reverts to zero by the next day in currency futures, within two days in equity and commodity futures, and within three days in bonds. This fits price pressure from hedging, not information — [paper PDF](https://academicweb.nd.edu/~zda/intramom.pdf)
- Mechanism: the effect is linked to gamma-hedging demand of option market makers and to leveraged-ETF rebalancing — [paper PDF](https://academicweb.nd.edu/~zda/intramom.pdf); [Quantpedia summary](https://vvv.quantpedia.com/?p=9310)
- **Bitcoin (Shen, Urquhart, Wang)**: using volume to define "trading sessions" in a 24 h market, the first half-hour predicts the last half-hour. The economic gains are strongest during Bitcoin downturns, and the driver is liquidity provision, not late-informed trading — [Birmingham repository](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/); [Reading PDF](https://reading-9.eprints-hosting.org/100181/3/21Sep2021Bitcoin%20Intraday%20Time-Series%20Momentum.R2.pdf)
- **Negative recent out-of-sample evidence (Mesfin, arXiv 2605.04004, May 2026)**: 14 intraday signal families (including opening-range breakout, gap continuation and reversal classifiers) tested on Micro E-mini Nasdaq (MNQ) 5-minute bars over 947 days in 2021-2025, with walk-forward validation. **None** passed all five criteria (out-of-sample net t ≥ 2, positive net returns, same sign across years, …). Eleven families had gross edge of only 0.07-1.50 points per trade, against a friction floor of about 2.0 points — [arXiv](https://arxiv.org/abs/2605.04004)
- Blue-chip high-frequency momentum/contrarian strategies: none beat the benchmark after reasonable transaction costs — [Business Perspectives, IMFI](https://businessperspectives.org/journals/investment-management-and-financial-innovations/issue-493/high-frequency-momentum-and-contrarian-strategies-in-u-s-blue-chips)

### Inferences
- Converting Baltussen's gross numbers to a per-day basis (÷252): equity indices ≈ 2.7 bp/day, commodities ≈ 1.7 bp/day, currencies ≈ 0.34 bp/day per round trip.
- Typical retail CFD costs, all approximate and broker-dependent:
  - US500: 0.5-1 point on about 6 000 ≈ 1-1.7 bp.
  - Gold: $0.25 on $3 000-4 000 ≈ 0.6-0.8 bp, plus slippage.
  - EURUSD: 0.1-0.3 pip plus commission ≈ 0.5-1.5 bp.
- With those costs, the plain last-half-hour trade is dead in FX for retail and marginal at best on index CFDs and gold.
- The effect is a liquidity/hedging premium, so it is unlikely to "disappear" the way an information anomaly would. But its size per trade is the size of a spread.
- For MT5, the effect is better used as a **feature or filter** than as a standalone trade: it tells you the probable direction of the last hour, and it can help time exits or entries the AI already wanted to make. Baltussen et al. suggest exactly this: "timing of already planned trades".

### Gaps
- I did not obtain post-2020 updates of the Gao et al. last-half-hour regression for SPY/ES (some practitioners claim it weakened after 2013; I found no peer-reviewed confirmation).
- I found no study on FX spot or gold spot CFDs specifically with retail spreads.

---

## 2. Zarattini / Aziz / Barbon "noise-area" intraday momentum (SPY) — the cost-tolerant variant

### Takeaway
A breakout of a time-of-day volatility band, with a VWAP trailing stop and volatility-scaled size, reports a net Sharpe of 1.33 on SPY in 2007-2024 and +32 % in the post-publication year 2024. On 33 futures (2007-09/2024) it reports an average Sharpe of 0.60 per market and 1.65 for the diversified portfolio. These are author-reported backtests with a commercial interest (Concretum). Treat them as optimistic until independently replicated. The costs assumed are for a stock ETF, much lower than retail CFD spreads.

### Cited Findings
- **Rules ("Beat the Market", SFI Research Paper 24-97, May 2024)**:
  - Noise area: for each time-of-day HH:MM, take the average absolute move from the 9:30 open over the previous 14 days. The bands are Open × (1 ± σ_HH:MM), adjusted for the overnight gap using the prior close.
  - Signal checks happen only at the top or bottom of the hour (every 30 minutes); long above the upper band, short below the lower band.
  - The stop is the current band or VWAP.
  - Size is scaled by daily volatility (target ≈ 2 % daily vol, leverage capped at 4×).
  - Source: [paper PDF, alexandria.unisg.ch](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content); [Concretum page](https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/); [QuantifiedStrategies summary](https://quantifiedstrategies.substack.com/p/systematic-intraday-trend-following)
- **Costs assumed**: $0.0035/share commission (IBKR entry level) plus $0.001/share slippage, measured on the authors' live trading — [paper PDF](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)
- **Results 2007-2024, building up the rules step by step**:

  | Variant | Total return | Annual return | Vol | Sharpe | Max drawdown | Other |
  |---|---|---|---|---|---|---|
  | Opposite-band stop | 178 % | 6.2 % | 10.9 % | 0.61 | 21 % | worst day -10.3 % |
  | VWAP + current-band stop | 380 % | 9.7 % | 7.7 % | 1.24 | 12 % | hit rate 43 % |
  | Plus volatility sizing | 1 985 % | 19.6 % | 14.3 % | 1.33 | 25 % | daily hit rate ≈ 43 %, beta slightly negative |

  The **stop design and the volatility sizing** are what turn a mediocre signal into a good one — [paper PDF](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)
- The Sharpe is higher when the VIX is high: about 1.5 when VIX > 6 overall, 3.50 when VIX > 40 — [paper PDF](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)
- **Year by year (author table, %)**:
  - 2016: **-12.8**; 2017: **-6.9** (calm years lose)
  - 2018: +61.1; 2019: +6.9; 2020: +26.8; 2021: +34.8; 2022: +24.4; 2023: +37.2
  - **2024 (post-publication): +32.2**; Jan 2025: -1.2
  - Source: [paper PDF, FAQ Q24](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)
- Robustness checks by the authors:
  - With a more conservative large-cap slippage model, the Sharpe falls from 1.33 to 1.17 and alpha from ≈ 20 % to > 15 %.
  - Average profit is $0.09/share per trade over the full period, $0.18/share over the last 7 years.
  - Source: [paper PDF, FAQ Q15/Q23](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)
- **Futures, 33 markets (21 commodities, 12 equity indices), Jan 2007-Sep 2024**: only 2 markets had a negative total return. The average Sharpe per market is 0.60 and the diversified portfolio Sharpe is 1.65. S&P 500 futures: Sharpe 1.32, 19.8 %/yr; Nasdaq 1.23; S&P 400 0.80; Russell 0.45. Commodity Sharpes range from -0.30 to 1.11. Hit rates are 36-44 %, with positive skew (profits come from a few trend days) — [paper PDF, FAQ Q13](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)
- Optimising the parameters raises the Sharpe (90-day lookback, 1.5× volatility multiplier), which is a warning sign for overfitting. The authors present it as robustness — [paper PDF, FAQ Q14](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)

### Inferences
- Per trade, the edge is small: $0.09-0.18 per share on a SPY price of $250-600, i.e. roughly 3-4 bp per trade. A retail index CFD with a 1-2 bp round-trip spread plus slippage would consume a large part of it. The futures table (same rules on ES/NQ) is the more relevant evidence for CFD traders.
- The structure that survives is a **trend-day capture machine**: hit rate ≈ 40 %, positive skew, losses in calm years (2016-2017), large gains in volatile years. That is compatible with FTMO only with strict sizing; a calm year means a long run of small losses.
- This is directly implementable on MT5 with M1 or M15 data: compute the per-time-of-day 14-day average move from the session open, build the bands, check at :00/:30, stop at max(band, VWAP), size to a volatility target. Gold and indices CFDs fit. FX has no clear "open", so the London or NY open would be an arbitrary anchor and is untested.

### Gaps
- No independent peer-reviewed replication found. Post-2025 performance is not available beyond Jan 2025 in the document version I read.

---

## 3. Opening-range breakout (ORB)

### Takeaway
The author-reported results are spectacular. On QQQ (2016-2023), the 5-minute ORB shows a 33 % annual alpha net of commissions. On the top 20 "stocks in play", Sharpe is 2.81 net. But a 2026 replication on index CFDs with M1 data and realistic spreads reproduced the gross edge and found **net ≈ 0** on all five indices (four of five negative). For a retail CFD trader, plain ORB on indices should be considered dead after costs.

### Cited Findings
- **Zarattini & Aziz (2023, SSRN 4416622), "Can Day Trading Really Be Profitable?"**: 5-minute ORB on QQQ, 2016-2023, annualized alpha 33 % net of commissions. Using TQQQ: +1 484 %, against +169 % for buy-and-hold QQQ — [SSRN](https://papers.ssrn.com/abstract=4416622); [Concretum](https://concretumgroup.com/can-day-trading-really-be-profitable/)
- **Zarattini, Barbon, Aziz (2024), ORB on "Stocks in Play"**: 7 000+ US stocks, 2016-2023, trading the top 20 stocks by relative volume with a 5-minute ORB. Net total return > 1 600 %, Sharpe 2.81, annual alpha 36 %, against 198 % for the S&P 500 — [Concretum](https://concretumgroup.com/a-profitable-day-trading-strategy-for-the-u-s-equity-market/); [QuantConnect replication thread](https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/)
- **Independent retail-CFD replication (T.-P. Krueger, MQL5 blog, 25/09/2026)**:
  - Data: NQ, SPX, Dow, DAX, FTSE CFDs; 1-minute bars; Jan 2015-Jun 2026; ~2 900 sessions each.
  - Costs: round-trip spread plus slippage of NQ 2.5 pts, SPX 0.8, Dow 4.0, DAX 2.5, FTSE 1.5.
  - NQ: +0.131 R per trade gross → **+0.002 R net**; hit rate ≈ 23 %.
  - "Net of costs no market is distinguishable from zero and four of five are negative"; the edge (≈ 0.1 R) "is what a 2.5-point round trip costs".
  - Source: [MQL5 blog](https://www.mql5.com/en/blogs/post/776235)
- On MNQ futures 2021-2025, ORB variants failed to show a tradable net edge — [arXiv 2605.04004](https://arxiv.org/abs/2605.04004)

### Inferences
- ORB on the index itself is a weak edge that lives inside the spread. The strong results come from **stock selection** (stocks in play with catalysts) and very cheap execution, neither of which is available on FTMO CFDs.
- If used at all, ORB should be one input for the AI, conditioned on volatility, gap and news, and never a standalone rule.

### Gaps
- No ORB study on gold or FX majors with retail costs was found.

---

## 4. Overnight vs intraday returns ("tug of war"), opening gap

### Takeaway
In US stocks, momentum profits accrue overnight and most other anomaly profits accrue intraday, with opposite-sign components. This is mostly a cross-sectional single-stock effect, not directly tradable on index or FX CFDs. In gold, an "overnight positive / daytime negative" pattern is documented, but part of it is a data artefact of open/close prices.

### Cited Findings
- **Lou, Polk, Skouras (JFE 2019, "A tug of war")**: all of the abnormal returns on momentum strategies occur overnight, while profits from other strategies occur intraday. The overnight and intraday components often have opposite signs, with strong overnight-overnight and intraday-intraday continuation and a cross-period reversal. The results are robust across subsamples and stronger for large and high-price stocks — [LSE Research Online](https://researchonline.lse.ac.uk/id/eprint/119010); [paper PDF](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf); [Alpha Architect summary](https://alphaarchitect.com/2015/02/overnight-momentum-vs-intraday-momentum/)
- **Gold overnight effect**: overnight returns are significantly positive and daytime returns significantly negative. This holds for COMEX gold front futures, spot gold (London fix), miners and gold funds/ETFs — [J. Economics & Finance 42(3), 2018, via IDEAS](https://ideas.repec.org/a/spr/jecfin/v42y2018i3d10.1007_s12197-017-9403-0.html); [Quantpedia summary](https://quantpedia.com/dangers-of-relying-on-ohlc-prices-the-case-of-overnight-drift-in-gdx-etf/)
- Quantpedia: in GDX the "overnight drift" exceeded 30 %/yr using official open prices. Executing at 9:31 with 1-minute data made the anomaly diminish significantly, i.e. part of it is an artefact of open/close prints — [Quantpedia](https://quantpedia.com/dangers-of-relying-on-ohlc-prices-the-case-of-overnight-drift-in-gdx-etf/)

### Inferences
- For MT5 gold (a 23 h market), "overnight" means the Asian session. Any test must use executable bid/ask prices at the exact minute, not session open/close prints, because the GDX case shows the artefact risk.
- For indices CFDs, a gap-continuation or gap-reversal rule was tested in the MNQ 2021-2025 study and failed after costs ([arXiv](https://arxiv.org/abs/2605.04004)).

### Gaps
- Kelly-Clark ("Returns in trading versus non-trading hours") and the opening-gap reversal literature: no source retrieved in this session, so no numbers.
- No recent (2018-2026) evidence on whether the gold overnight effect persisted.

---

## 5. Intraday seasonality / periodicity (equities)

### Takeaway
Heston, Korajczyk and Sadka show that a stock's return in a given half-hour predicts its return in the same half-hour on following days, for up to 40 days or more. Short-term reversal at sub-hour horizons is mostly bid-ask bounce and temporary liquidity imbalance. These are cross-sectional single-stock effects, so they transfer poorly to CFD trading.

### Cited Findings
- **Heston, Korajczyk, Sadka (JF 2010)**:
  - Return continuation at half-hour intervals that are exact multiples of a trading day, lasting at least 40 trading days; strongest for the first and last half-hours.
  - Volume, order imbalance, volatility and spreads show similar patterns but do not explain the return pattern.
  - Short-term reversal is driven by temporary liquidity imbalances lasting under an hour and by bid-ask bounce.
  - Source: [paper PDF, U. Houston](https://www.bauer.uh.edu/departments/finance/documents/Heston_Korajczyk_Sadka_paper_UH.pdf); [arXiv version](https://ar5iv.arxiv.org/html/1005.3535)
- Follow-up in the Financial Analysts Journal (2011): [IDEAS](https://ideas.repec.org/a/taf/ufajxx/v67y2011i2p36-44.html)

### Inferences
- Applied to the AI: same-time-of-day features (return in this half-hour over the past N days) are cheap to compute on M15 data and are a legitimate input, but no standalone retail edge is documented for indices, FX or gold.
- Intraday reversal at minutes horizons is mostly a market-maker (liquidity provision) return that requires earning the spread, not paying it. A retail CFD trader pays the spread, so this is structurally unavailable.

### Gaps
- No retrieved magnitude (bp per half-hour) for Heston-Korajczyk-Sadka. No post-2010 replication found in this session.

---

## 6. FX: fixes (WM/Reuters London 4pm, ECB, Tokyo), month-end, time-zone patterns

### Takeaway
The best-documented FX intraday pattern is the "W". The dollar appreciates before the Tokyo, ECB and London fixes and depreciates after them, a reversal of about 2.5-4 bp per day. It is statistically very robust over 1999-2019, but **it does not survive full indicative bid-ask costs**. With half the quoted spread, Sharpe is 0.12-1.03. The Tokyo-fix reversal shrank after 2014. Local-hours depreciation (Breedon-Ranaldo) is the same family.

### Cited Findings
- **Krohn, Mueller, Whelan ("Foreign exchange fixings and returns around the clock", Bank of Canada SWP 2021-48; published in J. Finance 2024)**:
  - The dollar appreciates in the run-up to fixes and depreciates afterwards, tracing a W-shaped pattern over 24 h, for the G9 currencies over 1999-2019.
  - Annualized pattern sizes:
    - Pre-ECB fix: euro -8.87 %/yr, krona -7.73 %/yr.
    - Post-London fix: currencies +3.89 % (CAD) to +6.87 % (EUR) per year.
    - Post-Tokyo reversal: yen 7.94 %, krone 7.44 % per year.
  - The daily reversal is about 2.5 bp (London) to 4 bp (Tokyo) per day.
  - Source: [Bank of Canada PDF](https://www.bankofcanada.ca/wp-content/uploads/2021/10/swp2021-48.pdf); [WU Vienna version](https://www.wu.ac.at/fileadmin/wu/d/ri/isk/VSFX_2022/Paper/Session_III_1a_Krohn__foreign_Exchange_Fixings_Returns_Around_The_Clock_0712.pdf)
- Krohn et al. on persistence:
  - The reversal averaged ≈ 6.5 % annualized on either side of the fix in 1999-2014.
  - In 2014-2019 the Tokyo reversal is "notably smaller but remains statistically significant"; the pre-ECB dollar appreciation is ≈ 5 %/yr in 1999-2009 and again in 2014-2019.
  - The cause is dealer hedging and inventory risk around a published reference rate.
  - Source: [Bank of Canada PDF](https://www.bankofcanada.ca/wp-content/uploads/2021/10/swp2021-48.pdf)
- Krohn et al. on costs:
  - Gross annual returns around the Tokyo fix: 10.44 % (EUR), 7.94 % (GBP), 12.0 % (JPY).
  - With full indicative bid-ask costs, most windows turn **negative** because of the huge turnover.
  - With 50 % of the bid-ask: +2.65 % (EUR), +0.51 % (GBP), +2.73 % (JPY); pre-ECB/post-London windows give 8.64 % and 5.46 %; Sharpe 0.12-1.03.
  - Net of half-spread, the Tokyo strategy has been flat or negative for EUR and GBP since ≈ 2013; the London reversal stayed positive.
  - Source: [Bank of Canada PDF](https://www.bankofcanada.ca/wp-content/uploads/2021/10/swp2021-48.pdf)
- Krohn et al.: the W pattern is **not** driven by the month-end equity-hedging channel of Melvin and Prins (2015), by quarter-ends or by day-of-week effects — [Bank of Canada PDF](https://www.bankofcanada.ca/wp-content/uploads/2021/10/swp2021-48.pdf)
- **London 4pm fix, month-end (Evans; Melvin & Prins 2015)**:
  - Rates partially reverse around the fix (they fall after rising into the fix, and vice versa), and the reversals are larger at month-end.
  - Pre-fix moves at month-end fall in the 95th percentile of the rate-change distribution four times more often than in normal trading.
  - Melvin & Prins link month-end fix flows to equity-hedging rebalancing.
  - The fix calculation window was lengthened from 1 minute to 5 minutes on 15/02/2015 after the fix-manipulation scandal.
  - Sources: [Evans, NYU micro meeting paper](https://pages.stern.nyu.edu/~jh4/SternMicroMtg/Old/SternMicroMtg2015/Papers/4ExEvans.pdf); [Norges Bank, Panagiotou, "The WMR fix and its impact on currency markets"](https://www.norges-bank.no/contentassets/619c8b75e1ed4ba691e8ad6a006855e6/39-panagiotou---the-wmr-fix-and-its-impact-on-currency-markets-.pdf); [Bank of Canada PDF, footnote 8](https://www.bankofcanada.ca/wp-content/uploads/2021/10/swp2021-48.pdf)
- **Breedon & Ranaldo (SNB WP 2011-04)**: currencies tend to depreciate during their own local trading hours, across currencies and time zones; e.g. EUR/USD falls in the European morning and rises in US hours. The pattern shows up in order flow (locals are net buyers of foreign currency in their own hours) and yields a "simple, profitable trading strategy" in EUR/USD — [SNB working paper](https://www.snb.ch/en/publications/research/working-papers/2011/working_paper_2011_04); [QMUL WP 694](https://qmul.ac.uk/sef/research/workingpapers/2012/items/694.html)
- Practitioner month-end fix commentary (flow-direction estimates each month) exists, e.g. [TheFullFX](https://thefullfx.com/?p=4992). It is not peer-reviewed.

### Inferences
- A daily 2.5-4 bp reversal against a retail EURUSD round trip of ≈ 0.5-1.5 bp (ECN account) leaves a thin edge on a single round trip per day. On standard accounts with 1+ pip spreads (≈ 9 bp), it is dead.
- The most usable form for an MT5 AI is **features**: minutes to the next fix, pre-fix return, month-end flag, local-session indicator. A rule-based trade is less useful.
- Fix times to encode:
  - Tokyo: 9:55 JST.
  - ECB: 14:15 CET.
  - WM/Reuters: 16:00 London, with a 5-minute window since 2015.

### Gaps
- No post-2019 data on the W pattern was retrieved. No independent net-of-retail-cost test was found. Breedon-Ranaldo magnitudes (bp, Sharpe) were not retrieved.

---

## 7. Gold intraday patterns (London AM/PM fix, Asia vs West)

### Takeaway
Gold tends to rise in Asian hours and fall during London/NY hours, especially around the PM fix. This shows in COMEX futures, the London fix and gold ETFs. Evidence quality is mixed: there is one peer-reviewed overnight-effect paper, plus practitioner and student work. I found no rigorous 2018-2026 net-of-cost test.

### Cited Findings
- Overnight (non-US hours) gold returns are significantly positive and daytime returns significantly negative, in COMEX gold futures, the spot London fix, miners and gold ETFs — [J. Economics & Finance 2018, IDEAS](https://ideas.repec.org/a/spr/jecfin/v42y2018i3d10.1007_s12197-017-9403-0.html)
- "Hat-shaped" intraday seasonality: gold appreciates robustly during Eastern trading hours and depreciates for the rest of the day (Copenhagen Business School thesis, not peer-reviewed) — [CBS](https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/)
- Practitioner "London bias" claim: buy at the PM fix and sell at the next AM fix. This is a non-academic source with no stated costs or period detail; treat with caution — [Sunshine Profits](https://www.sunshineprofits.com/gold-silver/dictionary/gold-london-bias)
- Baltussen et al. include COMEX gold (GC, 08:20-13:30 ET session) in commodity futures, and commodity intraday momentum is 4.34 %/yr gross for the portfolio — [paper PDF](https://academicweb.nd.edu/~zda/intramom.pdf)
- Zarattini noise-area rules on 21 commodity futures: Sharpes from -0.30 to 1.11 (the individual commodities are not named in the extracted table) — [paper PDF](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)

### Inferences
- With gold CFD spreads around $0.25 (≈ 0.6-0.8 bp), an Asia-long / London-short daily pattern only needs a few bp per day to survive. That makes it one of the few patterns worth testing directly on our own Dukascopy M15/M1 gold data for 2018-2026, with executable prices and swap/overnight costs included.
- 2023-2026 was a period of strong gold uptrend; any session pattern must be tested demeaned (relative to the daily drift) to avoid mistaking the trend for seasonality.

### Gaps
- No peer-reviewed paper with post-2018 numbers. The LBMA auction (replacing the old fix in 2015) is not studied in what I found.

---

## 8. Announcement effects: macro releases, pre-FOMC drift

### Takeaway
FX jumps to macro surprises within minutes, with little exploitable drift for a slow trader. The pre-FOMC equity drift was huge in 1994-2011 (49 bp in the 24 h before announcements, ≈ 80 % of the equity premium) and **essentially disappeared after 2015**: a textbook post-publication decay.

### Cited Findings
- **Andersen, Bollerslev, Diebold, Vega (AER 2003)**:
  - Data: 6 years of real-time quotes for USD against DEM, GBP, JPY, CHF and EUR.
  - Announcement surprises produce **conditional mean jumps**, i.e. fast price discovery; the response is asymmetric (bad news has a bigger impact).
  - Source: [NBER WP 8959](https://www.nber.org/system/files/working_papers/w8959/w8959.pdf); [SSRN](https://papers.ssrn.com/abstract=313660)
- **Lucca & Moench (JF 2015)**: since 1994 the S&P 500 rose on average 49 bp in the 24 h before scheduled FOMC announcements, accounting for ≈ 80 % of annual realized excess stock returns (sample Sep 1994-Mar 2011). The working paper came out in 2011 — [IDEAS (JF)](https://ideas.repec.org/a/bla/jfinan/v70y2015i1p329-371.html); [R-bloggers update](https://www.r-bloggers.com/2015/03/update-on-the-pre-fomc-announcement-drift/amp/)
- **Kurov, Wolfe, Gilbert ("The disappearing pre-FOMC announcement drift", sample to Dec 2019)**: the drift "essentially disappeared after 2015", both with and without press conferences. Possible explanation: reduced uncertainty. Another study argues the moderation reflects time variation that was already present in older data — [Skidmore PDF](https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf); [IDEAS, Finance Research Letters 2021](https://ideas.repec.org/a/eee/finlet/v40y2021ics1544612320315956.html); [Applied Economics 2025, IDEAS](https://ideas.repec.org/a/taf/applec/v57y2025i17p2021-2037.html)
- Quantpedia: the FOMC equity drift occurs in periods of high uncertainty — [Quantpedia](https://vvv.quantpedia.com/?p=4197)
- Gao et al.: intraday momentum is stronger on macro-news days — [Monash repository](https://researchmgt.monash.edu/ws/files/519509174/494419119_oa.pdf)

### Inferences
- For a retail MT5 AI, announcements matter mainly as **volatility and risk events** (widen stops, cut size, avoid trading the release minute when spreads explode) and as days when intraday momentum is stronger. They are not a reliable directional drift.
- Pre-FOMC drift should be treated as decayed. It may still be a useful conditional feature in high-uncertainty regimes.

### Gaps
- Post-announcement drift in FX at 15-minute+ horizons after 2018: no source retrieved. No net-of-cost FX news-trading study found.

---

## 9. Crypto intraday patterns (time of day, funding, quarter-hour)

### Takeaway
Bitcoin shows intraday momentum (first session → last session, driven by liquidity provision), hour-of-day return patterns (22:00-23:00 UTC strongest in 2015-2022) and strong periodic volatility bursts at :00/:15/:30/:45 linked to algorithms and funding. Return patterns are unstable: a large multi-exchange study found no consistent or persistent calendar effect. Volatility periodicity is robust and growing.

### Cited Findings
- **Shen, Urquhart, Wang**: Bitcoin intraday time-series momentum; strongest after the highest-volume or highest-volatility first sessions and in downturns; driven by liquidity provision — [Birmingham](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/)
- **Quantpedia (Gemini hourly data, 09/10/2015-03/02/2022)**: 22:00 and 23:00 UTC are the best hours and 03:00-04:00 UTC the worst. Buying at 21:00 UTC and selling at 23:00 UTC gave 33 %/yr, vol 20.9 %, max drawdown -22.5 %. No costs included and no post-2022 test — [Quantpedia](https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/)
- **Baur, Cahill, Godfrey, Liu**: 15 M+ observations from 7 exchanges show time-varying time-of-day / day-of-week effects in Bitcoin, with **no consistent or persistent** pattern — [Quantpedia summary](https://quantpedia.com/are-there-any-simple-calendar-effects-in-bitcoin-market/)
- **Periodicity in crypto volatility and volume**: BTC and ETH show a large volatility burst in the first minute of each hour, medium bursts at :15/:30/:45 and small bursts every 5 minutes. The patterns have grown stronger over the years and relate to algorithmic trading and futures funding times — [Quantpedia](https://quantpedia.com/?p=16396); [paper listing](https://astro.paperswithcode.com/paper/periodicity-in-cryptocurrency-volatility-and)
- **Kim & Hansen ("The Quarter-Hour Effect", arXiv 2607.09426, 2026)**: Binance perpetuals (BTC, ETH, XRP, SOL, DOGE, ADA), Jan 2021-Oct 2024. Returns at quarter-hour openings show out-of-sample predictability, and opening order imbalance predicts returns over 4-12 h. The abstract does not quantify profitability after fees — [arXiv](https://arxiv.org/abs/2607.09426)
- Large liquid coins show daily momentum and illiquid coins show reversal — [Up or down? (Medeniyet repository)](https://earsiv.medeniyet.edu.tr/items/23a96c9f-3952-4bdf-aec5-abafb3aaab70); [Economics & Finance 2022, "Intraday return predictability in cryptocurrency markets: momentum, reversal, or both"](https://ideas.repec.org:443/a/eee/ecofin/v62y2022ics1062940822000833.html)
- Using hourly Kraken prices 2016-2025, one study finds a "Reversal/Reversal" configuration for Bitcoin with an 08:00 UTC day start, and "Long/Reversal" for Ethereum with a 05:00 UTC start — [MDPI JRFM 19(9) 692](https://www.mdpi.com/1911-8074/19/9/692)

### Inferences
- Crypto CFD spreads on FTMO/MT5 are much wider than Binance futures fees, so hour-of-day return patterns are unlikely to survive. Volatility periodicity (hour starts, funding at 00/08/16 UTC on most exchanges) is useful for stop placement and entry timing.

### Gaps
- Funding-time **return** effects (not just volatility) with magnitudes: no reliable source retrieved.

---

## 10. Intraday volatility predictability and its use (sizing, stops)

### Takeaway
Volatility is far more predictable than direction: by time of day, by recent days, and by events. The cleanest evidence that this matters for profitability comes from the noise-area strategy. Sizing positions to recent daily volatility raised the result from 380 % to 1 985 % (Sharpe 1.24 → 1.33). VWAP or band trailing stops raised the Sharpe from 0.61 to 1.24 and cut the worst day from -10.3 % to -4.8 %.

### Cited Findings
- Time-of-day volatility bands (14-day average move from the open at the same HH:MM) define where "noise" ends — [paper PDF](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)
- Effect of stops and sizing on the same signal:
  - Opposite-band stop: Sharpe 0.61, max drawdown 21 %, worst day -10.3 %.
  - VWAP/current-band stop: Sharpe 1.24, max drawdown 12 %, worst day -4.8 %.
  - Plus volatility sizing (≈ 2 % daily vol target, max 4× leverage): Sharpe 1.33.
  - Source: [paper PDF, Table A1](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)
- Intraday momentum is stronger on more volatile days; the noise-area Sharpe rises with VIX up to about 40 — [Monash repository](https://researchmgt.monash.edu/ws/files/519509174/494419119_oa.pdf); [paper PDF](https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content)
- In crypto, volatility and volume periodicity (hour, :15 marks, day-of-week) is robust and growing — [Quantpedia](https://quantpedia.com/?p=16396)
- Heston-Korajczyk-Sadka: volume, volatility and spreads show strong daily periodicity — [paper PDF](https://www.bauer.uh.edu/departments/finance/documents/Heston_Korajczyk_Sadka_paper_UH.pdf)

### Inferences
- For an FTMO account (-5 %/day, -10 % total), the most reliable "intraday effect" to exploit is volatility-aware risk: stops placed outside the time-of-day noise band, size scaled to forecast volatility, and less exposure around fixes, announcements and hour starts. This improves survival odds even when the directional edge is near zero.

### Gaps
- No retrieved study on volatility-managed intraday strategies specifically on FX or gold CFDs.

---

## 11. Summary table (for the report writer)

| Effect | Size (paper) | Costs vs retail CFD | Status 2018-2026 |
|---|---|---|---|
| Last half-hour intraday momentum (Gao; Baltussen) | Gross, futures 1974-2020: indices 6.9 %/yr (≈ 2.7 bp/day*), Sharpe 1.73; commodities 4.3 %/yr; FX 0.85 %/yr | Edge ≈ spread on index CFDs; below spread in FX | Alive gross (hedging-driven). Net retail: marginal or dead. No simple OHLCV intraday-momentum signal passed on MNQ 2021-25 |
| Noise-area breakout + VWAP stop + vol sizing (Zarattini) | SPY 2007-24: 19.6 %/yr, Sharpe 1.33 net; 2024: +32 % (post-publication); futures portfolio Sharpe 1.65 | Assumes ETF costs (≈ 3-4 bp/trade edge*) | Author-reported, alive through 2024; not independently replicated |
| Opening-range breakout | QQQ alpha 33 %/yr; stocks in play Sharpe 2.81 (2016-23) | Index CFDs: gross +0.13 R → net ≈ 0 | **Dead net of CFD costs** (MQL5 replication 2015-2026; MNQ 2021-25) |
| FX fix "W" reversal | 2.5-4 bp/day; 5-9 %/yr gross per window | Negative with full spread; Sharpe 0.12-1.03 with half spread | Robust to 2019; Tokyo weaker after 2014; net profits small |
| FX local-hours depreciation (Breedon-Ranaldo) | "Profitable" EURUSD strategy | Not retrieved | Unknown recently |
| Pre-FOMC drift | 49 bp in 24 h; 80 % of the equity premium (1994-2011) | n/a | **Disappeared after 2015** |
| Macro news FX | Jumps within minutes | n/a | No slow-trader drift |
| Gold Asia-up / West-down | Documented (2018 paper) | Gold spread small (≈ 0.6-0.8 bp*) | Untested recently; worth testing in-house |
| Crypto hour-of-day | 33 %/yr gross (21-23 UTC, 2015-22) | No costs | Not persistent (Baur et al.); volatility periodicity robust |
| Volatility timing/sizing | Sharpe 0.61 → 1.24 → 1.33 via stops and sizing | Reduces costs per unit of risk | Robust |

(*) = my own conversions, see Inferences.

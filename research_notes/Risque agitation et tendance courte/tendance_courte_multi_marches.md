# Short-horizon trend following and cross-market links across FTMO-type CFD markets (days to a few weeks, flat on weekends)

Legend: **[V]** = number read in the source during this research (primary text, or a fetched summary of it); **[A]** = taken from an aggregator or search-engine summary of the paper, primary text not read; **[R]** = recalled from prior knowledge, NOT re-checked in this session (treat with caution); **[NPR]** = not peer-reviewed (working paper, preprint, industry note).

## 1. Is there a short-lookback trend effect (1 day to 1 month), and how big is it after costs?

### Takeaway
Before about 2003-2009, short trend signals (3 to 20 days) were as good as or better than slow ones: Sharpe ratio about 0.8 gross on a diversified futures pool. Since about 2009 the fast signals have largely collapsed. A 5-day signal fell from 0.84 to 0.12 Sharpe, gross of costs. The collapse is worst in equity indices and FX, which are the core of a FTMO CFD universe. Commodities (and bonds, which FTMO does not offer) held up better. Net of retail CFD costs, a fast (days) trend edge on FX and indices should be assumed to be about zero today. A 1-to-3-month horizon still has some evidence behind it, but it is weaker than its history.

### Cited Findings
- **Lempérière, Deremble, Seager, Potters, Bouchaud (2014), "Two centuries of trend following", Journal of Investment Strategies 3(3) [V, preprint arXiv:1404.3274]:**
  - Trend signal: price minus an exponential moving average, divided by a volatility estimate. The main time scale is n = 5 months.
  - Universe: 27 instruments, made of 7 commodities, 7 stock indices, 7 bonds and 6 currencies.
  - 1960 onward: pooled Sharpe ratio 0.78, t-stat 5.9 (5.0 once the long-only drift is removed).
  - By sector: commodities 0.80, currencies 0.57, bonds 0.49, indices 0.41.
  - Sensitivity to the moving-average length: Sharpe 0.80 (2 months), 0.78 (5 months), 0.76 (10 months), 0.57 (20 months). Results are "only weakly dependent on n".
  - The P&L is fictitious: "no attempt is made to model any realistic implementation costs".
  - Key line for this project, on 3-day trends: "The effect seems to have completely disappeared since 2003 (or has maybe even inverted)". Slow (5-month) trends show no significant decay, and the 10-year rolling Sharpe ratio has never been negative over two centuries.
  - Source: [arXiv/ar5iv 1404.3274](https://ar5iv.arxiv.org/html/1404.3274)
- **Kurth, Eisler, Rej, Bouchaud (submitted 2 July 2026), "Is Trend Still Your Friend? A Microstructural Account of the Demise of Short-Term Trend-Following" [V, NPR arXiv preprint]:**
  - Data: about 100 liquid futures, 1995-2025.
  - Equal-risk portfolio Sharpe ratios, pre-2009 vs post-2008 (Table 1):
    - 5-day signal: 0.84 ± 0.27 → 0.12 ± 0.24
    - 10-day: 0.83 → 0.22
    - 20-day: 0.79 → 0.27
    - 50-day: 0.70 → 0.40
  - Before 2009 the fastest signal was the best. After 2008 the ordering reverses and the fastest signal is the worst.
  - By asset class: in equity indices trend "has effectively vanished"; in FX the post-2010 P&L is "flat"; commodities and interest-rate yields show "no appreciable degradation".
  - The dividing variable is the volatility-normalised tick size. On small-tick contracts post-2008 Sharpe ratios are about zero (slightly negative for the fastest signals). On large-tick contracts they are about 1.0-1.2, with a degradation of only 0-30%.
  - Proposed mechanism: after the crisis, high-frequency market makers took over, and they withdraw liquidity in front of predictable directional flow. This broke the self-reinforcing loop in which trend trading pushed prices further.
  - The authors' reading of the industry index: the SG CTA Index has been "effectively flat or negative for the past fifteen years".
  - Sources: [arXiv abs 2607.01550](https://arxiv.org/abs/2607.01550), [HTML](https://arxiv.org/html/2607.01550)
- **Moskowitz, Ooi, Pedersen (2012), "Time series momentum", Journal of Financial Economics 104(2):228-250:**
  - Universe and sample: 58 futures and forwards (equity indices, currencies, commodities, bonds), January 1985 to about 2009 in the paper (the AQR data extends this) [A].
  - Each position is scaled to 40% annualized volatility [A].
  - Returns persist for 1 to 12 months and partially reverse at longer horizons [A].
  - Gross Sharpe ratio of the single-asset 12-month strategy, averaged across assets: 0.38 [A].
  - Gross Sharpe ratio of the portfolio diversified across all assets and lookbacks: 1.8 [A, CXO summary].
  - Average pairwise correlation of single-asset momentum returns: below 0.1 for each lookback [A].
  - [R] In the pooled regression of the paper's Figure 1, the 1-month lag is positive and significant. The lookback/holding grid (k, h in months) is positive for k = 1 month, but weaker than for k = 3 to 12.
  - Sources: [SSRN abstract](https://papers.ssrn.com/abstract=2089463); [CXO summary](https://www.cxoadvisory.com/momentum-investing/intrinsic-momentum-diversified-across-futures/); [Quantpedia](https://quantpedia.com/strategies/time-series-momentum-effect/)
- **Hurst, Ooi, Pedersen (2017), "A Century of Evidence on Trend-Following Investing", Journal of Portfolio Management 44(1):**
  - Universe and sample: 67 assets, 1880-2016 [A].
  - Signals: equal-weighted 1-, 3- and 12-month lookbacks [A].
  - Net returns positive in every decade [A].
  - Sharpe ratio about 0.76 after estimated trading costs and a 2%/20% fee; about 0.4 is quoted as an average figure elsewhere. The CXO and ETF.com summaries are ambiguous on which is which [A, conflicting].
  - The abstract explicitly discusses "increased correlations across markets since the credit crisis" and more assets in the strategy [V, abstract].
  - Sources: [AQR page](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing); [CXO](https://www.cxoadvisory.com/momentum-investing/trend-following-with-intrinsic-momentum-over-the-very-long-run)
- **Levine & Pedersen (2016), "Which trend is your friend?", Financial Analysts Journal 72(3):51-66 [A]:**
  - Time-series momentum and moving-average crossovers are, in their general forms, equivalent.
  - Both are linear filters that can be described by a "trend signature" of weights by horizon.
  - Implication: changing the indicator shape does not create a new edge. Only the horizon weighting matters.
  - Source: [CFA Institute page](https://rpc.cfainstitute.org/research/financial-analysts-journal/2016/which-trend-is-your-friend)
- **SG Short-Term Traders Index:**
  - Tracks the 10 largest diversified short-term CTAs with a holding period under 10 days [A, SG/press].
  - It sometimes diverges from the SG Trend Index. Examples: March 2016, short-term -1.18% (+5.47% year to date) vs SG Trend -2.91%; one November, short-term +0.43% vs SG Trend -1.25%.
  - No long-run performance figures were found in this session.
  - Sources: [Société Générale CTA announcement](https://www.societegenerale.co.uk/en/news/news/news/cta-index-performance-announcement-march/); [Hedgeweek](https://www.hedgeweek.com/ctas-march-dip-continues-april-says-societe-generale-prime-services/)
- **Baz, Granger, Harvey, Le Roux, Rattray (2015), "Dissecting investment strategies in the cross section and time series", SSRN [R, NPR]:**
  - Compares cross-sectional and time-series versions of carry, momentum and value across asset classes.
  - [R] Time-series momentum looked stronger than cross-sectional momentum, using an intermediate lookback.
  - The paper was not retrieved; its exact numbers are unverified.

### Inferences
- The two Bouchaud-group papers agree:
  - The fast trend horizon (days) was the best before 2003-2009 and is now the worst.
  - FX majors and equity indices are the asset classes where trend has "vanished/flat" since about 2010.
  - Most FTMO CFDs are FX and indices, so a short-horizon trend system built mainly on them should expect about zero gross edge. Costs would then make it negative.
- Commodities, including gold and oil, are the only FTMO-tradable class without a reported post-2008 degradation in Kurth et al. That is consistent with the project's earlier finding that the only measured edge was the long-term trend on gold. The paper does not say whether gold or crude are classed as "large-tick".
- Order of magnitude to plan for: a net single-market short-horizon trend Sharpe of 0 to 0.2 on FX and indices, and perhaps 0.2 to 0.4 on commodities. This is an inference, not a measured figure.
- The project's own earlier benchmark is consistent with this. It used long-term trend on 36 markets with realistic costs at 10% annual volatility, and found +0.5%/month, Sharpe 0.46 on 2018-2025 (project CLAUDE.md, section 5; internal, not peer-reviewed).

### Gaps
- Exact Sharpe ratios for the k = 1 month / h = 1 month cell in Moskowitz-Ooi-Pedersen, and for the 1-month signal in Hurst-Ooi-Pedersen. The PDFs could not be parsed in this session.
- The list of which instruments are "large-tick" in Kurth et al. 2026.
- Long-run SG Short-Term Traders Index statistics (annual return and Sharpe ratio 2008-2025).
- Baz et al. 2015 numbers.

## 2. Diversification arithmetic: how the portfolio Sharpe ratio grows with the number of markets, and what Sharpe per market 1%/month requires

### Takeaway
With N markets that each have Sharpe ratio s and an average pairwise correlation ρ of their strategy returns, the portfolio Sharpe ratio is s·√(N / (1+(N−1)ρ)). As N grows, it cannot exceed s/√ρ. Historically ρ for trend returns was below 0.1, but correlations rose after 2008. Reaching 1%/month (12%/year) at 10% annual volatility needs a portfolio Sharpe of about 1.2. With ρ = 0.1 that requires a net Sharpe per market of about 0.4 even with very many markets, which is well above what short-horizon trend now delivers on FX and indices.

### Cited Findings
- Average pairwise correlation of single-asset time-series momentum returns: below 0.1 for each lookback (58 instruments, 1985-2012) [A] — [CXO summary of Moskowitz-Ooi-Pedersen](https://www.cxoadvisory.com/momentum-investing/intrinsic-momentum-diversified-across-futures/)
- Single-asset average gross Sharpe ratio 0.38 vs a diversified gross Sharpe ratio of 1.8 (all assets and lookbacks). This shows the breadth effect empirically, before costs [A] — [same source](https://www.cxoadvisory.com/momentum-investing/intrinsic-momentum-diversified-across-futures/)
- Hurst-Ooi-Pedersen flag "increased correlations across markets since the credit crisis" as a risk to trend-following [V, abstract] — [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- Grinold's fundamental law: information ratio ≈ skill (information coefficient) × √breadth, where breadth counts independent bets [R]. Grinold (1989), Journal of Portfolio Management 15(3); Grinold & Kahn, *Active Portfolio Management*.

### Inferences
- Worked numbers, using the formula above (my computation):

  | Sharpe per market (net) | ρ | N=10 | N=30 | N=45 | limit (N→∞) |
  |---|---|---|---|---|---|
  | 0.10 | 0.10 | 0.23 | 0.28 | 0.29 | 0.32 |
  | 0.20 | 0.10 | 0.46 | 0.55 | 0.58 | 0.63 |
  | 0.20 | 0.25 | 0.35 | 0.38 | 0.39 | 0.40 |
  | 0.40 | 0.10 | 0.92 | 1.11 | 1.16 | 1.26 |

- Annual return ≈ Sharpe × volatility:
  - 1%/month at 10% annual volatility requires a Sharpe of about 1.2.
  - 1%/month at 6% annual volatility requires a Sharpe of about 2.0.
  - A FTMO-safe volatility, where -10% total is a rare drawdown, is more like 6-8% per year. The corresponding Sharpe of about 1.5-2 is far above any published net trend result since 2009.
- On FTMO CFD universes, ρ is probably well above the historical 0.1:
  - FX pairs share the dollar factor (see section 4).
  - Indices are highly correlated with each other.
  - Many FTMO "markets" are near-duplicates: several USD crosses, several US indices.
  - The effective number of independent bets among about 45 CFDs is plausibly 10-15, not 45.
- Practical rule: adding markets helps only if they bring independent bets. An edge of zero per market stays zero whatever N is.

### Gaps
- No source found giving post-2008 average pairwise correlations of trend returns, by asset class, specifically for FX/index/commodity CFDs.
- Grinold's formula is recalled, not fetched.

## 3. Effect of being flat on weekends, daily rebalancing costs, and gap risk

### Takeaway
No academic study was found that measures trend performance when positions must be closed every Friday. Closing on Friday and reopening on Monday for every position doubles the round-trip costs per week. It also drops the exposure over the weekend gap. For a multi-week trend, part of the move happens over that gap, so the strategy forgoes part of the return it was designed to capture. At day-to-week horizons, costs become the dominant term.

### Cited Findings
- Lou, Polk, Skouras (2019), "A tug of war: overnight versus intraday expected returns", Journal of Financial Economics [A]:
  - Across 14 equity strategies, momentum profits are earned "entirely overnight" while reversal profits are earned intraday.
  - The study covers single stocks, not futures. Even so, it suggests that removing exposure while the market is closed can remove a disproportionate share of momentum profit.
  - Source: [LSE Research Online](https://researchonline.lse.ac.uk/id/eprint/87481)
- Lempérière et al. assume no costs at all. They note that their P&L is fictitious [V] — [ar5iv](https://ar5iv.arxiv.org/html/1404.3274)
- Han, Kang & Ryu (crypto, see section 6) find that accounting for daily price fluctuations (intraday liquidation) and costs turns many significant momentum portfolios into insignificant ones [A] — [AUT ACFR paper](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)

### Inferences
- Cost arithmetic (inference): reopening every Monday adds about 52 extra round trips per year per market. At a typical retail CFD round-trip cost of 0.5 to 2 basis points on FX majors, more on crosses and indices, that comes to roughly 0.3% to 1% per year of notional per market. That is comparable to the entire gross post-2009 short-horizon trend edge on FX and indices.
- Swaps: holding overnight in the week costs the swap; on Wednesday the CFD swap is usually triple. Being flat on weekends avoids weekend swaps only if the broker charges them on Friday instead (it usually charges Wednesday). This needs to be checked in the FTMO symbol specifications. This is broker practice, not sourced here.
- Gap risk is mostly a safety benefit:
  - Weekend gaps in FX and indices can jump past stops, for example the 2015 Swiss franc unpeg on a Thursday or weekend political news.
  - Being flat removes the tail that could breach the FTMO -5% daily limit at Monday's open.
  - The price is the lost trend return carried over weekends, which is not quantified here.
- An honest test is the project's own backtest: the same signal with and without Friday close, with per-market spreads, commissions and swaps.

### Gaps
- No peer-reviewed measurement of the weekend share of trend returns in futures/FX was found.
- No published FTMO CFD cost table was checked.

## 4. Cross-market common factors and lead-lag links: which are stable?

### Takeaway
Contemporaneous common factors are strong and stable:
- the dollar factor in FX;
- risk-on/risk-off across equities, the yen, the Swiss franc and gold;
- commodity currencies with their commodities.

These factors are useful for risk control and for counting independent bets, because they tell you which positions are really the same bet. Lead-lag effects that could be traded at daily-to-monthly horizons are much weaker:
- The US lead over other stock markets is a monthly, mostly in-sample-strong finding.
- Oil predicting the Canadian dollar works mainly contemporaneously at daily frequency, not as a profitable lag.

### Cited Findings
- **Verdelhan (2018), "The share of systematic variation in bilateral exchange rates", Journal of Finance 73(1) [A]:**
  - The dollar factor and the carry factor together explain 18% to 80% of monthly bilateral exchange-rate movements.
  - The dollar factor alone explains 13% to 88%.
  - The carry factor alone explains 0% to 23% (adjusted R²) among developed countries.
  - Sources: [MIT DSpace](https://dspace.mit.edu/handle/1721.1/122354); [Econbrowser discussion](https://econbrowser.com/?p=10758)
- **Lustig, Roussanov, Verdelhan (2011), "Common risk factors in currency markets", Review of Financial Studies 24(11) [R]:** A "dollar" (level) factor and a "carry" (high-minus-low interest rate) factor explain most of the cross-section of currency portfolio returns.
- **Ferraro, Rogoff, Rossi (2015), "Can oil prices forecast exchange rates?", Journal of International Money and Finance 54:116-141 [A]:**
  - Oil prices show little systematic relation with USD/CAD at monthly and quarterly frequency.
  - There is a very short-term relationship at daily frequency, robust to using contemporaneous or lagged oil prices.
  - Source: [BSE abstract](https://bse.eu/research/publications/can-oil-prices-forecast-exchange-rates-empirical-analysis-relationship-between); [IDEAS](https://ideas.repec.org/p/upf/upfgen/1461.html)
  - [R] The out-of-sample gain with lagged oil is much smaller than with contemporaneous oil. The "forecast" result is largely contemporaneous.
- **Chen & Rogoff (2003), "Commodity currencies", Journal of International Economics 60(1) [R]:** World commodity prices in USD have a strong and stable influence on the real exchange rates of Australia and New Zealand, less clearly Canada. This is a contemporaneous link, not a lead.
- **Rapach, Strauss, Zhou (2013), "International stock return predictability: what is the role of the United States?", Journal of Finance 68(4):1633-1662 [A]:**
  - Lagged US returns significantly predict returns in many non-US industrialized countries at monthly frequency.
  - Lagged non-US returns have limited power to predict US returns.
  - Predictability is markedly stronger in recessions.
  - Source: [SUFE summary](https://academicnewsletter.sufe.edu.cn/info/360253)
  - A later paper asks whether this US role is time-varying ([EMU repository](https://i-rep.emu.edu.tr/items/32c97fff-b7a6-4b20-b7ae-2b55b0501ca2/full)), which suggests instability. Its result was not read.

### Inferences
- Stable and useful, as risk structure:
  - **Dollar factor:** many FTMO FX pairs (EURUSD, GBPUSD, AUDUSD, USDCHF, USDJPY…) are largely one bet on the dollar. A trend system on them has low breadth.
  - **Commodity currencies vs their commodity:** AUD and NZD with metals and commodities, CAD with oil, contemporaneous.
  - **Equity-index co-movement.**
- Weak or unstable as tradable lead-lag:
  - US-leads-world at monthly frequency was documented in-sample over decades. Futures now trade almost 24 hours, so a daily close-to-close US lead over European and Asian indices is largely arbitraged at the open.
  - Oil → CAD at a daily lag is fragile.
- The risk-on/risk-off grouping (equities vs JPY/CHF/gold) was not sourced in this session. It is standard practitioner knowledge, but its stability is debated. In particular, the gold/equity correlation flips sign across regimes.

### Gaps
- No direct primary source was fetched for risk-on/risk-off factor stability, or for intraday/daily lead-lag decay after 2010.
- The exact out-of-sample statistics of Ferraro-Rogoff-Rossi (lagged vs contemporaneous) were not verified.

## 5. Regime dependence: volatility, crisis periods, and recent (2010-2025) decay

### Takeaway
Trend has historically done best in extreme markets (the "smile"). Its decay since about 2009 is now documented. The decay concentrates in fast signals and in FX and equity indices. Slow signals and commodities are the most robust. The industry trend index (SG CTA) has been flat or negative for roughly 15 years by one 2026 reading, with episodic strong years in between.

### Cited Findings
- Time-series momentum "performs best during extreme markets" (Moskowitz-Ooi-Pedersen 2012) [A] — [AQR dataset page/summary](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data)
- Post-2008 collapse of fast signals, and of FX and indices (Kurth et al. 2026); the SG CTA Index "flat or negative for the past fifteen years" (authors' description) [V, NPR] — [arXiv html 2607.01550](https://arxiv.org/html/2607.01550)
- 3-day trends disappeared since about 2003; the 5-month trend shows no significant decay (Lempérière et al. 2014) [V] — [ar5iv](https://ar5iv.arxiv.org/html/1404.3274)
- Increased cross-market correlations since the credit crisis (Hurst-Ooi-Pedersen 2017) [V, abstract] — [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- Short-term CTAs sometimes outperform trend CTAs in choppy, volatile months, for example March 2016 [A] — [SG](https://www.societegenerale.co.uk/en/news/news/news/cta-index-performance-announcement-march/)

### Inferences
- A short-horizon trend system should be judged on its 2010-2025 sample only. Pre-2009 backtests overstate the fast edge by roughly 3-7x (5-day Sharpe 0.84 → 0.12).
- The "crisis alpha" mostly comes from slow trends that are already positioned when a crisis hits. A fast system that is flat on weekends captures less of it, because crises often gap.

### Gaps
- No verified numbers on trend Sharpe conditional on high vs low volatility regimes.
- Annual SG Trend / Short-Term index returns for 2010-2025 were not retrieved; the "flat for 15 years" statement comes from one preprint.

## 6. Crypto short-horizon momentum, and after costs

### Takeaway
In Bitcoin's early sample (2011-2018), one-week time-series momentum was strong. Studies that use realistic costs and intraday liquidation find many momentum portfolios lose significance. Time-series momentum survives better than cross-sectional momentum. Evidence after about 2021, when crypto matured and correlated more with equities, was not verified here.

### Cited Findings
- **Liu & Tsyvinski (2021), "Risks and returns of cryptocurrency", Review of Financial Studies 34(6):2689-2727:**
  - Strong time-series momentum, and investor-attention proxies forecast returns [A].
  - Next-week Bitcoin return: 11.2% for the top fifth of last-week returns vs 2.6% for the bottom fifth; Sharpe 0.45 vs 0.19 [A, CXO/NBER summary; sample about 2011-2018].
  - Sources: [NBER w24877](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf); [IDEAS RFS](https://ideas.repec.org/a/oup/rfinst/v34y2021i6p2689-2727..html); [CXO](https://www.cxoadvisory.com/currency-trading/crypto-asset-risks-and-returns/)
- **Liu, Tsyvinski, Wu (2022), "Common risk factors in cryptocurrency", Journal of Finance 77(2) [R]:** A three-factor model (crypto market, size, momentum) prices the cross-section of coins. Its momentum factor is cross-sectional and weekly.
- **Han, Kang & Ryu, "Time-series and cross-sectional momentum in the cryptocurrency market: a comprehensive analysis under realistic assumptions" [A, NPR/working paper]:**
  - With transaction costs and daily price fluctuations accounted for, "many momentum portfolios are liquidated", and many significant returns become insignificant.
  - Time-series momentum evidence stays strong; cross-sectional momentum is weak.
  - Source: [AUT ACFR PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)
- Crypto momentum strategies can need up to about 85% weekly turnover, with profitability problems after costs (search summary of crypto-anomaly research) [A, source not opened] — [search lead: arXiv 2501.12841](https://arxiv.org/html/2501.12841v3)

### Inferences
- Crypto CFDs at FTMO trade 7 days a week, but the trader must be flat on weekends. For crypto that cuts about 2/7 of the time, during which the market keeps moving. Every Monday re-entry pays the wide crypto CFD spread.
- Crypto is probably the FTMO class where a weekly trend signal has the most published support. It is also the class with the highest costs, the highest tail risk, and the most decline in early anomalies.

### Gaps
- No verified post-2020 net-of-cost Sharpe ratio for one-week crypto time-series momentum.
- Liu-Tsyvinski-Wu 2022 numbers are recalled, not checked.

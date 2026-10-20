# Predictability of volatility and risk — and its use for position sizing and stop placement (FX, metals, indices, crude, crypto; 15 min to a few weeks)

Scope note: research done 14/10/2026, ~20 tool calls. Several primary PDFs (Harvey et al. 2018, Andersen & Bollerslev 1998 IER) could not be text-extracted in this environment; numbers from them are taken from the authors' abstracts or from secondary summaries (flagged). Items recalled from background knowledge but not re-verified in this session are listed under "Gaps", never under "Cited Findings".

## 1. Volatility clustering and ARCH/GARCH — how predictable is next-day / next-week volatility?

### Takeaway
Volatility (unlike the direction of returns) is strongly and robustly predictable from its own past: this is the single best-established forecastability result in financial econometrics. Forecasts look "bad" (R² of a few %) only when scored against noisy squared daily returns; scored against high-frequency realized volatility, the same models explain a large share (order of 50-60 %) of next-day variation.

### Cited Findings
- Andersen & Bollerslev (1998), "Answering the Skeptics: Yes, Standard Volatility Models Do Provide Accurate Forecasts", International Economic Review 39(4), 885-905. ARCH/SV models have highly significant, persistent parameters in sample, yet traditional evaluation (regressing squared returns on forecasts) gives poor-looking fits; the authors show the models give "strikingly accurate interdaily forecasts for the latent volatility factor" once volatility is measured ex post with intraday data — [IDEAS/RePEc](https://ideas.repec.org/a/ier/iecrev/v39y1998i4p885-905.html); [NBER w6023](https://www.nber.org/papers/w6023)
- The low R² of GARCH forecasts against squared returns is consistent with the population value expected for a *correctly specified* GARCH model (i.e., low R² is a measurement-noise artefact, not a model failure) — [search summary of the IER paper, Kellogg page](https://www.kellogg.northwestern.edu/academics-research/research/detail/1998/answering-the-skeptics-yes-standard-volatility-models-do-provide/)
- Data in that paper: Deutsche mark-dollar and yen-dollar, with continuously recorded 5-minute returns used to build the realized measure — [Duke scholars record](https://scholars.duke.edu/publication/643385) (dataset details from search summary; exact table values not retrieved)
- Engle (1982, Econometrica) and Bollerslev (1986, Journal of Econometrics) are the founding ARCH / GARCH papers; Engle shared the 2003 Sveriges Riksbank Prize "for methods of analyzing economic time series with time-varying volatility (ARCH)" (Granger for cointegration). The nobelprize.org page returned HTTP 403 to automated fetch in this session, so the citation wording is not quoted from source here — see Gaps.

### Inferences
- For a 15-min-to-weeks trader, volatility is the one quantity that *can* be forecast reliably; direction cannot (see section 3). Practical consequence: the edge from volatility forecasting is mostly in **sizing and stop distance** (risk control), not in return prediction.
- Scoring a volatility forecast against single-bar squared returns will always look weak (R² of a few %); score against realized volatility built from finer bars (e.g., M1/M5 sums for an M15/H1/daily horizon).

### Gaps
- Exact R² values of Andersen-Bollerslev (1998): commonly quoted as roughly 0.05 against squared daily returns versus ~0.5 against 5-min realized variance for DM/$ — background knowledge, NOT verified in this session (PDF not extractable).
- Engle (1982) Econometrica 50(4): 987-1007 and Bollerslev (1986) Journal of Econometrics 31(3): 307-327 — bibliographic details from background knowledge, not re-fetched. Nobel citation not fetched (403).

## 2. Realized volatility, HAR-RV and long memory

### Takeaway
Realized volatility (sum of squared intraday returns) turns latent volatility into a nearly observable quantity; a simple linear regression of tomorrow's RV on daily, weekly and monthly averages of past RV (Corsi's HAR) captures the long memory of volatility and remains the hard-to-beat benchmark.

### Cited Findings
- Corsi (2009), "A Simple Approximate Long-Memory Model of Realized Volatility", Journal of Financial Econometrics 7(2), 174- — [OUP](https://academic.oup.com/jfec/article/7/2/174/856522); [SSRN](https://papers.ssrn.com/abstract=1365738)
- HAR-RV: OLS regression of RV on lagged daily, weekly and monthly RV components; all three components positive and significant ("heterogeneous persistence across daily, weekly, and monthly horizons"); one application reports in-sample adjusted R² = 0.605 — [Pollok 2025, arXiv 2506.07928](https://arxiv.org/pdf/2506.07928) (firm-level equity application, not Corsi's original table)
- HAR "has become the workhorse of this literature due to its consistently good forecasting performance" and is estimated by standard linear regression — [arXiv 2506.07928](https://arxiv.org/pdf/2506.07928); see also [GARP whitepaper on volatility forecasting](https://www.garp.org/hubfs/Whitepapers/a2r1W000000iDb0QAE_RiskIntell.6.20.19.Whitepaper.Volatility.pdf)
- Long memory: the autocorrelation of absolute returns decays slowly, as a power law with exponent β in [0.2, 0.4] (Cont's stylized fact 8) — [Revisiting Cont's stylized facts, arXiv 2311.07738](https://arxiv.org/html/2311.07738v2)
- Andersen & Bollerslev (1998, JF) show for DM/$ 5-minute data that intraday patterns, macro announcements and longer-run ARCH persistence "account for a substantial fraction of return variability, both at the intraday and daily level" — [Duke](https://scholars.duke.edu/publication/761296); [NBER w5783](https://projects.nber.org/papers/w5783)

### Inferences
- For COLLAPSAR-type inputs, feeding the network RV aggregated at several horizons (e.g., last hour / day / week / month) is the minimal "HAR-like" view; the network should at least match a linear HAR before anything fancier is claimed.
- Because the claim "HAR is hard to beat" is about the *loss on volatility*, any machine-learning gain must be measured on out-of-sample volatility loss (QLIKE/MSE) AND on the sizing outcome, since tiny forecast-loss gains can matter economically (Pollok's point) — [arXiv 2506.07928](https://arxiv.org/abs/2506.07928)

### Gaps
- Andersen, Bollerslev, Diebold & Labys (2003), "Modeling and Forecasting Realized Volatility", Econometrica 71(2): 579-625 — citation from background knowledge, not fetched; their reported out-of-sample R² for FX RV forecasts (DM/$, yen/$) not retrieved.
- Corsi's original out-of-sample R² figures (USD/CHF, S&P 500 futures, T-bond futures) not retrieved.
- No source found in this session giving HAR R² specifically for gold, crude, or crypto CFDs; the general literature reports HAR works across asset classes, but numbers were not verified.

## 3. Stylized facts of returns (Cont 2001)

### Takeaway
Returns are almost unpredictable linearly beyond ~20 minutes, fat-tailed (tail index between 2 and 5), and their *size* clusters with long memory. This combination is exactly why direction trading is hard but risk forecasting is easy.

### Cited Findings
- Cont (2001), "Empirical properties of asset returns: stylized facts and statistical issues", Quantitative Finance 1(2): 223-236 — [IDEAS](https://ideas.repec.org/a/taf/quantf/v1y2001i2p223-236.html)
- The 11 facts (as summarized in a 2023 re-test) — [arXiv 2311.07738](https://arxiv.org/html/2311.07738v2):
  1. Absence of linear autocorrelation except at very small intraday scales (~20 minutes, microstructure).
  2. Heavy tails: power-law tail index finite, >2 and <5.
  3. Gain/loss asymmetry (larger drawdowns than up-moves; equities, not FX).
  4. Aggregational Gaussianity: distributions look more normal at longer horizons.
  5. Intermittency: irregular bursts of volatility.
  6. Volatility clustering: positive autocorrelation of volatility measures over several days.
  7. Conditional heavy tails: GARCH residuals are still fat-tailed (less so).
  8. Slow (power-law, β 0.2-0.4) decay of autocorrelation of absolute returns.
  9. Leverage effect: volatility negatively correlated with returns.
  10. Volume/volatility correlation.
  11. Asymmetry in time scales: coarse volatility predicts fine volatility better than the reverse.
- Re-test on Dow 30 stocks, 18 Oct 2018 - 19 Mar 2019: facts 1, 2, 4, 5, 6, 7, 8 hold; fact 10 only in clock time; facts 3 (asymmetry), 9 (leverage) and 11 (time-scale asymmetry) NOT consistently supported — [arXiv 2311.07738](https://arxiv.org/html/2311.07738v2). Caveat: 5-month sample, single stocks only.

### Inferences
- Leverage effect (fact 9) is mainly an equity-index phenomenon; this matters for section 4 (vol targeting improves Sharpe mainly in equity/credit).
- Fact 11 supports giving the AI coarse-scale volatility (daily/weekly) to forecast fine-scale (M15) volatility, not only the reverse.
- Conditional fat tails (fact 7) mean a stop placed at "k × forecast volatility" will still be gapped through more often than a normal model predicts — stops must be sized assuming fat tails and weekend/announcement gaps.

### Gaps
- No verified source in this session for stylized-fact magnitudes specific to gold, crude, or crypto (crypto is commonly reported to have heavier tails and stronger clustering — unverified here).

## 4. Volatility-managed / volatility-targeting portfolios

### Takeaway
Scaling exposure inversely to recent volatility reliably reduces tail events and stabilizes risk in every asset class; it raises the Sharpe ratio only modestly and mainly for equities/credit (leverage effect). The large in-sample alphas of Moreira & Muir (2017) largely fail to translate into better real-time Sharpe ratios for unconstrained investors (Cederburg et al. 2020; Liu, Tang & Zhou 2019).

### Cited Findings
- Moreira & Muir (2017), "Volatility-Managed Portfolios", Journal of Finance 72(4): 1611-1644 — [NBER w22208](https://www.nber.org/papers/22208): "Managed portfolios that take less risk when volatility is high produce large alphas, substantially increase factor Sharpe ratios, and produce large utility gains for mean-variance investors"; documented for market, value, momentum, profitability, ROE, investment, betting-against-beta factors and the **currency carry trade**; mechanism: "changes in factor volatilities are not offset by proportional changes in expected returns"; it "takes relatively less risk in recessions and crises yet still earns high average returns."
- Cederburg, O'Doherty, Wang & Yan (2020), "On the performance of volatility-managed portfolios", Journal of Financial Economics 138(1): 95-117. Across 103 equity strategies, volatility-managed portfolios "do not systematically outperform their corresponding unmanaged portfolios in direct comparisons", although they show significantly positive alphas in spanning regressions (the alpha is not implementable out of sample because the optimal combination weights are unstable) — [SUFE newsletter abstract](https://academicnewsletter.sufe.edu.cn/info/355606); [Lehigh PDF](https://www.lehigh.edu/~xuy219/research/COWY.pdf). Reasonable out-of-sample versions "generally earn lower certainty equivalent returns and Sharpe ratios than simple investments in the original, unmanaged portfolios" — [search summary citing the same literature](https://www.nber.org/papers/22208)
- Liu, Tang & Zhou (2019), "Volatility-Managed Portfolio: Does It Really Work?", Journal of Portfolio Management 46(1): 38-51: the typical market-level application has **look-ahead bias** (scaling constant set with full-sample information); after correction, maximum drawdown is **68 %-93 %** in almost all cases, the strategy beats the market only during the financial crisis, and three alternative volatility-timing variants do not beat the market either — [WUSTL profile](https://profiles.wustl.edu/en/publications/volatility-managed-portfolio-does-it-really-work/)
- Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert (2018), "The Impact of Volatility Targeting", Journal of Portfolio Management, Fall 2018 (Man Group / Duke): 60+ assets, daily data from as early as 1926 to 2017 — [Alpha Architect summary](https://alphaarchitect.com/volatility-targeting-improves-risk-adjusted-returns/); [author PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf)
  - Equities: Sharpe ratio rises from **0.40 (unscaled) to 0.48-0.51 (vol-scaled)**; similar gains for credit ("risk assets"), attributed to the leverage effect.
  - Bonds, **currencies and commodities: Sharpe impact negligible**.
  - Across **all** asset classes: reduces likelihood of extreme returns; left-tail events less severe because exposure is already small when they hit.
  - Vol scaling introduces a momentum-like behaviour (volatility tends to rise after negative returns, so exposure is cut in falling markets). — all from [Alpha Architect](https://alphaarchitect.com/volatility-targeting-improves-risk-adjusted-returns/) / [Quantpedia](https://quantpedia.com/?p=830) summaries of the paper (primary PDF not text-extractable here)
- Kim, Tse & Wald (2016), "Time series momentum and volatility scaling", Journal of Financial Markets 30: 103-124: the alpha of Moskowitz-Ooi-Pedersen time-series momentum (futures, 1985-2009) falls from **1.27 %/month with volatility-scaled weights to 0.41 %/month without**; unscaled TSMOM and buy-and-hold have similar cumulative returns; TSMOM outperformance vanishes in 2009-2013 — [Alpha Architect](https://alphaarchitect.com/2016/08/time-series-momentum-and-volatility-scaling/); [bepress](https://works.bepress.com/yiuman-tse/10)

### Inferences
- For CFD trading on FX, metals, crude and crypto, expect vol targeting to **stabilize risk and cut tails, not to add return**. Its main value for an FTMO account is keeping the daily-loss probability roughly constant across calm and turbulent regimes — the -5 %/day wall is a tail constraint, and vol scaling acts precisely on tails.
- The Kim-Tse-Wald result is a warning for any trend/"tendance de fond" backtest: a large part of trend-following's historical performance comes from vol-scaling across assets (equalising risk), not from the trend signal itself. A fair benchmark for COLLAPSAR is "vol-scaled buy-and-hold / vol-scaled trend" rather than unscaled rules.
- Look-ahead bias (Liu-Tang-Zhou) is the main implementation trap: the scaling constant / target must be computed only from past data.

### Gaps
- Exact Moreira-Muir numbers (e.g., market alpha ~4.9 %/yr, Sharpe improvement, ~65 % utility gain) are recalled from background knowledge and not verified in this session.
- Harvey et al.'s precise tail statistics (e.g., change in frequency of 3-sigma days, max drawdown changes per asset class) not retrieved.
- No peer-reviewed vol-targeting study specific to crypto CFDs was verified in this session.

## 5. Intraday volatility patterns, trading sessions and announcements

### Takeaway
Intraday volatility follows a strong, deterministic, calendar-driven periodicity (session opens/overlaps, equity U-shape) plus spikes at scheduled macro announcements; ignoring it distorts any volatility estimate at the 5-min-to-hours scale, and modelling it is a prerequisite for sensible M15 stop and size choices.

### Cited Findings
- Andersen & Bollerslev (1997), "Intraday periodicity and volatility persistence in financial markets", Journal of Empirical Finance 4(2-3): 115-158 (DOI 10.1016/S0927-5398(97)00004-2): pervasive intraday periodicity in FX and equity volatility "has a strong impact on the dynamic properties of high frequency returns"; once filtered out, intraday volatility dynamics and persistence become visible and consistent with daily ARCH — [Duke](https://scholars.duke.edu/publication/761297); [Kellogg](https://www.kellogg.northwestern.edu/academics-research/research/detail/1997/intraday-periodicity-and-volatility-persistence-in-financial-markets/)
- Andersen & Bollerslev (1998), "Deutsche mark-dollar volatility: Intraday activity patterns, macroeconomic announcements, and longer run dependencies", Journal of Finance 53(1): 219-265: one year of 5-min DM/$ returns; intraday activity pattern + macro announcement effects + ARCH persistence each separately quantified and together account for a substantial share of return variability — [Duke](https://scholars.duke.edu/publication/761296); [NBER w5783](https://projects.nber.org/papers/w5783)
- Ongoing work on which events matter for FX volatility — [arXiv 2411.16244](https://arxiv.org/pdf/2411.16244) (not read in detail)

### Inferences
- For M15 decisions, the AI should see time of day / day of week / scheduled-announcement flags as *information* (not triggers): the same price move means different things at 03:00 Paris and at 14:30 (US data).
- A stop computed from "average range of the last N bars" without seasonal adjustment is too tight going into a session open/announcement and too wide in the Asian lull.

### Gaps
- Specific magnitudes (e.g., London-New York overlap volatility multiple vs Asian session, size of announcement spikes like US payrolls) not retrieved in this session.
- Equity U-shape magnitudes and session patterns for gold, crude and crypto (24/7) not verified here.

## 6. Volatility risk premium (implied minus realized)

### Takeaway
Implied variance exceeds realized variance on average (strongly in equity indices), and the gap (VRP) predicts index returns at a ~quarterly horizon. A CFD-only trader cannot harvest the premium directly but can use implied volatility (e.g., VIX) as an input or regime signal.

### Cited Findings
- Carr & Wu (2009), "Variance Risk Premiums", Review of Financial Studies 22(3): 1311-1341: synthesize variance swap rates from option portfolios on 5 stock indexes and 35 individual stocks; VRP = realized variance minus synthetic variance swap rate; strongly **negative** on average for equity indexes (i.e., long-variance positions lose on average; variance sellers are paid) — [IDEAS](https://ideas.repec.org/a/oup/rfinst/v22y2009i3p1311-1341..html); [working paper](https://econwpa.ub.uni-muenchen.de/econ-wp/fin/papers/0409/0409015.pdf). Note: one aggregator summary phrased this as "investors receive negative returns when selling variance", which is the reverse of the correct reading — [SUFE](https://academicnewsletter.sufe.edu.cn/info/354970)
- Bollerslev, Tauchen & Zhou (2009), "Expected Stock Returns and Variance Risk Premia", Review of Financial Studies 22(11): 4463-4492: implied-minus-realized variance explains a nontrivial fraction of post-1990 aggregate US stock returns; high premia predict high returns; predictability strongest at the **quarterly** horizon; combined with P/E, R² for quarterly returns > **25 %**; requires model-free implied variance and high-frequency realized variance — [SSRN](https://papers.ssrn.com/abstract=948309); [Fed FEDS 2007-11](https://www.federalreserve.gov/pubs/feds/2007/200711/index.html)

### Inferences
- For a CFD trader (no options) on FTMO: VIX / implied vol indices can be *observed* as information; the documented predictive horizon (a quarter) is longer than the 15-min-to-weeks scope, so expected direct value for short-horizon trading is small. Implied vol is, however, a good forward-looking volatility forecast for sizing around known events.
- Selling volatility synthetically with CFDs (e.g., mean-reversion with no stop) replicates a short-option payoff with crash risk — incompatible with the -5 %/day wall.

### Gaps
- Post-publication robustness of BTZ predictability (post-2009) not verified here.
- No verified source for VRP in gold, crude or crypto at short horizons.

## 7. Risk of ruin, Kelly, drawdown constraints and prop-firm style barriers

### Takeaway
Kelly maximises long-run growth but is far too aggressive for a hard drawdown limit; fractional Kelly trades a small growth loss for a large drawdown reduction. Drawdown-constrained optimal policies (Grossman-Zhou) size risk in proportion to the *distance to the floor*. Probability-of-goal problems (Browne) show that with a deadline, the optimal policy is option-like (bet more when behind) — the exact shape of prop-firm incentives, which is also the "casino" failure mode.

### Cited Findings
- MacLean, Thorp & Ziemba, "Long-term capital growth: the good and bad properties of the Kelly and fractional Kelly capital growth criteria" (Quantitative Finance 2010): full/near-full Kelly dominates over long horizons but is very risky in the short run; fractional Kelly is "significantly less risky" while keeping much of the upside — [search summary / EFMA paper](https://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2011-Braga/papers/0103.pdf); [Davis & Lleo Kelly chapter](https://him-application.uni-bonn.de/uploads/media/DavisLleoKellyChapter.pdf)
- Practitioner claim: under full Kelly with perfect inputs, the probability that the account eventually halves is about one half — [LuxAlgo glossary](https://www.luxalgo.com/library/concept/kelly-criterion/) (practitioner source; consistent with the continuous-time result P(ever falling to fraction x of current wealth) = x under full Kelly — see Gaps).
- Practitioner claim: "half-Kelly reduces volatility by ~75 % while sacrificing only 25 % of growth" — [LuxAlgo](https://www.luxalgo.com/library/concept/kelly-criterion/). **Distortion**: in the standard model, half-Kelly keeps 75 % of the growth rate (growth ∝ c(2−c)) and cuts *variance* by 75 % (∝ c²), i.e., *volatility* by 50 %, not 75 %.
- Grossman & Zhou (1993), "Optimal Investment Strategies for Controlling Drawdowns", Mathematical Finance 3(3): 241-276: investor who never wants to lose more than a fixed % of the running maximum of wealth; for CRRA utility the optimal risky investment is proportional to the **surplus** between current wealth and the drawdown floor; extended by Cvitanic & Karatzas (1995), Elie & Touzi (2008), Cherny & Obloj (2013) — [IDEAS](https://ideas.repec.org/a/bla/mathfi/v3y1993i3p241-276.html). A Lund paper argues "The Grossman and Zhou investment strategy is not always optimal" — [Lund](https://lup.lub.lu.se/record/223851) (not read in detail).
- Browne (1999), "Reaching goals by a deadline: digital options and continuous-time active portfolio management", Advances in Applied Probability: the policy maximising the probability of reaching a wealth target by a fixed date is equivalent to replicating a European **digital option**; for one stock with constant coefficients the optimal policy is independent of the drift — [Cambridge](https://www.cambridge.org/core/journals/advances-in-applied-probability/article/abs/reaching-goals-by-a-deadline-digital-options-and-continuoustime-active-portfolio-management/73CD9DEE7FCCD733988A72AFCE62573A); [RePEc](https://ideas.repec.org/p/fth/colubu/96-16.html)

### Inferences
- FTMO challenge = reach +10 % before −10 % total (and never −5 % in a day). Under a pure random walk with no edge, the gambler's-ruin result gives ≈50 % chance of hitting +10 % before −10 % regardless of position size, minus costs; the daily wall and costs push it below 50 %. **Sizing cannot create an edge; it only reshapes the path.** (Derived, standard gambler's-ruin; matches Run A's own measurement "sans avantage, la petite taille gagne" only once costs are included.)
- With a positive edge (drift μ per unit risk) and no deadline, the probability of hitting the upper barrier before the lower one *increases as size decreases* (the ratio μ/(σ²·size) governs it) — at the cost of more time. A deadline (Browne) pushes toward larger, option-like bets when behind schedule. The FTMO time rule therefore matters a lot for the optimal sizing policy (see Gaps).
- Grossman-Zhou maps directly to FTMO's trailing/static loss limits: risk per trade should scale with the remaining distance to the −10 % floor (and to the day's −5 % floor), shrinking toward zero as the account approaches it — a principled replacement for fixed "0.5 % per trade".
- Combining with section 4: risk budget = f(distance to floor) ÷ forecast volatility of the instrument.

### Gaps
- Kelly (1956), "A New Interpretation of Information Rate", Bell System Technical Journal 35(4): 917-926; Thorp's Kelly papers — citations from background knowledge, not fetched.
- The closed-form fractional-Kelly drawdown probability (P(ever hitting x of wealth) = x^(2/c − 1) for fraction c of Kelly, i.e., x³ for half-Kelly) is background knowledge, not verified in this session.
- No academic paper found specifically modelling prop-firm challenges (target +10 % / −10 % total / −5 % daily). Current FTMO time-limit rules not verified here.

## 8. ATR / volatility-scaled stops: practitioner literature versus evidence

### Takeaway
Evidence on stop-losses is conditional: under a random walk, stops always reduce expected return; they add value only when returns have momentum/serial dependence. No peer-reviewed study found in this session tests ATR-multiple stops specifically; "2×ATR stop" rules in retail content are conventions, not evidence-backed optima.

### Cited Findings
- Kaminski & Lo (2014), "When do stop-loss rules stop losses?", Journal of Financial Markets 18: 234-254: analytical framework for the effect of stop-loss rules on expected return and volatility; under the Random Walk Hypothesis simple 0/1 stop-loss rules **always decrease expected return**; with **momentum** they can add value; empirically (daily index futures, buy-and-hold) some stop-loss policies at longer sampling frequencies raise expected return while substantially reducing volatility — [IDEAS](https://ideas.repec.org/a/eee/finmar/v18y2014icp234-254.html); [MIT DSpace](https://dspace.mit.edu/handle/1721.1/114876)
- Kim, Tse & Wald (2016) (section 4): much of trend-following performance comes from volatility scaling of position size — [Alpha Architect](https://alphaarchitect.com/2016/08/time-series-momentum-and-volatility-scaling/)
- Retail/blog content often promotes stop-loss rules as universally protective; critical practitioner write-ups exist ("truths about stop losses that nobody wants to believe") — [Quant Investing](https://www.quant-investing.com/blog/truths-about-stop-losses-that-nobody-wants-to-believe) (opinion piece, not peer reviewed)

### Inferences
- A volatility-scaled stop (k × forecast vol) is mainly a **sizing device**: fixing risk per trade in % of account while letting distance follow volatility makes position size ∝ 1/vol — i.e., it is vol targeting at trade level (section 4), with its documented benefit (tail control) and its documented limit (little Sharpe gain outside equities).
- Whether a stop helps or hurts is an empirical property of the AI's own signal (does it have momentum after entry?), so letting COLLAPSAR choose the stop freely (as already designed) and measuring it after costs is consistent with Kaminski-Lo.
- Fat conditional tails and gaps (section 3) mean realized loss per stopped trade exceeds the planned 1R a non-trivial fraction of the time, especially at announcements and Monday opens (less relevant if positions are closed before weekends).

### Gaps
- No peer-reviewed test of "ATR multiple" stops (Wilder 1978 origin) across FX/metals/indices/crude/crypto was found in this session.
- Robustness of Kaminski-Lo's positive empirical findings out of sample and on intraday horizons not verified.

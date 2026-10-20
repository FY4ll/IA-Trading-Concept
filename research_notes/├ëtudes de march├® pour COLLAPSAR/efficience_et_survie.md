# Efficience des marchés et survie des régularités : ce qui persiste, ce qui est une illusion (notes pour COLLAPSAR)

Scope: the "meta" science of market regularities (efficiency, anomaly decay, false discoveries, adaptive markets,
limits to arbitrage, ML/RL evidence, simulation training, retail/prop-firm outcomes). Context: a self-learning AI
trading CFDs on an FTMO 100k account (FX, metals, indices, energies, crypto), 15 min to weeks, flat on weekends,
realistic costs.

Verification legend: items marked **[verified]** were checked against a primary or near-primary source during this
session; items marked **[recall]** come from well-known papers whose exact figures I could not re-open in this session
(publisher pages returned 403); treat their decimals as "to double-check". **[non-peer-reviewed]** = industry/press data.

---

## 1. 2013 Nobel (Fama, Hansen, Shiller): who contributed what, and what it implies for short vs long horizons

### Takeaway
The Nobel committee's own summary: prices are essentially unpredictable over days/weeks, but partly predictable over
3-5 years (via valuation ratios); Hansen supplied the econometrics (GMM) to test pricing models. For a 15-min-to-weeks
trader, the Nobel-level evidence says the "easy" predictability lives at horizons far longer than the project's.

### Cited Findings
- Committee summary: "There is no way to predict the price of stocks and bonds over the next few days or weeks. But it
  is quite possible to foresee the broad course of these prices over longer periods, such as the next three to five
  years." Fama = short-run unpredictability (efficient markets, event studies); Shiller = long-run predictability and
  excess volatility; Hansen = statistical method (GMM) to test asset pricing theories. **[verified]** —
  [Nobel press release 2013](https://www.nobelprize.org/prizes/economic-sciences/2013/press-release/);
  [KVA announcement](https://www.kva.se/en/news/ekonomipriset-2013-2/);
  [MPR News summary](https://www.mprnews.org/story/2013/10/14/3-americans-win-nobel-economics-prize)
- The scientific background PDF (nobelprize.org "advanced information") exists but returned HTTP 403 in this session;
  could not quote its tables. — [Scientific background (PDF)](https://www.nobelprize.org/uploads/2018/06/advanced-economicsciences2013.pdf)
- Shiller (1981, AER) "Do stock prices move too much to be justified by subsequent changes in dividends?": stock price
  volatility over the past century appeared "five to thirteen times too high" relative to an ex-post rational price.
  **[recall]** — [Shiller 1981, AER 71(3)](https://www.jstor.org/stable/1802789)
- Fama & French (1988, JFE) dividend yields: yields explain small fractions of monthly/quarterly return variance, but
  often >25% of the variance of 2-4 year returns (R² rises with horizon). **[recall]** —
  [Fama & French 1988, JFE](https://doi.org/10.1016/0304-405X(88)90020-7)
- Hansen (1982, Econometrica) "Large sample properties of generalized method of moments estimators": GMM tests
  pricing models via moment conditions without full distributional assumptions. **[recall]** —
  [Hansen 1982](https://doi.org/10.2307/1912775)
- Caveat on long-horizon predictability: Welch & Goyal (2008, RFS) found that most classic equity-premium predictors
  (dividend yield etc.) performed poorly out-of-sample, often worse than the historical mean; Campbell & Thompson (2008)
  replied that with sign/parameter restrictions, monthly out-of-sample R² of ~0.5% or less can still be economically
  meaningful. **[recall]** — [Welch & Goyal 2008](https://doi.org/10.1093/rfs/hhm014);
  [Campbell & Thompson 2008](https://doi.org/10.1093/rfs/hhm055)

### Inferences
- Long-horizon predictability is about expected returns that vary slowly (risk premia/valuation). At 15 min-weeks,
  it shows up as a tiny tilt, not a tradeable signal per trade. Expect per-trade directional accuracy near 50-52%
  (consistent with the project's own measurement of ~51% for COLLAPSAR's roots on 2020-2022).
- The joint-hypothesis problem (Fama): any found predictability can be either inefficiency or a risk premium. For
  the AI, a "risk premium" regularity (paid for bearing crash risk, e.g. carry, trend) is more likely to persist than
  a pure mispricing — but comes with fat-tail losses that can breach FTMO's -5%/day wall.

### Gaps
- Exact R² tables of the Nobel scientific background not retrieved (403). Shiller/Fama-French figures are from recall.

---

## 2. EMH forms (Fama 1970) and the Grossman-Stiglitz (1980) paradox

### Takeaway
Weak/semi-strong/strong efficiency is a spectrum, and Grossman-Stiglitz shows perfect efficiency is impossible:
there must be just enough mispricing to pay informed traders for their costs. Profits therefore exist, but roughly at
the level of the cost of obtaining and acting on information — they are a wage for effort, not free money.

### Cited Findings
- Fama (1970, JF) "Efficient Capital Markets: A Review of Theory and Empirical Work": weak form (past prices), semi-strong
  (all public information), strong form (all information incl. private). **[recall]** —
  [Fama 1970](https://doi.org/10.2307/2325486)
- Grossman & Stiglitz (1980, AER) "On the Impossibility of Informationally Efficient Markets": if prices fully revealed
  information, nobody would pay to gather it; equilibrium requires a degree of inefficiency that compensates
  information costs. **[recall]** — [Grossman & Stiglitz 1980](https://www.jstor.org/stable/1805228)

### Inferences
- For COLLAPSAR: an edge must be paid for by something the AI does that others find costly (processing many markets
  at once, patience across horizons, tolerating drawdowns). A regularity "anyone can see on a chart" (weak-form
  information) is the most competed-away class.
- Expected net edge is of the same order as frictions: on FX majors (spread ~0.5-1 pip) a 15-min strategy has to beat
  costs that are a large fraction of typical 15-min moves. Costs, not prediction, are often the binding constraint.

### Gaps
- None material; both are canonical theoretical papers.

---

## 3. Post-publication decay: McLean & Pontiff (2016); Chordia, Subrahmanyam & Tong (2014)

### Takeaway
Published stock-return anomalies lose about a quarter of their returns out-of-sample (statistical bias) and about
58% after publication (bias + arbitrage). Anomaly returns roughly halved in the high-liquidity era after decimalization.
Regularities decay; the bigger the in-sample return, the bigger the decay.

### Cited Findings
- McLean & Pontiff (2016, JF 71(1)): 97 cross-sectional predictors; portfolio returns are **26% lower out-of-sample**
  (after sample end, before publication) and **58% lower post-publication**; implied **~32% (58-26) attributable to
  publication-informed trading**. The 26% is an upper bound on data-mining effects. Post-publication declines are
  greater for predictors with higher in-sample returns; returns are higher in stocks with high idiosyncratic risk and
  low liquidity (costly to arbitrage). **[verified via abstract reproductions]** —
  [McLean & Pontiff 2016 (PDF)](https://Www.Gwern.net/doc/economics/2016-mclean.pdf);
  [Counterpoint copy](https://counterpointfunds.com/wp-content/uploads/2017/07/PredictabilityMcleanPontiff.pdf);
  [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365)
- Chordia, Subrahmanyam & Tong (2014, J. Accounting & Economics 58(1):41-58): the majority of anomalies attenuated;
  average returns of a portfolio of prominent anomalies **approximately halved after decimalization** (2001); hedge-fund
  AUM, short interest and share turnover explain the decline. **[verified]** —
  [IDEAS/RePEc](https://ideas.repec.org:443/a/eee/jaecon/v58y2014i1p41-58.html);
  [Emory summary](https://goizueta.emory.edu/research-spotlight/increased-trading-activity-and-declining-returns)
- Further literature on decay mechanisms exists (e.g., "Why and how systematic strategies decay", arXiv 2105.01380),
  not reviewed in detail here. — [arXiv 2105.01380](https://arxiv.org/pdf/2105.01380)

### Inferences
- Rule of thumb for the AI's evaluation: discount any backtested edge by ~25% for selection bias even with honest
  held-out data, and by ~50%+ if the pattern is well known (moving averages, RSI levels, breakouts).
- Edges that survive are concentrated where arbitrage is costly (illiquid, high idiosyncratic risk). On FTMO CFDs the
  instruments are among the most liquid in the world (FX majors, gold, index CFDs) → expect stronger competition
  than in small-cap stocks; crypto and exotic crosses are the less-arbitraged corners but carry higher CFD costs.

### Gaps
- Direct McLean-Pontiff-style decay studies for intraday FX/CFD patterns are scarce; Neely-Weller-Ulrich (section 5)
  is the closest analogue.

---

## 4. Data mining and false discoveries: Harvey-Liu-Zhu (2016), Hou-Xue-Zhang (2020), PBO, Deflated Sharpe

### Takeaway
With hundreds of factors tried, the usual t>2 bar is far too low: a t>3 hurdle is recommended; 65% of 452 published
anomalies fail even t>1.96 when microcaps are handled properly, 82% under multiple-testing thresholds. Backtest
overfitting is quantifiable (PBO, Deflated Sharpe): the more configurations tried, the higher the in-sample Sharpe
that arises from pure noise.

### Cited Findings
- Harvey, Liu & Zhu (2016, RFS 29(1):5-68) "...and the Cross-Section of Expected Returns": catalogued **316 factors**;
  a newly proposed factor should clear **t > 3.0** (not 2.0); "most claimed research findings in financial economics are
  likely false". **[verified]** — [NBER w20592](https://www.nber.org/papers/w20592.pdf);
  [SSRN 2513152](https://papers.ssrn.com/abstract=2513152)
- Hou, Xue & Zhang (2020, RFS 33(5):2019-2133) "Replicating Anomalies": **452 anomalies; 65% fail |t|≥1.96; 82% fail a
  multiple-testing threshold (t≥2.78)**; survivors have much smaller magnitudes than originally reported; robust ones
  include value, momentum, investment, profitability. Cause: microcaps are **3.2% of market cap but 60.7% of the
  number of stocks**, and equal-weighting overweights them. **[verified]** —
  [IDEAS/RePEc](https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html);
  [NBER w23394](https://www.nber.org/papers/w23394.pdf)
- Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting" (J. Computational Finance):
  PBO = probability that the in-sample best configuration ranks below the median out-of-sample, estimated by
  combinatorially symmetric cross-validation (CSCV) over the full matrix of all N trials' returns. **[verified]** —
  [SSRN 2326253](https://papers.ssrn.com/abstract=2326253);
  [Risk.net](https://www.risk.net/2471206)
- Bailey, Borwein, López de Prado & Zhu (2014, Notices of the AMS) "Pseudo-Mathematics and Financial Charlatanism":
  with only **5 years of data, no more than ~45 strategy variations** should be tried, otherwise one expects to find a
  configuration with an in-sample Sharpe ≈ 1 even if the true Sharpe is zero. **[verified via secondary summary]** —
  [WMU ScholarWorks](https://scholarworks.wmich.edu/math_pubs/40/);
  [ScienceDaily 2014](https://sciencedaily.com/releases/2014/04/140410103005.htm)
- Bailey & López de Prado (2014, J. Portfolio Management) "The Deflated Sharpe Ratio": corrects the observed Sharpe for
  the number of trials, their variance, non-normality (skew/kurtosis) and track length; gives the probability that the
  true Sharpe exceeds zero after selection. **[recall]** — [SSRN 2460551](https://papers.ssrn.com/abstract=2460551)
- DRL trading papers have been shown to suffer the same false-positive problem; Gort et al. apply PBO to reject
  overfit deep-RL crypto agents. **[verified (abstract)]** — [arXiv 2209.05559](https://arxiv.org/pdf/2209.05559)

### Inferences
- COLLAPSAR's "cimes", candidates, seeds, hyperparameters, reward variants and examined periods are ALL trials. The
  project's history (AUREXIS champion +0.8%/month on fixed exam → 32/36 markets losing on 12 hidden months) is a
  textbook case of selection on a fixed sample. Keep a running count of trials and report a deflated Sharpe / PBO.
- Practical bar for the AI: an edge measured on held-out data should reach t≥3 (≈ Sharpe ≥ 3/√years; e.g. 3 years of
  held-out daily-scale P&L needs annualized Sharpe ≳ 1.7 to clear t=3), or be tested on many independent markets.
- Prefer regularities that replicate across many markets with one fixed specification (like value/momentum did in
  HXZ) over market-specific tunings.

### Gaps
- Exact equations/thresholds of the DSR paper not re-read in this session.

---

## 5. Adaptive Markets Hypothesis (Lo 2004, 2017): edges wax and wane

### Takeaway
Market efficiency varies over time and across markets as participants adapt. Simple FX technical rules were genuinely
profitable in the 1970s-80s and had disappeared by the early 1990s; less-studied rules declined but did not fully
vanish. Stock-return dependence cycles between periods of independence and dependence.

### Cited Findings
- Lo (2004, J. Portfolio Management) "The Adaptive Markets Hypothesis": efficiency is an evolutionary, time-varying
  property; profit opportunities appear and disappear with competition, population of participants and environment.
  Book: Lo (2017), *Adaptive Markets*, Princeton UP. **[recall]** — [Lo 2004](https://doi.org/10.3905/jpm.2004.442611)
- Neely, Weller & Ulrich (2009, JFQA 44(2):467-488): out-of-sample tests of previously published FX technical rules —
  excess returns of the 1970s-80s were genuine (not data mining) but **had disappeared by the early 1990s for filter and
  moving-average rules**; returns to less-studied rules also declined but probably had not completely disappeared;
  consistent with AMH, not EMH. **[verified]** —
  [IDEAS/RePEc](https://ideas.repec.org/a/cup/jfinqa/v44y2009i02p467-488_09.html);
  [St. Louis Fed WP 2006-046](https://files.stlouisfed.org/files/htdocs/wp/2006/2006-046.pdf)
- Urquhart & Hudson (2013, IRFA 28:130-142): US, UK, Japan, very long daily histories in five-year subsamples; linear
  tests show alternating periods of independence and dependence (adaptive); nonlinear tests show dependence in every
  subsample with varying magnitude; AMH describes returns better than EMH. **[verified]** —
  [IDEAS/RePEc](https://ideas.repec.org/a/eee/finana/v28y2013icp130-142.html)
- What has persisted the longest across asset classes: time-series momentum / trend following. Moskowitz, Ooi &
  Pedersen (2012, JFE) document it in 58 futures/forwards (equity indices, currencies, commodities, bonds), 1-12 month
  lookbacks; Hurst, Ooi & Pedersen report positive trend-following returns in each decade since 1880 (AQR authors).
  **[recall]** — [Moskowitz, Ooi & Pedersen 2012](https://doi.org/10.1016/j.jfineco.2011.11.003);
  [AQR "A Century of Evidence on Trend-Following"](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)

### Inferences
- Consistent with the project's own finding (CLAUDE.md §5: the only measured edge = background trend), the most
  durable regularity class is slow trend (weeks-months), which is a risk premium/behavioural pattern with long losing
  spells, not a high-hit-rate signal.
- An adaptive market implies the AI must be judged on rolling, recent, unseen periods and expect regime-dependent
  performance; a single pass/fail on one period is not evidence of a persistent edge.
- Simple, popular intraday chart rules on FX majors are the class with the strongest documented decay.

### Gaps
- I did not retrieve Urquhart & Hudson's follow-ups on technical rules or specific intraday FX AMH studies.

---

## 6. Limits to arbitrage (Shleifer & Vishny 1997)

### Takeaway
Arbitrage is done by a few specialized, capital-constrained agents; when mispricing widens, they lose money and
capital is withdrawn exactly when the opportunity is best. Mispricings can persist and worsen before correcting.

### Cited Findings
- Shleifer & Vishny (1997, JF 52(1):35-55) "The Limits of Arbitrage": performance-based arbitrage by agents managing
  others' money is ineffective in extreme circumstances; arbitrageurs face redemptions after losses and so avoid
  volatile, long-horizon mispricings. **[recall]** — [Shleifer & Vishny 1997](https://doi.org/10.1111/j.1540-6261.1997.tb03807.x)
- Empirical echo: McLean & Pontiff find that post-publication returns stay higher in high-idiosyncratic-risk, low-
  liquidity stocks (costly to arbitrage). **[verified]** — [McLean & Pontiff 2016](https://Www.Gwern.net/doc/economics/2016-mclean.pdf)

### Inferences
- An FTMO account IS a maximally constrained arbitrageur: -5%/day and -10% total walls mean the AI cannot hold a
  correct but temporarily losing position. The regularities that persist precisely because of limits to arbitrage
  (mean reversion of large dislocations, carry, trend's crash phases) are the ones an FTMO account is worst placed to
  harvest. Position sizing must be calibrated to survive the adverse excursion, not to the expected value.

### Gaps
- None material.

---

## 7. Machine learning in asset pricing: Gu-Kelly-Xiu (2020), "virtue of complexity", short-horizon ML, RL

### Takeaway
ML improves return prediction, but the improvement is measured in tenths of a percent of monthly R² (best ≈0.4% for
individual stocks). The "virtue of complexity" claim is contested: Nagel (2025) shows the complex model mostly
reduces to volatility-timed momentum. Published DRL trading results are backtests by the authors; I found no rigorous,
audited live evidence of DRL trading profits.

### Cited Findings
- Gu, Kelly & Xiu (2020, RFS) "Empirical Asset Pricing via Machine Learning": ~30,000 US stocks 1957-2016, 900+
  predictors; trees and neural nets best, gains traced to nonlinear predictor interactions; "large economic gains ...
  in some cases doubling the performance of leading regression-based strategies". **[verified]** —
  [NBER w25398](https://www.nber.org/papers/w25398); [AQR page](https://www.aqr.com/Insights/Research/Journal-Article/Empirical-Asset-Pricing-via-Machine-Learning)
  - Monthly out-of-sample R² (pooled stock-level): penalized/dimension-reduction linear ≈0.26-0.27% **[verified via
    summary]**; best neural net (NN3) ≈**0.40%**, RF ≈0.33%, GBRT ≈0.34%, OLS with all predictors negative (≈-3.5%)
    **[recall, Table 1]** — [search summary](https://www.nber.org/papers/w25398.pdf)
  - Long-short decile portfolios from NN forecasts: annualized Sharpe ≈**1.35 value-weighted, 2.45 equal-weighted**
    (gross of costs, monthly rebalancing, US stocks). **[verified via secondary source]** —
    [arXiv 2009.03394 citing GKX](https://arxiv.org/pdf/2009.03394)
- Kelly, Malamud & Zhou (2024, JF 79(1):459-503) "The Virtue of Complexity in Return Prediction": theory and US
  market-timing evidence that models with more parameters than observations improve out-of-sample prediction.
  **[verified (bibliographic)]** —
  [Yale copy](https://economics.yale.edu/sites/default/files/2024-01/The%20Journal%20of%20Finance%20-%202023%20-%20KELLY%20-%20The%20Virtue%20of%20Complexity%20in%20Return%20Prediction%20%281%29.pdf)
- Nagel (2025, NBER w34104) "Seemingly Virtuous Complexity in Return Prediction": with P≫T and 12-month windows, the
  RFF forecast becomes a recency-weighted average of past returns = **volatility-timed momentum**; on artificial data
  with reversals the same method still builds momentum and performs poorly → the strong performance came from
  momentum happening to work, not from learning. Kelly & Malamud have published a reply. **[verified]** —
  [NBER w34104](https://www.nber.org/papers/w34104)
- Zhang, Zohren & Roberts (2020, J. Financial Data Science; arXiv 1911.10107) "Deep Reinforcement Learning for
  Trading": DQN/policy-gradient/A2C on **50 liquid futures, 2011-2019**, daily, volatility-scaled reward; reported to
  beat classical time-series momentum and stay positive despite heavy transaction costs. Authors' backtest, not live.
  **[verified (abstract)]** — [arXiv 1911.10107](https://arxiv.org/pdf/1911.10107)
- Gort et al. (DRL crypto): many DRL trading works "may suffer from false positive issues due to model overfitting";
  propose PBO-based rejection. **[verified (abstract)]** — [arXiv 2209.05559](https://arxiv.org/pdf/2209.05559)
- Related recent evidence: a 2025 arXiv study "Re(Visiting) Time Series Foundation Models in Finance" exists (not
  reviewed in detail). — [arXiv 2511.18578](https://arxiv.org/pdf/2511.18578)

### Inferences
- Scale of a realistic ML edge: R² ≈ 0.4% monthly ⇒ correlation √0.004 ≈ 6% between forecast and outcome. This
  matches the project's own "lien ≈ 3-4 %" with its supervised engine and the ~51% hit rate. Such an edge is only
  monetisable with many independent bets and very low costs — cross-sectional diversification, not single-market
  conviction.
- GKX's Sharpe 1.35 is a monthly-rebalanced, gross-of-cost, thousands-of-stocks long-short portfolio — a setting
  very different from a CFD account trading ~45 instruments intraday; do not transpose it.
- Nagel's result warns that a complex learner can silently rediscover momentum; COLLAPSAR should always compare its
  learned behaviour with simple baselines (time-series momentum, buy-and-hold, random entry with same stops) on the
  same costs, and test on synthetic data where the true pattern is known (e.g., reversal worlds).
- DRL: the credible evidence is at daily-to-monthly horizons on futures with volatility scaling — i.e., learned
  trend-following. No rigorous evidence found for 15-minute DRL profits after costs.

### Gaps
- Could not open GKX full text (PDF unreadable in this environment); individual-model R² decimals are from memory.
- No peer-reviewed, audited, live (out-of-sample in time AND real execution) DRL trading track record found.
- Systematic evidence on ML for short-horizon FX/commodity prediction was not retrieved in this session.

---

## 8. Simulation-based training / synthetic markets: domain randomization, PFNs, market generators, deep hedging

### Takeaway
Training purely on simulation transfers to reality when the simulator's randomization covers the real world's
variation (robotics). In finance, simulation works well where the task's value comes from the structure of the problem
(hedging under costs/constraints), not from discovering a return edge: a simulator contains only the edges you put
in it.

### Cited Findings
- Tobin et al. (2017, IROS; arXiv 1703.06907) "Domain Randomization": object detector trained only on simulated RGB
  images with non-realistic random textures transferred to a real robot, localizing objects to **~1.5 cm**, without
  real-image pre-training. **[verified]** — [arXiv 1703.06907](https://arxiv.org/abs/1703.06907)
- OpenAI et al. (2019, arXiv 1910.07113) "Solving Rubik's Cube with a Robot Hand": models trained only in simulation;
  Automatic Domain Randomization generates environments of ever-increasing difficulty; memory-augmented policies show
  "emergent meta-learning at test time". **[verified]** — [arXiv 1910.07113](https://arxiv.org/abs/1910.07113).
  Reported success ≈60% overall and ≈20% on maximally difficult scrambles (OpenAI blog). **[recall]**
- Müller et al. (2022, ICLR; arXiv 2112.10510) "Transformers Can Do Bayesian Inference": Prior-Data Fitted Networks
  trained on datasets sampled from a prior approximate Bayesian posterior prediction. **[recall]** —
  [arXiv 2112.10510](https://arxiv.org/abs/2112.10510)
- Hollmann et al. (2025, Nature) TabPFN: transformer pre-trained on millions of synthetic tabular datasets; on
  datasets up to ~10,000 samples it outperformed tuned baselines (claim: in 2.8 s beats an ensemble of the strongest
  baselines tuned for 4 h, classification). **[recall — Nature page redirected to login]** —
  [Nature DOI](https://doi.org/10.1038/s41586-024-08328-6)
- Buehler, Gonon, Teichmann & Wood (2019, Quantitative Finance 19(8):1271-1291) "Deep Hedging": neural hedging policies
  trained on simulated paths (Heston model) with transaction costs and risk limits outperform the complete-market
  delta-hedge in the synthetic market; also illustrated on S&P 500. **[verified]** —
  [arXiv 1802.03042](https://www.arxiv.org/abs/1802.03042);
  [IDEAS/RePEc](https://ideas.repec.org/a/taf/quantf/v19y2019i8p1271-1291.html)
- Kondratyev & Schwarz (2019, SSRN 3384948; Risk.net "The market generator"): restricted Boltzmann machine generating
  synthetic market data reproducing the dependence structure, autocorrelation and non-stationarity of real risk
  factors; non-parametric alternative to Monte Carlo. **[verified]** —
  [Risk.net](https://risk.net/cutting-edge/7401191/the-market-generator);
  [EPFL abstract](https://www.epfl.ch/schools/cdm/wp-content/uploads/2019/10/Abstract-Kondratyev.pdf)
- Nagel (2025) uses synthetic reversal data as a falsification test of a return-prediction method. **[verified]** —
  [NBER w34104](https://www.nber.org/papers/w34104)

### Inferences
- Sim-to-real in trading is asymmetric: physics is stationary, markets are adaptive. Synthetic data can teach the AI
  the *mechanics* (stops, sizing, costs, FTMO walls, gap risk, managing positions) and robustness to regimes — exactly
  like domain randomization — but cannot teach a *return edge* that is not in the generator. If a generator is fitted to
  history, any "edge" learned on it is history's edge (same overfitting risk).
- Best use for COLLAPSAR: (1) train risk/position management on randomized worlds (random drift sign, volatility
  regimes, jumps, spreads) so the policy is safe whatever the regime; (2) use worlds with KNOWN planted patterns (or none)
  as truth tests: in a zero-edge world, the AI must learn to stay small/flat; in a planted-edge world, it must find it.
- PFN/TabPFN shows the meta-learning idea works for small tabular problems; I found no peer-reviewed evidence of a
  PFN-style model producing net trading profits.

### Gaps
- No rigorous published evidence found of a trading policy trained mainly on synthetic markets producing live
  out-of-sample profits. Sim-to-real gap quantification for trading not found.

---

## 9. Retail and prop-firm trader outcomes

### Takeaway
Regulator data: 74-89% of retail CFD accounts lose money. Peer-reviewed day-trading studies: 97% of persistent
Brazilian futures day traders lost money; <1% of Taiwan day traders are predictably profitable after fees. Prop-firm
data (industry, not peer-reviewed): ~14% pass a challenge, ~7% of buyers ever get a payout, average payout ~4% of
account size.

### Cited Findings
- ESMA (23 March 2018 product intervention): national regulators' analyses show **74-89% of retail CFD accounts
  typically lose money**, average losses per client **€1,600 to €29,000**; leverage limits, negative-balance
  protection and mandatory risk warnings introduced. **[verified]** —
  [ESMA press release](https://www.esma.europa.eu/node/84933);
  [ESMA notice of PI decisions (PDF)](https://www.esma.europa.eu/sites/default/files/library/esma35-43-1135_notice_of_pi_decisions_on_cfds_and_binary_options.pdf)
- Chague, De-Losso & Giovannetti ("Day Trading for a Living?", 2019 WP, FGV/SSRN 3423101): all individuals who began
  day trading Brazilian equity-index mini-futures 2013-2015; of those who persisted >300 days, **97% lost money; only
  1.1% earned more than the Brazilian minimum wage; only 0.5% more than a bank teller's starting salary**. Note: the
  brief's "1.6%" figure is not what the sources state; the sources give 1.1%. **[verified]** —
  [SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101);
  [FGV repository](https://repositorio.fgv.br/items/e87d04fc-4b4c-4a56-ab5a-1c84c1afde1b/full)
- Barber, Lee, Liu & Odean (2014, J. Financial Markets 18:1-24) "The Cross-Section of Speculator Skill: Evidence from
  Day Trading" (Taiwan 1992-2006): top-500 ranked day traders subsequently earn **+61.3 bp/day before fees, +37.9 bp
  after**; bottom-ranked **-11.5 / -28.9 bp/day**; **less than 1% of day traders predictably and reliably earn positive
  abnormal returns net of fees**. **[verified]** —
  [IDEAS/RePEc](https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html);
  [Odean paper PDF](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf)
- Prop firms (FPFX Tech data reported by Finance Magnates, Sept 2024): **300,000+ accounts, ~100,000 traders,
  10 prop firms; 14% passed a challenge; ~45% of those got a payout ⇒ 7% of all traders; average payout ≈4% of plan
  size; average spend ≈$800 per trader over ~3 challenges**. **[non-peer-reviewed; vendor data, firms unnamed]** —
  [Finance Magnates exclusive](https://financemagnates.com/forex/analysis/exclusive-only-7-of-300000-prop-trading-accounts-achieved-payouts)
- Finance Magnates also reported a firm (The Funded Trader) saying only ~1 in 20 traders pass. **[non-peer-reviewed]**
  — [Finance Magnates](https://www.financemagnates.com/forex/only-1-in-20-traders-pass-prop-firm-challenges-reports-the-funded-trader/)
- FTMO 2023 accounts (as reported by TradeInformer, March 2025): revenue **$203.9 M**, operating costs $100.3 M
  (~49% of revenue); the article's pass/payout rates are the FPFX industry averages, not FTMO's own. **[non-peer-
  reviewed press; based on company filings]** —
  [TradeInformer](https://www.tradeinformer.com/prop-weekly/what-ftmo-tells-us-about-prop-firm-finances)
- Claims seen on blogs that "FTMO reports ~35% Stage-1 pass and ~10% overall" could not be traced to an official
  FTMO publication; treat as **unverified marketing/SEO content**. —
  [example blog](https://track360.io/blog/prop-trading-industry-statistics-2026)

### Inferences
- Zero-edge baseline for the FTMO challenge (math, not a source): for a driftless random walk with no time limit, the
  probability of reaching +a before -b is b/(a+b). Challenge +10% vs -10% ⇒ 50%; verification +5% vs -10% ⇒ 67%;
  both ⇒ ≈33% before costs and before the -5%/day wall. So a "simulated FTMO pass chance of 30-40%" (e.g., AUREX's
  ~40%) is NOT evidence of skill by itself; the meaningful test is the funded phase (repeated payouts over months)
  versus this coin-flip baseline. Costs and the daily wall pull the zero-edge figure down; any fair comparison should
  simulate the same walls and costs with random entries.
- The ~7% payout rate and ~4% average payout are consistent with near-zero-edge trading plus a variance lottery:
  the prop business model is funded by challenge fees (FTMO revenue ≈ $204 M in 2023).
- The peer-reviewed rate of persistent, skilled, after-cost day traders is ~1% or less. A self-learning AI should be
  assumed to be in the 99% until proven otherwise on unseen months and in live demo.

### Gaps
- FTMO does not appear to publish official pass/payout statistics; none found. Whether FTMO's current challenge has
  a time limit (affects the zero-edge baseline) was not verified in this session.
- No peer-reviewed study of prop-firm challenge outcomes found.

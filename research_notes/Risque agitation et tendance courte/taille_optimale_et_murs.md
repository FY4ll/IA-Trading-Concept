# Optimal position sizing under hard loss limits, applied to the FTMO challenge

Legend: **[V]** = verified this session on the cited page (abstract or official page actually read). **[R]** = recalled from the literature / standard textbook result, NOT re-read this session (citation details believed correct but should be double-checked before being quoted as authority). **[D]** = derived by me in these notes (standard mathematics, checked by hand; reproducible). Research budget limits: two PDFs (Busseti-Ryu-Boyd, Goldberg-Mahmoud drawdown survey) could not be text-extracted (no PDF library on the machine), and SSRN returned 403, so several formulas are [R].

## Q0. FTMO's current official rules (as of 15/10/2026)

### Takeaway
On ftmo.com today the 2-Step challenge (the product the project targets) keeps: +10 % then +5 %, daily wall = balance at 00:00 CE(S)T minus 5 % of initial capital, STATIC total wall at 90 % of initial capital, 4 minimum trading days; no time limit is mentioned (third parties say it was removed). FTMO now also sells a 1-Step product with a 3 % daily wall, a TRAILING end-of-day total wall and a 50 % "best day" consistency rule. Two important constraints for an AI: FTMO forbids "gambling"/unrealistic sizing, and its forbidden-practices list mentions unauthorized software/AI giving an unfair advantage.

### Cited Findings
- [V] Product line now has three CFD structures: Instant, 1-Step, 2-Step (plus a Futures product). Profit target: 1-Step 10 %; 2-Step phase 1 10 %, phase 2 (Verification) 5 % of Initial Simulated Capital; no target on the funded FTMO Account. — [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/)
- [V] Maximum Daily Loss: "recalculates daily at 00:00 CE(S)T"; limit = account balance at 00:00 CE(S)T minus a loss allowance of **5 % of initial capital for 2-Step**, **3 % for 1-Step / Instant / Futures**; equity may not drop below it; on day one the initial capital is used as opening balance. — [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/)
- [V] Maximum Loss, 2-Step: "The Maximum Loss rule establishes a **static** limit" = Initial Simulated Capital minus 10 % of it (i.e. 90 000 $ on 100 000 $). No effective date of change shown. — [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/)
- [V] Maximum Loss, 1-Step: trailing limit recalculated at 00:00 CE(S)T from the "highest account balance achieved at 00:00 CE(S)T of any preceding trading day or, if higher, the amount of Initial Simulated Capital" minus 10 %; can only increase. Instant/Futures: real-time balance-based trailing (highest closed balance − 10 %). — [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/); consistent with [PropNavi summary](https://propnavi.io/en/blog/ftmo-rules-explained/) and [Pipster](https://www.pipster.io/research/firms/ftmo) (third parties). NB: a first automated read of the same official page wrongly said both 1-Step and 2-Step are trailing; a targeted re-read quoted "static" for 2-Step — trust "static" for 2-Step.
- [V] Minimum trading days: **2-Step only**, at least 4 trading days (calendar day 00:00–23:59 CE(S)T with ≥1 position opened) in both phases. — [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/)
- [V] Consistency ("Best Day") rule: best day may not exceed 50 % of total profit (1-Step) / 30 % (Instant, Futures); "exceeding the Consistency limit is not treated as a rule breach" but trading must continue until satisfied. The official page lists it for 1-Step / Instant / Futures, not 2-Step. — [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/)
- Time limit: the official trading-objectives page contains **no time limit** for any product. Third-party pages state FTMO "removed the time constraints of the 30 and 60 calendar days Trading Periods and introduced an Unlimited Trading Period", applying to newly purchased accounts. — [fundedtrading.com](https://fundedtrading.com/?p=15823), [daytrading.com review](https://www.daytrading.com/ftmo). **Not confirmed by an FTMO announcement page this session** (but absence from the official objectives page is strong corroboration).
- [V-ish, official FAQ snippet via search] News trading: during the Evaluation (challenge + verification) "the restriction does not apply regardless of the account type". On the funded FTMO Account, **Standard** type only: on targeted instruments no opening/closing (incl. SL/TP or pending orders being triggered) from 2 minutes before to 2 minutes after selected releases; positions opened >2 min before may be held; SL/TP triggered in the window = breach. **Swing** type: no news restriction. — [FTMO FAQ "Can I trade news?"](https://ftmo.com/faq/can-i-trade-news/) (content seen through search snippet; page not fetched in full)
- Gambling: FTMO "prohibits gambling, which includes taking excessive risks such as utilizing maximum leverage to open large positions with the hope of reaching profit targets through a single price movement"; FTMO sets no universal per-trade risk limit, recommends 1–1.5 % per trade as best practice only. — [LuxAlgo summary](https://www.luxalgo.com/prop-firms/ftmo/) (third party paraphrasing FTMO). 
- [V] FTMO-OANDA forbidden-practices page lists, among others: "otherwise perform simulated trades that contradict how trading is actually performed in the financial markets" (linking to an FTMO blog "gambling is not the right way to make money"); **"unauthorized software/AI/ultra-high-speed tools providing unfair advantage"**; gap trading around major news or within 2 h of market close; hyperactive robots (2 000+ server requests/day); artificial profit distribution to get round the Best Day / Consistency rule; **"unrealistic position sizing compared to other trades"**; excessive/insufficient position counts vs typical trading; cumulative exposure concentrated in single/correlated symbols. Sanction: termination, possible forfeiture of fees. — [ftmo.oanda.com forbidden trading practices](https://ftmo.oanda.com/forbidden-trading-practices/) (list paraphrased by the fetch tool; ftmo.oanda.com is the FTMO–OANDA co-branded site, assumed to mirror ftmo.com terms)
- Profit split: 2-Step "80 %, up to 90 %"; 1-Step 90 %. — [Pipster](https://www.pipster.io/research/firms/ftmo), [PropNavi](https://propnavi.io/en/blog/ftmo-rules-explained/) (third parties). **Not confirmed on ftmo.com this session.**

### Inferences
- For a 100 k 2-Step: phase-1 window = [90 000 $ static floor, 110 000 $ target], plus a moving daily floor = (balance at 00:00) − 5 000 $. Because the daily floor is based on *balance* (closed P&L) while the test is on *equity* (incl. floating), an open position carried overnight with a floating loss shrinks the next day's room.
- The "bold play" that maximizes zero-edge pass probability (see Q3) is exactly what FTMO's anti-gambling / "unrealistic position sizing" clauses target: a benchmark policy for scoring may use it as a *mathematical* reference, but the AI must not be rewarded for it.
- The "unauthorized software/AI" clause must be read in full before the AI ever trades a paid challenge; it could be a contractual risk for the whole project.

### Gaps
- Not confirmed on ftmo.com this session: the official announcement of unlimited time; the 30-day inactivity rule; weekend-holding restriction on Standard accounts (believed: funded Standard accounts must not hold over the weekend, Swing may — [R]); profit split and Scaling Plan details ([R]: +25 % of capital every 4 months if ≥10 % net over the 4 months with ≥2 profitable months and payouts — unverified); exact wording of the AI/software clause on ftmo.com itself.

## Q1. Optimal fraction with a drawdown floor and a target: concrete formulas

### Takeaway
All the classical results say the same thing: **size proportionally to the cushion above the floor, with a multiplier equal to (a fraction of) the Kelly ratio μ/σ²**. Full Kelly has a 50 % chance of ever halving; fractional Kelly c·f* has probability α^(2/c−1) of ever falling to fraction α of current wealth. With a target and a floor and no deadline, smaller size always raises the pass probability when the net edge is positive (at the cost of time).

### Cited Findings
- [V] Grossman & Zhou, "Optimal Investment Strategies for Controlling Drawdowns", *Mathematical Finance* 3(3), 241–276, July 1993. Constraint W_t ≥ α·M_t with M_t = running maximum of wealth, 0<α<1; for CRRA utility "the optimal policy involves an investment in risky assets at time t in proportion to the 'surplus' W_t − αM_t". — [RePEc/IDEAS](https://ideas.repec.org/a/bla/mathfi/v3y1993i3p241-276.html)
- [R] Explicit form (Grossman-Zhou for long-run growth; Cvitanić & Karatzas, "On portfolio optimization under 'drawdown' constraints", IMA Volumes in Mathematics and its Applications 65, 1995, 35–45, extending to several assets and Itô coefficients): dollar amount in the risky asset = (1/γ)·Σ⁻¹μ·(W_t − αM_t) for relative risk aversion γ; in one asset: **exposure = (μ/(γσ²))·(W_t − floor_t)**. For log utility (γ=1) this is "Kelly on the cushion". A later paper argues the Grossman–Zhou strategy "is not always optimal" — [Lund University record](https://lup.lub.lu.se/record/223851) (title only seen).
- [V] Busseti, Ryu & Boyd, "Risk-Constrained Kelly Gambling", arXiv:1603.06183 (2016; published in *Journal of Investing* 25(3), 2016 — journal [R]): Kelly problem with general outcome distribution "and an additional risk constraint that limits the probability of a drawdown of wealth to a given undesirable level"; they derive a convex bound and their bets "outperform fractional-Kelly bets for the same drawdown risk level or growth rate"; quadratic approximation links to Markowitz mean–variance. — [arXiv abstract](https://arxiv.org/abs/1603.06183)
- [R] Exact RCK formulation: maximize E[log(rᵀb)] s.t. 1ᵀb=1, b≥0, and **E[(rᵀb)^(−λ)] ≤ 1 with λ = log β / log α**; this guarantees Prob(min_t W_t < α) ≤ α^λ = β (Doob/martingale bound: (W_t)^(−λ) is a supermartingale). Quadratic (Gaussian) version: maximize mean−½variance subject to a variance bound, which for a single asset reduces to a fraction ≤ 2μ/((λ+1)σ²) ([D] from the GBM case below: requiring k ≥ λ gives f ≤ 2μ/((λ+1)σ²)).
- [R] MacLean, Thorp & Ziemba (e.g. "Good and bad properties of the Kelly criterion", 2010; *The Kelly Capital Growth Investment Criterion*, World Scientific 2011): in continuous time (GBM) with fraction f = c·f*, f* = μ/σ² (Kelly), **P(wealth ever falls to α × initial) = α^(2/c − 1)**. Full Kelly: P(ever halving) = 1/2; half Kelly: (1/2)^3 = 12.5 %; P(ever −10 %) at c=0.2: 0.9^9 = 38.7 %. Growth rate at c·f*: g(c) = (2c − c²)·g*, g* = μ²/(2σ²) (half Kelly keeps 75 % of max growth). [the α^(2/c−1) result is also derivable, see [D] below]
- [R] Browne, "Survival and growth with a liability: optimal portfolio strategies in continuous time", *Mathematics of Operations Research* 22(2), 468–493, 1997: maximizing the probability of reaching an upper goal before ruin, minimizing expected time to goal, etc., for wealth with a liability (consumption) stream; optimal policies are of the form "constant multiple of μ/σ² times the distance to a 'safe' level". Details not re-read.
- [D] **Master formula (GBM, constant fraction f of equity on an asset with drift μ, volatility σ).** Log-equity Y=ln W: drift ν(f) = fμ − ½f²σ², volatility fσ. Define **k(f) = 2ν/(fσ)² = 2μ/(fσ²) − 1** (k = 1 at Kelly, k = 0 at 2×Kelly, k = −1 at zero edge). W^(−k) is a martingale, hence, with start 1, floor L, target U:
  **P(pass) = (1 − L^(−k)) / (U^(−k) − L^(−k))**, and **E[time] = (A·P − B·(1−P)) / ν**, A = ln U, B = ln(1/L).
  Without target: P(ever hit L) = L^k = L^(2/c−1) with c = f/f* (= MTZ result above).
- [D] Monotonicity: P(pass) increases with k, and k decreases with f. So **with net edge μ>0, smaller f ⇒ higher pass probability, → 1 as f → 0, but E[time] ∝ 1/f²** (in vol units). With **zero edge**, k = −1 and P = (1−L)/(U−L) whatever f. With **negative net edge** (costs), larger f ⇒ higher P, tending to (1−L)/(U−L) from below.
- [D] Worked numbers for phase 1 (L = 0.90, U = 1.10), strategy with annual Sharpe θ = 0.5 (Kelly account volatility would be 50 %/yr), account volatility s = fσ, account drift m = θ·s:

| account vol s / yr | fraction of Kelly c | k | P(phase 1) | expected time | P(phase 2, U=1.05) |
|---|---|---|---|---|---|
| 5 % | 0.10 | 19 | 88 % | ≈ 3.0 years | — |
| 10 % | 0.20 | 9 | 73 % | ≈ 11 months | 82 % (both phases ≈ 60 %) |
| 20 % | 0.40 | 4 | 62 % | ≈ 3 months | — |
| any, zero edge | — | −1 | 50 % | 10 % vol: ≈ 1.0 yr; 20 %: ≈ 3 months | 67 % (both ≈ 33 %) |

  (Zero-edge time formula [D]: with P = ½ and ν = −s²/2, E[τ] = (B − A)/s² = 0.01005/s² years; ignores costs, daily wall and the 4-day minimum.)

### Inferences
- "Risk connoisseur" benchmark (CPPI / Grossman–Zhou adapted to FTMO): at each decision, cushion_total = equity − 90 000; cushion_day = equity − (balance_00:00 − 5 000); **cushion = min(cushion_total, cushion_day) minus a safety margin for gaps/slippage/costs**; risk exposure (vol-scaled) = c·(μ̂/σ̂²)·cushion with c ≈ 0.2–0.5 (fractional Kelly) and μ̂ shrunk toward 0 because the edge is uncertain. This automatically de-risks after losses (Q4) and near the end of a bad day.
- Under parameter uncertainty, overestimating μ by 2× puts you at 2× Kelly, where growth is zero (k=0): the standard argument for fractional Kelly c ≤ 0.5.
- With a ~51 % hit rate edge, θ is likely far below 0.5/yr after costs; the table shows that even θ = 0.5 gives only ~60 % for both phases at a reasonable 10 % vol, versus ~33 % for zero edge.

### Gaps
- Could not read Busseti–Ryu–Boyd numerical results or Cvitanić–Karatzas exact theorem text this session (PDF extraction failed).
- No closed form found for the GBM two-barrier problem *with* the daily resetting wall; see Q2.

## Q2. Two-barrier problem, leverage, and the daily resetting wall

### Takeaway
For arithmetic Brownian motion with drift μ and volatility σ starting between −b and +a, the probability of hitting +a first is (1 − e^(2μb/σ²)) / (e^(−2μa/σ²) − e^(2μb/σ²)), reducing to b/(a+b) with no drift; leverage multiplies μ and σ by the same factor, so the "signal" 2μ/σ² is divided by the leverage: more leverage pushes the outcome toward the zero-edge value. The daily wall matters mainly when daily risk is a sizable fraction of 5 %; I found no academic closed form for it.

### Cited Findings
- [R/D] Scale-function result (any diffusion textbook, e.g. Karlin & Taylor, *A Second Course in Stochastic Processes*, 1981): X_t = μt + σW_t, X_0 = 0, barriers +a, −b: **P(+a first) = (1 − e^(2μb/σ²)) / (e^(−2μa/σ²) − e^(2μb/σ²))**; μ = 0: P = b/(a+b). **E[τ] = (a·P − b·(1−P))/μ** (μ≠0); μ = 0: **E[τ] = a·b/σ²**.
- [R] Discrete analogue (gambler's ruin, Feller vol. 1): win prob p per unit bet, start i, goal N: P = (1 − (q/p)^i)/(1 − (q/p)^N), q = 1 − p. Bet size enters through i and N (= distance in units of the bet): bigger bets ⇒ smaller i, N ⇒ closer to the fair-game value i/N.
- [D] Leverage ℓ: μ→ℓμ, σ→ℓσ ⇒ exponent 2μb/σ² → 2μb/(ℓσ²): edge advantage shrinks as 1/ℓ, time shrinks as 1/ℓ² (μ=0) or 1/ℓ (μ≠0 dominant). In GBM form see k(f) in Q1.
- [D] Daily wall (resetting barrier at balance_00:00 − 5 %): it never lowers the global floor (still 90 %) but adds an intraday barrier. With daily account vol s_d: s = 10 %/yr ⇒ s_d ≈ 0.63 %/day, the wall is ~8 daily standard deviations away (negligible unless gaps/fat tails or concentrated intraday risk); s = 20 %/yr ⇒ 1.26 %/day, ~4 sd; a single trade risking 2 % with stop slippage is far from it. The wall binds when **risk per trade × number of simultaneous/consecutive losing trades in one day** approaches 5 %, i.e. it limits *intraday concentration*, not overall sizing.

### Inferences
- For scoring, simulate the daily wall exactly (Monte Carlo with real intraday paths, real costs, swaps, weekend gaps) rather than seek a closed form; use the GBM formula only as a sanity check.
- The relevant leverage measure for FTMO is "risk at stop as % of the smaller cushion", not notional leverage.

### Gaps
- I found no peer-reviewed study of daily-loss-limit rules (resetting barriers) applied to prop accounts or of their effect on pass rates; FTMO publishes no pass-rate statistics by sizing found this session.

## Q3. Zero edge vs positive edge: bold play, timid play, deadline vs no deadline

### Takeaway
With zero edge and no costs, every sizing gives the same continuous-time pass probability (1−L)/(U−L) = 50 % for phase 1 and 67 % for phase 2 (≈ 33 % both phases); costs make it lower and favour bold play (few large bets). With positive edge and no deadline, timid play is optimal (probability → 1 as size → 0, at the price of time). With a deadline (Browne 1999), the maximum probability is Φ(Φ⁻¹(z) + θ√T): edge only helps through the Sharpe ratio times the square root of the time left.

### Cited Findings
- [R] Dubins & Savage, *How to Gamble If You Must: Inequalities for Stochastic Processes*, McGraw-Hill 1965: in subfair red-and-black (p < ½), **bold play** (stake min(x, goal − x)) maximizes the probability of reaching the goal; in superfair games (p > ½) **timid play** (smallest possible stakes) is optimal. Fair game: any strategy without overshoot gives P = x/goal (optional stopping).
- [R] Breiman, "Optimal gambling systems for favorable games", *Proc. 4th Berkeley Symposium* 1961: the Kelly (log-optimal) strategy asymptotically minimizes the expected time to reach a large goal and maximizes long-run growth — the time-oriented counterpart of timid play.
- [R] Pestien & Sudderth, "Continuous-time red and black: how to control a diffusion to a goal", *Mathematics of Operations Research* 10(4), 1985: for diffusions, maximize the drift/variance ratio pointwise (continuous analogue of timid/bold).
- [V partial] Browne, "Reaching goals by a deadline: digital options and continuous-time active portfolio management" (working paper Columbia 1996; *Advances in Applied Probability* 31(2), 551–577, 1999 [R]): studies "optimal investment problems for objectives related to attaining goals by a fixed terminal time"; the optimal payoff is a digital option. — [1library copy](https://1library.net/document/zle6m5gq-reaching-deadline-digital-options-continuous-active-portfolio-management.html)
- [R] Formula (Kulldorff, "Optimal control of favorable games with a time limit", *SIAM J. Control Optim.* 31(1), 1993; Browne 1999; Heath et al.): complete market, r = 0, Sharpe θ, wealth x, goal b, horizon T, wealth ≥ L allowed: **max P(W_T ≥ b) = Φ(Φ⁻¹((x−L)/(b−L)) + θ√T)**; θ = 0 ⇒ (x−L)/(b−L). Optimal exposure (in $ of risky asset) = (b−L)·φ(Φ⁻¹(Z_t))/(σ√(T−t)), where Z_t = probability state; it **explodes when behind near the deadline** (go-for-broke).
- [R] Browne, "Beating a moving target: optimal portfolio strategies for outperforming a stochastic benchmark", *Finance and Stochastics* 3, 275–294, 1999 — same machinery relative to a benchmark.
- [D] FTMO zero-edge maximum with the daily wall: still 50 % in principle: day 1 stop at −5 %, target +10 % → P = 1/3; if stopped (0.95), day 2 stop at 0.90, target +15 % → 1/4; total 1/3 + 2/3·1/4 = 1/2. Costs, slippage past the wall, and FTMO's anti-gambling clauses reduce this in practice. Phase 1 × phase 2 ⇒ ≈ 1/2 × 2/3 = 1/3.
- [D] Plugging FTMO numbers in the deadline formula (z = (100−90)/(110−90) = 0.5 ⇒ Φ⁻¹ = 0): **P_max = Φ(θ√T)**. θ = 0.5/yr: T = 1 month ⇒ Φ(0.144) = 55.7 %; T = 1 year ⇒ 69 %; as T→∞ ⇒ 100 %. This is an upper bound requiring unbounded, deadline-driven leverage (incompatible with the daily wall and FTMO's gambling rule).

### Inferences
- FTMO now has (per third parties and the official objectives page) **no deadline**: with a genuine positive net edge, the optimal policy is "timid" (fractional Kelly on the cushion); the real constraint becomes time-cost (fees, opportunity, 30-day inactivity rule if it exists). With a self-imposed deadline (e.g. "pass within 2 months"), the probability ceiling is Φ(θ√T) and getting near it needs go-for-broke behaviour near the end — undesirable.
- If the AI has no real edge, the "smart" sizing is bold, few trades; a scoring rule must therefore make bold play earn nothing (see Q5).

### Gaps
- Browne 1997/1999 and Kulldorff 1993 not re-read: formula is [R] (high confidence for the Φ(Φ⁻¹(z)+θ√T) form).

## Q4. Practical evidence: traders after losses, daily limits, risk budgeting

### Takeaway
Real professional traders tend to do the *opposite* of the cushion rule: after morning losses CBOT local traders take more risk in the afternoon. This is precisely why prop firms and CTAs impose daily loss limits and de-risking after drawdowns; a learning AI should be checked for the same bias.

### Cited Findings
- [V] Coval & Shumway, "Do Behavioral Biases Affect Prices?", *Journal of Finance* 60(1), 1–34, February 2005: CBOT proprietary traders split day into morning/afternoon; traders are "highly loss-averse": probability of taking above-average afternoon risk 31.2 % after morning losses vs 27 % after morning gains; losers place more trades, larger trades, accumulate more inventory, buy at higher / sell at lower prices than prevailing; prices temporarily affected but "the market appeared to distinguish these risk-seeking trades from informed trading". — [IDEAS/RePEc](https://ideas.repec.org/a/bla/jfinan/v60y2005i1p1-34.html), [CFA Digest summary](https://rpc.cfainstitute.org/en/research/cfa-digest/2005/11/do-behavioral-biases-affect-prices-digest-summary)
- [R] Locke & Mann, "Professional trader discipline and trade disposition", *Journal of Financial Economics* 76(2), 401–444, 2005: CME floor traders hold losing trades longer than winners (disposition effect); the more "disciplined" (less disposition) traders were not clearly more successful but disposition is costly.
- [R] Grossman & Zhou-type drawdown control is the theoretical basis of CTA "risk budgeting" practice (cut exposure in proportion to drawdown, volatility targeting); no CTA-specific study was verified this session.

### Inferences
- A sanity test for the AI: regress its risk-taking on intraday P&L; Grossman–Zhou implies a positive slope (less risk after losses), Coval–Shumway humans show a negative one.

### Gaps
- No verified empirical study of prop-firm daily loss limits or of FTMO pass rates by sizing; no verified CTA risk-budgeting paper.

## Q5. Scoring a trading AI fairly: pass rate above chance, deflated for many trials

### Takeaway
Score = simulated pass probability of the AI minus the pass probability of a zero-edge "twin" with the same sizing, timing, costs and walls; then correct for the number of candidates tried, using the Deflated Sharpe Ratio idea (expected maximum of N null results) or a probability of backtest overfitting.

### Cited Findings
- [R] Bailey & López de Prado, "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality", *Journal of Portfolio Management* 40(5), 94–107, 2014 (SSRN 2460551; SSRN page returned 403 this session):
  **DSR = Φ( (SR̂ − SR₀)·√(T−1) / √(1 − γ̂₃·SR̂ + ((γ̂₄ − 1)/4)·SR̂²) )**, with
  **SR₀ = √V[{SR̂ₙ}] · ( (1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)) )**,
  T = number of returns, γ̂₃ skewness, γ̂₄ kurtosis (non-excess), N = number of independent trials, V[{SR̂ₙ}] = variance of the trials' Sharpe ratios, γ ≈ 0.5772 (Euler–Mascheroni). With SR₀ = 0 it is the Probabilistic Sharpe Ratio (Bailey & López de Prado, "The Sharpe ratio efficient frontier", *Journal of Risk* 15(2), 2012).
- [R] Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting", *Journal of Computational Finance* 20(4), 2017: CSCV — split the performance matrix (time blocks × configurations) into S blocks, for every combination of S/2 in-sample blocks pick the best configuration, compute its relative rank ω̄ in the out-of-sample half, logit λ = ln(ω̄/(1−ω̄)); **PBO = P(λ ≤ 0)** (best in-sample is below median out-of-sample).

### Inferences
- Proposed rule [D]: for each candidate, simulate M challenges (random start dates over the judged period, real costs/swaps, both walls, 4-day minimum, both phases). P_AI = pass fraction. Build the null by **keeping the AI's exact sizing/timing/stops but randomizing trade direction (or shifting entries to random times)**, giving P₀ with the same costs; score = P_AI − P₀ (or the log-odds difference), with a binomial/Wilson standard error √(P(1−P)/M) on each.
- Multiple testing: if N candidates were scored, compare the best excess to the distribution of the **maximum of N null excesses** (simulate N zero-edge twins, or apply the SR₀ expected-max formula to the per-challenge excess), i.e. a DSR-style deflation; also report a PBO over time blocks.
- Reference levels for the 2-Step (no costs, continuous): zero-edge ≈ 50 % phase 1, 67 % phase 2, ≈ 33 % both; a cost-paying timid zero-edge policy will be much lower, so the null must be computed with the AI's own sizing, never a fixed 33 %.
- Overlapping simulated challenges (start dates days apart) are highly correlated: effective M is roughly (judged period length / typical challenge duration), which keeps the standard error large.

### Gaps
- DSR and PBO formulas are [R] (high confidence), not re-read this session.
- No published study found applying deflation methods to prop-challenge pass rates; the rule above is my construction.

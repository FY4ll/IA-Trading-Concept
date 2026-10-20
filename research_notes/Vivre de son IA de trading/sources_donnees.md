# Free or low-cost data sources (< ~50 $/month) for a private trading algorithm, 2025-2026

Research date: 18/10/2026. About 23 searches and page reads. Primary pages were read where possible: SEC, Alpha Vantage, Tiingo, MQL5, Cboe, EIA and the Binance GitHub. The FMP pricing page returned 403, so FMP figures come from FMP's own blog pages or from aggregators. Anything not checked during this session is listed under "Gaps" and marked as unverified.

## 1. Company earnings: dates, EPS and revenue actuals, consensus, surprises, revisions

### Takeaway
SEC EDGAR is free, official and has no API key. It gives actual reported numbers (XBRL) about a minute after filing, but it has no consensus estimates. Consensus, surprises and revisions are only cheap on low-cost APIs: Finnhub free (shallow history), FMP from about 14 $/month, EODHD calendar 19.99 $/month, and Alpha Vantage, which is paid from 49.99 $/month. I found no free source of true point-in-time historical consensus, so testing earnings surprises over past years risks look-ahead bias.

### Cited Findings
- **SEC EDGAR APIs** (data.sec.gov): Submissions, Company Concept, Company Facts and Frames (one value per company per calendar period). "These APIs do not require any authentication or API keys." Processing delay is under 1 s for submissions and under 1 min for XBRL, with longer delays at peak periods. Nightly bulk ZIP files `companyfacts.zip` and `submissions.zip` are published around 3:00 a.m. ET. The SEC gives no help with scripted downloading and points to its Privacy and Security Policy / Developer FAQ for access rules. — [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- **Financial Modeling Prep (FMP)**: from 14 $/month billed yearly, plus a free version. — [SourceForge listing](https://sourceforge.net/software/product/Financial-Modeling-Prep/). Starter allows 300 calls/min, Premium 750/min and Ultimate 3,000/min. The Basic (free) plan allows 250 calls/day. Some datasets are only partial on Free or Starter. Endpoints include earnings estimates, transcripts, earnings surprises and analyst upgrades/downgrades. — [FMP: choosing a plan](https://site.financialmodelingprep.com/insights/platform/how-to-choose-the-right-financial-modeling-prep-plan-for-your-workflow); [FMP: when to upgrade](https://site.financialmodelingprep.com/it/insights/platform/when-should-you-upgrade-your-financial-modeling-prep-account). The official pricing page returned HTTP 403, so exact 2026 prices per plan were not confirmed.
- **Finnhub free tier**: 60 calls/min, US coverage, 50 WebSocket symbols, 1 year of company news, 4 quarters of EPS surprises and 1 month of earnings calendar. Premium plans add deeper history (30+ years), transcripts and tick data. — [NexusFi / Finnhub](https://nexusfi.com/d/data-providers/finnhub/); [qveris guide (aggregator)](https://api.qveris.ai/guides/best-earnings-apis-for-ai-agents)
- **Alpha Vantage**: the free plan is limited to "25 API requests per day". Premium plans cost 49.99 to 249.99 $/month for 75 to 1,200 requests/min. The page says nothing explicit about commercial use. — [Alpha Vantage Premium](https://www.alphavantage.co/premium/)
- **EODHD**: All-In-One costs 99.99 $/month (100,000 calls/day, 1,000/min). The Calendar & News package (earnings calendar) and the EOD Historical package cost 19.99 $/month each. Fundamentals start at 59.99 $/month. — [EODHD (search summary of eodhd.com pages)](https://eodhd.com/financial-summary/ASML.TO)
- **Polygon.io, renamed Massive** on 30/10/2025: Stocks Starter costs 29 $/month (unlimited calls, data delayed by 15 min), Developer 79 $ and Advanced 199 $. Prices did not change with the new name. — [apicostcalc (aggregator)](https://apicostcalc.com/blog/polygon-massive-rebrand-api-pricing.html); [qveris Polygon pricing, "verified May 2026"](https://qveris.ai/guides/polygon-pricing-optimized/)
- **Yahoo Finance via yfinance**: the yfinance documentation says the Yahoo API "is intended for personal use only" and sends users to Yahoo's terms of use. — [yfinance on PyPI](https://pypi.org/project/yfinance/0.2.39). Rate limits are not documented. Too many requests lead to a temporary IP block or a captcha. — [yfinance rate limit guide (low-quality site)](https://dimaggio-old.heartlight.org/yfinance-rate-limit-guide-2392178394.html)

### Inferences
- A minimal, legal setup for a private individual: EDGAR for actuals (free, official, timestamped by filing date and time) plus Finnhub free or FMP Starter for the calendar and consensus. Budget about 0 to 30 $/month.
- Look-ahead traps:
  - EDGAR XBRL "facts" include later restatements. To rebuild what was known on a given day, filter on the `filed` date of each fact.
  - Low-cost APIs usually return today's estimate for past quarters, not the estimate as it stood on that date (point-in-time).
- yfinance is an unofficial access route to an endpoint that is not documented. It is fragile (blocks) and legally grey for automated use. Do not build a live trading system on it.
- For an FTMO account trading CFDs on indices, earnings data mainly matter as an event filter (big index-member reports). Precise consensus for each stock matters less.

### Gaps
- **Point-in-time consensus history**: no free or cheap source confirmed. From memory, unverified: I/B/E/S (LSEG) and Zacks history are institutional and expensive; Estimize (crowd estimates) had an academic/paid API, current status in 2025-26 unknown.
- **Nasdaq earnings calendar** (unofficial JSON endpoint api.nasdaq.com): ToS and stability not checked.
- **Zacks**: paid API, not checked. Scraping zacks.com is very likely forbidden by its ToS (not checked).
- Exact 2026 FMP prices per plan, and FMP terms (personal vs display), could not be read (403).
- Exact SEC rate limit: from memory, unverified, 10 requests/s with a mandatory User-Agent header containing an e-mail address. The page read today does not state the number.
- Analyst revisions (upgrades/downgrades history): available at FMP and Finnhub premium; free depth not confirmed.

## 2. Macro: economic calendar with consensus and exact times, FRED/ALFRED, yields, rate expectations

### Takeaway
For a MetaTrader trader, the best free calendar is the one built into MT5. It gives actual, forecast, previous and revised values through code, but its times are in the broker's server time, which must be converted carefully. Forex Factory is popular but has well-documented time-zone and daylight-saving offsets when lined up with price data. FRED/ALFRED is free with a key: 120 requests/min, and ALFRED vintages give values as they were known on each date.

### Cited Findings
- **MT5 calendar (MQL5 `CalendarValueHistory`)**: returns `actual_value`, `forecast_value`, `prev_value` and `revised_prev_value`. Values are multiplied by 1,000,000, and a missing value is coded `LONG_MIN`. "All functions for working with the economic calendar use the trade server time." If `datetime_to = 0`, it returns all values from the start date, future events included. History depth is not documented. — [MQL5 CalendarValueHistory](https://www.mql5.com/en/docs/calendar/calendarvaluehistory)
- **Forex Factory, time problems**:
  - an event at 08:30 on Forex Factory showed up at 09:30 or 10:30 in a backtesting tool, even with the time zone set correctly — [FTO feature request](https://fto.featurebase.app/p/news-time-misalignment-despite-correct-time-zone-setting)
  - a US release at 16:00 showed up at 17:00 — [FTO "times news events"](https://fto.featurebase.app/p/times-news-events)
  - European and US daylight-saving changes cause 1-hour offsets for about 2 weeks, twice a year, and price and news times depend on the broker's server time — [Tickstory](https://tickstory.com/?p=17892); [MQL5 forum "Economic News Calendar PROBLEM"](https://www.mql5.com/en/forum/457941)
- **FRED API**: free key, issued immediately. 120 calls/min across all endpoints. Described as having no commercial restriction like most financial data feeds. — [FRED errors / terms page](https://fred.stlouisfed.org/docs/api/fred/errors.html); [freeapihub FRED guide (secondary)](https://freeapihub.com/blog/fred-api-tutorial-python-economic-data). The claim of "40/min for series observations" comes from a third-party MCP page and was not confirmed on the official site — [glama FRED MCP docs](https://glama.ai/mcp/servers/@stefanoamorelli/fred-mcp-server/blob/41a5270f604aef6d81d0c33a9f2054be0d43a4dd/docs/core-concepts/authentication.mdx)

### Inferences
- For the project (MT5 / FTMO): reading the calendar directly from the MT5 terminal is the most consistent with the broker's prices, because it uses the same server clock. Store the history locally, since depth is undocumented, and convert to UTC once.
- ALFRED (vintages through the same FRED API with `realtime_start`/`realtime_end`) is the only free source checked here that avoids look-ahead on revised macro series (jobs, GDP). The vintage parameters were not checked on the official page during this session.
- Forex Factory: fine for reading; for a backtest, recompute every time in UTC and check a few known events (US jobs report at 8:30 New York time, Fed decision at 14:00 New York time) against the price data.

### Gaps
- **Investing.com, Trading Economics, Econoday** were not checked. From memory, unverified:
  - Investing.com forbids scraping in its ToS and has no official public API.
  - Trading Economics has a paid API, with a very limited free/guest tier.
  - Econoday is a professional subscription.
- **2-year yields** for USD, EUR, GBP, JPY, CHF, AUD, CAD: FRED carries the US 2-year (DGS2, daily) and some OECD monthly series. Daily foreign sources (Bundesbank, SNB, BoE, ECB data portal) were not checked.
- **Rate expectations**: CME FedWatch (free on the website; data API paid, not checked); OIS proxies (fed funds futures, €STR) not checked.
- Central bank statements (exact times, RSS): not checked.

## 3. Positioning and sentiment

### Takeaway
Free and long histories exist for CFTC COT (1986+, weekly, Friday 15:30 New York time for data as of Tuesday) and Cboe volatility indices (VIX since 1990, VVIX, VIX9D, OVX, GVZ). Crypto positioning is free from Binance, but the long/short ratios and open interest via API cover only the last 30 days, so you must record them yourself. Coinglass Hobbyist (29 $/month, personal use) offers longer history. Dukascopy's SWFX sentiment is free.

### Cited Findings
- **CFTC COT**: published every Friday at 15:30 ET. History goes back to 1986 (futures only), 1995 (futures and options combined) and 2006 (supplemental report). Historical files are compressed by year on cftc.gov. — [CFTC About COT](https://www.cftc.gov/MarketReports/CommitmentsofTraders/AbouttheCOTReports/index.htm); [Wikipedia COT](https://en.wikipedia.org/wiki/Commitments_of_Traders); Python downloader [cot_reports (GitHub)](https://github.com/NDelventhal/cot_reports)
- **Binance futures, long/short ratios**: endpoint `/futures/data/topLongShortPositionRatio`, periods from 5m to 1d. "Only the data of the latest 30 days is available." The same 30-day cap applies to open interest history, so it must be collected continuously. — [Binance developers: Top Trader Long/Short Ratio](https://developers.binance.com/docs/derivatives/coin-margined-futures/market-data/Top-Trader-Long-Short-Ratio); [Apify OI aggregator note](https://apify.com/gochujang/long-short-oi-aggregator)
- **Coinglass API**:
  - Hobbyist: 29 $/month, 80+ endpoints, 30 requests/min, "personal use only". History is limited: 6 days at 1 min, 30 days at 5 min, up to 360 days at hourly and daily.
  - Startup: 79 $/month. Standard: 299 $/month (commercial use). Professional: 699 $/month.
  — [CoinGlass pricing](https://coinglass.com/pricing)
- **Dukascopy SWFX sentiment index**: share of long and short positions from real trading activity, split between liquidity consumers and liquidity providers. Free current and historical readings for major pairs on the website. — [Dukascopy SWFX Sentiment](https://www.dukascopy.com/swiss/english/marketwatch/sentiment/)
- **OANDA v20**: the `InstrumentsOrderBook` and `InstrumentsPositionBook` endpoints exist (order book and position book of OANDA clients). — [oanda-api-v20 docs](https://oanda-api-v20.readthedocs.io/en/stable/endpoints/instruments.html). The 2025-26 status (available to a European account? which instruments?) was not confirmed.
- **Cboe**: free CSV downloads of daily VIX closes from 1990, plus VVIX, VIX9D, OVX (oil), GVZ (gold), VXEEM, VXAPL and VXAZN. Legacy VXO 1986-2021. Data furnished "without responsibility for accuracy". Custom data through Cboe DataShop (paid). — [Cboe VIX historical data](https://www.cboe.com/tradable_products/vix/vix_historical_data/)

### Inferences
- COT is weekly and published 3 days late (Tuesday data, Friday release). In a backtest, the information must only be used from Friday 15:30 New York time, never from Tuesday. That is a classic look-ahead trap.
- Retail broker sentiment (OANDA, IG, Myfxbook, Dukascopy) mainly measures "the crowd". This links to the project's C1 track "against the crowd". Free history is short or absent, so a local recorder must be started now to have history later.
- VIX3M is not in the list on the page read; it may be on another Cboe page (gap).

### Gaps
- **IG client sentiment** (IG API, needs an IG account; history?), **Myfxbook community outlook** (unofficial API, ToS?), **AAII survey** (weekly history: XLS reserved for members?), **Cboe put/call ratios** (free daily history stopped in 2019 according to my memory, unverified), **VIX3M**, **free options gamma proxies** (e.g. SqueezeMetrics DIX/GEX, free history in the past, current status unknown), **Coinalyze** (free API?): none of these were checked.
- CFTC Socrata API (publicreporting.cftc.gov): exists from memory, not confirmed during this session.

## 4. Commodities: EIA, natural gas, Baker Hughes, USDA

### Takeaway
The EIA API v2 is free with a key and covers the weekly petroleum report and weekly natural gas storage, with some history back to 1960. Baker Hughes and USDA were not checked.

### Cited Findings
- **EIA API v2**: free ("EIA data is provided free of charge"), registration and API key required, subject to the API Terms of Service and the Copyrights and Reuse Policy. Covers petroleum (weekly supply, daily and weekly prices), natural gas storage (weekly working gas), electricity and coal, with history back to 1960 for some series. Rate limits and maximum rows per request are not shown on the page read. — [EIA Open Data](https://www.eia.gov/opendata/)

### Inferences
- The weekly petroleum report (normally Wednesday 10:30 New York time) and natural gas storage (normally Thursday 10:30) are scheduled events. For a backtest, use the release time, not the reference week. These times come from memory and should be checked against the EIA schedule.
- Revisions: EIA revises some weekly series, and the API serves the current version. Look-ahead risk is similar to non-vintage macro data.

### Gaps
- **Baker Hughes rig count** (free Excel on the website, ToS on automation?), **USDA** (WASDE, NASS QuickStats API: free from memory), **API (American Petroleum Institute) weekly report** (paid): not checked.

## 5. News and text: free APIs, RSS, social networks, scraping

### Takeaway
Social networks have become expensive or closed. X moved in 2026 to pay-per-use at 0.005 $ per post read, with the old free plan effectively ended. Reddit keeps a free non-commercial tier at 100 requests/min, but new accounts are approved by hand. EDGAR (8-K filings) is free and timestamped. GDELT and wire-agency RSS feeds were not checked.

### Cited Findings
- **X (Twitter) API**: move to pay-per-use, about 0.005 $ per post read and 0.010 $ per user read, capped at 3 million posts read per month. Users of the old free plan were moved over with a one-time 10 $ credit. Basic (200 $/month) and Pro (5,000 $/month) stay available. — [Gigazine, 09/02/2026](https://gigazine.net/gsc_news/en/20260209-x-api-pay-per-use); [roboin.io](https://roboin.io/article/en/2026/02/08/x-transitions-api-to-pay-per-use-model-ending-free-plan/)
- **Reddit Data API**: free tier of 100 requests/min (OAuth required), non-commercial use only. Self-service registration is said to be closed, with manual approval taking 2-4 weeks. Listings are capped at 1,000 items and there is no date-range search. — [data365 Reddit API limits](https://data365.co/blog/reddit-api-limits); [socialcrawl Reddit 2026 (aggregator)](https://www.socialcrawl.dev/blog/reddit-data-api-2026.md). Sources are secondary; manual approval is not confirmed by Reddit.
- **SEC 8-K and all filings**: Submissions API with a processing delay under 1 s, free and without a key. — [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

### Inferences
- The cheapest and most legally solid news stream for an algorithm: EDGAR (filings), central bank press releases (official RSS feeds) and the MT5 calendar. Social networks cost money (X) or forbid commercial use (Reddit free).
- Scraping: the terms of most news and finance sites (Investing.com, Yahoo, Reuters) generally forbid automated collection. Prefer official RSS feeds and APIs. Not checked site by site.

### Gaps
- **GDELT** (free, updated every 15 min from memory), **Reuters/AP RSS** (Reuters closed its public RSS feeds in 2020 from memory), **official RSS feeds of the Fed, ECB and SNB**, and **the law on scraping in Switzerland and France** were not checked during this session.

## 6. Prices: intraday history

### Takeaway
For forex, metals and indices, Dukascopy remains the free reference (ticks, Swiss source), within its licence terms. For crypto, data.binance.vision gives free, complete files with checksums; note that spot timestamps are in microseconds since 01/01/2025. Tiingo free (500 symbols/month, internal use only) and Massive/Polygon at 29 $ cover US stocks.

### Cited Findings
- **Binance public data (data.binance.vision)**:
  - Contents: spot (aggTrades, klines from 1s to 1mo, trades), USD-M and COIN-M futures (aggTrades, klines, trades).
  - Release: daily files the next day; monthly files on the first Monday of the month; a `.CHECKSUM` file (sha256) for each zip.
  - Timestamps: "from January 1st 2025 onwards" spot timestamps are in **microseconds** (milliseconds before that).
  - Past file corrections are logged in an "Updates" section.
  — [binance-public-data GitHub](https://github.com/binance/binance-public-data). The README read does not mention fundingRate or metrics; a third-party library says it can download funding and "metrics" — [quantease-binance PyPI](https://pypi.org/project/quantease-binance/0.1.12) (not confirmed on the official side).
- **Tiingo**:
  - Starter (free): 500 symbols/month, 50 requests/hour, 1,000/day, 1 GB/month, 5 years of fundamentals.
  - Power: 30 $/month for individuals (50 $ commercial), 10,000 requests/hour, 15+ years of fundamentals.
  - Licence: "internal use only", meaning you may not show or share the data with others. 30+ years of price history.
  — [Tiingo pricing](https://www.tiingo.com/about/pricing)
- **Massive (formerly Polygon)** Stocks Starter at 29 $/month, data delayed by 15 min. — [apicostcalc](https://apicostcalc.com/blog/polygon-massive-rebrand-api-pricing.html)
- **Dukascopy**:
  - The terms of use appear in a prompt when downloading through JForex. Use is at the user's own risk, with no recourse against Dukascopy Bank SA. — [Tickstory support forum](https://support.tickstory.com/viewtopic.php?p=8363)
  - Dukascopy historical data page: [Dukascopy historical](https://www.dukascopy.com/swiss/lv/marketwatch/historical/)
  - The exact licence (personal vs commercial, redistribution) was not read in full.

### Inferences
- Binance trap: any program that reads Binance spot files before and after 2025 must detect the unit (ms vs µs). Otherwise the dates jump to the year 50000+ or get mixed up.
- Dukascopy: these are Dukascopy's prices, not those of the FTMO broker. Spreads, swaps and some gaps differ, so validate on the target broker's quotes (MT5).
- Survivorship bias: free US stock sources (Yahoo, Stooq, Tiingo free) often leave out delisted companies. This is not a problem for FTMO CFDs on indices, forex and metals, which are the project's targets.

### Gaps
- **HistData** (free M1 forex, time zone EST without daylight saving from memory), **Stooq** (free daily/intraday downloads, ToS?), **Alpaca** (free API with IEX data, needs an account; is a European or Swiss account possible?), **Yahoo intraday** (from memory: 1-minute history limited to 7-30 days): not checked during this session.
- Dukascopy licence: commercial use / redistribution not confirmed.

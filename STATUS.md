# Market-Neutral Trend-Quality System — Status

**Report date:** 2026-11-17  
**Selected provider:** MEXC Futures public API — technical data qualification passed  
**Research universe:** active cross-margin USDT-settled linear perpetuals  
**Forward paper account:** NOT INITIALIZED — state branch protection gate is closed  
**Historical replay:** not implemented  
**Verified portfolio NAV:** not available  
**Performance claims:** none

## Provider selection and evidence

The required search order was Polymarket Perps → MEXC → Bitget. The first provider to pass the configured public-data screen was MEXC. Bitget was checked separately for curiosity only; it did not change selection.

| Provider | Evidence | Current result |
|---|---|---|
| MEXC Futures | 1,152 instruments discovered; 1,143 cross-margin perpetuals across settlements; 1,061 active USDT-settled cross-margin perpetuals; sampled market data and full selected-universe ticker coverage | SELECTED — TECHNICAL PUBLIC-DATA PASS |
| Polymarket Perps | 90 active cross-margin instruments discovered; missing fee coverage for four categories and sampled order-book reads failed | NOT READY |
| Bitget | 886 active cross-margin USDT perpetuals; instrument, precision and sampled ticker/book/candle/funding checks passed | CURIOSITY-ONLY PASS; NOT SELECTED |

Verified MEXC workflow: [run 43976183941](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43976183941).

The MEXC response provided 1,161 bulk ticker rows; every one of the 1,061 selected instruments had a matching ticker. Public order-book, daily-candle and funding-history calls passed for sampled high-turnover instruments across crypto, equity, commodity, FX and unclassified categories. The sampled daily candles began at 00:00 UTC. This verifies API shapes and representative category coverage, not every book or funding record on the entire universe.

Romanian derivatives-product/account eligibility has not been independently confirmed. Public API reachability is not an authorization determination.

## Research configuration

| Setting | Value | Status |
|---|---:|---|
| Fast / slow EMA | 7 / 15 | Illustrated in source paper; not optimized |
| Trend smoothing m | 5 | Provisional |
| Noise smoothing n | 10 | Provisional; n > m |
| Noise method | Absolute deviation | Baseline; RMS option also implemented |
| Qualification | Strict |Q| > 2 | Research filter, not a validated trading edge |
| Correction factor | 1.0 | Provisional |
| ATR | Wilder 14 | Risk experiment |
| ATR multiplier | 3.0 | Provisional |
| Initial paper capital | 100 USDT | Account code only; account not initialized |
| Long / short allocation | 50% / 50% NAV | Dollar-neutral target, not beta-neutral |

## Implemented on main

| Component | Evidence / status |
|---|---|
| Exchange-neutral Q indicator | EMA, causal semi-cycle/CPC, Trend, absolute and RMS Noise, Q, B and Wilder ATR modules retained |
| MEXC public adapter | Instrument details, cross-margin filter, bulk tickers, public depth, daily Klines and funding history; adapter unit tests added |
| USDT universe normalization | 1,061 active USDT-settled cross-margin contracts observed; all categories retained, including unclassified |
| Contract-unit handling | contractSize, volUnit, minVol, maxVol and priceUnit normalized; book and Kline contract volume converted to base units; quote turnover retained separately |
| Research/execution split | Q ranker produces independent long and short research lists; liquidity/turnover and order-book impact are execution gates |
| Incremental data storage | Provider-isolated manifest, date-partitioned daily candles, compressed five-minute ticker snapshots, funding partitions, new listing lifecycle and delisting/settlement tracking |
| MEXC paper execution | Book VWAP simulation, taker fee, shortfall and stale-book rejection; no order endpoint |
| MEXC portfolio accounting | USDT cash/NAV, realized and unrealized P&L, fee/funding ledger, ATR stops, daily equity and sample-gated performance report functions; unit tests added |
| State journal | Immutable hash-chained event journal and GitHub state publisher retained; runtime gate strengthened |
| MEXC read-only preflight | Successful hosted-runner integration workflow and UTC daily-bar boundary sample |
| Five-minute cycle | New MEXC market-data/ranking workflow configured; first cycle completed a 150-instrument bootstrap batch, but its first data-branch commit failed because the branch ignored the data directory. Workflow was changed to force-add public data; a subsequent successful branch commit is still required before treating persistence as operational. |

Latest fully successful CI evidence before the human-readable ticker-reporting test and MEXC per-cycle metadata cache: [run 43976943722](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43976943722). A subsequent regression fix removed a duplicate normalized metadata key. Current CI is queued/pending for the latest main revision and must pass before the final code state is called green.

## Market-data bootstrap and cadence

- MEXC provider key is stored separately from any older Polymarket market-data manifest; the store refuses cross-provider history mixing.
- Initial backfill target: up to 365 days of available daily candles for each active eligible instrument.
- Batches are bounded to 150 instruments by default; the first observed cycle completed 150 and left 911 pending.
- Subsequent API requests begin after the last successfully stored/completed daily bar; newly listed instruments receive their own resumable backfill.
- Incomplete or insufficient history is explicitly marked; an instrument with insufficient history remains ineligible for Q ranking until it has enough completed bars.
- Routine snapshots are scheduled every five minutes. The daily Q decision uses only the latest completed UTC daily bar, and the decision key is its timestamp.
- A scheduled GitHub workflow is best-effort and is not a continuous monitoring service.

The first MEXC data/ranking cycle that attempted persistence failed because Git ignored the data/ directory. The workflow was corrected to force-add the dedicated public data directory. The subsequent cycle [43976810498](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43976810498) completed successfully, including its market-data branch commit and report upload. Its persisted report recorded 54,316 daily-candle rows, full 1,061/1,061 ticker coverage, zero missing latest completed bars, zero reported API failures, 150 instruments bootstrapped and 911 pending. The subsequent cycle [43977234937](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43977234937) also completed successfully and committed the reporting fix and next batch. The latest persisted report shows 108,118 candle rows, 300 instruments bootstrapped, 761 pending, 1,061/1,061 ticker coverage, zero latest-bar gaps and zero API failures. It now prints exchange tickers rather than internal IDs and separates research from executable lists. Thus this verifies the data persistence path and the first bounded batch, but not full-universe historical completeness. The full-history gate remains false and portfolio decisions remain blocked. The sample report currently shows three executable longs and twenty executable shorts, including a contract with an unclassified provider category; these are preliminary ranking candidates, not positions.

## Portfolio state and no-write gate

**The forward paper account remains uninitialized.**

The GitHub state branch is reported as unprotected; the branch-protection endpoint could not be verified through the connected integration and the repository rulesets endpoint returned an empty list. As a result:

- MEXC workflow sets PAPER_STATE_WRITE_ENABLED=false.
- No paper positions are opened, closed or maintained.
- No financial event batches are written to the state branch.
- No verified portfolio NAV, equity curve, trade count, return, CAGR, Sharpe, Sortino, drawdown or profitability metric is available.
- The cycle must not treat a rebuildable market-data projection as the durable financial ledger.

Before enabling paper-account transitions, configure and verify server-side state-branch protection, prohibit force-push/deletion, restrict writers, and pass a real GitHub event-publisher and recovery test. This repository is public; all branch data are public and permanent.

## Not yet complete

- Successfully persisted MEXC candle/snapshot bootstrap in market-data branch with verified integrity and recovery.
- Independent full-universe data quality, missing/gap and funding-history completeness audit.
- Full real-universe Q ranking verified against independent calculations and persisted daily report.
- End-to-end MEXC paper portfolio transition and real GitHub durable event write/replay test.
- State-branch server-side protection and restricted writers.
- Separate chronological historical replay with point-in-time universe reconstruction and survivorship audit.
- Sampled-stop delay/recovery analysis using MEXC detection-time public books.
- Forward account initialization after every data, execution, accounting and persistence gate passes.
- Equity curve, drawdown chart and human-readable risk report from actual persisted NAV observations.
- Independent audit of account state and performance.

## Safety and disclosure

No live trading, Testnet, private account endpoints, exchange credentials, wallet, proxy/VPN or paid infrastructure were used. No exchange orders were submitted. The paper modules only simulate hypothetical fills. MEXC account access in Romania remains unverified. No historical or forward profitability claim is made.

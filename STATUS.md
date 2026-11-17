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
| MEXC Futures | 1,152 instruments discovered; 1,143 cross-margin perpetuals across settlements; 1,061 active USDT quote+settlement execution/account contracts; sampled market data and ticker coverage verified | SELECTED — TECHNICAL PUBLIC-DATA PASS |
| Polymarket Perps | 90 active cross-margin instruments discovered; missing fee coverage for four categories and sampled order-book reads failed | NOT READY |
| Bitget | 886 active cross-margin USDT perpetuals; instrument, precision and sampled ticker/book/candle/funding checks passed | CURIOSITY-ONLY PASS; NOT SELECTED |

Verified all-settlement MEXC public API preflight: [run 43977889004](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43977889004).

The MEXC response provided 1,161 bulk ticker rows; all 1,143 active cross-margin research contracts had a matching ticker. Settlement groups were 1,061 USDT/USDT, 41 USDC/USDC, 31 USD1/USD1 and 10 USD-quoted coin-settled contracts. Sampled ticker, order-book, daily-candle and funding-history calls passed across commodity, crypto, equity, FX and unclassified categories. The sampled daily candles began at 00:00 UTC. This verifies API shapes and representative category coverage, not every individual book or every funding record on the entire universe.

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
| Research/execution universe normalization | All 1,143 active cross-margin perps retained for Q research; 1,061 USDT quote+settlement contracts are eligible for the single-currency portfolio; non-USDT instruments remain research-only pending conversion model |
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

The first MEXC data/ranking cycle failed to commit because Git ignored data/. The workflow was corrected to force-add the dedicated public data directory. Successful commits were then verified in runs [43976810498](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43976810498) and [43977234937](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43977234937). After widening research to every settlement type, run [43977854892](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43977854892) completed successfully and pushed the new report/data snapshot. It shows 231,692 daily-candle rows, full 1,143/1,143 ticker coverage, zero missing latest completed bars, zero reported API failures, 750 instruments bootstrapped and 393 pending. The ranking is recalculated across whatever instruments have enough valid completed history; it is therefore preliminary until all eligible histories bootstrap. It now prints human-readable tickers and separates all-settlement research lists from the USDT-only executable lists. The full-history gate remains false.

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

- Complete the 365-day MEXC candle/snapshot bootstrap across all 1,143 cross-margin contracts and audit data gaps, quote-currency semantics and recovery. The first 750 instruments are marked bootstrapped; 393 remain.
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


## 2026-11-17 — Authoritative cadence and risk implementation update

This section supersedes older cadence, bootstrap and CI statements above.

- **One five-minute cron, two modes:** the first invocation observing a newly completed UTC daily candle performs the full research/data/ranking and daily portfolio-decision workflow. Other invocations run portfolio-snapshot-only mode; they do not refresh the research universe, recalculate Q, run ordinary ATR decisions or rebalance.
- The heavy workflow is keyed by a persistent daily-candle watermark and runs one bounded resumable bootstrap batch per new completed daily candle. Routine snapshots do not repeatedly perform bootstrap work.
- **Leverage and sizing:** 50% of NAV is allocated as margin to each leg at 2× leverage. Each leg targets 1× NAV notional; combined target gross exposure is 2× NAV. Contract maximum leverage and lot rules remain binding.
- **Emergency stop:** a 25% combined portfolio drawdown from the observed UTC-day NAV peak triggers full-book simulated flattening. The stop includes realized/unrealized P&L, fees and confirmed funding through combined NAV. It is not a lifetime MDD cap. A pending flatten is persisted and retried on later five-minute runs; a missing mark cannot suppress an already-latched emergency exit.
- Daily return uses the previous UTC day's last stored NAV when available, preventing a delayed first daily invocation from resetting the baseline to an already-damaged mark. Five-minute drawdown remains sampled and can exceed the nominal threshold due to scheduling and execution delay.

**Verified execution evidence:**
- Full daily-close MEXC public-data/ranking workflow [43984343892](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984343892): 1,143 active cross-margin perpetuals, 273,160 daily-candle rows, 93 instruments completed in the final bootstrap batch, zero remaining bootstrap instruments, zero missing tickers, zero missing latest completed bars, zero API failures, and history coverage gate passed.
- Follow-up monitoring workflow [43984739626](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984739626): PORTFOLIO_SNAPSHOT_ONLY, daily_decision_due=false, q_rankings_recalculated=false, no missing position marks, zero orders.
- CI [43984752103](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984752103): Ruff passed; 141 tests passed.

**Forward paper account remains NOT INITIALIZED.** PAPER_STATE_WRITE_ENABLED remains false, so no positions or financial events have been created and no portfolio NAV, equity curve or performance result is verified. State-branch protection, restricted writers and the real publisher/recovery gate are still required before any paper-account state transitions. Live trading, private endpoints, credentials and exchange orders remain prohibited.

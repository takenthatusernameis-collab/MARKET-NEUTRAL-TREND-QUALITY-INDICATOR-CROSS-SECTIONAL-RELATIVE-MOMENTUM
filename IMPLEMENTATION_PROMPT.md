# Master Implementation Directive v2.8
## Market-Neutral Trend-Quality Indicator — Exchange-Neutral Paper Research

Repository: `takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM`  
Target: `main`  
Current ordered provider search: Polymarket Perps → MEXC → Bitget. Polymarket is the first candidate; its public SDK documents cross-margin non-expiring perpetuals and categories including crypto, equity, commodity, index and pre-IPO. Run the current public API acceptance workflow. The first provider that clears all strategy-data gates becomes the selected paper-research provider; do not probe later providers after a pass. Bybit is retained only as a historical/previously blocked adapter.  
Execution: local paper simulation only; no live orders, Testnet, credentials or private endpoints.  
Initial paper capital: 100 units in the selected provider's collateral denomination. For Polymarket, use pUSD as the ledger denomination and do not silently equate pUSD with USDT. Target gross exposure: 1.0x NAV, 50% long and 50% short.

Primary source: David Sepiashvili, [Trend-Quality Indicator](https://www.prorealcode.com/wp-content/uploads/2019/03/24-Q-Indicator.pdf).

## 1. Mission and non-negotiable priorities

Build an auditable, persistent, self-improving quantitative research system that evaluates every eligible contract on one explicitly approved exchange, calculates the original Q Indicator, ranks both directions, and eventually maintains one long and one short in a separate forward paper account. Keep the strategy mathematics and normalized data contract independent of exchange-specific symbol and response formats.

Priority order: (1) no look-ahead; (2) mathematical correctness; (3) accounting correctness; (4) complete data and universe; (5) risk integrity; (6) recoverability; (7) statistical validity; (8) reporting; (9) efficiency.

Never claim a feature is complete without evidence. Keep historical replay and forward paper accounts separate. Historical performance is not evidence of forward performance.

## 2. Repository authorization and state

Inspect the repository and current branch before changes. Preserve existing work. Target `main`; never force-push or bypass protection. Repository changes require explicit user authorization. No other repository or deployed system may be modified.

Maintain:
- `IMPLEMENTATION_PROMPT.md`
- `IMPLEMENTATION_PLAN.md`
- `PROMPT_REFINEMENT_LOG.md`
- `IMPLEMENTATION_DECISIONS.md`
- `MATHEMATICAL_REFERENCE.md`
- `ASSUMPTIONS.md`
- `DATA_DICTIONARY.md`
- `RUNBOOK.md`
- `STATUS.md`

Refine the specification after each material milestone: inspect, diagnose, revise, implement, test, independently verify, record evidence. Do not endlessly rewrite documents or weaken acceptance criteria.

## 3. Exchange-neutral cross-margin perpetual universe

The selected provider's instrument endpoint is the source of truth. For Polymarket use the unauthenticated public Perps API at `https://api.perpetuals.polymarket.com`:
- `GET /v1/info/instruments`: discover every perp and its category, ID, quote/base assets, precision, min/max notional, leverage/risk tiers, margin-mode flags and retirement state.
- `GET /v1/info/tickers` and `GET /v1/info/statistics`: bulk current market snapshots and 24-hour statistics.
- `GET /v1/info/fees`: category fee schedule and tiers.
- `GET /v1/info/book`: public order-book depth.
- `GET /v1/info/klines`: historical candles, including `interval=1d`.
- `GET /v1/info/funding`: funding history.

Universe rule is **per instrument**:
- Include every active contract for which cross margin is available (`isolated_only == false`).
- Exclude isolated-only contracts.
- Exclude permanently retired instruments with a non-null settlement record from new rankings and updates.
- Exclude `close_only == true` instruments from new entries; preserve them in the instrument history and continue managing an existing paper position until it exits or settles.
- Do not filter by asset category. Include crypto, equity, commodity, index, pre-IPO and any future category returned by the API whenever that specific instrument is active and cross-margin eligible. Preserve unknown category strings rather than rejecting them or guessing from the symbol.
- `ui_live_time` is advisory presentation metadata and must not be used as a trading-eligibility filter.
- An instrument disappearing from tickers is not automatically delisted. Confirm its status from the instrument endpoint and settlement state.

Maintain a stable internal key of provider + instrument ID. A display symbol is metadata, not a primary key. Persist listing, category changes, close-only transitions, settlement and delisting timestamps. Refresh instrument metadata every five-minute cycle or at a bounded interval; new instruments are added, delisted/settled contracts stop receiving routine price updates, and no historical rows are deleted.

Research universe and execution universe are distinct. Compute Q for every research-eligible cross-margin contract with adequate valid daily history, regardless of turnover or asset class. Separately apply min-notional, fee, depth, spread, impact and freshness constraints when deciding whether a ranked candidate can be paper-filled.

MEXC and Bitget remain ordered fallbacks only if Polymarket fails. Apply the same per-instrument cross-margin rule to those APIs; do not demand that an exchange offer every category. Do not assume coin-margined or alternate-settlement contracts are USD/USDT-equivalent. Any fallback must normalize contract value, collateral, settlement, P&L currency and conversion costs before portfolio simulation.

## 5. Original Q Indicator

Use daily close (P_t). Semi-cycle boundaries are determined causally by completed-bar fast/slow EMA crossovers. Reference EMA periods are 7 and 15 as illustrated in Figure 1 of the source paper; this is not an optimality claim.

EMA is recursive with alpha (2/(p+1)), seeded with the SMA of the first (p) valid closes. Before both EMAs are fully initialized, no crossover is available. The interval before the first genuine crossover is left-censored and must not be ranked. Do not invent a crossover at dataset start.

Bullish crossover: (Fast_t>Slow_t) and (Fast_{t-1}<=Slow_{t-1}). Bearish: (Fast_t<Slow_t) and (Fast_{t-1}>=Slow_{t-1}). Crossover is known only after the candle closes.

For a confirmed semi-cycle beginning at (t_0):
[
CPC_t=\sum_{\tau=t_0}^{t}(P_\tau-P_{\tau-1})
]
The first CPC observation includes the close-to-close difference on the crossover candle. Reset CPC at each confirmed crossover; never carry CPC across cycles.

[
Trend_t=MA(CPC,m)
]
Use a full-window simple moving average initially. The paper specifies MA but does not prescribe a universal (m) or (n). Provisional values: (m=5), (n=10); these are experimental defaults, not author parameters.

[
Noise_1=MA(|CPC-Trend|,n)
]
[
Noise_2=\sqrt{MA((CPC-Trend)^2,n)}
]
Require (n>m); use complete rolling windows and aligned residuals. Baseline noise is absolute deviation; RMS is a separate experiment. If a cycle lacks enough post-crossover observations, classify it INSUFFICIENT_CYCLE_HISTORY.

[
Q=\frac{Trend}{Noise}\times c
]
Initial (c=1.0), configurable and not represented as an author-prescribed constant. Zero or negligible noise that makes Q undefined must not be turned into an infinite/large rank. Exclude and report it.

Qualitative source thresholds: |Q| 0–1 noise-dominated; 1–2 weak; 2–5 moderate; >5 strong. Initial qualifying condition is strict (|Q|>2). It is a trend classification, not a success probability.

[
B=\frac{|Trend|}{|Trend|+Noise}\times100
]
B is supplementary and directionless. Source bands: 50–65 weak, 65–80 moderate, >80 strong; below 50 is noise-dominant/less convincing. Handle zero denominator.

Record all intermediate values, configuration, cycle start, direction, timestamps and data version. Golden tests must independently verify formulas, crossovers, resets, scaling invariance, offset invariance, no future leakage and zero-noise behaviour.

## 6. Full-universe ranking and execution eligibility

Calculate indicator values for every research-eligible contract. Bullish ranking sorts positive Q descending; bearish ranking sorts negative Q ascending (most negative first). Keep deterministic tie-breaks and audit every exclusion.

Separate research eligibility from execution eligibility. An asset may be ranked but fail minimum notional, quantity precision, liquidity or order-book depth requirements. If a top-ranked candidate is not executable, evaluate the next qualifying candidate and record the fallback.

Provisional liquidity policy must be configurable and separately validated. Starting defaults: 30 completed daily bars for median turnover; desired order notional <=0.1% of median daily turnover; maximum simulated book impact 10 bps; at most 10 fallback candidates. These are operational assumptions, not source-paper parameters.

## 7. Portfolio state machine

The account targets one long and one short, each 50% of current NAV; gross target 1.0x. This is dollar-neutral, not beta-neutral. The same symbol cannot fill both legs.

Select the highest-ranked executable candidate with Q>2 and lowest-ranked executable candidate with Q<-2. If either side is unavailable, do not open an unmatched new pair; at next daily rebalance close any surviving unmatched leg and remain flat until a complete pair exists.

On daily decisions: retain unchanged symbols; close/replace changed symbols independently; size each leg from 50% NAV; round quantity down to `qtyStep`; respect min quantity/notional and maximum market quantity; never round up to force a trade. Do not pyramid. Every transition has an explicit decision and event ID.

A stopped leg cannot be reopened by hourly monitoring. At the next completed daily decision it may re-enter only if it still qualifies and is selected. A surviving leg remains until next daily rebalance unless its own stop fires.

## 8. ATR stops and sampled monitoring

ATR(14) uses Wilder smoothing; seed with the first 14 true ranges, where first TR is high-low. Provisional stop multiplier k=3.0.

Long stop:
[
SL_L=\max(SL_{L,prev},HH_{post-entry}-k\times ATR)
]
Short stop:
[
SL_S=\min(SL_{S,prev},LL_{post-entry}+k\times ATR)
]

Initialize post-entry high/low at actual fill price. Never include pre-entry extremes. Calculate daily stop changes from completed daily candles only; new stops are effective only after their decision timestamp.

Monitor completed hourly candles, with one-minute data for partial-hour ownership/stop activation checks and finer stop verification. Use last traded prices to trigger stops and mark prices for NAV. Record all price sources.

**Never assume a trigger-price fill when monitoring is hourly.** The trigger may be observed only after candle completion and scheduled workflow delay. Forward paper exit is based on a fresh public order-book snapshot at actual detection time; record detection timestamp, book timestamp, fill time and VWAP. If quote is stale/unavailable, do not fabricate a fill.

For historical replay, model the configured schedule delay (initially 17 minutes after the hour close) plus a configurable operational lag. Use the first eligible one-minute reference at or after modeled detection and adverse spread/slippage assumptions. Report delay sensitivity. Do not claim continuous protection.

On a stop-out close only that leg; keep survivor, record single-leg exposure and continue monitoring. If multiple intervals were missed, process chronologically to identify a crossing but execute only at current detection-time conditions; never backdate.

## 9. Public order-book execution and costs

Use only public `GET /v5/market/orderbook` and `GET /v5/market/tickers`. For linear REST order books, the documented depth parameter supports up to 1,000 levels. Request a bounded depth (initially 200 or 1,000 after payload/latency benchmarking), validate the response and disclose that RPI orders are not included. Do not confuse REST limits with the separate WebSocket depth update tiers. Validate `ts` and matching-engine `cts` freshness. RPI orders are not exposed in the standard order-book snapshot; disclose this limitation.

For buys consume asks; for sells consume bids; calculate depth-weighted VWAP; support partial fill/reject if visible depth is insufficient. Apply configurable maximum impact. Historical order-book depth is unavailable from ordinary Klines, so historical execution must use next eligible one-minute open plus explicitly adverse spread/slippage assumptions. Never use signal-candle close retrospectively.

Use a provisional fee assumption of 0.10% per fill only as an explicit sensitivity baseline, not as the user's actual fee tier. Run higher-fee, higher-slippage and severe-friction scenarios. Fill-price effects already include slippage; do not deduct the same shortfall twice.

No broker or exchange order endpoints may exist in the project.

## 10. Funding

Use `GET /v5/market/funding/history` with category, symbol, start/end time and limit <=200. The endpoint has no pagination cursor; startTime alone returns an error, while bounded time windows are supported. Partition windows so no request can truncate more than 200 expected settlements; recursively subdivide full pages and verify expected count using each instrument's fundingInterval.

Use actual `fundingInterval` metadata. Funding cash flow:
[
Cashflow=-Side\times Quantity_{pre-settlement}\times MarkPrice_{settlement}\times FundingRate
]
Long side=+1, short=-1. Positive funding means long pays short.

Determine position state immediately before settlement. If a fill and settlement share indistinguishable timestamps, use a documented conservative rule and flag ambiguity. Use public mark-price Klines; a one-minute mark-price candle must be aligned carefully to settlement timestamp. Never silently replace missing settlement mark/funding with zero or last price. Only verified funding events enter authoritative accounting.

## 11. Accounting, event journal and state

Use Decimal/fixed-point for money, quantities, fees, funding and cash. NAV is:
[
NAV=Cash+UnrealizedPnL
]
Cash includes initial capital, realized gross price P&L, fees, confirmed funding and explicit adjustments. Do not double count realized P&L, fees or slippage.

Use SQLite as a transactional, rebuildable projection. The durable source of truth is immutable event batches stored on a dedicated `state` branch, not a mutable runner-local DB or Actions cache/artifact.

Each workflow produces a uniquely named event batch (for example `events/YYYY/MM/<run-id>.jsonl`) with unique event IDs and idempotency keys. Commit the entire batch atomically using a normal fast-forward push with conflict detection; no force push. If the state commit fails, the workflow must not claim the transition is durable. On a later run, replay already committed events into SQLite. Keep snapshots/checkpoints with checksums and schema version. Do not edit/delete past financial events; corrections are compensating events.

Before any new batch is committed, reconstruct the complete remote event-batch chain from the current `state` branch tree and verify that the new batch's `previous_batch_hash` equals the unique remote chain tip. Reject a second genesis batch, forks, cycles, orphaned/disconnected batches, invalid file paths, malformed blobs, and truncated Git trees. Do not trust a local SQLite hash or caller-supplied parent hash as evidence of the remote tip.

The `state` branch must have server-side GitHub branch protection or a repository ruleset that disallows force pushes/deletion and restricts writers before account initialization. Publisher-side fast-forward logic is not a substitute for server-side protection. Because this repository is public, every event file is public and persistent: never store credentials, personal identifiers or confidential account data in its Git history.

Storage is not unlimited. Estimate and monitor repository growth; partition compressed market data. If Git storage cannot safely support the required data volume, report the blocker instead of silently deleting history or introducing paid services.

## 12. Provider qualification and environment safeguards

### 12.1 Ordered provider decision
Test exactly this order and stop at the first provider that passes:
1. **Polymarket Perps**
2. **MEXC**
3. **Bitget**

Polymarket is first because its official Perps SDK documents public instrument/ticker/book/candle/funding/fee reads, non-expiring perpetuals, shared cross margin and multiple instrument categories. Its known categories include `crypto`, `equity`, `commodity`, `index` and `pre_ipo`; future category values must be preserved. A selected exchange is not required to offer every category. Every instrument the exchange does offer that supports cross margin must be considered.

### 12.2 Polymarket technical acceptance
Run a public, unauthenticated probe against the official Perps API host. Require:
- At least 20 active cross-margin contracts (`isolated_only == false`, no settlement record, and not close-only for new entries).
- Complete, unique instrument IDs and metadata: category, symbol, quote/base assets, funding interval, quantity/price precision, price bounds, liquidation fee, max order count, minimum/maximum notionals, max leverage and risk tiers.
- Full bulk-ticker coverage for every new-entry eligible instrument, including valid last/mark/index prices, funding rate and next funding timestamp.
- Fee-schedule coverage for every category in the eligible universe.
- Successful representative order book, completed daily candle and funding-history reads for every category actually present. Unknown/future categories are sampled and kept, not dropped.
- No nonzero or stale-data shortcuts: endpoint code/schema failures, duplicates, invalid decimals and missing active tickers fail the gate.
- Report the entire per-category universe, isolated-only exclusions, close-only instruments and retired instruments.

This stage is a public-data technical gate, not account authorization. The current published Polymarket restriction table does not list Romania, but terms require compliance with applicable law and account-level checks. Do not claim legal clearance or account eligibility from an API response. No VPN, proxy, alternate identity, wallet, credentials or private endpoint may be used.

### 12.3 Fallback gates
Only if Polymarket fails the API acceptance gate, test MEXC. If MEXC fails, test Bitget. Use all active cross-margin contracts available in each product family, not only USDT pairs or crypto. Keep categories as metadata, and preserve unknown values. Any alternate settlement/collateral currency requires explicit Decimal conversion and P&L attribution. A public technical pass does not establish Romanian account/product eligibility. Stop probing later providers immediately after a pass.

### 12.4 Selected provider implementation gate
After the first passing provider is selected, implement its normalized public market-data adapter, contract metadata parser, cross-margin universe, candle downloader, funding/fees, order-book paper execution and time-series store. The strategy's Q calculations, ranking and portfolio rules must remain exchange-neutral.

Never use account, private, order, transfer or wallet endpoints. No real orders, Testnet, API keys, signatures, wallet connection or funded account. The system remains paper-only. No paid infrastructure; use GitHub-hosted runners and repository-backed storage within documented quotas.

### 12.5 Data storage and incremental updates
Use the `market-data` branch for public instrument manifests, daily OHLCV series, five-minute snapshots and daily rank artifacts. Keep the `state` branch exclusively for immutable paper-account events and portfolio state. Do not mix user secrets or private account data into either public branch.

Bootstrap each active cross-margin instrument once using up to 365 days of available daily candles, with resumable batches/checkpoints. For each subsequent daily update, request only the missing range after the last stored candle. New instruments are added and individually backfilled; close-only instruments are blocked from new entries; permanently settled/delisted instruments retain history but cease routine updates. No full-history exchange download on every run.

Five-minute snapshots store ticker, mark, index, mid, last, open interest, 24-hour volume, current funding and next funding. Partition compressed snapshots by UTC hour. Store daily candle records partitioned by date and/or instrument; manifest records last-seen/last-candle timestamps and coverage. A failed snapshot never overwrites a valid previous observation.

## 13. Workflow design

Run the selected-provider paper pipeline every five minutes using a GitHub Actions cron schedule `*/5 * * * *`, plus `workflow_dispatch` for recovery and manual diagnosis. GitHub scheduling is best-effort and may be delayed; never represent it as real-time monitoring. Keep each snapshot cycle comfortably below five minutes. Use a fixed concurrency group with no overlapping state mutations, and make every write idempotent.

Each five-minute run:
1. Restore the latest verified `market-data` manifest and separate `state` branch portfolio events.
2. Discover/refresh the instrument universe and contract metadata; identify new, active, close-only and permanently settled instruments.
3. Fetch bulk tickers for the full active cross-margin universe and persist a UTC timestamped five-minute snapshot.
4. Update only missing daily candles and funding observations; advance bootstrap checkpoints for new/insufficient-history instruments.
5. Mark existing paper positions to market using fresh mark/index/ticker data, check active stops and reconcile any scheduled funding observations using authoritative rate/timestamp semantics.
6. Check the latest completed daily candle timestamp against the last processed daily decision. If no new completed bar exists, do not recompute rankings or rebalance.
7. On the **first successful workflow run after a new completed daily bar**, update Q for the full eligible universe, rank long/short candidates, apply separate execution eligibility, obtain fresh books, simulate the pair transition, record NAV and publish a single idempotent daily decision keyed by candle timestamp.
8. Persist market data, checkpoints and reports. Publish immutable paper-account events to `state`; publish public candles/snapshots to `market-data`.

The daily decision timestamp must be the completed candle timestamp, not the workflow start time. A delayed run processes the latest completed bar once and records skipped intermediate decisions; it must not fabricate fills at historical prices. If multiple completed bars were missed, catch up data chronologically but execute at current observed book conditions only; mark the delayed decision accordingly.

Daily ranking and portfolio transition run once per new completed daily candle, guarded by a durable processed-bar key. Re-runs, retries, concurrent workflow jobs and restored checkpoints cannot duplicate trades, fees, funding or daily decisions. Five-minute snapshots may update unrealized PnL and risk status but must not trigger another daily ranking.

## 14. Historical and forward account separation

Historical replay is chronological and point-in-time where possible. If historical cross-margin instrument snapshots are unavailable, disclose survivorship bias. It uses completed daily bars for Q, public funding history and actual fees/market constraints; it must not use future information.

The forward paper account begins at its actual initialization timestamp with the configured seed capital in the selected provider collateral denomination (Polymarket: pUSD). No historical trades or equity enter the forward account. Daily candle history is a signal dataset only; it cannot create historical paper fills. Missed daily decisions are recorded as skipped and are not backfilled with invented fills.

## 15. Performance reporting

Publish root `STATUS.md`, equity SVG, drawdown SVG and CSV/JSON exports. Forward and historical reports remain separate. All figures derive from persisted ledger/valuation records and carry run ID, account mode, config hash, source commit and UTC timestamp.

Metrics: lifetime return, CAGR, daily volatility, Sharpe, Sortino, Calmar, max drawdown, drawdown/recovery duration, win rate, avg win/loss, profit factor, expectancy, costs, funding and long/short attribution. Use 365-day annualization. Sharpe requires >=30 valid daily returns. Sortino requires >=20 consecutive daily returns and >=5 negative returns, MAR=0, annualized by sqrt(365). Withhold formal CAGR until >=1 year; earlier estimates are provisional. Never show unavailable metrics as zero.

Equity and drawdown curves must match CSV values. Hourly-sampled drawdown is an observed estimate, not continuous intrahour max drawdown. Show single-leg exposure duration, missing monitor intervals, longest gap and data quality.

## 16. Testing and independent audit

Mock API responses in CI. Tests cover indicator golden values, causality, pagination, duplicates, candle validation, missing data gates, ranking, selection, sizing, VWAP, partial fills, fees, funding, stop activation/delay/gaps, missed intervals, idempotency, event hash chain, persistence recovery, NAV reconstruction and report/CSV agreement.

Before completion independently reconstruct several trades from raw data and the entire forward account from persisted event batches. Distinguish implemented, unit-tested, integration-tested, historical-replay-tested, forward-paper-verified and independently audited.

## 17. Phased delivery

1. Repository/specification.
2. Bybit client and data-quality tests.
3. Q/B mathematical engine and golden tests.
4. Full-universe ranking.
5. Portfolio state machine and sizing.
6. Paper broker, stops, funding and accounting.
7. Event batch persistence and recovery.
8. Historical replay.
9. CI and public API preflight.
10. Daily/hourly workflows only after acceptance.
11. STATUS, equity, drawdown and exports.
12. Independent audit.

## 18. Acceptance and disclosure

Do not call the complete system finished until full active cross-margin universe retrieval across all categories offered, incremental 365-day/available daily history, validated Q, full-universe signed ranking, execution gating, chronological replay, separate forward paper account, five-minute snapshots, daily-close idempotent rebalance, realistic stops, verified funding/fees, reconciled NAV, durable data and event storage, recovery, tests, scheduled workflows and main-branch reports are demonstrated.

No live trading. No Testnet. No private endpoints. No credentials. No paid infrastructure. No false fills. No incomplete-universe claims. No hidden adjustments. No unsupported performance claims.## 4. Daily candle history, incremental storage and completeness

The signal timeframe is **one-day candles**. For Polymarket use `GET /v1/info/klines` with `interval=1d`, `instrument_id`, `start_timestamp` and `end_timestamp` in epoch milliseconds. Honor the response `data` and `more` fields; paginate monotonically and deduplicate by candle timestamp.

Create a one-time resumable bootstrap for every active cross-margin instrument: backfill up to 365 days of available daily OHLCV history (or all available history if the contract is younger). Batch and checkpoint the work; do not re-fetch a full year each day. A newly listed contract receives its own one-time backfill and remains unranked until it has sufficient valid completed history for the configured TQI.

Store daily bars durably on the dedicated `market-data` branch, keyed by provider, instrument ID and UTC candle-start timestamp. Maintain a manifest with instrument metadata version, first/last candle timestamp, latest completed candle, bootstrap state, missing ranges and active/close-only/settled status. On routine runs request only candles after the last stored timestamp; backfill only genuinely missing ranges. New listings are added; delisted/settled instruments stop receiving routine updates while their historical rows remain available.

A daily candle is complete only when its start timestamp plus one day is no later than the provider's server timestamp. Use the latest valid server/ticker timestamp, never local wall-clock time if a provider timestamp is available. Validate OHLC ordering, positive finite prices, non-negative volume/trade count, timestamps, duplicates and gaps. Never forward-fill a missing close or treat a partial candle as completed. Record missing data, expected pre-listing absence, insufficient history, API failure, retired instruments and invalid candles separately.

Five-minute ticker snapshots are stored as compact, time-stamped observations on the `market-data` branch. Partition snapshots by UTC hour and use compressed append-only records. Keep a documented retention policy for high-frequency snapshots; preserve the daily OHLCV history as the durable research dataset. The workflow must not re-download historical candle windows on each five-minute run.

A material active-universe or ticker-coverage failure blocks daily ranking-dependent portfolio transitions. Continue monitoring existing positions when fresh mark data is available, and mark incomplete runs PARTIAL. A newly discovered or insufficient-history asset remains visible in the universe manifest but does not enter rankings until qualified.

## 5. Original Q Indicator

Use daily close (P_t). Semi-cycle boundaries are determined causally by completed-bar fast/slow EMA crossovers. Reference EMA periods are 7 and 15 as illustrated in Figure 1 of the source paper; this is not an optimality claim.

EMA is recursive with alpha (2/(p+1)), seeded with the SMA of the first (p) valid closes. Before both EMAs are fully initialized, no crossover is available. The interval before the first genuine crossover is left-censored and must not be ranked. Do not invent a crossover at dataset start.

Bullish crossover: (Fast_t>Slow_t) and (Fast_{t-1}<=Slow_{t-1}). Bearish: (Fast_t<Slow_t) and (Fast_{t-1}>=Slow_{t-1}). Crossover is known only after the candle closes.

For a confirmed semi-cycle beginning at (t_0):
[
CPC_t=\sum_{\tau=t_0}^{t}(P_\tau-P_{\tau-1})
]
The first CPC observation includes the close-to-close difference on the crossover candle. Reset CPC at each confirmed crossover; never carry CPC across cycles.

[
Trend_t=MA(CPC,m)
]
Use a full-window simple moving average initially. The paper specifies MA but does not prescribe a universal (m) or (n). Provisional values: (m=5), (n=10); these are experimental defaults, not author parameters.

[
Noise_1=MA(|CPC-Trend|,n)
]
[
Noise_2=\sqrt{MA((CPC-Trend)^2,n)}
]
Require (n>m); use complete rolling windows and aligned residuals. Baseline noise is absolute deviation; RMS is a separate experiment. If a cycle lacks enough post-crossover observations, classify it INSUFFICIENT_CYCLE_HISTORY.

[
Q=\frac{Trend}{Noise}\times c
]
Initial (c=1.0), configurable and not represented as an author-prescribed constant. Zero or negligible noise that makes Q undefined must not be turned into an infinite/large rank. Exclude and report it.

Qualitative source thresholds: |Q| 0–1 noise-dominated; 1–2 weak; 2–5 moderate; >5 strong. Initial qualifying condition is strict (|Q|>2). It is a trend classification, not a success probability.

[
B=\frac{|Trend|}{|Trend|+Noise}\times100
]
B is supplementary and directionless. Source bands: 50–65 weak, 65–80 moderate, >80 strong; below 50 is noise-dominant/less convincing. Handle zero denominator.

Record all intermediate values, configuration, cycle start, direction, timestamps and data version. Golden tests must independently verify formulas, crossovers, resets, scaling invariance, offset invariance, no future leakage and zero-noise behaviour.

## 6. Full-universe ranking and execution eligibility

Calculate indicator values for every research-eligible contract. Bullish ranking sorts positive Q descending; bearish ranking sorts negative Q ascending (most negative first). Keep deterministic tie-breaks and audit every exclusion.

Separate research eligibility from execution eligibility. An asset may be ranked but fail minimum notional, quantity precision, liquidity or order-book depth requirements. If a top-ranked candidate is not executable, evaluate the next qualifying candidate and record the fallback.

Provisional liquidity policy must be configurable and separately validated. Starting defaults: 30 completed daily bars for median turnover; desired order notional <=0.1% of median daily turnover; maximum simulated book impact 10 bps; at most 10 fallback candidates. These are operational assumptions, not source-paper parameters.

## 7. Portfolio state machine

The account targets one long and one short, each 50% of current NAV; gross target 1.0x. This is dollar-neutral, not beta-neutral. The same symbol cannot fill both legs.

Select the highest-ranked executable candidate with Q>2 and lowest-ranked executable candidate with Q<-2. If either side is unavailable, do not open an unmatched new pair; at next daily rebalance close any surviving unmatched leg and remain flat until a complete pair exists.

On daily decisions: retain unchanged symbols; close/replace changed symbols independently; size each leg from 50% NAV; round quantity down to `qtyStep`; respect min quantity/notional and maximum market quantity; never round up to force a trade. Do not pyramid. Every transition has an explicit decision and event ID.

A stopped leg cannot be reopened by hourly monitoring. At the next completed daily decision it may re-enter only if it still qualifies and is selected. A surviving leg remains until next daily rebalance unless its own stop fires.

## 8. ATR stops and sampled monitoring

ATR(14) uses Wilder smoothing; seed with the first 14 true ranges, where first TR is high-low. Provisional stop multiplier k=3.0.

Long stop:
[
SL_L=\max(SL_{L,prev},HH_{post-entry}-k\times ATR)
]
Short stop:
[
SL_S=\min(SL_{S,prev},LL_{post-entry}+k\times ATR)
]

Initialize post-entry high/low at actual fill price. Never include pre-entry extremes. Calculate daily stop changes from completed daily candles only; new stops are effective only after their decision timestamp.

Monitor completed hourly candles, with one-minute data for partial-hour ownership/stop activation checks and finer stop verification. Use last traded prices to trigger stops and mark prices for NAV. Record all price sources.

**Never assume a trigger-price fill when monitoring is hourly.** The trigger may be observed only after candle completion and scheduled workflow delay. Forward paper exit is based on a fresh public order-book snapshot at actual detection time; record detection timestamp, book timestamp, fill time and VWAP. If quote is stale/unavailable, do not fabricate a fill.

For historical replay, model the configured schedule delay (initially 17 minutes after the hour close) plus a configurable operational lag. Use the first eligible one-minute reference at or after modeled detection and adverse spread/slippage assumptions. Report delay sensitivity. Do not claim continuous protection.

On a stop-out close only that leg; keep survivor, record single-leg exposure and continue monitoring. If multiple intervals were missed, process chronologically to identify a crossing but execute only at current detection-time conditions; never backdate.

## 9. Public order-book execution and costs

Use only public `GET /v5/market/orderbook` and `GET /v5/market/tickers`. For linear REST order books, the documented depth parameter supports up to 1,000 levels. Request a bounded depth (initially 200 or 1,000 after payload/latency benchmarking), validate the response and disclose that RPI orders are not included. Do not confuse REST limits with the separate WebSocket depth update tiers. Validate `ts` and matching-engine `cts` freshness. RPI orders are not exposed in the standard order-book snapshot; disclose this limitation.

For buys consume asks; for sells consume bids; calculate depth-weighted VWAP; support partial fill/reject if visible depth is insufficient. Apply configurable maximum impact. Historical order-book depth is unavailable from ordinary Klines, so historical execution must use next eligible one-minute open plus explicitly adverse spread/slippage assumptions. Never use signal-candle close retrospectively.

Use a provisional fee assumption of 0.10% per fill only as an explicit sensitivity baseline, not as the user's actual fee tier. Run higher-fee, higher-slippage and severe-friction scenarios. Fill-price effects already include slippage; do not deduct the same shortfall twice.

No broker or exchange order endpoints may exist in the project.

## 10. Funding

Use `GET /v5/market/funding/history` with category, symbol, start/end time and limit <=200. The endpoint has no pagination cursor; startTime alone returns an error, while bounded time windows are supported. Partition windows so no request can truncate more than 200 expected settlements; recursively subdivide full pages and verify expected count using each instrument's fundingInterval.

Use actual `fundingInterval` metadata. Funding cash flow:
[
Cashflow=-Side\times Quantity_{pre-settlement}\times MarkPrice_{settlement}\times FundingRate
]
Long side=+1, short=-1. Positive funding means long pays short.

Determine position state immediately before settlement. If a fill and settlement share indistinguishable timestamps, use a documented conservative rule and flag ambiguity. Use public mark-price Klines; a one-minute mark-price candle must be aligned carefully to settlement timestamp. Never silently replace missing settlement mark/funding with zero or last price. Only verified funding events enter authoritative accounting.

## 11. Accounting, event journal and state

Use Decimal/fixed-point for money, quantities, fees, funding and cash. NAV is:
[
NAV=Cash+UnrealizedPnL
]
Cash includes initial capital, realized gross price P&L, fees, confirmed funding and explicit adjustments. Do not double count realized P&L, fees or slippage.

Use SQLite as a transactional, rebuildable projection. The durable source of truth is immutable event batches stored on a dedicated `state` branch, not a mutable runner-local DB or Actions cache/artifact.

Each workflow produces a uniquely named event batch (for example `events/YYYY/MM/<run-id>.jsonl`) with unique event IDs and idempotency keys. Commit the entire batch atomically using a normal fast-forward push with conflict detection; no force push. If the state commit fails, the workflow must not claim the transition is durable. On a later run, replay already committed events into SQLite. Keep snapshots/checkpoints with checksums and schema version. Do not edit/delete past financial events; corrections are compensating events.

Before any new batch is committed, reconstruct the complete remote event-batch chain from the current `state` branch tree and verify that the new batch's `previous_batch_hash` equals the unique remote chain tip. Reject a second genesis batch, forks, cycles, orphaned/disconnected batches, invalid file paths, malformed blobs, and truncated Git trees. Do not trust a local SQLite hash or caller-supplied parent hash as evidence of the remote tip.

The `state` branch must have server-side GitHub branch protection or a repository ruleset that disallows force pushes/deletion and restricts writers before account initialization. Publisher-side fast-forward logic is not a substitute for server-side protection. Because this repository is public, every event file is public and persistent: never store credentials, personal identifiers or confidential account data in its Git history.

Storage is not unlimited. Estimate and monitor repository growth; partition compressed market data. If Git storage cannot safely support the required data volume, report the blocker instead of silently deleting history or introducing paid services.

## 12. Network access, automatic runner tests and official historical archive

### 12.1 Live API eligibility

The live market-data source remains Bybit Global V5 at exactly `https://api.bybit.com`. Bybit's Integration Guidance states that requests from US and mainland-China IP addresses are restricted and return HTTP 403. A 403 may have other causes, so retain the exact response, runner region/cloud, timestamp and endpoint; distinguish a provider-geography denial from rate limiting, malformed requests and general network errors.

The EEA endpoint `https://api.bybit.eu` is not an equivalent fallback for this project: current Bybit documentation limits its EU API to the "Connect to Third-Party Applications" feature for API-broker users. Do not substitute it for this unauthenticated public-market-data integration.

GitHub-hosted standard Linux jobs do not expose a selectable geographic region. Since 2026-10-28, eligible standard 2-core and 4-core Linux jobs may be scheduled automatically on AWS or Azure. The cloud provider and region remain scheduler-controlled; `ubuntu-slim` is not part of this eligible multi-cloud pool.

### 12.2 Automatic no-manual-input egress probe

A one-time matrix probe on 2026-11-16 tested the exact official Bybit server-time URL from six standard GitHub-hosted Linux jobs across Ubuntu 22.04, 24.04 and 26.04. GitHub assigned five jobs to Azure US regions and one to AWS `us-west-2`. All six requests returned HTTP 403 with the CloudFront country-block response. Evidence: workflow run `43911753549`.

This establishes that enabling GitHub's automatic AWS/Azure pool and changing standard Ubuntu labels does not currently provide an allowed egress route. Do not keep spawning jobs hoping for a different country, attempt to pin an undocumented region, or treat a single transient success as a stable deployment. Any future runner candidate must be tested against the exact endpoint, and its reported region/cloud and response must be recorded. Scheduled operation requires a repeatably allowed route, not a one-off pass.

No proxy, VPN, residential proxy, outbound relay, API-domain rotation, paid runner or unapproved user-installed self-hosted runner may be used to disguise a blocked source location. An explicitly requested replacement exchange is not a geographic bypass; it is a provider migration and must pass every acceptance gate in Section 12.5. Do not silently change the exchange, create exchange accounts, request credentials or migrate data until the candidate is independently verified and the user has approved the selected provider.

### 12.3 Official Bybit historical trade-archive lane

The official public archive is separately accessible from the tested GitHub-hosted runner pool. On 2026-11-16, Ubuntu 22.04, 24.04 and 26.04 jobs each fetched the first 2,048 bytes of:

`https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-11-15.csv.gz`

All three received HTTP 206 and valid gzip magic bytes. The response advertised a total compressed file size of 126,793,002 bytes. Evidence: workflow run `43912009008`. Bybit's public-trade documentation also states that archived historical trades can be downloaded from its website.

Daily linear trade archive path:

`https://public.bybit.com/trading/{SYMBOL}/{SYMBOL}{YYYY-MM-DD}.csv.gz`

The documented trade columns are `timestamp,symbol,side,size,price,tickDirection,trdMatchID,grossValue,homeNotional,foreignNotional`; recent files may include an additional `RPI` column. Parse by header name, not fixed trailing-column position. Validate symbol, UTC date, finite positive price, nonnegative size, row count, gzip CRC and source-file checksum. Write downloads atomically and make date/symbol backfill resumable. Do not assume every symbol has every date.

For each UTC day, trades can be aggregated into OHLCV: first price by timestamp, maximum price, minimum price, last price, summed size and turnover; retain trade count and taker-buy/taker-sell volume. Validate chronology and duplicates before declaring a bar complete. This is an archive-derived trade candle, not a native Bybit Kline response.

This lane may support selective historical price research and daily-bar reconstruction without the blocked V5 API. It is not evidence of a complete full-universe or point-in-time dataset: archive coverage varies by symbol/listing date, the directory alone does not establish historical execution eligibility or delisting status, and downloading a daily trade file can be large. Establish coverage and storage estimates before any universe-scale backfill. Do not silently select only surviving symbols and label the result survivorship-free.

The trade archive does not provide a verified replacement for historical funding settlements, mark/index prices, historical L2 order-book depth, current instrument quantity/price filters, or fresh live quotes. No spread, order-book VWAP, funding cashflow or intraday stop fill may be invented from daily trade aggregates. Any price-only replay that omits funding or executable depth must be labelled exploratory/gross and must not be presented as a full strategy validation.


### 12.4 Forward-operation boundary

A daily archive is not a live or intraday feed. It cannot support the current hourly stop monitor, timely order-book simulation, funding settlement reconciliation or reliable current-universe discovery. Do not enable a forward paper account, daily rebalance workflow or hourly monitor from archive files alone. Keep live API integration and portfolio automation disabled until a repeatably permitted public live-data route and the independent accounting/recovery gates pass.

### 12.5 Ordered 24/7 perpetual-exchange qualification gate

The user explicitly requested this provider order:
1. HTX
2. MEXC
3. Binance
4. WEEX
5. Bitget

Run the public qualification in that order. HTX is a hard jurisdiction rejection for Romania while the current HTX terms continue to exclude EU member states. Do not use a VPN, proxy, alternate identity or remote account to bypass that restriction. Continue to the next provider.

If none of the five primary providers is both technically suitable and demonstrably available for Romanian EEA derivatives access, evaluate **OKX EEA as the primary route** and retain **Kraken EEA as the backup**. Do not choose a provider just because its public endpoints respond.

This authorization covers public unauthenticated research and diagnostic API calls only. It does not authorize account creation, credentials, private endpoints, balance/position queries, orders, Testnet, or live trading.

A provider must pass every relevant gate:

1. **Romanian/EEA product eligibility:** inspect the current user agreement, country restrictions, regional entity, derivatives product notices and product-specific eligibility. A country missing from a prohibited list is not proof of authorization. Record outcomes as VERIFIED, PROHIBITED, or UNVERIFIED. PROHIBITED is an immediate hard failure; UNVERIFIED cannot be promoted to approved.
2. **True perpetual product:** require non-expiring perpetual contracts, not delivery futures or expiring CFDs. Record each contract's product type, delivery/expiry state, funding interval and any settlement, maintenance or trading pauses. "24/7" means the provider documents continuous trading for that contract class; distinguish it from a continuously available quote or 24/7 platform access. Stock/TradFi perpetuals may still have underlying-market closures, index-provider outages, corporate-action adjustments, halted periods or low-liquidity sessions; preserve those constraints.
3. **All listed asset classes:** fully enumerate every active API-tradable perpetual and classify only from provider metadata/official product documentation. Include every class the exchange actually offers (for example crypto, equities/stock indices, FX, commodities, precious metals and energy where present). Keep unclassified instruments visible and ineligible until resolved. Do not invent classes or infer them from ticker strings alone.
4. **Cross margin:** require documented cross-margin support for every retained instrument and the selected product family. Record whether the margin pool is shared account-wide, per settlement currency, or only within a contract type. Exclude isolated-only contracts. Distinguish ordinary cross margin from multi-asset/cross-currency collateral; do not assume they are equivalent. Prefer a single-currency cross mode compatible with the research account unless the currency-aware ledger is implemented and approved.
5. **Universe breadth and completeness:** enumerate all pages; require at least 50 active, cross-margin, 24/7 perpetuals overall for the existing cross-sectional strategy, while documenting every available class even if its individual count is smaller. Record excluded symbols, lifecycle state and reasons. No partial-universe ranking.
6. **Full contract metadata:** for every retained symbol, validate quote, settlement, margin and P&L currency; contract size/multiplier; tick size; quantity/contract step; minimum order size and notional; maximum order/position; precision; leverage and maintenance-margin tiers; status; listing/delivery fields; funding interval and next funding timestamp. Reconcile every retained contract against official provider specifications. Any mismatch or missing critical field excludes that contract.
7. **Market-data contract:** validate server time, complete instrument pagination, ticker, order-book depth, completed daily and intraday candles, funding history and mark/index price where applicable. Test at least one representative contract per asset class during initial qualification. Require nonempty successful responses and valid provider-level success codes; HTTP 200 alone is insufficient. The next acceptance stage must run these data checks across the entire eligible universe, not only BTC.
8. **Funding semantics:** verify funding history and timestamps per product class; confirm rate sign, settlement interval, index/mark reference, timestamp units and whether historical data is complete enough for the research horizon.
9. **Runner access:** call the documented official public host from standard GitHub-hosted runners. Record runner image, source region when supplied by GitHub, HTTP/API result and UTC time. Do not disguise source location.
10. **Adapter and currency accounting:** keep exchange-specific schemas outside the indicator/ranking core. Normalize contract IDs, currencies, precision, candles, books, funding and timestamps. For non-USDT P&L or collateral, implement time-aligned conversion, collateral haircuts, conversion fees, interest, funding, fees and NAV attribution in the accounting base currency. Never silently treat USD, USDT, USDC or coin collateral as equivalent.
11. **Independent tests:** add fixture-based parser tests, pagination and duplicate tests, invalid/missing metadata tests, per-class endpoint tests, Decimal sizing tests and live public diagnostics. A successful probe is not a production adapter.
12. **Historical and forward separation:** keep historical replay and forward paper account data separate. No forward account may initialize until full-universe freshness/coverage, stops, funding, fees, accounting, persistence, recovery and report reconciliation pass.

### 12.6 Fallback routes and current known constraints

**OKX EEA primary fallback:** Use the region-specific API host `https://eea.okx.com` for EU-registered accounts; the global `www.okx.com` host is not the correct EEA API target. OKX Europe's perpetual-futures guide documents non-expiring USDT/crypto-margined perpetuals with 24/7 trading and cross/isolated modes, but it also warns that availability may differ by customer. Prefer Futures account mode with cross margin, where positions sharing the same margin currency share margin. Multi-currency cross-margin mode can share multiple collateral assets, but activation requires at least USD 10,000 in account assets and must not be assumed available to the 100 USDT research account. Distinguish true non-expiring swaps from EEA X-Perps: X-Perps are five-year fixed-expiry contracts, not non-expiring perpetuals. They are documented as available to eligible clients in all 30 EEA jurisdictions subject to KYC and an appropriateness assessment, but they are not a like-for-like substitute for the requested 24/7 non-expiring perp universe. Verify actual account-level availability rather than assuming it.

**Kraken EEA backup:** Kraken EEA documents linear multi-collateral perpetuals, cross margin and supported collateral currencies, with USD P&L by default. Retain only contracts whose tick size, minimum lot and maximum position reconcile to Kraken's official EEA specification table. The latest diagnostic counted 95 EEA margin/precision candidates, 69 exact official-spec matches and 26 mismatches; exclude all 26 mismatches. The earlier endpoint test sampled BTC only, so the 69-symbol subset still needs full-universe ticker/book/candle/funding coverage and Decimal sizing validation. Implement currency-aware USD P&L and collateral/USDT reporting before migration.

**Known exclusions:** Crypto.com remains NOT_READY: six USD-quoted crypto perpetuals, funding-history API errors and Romania on its published derivatives restrictions list. HTX is not eligible while Romania is listed within the EU-wide excluded jurisdictions. Do not restore either candidate by changing the source IP.

A readiness workflow fails closed if a required check fails. It may report a technical pass separately from legal/account approval, but may never label a provider READY when jurisdiction is UNVERIFIED, when a product class lacks cross-margin support, when contract specifications are unreconciled, or when full eligible-universe data coverage is absent.

## 13. Workflow design

Required eventual workflows: CI, public API preflight, resumable bootstrap, daily research/rebalance, hourly monitor, manual recovery.

Start with CI and public API smoke tests. Do not enable automatic paper rebalance until data, accounting, stops, recovery and persistence have passed acceptance tests.

Daily and hourly state-mutating jobs share concurrency control and database idempotency. Use queued concurrency where supported, but never rely on queue order; catch up by persisted timestamps. GitHub Actions is best-effort scheduling and not a real-time monitor.

Daily sequence: restore/verify state; server time; catch up existing risk observations; fetch full universe; update/validate data; calculate completed-bar indicators; rank; update eligible stops; calculate pair transition; obtain current book; simulate fills; reconcile funding/NAV; persist event batch; regenerate and publish reports. An incomplete universe blocks new ranking-dependent transitions.

Hourly sequence: restore; find missed intervals; fetch completed candles; process chronologically; detect stops against stop values active at each timestamp; fetch fresh book; execute at current detection-time paper prices; reconcile; persist; publish risk status.

Use bounded batches and resumable checkpoints for full backfill. No partial-universe ranking or positions during BOOTSTRAPPING.

## 14. Historical and forward account separation

Historical replay is chronological, point-in-time where possible, and explicitly survivorship-biased if historical universe snapshots are unavailable. It uses next-minute execution, hourly stop monitoring, one-minute detection execution, historical funding and costs. Historical hourly/minute data is downloaded only for actual holding periods and required intervals.

Forward account begins at its real initialization timestamp with 100 USDT. No historical trades/equity may enter the forward account. Missed daily decisions are not backfilled with invented fills; record skipped dates and make any new decision at actual workflow time with current book.

## 15. Performance reporting

Publish root `STATUS.md`, equity SVG, drawdown SVG and CSV/JSON exports. Forward and historical reports remain separate. All figures derive from persisted ledger/valuation records and carry run ID, account mode, config hash, source commit and UTC timestamp.

Metrics: lifetime return, CAGR, daily volatility, Sharpe, Sortino, Calmar, max drawdown, drawdown/recovery duration, win rate, avg win/loss, profit factor, expectancy, costs, funding and long/short attribution. Use 365-day annualization. Sharpe requires >=30 valid daily returns. Sortino requires >=20 consecutive daily returns and >=5 negative returns, MAR=0, annualized by sqrt(365). Withhold formal CAGR until >=1 year; earlier estimates are provisional. Never show unavailable metrics as zero.

Equity and drawdown curves must match CSV values. Hourly-sampled drawdown is an observed estimate, not continuous intrahour max drawdown. Show single-leg exposure duration, missing monitor intervals, longest gap and data quality.

## 16. Testing and independent audit

Mock API responses in CI. Tests cover indicator golden values, causality, pagination, duplicates, candle validation, missing data gates, ranking, selection, sizing, VWAP, partial fills, fees, funding, stop activation/delay/gaps, missed intervals, idempotency, event hash chain, persistence recovery, NAV reconstruction and report/CSV agreement.

Before completion independently reconstruct several trades from raw data and the entire forward account from persisted event batches. Distinguish implemented, unit-tested, integration-tested, historical-replay-tested, forward-paper-verified and independently audited.

## 17. Phased delivery

1. Repository/specification.
2. Bybit client and data-quality tests.
3. Q/B mathematical engine and golden tests.
4. Full-universe ranking.
5. Portfolio state machine and sizing.
6. Paper broker, stops, funding and accounting.
7. Event batch persistence and recovery.
8. Historical replay.
9. CI and public API preflight.
10. Daily/hourly workflows only after acceptance.
11. STATUS, equity, drawdown and exports.
12. Independent audit.

## 18. Acceptance and disclosure

Do not call the complete system finished until full universe retrieval, available daily history, validated Q, rankings, chronological replay, separate forward paper account, realistic stop timing, verified funding, reconciled NAV, durable event storage, recovery, tests, workflows and main-branch reports are demonstrated.

No live trading. No Testnet. No private endpoints. No credentials. No paid infrastructure. No false fills. No incomplete-universe claims. No hidden adjustments. No unsupported performance claims.

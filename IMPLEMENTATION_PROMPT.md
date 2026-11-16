# Master Implementation Directive v2.3
## Market-Neutral Trend-Quality Indicator — Bybit Full-Universe Paper Research

Repository: `takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM`  
Target: `main`  
Data: unauthenticated Bybit Global public API only (`https://api.bybit.com`)  
Execution: local paper simulation only; no live orders, Testnet, credentials or private endpoints.  
Initial forward capital: 100 USDT. Target gross exposure: 1.0x NAV, 50% long and 50% short.

Primary source: David Sepiashvili, [Trend-Quality Indicator](https://www.prorealcode.com/wp-content/uploads/2019/03/24-Q-Indicator.pdf).

## 1. Mission and non-negotiable priorities

Build an auditable, persistent, self-improving quantitative research system that evaluates every eligible Bybit USDT linear perpetual contract, calculates the original Q Indicator, ranks both directions, and eventually maintains one long and one short in a separate forward paper account.

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

## 3. Bybit universe and API contracts

Use `GET /v5/market/instruments-info` with `category=linear`, `status=Trading`, `limit=1000`, and cursor pagination using `nextPageCursor`. Do not send `contractType`, `quoteCoin`, or `settleCoin` as unsupported filters. Filter returned objects locally for:
- `status == Trading`
- `contractType == LinearPerpetual`
- `quoteCoin == USDT`
- `settleCoin == USDT`

Use the returned `launchTime`, `deliveryTime`, `fundingInterval`, `priceFilter.tickSize`, `lotSizeFilter.qtyStep`, `minOrderQty`, `minNotionalValue`, and maximum quantity fields. Recheck instrument rules regularly; do not treat quantity limits as immutable.

Retrieve the entire paginated universe every daily run. Maintain listing, retention, inactivity and delisting history. An API failure is not a delisting.

## 4. Historical candles and completeness

Use `GET /v5/market/kline`, `category=linear`, `interval=D`, `symbol`, timestamp `start/end`, `limit<=1000`. The endpoint has no cursor and returns newest first. Retrieve history backward using the oldest returned start timestamp minus one millisecond as the next end boundary; guard against duplicate/non-moving pages. Store and sort chronologically.

Use `GET /v5/market/time`; a UTC daily candle is completed only when `start + 86,400,000 <= server_time_ms`. Never use an unfinished candle. Validate OHLC, positive price, volume, turnover, timestamps, duplicates and gaps. Never forward-fill missing prices.

Distinguish expected pre-listing absence, insufficient history, API failure, missing history, invalid candle and incomplete latest candle. A material active-universe retrieval failure blocks new ranking-dependent portfolio transitions and marks the run PARTIAL. Continue risk monitoring of existing positions when possible.

Use daily turnover for historical liquidity screening. Retrieve hourly and one-minute data only for actual selected or simulated holdings and their monitoring/execution windows, unless a documented test requires otherwise.

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

Storage is not unlimited. Estimate and monitor repository growth; partition compressed market data. If Git storage cannot safely support the required data volume, report the blocker instead of silently deleting history or introducing paid services.

## 12. Workflow design

Required eventual workflows: CI, public API preflight, resumable bootstrap, daily research/rebalance, hourly monitor, manual recovery.

Start with CI and public API smoke tests. Do not enable automatic paper rebalance until data, accounting, stops, recovery and persistence have passed acceptance tests.

Daily and hourly state-mutating jobs share concurrency control and database idempotency. Use queued concurrency where supported, but never rely on queue order; catch up by persisted timestamps. GitHub Actions is best-effort scheduling and not a real-time monitor.

Daily sequence: restore/verify state; server time; catch up existing risk observations; fetch full universe; update/validate data; calculate completed-bar indicators; rank; update eligible stops; calculate pair transition; obtain current book; simulate fills; reconcile funding/NAV; persist event batch; regenerate and publish reports. An incomplete universe blocks new ranking-dependent transitions.

Hourly sequence: restore; find missed intervals; fetch completed candles; process chronologically; detect stops against stop values active at each timestamp; fetch fresh book; execute at current detection-time paper prices; reconcile; persist; publish risk status.

Use bounded batches and resumable checkpoints for full backfill. No partial-universe ranking or positions during BOOTSTRAPPING.

## 13. Historical and forward account separation

Historical replay is chronological, point-in-time where possible, and explicitly survivorship-biased if historical universe snapshots are unavailable. It uses next-minute execution, hourly stop monitoring, one-minute detection execution, historical funding and costs. Historical hourly/minute data is downloaded only for actual holding periods and required intervals.

Forward account begins at its real initialization timestamp with 100 USDT. No historical trades/equity may enter the forward account. Missed daily decisions are not backfilled with invented fills; record skipped dates and make any new decision at actual workflow time with current book.

## 14. Performance reporting

Publish root `STATUS.md`, equity SVG, drawdown SVG and CSV/JSON exports. Forward and historical reports remain separate. All figures derive from persisted ledger/valuation records and carry run ID, account mode, config hash, source commit and UTC timestamp.

Metrics: lifetime return, CAGR, daily volatility, Sharpe, Sortino, Calmar, max drawdown, drawdown/recovery duration, win rate, avg win/loss, profit factor, expectancy, costs, funding and long/short attribution. Use 365-day annualization. Sharpe requires >=30 valid daily returns. Sortino requires >=20 consecutive daily returns and >=5 negative returns, MAR=0, annualized by sqrt(365). Withhold formal CAGR until >=1 year; earlier estimates are provisional. Never show unavailable metrics as zero.

Equity and drawdown curves must match CSV values. Hourly-sampled drawdown is an observed estimate, not continuous intrahour max drawdown. Show single-leg exposure duration, missing monitor intervals, longest gap and data quality.

## 15. Testing and independent audit

Mock API responses in CI. Tests cover indicator golden values, causality, pagination, duplicates, candle validation, missing data gates, ranking, selection, sizing, VWAP, partial fills, fees, funding, stop activation/delay/gaps, missed intervals, idempotency, event hash chain, persistence recovery, NAV reconstruction and report/CSV agreement.

Before completion independently reconstruct several trades from raw data and the entire forward account from persisted event batches. Distinguish implemented, unit-tested, integration-tested, historical-replay-tested, forward-paper-verified and independently audited.

## 16. Phased delivery

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

## 17. Acceptance and disclosure

Do not call the complete system finished until full universe retrieval, available daily history, validated Q, rankings, chronological replay, separate forward paper account, realistic stop timing, verified funding, reconciled NAV, durable event storage, recovery, tests, workflows and main-branch reports are demonstrated.

No live trading. No Testnet. No private endpoints. No credentials. No paid infrastructure. No false fills. No incomplete-universe claims. No hidden adjustments. No unsupported performance claims.

# Implementation Plan

## Current state

The repository is in emergency red-team no-go, not a trading-ready phase. No paper account, historical backtest or forward performance is claimed. Latest verified core CI run 43931058486 passed Ruff and 67 tests in 0.25 seconds on commit `a1c0e083893e5566fb2173b22c7afe81b196b4b9`.

## Phase 0 — Specification and safety

- [x] Verify exact repository, public visibility, default branch and initial empty state.
- [x] Establish v2.6 implementation specification and decision log with explicit exchange qualification gates.
- [x] Keep all execution paper-only; do not add private API calls or exchange order submission.
- [x] Add CI on Python 3.12 with Ruff and pytest.
- [x] Verify red-team repairs: run 43931058486 passed Ruff and 67 tests on commit `a1c0e083893e5566fb2173b22c7afe81b196b4b9`.
- [x] Keep automatic portfolio workflows disabled.
- [ ] Complete the data-access gate using a permitted runner/network.

## Phase 1 — Core mathematics and public API

- [x] Pure Python EMA and causal semi-cycle detection.
- [x] CPC, Trend, linear/RMS Noise, Q and B.
- [x] Wilder ATR.
- [x] Public Bybit server-time, instrument pagination, backward Kline retrieval, funding-history windows and order-book parsing.
- [x] Mocked API contract and pagination tests.
- [ ] Pass live public API integration; a 6-job multi-cloud test still returned HTTP 403 from five Azure US allocations and one AWS `us-west-2` allocation (run 43911753549).
- [x] Verify official Bybit static trade archive access from standard GitHub-hosted runners (3/3 HTTP 206 + valid gzip samples; run 43912009008).
- [x] Inspect the compressed archive CSV header and first data row on hosted runners (3/3 pass; run 43912788709; full-file integrity and coverage still pending).
- [ ] Implement and test a resumable, integrity-checked Bybit trade-archive importer and daily OHLCV aggregator for selective historical research only.

## Phase 2 — Ranking and data gates

- [x] Signed-Q ranking primitives for bullish and bearish candidates.
- [x] Execution eligibility filtering at the candidate-ranking function boundary.
- [x] Deterministic distinct-symbol long/short pair selection with bounded fallback.
- [ ] Complete full-universe ranking on a verified point-in-time universe and real Bybit market data.
- [ ] Separate research-universe membership from execution eligibility for all instruments.
- [ ] End-to-end data coverage, freshness, gap, duplicate and completeness gates.
- [ ] Persist daily universe snapshots and candle history.

## Phase 3 — Paper portfolio and execution

- [x] Decimal position P&L, funding cashflow, exposure/NAV arithmetic and quantity sizing primitives.
- [x] Pure order-book VWAP paper simulator with fee, shortfall, partial-fill and impact checks.
- [x] Historical next-minute execution-price/slippage primitive (does not claim historical depth).
- [ ] Fully integrated deterministic pair/position state machine.
- [ ] Sampled ATR stop monitor with detection-time execution and gap handling.
- [ ] Funding settlement ordering and cash/NAV reconciliation across both legs.
- [ ] Portfolio-level limits, minimum notional/quantity precision and rejection accounting.

## Phase 4 — Durable state and recovery

- [x] Canonical immutable event batches, SHA-256 event chain and batch hash.
- [x] Local atomic batch writer and schema validation.
- [x] Dedicated `state` branch created; append-only behavior is enforced by the application publisher, not server-side branch protection.
- [x] GitHub state-branch publisher with mocked API tests, duplicate protection and non-force fast-forward update.
- [x] Verify every remote event batch and require the appended batch's previous hash to match the unique remote chain tip; reject forks, orphan batches and duplicate genesis roots (mocked tests).
- [x] Transactional SQLite projection with chain/idempotency checks and integrity verification.
- [x] Remove server-side branch-protection and Administration-token dependencies for paper-only operation.
- [x] Serialize MEXC and the retired manual Polymarket state publishers with one non-cancelling repository-wide concurrency group.
- [x] Verify remote event-chain topology, exact canonical read-back, idempotent replay and non-forced fast-forward conflict handling in the publisher.
- [x] Restore local event batches by `previous_batch_hash` links rather than exchange timestamps; reject forks, orphan batches and duplicate identifiers.
- [x] Verify the first live GitHub probe write/read-back and following fresh-checkout recovery on the actual state branch (probe run 43989363042; recovery/init run 43990948665).
- [ ] Implement complete restore/rebuild from state-branch event files after runner loss.
- [ ] Integrate persistence as a mandatory precondition for any paper state transition.

## Phase 5 — Historical replay and validation

- [ ] Chronological causal replay with no look-ahead.
- [ ] Reconstruct point-in-time eligible universe and disclose survivorship limitations.
- [ ] Hourly stop-monitor simulation with detection delay and later executable price.
- [ ] Apply minute execution references, fees, spread/impact and funding settlements.
- [ ] Reconcile trade ledger, cash ledger and NAV independently.
- [ ] Validate sensitivity to costs, missing data, parameter choices and market regimes.

## Phase 6 — Forward paper operation and reporting

- [x] Add CI and manually dispatchable public API preflight.
- [x] Add reusable daily equity and drawdown analytics with explicit minimum-sample gates.
- [ ] Complete resumable historical backfill.
- [ ] Initialize the separate forward paper account only after all data/accounting gates pass.
- [ ] Add daily and hourly workflows only after end-to-end tests pass on a permitted runner.
- [ ] Generate STATUS, equity curve, drawdown chart, human-readable risk report and export files from persisted events.
- [ ] Monitor data freshness, scheduled-run delay, missing coverage, persistence conflicts and accounting invariants.

## External data access

### Live API blocker
The automatic GitHub multi-cloud standard Linux pool was tested across Ubuntu 22.04, 24.04 and 26.04. All 6/6 calls to the required Global V5 server-time endpoint returned HTTP 403; one runner was AWS `us-west-2`, and it was blocked too. GitHub controls the region and cloud selection; no geographic selector is documented. No VPN, proxy, relay, host rotation or paid service is permitted. The user has explicitly requested replacement-exchange evaluation; this is a provider migration, not an access-control bypass, and it must pass the complete qualification gate before implementation.

### Historical archive route
The official Bybit `public.bybit.com/trading` archive is reachable from the same runners. Three separate jobs fetched a valid gzip range from a dated BTCUSDT trade file (HTTP 206). This can be used to build an optional historical-only lane:
- Enumerate archive symbols and dates, then download only the requested symbol/date files.
- Validate CSV headers, UTC timestamp range, symbol, finite prices, sizes, gzip CRC, checksum and non-empty row count.
- Aggregate daily trades into UTC OHLCV with trade count, turnover and taker-side volume.
- Store coverage manifests and missing-date reasons; support atomic resumable downloads.
- Estimate storage/runtime and audit symbol coverage, launch/delist dates and survivorship bias before broad universe replay.

This archive does not establish funding, mark/index data, historical L2 depth, or fresh quotes. Do not use it for forward operation or fabricate intraday executable prices. Selective price-only replay must explicitly disclose omitted funding and execution-depth effects.

### Release implications
Historical price research may proceed after the importer and coverage gates are implemented. The live Bybit API gate remains blocked and all forward paper automation remains disabled until a compliant, repeatable public-data route and all accounting/recovery gates pass.

## Emergency red-team and replacement selection

- [x] Correct maximum drawdown duration to use the longest underwater episode; test exact high-water-mark recovery resetting the next episode clock.
- [x] Anchor every appended event batch to the verified remote chain tip; reject multiple genesis roots, orphans, forks and truncated state trees in mocked integration tests.
- [x] Replace Crypto.com false-positive candidate probe with a strict readiness gate; all three runner jobs currently reject it.
- [ ] Configure server-side protection for the public `state` branch and resolve the public-ledger privacy architecture before state initialization.
- [ ] Evaluate a replacement exchange using official jurisdiction restrictions, a sufficiently broad USDT-settled perpetual universe, funding-history availability, full public market-data APIs, precision metadata and repeatable runner connectivity.
- [ ] Implement a normalized provider adapter only after a candidate passes every gate. No replacement exchange is approved at present.

Crypto.com is NOT_READY: only six USD-quoted contracts, failed funding-history API code 40004 for the two tested index identifiers, quote-currency mismatch, and unverified collateral/jurisdiction. Its official derivatives restriction list includes Romania. Do not migrate to it.

## Release gate

No automated portfolio transition may run until complete universe/data coverage, causal calculations, execution timing, funding and fee accounting, independent NAV reconciliation, durable Git persistence and restore/recovery all pass integration tests.



## Phase 0B — ordered 24/7 cross-margin perpetual-provider search

- [x] Refine the master directive to include all explicitly listed perpetual asset classes, documented cross margin and Romanian/EEA product eligibility.
- [x] Preserve the requested primary order: HTX, MEXC, Binance, WEEX, Bitget.
- [x] Add strict provider-specific contract eligibility parsers and unit tests.
- [x] Add a read-only GitHub Actions workflow that checks instrument metadata and samples ticker, order-book, daily candle and funding endpoints by available asset class.
- [ ] Complete the public probes on the current main commit and inspect their full reports.
- [ ] If none of the five is both technically viable and legally/product-eligible for Romania, use OKX EEA as the primary fallback and retain Kraken EEA as backup.
- [ ] For either fallback, reconcile every retained contract against official specifications before coding the production adapter.
- [ ] Implement currency-aware P&L/collateral/funding/fee/NAV accounting for any non-USDT settlement route.
- [ ] Run the next acceptance test across every eligible contract and every available asset class; BTC-only endpoint coverage is insufficient.

The new workflow uses public, unauthenticated market-data endpoints only. Public API success is a technical signal, never proof of Romanian user eligibility. HTX is skipped at the jurisdiction gate because its published EU restrictions include Romania. No exchange account, credential, private endpoint or order is used.



## Phase 0C — Per-instrument cross-margin Perps selection and Polymarket-first implementation

- [x] Correct requirement: the exchange does not need to offer every asset class. Include every active instrument with cross-margin capability, across all categories the provider does offer.
- [x] Set provider order to Polymarket Perps → MEXC → Bitget; stop at the first technically suitable public API.
- [x] Add a public Polymarket Perps API adapter, with instrument, bulk ticker/statistics, fee, book, daily-candle and funding reads.
- [x] Add tests for cross-margin/isolated filtering, new categories, metadata, pagination, fee/funding reads and retry errors.
- [x] Add ordered provider qualification workflow and a separate market-data branch.
- [x] Add an incremental market-data store with instrument lifecycle manifest, date-partitioned daily OHLCV and compressed five-minute snapshots.
- [ ] Pass CI and the public Polymarket API acceptance run; only then mark Polymarket as selected.
- [ ] Bootstrap up to 365 days of available completed daily candles once per active cross-margin instrument, with checkpoints.
- [ ] Build the five-minute ticker snapshot cycle and first-after-daily-close idempotent Q/ranking/portfolio transition.
- [ ] Complete book-based paper entry/exit, funding reconciliation at observed settlement timestamps, fees, ATR stops, pUSD accounting and state-branch event publication.
- [ ] Do not initialize the forward paper account until all active cross-margin data and accounting gates pass.

The public-data API probe does not use a wallet, API key, private account endpoint or order operation. Five-minute GitHub Actions scheduling is best-effort, not exchange-grade real-time protection. Portfolio ranking uses completed daily candles only.


## Phase 0D — MEXC public-data adapter and paper-research implementation (2026-11-17)

- [x] Run the independent Bitget curiosity screen without changing the selected provider.
- [x] Preserve ordered provider history: Polymarket Perps failed the required fee/book coverage gate; MEXC passed first; Bitget later passed its curiosity sample.
- [x] Select MEXC Futures on public API evidence: 1,143 active cross-margin linear perps across settlements, including a 1,061-contract USDT execution/account subset.
- [x] Implement MEXC public instrument, bulk ticker, depth, daily Kline, funding history and server-time adapter for the all-settlement cross-margin research universe.
- [x] Normalize per-contract positionOpenType, settlement, contract multiplier, quantity/price steps, min/max volume, leverage and fee fields.
- [x] Preserve unclassified and future asset categories; keep research universe separate from execution eligibility.
- [x] Convert contract-denominated depth and Kline volume using contractSize; keep USDT turnover separately.
- [x] Add MEXC cross-sectional positive/negative Q ranker and execution-gated candidate lists.
- [x] Add simulated book VWAP fills, fees, maximum impact and stale-book rejection.
- [x] Add USDT portfolio accounting primitives for cash, realized/unrealized P&L, fees, signed funding, ATR stops, daily equity and sample-gated performance.
- [x] Extend provider-isolated incremental storage for daily candles, five-minute snapshots, funding and lifecycle state.
- [x] Add bounded 365-day initial bootstrap, resumable 150-instrument batches and incremental candles after stored cursors.
- [x] Verify sampled Day1 boundaries at 00:00 UTC across crypto, equity, commodity, FX and unclassified instrument groups.
- [x] Add read-only hosted-runner MEXC preflight; success evidence is linked in STATUS.md.
- [x] Add a five-minute MEXC public-data/ranking/forward-paper workflow; `PAPER_STATE_WRITE_ENABLED` defaults to true and can be disabled with the repository Actions variable.
- [x] Verify successful market-data branch commits after correcting the branch's ignored data directory. Runs 43976810498 and 43977234937 both completed, committed public candles/snapshots/reports and uploaded artifacts; progress advanced from 150 to 300 bootstrapped instruments.
- [ ] Complete full-universe data-quality/freshness verification and independent Q ranking reconstruction.
- [x] Configure a shared single-writer concurrency group across every workflow that can append to the state branch.
- [x] Verify the real publisher/read-back and fresh-checkout recovery cycle on the live GitHub state branch (run 43990948665; exact read-back, linked hashes and later account restore confirmed).
- [x] Initialize and independently restore the separate 1 USDT forward paper account after the recovery probe passes (initialization run 43990948665; follow-up restore run 43991147324).
- [ ] Implement chronological historical replay, survivorship-aware universe reconstruction and cost/funding/stop-delay sensitivity.
- [ ] Generate verified equity and drawdown charts and human-readable performance report from persisted NAV data.

MEXC is the current selected public-data provider. This phase overrides earlier historical Polymarket-first/Bybit-first plan entries. The account writer is enabled by default in the MEXC workflow. The live recovery probe, 1 USDT account initialization and subsequent account restore have all been verified. The account is currently flat pending a pair that meets execution constraints at 1 USDT; no profitability claim or meaningful performance statistics are available yet. The branch is intentionally unprotected, with residual privileged-rewrite risk documented in OPERATING_MODEL.md.

# Implementation Plan

## Current state

The repository is in a validated core-code phase, not a trading-ready phase. No paper account, historical backtest or forward performance is claimed. The current `main` CI run is green: Ruff passed and pytest reported 62 passed.

## Phase 0 — Specification and safety

- [x] Verify exact repository, public visibility, default branch and initial empty state.
- [x] Establish v2.4 implementation specification and decision log.
- [x] Keep all execution paper-only; do not add private API calls or exchange order submission.
- [x] Add CI on Python 3.12 with Ruff and pytest.
- [x] Verify core CI: 62 tests pass on commit `d7680c009904c4d0daa85a48fb61bc93ddb2dc15`.
- [x] Keep automatic portfolio workflows disabled.
- [ ] Complete the data-access gate using a permitted runner/network.

## Phase 1 — Core mathematics and public API

- [x] Pure Python EMA and causal semi-cycle detection.
- [x] CPC, Trend, linear/RMS Noise, Q and B.
- [x] Wilder ATR.
- [x] Public Bybit server-time, instrument pagination, backward Kline retrieval, funding-history windows and order-book parsing.
- [x] Mocked API contract and pagination tests.
- [ ] Pass live public API integration; standard free GitHub-hosted runners are blocked by CloudFront country restriction (eastus2, eastus and westus3).

## Phase 2 — Ranking and data gates

- [x] Signed-Q ranking primitives for bullish and bearish candidates.
- [x] Execution eligibility filtering at the candidate-ranking function boundary.
- [x] Deterministic distinct-symbol long/short pair selection with bounded fallback.
- [ ] Complete full-universe ranking on real Bybit market data.
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
- [x] Dedicated `state` branch created with append-only policy.
- [x] GitHub state-branch publisher with mocked API tests, duplicate protection and non-force fast-forward update.
- [x] Transactional SQLite projection with chain/idempotency checks and integrity verification.
- [ ] Verify publisher against the actual GitHub API with a narrowly scoped token.
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

## External blocker

Bybit public endpoints returned HTTP 403 from three standard free GitHub-hosted runner allocations in Azure eastus2, eastus and westus3. The latter two responses explicitly stated that CloudFront blocked access based on country. No proxy, VPN, endpoint rotation, alternate exchange or paid runner has been used.

A user-controlled self-hosted runner on a Bybit-permitted network is the remaining plausible no-paid route. It has not been provisioned; live Bybit integration and all data-dependent phases remain blocked until it is.

## Release gate

No automated portfolio transition may run until complete universe/data coverage, causal calculations, execution timing, funding and fee accounting, independent NAV reconciliation, durable Git persistence and restore/recovery all pass integration tests.

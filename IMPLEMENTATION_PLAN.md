# Implementation Plan

## Current state
Repository initialized from an empty public repository. This is bootstrap phase only. No paper account, historical backtest, or forward performance is claimed.

## Phase 0 — Specification and safety
- [x] Verify exact repository, public visibility, default branch, empty contents and lack of branches before initializing.
- [x] Capture canonical v2.2 specification.
- [x] Validate API client mocks and mathematics through CI (Ruff clean; 32 tests passing on main).
- [ ] Keep all trading/account workflows disabled until acceptance gates pass.

## Phase 1 — Core mathematics and public API
- [x] Pure Python EMA and causal semi-cycle detection.
- [x] CPC, Trend, linear/RMS Noise, Q and B.
- [x] Wilder ATR.
- [x] Public Bybit server time, full instrument pagination, Kline pagination, funding windows and order-book parsing (mocked tests; live public access blocked by runner region).
- [x] Golden numerical tests and API mocks.

## Phase 2 — Ranking and data gates
- [ ] Full-universe ranking.
- [ ] Research versus execution eligibility.
- [ ] Data coverage and completeness gates.
- [ ] Daily universe/candle persistence.

## Phase 3 — Paper portfolio
- [ ] Deterministic pair selection and position state machine.
- [ ] Decimal sizing, contract precision and order-book VWAP.
- [ ] Sampled ATR stop monitoring with detection-time fills.
- [ ] Funding and cash/NAV reconciliation.

## Phase 4 — Durable state
- [ ] Immutable per-run event batches on state branch.
- [ ] Optimistic fast-forward persistence.
- [ ] SQLite projection and rebuild.
- [ ] Idempotency and recovery tests.

## Phase 5 — Historical replay
- [ ] Chronological, causal replay.
- [ ] Hourly stop monitor simulation with configured delay.
- [ ] Minute execution references.
- [ ] Funding and cost scenarios.
- [ ] Explicit survivorship disclosure.

## Phase 6 — Automation and reporting
- [ ] CI and public API preflight.
- [ ] Resumable full backfill.
- [ ] Daily and hourly workflows only after passing gates.
- [ ] STATUS, equity/drawdown, exports and monitoring coverage.

## External blocker
Bybit V5 public endpoints return CloudFront HTTP 403 from the tested standard GitHub-hosted runners in Azure eastus2, eastus and westus3. Full live data ingestion, historical backfill and paper trading remain blocked until a permitted user-controlled runner/network is configured and integration-tested.

## Current release gate
No automated portfolio transition may run until data completeness, causal calculations, execution timing, accounting reconciliation, persistence and recovery have passed integration tests.

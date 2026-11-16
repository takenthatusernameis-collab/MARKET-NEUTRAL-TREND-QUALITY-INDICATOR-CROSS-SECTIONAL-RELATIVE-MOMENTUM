# Prompt Refinement Log

## 2026-11-16 — v2.1 to v2.3

### Review pass 1 — mathematical source fidelity
- Re-opened the original Sepiashvili paper and inspected rendered pages containing the equations and figures.
- Confirmed CPC is the accumulated close-to-close difference from a fixed point inside a semi-cycle.
- Confirmed Trend is MA(CPC,m), linear noise is MA(abs(CPC-Trend),n), RMS noise is sqrt(MA((CPC-Trend)^2,n)), and n>m.
- Confirmed Q is Trend/Noise multiplied by a correction factor.
- Confirmed B uses absolute Trend in numerator and denominator.
- Confirmed 7/15 EMAs are illustrated in Figure 1, not established as optimal.
- Added explicit treatment of the pre-first-crossover segment as left-censored and ineligible.

### Review pass 2 — API contract and market-data correctness
- Rechecked Bybit instrument, Kline, funding, mark-price Kline, server time and order-book docs.
- Corrected linear order-book REST depth to a maximum of 1,000 levels; REST depth is distinct from WebSocket push-depth tiers.
- Kept instrument filtering on returned objects; only documented request filters are sent.
- Distinguished cursor pagination for instruments from timestamp pagination for Klines.
- Replaced any implication of funding cursor pagination with bounded time windows and subdivision when a 200-record page is full.
- Added timestamp freshness validation for order-book snapshots and disclosure that RPI orders are not visible.

### Review pass 3 — execution and portfolio accounting
- Rejected trigger-price fills for hourly sampled monitoring.
- Forward stop exits use current order-book conditions at actual detection time.
- Historical exits model scheduled detection delay and subsequent minute execution reference.
- Added explicit event ordering around funding settlements.
- Replaced mutable local SQLite as sole durable ledger with immutable per-run state-branch event batches and rebuildable SQLite projection.
- Added rule that no transition is durable until event batch persistence succeeds.

### Review pass 4 — deployment and scope
- Kept CI and public-API preflight separate from live portfolio automation.
- Gated scheduled portfolio workflows until data, execution, accounting and recovery tests pass.
- Preserved paper-only boundaries and separation of historical replay from forward account.

### Evidence status
- Documentation/API review: completed.
- Repository initialization: completed.
- Code implementation and tests: in progress.
- Public API integration: not yet run.
- Historical replay: not implemented.
- Forward paper verification: not started.

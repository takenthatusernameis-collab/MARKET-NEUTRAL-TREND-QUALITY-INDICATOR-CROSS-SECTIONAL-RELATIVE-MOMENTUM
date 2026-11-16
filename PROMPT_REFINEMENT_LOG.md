# Prompt Refinement Log

## 2026-11-16 — v2.1 to v2.4

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

### Review pass 5 — runner-region and external API access
- Ran the public Bybit API smoke test from GitHub Actions; the runner log identified Azure region eastus2 and the first request to /v5/market/time returned HTTP 403.
- Bybit V5 Integration Guidance states that US and mainland-China IPs are restricted and return 403; the error-code page independently lists US IP usage and IP rate protection as 403 causes.
- Standard GitHub-hosted runners do not expose a documented region selector. Free ubuntu-slim is being probed before concluding that all standard runner pools are blocked.
- No VPN, proxy, API-domain change or exchange fallback will be introduced.
- If no free standard runner is outside the restricted geography, only a user-controlled self-hosted runner on permitted hardware/network remains a possible no-paid path; it requires user setup and explicit authorization.

### Review pass 6 — repeated free runner-region tests
- Public API smoke run 43897098694 was provisioned in Azure eastus2 and received HTTP 403 from Bybit.
- Public API smoke run 43897936443 used ubuntu-slim in Azure eastus; CloudFront explicitly returned: "The Amazon CloudFront distribution is configured to block access from your country".
- Public API smoke run 43898832858 used ubuntu-slim in Azure westus3 and returned the same country-block response.
- These runs establish that the tested standard free GitHub runner allocations are US-based and cannot reach the required Bybit Global endpoint. They do not establish a general Bybit outage.
- Removed automatic push-triggered public API smoke runs to avoid repeatedly generating known regional failures; the smoke test remains manually dispatchable.
- The only plausible no-paid deployment route is a user-installed self-hosted runner using a permitted user-controlled network. No such runner was created or configured.

### Evidence status
- Documentation/API review: completed.
- Repository initialization: completed.
- Mathematical/data/API client modules: implemented; CI validation pending.
- First CI lint run: failed with 15 findings; fixes reduced the remaining lint issues to two; those two import-order findings were corrected.
- Full green CI: pending confirmation.
- Public API integration: attempted on three GitHub-hosted runner allocations; all blocked by CloudFront regional restriction.
- Historical replay: not implemented.
- Forward paper verification: not started.

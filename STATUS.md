# Market-Neutral Trend-Quality System — Status

**Report date:** 2026-11-16  
**Overall status:** BOOTSTRAPPING — external data access blocked  
**Trading mode:** Paper-only; no exchange orders or authenticated account access  
**Forward paper account:** Not initialized  
**Historical replay:** Not implemented  
**Verified portfolio NAV:** Not available  
**Historical / forward performance claims:** None

## Repository and deployment

- Public repository verified; default branch is `main`.
- Code and documentation are committed on `main`.
- Dedicated `state` branch exists and is reserved for immutable paper-account events.
- The state branch currently contains only its policy/README file; no account or event batch has been initialized.
- No live trading, Testnet, private API calls, exchange credentials or real capital are used.

## Research configuration

| Setting | Current value | Status |
|---|---:|---|
| Fast / slow EMA | 7 / 15 | Illustrated in source paper; not optimized |
| Trend smoothing m | 5 | Provisional |
| Noise smoothing n | 10 | Provisional; n>m |
| Noise method | Absolute deviation | Baseline; RMS option also implemented |
| Qualification | Strict |Q|>2 | Research threshold, not a validated trading edge |
| Correction factor | 1.0 | Provisional |
| ATR | Wilder 14 | Risk experiment |
| ATR multiplier | 3.0 | Provisional |
| Initial forward paper capital | 100 USDT | Not yet initialized |
| Target long / short gross allocation | 50% / 50% NAV | Dollar-neutral target, not beta-neutral |

## Implemented on main

| Component | Current evidence / limitation |
|---|---|
| Specification and research safeguards | v2.4 documented; historical and forward accounts kept separate |
| Indicator engine | EMA, causal semi-cycle/CPC, Trend, absolute and RMS Noise, Q, B and Wilder ATR; tested |
| Cross-sectional ranking | Signed-Q candidate ranking and distinct-symbol pair-selection primitives; not yet applied to a complete live universe |
| Bybit public client | Server time, paginated USDT linear perpetual instruments, backward Kline retrieval, funding history subdivision and public order-book parsing; mocked API tests pass |
| Decimal accounting | Position P&L, funding cashflow, exposure/NAV arithmetic, quantity flooring and sizing primitives; tested |
| Paper execution models | Order-book VWAP, partial-fill handling, fee and shortfall calculations, impact rejection, and historical next-minute slippage model; pure simulator only |
| Performance analytics | Daily net returns, total return, sample-gated CAGR/volatility/Sharpe/Sortino, drawdown/duration/recovery, Calmar and closed-trade statistics; tested but not yet connected to a portfolio equity history |
| Immutable event journal | Canonical JSON, SHA-256 event/batch chains, validation and local atomic batch writing; tested |
| Git state publisher | Append-only file publisher using normal fast-forward ref updates, idempotent duplicate handling and concurrency rejection; mocked GitHub API tests pass |
| SQLite projection | Transactional, idempotent event projection, chain ordering and integrity checks; tested locally |
| CI | Ruff and pytest run on Python 3.12 |

## Verified CI evidence

- Latest successful run: [GitHub Actions run 43903004353](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43903004353).
- Commit tested: `d7680c009904c4d0daa85a48fb61bc93ddb2dc15`.
- Ruff: all checks passed.
- Pytest: **62 passed in 0.21 seconds**.
- These tests cover deterministic calculations, mocked API response/pagination behavior, accounting, simulated execution, performance metrics, local event persistence, SQLite projection and mocked Git state publication. They do not establish successful live Bybit access or strategy profitability.

## External Bybit connectivity blocker

Three standard GitHub-hosted runner allocations were tested:

- `eastus2`: HTTP 403 from `/v5/market/time`.
- `eastus`: CloudFront response explicitly stated that access was blocked based on the runner's country.
- `westus3`: the same CloudFront country-block response.

The Bybit public API client is therefore implemented but has not passed live integration from the available free GitHub-hosted runner network. This is evidence of a country restriction on those runner paths, not evidence of a general Bybit outage. No proxy, VPN, API-host rotation, exchange substitution or paid runner has been used.

A user-controlled self-hosted runner on a network permitted by Bybit is the remaining plausible no-paid-infrastructure route. It has not been provisioned or authorized.

## Not yet implemented or operational

- Complete full-universe data collection and daily historical persistence.
- End-to-end completeness/freshness gates over every eligible instrument.
- Historical replay and survivorship-aware universe reconstruction.
- Fully integrated paper broker/state machine, stop/funding event sequencing and cash/NAV reconciliation.
- Real GitHub state-branch publication and automated restore/rebuild from that branch.
- Forward paper account initialization and daily/hourly scheduled runs.
- Generated equity curve, drawdown chart and human-readable portfolio risk report from actual persisted performance.

**Release decision:** Do not activate ranking-dependent portfolio workflows. No NAV, trade count, return, CAGR, Sharpe, drawdown or profitability statistic is claimed until the missing data, replay/portfolio integration and persistence gates are passed.

This report is evidence-based and must be regenerated from persisted account state once that system exists.

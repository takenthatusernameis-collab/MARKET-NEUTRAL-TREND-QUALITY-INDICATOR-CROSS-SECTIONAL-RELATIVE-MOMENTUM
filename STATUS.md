# Market-Neutral Trend-Quality System — Status

**Report date:** 2026-11-16  
**Overall status:** RED-TEAM NO-GO — Bybit live API blocked; no replacement exchange approved  
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
| Specification and research safeguards | Master directive v2.6; exchange-neutral research core and explicit candidate qualification gates |
| Indicator engine | EMA, causal semi-cycle/CPC, Trend, absolute and RMS Noise, Q, B and Wilder ATR; tested |
| Cross-sectional ranking | Signed-Q candidate ranking and distinct-symbol pair-selection primitives; not yet applied to a complete live universe |
| Bybit public client | Server time, paginated USDT linear perpetual instruments, backward Kline retrieval, funding history subdivision and public order-book parsing; mocked API tests pass |
| Decimal accounting | Position P&L, funding cashflow, exposure/NAV arithmetic, quantity flooring and sizing primitives; tested |
| Paper execution models | Order-book VWAP, partial-fill handling, fee and shortfall calculations, impact rejection, and historical next-minute slippage model; pure simulator only |
| Performance analytics | Daily net returns, total return, sample-gated CAGR/volatility/Sharpe/Sortino, drawdown/duration/recovery, Calmar and closed-trade statistics; tested but not yet connected to a portfolio equity history |
| Immutable event journal | Canonical JSON, SHA-256 event/batch chains, validation and local atomic batch writing; tested |
| Git state publisher | Remote event-chain tip, fork, orphan and duplicate-genesis validation implemented; mocked tests pass. Server-side branch protection remains absent, so state writes are blocked |
| SQLite projection | Transactional, idempotent event projection, chain ordering and integrity checks; tested locally |
| CI | Ruff and pytest run on Python 3.12 |

## Verified CI evidence

- Latest successful core-code run: [GitHub Actions run 43931058486](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43931058486).
- Commit tested: `a1c0e083893e5566fb2173b22c7afe81b196b4b9`.
- Ruff: all checks passed.
- Pytest: **67 passed in 0.25 seconds**.
- Coverage includes the drawdown-duration regressions and mocked remote state-chain continuity/fork tests; it does not establish a real GitHub state write or a live exchange integration.
- These tests cover deterministic calculations, mocked API response/pagination behavior, accounting, simulated execution, performance metrics, local event persistence, SQLite projection and mocked Git state publication. They do not establish successful live Bybit access or strategy profitability.

## External Bybit API and archive access

### Live V5 API
Six jobs were run on GitHub-hosted standard Linux runners using Ubuntu 22.04, 24.04 and 26.04. Each made one request to `https://api.bybit.com/v5/market/time`.

- Workflow run [43911753549](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43911753549): 6/6 failed with HTTP 403 and a CloudFront country-block response.
- Five jobs were assigned to Azure US regions. One job was assigned to AWS `us-west-2`; it also received HTTP 403.
- The standard Linux multi-cloud pool is automatic and provides no user-selectable region. This test therefore did not create a compliant route to the live API.

### Official historical trade archive
A separate read-only probe tested the official Bybit archive host from the same standard Linux runner pool.

- Workflow run [43912009008](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43912009008): 3/3 initial gzip/range probes passed.
- Follow-up [schema probe 43912788709](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43912788709): 3/3 passed. Each fetched bytes 0–8191, decompressed a prefix, parsed the CSV header and first trade row, and received HTTP 206.
- Verified header: `timestamp,symbol,side,size,price,tickDirection,trdMatchID,grossValue,homeNotional,foreignNotional,RPI`.
- The three follow-up jobs were assigned to Azure `southcentralus`, AWS `us-east-1`, and Azure `northcentralus`.
- The archive index shows daily BTCUSDT trade files beginning 2020-03-25 and extending through 2026-11-15. The tested file advertises 126,793,002 compressed bytes.

The archive gives a credible path for selective historical trade ingestion and OHLCV reconstruction. It is not integrated yet, and it is not a replacement for live V5 data: funding history, mark/index prices, fresh order books, current instrument rules, and intraday execution are not established by this archive. Historical symbol coverage and survivorship bias also require audit before universe-level claims.

**Release decision:** Live ranking-dependent portfolio workflows remain disabled. The historical archive path may be implemented for selective price research only after schema, integrity, coverage, storage and cost validation. No NAV, trade count, return, CAGR, Sharpe, drawdown or profitability statistic is claimed until historical or forward account data actually exists.

## Emergency red-team findings

- Report: [RED_TEAM_REPORT.md](RED_TEAM_REPORT.md).
- Crypto.com candidate: **NOT_READY**. The former probe incorrectly passed on instrument discovery alone; the repaired gate requires universe breadth, USDT compatibility, successful funding history, all required public data and verified jurisdiction/collateral.
- Follow-up Crypto.com readiness run [43930116624](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43930116624): all three Ubuntu jobs reported NOT_READY. Six USD-quoted contracts were found; funding-history API code 40004 was returned for both tested instrument-name formats.
- Performance analytics: longest underwater drawdown duration now tracks all drawdown episodes and restarts its clock after exact high-water recovery; regression tests pass.
- State publisher: new batches must extend the verified remote event-chain tip; forked, orphaned and second-genesis chains are rejected in code and mocked tests.
- Critical unresolved integrity gate: GitHub reports `state` as unprotected and repository rulesets are empty. No account/event writes are permitted until server-side branch protection and writer restrictions are configured.
- This is a public repository. Future state-branch files would be public and persistent; no confidential or personal account data may be stored there.
- No replacement exchange is approved. The Bybit adapter remains the only implemented provider client, and its live V5 API remains blocked on tested GitHub-hosted runner routes.

**Release decision:** no historical or forward performance claims, no paper-account initialization, no event-ledger writes and no exchange migration approval.

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

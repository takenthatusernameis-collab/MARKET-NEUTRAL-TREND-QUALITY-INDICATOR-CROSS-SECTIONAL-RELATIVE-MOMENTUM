# Market-Neutral Trend-Quality System — Status

**Overall status:** BOOTSTRAPPING  
**Trading mode:** Paper-only; no real orders or exchange account access  
**Forward paper account:** Not initialized  
**Historical replay:** Not implemented  
**Current verified portfolio NAV:** Not available  
**Claimed performance:** None

## Repository initialization

- Exact public repository verified.
- Default branch: `main`.
- Repository was empty before initialization.
- Project specification and first pure-Python modules have been committed.
- No live, Testnet or private exchange access exists.

## Research configuration

- EMA: 7/15 (source-paper illustration).
- Trend MA: m=5 (provisional).
- Noise MA: n=10 (provisional; n>m).
- Noise: absolute deviation baseline.
- Correction factor: 1.0 (provisional).
- Qualification: strict |Q|>2.
- ATR: Wilder 14, multiplier 3.0 (risk experiment).
- Paper capital: 100 USDT (not yet initialized).

## Implementation gates

| Component | State |
|---|---|
| Specification v2.3 | Documented |
| Pure indicator module | Implemented; tests pending CI |
| Cross-sectional ranking | Implemented; tests pending CI |
| Decimal accounting primitives | Implemented; tests pending CI |
| Public Bybit client | Implemented; integration not yet verified |
| Funding history retrieval | Implemented as bounded-window prototype; completeness audit pending |
| Immutable event batch | Implemented locally; Git state-branch publisher not implemented |
| Historical replay | Not implemented |
| Forward paper broker | Not implemented |
| Daily/hourly automation | Not enabled |
| Equity/drawdown series | Not available |

## Latest evidence

No historical performance or forward paper performance is claimed. API integration, tests, full historical coverage, event-batch publication and independent accounting reconciliation are still outstanding.

This file must be regenerated from verified persisted state once the reporting pipeline exists.

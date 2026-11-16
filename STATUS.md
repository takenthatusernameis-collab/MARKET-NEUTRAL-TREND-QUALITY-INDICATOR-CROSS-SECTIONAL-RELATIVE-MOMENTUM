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
| Specification v2.4 | Documented |
| Pure indicator module | Implemented; tests pending CI |
| Cross-sectional ranking | Implemented; tests pending CI |
| Decimal accounting primitives | Implemented; tests pending CI |
| Public Bybit client | Implemented; GitHub-hosted public API calls blocked by CloudFront country restriction (US runners) |
| Funding history retrieval | Implemented as bounded-window prototype; completeness audit pending |
| Immutable event batch | Implemented locally; Git state-branch publisher not implemented |
| Historical replay | Not implemented |
| Forward paper broker | Not implemented |
| Daily/hourly automation | Not enabled |
| Equity/drawdown series | Not available |

## Latest evidence

- Public API smoke run 43897098694: runner region Azure eastus2; Bybit /v5/market/time returned HTTP 403.
- Public API smoke run 43897936443: free ubuntu-slim runner in Azure eastus; CloudFront body explicitly reported that the distribution blocks access from the runner's country.
- Public API smoke run 43898832858: free ubuntu-slim runner in Azure westus3; same CloudFront country-block response.
- The API client is built and can report the bounded denial details. Public market-data integration from the tested standard GitHub-hosted runners is blocked.
- No proxy, VPN, endpoint rotation, alternative exchange or paid runner has been used.
- A user-controlled self-hosted runner on a permitted non-US/non-mainland-China network is the remaining plausible no-paid route, but it requires user setup and explicit authorization.
- CI linting previously reported 15 findings and was reduced to two import-order findings. Those were fixed in the latest source commits; a full green CI result is still pending verification.

No historical performance or forward paper performance is claimed. Full Bybit connectivity, historical coverage, event-batch Git state publication, replay, broker, scheduled paper account, and independent accounting reconciliation remain outstanding.

This file must be regenerated from verified persisted state once the reporting pipeline exists.

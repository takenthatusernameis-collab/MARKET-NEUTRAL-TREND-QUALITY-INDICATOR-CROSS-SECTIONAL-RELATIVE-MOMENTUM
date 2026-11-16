# Implementation Decisions

| ID | Decision | Rationale / evidence | Status |
|---|---|---|---|
| D-001 | Use the exact public repo and main branch | User specified target; repository verified empty | Accepted |
| D-002 | Keep execution paper-only | User's explicit safety boundary | Accepted |
| D-003 | Filter contractType/quoteCoin/settleCoin from instrument response | Current Bybit instrument endpoint request parameters do not include these filters; fields are in each response record | Accepted |
| D-004 | Instrument endpoint uses nextPageCursor; Kline does not | Different pagination contracts | Accepted |
| D-005 | EMA 7/15 is reference, not a universal optimum | Source Figure 1 illustrates the 7/15 crossover | Accepted |
| D-006 | Provisional m=5, n=10, c=1.0 | Paper does not prescribe a universal set; n must exceed m | Accepted |
| D-007 | Reject left-censored initial semi-cycle | Avoid arbitrary CPC initialization | Accepted |
| D-008 | Use absolute Trend in B formula | Source formula is abs(Trend)/(abs(Trend)+Noise)*100 | Accepted |
| D-009 | No trigger-price fill when sampled monitor detects a stop later | Avoid unrealistic execution and backdated fills | Accepted |
| D-010 | Linear REST order-book depth limit up to 1,000 | Current Bybit order-book endpoint documents linear/inverse limit 1–1,000; choose bounded depth after benchmarking | Accepted |
| D-011 | Funding history has no cursor; bounded time windows and subdivision required | Maximum 200 records; startTime-only errors | Accepted |
| D-012 | Immutable per-run event batches are durable source; SQLite is rebuildable projection | Recover from runner loss and prevent mutable ledger edits | Accepted |
| D-013 | No paper automation until core acceptance tests pass | Prevent partial data and incomplete accounting from affecting paper state | Accepted |
| D-014 | Historical and forward accounts are separate | Prevent backtest contamination of forward results | Accepted |
| D-015 | Historical daily replay must use delayed stop detection and later execution price | Match sampled monitoring limitations | Accepted |
| D-016 | Do not run Bybit market-data jobs from US/mainland-China source IPs | Official Bybit guidance says these source IPs return HTTP 403; observed free GitHub runner region was eastus2 | Blocking |
| D-017 | Do not use paid larger runners, proxies, or endpoint rotation to bypass a 403 | User's free-infrastructure and exact API-host constraints; preserve provider access restrictions | Accepted |
| D-018 | A self-hosted runner on user-controlled non-US/non-China hardware may be considered only after explicit setup authorization | Current standard GitHub-hosted runner does not provide a documented region selector | Pending user environment |
| D-019 | Test GitHub's automatic multi-cloud standard Linux pool before requiring any manual runner setup | 6/6 jobs across Ubuntu 22.04/24.04/26.04 received HTTP 403; one AWS `us-west-2` allocation was also blocked. The pool has no geographic selector. | Blocking for live API |
| D-020 | Permit official Bybit `public.bybit.com/trading` daily trade archives as a historical-only source | 3/3 hosted-runner probes fetched a valid gzip range (HTTP 206) from the 2026-11-15 BTCUSDT archive. Archive-derived candles are not native V5 Klines and do not provide funding, mark/index prices, L2 depth or current instrument metadata. | Accepted for selective historical research; integration pending |
| D-021 | Do not activate forward paper workflows using the daily trade archive as a substitute for the V5 API | Archive files are daily, do not provide fresh executable books or a verified funding feed, and cannot support the current hourly stop monitor. | Accepted |
| D-022 | Exchange replacement must pass full jurisdiction, USDT collateral, universe breadth, funding, public market-data, precision and integration gates | A public endpoint or one available perpetual is not proof the product is usable or sufficient for cross-sectional ranking. | Accepted |
| D-023 | Reject Crypto.com as the current replacement candidate | Three hosted-runner probes found six USD-quoted crypto perpetuals; funding-history returned API code 40004 for tested identifiers; min-universe and USDT quote gates fail; collateral/jurisdiction unverified. Official derivatives restrictions list Romania. | NOT_READY |
| D-024 | Maximum drawdown duration is the longest high-water-to-recovery underwater episode | The former implementation measured duration only for the deepest drawdown. New regression tests cover longer shallow episodes and exact high-water recovery reset. | Repaired; CI passed |
| D-025 | New remote state batches must extend the unique verified remote event-chain tip | Prior publisher checked only each batch's own hash and could append a second genesis or a fork. New publisher rebuilds and verifies the remote chain before append; mocked tests pass. | Repaired in code; actual remote write test pending |
| D-026 | No account event may be written while the state branch is unprotected | GitHub reports the state branch as unprotected and the repository has no rulesets; branch protection must be configured and verified first. | Blocking |
| D-027 | Event batches in this public repository are public and persistent | The repository is public; do not store personal, credential, confidential or private account data in the state branch. Redesign storage if private records are required. | Accepted disclosure |

| D-028 | Search 24/7 perpetuals across all documented asset classes with strict cross-margin eligibility | User's ordered provider request; avoid crypto-only assumptions and isolated-only contracts | In progress |
| D-029 | Test primary exchanges in this order: HTX, MEXC, Binance, WEEX, Bitget | Explicit user priority; if no candidate clears technical and Romania/EEA gates, use OKX EEA primary and Kraken EEA backup | Accepted |
| D-030 | HTX is a hard jurisdiction rejection for a Romania-based user while EU member states remain listed in HTX's restrictions | Public API reachability does not override the provider's terms; no geographic workaround | Blocking |
| D-031 | Treat provider-specific jurisdiction outcomes as VERIFIED, PROHIBITED or UNVERIFIED; UNVERIFIED is not approval | Absence from a prohibited list is not positive product authorization | Accepted |
| D-032 | Cross margin must be documented per retained contract and its sharing scope must be recorded | Account-wide, settlement-currency and product-type cross-margin are not interchangeable | Accepted |
| D-033 | Require complete metadata and official-spec reconciliation for every retained contract | Any tick/step/minimum/maximum/multiplier/currency mismatch excludes that instrument | Accepted |
| D-034 | For OKX EEA fallback, distinguish Futures-mode cross margin from multi-currency margin eligibility | Avoid assuming multi-currency mode is available to the 100 USDT research account | Accepted |
| D-035 | Kraken EEA remains backup with only 69 previously exact-matched contracts retained; 26 mismatches excluded | Earlier probe: 95 candidates, 69 exact official-spec matches and 26 mismatches; full 69-contract endpoint coverage still required | Accepted; validation pending |

| D-036 | The exchange need not offer every asset class; include every active cross-margin contract across the categories it actually offers | User clarification; asset class is an instrument attribute, not an exchange-level pass condition | Accepted |
| D-037 | Provider priority is Polymarket Perps → MEXC → Bitget; stop at the first public API technical pass | Explicit user order and immediate-first-pass instruction | Accepted |
| D-038 | Polymarket eligible research instruments require cross-margin capability; isolated-only contracts are excluded | Public Perps instrument metadata exposes isolated_only, close_only and permanent settlement | Accepted |
| D-039 | Five-minute snapshots; daily ranking/portfolio transition on first successful workflow after a new completed daily candle | User cadence; daily decision idempotency keyed by candle timestamp | Accepted |
| D-040 | Public market-data artifacts go to market-data branch; immutable paper events remain on state | Isolate public market series from the hash-chained paper account ledger | Accepted |
| D-041 | Bootstrap up to 365 available daily candles once per active instrument; subsequent runs fetch only missing candles | Reduce repeat API load; preserve new-listing and delisting history | Accepted |
| D-042 | Polymarket paper ledger is denominated in pUSD and is not silently converted to USDT | Use provider collateral unit and explicit currency attribution | Accepted |

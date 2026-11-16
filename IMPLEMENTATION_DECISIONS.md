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

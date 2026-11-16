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
- Full green CI: completed on main commit a99774baa59aa35795622abe7a7cfc8f456762c8; Ruff passed and pytest reported 32 passed in 0.06 seconds.
- Public API integration: attempted on three GitHub-hosted runner allocations; all blocked by CloudFront regional restriction (documented runs and response body).
- Historical replay: not implemented.
- Forward paper verification: not started.


## 2026-11-16 — v2.4 to v2.5: no-manual-input network recovery investigation

### Review pass 7 — test GitHub's new multi-cloud runner pool
- Rechecked GitHub's 2026-10-28 multi-cloud compute change: eligible standard 2-core and 4-core Linux jobs can be scheduled automatically on AWS as well as Azure, but users cannot choose cloud provider or geographic region.
- Added a bounded, no-credential probe matrix for Ubuntu 22.04, 24.04 and 26.04. Each job made exactly one request to the required `https://api.bybit.com/v5/market/time` endpoint.
- Run `43911753549`: all 6/6 jobs failed. Five jobs were assigned to Azure US regions; one was assigned to AWS `us-west-2`. Every request received HTTP 403 and the CloudFront response stated access was blocked based on country.
- Conclusion: the automatic multi-cloud pool is not a live API solution for the current repository. Do not repeat the same runner-label experiment indefinitely or switch to an unapproved endpoint.

### Review pass 8 — verify Bybit's official historical archive separately
- Inspected the official `public.bybit.com/trading/` directory and a BTCUSDT symbol directory. It contains dated compressed per-symbol trade files; the BTCUSDT index currently reaches 2026-11-15 and includes data beginning 2020-03-25.
- Bybit's public recent-trade documentation confirms archived historical trades can be downloaded from its website. The archive schema is timestamp, symbol, taker side, size, price, tick direction, trade-match ID, gross value, home notional and foreign notional; recent files may append RPI.
- Added a no-credential GitHub-hosted archive probe using a 2,048-byte HTTP Range request against the 2026-11-15 BTCUSDT file.
- Run `43912009008`: all 3/3 jobs passed, across Azure `centralus`, Azure `westus3` and AWS `us-west-2`. Each returned HTTP 206 and a valid gzip header. The server advertised a total file size of 126,793,002 bytes.
- This is a real, official historical price-data path from the current hosted runners. It can support selective historical OHLCV aggregation from trades, but it is not an alternative live feed and does not supply funding, mark/index history, L2 order-book depth or current instrument metadata.

### Revised release interpretation
- No fully automatic, free, no-manual-input route to Bybit's live V5 API was found. US geography is explicit in all 6 probes, including the AWS allocation.
- The official Bybit daily trade archive is accessible and may unblock selective historical price replay after coverage, integrity, data-volume and survivorship checks.
- A full universe historical backfill is not yet demonstrated; per-symbol daily archives can be large and historical universe membership cannot be inferred from present-day symbols alone.
- Forward paper operation, hourly stop monitoring and funding reconciliation remain disabled. Do not present archive-derived price-only results as full strategy validation.


### Review pass 9 — inspect the actual compressed CSV schema
- Extended the archive probe to request bytes 0–8191, decompress the gzip prefix, parse the CSV header and first data row, and require the expected trade columns.
- Run `43912788709`: 3/3 jobs passed. All read HTTP 206 ranges, decompressed 27,914 bytes from 8,192 compressed bytes, and found the columns `timestamp,symbol,side,size,price,tickDirection,trdMatchID,grossValue,homeNotional,foreignNotional,RPI`.
- The first sample row parsed as a BTCUSDT sell trade with timestamp, quantity and price values, confirming the archive payload schema on the actual official file rather than relying only on a third-party description.
- This remains a prefix/schema test; it does not prove full-file CRC validation, complete-day integrity, chronological ordering, or the coverage of other symbols and dates. The downloader must validate the complete gzip stream before trusting a file.


## 2026-11-16 — v2.5 to v2.6: emergency red-team and provider qualification

### Review pass 10 — exchange readiness false positive
- Reviewed the Crypto.com derivative diagnostic run `43924834692`, which had returned success whenever the instrument endpoint found any perpetual instruments.
- Identified six USD-quoted crypto perpetuals only; the funding-history API call returned HTTP 400 and the old workflow still passed.
- Replaced the weak pass condition with a strict readiness gate requiring at least 20 eligible crypto perpetuals, successful nonempty book/ticker/candlestick/funding data, USDT quote compatibility and explicit account-collateral/jurisdiction verification.
- Follow-up run `43930116624`: all three Ubuntu runner jobs returned NOT_READY. The observed universe was six symbols, quote currency USD; funding-history API code 40004 was returned for both tested index-name formats; minimum universe, funding-data and USDT-quote gates failed; collateral/jurisdiction remained UNVERIFIED.
- Official Crypto.com derivatives restrictions list Romania. This candidate is rejected for the current use case and is not a production adapter.
- Updated the exchange-migration directive: provider substitution is permitted only through explicit evaluation and all qualification gates, not by endpoint reachability alone.

### Review pass 11 — performance analytics red-team
- Found that `maximum_drawdown_duration_days` previously measured the duration of the deepest drawdown rather than the longest period spent below a high-water mark.
- Reworked the calculation to track all high-watermark-to-recovery episodes, including the currently open episode.
- Added regression tests where a shallower drawdown lasts longer than the deepest drawdown and where NAV exactly returns to the prior high before a later drawdown begins.
- CI run `43930818436`: Ruff passed, 64 tests passed.
- Confirmed the following state-chain changes separately with tests: run `43931058486` passed Ruff and 67 tests.

### Review pass 12 — remote event-chain integrity
- Found that the original GitHub state publisher validated the new batch's internal SHA hashes but did not anchor `previous_batch_hash` to the actual state branch's latest batch.
- Added remote tree/blob reconstruction and full-chain verification before append. The publisher now fails closed on multiple genesis batches, forks, cycles, orphan batches, disconnected chains, bad event paths, invalid blobs and truncated trees. A submitted new batch must extend the unique remote chain tip.
- Added mocked publisher tests for valid sequential continuation, an unanchored second genesis and a pre-existing fork.
- This is mocked API verification only. No real event batch has been written to GitHub state.

### Review pass 13 — server-side state protection and privacy
- Checked branches and rulesets: GitHub reports `main` and `state` as unprotected; repository rulesets endpoint returns an empty list.
- Branch-protection detail GET was not accessible to the connected integration, and available GitHub actions did not expose a branch-protection mutation. No server-side protection was claimed or applied.
- Because the repository is public, future event files on `state` would also be public and persistent. The branch currently contains only policy documentation; no account or event batches exist.
- Server-side state-branch protection and a decision on public-vs-private event storage remain release blockers.

### Final red-team evidence
- Successful core CI after code repairs: run `43931058486`, commit `a1c0e083893e5566fb2173b22c7afe81b196b4b9`, Ruff passed, 67 passed.
- Latest performance/persistence fixes are covered by mocked/unit tests; no real exchange integration, real state-branch publishing, portfolio restore, historical replay or forward paper operation is verified.
- Overall release state remains RED-TEAM NO-GO. No replacement exchange is approved.

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


## 2026-11-16 — v2.6 to v2.7: ordered 24/7 cross-margin multi-asset provider search

### Prompt refinement pass 14 — clarify the product target
- Reframed the replacement target from crypto-only USDT perpetuals to all explicitly documented, active 24/7 perpetual asset classes offered by each candidate.
- Added separate checks for contract type, continuous trading/settlement interruptions, underlying-market closures, class metadata, funding intervals and full contract lifecycle.
- Cross margin must be available for every retained symbol. Document whether risk is shared account-wide, by settlement currency or only within a product/contract type. Do not confuse ordinary cross margin with multi-asset collateral.
- Required all pages and a minimum of 50 active eligible perpetuals overall, with each offered class enumerated and all unclassified symbols disclosed.
- Strengthened per-contract requirements: tick, step, min quantity/notional, max quantity/position, contract multiplier, quote/settlement/margin/P&L currency, precision, risk tiers, status and funding.

### Prompt refinement pass 15 — enforce provider order and fallback
- Primary order is exactly HTX → MEXC → Binance → WEEX → Bitget.
- HTX is rejected at the Romanian jurisdiction gate while the current EU-wide exclusion remains in its terms; do not bypass it.
- If the primary five do not yield a technically and legally suitable product, evaluate OKX EEA as primary and preserve Kraken EEA as backup.
- OKX cross-margin route must account for its margin mode and account-level restrictions; do not assume multi-currency mode eligibility for a 100 USDT paper account.
- Kraken backup retains only contracts matching official EEA specifications. Current evidence is 69 exact matches and 26 exclusions out of 95 candidates; full data coverage of the 69 is outstanding.

### Prompt refinement pass 16 — evidence separation and safety
- Added a pure parser module and mocked unit tests for exchange-specific cross/perpetual criteria.
- Added a read-only ordered GitHub Actions probe. It uses no credentials, private endpoints, account creation, orders, proxy, VPN or endpoint rotation.
- Reports separate technical endpoint checks from legal/account eligibility. Romania not appearing in a provider's prohibited list is not treated as proof of permission.
- The first CI attempts found lint issues in the new probe/test code; repairs were committed, and the newer CI/probe results are being rechecked. No exchange is approved until the results are green and independently inspected.
- Defined the full-universe acceptance test as the next major gate: complete instrument coverage plus ticker, L2 book, completed candle, funding, mark/index and precision validation for every retained symbol and every available class, not a BTC-only sample.


## 2026-11-16 — v2.7 to v2.8: correct asset-class interpretation and Perps provider order

### Prompt refinement pass 17 — interpret asset classes as an instrument-universe property
- The user clarified that a venue need not offer every asset class.
- Include every active cross-margin instrument on the selected venue, independent of its category; categories are preserved for reporting and later attribution.
- Isolated-only instruments are excluded. Close-only instruments are not selected for new positions. Retired/settled contracts remain in historical data but receive no routine market-data updates.
- Unknown/future provider category strings are preserved and not silently dropped.

### Prompt refinement pass 18 — provider order and first-pass stop
- Exact order: Polymarket Perps → MEXC → Bitget.
- Stop provider probing at the first public API that clears instrument completeness, cross-margin, bulk ticker, fees, daily candle, book and funding checks.
- A technical API pass permits paper-research implementation only; it is not a trading authorization or account-level legal clearance.
- Polymarket is first because its official Perps SDK exposes unauthenticated public instrument/ticker/book/fees/klines/funding methods and a non-expiring cross-margin perpetual product. Published country restrictions do not list Romania; do not infer individual account entitlement.

### Prompt refinement pass 19 — operational cadence and durable data layout
- Five-minute workflow cadence captures every cross-margin instrument's latest ticker/mark/index/funding snapshot.
- The first successful five-minute workflow after a new completed UTC daily candle runs the daily indicator/ranking/portfolio transition. Daily decisions are keyed by completed candle timestamp and must be idempotent.
- Bootstrap each eligible instrument once with up to 365 days of available daily history; all later API candle requests begin after the stored last candle.
- New listings get a resumable one-time backfill. Close-only assets stop new entries. Permanently settled/delisted contracts are archived and stop routine updates.
- Public market data goes to the new `market-data` branch; immutable paper-account events remain on `state`. Five-minute snapshots are gzip-compressed into hourly partitions; daily OHLCV uses date partitions.

### Evidence and implementation status
- Added the Polymarket Perps public API adapter and unit tests.
- Added ordered Polymarket/MEXC/Bitget qualification script and GitHub Actions workflow.
- Added `MarketDataStore` with incremental candle persistence, lifecycle manifest, hourly snapshot append and snapshot retention.
- The first priority workflow did not reach the public API because the shared lint/test gate found fallback-probe and adapter formatting issues. These are being repaired; no provider pass is claimed until the workflow runs through its API step.


## 2026-11-17 — Six refinement passes: Bitget curiosity and MEXC implementation

### Pass 20 — provider-status honesty and priority preservation
- Separated public endpoint reachability, API-contract completeness, account/jurisdiction eligibility and end-to-end paper readiness.
- Added an independent Bitget diagnostic for curiosity only. It was not allowed to change the established provider priority or the MEXC selection.

### Pass 21 — collateral and per-instrument universe
- Confirmed the MEXC account research universe is active cross-margin linear USDT quote + USDT settlement perpetuals.
- Kept other settlement currencies in metadata but outside the single-currency USDT account.
- Preserved unknown asset categories rather than excluding them.

### Pass 22 — contract math and research/execution separation
- Required contractSize conversion for contract-count depth and Kline volume.
- Used volUnit, minVol, maxVol, priceUnit and fee fields for sizing/fills.
- Kept valid research candidates in the Q universe even when turnover or order book makes them non-executable.

### Pass 23 — durable portfolio-account boundary
- Reconfirmed the state branch is not protected and the repository rulesets endpoint is empty.
- Portfolio writer must remain disabled; market-data collection and ranking do not initialize a financial account.
- Required real branch-protection checks, restricted writers, remote chain anchoring, publisher test and full recovery before any account writes.

### Pass 24 — public API and UTC daily-bar verification
- Added a read-only MEXC hosted-runner preflight and executed real public calls.
- Confirmed 1,061 active cross-margin USDT perps, full selected ticker coverage and sampled book/candle/funding access across all reported categories.
- Added an explicit daily boundary check. The sampled Day1 bars opened at 00:00 UTC; the daily decision uses completed UTC bars only.

### Pass 25 — incremental operation and reporting
- Added provider-specific manifest isolation, daily candle/funding partitions, five-minute snapshots, bootstrap progress and incremental cursors.
- Added MEXC contract-aware Q rankings, simulated fills, USDT account accounting primitives, funding and ATR stop functions, and sample-gated performance metrics.
- Added the five-minute MEXC market-data/ranking workflow with account writing explicitly disabled.
- Initial workflow run completed a 150-contract bootstrap batch (911 remained) but the data-branch commit failed because data/ was ignored. After force-add was applied, runs 43976810498 and 43977234937 both completed and committed data successfully. The second report advanced to 300 bootstrapped contracts (761 remained) and 108,118 stored candle rows. An additional report regression ensures human-readable MEXC tickers are shown instead of internal instrument keys.

### Result and disclosure
- MEXC remains selected. Bitget's 886-instrument curiosity screen is recorded but does not replace it.
- All-settlement MEXC preflight run 43977889004 passed: 1,143/1,143 research tickers, sampled order-book/candle/funding calls across all discovered categories, with 1,061 USDT/USDT execution-account contracts.
- MEXC five-minute cycle run 43977854892 committed 231,692 candle rows and full ticker snapshots, with 750 instruments bootstrapped and 393 pending; market-data persistence is verified, but full history coverage remains incomplete.
- The forward paper account is uninitialized; no NAV, fills, return or performance claim exists. Romania-specific derivatives account eligibility remains unverified.


### Pass 26 — honor the full cross-margin universe across settlement types
- Reconciled the all-cross-margin-instrument research requirement with the single-currency USDT paper ledger.
- Widened MEXC instrument discovery and daily history/Q ranking to all 1,143 active cross-margin linear perpetuals, across settlement types and categories.
- Preserved a narrower 1,061-contract USDT quote+settlement execution universe for the current 100 USDT paper account.
- Added research-only status for non-USDT contracts until quote/collateral conversion, inverse contract P&L and fee/funding settlement are independently normalized.
- Renamed turnover fields to quote-currency semantics to avoid treating USDC/USD/BTC quote turnover as USDT.


### Pass 27 — one active $50 account, unmistakable manual workflow and readable mobile equity chart (2026-11-18)

- Audited the immutable `state` event branch and the main-branch account selectors. Confirmed the active account is `mexc-usdt-forward-50usdt-v3` with strategy `trend-quality-daily-cross-sectional-v3-50usdt` and initial capital 50 USDT.
- Preserved earlier $1 and $10 generations as archived event history; never delete, rewrite, import or pool their historical fills, equity or balances into the v3 account.
- Designated the MEXC workflow as the single active portfolio-state writer. Give it an explicit $50/manual/auto workflow title, unmistakable manual run label, branch `main` instruction and required confirmation input. Make the separate MEXC preflight visibly read-only; remove the retired Polymarket state-writer workflow entry point.
- Reconcile README, status, runbook, operating model, state metadata and a dedicated account card so old account sizes cannot be mistaken for active settings.
- Red-team the equity SVG against the mobile screenshot. Remove duplicated midpoint/last labels on two-point curves; render dates and exact UTC times on separate lines; anchor endpoints away from each other; provide vertical space between x-axis labels and observation-count footer; suppress crowded intermediate labels without dropping NAV observations; retain start/latest NAV and initial-capital reference.
- Add regression tests for one-point, two-point and dense/clustered timestamp histories. Keep all equity data, accounting calculations and immutable event timestamps unchanged.
- Require CI, merged `main`, active-workflow YAML verification and a freshly rebuilt report/SVG before calling the task complete. Paper-only boundary remains mandatory: no live exchange orders, private endpoints, credentials or wallet actions.

**Consolidated implementation prompt:**  
“On `main`, audit and retain exactly one active MEXC forward-paper account generation: `mexc-usdt-forward-50usdt-v3` with 50 USDT initial capital. Keep former $1/$10 generations immutable and excluded from the current account/report; never rewrite history or merge balances. Make the MEXC $50 paper cycle the only active portfolio-state writer, make its manual Actions trigger visually unmistakable and explicitly confirmed on branch `main`, and label all read-only diagnostics as such. Remove retired state-writing workflow entry points. Reconcile account/run instructions throughout the repository. Fix the independent report's equity SVG so UTC date, exact time, NAV and supporting annotations remain distinct and readable on narrow mobile displays, including one-point, two-point and dense histories. Add regression coverage, run CI, merge to `main`, then verify the current state branch, active account report and newly generated chart. Do not touch exchange credentials, private endpoints, wallet state or live orders; this is paper simulation only.”

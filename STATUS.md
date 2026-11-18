# Market-Neutral Trend-Quality System — Status

**Report date:** 2026-11-18  
**Selected provider:** MEXC Futures public API — prior HTML HTTP 403 was returned while the client still used the Futures REST host that MEXC discontinued on 2026-01-19; integration is being moved to the current official host and endpoint, with post-fix hosted preflight validation still outstanding  
**Research universe:** active cross-margin USDT-settled linear perpetuals  
**Forward paper account:** ACTIVE GENERATION — 50 USDT seed; v3 VSTOCK_USDT long + BILL_USDT short simulated; independently restored from verified event chain  
**Historical replay:** not implemented  
**Latest verified portfolio NAV:** 49.66302776 USDT at 2026-11-18 05:37:15 UTC (two simulated positions open)  
**Performance claims:** none; sample gates remain unmet

## Provider selection and evidence

The required search order was Polymarket Perps → MEXC → Bitget. The first provider to pass the configured public-data screen was MEXC. Bitget was checked separately for curiosity only; it did not change selection.

| Provider | Evidence | Current result |
|---|---|---|
| MEXC Futures | 1,152 instruments discovered; 1,143 cross-margin perpetuals across settlements; 1,061 active USDT quote+settlement execution/account contracts; sampled market data and ticker coverage verified | SELECTED — TECHNICAL PUBLIC-DATA PASS |
| Polymarket Perps | 90 active cross-margin instruments discovered; missing fee coverage for four categories and sampled order-book reads failed | NOT READY |
| Bitget | 886 active cross-margin USDT perpetuals; instrument, precision and sampled ticker/book/candle/funding checks passed | CURIOSITY-ONLY PASS; NOT SELECTED |

Verified all-settlement MEXC public API preflight: [run 43977889004](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43977889004).

The MEXC response provided 1,161 bulk ticker rows; all 1,143 active cross-margin research contracts had a matching ticker. Settlement groups were 1,061 USDT/USDT, 41 USDC/USDC, 31 USD1/USD1 and 10 USD-quoted coin-settled contracts. Sampled ticker, order-book, daily-candle and funding-history calls passed across commodity, crypto, equity, FX and unclassified categories. The sampled daily candles began at 00:00 UTC. This verifies API shapes and representative category coverage, not every individual book or every funding record on the entire universe.

Romanian derivatives-product/account eligibility has not been independently confirmed. Public API reachability is not an authorization determination.

## Research configuration

| Setting | Value | Status |
|---|---:|---|
| Fast / slow EMA | 7 / 15 | Illustrated in source paper; not optimized |
| Trend smoothing m | 5 | Provisional |
| Noise smoothing n | 10 | Provisional; n > m |
| Noise method | Absolute deviation | Baseline; RMS option also implemented |
| Qualification | Strict |Q| > 2 | Research filter, not a validated trading edge |
| Correction factor | 1.0 | Provisional |
| ATR | Wilder 14 | Risk experiment |
| ATR multiplier | 3.0 | Provisional |
| Initial paper capital | 50 USDT | Active v3 generation initialized 2026-11-18; one simulated long/short pair open |
| Long / short allocation | 50% / 50% NAV | Dollar-neutral target, not beta-neutral |

## Implemented on main

| Component | Evidence / status |
|---|---|
| Exchange-neutral Q indicator | EMA, causal semi-cycle/CPC, Trend, absolute and RMS Noise, Q, B and Wilder ATR modules retained |
| MEXC public adapter | Instrument details, cross-margin filter, bulk tickers, public depth, daily Klines and funding history; adapter unit tests added |
| Research/execution universe normalization | All 1,143 active cross-margin perps retained for Q research; 1,061 USDT quote+settlement contracts are eligible for the single-currency portfolio; non-USDT instruments remain research-only pending conversion model |
| Contract-unit handling | contractSize, volUnit, minVol, maxVol and priceUnit normalized; book and Kline contract volume converted to base units; quote turnover retained separately |
| Research/execution split | Q ranker produces independent long and short research lists; liquidity/turnover and order-book impact are execution gates |
| Incremental data storage | Provider-isolated manifest, date-partitioned daily candles, compressed five-minute ticker snapshots, funding partitions, new listing lifecycle and delisting/settlement tracking |
| MEXC paper execution | Book VWAP simulation, taker fee, shortfall and stale-book rejection; no order endpoint |
| MEXC portfolio accounting | USDT cash/NAV, realized and unrealized P&L, fee/funding ledger, ATR stops, daily equity and sample-gated performance report functions; unit tests added |
| State journal | Immutable hash-chained event journal and GitHub state publisher retained; runtime gate strengthened |
| MEXC read-only preflight | Successful hosted-runner integration workflow and UTC daily-bar boundary sample |
| Five-minute cycle | New MEXC market-data/ranking workflow configured; first cycle completed a 150-instrument bootstrap batch, but its first data-branch commit failed because the branch ignored the data directory. Workflow was changed to force-add public data; a subsequent successful branch commit is still required before treating persistence as operational. |

Historical CI checkpoint (superseded): [run 43976943722](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43976943722) predates the subsequent MEXC paper-account activation, partial-rebalance work and later regression tests. Current final CI evidence is recorded in the latest dated section at the bottom of this file.

## Market-data bootstrap and cadence

- MEXC provider key is stored separately from any older Polymarket market-data manifest; the store refuses cross-provider history mixing.
- Initial backfill target: up to 365 days of available daily candles for each active eligible instrument.
- Batches are bounded to 150 instruments by default; the first observed cycle completed 150 and left 911 pending.
- Subsequent API requests begin after the last successfully stored/completed daily bar; newly listed instruments receive their own resumable backfill.
- Incomplete or insufficient history is explicitly marked; an instrument with insufficient history remains ineligible for Q ranking until it has enough completed bars.
- Routine snapshots are scheduled every five minutes. The daily Q decision uses only the latest completed UTC daily bar, and the decision key is its timestamp.
- A scheduled GitHub workflow is best-effort and is not a continuous monitoring service.

The first MEXC data/ranking cycle failed to commit because Git ignored data/. The workflow was corrected to force-add the dedicated public data directory. Successful commits were then verified in runs [43976810498](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43976810498) and [43977234937](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43977234937). After widening research to every settlement type, run [43977854892](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43977854892) completed successfully and pushed the new report/data snapshot. It shows 231,692 daily-candle rows, full 1,143/1,143 ticker coverage, zero missing latest completed bars, zero reported API failures, 750 instruments bootstrapped and 393 pending. The ranking is recalculated across whatever instruments have enough valid completed history; it is therefore preliminary until all eligible histories bootstrap. It now prints human-readable tickers and separates all-settlement research lists from the USDT-only executable lists. The full-history gate remains false.

## Historical checkpoint — pre-activation paper-state gate (superseded)

The following checkpoint records an earlier repository state before the paper publisher was enabled and the $10 account was initialized. It is historical, not the current operating state; see the later dated sections below.

**The forward paper account remains uninitialized.**

The GitHub state branch is reported as unprotected; the branch-protection endpoint could not be verified through the connected integration and the repository rulesets endpoint returned an empty list. As a result:

- MEXC workflow sets PAPER_STATE_WRITE_ENABLED=false.
- No paper positions are opened, closed or maintained.
- No financial event batches are written to the state branch.
- No verified portfolio NAV, equity curve, trade count, return, CAGR, Sharpe, Sortino, drawdown or profitability metric is available.
- The cycle must not treat a rebuildable market-data projection as the durable financial ledger.

Before enabling paper-account transitions, configure and verify server-side state-branch protection, prohibit force-push/deletion, restrict writers, and pass a real GitHub event-publisher and recovery test. This repository is public; all branch data are public and permanent.

## Not yet complete

- Complete the 365-day MEXC candle/snapshot bootstrap across all 1,143 cross-margin contracts and audit data gaps, quote-currency semantics and recovery. The first 750 instruments are marked bootstrapped; 393 remain.
- Independent full-universe data quality, missing/gap and funding-history completeness audit.
- Full real-universe Q ranking verified against independent calculations and persisted daily report.
- End-to-end MEXC paper portfolio transition and real GitHub durable event write/replay test.
- State-branch server-side protection and restricted writers.
- Separate chronological historical replay with point-in-time universe reconstruction and survivorship audit.
- Sampled-stop delay/recovery analysis using MEXC detection-time public books.
- Forward account initialization after every data, execution, accounting and persistence gate passes.
- Equity curve, drawdown chart and human-readable risk report from actual persisted NAV observations.
- Independent audit of account state and performance.

## Safety and disclosure

No live trading, Testnet, private account endpoints, exchange credentials, wallet, proxy/VPN or paid infrastructure were used. No exchange orders were submitted. The paper modules only simulate hypothetical fills. MEXC account access in Romania remains unverified. No historical or forward profitability claim is made.


## 2026-11-17 — Authoritative cadence and risk implementation update

This section supersedes older cadence, bootstrap and CI statements above.

- **One five-minute cron, two modes:** the first invocation observing a newly completed UTC daily candle performs the full research/data/ranking and daily portfolio-decision workflow. Other invocations run portfolio-snapshot-only mode; they do not refresh the research universe, recalculate Q, run ordinary ATR decisions or rebalance.
- The heavy workflow is keyed by a persistent daily-candle watermark and runs one bounded resumable bootstrap batch per new completed daily candle. Routine snapshots do not repeatedly perform bootstrap work.
- **Leverage and sizing:** 50% of NAV is allocated as margin to each leg at 2× leverage. Each leg targets 1× NAV notional; combined target gross exposure is 2× NAV. Contract maximum leverage and lot rules remain binding.
- **Emergency stop:** a 25% combined portfolio drawdown from the observed UTC-day NAV peak triggers full-book simulated flattening. The stop includes realized/unrealized P&L, fees and confirmed funding through combined NAV. It is not a lifetime MDD cap. A pending flatten is persisted and retried on later five-minute runs; a missing mark cannot suppress an already-latched emergency exit.
- Daily return uses the previous UTC day's last stored NAV when available, preventing a delayed first daily invocation from resetting the baseline to an already-damaged mark. Five-minute drawdown remains sampled and can exceed the nominal threshold due to scheduling and execution delay.

**Verified execution evidence:**
- Full daily-close MEXC public-data/ranking workflow [43984343892](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984343892): 1,143 active cross-margin perpetuals, 273,160 daily-candle rows, 93 instruments completed in the final bootstrap batch, zero remaining bootstrap instruments, zero missing tickers, zero missing latest completed bars, zero API failures, and history coverage gate passed.
- Follow-up monitoring workflow [43984739626](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984739626): PORTFOLIO_SNAPSHOT_ONLY, daily_decision_due=false, q_rankings_recalculated=false, no missing position marks, zero orders.
- CI [43985254705](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43985254705): Ruff passed; 142 tests passed. The latest scheduled snapshot-only run [43985254683](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43985254683) also completed successfully on the final code revision.

**Forward paper account remains NOT INITIALIZED.** PAPER_STATE_WRITE_ENABLED remains false, so no positions or financial events have been created and no portfolio NAV, equity curve or performance result is verified. State-branch protection, restricted writers and the real publisher/recovery gate are still required before any paper-account state transitions. Live trading, private endpoints, credentials and exchange orders remain prohibited.



## Historical 1 USDT activation readiness and protection blocker (superseded after later activation)

**Configured forward seed:** 1 USDT.  
**Forward paper account:** NOT INITIALIZED.  
**State branch:** exists, but UNPROTECTED.  
**Financial ledger writes:** disabled; no event files exist on the state branch.

### Code and test work completed

- Portfolio and MEXC cycle defaults are both 1 USDT.
- At 50% NAV margin per leg and 2× leverage, target notional is approximately 1 USDT per leg; the simulator must remain flat if MEXC minimum-size constraints prevent a valid pair.
- The workflow's PAPER_STATE_WRITE_ENABLED repository variable defaults to false.
- The workflow reads a separate STATE_PROTECTION_TOKEN secret solely to inspect the detailed branch-protection endpoint (Administration: read). The regular GITHUB_TOKEN remains the event publisher credential (Contents: write).
- Runtime protection validation requires branch protection, administrator enforcement, force-push prohibition, deletion prohibition, linear history and nonempty writer restrictions.
- The event publisher verifies exact canonical event contents and the complete remote hash chain after a new write and on idempotent replay.
- Account activation is two-stage: first append a non-financial recovery probe; then require a fresh scheduled checkout to verify it before the 1 USDT paper-account initialization event can be created.
- Tests cover 1 USDT initial cash, 1 USDT target leg notional, protection-token separation, force-push/linear-history fail-closed checks, recovery-probe recognition and publisher read-back/replay validation.

**Final CI:** [run 43986748619](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43986748619) — Ruff passed; 150 tests passed.

**Latest scheduled MEXC run:** [run 43986724889](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43986724889) — success; snapshot-only mode; PAPER_STATE_WRITE_ENABLED=false; paper_simulation_enabled=false; zero orders.

### Remaining administrator-only activation

A current live read of the repository confirms:

- GET state branch summary: protected=false.
- Branch-protection summary: protection.enabled=false.
- Repository rulesets: empty.
- State branch event tree: no events/ files.
- Detailed GET branch-protection endpoint: 403 from the connected GitHub App integration because it lacks Administration access.

The connected GitHub integration can commit source files and normal Git refs, but does not expose a branch-protection/ruleset mutation action or the Administration permission needed to configure this repository's protected branch. This is an integration permission boundary, not a code/test failure. Do not bypass it with an unprotected financial write.

The one remaining external action is to apply the settings and add the least-privilege protection-read secret described in [STATE_PROTECTION_SETUP.md](STATE_PROTECTION_SETUP.md). Keep PAPER_STATE_WRITE_ENABLED absent or false until that is complete. The first enabled run must publish only the non-financial recovery probe. A later fresh checkout must verify it. Only then can a distinct 1 USDT account-initialization event be appended and subsequently restored.

No financial event, position, NAV, equity or performance observation has been created. No live orders, private MEXC endpoints, exchange credentials or wallet access were used.



## 2026-11-17 — Unprotected single-writer paper mode implemented

The repository no longer requires state-branch protection, a repository ruleset, Administration permission or `STATE_PROTECTION_TOKEN`. The state branch is intentionally unprotected to avoid blocking paper-evidence collection on repository administration.

- MEXC paper-state writing defaults to enabled in the five-minute workflow; setting the repository Actions variable `PAPER_STATE_WRITE_ENABLED=false` pauses all portfolio-state writes.
- MEXC and the retired manual Polymarket diagnostic share the same repository-wide `paper-state-branch-single-writer` concurrency group with `cancel-in-progress: false`; no two workflow publishers can run simultaneously.
- The publisher remains application-level append-only: full remote hash-chain checks, unique genesis/linear topology, duplicate-ID/idempotency rejection, fast-forward-only writes, exact canonical remote read-back and verification on idempotent replay remain mandatory.
- Local restoration now follows `previous_batch_hash` links rather than `created_at_ms`, avoiding ordering errors from different exchange server clocks.
- The two-stage recovery handshake remains: first write only a non-financial recovery probe; later fresh checkout must verify it before the 1 USDT financial account-initialization event.
- **At this code revision the account is still NOT INITIALIZED.** No initialization or performance evidence is claimed until the actual workflow probe, fresh-checkout recovery and financial event are observed. The 1 USDT account may legitimately remain flat if MEXC minimum-size and cost constraints prevent a valid pair.
- **Residual risk accepted:** because the branch is unprotected, a repository user with write/admin access can rewrite or delete history outside the publisher. Chain validation detects malformed state when observed but cannot prevent privileged manual tampering.
- No live orders, private MEXC endpoints, credentials or wallet access are used.

CI and the first workflow recovery-probe run must be checked after this commit before the account is reported as initialized.


## 2026-11-17 — Initial 1 USDT generation initialized, then archived

**Final state: INITIALIZED, 1 USDT cash/NAV, flat, paper-only.**

Verified end-to-end sequence on the live GitHub repository:

1. **Recovery probe** — MEXC run [43989363042](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43989363042) created `events/2026/11/state-probe-1794875970712.json`. The publisher verified exact remote read-back and the complete chain. The probe records no financial state, no initialized account and zero orders.
2. **Fresh-checkout recovery and initialization** — MEXC run [43990948665](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43990948665) checked out the state branch afresh, verified the probe, then appended `paper_account_initialized` at `events/2026/11/account-init-1794876688471.json`. Starting cash and initial capital are exactly 1 USDT; no historical trades/equity were imported.
3. **Independent account restore** — follow-up MEXC run [43991147324](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43991147324) reported `paper_account_restored_from_state_branch=true` and `paper_account_recovery_status=RESTORED_FROM_VERIFIED_EVENT_CHAIN`. It reconstructed cash=1 USDT and NAV=1 USDT, then appended `events/2026/11/snapshot-1794876766509.json`.

**Verified ledger chain:** probe hash `ad7ff8e50fcf462f8851e81512cb6d487debad9cfc3cb289d5bad2cade7256fc` → initialization hash `6334d2b5c3c98f893c2895bb7e975ac61e5453ea089c22a2584353f52b1cbd9f` → snapshot hash `87476f8ffe9c951305323e078aa6b6a9f6c8821df05657b2486f4563e2c1bbb0`. Both parent-hash links were verified.

### Initial operating statistics

- Cash: **1.000000 USDT**
- NAV: **1.000000 USDT**
- Positions: **0**; gross/net exposure: **0**
- Closed trades: **0**; fees: **0**; confirmed funding: **0**
- Orders submitted: **0**
- History coverage at initialization: passed across 1,143 active cross-margin perps, including 1,061 USDT-eligible instruments; 273,160 daily-candle rows; zero missing tickers, missing latest bars or reported API failures.
- Entry decision: `FLAT_NO_EXECUTABLE_PAIR`; no valid pair met all execution constraints with a 1 USDT account. It stayed flat rather than forcing undersized simulated trades.
- Performance metrics: **not yet meaningful**. Only one daily equity observation exists; CAGR, Sharpe and other sample-dependent statistics remain unavailable. Actual forward evidence starts at the initialization timestamp, not from historical backfill.

**Latest CI:** [run 43991147484](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43991147484) — Ruff passed; 153 tests passed.

The state branch remains intentionally unprotected. The accepted residual risk is privileged manual history rewrite/deletion outside the application publisher. The single-writer workflow lock, hash-chain validation, fast-forward-only updates, exact read-back and fresh-checkout restore checks remain enabled. No live orders, private MEXC endpoints, exchange credentials or wallet access were used.



## 2026-11-17 — Archived $10 generation, manual launcher and five-minute entry retries

**Historical record only.** This $10 generation was subsequently superseded by the $50 v3 account initialized on 2026-11-18; it remains in the immutable event chain as archived history.

### Manual start cue

<badge>Paper only</badge> **[▶ START PAPER SIMULATION — MEXC (PAPER ONLY)](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml)**

On the GitHub Actions page, choose branch `main`, select **Run workflow**, then select **Run workflow** again to start the same paper cycle immediately. The workflow is also scheduled every five minutes. Manual dispatch does not change the strategy, create a separate account or submit exchange orders.

### New account generation

- Active account ID: `mexc-usdt-forward-10usdt-v2`
- Strategy generation: `trend-quality-daily-cross-sectional-v2-10usdt`
- Initial capital and starting cash: **10.000000 USDT**
- Recovery probe: run [43993530651](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43993530651), which published the new generation's non-financial probe.
- Fresh-checkout recovery and initialization: run [43993542045](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43993542045). It verified the preceding probe and appended `events/2026/11/account-init-1794877891864.json`, batch hash `45974be192090b0a88017bd2009076e20e4b471319b4bba1fbd6cb1ad138e9dd`.
- **First simulated pair opened:** long `VSTOCK_USDT` (0.02 base units at 426.35) and short `BILL_USDT` (2,500 base units at 0.003974). Both fills are simulated from public MEXC order-book depth.
- Reported starting cash after entry fee: **9.99829460 USDT**. Initial marked NAV: **9.99529460 USDT**. Entry fee: **0.00170540 USDT**. Two open positions. No live orders, credentials, private endpoints or wallet access.
- The run reported full data coverage across 1,143 cross-margin perpetuals, 1,061 USDT-execution-eligible instruments, 273,160 daily-candle rows, zero missing tickers, zero missing latest bars and zero reported API failures.
- The initialization report first showed `paper_account_recovery_status=INITIALIZED_THIS_CYCLE`. Follow-up run [43993684041](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43993684041) checked out the state branch independently, reported `paper_account_recovery_status=RESTORED_FROM_VERIFIED_EVENT_CHAIN`, and appended snapshot `events/2026/11/snapshot-1794877922711.json` (batch hash `71400ed314111845d556825d1ef09c1cef034110caa55b81d21a91ba746f2eb6`). The restored report showed cash 9.99829460 USDT, NAV 9.99139460 USDT, unrealized P&L -0.00690000 USDT, and two open simulated positions.

### Is $1 generally below MEXC minimum order size?

A live public-data diagnostic evaluated the minimum contract quantity/step times current mid-price for all **1,061** USDT-eligible instruments:

| Measure | Result |
|---|---:|
| Median minimum order notional | 0.2878 USDT |
| 75th percentile | 1.0955 USDT |
| 90th percentile | 2.82715 USDT |
| Contracts whose minimum notional is above 1 USDT | 283 / 1,061 |
| Contracts whose minimum notional is above 10 USDT | 16 / 1,061 |
| Contracts meeting minimum quantity and lot step at 1 USDT per leg | 778 / 1,061 |
| Contracts meeting minimum quantity and lot step at 10 USDT per leg | 1,045 / 1,061 |

**Interpretation:** minimum notional is not above 1 USDT for most of the universe. The $10 change was a conservative expansion after the $1 account's actual daily decision returned `FLAT_NO_EXECUTABLE_PAIR`; the live diagnostic shows broader contract coverage at $10, and the first pair has now opened. It does not prove that $1 could never execute. Turnover, book depth, taker fees, impact and the need for a valid long/short combination remain separate gates.

The old `mexc-usdt-forward` $1 account is retained as an archived generation in the append-only `state` event history. It was not deleted or merged into the $10 ledger. New $10 events use a distinct account and strategy ID.

### Entry retry behaviour

- One completed UTC daily candle creates the Q ranking and a frozen executable shortlist.
- If the initial attempt does not produce a pair but both executable sides exist, the shortlist is retried on five-minute invocations, checking at most five candidate pairs per retry with fresh public tickers and order books.
- Retries do not recalculate Q or reuse stale execution books. The pending shortlist expires at the next completed daily candle.
- Once a pair is open, routine five-minute cycles monitor equity/risk and do not initiate a new ordinary rebalance.
- If no valid executable long/short shortlist exists at the daily decision, there is no pending retry; the system waits for the next completed daily candle.

### Evidence and limitations

The first $10 initialization cycle reports one daily equity observation, so CAGR, Sharpe, Sortino, meaningful drawdown history and profitability remain unavailable. The initial unrealized mark and fees are not performance evidence. The state branch remains intentionally unprotected; publisher-side chain checks and single-writer coordination remain active, but a repository writer/admin can still rewrite or delete history outside the publisher.


**Final implementation validation:** CI [run 43994339602](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43994339602) on commit `b5311cf83dd30fd6d9ef8c9308ded54e5ce2b458` — Ruff passed; **155 tests passed**. This includes the regression test for serialization and restoration of the frozen daily entry shortlist used by five-minute retries.

**Scheduling evidence:** the workflow YAML contains both `schedule: "*/5 * * * *"` and `workflow_dispatch`. Recent Actions run history through 2026-11-17 01:17 UTC showed successful push-triggered runs, including the independent $10 account restore, but no schedule-originated run. The cron is configured; automatic scheduled execution has not yet been independently observed. The manual launcher is available for immediate starts.



## 2026-11-17 — Daily equal-notional rebalance and fresh risk window

The daily-close strategy decision now rebalances the selected long and short legs toward equal USDT notional even when the same contracts remain selected.

- Target per leg remains 50% NAV margin at 2× leverage, or approximately 1× NAV notional per leg.
- A retained contract is resized using only `target_quantity - current_quantity`. Increases add the required quantity; reductions close only the required slice, realize P&L on that slice, allocate entry fees proportionally and leave the remainder open with its original entry identity.
- When one contract is replaced, only that contract is closed and replaced. The other retained position remains open and is independently resized.
- If the adjustment is below MEXC's minimum lot or current public depth cannot fill it within the impact limit, no forced trade occurs; the residual imbalance and reason remain reportable.
- After the pre-rebalance equity/risk check passes, every successful daily pair decision starts a fresh 25% combined drawdown window from post-rebalance NAV. The separate daily-return metric remains anchored to UTC-day opening NAV, even after a delayed rebalance. A latched emergency stop or pending flatten cannot be reset. Five-minute pending-entry retries also reset the drawdown window when they first open the pair.

The event report now includes `rebalance_actions` and `portfolio_daily_risk_reset`. Partial increases/decreases update weighted-average entry price, entry fees, margin, realized P&L, partial realized net P&L and funding watermarks.

### Verification

- Integration regression: an existing 0.8-unit long and 1.2-unit short are moved to 1.0 each by simulating only +0.2 long and -0.2 short. Both original position timestamps remain intact, and no full close event is generated.
- Accounting tests cover partial realized P&L, entry-fee allocation, margin updates, a new drawdown reference after rebalance, and refusal to reset an emergency latch.
- Final CI [run 43995767758](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43995767758) on commit `6b3fd06022be1f590e04686e853a268c37357e8d`: Ruff passed; **159 tests passed**, including preservation of the UTC daily-return reference after a drawdown-window reset.
- The latest observed MEXC run during implementation remained `PORTFOLIO_SNAPSHOT_ONLY`; the already-open VSTOCK_USDT / BILL_USDT pair was marked and not modified by a daily decision in that snapshot. The new rebalance behaviour is therefore code- and test-verified, but has not yet been exercised by a subsequent completed daily-candle decision in the forward account.

No live orders, private endpoints, credentials or wallet access were introduced.

 
## 2026-11-17 — Standalone paper performance ledger (historical implementation milestone)

The root-level [PAPER_PERFORMANCE_REPORT.md](PAPER_PERFORMANCE_REPORT.md) is the independent human-readable performance file.

- Each MEXC workflow run refreshes the state-branch checkout, verifies the full hash-chained event ledger, rebuilds the report and publishes it to main. A bounded fast-forward retry handles concurrent main updates; the report commit skips redundant CI and does not retrigger the MEXC workflow.
- It contains the full mark-to-market equity curve, daily equity marks, drawdown by risk session and lifetime/cross-session maximum drawdown, sample-gated Sortino/Sharpe/CAGR/Calmar and other statistics, cash/NAV/P&L/fees/funding/exposure, open positions, and timestamped opening, increase, reduction, close, funding and risk-reset records.
- Session drawdown is kept separate from lifetime drawdown; resetting the operational risk window cannot erase historical MDD.
- Trade history uses explicit fill and funding payloads. Persisted position changes are a backstop and are labelled when exact execution details were not stored.
- At the time of this implementation milestone the report selected the $10 generation. The current report selects only `mexc-usdt-forward-50usdt-v3`; both earlier $1 and $10 generations are excluded. Invalid batches, broken links, duplicate IDs and forks stop publication rather than generating a misleading report.
- Sortino and other daily statistics remain unavailable until their existing sample thresholds are satisfied.

The report does not imply any live trading. The strategy uses public data and simulated fills only.


## 2026-11-18 — Active $50 USDT account, single-writer workflow and readable equity chart

**Current operating state. This section supersedes the prior $1 and $10 activation summaries.**

- **Only active account:** `mexc-usdt-forward-50usdt-v3`
- **Strategy generation:** `trend-quality-daily-cross-sectional-v3-50usdt`
- **Initial capital / starting cash:** 50.00000000 USDT. The older `mexc-usdt-forward` ($1) and `mexc-usdt-forward-10usdt-v2` ($10) generations remain immutable archived records; they are not restored or reported by the active cycle.
- **Initialization:** MEXC workflow run [44236973900](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44236973900), after the verified recovery-probe/fresh-checkout handshake. No historical trades or equity were imported.
- **Latest successful persisted snapshot:** MEXC run [44245469767](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44245469767), timestamp 2026-11-18 05:37:15.935 UTC. NAV 49.66302776 USDT; two simulated legs remain open.
- **Last observed pair:** long VSTOCK_USDT, 0.11 base units; short BILL_USDT, 11,500 base units. At the latest snapshot, long and short notionals were 45.822700 and 45.770000 USDT. Dollar imbalance was 0.052700 USDT, or 0.1061% of NAV—inside the 0.5% monitoring limit. The workflow reduced the short by 100 base units in a paper-only partial rebalance.
- **Latest run's evidence is a mark-to-market snapshot, not a return-history claim.** There are only two persisted intraday NAV observations and one daily return observation. Sharpe, Sortino, CAGR, Calmar and daily-equity drawdown statistics remain unavailable under their existing sample gates. The current NAV change is not evidence of strategy profitability.
- **Active workflow on main:** [▶ RUN THIS — ACTIVE MEXC $50 USDT PAPER ONLY — MANUAL / AUTO](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml). Manual dispatch requires the `I_CONFIRM_ACTIVE_50_USDT_PAPER_ONLY` choice and run titles show `MANUAL`; the scheduled cadence is best-effort every five minutes. Post-merge run [44243034540](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44243034540) encountered MEXC HTTP 403 and submitted zero orders. Its later report-build/publish steps succeeded from the existing verified state chain; it did not create a new portfolio snapshot. The read-only MEXC public preflight is manual-only; run #14 was a separate manual/queued diagnostic that returned HTTP 403 for /api/v1/contract/ping with an HTML Access Denied response. It is no longer automatically triggered by code pushes. The retired Polymarket state-writing workflow was removed.
- **Equity chart:** UTC dates and exact times now render on separate lines; the first and latest observations are anchored to opposite chart edges, duplicate two-point midpoint labels are removed, and crowded intermediate labels are suppressed. All underlying event timestamps and NAV values remain unchanged.
- **Paper-only boundary:** no live orders, private exchange endpoints, API credentials or wallet access. The state branch remains unprotected; application-level hash-chain verification and fast-forward-only writes do not prevent a privileged repository writer from manually rewriting branch history.


## 2026-11-18 — MEXC 403 diagnosis and phone chart typography

- Post-merge MEXC paper workflow run [44243034540](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44243034540) returned HTTP 403 during its public-data cycle. It submitted zero orders, used no private endpoints or credentials, and created no new financial snapshot. The downstream report and SVG generation and publication steps succeeded from the existing verified event chain.
- The concurrent read-only MEXC preflight [44243034106](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44243034106) passed its samples: 1,146 active cross-margin perpetuals, 1,064 USDT-eligible contracts, full bulk ticker coverage, and sampled books, daily candles and funding history in five categories. This does not establish that every full-history request in the paper bootstrap was available.
- The prior adapter error omitted the failing endpoint path and response details, so the exact cause of run #76 is **not established**. This follow-on adds endpoint-aware 403 diagnostics, stops a bootstrap batch at the first access denial, slows the shared public client to five requests per second, and serializes the read-only preflight behind the active paper writer. No circumvention or alternative network route is introduced.
- Equity SVG labels were separated in the prior merge; this follow-on raises title, NAV annotation, UTC date/time, tick and footer font sizes for phone-sized rendering, with regression tests guarding the minimum sizes.
- The latest persisted portfolio evidence remains the $50 v3 snapshot from run [44239954487](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44239954487): NAV 50.13572776 USDT, two simulated positions, 0.256% NAV dollar imbalance. Run #76 did not update this mark. No meaningful daily performance statistics are available yet.


## 2026-11-18 — Latest forward snapshot and manual-only diagnostics

- Paper workflow run [44245469767](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44245469767) completed successfully in FIVE_MINUTE_PORTFOLIO_SNAPSHOT mode. It restored the active v3 account, reduced BILL_USDT short quantity by 100 base units (11,600 to 11,500) using a simulated partial fill, and persisted the new state snapshot at events/2026/11/snapshot-1794980235935.json. No live orders were sent.
- Latest NAV: **49.66302776 USDT** on 50 USDT initial capital. Latest dollar exposures: long 45.822700 USDT; short 45.770000 USDT; imbalance 0.052700 USDT = 0.1061% of NAV, inside the 0.5% ceiling. Daily return versus the UTC day opening reference is -0.6739%; drawdown from the observed daily peak is -0.9428%. The 25% emergency stop was not triggered.
- The report and enlarged phone-readable SVG were successfully rebuilt and published after run #77. Daily-equity history still has one daily return observation, so Sharpe, Sortino, CAGR and other sample-gated metrics remain unavailable.
- Read-only preflight run [44245469914](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44245469914) ran after the paper workflow due to the shared non-cancelling concurrency group, then received HTTP 403 for the public /api/v1/contract/ping endpoint. The response was HTML Access Denied, not a structured MEXC JSON error. The cause of the upstream denial is not established.
- To avoid repeat, push-triggered diagnostic traffic, the read-only MEXC preflight is now manual-dispatch only. The active paper workflow remains separate and continues using the public-data fail-closed behavior.


## 2026-11-18 — MEXC Futures REST migration and request-safety update

- MEXC's official [Futures API domain announcement](https://www.mexc.co/announcements/article/futures-api-access-domain-update-17827791532974) states that the former `https://contract.mexc.com` REST host was discontinued on 2026-01-19 and the current host is `https://api.mexc.com`.
- The current [MEXC contract-information endpoint documentation](https://www.mexc.io/api-docs/futures/market-endpoints/get-contract-info) specifies `GET /api/v1/contract/detail/country`. The adapter and preflight now use this endpoint and report the actual configured host.
- Global client pacing has been reduced from one request per 0.20 seconds to one request per 1.5 seconds (about 0.67 requests/second). HTTP 429 and API code 510 trigger at least 60 seconds of exponential cooldown; transient 5xx/network errors use exponential backoff and server `Retry-After` is respected.
- HTTP 403 remains non-retryable and immediately fail-closed. No proxy, VPN, alternate IP, private endpoint, credential or access-control circumvention is used.
- The active portfolio workflow is still the single $50 USDT paper-account writer. The preflight remains a separate manual-only, read-only diagnostic. A post-migration hosted preflight has not yet completed; do not claim live API access or a full daily-cycle pass until that evidence exists.

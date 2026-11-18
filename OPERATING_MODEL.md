# MEXC Paper Workflow — Authoritative Operating Model

**Effective date:** 2026-11-18  
**Provider:** MEXC Futures public market data  
**Account mode:** USDT-settled paper simulation only  
**Active account generation:** 50 USDT seed — `mexc-usdt-forward-50usdt-v3` / `trend-quality-daily-cross-sectional-v3-50usdt`  
**Scheduler:** GitHub Actions every five minutes (*/5 * * * *) plus a daily-close backup at 00:01 UTC (1 0 * * *)  
**Manual launcher:** [▶ RUN THIS — ACTIVE MEXC $50 USDT PAPER ONLY — MANUAL / AUTO](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml)

This document is the authoritative operating contract for the MEXC forward-paper workflow. It supersedes older instructions that imply a five-minute strategy-decision loop, hourly strategy decisions, or independent per-leg 25% drawdown stops.

## 1. One scheduler, two modes

Both scheduled triggers invoke the same workflow and active account. It determines its mode from the latest fully completed MEXC UTC daily candle and the persisted daily-workflow watermark; the daily-close trigger is a backup attempt, not a separate strategy cycle.

### Daily-close research and decision mode

The first workflow invocation that observes a newly completed UTC daily candle runs the heavy path once for that candle:

1. Restore and verify the persisted paper event chain and market-data manifest.
2. Fetch current MEXC contract metadata, eligible cross-margin universe and bulk tickers.
3. Refresh instrument lifecycle and perform one bounded, resumable candle-bootstrap/incremental-history batch.
4. Validate completed daily candles and data coverage.
5. Recalculate exchange-neutral Q/B/ATR features and cross-sectional research/execution rankings.
6. If the paper-account state-write gate is open and the data gate passes, process due funding, assess the portfolio-level emergency limit, evaluate daily ATR/trailing exits, then select the daily pair and rebalance both retained legs toward equal USDT notional using only the required quantity deltas. Close/reopen only the contract(s) actually replaced.
7. Persist the daily decision/risk event and human-readable research/performance reports.

The daily workload is keyed to the completed UTC daily candle timestamp, not the cron start minute. A given daily candle must not cause duplicate heavy work or duplicate portfolio decisions. The bootstrap batch is deliberately bounded; incomplete bootstrap is resumed on a later daily-close cycle, not by repeating the heavy workload every five minutes.

### Five-minute portfolio-snapshot mode

Every invocation that does not observe a new daily candle performs a monitoring-only path:

- Fetch a bulk public ticker snapshot only when an initialized paper account has open positions.
- Mark existing positions to MEXC mark prices and calculate combined NAV.
- Record the equity curve, lifetime ROI, daily return, daily drawdown, peak NAV, notional exposure and performance statistics available at the current sample size.
- Apply confirmed funding settlements exactly once as accounting events; unresolved settlement marks remain unresolved and are not replaced with zero.
- Check the combined-book emergency daily drawdown threshold.
- Retry a previously triggered but incomplete emergency flatten.
- Publish the portfolio valuation/risk event when the paper-state persistence gate is open.

This mode does not refresh the full research universe, backfill candles, recalculate Q rankings, or run ordinary ATR/trailing-stop decisions. It has one narrowly scoped exception when the portfolio is flat: if the latest daily decision persisted a valid executable long and short shortlist but its first simulated pair attempt failed, the five-minute invocation may retry that frozen shortlist. It fetches fresh public tickers and order books, checks at most five candidate pairs per invocation, and persists the attempt/result. It does not recalculate Q, does not create a new signal, and does not reuse an old order book. The pending shortlist expires when a new completed UTC daily candle is observed. If the original daily decision had no executable long/short shortlist at all, no retry is scheduled; the system waits for the next daily decision. Once a pair is open, snapshot mode returns to monitoring-only. A monitoring run may also close positions only to complete an already-triggered emergency flatten.

### Manual on-demand start

Open the [GitHub Actions paper workflow](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml), select the workflow named **▶ RUN THIS — ACTIVE MEXC $50 USDT PAPER ONLY — MANUAL / AUTO**, choose branch `main`, then select **Run workflow** and confirm the required choice `I_CONFIRM_ACTIVE_50_USDT_PAPER_ONLY`. The run title begins **▶ MANUAL PAPER RUN — MEXC $50 USDT**. This invokes the same existing $50 v3 account cycle immediately; it does not create a new account or bypass the data, ranking, execution, persistence or risk gates. The YAML retains the automatic five-minute schedule and adds a dedicated 00:01 UTC daily-close attempt. Both are best-effort rather than a continuous service. The separate MEXC public preflight is read-only and serialized behind the paper writer. It runs automatically on `main` when `.github/workflows/mexc-public-preflight.yml`, `scripts/mexc_public_preflight.py`, `src/trend_quality/mexc_api.py` or `pyproject.toml` changes; manual dispatch remains available. It has no recurring schedule, so ordinary five-minute paper monitoring does not trigger a second data poll. The retired Polymarket state-writer workflow has been removed.

### Public API pacing and access-denial handling

MEXC's [Futures API domain announcement](https://www.mexc.com/announcements/article/futures-api-access-domain-update-17827791532974) says the former `https://contract.mexc.com` host was discontinued on 2026-01-19 and identifies `https://api.mexc.com` as the current host. MEXC's [official API page](https://www.mexc.com/mexc-api) identifies `https://api.mexc.com/api/v1/contract/detail` as the default API-supported Futures-pairs endpoint. The adapter therefore uses the supported host and the default `/api/v1/contract/detail` route for broad research discovery; it does not use the country-detail route to define the Q universe. Request pacing remains **1.5 seconds minimum between requests** (about 0.67 requests/second), a 7.5× lower request rate than the previous 0.20-second setting. HTTP 429 / API code 510 triggers at least 60 seconds of exponential cooldown; transient 5xx/network failures use exponential backoff, and `Retry-After` is respected when present.

The read-only MEXC preflight shares the paper cycle's non-cancelling `paper-state-branch-single-writer` concurrency group. It runs automatically on `main` when its workflow, preflight script, MEXC public adapter or dependency manifest changes; manual dispatch remains available. It has no recurring schedule and must not issue a concurrent burst of public requests while the portfolio workflow is backfilling history or marking positions.

An HTTP 403 is treated as an access denial, not retried or bypassed. The prior November 18, 2026 403 was returned while the client was still using MEXC's retired `contract.mexc.com` host; that obsolete-domain defect is now corrected, although a successful post-fix hosted preflight is still required to prove end-to-end access. Diagnostics record the endpoint path without query parameters, response server/content type/retry-after headers when available, and a short response-body/provider-message excerpt. A 403 during bootstrap stops the batch immediately; do not continue issuing requests to the denied endpoint. The workflow must remain paper-only and must not use proxies, VPNs, alternate IPs, private endpoints, credentials or other circumvention methods.

A successful read-only preflight proves only the tested endpoint samples at the reported time. It does not prove that the complete default-endpoint research universe or the full 365-day candle bootstrap is accessible. Keep sampled preflight success, full-cycle success, market-data coverage, state persistence and portfolio performance as separate evidence categories. Do not infer the cause of a 403 (rate restriction, edge/WAF policy, contract-specific restriction or other denial) until endpoint-level diagnostics support it.


## 2. Portfolio construction and leverage

The active forward account is denominated entirely in USDT. The only active generation ID is `mexc-usdt-forward-50usdt-v3`; its strategy generation is `trend-quality-daily-cross-sectional-v3-50usdt`. The prior 1 USDT `mexc-usdt-forward` and 10 USDT `mexc-usdt-forward-10usdt-v2` accounts remain archived, separate, immutable events in the append-only state history and are not merged into the active account.

| Parameter | Setting |
|---|---:|
| Initial paper capital | 50 USDT |
| Long margin allocation | 50% of NAV |
| Short margin allocation | 50% of NAV |
| Default leverage | 2× per leg |
| Long target notional | 1× NAV |
| Short target notional | 1× NAV |
| Combined target gross notional | 2× NAV |

Sizing is calculated as NAV × margin allocation × leverage ÷ reference price, then rounded down to the exchange contract increment. Instrument maximum leverage and minimum/maximum contract constraints remain binding. The two positions are one combined portfolio; margin allocations do not mean that notional is capped at 50% of NAV.

Only USDT-quoted and USDT-settled contracts can enter this homogeneous paper account. Other settlement types may remain in research rankings, but must not be mixed into USDT NAV without a separately validated conversion and settlement model.


### Daily pair maintenance and equal-notional rebalance

Every eligible completed daily candle is a fresh sizing checkpoint, even when the selected long and short contracts are unchanged.

- The two legs target equal USDT notional: each target is `NAV × 50% margin allocation × 2× leverage` (approximately 1× current NAV per leg). This is dollar-notional neutrality, not beta neutrality.
- If the selected instrument and side are already held, calculate `target_quantity − current_quantity` and simulate only that signed delta. A positive delta adds quantity; a negative delta reduces quantity and realizes P&L only on the reduced slice. Entry fees, weighted-average entry price, margin, partial realized P&L and funding watermarks are updated proportionally.
- Do not close and reopen an unchanged contract just to rebalance it. A retained leg keeps its original position identity/entry timestamp; only the changed quantity is added or removed.
- If the long or short contract is replaced, close only the replaced position and open its replacement. The other retained leg stays open and is independently resized toward its target.
- MEXC lot increments, minimum quantity, current book depth and impact limits remain binding. When the required adjustment is below the venue's minimum executable quantity, or the current book cannot fill it, leave that leg unchanged and report the constraint. Never round the delta up or force a full close merely to make the exposure numbers look equal. Any remaining imbalance caused by venue precision/minimums must remain visible in the report.
- The workflow reports the action and signed quantity delta for every leg under `rebalance_actions`, alongside the simulated fills and costs.

After a successful daily pair decision/rebalance—including a decision that retains the same pair with no executable quantity change—the 25% drawdown window is reset to the post-rebalance NAV and peak NAV, with the reset timestamp recorded. This treats the maintained pair as a fresh daily trade window. The separate UTC-day return baseline is preserved, so a delayed decision/rebalance cannot erase the day's earlier performance. The pre-rebalance equity/risk snapshot is evaluated **before** this reset. If that check has already triggered the emergency stop, or an emergency flatten remains pending, the daily rebalance is blocked and the reset helper refuses to clear the latch. A later five-minute retry that opens a previously pending daily signal likewise starts the new risk window at its post-fill NAV.


## 3. Combined portfolio emergency stop

The emergency limit is evaluated on combined account equity, not independently on the long and short legs.

NAV includes cash, realized P&L, unrealized P&L, entry/exit fees and confirmed funding cashflows. The implementation therefore naturally catches cases where both legs lose less than 25% individually but their combined losses cause the portfolio threshold to be breached.

The risk state is UTC-dated and keeps the reporting and protection references separate:

- **Daily return:** current portfolio NAV relative to the previous UTC day's last successful NAV snapshot. If there is no prior-day snapshot, the first observation of the UTC day is used as the initial baseline. This calendar-day return reference is not changed by an intraday rebalance.
- **Daily drawdown stop:** current NAV relative to the highest observed NAV since the latest drawdown-window start. At UTC rollover the window starts from the prior-day close (or first observation if no prior snapshot exists). After a successful daily pair rebalance it restarts from post-rebalance NAV, while the calendar-day return reference remains unchanged.

When daily drawdown reaches or exceeds a 25% loss (NAV / daily peak NAV - 1 <= -0.25):

1. Latch the emergency-stop state in the persisted portfolio.
2. Cancel/disable any ordinary entry or rebalance decision for that cycle.
3. Simulate closing **both legs** from current public order-book depth, charging modeled exit fees and slippage.
4. Persist the liquidation reason, prices/costs, attempts and whether the book is confirmed flat.
5. Keep a durable emergency-liquidation-pending latch if the simulated close cannot be completed. Retry on every subsequent five-minute invocation, even across UTC rollover and even if a mark quote is missing.
6. Do not reopen until the book is flat and a later eligible daily-close decision cycle is reached.

The emergency limit is a daily risk control, **not a lifetime maximum-drawdown cap**. Lifetime MDD may exceed 25%. The daily latch resets at the next UTC day, but an uncompleted liquidation latch survives until the book is flat.

## 4. Detection and execution limitations

Five-minute monitoring is sampled, not continuous or exchange-native. A price excursion may occur and reverse between observations, and a delayed GitHub Actions run may detect a breach late. Actual simulated liquidation can therefore occur beyond the nominal 25% threshold. Reports must preserve the observed trigger NAV, detection timestamp, closing book timestamp, simulated fill prices, fees, slippage and delay where available. Never represent this simulated protection as an exchange-side stop order.

For a missing/stale position mark, do not fabricate a NAV observation or pretend that the risk threshold was evaluated. Report the missing symbol(s). If emergency liquidation was already triggered or remains pending, still attempt to close the book using current public depth; a missing mark must not suppress a latched emergency exit.

## 5. Idempotency, recovery and data gates

- One completed daily candle produces at most one heavy research cycle and one ordinary portfolio decision attempt.
- Routine five-minute snapshots use unique timestamps and are idempotent for an exact repeated timestamp.
- Event journal hashes and idempotency keys must remain verified; never fork, rewrite or force-push the state chain.
- Daily history bootstrap is bounded and resumable. It must not cause the five-minute snapshot path to become a repeated research path.
- Missing/incomplete market data blocks ranking-dependent new positions. Never invent candles, prices, funding marks or fills.
- Missed cron periods are disclosed. The system must not fabricate historical fills using current order books or claim that late decisions occurred at the intended historical close.

## 6. Persistence and non-live boundary

The `state` branch is intentionally unprotected in this paper-only mode; no repository-administrator setup or `STATE_PROTECTION_TOKEN` is required. The MEXC workflow defaults `PAPER_STATE_WRITE_ENABLED` to true, while the repository Actions variable can be set to the literal string `false` as an emergency write-disable switch. Every workflow capable of appending to the shared `state` branch uses the same repository-wide `paper-state-branch-single-writer` concurrency group with `cancel-in-progress: false`; only one writer workflow can be active at a time. The MEXC and retired manual Polymarket workflows share that lock. The publisher independently verifies the complete remote chain before append, rejects multiple genesis roots, forks, orphaned or disconnected batches and duplicate event/run/idempotency identifiers, advances the ref with a non-forced fast-forward update, and after both new writes and idempotent replays verifies exact canonical file contents and membership in the complete remote chain. Any API failure or competing ref update fails closed; it must never force-push or claim that an uncommitted event is durable. Local restore follows `previous_batch_hash` links, not exchange timestamps. The first writer run for a new account generation appends only a non-financial recovery probe; a fresh checkout on a later run must verify it before that generation's 10 USDT account-initialization event can be created. The workflow's `GITHUB_TOKEN` retains Contents: write for publishing. Because the branch is unprotected, an authorized repository writer can still manually rewrite or delete history outside this publisher; hash-chain validation detects malformed/incomplete state when observed but cannot prevent a privileged rewrite. The branch and its events are public and permanent.

The repository remains public. State written to its branches is public and permanent. Never add API credentials or private endpoints.

Prohibited in this research workflow:
- Live orders, exchange Testnet orders or exchange-side stop placement.
- Private account, position or order endpoints.
- Exchange credentials, wallet access, deposits or withdrawals.
- Automatic activation of paper-state writing before the persistence/protection gate is proven.
- Unsupported profitability claims or treating unit tests as trading evidence.

## 7. Acceptance tests and report evidence

The test suite must prove: 2× margin-aware sizing; 50/50 margin allocation; combined-leg losses trigger the whole-book stop; a lifetime MDD greater than 25% does not itself stop the account; daily risk resets at UTC rollover; delayed first cron uses the previous day's last NAV; five-minute snapshots do not recalculate Q or rebalance; frozen daily entry shortlists serialize/restore correctly for five-minute retries; candidate retries are bounded and expire on a new daily candle; retained pair legs rebalance by signed quantity deltas with partial realized-P&L/fee accounting; replacing one contract does not close the retained opposite leg; successful rebalance resets the risk baseline only after the prior risk check; a latched emergency stop cannot be cleared; duplicate daily candle/snapshot events are idempotent; pending emergency flatten survives restart/rollover and is retried; missing marks are disclosed without fabricating NAV; funding/fees are reconciled exactly once; event-chain corruption fails closed.

CI evidence is not performance evidence. Report separately: source-data coverage, unit/integration test results, state-write readiness, forward account initialization, actual persisted portfolio observations, and any independently audited performance.


## 8. Active $50 USDT seed and state controls

The active forward paper account seed is 50 USDT. Both the portfolio module default and daily cycle capital constant are 50 USDT. At 50% NAV margin per leg and 2× leverage, each leg targets approximately 50 USDT notional and the combined book targets approximately 100 USDT gross notional, subject to current NAV, venue lot sizes, contract limits, book depth, fees and simulated costs. The simulator must never round a requested trade up merely to meet a venue minimum. Earlier public minimum-order diagnostics evaluated $1 and $10 per-leg thresholds only; they are not extrapolated as a measured $50 universe-wide coverage result. The $50 account has demonstrated a feasible pair on actual MEXC public depth. This is an execution-feasibility observation, not proof of profitability.

The scheduler defaults `PAPER_STATE_WRITE_ENABLED` to true. Set the repository Actions variable to the literal string `false` to pause paper-state writes; remove the variable or set it to `true` to run the enabled mode. No branch-protection rule, ruleset or Administration token is needed. The publisher uses the workflow `GITHUB_TOKEN` with Contents: write. The active $50 v3 generation was initialized only after its non-financial recovery probe was published, read back and verified from a later fresh checkout. The $1 and $10 account generations remain immutable archived history. Failed read-back, broken chain or a non-fast-forward conflict keeps the workflow fail-closed.


## 9. Two-stage recovery-before-initialization protocol

When the workflow runs with paper-state writing enabled (the default unless the repository variable is explicitly set to `false`):

1. The first write-capable invocation must publish only a non-financial paper_state_recovery_probe event. The publisher must read back the exact canonical event and verify the complete remote chain before reporting success. No financial state or account balance is created in this invocation.
2. The next invocation checks out the state branch afresh and locally verifies every event batch and the linear hash chain. It must detect the exact recovery-probe event before account initialization is allowed.
3. Only after that fresh-checkout recovery succeeds may the first financial event be written. It is typed paper_account_initialized and records initial_capital_usdt=50, starting_cash_usdt=50, forward-paper-only mode, no historical imports and the first valuation/decision timestamp.
4. Subsequent runs restore the financial event from the state branch and reconstruct the same account state. A missing probe, broken hash chain, missing account identifier, failed read-back or non-fast-forward conflict prevents initialization or further transitions and keeps the workflow fail-closed.

The non-financial probe is part of the append-only public state chain. It is not a trade, position, P&L entry or account initialization.

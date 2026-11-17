# MEXC Paper Workflow — Authoritative Operating Model

**Effective date:** 2026-11-17  
**Provider:** MEXC Futures public market data  
**Account mode:** USDT-settled paper simulation only  
**Active account generation:** 10 USDT seed — `mexc-usdt-forward-10usdt-v2`  
**Scheduler:** one GitHub Actions cron, every five minutes (*/5 * * * *)  
**Manual launcher:** [▶ START PAPER SIMULATION — MEXC (PAPER ONLY)](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml)

This document is the authoritative operating contract for the MEXC forward-paper workflow. It supersedes older instructions that imply a five-minute strategy-decision loop, hourly strategy decisions, or independent per-leg 25% drawdown stops.

## 1. One scheduler, two modes

The workflow is invoked by the same five-minute cron on every run. It determines its mode from the latest fully completed MEXC UTC daily candle and the persisted daily-workflow watermark.

### Daily-close research and decision mode

The first workflow invocation that observes a newly completed UTC daily candle runs the heavy path once for that candle:

1. Restore and verify the persisted paper event chain and market-data manifest.
2. Fetch current MEXC contract metadata, eligible cross-margin universe and bulk tickers.
3. Refresh instrument lifecycle and perform one bounded, resumable candle-bootstrap/incremental-history batch.
4. Validate completed daily candles and data coverage.
5. Recalculate exchange-neutral Q/B/ATR features and cross-sectional research/execution rankings.
6. If the paper-account state-write gate is open and the data gate passes, process due funding, assess the portfolio-level emergency limit, evaluate daily ATR/trailing exits and make the ordinary daily portfolio decision/rebalance.
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

Open the [GitHub Actions paper workflow](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml), select **▶ START PAPER SIMULATION — MEXC (PAPER ONLY)**, choose branch `main`, and select **Run workflow**. This invokes the same cycle immediately; it does not bypass the data, ranking, execution, persistence or risk gates. The automatic five-minute schedule remains enabled.

## 2. Portfolio construction and leverage

The active forward account is denominated entirely in USDT. The current generation ID is `mexc-usdt-forward-10usdt-v2`; its strategy generation is `trend-quality-daily-cross-sectional-v2-10usdt`. The prior 1 USDT account remains an archived, separate account in the append-only state history and is not merged into this account.

| Parameter | Setting |
|---|---:|
| Initial paper capital | 10 USDT |
| Long margin allocation | 50% of NAV |
| Short margin allocation | 50% of NAV |
| Default leverage | 2× per leg |
| Long target notional | 1× NAV |
| Short target notional | 1× NAV |
| Combined target gross notional | 2× NAV |

Sizing is calculated as NAV × margin allocation × leverage ÷ reference price, then rounded down to the exchange contract increment. Instrument maximum leverage and minimum/maximum contract constraints remain binding. The two positions are one combined portfolio; margin allocations do not mean that notional is capped at 50% of NAV.

Only USDT-quoted and USDT-settled contracts can enter this homogeneous paper account. Other settlement types may remain in research rankings, but must not be mixed into USDT NAV without a separately validated conversion and settlement model.

## 3. Combined portfolio emergency stop

The emergency limit is evaluated on combined account equity, not independently on the long and short legs.

NAV includes cash, realized P&L, unrealized P&L, entry/exit fees and confirmed funding cashflows. The implementation therefore naturally catches cases where both legs lose less than 25% individually but their combined losses cause the portfolio threshold to be breached.

The daily risk state is UTC-dated and has two distinct measures:

- **Daily return:** current portfolio NAV relative to the previous UTC day's last successful NAV snapshot. If there is no prior-day snapshot, the first observation of the UTC day is used as the initial baseline.
- **Daily drawdown stop:** current NAV relative to the highest observed NAV in the current UTC day, including the prior-day closing NAV as the opening reference.

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

The test suite must prove: 2× margin-aware sizing; 50/50 margin allocation; combined-leg losses trigger the whole-book stop; a lifetime MDD greater than 25% does not itself stop the account; daily risk resets at UTC rollover; delayed first cron uses the previous day's last NAV; five-minute snapshots do not recalculate Q or rebalance; duplicate daily candle/snapshot events are idempotent; pending emergency flatten survives restart/rollover and is retried; missing marks are disclosed without fabricating NAV; funding/fees are reconciled exactly once; event-chain corruption fails closed.

CI evidence is not performance evidence. Report separately: source-data coverage, unit/integration test results, state-write readiness, forward account initialization, actual persisted portfolio observations, and any independently audited performance.


## 8. 10 USDT seed and activation controls

The active forward paper account seed is 10 USDT. Both the portfolio module default and daily cycle capital constant are 10 USDT. At 50% NAV margin per leg and 2× leverage, the target is approximately 10 USDT notional per leg and 20 USDT combined gross notional. MEXC quantity increments, minimum/maximum contract limits, depth and simulated costs remain binding; the simulator must never round a requested trade up merely to meet a venue minimum. A live diagnostic over 1,061 active USDT-eligible perpetuals measured a median minimum contract notional of 0.2878 USDT, with 778 contracts meeting minimum quantity and step at a 1 USDT per-leg target and 1,045 at a 10 USDT target. Thus minimum orders are not generally above 1 USDT; the new 10 USDT generation was selected after the prior 1 USDT account's real decision returned FLAT_NO_EXECUTABLE_PAIR, to increase lot-size coverage. This is an execution-feasibility choice, not proof of profitability.

The scheduler defaults `PAPER_STATE_WRITE_ENABLED` to true. Set the repository Actions variable to the literal string `false` to pause paper-state writes; remove the variable or set it to `true` to run the enabled mode. No branch-protection rule, ruleset or Administration token is needed. The publisher uses the workflow `GITHUB_TOKEN` with Contents: write. The $10 generation is initialized after its own non-financial probe was published/read back and verified from a later fresh checkout. Its first successful initialization cycle opened a simulated VSTOCK_USDT long / BILL_USDT short pair. A subsequent independent restore check is still required before the new generation is described as independently restored. Failed read-back, broken chain, or a non-fast-forward conflict keeps the workflow fail-closed.


## 9. Two-stage recovery-before-initialization protocol

When the workflow runs with paper-state writing enabled (the default unless the repository variable is explicitly set to `false`):

1. The first write-capable invocation must publish only a non-financial paper_state_recovery_probe event. The publisher must read back the exact canonical event and verify the complete remote chain before reporting success. No financial state or account balance is created in this invocation.
2. The next invocation checks out the state branch afresh and locally verifies every event batch and the linear hash chain. It must detect the exact recovery-probe event before account initialization is allowed.
3. Only after that fresh-checkout recovery succeeds may the first financial event be written. It is typed paper_account_initialized and records initial_capital_usdt=10, starting_cash_usdt=10, forward-paper-only mode, no historical imports and the first valuation/decision timestamp.
4. Subsequent runs restore the financial event from the state branch and reconstruct the same account state. A missing probe, broken hash chain, missing account identifier, failed read-back or non-fast-forward conflict prevents initialization or further transitions and keeps the workflow fail-closed.

The non-financial probe is part of the append-only public state chain. It is not a trade, position, P&L entry or account initialization.

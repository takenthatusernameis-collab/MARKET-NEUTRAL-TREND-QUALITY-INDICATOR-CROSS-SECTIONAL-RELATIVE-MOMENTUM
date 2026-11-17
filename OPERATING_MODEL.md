# MEXC Paper Workflow — Authoritative Operating Model

**Effective date:** 2026-11-17  
**Provider:** MEXC Futures public market data  
**Account mode:** USDT-settled paper simulation only  
**Scheduler:** one GitHub Actions cron, every five minutes (*/5 * * * *)

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

This mode must **not** refresh the full research universe, backfill candles, recalculate Q rankings, alter ordinary target positions, initiate a normal rebalance, or run ordinary ATR/trailing-stop decisions. A monitoring run may close positions only to complete an already-triggered emergency flatten.

## 2. Portfolio construction and leverage

The forward account is denominated entirely in USDT.

| Parameter | Setting |
|---|---:|
| Initial paper capital | 1 USDT |
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

PAPER_STATE_WRITE_ENABLED must remain false unless the state branch has independently verified server-side protection against force-push/deletion, restricted writers, and a successful publisher/recovery test. The runtime protection check is also mandatory. The workflow defaults this setting to false and reads an explicit repository Actions variable named PAPER_STATE_WRITE_ENABLED; do not set it to true until protection and recovery verification pass. The workflow also requires an Actions secret named STATE_PROTECTION_TOKEN containing a fine-grained token limited to this repository with Administration: read permission, used only to inspect protection settings. The separate GITHUB_TOKEN retains Contents: write for append-only event publishing. Do not bypass either gate to make the paper account appear active.

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


## 8. 1 USDT seed and activation controls

The current forward paper account seed is 1 USDT, not the historical 100 USDT planning value. Both the portfolio module default and daily cycle capital constant are 1 USDT. At 50% NAV margin per leg and 2× leverage, the target is approximately 1 USDT notional per leg and 2 USDT combined gross notional. MEXC quantity increments, minimum/maximum contract limits, depth and simulated costs may prevent a pair from opening at this capital level; a flat 1 USDT account is a valid starting state and must not be forced into an undersized order.

The scheduler reads the repository variable PAPER_STATE_WRITE_ENABLED and defaults to false when it is absent. Before changing it to true, configure the state branch as protected with administrator enforcement, force-push disabled, deletion disabled and writer restrictions limited to the intended GitHub Actions app. Add the repository secret STATE_PROTECTION_TOKEN as a fine-grained token with only repository Administration: read permission so the workflow can independently inspect the branch-protection endpoint. The publisher continues to use the workflow GITHUB_TOKEN with Contents: write. A missing/invalid protection token, missing restrictions or failed publisher read-back must keep the account uninitialized.


## 9. Two-stage recovery-before-initialization protocol

When the operator has configured branch protection, added STATE_PROTECTION_TOKEN and explicitly enabled PAPER_STATE_WRITE_ENABLED:

1. The first write-capable invocation must publish only a non-financial paper_state_recovery_probe event. The publisher must read back the exact canonical event and verify the complete remote chain before reporting success. No financial state or account balance is created in this invocation.
2. The next invocation checks out the state branch afresh and locally verifies every event batch and the linear hash chain. It must detect the exact recovery-probe event before account initialization is allowed.
3. Only after that fresh-checkout recovery succeeds may the first financial event be written. It is typed paper_account_initialized and records initial_capital_usdt=1, starting_cash_usdt=1, forward-paper-only mode, no historical imports and the first valuation/decision timestamp.
4. Subsequent runs restore the financial event from the protected branch and reconstruct the same account state. A missing probe, broken hash chain, missing account identifier, failed read-back or failed protection check prevents initialization and keeps the workflow fail-closed.

The non-financial probe is part of the append-only public state chain. It is not a trade, position, P&L entry or account initialization.

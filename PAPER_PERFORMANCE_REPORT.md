# MEXC Paper Performance Report

Generated: 2026-11-17 03:53:31.912 UTC  
Account: mexc-usdt-forward-10usdt-v2  
Strategy generation: trend-quality-daily-cross-sectional-v2-10usdt  
Workflow run: [44012761360](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44012761360) (run #53, attempt 1; outcome: success)

This standalone report is rebuilt from the dedicated state branch after every MEXC paper workflow run. The complete source event chain is verified before publication to main.

## Current account snapshot

| Metric | Current value |
|---|---:|
| Initial capital | 10.00000000 USDT |
| **Net asset value (NAV)** | **9.79369460 USDT** |
| Total return from initial capital | -2.0631% |
| Cash | 9.99829460 USDT |
| Unrealized P&L | -0.20460000 USDT |
| Realized gross P&L | 0.00000000 USDT |
| Fees paid | 0.00170540 USDT |
| Confirmed funding | 0.00000000 USDT |
| Partial realized net P&L | 0.00000000 USDT |
| Open positions | 2 |
| Fully closed position trades | 0 |
| Closed-trade win rate | Unavailable — sample gate not met |
| Gross exposure | 1.9020× NAV |
| Net exposure | 0.1647× NAV |
| Long / short notional | 8.50740000 / 10.12000000 USDT |

Latest portfolio valuation: 2026-11-17 03:53:17.041 UTC.
Latest saved account event: 2026-11-17 03:53:17.041 UTC.

## Risk and performance metrics

| Metric | Result | Basis / sample gate |
|---|---:|---|
| Sortino ratio | Unavailable — at least 20 daily returns and 5 negative returns required | Daily NAV returns; minimum 20 returns and 5 negative returns |
| Sharpe ratio | Unavailable — at least 30 daily returns required | Daily NAV returns; minimum 30 returns |
| CAGR | Unavailable — at least 365 elapsed calendar days required | At least 365 elapsed calendar days |
| Calmar ratio | Unavailable — sample gate not met | CAGR divided by daily-equity drawdown |
| Annualized daily volatility | Unavailable — at least 30 daily returns required | Minimum 30 daily returns |
| Daily-equity maximum drawdown | Unavailable — sample gate not met | Daily UTC equity series |
| Maximum drawdown duration | Unavailable — sample gate not met | Daily UTC equity series |
| Recovery period after maximum drawdown | Unavailable — sample gate not met | Requires recovery to the prior peak |
| Closed-trade expectancy | Unavailable — sample gate not met USDT | Fully closed position trades only |
| Profit factor | Unavailable — sample gate not met | Fully closed position trades only |
| Current risk-window drawdown | -2.3530% | Versus current risk-window peak 10.02969460 USDT |

**Lifetime / cross-session maximum drawdown:** -2.3530%.
**Worst individual risk-session maximum drawdown:** -2.3530%.

Risk-session drawdown resets only at a successful new-pair entry, daily rebalance or UTC-day rollover. Lifetime drawdown is measured from original capital across all sessions and never resets.

### Maximum drawdown by risk session

| Session | Start (UTC) | Starting NAV | Latest NAV | Session return | Maximum drawdown | Marks |
|---:|---|---:|---:|---:|---:|---:|
| 1 | 2026-11-17 00:00:00.000 UTC | 10.00000000 | 9.79369460 | -2.0631% | -2.3530% | 14 |

Lifetime drawdown peak: 2026-11-17 01:51:41.256 UTC.
Lifetime drawdown trough: 2026-11-17 03:53:17.041 UTC (NAV 9.79369460 USDT).

## Equity curve

All persisted mark-to-market observations (14 points):

Sparkline: ▇▆▇▇▇▇▇▇█▇▇▇▇▁

Observed NAV range: 9.79369460 to 10.02969460 USDT.
Daily-equity observations: 1; daily metric status: INSUFFICIENT_DAILY_EQUITY_HISTORY (1 daily return observations).

### Daily equity observations

| UTC timestamp | NAV (USDT) |
|---|---:|
| 2026-11-16 00:00:00.000 UTC | 9.99529460 |

### Full mark-to-market equity history

| Timestamp (UTC) | NAV (USDT) | ROI from initial capital | Risk-window drawdown | Long notional | Short notional |
|---|---:|---:|---:|---:|---:|
| 2026-11-17 01:11:31.864 UTC | 10.00000000 | 0% | 0% | 0.00000000 | 0.00000000 |
| 2026-11-17 01:12:02.711 UTC | 9.99139460 | -0.08605400% | -0.08605400% | 8.52260000 | 9.93750000 |
| 2026-11-17 01:21:45.489 UTC | 10.00649460 | 0.06494600% | 0% | 8.53020000 | 9.93000000 |
| 2026-11-17 01:22:10.989 UTC | 10.00049460 | 0.00494600% | -0.0599610576914716967918016000% | 8.52920000 | 9.93500000 |
| 2026-11-17 01:22:42.301 UTC | 9.99649460 | -0.03505400% | -0.0999350961524528279863359900% | 8.53020000 | 9.94000000 |
| 2026-11-17 01:23:18.334 UTC | 10.00349460 | 0.03494600% | -0.0299805288457358483959008000% | 8.52720000 | 9.93000000 |
| 2026-11-17 01:23:50.444 UTC | 10.01269460 | 0.12694600% | 0% | 8.52640000 | 9.92000000 |
| 2026-11-17 01:26:57.853 UTC | 10.01229460 | 0.12294600% | -0.0039949285979420564769847300% | 8.52600000 | 9.92000000 |
| 2026-11-17 01:51:41.256 UTC | 10.02969460 | 0.29694600% | 0% | 8.53340000 | 9.91000000 |
| 2026-11-17 01:54:44.226 UTC | 9.99699460 | -0.03005400% | -0.3260318614287617491364094000% | 8.53320000 | 9.94250000 |
| 2026-11-17 01:55:24.172 UTC | 9.99699460 | -0.03005400% | -0.3260318614287617491364094000% | 8.53320000 | 9.94250000 |
| 2026-11-17 02:37:58.804 UTC | 10.01539460 | 0.15394600% | -0.1425766244168591135367172600% | 8.53160000 | 9.92250000 |
| 2026-11-17 02:38:43.277 UTC | 9.99659460 | -0.03405400% | -0.3300200187551074586059679200% | 8.53280000 | 9.94250000 |
| 2026-11-17 03:53:17.041 UTC | 9.79369460 | -2.06305400% | -2.353012822543968587039529600% | 8.50740000 | 10.12000000 |

## Open positions

| Symbol | Side | Quantity | Entry | Mark | Notional (USDT) | Unrealized P&L (USDT) | Entry UTC |
|---|---|---:|---:|---:|---:|---:|---|
| VSTOCK_USDT | long | 0.02 | 426.35 | 425.37 | 8.50740000 | -0.01960000 | 2026-11-17 01:11:31.864 UTC |
| BILL_USDT | short | 2500 | 0.003974 | 0.004048 | 10.12000000 | -0.18500000 | 2026-11-17 01:11:31.864 UTC |

## Full timestamped trade and funding history

Explicit fills and funding records are shown directly. Persisted before/after position changes are used as a backstop; where an event did not preserve an exact fill price or P&L, the note identifies the row as derived rather than inventing details.

| Timestamp (UTC) | Action | Symbol | Side | Quantity / Δ | Price | Fees (USDT) | Net P&L (USDT) | Funding (USDT) | Source / note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-11-17 01:11:31.864 UTC | OPENED | VSTOCK_USDT | long | 0.02 | 426.35 | 0.00170540 | — | — | fills; paper_account_initialized |
| 2026-11-17 01:11:31.864 UTC | OPENED | BILL_USDT | short | 2500 | 0.003974 | — | — | — | fills; paper_account_initialized |

## Data integrity and operating boundary

Verified global event batches: **18**.
Events for this account/strategy generation: **15** (14 carry full account-state snapshots).
Latest global event-batch hash: f53bb1e2fee630e9436702b463e3553c152f71663aefee157efae106916745a3.
All batches were hash-verified and the complete parent-hash chain was checked for a single genesis, missing parents, duplicate identifiers and forks.
The archived $1 account generation is excluded; only the active $10 USDT account is reported.
Paper simulation only: no live orders, private exchange endpoints, credentials or wallet access.
Metrics remain unavailable until their documented sample gates are satisfied.

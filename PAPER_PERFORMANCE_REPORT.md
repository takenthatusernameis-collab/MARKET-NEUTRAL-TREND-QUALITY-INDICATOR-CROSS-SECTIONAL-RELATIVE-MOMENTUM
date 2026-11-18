# MEXC Paper Performance Report

Generated: 2026-11-18 05:17:01.233 UTC  
Account: mexc-usdt-forward-50usdt-v3  
Strategy generation: trend-quality-daily-cross-sectional-v3-50usdt  
Workflow run: [44243034540](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44243034540) (run #76, attempt 1; outcome: failure)

This standalone report is rebuilt from the dedicated state branch after every MEXC paper workflow run. The complete source event chain is verified before publication to main.

## Current account snapshot

| Metric | Current value |
|---|---:|
| Initial capital | 50.00000000 USDT |
| **Net asset value (NAV)** | **50.13572776 USDT** |
| Total return from initial capital | +0.2715% |
| Cash | 49.99082776 USDT |
| Unrealized P&L | 0.14490000 USDT |
| Realized gross P&L | 0.00000000 USDT |
| Fees paid | 0.00917224 USDT |
| Confirmed funding | 0.00000000 USDT |
| Partial realized net P&L | 0.00000000 USDT |
| Open positions | 2 |
| Fully closed position trades | 0 |
| Closed-trade win rate | Unavailable — sample gate not met |
| Gross exposure | 1.8253× NAV |
| Net exposure | 0.0026× NAV |
| Long / short notional | 45.82050000 / 45.69240000 USDT |

Latest portfolio valuation: 2026-11-18 04:54:39.546 UTC.
Latest saved account event: 2026-11-18 04:54:39.546 UTC.

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
| Current risk-window drawdown | +0.0000% | Versus current risk-window peak 50.13572776 USDT |

**Lifetime / cross-session maximum drawdown:** -0.2483%.
**Worst individual risk-session maximum drawdown:** -0.2483%.

Risk-session drawdown resets only at a successful new-pair entry, daily rebalance or UTC-day rollover. Lifetime drawdown is measured from original capital across all sessions and never resets.

### Maximum drawdown by risk session

| Session | Start (UTC) | Starting NAV | Latest NAV | Session return | Maximum drawdown | Marks |
|---:|---|---:|---:|---:|---:|---:|
| 1 | 2026-11-18 04:26:47.111 UTC | 50.01072776 | 50.13572776 | +0.2499% | -0.2483% | 3 |

Lifetime drawdown peak: 2026-11-18 04:26:47.111 UTC.
Lifetime drawdown trough: 2026-11-18 04:39:33.310 UTC (NAV 49.88652776 USDT).

## Equity curve

All persisted mark-to-market observations (3 points):

![Trend-Quality paper portfolio equity curve](equity_curve.svg)

The SVG uses the same hash-chain-verified mark-to-market NAV observations shown in the full history below. The dashed line marks original account capital.

Observed NAV range: 49.88652776 to 50.13572776 USDT.
Daily-equity observations: 1; daily metric status: INSUFFICIENT_DAILY_EQUITY_HISTORY (1 daily return observations).

### Daily equity observations

| UTC timestamp | NAV (USDT) |
|---|---:|
| 2026-11-17 00:00:00.000 UTC | 50.01072776 |

### Full mark-to-market equity history

| Timestamp (UTC) | NAV (USDT) | ROI from initial capital | Risk-window drawdown | Long notional | Short notional |
|---|---:|---:|---:|---:|---:|
| 2026-11-18 04:26:47.111 UTC | 50.01072776 | 0.0214555200% | 0% | 45.85790000 | 45.85480000 |
| 2026-11-18 04:39:33.310 UTC | 49.88652776 | -0.2269444800% | -0.2483467159206962918229686600% | 45.83810000 | 45.95920000 |
| 2026-11-18 04:54:39.546 UTC | 50.13572776 | 0.2714555200% | 0% | 45.82050000 | 45.69240000 |

## Open positions

| Symbol | Side | Quantity | Entry | Mark | Notional (USDT) | Unrealized P&L (USDT) | Entry UTC |
|---|---|---:|---:|---:|---:|---:|---|
| VSTOCK_USDT | long | 0.11 | 416.92 | 416.55 | 45.82050000 | -0.04070000 | 2026-11-18 04:26:47.111 UTC |
| BILL_USDT | short | 11600 | 0.003955 | 0.003939 | 45.69240000 | 0.18560000 | 2026-11-18 04:26:47.111 UTC |

## Full timestamped trade and funding history

Explicit fills and funding records are shown directly. Persisted before/after position changes are used as a backstop; where an event did not preserve an exact fill price or P&L, the note identifies the row as derived rather than inventing details.

| Timestamp (UTC) | Action | Symbol | Side | Quantity / Δ | Price | Fees (USDT) | Net P&L (USDT) | Funding (USDT) | Source / note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-11-18 04:26:47.111 UTC | OPENED | VSTOCK_USDT | long | 0.11 | 416.92 | 0.00917224 | — | — | fills; paper_account_initialized |
| 2026-11-18 04:26:47.111 UTC | OPENED | BILL_USDT | short | 11600 | 0.003955 | — | — | — | fills; paper_account_initialized |
| 2026-11-18 04:26:47.111 UTC | RISK WINDOW RESET | Portfolio | — | — | 50.01072776 | — | — | — | daily_portfolio_rebalance |

## Data integrity and operating boundary

Verified global event batches: **38**.
Events for this account/strategy generation: **4** (3 carry full account-state snapshots).
Latest global event-batch hash: a1fe9de2cadfa952c9ddbe08cb5cd57d99b74ad5f8f0ffe6b1eb0896965d922e.
All batches were hash-verified and the complete parent-hash chain was checked for a single genesis, missing parents, duplicate identifiers and forks.
The archived $1 and $10 USDT account generations are excluded; only the active $50 USDT account is reported.
Paper simulation only: no live orders, private exchange endpoints, credentials or wallet access.
Metrics remain unavailable until their documented sample gates are satisfied.

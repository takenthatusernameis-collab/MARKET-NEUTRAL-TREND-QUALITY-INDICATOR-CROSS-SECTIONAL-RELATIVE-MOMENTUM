# MEXC Paper Performance Report

Generated: 2026-11-18 08:13:58.682 UTC  
Account: mexc-usdt-forward-50usdt-v3  
Strategy generation: trend-quality-daily-cross-sectional-v3-50usdt  
Workflow run: [44264992523](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44264992523) (run #87, attempt 1; outcome: success)

This standalone report is rebuilt from the dedicated state branch after every MEXC paper workflow run. The complete source event chain is verified before publication to main.

## Current account snapshot

| Metric | Current value |
|---|---:|
| Initial capital | 50.00000000 USDT |
| **Net asset value (NAV)** | **48.20552776 USDT** |
| Total return from initial capital | -3.5889% |
| Cash | 49.93412776 USDT |
| Unrealized P&L | -1.72860000 USDT |
| Realized gross P&L | -0.05670000 USDT |
| Fees paid | 0.00917224 USDT |
| Confirmed funding | 0.00000000 USDT |
| Partial realized net P&L | -0.05670000 USDT |
| Open positions | 2 |
| Fully closed position trades | 0 |
| Closed-trade win rate | Unavailable — sample gate not met |
| Gross exposure | 1.9084× NAV |
| Net exposure | 0.0037× NAV |
| Long / short notional | 45.90850000 / 46.08800000 USDT |

Latest portfolio valuation: 2026-11-18 08:13:34.956 UTC.
Latest saved account event: 2026-11-18 08:13:34.956 UTC.

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
| Current risk-window drawdown | -3.8499% | Versus current risk-window peak 50.13572776 USDT |

**Lifetime / cross-session maximum drawdown:** -4.2329%.
**Worst individual risk-session maximum drawdown:** -4.2329%.

Risk-session drawdown resets only at a successful new-pair entry, daily rebalance or UTC-day rollover. Lifetime drawdown is measured from original capital across all sessions and never resets.

### Maximum drawdown by risk session

| Session | Start (UTC) | Starting NAV | Latest NAV | Session return | Maximum drawdown | Marks |
|---:|---|---:|---:|---:|---:|---:|
| 1 | 2026-11-18 04:26:47.111 UTC | 50.01072776 | 48.20552776 | -3.6096% | -4.2329% | 15 |

Lifetime drawdown peak: 2026-11-18 04:54:39.546 UTC.
Lifetime drawdown trough: 2026-11-18 08:05:25.826 UTC (NAV 48.01352776 USDT).

## Equity curve

All persisted mark-to-market observations (15 points):

![Trend-Quality paper portfolio equity curve](equity_curve.svg)

The SVG uses the same hash-chain-verified mark-to-market NAV observations shown in the full history below. The dashed line marks original account capital.

Observed NAV range: 48.01352776 to 50.13572776 USDT.
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
| 2026-11-18 05:37:14.308 UTC | 49.66232776 | -0.6753444800% | -0.9442368170382772957677317700% | 45.82270000 | 46.16800000 |
| 2026-11-18 05:37:15.935 UTC | 49.66302776 | -0.6739444800% | -0.9428406071271518329307283600% | 45.82270000 | 45.77000000 |
| 2026-11-18 06:27:47.521 UTC | 48.61812776 | -2.7637444800% | -3.026983087320003430623383460% | 45.81280000 | 46.80500000 |
| 2026-11-18 06:27:59.632 UTC | 48.61672776 | -2.7665444800% | -3.029775507142254356297390270% | 45.81280000 | 45.99100000 |
| 2026-11-18 06:46:25.386 UTC | 48.75802776 | -2.4839444800% | -2.747940563653643072199417100% | 45.85240000 | 45.88930000 |
| 2026-11-18 07:25:47.876 UTC | 48.41272776 | -3.1745444800% | -3.436670966955960668795525630% | 45.83480000 | 46.21700000 |
| 2026-11-18 07:25:56.825 UTC | 48.41252776 | -3.1749444800% | -3.437069884073425086748955170% | 45.83480000 | 45.80800000 |
| 2026-11-18 08:05:25.826 UTC | 48.01352776 | -3.9729444800% | -4.232909533414938903840896390% | 45.85020000 | 46.22240000 |
| 2026-11-18 08:05:34.824 UTC | 48.08262776 | -3.8347444800% | -4.095083669330982500930988780% | 45.86340000 | 45.75420000 |
| 2026-11-18 08:12:35.494 UTC | 48.09222776 | -3.8155444800% | -4.075935647692690439166370640% | 45.90630000 | 45.78750000 |
| 2026-11-18 08:13:24.728 UTC | 48.21762776 | -3.5647444800% | -3.825814615042500382366046260% | 45.90960000 | 45.66540000 |
| 2026-11-18 08:13:34.956 UTC | 48.20552776 | -3.5889444800% | -3.849949100649097668548533700% | 45.90850000 | 46.08800000 |

## Open positions

| Symbol | Side | Quantity | Entry | Mark | Notional (USDT) | Unrealized P&L (USDT) | Entry UTC |
|---|---|---:|---:|---:|---:|---:|---|
| VSTOCK_USDT | long | 0.11 | 416.92 | 417.35 | 45.90850000 | 0.04730000 | 2026-11-18 04:26:47.111 UTC |
| BILL_USDT | short | 11200 | 0.0039564375 | 0.004115 | 46.08800000 | -1.77590000 | 2026-11-18 04:26:47.111 UTC |

## Full timestamped trade and funding history

Explicit fills and funding records are shown directly. Persisted before/after position changes are used as a backstop; where an event did not preserve an exact fill price or P&L, the note identifies the row as derived rather than inventing details.

| Timestamp (UTC) | Action | Symbol | Side | Quantity / Δ | Price | Fees (USDT) | Net P&L (USDT) | Funding (USDT) | Source / note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-11-18 04:26:47.111 UTC | OPENED | VSTOCK_USDT | long | 0.11 | 416.92 | 0.00917224 | — | — | fills; paper_account_initialized |
| 2026-11-18 04:26:47.111 UTC | OPENED | BILL_USDT | short | 11600 | 0.003955 | — | — | — | fills; paper_account_initialized |
| 2026-11-18 04:26:47.111 UTC | RISK WINDOW RESET | Portfolio | — | — | 50.01072776 | — | — | — | daily_portfolio_rebalance |
| 2026-11-18 05:37:15.935 UTC | REDUCED | BILL_USDT | short | -100 | — | — | — | — | Derived from consecutive persisted account states; exact fill price and P&L were not present in this event. |
| 2026-11-18 06:27:59.632 UTC | REDUCED | BILL_USDT | short | -200 | — | — | — | — | Derived from consecutive persisted account states; exact fill price and P&L were not present in this event. |
| 2026-11-18 07:25:56.825 UTC | REDUCED | BILL_USDT | short | -100 | — | — | — | — | Derived from consecutive persisted account states; exact fill price and P&L were not present in this event. |
| 2026-11-18 08:05:34.824 UTC | REDUCED | BILL_USDT | short | -100 | — | — | — | — | Derived from consecutive persisted account states; exact fill price and P&L were not present in this event. |
| 2026-11-18 08:13:34.956 UTC | INCREASED | BILL_USDT | short | 100 | 0.0039564375 | — | — | — | Derived from consecutive persisted account states; exact fill price and P&L were not present in this event. |

## Data integrity and operating boundary

Verified global event batches: **45**.
Events for this account/strategy generation: **11** (10 carry full account-state snapshots).
Latest global event-batch hash: c88461290d02d5a713b7a8757a2d90e06cce2ac8efed9ba86bb78791b2af0378.
All batches were hash-verified and the complete parent-hash chain was checked for a single genesis, missing parents, duplicate identifiers and forks.
The archived $1 and $10 USDT account generations are excluded; only the active $50 USDT account is reported.
Paper simulation only: no live orders, private exchange endpoints, credentials or wallet access.
Metrics remain unavailable until their documented sample gates are satisfied.

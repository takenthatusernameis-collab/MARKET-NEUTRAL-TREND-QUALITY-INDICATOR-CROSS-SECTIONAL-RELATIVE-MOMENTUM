# MEXC Paper Performance Report

> **Initial report seed:** 2026-11-17 01:26:57.853 UTC  
> **Account:** `mexc-usdt-forward-10usdt-v2`  
> **Strategy generation:** `trend-quality-daily-cross-sectional-v2-10usdt`  
> **Source state-batch hash:** `d6ed6334e31902a4fb9db09ab0c2dd36c0af86f6b16ed460932cb19a91699b2e`

This independent file is automatically regenerated from the verified paper-event chain and committed to main after each MEXC workflow run. This seed reflects the latest verified account snapshot available when the file was added; the next workflow run will add its own run link and refresh all values.

## Current account snapshot

| Metric | Value |
|---|---:|
| Initial capital | 10.00000000 USDT |
| **Net asset value (NAV)** | **10.01229460 USDT** |
| Return from initial capital | +0.1229% |
| Cash | 9.99829460 USDT |
| Unrealized P&L | +0.01400000 USDT |
| Realized gross P&L | 0.00000000 USDT |
| Fees paid | 0.00170540 USDT |
| Confirmed funding | 0.00000000 USDT |
| Partial realized net P&L | 0.00000000 USDT |
| Open positions | 2 |
| Fully closed position trades | 0 |
| Gross exposure | 1.8423× NAV |
| Net exposure | 0.1392× NAV |
| Long / short notional | 8.52600000 / 9.92000000 USDT |

Latest saved account event: **2026-11-17 01:26:57.853 UTC**.

## Risk and performance metrics

| Metric | Result |
|---|---:|
| Current risk-window drawdown | -0.0040% |
| Maximum drawdown in current risk session | -0.0999% |
| Lifetime / cross-session maximum drawdown | -0.0999% |
| Sortino ratio | Unavailable — requires at least 20 daily returns and 5 negative daily returns |
| Sharpe ratio | Unavailable — requires at least 30 daily returns |
| CAGR | Unavailable — requires at least 365 elapsed calendar days |
| Calmar ratio | Unavailable — CAGR sample gate not met |
| Annualized daily volatility | Unavailable — requires at least 30 daily returns |
| Daily-equity maximum drawdown | Unavailable — daily-equity history is insufficient |
| Closed-trade expectancy / profit factor | Unavailable — no closed trades |

Risk-window drawdown restarts at a successful new-pair entry, daily rebalance or UTC-day rollover. Lifetime drawdown never resets.

### Maximum drawdown by risk session

| Session | Start (UTC) | Starting NAV | Latest NAV | Maximum drawdown | Marks |
|---:|---|---:|---:|---:|---:|
| 1 | 2026-11-17 00:00:00 UTC | 10.00000000 | 10.01229460 | -0.0999% | 8 |

## Equity curve

**Mark-to-market observations:** 8

Sparkline: ▃▁▅▃▂▄██

| Timestamp (UTC) | NAV (USDT) | ROI from initial capital | Risk-window drawdown |
|---|---:|---:|---:|
| 2026-11-17 01:11:31.864 UTC | 10.00000000 | 0.00000000% | 0.00000000% |
| 2026-11-17 01:12:02.711 UTC | 9.99139460 | -0.08605400% | -0.08605400% |
| 2026-11-17 01:21:45.489 UTC | 10.00649460 | +0.06494600% | 0.00000000% |
| 2026-11-17 01:22:10.989 UTC | 10.00049460 | +0.00494600% | -0.05996106% |
| 2026-11-17 01:22:42.301 UTC | 9.99649460 | -0.03505400% | -0.09993510% |
| 2026-11-17 01:23:18.334 UTC | 10.00349460 | +0.03494600% | -0.02998053% |
| 2026-11-17 01:23:50.444 UTC | 10.01269460 | +0.12694600% | 0.00000000% |
| 2026-11-17 01:26:57.853 UTC | 10.01229460 | +0.12294600% | -0.00399493% |

Daily-equity observations: 1. Daily-return ratios are therefore not statistically meaningful yet.

### Daily equity observations

| UTC timestamp | NAV (USDT) |
|---|---:|
| 2026-11-16 00:00:00 UTC | 9.99529460 |

## Open positions

| Symbol | Side | Quantity | Entry | Latest mark | Unrealized P&L |
|---|---|---:|---:|---:|---:|
| VSTOCK_USDT | Long | 0.02 | 426.35 | 426.30 | -0.00100000 USDT |
| BILL_USDT | Short | 2,500 | 0.003974 | 0.003968 | +0.01500000 USDT |

## Full timestamped trade and funding history

| Timestamp (UTC) | Action | Symbol | Side | Quantity | Price | Fees (USDT) | Realized P&L (USDT) | Funding (USDT) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2026-11-17 01:11:31.864 UTC | OPENED | VSTOCK_USDT | Long | 0.02 | 426.35 | 0.00170540 | — | — |
| 2026-11-17 01:11:31.864 UTC | OPENED | BILL_USDT | Short | 2,500 | 0.003974 | 0.00000000 | — | — |

No close, partial reduction or funding-settlement event has been recorded for this account generation yet.

## Data integrity and operating boundary

- Verified global event batches: 12; active $10 account events: 9; events with full portfolio-state snapshots: 8.
- The source chain is verified from a single genesis through the latest batch; archived $1 history is excluded.
- This report records hypothetical fills from the paper simulator only. No live orders, private endpoints, credentials or wallet access are used.
- Metrics remain unavailable until their respective sample gates are satisfied.

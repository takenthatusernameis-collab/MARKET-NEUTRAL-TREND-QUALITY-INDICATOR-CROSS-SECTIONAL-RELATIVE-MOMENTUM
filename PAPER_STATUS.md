# ACTIVE PAPER STATUS — MEXC $100 USDT

**🟢 ACTIVE · PAPER ONLY · NO LIVE ORDERS**

**Correct workflow:** [Open active workflow](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml)

- Account: `mexc-usdt-forward-100usdt-v4`
- Strategy generation: `trend-quality-daily-cross-sectional-v4-100usdt`
- Starting capital: **100.00000000 USDT**
- Account state: **INITIALIZED — FORWARD PAPER**
- Last report build: 2026-11-20 05:59:22 UTC
- Latest workflow run: [44684416917](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44684416917) · run #123, attempt 1 · success · workflow_dispatch
- Latest processed daily candle: 2026-11-19 00:00:00 UTC
- Latest account event: 2026-11-20 05:58:46 UTC
- Primary execution journal: [PAPER_TRADE_JOURNAL.md](PAPER_TRADE_JOURNAL.md)

## Current performance

| Metric | Value |
|---|---:|
| Initial capital | 100.00000000 USDT |
| **NAV** | **95.85983524 USDT** |
| Total return | -4.140% |
| Cash | 91.54223524 USDT |
| Unrealized P&L | +4.31760000 USDT |
| Fees paid | 0.09876476 USDT |
| Confirmed funding | +0.00000000 USDT |
| Gross exposure | 1.866× NAV |
| Net exposure | 0.045× NAV |
| Current drawdown from risk-window peak | -2.358% |
| Lifetime / cross-session maximum drawdown | -18.476% |
| Worst risk-session maximum drawdown | -18.476% |
| Sharpe ratio | Unavailable — At least 30 daily returns are required |
| Sortino ratio | Unavailable — Requires at least 20 daily returns and 5 negative daily returns |
| Annualized daily volatility | Unavailable — At least 30 daily returns are required |

### Maximum drawdown by risk session

| Session start (UTC) | Starting NAV | Latest NAV | Max drawdown | Marks |
|---|---:|---:|---:|---:|
| 2026-11-18 00:00:00 UTC | 100.00000000 | 100.00000000 | +0.000% | 1 |
| 2026-11-18 15:33:17 UTC | 99.85838576 | 102.38258576 | +0.000% | 3 |
| 2026-11-19 00:00:00 UTC | 102.40508576 | 102.40508576 | +0.000% | 1 |
| 2026-11-19 01:20:33 UTC | 102.23450048 | 83.84700048 | -18.476% | 14 |
| 2026-11-20 00:00:00 UTC | 91.63750048 | 91.63750048 | +0.000% | 1 |
| 2026-11-20 00:34:42 UTC | 91.48783524 | 95.85983524 | -2.358% | 9 |

## Open positions

| Symbol | Side | Quantity | Entry price | Mark | Notional (USDT) |
|---|---|---:|---:|---:|---:|
| WMTSTOCK_USDT | long | 0.72 | 126.55 | 127.19 | 91.576800 |
| BILL_USDT | short | 20800 | 0.004382423076923076923076923077 | 0.004197 | 87.297600 |

## Primary path — equal exposure

The live forward-paper strategy sizes the long and short legs independently toward equal USDT notional (approximately 1× NAV per leg before lot rounding).

![Equal-exposure strategy equity curve](equal_exposure_equity_curve.svg)

## Alternative path — volatility-weighted sizing

This chart is a **visual-only counterfactual**, not an executed account. It reuses the primary strategy’s exact selected symbols, sides and rebalance timestamps; only the notional split changes. No alternative trade journal is created.

At each rebalance, the quieter leg receives the larger share using inverse 30-completed-day realized volatility. The leverage overlay is the ratio of equal-exposure pair volatility to the inverse-volatility pair’s base estimated volatility. It increases modeled gross exposure only when the alternative has lower estimated volatility. Estimates use only data available at that rebalance.

- Latest long / short allocation: **83.5% / 16.5%** of alternative gross notional.
- Latest volatility-matching leverage multiplier: **2.027×**.
- Estimated base volatility reduction before leverage: **+50.67%**.
- Volatility observations used: **30**; status: `RISK_MATCHED_INVERSE_VOLATILITY`.

![Inverse-volatility alternative equity curve](alternative_path_equity_curve.svg)

**Model limitations:** the counterfactual scales observed primary entry/exit fees and funding by shadow notional. It does not model additional nonlinear market impact, depth constraints, liquidation limits or exchange leverage caps for larger hypothetical exposure. It is not an executable leverage recommendation.

## Next workflow action

The next daily decision requires a newer completed UTC candle and a passing data-coverage gate.

The daily-candle watermark is not advanced by this report. Only the paper workflow can consume a completed candle after full-history and execution gates pass. A blocked or incomplete run remains visible.

## Historical separation

The v3 $50 USDT generation and its preliminary snapshots are archived and excluded from this account’s NAV, returns, equity curves and metrics. The immutable event ledger remains intact.

## Alternative-path reconstruction notes

- No reconstruction warnings.

This is the compact live status page. The former detailed v3 report is retained under `archive/2026-11-18/` for audit purposes only.

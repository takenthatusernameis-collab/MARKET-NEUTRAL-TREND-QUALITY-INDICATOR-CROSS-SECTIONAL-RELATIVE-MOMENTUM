# Active Paper Account — MEXC $50 USDT

<badge>Paper only</badge> **There is one active forward-paper account.**

| Field | Active value |
|---|---|
| Exchange/data venue | MEXC Futures public market data |
| Account ID | `mexc-usdt-forward-50usdt-v3` |
| Strategy generation | `trend-quality-daily-cross-sectional-v3-50usdt` |
| Initial capital | **50.00000000 USDT** |
| Account mode | Forward paper only |
| State branch | `state` |
| Active writer workflow | [▶ RUN THIS — ACTIVE MEXC $50 USDT PAPER ONLY — MANUAL / AUTO](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml) |
| Standalone report | [PAPER_PERFORMANCE_REPORT.md](PAPER_PERFORMANCE_REPORT.md) |

## Manual trigger

1. Open the linked MEXC paper workflow.
2. Select branch `main`.
3. Select **Run workflow**.
4. Set the required confirmation to `I_CONFIRM_ACTIVE_50_USDT_PAPER_ONLY`.
5. Confirm the run. Its title will start with **▶ MANUAL PAPER RUN — MEXC $50 USDT**.

Manual dispatch and the five-minute scheduler use the same account ID and strategy ID. Neither trigger creates a new financial account generation. The MEXC public preflight is a manual-only, read-only diagnostic, not the paper account workflow. The retired Polymarket paper-state workflow has been removed.

## Archived generations

The append-only event ledger retains earlier account generations:

- `mexc-usdt-forward` — 1 USDT, archived.
- `mexc-usdt-forward-10usdt-v2` — 10 USDT, archived.

Their events are not deleted or overwritten. The current MEXC cycle and performance report select only the v3 $50 account; prior cash, positions, NAV, trades and returns are not imported or combined.

## Last persisted snapshot

On 2026-11-18 05:37:15.935 UTC, run [44245469767](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44245469767) recorded NAV 49.66302776 USDT and two simulated open positions: VSTOCK_USDT long (0.11 base units) and BILL_USDT short (11,500 base units). Dollar notionals were 45.822700 and 45.770000 USDT; the 0.052700 USDT imbalance was 0.1061% of NAV, below the 0.5% band. The run reduced the short position by 100 units through a paper-only partial fill. No live order was submitted. Consult the linked report for the latest verified values.

## Operating boundary

Public market-data endpoints and simulated fills only. No live exchange orders, private account endpoints, credentials or wallet access. Five-minute observations are scheduled/best-effort rather than continuous. Dollar-notional neutrality is not beta neutrality or a guarantee of zero market risk. Performance metrics remain unavailable until their documented sample-size gates are met.

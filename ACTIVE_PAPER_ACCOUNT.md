# ACTIVE PAPER ACCOUNT — MEXC $100 USDT

**🟢 ACTIVE · FORWARD PAPER ONLY · NO LIVE EXCHANGE ORDERS**

| Field | Active value |
|---|---|
| Exchange/data venue | MEXC Futures public market data |
| Account ID | `mexc-usdt-forward-100usdt-v4` |
| Strategy generation | `trend-quality-daily-cross-sectional-v4-100usdt` |
| Starting capital | **100.00000000 USDT** |
| Account mode | New forward-paper generation |
| State branch | `state` |
| Active workflow | [▶ RUN THIS — ACTIVE MEXC $100 USDT PAPER ONLY](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml) |
| Live status | [PAPER_STATUS.md](PAPER_STATUS.md) |

## Manual trigger — correct workflow

1. Open the linked **▶ ACTIVE PAPER ACCOUNT — MEXC $100 USDT PAPER ONLY — MANUAL / AUTO** workflow.
2. Select branch `main`.
3. Select **Run workflow**.
4. Select the confirmation `I_CONFIRM_ACTIVE_100_USDT_PAPER_ONLY`.
5. Start the run. The run name begins **▶ MANUAL PAPER RUN — MEXC $100 USDT — ACTIVE ACCOUNT**.

The same account is used by the five-minute monitor/retry schedule and the dedicated 00:01 UTC daily-close schedule. There is no push-triggered paper-account run. The workflow uses the official public MEXC Futures REST host, `https://api.mexc.com`, and sends no live orders.

## Restart and daily-candle semantics

Generation v4 is a new account, not a reset or rewrite of the v3 ledger:

- Its financial starting cash is exactly **100 USDT**.
- Its account decision watermark starts empty. The latest genuinely completed UTC daily candle is therefore eligible for the first v4 decision, subject to complete history, current marks, fresh books and successful two-leg simulated fills.
- Shared public candle history and its market-data manifest are preserved; they are not rewritten, fabricated or backdated.
- Immutable v3 $50 events, fills, fees, snapshots and reports remain archived and are excluded from v4 NAV, returns, curves and performance metrics.
- The first daily decision is recorded only after the new account passes the recovery-probe/fresh-checkout protocol.

A blocked data or execution gate must remain visible as blocked. It must not consume the daily decision watermark or create partial financial state.

## Archived generations

The former v3 $50 account is retained under `archive/2026-11-18/v3/` for historical inspection only. Earlier 1 USDT and 10 USDT generations remain in the immutable state ledger. None of those generations are active, pooled into v4, or used to calculate v4 performance.

## Operating boundary

Public market-data endpoints and simulated order-book fills only. No private account endpoints, API credentials, wallet access or real orders. The $100 account remains a paper-only research simulation. Dollar-notional equality is not beta neutrality or a guarantee of low market risk.

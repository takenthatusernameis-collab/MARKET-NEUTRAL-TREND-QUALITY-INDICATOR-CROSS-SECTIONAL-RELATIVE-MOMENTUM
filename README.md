# Market-Neutral Trend-Quality Indicator — Cross-Sectional Relative Momentum

A paper-only research system for the Sepiashvili Trend-Quality Indicator (Q), ranking active cross-margin perpetual contracts and eventually maintaining one long and one short. The indicator engine is exchange-neutral; the selected market-data adapter is **MEXC Futures, USDT-settled cross-margin perpetuals**.

**Standalone account performance ledger:** [PAPER_PERFORMANCE_REPORT.md](PAPER_PERFORMANCE_REPORT.md) — equity curve, per-session and lifetime maximum drawdown, sample-gated Sortino/Sharpe/CAGR metrics, account snapshot and full timestamped trade/funding activity. It is rebuilt from the verified state event chain and committed to `main` after every MEXC paper workflow run.

## ▶ MANUAL TRIGGER — ACTIVE $50 USDT PAPER ACCOUNT

<badge>Paper only</badge> **[▶ ACTIVE PAPER ACCOUNT — MEXC $50 USDT — MANUAL / AUTO](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml)**

On the GitHub Actions page, choose the workflow named **▶ RUN THIS — ACTIVE MEXC $50 USDT PAPER ONLY — MANUAL / AUTO**, select branch **main**, choose **Run workflow**, and set the required confirmation to `I_CONFIRM_ACTIVE_50_USDT_PAPER_ONLY`. The run title will begin **▶ MANUAL PAPER RUN — MEXC $50 USDT — ACTIVE ACCOUNT** so it is easy to distinguish from scheduled and push-triggered cycles. This is the only active portfolio-state writer. The same $50 account is invoked by a five-minute schedule plus a dedicated 00:01 UTC daily-close backup trigger; both share the same writer lock and completed-candle watermark. Manual dispatch does not create a second account.

The separate MEXC public preflight is a read-only diagnostic, not the account workflow. It runs automatically on `main` when its workflow, preflight script, MEXC public adapter or dependency manifest changes; manual dispatch remains available as an explicit diagnostic option. It shares the paper writer's non-cancelling concurrency group to avoid competing bursts of public API calls. It does not run on a recurring schedule and is not a prerequisite for each daily account decision. The retired Polymarket paper-state workflow has been removed. No exchange orders are ever sent; all executions remain simulated from public MEXC data. See [ACTIVE_PAPER_ACCOUNT.md](ACTIVE_PAPER_ACCOUNT.md) for the account identity and operating boundary.


## Current provider selection

**Selected provider: MEXC Futures**

The ordered technical search was Polymarket Perps → MEXC → Bitget. MEXC was the first provider to pass the public-data qualification.

| Provider | Result |
|---|---|
| MEXC Futures | **Selected — technical public-data pass** |
| Polymarket Perps | Not ready — fee coverage was missing for four reported categories and sampled public order books failed |
| Bitget | Curiosity-only diagnostic passed; it did not replace MEXC |

### MEXC verification

**Pre-restoration supported-host public preflight (2026-11-18, automatic run #16)** used `https://api.mexc.com` with `/api/v1/contract/detail/country` and reported:

- 690 raw instrument records; **684 active cross-margin perpetuals** returned by that endpoint and accepted by the adapter's active/cross/API-allowed filter.
- **612 active USDT/USDT quote-and-settlement contracts** in that endpoint's paper-execution subset.
- 1,166 all-market ticker rows; **zero unmatched symbols** across all 684 returned active cross-margin instruments.
- Sampled order-book, daily-candle and funding-history checks passed across commodity, crypto, equity and unclassified categories.
- No credentials or private endpoints were used; no wallet or orders were used.

[Pre-restoration MEXC preflight run #16](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44256962226) · `TECHNICAL_PUBLIC_DATA_PASS`

This was a successful coverage check for the **country-detail route**, not the broad research-universe baseline. The adapter has now been restored to the default `/api/v1/contract/detail` route on the supported hostname. A new automatic preflight must establish the current broad-universe count; do not carry 684 or 612 forward as current counts.

**Historical universe observations:** run [43977889004](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43977889004) on 2026-11-16 used the former `https://contract.mexc.com` host with the default `/api/v1/contract/detail` route and reported 1,143 active cross-margin / 1,061 USDT contracts. MEXC discontinued that hostname on 2026-01-19, so this remains a historical observation, not a current supported-host count. On 2026-11-18 the implementation moved to `https://api.mexc.com` but selected `/detail/country`, producing the separate 684 / 612 observation in run #16. The adapter now uses the supported hostname with the default `/api/v1/contract/detail` route. Do not assume the new count will equal either historical observation; use the fresh automatic preflight as the current source of truth.

The broad research discovery route is intentionally not an individual-account eligibility check. The Q research universe must not be silently narrowed by country-configured execution metadata. Any live-promotion review can separately verify account eligibility and applicable exchange restrictions at that time.

## Research universe and currency

The research ranking includes **every active MEXC linear perpetual with per-instrument cross-margin support**, across all quote/settlement currencies and every asset category. MEXC's positionOpenType values 2 or 3 indicate cross-margin capability; isolated-only, inactive and retired/settled contracts are excluded. Unknown category labels remain eligible as unclassified. The last reported broad-route observation was **1,143 cross-margin perpetuals** across settlements on 2026-11-16, but it used the now-discontinued hostname. The current supported-host broad-route count is pending the new automatic preflight.

The last reported broad-route execution subset was **1,061 active USDT-quoted and USDT-settled contracts** on the same historical run; the current supported-host count is pending fresh verification. Non-USDT contracts remain in the research Q rankings but are labelled research-only for execution. Do not mix USDC, USD1, BTC or other collateral and quote-currency P&L into USDT NAV without a separately validated point-in-time conversion and settlement model.

MEXC contract volume is denominated in contracts. Convert it using each instrument's contractSize only for validated linear USDT execution; use volUnit, minVol, maxVol, priceUnit and its fee rates. Public order-book quantities and Kline volume are also in contract units. amount24 and daily amount are denominated in the instrument's quote currency, not universally USDT; never mix USDC, USD1 or other quote turnover into USDT comparisons. See the [current MEXC Futures API integration guide](https://www.mexc.io/api-docs/futures/integration-guide) and [contract-information endpoint](https://www.mexc.io/api-docs/futures/market-endpoints/get-contract-info). MEXC announced that Futures REST requests must use `https://api.mexc.com`; support for the former `https://contract.mexc.com` host ended on 2026-01-19. The client now uses the default `/api/v1/contract/detail` route on the supported hostname and a 1.5-second minimum interval between requests.

## Implemented components

- Exchange-neutral EMA/semi-cycle/CPC, Trend, Noise, Q, B and Wilder ATR calculations.
- Cross-sectional positive-Q long and negative-Q short rankings, with research membership separated from execution eligibility.
- Public MEXC adapter for contract metadata, bulk ticker, order book, daily Klines and funding history.
- Contract-multiplier-aware quantity conversion, book VWAP fills, taker fees and impact caps.
- Incremental, provider-isolated market-data persistence: up to 365 days of initial daily history, in resumable batches of 150 instruments, then only missing daily candles. Five-minute ticker snapshots are stored separately.
- USDT paper-account accounting primitives for cash, realized/unrealized P&L, fees, funding, ATR stops, five-minute equity snapshots, combined daily drawdown control and sample-gated performance metrics.
- Margin-aware default sizing: 50% NAV margin per leg at 2× leverage, targeting 1× NAV notional per leg and 2× total gross notional.
- Daily full-book refresh: close both legs and reopen both selected legs after each completed daily candle, even when the same contracts remain selected; model and report every close/open fee and slippage charge.
- Simple per-leg sizing: target about 1× current NAV notional per leg (about 50 USDT each at the 50 USDT seed), independently rounded down to venue lot sizes; report the remaining dollar imbalance without a percentage tolerance gate.
- After the pre-rebalance daily risk check passes, every successful daily pair decision resets the combined drawdown window to post-rebalance NAV. The separate daily-return metric remains anchored to UTC-day opening NAV. A latched emergency stop or pending flatten cannot be cleared by this reset.
- Application-level append-only event journal and GitHub state publisher with remote hash-chain validation, exact read-back and fast-forward-only updates.

Key files: src/trend_quality/mexc_api.py, mexc_paper.py, mexc_portfolio.py, market_data_store.py and scripts/mexc_paper_cycle.py.

## Operating state and account safety gate

The single MEXC workflow in [.github/workflows/mexc-paper-cycle.yml](.github/workflows/mexc-paper-cycle.yml) runs a daily research/portfolio refresh plus five-minute monitoring and retry passes. After each completed UTC daily candle it recalculates Q once, freezes the daily shortlist, closes both held legs and opens both selected legs again—even when the symbols are unchanged. Each leg independently targets about 1× NAV notional, rounded down to its own MEXC lot size; the resulting dollar imbalance is reported without a 0.5%-of-NAV rejection gate. If a full close/reopen cannot be simulated, the existing paper state remains intact and five-minute workflow invocations retry the same frozen shortlist (up to five candidate pairs per invocation) without recalculating Q. The first successful rebuild clears the pending signal; no more portfolio construction occurs until the next daily candle. Five-minute passes otherwise monitor equity, funding and risk exits. See [OPERATING_MODEL.md](OPERATING_MODEL.md).

**Historical full daily-close MEXC run (2026-11-16, retired hostname):** [43984343892](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984343892) completed successfully with 1,143 active cross-margin perpetuals, 273,160 stored daily-candle rows, 93 instruments completed in the final bootstrap batch, zero bootstrap instruments remaining, zero missing tickers, zero missing latest completed bars and zero reported API failures. The history-coverage gate passed. Q rankings were recalculated. The routine follow-up snapshot run [43984739626](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984739626) reported PORTFOLIO_SNAPSHOT_ONLY, daily_decision_due=false and q_rankings_recalculated=false. These are historical public-data workflow checks from the retired hostname, not current supported-host universe or portfolio-performance evidence. After the restored default endpoint passes preflight, the next eligible full daily cycle must establish fresh broad-universe history coverage and Q rankings.

**Active forward generation: 50 USDT paper-only.** The v3 account `mexc-usdt-forward-50usdt-v3` / strategy `trend-quality-daily-cross-sectional-v3-50usdt` passed the recovery-probe/fresh-checkout gate and initialized on 2026-11-18 with 50 USDT. It opened a simulated VSTOCK_USDT long / BILL_USDT short pair. The latest persisted snapshot linked in [PAPER_PERFORMANCE_REPORT.md](PAPER_PERFORMANCE_REPORT.md) is the current source for NAV, marks and positions; its latest successful persisted snapshot is run #75, [44239954487](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44239954487). The former $1 and $10 account generations remain immutable archived history and are not selected by the active MEXC workflow or report. Paper-state writing is enabled by default; set the Actions variable `PAPER_STATE_WRITE_ENABLED=false` to pause writes.

The 25% emergency stop is a combined portfolio daily drawdown stop, measured from the highest observed NAV in the UTC day; it closes both simulated legs. It does not cap lifetime MDD. Default leverage is 2× on 50% NAV margin per leg (1× NAV notional each, 2× combined gross). Five-minute monitoring is sampled and cannot guarantee detection at the exact threshold between invocations.

Historical replay is not implemented. The active $50 account has two open simulated positions and zero closed trades; it has only just begun collecting forward observations. Daily performance statistics remain gated by insufficient history, so no meaningful CAGR, Sharpe, Sortino, drawdown history or profitability claim is available.

## Safety boundary

Paper research only. No live orders, Testnet, private account endpoints, exchange credentials, wallet, proxy/VPN or paid infrastructure. All fills from the simulator are hypothetical. Five-minute monitoring is sampled, not continuous; missed runs and delayed stop detection must be reported.

## Development

Python 3.12+.

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
python scripts/mexc_public_preflight.py
```

The preflight is a live, read-only public-data check. It never accesses an account or submits an order.

See [STATUS](STATUS.md), [master implementation directive](IMPLEMENTATION_PROMPT.md), [implementation plan](IMPLEMENTATION_PLAN.md), [decisions](IMPLEMENTATION_DECISIONS.md), [prompt refinement log](PROMPT_REFINEMENT_LOG.md) and [runbook](RUNBOOK.md).


## Forward-paper seed and activation

The active forward seed is 50 USDT. At 50% NAV margin per leg and 2× leverage, the nominal target is approximately 50 USDT notional per leg (about 100 USDT combined gross exposure before fees and valuation drift). Earlier minimum-order diagnostics measured $1 and $10 per-leg thresholds; those measurements are not extrapolated to $50. The current v3 account has opened a feasible pair using venue lot sizes and public depth. The $1 and $10 generations remain archived in the append-only event history; they are not active or included in the current report. Only the MEXC paper workflow writes this portfolio's state; the preflight workflow is read-only and the retired Polymarket workflow file has been removed. The MEXC publisher still validates the full hash chain, rejects forks and conflicting writes, uses fast-forward-only commits and verifies exact remote read-back. The `state` branch is intentionally unprotected, so repository users with write access can still rewrite or delete history outside the application publisher; this residual risk is documented in OPERATING_MODEL.md.

See the [paper-state operating guide](STATE_PROTECTION_SETUP.md) for the writer switch, recovery handshake and integrity limitations.

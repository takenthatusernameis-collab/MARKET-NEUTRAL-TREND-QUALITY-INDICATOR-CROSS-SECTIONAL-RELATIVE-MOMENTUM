# Market-Neutral Trend-Quality Indicator — Cross-Sectional Relative Momentum

A paper-only research system for the Sepiashvili Trend-Quality Indicator (Q), ranking active cross-margin perpetual contracts and eventually maintaining one long and one short. The indicator engine is exchange-neutral; the selected market-data adapter is **MEXC Futures, USDT-settled cross-margin perpetuals**.

## Current provider selection

**Selected provider: MEXC Futures**

The ordered technical search was Polymarket Perps → MEXC → Bitget. MEXC was the first provider to pass the public-data qualification.

| Provider | Result |
|---|---|
| MEXC Futures | **Selected — technical public-data pass** |
| Polymarket Perps | Not ready — fee coverage was missing for four reported categories and sampled public order books failed |
| Bitget | Curiosity-only diagnostic passed; it did not replace MEXC |

### MEXC verification

The hosted-runner public API preflight (run 43977889004) established:

- 1,152 instruments discovered; **1,143 active cross-margin perpetuals** across all settlement types.
- **1,061 active USDT/USDT quote-and-settlement contracts** are the subset eligible for the current homogeneous USDT paper account.
- 1,161 bulk ticker rows returned, with no missing ticker for any of the 1,143 research instruments.
- Sampled ticker, book, daily-candle and funding-history requests passed for every reported category: commodity, crypto, equity, FX and unclassified.
- Settlement groups: 1,061 USDT/USDT, 41 USDC/USDC, 31 USD1/USD1 and 10 USD-quoted coin-settled contracts.
- Sampled daily candles opened at 00:00 UTC.
- No credentials or private endpoints were used; no orders were submitted.

[Successful all-settlement MEXC public API preflight](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43977889004)

Bitget's independent curiosity run found 886 active cross-margin USDT perpetuals and passed its sampled public-data checks. This did not change the ordered selection: MEXC remains selected.

Technical API reachability does **not** establish individual account or Romanian derivatives-product eligibility. That remains unconfirmed.

## Research universe and currency

The research ranking includes **every active MEXC linear perpetual with per-instrument cross-margin support**, across all quote/settlement currencies and every asset category. MEXC's positionOpenType values 2 or 3 indicate cross-margin capability; isolated-only, inactive and retired/settled contracts are excluded. Unknown category labels remain eligible as unclassified. The live public discovery returned **1,143 cross-margin perpetuals** across settlements.

The current single-currency paper execution/account subset is **1,061 active USDT-quoted and USDT-settled contracts**. Non-USDT contracts remain in the research Q rankings but are labelled research-only for execution. Do not mix USDC, USD1, BTC or other collateral and quote-currency P&L into USDT NAV without a separately validated point-in-time conversion and settlement model.

MEXC contract volume is denominated in contracts. Convert it using each instrument's contractSize only for validated linear USDT execution; use volUnit, minVol, maxVol, priceUnit and its fee rates. Public order-book quantities and Kline volume are also in contract units. amount24 and daily amount are denominated in the instrument's quote currency, not universally USDT; never mix USDC, USD1 or other quote turnover into USDT comparisons. See the [official MEXC Futures API documentation](https://mexcdevelop.github.io/apidocs/contract_v1_en/).

## Implemented components

- Exchange-neutral EMA/semi-cycle/CPC, Trend, Noise, Q, B and Wilder ATR calculations.
- Cross-sectional positive-Q long and negative-Q short rankings, with research membership separated from execution eligibility.
- Public MEXC adapter for contract metadata, bulk ticker, order book, daily Klines and funding history.
- Contract-multiplier-aware quantity conversion, book VWAP fills, taker fees and impact caps.
- Incremental, provider-isolated market-data persistence: up to 365 days of initial daily history, in resumable batches of 150 instruments, then only missing daily candles. Five-minute ticker snapshots are stored separately.
- USDT paper-account accounting primitives for cash, realized/unrealized P&L, fees, funding, ATR stops, five-minute equity snapshots, combined daily drawdown control and sample-gated performance metrics.
- Margin-aware default sizing: 50% NAV margin per leg at 2× leverage, targeting 1× NAV notional per leg and 2× total gross notional.
- Application-level append-only event journal and GitHub state publisher with remote hash-chain validation, exact read-back and fast-forward-only updates.

Key files: src/trend_quality/mexc_api.py, mexc_paper.py, mexc_portfolio.py, market_data_store.py and scripts/mexc_paper_cycle.py.

## Operating state and account safety gate

The single five-minute workflow in [.github/workflows/mexc-paper-cycle.yml](.github/workflows/mexc-paper-cycle.yml) now has two explicit modes, selected by the latest completed UTC daily candle. The first invocation after a new daily close performs the full market-data refresh, one bounded bootstrap/incremental batch, Q rankings and (only when the paper-state gate is open) the daily portfolio decision. Other five-minute invocations are portfolio-monitoring snapshots only: no universe refresh, Q recalculation, ATR decision or ordinary rebalance. The authoritative specification is [OPERATING_MODEL.md](OPERATING_MODEL.md).

**Latest full daily-close MEXC run:** [43984343892](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984343892) completed successfully with 1,143 active cross-margin perpetuals, 273,160 stored daily-candle rows, 93 instruments completed in the final bootstrap batch, zero bootstrap instruments remaining, zero missing tickers, zero missing latest completed bars and zero reported API failures. The history-coverage gate passed. Q rankings were recalculated. The routine follow-up snapshot run [43984739626](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984739626) reported PORTFOLIO_SNAPSHOT_ONLY, daily_decision_due=false and q_rankings_recalculated=false. These are public-data workflow checks, not portfolio-performance evidence.

**The 1 USDT forward paper account is initialized and has been independently restored from the event branch.** It is currently flat because no pair passed all minimum-size and execution constraints at this capital level. The MEXC workflow enables paper-state writing by default; set the repository Actions variable `PAPER_STATE_WRITE_ENABLED=false` to pause it. The ledger is paper-only and no real exchange orders or private endpoints are used.

The 25% emergency stop is a combined portfolio daily drawdown stop, measured from the highest observed NAV in the UTC day; it closes both simulated legs. It does not cap lifetime MDD. Default leverage is 2× on 50% NAV margin per leg (1× NAV notional each, 2× combined gross). Five-minute monitoring is sampled and cannot guarantee detection at the exact threshold between invocations.

CI on [run 43984752103](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43984752103) passed Ruff and 141 tests. This is implementation validation only. Historical replay is not implemented, and no realized forward equity curve, trade count, return, CAGR, Sharpe, drawdown or profitability claim is available until the paper account has passed its persistence gate and accumulated actual observations.

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

The initialized forward seed is 1 USDT. At 50% NAV margin per leg and 2× leverage, the nominal target is 1 USDT notional per leg; MEXC minimum contract sizes currently leave the account flat. The state branch is intentionally unprotected, so no administrator route or `STATE_PROTECTION_TOKEN` is required. The MEXC workflow and retired manual Polymarket diagnostic share repository-wide concurrency group `paper-state-branch-single-writer`. The publisher still validates the full hash chain, rejects forks and conflicting writes, uses fast-forward-only commits and verifies exact remote read-back. Because the branch is unprotected, repository users with write access could still rewrite or delete history outside the publisher; this residual risk is documented in OPERATING_MODEL.md.

See the [paper-state operating guide](STATE_PROTECTION_SETUP.md) for the writer switch, recovery handshake and integrity limitations.

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

The hosted-runner public API preflight established:

- 1,152 instruments discovered; 1,143 cross-margin perpetuals across all settlement types.
- **1,061 active cross-margin USDT-settled perpetuals** selected for the homogeneous USDT research account.
- 1,161 bulk ticker rows returned, with no missing ticker for the 1,061 selected instruments.
- Instrument precision, sampled order books, daily candles and funding-history reads passed across crypto, equities, commodities, FX and unclassified instruments.
- Sampled daily candles opened at 00:00 UTC.
- No credentials or private endpoints were used; no orders were submitted.

[Successful MEXC API and daily-candle boundary preflight](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43976183941)

Bitget's independent curiosity run found 886 active cross-margin USDT perpetuals and passed its sampled public-data checks. This did not change the ordered selection: MEXC remains selected.

Technical API reachability does **not** establish individual account or Romanian derivatives-product eligibility. That remains unconfirmed.

## Research universe and currency

Use every active MEXC linear perpetual with cross-margin support and both quote and settlement currency USDT. MEXC's positionOpenType values 2 or 3 indicate cross-margin capability; isolated-only contracts are excluded. Do not require any particular asset category. Unknown category labels remain eligible as unclassified.

Other settlement currencies are retained as provider metadata but excluded from the USDT paper account. Do not mix USDC, USD1, coin-margined or other collateral into USDT NAV.

MEXC contract volume is denominated in contracts. Convert it using each instrument's contractSize; use volUnit, minVol, maxVol, priceUnit and its fee rates for sizing and paper execution. Public order-book quantities and Kline volume are also in contract units. amount24 and daily amount supply USDT turnover; do not confuse turnover with contract volume. See the [official MEXC Futures API documentation](https://mexcdevelop.github.io/apidocs/contract_v1_en/).

## Implemented components

- Exchange-neutral EMA/semi-cycle/CPC, Trend, Noise, Q, B and Wilder ATR calculations.
- Cross-sectional positive-Q long and negative-Q short rankings, with research membership separated from execution eligibility.
- Public MEXC adapter for contract metadata, bulk ticker, order book, daily Klines and funding history.
- Contract-multiplier-aware quantity conversion, book VWAP fills, taker fees and impact caps.
- Incremental, provider-isolated market-data persistence: up to 365 days of initial daily history, in resumable batches of 150 instruments, then only missing daily candles. Five-minute ticker snapshots are stored separately.
- USDT paper-account accounting primitives for cash, realized/unrealized P&L, fees, funding, ATR stops, daily NAV and sample-gated performance metrics.
- Immutable event journal and GitHub state publisher with remote hash-chain validation.

Key files: src/trend_quality/mexc_api.py, mexc_paper.py, mexc_portfolio.py, market_data_store.py and scripts/mexc_paper_cycle.py.

## Operating state and account safety gate

The five-minute workflow is configured in [.github/workflows/mexc-paper-cycle.yml](.github/workflows/mexc-paper-cycle.yml). It collects public market data, incrementally updates history and publishes Q rankings to the separate market-data branch.

**The forward paper account has not been initialized.** The state branch is currently unprotected and the repository has no rulesets. Therefore the workflow explicitly sets PAPER_STATE_WRITE_ENABLED=false. It will not open, close or carry simulated positions, publish financial state events or claim portfolio NAV. The runtime protection check also fails closed.

Account initialization requires server-side state-branch protection, force-push/deletion restrictions, restricted writers, and a real publisher/recovery test. The portfolio accounting code is implemented and unit-tested, but the durable persistence/forward-operation gate remains closed.

Historical replay is not implemented. No equity curve, trade count, return, CAGR, Sharpe, drawdown or profitability claim is available until actual persisted paper-account observations exist.

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

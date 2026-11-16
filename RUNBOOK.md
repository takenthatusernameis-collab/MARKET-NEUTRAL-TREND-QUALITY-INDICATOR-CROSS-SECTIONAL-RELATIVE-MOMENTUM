# MEXC Trend-Quality Research Runbook

## Current provider and mode

- Selected provider: MEXC Futures.
- Strategy universe: active linear USDT-settled cross-margin perpetuals.
- Technical API qualification: passed from GitHub-hosted runner.
- Account/derivatives eligibility for a Romanian user: not independently confirmed.
- Mode: public market-data collection and paper research only.
- Live orders, Testnet, private endpoints, credentials, wallets, proxy/VPN and paid infrastructure are prohibited.

Provider selection history: Polymarket Perps → MEXC → Bitget. Polymarket did not pass fee/book coverage. MEXC was the first technical pass. Bitget's later curiosity check found 886 active cross-margin USDT perps but does not change the MEXC selection.

## Public API preflight

Run:

```bash
python -m pip install -e .
python scripts/mexc_public_preflight.py
```

The preflight reads only official public MEXC Futures endpoints. It discovers contract details, bulk tickers, server time, sampled depth, daily candles and funding history. It emits a JSON report and returns nonzero if mandatory technical checks fail. It does not query account endpoints or place orders.

Successful preflight and UTC daily boundary evidence: [GitHub Actions run 43976183941](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43976183941).

## Universe and market data

- Filter each instrument, not the exchange by asset class.
- Include only active perpetuals with cross-margin available, quoteCoin=USDT and settleCoin=USDT.
- Use positionOpenType=2 or 3; exclude isolated-only, inactive and non-USDT settlement contracts from the USDT strategy account.
- Preserve unknown asset categories.
- Read the bulk ticker endpoint once each cycle.
- Convert contract-count depth and Kline volume using contractSize. Do not mistake amount24 or Kline amount for contract volume; these are USDT turnover.
- Use volUnit, minVol, maxVol, priceUnit, contractSize and fee fields from the instrument record.

The MEXC workflow is scheduled every five minutes. Initial history bootstrap is up to 365 days, 150 instruments per default batch; later calls begin after the last stored completed daily candle. New listings get a one-time resumable backfill. Only completed Day1 bars may feed Q. Representative sampled bars opened at 00:00 UTC; every timestamp still requires validation.

Public market data and ranking reports belong on the market-data branch, not the financial event branch. The first workflow run completed 150 bootstrap instruments and left 911 pending but its market-data commit was blocked by the repository ignore rule. The workflow now force-adds the data directory. Confirm a subsequent successful commit before describing market data as durably persisted.

## Paper-account gate

**Do not enable paper portfolio writes yet.**

The state branch is currently unprotected and repository rulesets are absent. The MEXC workflow must keep PAPER_STATE_WRITE_ENABLED=false. This allows public market-data updates and Q ranking but no portfolio initialization, simulated position transition, financial event commit or NAV claim.

Before considering the writer flag:
1. Configure server-side state branch protection or a repository ruleset.
2. Prohibit force-push and branch deletion; restrict writers and enforce protections for administrators.
3. Verify the actual branch-protection API response from the workflow's token.
4. Run a real append, duplicate/idempotency and conflict test.
5. Rebuild the paper state from immutable events and verify chain integrity.
6. Only after full market-data, execution, accounting and stop/funding tests pass, consider initializing the 100 USDT account.

The repository is public. Every state and market-data artifact is public and permanent. Never commit personal identifiers, secrets or private account information.

## Data and funding failures

- Preserve the last verified market-data store and manifest.
- Mark a cycle PARTIAL or FAILED when any required data is missing or stale.
- Do not rank on incomplete or corrupted data as if coverage were complete.
- Missing bid/ask means non-executable, not a fabricated market price.
- Missing funding history or settlement mark remains unresolved; never substitute zero or a stale price.
- Apply funding only for a position open immediately before the published settleTime, once only.
- Do not redownload full history every five-minute cycle.
- Delisting must be confirmed from instrument lifecycle fields; a missing ticker alone does not mean delisted.
- Stop routine updates for explicitly retired/settled contracts but preserve their historical data.

## Execution and sampled stops

- Simulated buys consume asks; sells consume bids; convert contract depth to base units before the fill model.
- Use current public depth, fresh timestamp, contract precision and current fee rate.
- Apply maximum modeled impact. Reject stale or one-sided books.
- Five-minute monitoring is sampled and can miss intra-interval crossings. A stop must never be filled retroactively at its trigger price; use detection-time book conditions and report missed-run delays.
- No actual exchange order calls are allowed.

## Performance and reporting

The MEXC cycle emits machine-readable and human-readable research reports with universe counts, history bootstrap progress, gaps, Q rankings, exclusions and execution eligibility. If a durable paper account is later enabled, report cash, NAV, realized/unrealized P&L, fees, confirmed/unresolved funding, positions, gross/net exposure, stops, trade statistics and daily equity curve.

Never show unavailable CAGR, Sharpe, Sortino or drawdown statistics as zero. State the required sample window and reason. Currently no forward portfolio NAV or profitability result exists.

## Historical replay

Historical replay is not implemented. Do not describe current live-data ingestion or unit tests as a backtest. A future replay must reconstruct a point-in-time universe, preserve delistings/survivorship limitations, use only completed daily bars, model costs/funding and sampled-stop delays, and reconcile cash/NAV independently.

## Recovery

- Restore market-data manifest and compressed candle/snapshot partitions.
- Verify provider identity before loading; never merge MEXC data into a Polymarket/Bybit manifest.
- Verify timestamps, duplicates, gaps, monotonic cursors and gzip integrity.
- For any future paper account, restore the immutable state event chain first, validate every batch hash and idempotency key, then rebuild the transactional SQLite projection.
- If any publisher/state commit fails, stop portfolio transitions. Do not force-push or rewrite prior events.

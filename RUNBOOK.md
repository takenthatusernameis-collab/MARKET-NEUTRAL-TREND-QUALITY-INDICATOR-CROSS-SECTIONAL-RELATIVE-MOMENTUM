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

The preflight reads only official public MEXC Futures endpoints through `https://api.mexc.com` (current server-time, `/api/v1/contract/detail`, bulk tickers, sampled depth, daily candles and funding history). The former `contract.mexc.com` Futures REST host was discontinued on 2026-01-19. The shared public client waits at least 1.5 seconds between requests and uses long exponential backoff after 429 / code 510 responses. It discovers contract details, bulk tickers, server time, sampled depth, daily candles and funding history. It emits a JSON report and returns nonzero if mandatory technical checks fail. It does not query account endpoints or place orders.

Successful preflight and UTC daily boundary evidence: [GitHub Actions run 43976183941](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/43976183941).

## Universe and market data

- Filter each instrument, not the exchange by asset class.
- The Q research universe includes every active perpetual with per-instrument cross-margin available, across all quote/settlement currencies and asset categories. Preserve unknown asset categories.
- Use positionOpenType=2 or 3; exclude isolated-only, inactive and retired/settled contracts.
- The current single-currency USDT paper execution subset is restricted to quoteCoin=USDT and settleCoin=USDT. Non-USDT perps remain research-only until quote/collateral conversion, inverse contract value and settlement P&L are validated.
- Read the bulk ticker endpoint once each cycle.
- Convert contract-count depth and Kline volume using contractSize for the supported USDT linear execution path. For other settlements, retain contract counts and native quote turnover; never label non-USDT turnover as USDT.
- Use volUnit, minVol, maxVol, priceUnit, contractSize and fee fields from the instrument record.

The MEXC workflow is scheduled every five minutes, with an additional daily-close backup attempt at 00:01 UTC. Initial history bootstrap is up to 365 days, 150 instruments per default batch; later calls begin after the last stored completed daily candle. New listings get a one-time resumable backfill. Only completed Day1 bars may feed Q. Representative sampled bars opened at 00:00 UTC; every timestamp still requires validation.

Public market data and ranking reports belong on the market-data branch, not the financial event branch. The first workflow run completed 150 bootstrap instruments and left 911 pending but its market-data commit was blocked by the repository ignore rule. The workflow now force-adds the data directory. Confirm a subsequent successful commit before describing market data as durably persisted.

## Paper-account state and single-writer mode

The forward account seed is 50 USDT. The only active account ID is `mexc-usdt-forward-50usdt-v3`, with strategy ID `trend-quality-daily-cross-sectional-v3-50usdt`. The MEXC workflow defaults `PAPER_STATE_WRITE_ENABLED` to true; set the repository Actions variable to the literal string `false` to pause all account-state transitions. A protected branch, repository ruleset, administrator intervention or `STATE_PROTECTION_TOKEN` is not required. The $1 and $10 generations are archived immutable history, not active accounts.

The MEXC paper workflow is the only active portfolio-state writer and uses the `paper-state-branch-single-writer` concurrency group with `cancel-in-progress: false`. The retired Polymarket paper-state workflow was removed from `.github/workflows`; the remaining MEXC public preflight is read-only and queued behind the paper workflow. It runs automatically on `main` when its workflow, preflight script, MEXC public adapter or dependency manifest changes; manual dispatch remains available for an explicit diagnostic. It has no recurring schedule. The publisher remains append-only at the application level: it verifies the full remote hash chain, rejects forks/orphans/duplicate identifiers and different content at an existing path, commits with a normal non-forced fast-forward update and verifies exact remote read-back after writes and idempotent retries. Local recovery follows parent hashes rather than venue timestamps. A non-fast-forward conflict or failed verification must stop the run; never force-push or claim unpersisted account state as durable.

The $50 v3 account has completed the two-stage recovery handshake: a non-financial recovery probe was published, a later fresh checkout verified it and the full chain, then a distinct 50 USDT initialization event was appended and restored on a follow-up run. A future new account generation must repeat this handshake and must be explicitly authorized; routine manual dispatches use the existing v3 account rather than creating a new generation.

**Residual risk:** the branch is intentionally unprotected. A repository user with write/admin permissions can rewrite or delete history outside the publisher; application-level chain validation cannot prevent privileged manual tampering. The repository is public and all committed ledger/data is public and permanent.

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

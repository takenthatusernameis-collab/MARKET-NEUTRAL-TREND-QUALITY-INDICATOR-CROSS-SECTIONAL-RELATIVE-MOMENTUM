# Runbook

## Bootstrap
1. Install Python 3.12+.
2. Run `python -m pip install -e '.[dev]'`.
3. Run `pytest`.
4. Run `python -m trend_quality.cli public-api-smoke`.
5. Do not enable paper account workflows while status is BOOTSTRAPPING.

## Public API smoke test
Uses only Bybit Global public endpoints:
- /v5/market/time
- /v5/market/instruments-info (first page, with pagination implementation available in client)

No credentials or order endpoints are used.

## Bybit HTTP 403 / regional restriction
- Inspect the GitHub Actions runner-region log and the bounded HTTP denial diagnostics.
- Bybit documentation identifies US/mainland-China source IPs as restricted; a 403 can also have other causes, so retain the response body/header evidence when available.
- Do not retry a geographic restriction indefinitely, use a VPN/proxy, rotate API hosts, or switch exchanges.
- Leave automated paper transitions disabled until a public unauthenticated Bybit request succeeds from an approved runner location.
- A user-installed self-hosted runner on permitted hardware/network is a possible no-paid route, but requires explicit user setup and always-on availability.

## Data failure
- Preserve last verified data and account state.
- Mark the run PARTIAL or FAILED.
- Do not rank on an incomplete universe.
- Do not backfill missing fills at historical prices.
- Continue risk observation where possible.

## Delayed hourly monitoring
- Restore last durable event batch.
- Fetch all missing completed hourly candles.
- Process missed intervals chronologically.
- If a stop was crossed, execute at current detection-time paper market data.
- Record the delay and any uncertainty.
- Never backdate the fill.

## Persistence failure
- Do not declare the state durable.
- Do not process further portfolio transitions.
- On next run, reconcile the last committed event batch and idempotency keys.
- Rebuild SQLite from immutable event batches.

## Reset
No automated reset is available in bootstrap stage. Any future reset must be explicitly authorized, create a new account ID and preserve the previous account history.

# Runbook

## Bootstrap
1. Install Python 3.12+.
2. Run `python -m pip install -e '.[dev]'`.
3. Run `pytest`.
4. Run `python -m trend_quality.cli public-api-smoke`.
5. Do not enable paper account workflows while status is BOOTSTRAPPING or RED-TEAM NO-GO.

## Public API smoke test
Uses only Bybit Global public endpoints:
- /v5/market/time
- /v5/market/instruments-info (first page, with pagination implementation available in client)

No credentials or order endpoints are used.

## Bybit HTTP 403 / regional restriction
- Inspect the GitHub Actions runner-region log and the bounded HTTP denial diagnostics.
- Bybit documentation identifies US/mainland-China source IPs as restricted; a 403 can also have other causes, so retain the response body/header evidence when available.
- Do not retry a geographic restriction indefinitely, use a VPN/proxy, rotate API hosts, or disguise the request source.
- The user explicitly requested replacement-exchange evaluation. Do not silently substitute a provider: every candidate must pass the Section 12.5 qualification gates in `IMPLEMENTATION_PROMPT.md` before any adapter migration.
- Crypto.com is currently NOT_READY: only six USD-quoted crypto perpetuals were found; the funding-history request returned API code 40004 for the tested identifiers; USDT quote compatibility and jurisdiction/collateral gates failed or remain unverified.
- Leave all automated paper transitions disabled until one provider has passed the complete public-data, funding, instrument precision and jurisdiction gates and the integrated portfolio/accounting/recovery acceptance tests pass.
- A self-hosted runner is not a default workaround. Do not create or configure one without explicit setup authorization and verification that its source network is permitted.

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

## State branch integrity and privacy

- The repository is public. Treat every state-branch file as public and permanent.
- Do not write credentials, personal identifiers, confidential user data or private account records to this repository.
- Before account initialization, verify GitHub server-side protection or a repository ruleset for the `state` branch, disallowing force-push/deletion and restricting writers.
- The state publisher must verify the full remote event chain and append only when the submitted batch extends its unique tip.
- The current branch is reported unprotected and no repository rulesets are present. Therefore, do not publish financial event batches or initialize an account yet.
- A mocked publisher test is not a real GitHub API publishing or restore test.

## Persistence failure
- Do not declare the state durable.
- Do not process further portfolio transitions.
- On next run, reconcile the last committed event batch and idempotency keys.
- Rebuild SQLite from immutable event batches.

## Reset
No automated reset is available in bootstrap stage. Any future reset must be explicitly authorized, create a new account ID and preserve the previous account history.

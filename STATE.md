# Durable Paper Research State

This branch is reserved for immutable, append-only paper-account event batches and their recovery metadata.

- Source code and human-facing reports belong on `main`.
- The authoritative event history is appended under `events/YYYY/MM/<run_id>.json`.
- Every batch must pass its SHA-256 hash-chain verification before publication.
- Every update must be a normal fast-forward commit.
- Force-pushes, event deletion, silent corrections and rewriting previous accounting records are prohibited.
- SQLite is a rebuildable projection; it is not the sole durable source of truth.

## Current active forward-paper generation

- **Only active account:** `mexc-usdt-forward-50usdt-v3`
- **Strategy generation:** `trend-quality-daily-cross-sectional-v3-50usdt`
- **Initial capital / starting cash:** 50 USDT
- **Initialization event:** `events/2026/11/account-init-1794976007111.json`
- **Latest persisted portfolio snapshot:** `events/2026/11/snapshot-1794980235935.json` (2026-11-18 05:37:15.935 UTC; NAV 49.66302776 USDT; two simulated positions).
- The former 1 USDT `mexc-usdt-forward` and 10 USDT `mexc-usdt-forward-10usdt-v2` generations remain preserved as immutable historical records. They are archived, not active; their records are not deleted, edited, pooled with the active NAV or restored by the v3 workflow.

The active MEXC cycle and standalone performance report on `main` select only the v3 account and strategy identifiers. The full global event chain remains the integrity boundary for any read, append or report. Update this metadata only after a successful state append; do not edit the event records.

All account activity is forward paper simulation only. The workflow uses public MEXC market data and simulated fills; it does not access private account endpoints or submit live exchange orders.

# Durable Paper Research State

This branch is reserved for immutable, append-only paper-account event batches and recovery metadata.

- Source code and human-facing reports belong on \`main\`.
- The authoritative event history is appended under \`events/YYYY/MM/<run_id>.json\`.
- Every batch must pass its SHA-256 hash-chain verification before publication.
- Every update must be a normal fast-forward commit.
- Force-pushes, event deletion, silent corrections and rewriting previous accounting records are prohibited.
- SQLite is a rebuildable projection; it is not the sole durable source of truth.

## Current active forward-paper generation

- **Only active account:** \`mexc-usdt-forward-100usdt-v4\`
- **Strategy generation:** \`trend-quality-daily-cross-sectional-v4-100usdt\`
- **Authorized initial capital / starting cash:** **100 USDT**
- **Financial account state:** not initialized yet; only the non-financial recovery probe has been published.
- **Recovery probe:** \`events/2026/11/state-probe-1795004591521.json\` (workflow run [#91](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/runs/44303345661); success; fresh-checkout verification is required on the next workflow invocation).
- **Daily-decision watermark:** unset for v4. The next successful initialization run may process the latest genuinely completed UTC daily bar if full-history, ticker, book-depth and two-sided simulated execution gates pass.
- **Latest v4 portfolio snapshot:** none yet.
- **Archived generations:** the former 50 USDT v3, 10 USDT v2 and 1 USDT generations remain immutable history. Their financial state is not restored, pooled into v4 NAV or used in v4 performance calculations.

The active MEXC cycle and compact status report on \`main\` select only the v4 account and strategy identifiers. The full global event chain remains the integrity boundary for any read, append or report. Update this metadata after a successful state append; never edit event records.

All account activity is forward paper simulation only. The workflow uses public MEXC market data and simulated fills; it does not access private account endpoints or submit live exchange orders.

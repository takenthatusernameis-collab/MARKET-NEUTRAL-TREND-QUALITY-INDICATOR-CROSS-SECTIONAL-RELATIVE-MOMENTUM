# Durable Paper Research State

This branch is reserved for immutable, append-only paper-account event batches and their recovery metadata.

- Source code and human-facing reports belong on `main`.
- The authoritative event history is appended under `events/YYYY/MM/<run_id>.json`.
- Every batch must pass its SHA-256 hash-chain verification before publication.
- Every update must be a normal fast-forward commit.
- Force-pushes, event deletion, silent corrections and rewriting previous accounting records are prohibited.
- SQLite is a rebuildable projection; it is not the sole durable source of truth.

No paper account has been initialized in this branch yet.

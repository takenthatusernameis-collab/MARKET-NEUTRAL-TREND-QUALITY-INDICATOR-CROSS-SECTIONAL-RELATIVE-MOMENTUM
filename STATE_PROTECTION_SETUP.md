# Paper-State Operating Guide — Active $50 USDT MEXC Paper Account

**Current status (2026-11-18):** the only active forward-paper account is `mexc-usdt-forward-50usdt-v3`, strategy generation `trend-quality-daily-cross-sectional-v3-50usdt`, with 50 USDT initial capital. The earlier $1 and $10 generations are archived in the append-only state history and are excluded by the active cycle and performance report.

## Active workflow and manual launch

Use only [▶ RUN THIS — ACTIVE MEXC $50 USDT PAPER ONLY — MANUAL / AUTO](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml) from the repository's `main` branch.

For a manual run, select branch `main` and the required input `I_CONFIRM_ACTIVE_50_USDT_PAPER_ONLY`. The run title begins `▶ MANUAL PAPER RUN — MEXC $50 USDT`. Scheduled runs use the same account and strategy; dispatch does not create a new account. The MEXC public preflight is read-only and must not be mistaken for the account workflow. The retired Polymarket paper-state writer workflow has been removed.

## Account identity and historical separation

- Active account ID: `mexc-usdt-forward-50usdt-v3`
- Active strategy ID: `trend-quality-daily-cross-sectional-v3-50usdt`
- Initial capital and starting cash: `50` USDT
- Initialization event: `events/2026/11/account-init-1794976007111.json`
- Latest recorded account snapshot at the time of this document: `events/2026/11/snapshot-1794976773310.json`
- The archived $1 generation (`mexc-usdt-forward`) and $10 generation (`mexc-usdt-forward-10usdt-v2`) are preserved unchanged. Historical events are never rewritten or deleted to make the active report appear single-generation.

The MEXC cycle and standalone performance report use the v3 account and strategy identifiers. A report is built only from matching v3 account events after verifying the complete global event chain. Archived account records are not pooled into v3 NAV, equity, trades or performance metrics.

## State-write controls

- The MEXC paper workflow defaults `PAPER_STATE_WRITE_ENABLED` to true. Set the repository Actions variable to the literal string `false` to pause portfolio-state transitions.
- The single active portfolio writer uses concurrency group `paper-state-branch-single-writer` with `cancel-in-progress: false`.
- The publisher validates the complete hash chain before append, rejects a second genesis/fork/orphan/duplicate identifier, uses a normal non-forced fast-forward ref update, reads back the exact canonical event file and verifies chain membership.
- Recovery follows `previous_batch_hash` links, not venue timestamps. A conflict, missing parent, failed read-back or failed verification must stop the state transition; never force-push or silently overwrite an event.
- The $50 v3 account has already passed the non-financial recovery-probe and fresh-checkout handshake. This handshake must be repeated for any future, explicitly authorized new account generation.

## What is and is not protected

The state branch is not server-side protected by a branch-protection rule or repository ruleset. The publisher's checks provide application-level append-only behavior, not protection against a privileged repository writer who manually rewrites or deletes branch history. That residual risk remains accepted and is visible in the operating model.

The workflow uses public MEXC market-data endpoints and simulated book fills only. It never calls private exchange account endpoints and never submits, amends or cancels live orders. The account is paper research, not an exchange-funded account and not evidence of profitability.

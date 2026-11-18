# Paper-State Operating Guide — Active $100 USDT MEXC Paper Account

**Current status (2026-11-18):** the only active forward-paper generation is configured as account
\`mexc-usdt-forward-100usdt-v4\`, strategy
\`trend-quality-daily-cross-sectional-v4-100usdt\`, with 100 USDT initial capital. The state
branch contains the v4 non-financial recovery probe
\`events/2026/11/state-probe-1795004591521.json\`, whose publisher write/read-back succeeded.
**No v4 financial account-initialization event has been published.** The latest generated
\`PAPER_STATUS.md\` therefore reports the account as ready and waiting for its first financial
paper event, with no positions or performance observations. The former $1, $10 and $50
generations are archived and excluded from v4 accounting.

## Active workflow and manual launch

Use only [▶ RUN THIS — ACTIVE MEXC $100 USDT PAPER ONLY — MANUAL / AUTO](https://github.com/takenthatusernameis-collab/MARKET-NEUTRAL-TREND-QUALITY-INDICATOR-CROSS-SECTIONAL-RELATIVE-MOMENTUM/actions/workflows/mexc-paper-cycle.yml)
from the repository's \`main\` branch.

For a manual run, select branch \`main\` and the required input
\`I_CONFIRM_ACTIVE_100_USDT_PAPER_ONLY\`. The run title begins
\`▶ MANUAL PAPER RUN — MEXC $100 USDT\`. Scheduled and manual invocations use the same v4
account; dispatch does not create a new account. The MEXC public preflight is read-only and is
not the account workflow.

## Account identity and historical separation

- Active account ID: \`mexc-usdt-forward-100usdt-v4\`
- Active strategy ID: \`trend-quality-daily-cross-sectional-v4-100usdt\`
- Configured initial capital: 100 USDT
- Recovery probe: \`events/2026/11/state-probe-1795004591521.json\`
- Financial initialization event: **not yet present**
- Latest generated account/performance report: [\`PAPER_STATUS.md\`](PAPER_STATUS.md)

The report and state reader must filter by the v4 account and strategy identifiers after
verifying the complete global event chain. The $1, $10 and $50 account generations remain
separate immutable history; they must never be pooled into v4 NAV, equity, trades or metrics.
A recovery probe is not an initialization event, trade, position, cash movement or P&L entry.

## State-write controls

- The MEXC paper workflow defaults \`PAPER_STATE_WRITE_ENABLED\` to true. Set the repository
  Actions variable to the literal string \`false\` to pause portfolio-state transitions.
- The single active portfolio writer uses concurrency group
  \`paper-state-branch-single-writer\` with \`cancel-in-progress: false\`.
- The publisher validates the complete hash chain before append, rejects a second
  genesis/fork/orphan/duplicate identifier, uses a normal non-forced fast-forward ref update,
  reads back the exact canonical event file and verifies chain membership.
- Recovery follows \`previous_batch_hash\` links, not venue timestamps. A conflict, missing
  parent, failed read-back or failed verification must stop the state transition; never
  force-push or silently overwrite an event.
- Only the active MEXC workflow may append v4 financial state. It must first verify the
  recovery probe from a fresh checkout, and then pass the existing market-data, decision,
  execution and risk gates. Never create an initialization event or trade manually.

## What is and is not protected

The \`state\` branch is not server-side protected by a branch-protection rule or repository
ruleset. The publisher's checks provide application-level append-only behavior, not protection
against a privileged repository writer who manually rewrites or deletes branch history. That
residual risk remains accepted and is visible in the operating model.

The workflow uses public MEXC market-data endpoints and simulated book fills only. It never
calls private exchange account endpoints and never submits, amends or cancels live orders.
The account is paper research, not an exchange-funded account and not evidence of profitability.

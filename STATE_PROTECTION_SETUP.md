# Paper-State Operating Guide — Unprotected Single-Writer Mode

**Status (2026-11-17):** the administrator-only branch-protection setup described by the original version of this file is retired. The MEXC forward-paper workflow no longer depends on repository Administration permissions, a protected branch, a ruleset or a `STATE_PROTECTION_TOKEN` secret.

**Live account status:** initialized with 1 USDT and independently restored from the hash-chained `state` branch. The account is currently flat (zero positions, zero orders). The recovery probe, initialization event and subsequent valuation snapshot form a verified linear event chain. See [STATUS.md](STATUS.md) for run IDs, hashes and current metrics.

## Current operating configuration

- The MEXC workflow is the scheduled forward-paper account writer and defaults `PAPER_STATE_WRITE_ENABLED` to true.
- Set the repository Actions variable `PAPER_STATE_WRITE_ENABLED=false` to pause paper-state transitions. No secret is required to enable or disable the writer.
- The MEXC workflow and retired manually dispatched Polymarket diagnostic share repository-wide concurrency group `paper-state-branch-single-writer`, with `cancel-in-progress: false`. Their workflows cannot execute state writes concurrently.
- The publisher only appends a new event batch with a normal non-forced fast-forward ref update. It verifies the complete remote hash chain before append, rejects a second genesis/fork/orphan/disconnected chain and duplicate identifiers, then reads back the exact canonical event file and re-verifies chain membership. Idempotent replays repeat remote verification.
- Local state restoration follows `previous_batch_hash` links rather than exchange timestamps, so venue clock skew cannot reorder the persisted event history.
- First writer invocation publishes only a non-financial `paper_state_recovery_probe`. A later workflow invocation checks out `state` afresh and verifies the full chain and probe before creating the 1 USDT `paper_account_initialized` event.

## Recovery and account initialization

The account is **not initialized** merely because the source code is ready or the workflow is enabled. Initialization is confirmed only after all of these are visible:

1. A successful MEXC workflow run reports `STATE_PERSISTENCE_PROBE`, with exact remote read-back verified and no account created.
2. A later run restores that probe from its fresh `state` checkout and reports `state_recovery_probe_verified_from_prior_checkout=true`.
3. The same later run, or a subsequent eligible run, appends a `paper_account_initialized` event with 1 USDT starting cash, forward-paper-only mode, and no imported historical trades/equity.
4. A subsequent run restores the financial event and reports a reconciled 1 USDT cash/NAV starting state.

The account may remain flat if MEXC's minimum contract size, quantity step, market depth or modeled costs make both legs infeasible at 1 USDT. Never increase starting capital or force an undersized trade to manufacture activity.

## What this mode protects — and what it does not

The publisher and recovery code preserve application-level append-only behavior, hash-chain integrity, idempotency, exact remote read-back and fast-forward conflict detection. The shared concurrency group prevents overlapping GitHub Actions writers. A write conflict or verification failure must stop the state transition; never force-push, overwrite a different event file or claim an unverified state is durable.

**Residual risk:** the `state` branch is not server-side protected. A repository user with sufficient write/admin permissions can manually delete or rewrite history outside the publisher. Hash-chain validation can reject a malformed or incomplete history when the workflow next reads it, but it cannot prevent a privileged user from rewriting the branch or guarantee preservation against deliberate tampering. This trade-off is accepted to remove the Administration dependency and allow paper evidence collection without live funds or live orders.

The repository is public. State events and market-data reports are publicly visible and persistent. Never store exchange credentials, private account information, secrets or personal identifiers in the repository. The entire workflow uses public MEXC market-data endpoints and never submits orders.

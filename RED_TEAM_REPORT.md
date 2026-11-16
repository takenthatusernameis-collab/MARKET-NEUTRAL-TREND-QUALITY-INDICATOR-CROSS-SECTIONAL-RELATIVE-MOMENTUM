# Emergency Red-Team Report

**Review date:** 2026-11-16  
**Target:** `main`  
**Review type:** Repository integrity, exchange-readiness, performance analytics, persistence and deployment controls  
**Current verdict:** **NO-GO for exchange migration, historical-performance claims, forward paper operation or account-state writes**

This review found defects in candidate-exchange qualification and two integrity/reporting issues. The code repairs described below are committed and pass CI. Critical deployment and governance blockers remain open. No exchange orders, private exchange endpoints or real funds were used.

## Executive findings

| Severity | Finding | Disposition |
|---|---|---|
| Critical | Crypto.com derivative probe produced a false-positive success despite an inadequate USD-quoted market universe, failing funding-history calls and unverified account/jurisdiction eligibility | Repaired the readiness gate; Crypto.com rejected |
| High | Maximum drawdown duration measured the duration of the deepest drawdown, not the longest underwater episode | Fixed; regression tests added |
| High | State publisher validated each event batch's hash but did not verify it extended the remote branch's existing chain | Fixed in code; remote-chain tests added |
| Critical | Dedicated `state` branch is unprotected and repository has no rulesets | Open blocker; no state/account writes authorized |
| High | Repository is public, so future `state` branch events and paper account records would also be public | Disclosure and data-minimization control required |
| Critical | No complete production exchange adapter, replay engine, integrated paper portfolio, restore workflow or independent NAV reconciliation exists | Open blocker; do not activate |

## 1. Exchange-readiness false positive — repaired

The original Crypto.com candidate workflow exited successfully whenever its instrument endpoint returned any perpetual contracts. It did not require successful book, ticker, candle and funding data; sufficient universe breadth; compatibility with the repository's USDT account; or confirmed jurisdiction eligibility.

The original run **43924834692** therefore reported success even though:
- It found only six crypto perpetuals: BTC, ETH, SOL, HYPE, ZEC and SEI.
- The returned instruments were USD-quoted, not USDT-quoted.
- The funding-history request failed with HTTP 400.
- No account-collateral or local derivatives eligibility had been established.

The follow-up strict gate, run **43930116624**, tested three GitHub-hosted Ubuntu versions. All three correctly returned **NOT_READY**:
- Only six eligible contracts were discovered, below the configured minimum of 20.
- The current USD quote currency does not match the strategy's USDT paper-account denomination.
- Funding-history returned API code `40004`: `Invalid instrument not tradeable` for the returned underlying identifier, and `Invalid instrument_name` for the alternate documented-style identifier.
- Account collateral and jurisdiction remain unverified.

Separate from the API test, Crypto.com's published derivatives restrictions list Romania. Its successful public REST responses do not establish that a resident there can use the derivative product. The candidate is therefore rejected for this use case pending any change in official product eligibility. See the official restrictions page: https://help.crypto.com/en/articles/5792178-derivatives-trading-restrictions

**Repair:** the workflow is now a strict readiness gate. It requires pagination, at least 20 live crypto perpetuals, nonempty successful book/ticker/candle/funding responses, USDT quote compatibility, and explicit collateral/jurisdiction verification. A candidate is READY only when every gate passes. Its intentional nonzero result currently means no replacement passed; it is not a CI failure.

**Decision:** Crypto.com is not approved. This workflow is a diagnostic, not an exchange adapter or a production migration.

## 2. Performance analytics — repaired

The former `maximum_drawdown_duration_days` used the duration of the deepest drawdown. That does not necessarily equal the longest time the account remained below a high-water mark.

The metric now tracks each complete and still-open underwater episode independently, then reports the longest duration. A further edge case was found and corrected: when NAV exactly recovers to its previous high-water mark, the next drawdown episode's clock must restart at that recovery timestamp.

Regression coverage now includes:
- A shallower drawdown that lasts longer than the deepest drawdown.
- A later drawdown after NAV exactly touches the previous high-water mark.
- Existing no-drawdown and recovery-period cases.

## 3. Event-ledger hash-chain integrity — repaired in code; production control remains open

Previously, `GitHubStatePublisher` verified the submitted batch's own hashes but did not prove that `previous_batch_hash` matched the newest batch already committed on the remote `state` branch. A caller could therefore submit a second genesis batch or create a fork, despite the stated append-only hash-chain design.

The publisher now:
1. Reads the current state-branch tree.
2. Finds and downloads every event JSON blob.
3. Verifies each batch's own hash and event path.
4. Requires exactly one genesis batch, no orphan batches, no forks, no cycles and no disconnected chains.
5. Requires the new batch's previous hash to equal the unique current chain tip.
6. Fails closed if the Git tree is truncated or malformed.

Mocked regression tests cover valid sequential publication, unanchored second genesis rejection, fork rejection, idempotency and non-fast-forward races.

**Important limitation:** this has only been validated against the mocked GitHub transport in CI. No real event batch has been written to the `state` branch, and no remote restore/rebuild integration has passed.

## 4. State branch protection — unresolved critical blocker

The GitHub branches endpoint reports both `main` and `state` as `protected: false`. The repository's rulesets endpoint returns an empty list. The connected integration was not allowed to read the branch-protection detail endpoint, and the available GitHub actions did not expose a branch-protection write operation.

The publisher's code uses normal fast-forward updates and now validates the event hash chain, but these controls do not prevent a maintainer or another token with write access from editing or deleting state files through another route.

**Required before any account-state writes:**
- Enable server-side protection or an appropriate repository ruleset for `state`.
- Disallow force pushes and deletion.
- Restrict who can write the branch.
- Require appropriate review/audit for state changes where compatible with the event-publisher design.
- Verify the configured rules using the GitHub repository settings/API after applying them.

This review did not claim to repair server-side branch protection.

## 5. Public repository and state-data privacy

The repository is public. A future `state` branch in this repository is public too. Immutable event batches, paper holdings, entries/exits, funding and NAV history would be visible and could remain in the public Git history.

The branch currently contains only its policy/README; no account or event batch has been created. Do not place credentials, API secrets, personal identifiers, private account details or other confidential data in this repository. If paper-account history is intended to be private, public Git storage is the wrong persistence location and that architecture must be redesigned before initialization.

## 6. System-integration gaps — still open

The current CI proves isolated mathematical/accounting/persistence primitives and mocked API contracts. It does not prove a working strategy system.

Not implemented or not independently verified:
- A fully qualified replacement exchange and production data adapter.
- Complete paginated live-market ingestion and end-to-end freshness/coverage gates.
- A point-in-time universe and survivorship-aware historical reconstruction.
- Chronological historical replay and a complete integrated paper broker/state machine.
- Funding, fee, stop sequencing and portfolio-level cash/NAV reconciliation.
- Real GitHub state publishing, remote restore and rebuild.
- Daily and hourly forward paper workflows.
- Equity curve, drawdown chart and human-readable portfolio risk report generated from a persisted account ledger.
- Independent reconstruction of the account from raw market data and immutable events.

No portfolio is initialized. There is no verified NAV, strategy return, CAGR, Sharpe, maximum drawdown or profitability claim.

## 7. Current verified evidence

- Successful CI: run **43931058486**; Ruff passed and **67 tests passed**.
- Performance fixes were tested on actual calculation fixtures.
- Event-chain anchoring was tested with mocked GitHub API behavior.
- Crypto.com readiness gate: run **43930116624**; all three runner jobs reported NOT_READY and failed the gate as intended.
- No actual exchange adapter migration, exchange order, Testnet, authenticated exchange request or real account operation occurred.

## Release decision

**Keep the system in BOOTSTRAPPING / NO-GO.**

Do not initialize a forward paper account or write financial events to the public `state` branch yet. Continue replacement-exchange research only with the stricter readiness gate. A replacement must be legally available in the user's jurisdiction, have adequate breadth of USDT-settled linear crypto perpetuals, supply working market data and funding history, and pass a full adapter contract test before migration.

The successful 67-test CI run is evidence of repaired code paths; it is not evidence of a trading-ready system.

# State Branch Protection and 1 USDT Forward Initialization

**Current state:** blocked pending repository-admin configuration. The state branch exists, but GitHub currently reports it as unprotected and there are no repository rulesets. The connected GitHub integration can commit files and refs but cannot change branch protection because its GitHub App installation lacks Administration permission.

## 1. Protect the state branch in GitHub

In the repository, open **Settings → Branches → Add branch protection rule**.

Set the branch name pattern to:

- state

Enable the following controls:

- **Enforce administrators** / include administrators.
- **Restrict who can push to matching branches**; restrict the allow-list to the GitHub Actions app used by this repository's workflow.
- **Do not allow force pushes**.
- **Do not allow deletions**.
- **Require linear history**.

Do not require pull-request-only writes for this branch: the event publisher appends verified fast-forward Git commits directly. Do not allow broad user/team write access. The state branch is public; all ledger contents will be publicly visible and permanent.

## 2. Add a narrowly scoped protection-read secret

Create a fine-grained personal access token restricted to this repository with only:

- **Repository permissions → Administration: Read-only**.

No Contents write, Actions write, exchange permissions or other repositories are required for this token. Add it under **Settings → Secrets and variables → Actions → New repository secret**:

- Name: STATE_PROTECTION_TOKEN
- Value: the fine-grained token

The workflow uses this secret only to read the dedicated branch-protection endpoint. The separate Actions GITHUB_TOKEN remains the append-only event publisher and has Contents: write in the workflow. Do not put the token in source files or workflow YAML.

GitHub documents that the protected-branch GET endpoint requires Administration repository permissions (read) for fine-grained tokens:
https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection

## 3. Keep the writer disabled until verification passes

The workflow defaults the repository Actions variable PAPER_STATE_WRITE_ENABLED to false.

After branch protection and the read-only secret are in place, the next run must first report:

- STATE_PERSISTENCE_PROBE
- PUBLISH_READBACK_VERIFIED_AWAITING_FRESH_CHECKOUT
- no account initialized
- zero orders

The publisher performs a post-write read-back of exact canonical event contents and a full event-chain verification. The following scheduled invocation checks the persisted probe from a fresh checkout of the state branch. Only after that does the workflow become eligible to initialize the financial account.

Review that recovered probe run, then set the repository Actions variable:

- Name: PAPER_STATE_WRITE_ENABLED
- Value: true

The runtime protection check is still mandatory on every write-capable run. Missing/invalid protection credentials, unprotected branch state, force-push/deletion allowance, missing writer restrictions or failed event read-back all fail closed.

## 4. 1 USDT account initialization

The first financial event must be paper_account_initialized with:

- Currency: USDT
- Initial capital: 1 USDT
- Starting cash: 1 USDT
- Forward-paper-only mode
- No imported historical trades or equity

The first eligible daily-close decision cycle may simulate a pair only if both MEXC legs pass minimum contract size, lot step, maximum quantity, current book depth, fees and shortfall constraints. At 50% NAV margin per leg and 2× leverage, the target notional is about 1 USDT per leg. If the venue's minimum order constraints make a valid pair impossible, initialize the 1 USDT ledger flat and keep it flat. Never inflate the account or force an undersized trade.

Historical performance must remain separate. The account starts at its actual initialization timestamp; no backfilled equity or fabricated fills are permitted.

## 5. Acceptance evidence

Do not report the account as initialized until all of the following are verified in GitHub Actions and on the state branch:

1. The branch protection endpoint confirms administrator enforcement, force pushes disabled, deletions disabled and restricted writers.
2. First run publishes the non-financial state recovery probe and reads it back exactly.
3. A later run restores the probe from a fresh checkout and verifies its event-batch hash chain.
4. The first financial event creates a 1 USDT starting balance.
5. A later run restores that financial event and reconstructs the same 1 USDT account state.
6. CI, event-chain integrity, NAV reconciliation and paper-only boundary tests pass.

No live orders, private MEXC endpoints, exchange credentials or wallet access are used.

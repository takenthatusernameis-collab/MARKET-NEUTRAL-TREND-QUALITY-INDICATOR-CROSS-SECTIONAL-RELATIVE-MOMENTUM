# Market-Neutral Trend-Quality Research System

**Status: RED-TEAM NO-GO — no portfolio is active and no replacement exchange is approved.**  
**Execution: local paper simulation only.**  
**Live data source: Bybit Global V5 public API (currently blocked from tested GitHub runners).**  
**Historical data path: official Bybit public trade archive (verified reachable; importer not yet implemented).**

This repository implements a research system based on David Sepiashvili's [Trend-Quality Indicator paper](https://www.prorealcode.com/wp-content/uploads/2019/03/24-Q-Indicator.pdf). The strategy hypothesis is exchange-neutral: rank the complete eligible USDT-settled linear crypto perpetual universe from one explicitly approved provider, select the strongest qualifying positive-Q asset as the long and the strongest qualifying negative-Q asset as the short, then evaluate the pair under realistic simulated costs and risk controls. The Bybit adapter remains the only implemented provider client; its live API access is currently blocked and no replacement has passed the readiness gate.

## Current implementation

The core repository now contains the causal indicator engine, signed-Q ranking and pair-selection primitives, a public Bybit API client, Decimal accounting functions, paper execution models, daily performance analytics, an immutable event journal, a SQLite projection and an append-only Git state-branch publisher. The code and mocked contracts are covered by CI.

The latest verified core CI run reports **67 passing tests**. See [RED_TEAM_REPORT.md](RED_TEAM_REPORT.md) for the emergency review, corrected performance and state-chain defects, and outstanding no-go controls. This is not a live Bybit integration result and not a strategy backtest. Full-universe ingestion, historical replay, an integrated forward paper broker and portfolio automation are not operational.

## Baseline configuration

| Setting | Initial value | Status |
|---|---:|---|
| Fast / slow EMA | 7 / 15 | Illustrated in the paper |
| Trend smoothing m | 5 | Provisional experiment |
| Noise smoothing n | 10 | Provisional experiment; must exceed m |
| Noise method | Absolute deviation | Baseline |
| Q threshold | \\|Q\\| > 2 | Paper's promising-trend threshold |
| Correction factor | 1.0 | Provisional |
| ATR | 14, Wilder | Risk experiment |
| ATR multiplier | 3.0 | Provisional |
| Initial paper equity | 100 USDT | Account setting |
| Long / short target | 50% / 50% NAV | Dollar neutral, not beta neutral |

The paper's equations and qualitative interpretations are not a guarantee of profitability. See [IMPLEMENTATION_PROMPT.md](IMPLEMENTATION_PROMPT.md) and [MATHEMATICAL_REFERENCE.md](MATHEMATICAL_REFERENCE.md).

## Safety and research gates

- An unfinished UTC daily candle is never used.
- An incomplete universe or material data-quality failure blocks new ranking-dependent portfolio transitions.
- Historical replay and forward paper accounting are separate accounts.
- An hourly monitor is not continuous protection. A stop crossed between checks is executed at the later detection-time paper price, not automatically at the trigger price.
- Financial events are immutable and idempotent. A paper transition is not considered durable until its run-event batch has been persisted.
- A successful unit test is not evidence of successful public API integration or forward paper performance.

## Development

Python 3.12+.

```bash
python -m pip install -e '.[dev]'
pytest
python -m trend_quality.cli public-api-smoke
```

The public API smoke command uses only unauthenticated Bybit Global public market-data endpoints. It does not place or simulate orders.


## Replacement exchange status

Crypto.com is **NOT_READY**, not a replacement: its diagnostic probe found only six USD-quoted perpetuals, funding-history returned API error 40004 for the tested instrument names, and local derivatives access/collateral eligibility is not verified. Candidate readiness now requires geographic eligibility, at least 20 qualifying contracts (research threshold to be raised/validated), compatible USDT settlement, functioning market-data and funding endpoints, and execution metadata. No exchange migration has been performed. See [the red-team report](RED_TEAM_REPORT.md) and [master directive](IMPLEMENTATION_PROMPT.md).

## Network access constraint

A six-job GitHub-hosted multi-cloud test (Ubuntu 22.04/24.04/26.04) received HTTP 403 from Bybit Global V5 in all cases, including the one job scheduled on AWS `us-west-2`. GitHub selects the cloud and region automatically; no region selector is available in the workflow. No proxy, VPN, domain rotation, alternate exchange, paid runner or manual self-hosted runner is used. Live API ingestion and forward portfolio automation remain gated.

The separate official Bybit historical trade archive is reachable: three standard runner jobs successfully read a valid gzip range from a BTCUSDT daily file (HTTP 206). This may support selective historical OHLCV reconstruction after a resumable importer, coverage checks and data-quality audit are implemented. It does not supply verified funding, mark/index prices, current instrument metadata, or executable L2 order-book data, and is not a live-data substitute.

## Repository status

The current state is bootstrap-only. No historical performance, forward paper return, trade count, or risk statistic is claimed. The status report must say so until the relevant evidence exists.

See:
- [Implementation prompt](IMPLEMENTATION_PROMPT.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Implementation decisions](IMPLEMENTATION_DECISIONS.md)
- [Prompt refinement log](PROMPT_REFINEMENT_LOG.md)
- [Runbook](RUNBOOK.md)

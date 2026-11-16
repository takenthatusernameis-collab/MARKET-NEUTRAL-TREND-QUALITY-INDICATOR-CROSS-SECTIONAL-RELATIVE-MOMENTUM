# Market-Neutral Trend-Quality Research System

**Status: BOOTSTRAPPING — no portfolio is active.**  
**Execution: local paper simulation only.**  
**Data source: Bybit Global public endpoints only.**

This repository implements a research system based on David Sepiashvili's [Trend-Quality Indicator paper](https://www.prorealcode.com/wp-content/uploads/2019/03/24-Q-Indicator.pdf). The strategy hypothesis is to rank the complete eligible Bybit USDT linear perpetual universe, select the strongest qualifying positive-Q asset as the long and the strongest qualifying negative-Q asset as the short, then evaluate the pair under realistic simulated costs and risk controls.

## Current scope

The repository is being initialized from an empty main branch. The first implementation milestone covers the pure mathematical indicator engine, public API client, deterministic ranking, and accounting/event primitives. The historical replay, durable GitHub state publisher, complete paper broker, and scheduled portfolio workflows remain gated until independently tested.

**No live orders, authenticated account access, Testnet, exchange credentials, or real capital are used.**

## Baseline configuration

| Setting | Initial value | Status |
|---|---:|---|
| Fast / slow EMA | 7 / 15 | Illustrated in the paper |
| Trend smoothing m | 5 | Provisional experiment |
| Noise smoothing n | 10 | Provisional experiment; must exceed m |
| Noise method | Absolute deviation | Baseline |
| Q threshold | |Q| > 2 | Paper's promising-trend threshold |
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

## Repository status

The current state is bootstrap-only. No historical performance, forward paper return, trade count, or risk statistic is claimed. The status report must say so until the relevant evidence exists.

See:
- [Implementation prompt](IMPLEMENTATION_PROMPT.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Implementation decisions](IMPLEMENTATION_DECISIONS.md)
- [Prompt refinement log](PROMPT_REFINEMENT_LOG.md)
- [Runbook](RUNBOOK.md)

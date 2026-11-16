# Assumptions and Limitations

## Provisional values
- EMA: 7 / 15 (illustrated in paper).
- Trend m: 5 (experimental).
- Noise n: 10 (experimental; must be >m).
- Correction factor: 1.0 (experimental).
- Noise: absolute deviation baseline; RMS separate experiment.
- Q threshold: strict |Q|>2 (source's promising-trend threshold).
- ATR: Wilder 14, multiplier 3.0 (experimental).
- Initial capital: 100 USDT.
- Taker fee assumption: 0.10% per fill (not the user's actual fee tier).
- Historical execution: next eligible minute open plus adverse cost assumption.
- Hourly workflow scheduled at minute 17; actual delay is measured, not assumed exact.
- Maximum linear order-book REST depth: 200 levels.
- Public order-book snapshots exclude RPI liquidity.

## Model limitations
- Equal-dollar long/short exposure is not beta neutrality.
- Hourly scheduled monitoring is not continuous stop protection.
- Public order book is a snapshot and does not guarantee fills.
- Historical Kline execution cannot reconstruct historical queue position or full historical depth.
- Historical universe replay is survivorship-biased unless point-in-time listings/delistings are known.
- The initial synthetic account does not reproduce the complete Bybit margin/liquidation engine.
- GitHub-hosted workflows may be delayed, skipped, or cancelled; recovery must catch up without backdating fills.
- No profitability or edge is assumed.

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
- Maximum linear order-book REST depth: 1,000 levels; initial request depth is configurable and must be benchmarked.
- Public order-book snapshots exclude RPI liquidity.

## Network and runner limitation
- Bybit V5 guidance states that US and mainland-China source IPs return HTTP 403.
- One GitHub Actions run was provisioned in Azure eastus2 and received HTTP 403 on the first public server-time call.
- A free ubuntu-slim connectivity probe is being used to test whether another standard runner pool is assigned outside the restricted geography; until verified, Bybit data integration remains blocked from GitHub-hosted execution.
- No proxy, VPN, geo-spoofing, alternative exchange, or unapproved API host is permitted.
- If standard free runners remain US-based, the no-paid option may require a user-installed self-hosted runner on permitted user-controlled hardware; this is not available until the user explicitly configures it.

## Model limitations
- Equal-dollar long/short exposure is not beta neutrality.
- Hourly scheduled monitoring is not continuous stop protection.
- Public order book is a snapshot and does not guarantee fills.
- Historical Kline execution cannot reconstruct historical queue position or full historical depth.
- Historical universe replay is survivorship-biased unless point-in-time listings/delistings are known.
- The initial synthetic account does not reproduce the complete Bybit margin/liquidation engine.
- GitHub-hosted workflows may be delayed, skipped, or cancelled; recovery must catch up without backdating fills.
- No profitability or edge is assumed.

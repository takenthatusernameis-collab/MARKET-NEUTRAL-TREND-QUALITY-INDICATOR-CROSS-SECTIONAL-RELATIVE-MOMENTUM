# Data Dictionary

## Time convention
All persisted timestamps are UTC ISO-8601 or Unix milliseconds. Daily candles use UTC 00:00 start times. Completed status is based on Bybit server time.

## Instrument fields
- symbol: exchange contract identifier.
- contract_type: response field; eligible value LinearPerpetual.
- status: Trading or other lifecycle status.
- quote_coin / settle_coin: response fields, both USDT for this strategy.
- launch_time / delivery_time: milliseconds.
- funding_interval_minutes: response metadata.
- tick_size / qty_step / min_qty / min_notional / max_market_qty: response constraints.

## Candle fields
- start_ms: candle start.
- open/high/low/close: decimal strings in source data, parsed into Decimal at ingestion.
- volume: base coin for linear contracts.
- turnover: quote-currency turnover for linear contracts.
- completed: true only when interval end <= server time.

## Indicator fields
- fast_ema / slow_ema.
- semi_cycle_direction.
- semi_cycle_start_ms.
- semi_cycle_age.
- cpc.
- trend.
- noise_method.
- noise.
- correction_factor.
- q.
- b.
- eligibility_status.

## Accounting event fields
- event_id: immutable unique ID.
- idempotency_key: unique transition key.
- account_id: historical or forward account.
- strategy_id.
- run_id.
- occurred_at_ms.
- event_type.
- payload.
- event_hash / previous_hash.

## Portfolio terminology
- Long notional: positive signed exposure.
- Short notional: negative signed exposure.
- Gross exposure: sum absolute leg notionals / NAV.
- Net exposure: signed sum notionals / NAV.
- Dollar neutrality: closeness of long notional to short notional; not beta neutrality.
- Observed drawdown: based on available valuation frequency, not continuous intrahour prices.

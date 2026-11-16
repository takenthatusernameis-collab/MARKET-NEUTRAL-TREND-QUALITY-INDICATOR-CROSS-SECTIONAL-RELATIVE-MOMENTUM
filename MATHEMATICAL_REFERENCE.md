# Mathematical Reference

Primary source: David Sepiashvili, *Trend-Quality Indicator*, Stocks & Commodities V.22:4, pp. 14–20. [PDF](https://www.prorealcode.com/wp-content/uploads/2019/03/24-Q-Indicator.pdf)

## CPC
For close price P and fixed cycle start t0:
`CPC(t) = sum from tau=t0 to t of [P(tau)-P(tau-1)]`.
The first observation at a confirmed crossover includes the crossover candle's close-to-close change. Reset at the next confirmed moving-average reversal.

## Trend
`Trend(t) = MA(CPC, m, t >= t0)`.
The paper does not establish a universal m.

## Noise
Linear:
`Noise1 = MA(abs(CPC - Trend), n)`.

RMS:
`Noise2 = sqrt(MA((CPC - Trend)^2, n))`.

The paper explicitly permits n > m. This implementation uses complete rolling windows and residuals aligned to the same timestamps.

## Q
`Q = (Trend / Noise) * c`.
The source calls c an appropriate correction factor, not a universal constant. The initial c=1.0 is an experiment. Undefined zero-noise values are excluded rather than converted to infinite strength.

## Source qualitative bands
- |Q| in 0–1: trend buried beneath noise.
- |Q| in 1–2: weak trending.
- |Q| in 2–5: moderate trending.
- |Q| > 5: strong trending.
- |Q| > 2 is described as promising by the source, but is not a probability or profitability guarantee.

## B
`B = abs(Trend) / (abs(Trend) + Noise) * 100`.
B is directionless. Source interpretation: 50–65 weak, 65–80 moderate, above 80 strong.

## EMA cycle extraction
Figure 1 illustrates 7-day and 15-day EMA crossovers. The project treats 7/15 as the reproducible initial reference only. EMA seed convention and the first left-censored cycle handling are implementation decisions, not author-prescribed rules.

## ATR
ATR(14) Wilder smoothing is a separate project risk model and is not part of the Q Indicator paper.

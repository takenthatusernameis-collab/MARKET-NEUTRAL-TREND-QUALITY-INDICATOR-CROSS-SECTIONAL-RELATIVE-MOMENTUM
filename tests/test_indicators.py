from __future__ import annotations

import math

import pytest

from trend_quality.indicators import compute_q_series, ema, wilder_atr


def test_ema_sma_seed_and_recursive_update() -> None:
    assert ema([10.0, 11.0, 12.0, 13.0], 3) == [None, None, 11.0, 12.0]


def _cycle_prices() -> list[float]:
    return [10, 9, 8, 7, 6, 7, 8, 9, 10, 11, 12, 11, 10, 9, 8, 7, 6, 7, 8, 9, 10]


def test_left_censored_initial_cycle_is_not_ranked() -> None:
    points = compute_q_series(
        _cycle_prices(),
        fast_period=2,
        slow_period=3,
        trend_period=2,
        noise_period=3,
    )
    assert all(point.cycle_start_index is None for point in points[:6])
    assert points[6].direction == "bullish"
    assert points[6].cycle_start_index == 6
    assert points[6].cpc == pytest.approx(1.0)


def test_cpc_accumulates_and_resets_only_on_confirmed_crossovers() -> None:
    points = compute_q_series(
        _cycle_prices(),
        fast_period=2,
        slow_period=3,
        trend_period=2,
        noise_period=3,
    )
    assert points[7].cpc == pytest.approx(2.0)
    assert points[8].cpc == pytest.approx(3.0)
    bearish_starts = [
        point.index
        for point in points
        if point.direction == "bearish" and point.cycle_start_index == point.index
    ]
    assert bearish_starts
    first_bearish = bearish_starts[0]
    assert points[first_bearish].cpc == pytest.approx(
        _cycle_prices()[first_bearish] - _cycle_prices()[first_bearish - 1]
    )


def test_q_and_b_are_finite_when_noise_is_positive() -> None:
    points = compute_q_series(
        _cycle_prices(),
        fast_period=2,
        slow_period=3,
        trend_period=2,
        noise_period=3,
    )
    valid = [point for point in points if point.q is not None]
    assert valid
    for point in valid:
        assert math.isfinite(point.q)
        assert point.noise is not None and point.noise > 0
        assert point.b is not None and 0 <= point.b <= 100


def test_rms_noise_is_not_less_than_absolute_noise() -> None:
    prices = _cycle_prices()
    absolute = compute_q_series(
        prices, fast_period=2, slow_period=3, trend_period=2,
        noise_period=3, noise_method="absolute"
    )
    rms = compute_q_series(
        prices, fast_period=2, slow_period=3, trend_period=2,
        noise_period=3, noise_method="rms"
    )
    comparable = [
        (a.noise, b.noise)
        for a, b in zip(absolute, rms, strict=True)
        if a.noise is not None and b.noise is not None
    ]
    assert comparable
    assert all(right + 1e-12 >= left for left, right in comparable)


def test_no_lookahead_prefix_invariance() -> None:
    prices = _cycle_prices()
    full = compute_q_series(
        prices, fast_period=2, slow_period=3, trend_period=2, noise_period=3
    )
    prefix = compute_q_series(
        prices[:15], fast_period=2, slow_period=3, trend_period=2, noise_period=3
    )
    for left, right in zip(prefix, full[:15], strict=True):
        assert left == right


def test_positive_scale_and_offset_invariance_of_q() -> None:
    prices = _cycle_prices()
    kwargs = dict(fast_period=2, slow_period=3, trend_period=2, noise_period=3)
    baseline = compute_q_series(prices, **kwargs)
    scaled = compute_q_series([p * 7.5 for p in prices], **kwargs)
    shifted = compute_q_series([p + 1000 for p in prices], **kwargs)
    for base, scale, shift in zip(baseline, scaled, shifted, strict=True):
        if base.q is not None:
            assert scale.q == pytest.approx(base.q)
            assert shift.q == pytest.approx(base.q)


def test_invalid_noise_period_rejected() -> None:
    with pytest.raises(ValueError, match="greater than trend_period"):
        compute_q_series([1, 2, 3, 4], trend_period=5, noise_period=5)


def test_constant_price_history_never_manufactures_q() -> None:
    points = compute_q_series([10.0] * 100)
    assert all(point.q is None for point in points)


def test_wilder_atr_seed_and_recursion() -> None:
    highs = [11, 12, 14, 16]
    lows = [9, 10, 11, 12]
    closes = [10, 11, 12, 15]
    values = wilder_atr(highs, lows, closes, period=3)
    assert values[:2] == [None, None]
    assert values[2] == pytest.approx(7.0 / 3.0)
    assert values[3] == pytest.approx((2 * (7.0 / 3.0) + 4.0) / 3.0)


def test_atr_rejects_mismatched_and_invalid_ohlc() -> None:
    with pytest.raises(ValueError, match="equal lengths"):
        wilder_atr([2], [], [1])
    with pytest.raises(ValueError, match="invalid OHLC"):
        wilder_atr([1], [2], [1])

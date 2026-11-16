from __future__ import annotations

import decimal

import pytest

from trend_quality.performance import (
    DAY_MS,
    EquityPoint,
    compute_performance_metrics,
    daily_returns,
    drawdown_series,
)


BASE_TIME = 1794787200000


def _equity(values: list[str], start_ms: int = BASE_TIME) -> list[EquityPoint]:
    return [
        EquityPoint(start_ms + index * DAY_MS, decimal.Decimal(value))
        for index, value in enumerate(values)
    ]


def test_daily_returns_and_drawdown_series() -> None:
    points = _equity(["100", "110", "99", "105", "120"])
    returns = daily_returns(points)
    assert returns[0] == pytest.approx(0.10)
    assert returns[1] == pytest.approx(-0.10)
    series = drawdown_series(points)
    assert [item.drawdown for item in series] == pytest.approx(
        [0.0, 0.0, -0.10, 105 / 110 - 1, 0.0]
    )
    assert series[2].high_watermark == decimal.Decimal("110")


def test_drawdown_duration_and_recovery_period() -> None:
    metrics = compute_performance_metrics(
        _equity(["100", "110", "99", "105", "120"])
    )
    assert metrics["maximum_drawdown"].value == pytest.approx(0.10)
    assert metrics["maximum_drawdown_duration_days"].value == pytest.approx(3.0)
    assert metrics["recovery_period_days"].value == pytest.approx(2.0)


def test_monotonic_equity_has_no_drawdown_or_recovery_duration() -> None:
    metrics = compute_performance_metrics(_equity(["100", "101", "102"]))
    assert metrics["maximum_drawdown"].value == 0.0
    assert metrics["maximum_drawdown_duration_days"].value == 0.0
    assert metrics["recovery_period_days"].value is None
    assert metrics["recovery_period_days"].reason == "No drawdown occurred"


def test_formal_cagr_is_withheld_before_365_elapsed_days() -> None:
    metrics = compute_performance_metrics(_equity(["100", "101"]))
    assert metrics["cagr"].value is None
    assert "365" in str(metrics["cagr"].reason)


def test_cagr_is_available_after_one_year() -> None:
    points = _equity(["100"] + ["110"] * 365)
    metrics = compute_performance_metrics(points)
    assert metrics["cagr"].value == pytest.approx(0.10)
    assert metrics["calmar"].value == pytest.approx(
        0.10 / metrics["maximum_drawdown"].value
    ) if metrics["maximum_drawdown"].value > 0 else metrics["calmar"].value is None


def test_sharpe_requires_30_returns_and_nonzero_volatility() -> None:
    points = [EquityPoint(BASE_TIME, decimal.Decimal("100"))]
    nav = decimal.Decimal("100")
    for index in range(30):
        rate = decimal.Decimal("0.001") if index % 2 == 0 else decimal.Decimal("0.002")
        nav *= decimal.Decimal("1") + rate
        points.append(EquityPoint(BASE_TIME + (index + 1) * DAY_MS, nav))
    metrics = compute_performance_metrics(points)
    assert metrics["sharpe"].value is not None
    assert metrics["annualized_daily_volatility"].value is not None


def test_sortino_requires_20_returns_and_five_negative_returns() -> None:
    points = [EquityPoint(BASE_TIME, decimal.Decimal("100"))]
    nav = decimal.Decimal("100")
    rates = [decimal.Decimal("0.002")] * 20 + [decimal.Decimal("-0.001")] * 5
    for index, rate in enumerate(rates):
        nav *= decimal.Decimal("1") + rate
        points.append(EquityPoint(BASE_TIME + (index + 1) * DAY_MS, nav))
    metrics = compute_performance_metrics(points)
    assert metrics["sortino"].value is not None


def test_sortino_withholds_for_insufficient_negative_returns() -> None:
    points = [EquityPoint(BASE_TIME, decimal.Decimal("100"))]
    nav = decimal.Decimal("100")
    for index in range(25):
        rate = decimal.Decimal("-0.001") if index < 4 else decimal.Decimal("0.001")
        nav *= decimal.Decimal("1") + rate
        points.append(EquityPoint(BASE_TIME + (index + 1) * DAY_MS, nav))
    metrics = compute_performance_metrics(points)
    assert metrics["sortino"].value is None


def test_trade_statistics_use_net_closed_trade_pnl() -> None:
    metrics = compute_performance_metrics(
        _equity(["100", "101", "102"]),
        [
            decimal.Decimal("10"),
            decimal.Decimal("-5"),
            decimal.Decimal("0"),
            decimal.Decimal("-5"),
        ],
    )
    assert metrics["closed_trade_count"].value == 4
    assert metrics["win_rate"].value == pytest.approx(0.25)
    assert metrics["average_winner_net_pnl"].value == pytest.approx(10.0)
    assert metrics["average_loser_net_pnl"].value == pytest.approx(-5.0)
    assert metrics["profit_factor"].value == pytest.approx(1.0)
    assert metrics["expectancy_net_pnl"].value == pytest.approx(0.0)


def test_profit_factor_is_not_claimed_without_losing_trades() -> None:
    metrics = compute_performance_metrics(
        _equity(["100", "101", "102"]),
        [decimal.Decimal("1"), decimal.Decimal("2")],
    )
    assert metrics["profit_factor"].value is None
    assert "No losing" in str(metrics["profit_factor"].reason)


def test_daily_metrics_reject_missing_dates_and_nonpositive_nav() -> None:
    with pytest.raises(ValueError, match="consecutive UTC daily"):
        daily_returns(
            [
                EquityPoint(BASE_TIME, decimal.Decimal("100")),
                EquityPoint(BASE_TIME + 2 * DAY_MS, decimal.Decimal("101")),
            ]
        )
    with pytest.raises(ValueError, match="positive"):
        daily_returns(_equity(["100", "0"]))

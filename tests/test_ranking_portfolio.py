from __future__ import annotations

from decimal import Decimal

import pytest

from trend_quality.indicators import QObservation
from trend_quality.portfolio import (
    Position,
    calculate_nav,
    floor_to_step,
    funding_cashflow,
    portfolio_exposure,
    target_quantity,
)
from trend_quality.ranking import Candidate, rank_candidates
from trend_quality.selection import select_pair


def _point(symbol: str, q: float, direction: str) -> tuple[str, QObservation]:
    return symbol, QObservation(
        index=20,
        direction=direction,
        cycle_start_index=5,
        cycle_age=16,
        fast_ema=1.1,
        slow_ema=1.0,
        cpc=2.0,
        trend=1.0,
        noise=0.2,
        q=q,
        b=83.3,
    )


def test_rankings_sort_bullish_descending_and_bearish_ascending() -> None:
    bullish, bearish = rank_candidates(
        [
            _point("AUSDT", 3.0, "bullish"),
            _point("BUSDT", 5.0, "bullish"),
            _point("CUSDT", -2.5, "bearish"),
            _point("DUSDT", -4.0, "bearish"),
            _point("EUSDT", 1.9, "bullish"),
        ]
    )
    assert [c.symbol for c in bullish] == ["BUSDT", "AUSDT"]
    assert [c.symbol for c in bearish] == ["DUSDT", "CUSDT"]


def test_signed_q_defines_direction_not_ema_cycle_label() -> None:
    bullish, bearish = rank_candidates(
        [_point("BULL", 3.5, "bearish"), _point("BEAR", -3.5, "bullish")]
    )
    assert [c.symbol for c in bullish] == ["BULL"]
    assert [c.symbol for c in bearish] == ["BEAR"]
    assert bullish[0].semi_cycle_direction == "bearish"
    assert bearish[0].semi_cycle_direction == "bullish"


def test_execution_eligibility_filters_candidates() -> None:
    bullish, bearish = rank_candidates(
        [_point("AUSDT", 5.0, "bullish"), _point("BUSDT", -5.0, "bearish")],
        execution_eligible={"AUSDT"},
    )
    assert [c.symbol for c in bullish] == ["AUSDT"]
    assert bearish == []


def test_pair_selection_avoids_same_symbol_using_ranked_fallback() -> None:
    long = Candidate("SAME", 9.0, 90.0, "long", 20)
    second_long = Candidate("LONG", 8.0, 85.0, "long", 20)
    short = Candidate("SAME", -9.0, 90.0, "short", 20)
    second_short = Candidate("SHORT", -8.0, 85.0, "short", 20)
    pair = select_pair([long, second_long], [short, second_short])
    assert pair is not None
    assert pair.long.symbol == "SAME"
    assert pair.short.symbol == "SHORT"


def test_pair_selection_requires_two_distinct_symbols() -> None:
    item_long = Candidate("SAME", 4.0, 80.0, "long", 5)
    item_short = Candidate("SAME", -4.0, 80.0, "short", 5)
    assert select_pair([item_long], [item_short]) is None


def test_floor_to_step_never_rounds_up() -> None:
    assert floor_to_step(Decimal("1.239"), Decimal("0.01")) == Decimal("1.23")


def test_target_quantity_respects_all_constraints() -> None:
    qty = target_quantity(
        Decimal("100"),
        Decimal("0.5"),
        Decimal("10"),
        Decimal("0.01"),
        Decimal("0.1"),
        Decimal("5"),
        Decimal("4"),
    )
    assert qty == Decimal("4")
    too_small = target_quantity(
        Decimal("10"), Decimal("0.5"), Decimal("100"),
        Decimal("0.01"), Decimal("0.1"), Decimal("5")
    )
    assert too_small == Decimal("0")


def test_linear_position_pnl_signs() -> None:
    long = Position("AUSDT", "long", Decimal("2"), Decimal("100"))
    short = Position("BUSDT", "short", Decimal("2"), Decimal("100"))
    assert long.unrealized_pnl(Decimal("110")) == Decimal("20")
    assert short.unrealized_pnl(Decimal("110")) == Decimal("-20")


def test_funding_signs() -> None:
    quantity = Decimal("2")
    mark = Decimal("100")
    positive = Decimal("0.001")
    negative = Decimal("-0.001")
    assert funding_cashflow("long", quantity, mark, positive) == Decimal("-0.200")
    assert funding_cashflow("short", quantity, mark, positive) == Decimal("0.200")
    assert funding_cashflow("long", quantity, mark, negative) == Decimal("0.200")
    assert funding_cashflow("short", quantity, mark, negative) == Decimal("-0.200")


def test_exposure_and_nav_reconciliation() -> None:
    exposure = portfolio_exposure(
        Decimal("100"), Decimal("50"), Decimal("48")
    )
    assert exposure["gross_exposure"] == Decimal("0.98")
    assert exposure["net_exposure"] == Decimal("0.02")
    nav = calculate_nav(
        Decimal("100"), Decimal("5"), Decimal("-2"),
        Decimal("0.5"), Decimal("0.2")
    )
    assert nav == Decimal("102.7")

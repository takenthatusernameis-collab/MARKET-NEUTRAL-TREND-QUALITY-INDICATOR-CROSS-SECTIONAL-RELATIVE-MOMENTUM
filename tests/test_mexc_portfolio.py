from __future__ import annotations

from decimal import Decimal

from trend_quality.execution import SimulatedFill
from trend_quality.mexc_portfolio import (
    account_report,
    append_daily_equity,
    append_equity_snapshot,
    apply_confirmed_funding,
    close_paper_position,
    increase_paper_position,
    initial_portfolio_state,
    lifetime_max_drawdown,
    open_paper_position,
    performance_summary,
    portfolio_nav,
    reduce_paper_position,
    reset_daily_risk_window,
    stop_is_triggered,
    update_trailing_stop,
)


def fill(
    side: str,
    quantity: str,
    price: str,
    fee: str,
) -> SimulatedFill:
    qty = Decimal(quantity)
    px = Decimal(price)
    notional = qty * px
    return SimulatedFill(
        side=side,
        requested_quantity=qty,
        filled_quantity=qty,
        average_price=px,
        reference_price=px,
        notional=notional,
        fee=Decimal(fee),
        shortfall=Decimal("0"),
        shortfall_bps=Decimal("0"),
        complete=True,
        levels_consumed=1,
    )


def btc_instrument() -> dict[str, object]:
    return {
        "instrument_id": 1,
        "symbol": "BTC_USDT",
        "category": "crypto",
    }


def test_open_mark_close_accounts_pnl_and_both_fees_once() -> None:
    state = initial_portfolio_state(Decimal("100"))
    position = open_paper_position(
        state,
        btc_instrument(),
        {"mark_price": "100"},
        "long",
        Decimal("5"),
        fill("buy", "0.5", "100", "0.01"),
        1_700_000_000_000,
    )
    assert state["cash"] == "99.99"
    assert position["quantity"] == "0.5"
    nav = portfolio_nav(state, {1: {"mark_price": "110"}})
    assert nav == Decimal("104.99")

    details = close_paper_position(
        state,
        position,
        fill("sell", "0.5", "108", "0.0108"),
        1_700_086_400_000,
    )
    assert details["realized_gross_pnl"] == "4.0"
    assert details["net_trade_pnl"] == "3.9792"
    assert state["cash"] == "103.9792"
    assert state["fees_paid"] == "0.0208"
    assert state["positions"] == []
    assert state["closed_trade_net_pnls"] == ["3.9792"]


def test_funding_cashflow_respects_side_and_signed_funding_rate() -> None:
    state = initial_portfolio_state(Decimal("100"))
    position = open_paper_position(
        state,
        btc_instrument(),
        {"mark_price": "100"},
        "long",
        Decimal("5"),
        fill("buy", "0.5", "100", "0"),
        1_700_000_000_000,
    )
    positive = apply_confirmed_funding(
        state, position, Decimal("0.001"), Decimal("100"), 1_700_028_800_000
    )
    assert positive["cashflow_usdt"] == "-0.0500"
    negative = apply_confirmed_funding(
        state, position, Decimal("-0.001"), Decimal("100"), 1_700_057_600_000
    )
    assert negative["cashflow_usdt"] == "0.0500"
    assert state["confirmed_funding"] == "0.0000"


def test_trailing_stop_only_moves_in_favourable_direction() -> None:
    state = initial_portfolio_state(Decimal("100"))
    position = open_paper_position(
        state,
        btc_instrument(),
        {"mark_price": "100"},
        "long",
        Decimal("5"),
        fill("buy", "0.5", "100", "0"),
        1_700_000_000_000,
    )
    assert update_trailing_stop(
        position, Decimal("130"), Decimal("110"), Decimal("5")
    ) == Decimal("115")
    assert update_trailing_stop(
        position, Decimal("120"), Decimal("100"), Decimal("10")
    ) == Decimal("115")
    assert not stop_is_triggered(position, Decimal("116"))
    assert stop_is_triggered(position, Decimal("114"))


def test_daily_equity_and_risk_metrics_show_sample_gates() -> None:
    state = initial_portfolio_state(Decimal("100"))
    append_daily_equity(state, 1_700_000_000_000, Decimal("100"))
    append_daily_equity(state, 1_700_086_400_000, Decimal("101"))
    summary = performance_summary(state)
    assert summary["status"] == "AVAILABLE_WITH_SAMPLE_GATES"
    metrics = summary["metrics"]
    assert metrics["total_return"]["value"] == 0.01
    assert metrics["cagr"]["value"] is None
    assert "365" in metrics["cagr"]["reason"]
    assert metrics["sharpe"]["value"] is None
    assert metrics["closed_trade_count"]["value"] == 0


def test_daily_equity_is_idempotent_for_same_completed_bar() -> None:
    state = initial_portfolio_state(Decimal("100"))
    timestamp = 1_700_000_000_000
    append_daily_equity(state, timestamp, Decimal("100"))
    append_daily_equity(state, timestamp, Decimal("101"))
    assert state["daily_equity"] == [{"timestamp_ms": timestamp, "nav": "101"}]


def test_account_report_discloses_exposure_and_ledgers() -> None:
    state = initial_portfolio_state(Decimal("100"))
    position = open_paper_position(
        state,
        btc_instrument(),
        {"mark_price": "100"},
        "long",
        Decimal("5"),
        fill("buy", "0.5", "100", "0.01"),
        1_700_000_000_000,
    )
    report = account_report(state, {1: {"mark_price": "100"}})
    assert report["currency"] == "USDT"
    assert report["position_count"] == 1
    assert report["gross_exposure"] == "0.5000500050005000500050005001"
    assert report["fees_paid"] == "0.01"
    assert report["positions"][0]["instrument_id"] == position["instrument_id"]



def test_two_x_default_leverage_and_balanced_margin_report() -> None:
    state = initial_portfolio_state(Decimal("100"))
    position = open_paper_position(
        state,
        btc_instrument(),
        {"mark_price": "100"},
        "long",
        Decimal("5"),
        fill("buy", "1", "100", "0"),
        1_700_000_000_000,
    )
    assert position["leverage"] == "2"
    assert position["initial_margin_usdt"] == "50"
    report = account_report(state, {1: {"mark_price": "100"}})
    assert Decimal(report["long_notional_usdt"]) == Decimal("100")
    assert Decimal(report["long_margin_used_usdt"]) == Decimal("50")


def test_combined_portfolio_daily_drawdown_triggers_even_when_legs_are_each_below_25pct() -> None:
    state = initial_portfolio_state(Decimal("100"))
    first = append_equity_snapshot(
        state, 1_700_000_000_000, Decimal("100"),
        Decimal("100"), Decimal("100"),
    )
    assert not first["emergency_stop_triggered"]

    # At 2x on 50% margin each, a 12.5% adverse move on both 1x-NAV legs
    # produces a 25% combined NAV loss. The risk rule sees the combined NAV.
    snapshot = append_equity_snapshot(
        state, 1_700_000_300_000, Decimal("75"),
        Decimal("100"), Decimal("100"),
    )
    assert snapshot["daily_return_pct"] == "-25.00"
    assert snapshot["daily_drawdown_pct"] == "-25.00"
    assert snapshot["emergency_stop_newly_triggered"]
    assert state["daily_risk"]["stop_reason"] == "COMBINED_PORTFOLIO_DAILY_DRAWDOWN_LIMIT"


def test_daily_stop_uses_intraday_peak_not_lifetime_high_water_mark() -> None:
    state = initial_portfolio_state(Decimal("100"))
    append_equity_snapshot(
        state, 1_700_000_000_000, Decimal("100"),
        Decimal("100"), Decimal("100"),
    )
    append_equity_snapshot(
        state, 1_700_000_300_000, Decimal("120"),
        Decimal("100"), Decimal("100"),
    )
    intraday = append_equity_snapshot(
        state, 1_700_000_600_000, Decimal("90"),
        Decimal("100"), Decimal("100"),
    )
    assert intraday["daily_return_pct"] == "-10.0"
    assert intraday["daily_drawdown_pct"] == "-25.00"
    assert intraday["emergency_stop_triggered"]


def test_daily_risk_resets_at_utc_rollover_but_lifetime_mdd_can_exceed_25pct() -> None:
    state = initial_portfolio_state(Decimal("100"))
    append_equity_snapshot(
        state, 1_700_000_000_000, Decimal("100"),
        Decimal("100"), Decimal("100"),
    )
    append_equity_snapshot(
        state, 1_700_000_300_000, Decimal("70"),
        Decimal("100"), Decimal("100"),
    )
    next_day_ms = 1_700_086_400_000
    next_day = append_equity_snapshot(
        state, next_day_ms, Decimal("70"),
        Decimal("100"), Decimal("100"),
    )
    assert next_day["daily_drawdown_pct"] == "0"
    assert not next_day["emergency_stop_triggered"]
    assert lifetime_max_drawdown(state) == Decimal("-0.3")


def test_equity_snapshot_is_idempotent_and_rejects_time_reversal() -> None:
    state = initial_portfolio_state(Decimal("100"))
    timestamp = 1_700_000_000_000
    append_equity_snapshot(
        state, timestamp, Decimal("100"),
        Decimal("100"), Decimal("100"),
    )
    append_equity_snapshot(
        state, timestamp, Decimal("101"),
        Decimal("100"), Decimal("100"),
    )
    assert len(state["equity_curve"]) == 1
    assert state["equity_curve"][0]["nav"] == "101"
    try:
        append_equity_snapshot(
            state, timestamp - 1, Decimal("100"),
            Decimal("100"), Decimal("100"),
        )
    except ValueError as exc:
        assert "cannot move backwards" in str(exc)
    else:
        raise AssertionError("out-of-order equity observations must fail")



def test_new_utc_day_uses_previous_day_last_nav_when_first_cron_is_delayed() -> None:
    state = initial_portfolio_state(Decimal("100"))
    first_timestamp = 1_700_000_000_000
    append_equity_snapshot(
        state, first_timestamp, Decimal("100"),
        Decimal("100"), Decimal("100"),
    )
    next_utc_day_after_five_minutes = (
        (first_timestamp // 86_400_000 + 1) * 86_400_000 + 300_000
    )
    snapshot = append_equity_snapshot(
        state, next_utc_day_after_five_minutes, Decimal("70"),
        Decimal("70"), Decimal("70"),
    )
    assert snapshot["daily_starting_nav"] == "100"
    assert snapshot["daily_starting_reference"] == "previous_utc_day_last_snapshot"
    assert snapshot["daily_return_pct"] == "-30.0"
    assert snapshot["daily_drawdown_pct"] == "-30.0"
    assert snapshot["emergency_stop_newly_triggered"]



def test_new_forward_account_default_is_hundred_usdt_generation() -> None:
    state = initial_portfolio_state()
    assert state["initial_capital"] == "100"
    assert state["cash"] == "100"
    assert state["currency"] == "USDT"
    assert state["account_id"] == "mexc-usdt-forward-100usdt-v4"
    assert state["strategy_id"] == "trend-quality-daily-cross-sectional-v4-100usdt"
    assert state["positions"] == []



def test_daily_rebalance_increases_and_reduces_only_position_deltas() -> None:
    state = initial_portfolio_state(Decimal("100"))
    position = open_paper_position(
        state,
        btc_instrument(),
        {"mark_price": "100"},
        "long",
        Decimal("5"),
        fill("buy", "1", "100", "0.10"),
        1_700_000_000_000,
    )
    original_entry_timestamp = position["entry_timestamp_ms"]

    add = increase_paper_position(
        state,
        position,
        btc_instrument(),
        {"mark_price": "110"},
        Decimal("5"),
        fill("buy", "1", "110", "0.22"),
        1_700_000_300_000,
    )
    assert add["action"] == "INCREASED"
    assert position["quantity"] == "2"
    assert position["entry_price"] == "105"
    assert position["entry_fee"] == "0.32"
    assert position["initial_margin_usdt"] == "105"
    assert position["entry_timestamp_ms"] == original_entry_timestamp

    reduction = reduce_paper_position(
        state,
        position,
        fill("sell", "0.5", "120", "0.06"),
        1_700_000_600_000,
    )
    assert reduction["action"] == "REDUCED"
    assert reduction["quantity_delta"] == "-0.5"
    assert reduction["remaining_quantity"] == "1.5"
    assert position["quantity"] == "1.5"
    assert position["entry_fee"] == "0.240"
    assert position["initial_margin_usdt"] == "78.75"
    assert reduction["realized_gross_pnl"] == "7.5"
    assert reduction["partial_realized_net_pnl"] == "7.360"
    assert state["cash"] == "107.12"
    assert state["fees_paid"] == "0.38"
    assert state["realized_gross_pnl"] == "7.5"
    assert state["closed_trade_net_pnls"] == []
    assert state["partial_realized_net_pnls"] == ["7.360"]


def test_successful_daily_rebalance_resets_drawdown_baseline_but_not_lifetime_curve() -> None:
    state = initial_portfolio_state(Decimal("100"))
    first = 1_700_000_000_000
    append_equity_snapshot(
        state, first, Decimal("100"), Decimal("100"), Decimal("100")
    )
    interim = append_equity_snapshot(
        state, first + 300_000, Decimal("85"), Decimal("90"), Decimal("100")
    )
    assert interim["daily_drawdown_pct"] == "-15.00"
    assert not interim["emergency_stop_triggered"]

    reset = reset_daily_risk_window(
        state, first + 600_000, Decimal("85"),
        reference="daily_portfolio_rebalance",
    )
    assert reset["starting_nav"] == "85"
    assert reset["peak_nav"] == "85"
    assert reset["starting_reference"] == "daily_portfolio_rebalance"
    assert reset["calendar_day_starting_nav"] == "100"
    assert reset["stop_triggered"] is False

    after_reset = append_equity_snapshot(
        state, first + 900_000, Decimal("63.75"),
        Decimal("90"), Decimal("100"),
    )
    assert after_reset["daily_drawdown_pct"] == "-25.00"
    assert after_reset["drawdown_window_starting_nav"] == "85"
    assert after_reset["daily_starting_nav"] == "100"
    assert Decimal(after_reset["daily_return_pct"]) == Decimal("-36.25")
    assert after_reset["emergency_stop_newly_triggered"]
    assert lifetime_max_drawdown(state) == Decimal("-0.3625")


def test_daily_rebalance_cannot_clear_a_latched_emergency_flatten() -> None:
    state = initial_portfolio_state(Decimal("100"))
    first = 1_700_000_000_000
    append_equity_snapshot(
        state, first, Decimal("100"), Decimal("100"), Decimal("100")
    )
    append_equity_snapshot(
        state, first + 300_000, Decimal("75"), Decimal("100"), Decimal("100")
    )
    try:
        reset_daily_risk_window(
            state, first + 600_000, Decimal("75")
        )
    except ValueError as exc:
        assert "latched emergency" in str(exc)
    else:
        raise AssertionError("a daily rebalance must never clear an emergency stop")
    assert state["daily_risk"]["stop_triggered"] is True

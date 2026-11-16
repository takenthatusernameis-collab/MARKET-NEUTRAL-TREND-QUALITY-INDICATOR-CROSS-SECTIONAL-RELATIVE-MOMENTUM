from __future__ import annotations

from decimal import Decimal

from trend_quality.execution import SimulatedFill
from trend_quality.mexc_portfolio import (
    account_report,
    append_daily_equity,
    apply_confirmed_funding,
    close_paper_position,
    initial_portfolio_state,
    open_paper_position,
    performance_summary,
    portfolio_nav,
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
    state = initial_portfolio_state()
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
    state = initial_portfolio_state()
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
    state = initial_portfolio_state()
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
    state = initial_portfolio_state()
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
    state = initial_portfolio_state()
    timestamp = 1_700_000_000_000
    append_daily_equity(state, timestamp, Decimal("100"))
    append_daily_equity(state, timestamp, Decimal("101"))
    assert state["daily_equity"] == [{"timestamp_ms": timestamp, "nav": "101"}]


def test_account_report_discloses_exposure_and_ledgers() -> None:
    state = initial_portfolio_state()
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

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

import pytest

from trend_quality.event_journal import build_event_batch, write_batch_atomic
from trend_quality.paper_performance_report import (
    _equity_curve_svg,
    render_performance_report,
)

ACCOUNT_ID = "mexc-usdt-forward-50usdt-v3"
STRATEGY_ID = "trend-quality-daily-cross-sectional-v3-50usdt"


def _state(
    *,
    positions: list[dict[str, object]],
    equity: list[dict[str, object]],
    risk_start: int,
    risk_nav: str,
    closed: list[str] | None = None,
    partial: list[str] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "account_id": ACCOUNT_ID,
        "strategy_id": STRATEGY_ID,
        "currency": "USDT",
        "initial_capital": "100",
        "cash": "99.8",
        "realized_gross_pnl": "0",
        "fees_paid": "0.2",
        "confirmed_funding": "0",
        "positions": positions,
        "closed_trade_net_pnls": closed or [],
        "partial_realized_net_pnls": partial or [],
        "daily_equity": [{"timestamp_ms": risk_start, "nav": "100"}],
        "equity_curve": equity,
        "daily_risk": {
            "starting_nav": risk_nav,
            "starting_timestamp_ms": risk_start,
            "peak_nav": risk_nav,
            "utc_date": "2027-01-15",
            "stop_triggered": False,
        },
    }


def _write_event(
    root: Path,
    *,
    run_id: str,
    timestamp: int,
    previous_hash: str | None,
    state: dict[str, object] | None,
    details: dict[str, object],
) -> str:
    payload: dict[str, object] = {"details": details}
    if state is not None:
        payload["portfolio_state"] = state
    event = {
        "event_id": f"event-{run_id}",
        "idempotency_key": run_id,
        "account_id": ACCOUNT_ID,
        "strategy_id": STRATEGY_ID,
        "occurred_at_ms": timestamp,
        "event_type": "paper_test_event",
        "payload": payload,
    }
    batch = build_event_batch(
        run_id,
        timestamp,
        [event],
        previous_batch_hash=previous_hash,
    )
    write_batch_atomic(root, batch)
    return str(batch["batch_hash"])


def test_report_calculates_per_session_and_lifetime_drawdowns_and_trade_history(
    tmp_path: Path,
) -> None:
    start = 1_800_000_000_000
    opened = {
        "instrument_id": 7,
        "symbol": "AAA_USDT",
        "side": "long",
        "quantity": "2",
        "entry_price": "100",
        "entry_timestamp_ms": start,
        "entry_fee": "0.2",
        "last_mark_price": "80",
        "leverage": "2",
    }
    first_state = _state(
        positions=[opened],
        equity=[
            {"timestamp_ms": start, "nav": "100", "roi_pct": "0"},
            {"timestamp_ms": start + 1, "nav": "80", "roi_pct": "-20"},
        ],
        risk_start=start,
        risk_nav="100",
    )
    parent = _write_event(
        tmp_path,
        run_id="open",
        timestamp=start,
        previous_hash=None,
        state=first_state,
        details={"fills": [opened]},
    )

    reduced = dict(opened, quantity="1", last_mark_price="90")
    second_state = _state(
        positions=[reduced],
        equity=[
            {"timestamp_ms": start, "nav": "100", "roi_pct": "0"},
            {"timestamp_ms": start + 1, "nav": "80", "roi_pct": "-20"},
            {"timestamp_ms": start + 2, "nav": "95", "roi_pct": "-5"},
            {"timestamp_ms": start + 3, "nav": "90", "roi_pct": "-10"},
        ],
        risk_start=start + 2,
        risk_nav="90",
        partial=["-10"],
    )
    parent = _write_event(
        tmp_path,
        run_id="reduce",
        timestamp=start + 2,
        previous_hash=parent,
        state=second_state,
        details={
            "fills": [{
                "instrument_id": 7,
                "symbol": "AAA_USDT",
                "side": "long",
                "action": "REDUCED",
                "quantity_delta": "-1",
                "remaining_quantity": "1",
                "entry_price": "100",
                "exit_price": "90",
                "partial_realized_net_pnl": "-10",
                "exit_fee": "0.1",
            }],
            "portfolio_daily_risk_reset": {
                "risk_window_reset_at_ms": start + 2,
                "starting_nav": "90",
                "risk_window_reset_reason": "daily_portfolio_rebalance",
            },
        },
    )

    flat_state = _state(
        positions=[],
        equity=second_state["equity_curve"],  # type: ignore[arg-type]
        risk_start=start + 2,
        risk_nav="90",
        closed=["-15.1"],
        partial=["-10"],
    )
    _write_event(
        tmp_path,
        run_id="close",
        timestamp=start + 4,
        previous_hash=parent,
        state=flat_state,
        details={
            "stop_exits": [{
                "instrument_id": 7,
                "symbol": "AAA_USDT",
                "side": "long",
                "quantity": "1",
                "entry_price": "100",
                "exit_price": "85",
                "net_trade_pnl": "-15.1",
                "exit_timestamp_ms": start + 4,
                "exit_fee": "0.1",
            }]
        },
    )

    report = render_performance_report(tmp_path, {"outcome": "success"})

    assert "Lifetime / cross-session maximum drawdown:** -20.0000%" in report
    assert "Worst individual risk-session maximum drawdown:** -20.0000%" in report
    assert "| OPENED | AAA_USDT | long |" in report
    assert "| REDUCED | AAA_USDT | long |" in report
    assert "| CLOSED | AAA_USDT | long |" in report
    assert "Sortino ratio" in report
    assert "sample gate" in report
    assert "Full mark-to-market equity history" in report
    assert "Verified global event batches: **3**" in report
    assert "RISK WINDOW RESET" in report



def test_report_embeds_a_readable_svg_equity_curve(tmp_path: Path) -> None:
    start = 1_800_000_000_000
    state = _state(
        positions=[],
        equity=[
            {"timestamp_ms": start, "nav": "100", "roi_pct": "0"},
            {"timestamp_ms": start + 60_000, "nav": "103", "roi_pct": "3"},
            {"timestamp_ms": start + 120_000, "nav": "98", "roi_pct": "-2"},
        ],
        risk_start=start,
        risk_nav="100",
    )
    _write_event(
        tmp_path,
        run_id="svg-chart",
        timestamp=start,
        previous_hash=None,
        state=state,
        details={},
    )
    svg_path = tmp_path / "equity_curve.svg"
    report = render_performance_report(
        tmp_path,
        {"outcome": "success"},
        equity_svg_path=svg_path,
    )

    svg = svg_path.read_text(encoding="utf-8")
    assert "![Trend-Quality paper portfolio equity curve](equity_curve.svg)" in report
    assert "Sparkline:" not in report
    assert "<svg " in svg
    assert "<polyline " in svg
    assert "Initial capital: 100.0000 USDT" in svg
    assert "Start: 100.0000 USDT" in svg
    assert "Latest: 98.0000 USDT" in svg
    assert "3 persisted NAV observations" in svg
    assert "stroke-dasharray" in svg


def test_uninitialized_report_writes_a_waiting_svg_chart(tmp_path: Path) -> None:
    stamp = 1_800_000_000_000
    probe = {
        "event_id": "svg-probe",
        "idempotency_key": "svg-probe",
        "account_id": ACCOUNT_ID,
        "strategy_id": STRATEGY_ID,
        "occurred_at_ms": stamp,
        "event_type": "paper_state_recovery_probe",
        "payload": {"details": {"financial_state_created": False}},
    }
    batch = build_event_batch("svg-probe", stamp, [probe])
    write_batch_atomic(tmp_path, batch)
    svg_path = tmp_path / "equity_curve.svg"

    render_performance_report(tmp_path, equity_svg_path=svg_path)

    svg = svg_path.read_text(encoding="utf-8")
    assert "Waiting for the first paper equity observation" in svg
    assert "<svg " in svg


def test_report_rejects_a_tampered_event_batch(tmp_path: Path) -> None:
    start = 1_800_000_000_000
    state = _state(
        positions=[],
        equity=[{"timestamp_ms": start, "nav": "100"}],
        risk_start=start,
        risk_nav="100",
    )
    _write_event(
        tmp_path,
        run_id="integrity",
        timestamp=start,
        previous_hash=None,
        state=state,
        details={},
    )
    event_file = next((tmp_path / "events").glob("**/*.json"))
    batch = json.loads(event_file.read_text(encoding="utf-8"))
    batch["events"][0]["payload"]["details"]["tampered"] = True
    event_file.write_text(json.dumps(batch), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid immutable paper event batch"):
        render_performance_report(tmp_path)


def test_report_filters_archived_account_generations(tmp_path: Path) -> None:
    start = 1_800_000_000_000
    archived_event = {
        "event_id": "archived-event",
        "idempotency_key": "archived-event",
        "account_id": "mexc-usdt-forward",
        "strategy_id": "trend-quality-daily-cross-sectional-v1-1usdt",
        "occurred_at_ms": start,
        "event_type": "paper_account_initialized",
        "payload": {
            "portfolio_state": {
                "account_id": "mexc-usdt-forward",
                "initial_capital": "1",
            },
            "details": {},
        },
    }
    first = build_event_batch("archived", start, [archived_event])
    write_batch_atomic(tmp_path, first)
    active_state = _state(
        positions=[],
        equity=[{"timestamp_ms": start + 1, "nav": "100"}],
        risk_start=start + 1,
        risk_nav="100",
    )
    _write_event(
        tmp_path,
        run_id="active",
        timestamp=start + 1,
        previous_hash=str(first["batch_hash"]),
        state=active_state,
        details={},
    )

    report = render_performance_report(tmp_path)
    assert "Events for this account/strategy generation: **1**" in report
    assert "archived $1 and $10 USDT account generations are excluded" in report


def test_report_is_informative_before_account_initialization(tmp_path: Path) -> None:
    stamp = 1_800_000_000_000
    probe = {
        "event_id": "probe",
        "idempotency_key": "probe",
        "account_id": ACCOUNT_ID,
        "strategy_id": STRATEGY_ID,
        "occurred_at_ms": stamp,
        "event_type": "paper_state_recovery_probe",
        "payload": {"details": {"financial_state_created": False}},
    }
    batch = build_event_batch("probe", stamp, [probe])
    write_batch_atomic(tmp_path, batch)
    report = render_performance_report(tmp_path)
    assert "not yet initialized" in report
    assert "No account performance is inferred" in report



def test_report_renders_metrics_and_open_positions_after_svg_refactor(tmp_path: Path) -> None:
    start = 1_800_000_000_000
    positions = [
        {
            "instrument_id": 1595,
            "symbol": "VSTOCK_USDT",
            "side": "long",
            "quantity": "0.02",
            "entry_price": "426.35",
            "last_mark_price": "419.00",
            "entry_timestamp_ms": start,
            "entry_fee": "0.0017",
        },
        {
            "instrument_id": 1899,
            "symbol": "BILL_USDT",
            "side": "short",
            "quantity": "2500",
            "entry_price": "0.003974",
            "last_mark_price": "0.003950",
            "entry_timestamp_ms": start,
            "entry_fee": "0",
        },
    ]
    state = _state(
        positions=positions,
        equity=[
            {"timestamp_ms": start, "nav": "100", "roi_pct": "0"},
            {"timestamp_ms": start + 60_000, "nav": "99.9", "roi_pct": "-0.1"},
        ],
        risk_start=start,
        risk_nav="100",
    )
    _write_event(
        tmp_path,
        run_id="open-position-render-regression",
        timestamp=start,
        previous_hash=None,
        state=state,
        details={"fills": positions},
    )

    report = render_performance_report(tmp_path)

    assert "Closed-trade win rate" in report
    assert "Sortino ratio" in report
    assert "Unavailable" in report
    assert "## Open positions" in report
    assert "| VSTOCK_USDT | long | 0.02 | 426.35 | 419.00 |" in report
    assert "| BILL_USDT | short | 2500 | 0.003974 | 0.003950 |" in report
    assert "Full mark-to-market equity history" in report



def test_two_point_equity_curve_labels_do_not_duplicate_or_overlap() -> None:
    points = [
        {"timestamp_ms": 1794976007111, "nav": "50.01072776"},
        {"timestamp_ms": 1794976773310, "nav": "49.88652776"},
    ]
    svg = _equity_curve_svg(points, Decimal("50"))
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    text_nodes = root.findall(".//svg:text", namespace)
    nodes_by_text: dict[str, list[ET.Element]] = {}
    for node in text_nodes:
        nodes_by_text.setdefault("".join(node.itertext()), []).append(node)

    assert len(nodes_by_text["2026-11-18"]) == 2
    assert len(nodes_by_text["04:26:47 UTC"]) == 1
    assert len(nodes_by_text["04:39:33 UTC"]) == 1
    first_date, last_date = nodes_by_text["2026-11-18"]
    assert float(first_date.attrib["x"]) < float(last_date.attrib["x"])
    assert first_date.attrib["y"] == last_date.attrib["y"]

    first_time = nodes_by_text["04:26:47 UTC"][0]
    last_time = nodes_by_text["04:39:33 UTC"][0]
    observation_count = nodes_by_text["2 persisted NAV observations"][0]
    assert first_time.attrib["y"] == last_time.attrib["y"]
    assert float(observation_count.attrib["y"]) > float(first_time.attrib["y"]) + 24
    assert "Start: 50.0107 USDT" in svg
    assert "Latest: 49.8865 USDT" in svg


def test_one_point_equity_curve_uses_one_centered_utc_label() -> None:
    svg = _equity_curve_svg(
        [{"timestamp_ms": 1794976007111, "nav": "50.01072776"}],
        Decimal("50"),
    )
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    labels = [
        node for node in root.findall(".//svg:text", namespace)
        if "".join(node.itertext()) in {"2026-11-18", "04:26:47 UTC"}
    ]
    assert ["".join(node.itertext()) for node in labels] == [
        "2026-11-18",
        "04:26:47 UTC",
    ]
    assert len({node.attrib["x"] for node in labels}) == 1


def test_dense_equity_history_suppresses_crowded_interior_time_ticks() -> None:
    start = 1794976007111
    points = [
        {"timestamp_ms": start, "nav": "50.00"},
        *[
            {"timestamp_ms": start + index * 1_000, "nav": str(50 + index / 100)}
            for index in range(1, 19)
        ],
        {"timestamp_ms": start + 3_600_000, "nav": "50.19"},
    ]
    svg = _equity_curve_svg(points, Decimal("50"))
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    date_labels = [
        node for node in root.findall(".//svg:text", namespace)
        if len("".join(node.itertext())) == 10
        and "".join(node.itertext()).count("-") == 2
    ]
    time_labels = [
        node for node in root.findall(".//svg:text", namespace)
        if "".join(node.itertext()).endswith(" UTC")
    ]
    assert len(date_labels) == 2
    assert len(time_labels) == 2
    assert len({node.attrib["x"] for node in date_labels}) == 2



def test_equity_curve_uses_phone_legible_svg_typography() -> None:
    start = 1_800_000_000_000
    svg = _equity_curve_svg(
        [
            {"timestamp_ms": start, "nav": "50"},
            {"timestamp_ms": start + 60_000, "nav": "49.9"},
        ],
        Decimal("50"),
    )
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    nodes = root.findall(".//svg:text", namespace)
    by_text = {"".join(node.itertext()): node for node in nodes}

    assert root.attrib["viewBox"] == "0 0 1120 500"
    assert int(by_text["Trend-Quality Paper Portfolio — Equity Curve"].attrib["font-size"]) >= 26
    assert int(by_text["2027-01-15"].attrib["font-size"]) >= 19
    assert int(by_text["2027-01-15"].attrib["font-size"]) == 19
    assert int(by_text["2 persisted NAV observations"].attrib["font-size"]) >= 16
    assert int(by_text["Latest: 49.9000 USDT (-0.20% vs initial)"].attrib["font-size"]) >= 19
    times = [node for node in nodes if "".join(node.itertext()).endswith("UTC")]
    assert len(times) == 2
    assert all(int(node.attrib["font-size"]) >= 18 for node in times)

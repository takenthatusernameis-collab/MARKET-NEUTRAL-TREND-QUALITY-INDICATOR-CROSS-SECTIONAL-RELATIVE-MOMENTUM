from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from trend_quality.paper_status import (
    _equity_svg,
    _risk_profile,
    render_paper_status,
    render_primary_trade_journal,
)

DAY_MS = 86_400_000


def pair_history():
    start = 1_800_000_000_000
    long_price = Decimal("100")
    short_price = Decimal("100")
    history = {1: [], 2: []}
    for index in range(31):
        stamp = start + index * DAY_MS
        if index:
            long_return = Decimal("0.005") if index % 2 else Decimal("-0.005")
            short_return = Decimal("-0.02") if index % 2 else Decimal("0.02")
            long_price *= Decimal("1") + long_return
            short_price *= Decimal("1") + short_return
        history[1].append({"timestamp_ms": stamp, "close": str(long_price)})
        history[2].append({"timestamp_ms": stamp, "close": str(short_price)})
    return history, start + 30 * DAY_MS


def test_inverse_volatility_gives_quieter_leg_more_weight_and_matches_pair_risk():
    history, cutoff = pair_history()
    profile = _risk_profile(1, 2, history, cutoff)
    assert profile["observations"] == 30
    assert profile["long_weight"] > Decimal("0.5")
    assert profile["short_weight"] < Decimal("0.5")
    assert profile["long_weight"] + profile["short_weight"] == Decimal("1")
    assert profile["estimated_volatility_reduction"] > Decimal("0")
    assert profile["leverage_multiplier"] > Decimal("1")


def test_inverse_volatility_estimate_excludes_future_candles():
    history, cutoff = pair_history()
    baseline = _risk_profile(1, 2, history, cutoff)
    history[1].append({"timestamp_ms": cutoff + DAY_MS, "close": "999999999"})
    history[2].append({"timestamp_ms": cutoff + DAY_MS, "close": "0.0000001"})
    revised = _risk_profile(1, 2, history, cutoff)
    assert revised == baseline


def test_equity_svg_has_separated_endpoints_and_readable_axis_labels():
    start = 1_800_000_000_000
    svg = _equity_svg(
        [
            {"timestamp_ms": start, "nav": "100"},
            {"timestamp_ms": start + 60_000, "nav": "99.5"},
        ],
        Decimal("100"),
        "Phone layout regression",
        "A compact chart with separated labels",
        "#2563eb",
    )
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    labels = {
        "".join(node.itertext()): node
        for node in root.findall(".//svg:text", namespace)
    }
    assert root.attrib["viewBox"] == "0 0 1200 480"
    assert float(labels["Start: 100.0000 USDT"].attrib["x"]) < float(
        labels["Latest: 99.5000 USDT"].attrib["x"]
    )
    dates = [
        node for node in root.findall(".//svg:text", namespace)
        if len("".join(node.itertext())) == 10
        and "".join(node.itertext()).count("-") == 2
    ]
    times = [
        node for node in root.findall(".//svg:text", namespace)
        if "".join(node.itertext()).endswith("UTC")
    ]
    assert len(dates) == 2
    assert len(times) == 2
    assert len({node.attrib["x"] for node in dates}) == 2
    assert len({node.attrib["x"] for node in times}) == 2


def test_compact_status_starts_at_100_and_marks_curves_as_waiting(tmp_path):
    equal = tmp_path / "equal.svg"
    alternative = tmp_path / "alternative.svg"
    report = render_paper_status(
        tmp_path,
        {},
        {},
        generated_at_ms=1_800_000_000_000,
        equal_svg_path=equal,
        alternative_svg_path=alternative,
    )
    assert "mexc-usdt-forward-100usdt-v4" in report
    assert "100.00000000 USDT" in report
    assert "mexc-usdt-forward-50usdt-v3" not in report
    assert "visual-only counterfactual" in report
    assert equal.exists() and alternative.exists()
    ET.fromstring(equal.read_text(encoding="utf-8"))
    ET.fromstring(alternative.read_text(encoding="utf-8"))


def test_primary_trade_journal_contains_primary_fills_and_funding_only(tmp_path):
    from trend_quality.event_journal import build_event_batch, write_batch_atomic

    timestamp = 1_800_000_000_000
    event = {
        "event_id": "v4-primary-trades",
        "idempotency_key": "v4-primary-trades",
        "account_id": "mexc-usdt-forward-100usdt-v4",
        "strategy_id": "trend-quality-daily-cross-sectional-v4-100usdt",
        "occurred_at_ms": timestamp,
        "event_type": "daily_portfolio_decision",
        "payload": {
            "details": {
                "fills": [
                    {
                        "action": "OPENED",
                        "instrument_id": 11,
                        "symbol": "QUIET_USDT",
                        "side": "long",
                        "quantity": "2",
                        "entry_price": "50",
                        "entry_fee": "0.02",
                    },
                    {
                        "action": "CLOSED",
                        "instrument_id": 11,
                        "symbol": "QUIET_USDT",
                        "side": "long",
                        "quantity": "2",
                        "exit_price": "52",
                        "exit_fee": "0.02",
                        "realized_net_pnl": "3.96",
                    },
                ],
                "funding_events": [
                    {
                        "instrument_id": 11,
                        "symbol": "QUIET_USDT",
                        "side": "long",
                        "cashflow_usdt": "0.03",
                        "timestamp_ms": timestamp + 1000,
                    }
                ],
            }
        },
    }
    batch = build_event_batch(
        run_id="v4-primary-trades",
        created_at_ms=timestamp,
        events=[event],
        previous_batch_hash=None,
    )
    write_batch_atomic(tmp_path, batch)
    journal = render_primary_trade_journal(
        tmp_path,
        generated_at_ms=timestamp + 2000,
        workflow_metadata={},
    )
    assert "QUIET_USDT" in journal
    assert "OPENED" in journal
    assert "CLOSED" in journal
    assert "FUNDING" in journal
    assert "0.03" in journal
    assert "alternative-path trades or shadow executions" in journal
    assert "mexc-usdt-forward-50usdt-v3" not in journal


def test_drawdown_summary_reports_lifetime_and_each_risk_session():
    from trend_quality.paper_status import _drawdown_summary

    first_state = {
        "daily_risk": {
            "starting_timestamp_ms": 1_800_000_000_000,
            "starting_nav": "100",
        },
        "equity_curve": [
            {"timestamp_ms": 1_800_000_000_000, "nav": "100"},
            {"timestamp_ms": 1_800_000_001_000, "nav": "95"},
        ],
    }
    second_state = {
        "daily_risk": {
            "starting_timestamp_ms": 1_800_000_002_000,
            "starting_nav": "95",
        },
        "equity_curve": [
            {"timestamp_ms": 1_800_000_000_000, "nav": "100"},
            {"timestamp_ms": 1_800_000_001_000, "nav": "95"},
            {"timestamp_ms": 1_800_000_002_000, "nav": "95"},
            {"timestamp_ms": 1_800_000_003_000, "nav": "90"},
        ],
    }
    events = [
        {"payload": {"portfolio_state": first_state}},
        {"payload": {"portfolio_state": second_state}},
    ]
    lifetime, worst_session, sessions = _drawdown_summary(events, Decimal("100"))
    assert lifetime == Decimal("-0.10")
    assert len(sessions) == 2
    assert sessions[0]["max_drawdown"] == Decimal("-0.05")
    assert sessions[1]["max_drawdown"] == Decimal("-5") / Decimal("95")
    assert worst_session == Decimal("-5") / Decimal("95")

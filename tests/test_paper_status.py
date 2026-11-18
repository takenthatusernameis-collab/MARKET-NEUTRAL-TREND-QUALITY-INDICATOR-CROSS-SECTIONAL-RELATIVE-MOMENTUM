from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from trend_quality.paper_status import (
    _equity_svg,
    _risk_profile,
    render_paper_status,
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

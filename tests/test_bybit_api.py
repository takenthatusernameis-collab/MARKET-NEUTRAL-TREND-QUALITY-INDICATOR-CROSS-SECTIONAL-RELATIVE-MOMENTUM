from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from trend_quality.bybit_api import BybitAPIError, BybitPublicClient


class FakeTransport:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Mapping[str, str | int]]] = []

    def __call__(self, path: str, params: Mapping[str, str | int]) -> dict[str, Any]:
        self.calls.append((path, dict(params)))
        if not self.responses:
            raise AssertionError("Unexpected API call")
        return self.responses.pop(0)


def _instrument(symbol: str, **changes: str) -> dict[str, str]:
    item = {
        "symbol": symbol,
        "status": "Trading",
        "contractType": "LinearPerpetual",
        "quoteCoin": "USDT",
        "settleCoin": "USDT",
    }
    item.update(changes)
    return item


def test_instrument_cursor_pagination_and_local_filters() -> None:
    fake = FakeTransport(
        [
            {
                "retCode": 0,
                "result": {
                    "list": [_instrument("BTCUSDT"), _instrument("ETHUSDT", quoteCoin="USDC")],
                    "nextPageCursor": "next-1",
                },
            },
            {
                "retCode": 0,
                "result": {
                    "list": [_instrument("SOLUSDT"), _instrument("OLDUSDT", status="Settling")],
                    "nextPageCursor": "",
                },
            },
        ]
    )
    client = BybitPublicClient(transport=fake)
    instruments = client.eligible_linear_usdt_perpetuals()
    assert [item["symbol"] for item in instruments] == ["BTCUSDT", "SOLUSDT"]
    assert fake.calls[1][1]["cursor"] == "next-1"
    assert "contractType" not in fake.calls[0][1]
    assert "quoteCoin" not in fake.calls[0][1]
    assert "settleCoin" not in fake.calls[0][1]


def test_repeated_cursor_is_rejected() -> None:
    fake = FakeTransport(
        [
            {"retCode": 0, "result": {"list": [], "nextPageCursor": "same"}},
            {"retCode": 0, "result": {"list": [], "nextPageCursor": "same"}},
        ]
    )
    with pytest.raises(BybitAPIError, match="cursor repeated"):
        BybitPublicClient(transport=fake).eligible_linear_usdt_perpetuals()


def test_kline_backward_pagination_deduplicates_and_sorts() -> None:
    fake = FakeTransport(
        [
            {
                "retCode": 0,
                "result": {
                    "list": [
                        ["3000", "3", "4", "2", "3", "10", "30"],
                        ["2000", "2", "3", "1", "2", "10", "20"],
                    ]
                },
            },
            {
                "retCode": 0,
                "result": {
                    "list": [
                        ["2000", "2", "3", "1", "2", "10", "20"],
                        ["1000", "1", "2", "0.5", "1", "10", "10"],
                    ]
                },
            },
        ]
    )
    candles = BybitPublicClient(transport=fake).klines_backward(
        "BTCUSDT", "D", 1000, 3000, limit=2
    )
    assert [c.start_ms for c in candles] == [1000, 2000, 3000]
    assert fake.calls[1][1]["end"] == 1999


def test_funding_full_page_is_subdivided() -> None:
    # Simulate a capped page followed by two smaller complete partitions.
    full = [
        {"fundingRateTimestamp": str(i), "fundingRate": "0.001"}
        for i in range(200)
    ]
    fake = FakeTransport(
        [
            {"retCode": 0, "result": {"list": full}},
            {
                "retCode": 0,
                "result": {
                    "list": [{"fundingRateTimestamp": "10", "fundingRate": "0.001"}]
                },
            },
            {
                "retCode": 0,
                "result": {
                    "list": [{"fundingRateTimestamp": "90", "fundingRate": "0.002"}]
                },
            },
        ]
    )
    rows = BybitPublicClient(transport=fake).funding_history_complete(
        "BTCUSDT", 0, 100
    )
    assert [row["fundingRateTimestamp"] for row in rows] == ["10", "90"]


def test_orderbook_accepts_documented_depth_up_to_1000() -> None:
    fake = FakeTransport(
        [
            {
                "retCode": 0,
                "result": {
                    "s": "BTCUSDT",
                    "b": [["99", "1"]],
                    "a": [["101", "1"]],
                    "ts": 1000,
                    "cts": 999,
                },
            }
        ]
    )
    result = BybitPublicClient(transport=fake).orderbook("BTCUSDT", limit=1000)
    assert result["s"] == "BTCUSDT"
    assert fake.calls[0][1]["limit"] == 1000


def test_bybit_application_error_is_rejected() -> None:
    fake = FakeTransport(
        [{"retCode": 10001, "retMsg": "invalid request", "result": {}}]
    )
    with pytest.raises(BybitAPIError, match="10001"):
        BybitPublicClient(transport=fake).server_time_ms()

from __future__ import annotations

from typing import Any

import pytest

from trend_quality.polymarket_api import (
    PolymarketAPIError,
    PolymarketPublicClient,
    is_cross_margin_instrument,
    is_new_position_eligible,
    validate_instrument,
)


def instrument(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "instrument_id": 7,
        "category": "equity",
        "symbol": "NVDA-PERP",
        "base_asset": "NVDA",
        "quote_asset": "USD",
        "funding_interval": "8h",
        "quantity_decimals": 4,
        "price_decimals": 2,
        "price_bounds": "0.1",
        "liquidation_fee": "0.01",
        "max_order_count": 100,
        "min_notional": "1",
        "max_market_notional": "100000",
        "max_limit_notional": "1000000",
        "max_leverage": 10,
        "isolated_only": False,
        "close_only": False,
        "settlement": None,
        "risk_tiers": [{"lower_bound": "0", "max_leverage": 10}],
        "ui_live_time": None,
    }
    row.update(overrides)
    return row


def test_cross_margin_universe_includes_any_category_and_keeps_visibility_advisory() -> None:
    assert is_cross_margin_instrument(instrument(category="equity"))
    assert is_cross_margin_instrument(instrument(category="commodity"))
    assert is_cross_margin_instrument(instrument(category="future_category"))
    assert is_new_position_eligible(instrument(ui_live_time=None))
    assert not is_cross_margin_instrument(instrument(isolated_only=True))
    assert not is_cross_margin_instrument(instrument(settlement={"price": "1"}))
    assert not is_new_position_eligible(instrument(close_only=True))


def test_instrument_metadata_validator_accepts_complete_cross_market() -> None:
    assert validate_instrument(instrument()) == []


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"quantity_decimals": -1}, "INVALID_QUANTITY_DECIMALS"),
        ({"min_notional": "-1"}, "NEGATIVE_MIN_NOTIONAL"),
        ({"max_leverage": 0}, "INVALID_MAX_LEVERAGE"),
        ({"risk_tiers": []}, "MISSING_RISK_TIERS"),
        ({"risk_tiers": [{"lower_bound": "bad", "max_leverage": 10}]}, "INVALID_RISK_TIER"),
    ],
)
def test_instrument_metadata_validator_reports_invalid_fields(
    overrides: dict[str, Any], expected: str
) -> None:
    assert expected in validate_instrument(instrument(**overrides))


def test_instruments_and_tickers_use_bulk_public_endpoints() -> None:
    def transport(path: str, params: Any) -> tuple[int, dict[str, str], Any]:
        if path == "/v1/info/instruments":
            return 200, {}, [instrument()]
        if path == "/v1/info/tickers":
            return 200, {}, [{"instrument_id": 7, "last_price": "100"}]
        if path == "/v1/info/statistics":
            return 200, {}, [{"instrument_id": 7, "volume": "1000", "open_price": "95"}]
        raise AssertionError(path)

    client = PolymarketPublicClient(transport=transport, minimum_interval_seconds=0)
    rows = client.instruments()
    tickers, stats = client.tickers()
    assert rows[0]["symbol"] == "NVDA-PERP"
    assert tickers[0]["last_price"] == "100"
    assert stats[0]["volume"] == "1000"


def test_instrument_endpoint_rejects_duplicate_ids() -> None:
    def transport(path: str, params: Any) -> tuple[int, dict[str, str], Any]:
        return 200, {}, [instrument(), instrument()]

    client = PolymarketPublicClient(transport=transport, minimum_interval_seconds=0)
    with pytest.raises(PolymarketAPIError, match="duplicate"):
        client.instruments()


def test_kline_pagination_adds_only_missing_interval() -> None:
    calls: list[int] = []

    def transport(path: str, params: Any) -> tuple[int, dict[str, str], Any]:
        assert path == "/v1/info/klines"
        start = int(params["start_timestamp"])
        calls.append(start)
        if len(calls) == 1:
            return 200, {}, {
                "data": [[start, "1", "2", "0.5", "1.5", "10", 100]],
                "more": True,
            }
        return 200, {}, {
            "data": [[start, "1.5", "2", "1", "1.8", "11", 110]],
            "more": False,
        }

    client = PolymarketPublicClient(transport=transport, minimum_interval_seconds=0)
    start = 1_700_000_000_000
    candles = client.candles(
        7, start_timestamp=start, end_timestamp=start + 3 * 86_400_000
    )
    assert len(candles) == 2
    assert calls == [start, start + 86_400_000]


def test_funding_history_and_fee_schedule_public_parsing() -> None:
    def transport(path: str, params: Any) -> tuple[int, dict[str, str], Any]:
        if path == "/v1/info/funding":
            return 200, {}, {
                "data": [{"funding_rate": "0.0001", "timestamp": 1_700_000_000_000}],
                "more": False,
            }
        if path == "/v1/info/fees":
            return 200, {}, {
                "fee_schedule": [{
                    "category": "equity", "taker_fee_rate": "0.0005",
                    "maker_fee_rate": "0.0001", "tiers": [],
                }]
            }
        raise AssertionError(path)

    client = PolymarketPublicClient(transport=transport, minimum_interval_seconds=0)
    assert client.funding_history(
        7, start_timestamp=1_699_000_000_000, end_timestamp=1_701_000_000_000
    )[0]["funding_rate"] == "0.0001"
    assert client.fees()["fee_schedule"][0]["category"] == "equity"


def test_non_retryable_http_errors_fail_without_retry() -> None:
    calls = 0

    def transport(path: str, params: Any) -> tuple[int, dict[str, str], Any]:
        nonlocal calls
        calls += 1
        return 403, {}, {"error": "forbidden"}

    client = PolymarketPublicClient(
        transport=transport, minimum_interval_seconds=0, retries=3
    )
    with pytest.raises(PolymarketAPIError, match="HTTP 403"):
        client.instruments()
    assert calls == 1

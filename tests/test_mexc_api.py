from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from trend_quality.mexc_api import (
    MEXCAPIError,
    MEXCPublicClient,
    is_active_cross_usdt_perpetual,
    normalize_instrument,
)


def contract(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": 17,
        "symbol": "BTC_USDT",
        "displayNameEn": "BTC_USDT PERPETUAL",
        "positionOpenType": 3,
        "futureType": 1,
        "baseCoin": "BTC",
        "quoteCoin": "USDT",
        "settleCoin": "USDT",
        "contractSize": "0.0001",
        "priceUnit": "0.1",
        "volUnit": "1",
        "minVol": "1",
        "maxVol": "400000",
        "takerFeeRate": "0.0002",
        "makerFeeRate": "0",
        "maxLeverage": 100,
        "state": 0,
        "apiAllowed": True,
        "createTime": 1_700_000_000_000,
        "conceptPlate": ["mc-trade-zone-mainly"],
    }
    base.update(overrides)
    return base


def success(data: Any) -> dict[str, Any]:
    return {"success": True, "code": 0, "data": data}


def client_for(responses: Mapping[str, Any]) -> MEXCPublicClient:
    def transport(path: str, params: Mapping[str, Any]) -> tuple[int, Any]:
        if path not in responses:
            raise AssertionError(f"Unexpected endpoint {path} with params {params}")
        response = responses[path]
        if callable(response):
            response = response(params)
        return 200, response
    return MEXCPublicClient(minimum_interval_seconds=0, retries=0, transport=transport)


def test_cross_margin_usdt_perpetual_filter_is_per_instrument() -> None:
    assert is_active_cross_usdt_perpetual(contract(positionOpenType=2))
    assert is_active_cross_usdt_perpetual(contract(positionOpenType=3))
    assert not is_active_cross_usdt_perpetual(contract(positionOpenType=1))
    assert not is_active_cross_usdt_perpetual(contract(futureType=2))
    assert not is_active_cross_usdt_perpetual(contract(state=4))
    assert not is_active_cross_usdt_perpetual(contract(quoteCoin="USDC", settleCoin="USDC"))
    assert not is_active_cross_usdt_perpetual(contract(apiAllowed=False))


def test_normalizer_preserves_contract_multipliers_and_unknown_categories() -> None:
    row = normalize_instrument(contract(
        conceptPlate=[],
        displayNameEn="NEWPAIR_USDT SWAP",
        baseCoinName="NEWPAIR",
    ))
    assert row["instrument_id"] == 17
    assert row["category"] == "unclassified"
    assert row["contract_size"] == "0.0001"
    assert row["min_quantity_base"] == "0.0001"
    assert row["max_quantity_base"] == "40.0000"
    assert row["quantity_step_contracts"] == "1"


def test_instruments_keep_all_categories_and_only_active_usdt_cross_rows() -> None:
    client = client_for({
        "/api/v1/contract/detail": success([
            contract(),
            contract(id=18, symbol="ETH_USDT", positionOpenType=2, conceptPlate=["stock"]),
            contract(id=19, symbol="ISO_USDT", positionOpenType=1),
            contract(id=20, symbol="USDC_USDC", quoteCoin="USDC", settleCoin="USDC"),
        ])
    })
    rows = client.instruments()
    assert [row["symbol"] for row in rows] == ["BTC_USDT", "ETH_USDT"]
    assert rows[0]["category"] == "crypto"
    assert rows[1]["category"] == "equity"


def test_bulk_tickers_accept_signed_funding_and_returns() -> None:
    client = client_for({
        "/api/v1/contract/ticker": success([
            {
                "symbol": "BTC_USDT",
                "lastPrice": "100",
                "fairPrice": "101",
                "indexPrice": "100.5",
                "bid1": "100.9",
                "ask1": "101.1",
                "fundingRate": "-0.0001",
                "volume24": "1200",
                "amount24": "120000",
                "holdVol": "500",
                "riseFallRate": "-0.025",
                "timestamp": 1_700_000_000_000,
            }
        ])
    })
    ticker = client.tickers()[0]
    assert ticker["mid_price"] == "101.0"
    assert ticker["funding_rate"] == "-0.0001"
    assert ticker["change_24h"] == "-0.025"
    assert ticker["turnover_24h_usdt"] == "120000"


def test_orderbook_translates_contract_depth_levels() -> None:
    client = client_for({
        "/api/v1/contract/depth/BTC_USDT": success({
            "bids": [[100, 12, 1], [99, 50, 2]],
            "asks": [[101, 10, 1], [102, 40, 2]],
            "timestamp": 1_700_000_000_000,
            "version": 99,
        })
    })
    book = client.orderbook("BTC_USDT")
    assert book["bids"][0] == {"price": "100", "quantity_contracts": "12"}
    assert book["asks"][0]["quantity_contracts"] == "10"
    assert book["version"] == 99


def test_daily_candle_arrays_are_normalized_to_milliseconds() -> None:
    stamp = 1_700_006_400
    client = client_for({
        "/api/v1/contract/kline/BTC_USDT": success({
            "time": [stamp],
            "open": [100],
            "high": [110],
            "low": [90],
            "close": [105],
            "vol": [1234],
            "amount": [129_570],
        })
    })
    rows = client.candles(
        "BTC_USDT",
        start_timestamp_ms=stamp * 1000,
        end_timestamp_ms=(stamp + 86_400) * 1000,
    )
    assert rows == [{
        "timestamp_ms": stamp * 1000,
        "open": "100",
        "high": "110",
        "low": "90",
        "close": "105",
        "volume_contracts": "1234",
        "turnover_usdt": "129570",
    }]


def test_funding_history_paginates_and_keeps_negative_rates() -> None:
    client = client_for({
        "/api/v1/contract/funding_rate/history": lambda params: success({
            "resultList": (
                [
                    {"settleTime": 1_700_000_200_000, "fundingRate": "-0.0002"},
                    {"settleTime": 1_700_000_100_000, "fundingRate": "0.0001"},
                ]
                if params["page_num"] == 1 else []
            )
        })
    })
    rows = client.funding_history(
        "BTC_USDT",
        start_timestamp_ms=1_700_000_150_000,
        end_timestamp_ms=1_700_000_300_000,
        page_size=2,
    )
    assert len(rows) == 1
    assert rows[0]["funding_rate"] == "-0.0002"


def test_only_official_mexc_api_host_is_accepted() -> None:
    with pytest.raises(ValueError, match="official MEXC"):
        MEXCPublicClient(base_url="https://example.com")


def test_malformed_market_response_fails_closed() -> None:
    client = client_for({"/api/v1/contract/detail": {"success": False, "code": 6001}})
    with pytest.raises(MEXCAPIError):
        client.contract_details()

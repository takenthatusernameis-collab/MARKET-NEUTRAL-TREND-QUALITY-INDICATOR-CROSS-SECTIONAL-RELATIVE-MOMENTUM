from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from trend_quality.mexc_api import (
    MEXCAPIError,
    MEXCForbiddenError,
    MEXCPublicClient,
    _retry_after_seconds,
    _retry_delay_seconds,
    is_active_cross_perpetual,
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


def test_cross_margin_perpetual_filter_is_per_instrument() -> None:
    assert is_active_cross_perpetual(contract(positionOpenType=2))
    assert is_active_cross_perpetual(contract(positionOpenType=3))
    assert is_active_cross_perpetual(
        contract(quoteCoin="USDC", settleCoin="USDC")
    )
    assert not is_active_cross_perpetual(contract(positionOpenType=1))
    assert not is_active_cross_perpetual(contract(futureType=2))
    assert not is_active_cross_perpetual(contract(state=4))
    assert not is_active_cross_perpetual(contract(apiAllowed=False))
    assert is_active_cross_usdt_perpetual(contract(positionOpenType=2))
    assert not is_active_cross_usdt_perpetual(
        contract(quoteCoin="USDC", settleCoin="USDC")
    )


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
    assert row["cross_margin_available"] is True
    assert row["isolated_only"] is False
    assert row["settlement"] is None
    assert row["usdt_account_eligible"] is True
    alt = normalize_instrument(contract(
        quoteCoin="USDC",
        settleCoin="USDC",
        symbol="BTC_USDC",
    ))
    assert alt["usdt_account_eligible"] is False
    assert alt["min_quantity_base"] is None


def test_instruments_research_all_cross_settlements_and_usdt_execution_subset() -> None:
    client = client_for({
        "/api/v1/contract/detail": success([
            contract(),
            contract(id=18, symbol="ETH_USDT", positionOpenType=2, conceptPlate=["stock"]),
            contract(id=19, symbol="ISO_USDT", positionOpenType=1),
            contract(id=20, symbol="BTC_USDC", quoteCoin="USDC", settleCoin="USDC"),
        ])
    })
    all_rows = client.instruments()
    usdt_rows = client.instruments(usdt_only=True)
    assert [row["symbol"] for row in all_rows] == [
        "BTC_USDT", "ETH_USDT", "BTC_USDC"
    ]
    assert [row["symbol"] for row in usdt_rows] == ["BTC_USDT", "ETH_USDT"]
    assert all_rows[0]["category"] == "crypto"
    assert all_rows[1]["category"] == "equity"
    assert all_rows[2]["usdt_account_eligible"] is False


def test_all_market_websocket_tickers_normalize_global_push() -> None:
    import json

    timestamp = 1_700_000_000_000

    class FakeWebSocket:
        def __init__(self) -> None:
            self.sent: list[str] = []
            self.messages = [
                json.dumps({"channel": "rs.sub.tickers", "data": "success"}),
                json.dumps({
                    "channel": "push.tickers",
                    "ts": timestamp,
                    "data": [
                        {
                            "symbol": "BTC_USDT",
                            "lastPrice": "100",
                            "fairPrice": "101",
                            "riseFallRate": "-0.025",
                            "volume24": "1200",
                            "timestamp": 1_699_000_000_000,
                        },
                        {
                            "symbol": "BILL_USDT",
                            "lastPrice": "0.0039",
                            "fairPrice": "0.00391",
                            "riseFallRate": "0.01",
                            "volume24": "800",
                        },
                    ],
                }),
            ]
            self.closed = False

        def send(self, message: str) -> None:
            self.sent.append(message)

        def recv(self) -> str:
            return self.messages.pop(0)

        def close(self) -> None:
            self.closed = True

    socket = FakeWebSocket()
    connections: list[tuple[str, float]] = []

    def connect(url: str, timeout: float) -> FakeWebSocket:
        connections.append((url, timeout))
        return socket

    client = MEXCPublicClient(
        minimum_interval_seconds=0,
        retries=0,
        websocket_connector=connect,
    )
    tickers = client.tickers()

    assert connections == [("wss://contract.mexc.com/edge", 12.0)]
    assert json.loads(socket.sent[0]) == {
        "method": "sub.tickers", "param": {}, "gzip": False
    }
    assert socket.closed is True
    assert [row["symbol"] for row in tickers] == ["BTC_USDT", "BILL_USDT"]
    assert tickers[0]["last_price"] == "100"
    assert tickers[0]["mark_price"] == "101"
    assert tickers[0]["mid_price"] == "101"
    assert tickers[0]["funding_rate"] == "0"
    assert tickers[0]["change_24h"] == "-0.025"
    assert tickers[0]["volume_24h_contracts"] == "1200"
    assert tickers[0]["timestamp_ms"] == timestamp


def test_single_contract_rest_ticker_is_symbol_scoped() -> None:
    client = client_for({
        "/api/v1/contract/ticker": lambda params: success({
            "symbol": "BILL_USDT",
            "lastPrice": "0.0039",
            "fairPrice": "0.00391",
            "indexPrice": "0.0039",
            "bid1": "0.00390",
            "ask1": "0.00392",
            "fundingRate": "-0.0001",
            "volume24": "1200",
            "amount24": "120000",
            "holdVol": "500",
            "riseFallRate": "-0.025",
            "timestamp": 1_700_000_000_000,
        })
    })
    ticker = client.ticker("BILL_USDT")
    assert ticker["symbol"] == "BILL_USDT"
    assert ticker["mid_price"] == "0.00391"
    assert ticker["funding_rate"] == "-0.0001"
    assert ticker["turnover_24h_quote"] == "120000"


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
        "turnover_quote": "129570",
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


def test_only_current_official_mexc_api_host_is_accepted() -> None:
    client = MEXCPublicClient(
        minimum_interval_seconds=0,
        retries=0,
        transport=lambda _path, _params: (200, success(1)),
    )
    assert client.base_url == "https://api.mexc.com"
    with pytest.raises(ValueError, match="official MEXC"):
        MEXCPublicClient(base_url="https://contract.mexc.com")
    with pytest.raises(ValueError, match="official MEXC"):
        MEXCPublicClient(base_url="https://example.com")


def test_malformed_market_response_fails_closed() -> None:
    client = client_for({"/api/v1/contract/detail": {"success": False, "code": 6001}})
    with pytest.raises(MEXCAPIError):
        client.contract_details()



def test_single_ticker_keeps_contract_when_best_quotes_are_absent() -> None:
    client = client_for({
        "/api/v1/contract/ticker": success({
            "symbol": "USDGO_USDT",
            "lastPrice": "1.25",
            "fairPrice": "1.24",
            "indexPrice": "1.25",
            "bid1": None,
            "ask1": "",
            "fundingRate": None,
            "volume24": None,
            "amount24": None,
            "holdVol": None,
            "riseFallRate": None,
            "timestamp": 1_700_000_000_000,
            "nextSettleTime": "",
        })
    })
    row = client.ticker("USDGO_USDT")
    assert row["symbol"] == "USDGO_USDT"
    assert row["bid_price"] == "0"
    assert row["ask_price"] == "0"
    assert row["mid_price"] == "1.24"
    assert row["mark_price"] == "1.24"
    assert row["funding_rate"] == "0"
    assert row["turnover_24h_quote"] == "0"
    assert row["next_funding_timestamp_ms"] is None



def test_http_403_reports_public_endpoint_and_provider_message() -> None:
    calls = 0

    def forbidden_transport(
        path: str, params: Mapping[str, Any]
    ) -> tuple[int, Any]:
        nonlocal calls
        calls += 1
        assert path == "/api/v1/contract/kline/BTC_USDT"
        return 403, {"code": 511, "message": "endpoint temporarily inaccessible"}

    client = MEXCPublicClient(
        minimum_interval_seconds=0,
        retries=3,
        transport=forbidden_transport,
    )
    with pytest.raises(MEXCForbiddenError) as raised:
        client.candles(
            "BTC_USDT",
            start_timestamp_ms=1_700_000_000_000,
            end_timestamp_ms=1_700_086_400_000,
        )

    message = str(raised.value)
    assert "HTTP 403" in message
    assert "/api/v1/contract/kline/BTC_USDT" in message
    assert "code=511" in message
    assert "endpoint temporarily inaccessible" in message
    assert "?" not in message
    assert calls == 1


def test_http_429_uses_long_exponential_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleeps: list[float] = []

    def rate_limited_then_success(
        _path: str, _params: Mapping[str, Any]
    ) -> tuple[int, Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return 429, {"success": False, "code": 510}
        return 200, success(1_700_000_000_000)

    monkeypatch.setattr("trend_quality.mexc_api.time.sleep", sleeps.append)
    client = MEXCPublicClient(
        minimum_interval_seconds=0,
        retries=1,
        transport=rate_limited_then_success,
    )
    assert client.server_time_ms() == 1_700_000_000_000
    assert calls == 2
    assert sleeps == [60.0]


def test_retry_after_is_parsed_and_never_shortens_rate_limit_cooldown() -> None:
    assert _retry_after_seconds("90") == pytest.approx(90.0)
    assert _retry_delay_seconds(429, 0, 90.0) == pytest.approx(90.0)
    assert _retry_delay_seconds(429, 1, 10.0) == pytest.approx(120.0)
    assert _retry_delay_seconds(503, 1, 10.0) == pytest.approx(10.0)


def test_public_client_uses_substantially_slower_default_request_interval() -> None:
    client = MEXCPublicClient(transport=lambda _path, _params: (200, success(1)))
    assert client.minimum_interval_seconds == pytest.approx(1.5)

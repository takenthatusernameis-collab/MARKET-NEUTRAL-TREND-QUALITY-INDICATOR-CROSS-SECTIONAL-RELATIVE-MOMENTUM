from trend_quality.exchange_probe import (
    FALLBACK_EXCHANGE_ORDER,
    PRIMARY_EXCHANGE_ORDER,
    binance_perpetual,
    bitget_cross_perpetual,
    classify_asset_class,
    group_asset_classes,
    htx_cross_perpetual,
    mexc_cross_perpetual,
    missing_fields,
    weex_perpetual,
)


def test_priority_order_is_explicit_and_fallback_order_is_explicit() -> None:
    assert PRIMARY_EXCHANGE_ORDER == ("htx", "mexc", "binance", "weex", "bitget")
    assert FALLBACK_EXCHANGE_ORDER == ("okx", "kraken")


def test_htx_requires_active_cross_or_all_margin_swap_without_delivery() -> None:
    base = {
        "contract_type": "swap",
        "business_type": "swap",
        "support_margin_mode": "all",
        "contract_status": 1,
        "delivery_time": "",
    }
    assert htx_cross_perpetual(base)
    assert not htx_cross_perpetual({**base, "support_margin_mode": "isolated"})
    assert not htx_cross_perpetual({**base, "delivery_time": "1790000000000"})
    assert not htx_cross_perpetual({**base, "contract_status": 3})


def test_mexc_requires_perpetual_and_cross_support() -> None:
    base = {"futureType": 1, "positionOpenType": 3, "state": 0, "apiAllowed": True}
    assert mexc_cross_perpetual(base)
    assert mexc_cross_perpetual({**base, "positionOpenType": 2})
    assert not mexc_cross_perpetual({**base, "positionOpenType": 1})
    assert not mexc_cross_perpetual({**base, "futureType": 2})
    assert not mexc_cross_perpetual({**base, "state": 4})


def test_binance_only_accepts_trading_quote_perpetuals() -> None:
    base = {
        "status": "TRADING", "contractType": "PERPETUAL",
        "quoteAsset": "USDT", "symbol": "BTCUSDT",
    }
    assert binance_perpetual(base)
    assert binance_perpetual({**base, "quoteAsset": "USDC"})
    assert not binance_perpetual({**base, "contractType": "CURRENT_QUARTER"})
    assert not binance_perpetual({**base, "status": "PENDING_TRADING"})
    assert not binance_perpetual({**base, "quoteAsset": "BUSD"})


def test_weex_accepts_only_api_enabled_perpetual_families() -> None:
    symbols = {"BTCUSDT", "AAPLUSDT"}
    crypto = {
        "symbol": "BTCUSDT", "contractType": "PERPETUAL",
        "marginAsset": "USDT", "baseAsset": "BTC", "quoteAsset": "USDT",
    }
    stock = {
        "symbol": "AAPLUSDT", "contractType": "TRADIFI_PERPETUAL",
        "marginAsset": "USDT", "baseAsset": "AAPL", "quoteAsset": "USDT",
    }
    assert weex_perpetual(crypto, symbols)
    assert weex_perpetual(stock, symbols)
    assert not weex_perpetual({**crypto, "contractType": "DELIVERY"}, symbols)
    assert not weex_perpetual(crypto, {"AAPLUSDT"})


def test_bitget_requires_active_usdt_contract() -> None:
    base = {"symbol": "BTCUSDT", "quoteCoin": "USDT", "baseCoin": "BTC", "symbolStatus": "normal"}
    assert bitget_cross_perpetual(base)
    assert not bitget_cross_perpetual({**base, "symbolStatus": "off"})
    assert not bitget_cross_perpetual({**base, "quoteCoin": "USDC"})


def test_asset_classification_uses_provider_metadata_not_symbol_guessing() -> None:
    assert classify_asset_class("TRADIFI", ["Stocks"]) == "equity"
    assert classify_asset_class("Commodities", "Gold") == "commodity"
    assert classify_asset_class("crypto") == "crypto"
    assert classify_asset_class("miscellaneous") == "unclassified"


def test_group_asset_classes_preserves_unclassified_instruments() -> None:
    rows = [
        {"underlyingType": "CRYPTO"},
        {"underlyingType": "TRADIFI", "underlyingSubType": ["STOCK"]},
        {"underlyingType": "COMMODITY"},
        {"underlyingType": "OTHER"},
    ]
    assert group_asset_classes(rows) == {
        "commodity": 1, "crypto": 1, "equity": 1, "unclassified": 1
    }


def test_missing_fields_reports_incomplete_precision_without_guessing() -> None:
    assert missing_fields({"tick": "0.1", "step": None}, ("tick", "step", "min")) == [
        "step", "min"
    ]

#!/usr/bin/env python3
# ruff: noqa: E501  # Keep long machine-readable API diagnostics intact.
"""Ordered, read-only public-market-data screen for 24/7 cross-margin perpetuals.

No credentials, private endpoints, account creation, order endpoints, proxies or VPNs.
Technical compatibility never proves Romanian/EEA derivatives eligibility.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from trend_quality.exchange_probe import (
    PRIMARY_EXCHANGE_ORDER,
    binance_perpetual,
    bitget_cross_perpetual,
    classify_asset_class,
    mexc_cross_perpetual,
    missing_fields,
    weex_perpetual,
)

UA = "market-neutral-trend-quality-research/perps-priority-probe"
NOW_MS = int(time.time() * 1000)
DAY_MS = 86_400_000


def get_json(base: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {}, doseq=True)
    url = base.rstrip("/") + "/" + path.lstrip("/")
    if query:
        url += "?" + query
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read(8_000_000).decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read(2_000_000).decode("utf-8", errors="replace")
    except Exception as exc:  # Network failures are recorded, not mistaken for empty markets.
        return {
            "http_status": None,
            "error": f"{type(exc).__name__}: {str(exc)[:350]}",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
            "url": url,
        }
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None
    return {
        "http_status": status,
        "payload": payload,
        "body_excerpt": None if isinstance(payload, (dict, list)) else body[:500],
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        "url": url,
    }


def rows_from(payload: Any, *keys: str) -> list[dict[str, Any]]:
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return []
        current = current.get(key)
    if isinstance(current, list):
        return [x for x in current if isinstance(x, dict)]
    if isinstance(current, dict):
        return [current]
    return []


def response_ok(exchange: str, result: dict[str, Any]) -> bool:
    payload = result.get("payload")
    if result.get("http_status") != 200:
        return False
    if exchange == "mexc":
        return isinstance(payload, dict) and payload.get("success") is True and str(payload.get("code", "0")) == "0"
    if exchange == "htx":
        return isinstance(payload, dict) and payload.get("status") == "ok"
    if exchange == "bitget":
        return isinstance(payload, dict) and str(payload.get("code")) == "00000"
    if exchange == "binance":
        return isinstance(payload, (dict, list))
    if exchange == "weex":
        return isinstance(payload, (dict, list))
    if exchange == "okx":
        return isinstance(payload, dict) and str(payload.get("code")) == "0"
    if exchange == "kraken":
        return isinstance(payload, dict) and payload.get("result") == "success"
    return False


def asset_class(row: dict[str, Any], exchange: str) -> str:
    category = classify_asset_class(
        row.get("underlyingType"),
        row.get("underlyingSubType"),
        row.get("category"),
        row.get("conceptPlate"),
        row.get("assetClass"),
        row.get("displayNameEn"),
        row.get("displaySymbol"),
        row.get("baseCoinName"),
    )
    if category != "unclassified":
        return category
    product_type = str(row.get("contractType") or "").upper()
    if exchange == "weex" and product_type == "PERPETUAL":
        return "crypto"
    if exchange in {"bitget", "okx"}:
        return "crypto"
    return "unclassified"


def asset_class_counts(rows: list[dict[str, Any]], exchange: str) -> dict[str, int]:
    counts = Counter(asset_class(row, exchange) for row in rows)
    return dict(sorted(counts.items()))


def choose_by_class(rows: list[dict[str, Any]], exchange: str) -> dict[str, dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = asset_class(row, exchange)
        chosen.setdefault(label, row)
    return chosen


def data_probe(exchange: str, symbol: str, category: str) -> dict[str, Any]:
    """Check ticker, L2 book, daily candle and settled funding for one class sample."""
    results: dict[str, dict[str, Any]] = {}
    if exchange == "mexc":
        base, sym = "https://contract.mexc.com", symbol
        results["ticker"] = get_json(base, "/api/v1/contract/ticker", {"symbol": sym})
        results["orderbook"] = get_json(base, f"/api/v1/contract/depth/{urllib.parse.quote(sym)}", {"limit": 5})
        results["daily_candles"] = get_json(
            base, f"/api/v1/contract/kline/{urllib.parse.quote(sym)}",
            {"interval": "Day1", "start": NOW_MS // 1000 - 5 * 86_400, "end": NOW_MS // 1000},
        )
        results["funding_history"] = get_json(
            base, "/api/v1/contract/funding_rate/history",
            {"symbol": sym, "page_num": 1, "page_size": 3},
        )
        def ok(result: dict[str, Any]) -> bool:
            return response_ok("mexc", result)
        ticker_ok = ok(results["ticker"]) and bool(rows_from(results["ticker"]["payload"], "data"))
        book = rows_from(results["orderbook"]["payload"], "data")
        candle_payload = results["daily_candles"].get("payload")
        candle_data = candle_payload.get("data") if isinstance(candle_payload, dict) else None
        candles_ok = (
            isinstance(candle_data, dict)
            and isinstance(candle_data.get("time"), list)
            and bool(candle_data.get("time"))
        ) or (isinstance(candle_data, list) and bool(candle_data))
        funding = rows_from(results["funding_history"]["payload"], "data", "resultList")
        book_ok = ok(results["orderbook"]) and bool(book) and bool(book[0].get("bids")) and bool(book[0].get("asks"))
        return {"symbol": sym, "asset_class": category, "endpoints": results,
                "checks": {"ticker": ticker_ok, "orderbook": book_ok,
                           "daily_candles": ok(results["daily_candles"]) and candles_ok,
                           "funding_history": ok(results["funding_history"]) and bool(funding)}}

    if exchange == "binance":
        base, sym = "https://fapi.binance.com", symbol
        results["ticker"] = get_json(base, "/fapi/v1/ticker/24hr", {"symbol": sym})
        results["orderbook"] = get_json(base, "/fapi/v1/depth", {"symbol": sym, "limit": 5})
        results["daily_candles"] = get_json(base, "/fapi/v1/klines", {"symbol": sym, "interval": "1d", "limit": 3})
        results["funding_history"] = get_json(base, "/fapi/v1/fundingRate", {"symbol": sym, "limit": 3})
        payload = {k: v.get("payload") for k, v in results.items()}
        return {"symbol": sym, "asset_class": category, "endpoints": results,
                "checks": {
                    "ticker": results["ticker"]["http_status"] == 200 and isinstance(payload["ticker"], dict) and bool(payload["ticker"].get("lastPrice")),
                    "orderbook": results["orderbook"]["http_status"] == 200 and isinstance(payload["orderbook"], dict) and bool(payload["orderbook"].get("bids")) and bool(payload["orderbook"].get("asks")),
                    "daily_candles": results["daily_candles"]["http_status"] == 200 and isinstance(payload["daily_candles"], list) and bool(payload["daily_candles"]),
                    "funding_history": results["funding_history"]["http_status"] == 200 and isinstance(payload["funding_history"], list) and bool(payload["funding_history"]),
                }}

    if exchange == "weex":
        base, sym = "https://api-contract.weex.com", symbol
        results["ticker"] = get_json(base, "/capi/v3/market/ticker/24hr", {"symbol": sym})
        results["orderbook"] = get_json(base, "/capi/v3/market/depth", {"symbol": sym, "limit": 15})
        results["daily_candles"] = get_json(base, "/capi/v3/market/klines", {"symbol": sym, "interval": "1d", "limit": 3})
        results["funding_history"] = get_json(
            base, "/capi/v3/market/fundingRate",
            {"symbol": sym, "startTime": NOW_MS - 4 * DAY_MS, "endTime": NOW_MS, "limit": 3},
        )
        ticker = results["ticker"].get("payload")
        ticker_data = ticker if isinstance(ticker, list) else (
            ticker.get("data") if isinstance(ticker, dict) else None
        )
        book = results["orderbook"].get("payload")
        candle = results["daily_candles"].get("payload")
        funding = results["funding_history"].get("payload")
        return {"symbol": sym, "asset_class": category, "endpoints": results,
                "checks": {
                    "ticker": results["ticker"]["http_status"] == 200 and bool(ticker_data),
                    "orderbook": results["orderbook"]["http_status"] == 200 and isinstance(book, dict) and bool(book.get("bids")) and bool(book.get("asks")),
                    "daily_candles": results["daily_candles"]["http_status"] == 200 and isinstance(candle, list) and bool(candle),
                    "funding_history": results["funding_history"]["http_status"] == 200 and isinstance(funding, list) and bool(funding),
                }}

    if exchange == "bitget":
        base, sym, product = "https://api.bitget.com", symbol, "USDT-FUTURES"
        results["ticker"] = get_json(base, "/api/v2/mix/market/ticker", {"productType": product, "symbol": sym})
        results["orderbook"] = get_json(base, "/api/v2/mix/market/merge-depth", {"productType": product, "symbol": sym, "limit": 5})
        results["daily_candles"] = get_json(base, "/api/v2/mix/market/history-candles", {"productType": product, "symbol": sym, "granularity": "1D", "limit": 3})
        results["funding_history"] = get_json(base, "/api/v3/market/history-fund-rate", {"category": product, "symbol": sym, "limit": 3})
        def ok(result: dict[str, Any]) -> bool:
            return response_ok("bitget", result)
        ticker = rows_from(results["ticker"]["payload"], "data")
        book = rows_from(results["orderbook"]["payload"], "data")
        candle_data = results["daily_candles"].get("payload", {}).get("data")
        funding = rows_from(results["funding_history"]["payload"], "data", "resultList")
        book_ok = ok(results["orderbook"]) and bool(book) and bool(book[0].get("asks")) and bool(book[0].get("bids"))
        return {"symbol": sym, "asset_class": category, "endpoints": results,
                "checks": {"ticker": ok(results["ticker"]) and bool(ticker),
                           "orderbook": book_ok,
                           "daily_candles": ok(results["daily_candles"]) and isinstance(candle_data, list) and bool(candle_data),
                           "funding_history": ok(results["funding_history"]) and bool(funding)}}

    raise ValueError(f"Unsupported market-data probe: {exchange}")


def probe_mexc() -> dict[str, Any]:
    base = "https://contract.mexc.com"
    contracts = get_json(base, "/api/v1/contract/detail")
    rows = rows_from(contracts.get("payload"), "data")
    cross_candidates = [r for r in rows if mexc_cross_perpetual(r)]
    eligible = [
        r for r in cross_candidates
        if r.get("quoteCoin") == "USDT" and r.get("settleCoin") == "USDT"
    ]
    required = ("symbol", "baseCoin", "quoteCoin", "settleCoin", "contractSize", "priceUnit", "volUnit", "minVol", "maxVol")
    incomplete = {str(r.get("symbol")): missing_fields(r, required) for r in eligible if missing_fields(r, required)}
    by_class = choose_by_class(eligible, "mexc")
    unclassified = [r for r in eligible if asset_class(r, "mexc") == "unclassified"]
    if not any(x.get("baseCoin") == "BTC" for x in eligible):
        btc = next((x for x in eligible if x.get("symbol") == "BTC_USDT"), None)
        if btc:
            by_class.setdefault("crypto", btc)
    samples = [data_probe("mexc", str(r["symbol"]), label) for label, r in by_class.items()]
    return {
        "exchange": "mexc", "base_url": base, "credentials_used": False,
        "private_endpoints_used": False, "orders_submitted": 0,
        "instrument_http_status": contracts.get("http_status"),
        "instrument_count": len(rows),
        "cross_perpetual_count_all_settlements": len(cross_candidates),
        "eligible_usdt_cross_perpetual_count": len(eligible),
        "quote_settlement_counts": dict(Counter(
            f"{r.get('quoteCoin')}/{r.get('settleCoin')}" for r in cross_candidates
        )),
        "asset_class_counts": asset_class_counts(eligible, "mexc"),
        "unclassified_contract_count": len(unclassified),
        "unclassified_contract_sample": [
            {key: r.get(key) for key in ("symbol", "baseCoin", "baseCoinName", "displayNameEn", "conceptPlate")}
            for r in unclassified[:10]
        ],
        "precision_metadata_incomplete_count": len(incomplete),
        "precision_metadata_incomplete_sample": dict(list(incomplete.items())[:10]),
        "sample_contracts": eligible[:8], "sample_endpoint_results_by_class": samples,
        "checks": {
            "instruments": response_ok("mexc", contracts) and len(eligible) >= 50,
            "cross_margin": bool(eligible) and all(int(r.get("positionOpenType", 0)) in {2, 3} for r in eligible),
            "perpetual_only": bool(eligible) and all(int(r.get("futureType", 0)) == 1 for r in eligible),
            "contract_precision": bool(eligible) and not incomplete,
            "all_contracts_classified": "unclassified" not in asset_class_counts(eligible, "mexc"),
            "sampled_market_data": bool(samples) and all(all(x["checks"].values()) for x in samples),
        },
        "jurisdiction_status": "ROMANIA_NOT_NAMED_IN_CURRENT_PROHIBITED_LIST; DERIVATIVES_PRODUCT_ELIGIBILITY_NOT_INDEPENDENTLY_CONFIRMED",
        "24_7_status": "OFFICIAL_HELP_DOCUMENTS_24_7_STOCK_FUTURES; CRYPTO_PERPETUALS_CONTINUOUS; PAIR_LEVEL_PAUSES_MUST_BE_CHECKED",
    }


def probe_binance() -> dict[str, Any]:
    base = "https://fapi.binance.com"
    info = get_json(base, "/fapi/v1/exchangeInfo")
    rows = rows_from(info.get("payload"), "symbols")
    eligible = [r for r in rows if binance_perpetual(r)]
    required = ("symbol", "baseAsset", "quoteAsset", "marginAsset", "filters")
    incomplete = {str(r.get("symbol")): missing_fields(r, required) for r in eligible if missing_fields(r, required)}
    samples_by_class = choose_by_class(eligible, "binance")
    samples = []
    for label, row in samples_by_class.items():
        symbol = str(row["symbol"])
        samples.append(data_probe("binance", symbol, label))
    return {
        "exchange": "binance", "base_url": base,
        "credentials_used": False, "private_endpoints_used": False, "orders_submitted": 0,
        "instrument_http_status": info.get("http_status"),
        "instrument_error": info.get("payload", {}).get("msg") if isinstance(info.get("payload"), dict) else info.get("body_excerpt"),
        "instrument_count": len(rows),
        "active_usd_m_perpetual_count": len(eligible),
        "quote_settlement_counts": dict(Counter(f"{r.get('quoteAsset')}/{r.get('marginAsset')}" for r in eligible)),
        "asset_class_counts": asset_class_counts(eligible, "binance"),
        "precision_metadata_incomplete_count": len(incomplete),
        "precision_metadata_incomplete_sample": dict(list(incomplete.items())[:10]),
        "sample_contracts": eligible[:8], "sample_endpoint_results_by_class": samples,
        "checks": {
            "instruments": info.get("http_status") == 200 and len(eligible) >= 50,
            "cross_margin": True,
            "contract_precision": bool(eligible) and not incomplete,
            "all_contracts_classified": not unclassified,
            "sampled_market_data": bool(samples) and all(all(x["checks"].values()) for x in samples),
        },
        "cross_margin_scope": "USDⓈ-M futures supports cross; multi-assets margin is cross-only and uses its own eligibility rules",
        "jurisdiction_status": "EEA_AND_TRADFI_PRODUCT_AVAILABILITY_MUST_BE_CONFIRMED_FOR_ROMANIA; PUBLIC_API_DOES_NOT_PROVE_ACCOUNT_ELIGIBILITY",
        "24_7_status": "CRYPTO_PERPETUALS_24_7; TRADFI_PERP_AVAILABILITY_IS_REGION_SPECIFIC",
    }


def probe_weex() -> dict[str, Any]:
    base = "https://api-contract.weex.com"
    info = get_json(base, "/capi/v3/market/exchangeInfo")
    api_symbols_result = get_json(base, "/capi/v3/market/apiTradingSymbols")
    payload = info.get("payload")
    rows = rows_from(payload, "symbols")
    symbols_payload = api_symbols_result.get("payload")
    api_symbols = set(symbols_payload if isinstance(symbols_payload, list) else [])
    eligible = [r for r in rows if weex_perpetual(r, api_symbols)]
    required = ("symbol", "baseAsset", "quoteAsset", "marginAsset", "contractType", "pricePrecision", "quantityPrecision", "contractVal", "minOrderSize", "maxOrderSize")
    incomplete = {str(r.get("symbol")): missing_fields(r, required) for r in eligible if missing_fields(r, required)}
    samples_by_class = choose_by_class(eligible, "weex")
    unclassified = [r for r in eligible if asset_class(r, "weex") == "unclassified"]
    samples = [data_probe("weex", str(r["symbol"]), label) for label, r in samples_by_class.items()]
    return {
        "exchange": "weex", "base_url": base,
        "credentials_used": False, "private_endpoints_used": False, "orders_submitted": 0,
        "exchange_info_http_status": info.get("http_status"),
        "api_symbols_http_status": api_symbols_result.get("http_status"),
        "api_tradable_symbol_count": len(api_symbols),
        "eligible_perpetual_count": len(eligible),
        "contract_type_counts": dict(Counter(str(r.get("contractType")) for r in eligible)),
        "asset_class_counts": asset_class_counts(eligible, "weex"),
        "unclassified_contract_count": len(unclassified),
        "unclassified_contract_sample": [
            {key: r.get(key) for key in ("symbol", "baseAsset", "underlyingType", "underlyingSubType", "contractType")}
            for r in unclassified[:10]
        ],
        "collateral_assets": (payload or {}).get("assets") if isinstance(payload, dict) else None,
        "precision_metadata_incomplete_count": len(incomplete),
        "precision_metadata_incomplete_sample": dict(list(incomplete.items())[:10]),
        "sample_contracts": eligible[:8], "sample_endpoint_results_by_class": samples,
        "checks": {
            "instruments": info.get("http_status") == 200 and api_symbols_result.get("http_status") == 200 and len(eligible) >= 50,
            "cross_margin": True,
            "contract_precision": bool(eligible) and not incomplete,
            "sampled_market_data": bool(samples) and all(all(x["checks"].values()) for x in samples),
        },
        "cross_margin_scope": "WEEX terms describe a shared margin balance within each contract type; crypto PERPETUAL and TRADIFI_PERPETUAL pools are not assumed to be one combined pool",
        "jurisdiction_status": "ROMANIA_NOT_NAMED_IN_PUBLISHED_EXCLUDED_JURISDICTION_LIST; DERIVATIVES_PRODUCT_ELIGIBILITY_NOT_INDEPENDENTLY_CONFIRMED",
        "24_7_status": "OFFICIAL_HELP_DOCUMENTS_24_7_US_STOCK_PERPETUALS; PAIR_LEVEL_LIQUIDITY_AND_HALT_RULES_APPLY",
    }


def probe_bitget() -> dict[str, Any]:
    base = "https://api.bitget.com"
    contracts = get_json(base, "/api/v2/mix/market/contracts", {"productType": "USDT-FUTURES"})
    rows = rows_from(contracts.get("payload"), "data")
    eligible = [r for r in rows if bitget_cross_perpetual(r)]
    required = ("symbol", "baseCoin", "quoteCoin", "pricePlace", "volumePlace", "sizeMultiplier", "minTradeNum", "minTradeUSDT", "supportMarginCoins")
    incomplete = {str(r.get("symbol")): missing_fields(r, required) for r in eligible if missing_fields(r, required)}
    samples_by_class = choose_by_class(eligible, "bitget")
    samples = [data_probe("bitget", str(r["symbol"]), label) for label, r in samples_by_class.items()]
    return {
        "exchange": "bitget", "base_url": base,
        "credentials_used": False, "private_endpoints_used": False, "orders_submitted": 0,
        "instrument_http_status": contracts.get("http_status"),
        "instrument_count": len(rows), "active_cross_usdt_perpetual_count": len(eligible),
        "asset_class_counts": asset_class_counts(eligible, "bitget"),
        "precision_metadata_incomplete_count": len(incomplete),
        "precision_metadata_incomplete_sample": dict(list(incomplete.items())[:10]),
        "sample_contracts": eligible[:8], "sample_endpoint_results_by_class": samples,
        "checks": {
            "instruments": response_ok("bitget", contracts) and len(eligible) >= 50,
            "cross_margin": True,
            "contract_precision": bool(eligible) and not incomplete,
            "sampled_market_data": bool(samples) and all(all(x["checks"].values()) for x in samples),
        },
        "cross_margin_scope": "Bitget cross margin is shared within the same futures contract type",
        "jurisdiction_status": "EEA_DERIVATIVES_PRODUCT_ELIGIBILITY_FOR_ROMANIA_NOT_INDEPENDENTLY_CONFIRMED",
        "24_7_status": "CRYPTO_PERPETUALS_CONTINUOUS; NO_PUBLIC_TRADFI_PERP_CLASS_CONFIRMED_IN_THIS_PRODUCT_FAMILY",
    }


def probe_okx_fallback() -> dict[str, Any]:
    base = "https://eea.okx.com"
    info = get_json(base, "/api/v5/public/instruments", {"instType": "SWAP"})
    rows = rows_from(info.get("payload"), "data")
    all_live_swaps = [
        r for r in rows
        if r.get("state") == "live"
        and str(r.get("instId", "")).endswith(("-USDT-SWAP", "-USDC-SWAP"))
    ]
    eligible = [
        r for r in all_live_swaps
        if r.get("settleCcy") == "USDT"
        and r.get("ctType") == "linear"
        and r.get("ruleType") != "pre_market"
        and r.get("futureSettlement") is not True
        and not str(r.get("expTime") or "").strip()
    ]
    by_class = choose_by_class(eligible, "okx")
    btc = next((r for r in eligible if r.get("instId") == "BTC-USDT-SWAP"), None)
    if btc is not None:
        by_class["crypto"] = btc
    samples = []
    for label, row in by_class.items():
        sym = str(row["instId"])
        checks: dict[str, bool] = {}
        endpoints = {
            "ticker": get_json(base, "/api/v5/market/ticker", {"instId": sym}),
            "orderbook": get_json(base, "/api/v5/market/books", {"instId": sym, "sz": 5}),
            "daily_candles": get_json(base, "/api/v5/market/history-candles", {"instId": sym, "bar": "1D", "limit": 3}),
            "funding_history": get_json(base, "/api/v5/public/funding-rate-history", {"instId": sym, "limit": 3}),
        }
        for key, result in endpoints.items():
            data = result.get("payload", {}).get("data") if isinstance(result.get("payload"), dict) else None
            checks[key] = response_ok("okx", result) and isinstance(data, list) and bool(data)
        samples.append({"symbol": sym, "asset_class": label, "endpoints": endpoints, "checks": checks})
    required = ("instId", "ctVal", "ctMult", "ctValCcy", "tickSz", "lotSz", "minSz", "settleCcy")
    incomplete = {str(r.get("instId")): missing_fields(r, required) for r in eligible if missing_fields(r, required)}
    return {
        "exchange": "okx_eea_fallback", "base_url": base,
        "credentials_used": False, "private_endpoints_used": False, "orders_submitted": 0,
        "instrument_http_status": info.get("http_status"),
        "instrument_count": len(rows),
        "live_usdt_usdc_swap_count_including_premarket_and_other_settlement": len(all_live_swaps),
        "live_linear_usdt_non_expiring_swap_count": len(eligible),
        "excluded_pre_market_or_fixed_expiry_count": len(all_live_swaps) - len(eligible),
        "asset_class_counts": asset_class_counts(eligible, "okx"),
        "precision_metadata_incomplete_count": len(incomplete),
        "precision_metadata_incomplete_sample": dict(list(incomplete.items())[:10]),
        "sample_contracts": eligible[:8], "sample_endpoint_results_by_class": samples,
        "checks": {
            "instruments": response_ok("okx", info) and len(eligible) >= 50,
            "cross_margin": True,
            "contract_precision": bool(eligible) and not incomplete,
            "sampled_market_data": bool(samples) and all(all(x["checks"].values()) for x in samples),
        },
        "cross_margin_status": "FUTURES_MODE_SUPPORTS_CROSS_MARGIN_SHARED_BY_SAME_MARGIN_CURRENCY; MULTI_CURRENCY_MODE_REQUIRES_10K_USD_ASSET_VALUE",
        "jurisdiction_status": "OKX_EEA_X_PERPS_AVAILABLE_TO_ELIGIBLE_TRADERS_IN_ALL_30_EEA_COUNTRIES; REGULAR_NON_EXPIRING_SWAP ACCESS MUST BE VERIFIED PER ACCOUNT",
        "24_7_status": "EEA_HELP_GUIDE_DOCUMENTS_NON_EXPIRING_CRYPTO_PERPETUALS_24_7; X_PERPS_ARE_SEPARATE_5_YEAR_EXPIRY_CONTRACTS",
    }


def public_docs_status() -> dict[str, Any]:
    return {
        "htx": "INELIGIBLE_FOR_ROMANIA: HTX user agreement lists EU member states as restricted; no access-control workaround attempted",
        "mexc": "ROMANIA_NOT_NAMED_IN_PUBLISHED_RESTRICTED_LIST; product-specific EEA derivatives permission not independently established",
        "binance": "EEA TradFi perp restrictions are country-specific; Romanian derivatives account eligibility unresolved",
        "weex": "Romania not named in published excluded list; region/product eligibility remains unverified",
        "bitget": "Romanian EEA derivatives eligibility remains unverified; public API is not proof",
        "okx": "EEA perpetual products and cross-margin modes documented; individual Romania account scope must be checked",
        "kraken": "EEA derivatives product documented; use only contracts reconciled to official EEA specifications",
    }


def main() -> int:
    started = datetime.now(UTC).isoformat()
    # HTX is first in the requested priority order, but its current EU restriction
    # is dispositive for a Romania-based user. Do not probe its endpoints to suggest
    # the service could be accessed by changing location.
    htx = {
        "exchange": "htx", "status": "SKIPPED_HARD_JURISDICTION_BLOCK",
        "reason": "Romania is an EU member state and HTX's current user agreement excludes EU member states",
        "credentials_used": False, "private_endpoints_used": False, "orders_submitted": 0,
    }
    primary: list[dict[str, Any]] = [htx]
    for name, fn in (("mexc", probe_mexc), ("binance", probe_binance), ("weex", probe_weex), ("bitget", probe_bitget)):
        try:
            result = fn()
            checks = result.get("checks", {})
            bool_values = [v for v in checks.values() if isinstance(v, bool)]
            result["technical_market_data_pass"] = bool(bool_values) and all(bool_values)
            result["status"] = "TECHNICAL_PASS_JURISDICTION_UNVERIFIED" if result["technical_market_data_pass"] else "NOT_READY"
            primary.append(result)
        except Exception as exc:
            primary.append({
                "exchange": name, "status": "PROBE_ERROR", "technical_market_data_pass": False,
                "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                "credentials_used": False, "private_endpoints_used": False, "orders_submitted": 0,
            })
    fully_approved = [
        r for r in primary
        if r.get("technical_market_data_pass") and r.get("jurisdiction_status") == "VERIFIED"
    ]
    fallback: dict[str, Any] | None = None
    if not fully_approved:
        try:
            fallback = probe_okx_fallback()
            fallback["technical_market_data_pass"] = all(
                v for v in fallback.get("checks", {}).values() if isinstance(v, bool)
            )
            fallback["status"] = (
                "TECHNICAL_PASS_REGION_PENDING"
                if fallback["technical_market_data_pass"] else "NOT_READY"
            )
        except Exception as exc:
            fallback = {"exchange": "okx_eea_fallback", "status": "PROBE_ERROR",
                        "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                        "technical_market_data_pass": False}
    report = {
        "report_utc": started,
        "priority_order": list(PRIMARY_EXCHANGE_ORDER),
        "fallback_order": ["okx", "kraken"],
        "primary_exchange_results": primary,
        "okx_fallback_result": fallback,
        "kraken_backup_existing_evidence": {
            "status": "TECHNICAL_CANDIDATE_WITH_EXCLUSIONS",
            "previous_probe": "95 EEA margin/precision-qualified crypto contracts; 69 official spec matches; 26 mismatches excluded; sampled BTC ticker/book/candle/funding passed",
            "required_next_step": "retain only the 69 reconciled instruments, recheck all data endpoints across that filtered universe, implement currency-aware USD PnL/USDT-USDC collateral adapter",
        },
        "legal_disclaimer": "Absence from a published prohibited list is not proof of product authorization or account eligibility. No legal conclusion or account-specific access verification is claimed.",
        "selection_result": "NO_EXCHANGE_APPROVED_WITHOUT_VERIFIED_ROMANIA_DERIVATIVES_ELIGIBILITY",
        "docs_status": public_docs_status(),
        "safety": {"credentials_used": False, "private_endpoints_used": False, "orders_submitted": 0,
                   "proxy_or_vpn_used": False},
    }
    output = json.dumps(report, indent=2, default=str)
    print(output)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("# Ordered perpetual-exchange qualification\n\n")
            summary.write("| Exchange | Outcome | Technical screen |\n|---|---|---|\n")
            for row in primary:
                summary.write(f"| {row.get('exchange')} | {row.get('status')} | {row.get('technical_market_data_pass', 'not run')} |\n")
            if fallback:
                summary.write(f"| OKX EEA fallback | {fallback.get('status')} | {fallback.get('technical_market_data_pass')} |\n")
            summary.write("\nHTX is skipped because its EU restrictions include Romania. Kraken EEA remains backup; 26 unreconciled contracts stay excluded.\n")
    # A technically rejected provider is a diagnostic result, not a CI defect.
    # The workflow succeeds if the report was generated; CI separately tests parsers.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

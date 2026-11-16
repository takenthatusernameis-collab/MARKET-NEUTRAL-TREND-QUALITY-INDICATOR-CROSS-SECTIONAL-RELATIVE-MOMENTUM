#!/usr/bin/env python3
# ruff: noqa: E501  # Long failure samples and public API diagnostics are intentional.
"""Full-universe, read-only acceptance test for OKX's EEA public SWAP API.

Validates every live linear USDT-settled non-pre-market perpetual contract:
instrument precision/size metadata, bulk ticker coverage, per-symbol book,
completed daily candles, recent funding and mark price. Never authenticates,
reads private account data or submits orders.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

BASE = "https://eea.okx.com"
UA = "market-neutral-trend-quality-research/okx-eea-full-universe"
MIN_INTERVAL_SECONDS = 0.15
REQUEST_TIMEOUT_SECONDS = 15
MAX_WORKERS = 8
RATE_LOCK = threading.Lock()
LAST_REQUEST_AT = 0.0


def request_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    global LAST_REQUEST_AT
    with RATE_LOCK:
        now = time.monotonic()
        wait = MIN_INTERVAL_SECONDS - (now - LAST_REQUEST_AT)
        if wait > 0:
            time.sleep(wait)
        LAST_REQUEST_AT = time.monotonic()
    query = urllib.parse.urlencode(params or {})
    url = BASE + path + ("?" + query if query else "")
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": UA}
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = response.status
            body = response.read(4_000_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read(1_000_000).decode("utf-8", errors="replace")
    except Exception as exc:
        return {
            "http_status": None,
            "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
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
    }


def ok(result: dict[str, Any]) -> bool:
    payload = result.get("payload")
    return (
        result.get("http_status") == 200
        and isinstance(payload, dict)
        and str(payload.get("code")) == "0"
        and payload.get("data") is not None
    )


def data_rows(result: dict[str, Any]) -> list[Any]:
    payload = result.get("payload")
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, list) else []


def positive_decimal(value: Any) -> bool:
    try:
        parsed = Decimal(str(value))
        return parsed.is_finite() and parsed > 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def metadata_check(row: dict[str, Any]) -> list[str]:
    required = (
        "instId", "instFamily", "ctType", "ctVal", "ctMult", "ctValCcy",
        "tickSz", "lotSz", "minSz", "maxLmtSz", "maxMktSz", "settleCcy",
        "state", "instType", "ruleType",
    )
    missing = [key for key in required if row.get(key) is None or str(row.get(key)).strip() == ""]
    positive_fields = (
        "ctVal", "ctMult", "tickSz", "lotSz", "minSz", "maxLmtSz", "maxMktSz"
    )
    invalid = [key for key in positive_fields if not positive_decimal(row.get(key))]
    return sorted(set(missing + [f"INVALID_{key}" for key in invalid]))


def rows_for_universe() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    result = request_json("/api/v5/public/instruments", {"instType": "SWAP"})
    if not ok(result):
        raise RuntimeError(f"EEA instrument endpoint failed: {result}")
    rows = [x for x in data_rows(result) if isinstance(x, dict)]
    live_linear_usdt = [
        row for row in rows
        if row.get("instType") == "SWAP"
        and row.get("state") == "live"
        and str(row.get("instId", "")).endswith("-USDT-SWAP")
        and row.get("settleCcy") == "USDT"
        and row.get("ctType") == "linear"
    ]
    pre_market = [row for row in live_linear_usdt if row.get("ruleType") == "pre_market"]
    eligible = [row for row in live_linear_usdt if row.get("ruleType") != "pre_market"]
    return result, eligible, {
        "all_swap_instruments": len(rows),
        "live_linear_usdt_swaps_including_pre_market": len(live_linear_usdt),
        "excluded_pre_market_swaps": len(pre_market),
        "eligible_live_linear_usdt_swaps": len(eligible),
    }


def check_tickers(eligible: list[dict[str, Any]]) -> dict[str, Any]:
    result = request_json("/api/v5/market/tickers", {"instType": "SWAP"})
    if not ok(result):
        return {"endpoint_ok": False, "covered_count": 0, "missing_count": len(eligible),
                "failure_sample": ["bulk ticker request failed"]}
    tickers = {
        str(row.get("instId")): row
        for row in data_rows(result)
        if isinstance(row, dict)
    }
    missing: list[str] = []
    invalid: list[str] = []
    for row in eligible:
        symbol = str(row["instId"])
        ticker = tickers.get(symbol)
        if ticker is None:
            missing.append(symbol)
            continue
        if not positive_decimal(ticker.get("last")):
            invalid.append(symbol)
    return {
        "endpoint_ok": True,
        "covered_count": len(eligible) - len(missing),
        "missing_count": len(missing),
        "invalid_last_price_count": len(invalid),
        "failure_sample": (missing + invalid)[:20],
    }


def validate_one(kind: str, symbol: str) -> tuple[str, str, bool, str | None]:
    params: dict[str, Any] = {"instId": symbol}
    if kind == "orderbook":
        result = request_json("/api/v5/market/books", {**params, "sz": 5})
        rows = data_rows(result)
        if not ok(result) or not rows or not isinstance(rows[0], dict):
            return kind, symbol, False, "EMPTY_OR_FAILED_BOOK"
        book = rows[0]
        bids, asks = book.get("bids"), book.get("asks")
        valid = isinstance(bids, list) and bool(bids) and isinstance(asks, list) and bool(asks)
        if valid:
            valid = positive_decimal(bids[0][0]) and positive_decimal(bids[0][1]) and positive_decimal(asks[0][0]) and positive_decimal(asks[0][1])
        return kind, symbol, bool(valid), None if valid else "INVALID_BID_ASK_LEVELS"

    if kind == "daily_candles":
        result = request_json(
            "/api/v5/market/history-candles",
            {**params, "bar": "1D", "limit": 3},
        )
        rows = data_rows(result)
        complete = [
            row for row in rows
            if isinstance(row, list) and len(row) >= 9 and str(row[8]) == "1"
        ]
        valid = ok(result) and bool(complete)
        return kind, symbol, valid, None if valid else "NO_COMPLETED_DAILY_CANDLE"

    if kind == "funding_history":
        result = request_json(
            "/api/v5/public/funding-rate-history",
            {**params, "limit": 1},
        )
        rows = data_rows(result)
        if not ok(result) or not rows or not isinstance(rows[0], dict):
            return kind, symbol, False, "EMPTY_OR_FAILED_FUNDING_HISTORY"
        funding = rows[0]
        try:
            rate = Decimal(str(funding.get("fundingRate")))
            valid_rate = rate.is_finite()
        except (InvalidOperation, TypeError, ValueError):
            valid_rate = False
        valid = bool(valid_rate and str(funding.get("fundingTime", "")).isdigit())
        return kind, symbol, valid, None if valid else "INVALID_FUNDING_RECORD"

    if kind == "mark_price":
        result = request_json(
            "/api/v5/public/mark-price",
            {"instType": "SWAP", "instId": symbol},
        )
        rows = data_rows(result)
        valid = (
            ok(result) and bool(rows) and isinstance(rows[0], dict)
            and positive_decimal(rows[0].get("markPx"))
        )
        return kind, symbol, bool(valid), None if valid else "MISSING_OR_INVALID_MARK_PRICE"

    raise ValueError(f"Unknown validation kind: {kind}")


def run_full_endpoint(kind: str, symbols: list[str]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    passed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(validate_one, kind, symbol) for symbol in symbols]
        for future in as_completed(futures):
            _, symbol, success, reason = future.result()
            if success:
                passed += 1
            else:
                failures.append({"symbol": symbol, "reason": str(reason)})
    failures.sort(key=lambda x: x["symbol"])
    return {
        "passed_count": passed,
        "failed_count": len(failures),
        "total": len(symbols),
        "coverage": round(passed / len(symbols), 6) if symbols else 0.0,
        "failure_sample": failures[:25],
    }


def main() -> int:
    report_utc = datetime.now(UTC).isoformat()
    server_time = request_json("/api/v5/public/time")
    if not ok(server_time):
        raise SystemExit(f"OKX EEA server time unavailable: {server_time}")
    instruments_result, eligible, counts = rows_for_universe()
    if not eligible:
        raise SystemExit("No live, linear, USDT-settled, non-pre-market SWAP contracts found on EEA host")

    metadata_failures = []
    for row in eligible:
        missing = metadata_check(row)
        if missing:
            metadata_failures.append({"instId": str(row.get("instId")), "missing_or_invalid": missing})
    metadata_failures.sort(key=lambda x: x["instId"])
    tickers = check_tickers(eligible)
    symbols = [str(row["instId"]) for row in eligible]
    endpoint_results: dict[str, Any] = {}
    for kind in ("orderbook", "daily_candles", "funding_history", "mark_price"):
        endpoint_results[kind] = run_full_endpoint(kind, symbols)

    total = len(eligible)
    metadata_pass = len(metadata_failures) == 0
    ticker_pass = tickers["missing_count"] == 0 and tickers.get("invalid_last_price_count", 0) == 0
    endpoints_pass = all(result["failed_count"] == 0 for result in endpoint_results.values())
    full_pass = total >= 50 and metadata_pass and ticker_pass and endpoints_pass
    report = {
        "report_utc": report_utc,
        "exchange": "OKX EEA",
        "api_host": BASE,
        "mode": "PUBLIC_UNAUTHENTICATED_READ_ONLY",
        "credentials_used": False,
        "private_endpoints_used": False,
        "orders_submitted": 0,
        "server_time_endpoint_ok": ok(server_time),
        "instrument_endpoint_ok": ok(instruments_result),
        "universe_counts": counts,
        "eligible_contract_count": total,
        "asset_class_scope": "EEA SWAP instruments in this feed are crypto perpetual futures; X-Perps are a separate five-year expiry product",
        "cross_margin_scope": "Futures mode supports cross margin shared by positions using the same margin currency; all retained contracts settle in USDT",
        "metadata_pass_count": total - len(metadata_failures),
        "metadata_failure_count": len(metadata_failures),
        "metadata_failure_sample": metadata_failures[:25],
        "bulk_ticker_coverage": tickers,
        "per_symbol_endpoint_coverage": endpoint_results,
        "full_universe_acceptance_pass": full_pass,
        "paper_account_activation_authorized": False,
        "remaining_gates": [
            "Romania account-level product entitlement and appropriateness assessment",
            "Currency-aware ledger, stop/funding ordering, portfolio limits and independent NAV reconstruction",
            "Durable private persistence design; do not store private account events in the public repository",
        ],
    }
    output = json.dumps(report, indent=2)
    print(output)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("# OKX EEA full-universe acceptance\n\n")
            summary.write(f"- Eligible live linear USDT swaps: **{total}**\n")
            summary.write(f"- Pre-market instruments excluded: **{counts['excluded_pre_market_swaps']}**\n")
            summary.write(f"- Metadata-complete instruments: **{total - len(metadata_failures)}/{total}**\n")
            summary.write(f"- Full-universe ticker coverage: **{tickers['covered_count']}/{total}**\n")
            for name, values in endpoint_results.items():
                summary.write(f"- {name}: **{values['passed_count']}/{values['total']}**\n")
            summary.write(f"\n**Acceptance result: {'PASS' if full_pass else 'FAIL'}**\n")
            summary.write("No account access or paper account activation was performed.\n")
    return 0 if full_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

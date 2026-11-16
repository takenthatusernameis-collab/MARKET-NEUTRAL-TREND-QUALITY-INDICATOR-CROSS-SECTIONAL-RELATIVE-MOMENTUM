#!/usr/bin/env python3
"""Qualify Polymarket first, then MEXC and Bitget, using public data only.

Polymarket qualifies on a per-instrument basis: every active cross-margin
perpetual is included regardless of category. Isolated-only and retired
instruments are excluded. Close-only instruments are kept in the archive but
cannot enter a new simulated position.
"""
from __future__ import annotations

import importlib.util
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trend_quality.polymarket_api import (
    PolymarketAPIError,
    PolymarketPublicClient,
    as_decimal,
    is_cross_margin_instrument,
    is_new_position_eligible,
    validate_instrument,
)

ROOT = Path(__file__).resolve().parents[1]


def _valid_price(value: Any) -> bool:
    try:
        return as_decimal(value, "price", positive=True) > 0
    except PolymarketAPIError:
        return False


def _sample_symbols(
    instruments: list[dict[str, Any]],
    tickers: dict[int, dict[str, Any]],
    statistics: dict[int, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for instrument in instruments:
        category = str(instrument.get("category") or "unknown")
        grouped.setdefault(category, []).append(instrument)
    selected: dict[str, dict[str, Any]] = {}
    for category, rows in sorted(grouped.items()):
        def volume(row: dict[str, Any]) -> float:
            iid = int(row["instrument_id"])
            statistic = statistics.get(iid, {})
            try:
                return float(statistic.get("volume", statistic.get("vol", 0)) or 0)
            except (TypeError, ValueError):
                return 0.0

        chosen = max(rows, key=lambda row: (volume(row), -int(row["instrument_id"])))
        selected[category] = chosen
    return selected


def _book_ok(book: dict[str, Any]) -> bool:
    bids, asks = book.get("bids"), book.get("asks")
    if not isinstance(bids, list) or not bids or not isinstance(asks, list) or not asks:
        return False
    for level in (bids[0], asks[0]):
        if not isinstance(level, dict):
            return False
        if not _valid_price(level.get("price")) or not _valid_price(level.get("quantity")):
            return False
    try:
        return as_decimal(bids[0]["price"], "bid") < as_decimal(asks[0]["price"], "ask")
    except PolymarketAPIError:
        return False


def probe_polymarket() -> dict[str, Any]:
    client = PolymarketPublicClient()
    instruments = client.instruments()
    all_cross = [row for row in instruments if is_cross_margin_instrument(row)]
    new_entry = [row for row in all_cross if is_new_position_eligible(row)]
    close_only = [row for row in all_cross if row.get("close_only") is True]
    invalid_metadata = {
        str(row.get("instrument_id")): validate_instrument(row)
        for row in all_cross
        if validate_instrument(row)
    }

    ticker_rows, statistic_rows = client.tickers()
    ticker_map = {
        int(row["instrument_id"]): row
        for row in ticker_rows
        if isinstance(row.get("instrument_id"), int)
        and not isinstance(row.get("instrument_id"), bool)
    }
    stats_map = {
        int(row.get("instrument_id", row.get("iid"))): row
        for row in statistic_rows
        if isinstance(row.get("instrument_id", row.get("iid")), int)
        and not isinstance(row.get("instrument_id", row.get("iid")), bool)
    }
    missing_tickers = [
        int(row["instrument_id"]) for row in new_entry
        if int(row["instrument_id"]) not in ticker_map
    ]
    invalid_tickers = [
        int(row["instrument_id"]) for row in new_entry
        if int(row["instrument_id"]) in ticker_map
        and (
            not _valid_price(ticker_map[int(row["instrument_id"])].get("last_price"))
            or not _valid_price(ticker_map[int(row["instrument_id"])].get("mark_price"))
            or not _valid_price(ticker_map[int(row["instrument_id"])].get("index_price"))
        )
    ]

    fee_payload = client.fees()
    fee_categories = {
        str(row.get("category")) for row in fee_payload["fee_schedule"]
        if isinstance(row, dict)
    }
    categories = sorted({str(row.get("category") or "unknown") for row in new_entry})
    fee_coverage_missing = sorted(set(categories) - fee_categories)

    sample_checks: list[dict[str, Any]] = []
    timestamps = [
        int(row["timestamp"])
        for row in ticker_rows
        if isinstance(row.get("timestamp"), int) and not isinstance(row.get("timestamp"), bool)
    ]
    reference_now_ms = max(timestamps) if timestamps else int(time.time() * 1000)
    start_ms = reference_now_ms - 14 * 86_400_000

    selected = _sample_symbols(new_entry, ticker_map, stats_map)
    for category, instrument in selected.items():
        iid = int(instrument["instrument_id"])
        ticker = ticker_map.get(iid)
        result: dict[str, Any] = {
            "category": category,
            "instrument_id": iid,
            "symbol": instrument.get("symbol"),
            "ticker_ok": ticker is not None and _valid_price(ticker.get("last_price")),
        }
        try:
            book = client.book(iid, depth=10)
            result["book_ok"] = _book_ok(book)
        except Exception as exc:
            result["book_ok"] = False
            result["book_error"] = f"{type(exc).__name__}: {str(exc)[:250]}"
        try:
            candles = client.candles(
                iid, start_timestamp=start_ms, end_timestamp=reference_now_ms, interval="1d"
            )
            completed = [
                row for row in candles
                if isinstance(row, list)
                and len(row) >= 7
                and isinstance(row[0], int)
                and row[0] + 86_400_000 <= reference_now_ms
                and all(_valid_price(row[index]) for index in (1, 2, 3, 4))
            ]
            result["daily_candles_ok"] = bool(completed)
            result["completed_daily_candle_count_14d"] = len(completed)
        except Exception as exc:
            result["daily_candles_ok"] = False
            result["candle_error"] = f"{type(exc).__name__}: {str(exc)[:250]}"
        try:
            funding = client.funding_history(
                iid, start_timestamp=start_ms, end_timestamp=reference_now_ms
            )
            result["funding_endpoint_ok"] = True
            result["funding_observation_count_14d"] = len(funding)
        except Exception as exc:
            result["funding_endpoint_ok"] = False
            result["funding_error"] = f"{type(exc).__name__}: {str(exc)[:250]}"
        sample_checks.append(result)

    checks = {
        "instrument_discovery": len(instruments) >= 20,
        "cross_margin_universe": len(new_entry) >= 20,
        "instrument_metadata": not invalid_metadata,
        "bulk_ticker_coverage": not missing_tickers and not invalid_tickers,
        "category_fee_coverage": not fee_coverage_missing,
        "sampled_market_data": bool(sample_checks) and all(
            row.get("ticker_ok")
            and row.get("book_ok")
            and row.get("daily_candles_ok")
            and row.get("funding_endpoint_ok")
            for row in sample_checks
        ),
    }
    return {
        "exchange": "polymarket",
        "api_base": "https://api.perpetuals.polymarket.com",
        "report_utc": datetime.now(UTC).isoformat(),
        "public_unauthenticated_only": True,
        "credentials_used": False,
        "private_endpoints_used": False,
        "orders_submitted": 0,
        "instrument_count_total": len(instruments),
        "cross_margin_instrument_count": len(all_cross),
        "new_position_eligible_count": len(new_entry),
        "close_only_cross_margin_count": len(close_only),
        "isolated_only_excluded_count": sum(
            row.get("isolated_only") is True for row in instruments
        ),
        "retired_settled_excluded_count": sum(
            row.get("settlement") is not None for row in instruments
        ),
        "eligible_category_counts": dict(sorted(Counter(
            str(row.get("category") or "unknown") for row in new_entry
        ).items())),
        "eligible_instruments_unclassified_or_future_category_count": sum(
            str(row.get("category") or "unknown") not in {
                "crypto", "equity", "commodity", "index", "pre_ipo"
            } for row in new_entry
        ),
        "bulk_ticker_count": len(ticker_rows),
        "missing_ticker_count": len(missing_tickers),
        "missing_ticker_sample": missing_tickers[:20],
        "invalid_ticker_count": len(invalid_tickers),
        "invalid_ticker_sample": invalid_tickers[:20],
        "metadata_invalid_count": len(invalid_metadata),
        "metadata_invalid_sample": dict(list(invalid_metadata.items())[:20]),
        "fee_schedule_categories": sorted(fee_categories),
        "fee_category_missing": fee_coverage_missing,
        "sample_market_data_by_category": sample_checks,
        "checks": checks,
        "technical_api_pass": all(checks.values()),
        "romanian_restriction_status": (
            "ROMANIA_NOT_LISTED_IN_CURRENT_PUBLISHED_GEOBLOCK_COUNTRY_TABLE; "
            "TERMS_REMAIN_SUBJECT_TO_APPLICABLE_LAW_AND_ACCOUNT_LEVEL_CHECKS"
        ),
        "paper_simulation_only": True,
        "paper_account_activation_authorized": False,
    }


def _load_existing_fallback_module() -> Any:
    path = ROOT / "scripts" / "probe_perp_priority.py"
    spec = importlib.util.spec_from_file_location("existing_exchange_public_probes", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load existing MEXC/Bitget public probes")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    results: list[dict[str, Any]] = []
    chosen: dict[str, Any] | None = None
    try:
        polymarket = probe_polymarket()
    except Exception as exc:
        polymarket = {
            "exchange": "polymarket",
            "technical_api_pass": False,
            "error": f"{type(exc).__name__}: {str(exc)[:600]}",
        }
    results.append(polymarket)
    if polymarket.get("technical_api_pass") is True:
        chosen = polymarket
    else:
        fallback_module = _load_existing_fallback_module()
        for name in ("mexc", "bitget"):
            function = getattr(fallback_module, f"probe_{name}")
            try:
                result = function()
                checks = result.get("checks", {})
                if name == "mexc":
                    required = (
                        "instruments", "cross_margin", "perpetual_only",
                        "contract_precision", "sampled_market_data",
                    )
                else:
                    required = (
                        "instruments", "cross_margin",
                        "contract_precision", "sampled_market_data",
                    )
                technical_pass = all(checks.get(key) is True for key in required)
                result["technical_api_pass"] = technical_pass
                result["asset_class_policy"] = (
                    "Include all active cross-margin contracts offered by this product; "
                    "classification labels are metadata, not an exchange-wide prerequisite."
                )
            except Exception as exc:
                result = {
                    "exchange": name,
                    "technical_api_pass": False,
                    "error": f"{type(exc).__name__}: {str(exc)[:600]}",
                }
            results.append(result)
            if result.get("technical_api_pass") is True:
                chosen = result
                break

    report = {
        "report_utc": datetime.now(UTC).isoformat(),
        "priority_order": ["polymarket", "mexc", "bitget"],
        "results": results,
        "selected_exchange": None if chosen is None else chosen.get("exchange"),
        "selection_status": (
            "NO_PUBLIC_API_PASSED"
            if chosen is None
            else "TECHNICAL_PUBLIC_DATA_PASS; PAPER_IMPLEMENTATION_ONLY"
        ),
        "safety": {
            "credentials_used": False,
            "private_endpoints_used": False,
            "orders_submitted": 0,
            "wallet_used": False,
            "vpn_or_proxy_used": False,
        },
    }
    print(json.dumps(report, indent=2, default=str))
    output = ROOT / "exchange-priority-report.json"
    output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return 0 if chosen is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())

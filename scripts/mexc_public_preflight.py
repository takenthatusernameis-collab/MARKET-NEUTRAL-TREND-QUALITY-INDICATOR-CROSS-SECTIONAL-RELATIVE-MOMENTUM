#!/usr/bin/env python3
"""MEXC public API integration preflight; no credentials or account endpoints."""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trend_quality.mexc_api import MEXCPublicClient


def main() -> int:
    client = MEXCPublicClient()
    report: dict[str, Any] = {
        "report_utc": datetime.now(UTC).isoformat(),
        "exchange": "mexc",
        "api_base": "https://contract.mexc.com",
        "public_unauthenticated_only": True,
        "credentials_used": False,
        "private_endpoints_used": False,
        "orders_submitted": 0,
        "wallet_used": False,
        "checks": {},
        "sample_results": [],
    }

    try:
        server_ms = client.server_time_ms()
        raw_instruments = client.contract_details()
        instruments = client.instruments()
        ticker_rows = client.tickers()
        report.update({
            "server_time_ms": server_ms,
            "instrument_count_all": len(raw_instruments),
            "active_cross_usdt_perpetual_count": len(instruments),
            "asset_class_counts": dict(sorted(Counter(
                row["category"] for row in instruments
            ).items())),
            "ticker_count": len(ticker_rows),
            "unmatched_ticker_symbols": sorted(
                {row["symbol"] for row in instruments}
                - {row["symbol"] for row in ticker_rows}
            )[:20],
        })
        ticker_by_symbol = {row["symbol"]: row for row in ticker_rows}
        report["checks"]["server_time"] = server_ms > 0
        report["checks"]["instrument_discovery"] = len(instruments) >= 50
        report["checks"]["bulk_ticker_coverage"] = (
            bool(ticker_by_symbol)
            and not (
                {row["symbol"] for row in instruments}
                - set(ticker_by_symbol)
            )
        )

        # Probe the most liquid member of each reported classification, plus
        # unknown categories. Class labels are observational, not a filter.
        samples: dict[str, dict[str, Any]] = {}
        for instrument in instruments:
            category = str(instrument["category"])
            ticker = ticker_by_symbol.get(instrument["symbol"])
            if ticker is None:
                continue
            prior = samples.get(category)
            if prior is None or (
                float(ticker["turnover_24h_usdt"])
                > float(prior["ticker"]["turnover_24h_usdt"])
            ):
                samples[category] = {"instrument": instrument, "ticker": ticker}

        now_ms = server_ms
        sample_results: list[dict[str, Any]] = []
        for category, selected in sorted(samples.items()):
            instrument = selected["instrument"]
            symbol = str(instrument["symbol"])
            checks: dict[str, bool] = {
                "ticker": str(selected["ticker"]["symbol"]) == symbol,
            }
            row: dict[str, Any] = {
                "category": category,
                "instrument_id": instrument["instrument_id"],
                "symbol": symbol,
            }
            try:
                book = client.orderbook(symbol, depth=10)
                checks["orderbook"] = bool(book["bids"] and book["asks"])
                row["book_timestamp_ms"] = book["timestamp_ms"]
                row["book_bid_levels"] = len(book["bids"])
                row["book_ask_levels"] = len(book["asks"])
            except Exception as exc:
                checks["orderbook"] = False
                row["orderbook_error"] = f"{type(exc).__name__}: {str(exc)[:250]}"

            try:
                candles = client.candles(
                    symbol,
                    start_timestamp_ms=now_ms - 14 * 86_400_000,
                    end_timestamp_ms=now_ms,
                    interval="Day1",
                )
                completed = [
                    candle for candle in candles
                    if int(candle["timestamp_ms"]) + 86_400_000 <= now_ms
                ]
                checks["daily_candles"] = bool(completed)
                row["completed_daily_candles_14d"] = len(completed)
            except Exception as exc:
                checks["daily_candles"] = False
                row["candle_error"] = f"{type(exc).__name__}: {str(exc)[:250]}"

            try:
                funding = client.funding_history(
                    symbol,
                    start_timestamp_ms=now_ms - 14 * 86_400_000,
                    end_timestamp_ms=now_ms + 1,
                    page_size=100,
                )
                checks["funding_history"] = bool(funding)
                row["funding_observations_14d"] = len(funding)
                row["funding_negative_rate_sample"] = next(
                    (item["funding_rate"] for item in funding
                     if float(item["funding_rate"]) < 0),
                    None,
                )
            except Exception as exc:
                checks["funding_history"] = False
                row["funding_error"] = f"{type(exc).__name__}: {str(exc)[:250]}"

            row["checks"] = checks
            sample_results.append(row)

        report["sample_results"] = sample_results
        report["sampled_categories"] = sorted(samples)
        report["checks"]["category_market_data"] = (
            bool(sample_results)
            and all(all(item["checks"].values()) for item in sample_results)
        )
        report["technical_public_data_pass"] = all(report["checks"].values())
        report["status"] = (
            "TECHNICAL_PUBLIC_DATA_PASS"
            if report["technical_public_data_pass"]
            else "NOT_READY"
        )
    except Exception as exc:
        report["technical_public_data_pass"] = False
        report["status"] = "PROBE_ERROR"
        report["error"] = f"{type(exc).__name__}: {str(exc)[:800]}"

    output = json.dumps(report, indent=2, sort_keys=True)
    print(output)
    Path("mexc-public-preflight-report.json").write_text(
        output + "\n", encoding="utf-8"
    )
    return 0 if report.get("technical_public_data_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())

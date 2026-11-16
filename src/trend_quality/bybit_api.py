"""Unauthenticated Bybit V5 public market-data client.

This module deliberately contains no private endpoint or order-submission method.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class BybitAPIError(RuntimeError):
    """Raised when Bybit returns an invalid or unsuccessful public response."""


Transport = Callable[[str, Mapping[str, str | int]], dict[str, Any]]


@dataclass(frozen=True)
class Kline:
    start_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal


def _decimal(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BybitAPIError(f"Invalid decimal field {field}: {value!r}") from exc
    if not result.is_finite():
        raise BybitAPIError(f"Non-finite decimal field {field}")
    return result


class BybitPublicClient:
    """Small public-only client with bounded retries and injectable test transport."""

    def __init__(
        self,
        base_url: str = "https://api.bybit.com",
        timeout_seconds: float = 12.0,
        max_retries: int = 3,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("Only HTTPS is permitted")
        if timeout_seconds <= 0 or max_retries < 0:
            raise ValueError("Invalid timeout or retry count")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.transport = transport
        self._sleep = sleep

    def _http_transport(self, path: str, params: Mapping[str, str | int]) -> dict[str, Any]:
        query = urlencode({key: str(value) for key, value in params.items()})
        request = Request(
            f"{self.base_url}{path}?{query}",
            headers={
                "User-Agent": "trend-quality-paper-research/0.1",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise BybitAPIError("Expected a JSON object from Bybit")
        return payload

    def _request(self, path: str, params: Mapping[str, str | int]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                transport = self.transport or self._http_transport
                payload = transport(path, params)
                if not isinstance(payload, dict):
                    raise BybitAPIError("API transport returned a non-object payload")
                code = payload.get("retCode")
                if code is None:
                    raise BybitAPIError("Bybit response is missing retCode")
                if str(code) != "0":
                    message = str(payload.get("retMsg", "unknown API error"))
                    api_error = BybitAPIError(f"Bybit retCode={code}: {message}")
                    retryable_codes = {"10000", "10006", "10016", "10018"}
                    if str(code) not in retryable_codes or attempt >= self.max_retries:
                        raise api_error
                    last_error = api_error
                else:
                    result = payload.get("result")
                    if not isinstance(result, dict):
                        raise BybitAPIError("Bybit response result is not an object")
                    return payload
            except BybitAPIError:
                raise
            except HTTPError as exc:
                last_error = exc
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if not retryable or attempt >= self.max_retries:
                    body = exc.read(2048).decode("utf-8", errors="replace")
                    server = exc.headers.get("Server", "unknown")
                    cf_ray = exc.headers.get("CF-RAY", "not-present")
                    detail = (
                        f"HTTP {exc.code} for {path}; server={server}; "
                        f"cf_ray={cf_ray}; body={body[:500]!r}"
                    )
                    raise BybitAPIError(detail) from exc
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise BybitAPIError(f"Request failed for {path}: {exc}") from exc
            delay = min(8.0, 0.5 * (2**attempt))
            self._sleep(delay)
        raise BybitAPIError(f"Request failed for {path}: {last_error}")

    def server_time_ms(self) -> int:
        payload = self._request("/v5/market/time", {})
        result = payload["result"]
        time_nano = result.get("timeNano")
        time_second = result.get("timeSecond")
        if time_nano is not None:
            value = int(time_nano) // 1_000_000
        elif time_second is not None:
            value = int(time_second) * 1000
        elif payload.get("time") is not None:
            value = int(payload["time"])
        else:
            raise BybitAPIError("Server-time response has no recognized time field")
        if value <= 0:
            raise BybitAPIError("Invalid Bybit server timestamp")
        return value

    def eligible_linear_usdt_perpetuals(self, max_pages: int = 100) -> list[dict[str, Any]]:
        """Fetch all instrument pages and locally filter actual response fields."""
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        cursor: str | None = None
        seen_cursors: set[str] = set()
        instruments: dict[str, dict[str, Any]] = {}
        for _ in range(max_pages):
            params: dict[str, str | int] = {
                "category": "linear",
                "status": "Trading",
                "limit": 1000,
            }
            if cursor:
                params["cursor"] = cursor
            payload = self._request("/v5/market/instruments-info", params)
            result = payload["result"]
            items = result.get("list")
            if not isinstance(items, list):
                raise BybitAPIError("Instrument response list is missing or invalid")
            for item in items:
                if not isinstance(item, dict):
                    raise BybitAPIError("Instrument list contains a non-object")
                if (
                    item.get("status") == "Trading"
                    and item.get("contractType") == "LinearPerpetual"
                    and item.get("quoteCoin") == "USDT"
                    and item.get("settleCoin") == "USDT"
                ):
                    symbol = item.get("symbol")
                    if not isinstance(symbol, str) or not symbol:
                        raise BybitAPIError("Eligible instrument is missing symbol")
                    instruments[symbol] = item
            next_cursor = result.get("nextPageCursor") or ""
            if not next_cursor:
                return [instruments[key] for key in sorted(instruments)]
            if next_cursor in seen_cursors:
                raise BybitAPIError("Instrument pagination cursor repeated")
            seen_cursors.add(next_cursor)
            cursor = str(next_cursor)
        raise BybitAPIError(f"Instrument pagination exceeded max_pages={max_pages}")

    @staticmethod
    def _parse_kline(row: object) -> Kline:
        if not isinstance(row, list) or len(row) < 7:
            raise BybitAPIError("Kline row must contain at least seven fields")
        try:
            start_ms = int(row[0])
        except (TypeError, ValueError) as exc:
            raise BybitAPIError("Invalid Kline start timestamp") from exc
        values = [_decimal(row[i], f"kline[{i}]") for i in range(1, 7)]
        candle = Kline(start_ms, *values)
        if candle.start_ms < 0:
            raise BybitAPIError("Negative candle timestamp")
        if (
            candle.open <= 0
            or candle.high <= 0
            or candle.low <= 0
            or candle.close <= 0
            or candle.volume < 0
            or candle.turnover < 0
            or candle.high < max(candle.open, candle.close, candle.low)
            or candle.low > min(candle.open, candle.close, candle.high)
        ):
            raise BybitAPIError(f"Invalid OHLCV candle at {candle.start_ms}")
        return candle

    def klines_backward(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        *,
        limit: int = 1000,
        max_pages: int = 10000,
    ) -> list[Kline]:
        """Retrieve a complete timestamp window backward; Kline has no cursor."""
        if not symbol or start_ms < 0 or end_ms < start_ms:
            raise ValueError("Invalid symbol or timestamp window")
        if not 1 <= limit <= 1000 or max_pages < 1:
            raise ValueError("Invalid limit or max_pages")
        cursor_end = end_ms
        candles: dict[int, Kline] = {}
        page_count = 0
        while cursor_end >= start_ms:
            page_count += 1
            if page_count > max_pages:
                raise BybitAPIError("Kline pagination exceeded max_pages")
            payload = self._request(
                "/v5/market/kline",
                {
                    "category": "linear",
                    "symbol": symbol,
                    "interval": interval,
                    "start": start_ms,
                    "end": cursor_end,
                    "limit": limit,
                },
            )
            rows = payload["result"].get("list")
            if not isinstance(rows, list):
                raise BybitAPIError("Kline response list is missing or invalid")
            if not rows:
                break
            page = [self._parse_kline(row) for row in rows]
            for candle in page:
                if start_ms <= candle.start_ms <= end_ms:
                    candles[candle.start_ms] = candle
            oldest = min(c.start_ms for c in page)
            if oldest <= start_ms or len(page) < limit:
                break
            next_end = oldest - 1
            if next_end >= cursor_end:
                raise BybitAPIError("Kline pagination made no backward progress")
            cursor_end = next_end
        return [candles[key] for key in sorted(candles)]

    def funding_history_complete(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
        *,
        max_depth: int = 32,
    ) -> list[dict[str, Any]]:
        """Fetch funding history using bounded windows, subdividing full pages.

        The endpoint has no cursor and caps each page at 200 records. A full page
        is subdivided to avoid silently losing older settlements.
        """
        if not symbol or start_ms < 0 or end_ms < start_ms:
            raise ValueError("Invalid symbol or funding time window")
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        collected: dict[int, dict[str, Any]] = {}

        def fetch_window(left: int, right: int, depth: int) -> None:
            payload = self._request(
                "/v5/market/funding/history",
                {
                    "category": "linear",
                    "symbol": symbol,
                    "startTime": left,
                    "endTime": right,
                    "limit": 200,
                },
            )
            rows = payload["result"].get("list")
            if not isinstance(rows, list):
                raise BybitAPIError("Funding response list is missing or invalid")
            if len(rows) >= 200:
                if depth >= max_depth or left >= right:
                    raise BybitAPIError("Funding window remains truncated after subdivision")
                midpoint = (left + right) // 2
                fetch_window(left, midpoint, depth + 1)
                if midpoint < right:
                    fetch_window(midpoint + 1, right, depth + 1)
                return
            for row in rows:
                if (
                    not isinstance(row, dict)
                    or row.get("symbol") != symbol
                    or "fundingRateTimestamp" not in row
                    or "fundingRate" not in row
                ):
                    raise BybitAPIError("Malformed or mismatched funding record")
                try:
                    timestamp = int(row["fundingRateTimestamp"])
                except (TypeError, ValueError, OverflowError) as exc:
                    raise BybitAPIError("Invalid funding timestamp") from exc
                _decimal(row["fundingRate"], "fundingRate")
                if timestamp < 0:
                    raise BybitAPIError("Negative funding timestamp")
                if left <= timestamp <= right:
                    previous = collected.get(timestamp)
                    if previous is not None and previous != row:
                        raise BybitAPIError(
                            f"Conflicting funding records at timestamp {timestamp}"
                        )
                    collected[timestamp] = row

        fetch_window(start_ms, end_ms, 0)
        return [collected[key] for key in sorted(collected)]

    def orderbook(self, symbol: str, limit: int = 200) -> dict[str, Any]:
        """Return a public linear order-book snapshot; REST accepts up to 1,000."""
        if not symbol or not 1 <= limit <= 1000:
            raise ValueError("Invalid symbol or order-book depth")
        payload = self._request(
            "/v5/market/orderbook",
            {"category": "linear", "symbol": symbol, "limit": limit},
        )
        result = payload["result"]
        if (
            result.get("s") != symbol
            or not isinstance(result.get("b"), list)
            or not isinstance(result.get("a"), list)
        ):
            raise BybitAPIError("Malformed order-book response")
        return result

"""Public, unauthenticated Polymarket Perps market-data adapter.

Only read-only information endpoints are implemented here. No wallet, signature,
secret, private account endpoint or order method exists in this module.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://api.perpetuals.polymarket.com"
DAY_MS = 86_400_000
USER_AGENT = "market-neutral-trend-quality-research/1.0"


class PolymarketAPIError(RuntimeError):
    """A public API request or response validation failed."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


Transport = Callable[[str, Mapping[str, Any]], tuple[int, Mapping[str, str], Any]]


def as_decimal(value: object, field: str, *, positive: bool = False) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PolymarketAPIError(f"Invalid decimal field {field}: {value!r}") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise PolymarketAPIError(f"Invalid decimal field {field}: {value!r}")
    return parsed


def is_cross_margin_instrument(instrument: Mapping[str, Any]) -> bool:
    """Include every non-retired instrument that offers cross margin."""
    return (
        instrument.get("isolated_only") is False
        and instrument.get("settlement") is None
    )


def is_new_position_eligible(instrument: Mapping[str, Any]) -> bool:
    """Close-only markets remain monitorable but cannot enter new rankings."""
    return is_cross_margin_instrument(instrument) and instrument.get("close_only") is not True


def validate_instrument(instrument: Mapping[str, Any]) -> list[str]:
    required_strings = (
        "category", "symbol", "base_asset", "quote_asset", "funding_interval"
    )
    required_integers = (
        "instrument_id", "quantity_decimals", "price_decimals", "max_order_count",
        "max_leverage",
    )
    errors: list[str] = []
    for key in required_strings:
        if not isinstance(instrument.get(key), str) or not instrument[key].strip():
            errors.append(f"MISSING_{key.upper()}")
    for key in required_integers:
        value = instrument.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append(f"INVALID_{key.upper()}")
    for key in (
        "price_bounds", "liquidation_fee", "min_notional",
        "max_market_notional", "max_limit_notional",
    ):
        try:
            value = as_decimal(instrument.get(key), key)
            if key in {"price_bounds", "max_market_notional", "max_limit_notional"} and value <= 0:
                errors.append(f"NONPOSITIVE_{key.upper()}")
            if key == "min_notional" and value < 0:
                errors.append("NEGATIVE_MIN_NOTIONAL")
            if key == "liquidation_fee" and value < 0:
                errors.append("NEGATIVE_LIQUIDATION_FEE")
        except PolymarketAPIError:
            errors.append(f"INVALID_{key.upper()}")
    if instrument.get("isolated_only") not in (True, False):
        errors.append("INVALID_ISOLATED_ONLY")
    tiers = instrument.get("risk_tiers")
    if not isinstance(tiers, list) or not tiers:
        errors.append("MISSING_RISK_TIERS")
    else:
        for tier in tiers:
            if not isinstance(tier, dict):
                errors.append("INVALID_RISK_TIER")
                break
            try:
                lower_bound = as_decimal(tier.get("lower_bound"), "risk_tier.lower_bound")
            except PolymarketAPIError:
                errors.append("INVALID_RISK_TIER")
                break
            leverage = tier.get("max_leverage")
            if (
                isinstance(leverage, bool)
                or not isinstance(leverage, int)
                or leverage < 1
                or lower_bound < 0
            ):
                errors.append("INVALID_RISK_TIER")
                break
    return errors


@dataclass(frozen=True)
class PublicResponse:
    status_code: int
    headers: Mapping[str, str]
    payload: Any


class PolymarketPublicClient:
    """Rate-limited, retrying client for Polymarket's public Perps API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout_seconds: float = 12.0,
        minimum_interval_seconds: float = 0.05,
        retries: int = 3,
        transport: Transport | None = None,
    ) -> None:
        if base_url.rstrip("/") != DEFAULT_BASE_URL:
            raise ValueError("Only the official Polymarket Perps API host is allowed")
        if timeout_seconds <= 0 or minimum_interval_seconds < 0 or retries < 0:
            raise ValueError("Invalid timeout, interval or retry setting")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.minimum_interval_seconds = minimum_interval_seconds
        self.retries = retries
        self.transport = transport
        self._rate_lock = Lock()
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        with self._rate_lock:
            elapsed = time.monotonic() - self._last_request_at
            wait = self.minimum_interval_seconds - elapsed
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()

    def _request_once(self, path: str, params: Mapping[str, Any]) -> PublicResponse:
        self._throttle()
        if not path.startswith("/v1/info/"):
            raise PolymarketAPIError("Only public /v1/info endpoints are permitted")
        if self.transport is not None:
            status, headers, payload = self.transport(path, params)
            return PublicResponse(status, headers, payload)

        query = urlencode({k: v for k, v in params.items() if v is not None})
        url = self.base_url + path + ("?" + query if query else "")
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(8_000_000)
                status = response.status
                headers = dict(response.headers.items())
        except HTTPError as exc:
            raw = exc.read(2_000_000)
            headers = dict(exc.headers.items()) if exc.headers else {}
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = {"error": raw.decode("utf-8", errors="replace")[:1000]}
            return PublicResponse(exc.code, headers, payload)
        except (URLError, TimeoutError, OSError) as exc:
            raise PolymarketAPIError(f"Public API transport failed: {exc}") from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PolymarketAPIError("Public API returned invalid JSON", status) from exc
        return PublicResponse(status, headers, payload)

    def get(self, path: str, **params: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self._request_once(path, params)
                if response.status_code == 200:
                    return response.payload
                message = f"HTTP {response.status_code}: {response.payload!r}"
                error = PolymarketAPIError(message, response.status_code)
                if response.status_code != 429 and response.status_code < 500:
                    raise error
                last_error = error
                retry_after = (
                    response.headers.get("Retry-After")
                    or response.headers.get("retry-after")
                )
                if attempt < self.retries:
                    try:
                        delay = (
                            min(5.0, max(0.1, float(retry_after)))
                            if retry_after
                            else 0.5 * (2 ** attempt)
                        )
                    except ValueError:
                        delay = 0.5 * (2 ** attempt)
                    time.sleep(delay)
            except PolymarketAPIError as exc:
                if exc.status_code is not None:
                    raise
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.25 * (2 ** attempt))
        raise PolymarketAPIError(
            f"Public API request exhausted retries: {last_error}"
        ) from last_error

    def instruments(self) -> list[dict[str, Any]]:
        payload = self.get("/v1/info/instruments")
        if not isinstance(payload, list):
            raise PolymarketAPIError("Instruments endpoint did not return a list")
        rows = [item for item in payload if isinstance(item, dict)]
        if len(rows) != len(payload):
            raise PolymarketAPIError("Instruments endpoint contained malformed rows")
        ids = [row.get("instrument_id") for row in rows]
        if any(isinstance(value, bool) or not isinstance(value, int) for value in ids):
            raise PolymarketAPIError("Instruments endpoint returned an invalid instrument_id")
        if len(ids) != len(set(ids)):
            raise PolymarketAPIError("Instruments endpoint returned duplicate instrument IDs")
        return rows

    def tickers(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        tickers = self.get("/v1/info/tickers")
        statistics = self.get("/v1/info/statistics")
        if not isinstance(tickers, list) or not isinstance(statistics, list):
            raise PolymarketAPIError("Bulk ticker/statistics endpoint did not return lists")
        ticker_rows = [row for row in tickers if isinstance(row, dict)]
        statistic_rows = [row for row in statistics if isinstance(row, dict)]
        if len(ticker_rows) != len(tickers) or len(statistic_rows) != len(statistics):
            raise PolymarketAPIError("Ticker/statistics response contained malformed rows")
        return ticker_rows, statistic_rows

    def fees(self) -> dict[str, Any]:
        payload = self.get("/v1/info/fees")
        if not isinstance(payload, dict) or not isinstance(payload.get("fee_schedule"), list):
            raise PolymarketAPIError("Fee schedule response did not match its documented schema")
        return payload

    def book(self, instrument_id: int, depth: int = 100) -> dict[str, Any]:
        if depth not in (10, 100, 500, 1000):
            raise ValueError("depth must be 10, 100, 500 or 1000")
        payload = self.get("/v1/info/book", instrument_id=instrument_id, depth=depth)
        if not isinstance(payload, dict):
            raise PolymarketAPIError("Order-book response was not an object")
        return payload

    def candles(
        self,
        instrument_id: int,
        *,
        start_timestamp: int,
        end_timestamp: int,
        interval: str = "1d",
    ) -> list[list[Any]]:
        if interval not in ("1s", "1m", "5m", "15m", "1h", "4h", "1d", "1w"):
            raise ValueError("Unsupported candle interval")
        if start_timestamp <= 0 or end_timestamp <= start_timestamp:
            raise ValueError("Invalid candle time window")
        cursor = start_timestamp
        output: list[list[Any]] = []
        seen: set[int] = set()
        for _ in range(100):
            payload = self.get(
                "/v1/info/klines",
                instrument_id=instrument_id,
                interval=interval,
                start_timestamp=cursor,
                end_timestamp=end_timestamp,
            )
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list):
                raise PolymarketAPIError("Kline response has no data list")
            page = [row for row in data if isinstance(row, list) and len(row) >= 7]
            for row in page:
                timestamp = row[0]
                if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                    raise PolymarketAPIError("Kline row has invalid timestamp")
                if timestamp not in seen:
                    output.append(row)
                    seen.add(timestamp)
            more = payload.get("more") is True
            if not more:
                break
            if not page:
                raise PolymarketAPIError("Kline API reported more data without a progress row")
            next_cursor = max(int(row[0]) for row in page) + (
                DAY_MS if interval == "1d" else self._interval_ms(interval)
            )
            if next_cursor <= cursor:
                raise PolymarketAPIError("Kline pagination did not advance")
            cursor = next_cursor
        else:
            raise PolymarketAPIError("Kline pagination exceeded 100 pages")
        return sorted(output, key=lambda row: int(row[0]))

    def funding_history(
        self,
        instrument_id: int,
        *,
        start_timestamp: int,
        end_timestamp: int,
    ) -> list[dict[str, Any]]:
        payload = self.get(
            "/v1/info/funding",
            instrument_id=instrument_id,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise PolymarketAPIError("Funding response has no data list")
        return [row for row in data if isinstance(row, dict)]

    @staticmethod
    def _interval_ms(interval: str) -> int:
        factors = {
            "1s": 1_000, "1m": 60_000, "5m": 300_000, "15m": 900_000,
            "1h": 3_600_000, "4h": 14_400_000, "1d": DAY_MS,
            "1w": 7 * DAY_MS,
        }
        return factors[interval]

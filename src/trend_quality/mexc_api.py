"""Read-only public MEXC USDT perpetual market-data adapter.

The client intentionally has no authentication, private-account, position, or order
methods. Contract sizes and trading increments are preserved so the paper simulator
can convert contract quantities correctly.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .exchange_probe import classify_asset_class

DEFAULT_BASE_URL = "https://contract.mexc.com"
USER_AGENT = "market-neutral-trend-quality-paper-research/1.0"
DAY_SECONDS = 86_400
MAX_KLINE_ROWS = 2_000
MAX_FUNDING_PAGE_SIZE = 1_000

Transport = Callable[[str, Mapping[str, Any]], tuple[int, Any]]


class MEXCAPIError(RuntimeError):
    """Raised for invalid public responses or failed API requests."""


def _decimal(value: object, field: str, *, allow_zero: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MEXCAPIError(f"Invalid decimal field {field}") from exc
    if not result.is_finite() or result < 0 or (result == 0 and not allow_zero):
        raise MEXCAPIError(f"Non-positive or non-finite decimal field {field}")
    return result


def _signed_decimal(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MEXCAPIError(f"Invalid decimal field {field}") from exc
    if not result.is_finite():
        raise MEXCAPIError(f"Non-finite decimal field {field}")
    return result


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise MEXCAPIError(f"Invalid integer field {field}")
    try:
        parsed = int(value)  # MEXC publishes integer identifiers and precision fields.
    except (TypeError, ValueError) as exc:
        raise MEXCAPIError(f"Invalid integer field {field}") from exc
    if parsed < minimum:
        raise MEXCAPIError(f"Out-of-range integer field {field}")
    return parsed


def _payload_rows(payload: Any, field: str = "data") -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise MEXCAPIError("MEXC response is not a JSON object")
    value = payload.get(field)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []


def classify_mexc_instrument(row: Mapping[str, Any]) -> str:
    """Classify where provider labels permit; unknown labels remain valid metadata."""
    category = classify_asset_class(
        row.get("underlyingType"),
        row.get("underlyingSubType"),
        row.get("category"),
        row.get("conceptPlate"),
        row.get("assetClass"),
        row.get("displayNameEn"),
        row.get("baseCoinName"),
    )
    return category if category != "unclassified" else "unclassified"


def is_active_cross_usdt_perpetual(row: Mapping[str, Any]) -> bool:
    """MEXC positionOpenType 2/3 supports cross; state 0 is enabled."""
    try:
        return (
            _integer(row.get("futureType"), "futureType") == 1
            and _integer(row.get("positionOpenType"), "positionOpenType") in {2, 3}
            and _integer(row.get("state"), "state") == 0
            and row.get("apiAllowed") is not False
            and str(row.get("quoteCoin", "")).upper() == "USDT"
            and str(row.get("settleCoin", "")).upper() == "USDT"
            and bool(str(row.get("symbol", "")).strip())
        )
    except MEXCAPIError:
        return False


def normalize_instrument(row: Mapping[str, Any]) -> dict[str, Any]:
    """Convert an active MEXC detail record to the exchange-neutral data contract."""
    instrument_id = _integer(row.get("id", row.get("contractId")), "id", minimum=1)
    symbol = str(row.get("symbol", "")).strip()
    if not symbol:
        raise MEXCAPIError("Instrument symbol is missing")
    contract_size = _decimal(row.get("contractSize"), "contractSize")
    price_tick = _decimal(row.get("priceUnit"), "priceUnit")
    quantity_step = _decimal(row.get("volUnit"), "volUnit")
    min_contracts = _decimal(row.get("minVol"), "minVol", allow_zero=True)
    max_contracts = _decimal(row.get("maxVol"), "maxVol")
    if quantity_step <= 0 or max_contracts < min_contracts:
        raise MEXCAPIError(f"Invalid contract size rules for {symbol}")
    taker_fee = _decimal(row.get("takerFeeRate"), "takerFeeRate", allow_zero=True)
    maker_fee = _decimal(row.get("makerFeeRate"), "makerFeeRate", allow_zero=True)
    create_time = row.get("createTime")
    create_time_ms = None if create_time in (None, "", 0, "0") else _integer(
        create_time, "createTime", minimum=1
    )
    category = classify_mexc_instrument(row)
    return {
        "instrument_id": instrument_id,
        "symbol": symbol,
        "category": category,
        "raw_category_labels": row.get("conceptPlate", []),
        "base_asset": str(row.get("baseCoin", "")),
        "quote_asset": str(row.get("quoteCoin", "")),
        "settlement_asset": str(row.get("settleCoin", "")),
        "contract_size": str(contract_size),
        "price_tick": str(price_tick),
        "quantity_step_contracts": str(quantity_step),
        "min_contracts": str(min_contracts),
        "max_contracts": str(max_contracts),
        "min_quantity_base": str(min_contracts * contract_size),
        "max_quantity_base": str(max_contracts * contract_size),
        "taker_fee_rate": str(taker_fee),
        "maker_fee_rate": str(maker_fee),
        "max_leverage": _integer(row.get("maxLeverage"), "maxLeverage", minimum=1),
        "position_open_type": _integer(row.get("positionOpenType"), "positionOpenType"),
        "state": _integer(row.get("state"), "state"),
        "api_allowed": row.get("apiAllowed") is not False,
        "create_time_ms": create_time_ms,
        "close_only": False,
        "settlement": None,
        "raw_display_name": row.get("displayNameEn"),
    }


class MEXCPublicClient:
    """Rate-limited, retrying MEXC contract-v1 public client."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout_seconds: float = 12.0,
        minimum_interval_seconds: float = 0.11,
        retries: int = 3,
        transport: Transport | None = None,
    ) -> None:
        if base_url.rstrip("/") != DEFAULT_BASE_URL:
            raise ValueError("Only the official MEXC contract API host is allowed")
        if timeout_seconds <= 0 or minimum_interval_seconds < 0 or retries < 0:
            raise ValueError("Invalid timeout, rate interval or retry setting")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.minimum_interval_seconds = minimum_interval_seconds
        self.retries = retries
        self.transport = transport
        self._rate_lock = threading.Lock()
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        with self._rate_lock:
            elapsed = time.monotonic() - self._last_request_at
            delay = self.minimum_interval_seconds - elapsed
            if delay > 0:
                time.sleep(delay)
            self._last_request_at = time.monotonic()

    def _request(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not path.startswith("/api/v1/contract/") or path.startswith("//"):
            raise MEXCAPIError("Only public MEXC /api/v1/contract endpoints are permitted")
        query = {key: value for key, value in (params or {}).items() if value is not None}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self._throttle()
            try:
                if self.transport is not None:
                    status, payload = self.transport(path, query)
                else:
                    url = self.base_url + path
                    if query:
                        url += "?" + urlencode(query)
                    request = Request(
                        url,
                        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                        method="GET",
                    )
                    with urlopen(request, timeout=self.timeout_seconds) as response:
                        status = int(response.status)
                        payload = json.loads(response.read(8_000_000).decode("utf-8"))
                if status == 429 or status >= 500:
                    raise MEXCAPIError(f"Retryable MEXC HTTP status {status}")
                if status != 200:
                    raise MEXCAPIError(f"MEXC returned HTTP {status}")
                if not isinstance(payload, dict):
                    raise MEXCAPIError("MEXC response is not a JSON object")
                if payload.get("success") is not True or str(payload.get("code", "0")) != "0":
                    raise MEXCAPIError(
                        f"MEXC API rejected request: code={payload.get('code')!r} "
                        f"message={str(payload.get('message', ''))[:200]}"
                    )
                return payload
            except urllib.error.HTTPError as exc:
                if exc.code != 429 and exc.code < 500:
                    raise MEXCAPIError(f"MEXC returned HTTP {exc.code}") from exc
                last_error = exc
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
            except MEXCAPIError as exc:
                if "Retryable MEXC HTTP status" not in str(exc):
                    raise
                last_error = exc
            if attempt < self.retries:
                time.sleep(min(0.25 * (2**attempt), 2.0))
        raise MEXCAPIError(f"MEXC request failed after retries: {last_error}") from last_error

    def server_time_ms(self) -> int:
        payload = self._request("/api/v1/contract/ping")
        return _integer(payload.get("data"), "server time", minimum=1)

    def contract_details(self) -> list[dict[str, Any]]:
        payload = self._request("/api/v1/contract/detail")
        rows = _payload_rows(payload)
        if not rows:
            raise MEXCAPIError("MEXC contract detail returned no instruments")
        return rows

    def instruments(self) -> list[dict[str, Any]]:
        """Return every active cross-margin USDT-settled linear perpetual."""
        output: list[dict[str, Any]] = []
        for row in self.contract_details():
            if not is_active_cross_usdt_perpetual(row):
                continue
            output.append(normalize_instrument(row))
        if not output:
            raise MEXCAPIError("No active cross-margin USDT perpetuals were discovered")
        return sorted(output, key=lambda row: int(row["instrument_id"]))

    def tickers(self) -> list[dict[str, Any]]:
        """Fetch the bulk ticker endpoint once; do not issue 1,000 symbol requests."""
        payload = self._request("/api/v1/contract/ticker")
        rows = _payload_rows(payload)
        if not rows:
            raise MEXCAPIError("MEXC bulk ticker returned no ticker rows")
        output: list[dict[str, Any]] = []
        for row in rows:
            symbol = str(row.get("symbol", "")).strip()
            if not symbol:
                continue
            bid = _decimal(row.get("bid1"), f"{symbol}.bid1", allow_zero=True)
            ask = _decimal(row.get("ask1"), f"{symbol}.ask1", allow_zero=True)
            last = _decimal(row.get("lastPrice"), f"{symbol}.lastPrice")
            fair = _decimal(row.get("fairPrice"), f"{symbol}.fairPrice")
            index = _decimal(row.get("indexPrice"), f"{symbol}.indexPrice")
            mid = (bid + ask) / Decimal("2") if bid > 0 and ask > bid else fair
            output.append({
                "symbol": symbol,
                "last_price": str(last),
                "mark_price": str(fair),
                "index_price": str(index),
                "bid_price": str(bid),
                "ask_price": str(ask),
                "mid_price": str(mid),
                "funding_rate": str(_signed_decimal(
                    row.get("fundingRate", 0), f"{symbol}.fundingRate"
                )),
                "volume_24h_contracts": str(_decimal(
                    row.get("volume24", 0), f"{symbol}.volume24", allow_zero=True
                )),
                "turnover_24h_usdt": str(_decimal(
                    row.get("amount24", 0), f"{symbol}.amount24", allow_zero=True
                )),
                "open_interest_contracts": str(_decimal(
                    row.get("holdVol", 0), f"{symbol}.holdVol", allow_zero=True
                )),
                "change_24h": str(_signed_decimal(
                    row.get("riseFallRate", 0), f"{symbol}.riseFallRate"
                )),
                "timestamp_ms": _integer(row.get("timestamp"), f"{symbol}.timestamp", minimum=1),
                "next_funding_timestamp_ms": (
                    None if row.get("nextSettleTime") is None
                    else _integer(row.get("nextSettleTime"), f"{symbol}.nextSettleTime")
                ),
            })
        if not output:
            raise MEXCAPIError("MEXC bulk ticker contained no valid symbol rows")
        return output

    def orderbook(self, symbol: str, *, depth: int = 20) -> dict[str, Any]:
        if not symbol or depth < 1 or depth > 1_000:
            raise ValueError("Invalid symbol or depth")
        payload = self._request(f"/api/v1/contract/depth/{symbol}", {"limit": depth})
        rows = _payload_rows(payload)
        if not rows:
            raise MEXCAPIError(f"MEXC order book is empty for {symbol}")
        raw = rows[0]
        levels: dict[str, list[dict[str, str]]] = {}
        for side in ("bids", "asks"):
            raw_levels = raw.get(side)
            if not isinstance(raw_levels, list):
                raise MEXCAPIError(f"MEXC {side} depth is malformed for {symbol}")
            parsed = []
            for level in raw_levels:
                if not isinstance(level, list) or len(level) < 2:
                    continue
                price = _decimal(level[0], f"{symbol}.{side}.price")
                quantity = _decimal(level[1], f"{symbol}.{side}.quantity", allow_zero=True)
                if quantity > 0:
                    parsed.append({"price": str(price), "quantity_contracts": str(quantity)})
            levels[side] = parsed
        if not levels["bids"] or not levels["asks"]:
            raise MEXCAPIError(f"MEXC order book has an empty side for {symbol}")
        return {
            **levels,
            "timestamp_ms": _integer(raw.get("timestamp"), f"{symbol}.book_timestamp", minimum=1),
            "version": raw.get("version"),
        }

    def candles(
        self,
        symbol: str,
        *,
        start_timestamp_ms: int,
        end_timestamp_ms: int,
        interval: str = "Day1",
    ) -> list[dict[str, Any]]:
        if not symbol or start_timestamp_ms <= 0 or end_timestamp_ms <= start_timestamp_ms:
            raise ValueError("Invalid candle symbol or time window")
        seconds_per_bar = {
            "Min1": 60, "Min5": 300, "Min15": 900, "Min30": 1_800,
            "Min60": 3_600, "Hour4": 14_400, "Hour8": 28_800,
            "Day1": DAY_SECONDS, "Week1": 604_800, "Month1": 2_592_000,
        }.get(interval)
        if seconds_per_bar is None:
            raise ValueError("Unsupported MEXC candle interval")
        cursor = start_timestamp_ms // 1000
        end_seconds = end_timestamp_ms // 1000
        output: dict[int, dict[str, Any]] = {}
        while cursor < end_seconds:
            payload = self._request(
                f"/api/v1/contract/kline/{symbol}",
                {"interval": interval, "start": cursor, "end": end_seconds},
            )
            data = payload.get("data")
            if not isinstance(data, dict):
                raise MEXCAPIError(f"MEXC kline response malformed for {symbol}")
            arrays = {
                name: data.get(name)
                for name in ("time", "open", "high", "low", "close", "vol", "amount")
            }
            if any(not isinstance(value, list) for value in arrays.values()):
                raise MEXCAPIError(f"MEXC kline arrays incomplete for {symbol}")
            count = len(arrays["time"] or [])
            if any(len(value or []) != count for value in arrays.values()):
                raise MEXCAPIError(f"MEXC kline arrays have unequal lengths for {symbol}")
            if count == 0:
                break
            for i in range(count):
                stamp_seconds = _integer(arrays["time"][i], "kline time", minimum=1)
                stamp_ms = stamp_seconds * 1000
                if not start_timestamp_ms <= stamp_ms < end_timestamp_ms:
                    continue
                output[stamp_ms] = {
                    "timestamp_ms": stamp_ms,
                    "open": str(_decimal(arrays["open"][i], "kline open")),
                    "high": str(_decimal(arrays["high"][i], "kline high")),
                    "low": str(_decimal(arrays["low"][i], "kline low")),
                    "close": str(_decimal(arrays["close"][i], "kline close")),
                    "volume_contracts": str(_decimal(
                        arrays["vol"][i], "kline volume", allow_zero=True
                    )),
                    "turnover_usdt": str(_decimal(
                        arrays["amount"][i], "kline turnover", allow_zero=True
                    )),
                }
            last_stamp = max(
                _integer(value, "kline time", minimum=1) for value in arrays["time"]
            )
            if count < MAX_KLINE_ROWS:
                break
            next_cursor = last_stamp + seconds_per_bar
            if next_cursor <= cursor:
                raise MEXCAPIError(f"MEXC kline pagination stalled for {symbol}")
            cursor = next_cursor
        return [output[key] for key in sorted(output)]

    def funding_history(
        self,
        symbol: str,
        *,
        start_timestamp_ms: int,
        end_timestamp_ms: int,
        page_size: int = MAX_FUNDING_PAGE_SIZE,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        if not symbol or start_timestamp_ms < 0 or end_timestamp_ms <= start_timestamp_ms:
            raise ValueError("Invalid funding symbol or time window")
        if not 1 <= page_size <= MAX_FUNDING_PAGE_SIZE or max_pages < 1:
            raise ValueError("Invalid funding pagination settings")
        output: dict[int, dict[str, Any]] = {}
        for page_num in range(1, max_pages + 1):
            payload = self._request(
                "/api/v1/contract/funding_rate/history",
                {"symbol": symbol, "page_num": page_num, "page_size": page_size},
            )
            data = payload.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("resultList"), list):
                raise MEXCAPIError(f"MEXC funding history is malformed for {symbol}")
            records = [row for row in data["resultList"] if isinstance(row, dict)]
            if not records:
                break
            for row in records:
                stamp = _integer(row.get("settleTime"), "funding settleTime", minimum=1)
                if start_timestamp_ms <= stamp < end_timestamp_ms:
                    output[stamp] = {
                        "symbol": symbol,
                        "timestamp_ms": stamp,
                        "funding_rate": str(_signed_decimal(
                            row.get("fundingRate"), "fundingRate"
                        )),
                    }
            oldest = min(
                _integer(row.get("settleTime"), "funding settleTime", minimum=1)
                for row in records
            )
            if oldest < start_timestamp_ms or len(records) < page_size:
                break
            if page_num == max_pages:
                raise MEXCAPIError(f"MEXC funding pagination limit reached for {symbol}")
        return [output[key] for key in sorted(output)]

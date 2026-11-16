"""Pure MEXC-specific normalization for the cross-sectional paper portfolio."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import median
from typing import Any

from .execution import BookLevel, SimulatedFill, simulate_orderbook_fill
from .indicators import compute_q_series
from .portfolio import target_quantity
from .ranking import Candidate, rank_candidates

DEFAULT_Q_THRESHOLD = 2.0
MIN_HISTORY_FOR_RANKING = 35
MAX_BOOK_AGE_MS = 60_000
MAX_SHORTFALL_BPS = Decimal("10")
DEFAULT_MAX_TURNOVER_SHARE = Decimal("0.001")


@dataclass(frozen=True)
class MEXCRankings:
    research_longs: list[Candidate]
    research_shorts: list[Candidate]
    executable_longs: list[Candidate]
    executable_shorts: list[Candidate]
    instruments_by_key: dict[str, dict[str, Any]]
    excluded: list[str]


def _dec(value: object, field: str, *, positive: bool = False) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"Invalid {field}") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise ValueError(f"Invalid {field}")
    return parsed


def rank_mexc_universe(
    instruments: Sequence[dict[str, Any]],
    histories: Mapping[int, Sequence[dict[str, Any]]],
    tickers: Mapping[int, dict[str, Any]],
    nav: Decimal,
    *,
    threshold: float = DEFAULT_Q_THRESHOLD,
    minimum_history: int = MIN_HISTORY_FOR_RANKING,
    max_turnover_share: Decimal = DEFAULT_MAX_TURNOVER_SHARE,
) -> MEXCRankings:
    """Rank all valid Q observations and separately apply turnover execution gates."""
    if nav <= 0 or not nav.is_finite():
        raise ValueError("nav must be a finite positive Decimal")
    if minimum_history < 1 or max_turnover_share <= 0:
        raise ValueError("Invalid ranking history or turnover policy")

    observations: list[tuple[str, Any]] = []
    eligible_for_execution: set[str] = set()
    instruments_by_key: dict[str, dict[str, Any]] = {}
    excluded: list[str] = []

    for instrument in instruments:
        instrument_id = int(instrument["instrument_id"])
        symbol = str(instrument["symbol"])
        key = f"mexc:{instrument_id}"
        rows = sorted(
            histories.get(instrument_id, []),
            key=lambda row: int(row["timestamp_ms"]),
        )
        if len(rows) < minimum_history:
            excluded.append(f"{symbol}:INSUFFICIENT_HISTORY:{len(rows)}")
            continue
        ticker = tickers.get(instrument_id)
        if ticker is None or _dec(ticker.get("last_price"), "last_price") <= 0:
            excluded.append(f"{symbol}:MISSING_OR_INVALID_TICKER")
            continue
        closes = [float(row["close"]) for row in rows]
        points = compute_q_series(closes)
        point = points[-1]
        if point.q is None:
            excluded.append(f"{symbol}:NO_VALID_Q")
            continue

        observations.append((key, point))
        instruments_by_key[key] = instrument

        turnovers: list[Decimal] = []
        for row in rows[-30:]:
            value = row.get("turnover_usdt")
            if value is None:
                value = (
                    _dec(row["close"], "daily close", positive=True)
                    * _dec(row["volume"], "daily base volume", positive=True)
                )
            turnover = _dec(value, "daily turnover")
            if turnover > 0:
                turnovers.append(turnover)
        if not turnovers:
            excluded.append(f"{symbol}:NO_TURNOVER_HISTORY")
            continue
        median_turnover = Decimal(str(median(turnovers)))
        desired_leg_notional = nav * Decimal("0.5")
        if desired_leg_notional <= median_turnover * max_turnover_share:
            eligible_for_execution.add(key)
        else:
            excluded.append(f"{symbol}:TURNOVER_CAP")

    research_longs, research_shorts = rank_candidates(
        observations, threshold=threshold
    )
    executable_longs, executable_shorts = rank_candidates(
        observations,
        threshold=threshold,
        execution_eligible=eligible_for_execution,
    )
    return MEXCRankings(
        research_longs=research_longs,
        research_shorts=research_shorts,
        executable_longs=executable_longs,
        executable_shorts=executable_shorts,
        instruments_by_key=instruments_by_key,
        excluded=excluded,
    )


def base_quantity_rules(
    instrument: Mapping[str, Any],
    reference_price: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return base-unit step, minimum, maximum and contract multiplier."""
    contract_size = _dec(instrument["contract_size"], "contract_size", positive=True)
    step_contracts = _dec(
        instrument["quantity_step_contracts"], "quantity_step_contracts", positive=True
    )
    minimum_contracts = _dec(
        instrument["min_contracts"], "min_contracts", positive=True
    )
    maximum_contracts = _dec(
        instrument["max_contracts"], "max_contracts", positive=True
    )
    if reference_price <= 0 or maximum_contracts < minimum_contracts:
        raise ValueError("Invalid MEXC contract sizing bounds")
    return (
        step_contracts * contract_size,
        minimum_contracts * contract_size,
        maximum_contracts * contract_size,
        contract_size,
    )


def size_mexc_leg(
    instrument: Mapping[str, Any],
    nav: Decimal,
    reference_price: Decimal,
    *,
    allocation_fraction: Decimal = Decimal("0.5"),
) -> Decimal:
    """Size base-asset quantity while respecting MEXC contract volume increments."""
    step, minimum, maximum, _ = base_quantity_rules(instrument, reference_price)
    return target_quantity(
        nav,
        allocation_fraction,
        reference_price,
        step,
        minimum,
        Decimal("0"),
        maximum,
    )


def mexc_book_levels(
    raw_levels: Sequence[Mapping[str, Any]],
    contract_size: Decimal,
) -> list[BookLevel]:
    """Convert MEXC contract-count depth into the base units used by the fill model."""
    if not contract_size.is_finite() or contract_size <= 0:
        raise ValueError("contract_size must be positive")
    result: list[BookLevel] = []
    for row in raw_levels:
        price = _dec(row.get("price"), "book price", positive=True)
        quantity_contracts = _dec(
            row.get("quantity_contracts"), "book contract quantity", positive=True
        )
        result.append(BookLevel(price, quantity_contracts * contract_size))
    if not result:
        raise ValueError("MEXC order-book side is empty")
    return result


def simulate_mexc_fill(
    raw_book: Mapping[str, Any],
    instrument: Mapping[str, Any],
    side: str,
    base_quantity: Decimal,
    now_ms: int,
    *,
    max_shortfall_bps: Decimal = MAX_SHORTFALL_BPS,
) -> SimulatedFill:
    """Simulate a taker fill from current public depth; never submits an order."""
    timestamp = int(raw_book["timestamp_ms"])
    age = now_ms - timestamp
    if age < 0 or age > MAX_BOOK_AGE_MS:
        raise ValueError(f"Stale or future MEXC order book ({age} ms)")
    contract_size = _dec(instrument["contract_size"], "contract_size", positive=True)
    bids = mexc_book_levels(raw_book["bids"], contract_size)
    asks = mexc_book_levels(raw_book["asks"], contract_size)
    fee_rate = _dec(instrument["taker_fee_rate"], "taker_fee_rate")
    return simulate_orderbook_fill(
        side,
        base_quantity,
        bids,
        asks,
        fee_rate=fee_rate,
        max_shortfall_bps=max_shortfall_bps,
        allow_partial=False,
    )

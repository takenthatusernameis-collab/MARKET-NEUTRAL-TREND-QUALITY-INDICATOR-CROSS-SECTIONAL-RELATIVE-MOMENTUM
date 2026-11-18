"""MEXC-specific normalization for the cross-sectional paper portfolio."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from statistics import median
from typing import Any

from .execution import BookLevel, SimulatedFill, simulate_orderbook_fill
from .indicators import compute_q_series
from .portfolio import floor_to_step, target_quantity
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

        # All settlement types remain in the Q research ranking. Only the
        # homogeneous USDT quote+settlement subset can be sized in this account.
        usdt_account_eligible = instrument.get(
            "usdt_account_eligible",
            str(instrument.get("quote_asset", "")).upper() == "USDT"
            and str(instrument.get("settlement_asset", "")).upper() == "USDT",
        )
        if not usdt_account_eligible:
            excluded.append(f"{symbol}:NON_USDT_SETTLEMENT_RESEARCH_ONLY")
            continue

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
        desired_leg_notional = nav
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
    leverage: Decimal = Decimal("2"),
) -> Decimal:
    """Size from margin allocation × leverage, respecting MEXC increments.

    Default: 50% of NAV margin at 2x leverage = 1x NAV notional per leg.
    Two balanced legs therefore target 2x gross exposure.
    """
    if not leverage.is_finite() or leverage <= 0:
        raise ValueError("leverage must be finite and positive")
    notional_fraction = allocation_fraction * leverage
    if notional_fraction <= 0 or notional_fraction > 1:
        raise ValueError("allocation_fraction × leverage must be in (0, 1]")
    step, minimum, maximum, _ = base_quantity_rules(instrument, reference_price)
    return target_quantity(
        nav,
        notional_fraction,
        reference_price,
        step,
        minimum,
        Decimal("0"),
        maximum,
    )


def size_neutral_mexc_pair(
    long_instrument: Mapping[str, Any],
    short_instrument: Mapping[str, Any],
    nav: Decimal,
    long_price: Decimal,
    short_price: Decimal,
    *,
    allocation_fraction: Decimal = Decimal("0.5"),
    leverage: Decimal = Decimal("2"),
    max_imbalance_nav_fraction: Decimal = Decimal("0.005"),
    max_search_steps: int = 4096,
) -> dict[str, Decimal] | None:
    """Jointly size both legs on venue lot grids without exceeding target notional.

    The coarser notional lot is enumerated from the largest affordable size down.
    The other leg is floored to the largest lot that does not exceed that notional.
    A pair is returned only when both legs are executable and their mark notionals
    differ by no more than the configured fraction of NAV. Neither side is ever
    independently rounded up to satisfy a minimum.
    """
    for value, field in (
        (nav, "nav"),
        (long_price, "long_price"),
        (short_price, "short_price"),
        (allocation_fraction, "allocation_fraction"),
        (leverage, "leverage"),
        (max_imbalance_nav_fraction, "max_imbalance_nav_fraction"),
    ):
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError(f"{field} must be a finite Decimal")
    if nav <= 0 or long_price <= 0 or short_price <= 0:
        raise ValueError("NAV and both reference prices must be positive")
    if allocation_fraction <= 0 or allocation_fraction > 1 or leverage <= 0:
        raise ValueError("Invalid allocation fraction or leverage")
    target_fraction = allocation_fraction * leverage
    if target_fraction <= 0 or target_fraction > 1:
        raise ValueError("Per-leg target notional must be in (0, NAV]")
    if max_imbalance_nav_fraction < 0 or max_search_steps < 1:
        raise ValueError("Invalid neutrality tolerance or search limit")

    target_notional = nav * target_fraction
    long_step, long_min, long_max, _ = base_quantity_rules(
        long_instrument, long_price
    )
    short_step, short_min, short_max, _ = base_quantity_rules(
        short_instrument, short_price
    )

    long_max_target = floor_to_step(
        min(long_max, target_notional / long_price), long_step
    )
    short_max_target = floor_to_step(
        min(short_max, target_notional / short_price), short_step
    )
    if long_max_target < long_min or short_max_target < short_min:
        return None

    long_lot_notional = long_step * long_price
    short_lot_notional = short_step * short_price
    primary_is_long = long_lot_notional >= short_lot_notional
    if primary_is_long:
        primary_step = long_step
        primary_min = long_min
        primary_max_target = long_max_target
        primary_price = long_price
        other_step = short_step
        other_min = short_min
        other_max_target = short_max_target
        other_price = short_price
    else:
        primary_step = short_step
        primary_min = short_min
        primary_max_target = short_max_target
        primary_price = short_price
        other_step = long_step
        other_min = long_min
        other_max_target = long_max_target
        other_price = long_price

    minimum_lots = int(
        (primary_min / primary_step).to_integral_value(rounding=ROUND_CEILING)
    )
    maximum_lots = int(
        (primary_max_target / primary_step).to_integral_value(rounding=ROUND_DOWN)
    )
    if maximum_lots < minimum_lots:
        return None
    first_lot = max(minimum_lots, maximum_lots - max_search_steps + 1)

    for lot_count in range(maximum_lots, first_lot - 1, -1):
        primary_quantity = primary_step * lot_count
        primary_notional = primary_quantity * primary_price
        lower_quantity = floor_to_step(
            min(other_max_target, primary_notional / other_price),
            other_step,
        )
        adjacent_quantities = [lower_quantity]
        upper_quantity = lower_quantity + other_step
        if upper_quantity <= other_max_target:
            adjacent_quantities.append(upper_quantity)

        candidates: list[dict[str, Decimal]] = []
        for other_quantity in adjacent_quantities:
            if other_quantity < other_min:
                continue
            if primary_is_long:
                long_quantity, short_quantity = primary_quantity, other_quantity
            else:
                long_quantity, short_quantity = other_quantity, primary_quantity

            long_notional = long_quantity * long_price
            short_notional = short_quantity * short_price
            if max(long_notional, short_notional) > target_notional:
                continue
            imbalance_fraction = abs(long_notional - short_notional) / nav
            if imbalance_fraction > max_imbalance_nav_fraction:
                continue
            candidates.append({
                "long_quantity": long_quantity,
                "short_quantity": short_quantity,
                "long_notional": long_notional,
                "short_notional": short_notional,
                "target_leg_notional": target_notional,
                "imbalance_fraction": imbalance_fraction,
            })

        if candidates:
            return min(
                candidates,
                key=lambda row: (
                    row["imbalance_fraction"],
                    -(row["long_notional"] + row["short_notional"]),
                ),
            )
    return None


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

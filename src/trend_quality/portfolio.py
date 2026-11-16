"""Pure Decimal-based portfolio sizing and linear-perpetual accounting."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True)
class Position:
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal

    def __post_init__(self) -> None:
        if self.side not in ("long", "short"):
            raise ValueError("side must be long or short")
        if self.quantity <= ZERO or self.entry_price <= ZERO:
            raise ValueError("quantity and entry_price must be positive")

    def unrealized_pnl(self, mark_price: Decimal) -> Decimal:
        if mark_price <= ZERO:
            raise ValueError("mark_price must be positive")
        sign = ONE if self.side == "long" else Decimal("-1")
        return sign * self.quantity * (mark_price - self.entry_price)


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if value < ZERO or step <= ZERO:
        raise ValueError("value must be non-negative and step positive")
    units = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return units * step


def target_quantity(
    nav: Decimal,
    allocation_fraction: Decimal,
    price: Decimal,
    qty_step: Decimal,
    min_qty: Decimal,
    min_notional: Decimal,
    max_market_qty: Decimal | None = None,
) -> Decimal:
    """Size a leg and round down; never increase target exposure to meet minima."""
    if nav <= ZERO or price <= ZERO:
        raise ValueError("nav and price must be positive")
    if allocation_fraction <= ZERO or allocation_fraction > ONE:
        raise ValueError("allocation_fraction must be in (0, 1]")
    if min_qty < ZERO or min_notional < ZERO:
        raise ValueError("minimum constraints must be non-negative")
    raw_quantity = nav * allocation_fraction / price
    quantity = floor_to_step(raw_quantity, qty_step)
    if max_market_qty is not None and quantity > max_market_qty:
        quantity = floor_to_step(max_market_qty, qty_step)
    if quantity < min_qty or quantity * price < min_notional:
        return ZERO
    return quantity


def funding_cashflow(
    side: str,
    quantity: Decimal,
    mark_price: Decimal,
    funding_rate: Decimal,
) -> Decimal:
    if side not in ("long", "short"):
        raise ValueError("side must be long or short")
    if quantity <= ZERO or mark_price <= ZERO:
        raise ValueError("quantity and mark_price must be positive")
    sign = ONE if side == "long" else Decimal("-1")
    return -sign * quantity * mark_price * funding_rate


def portfolio_exposure(
    nav: Decimal,
    long_notional: Decimal,
    short_notional: Decimal,
) -> dict[str, Decimal]:
    if nav <= ZERO:
        raise ValueError("nav must be positive")
    if long_notional < ZERO or short_notional < ZERO:
        raise ValueError("notionals must be non-negative magnitudes")
    gross = (long_notional + short_notional) / nav
    net = (long_notional - short_notional) / nav
    imbalance = abs(long_notional - short_notional) / nav
    return {
        "gross_exposure": gross,
        "net_exposure": net,
        "dollar_neutrality_imbalance": imbalance,
    }


def calculate_nav(
    initial_capital: Decimal,
    realized_gross_pnl: Decimal,
    unrealized_pnl: Decimal,
    fees: Decimal,
    confirmed_funding: Decimal,
    adjustments: Decimal = ZERO,
) -> Decimal:
    """NAV = initial + realized gross + unrealized - fees + funding + adjustments."""
    return (
        initial_capital
        + realized_gross_pnl
        + unrealized_pnl
        - fees
        + confirmed_funding
        + adjustments
    )

"""Deterministic cross-sectional candidate ranking."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from .indicators import QObservation


@dataclass(frozen=True)
class Candidate:
    symbol: str
    q: float
    b: float | None
    direction: str
    cycle_age: int | None
    semi_cycle_direction: str | None = None


def rank_candidates(
    observations: Iterable[tuple[str, QObservation]],
    *,
    threshold: float = 2.0,
    execution_eligible: set[str] | None = None,
) -> tuple[list[Candidate], list[Candidate]]:
    """Return bullish descending-Q and bearish ascending-Q rankings."""
    if not isfinite(threshold) or threshold < 0:
        raise ValueError("threshold must be finite and non-negative")
    bullish: list[Candidate] = []
    bearish: list[Candidate] = []
    for symbol, point in observations:
        if execution_eligible is not None and symbol not in execution_eligible:
            continue
        q_value = point.q
        if q_value is None or not isfinite(q_value):
            continue
        # Signed Q itself determines trend direction. The EMA semi-cycle is
        # retained as metadata; it must not override Q's signed definition.
        if q_value > threshold:
            bullish.append(
                Candidate(symbol, float(q_value), point.b, "long", point.cycle_age, point.direction)
            )
        elif q_value < -threshold:
            bearish.append(
                Candidate(symbol, float(q_value), point.b, "short", point.cycle_age, point.direction)
            )
    bullish.sort(key=lambda item: (-item.q, item.symbol))
    bearish.sort(key=lambda item: (item.q, item.symbol))
    return bullish, bearish

"""Deterministic selection of one long and one short candidate."""
from __future__ import annotations

from dataclasses import dataclass

from .ranking import Candidate


@dataclass(frozen=True)
class SelectedPair:
    long: Candidate
    short: Candidate


def select_pair(
    bullish: list[Candidate],
    bearish: list[Candidate],
    *,
    max_fallbacks: int = 10,
) -> SelectedPair | None:
    """Select highest-ranked distinct-symbol pair, bounded by fallback policy."""
    if max_fallbacks < 1:
        raise ValueError("max_fallbacks must be positive")
    long_candidates = bullish[:max_fallbacks]
    short_candidates = bearish[:max_fallbacks]
    for long_candidate in long_candidates:
        for short_candidate in short_candidates:
            if long_candidate.symbol != short_candidate.symbol:
                return SelectedPair(long_candidate, short_candidate)
    return None

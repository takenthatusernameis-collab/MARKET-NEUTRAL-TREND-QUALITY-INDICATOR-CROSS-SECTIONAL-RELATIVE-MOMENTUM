from __future__ import annotations

from decimal import Decimal
from typing import Any

from trend_quality.indicators import QObservation
from trend_quality.mexc_paper import (
    mexc_book_levels,
    rank_mexc_universe,
    simulate_mexc_fill,
    size_mexc_leg,
)


def instrument(instrument_id: int, symbol: str) -> dict[str, Any]:
    return {
        "instrument_id": instrument_id,
        "symbol": symbol,
        "category": "crypto",
        "contract_size": "0.0001",
        "quantity_step_contracts": "1",
        "min_contracts": "1",
        "max_contracts": "10000",
        "taker_fee_rate": "0.0002",
    }


def history(instrument_id: int, close: str, turnover: str) -> list[dict[str, Any]]:
    return [
        {
            "instrument_id": instrument_id,
            "timestamp_ms": 1_700_000_000_000 + day * 86_400_000,
            "close": close,
            "volume": "1000",
            "turnover_usdt": turnover,
        }
        for day in range(40)
    ]


def test_ranker_keeps_research_universe_separate_from_execution_gate(monkeypatch) -> None:
    import trend_quality.mexc_paper as paper

    def fake_q(closes: list[float]) -> list[QObservation]:
        q = 3.5 if closes[0] == 100.0 else -3.2
        return [QObservation(
            index=len(closes) - 1,
            direction="bullish" if q > 0 else "bearish",
            cycle_start_index=1,
            cycle_age=len(closes) - 1,
            fast_ema=1.0,
            slow_ema=0.9,
            cpc=2.0,
            trend=2.0,
            noise=0.5,
            q=q,
            b=80.0,
        )]

    monkeypatch.setattr(paper, "compute_q_series", fake_q)
    instruments = [instrument(1, "UP_USDT"), instrument(2, "DOWN_USDT")]
    histories = {
        1: history(1, "100", "100000"),
        2: history(2, "90", "1000"),
    }
    tickers = {
        1: {"last_price": "100"},
        2: {"last_price": "90"},
    }
    ranked = rank_mexc_universe(instruments, histories, tickers, Decimal("100"))
    assert [row.symbol for row in ranked.research_longs] == ["mexc:1"]
    assert [row.symbol for row in ranked.research_shorts] == ["mexc:2"]
    assert [row.symbol for row in ranked.executable_longs] == ["mexc:1"]
    assert ranked.executable_shorts == []
    assert any("TURNOVER_CAP" in reason for reason in ranked.excluded)


def test_mexc_contract_sizing_converts_contracts_to_base_quantity() -> None:
    rules = instrument(1, "BTC_USDT")
    quantity = size_mexc_leg(rules, Decimal("100"), Decimal("100"))
    assert quantity == Decimal("0.5000")


def test_mexc_orderbook_levels_convert_contract_depth_to_base_units() -> None:
    levels = mexc_book_levels(
        [
            {"price": "100", "quantity_contracts": "20000"},
            {"price": "99", "quantity_contracts": "10000"},
        ],
        Decimal("0.0001"),
    )
    assert levels[0].quantity == Decimal("2.0000")
    assert levels[1].quantity == Decimal("1.0000")


def test_mexc_paper_fill_uses_contract_multiplier_and_taker_fee() -> None:
    rules = instrument(1, "BTC_USDT")
    book = {
        "timestamp_ms": 1_700_000_000_000,
        "bids": [{"price": "100", "quantity_contracts": "20000"}],
        "asks": [{"price": "100.01", "quantity_contracts": "20000"}],
    }
    fill = simulate_mexc_fill(
        book, rules, "buy", Decimal("0.5"), 1_700_000_000_000
    )
    assert fill.filled_quantity == Decimal("0.5")
    assert fill.notional == Decimal("50.005")
    assert fill.fee == Decimal("0.010001")
    assert fill.shortfall_bps < Decimal("10")

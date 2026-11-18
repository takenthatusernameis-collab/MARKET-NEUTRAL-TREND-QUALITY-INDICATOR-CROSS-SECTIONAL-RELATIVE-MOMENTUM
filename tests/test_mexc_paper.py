from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path
from typing import Any

from trend_quality.execution import SimulatedFill
from trend_quality.indicators import QObservation
from trend_quality.mexc_paper import (
    MEXCRankings,
    mexc_book_levels,
    rank_mexc_universe,
    simulate_mexc_fill,
    size_mexc_leg,
)
from trend_quality.mexc_portfolio import (
    initial_portfolio_state,
    open_paper_position,
)
from trend_quality.ranking import Candidate


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
        "quote_asset": "USDT",
        "settlement_asset": "USDT",
        "usdt_account_eligible": True,
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
    instruments = [
        instrument(1, "UP_USDT"),
        instrument(2, "DOWN_USDT"),
        {
            **instrument(3, "ALT_USDC"),
            "quote_asset": "USDC",
            "settlement_asset": "USDC",
            "usdt_account_eligible": False,
        },
    ]
    histories = {
        1: history(1, "100", "100000"),
        2: history(2, "90", "1000"),
        3: history(3, "110", "100000"),
    }
    tickers = {
        1: {"last_price": "100"},
        2: {"last_price": "90"},
        3: {"last_price": "110"},
    }
    ranked = rank_mexc_universe(instruments, histories, tickers, Decimal("100"))
    assert [row.symbol for row in ranked.research_longs] == ["mexc:1"]
    assert [row.symbol for row in ranked.research_shorts] == ["mexc:2", "mexc:3"]
    assert [row.symbol for row in ranked.executable_longs] == ["mexc:1"]
    assert ranked.executable_shorts == []
    assert any("NON_USDT_SETTLEMENT_RESEARCH_ONLY" in reason for reason in ranked.excluded)
    assert any("TURNOVER_CAP" in reason for reason in ranked.excluded)


def test_mexc_contract_sizing_converts_contracts_to_base_quantity() -> None:
    rules = instrument(1, "BTC_USDT")
    quantity = size_mexc_leg(rules, Decimal("100"), Decimal("100"))
    assert quantity == Decimal("1.0000")


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



def test_one_usdt_account_sizes_each_leg_to_one_usdt_notional_at_two_x() -> None:
    rules = instrument(1, "TEST_USDT")
    quantity = size_mexc_leg(
        rules,
        Decimal("1"),
        Decimal("100"),
        allocation_fraction=Decimal("0.5"),
        leverage=Decimal("2"),
    )
    assert quantity == Decimal("0.0100")
    assert quantity * Decimal("100") == Decimal("1")



def test_ten_usdt_seed_clears_a_ten_unit_contract_minimum_that_blocks_one_usdt() -> None:
    rules = {
        **instrument(77, "MIN_SIZE_USDT"),
        "contract_size": "1",
        "quantity_step_contracts": "1",
        "min_contracts": "10",
    }
    one_usdt_quantity = size_mexc_leg(
        rules,
        Decimal("1"),
        Decimal("0.5"),
        allocation_fraction=Decimal("0.5"),
        leverage=Decimal("2"),
    )
    ten_usdt_quantity = size_mexc_leg(
        rules,
        Decimal("10"),
        Decimal("0.5"),
        allocation_fraction=Decimal("0.5"),
        leverage=Decimal("2"),
    )
    assert one_usdt_quantity == Decimal("0")
    assert ten_usdt_quantity == Decimal("20")
    assert ten_usdt_quantity * Decimal("0.5") == Decimal("10")



def test_frozen_daily_entry_shortlist_round_trips_for_five_minute_retries() -> None:
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "mexc_paper_cycle.py"
    )
    spec = importlib.util.spec_from_file_location("mexc_paper_cycle", script_path)
    assert spec is not None and spec.loader is not None
    cycle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cycle)

    long_instrument = instrument(101, "LONG_USDT")
    short_instrument = instrument(202, "SHORT_USDT")
    rankings = MEXCRankings(
        research_longs=[],
        research_shorts=[],
        executable_longs=[
            Candidate("mexc:101", 3.5, 88.0, "long", 41, "bullish")
        ],
        executable_shorts=[
            Candidate("mexc:202", -4.2, 91.0, "short", 36, "bearish")
        ],
        instruments_by_key={
            "mexc:101": long_instrument,
            "mexc:202": short_instrument,
        },
        excluded=[],
    )

    pending = cycle._pending_entry_signal(rankings, 1_800_000_000_000)
    assert pending is not None
    assert pending["daily_bar_timestamp_ms"] == 1_800_000_000_000
    assert pending["attempt_count"] == 0
    assert pending["executable_longs"][0]["q"] == "3.5"
    assert pending["executable_shorts"][0]["q"] == "-4.2"

    restored = cycle._restore_pending_rankings(
        pending,
        {"101": long_instrument, "202": short_instrument},
    )
    assert restored is not None
    assert [row.symbol for row in restored.executable_longs] == ["mexc:101"]
    assert [row.symbol for row in restored.executable_shorts] == ["mexc:202"]
    assert restored.instruments_by_key["mexc:101"]["symbol"] == "LONG_USDT"
    assert restored.instruments_by_key["mexc:202"]["symbol"] == "SHORT_USDT"



def test_daily_refresh_closes_and_reopens_even_when_same_contracts_are_selected() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "mexc_paper_cycle.py"
    spec = importlib.util.spec_from_file_location("mexc_paper_cycle_full_refresh", script_path)
    assert spec is not None and spec.loader is not None
    cycle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cycle)

    now_ms = 1_800_000_000_000
    long_instrument = instrument(101, "LONG_USDT")
    short_instrument = instrument(202, "SHORT_USDT")
    long_ticker = {"mid_price": "100", "mark_price": "100"}
    short_ticker = {"mid_price": "100", "mark_price": "100"}
    state = initial_portfolio_state(Decimal("100"))

    def opening_fill(side: str, quantity: str) -> SimulatedFill:
        qty = Decimal(quantity)
        return SimulatedFill(
            side=side, requested_quantity=qty, filled_quantity=qty,
            average_price=Decimal("100"), reference_price=Decimal("100"),
            notional=qty * Decimal("100"), fee=Decimal("0"),
            shortfall=Decimal("0"), shortfall_bps=Decimal("0"),
            complete=True, levels_consumed=1,
        )

    old_long = open_paper_position(
        state, long_instrument, long_ticker, "long", Decimal("2"),
        opening_fill("buy", "0.8"), now_ms - 86_400_000,
    )
    old_short = open_paper_position(
        state, short_instrument, short_ticker, "short", Decimal("2"),
        opening_fill("sell", "1.2"), now_ms - 86_400_000,
    )
    old_times = {101: old_long["entry_timestamp_ms"], 202: old_short["entry_timestamp_ms"]}
    rankings = MEXCRankings(
        research_longs=[], research_shorts=[],
        executable_longs=[Candidate("mexc:101", 3.5, 88.0, "long", 41, "bullish")],
        executable_shorts=[Candidate("mexc:202", -4.2, 91.0, "short", 36, "bearish")],
        instruments_by_key={"mexc:101": long_instrument, "mexc:202": short_instrument},
        excluded=[],
    )
    history_rows = [
        {"timestamp_ms": now_ms - (40 - day) * 86_400_000,
         "high": "102", "low": "98", "close": "100"}
        for day in range(40)
    ]
    history = {101: history_rows, 202: history_rows}
    tickers = {101: long_ticker, 202: short_ticker}

    class PublicBookClient:
        def server_time_ms(self) -> int:
            return now_ms

        def orderbook(self, symbol: str, depth: int) -> dict[str, Any]:
            return {
                "timestamp_ms": now_ms,
                "bids": [{"price": "99.99", "quantity_contracts": "100000000"}],
                "asks": [{"price": "100.01", "quantity_contracts": "100000000"}],
            }

    result = cycle._rebuild_fresh_portfolio(
        PublicBookClient(), state, rankings, history, tickers,
        {101: long_instrument, 202: short_instrument}, now_ms,
    )
    assert result["status"] == "PAIR_REBUILT"
    assert [row["action"] for row in result["close_actions"]] == ["CLOSED", "CLOSED"]
    assert [row["action"] for row in result["open_actions"]] == ["OPENED", "OPENED"]
    rebuilt = result["portfolio_state"]
    assert {row["instrument_id"] for row in rebuilt["positions"]} == {101, 202}
    assert all(row["entry_timestamp_ms"] == now_ms for row in rebuilt["positions"])
    assert all(
        row["entry_timestamp_ms"] != old_times[row["instrument_id"]]
        for row in rebuilt["positions"]
    )
    assert len(rebuilt["closed_trade_net_pnls"]) == 2
    # The source account is not changed until its caller commits the complete refresh.
    assert {row["instrument_id"]: row["quantity"] for row in state["positions"]} == {
        101: "0.8", 202: "1.2",
    }


def test_execution_pair_accepts_independent_lot_rounding_without_percentage_gate() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "mexc_paper_cycle.py"
    spec = importlib.util.spec_from_file_location("mexc_paper_cycle_no_tolerance", script_path)
    assert spec is not None and spec.loader is not None
    cycle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cycle)

    now_ms = 1_800_000_000_000
    long_instrument = {
        **instrument(1760, "SPOTSTOCK_USDT"),
        "contract_size": "0.01", "quantity_step_contracts": "1",
        "min_contracts": "1", "max_contracts": "20000",
    }
    short_instrument = {
        **instrument(1899, "BILL_USDT"),
        "contract_size": "100", "quantity_step_contracts": "1",
        "min_contracts": "1", "max_contracts": "2000",
    }
    long_price = Decimal("600.54")
    short_price = Decimal("0.003906")
    rankings = MEXCRankings(
        research_longs=[], research_shorts=[],
        executable_longs=[Candidate("mexc:1760", 3.5, 88.0, "long", 41, "bullish")],
        executable_shorts=[Candidate("mexc:1899", -4.2, 91.0, "short", 36, "bearish")],
        instruments_by_key={"mexc:1760": long_instrument, "mexc:1899": short_instrument},
        excluded=[],
    )
    history = {
        1760: [
            {"timestamp_ms": now_ms - (30 - day) * 86_400_000,
             "high": "606.55", "low": "594.53", "close": "600.54"}
            for day in range(30)
        ],
        1899: [
            {"timestamp_ms": now_ms - (30 - day) * 86_400_000,
             "high": "0.003945", "low": "0.003867", "close": "0.003906"}
            for day in range(30)
        ],
    }
    tickers = {
        1760: {"mid_price": str(long_price), "mark_price": str(long_price)},
        1899: {"mid_price": str(short_price), "mark_price": str(short_price)},
    }

    class PublicBookClient:
        def server_time_ms(self) -> int:
            return now_ms

        def orderbook(self, symbol: str, depth: int) -> dict[str, Any]:
            price = long_price if symbol == "SPOTSTOCK_USDT" else short_price
            return {
                "timestamp_ms": now_ms,
                "bids": [{"price": str(price), "quantity_contracts": "100000000"}],
                "asks": [{"price": str(price), "quantity_contracts": "100000000"}],
            }

    pair = cycle._try_pair(
        PublicBookClient(), rankings, history, tickers,
        initial_portfolio_state(Decimal("50")), now_ms,
    )
    assert pair is not None
    proposed, fills, _symbols = pair
    notionals = {row["side"]: Decimal(row["mark_notional_usdt"]) for row in proposed}
    assert notionals["long"] <= Decimal("50")
    assert notionals["short"] <= Decimal("50")
    imbalance_fraction = abs(notionals["long"] - notionals["short"]) / Decimal("50")
    assert imbalance_fraction > Decimal("0.005")
    assert all(
        Decimal(row["pair_imbalance_nav_fraction"]) > Decimal("0.005")
        for row in fills
    )


def test_joint_pair_sizing_respects_lot_grids_and_neutrality_tolerance() -> None:
    from trend_quality.mexc_paper import size_neutral_mexc_pair

    long_instrument = {
        **instrument(1760, "SPOTSTOCK_USDT"),
        "contract_size": "0.01",
        "quantity_step_contracts": "1",
        "min_contracts": "1",
        "max_contracts": "20000",
    }
    short_instrument = {
        **instrument(1899, "BILL_USDT"),
        "contract_size": "100",
        "quantity_step_contracts": "1",
        "min_contracts": "1",
        "max_contracts": "2000",
    }

    sized = size_neutral_mexc_pair(
        long_instrument,
        short_instrument,
        Decimal("50"),
        Decimal("600.54"),
        Decimal("0.003906"),
    )
    assert sized is not None
    assert sized["long_quantity"] == Decimal("0.08")
    assert sized["short_quantity"] == Decimal("12300")
    assert sized["long_notional"] == Decimal("48.0432")
    assert sized["short_notional"] == Decimal("48.043800")
    assert sized["imbalance_fraction"] <= Decimal("0.005")
    assert sized["long_notional"] <= Decimal("50")
    assert sized["short_notional"] <= Decimal("50")

    # The former 10-USDT sizing cannot reach the same neutrality band for
    # these venue lot sizes. It must not fabricate a one-sided executable pair.
    assert size_neutral_mexc_pair(
        long_instrument,
        short_instrument,
        Decimal("10"),
        Decimal("600.54"),
        Decimal("0.003906"),
    ) is None


def test_joint_pair_sizing_never_rounds_an_unaffordable_leg() -> None:
    from trend_quality.mexc_paper import size_neutral_mexc_pair

    long_instrument = {
        **instrument(11, "COARSE_LONG_USDT"),
        "contract_size": "1",
        "quantity_step_contracts": "10",
        "min_contracts": "10",
        "max_contracts": "100000",
    }
    short_instrument = {
        **instrument(22, "FINE_SHORT_USDT"),
        "contract_size": "0.001",
        "quantity_step_contracts": "1",
        "min_contracts": "1",
        "max_contracts": "100000000",
    }

    sized = size_neutral_mexc_pair(
        long_instrument,
        short_instrument,
        Decimal("50"),
        Decimal("1"),
        Decimal("0.01"),
    )
    assert sized is not None
    assert sized["long_notional"] <= Decimal("50")
    assert sized["short_notional"] <= Decimal("50")
    assert sized["imbalance_fraction"] <= Decimal("0.005")



from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

from trend_quality.ranking import Candidate


def load_cycle_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "mexc_paper_cycle.py"
    spec = importlib.util.spec_from_file_location("mexc_paper_cycle_test_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ranking_report_uses_exchange_ticker_not_internal_key() -> None:
    cycle = load_cycle_module()
    candidate = Candidate(
        symbol="mexc:233",
        q=5.45,
        b=84.5,
        direction="long",
        cycle_age=40,
    )
    instrument = {
        "instrument_id": 233,
        "symbol": "BTC_USDT",
        "category": "crypto",
    }

    rows = cycle._ranking_report_rows(
        [candidate],
        {"mexc:233": instrument},
    )

    assert rows == [{
        "symbol": "BTC_USDT",
        "instrument_id": 233,
        "category": "crypto",
        "q": "5.45",
        "direction": "long",
        "cycle_age": 40,
        "b": "84.5",
    }]


def test_execution_ranking_report_can_omit_supplementary_b() -> None:
    cycle = load_cycle_module()
    candidate = Candidate(
        symbol="mexc:326",
        q=-50.76,
        b=98.06,
        direction="short",
        cycle_age=65,
    )
    rows = cycle._ranking_report_rows(
        [candidate],
        {"mexc:326": {
            "instrument_id": 326,
            "symbol": "ETH_USDT",
            "category": "crypto",
        }},
        include_b=False,
    )
    assert rows[0]["symbol"] == "ETH_USDT"
    assert "b" not in rows[0]



def test_daily_risk_path_rejects_missing_stale_and_nonpositive_position_marks() -> None:
    cycle = load_cycle_module()
    positions = [{"instrument_id": 7, "symbol": "TEST_USDT"}]
    assert cycle._stale_or_missing_position_marks(
        positions,
        {7: {"timestamp_ms": 1_000_000, "mark_price": "10"}},
        1_100_000,
    ) == []
    assert cycle._stale_or_missing_position_marks(
        positions,
        {7: {"timestamp_ms": 1_000_000, "mark_price": "10"}},
        1_400_001,
    ) == ["TEST_USDT"]
    assert cycle._stale_or_missing_position_marks(positions, {}, 1_100_000) == [
        "TEST_USDT"
    ]
    assert cycle._stale_or_missing_position_marks(
        positions,
        {7: {"timestamp_ms": 1_100_000, "mark_price": "0"}},
        1_100_000,
    ) == ["TEST_USDT"]



def test_paper_state_writer_requires_explicit_true_flag(monkeypatch) -> None:
    cycle = load_cycle_module()
    monkeypatch.delenv("PAPER_STATE_WRITE_ENABLED", raising=False)
    assert cycle._paper_state_writer_requested() is False
    monkeypatch.setenv("PAPER_STATE_WRITE_ENABLED", "true")
    assert cycle._paper_state_writer_requested() is True
    monkeypatch.setenv("PAPER_STATE_WRITE_ENABLED", "FALSE")
    assert cycle._paper_state_writer_requested() is False


def test_only_active_mexc_workflow_can_write_portfolio_state() -> None:
    root = Path(__file__).resolve().parents[1]
    mexc = (root / ".github" / "workflows" / "mexc-paper-cycle.yml").read_text()
    preflight = (
        root / ".github" / "workflows" / "mexc-public-preflight.yml"
    ).read_text()
    retired_polymarket = (
        root / ".github" / "workflows" / "polymarket-paper-cycle.yml"
    )
    cycle_source = (root / "scripts" / "mexc_paper_cycle.py").read_text()

    assert "ACTIVE — MEXC $50 USDT PAPER ONLY" in mexc
    assert "▶ MANUAL PAPER RUN — MEXC $50 USDT" in mexc
    assert "I_CONFIRM_ACTIVE_50_USDT_PAPER_ONLY" in mexc
    assert "group: paper-state-branch-single-writer" in mexc
    assert "cancel-in-progress: false" in mexc
    assert "PAPER_STATE_WRITE_ENABLED: ${{ vars.PAPER_STATE_WRITE_ENABLED || 'true' }}" in mexc
    assert "STATE_PROTECTION_TOKEN" not in mexc
    assert "STATE_PROTECTION_TOKEN" not in cycle_source
    assert "def _state_branch_protection" not in cycle_source

    assert not retired_polymarket.exists()
    assert "DIAGNOSTIC ONLY — READ-ONLY MEXC PREFLIGHT" in preflight
    assert "permissions:\n  contents: read" in preflight
    assert "contents: write" not in preflight


def test_recovery_probe_requires_fresh_checkout_and_does_not_initialize_account(tmp_path) -> None:
    from trend_quality.event_journal import build_event_batch, write_batch_atomic

    cycle = load_cycle_module()
    event = {
        "event_id": "state-probe-1",
        "idempotency_key": "state-probe-1",
        "account_id": cycle.ACCOUNT_ID,
        "strategy_id": cycle.STRATEGY_ID,
        "occurred_at_ms": 1_800_000_000_000,
        "event_type": "paper_state_recovery_probe",
        "payload": {
            "details": {
                "protocol": "PUBLISH_READBACK_THEN_FRESH_CHECKOUT",
                "financial_state_created": False,
                "account_initialized": False,
                "orders_submitted": 0,
            }
        },
    }
    batch = build_event_batch(
        "state-probe-1",
        1_800_000_000_000,
        [event],
    )
    write_batch_atomic(tmp_path, batch)

    portfolio, previous_hash, recovered = cycle._load_state(tmp_path)
    assert portfolio is None
    assert previous_hash == batch["batch_hash"]
    assert recovered is True


def test_recovery_probe_not_inferred_from_unrelated_state_event(tmp_path) -> None:
    from trend_quality.event_journal import build_event_batch, write_batch_atomic

    cycle = load_cycle_module()
    event = {
        "event_id": "risk-event-1",
        "idempotency_key": "risk-event-1",
        "account_id": cycle.ACCOUNT_ID,
        "strategy_id": cycle.STRATEGY_ID,
        "occurred_at_ms": 1_800_000_000_000,
        "event_type": "paper_risk_update",
        "payload": {"details": {"protocol": "PUBLISH_READBACK_THEN_FRESH_CHECKOUT"}},
    }
    batch = build_event_batch("risk-event-1", 1_800_000_000_000, [event])
    write_batch_atomic(tmp_path, batch)

    portfolio, previous_hash, recovered = cycle._load_state(tmp_path)
    assert portfolio is None
    assert previous_hash == batch["batch_hash"]
    assert recovered is False


def test_recovery_probe_with_financial_claim_does_not_unlock_initialization(tmp_path) -> None:
    from trend_quality.event_journal import build_event_batch, write_batch_atomic

    cycle = load_cycle_module()
    event = {
        "event_id": "state-probe-invalid",
        "idempotency_key": "state-probe-invalid",
        "account_id": cycle.ACCOUNT_ID,
        "strategy_id": cycle.STRATEGY_ID,
        "occurred_at_ms": 1_800_000_000_000,
        "event_type": "paper_state_recovery_probe",
        "payload": {
            "details": {
                "protocol": "PUBLISH_READBACK_THEN_FRESH_CHECKOUT",
                "financial_state_created": True,
                "account_initialized": False,
                "orders_submitted": 0,
            }
        },
    }
    batch = build_event_batch(
        "state-probe-invalid",
        1_800_000_000_000,
        [event],
    )
    write_batch_atomic(tmp_path, batch)

    portfolio, _previous_hash, recovered = cycle._load_state(tmp_path)
    assert portfolio is None
    assert recovered is False


def test_recovery_probe_with_orders_does_not_unlock_initialization(tmp_path) -> None:
    from trend_quality.event_journal import build_event_batch, write_batch_atomic

    cycle = load_cycle_module()
    event = {
        "event_id": "state-probe-orders",
        "idempotency_key": "state-probe-orders",
        "account_id": cycle.ACCOUNT_ID,
        "strategy_id": cycle.STRATEGY_ID,
        "occurred_at_ms": 1_800_000_000_000,
        "event_type": "paper_state_recovery_probe",
        "payload": {
            "details": {
                "protocol": "PUBLISH_READBACK_THEN_FRESH_CHECKOUT",
                "financial_state_created": False,
                "account_initialized": False,
                "orders_submitted": 1,
            }
        },
    }
    batch = build_event_batch(
        "state-probe-orders",
        1_800_000_000_000,
        [event],
    )
    write_batch_atomic(tmp_path, batch)

    portfolio, _previous_hash, recovered = cycle._load_state(tmp_path)
    assert portfolio is None
    assert recovered is False


def test_initialized_paper_account_restores_from_probe_chained_state(tmp_path) -> None:
    from trend_quality.event_journal import build_event_batch, write_batch_atomic

    cycle = load_cycle_module()
    stamp = 1_800_000_000_000
    probe_event = {
        "event_id": "probe-before-init",
        "idempotency_key": "probe-before-init",
        "account_id": cycle.ACCOUNT_ID,
        "strategy_id": cycle.STRATEGY_ID,
        "occurred_at_ms": stamp,
        "event_type": "paper_state_recovery_probe",
        "payload": {
            "details": {
                "protocol": "PUBLISH_READBACK_THEN_FRESH_CHECKOUT",
                "financial_state_created": False,
                "account_initialized": False,
                "orders_submitted": 0,
            }
        },
    }
    probe = build_event_batch("probe-before-init", stamp, [probe_event])
    write_batch_atomic(tmp_path, probe)

    initialized_state = {
        "account_id": cycle.ACCOUNT_ID,
        "currency": "USDT",
        "initial_capital": "1",
        "cash": "1",
        "positions": [],
        "status": "INITIALIZED_PAPER_ONLY",
    }
    init_event = {
        "event_id": "init-after-probe",
        "idempotency_key": "init-after-probe",
        "account_id": cycle.ACCOUNT_ID,
        "strategy_id": cycle.STRATEGY_ID,
        "occurred_at_ms": stamp + 1,
        "event_type": "paper_account_initialized",
        "payload": {
            "portfolio_state": initialized_state,
            "details": {
                "account_initialization": {
                    "initial_capital_usdt": "1",
                    "starting_cash_usdt": "1",
                    "account_mode": "FORWARD_PAPER_ONLY",
                    "historical_equity_imported": False,
                    "historical_trades_imported": False,
                }
            },
        },
    }
    init_batch = build_event_batch(
        "init-after-probe",
        stamp + 1,
        [init_event],
        previous_batch_hash=str(probe["batch_hash"]),
    )
    write_batch_atomic(tmp_path, init_batch)

    restored, latest_hash, probe_verified = cycle._load_state(tmp_path)

    assert restored == initialized_state
    assert latest_hash == init_batch["batch_hash"]
    assert probe_verified is True





def test_daily_decision_is_not_consumed_until_history_coverage_passes() -> None:
    cycle = load_cycle_module()
    latest_bar = 1_800_000_000_000
    previous_attempt = latest_bar - 86_400_000

    assert cycle._daily_decision_is_due(False, latest_bar, previous_attempt) is False
    assert cycle._daily_decision_is_due(True, latest_bar, previous_attempt) is True
    assert cycle._daily_decision_is_due(True, latest_bar, latest_bar) is False


def test_blocked_daily_and_retry_execution_statuses_fail_workflow() -> None:
    cycle = load_cycle_module()

    assert cycle._cycle_status_requires_attention(
        "REBALANCE_BLOCKED:ValueError:stale book"
    )
    assert cycle._cycle_status_requires_attention("BLOCKED_INCOMPLETE_MARKET_DATA")
    assert cycle._cycle_status_requires_attention("RETRY_EXECUTION_BLOCKED")
    assert cycle._cycle_status_requires_attention("RETRY_NO_EXECUTABLE_PAIR")
    assert not cycle._cycle_status_requires_attention("PAIR_REBALANCED")
    assert not cycle._cycle_status_requires_attention("MONITORING_ONLY_NO_STRATEGY_DECISIONS")


def test_fill_uses_fresh_exchange_time_after_fetching_the_orderbook() -> None:
    cycle = load_cycle_module()
    cycle_start_ms = 1_700_000_000_000
    book_timestamp_ms = cycle_start_ms + 257_338
    call_order: list[str] = []

    class PublicBookClient:
        def orderbook(self, symbol: str, depth: int) -> dict:
            call_order.append("orderbook")
            return {
                "timestamp_ms": book_timestamp_ms,
                "bids": [{"price": "99.99", "quantity_contracts": "100"}],
                "asks": [{"price": "100.01", "quantity_contracts": "100"}],
            }

        def server_time_ms(self) -> int:
            call_order.append("server_time")
            return book_timestamp_ms + 500

    fill, book = cycle._fill(
        PublicBookClient(),
        {
            "symbol": "TEST_USDT",
            "contract_size": "1",
            "taker_fee_rate": "0.0002",
        },
        "buy",
        Decimal("0.1"),
        cycle_start_ms,
    )

    assert call_order == ["orderbook", "server_time"]
    assert book["timestamp_ms"] == book_timestamp_ms
    assert fill.filled_quantity == Decimal("0.1")


def test_pending_retry_rebalances_existing_positions_and_clears_signal(monkeypatch) -> None:
    cycle = load_cycle_module()
    pending = {
        "daily_bar_timestamp_ms": 1_800_000_000_000,
        "attempt_count": 0,
        "last_attempt_ms": None,
    }
    portfolio = {
        "cash": "9",
        "positions": [
            {
                "instrument_id": 101,
                "symbol": "OLD_USDT",
                "side": "long",
                "quantity": "0.1",
                "entry_price": "100",
                "last_mark_price": "100",
            },
            {
                "instrument_id": 202,
                "symbol": "SHORT_USDT",
                "side": "short",
                "quantity": "0.2",
                "entry_price": "100",
                "last_mark_price": "100",
            },
        ],
        "pending_entry_signal": pending,
    }

    class PublicBookClient:
        def server_time_ms(self) -> int:
            return 1_800_000_001_000

    def fake_try_pair(*args, **kwargs):
        return ([{"instrument_id": 101}], [], ("mexc:101", "mexc:202"))

    def fake_apply(_client, trial, proposed, _instruments, now_ms):
        assert trial["positions"][0]["symbol"] == "OLD_USDT"
        trial["positions"][0]["quantity"] = "0.2"
        return [], [{"action": "INCREASED", "timestamp_ms": now_ms}]

    monkeypatch.setattr(cycle, "_try_pair", fake_try_pair)
    monkeypatch.setattr(cycle, "_apply_selected_pair", fake_apply)
    monkeypatch.setattr(cycle, "portfolio_nav", lambda *_args: Decimal("10"))
    monkeypatch.setattr(
        cycle, "reset_daily_risk_window", lambda *_args, **_kwargs: {"reset": True}
    )

    report = cycle._retry_pending_pair(
        PublicBookClient(),
        portfolio,
        pending,
        None,
        {},
        {},
        {},
        pending["daily_bar_timestamp_ms"],
        pending["daily_bar_timestamp_ms"],
    )

    assert report["status"] == "RETRY_PAIR_REBALANCED"
    assert portfolio["positions"][0]["quantity"] == "0.2"
    assert portfolio["pending_entry_signal"] is None


def test_pending_retry_preserves_positions_and_signal_when_execution_fails(monkeypatch) -> None:
    cycle = load_cycle_module()
    pending = {
        "daily_bar_timestamp_ms": 1_800_000_000_000,
        "attempt_count": 0,
        "last_attempt_ms": None,
    }
    portfolio = {
        "cash": "9",
        "positions": [{
            "instrument_id": 101,
            "symbol": "OLD_USDT",
            "side": "long",
            "quantity": "0.1",
            "last_mark_price": "100",
        }],
        "pending_entry_signal": pending,
    }

    class PublicBookClient:
        def server_time_ms(self) -> int:
            return 1_800_000_001_000

    def fail_try_pair(*args, **kwargs):
        raise cycle.MEXCExecutionUnavailable("stale public depth")

    monkeypatch.setattr(cycle, "_try_pair", fail_try_pair)

    report = cycle._retry_pending_pair(
        PublicBookClient(),
        portfolio,
        pending,
        None,
        {},
        {},
        {},
        pending["daily_bar_timestamp_ms"],
        pending["daily_bar_timestamp_ms"],
    )

    assert report["status"] == "RETRY_EXECUTION_BLOCKED"
    assert portfolio["positions"][0]["quantity"] == "0.1"
    assert portfolio["pending_entry_signal"] is pending
    assert pending["attempt_count"] == 1


def test_portfolio_neutrality_gate_rejects_large_imbalance_and_one_sided_book() -> None:
    cycle = load_cycle_module()

    balanced = {
        "cash": "100",
        "positions": [
            {
                "instrument_id": 1,
                "symbol": "LONG_USDT",
                "side": "long",
                "quantity": "1",
                "entry_price": "50",
                "last_mark_price": "50",
            },
            {
                "instrument_id": 2,
                "symbol": "SHORT_USDT",
                "side": "short",
                "quantity": "1",
                "entry_price": "50",
                "last_mark_price": "50",
            },
        ],
    }
    marks = {
        1: {"mark_price": "50", "timestamp_ms": 1_800_000_000_000},
        2: {"mark_price": "50", "timestamp_ms": 1_800_000_000_000},
    }
    metrics = cycle._require_market_neutrality(balanced, marks)
    assert Decimal(metrics["imbalance_nav_fraction"]) == Decimal("0")

    imbalanced = {
        **balanced,
        "positions": [
            {**balanced["positions"][0], "quantity": "1.1"},
            balanced["positions"][1],
        ],
    }
    try:
        cycle._require_market_neutrality(imbalanced, marks)
    except cycle.MEXCExecutionUnavailable as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("a materially imbalanced portfolio must fail closed")

    one_sided = {**balanced, "positions": balanced["positions"][:1]}
    try:
        cycle._require_market_neutrality(one_sided, marks)
    except cycle.MEXCExecutionUnavailable as exc:
        assert "both a positive long and short" in str(exc)
    else:
        raise AssertionError("a one-sided portfolio must fail closed")


def test_new_active_account_uses_fifty_usdt_seed_and_neutral_sizing_gate() -> None:
    cycle = load_cycle_module()
    assert cycle.INITIAL_CAPITAL == Decimal("50")
    assert cycle.ACCOUNT_ID == "mexc-usdt-forward-50usdt-v3"
    assert cycle.STRATEGY_ID == "trend-quality-daily-cross-sectional-v3-50usdt"
    assert cycle.MAX_NEUTRALITY_IMBALANCE_NAV_FRACTION == Decimal("0.005")



def test_five_minute_neutrality_rebalance_adds_only_the_underweight_leg() -> None:
    from trend_quality.execution import SimulatedFill
    from trend_quality.mexc_portfolio import initial_portfolio_state, open_paper_position

    cycle = load_cycle_module()
    now_ms = 1_800_000_000_000
    long_instrument = {
        "instrument_id": 1760,
        "symbol": "SPOTSTOCK_USDT",
        "category": "crypto",
        "contract_size": "0.01",
        "quantity_step_contracts": "1",
        "min_contracts": "1",
        "max_contracts": "20000",
        "max_leverage": 20,
        "taker_fee_rate": "0",
    }
    short_instrument = {
        "instrument_id": 1899,
        "symbol": "BILL_USDT",
        "category": "crypto",
        "contract_size": "100",
        "quantity_step_contracts": "1",
        "min_contracts": "1",
        "max_contracts": "2000",
        "max_leverage": 20,
        "taker_fee_rate": "0",
    }

    def fill(side: str, quantity: str, price: str) -> SimulatedFill:
        qty = Decimal(quantity)
        px = Decimal(price)
        return SimulatedFill(
            side=side,
            requested_quantity=qty,
            filled_quantity=qty,
            average_price=px,
            reference_price=px,
            notional=qty * px,
            fee=Decimal("0"),
            shortfall=Decimal("0"),
            shortfall_bps=Decimal("0"),
            complete=True,
            levels_consumed=1,
        )

    state = initial_portfolio_state(Decimal("50"))
    long_ticker = {"mark_price": "600.54", "mid_price": "600.54"}
    short_ticker = {"mark_price": "0.003906", "mid_price": "0.003906"}
    open_paper_position(
        state, long_instrument, long_ticker, "long", Decimal("1"),
        fill("buy", "0.08", "600.54"), now_ms - 86_400_000,
    )
    open_paper_position(
        state, short_instrument, short_ticker, "short", Decimal("0.0002"),
        fill("sell", "12000", "0.003906"), now_ms - 86_400_000,
    )

    class Store:
        def load_candles(self, instrument_id: int, *, start_timestamp_ms: int):
            assert instrument_id == 1899
            return [
                {
                    "timestamp_ms": now_ms - (40 - day) * 86_400_000,
                    "high": "0.0040",
                    "low": "0.0038",
                    "close": "0.0039",
                }
                for day in range(40)
            ]

    class PublicBookClient:
        def server_time_ms(self) -> int:
            return now_ms + 100

        def orderbook(self, symbol: str, depth: int):
            bid = "600.53" if symbol == "SPOTSTOCK_USDT" else "0.003905"
            ask = "600.55" if symbol == "SPOTSTOCK_USDT" else "0.003907"
            return {
                "timestamp_ms": now_ms,
                "bids": [{"price": bid, "quantity_contracts": "100000"}],
                "asks": [{"price": ask, "quantity_contracts": "100000"}],
            }

        def tickers(self):
            return [
                {
                    "symbol": "SPOTSTOCK_USDT",
                    "timestamp_ms": now_ms + 100,
                    "mark_price": "600.54",
                    "mid_price": "600.54",
                    "last_price": "600.54",
                },
                {
                    "symbol": "BILL_USDT",
                    "timestamp_ms": now_ms + 100,
                    "mark_price": "0.003906",
                    "mid_price": "0.003906",
                    "last_price": "0.003906",
                },
            ]

    client = PublicBookClient()
    before = cycle._portfolio_neutrality_metrics(
        state,
        {
            1760: {"mark_price": "600.54"},
            1899: {"mark_price": "0.003906"},
        },
    )
    assert Decimal(before["imbalance_nav_fraction"]) > Decimal("0.005")

    result = cycle._rebalance_existing_pair(
        client,
        state,
        [long_instrument, short_instrument],
        {
            1760: {"mark_price": "600.54", "mid_price": "600.54"},
            1899: {"mark_price": "0.003906", "mid_price": "0.003906"},
        },
        Store(),
        now_ms,
    )

    assert result["status"] == "REBALANCED"
    assert len(result["actions"]) == 1
    assert result["actions"][0]["symbol"] == "BILL_USDT"
    assert result["actions"][0]["action"] == "INCREASED"
    assert Decimal(state["positions"][1]["quantity"]) == Decimal("12300")
    assert Decimal(result["portfolio_neutrality"]["imbalance_nav_fraction"]) <= Decimal("0.005")


def test_a_single_leg_stop_flattens_the_entire_market_neutral_pair() -> None:
    cycle = load_cycle_module()
    now_ms = 1_800_000_000_000
    state = {
        "cash": "100",
        "realized_gross_pnl": "0",
        "fees_paid": "0",
        "closed_trade_net_pnls": [],
        "positions": [
            {
                "instrument_id": 1,
                "symbol": "LONG_USDT",
                "side": "long",
                "quantity": "1",
                "entry_price": "100",
                "entry_fee": "0",
                "entry_timestamp_ms": now_ms - 1,
                "last_mark_price": "100",
                "stop_price": "100",
            },
            {
                "instrument_id": 2,
                "symbol": "SHORT_USDT",
                "side": "short",
                "quantity": "1",
                "entry_price": "100",
                "entry_fee": "0",
                "entry_timestamp_ms": now_ms - 1,
                "last_mark_price": "100",
                "stop_price": "110",
            },
        ],
    }
    instruments = {
        1: {
            "instrument_id": 1,
            "symbol": "LONG_USDT",
            "contract_size": "1",
            "taker_fee_rate": "0",
        },
        2: {
            "instrument_id": 2,
            "symbol": "SHORT_USDT",
            "contract_size": "1",
            "taker_fee_rate": "0",
        },
    }

    class PublicBookClient:
        def server_time_ms(self) -> int:
            return now_ms + 10

        def orderbook(self, symbol: str, depth: int):
            return {
                "timestamp_ms": now_ms,
                "bids": [{"price": "99.99", "quantity_contracts": "100"}],
                "asks": [{"price": "100.01", "quantity_contracts": "100"}],
            }

    exits, trailing = cycle._process_stops(
        PublicBookClient(),
        state,
        instruments,
        {
            1: {"last_price": "99", "mark_price": "99"},
            2: {"last_price": "100", "mark_price": "100"},
        },
        {},
        now_ms - 86_400_000,
        now_ms,
    )

    assert trailing == []
    assert len(exits) == 2
    assert state["positions"] == []
    assert exits[0]["pair_stop_triggered_by"] == ["LONG_USDT"]



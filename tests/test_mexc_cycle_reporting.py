from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

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



def test_current_position_marks_use_all_market_server_timestamp_not_trade_time() -> None:
    cycle = load_cycle_module()
    now_ms = 1_800_000_000_000

    class PublicTickerClient:
        def tickers(self):
            return [
                {
                    "symbol": "VSTOCK_USDT",
                    "timestamp_ms": now_ms + 356,
                    "mark_price": "600.54",
                    "last_price": "600.50",
                },
                {
                    "symbol": "BILL_USDT",
                    "timestamp_ms": now_ms + 356,
                    "mark_price": "0.003906",
                    "last_price": "0.003905",
                },
            ]

        def ticker(self, _symbol):
            raise AssertionError("snapshot must use server-timestamped all-market feed")

    positions = [
        {"instrument_id": 101, "symbol": "VSTOCK_USDT"},
        {"instrument_id": 202, "symbol": "BILL_USDT"},
    ]
    mapped, missing, errors = cycle._current_position_tickers(
        PublicTickerClient(), positions, now_ms
    )

    assert set(mapped) == {101, 202}
    assert mapped[202]["mark_price"] == "0.003906"
    assert missing == []
    assert errors == []


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
    # REST ping and WebSocket server clocks can differ by a few hundred ms.
    assert cycle._stale_or_missing_position_marks(
        positions,
        {7: {"timestamp_ms": 1_100_356, "mark_price": "10"}},
        1_100_000,
    ) == []
    # A materially future-dated mark still fails closed.
    assert cycle._stale_or_missing_position_marks(
        positions,
        {7: {"timestamp_ms": 1_106_000, "mark_price": "10"}},
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

    assert "ACTIVE PAPER ACCOUNT — MEXC $100 USDT PAPER ONLY" in mexc
    assert "▶ MANUAL PAPER RUN — MEXC $100 USDT" in mexc
    assert "I_CONFIRM_ACTIVE_100_USDT_PAPER_ONLY" in mexc
    assert "group: paper-state-branch-single-writer" in mexc
    assert "cancel-in-progress: false" in mexc
    assert "  push:" not in mexc
    assert '- cron: "*/5 * * * *"' in mexc
    assert '- cron: "1 0 * * *"' in mexc
    assert "group: paper-state-branch-single-writer" in preflight
    assert "cancel-in-progress: false" in preflight
    assert "PAPER_STATE_WRITE_ENABLED: ${{ vars.PAPER_STATE_WRITE_ENABLED || 'true' }}" in mexc
    assert "STATE_PROTECTION_TOKEN" not in mexc
    assert "STATE_PROTECTION_TOKEN" not in cycle_source
    assert "def _state_branch_protection" not in cycle_source

    assert not retired_polymarket.exists()
    assert "DIAGNOSTIC ONLY — READ-ONLY MEXC PREFLIGHT" in preflight
    assert "AUTOMATIC READ-ONLY MEXC PREFLIGHT" in preflight
    assert "on:\n  push:\n    branches: [main]" in preflight
    assert "\n  workflow_dispatch:" in preflight
    for trigger_path in (
        ".github/workflows/mexc-public-preflight.yml",
        "scripts/mexc_public_preflight.py",
        "src/trend_quality/mexc_api.py",
        "pyproject.toml",
    ):
        assert f'      - "{trigger_path}"' in preflight
    assert "schedule:" not in preflight
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






def test_bootstrap_stops_after_first_http_403_instead_of_hammering_endpoints() -> None:
    from trend_quality.mexc_api import MEXCForbiddenError

    cycle = load_cycle_module()

    class FakeStore:
        manifest = {
            "instruments": {
                "1": {
                    "bootstrap_complete": False,
                    "bootstrap_attempts": 0,
                    "first_seen_at_ms": 1,
                },
                "2": {
                    "bootstrap_complete": False,
                    "bootstrap_attempts": 0,
                    "first_seen_at_ms": 2,
                },
            }
        }

        def load_all_candles(self):
            return {}

    class ForbiddenClient:
        calls: list[str] = []

        def candles(self, symbol, **_kwargs):
            self.calls.append(symbol)
            raise MEXCForbiddenError(
                "MEXC returned HTTP 403 for /api/v1/contract/kline/" + symbol
            )

    client = ForbiddenClient()
    instruments = [
        {"instrument_id": 1, "symbol": "AAA_USDT", "create_time_ms": 1},
        {"instrument_id": 2, "symbol": "BBB_USDT", "create_time_ms": 1},
    ]
    with pytest.raises(MEXCForbiddenError, match="AAA_USDT"):
        cycle._bootstrap_or_increment(
            client,
            FakeStore(),
            instruments,
            server_ms=1_800_000_000_000,
            latest_completed_bar_ms=1_799_913_600_000,
            batch_size=2,
        )
    assert client.calls == ["AAA_USDT"]



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


def test_pending_retry_performs_full_book_rebuild_and_clears_signal(monkeypatch) -> None:
    cycle = load_cycle_module()
    pending = {
        "daily_bar_timestamp_ms": 1_800_000_000_000,
        "attempt_count": 0,
        "last_attempt_ms": None,
    }
    old_positions = [
        {
            "instrument_id": 101,
            "symbol": "OLD_LONG_USDT",
            "side": "long",
            "quantity": "0.1",
            "entry_price": "100",
            "last_mark_price": "100",
        },
        {
            "instrument_id": 202,
            "symbol": "OLD_SHORT_USDT",
            "side": "short",
            "quantity": "0.2",
            "entry_price": "100",
            "last_mark_price": "100",
        },
    ]
    portfolio = {
        "cash": "9",
        "positions": old_positions,
        "pending_entry_signal": pending,
    }
    rebuilt_positions = [
        {
            "instrument_id": 303,
            "symbol": "NEW_LONG_USDT",
            "side": "long",
            "quantity": "0.08",
            "entry_price": "100",
            "last_mark_price": "100",
        },
        {
            "instrument_id": 404,
            "symbol": "NEW_SHORT_USDT",
            "side": "short",
            "quantity": "12800",
            "entry_price": "0.003906",
            "last_mark_price": "0.003906",
        },
    ]
    rebuilt_state = {
        **portfolio,
        "positions": rebuilt_positions,
        "pending_entry_signal": pending,
    }
    closes = [
        {"action": "CLOSED", "symbol": "OLD_LONG_USDT", "exit_price": "99"},
        {"action": "CLOSED", "symbol": "OLD_SHORT_USDT", "exit_price": "101"},
    ]
    opens = [
        {"action": "OPENED", "symbol": "NEW_LONG_USDT", "entry_price": "100"},
        {"action": "OPENED", "symbol": "NEW_SHORT_USDT", "entry_price": "0.003906"},
    ]
    call_args = {}

    def fake_rebuild(
        _client,
        state,
        _rankings,
        _history,
        _tickers,
        _instruments,
        now_ms,
        *,
        max_pairs,
    ):
        assert state is portfolio
        call_args["now_ms"] = now_ms
        call_args["max_pairs"] = max_pairs
        return {
            "status": "PAIR_REBUILT",
            "portfolio_state": rebuilt_state,
            "execution_timestamp_ms": now_ms + 500,
            "pair": ("mexc:303", "mexc:404"),
            "candidate_fill_estimates": [],
            "close_actions": closes,
            "open_actions": opens,
            "portfolio_neutrality": {
                "long_notional_usdt": "48",
                "short_notional_usdt": "49.9968",
                "imbalance_usdt": "1.9968",
                "imbalance_nav_fraction": "0.039936",
            },
        }

    monkeypatch.setattr(cycle, "_rebuild_fresh_portfolio", fake_rebuild)
    monkeypatch.setattr(
        cycle, "portfolio_nav", lambda *_args: Decimal("50")
    )
    monkeypatch.setattr(
        cycle,
        "reset_daily_risk_window",
        lambda *_args, **_kwargs: {"reset": True},
    )
    report = cycle._retry_pending_pair(
        object(),
        portfolio,
        pending,
        None,
        {},
        {},
        {},
        pending["daily_bar_timestamp_ms"],
        pending["daily_bar_timestamp_ms"],
    )

    assert report["status"] == "RETRY_PAIR_REBUILT"
    assert call_args == {
        "now_ms": pending["daily_bar_timestamp_ms"],
        "max_pairs": 5,
    }
    assert portfolio["positions"] == rebuilt_positions
    assert portfolio["pending_entry_signal"] is None
    assert report["close_actions"] == closes
    assert report["open_actions"] == opens
    assert report["fills"] == closes + opens
    assert report["risk_window_reset"] == {"reset": True}


def test_pending_retry_preserves_book_and_signal_when_full_rebuild_fails(
    monkeypatch,
) -> None:
    cycle = load_cycle_module()
    pending = {
        "daily_bar_timestamp_ms": 1_800_000_000_000,
        "attempt_count": 0,
        "last_attempt_ms": None,
    }
    old_positions = [
        {
            "instrument_id": 101,
            "symbol": "OLD_LONG_USDT",
            "side": "long",
            "quantity": "0.1",
            "last_mark_price": "100",
        },
        {
            "instrument_id": 202,
            "symbol": "OLD_SHORT_USDT",
            "side": "short",
            "quantity": "0.2",
            "last_mark_price": "100",
        },
    ]
    portfolio = {
        "cash": "9",
        "positions": old_positions,
        "pending_entry_signal": pending,
    }

    def fail_rebuild(*_args, **_kwargs):
        raise cycle.MEXCExecutionUnavailable("stale public depth")

    monkeypatch.setattr(cycle, "_rebuild_fresh_portfolio", fail_rebuild)
    report = cycle._retry_pending_pair(
        object(),
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
    assert portfolio["positions"] == old_positions
    assert portfolio["pending_entry_signal"] is pending
    assert pending["attempt_count"] == 1


def test_two_sided_portfolio_reports_imbalance_without_percentage_gate() -> None:
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
    metrics = cycle._validate_two_sided_portfolio(balanced, marks)
    assert Decimal(metrics["imbalance_nav_fraction"]) == Decimal("0")

    imbalanced = {
        **balanced,
        "positions": [
            {**balanced["positions"][0], "quantity": "1.1"},
            balanced["positions"][1],
        ],
    }
    imbalanced_metrics = cycle._validate_two_sided_portfolio(imbalanced, marks)
    assert Decimal(imbalanced_metrics["imbalance_usdt"]) > 0
    assert Decimal(imbalanced_metrics["imbalance_nav_fraction"]) > Decimal("0.005")

    one_sided = {**balanced, "positions": balanced["positions"][:1]}
    with pytest.raises(
        cycle.MEXCExecutionUnavailable,
        match="exactly one long and one short",
    ):
        cycle._validate_two_sided_portfolio(one_sided, marks)



def test_active_account_uses_hundred_usdt_seed_without_neutrality_threshold() -> None:
    cycle = load_cycle_module()
    assert cycle.INITIAL_CAPITAL == Decimal("100")
    assert cycle.ACCOUNT_ID == "mexc-usdt-forward-100usdt-v4"
    assert cycle.STRATEGY_ID == "trend-quality-daily-cross-sectional-v4-100usdt"
    assert not hasattr(cycle, "MAX_NEUTRALITY_IMBALANCE_NAV_FRACTION")
    assert not hasattr(cycle, "_rebalance_existing_pair")
    assert hasattr(cycle, "_validate_two_sided_portfolio")


def test_five_minute_snapshot_monitors_risk_without_portfolio_construction() -> None:
    import inspect

    cycle = load_cycle_module()
    snapshot_source = inspect.getsource(cycle._snapshot_only_cycle)
    for forbidden in (
        "_try_pair(", "_rebuild_fresh_portfolio(", "_apply_selected_pair(",
        "size_mexc_leg(", "_validate_two_sided_portfolio(",
    ):
        assert forbidden not in snapshot_source
    assert "_current_position_tickers(" in snapshot_source
    assert "_process_funding(" in snapshot_source
    assert "append_equity_snapshot(" in snapshot_source
    assert "_close_all(" in snapshot_source




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



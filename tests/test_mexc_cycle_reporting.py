from __future__ import annotations

import importlib.util
import sys
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


def test_state_branch_writers_share_one_non_cancelling_concurrency_group() -> None:
    root = Path(__file__).resolve().parents[1]
    mexc = (root / ".github" / "workflows" / "mexc-paper-cycle.yml").read_text()
    polymarket = (
        root / ".github" / "workflows" / "polymarket-paper-cycle.yml"
    ).read_text()
    cycle_source = (root / "scripts" / "mexc_paper_cycle.py").read_text()

    for workflow in (mexc, polymarket):
        assert "group: paper-state-branch-single-writer" in workflow
        assert "cancel-in-progress: false" in workflow
    assert "PAPER_STATE_WRITE_ENABLED: ${{ vars.PAPER_STATE_WRITE_ENABLED || 'true' }}" in mexc
    assert "STATE_PROTECTION_TOKEN" not in mexc
    assert "STATE_PROTECTION_TOKEN" not in cycle_source
    assert "def _state_branch_protection" not in cycle_source


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

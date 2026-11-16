from __future__ import annotations

import json

import pytest

from trend_quality.event_journal import (
    EventJournalError,
    build_event_batch,
    read_batch,
    verify_event_batch,
    write_batch_atomic,
)


def _event(event_id: str = "evt-1") -> dict[str, object]:
    return {
        "event_id": event_id,
        "idempotency_key": f"idem-{event_id}",
        "account_id": "forward-paper",
        "strategy_id": "q-baseline",
        "occurred_at_ms": 1794787200000,
        "event_type": "ACCOUNT_INITIALIZED",
        "payload": {"initial_capital": "100.00", "currency": "USDT"},
    }


def test_batch_hash_and_event_chain_verify() -> None:
    batch = build_event_batch("run-1", 1794787201000, [_event()])
    assert verify_event_batch(batch)
    batch["events"][0]["payload"]["initial_capital"] = "999.00"  # type: ignore[index]
    assert not verify_event_batch(batch)


def test_binary_float_rejected_for_financial_ledger() -> None:
    event = _event()
    event["payload"] = {"amount": 1.25}
    with pytest.raises(EventJournalError, match="Binary float"):
        build_event_batch("run-2", 1794787201000, [event])


def test_duplicate_event_ids_and_idempotency_keys_rejected() -> None:
    with pytest.raises(EventJournalError, match="Duplicate"):
        build_event_batch("run-3", 1794787201000, [_event(), _event("evt-1")])


def test_atomic_write_and_identical_retry_are_idempotent(tmp_path) -> None:
    batch = build_event_batch("run-4", 1794787201000, [_event()])
    path = write_batch_atomic(tmp_path, batch)
    assert read_batch(path) == batch
    assert write_batch_atomic(tmp_path, batch) == path
    assert json.loads(path.read_text())["batch_hash"] == batch["batch_hash"]


def test_run_id_collision_with_different_payload_is_rejected(tmp_path) -> None:
    first = build_event_batch("run-5", 1794787201000, [_event()])
    second = build_event_batch("run-5", 1794787201001, [_event()])
    write_batch_atomic(tmp_path, first)
    with pytest.raises(EventJournalError, match="different event content"):
        write_batch_atomic(tmp_path, second)

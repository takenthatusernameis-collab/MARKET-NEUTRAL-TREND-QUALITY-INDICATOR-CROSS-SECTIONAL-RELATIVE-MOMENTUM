from __future__ import annotations

from trend_quality.event_journal import build_event_batch
from trend_quality.sqlite_store import SQLiteEventStore, SQLiteEventStoreError


def _event(
    event_id: str,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "idempotency_key": idempotency_key or f"idem-{event_id}",
        "account_id": "forward-paper",
        "strategy_id": "q-baseline",
        "occurred_at_ms": 1794787200000,
        "event_type": "VALUATION",
        "payload": {"nav": "100.00", "currency": "USDT"},
    }


def test_apply_batch_is_atomic_idempotent_and_verifiable() -> None:
    first = build_event_batch("run-1", 1794787201000, [_event("event-1")])
    second = build_event_batch(
        "run-2",
        1794787202000,
        [_event("event-2")],
        previous_batch_hash=first["batch_hash"],
    )

    with SQLiteEventStore(":memory:") as store:
        assert store.apply_batch(first) is True
        assert store.apply_batch(first) is False
        assert store.apply_batch(second) is True
        assert store.batch_count() == 2
        assert store.event_count() == 2
        assert store.latest_batch_hash() == second["batch_hash"]
        assert store.integrity_check()["ok"] is True


def test_out_of_order_batch_is_rejected_without_partial_insert() -> None:
    first = build_event_batch("run-first", 1794787201000, [_event("event-first")])
    second = build_event_batch(
        "run-second",
        1794787202000,
        [_event("event-second")],
        previous_batch_hash=first["batch_hash"],
    )

    with SQLiteEventStore(":memory:") as store:
        try:
            store.apply_batch(second)
        except SQLiteEventStoreError as exc:
            assert "chain mismatch" in str(exc)
        else:
            raise AssertionError("out-of-order batch must fail")
        assert store.batch_count() == 0
        assert store.event_count() == 0


def test_cross_batch_idempotency_conflict_rolls_back_whole_batch() -> None:
    first = build_event_batch("run-a", 1794787201000, [_event("event-a", "shared-key")])
    second = build_event_batch(
        "run-b",
        1794787202000,
        [_event("event-b", "shared-key")],
        previous_batch_hash=first["batch_hash"],
    )

    with SQLiteEventStore(":memory:") as store:
        assert store.apply_batch(first)
        try:
            store.apply_batch(second)
        except SQLiteEventStoreError as exc:
            assert "Atomic event batch" in str(exc)
        else:
            raise AssertionError("cross-batch duplicate idempotency key must fail")
        assert store.batch_count() == 1
        assert store.event_count() == 1
        assert store.integrity_check()["ok"] is True


def test_run_id_collision_with_different_hash_is_rejected() -> None:
    first = build_event_batch("same-run", 1794787201000, [_event("event-a")])
    different = build_event_batch("same-run", 1794787201001, [_event("event-b")])
    with SQLiteEventStore(":memory:") as store:
        assert store.apply_batch(first)
        try:
            store.apply_batch(different)
        except SQLiteEventStoreError as exc:
            assert "different batch hash" in str(exc)
        else:
            raise AssertionError("same run ID with different hash must fail")
        assert store.batch_count() == 1
        assert store.integrity_check()["ok"] is True


def test_empty_checkpoint_batch_is_valid_and_linked() -> None:
    first = build_event_batch("empty-checkpoint", 1794787201000, [])
    with SQLiteEventStore(":memory:") as store:
        assert store.apply_batch(first)
        assert store.batch_count() == 1
        assert store.event_count() == 0
        assert store.integrity_check()["ok"] is True

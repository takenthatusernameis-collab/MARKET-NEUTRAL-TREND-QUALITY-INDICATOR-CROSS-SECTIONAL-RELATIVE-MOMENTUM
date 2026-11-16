"""Immutable, hash-chained per-run event batches.

This module handles local atomic batch files. Publishing a completed batch to
the dedicated Git state branch is a separate workflow responsibility.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class EventJournalError(RuntimeError):
    pass


def _reject_floats(value: Any, path: str = "event") -> None:
    if isinstance(value, float):
        raise EventJournalError(f"Binary float is not allowed in durable events: {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_floats(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_floats(child, f"{path}[{index}]")


def canonical_json(value: Any) -> str:
    _reject_floats(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _event_hash(event_without_hash: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(event_without_hash).encode("utf-8")).hexdigest()


def build_event_batch(
    run_id: str,
    created_at_ms: int,
    events: Iterable[dict[str, Any]],
    previous_batch_hash: str | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", run_id):
        raise EventJournalError("run_id contains unsupported characters")
    if created_at_ms <= 0:
        raise EventJournalError("created_at_ms must be positive")
    if previous_batch_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", previous_batch_hash):
        raise EventJournalError("previous_batch_hash must be a SHA-256 hex digest or null")

    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    chained: list[dict[str, Any]] = []
    previous_event_hash = previous_batch_hash
    for original in events:
        event = dict(original)
        required = {
            "event_id",
            "idempotency_key",
            "account_id",
            "strategy_id",
            "occurred_at_ms",
            "event_type",
            "payload",
        }
        missing = required - event.keys()
        if missing:
            raise EventJournalError(f"Event missing required keys: {sorted(missing)}")
        event_id = str(event["event_id"])
        idempotency_key = str(event["idempotency_key"])
        if not event_id or event_id in seen_ids:
            raise EventJournalError("Duplicate or empty event_id")
        if not idempotency_key or idempotency_key in seen_keys:
            raise EventJournalError("Duplicate or empty idempotency_key")
        if int(event["occurred_at_ms"]) <= 0:
            raise EventJournalError("occurred_at_ms must be positive")
        seen_ids.add(event_id)
        seen_keys.add(idempotency_key)
        event.pop("event_hash", None)
        event["previous_event_hash"] = previous_event_hash
        _reject_floats(event)
        event["event_hash"] = _event_hash(event)
        previous_event_hash = event["event_hash"]
        chained.append(event)

    batch: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at_ms": created_at_ms,
        "previous_batch_hash": previous_batch_hash,
        "events": chained,
    }
    batch["batch_hash"] = hashlib.sha256(canonical_json(batch).encode("utf-8")).hexdigest()
    return batch


def verify_event_batch(batch: dict[str, Any]) -> bool:
    try:
        if batch.get("schema_version") != 1 or not isinstance(batch.get("events"), list):
            return False
        expected_previous = batch.get("previous_batch_hash")
        if expected_previous is not None and not re.fullmatch(
            r"[0-9a-f]{64}", str(expected_previous)
        ):
            return False
        events = batch["events"]
        prior = expected_previous
        event_ids: set[str] = set()
        idempotency: set[str] = set()
        for event in events:
            if event.get("previous_event_hash") != prior:
                return False
            event_hash = event.get("event_hash")
            without_hash = dict(event)
            without_hash.pop("event_hash", None)
            if _event_hash(without_hash) != event_hash:
                return False
            if event.get("event_id") in event_ids or event.get("idempotency_key") in idempotency:
                return False
            event_ids.add(event.get("event_id"))
            idempotency.add(event.get("idempotency_key"))
            prior = event_hash
        without_batch_hash = dict(batch)
        actual_hash = without_batch_hash.pop("batch_hash", None)
        calculated_hash = hashlib.sha256(
            canonical_json(without_batch_hash).encode("utf-8")
        ).hexdigest()
        return calculated_hash == actual_hash
    except (EventJournalError, TypeError, ValueError, KeyError):
        return False


def write_batch_atomic(root: str | Path, batch: dict[str, Any]) -> Path:
    """Atomically create a new batch file; never overwrite another run."""
    if not verify_event_batch(batch):
        raise EventJournalError("Refusing to persist an invalid event batch")
    created_at_ms = int(batch["created_at_ms"])
    import datetime

    date = datetime.datetime.fromtimestamp(created_at_ms / 1000, tz=datetime.UTC)
    directory = Path(root) / "events" / date.strftime("%Y") / date.strftime("%m")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{batch['run_id']}.json"
    payload = canonical_json(batch) + "\n"

    if destination.exists():
        if destination.read_text(encoding="utf-8") == payload:
            return destination
        raise EventJournalError("run_id already exists with different event content")

    fd, temporary_name = tempfile.mkstemp(prefix=".event-batch-", dir=directory)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, destination)
        except FileExistsError:
            if destination.read_text(encoding="utf-8") != payload:
                raise EventJournalError("Concurrent run_id collision") from None
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination


def read_batch(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not verify_event_batch(data):
        raise EventJournalError(f"Event batch integrity check failed: {path}")
    return data

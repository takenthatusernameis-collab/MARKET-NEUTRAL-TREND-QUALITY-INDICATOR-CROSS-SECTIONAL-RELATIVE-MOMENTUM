"""Transactional SQLite projection for immutable event batches.

The Git state-branch publisher is deliberately separate. A batch is durable
across runner loss only after its immutable file is committed to that branch.
This module provides a rebuildable local projection and consistency checks.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .event_journal import EventJournalError, verify_event_batch


class SQLiteEventStoreError(RuntimeError):
    """Raised when projection application or integrity verification fails."""


class SQLiteEventStore:
    """SQLite projection with idempotent, append-only batch application.

    One connection is kept open so the store also works with :memory: databases.
    Use as a context manager or call close() explicitly.
    """

    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._connection = sqlite3.connect(
                self.database_path,
                timeout=30.0,
                isolation_level=None,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA busy_timeout=30000")
            if self.database_path != ":memory:":
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA synchronous=FULL")
            self._initialize_schema()
        except sqlite3.Error as exc:
            raise SQLiteEventStoreError(f"Unable to initialize SQLite store: {exc}") from exc

    def _initialize_schema(self) -> None:
        current_version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if current_version > self.SCHEMA_VERSION:
            raise SQLiteEventStoreError(
                f"Database schema {current_version} is newer than supported "
                f"schema {self.SCHEMA_VERSION}"
            )
        if current_version == self.SCHEMA_VERSION:
            return
        if current_version not in (0,):
            raise SQLiteEventStoreError(f"No migration path from schema {current_version}")

        self._connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS applied_batches (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                batch_hash TEXT NOT NULL UNIQUE,
                previous_batch_hash TEXT,
                created_at_ms INTEGER NOT NULL,
                event_count INTEGER NOT NULL CHECK(event_count >= 0)
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_hash TEXT NOT NULL UNIQUE,
                event_id TEXT NOT NULL UNIQUE,
                idempotency_key TEXT NOT NULL UNIQUE,
                batch_hash TEXT NOT NULL REFERENCES applied_batches(batch_hash),
                batch_sequence INTEGER NOT NULL CHECK(batch_sequence >= 0),
                account_id TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                occurred_at_ms INTEGER NOT NULL CHECK(occurred_at_ms > 0),
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE(batch_hash, batch_sequence)
            );
            CREATE INDEX IF NOT EXISTS idx_events_account_time
                ON events(account_id, occurred_at_ms, sequence);
            CREATE INDEX IF NOT EXISTS idx_events_type_time
                ON events(event_type, occurred_at_ms, sequence);
            PRAGMA user_version=1;
            COMMIT;
            """
        )

    def apply_batch(self, batch: dict[str, Any]) -> bool:
        """Apply a verified next batch; return False for an identical retry.

        Batches must be supplied in their previous_batch_hash chain order.
        Any failed insert rolls back the entire batch.
        """
        if not verify_event_batch(batch):
            raise SQLiteEventStoreError("Refusing to apply an invalid event batch")

        run_id = str(batch["run_id"])
        batch_hash = str(batch["batch_hash"])
        previous_hash = batch.get("previous_batch_hash")
        events = batch["events"]

        try:
            self._connection.execute("BEGIN IMMEDIATE")
            existing = self._connection.execute(
                "SELECT batch_hash FROM applied_batches WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if existing is not None:
                if existing["batch_hash"] == batch_hash:
                    self._connection.execute("ROLLBACK")
                    return False
                raise SQLiteEventStoreError(
                    f"run_id {run_id!r} already exists with a different batch hash"
                )

            latest = self._connection.execute(
                "SELECT batch_hash FROM applied_batches ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            expected_previous = None if latest is None else str(latest["batch_hash"])
            if previous_hash != expected_previous:
                raise SQLiteEventStoreError(
                    "Event batch chain mismatch: "
                    f"expected previous hash {expected_previous!r}, got {previous_hash!r}"
                )

            self._connection.execute(
                """
                INSERT INTO applied_batches
                    (run_id, batch_hash, previous_batch_hash, created_at_ms, event_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    batch_hash,
                    previous_hash,
                    int(batch["created_at_ms"]),
                    len(events),
                ),
            )
            for index, event in enumerate(events):
                payload_json = json.dumps(
                    event["payload"],
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                )
                self._connection.execute(
                    """
                    INSERT INTO events (
                        event_hash, event_id, idempotency_key, batch_hash,
                        batch_sequence, account_id, strategy_id, occurred_at_ms,
                        event_type, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["event_hash"],
                        event["event_id"],
                        event["idempotency_key"],
                        batch_hash,
                        index,
                        event["account_id"],
                        event["strategy_id"],
                        int(event["occurred_at_ms"]),
                        event["event_type"],
                        payload_json,
                    ),
                )
            self._connection.execute("COMMIT")
            return True
        except SQLiteEventStoreError:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise
        except (sqlite3.Error, EventJournalError, TypeError, ValueError) as exc:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise SQLiteEventStoreError(f"Atomic event batch application failed: {exc}") from exc

    def event_count(self, account_id: str | None = None) -> int:
        if account_id is None:
            row = self._connection.execute("SELECT COUNT(*) AS n FROM events").fetchone()
        else:
            row = self._connection.execute(
                "SELECT COUNT(*) AS n FROM events WHERE account_id=?",
                (account_id,),
            ).fetchone()
        return int(row["n"])

    def batch_count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS n FROM applied_batches").fetchone()
        return int(row["n"])

    def latest_batch_hash(self) -> str | None:
        row = self._connection.execute(
            "SELECT batch_hash FROM applied_batches ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return None if row is None else str(row["batch_hash"])

    def events(self, account_id: str | None = None) -> list[dict[str, Any]]:
        """Return ledger events in committed batch order and batch event order."""
        if account_id is None:
            rows = self._connection.execute(
                """
                SELECT * FROM events
                ORDER BY sequence ASC
                """
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT * FROM events WHERE account_id=?
                ORDER BY sequence ASC
                """,
                (account_id,),
            ).fetchall()
        return [
            {
                "event_hash": str(row["event_hash"]),
                "event_id": str(row["event_id"]),
                "idempotency_key": str(row["idempotency_key"]),
                "batch_hash": str(row["batch_hash"]),
                "batch_sequence": int(row["batch_sequence"]),
                "account_id": str(row["account_id"]),
                "strategy_id": str(row["strategy_id"]),
                "occurred_at_ms": int(row["occurred_at_ms"]),
                "event_type": str(row["event_type"]),
                "payload": json.loads(str(row["payload_json"])),
            }
            for row in rows
        ]

    def integrity_check(self) -> dict[str, Any]:
        """Verify SQLite, each reconstructed batch hash and the cross-batch chain."""
        sqlite_result = str(
            self._connection.execute("PRAGMA integrity_check").fetchone()[0]
        )
        foreign_key_errors = self._connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        rows = self._connection.execute(
            "SELECT * FROM applied_batches ORDER BY sequence ASC"
        ).fetchall()
        expected_previous: str | None = None
        batches_valid = True
        event_counts_valid = True
        for batch_row in rows:
            batch_hash = str(batch_row["batch_hash"])
            if batch_row["previous_batch_hash"] != expected_previous:
                batches_valid = False
            event_rows = self._connection.execute(
                """
                SELECT * FROM events
                WHERE batch_hash=?
                ORDER BY batch_sequence ASC
                """,
                (batch_hash,),
            ).fetchall()
            if len(event_rows) != int(batch_row["event_count"]):
                event_counts_valid = False
            event_payloads = []
            for event_row in event_rows:
                event_payloads.append(
                    {
                        "event_id": str(event_row["event_id"]),
                        "idempotency_key": str(event_row["idempotency_key"]),
                        "account_id": str(event_row["account_id"]),
                        "strategy_id": str(event_row["strategy_id"]),
                        "occurred_at_ms": int(event_row["occurred_at_ms"]),
                        "event_type": str(event_row["event_type"]),
                        "payload": json.loads(str(event_row["payload_json"])),
                        "previous_event_hash": (
                            None
                            if event_row["batch_sequence"] == 0
                            and batch_row["previous_batch_hash"] is None
                            else None
                        ),
                        "event_hash": str(event_row["event_hash"]),
                    }
                )
            # Reconstruct previous_event_hash from the hash chain, anchored to
            # the previous batch hash for event zero.
            prior_event_hash = batch_row["previous_batch_hash"]
            for event in event_payloads:
                event["previous_event_hash"] = prior_event_hash
                prior_event_hash = event["event_hash"]
            reconstructed = {
                "schema_version": 1,
                "run_id": str(batch_row["run_id"]),
                "created_at_ms": int(batch_row["created_at_ms"]),
                "previous_batch_hash": batch_row["previous_batch_hash"],
                "events": event_payloads,
                "batch_hash": batch_hash,
            }
            if not verify_event_batch(reconstructed):
                batches_valid = False
            expected_previous = batch_hash

        return {
            "sqlite_integrity": sqlite_result,
            "foreign_key_errors": len(foreign_key_errors),
            "batch_chain_valid": batches_valid,
            "event_counts_valid": event_counts_valid,
            "batch_count": len(rows),
            "event_count": self.event_count(),
            "ok": (
                sqlite_result == "ok"
                and not foreign_key_errors
                and batches_valid
                and event_counts_valid
            ),
        }

    def close(self) -> None:
        if getattr(self, "_connection", None) is not None:
            self._connection.close()

    def __enter__(self) -> SQLiteEventStore:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

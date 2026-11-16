"""Compact, incremental public market-data persistence for GitHub Actions.

Daily candles are partitioned by UTC date; five-minute ticker observations are
gzip-compressed into UTC-hour partitions. The manifest is atomic and records
instrument lifecycle and per-instrument candle watermarks.
"""
from __future__ import annotations

import gzip
import json
import os
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SNAPSHOT_RETENTION_DAYS = 90


class MarketDataStoreError(RuntimeError):
    pass


class MarketDataStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.data_dir = self.root / "data"
        self.candles_dir = self.data_dir / "candles"
        self.snapshots_dir = self.data_dir / "snapshots"
        self.manifest_path = self.data_dir / "manifest.json"
        self.candles_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {
                "schema_version": SCHEMA_VERSION,
                "provider": "polymarket",
                "created_at_ms": None,
                "updated_at_ms": None,
                "last_snapshot_ms": None,
                "last_processed_daily_bar_ms": None,
                "bootstrap_complete": False,
                "instruments": {},
            }
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MarketDataStoreError(f"Invalid market-data manifest: {exc}") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != SCHEMA_VERSION
            or not isinstance(value.get("instruments"), dict)
        ):
            raise MarketDataStoreError("Unsupported or malformed market-data manifest")
        return value

    def save_manifest(self, now_ms: int) -> None:
        self.manifest["updated_at_ms"] = int(now_ms)
        if self.manifest["created_at_ms"] is None:
            self.manifest["created_at_ms"] = int(now_ms)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.manifest_path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(self.manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, self.manifest_path)

    def sync_universe(
        self, instruments: list[dict[str, Any]], now_ms: int
    ) -> dict[str, int]:
        """Refresh metadata and lifecycle without treating one miss as a delisting."""
        current_ids: set[str] = set()
        counts = defaultdict(int)
        stored = self.manifest["instruments"]
        for row in instruments:
            instrument_id = str(row["instrument_id"])
            current_ids.add(instrument_id)
            previous = stored.get(instrument_id, {})
            status = "settled" if row.get("settlement") is not None else (
                "close_only" if row.get("close_only") is True else "active"
            )
            first_seen = previous.get("first_seen_at_ms", int(now_ms))
            stored[instrument_id] = {
                **row,
                "instrument_id": int(row["instrument_id"]),
                "first_seen_at_ms": int(first_seen),
                "last_seen_at_ms": int(now_ms),
                "missing_from_feed_count": 0,
                "status": status,
                "last_candle_timestamp_ms": previous.get("last_candle_timestamp_ms"),
                "bootstrap_complete": bool(previous.get("bootstrap_complete", False)),
            }
            counts[status] += 1
        for instrument_id, previous in stored.items():
            if instrument_id in current_ids:
                continue
            previous["missing_from_feed_count"] = int(
                previous.get("missing_from_feed_count", 0)
            ) + 1
            if previous["missing_from_feed_count"] >= 2:
                previous["status"] = "missing_from_feed"
            counts[str(previous.get("status", "unknown"))] += 1
        return dict(sorted(counts.items()))

    def append_candles(self, rows: list[dict[str, Any]]) -> int:
        """Append completed daily candle rows to one gzip partition per UTC date."""
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        seen: set[tuple[int, int]] = set()
        for row in rows:
            instrument_id = row.get("instrument_id")
            timestamp = row.get("timestamp_ms")
            if (
                isinstance(instrument_id, bool)
                or not isinstance(instrument_id, int)
                or isinstance(timestamp, bool)
                or not isinstance(timestamp, int)
                or timestamp <= 0
            ):
                raise MarketDataStoreError("Candle row has invalid instrument or timestamp")
            key = (instrument_id, timestamp)
            if key in seen:
                continue
            seen.add(key)
            day = datetime.fromtimestamp(timestamp / 1000, tz=UTC).strftime("%Y-%m-%d")
            grouped[day].append(row)
        for day, day_rows in grouped.items():
            path = self.candles_dir / f"{day}.jsonl.gz"
            block = "".join(
                json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                for row in sorted(day_rows, key=lambda item: (item["instrument_id"], item["timestamp_ms"]))
            ).encode("utf-8")
            with path.open("ab") as handle:
                handle.write(gzip.compress(block, mtime=0))
        for row in rows:
            instrument = self.manifest["instruments"].get(str(row["instrument_id"]))
            if instrument is not None:
                latest = instrument.get("last_candle_timestamp_ms")
                timestamp = int(row["timestamp_ms"])
                if latest is None or timestamp > int(latest):
                    instrument["last_candle_timestamp_ms"] = timestamp
                instrument["bootstrap_complete"] = True
        return sum(len(items) for items in grouped.values())

    def save_snapshot(self, snapshot_ms: int, rows: list[dict[str, Any]]) -> Path:
        stamp = datetime.fromtimestamp(snapshot_ms / 1000, tz=UTC)
        directory = self.snapshots_dir / stamp.strftime("%Y-%m-%d")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{stamp:%H}.jsonl.gz"
        block = "".join(
            json.dumps(
                {"snapshot_timestamp_ms": int(snapshot_ms), **row},
                sort_keys=True,
                separators=(",", ":"),
            ) + "\n"
            for row in sorted(rows, key=lambda item: int(item["instrument_id"]))
        ).encode("utf-8")
        with path.open("ab") as handle:
            handle.write(gzip.compress(block, mtime=0))
        self.manifest["last_snapshot_ms"] = int(snapshot_ms)
        return path

    def load_candles(
        self,
        instrument_id: int,
        *,
        start_timestamp_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.candles_dir.glob("*.jsonl.gz")):
            try:
                with gzip.open(path, "rt", encoding="utf-8") as source:
                    for line in source:
                        if not line.strip():
                            continue
                        item = json.loads(line)
                        if int(item.get("instrument_id", -1)) != int(instrument_id):
                            continue
                        timestamp = int(item["timestamp_ms"])
                        if start_timestamp_ms is not None and timestamp < start_timestamp_ms:
                            continue
                        rows.append(item)
            except (OSError, EOFError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise MarketDataStoreError(f"Invalid candle partition {path}: {exc}") from exc
        rows.sort(key=lambda item: int(item["timestamp_ms"]))
        deduped: dict[int, dict[str, Any]] = {}
        for row in rows:
            deduped[int(row["timestamp_ms"])] = row
        return list(deduped.values())

    def prune_snapshots(self, now_ms: int, retain_days: int = SNAPSHOT_RETENTION_DAYS) -> int:
        if retain_days < 1:
            raise ValueError("retain_days must be positive")
        cutoff = datetime.fromtimestamp(now_ms / 1000, tz=UTC) - timedelta(days=retain_days)
        deleted = 0
        for path in self.snapshots_dir.glob("*/*.jsonl.gz"):
            try:
                day = datetime.strptime(path.parent.name, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                continue
            if day < cutoff:
                path.unlink(missing_ok=True)
                deleted += 1
        for directory in self.snapshots_dir.iterdir():
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        return deleted

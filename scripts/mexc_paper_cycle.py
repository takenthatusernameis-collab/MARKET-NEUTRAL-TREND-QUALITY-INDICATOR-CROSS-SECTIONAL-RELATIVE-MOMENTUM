#!/usr/bin/env python3
"""Five-minute MEXC market-data and gated USDT forward-paper cycle.

Public market data can be collected and ranked without state-write authorization.
Portfolio transitions require the explicit PAPER_STATE_WRITE_ENABLED flag AND
a live positive GitHub state-branch protection check. There are no live orders.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from trend_quality.event_journal import build_event_batch, verify_event_batch
from trend_quality.github_state import GitHubStatePublisher
from trend_quality.indicators import wilder_atr
from trend_quality.market_data_store import MarketDataStore
from trend_quality.mexc_api import MEXCPublicClient
from trend_quality.mexc_paper import (
    MEXCRankings,
    rank_mexc_universe,
    simulate_mexc_fill,
    size_mexc_leg,
)
from trend_quality.mexc_portfolio import (
    account_report,
    append_daily_equity,
    apply_confirmed_funding,
    close_paper_position,
    initial_portfolio_state,
    open_paper_position,
    portfolio_nav,
    stop_is_triggered,
    update_trailing_stop,
)

DAY_MS = 86_400_000
BOOTSTRAP_DAYS = 365
DEFAULT_BOOTSTRAP_BATCH_SIZE = 150
MAX_SHORTFALL_BPS = Decimal("10")
STOP_ATR_MULTIPLE = Decimal("3")
INITIAL_CAPITAL = Decimal("100")
ACCOUNT_ID = "mexc-usdt-forward"
STRATEGY_ID = "trend-quality-daily-cross-sectional-v1"


def dec(value: object, default: str = "0") -> Decimal:
    try:
        parsed = Decimal(str(default if value is None else value))
    except Exception:
        return Decimal(default)
    return parsed if parsed.is_finite() else Decimal(default)


def _last_completed_daily_bar(server_ms: int) -> int:
    return (server_ms // DAY_MS) * DAY_MS - DAY_MS


def _history_row(instrument: dict[str, Any], candle: dict[str, Any]) -> dict[str, Any]:
    contract_size = dec(instrument["contract_size"])
    volume_contracts = dec(candle["volume_contracts"])
    return {
        "instrument_id": int(instrument["instrument_id"]),
        "symbol": str(instrument["symbol"]),
        "category": str(instrument.get("category", "unclassified")),
        "timestamp_ms": int(candle["timestamp_ms"]),
        "open": str(candle["open"]),
        "high": str(candle["high"]),
        "low": str(candle["low"]),
        "close": str(candle["close"]),
        "volume": str(volume_contracts * contract_size),
        "volume_contracts": str(volume_contracts),
        "turnover_usdt": str(candle["turnover_usdt"]),
    }


def _completed_candles(
    instrument: dict[str, Any],
    candles: list[dict[str, Any]],
    server_ms: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candle in candles:
        timestamp = int(candle["timestamp_ms"])
        if timestamp + DAY_MS > server_ms:
            continue
        values = [
            dec(candle[name])
            for name in ("open", "high", "low", "close")
        ]
        open_price, high, low, close = values
        if (
            min(values) <= 0
            or high < max(open_price, low, close)
            or low > min(open_price, high, close)
        ):
            continue
        rows.append(_history_row(instrument, candle))
    return rows


def _ticker_maps(
    instruments: list[dict[str, Any]],
    ticker_rows: list[dict[str, Any]],
) -> tuple[dict[int, dict[str, Any]], list[int]]:
    ticker_by_symbol = {str(row["symbol"]): row for row in ticker_rows}
    mapped: dict[int, dict[str, Any]] = {}
    missing: list[int] = []
    for instrument in instruments:
        iid = int(instrument["instrument_id"])
        ticker = ticker_by_symbol.get(str(instrument["symbol"]))
        if ticker is None:
            missing.append(iid)
            continue
        mapped[iid] = ticker
    return mapped, missing


def _snapshot_rows(
    instruments: list[dict[str, Any]],
    ticker_by_id: dict[int, dict[str, Any]],
    now_ms: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for instrument in instruments:
        iid = int(instrument["instrument_id"])
        ticker = ticker_by_id.get(iid)
        if ticker is None:
            continue
        rows.append({
            "instrument_id": iid,
            "symbol": str(instrument["symbol"]),
            "category": str(instrument.get("category", "unclassified")),
            "last_price": str(ticker["last_price"]),
            "mark_price": str(ticker["mark_price"]),
            "index_price": str(ticker["index_price"]),
            "mid_price": str(ticker["mid_price"]),
            "bid_price": str(ticker["bid_price"]),
            "ask_price": str(ticker["ask_price"]),
            "funding_rate": str(ticker["funding_rate"]),
            "turnover_24h_usdt": str(ticker["turnover_24h_usdt"]),
            "open_interest_contracts": str(ticker["open_interest_contracts"]),
            "timestamp_ms": int(ticker["timestamp_ms"]),
            "snapshot_timestamp_ms": int(now_ms),
        })
    return rows


def _bootstrap_or_increment(
    client: MEXCPublicClient,
    store: MarketDataStore,
    instruments: list[dict[str, Any]],
    server_ms: int,
    latest_completed_bar_ms: int,
    batch_size: int,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Backfill new assets in bounded, fair batches; fetch only unchecked bars."""
    manifest_rows = store.manifest["instruments"]
    pending = [
        row for row in instruments
        if not manifest_rows[str(row["instrument_id"])].get("bootstrap_complete")
    ]
    pending.sort(key=lambda row: (
        int(manifest_rows[str(row["instrument_id"])].get("bootstrap_attempts", 0)),
        int(manifest_rows[str(row["instrument_id"])].get("first_seen_at_ms", 0)),
        int(row["instrument_id"]),
    ))
    selected_ids = {
        int(row["instrument_id"]) for row in pending[:batch_size]
    }
    completed_count = 0
    api_failures: list[dict[str, Any]] = []
    all_candle_updates: list[dict[str, Any]] = []

    for instrument in instruments:
        iid = int(instrument["instrument_id"])
        record = manifest_rows[str(iid)]
        is_bootstrap = not bool(record.get("bootstrap_complete"))
        if is_bootstrap and iid not in selected_ids:
            continue

        last_timestamp = record.get("last_candle_timestamp_ms")
        last_checked = record.get("last_checked_daily_bar_ms")
        if is_bootstrap and last_timestamp is None and last_checked is None:
            listing_time = instrument.get("create_time_ms")
            start_ms = max(
                server_ms - BOOTSTRAP_DAYS * DAY_MS,
                int(listing_time) if listing_time else server_ms - BOOTSTRAP_DAYS * DAY_MS,
            )
        elif last_timestamp is not None:
            start_ms = int(last_timestamp) + DAY_MS
        else:
            start_ms = int(last_checked or 0) + DAY_MS

        end_ms = min(server_ms, latest_completed_bar_ms + DAY_MS)
        if start_ms >= end_ms:
            if is_bootstrap:
                store.mark_bootstrap_complete(
                    iid,
                    completed_at_ms=server_ms,
                    history_status="INSUFFICIENT_HISTORY",
                )
                record["last_checked_daily_bar_ms"] = latest_completed_bar_ms
                record["bootstrap_attempts"] = int(record.get("bootstrap_attempts", 0)) + 1
                completed_count += 1
            continue
        try:
            raw = client.candles(
                str(instrument["symbol"]),
                start_timestamp_ms=start_ms,
                end_timestamp_ms=end_ms,
                interval="Day1",
            )
            rows = _completed_candles(instrument, raw, server_ms)
            existing = store.load_candles(iid)
            existing_stamps = {int(row["timestamp_ms"]) for row in existing}
            all_candle_updates.extend(
                row for row in rows
                if int(row["timestamp_ms"]) not in existing_stamps
            )
            total_count = len(existing) + sum(
                int(row["timestamp_ms"]) not in existing_stamps for row in rows
            )
            if is_bootstrap:
                status = "AVAILABLE" if total_count >= 35 else "INSUFFICIENT_HISTORY"
                store.mark_bootstrap_complete(
                    iid,
                    completed_at_ms=server_ms,
                    history_status=status,
                )
                completed_count += 1
            elif (
                record.get("history_status") == "INSUFFICIENT_HISTORY"
                and total_count >= 35
            ):
                record["history_status"] = "AVAILABLE"
            record["last_checked_daily_bar_ms"] = latest_completed_bar_ms
            record["bootstrap_attempts"] = int(record.get("bootstrap_attempts", 0)) + 1
            record["last_bootstrap_error"] = None
        except Exception as exc:
            record["bootstrap_attempts"] = int(record.get("bootstrap_attempts", 0)) + 1
            record["last_bootstrap_error"] = f"{type(exc).__name__}: {str(exc)[:250]}"
            api_failures.append({
                "instrument_id": iid,
                "symbol": instrument["symbol"],
                "error": record["last_bootstrap_error"],
            })

    if all_candle_updates:
        store.append_candles(all_candle_updates)
    remaining = sum(
        not bool(manifest_rows[str(row["instrument_id"])].get("bootstrap_complete"))
        for row in instruments
    )
    return completed_count, remaining, api_failures

def _load_state(state_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    paths = sorted((state_dir / "events").glob("**/*.json"))
    batches: list[dict[str, Any]] = []
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not verify_event_batch(value):
            raise RuntimeError(f"Invalid immutable paper event batch: {path}")
        batches.append(value)
    batches.sort(key=lambda row: int(row["created_at_ms"]))
    previous_hash: str | None = None
    portfolio: dict[str, Any] | None = None
    for batch in batches:
        if batch.get("previous_batch_hash") != previous_hash:
            raise RuntimeError("Paper state branch contains a broken event-batch chain")
        previous_hash = str(batch["batch_hash"])
        for event in batch["events"]:
            if event.get("account_id") == ACCOUNT_ID:
                state = event.get("payload", {}).get("portfolio_state")
                if isinstance(state, dict):
                    portfolio = state
    return portfolio, previous_hash


def _state_branch_protection(
    repository: str,
    token: str,
) -> tuple[bool, str]:
    """Require a real positive branch-protection response before any account write."""
    if not repository or not token:
        return False, "MISSING_GITHUB_REPOSITORY_OR_TOKEN"
    url = f"https://api.github.com/repos/{repository}/branches/state/protection"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mexc-paper-state-protection-check/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            value = json.loads(response.read(1_000_000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return False, f"BRANCH_PROTECTION_HTTP_{exc.code}"
    except Exception as exc:
        return False, f"BRANCH_PROTECTION_CHECK_FAILED:{type(exc).__name__}"
    if not isinstance(value, dict) or not value:
        return False, "BRANCH_PROTECTION_RESPONSE_EMPTY"
    return True, "BRANCH_PROTECTION_CONFIRMED"


def _publish_event(
    state: dict[str, Any],
    details: dict[str, Any],
    event_type: str,
    idempotency_key: str,
    now_ms: int,
    previous_hash: str | None,
) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    event = {
        "event_id": f"{event_type}-{idempotency_key}",
        "idempotency_key": idempotency_key,
        "account_id": ACCOUNT_ID,
        "strategy_id": STRATEGY_ID,
        "occurred_at_ms": int(now_ms),
        "event_type": event_type,
        "payload": {
            "portfolio_state": state,
            "details": details,
        },
    }
    batch = build_event_batch(
        run_id=idempotency_key[:120],
        created_at_ms=int(now_ms),
        events=[event],
        previous_batch_hash=previous_hash,
    )
    publisher = GitHubStatePublisher(repository, token, branch="state")
    result = publisher.publish_batch(batch)
    return {
        "path": result.path,
        "batch_hash": result.batch_hash,
        "created": result.created,
        "commit_sha": result.commit_sha,
    }


def _atr(history: list[dict[str, Any]]) -> Decimal | None:
    if len(history) < 14:
        return None
    values = wilder_atr(
        [float(row["high"]) for row in history],
        [float(row["low"]) for row in history],
        [float(row["close"]) for row in history],
        period=14,
    )
    return None if values[-1] is None else Decimal(str(values[-1]))


def _fill(
    client: MEXCPublicClient,
    instrument: dict[str, Any],
    side: str,
    quantity: Decimal,
    now_ms: int,
) -> tuple[Any, dict[str, Any]]:
    book = client.orderbook(str(instrument["symbol"]), depth=50)
    result = simulate_mexc_fill(
        book,
        instrument,
        side,
        quantity,
        now_ms,
        max_shortfall_bps=MAX_SHORTFALL_BPS,
    )
    return result, book


def _try_pair(
    client: MEXCPublicClient,
    rankings: MEXCRankings,
    history: dict[int, list[dict[str, Any]]],
    tickers: dict[int, dict[str, Any]],
    state: dict[str, Any],
    now_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[str, str]] | None:
    nav = portfolio_nav(state, tickers)
    if nav <= 0:
        return None
    for long_candidate in rankings.executable_longs[:10]:
        for short_candidate in rankings.executable_shorts[:10]:
            if long_candidate.symbol == short_candidate.symbol:
                continue
            long_instrument = rankings.instruments_by_key[long_candidate.symbol]
            short_instrument = rankings.instruments_by_key[short_candidate.symbol]
            proposed: list[dict[str, Any]] = []
            fills: list[dict[str, Any]] = []
            valid = True
            for _candidate, instrument, side in (
                (long_candidate, long_instrument, "long"),
                (short_candidate, short_instrument, "short"),
            ):
                iid = int(instrument["instrument_id"])
                atr = _atr(history.get(iid, []))
                ticker = tickers.get(iid)
                if atr is None or ticker is None:
                    valid = False
                    break
                mid = dec(ticker.get("mid_price"))
                if mid <= 0:
                    valid = False
                    break
                quantity = size_mexc_leg(instrument, nav, mid)
                if quantity <= 0:
                    valid = False
                    break
                order_side = "buy" if side == "long" else "sell"
                try:
                    simulated, book = _fill(
                        client, instrument, order_side, quantity, now_ms
                    )
                except Exception:
                    valid = False
                    break
                proposed.append({
                    "instrument": instrument,
                    "ticker": ticker,
                    "side": side,
                    "atr": atr,
                    "fill": simulated,
                })
                fills.append({
                    "instrument_id": iid,
                    "symbol": instrument["symbol"],
                    "side": side,
                    "quantity_base": str(simulated.filled_quantity),
                    "entry_price": str(simulated.average_price),
                    "notional_usdt": str(simulated.notional),
                    "fee_usdt": str(simulated.fee),
                    "shortfall_bps": str(simulated.shortfall_bps),
                    "book_timestamp_ms": book["timestamp_ms"],
                })
            if valid and len(proposed) == 2:
                return proposed, fills, (
                    long_candidate.symbol,
                    short_candidate.symbol,
                )
    return None


def _close_all(
    client: MEXCPublicClient,
    state: dict[str, Any],
    instruments_by_id: dict[int, dict[str, Any]],
    now_ms: int,
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    trial = deepcopy(state)
    for position in list(trial.get("positions", [])):
        instrument = instruments_by_id.get(int(position["instrument_id"]))
        if instrument is None:
            raise RuntimeError(
                f"Cannot close missing MEXC instrument {position['instrument_id']}"
            )
        quantity = dec(position["quantity"])
        side = "sell" if position["side"] == "long" else "buy"
        simulated, _ = _fill(client, instrument, side, quantity, now_ms)
        details.append(close_paper_position(trial, position, simulated, now_ms))
    state.clear()
    state.update(trial)
    return details


def _process_funding(
    client: MEXCPublicClient,
    store: MarketDataStore,
    state: dict[str, Any],
    server_ms: int,
) -> tuple[list[dict[str, Any]], int]:
    applied: list[dict[str, Any]] = []
    unresolved = 0
    for position in state.get("positions", []):
        iid = int(position["instrument_id"])
        start_ms = int(position.get(
            "last_funding_timestamp_ms", position["entry_timestamp_ms"]
        )) + 1
        try:
            observations = client.funding_history(
                str(position["symbol"]),
                start_timestamp_ms=start_ms,
                end_timestamp_ms=server_ms + 1,
                page_size=1000,
            )
        except Exception:
            unresolved += 1
            continue
        funding_rows = [
            {
                "instrument_id": iid,
                "symbol": str(position["symbol"]),
                **row,
            }
            for row in observations
        ]
        if funding_rows:
            store.append_funding(funding_rows)
        for row in sorted(funding_rows, key=lambda item: int(item["timestamp_ms"])):
            funding_ts = int(row["timestamp_ms"])
            if funding_ts <= int(position["entry_timestamp_ms"]):
                position["last_funding_timestamp_ms"] = max(
                    int(position["last_funding_timestamp_ms"]), funding_ts
                )
                continue
            mark = store.find_snapshot_mark(iid, funding_ts, max_age_ms=300_000)
            if mark is None:
                unresolved += 1
                # Do not leapfrog an unmatched settlement; retry from this event next run.
                break
            event = apply_confirmed_funding(
                state,
                position,
                dec(row["funding_rate"]),
                dec(mark[1]),
                funding_ts,
            )
            event["snapshot_timestamp_ms"] = mark[0]
            applied.append(event)
    state["unresolved_funding_count"] = unresolved
    return applied, unresolved


def _process_stops(
    client: MEXCPublicClient,
    state: dict[str, Any],
    instruments_by_id: dict[int, dict[str, Any]],
    tickers: dict[int, dict[str, Any]],
    history: dict[int, list[dict[str, Any]]],
    latest_completed_bar_ms: int,
    now_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exits: list[dict[str, Any]] = []
    trailing: list[dict[str, Any]] = []
    for position in list(state.get("positions", [])):
        iid = int(position["instrument_id"])
        ticker = tickers.get(iid)
        instrument = instruments_by_id.get(iid)
        if ticker is None or instrument is None:
            continue
        last_price = dec(ticker.get("last_price"))
        if last_price <= 0:
            continue
        series = history.get(iid, [])
        last_trailing_bar = int(position.get("last_trailing_bar_ms", 0))
        if (
            latest_completed_bar_ms > last_trailing_bar
            and latest_completed_bar_ms > int(position["entry_timestamp_ms"])
        ):
            bar = next(
                (
                    row for row in series
                    if int(row["timestamp_ms"]) == latest_completed_bar_ms
                ),
                None,
            )
            atr = _atr(series)
            if bar is not None and atr is not None:
                stop = update_trailing_stop(
                    position,
                    dec(bar["high"]),
                    dec(bar["low"]),
                    atr,
                    multiple=STOP_ATR_MULTIPLE,
                )
                position["last_trailing_bar_ms"] = latest_completed_bar_ms
                trailing.append({
                    "instrument_id": iid,
                    "daily_bar_timestamp_ms": latest_completed_bar_ms,
                    "atr14": str(atr),
                    "stop_price": str(stop),
                })
        if stop_is_triggered(position, last_price):
            quantity = dec(position["quantity"])
            close_side = "sell" if position["side"] == "long" else "buy"
            try:
                simulated, _ = _fill(
                    client, instrument, close_side, quantity, now_ms
                )
                detail = close_paper_position(state, position, simulated, now_ms)
                exits.append(detail)
            except Exception as exc:
                position["stop_triggered_unfilled"] = True
                position["stop_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return exits, trailing


def _branch_files_missing(state_dir: Path) -> bool:
    return not any((state_dir / "events").glob("**/*.json"))


def _run() -> int:
    market_data_dir = Path(os.environ.get("MARKET_DATA_DIR", "market-data"))
    state_dir = Path(os.environ.get("PAPER_STATE_DIR", "state"))
    batch_size = max(
        1,
        min(
            int(os.environ.get(
                "BOOTSTRAP_BATCH_SIZE", str(DEFAULT_BOOTSTRAP_BATCH_SIZE)
            )),
            300,
        ),
    )
    store = MarketDataStore(market_data_dir, provider="mexc")
    client = MEXCPublicClient()
    server_ms = client.server_time_ms()
    instruments = client.instruments()
    ticker_rows = client.tickers()
    ticker_by_id, missing_tickers = _ticker_maps(instruments, ticker_rows)
    instrument_by_id = {
        int(row["instrument_id"]): row for row in instruments
    }
    lifecycle_counts = store.sync_universe(instruments, server_ms)
    latest_bar_ms = _last_completed_daily_bar(server_ms)

    snapshot_rows = _snapshot_rows(instruments, ticker_by_id, server_ms)
    snapshot_path = store.save_snapshot(server_ms, snapshot_rows)
    bootstrap_completed, bootstrap_remaining, api_failures = _bootstrap_or_increment(
        client,
        store,
        instruments,
        server_ms,
        latest_bar_ms,
        batch_size,
    )
    history = store.load_all_candles(
        start_timestamp_ms=max(0, server_ms - BOOTSTRAP_DAYS * DAY_MS)
    )
    missing_latest_bar = []
    for instrument in instruments:
        iid = int(instrument["instrument_id"])
        manifest_row = store.manifest["instruments"][str(iid)]
        if (
            manifest_row.get("history_status") == "AVAILABLE"
            and (
                not history.get(iid)
                or int(history[iid][-1]["timestamp_ms"]) < latest_bar_ms
            )
        ):
            missing_latest_bar.append(iid)

    history_coverage_pass = (
        bootstrap_remaining == 0
        and not api_failures
        and not missing_tickers
        and not missing_latest_bar
    )
    # Rankings remain available as soon as any instrument has enough causal
    # daily data; incomplete coverage blocks portfolio decisions, not research output.
    rankings = rank_mexc_universe(
        instruments,
        history,
        ticker_by_id,
        INITIAL_CAPITAL,
    )
    previous_state, previous_hash = _load_state(state_dir)
    writer_requested = os.environ.get("PAPER_STATE_WRITE_ENABLED", "").lower() == "true"
    state_protected = False
    state_protection_reason = "PAPER_STATE_WRITES_DISABLED_BY_CONFIGURATION"
    if writer_requested:
        state_protected, state_protection_reason = _state_branch_protection(
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_TOKEN", ""),
        )
    writer_enabled = writer_requested and state_protected

    portfolio = previous_state
    if portfolio is None and writer_enabled:
        portfolio = initial_portfolio_state(INITIAL_CAPITAL)
    elif portfolio is not None:
        if portfolio.get("currency") != "USDT":
            raise RuntimeError("Existing paper account currency is not USDT")

    paper_decision_status = (
        "BLOCKED_STATE_WRITE_GATE"
        if not writer_enabled
        else "BLOCKED_INCOMPLETE_MARKET_DATA"
    )
    state_event: dict[str, Any] | None = None
    funding_events: list[dict[str, Any]] = []
    stop_exits: list[dict[str, Any]] = []
    trailing_updates: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    unresolved_funding = 0
    if writer_enabled and portfolio is not None:
        old_last_processed = portfolio.get("last_processed_daily_bar_ms")
        new_daily_bar = (
            history_coverage_pass
            and (
                old_last_processed is None
                or latest_bar_ms > int(old_last_processed)
            )
        )
        funding_events, unresolved_funding = _process_funding(
            client, store, portfolio, server_ms
        )
        stop_exits, trailing_updates = _process_stops(
            client,
            portfolio,
            instrument_by_id,
            ticker_by_id,
            history,
            latest_bar_ms,
            server_ms,
        )
        state_changed = bool(funding_events or stop_exits or trailing_updates)

        if new_daily_bar:
            pair = (
                _try_pair(
                    client,
                    rankings,
                    history,
                    ticker_by_id,
                    portfolio,
                    server_ms,
                )
                if rankings.executable_longs and rankings.executable_shorts
                else None
            )
            wanted: set[tuple[int, str]] = set()
            if pair is not None:
                proposed, fills, _ = pair
                wanted = {
                    (int(row["instrument"]["instrument_id"]), str(row["side"]))
                    for row in proposed
                }
            current = {
                (int(row["instrument_id"]), str(row["side"]))
                for row in portfolio.get("positions", [])
            }
            if current == wanted and current:
                paper_decision_status = "PAIR_HELD"
            else:
                trial = deepcopy(portfolio)
                try:
                    closed = _close_all(
                        client, trial, instrument_by_id, server_ms
                    ) if trial.get("positions") else []
                    opened: list[dict[str, Any]] = []
                    if pair is not None:
                        proposed, fills, _ = pair
                        for row in proposed:
                            position = open_paper_position(
                                trial,
                                row["instrument"],
                                row["ticker"],
                                row["side"],
                                row["atr"],
                                row["fill"],
                                server_ms,
                                stop_atr_multiple=STOP_ATR_MULTIPLE,
                            )
                            opened.append(position)
                    trial["positions"] = opened
                    portfolio = trial
                    fills = closed + fills
                    paper_decision_status = (
                        "PAIR_OPENED_OR_REPLACED"
                        if opened else "FLAT_NO_EXECUTABLE_PAIR"
                    )
                    state_changed = True
                except Exception as exc:
                    paper_decision_status = (
                        f"REBALANCE_BLOCKED:{type(exc).__name__}:{str(exc)[:180]}"
                    )
            if paper_decision_status in {
                "PAIR_HELD", "PAIR_OPENED_OR_REPLACED", "FLAT_NO_EXECUTABLE_PAIR"
            }:
                nav = portfolio_nav(portfolio, ticker_by_id)
                append_daily_equity(portfolio, latest_bar_ms, nav)
                portfolio["last_processed_daily_bar_ms"] = latest_bar_ms
                state_changed = True
        if state_changed:
            report_details = {
                "provider": "mexc",
                "daily_bar_timestamp_ms": latest_bar_ms,
                "daily_decision_status": paper_decision_status,
                "fills": fills,
                "stop_exits": stop_exits,
                "trailing_stop_updates": trailing_updates,
                "funding_events": funding_events,
                "research_long_top": [
                    {"symbol": row.symbol, "q": str(row.q)}
                    for row in rankings.research_longs[:10]
                ],
                "research_short_top": [
                    {"symbol": row.symbol, "q": str(row.q)}
                    for row in rankings.research_shorts[:10]
                ],
                "execution_long_top": [
                    {"symbol": row.symbol, "q": str(row.q)}
                    for row in rankings.executable_longs[:10]
                ],
                "execution_short_top": [
                    {"symbol": row.symbol, "q": str(row.q)}
                    for row in rankings.executable_shorts[:10]
                ],
                "history_coverage_pass": history_coverage_pass,
                "unresolved_funding_count": unresolved_funding,
            }
            key = (
                f"daily-{latest_bar_ms}"
                if paper_decision_status in {
                    "PAIR_HELD", "PAIR_OPENED_OR_REPLACED", "FLAT_NO_EXECUTABLE_PAIR"
                }
                else f"risk-{server_ms}"
            )
            state_event = _publish_event(
                portfolio,
                report_details,
                "daily_portfolio_decision"
                if key.startswith("daily-") else "paper_risk_update",
                key,
                server_ms,
                previous_hash,
            )
            store.save_projection({
                "schema_version": 1,
                "portfolio_state": portfolio,
                "last_run_utc": datetime.fromtimestamp(
                    server_ms / 1000, tz=UTC
                ).isoformat(),
                "state_event": state_event,
            })
            store.manifest["last_processed_daily_bar_ms"] = (
                portfolio.get("last_processed_daily_bar_ms")
            )

    # A disabled or unprotected journal never initializes a simulated account.
    portfolio_report = (
        account_report(portfolio, ticker_by_id)
        if writer_enabled and portfolio is not None
        else None
    )
    report = {
        "run_utc": datetime.now(UTC).isoformat(),
        "provider": "mexc",
        "mode": "PUBLIC_DATA_AND_Q_RANKING_PAPER_ONLY",
        "instrument_count_all": len(client.contract_details()),
        "active_cross_usdt_perpetual_count": len(instruments),
        "asset_class_counts": {
            category: sum(1 for row in instruments if row["category"] == category)
            for category in sorted({str(row["category"]) for row in instruments})
        },
        "ticker_count": len(ticker_rows),
        "ticker_coverage": len(ticker_by_id),
        "missing_ticker_count": len(missing_tickers),
        "missing_ticker_sample": missing_tickers[:20],
        "lifecycle_counts": lifecycle_counts,
        "bootstrap_completed_this_run": bootstrap_completed,
        "bootstrap_remaining": bootstrap_remaining,
        "candle_rows_stored": sum(len(rows) for rows in history.values()),
        "latest_completed_daily_bar_ms": latest_bar_ms,
        "missing_latest_bar_count": len(missing_latest_bar),
        "missing_latest_bar_sample": missing_latest_bar[:20],
        "api_failure_count": len(api_failures),
        "api_failure_sample": api_failures[:20],
        "history_coverage_pass": history_coverage_pass,
        "research_long_top": [
            {"symbol": row.symbol, "q": str(row.q), "b": row.b}
            for row in rankings.research_longs[:20]
        ],
        "research_short_top": [
            {"symbol": row.symbol, "q": str(row.q), "b": row.b}
            for row in rankings.research_shorts[:20]
        ],
        "execution_long_top": [
            {"symbol": row.symbol, "q": str(row.q)}
            for row in rankings.executable_longs[:20]
        ],
        "execution_short_top": [
            {"symbol": row.symbol, "q": str(row.q)}
            for row in rankings.executable_shorts[:20]
        ],
        "excluded_or_unranked_sample": rankings.excluded[:50],
        "paper_state_write_requested": writer_requested,
        "state_branch_protection": state_protection_reason,
        "paper_simulation_enabled": writer_enabled,
        "paper_decision_status": paper_decision_status,
        "portfolio": portfolio_report,
        "state_event": state_event,
        "funding_events": funding_events,
        "unresolved_funding_count": unresolved_funding,
        "stop_exits": stop_exits,
        "trailing_stop_updates": trailing_updates,
        "snapshot_partition": str(snapshot_path),
        "orders_submitted": 0,
        "credentials_used": False,
        "private_endpoints_used": False,
        "wallet_used": False,
    }
    report_dir = market_data_dir / "data" / "reports" / "mexc"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "latest_cycle.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    (report_dir / "latest_cycle.md").write_text(
        _markdown_report(report),
        encoding="utf-8",
    )
    store.manifest["selected_provider"] = "mexc"
    store.manifest["last_processed_daily_bar_ms"] = (
        store.manifest.get("last_processed_daily_bar_ms")
    )
    store.manifest["bootstrap_complete"] = bootstrap_remaining == 0
    store.save_manifest(server_ms)
    store.prune_snapshots(server_ms)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# MEXC Trend-Quality Paper Research",
        "",
        f"- Run (UTC): {report['run_utc']}",
        f"- Active cross-margin USDT perpetuals: {report['active_cross_usdt_perpetual_count']}",
        f"- Bootstrap remaining: {report['bootstrap_remaining']}",
        f"- History coverage gate: {report['history_coverage_pass']}",
        f"- Paper-state write gate: {report['state_branch_protection']}",
        f"- Paper simulation enabled: {report['paper_simulation_enabled']}",
        f"- Decision: {report['paper_decision_status']}",
        "",
        "## Research long ranking",
        "",
        "| Symbol | Q | B |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| {row['symbol']} | {row['q']} | {row['b']} |"
        for row in report["research_long_top"]
    )
    lines.extend(["", "## Research short ranking", "", "| Symbol | Q | B |", "|---|---:|---:|"])
    lines.extend(
        f"| {row['symbol']} | {row['q']} | {row['b']} |"
        for row in report["research_short_top"]
    )
    lines.extend([
        "",
        "## Data completeness",
        "",
        f"- Ticker coverage: {report['ticker_coverage']}",
        f"- Missing latest daily bars: {report['missing_latest_bar_count']}",
        f"- API failures: {report['api_failure_count']}",
        f"- Excluded/unranked records sampled: {len(report['excluded_or_unranked_sample'])}",
        "",
        "## Portfolio accounting",
        "",
    ])
    portfolio = report.get("portfolio")
    if portfolio is None:
        lines.append(
            "Not initialized. Ranking and market-data collection do not imply a paper account. "
            "The immutable state branch must be protected and the explicit writer gate enabled."
        )
    else:
        lines.extend([
            f"- Currency: {portfolio['currency']}",
            f"- Cash: {portfolio['cash']}",
            f"- NAV: {portfolio['nav']}",
            f"- Realized gross P&L: {portfolio['realized_gross_pnl']}",
            f"- Unrealized P&L: {portfolio['unrealized_pnl']}",
            f"- Fees paid: {portfolio['fees_paid']}",
            f"- Confirmed funding: {portfolio['confirmed_funding']}",
            f"- Gross exposure: {portfolio['gross_exposure']}",
            f"- Net exposure: {portfolio['net_exposure']}",
            f"- Open positions: {portfolio['position_count']}",
            f"- Closed trades: {portfolio['closed_trade_count']}",
            f"- Performance report status: {portfolio['performance']['status']}",
        ])
        for name, metric in portfolio["performance"].get("metrics", {}).items():
            lines.append(
                f"- {name}: {metric['value'] if metric['value'] is not None else 'Unavailable'}"
                + (f" ({metric['reason']})" if metric.get("reason") else "")
            )
    lines.extend([
        "",
        "No exchange orders were submitted. All execution records are simulated.",
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        raise SystemExit(_run())
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {str(exc)[:1000]}",
            "provider": "mexc",
            "orders_submitted": 0,
            "credentials_used": False,
            "private_endpoints_used": False,
        }, indent=2))
        raise SystemExit(1) from exc

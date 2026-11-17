#!/usr/bin/env python3
"""Five-minute MEXC market-data and gated USDT forward-paper cycle.

Public market data can be collected and ranked without state-write authorization.
Portfolio transitions require the explicit PAPER_STATE_WRITE_ENABLED flag.
State writes are serialized, hash-chain checked and verified by exact remote
read-back. There are no live orders.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from trend_quality.event_journal import (
    build_event_batch,
    order_event_batches,
    verify_event_batch,
)
from trend_quality.github_state import GitHubStatePublisher
from trend_quality.indicators import wilder_atr
from trend_quality.market_data_store import MarketDataStore
from trend_quality.mexc_api import MEXCPublicClient
from trend_quality.mexc_paper import (
    MEXCRankings,
    base_quantity_rules,
    rank_mexc_universe,
    simulate_mexc_fill,
    size_mexc_leg,
)
from trend_quality.mexc_portfolio import (
    account_report,
    append_daily_equity,
    append_equity_snapshot,
    apply_confirmed_funding,
    close_paper_position,
    increase_paper_position,
    initial_portfolio_state,
    open_paper_position,
    portfolio_nav,
    reduce_paper_position,
    reset_daily_risk_window,
    stop_is_triggered,
    update_trailing_stop,
)
from trend_quality.ranking import Candidate

DAY_MS = 86_400_000
BOOTSTRAP_DAYS = 365
DEFAULT_BOOTSTRAP_BATCH_SIZE = 150
MAX_SHORTFALL_BPS = Decimal("10")
STOP_ATR_MULTIPLE = Decimal("3")
INITIAL_CAPITAL = Decimal("10")
ACCOUNT_ID = "mexc-usdt-forward-10usdt-v2"
STRATEGY_ID = "trend-quality-daily-cross-sectional-v2-10usdt"


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
    usdt_eligible = bool(instrument.get("usdt_account_eligible"))
    quote_turnover = candle.get("turnover_quote", candle.get("turnover_usdt"))
    return {
        "instrument_id": int(instrument["instrument_id"]),
        "symbol": str(instrument["symbol"]),
        "category": str(instrument.get("category", "unclassified")),
        "quote_asset": str(instrument.get("quote_asset", "")),
        "settlement_asset": str(instrument.get("settlement_asset", "")),
        "timestamp_ms": int(candle["timestamp_ms"]),
        "open": str(candle["open"]),
        "high": str(candle["high"]),
        "low": str(candle["low"]),
        "close": str(candle["close"]),
        "volume": str(volume_contracts * contract_size) if usdt_eligible else None,
        "volume_contracts": str(volume_contracts),
        "turnover_quote": str(quote_turnover),
        "turnover_quote_asset": str(instrument.get("quote_asset", "")),
        "turnover_usdt": str(quote_turnover) if usdt_eligible else None,
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


def _stale_or_missing_position_marks(
    positions: list[dict[str, Any]],
    ticker_by_id: dict[int, dict[str, Any]],
    now_ms: int,
    *,
    max_age_ms: int = 300_000,
) -> list[str]:
    """Return open-position symbols without a fresh, positive mark price."""
    missing: list[str] = []
    for position in positions:
        iid = int(position["instrument_id"])
        ticker = ticker_by_id.get(iid)
        if ticker is None:
            missing.append(str(position["symbol"]))
            continue
        age = now_ms - int(ticker.get("timestamp_ms", 0))
        mark = dec(ticker.get("mark_price"))
        if age < 0 or age > max_age_ms or mark <= 0:
            missing.append(str(position["symbol"]))
    return sorted(set(missing))


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


def _ranking_report_rows(
    candidates: list[Any],
    instruments_by_key: dict[str, dict[str, Any]],
    *,
    include_b: bool = True,
) -> list[dict[str, Any]]:
    """Translate stable internal ranking keys to human-readable venue tickers."""
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        instrument = instruments_by_key.get(candidate.symbol)
        if instrument is None:
            continue
        row = {
            "symbol": str(instrument["symbol"]),
            "instrument_id": int(instrument["instrument_id"]),
            "category": str(instrument.get("category", "unclassified")),
            "q": str(candidate.q),
            "direction": candidate.direction,
            "cycle_age": candidate.cycle_age,
        }
        if include_b:
            row["b"] = str(candidate.b)
        rows.append(row)
    return rows


def _pending_entry_signal(
    rankings: MEXCRankings,
    daily_bar_timestamp_ms: int,
) -> dict[str, Any] | None:
    """Persist the candle-stamped execution shortlist for five-minute retries."""
    def encode(candidates: list[Candidate]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for candidate in candidates[:10]:
            instrument = rankings.instruments_by_key.get(candidate.symbol)
            if instrument is None:
                continue
            rows.append({
                "candidate_key": candidate.symbol,
                "instrument_id": int(instrument["instrument_id"]),
                "q": str(candidate.q),
                "b": None if candidate.b is None else str(candidate.b),
                "direction": candidate.direction,
                "cycle_age": candidate.cycle_age,
                "semi_cycle_direction": candidate.semi_cycle_direction,
            })
        return rows

    longs = encode(rankings.executable_longs)
    shorts = encode(rankings.executable_shorts)
    if not longs or not shorts:
        return None
    return {
        "daily_bar_timestamp_ms": int(daily_bar_timestamp_ms),
        "attempt_count": 0,
        "last_attempt_ms": None,
        "executable_longs": longs,
        "executable_shorts": shorts,
    }


def _restore_pending_rankings(
    pending: dict[str, Any],
    manifest_instruments: dict[str, dict[str, Any]],
) -> MEXCRankings | None:
    """Rehydrate the frozen daily ranking without recalculating Q."""
    instruments_by_key: dict[str, dict[str, Any]] = {}

    def decode(side: str) -> list[Candidate]:
        rows: list[Candidate] = []
        for item in pending.get(side, []):
            iid = int(item["instrument_id"])
            instrument = manifest_instruments.get(str(iid))
            if instrument is None:
                continue
            key = str(item["candidate_key"])
            instruments_by_key[key] = instrument
            b_value = item.get("b")
            rows.append(Candidate(
                symbol=key,
                q=float(item["q"]),
                b=None if b_value is None else float(b_value),
                direction=str(item["direction"]),
                cycle_age=(
                    None if item.get("cycle_age") is None else int(item["cycle_age"])
                ),
                semi_cycle_direction=item.get("semi_cycle_direction"),
            ))
        return rows

    longs = decode("executable_longs")
    shorts = decode("executable_shorts")
    if not longs or not shorts:
        return None
    return MEXCRankings(
        research_longs=longs,
        research_shorts=shorts,
        executable_longs=longs,
        executable_shorts=shorts,
        instruments_by_key=instruments_by_key,
        excluded=[],
    )


def _minimum_order_size_diagnostics(
    instruments: list[dict[str, Any]],
    ticker_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Measure minVol × contractSize × live mid-price for USDT contracts."""
    notionals: list[Decimal] = []
    affordable = {"1": 0, "10": 0}
    evaluated = 0
    for instrument in instruments:
        if not instrument.get("usdt_account_eligible"):
            continue
        iid = int(instrument["instrument_id"])
        ticker = ticker_by_id.get(iid)
        if ticker is None:
            continue
        mid = dec(ticker.get("mid_price"))
        if mid <= 0:
            continue
        minimum_base = (
            dec(instrument.get("min_contracts"))
            * dec(instrument.get("contract_size"))
        )
        notionals.append(minimum_base * mid)
        evaluated += 1
        for capital in ("1", "10"):
            try:
                quantity = size_mexc_leg(instrument, Decimal(capital), mid)
            except Exception:
                quantity = Decimal("0")
            if quantity > 0:
                affordable[capital] += 1

    if not notionals:
        return {"status": "NO_CURRENT_USDT_TICKERS", "evaluated_contracts": 0}
    ordered = sorted(notionals)

    def percentile(fraction: float) -> str:
        index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction)))
        return str(ordered[index])

    return {
        "status": "MEASURED_FROM_CURRENT_PUBLIC_TICKERS",
        "evaluated_contracts": evaluated,
        "minimum_order_notional_usdt": {
            "p10": percentile(0.10),
            "median": percentile(0.50),
            "p75": percentile(0.75),
            "p90": percentile(0.90),
            "maximum": str(ordered[-1]),
        },
        "contracts_satisfying_minimum_quantity_and_step": {
            "at_1_usdt_per_leg": affordable["1"],
            "at_10_usdt_per_leg": affordable["10"],
        },
        "contracts_with_minimum_notional_above_1_usdt": sum(
            value > Decimal("1") for value in notionals
        ),
        "contracts_with_minimum_notional_above_10_usdt": sum(
            value > Decimal("10") for value in notionals
        ),
        "scope_note": (
            "Minimum quantity and lot-step affordability only; turnover, book depth, "
            "fees and shortfall remain separate execution gates."
        ),
    }


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
            "quote_asset": str(instrument.get("quote_asset", "")),
            "settlement_asset": str(instrument.get("settlement_asset", "")),
            "usdt_account_eligible": bool(instrument.get("usdt_account_eligible")),
            "last_price": str(ticker["last_price"]),
            "mark_price": str(ticker["mark_price"]),
            "index_price": str(ticker["index_price"]),
            "mid_price": str(ticker["mid_price"]),
            "bid_price": str(ticker["bid_price"]),
            "ask_price": str(ticker["ask_price"]),
            "funding_rate": str(ticker["funding_rate"]),
            "turnover_24h_quote": str(ticker["turnover_24h_quote"]),
            "turnover_24h_usdt": (
                str(ticker["turnover_24h_quote"])
                if instrument.get("usdt_account_eligible") else None
            ),
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
    existing_history = store.load_all_candles()
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
            existing = existing_history.get(iid, [])
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

def _load_state(
    state_dir: Path,
) -> tuple[dict[str, Any] | None, str | None, bool]:
    """Verify the persisted chain and report whether a prior-run recovery probe exists."""
    paths = sorted((state_dir / "events").glob("**/*.json"))
    batches: list[dict[str, Any]] = []
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not verify_event_batch(value):
            raise RuntimeError(f"Invalid immutable paper event batch: {path}")
        batches.append(value)
    batches = order_event_batches(batches)
    previous_hash: str | None = None
    portfolio: dict[str, Any] | None = None
    recovery_probe_verified = False
    for batch in batches:
        if batch.get("previous_batch_hash") != previous_hash:
            raise RuntimeError("Paper state branch contains a broken event-batch chain")
        previous_hash = str(batch["batch_hash"])
        for event in batch["events"]:
            payload = event.get("payload", {})
            details = payload.get("details", {}) if isinstance(payload, dict) else {}
            if (
                event.get("account_id") == ACCOUNT_ID
                and event.get("event_type") == "paper_state_recovery_probe"
                and isinstance(details, dict)
                and details.get("protocol") == "PUBLISH_READBACK_THEN_FRESH_CHECKOUT"
                and details.get("financial_state_created") is False
                and details.get("account_initialized") is False
                and details.get("orders_submitted") == 0
                and "portfolio_state" not in payload
            ):
                recovery_probe_verified = True
            if event.get("account_id") == ACCOUNT_ID:
                state = payload.get("portfolio_state") if isinstance(payload, dict) else None
                if isinstance(state, dict) and state.get("account_id") == ACCOUNT_ID:
                    portfolio = state
    return portfolio, previous_hash, recovery_probe_verified


def _publish_recovery_probe(
    now_ms: int,
    previous_hash: str | None,
) -> dict[str, Any]:
    """Append a non-financial probe; publisher returns only after remote read-back."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repository:
        raise RuntimeError("Missing GitHub publisher configuration for state probe")
    stamp = int(now_ms)
    key = f"state-probe-{stamp}"
    event = {
        "event_id": key,
        "idempotency_key": key,
        "account_id": ACCOUNT_ID,
        "strategy_id": STRATEGY_ID,
        "occurred_at_ms": stamp,
        "event_type": "paper_state_recovery_probe",
        "payload": {
            "details": {
                "protocol": "PUBLISH_READBACK_THEN_FRESH_CHECKOUT",
                "purpose": (
                    "Verify GitHub append-only publisher read-back "
                    "before financial initialization"
                ),
                "financial_state_created": False,
                "account_initialized": False,
                "orders_submitted": 0,
            }
        },
    }
    batch = build_event_batch(
        run_id=key,
        created_at_ms=stamp,
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
        "remote_readback_verified": True,
        "fresh_checkout_recovery_required": True,
    }

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
    *,
    max_pairs: int = 100,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[str, str]] | None:
    """Find a valid pair and simulate only each leg's required quantity delta."""
    nav = portfolio_nav(state, tickers)
    if nav <= 0 or max_pairs < 1:
        return None
    current_by_id = {
        int(row["instrument_id"]): row
        for row in state.get("positions", [])
    }
    attempted_pairs = 0
    for long_candidate in rankings.executable_longs[:10]:
        for short_candidate in rankings.executable_shorts[:10]:
            if attempted_pairs >= max_pairs:
                return None
            attempted_pairs += 1
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
                target_qty = size_mexc_leg(instrument, nav, mid)
                if target_qty <= 0:
                    valid = False
                    break

                existing = current_by_id.get(iid)
                retained = existing is not None and existing.get("side") == side
                current_qty = dec(existing["quantity"]) if retained else Decimal("0")
                requested_delta = target_qty - current_qty if retained else target_qty
                executable_delta = requested_delta
                simulated = None
                book = None
                rebalance_constraint = None

                if retained and requested_delta != 0:
                    _step, minimum_qty, _maximum, _contract_size = (
                        base_quantity_rules(instrument, mid)
                    )
                    if abs(requested_delta) < minimum_qty:
                        executable_delta = Decimal("0")
                        rebalance_constraint = "DELTA_BELOW_VENUE_MINIMUM"
                    else:
                        entry_order_side = "buy" if side == "long" else "sell"
                        order_side = (
                            entry_order_side
                            if requested_delta > 0
                            else ("sell" if entry_order_side == "buy" else "buy")
                        )
                        try:
                            simulated, book = _fill(
                                client, instrument, order_side,
                                abs(requested_delta), now_ms,
                            )
                        except Exception as exc:
                            # Retaining a valid existing contract is preferable
                            # to liquidating it just because a small rebalance
                            # delta cannot currently be filled from public depth.
                            executable_delta = Decimal("0")
                            rebalance_constraint = (
                                f"DELTA_FILL_UNAVAILABLE:{type(exc).__name__}"
                            )
                else:
                    order_side = "buy" if side == "long" else "sell"
                    try:
                        simulated, book = _fill(
                            client, instrument, order_side, target_qty, now_ms
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
                    "target_quantity": str(target_qty),
                    "current_quantity": str(current_qty),
                    "quantity_delta": str(executable_delta),
                    "retained_position": retained,
                    "rebalance_constraint": rebalance_constraint,
                })
                if simulated is not None and book is not None:
                    action = (
                        "OPEN" if not retained
                        else "INCREASE" if executable_delta > 0
                        else "REDUCE"
                    )
                    fills.append({
                        "instrument_id": iid,
                        "symbol": instrument["symbol"],
                        "side": side,
                        "action": action,
                        "quantity_base": str(simulated.filled_quantity),
                        "quantity_delta": str(executable_delta),
                        "entry_or_exit_price": str(simulated.average_price),
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


def _apply_selected_pair(
    client: MEXCPublicClient,
    state: dict[str, Any],
    proposed: list[dict[str, Any]],
    instruments_by_id: dict[int, dict[str, Any]],
    now_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Replace only changed contracts and resize retained legs by the needed delta."""
    trial = deepcopy(state)
    close_details: list[dict[str, Any]] = []
    resize_details: list[dict[str, Any]] = []
    wanted = {
        (int(row["instrument"]["instrument_id"]), str(row["side"]))
        for row in proposed
    }

    for position in list(trial.get("positions", [])):
        key = (int(position["instrument_id"]), str(position["side"]))
        if key in wanted:
            continue
        instrument = instruments_by_id.get(key[0])
        if instrument is None:
            raise RuntimeError(
                f"Cannot replace missing MEXC instrument {position['symbol']}"
            )
        quantity = dec(position["quantity"])
        order_side = "sell" if key[1] == "long" else "buy"
        simulated, _ = _fill(
            client, instrument, order_side, quantity, now_ms
        )
        close_details.append(
            close_paper_position(trial, position, simulated, now_ms)
        )

    for row in proposed:
        instrument = row["instrument"]
        iid = int(instrument["instrument_id"])
        side = str(row["side"])
        existing = next(
            (
                position for position in trial.get("positions", [])
                if int(position["instrument_id"]) == iid
                and str(position["side"]) == side
            ),
            None,
        )
        delta = dec(row["quantity_delta"])
        simulated = row.get("fill")
        if existing is None:
            if simulated is None or delta <= 0:
                raise RuntimeError(
                    f"Missing full entry fill for new paper position {instrument['symbol']}"
                )
            resize_details.append(open_paper_position(
                trial,
                instrument,
                row["ticker"],
                side,
                row["atr"],
                simulated,
                now_ms,
                stop_atr_multiple=STOP_ATR_MULTIPLE,
            ) | {"action": "OPENED"})
        elif delta > 0:
            if simulated is None:
                raise RuntimeError(
                    f"Missing incremental fill for {instrument['symbol']} increase"
                )
            resize_details.append(increase_paper_position(
                trial,
                existing,
                instrument,
                row["ticker"],
                row["atr"],
                simulated,
                now_ms,
                stop_atr_multiple=STOP_ATR_MULTIPLE,
            ))
        elif delta < 0:
            if simulated is None:
                raise RuntimeError(
                    f"Missing incremental fill for {instrument['symbol']} reduction"
                )
            resize_details.append(reduce_paper_position(
                trial, existing, simulated, now_ms
            ))
        elif row.get("rebalance_constraint"):
            resize_details.append({
                "instrument_id": iid,
                "symbol": instrument["symbol"],
                "side": side,
                "action": "REBALANCE_UNCHANGED",
                "quantity_delta": "0",
                "constraint": row["rebalance_constraint"],
                "current_quantity": row["current_quantity"],
                "target_quantity": row["target_quantity"],
            })

    state.clear()
    state.update(trial)
    return close_details, resize_details

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





def _snapshot_only_cycle(
    *,
    client: MEXCPublicClient,
    store: MarketDataStore,
    portfolio: dict[str, Any] | None,
    writer_enabled: bool,
    writer_requested: bool,
    state_write_mode: str,
    paper_account_restored_from_state_branch: bool,
    previous_hash: str | None,
    latest_bar_ms: int,
    server_ms: int,
    market_data_dir: Path,
) -> int:
    """Five-minute portfolio valuation/risk path; no ordinary strategy decisions."""
    ticker_by_id: dict[int, dict[str, Any]] = {}
    position_instruments: list[dict[str, Any]] = []
    missing_symbols: list[str] = []
    snapshot: dict[str, Any] | None = None
    state_event: dict[str, Any] | None = None
    portfolio_report: dict[str, Any] | None = None
    emergency_exits: list[dict[str, Any]] = []
    funding_events: list[dict[str, Any]] = []
    unresolved_funding = 0
    risk_status = "NOT_APPLICABLE_NO_INITIALIZED_PAPER_ACCOUNT"
    state_changed = False
    entry_retry_report: dict[str, Any] | None = None

    if portfolio is not None:
        positions = list(portfolio.get("positions", []))
        pending_entry = portfolio.get("pending_entry_signal")
        if (
            writer_enabled
            and not positions
            and isinstance(pending_entry, dict)
            and int(pending_entry.get("daily_bar_timestamp_ms", 0)) == latest_bar_ms
            and not portfolio.get("daily_risk", {}).get("stop_triggered")
            and not portfolio.get("emergency_liquidation_pending")
        ):
            retry_rankings = _restore_pending_rankings(
                pending_entry, store.manifest.get("instruments", {})
            )
            if retry_rankings is not None:
                retry_instruments = list(retry_rankings.instruments_by_key.values())
                retry_tickers, retry_missing = _ticker_maps(
                    retry_instruments, client.tickers()
                )
                if retry_missing:
                    pending_entry["attempt_count"] = (
                        int(pending_entry.get("attempt_count", 0)) + 1
                    )
                    pending_entry["last_attempt_ms"] = server_ms
                    entry_retry_report = {
                        "status": "RETRY_BLOCKED_MISSING_TICKER",
                        "missing_instrument_ids": retry_missing,
                        "daily_bar_timestamp_ms": latest_bar_ms,
                        "attempt_count": pending_entry["attempt_count"],
                    }
                    state_changed = True
                else:
                    retry_history = store.load_all_candles(
                        start_timestamp_ms=max(0, server_ms - BOOTSTRAP_DAYS * DAY_MS)
                    )
                    pair = _try_pair(
                        client,
                        retry_rankings,
                        retry_history,
                        retry_tickers,
                        portfolio,
                        server_ms,
                        max_pairs=5,
                    )
                    pending_entry["attempt_count"] = (
                        int(pending_entry.get("attempt_count", 0)) + 1
                    )
                    pending_entry["last_attempt_ms"] = server_ms
                    if pair is None:
                        entry_retry_report = {
                            "status": "RETRY_NO_EXECUTABLE_PAIR",
                            "daily_bar_timestamp_ms": latest_bar_ms,
                            "attempt_count": pending_entry["attempt_count"],
                            "pairs_checked_this_run": 5,
                        }
                    else:
                        proposed, retry_fills, pair_symbols = pair
                        trial = deepcopy(portfolio)
                        opened: list[dict[str, Any]] = []
                        for row in proposed:
                            opened.append(open_paper_position(
                                trial,
                                row["instrument"],
                                row["ticker"],
                                row["side"],
                                row["atr"],
                                row["fill"],
                                server_ms,
                                stop_atr_multiple=STOP_ATR_MULTIPLE,
                            ))
                        trial["positions"] = opened
                        trial["pending_entry_signal"] = None
                        retry_nav = portfolio_nav(trial, retry_tickers)
                        risk_window_reset = reset_daily_risk_window(
                            trial,
                            server_ms,
                            retry_nav,
                            reference="new_pair_opened_after_daily_signal",
                        )
                        portfolio.clear()
                        portfolio.update(trial)
                        positions = list(portfolio.get("positions", []))
                        entry_retry_report = {
                            "status": "RETRY_PAIR_OPENED",
                            "daily_bar_timestamp_ms": latest_bar_ms,
                            "attempt_count": pending_entry["attempt_count"],
                            "pair": list(pair_symbols),
                            "fills": retry_fills,
                            "risk_window_reset": risk_window_reset,
                        }
                    state_changed = True
        elif (
            writer_enabled
            and isinstance(pending_entry, dict)
            and int(pending_entry.get("daily_bar_timestamp_ms", 0)) < latest_bar_ms
        ):
            portfolio["pending_entry_signal"] = None
            entry_retry_report = {
                "status": "PENDING_SIGNAL_EXPIRED_ON_NEW_DAILY_CANDLE",
                "daily_bar_timestamp_ms": latest_bar_ms,
            }
            state_changed = True

        if positions:
            ticker_rows = client.tickers()
            ticker_by_symbol = {str(row["symbol"]): row for row in ticker_rows}
            for position in positions:
                symbol = str(position["symbol"])
                ticker = ticker_by_symbol.get(symbol)
                if ticker is None:
                    missing_symbols.append(symbol)
                    continue
                age = server_ms - int(ticker["timestamp_ms"])
                mark = dec(ticker.get("mark_price"))
                if age < 0 or age > 300_000 or mark <= 0:
                    missing_symbols.append(symbol)
                    continue
                ticker_by_id[int(position["instrument_id"])] = ticker
                instrument = store.manifest["instruments"].get(
                    str(position["instrument_id"])
                )
                if instrument is None:
                    missing_symbols.append(symbol)
                else:
                    position_instruments.append(instrument)

        # Funding is a confirmed cash-flow event, not an ordinary strategy decision.
        if writer_enabled:
            funding_events, unresolved_funding = _process_funding(
                client, store, portfolio, server_ms
            )
            state_changed = bool(state_changed or funding_events)

        risk = portfolio.setdefault("daily_risk", {})
        pending_flatten = bool(
            risk.get("stop_triggered")
            or portfolio.get("emergency_liquidation_pending")
        )
        if missing_symbols:
            risk_status = "UNAVAILABLE_STALE_OR_MISSING_POSITION_MARK"
            # Never defer an already-triggered emergency exit merely because a
            # mark is unavailable. The closing order-book simulator is independent.
            if writer_enabled and pending_flatten and portfolio.get("positions"):
                portfolio["emergency_liquidation_pending"] = True
                try:
                    instruments_by_id = {
                        int(key): value
                        for key, value in store.manifest["instruments"].items()
                    }
                    emergency_exits.extend(_close_all(client, portfolio, instruments_by_id, server_ms))
                    portfolio["daily_risk"]["flattened"] = True
                    portfolio["daily_risk"]["flatten_error"] = (None)
                    portfolio["emergency_liquidation_pending"] = False
                    risk_status = "EMERGENCY_BOOK_FLATTENED_WITH_MARK_GAP"
                except Exception as exc:
                    portfolio["daily_risk"]["flattened"] = False
                    portfolio["daily_risk"]["flatten_attempts"] = int(
                        portfolio["daily_risk"].get("flatten_attempts", 0)
                    ) + 1
                    portfolio["daily_risk"]["flatten_error"] = (
                        f"{type(exc).__name__}: {str(exc)[:200]}"
                    )
                    risk_status = "EMERGENCY_FLATTEN_PENDING_RETRY"
                state_changed = True
        elif not writer_enabled:
            risk_status = "READ_ONLY_ONLY_STATE_WRITE_GATE_CLOSED"
        else:
            nav = portfolio_nav(portfolio, ticker_by_id)
            long_notional = Decimal("0")
            short_notional = Decimal("0")
            for position in portfolio.get("positions", []):
                iid = int(position["instrument_id"])
                mark = dec(
                    ticker_by_id.get(iid, {}).get(
                        "mark_price", position.get("last_mark_price")
                    )
                )
                notional = dec(position["quantity"]) * mark
                if position["side"] == "long":
                    long_notional += notional
                else:
                    short_notional += notional

            snapshot = append_equity_snapshot(
                portfolio, server_ms, nav, long_notional, short_notional
            )
            state_changed = True
            risk = portfolio["daily_risk"]
            if risk.get("stop_triggered"):
                portfolio["emergency_liquidation_pending"] = bool(
                    portfolio.get("positions")
                )

            if (
                risk.get("stop_triggered")
                or portfolio.get("emergency_liquidation_pending")
            ) and portfolio.get("positions"):
                portfolio["emergency_liquidation_pending"] = True
                try:
                    instruments_by_id = {
                        int(key): value
                        for key, value in store.manifest["instruments"].items()
                    }
                    emergency_exits.extend(_close_all(client, portfolio, instruments_by_id, server_ms))
                    portfolio["daily_risk"]["flattened"] = True
                    portfolio["daily_risk"]["flatten_error"] = (None)
                    portfolio["emergency_liquidation_pending"] = False
                    risk_status = "EMERGENCY_BOOK_FLATTENED"
                except Exception as exc:
                    portfolio["daily_risk"]["flattened"] = False
                    portfolio["daily_risk"]["flatten_attempts"] = int(
                        portfolio["daily_risk"].get("flatten_attempts", 0)
                    ) + 1
                    portfolio["daily_risk"]["flatten_error"] = (
                        f"{type(exc).__name__}: {str(exc)[:200]}"
                    )
                    risk_status = "EMERGENCY_FLATTEN_PENDING_RETRY"
            elif risk.get("stop_triggered"):
                portfolio["daily_risk"]["flattened"] = True
                portfolio["emergency_liquidation_pending"] = False
                risk_status = "EMERGENCY_STOP_ACTIVE_BOOK_ALREADY_FLAT"
            else:
                risk_status = "MONITORING_ONLY_NO_STRATEGY_DECISIONS"

        if writer_enabled and state_changed:
            details = {
                "provider": "mexc",
                "workflow_mode": "FIVE_MINUTE_PORTFOLIO_SNAPSHOT",
                "portfolio_snapshot": snapshot,
                "emergency_risk_status": risk_status,
                "funding_events": funding_events,
                "emergency_exits": emergency_exits,
                "unresolved_funding_count": unresolved_funding,
                "missing_position_marks": missing_symbols,
                "ordinary_strategy_decisions": entry_retry_report is not None,
                "entry_retry": entry_retry_report,
                "live_orders_submitted": 0,
            }
            state_event = _publish_event(
                portfolio,
                details,
                (
                    "paper_entry_retry" if entry_retry_report is not None
                    else "paper_portfolio_snapshot"
                ),
                f"snapshot-{server_ms}",
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

        if writer_enabled and not missing_symbols:
            try:
                portfolio_report = account_report(portfolio, ticker_by_id)
            except Exception as exc:
                portfolio_report = {
                    "status": "PORTFOLIO_REPORT_UNAVAILABLE",
                    "reason": f"{type(exc).__name__}: {str(exc)[:200]}",
                    "currency": "USDT",
                    "position_count": len(portfolio.get("positions", [])),
                }
        elif not writer_enabled:
            try:
                portfolio_report = account_report(portfolio, ticker_by_id)
            except Exception:
                portfolio_report = None

    if position_instruments and ticker_by_id:
        store.save_snapshot(
            server_ms, _snapshot_rows(position_instruments, ticker_by_id, server_ms)
        )
    store.manifest["last_snapshot_ms"] = server_ms
    store.save_manifest(server_ms)
    store.prune_snapshots(server_ms)

    report = {
        "run_utc": datetime.fromtimestamp(server_ms / 1000, tz=UTC).isoformat(),
        "provider": "mexc",
        "mode": "PORTFOLIO_SNAPSHOT_ONLY",
        "workflow_mode": "FIVE_MINUTE_PORTFOLIO_SNAPSHOT",
        "latest_completed_daily_bar_ms": latest_bar_ms,
        "daily_decision_due": False,
        "research_refresh_performed": False,
        "q_rankings_recalculated": False,
        "ordinary_strategy_decisions": False,
        "paper_state_write_requested": writer_requested,
        "paper_simulation_enabled": writer_enabled,
        "paper_account_restored_from_state_branch": paper_account_restored_from_state_branch,
        "paper_account_recovery_status": (
            "RESTORED_FROM_VERIFIED_EVENT_CHAIN"
            if paper_account_restored_from_state_branch
            else "NOT_INITIALIZED"
        ),
        "state_write_mode": state_write_mode,
        "paper_decision_status": (
            entry_retry_report["status"] if entry_retry_report is not None else risk_status
        ),
        "entry_retry": entry_retry_report,
        "ticker_coverage": len(ticker_by_id),
        "missing_ticker_count": len(missing_symbols),
        "missing_position_marks": missing_symbols,
        "active_cross_usdt_perpetual_count": "not refreshed in snapshot mode",
        "bootstrap_remaining": "not refreshed in snapshot mode",
        "history_coverage_pass": "not checked in snapshot mode",
        "missing_latest_bar_count": 0,
        "api_failure_count": 0,
        "research_long_top": [],
        "research_short_top": [],
        "execution_long_top": [],
        "execution_short_top": [],
        "excluded_or_unranked_sample": [],
        "portfolio": portfolio_report,
        "portfolio_snapshot": snapshot,
        "funding_events": funding_events,
                "emergency_exits": emergency_exits,
        "unresolved_funding_count": unresolved_funding,
        "emergency_risk_status": risk_status,
        "state_event": state_event,
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
        _markdown_report(report), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0

def _paper_state_writer_requested() -> bool:
    """Require an explicit true flag; the scheduled workflow supplies the default."""
    return os.environ.get("PAPER_STATE_WRITE_ENABLED", "").strip().lower() == "true"


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
    latest_bar_ms = _last_completed_daily_bar(server_ms)

    # Inspect the persistent state before any universe/history/ranking requests.
    previous_state, previous_hash, recovery_probe_verified = _load_state(state_dir)
    writer_requested = _paper_state_writer_requested()
    state_write_mode = (
        "UNPROTECTED_SINGLE_WRITER_APPEND_ONLY"
        if writer_requested
        else "PAPER_STATE_WRITES_DISABLED_BY_CONFIGURATION"
    )
    writer_enabled = writer_requested
    if writer_enabled and previous_state is None and not recovery_probe_verified:
        probe_result = _publish_recovery_probe(server_ms, previous_hash)
        store.manifest["last_state_recovery_probe_ms"] = server_ms
        store.save_manifest(server_ms)
        report = {
            "run_utc": datetime.now(UTC).isoformat(),
            "provider": "mexc",
            "mode": "STATE_PERSISTENCE_PROBE",
            "paper_decision_status": "PUBLISH_READBACK_VERIFIED_AWAITING_FRESH_CHECKOUT",
            "paper_state_write_requested": True,
            "paper_simulation_enabled": False,
            "paper_account_initialized": False,
            "initial_capital_usdt": str(INITIAL_CAPITAL),
            "state_write_mode": state_write_mode,
            "state_recovery_probe": probe_result,
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
            "# MEXC State Persistence Probe\n\n"
            "- Status: publisher write/read-back succeeded\n"
            "- Financial account initialized: no\n"
            "- Orders submitted: 0\n"
            "- Next invocation must verify this event from a fresh state-branch checkout\n",
            encoding="utf-8",
        )
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0

    account_initialization_due = (
        previous_state is None and writer_enabled and recovery_probe_verified
    )
    portfolio = previous_state
    if account_initialization_due:
        portfolio = initial_portfolio_state(
            INITIAL_CAPITAL, account_id=ACCOUNT_ID, strategy_id=STRATEGY_ID
        )
    elif portfolio is not None and portfolio.get("currency") != "USDT":
        raise RuntimeError("Existing paper account currency is not USDT")

    last_daily_workflow_bar = store.manifest.get("last_daily_workflow_bar_ms")
    if last_daily_workflow_bar is None:
        last_daily_workflow_bar = store.manifest.get("last_research_daily_bar_ms")
    if last_daily_workflow_bar is None:
        last_daily_workflow_bar = store.manifest.get("last_processed_daily_bar_ms")
    research_due = (
        last_daily_workflow_bar is None
        or latest_bar_ms > int(last_daily_workflow_bar)
    )
    account_attempt_bar = None
    if portfolio is not None:
        account_attempt_bar = portfolio.get(
            "last_decision_attempt_daily_bar_ms",
            portfolio.get("last_processed_daily_bar_ms"),
        )
    account_due = bool(
        writer_enabled
        and portfolio is not None
        and (
            account_attempt_bar is None
            or latest_bar_ms > int(account_attempt_bar)
        )
    )
    if not research_due and not account_due:
        return _snapshot_only_cycle(
            client=client,
            store=store,
            portfolio=portfolio,
            writer_enabled=writer_enabled,
            writer_requested=writer_requested,
            state_write_mode=state_write_mode,
            paper_account_restored_from_state_branch=previous_state is not None,
            previous_hash=previous_hash,
            latest_bar_ms=latest_bar_ms,
            server_ms=server_ms,
            market_data_dir=market_data_dir,
        )

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
        old_last_attempt = portfolio.get(
            "last_decision_attempt_daily_bar_ms",
            portfolio.get("last_processed_daily_bar_ms"),
        )
        new_daily_bar = (
            history_coverage_pass
            and (old_last_attempt is None or latest_bar_ms > int(old_last_attempt))
        )
        if old_last_attempt is None or latest_bar_ms > int(old_last_attempt):
            portfolio["last_decision_attempt_daily_bar_ms"] = latest_bar_ms
        funding_events, unresolved_funding = _process_funding(
            client, store, portfolio, server_ms
        )
        position_mark_gaps = _stale_or_missing_position_marks(
            list(portfolio.get("positions", [])),
            ticker_by_id,
            server_ms,
        )
        daily_risk_snapshot: dict[str, Any] | None = None
        if position_mark_gaps:
            state_changed = True
            paper_decision_status = "BLOCKED_MISSING_POSITION_MARK"
            emergency_pending = bool(
                portfolio.get("daily_risk", {}).get("stop_triggered")
                or portfolio.get("emergency_liquidation_pending")
            )
            if emergency_pending and portfolio.get("positions"):
                portfolio["emergency_liquidation_pending"] = True
                try:
                    stop_exits.extend(
                        _close_all(client, portfolio, instrument_by_id, server_ms)
                    )
                    portfolio["daily_risk"]["flattened"] = True
                    portfolio["daily_risk"]["flatten_error"] = None
                    portfolio["emergency_liquidation_pending"] = False
                    paper_decision_status = "EMERGENCY_BOOK_FLATTENED_WITH_MARK_GAP"
                except Exception as exc:
                    portfolio["daily_risk"]["flattened"] = False
                    portfolio["emergency_liquidation_pending"] = True
                    portfolio["daily_risk"]["flatten_attempts"] = int(
                        portfolio["daily_risk"].get("flatten_attempts", 0)
                    ) + 1
                    portfolio["daily_risk"]["flatten_error"] = (
                        f"{type(exc).__name__}: {str(exc)[:200]}"
                    )
                    paper_decision_status = "EMERGENCY_FLATTEN_PENDING_RETRY"
        else:
            nav_before_decisions = portfolio_nav(portfolio, ticker_by_id)
            long_notional_before = Decimal("0")
            short_notional_before = Decimal("0")
            for position in portfolio.get("positions", []):
                mark = dec(ticker_by_id.get(int(position["instrument_id"]), {}).get(
                    "mark_price", position.get("last_mark_price")
                ))
                notional = dec(position["quantity"]) * mark
                if position["side"] == "long":
                    long_notional_before += notional
                else:
                    short_notional_before += notional
            daily_risk_snapshot = append_equity_snapshot(
                portfolio, server_ms, nav_before_decisions,
                long_notional_before, short_notional_before,
            )
            state_changed = True
            if (
                portfolio["daily_risk"].get("stop_triggered")
                or portfolio.get("emergency_liquidation_pending")
            ) and portfolio.get("positions"):
                try:
                    stop_exits.extend(_close_all(
                        client, portfolio, instrument_by_id, server_ms
                    ))
                    portfolio["daily_risk"]["flattened"] = True
                    portfolio["daily_risk"]["flatten_error"] = None
                    portfolio["emergency_liquidation_pending"] = False
                    paper_decision_status = "EMERGENCY_BOOK_FLATTENED"
                except Exception as exc:
                    portfolio["daily_risk"]["flattened"] = False
                    portfolio["emergency_liquidation_pending"] = True
                    portfolio["daily_risk"]["flatten_attempts"] = int(
                        portfolio["daily_risk"].get("flatten_attempts", 0)
                    ) + 1
                    portfolio["daily_risk"]["flatten_error"] = (
                        f"{type(exc).__name__}: {str(exc)[:200]}"
                    )
                    paper_decision_status = "EMERGENCY_FLATTEN_PENDING_RETRY"
            elif portfolio.get("daily_risk", {}).get("stop_triggered"):
                portfolio["daily_risk"]["flattened"] = True
                portfolio["emergency_liquidation_pending"] = False
                paper_decision_status = "EMERGENCY_STOP_ACTIVE_BOOK_ALREADY_FLAT"
            else:
                if history_coverage_pass:
                    stop_exits, trailing_updates = _process_stops(
                        client,
                        portfolio,
                        instrument_by_id,
                        ticker_by_id,
                        history,
                        latest_bar_ms,
                        server_ms,
                    )
                state_changed = bool(
                    state_changed or funding_events or stop_exits or trailing_updates
                )
    
    
        if (
            new_daily_bar
            and not portfolio.get("daily_risk", {}).get("stop_triggered")
            and not portfolio.get("emergency_liquidation_pending")
            and not position_mark_gaps
        ):
            portfolio["pending_entry_signal"] = _pending_entry_signal(
                rankings, latest_bar_ms
            )
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
            pair_rebalance_actions: list[dict[str, Any]] = []
            risk_window_reset: dict[str, Any] | None = None
            if pair is not None:
                proposed, _pair_candidate_fills, _ = pair
                prior_keys = {
                    (int(row["instrument_id"]), str(row["side"]))
                    for row in portfolio.get("positions", [])
                }
                wanted = {
                    (int(row["instrument"]["instrument_id"]), str(row["side"]))
                    for row in proposed
                }
                same_pair = bool(prior_keys) and prior_keys == wanted
                trial = deepcopy(portfolio)
                try:
                    closed_details, resize_details = _apply_selected_pair(
                        client, trial, proposed, instrument_by_id, server_ms
                    )
                    portfolio = trial
                    fills = closed_details + resize_details
                    pair_rebalance_actions = resize_details
                    actual_delta = any(
                        row.get("action") in {"OPENED", "INCREASED", "REDUCED"}
                        for row in resize_details
                    )
                    if same_pair:
                        paper_decision_status = (
                            "PAIR_REBALANCED" if actual_delta else "PAIR_HELD"
                        )
                    else:
                        paper_decision_status = "PAIR_OPENED_OR_REPLACED"
                    portfolio["pending_entry_signal"] = None

                    # A successful daily rebalance starts a fresh combined-book
                    # risk window, like a new trade. The pre-rebalance snapshot
                    # above has already had a chance to trigger the emergency stop.
                    post_nav = portfolio_nav(portfolio, ticker_by_id)
                    post_long_notional = Decimal("0")
                    post_short_notional = Decimal("0")
                    for position in portfolio.get("positions", []):
                        mark = dec(ticker_by_id.get(
                            int(position["instrument_id"]), {}
                        ).get("mark_price", position.get("last_mark_price")))
                        notional = dec(position["quantity"]) * mark
                        if position["side"] == "long":
                            post_long_notional += notional
                        else:
                            post_short_notional += notional
                    risk_window_reset = reset_daily_risk_window(
                        portfolio, server_ms, post_nav,
                        reference="daily_portfolio_rebalance",
                    )
                    daily_risk_snapshot = append_equity_snapshot(
                        portfolio, server_ms, post_nav,
                        post_long_notional, post_short_notional,
                    )
                    state_changed = True
                except Exception as exc:
                    paper_decision_status = (
                        f"REBALANCE_BLOCKED:{type(exc).__name__}:{str(exc)[:180]}"
                    )
            else:
                trial = deepcopy(portfolio)
                try:
                    closed = _close_all(
                        client, trial, instrument_by_id, server_ms
                    ) if trial.get("positions") else []
                    trial["positions"] = []
                    portfolio = trial
                    fills = closed
                    paper_decision_status = "FLAT_NO_EXECUTABLE_PAIR"
                    state_changed = True
                except Exception as exc:
                    paper_decision_status = (
                        f"REBALANCE_BLOCKED:{type(exc).__name__}:{str(exc)[:180]}"
                    )
            if paper_decision_status in {
                "PAIR_HELD", "PAIR_REBALANCED", "PAIR_OPENED_OR_REPLACED",
                "FLAT_NO_EXECUTABLE_PAIR"
            }:
                nav = portfolio_nav(portfolio, ticker_by_id)
                append_daily_equity(portfolio, latest_bar_ms, nav)
                portfolio["last_processed_daily_bar_ms"] = latest_bar_ms
                state_changed = True
        if new_daily_bar and portfolio.get("daily_risk", {}).get("stop_triggered"):
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
                "research_long_top": _ranking_report_rows(
                    rankings.research_longs[:10], rankings.instruments_by_key
                ),
                "research_short_top": _ranking_report_rows(
                    rankings.research_shorts[:10], rankings.instruments_by_key
                ),
                "execution_long_top": _ranking_report_rows(
                    rankings.executable_longs[:10],
                    rankings.instruments_by_key,
                    include_b=False,
                ),
                "execution_short_top": _ranking_report_rows(
                    rankings.executable_shorts[:10],
                    rankings.instruments_by_key,
                    include_b=False,
                ),
                "history_coverage_pass": history_coverage_pass,
                "missing_position_marks": position_mark_gaps,
                "unresolved_funding_count": unresolved_funding,
                "portfolio_daily_risk_snapshot": daily_risk_snapshot,
                "portfolio_daily_risk_reset": risk_window_reset,
                "rebalance_actions": pair_rebalance_actions,
                "emergency_risk_status": (
                    paper_decision_status
                    if str(paper_decision_status).startswith("EMERGENCY_")
                    else "WITHIN_DAILY_LIMIT"
                ),
            }
            if account_initialization_due:
                report_details["account_initialization"] = {
                    "initial_capital_usdt": str(INITIAL_CAPITAL),
                    "starting_cash_usdt": str(INITIAL_CAPITAL),
                    "account_mode": "FORWARD_PAPER_ONLY",
                    "historical_equity_imported": False,
                    "historical_trades_imported": False,
                }
                key = f"account-init-{server_ms}"
                event_type = "paper_account_initialized"
            else:
                key = (
                    f"daily-{latest_bar_ms}"
                    if paper_decision_status in {
                        "PAIR_HELD", "PAIR_REBALANCED",
                        "PAIR_OPENED_OR_REPLACED", "FLAT_NO_EXECUTABLE_PAIR"
                    }
                    else f"risk-{server_ms}"
                )
                event_type = (
                    "daily_portfolio_decision"
                    if key.startswith("daily-") else "paper_risk_update"
                )
            state_event = _publish_event(
                portfolio,
                report_details,
                event_type,
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

    # A disabled paper-state writer never initializes a simulated account.
    portfolio_report = (
        account_report(portfolio, ticker_by_id)
        if writer_enabled and portfolio is not None
        else None
    )
    report = {
        "run_utc": datetime.now(UTC).isoformat(),
        "provider": "mexc",
        "mode": "DAILY_CLOSE_RESEARCH_AND_DECISION",
        "workflow_mode": "DAILY_CLOSE_RESEARCH_AND_DECISION",
        "daily_decision_due": True,
        "research_refresh_performed": True,
        "q_rankings_recalculated": True,
        "ordinary_strategy_decisions": bool(writer_enabled),
        "state_recovery_probe_verified_from_prior_checkout": recovery_probe_verified,
        "paper_account_restored_from_state_branch": previous_state is not None,
        "paper_account_recovery_status": (
            "RESTORED_FROM_VERIFIED_EVENT_CHAIN"
            if previous_state is not None
            else (
                "INITIALIZED_THIS_CYCLE"
                if account_initialization_due
                else "NOT_INITIALIZED"
            )
        ),
        "paper_account_initialized_this_cycle": account_initialization_due,
        "paper_account_initial_capital_usdt": (
            str(INITIAL_CAPITAL) if account_initialization_due else None
        ),
        "instrument_count_all": len(client.contract_details()),
        "active_cross_margin_perpetual_count": len(instruments),
        "active_cross_usdt_perpetual_count": sum(
            bool(row.get("usdt_account_eligible")) for row in instruments
        ),
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
        "minimum_order_size_diagnostics": _minimum_order_size_diagnostics(
            instruments, ticker_by_id
        ),
        "initial_capital_usdt": str(INITIAL_CAPITAL),
        "account_id": ACCOUNT_ID,
        "research_long_top": _ranking_report_rows(
            rankings.research_longs[:20], rankings.instruments_by_key
        ),
        "research_short_top": _ranking_report_rows(
            rankings.research_shorts[:20], rankings.instruments_by_key
        ),
        "execution_long_top": _ranking_report_rows(
            rankings.executable_longs[:20],
            rankings.instruments_by_key,
            include_b=False,
        ),
        "execution_short_top": _ranking_report_rows(
            rankings.executable_shorts[:20],
            rankings.instruments_by_key,
            include_b=False,
        ),
        "excluded_or_unranked_sample": rankings.excluded[:50],
        "paper_state_write_requested": writer_requested,
        "state_write_mode": state_write_mode,
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
    if history_coverage_pass:
        store.manifest["last_research_daily_bar_ms"] = latest_bar_ms
    store.manifest["last_daily_workflow_bar_ms"] = latest_bar_ms
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
        f"- State write mode: {report['state_write_mode']}",
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
        equity_curve = portfolio.get("daily_equity_curve", [])
        lines.extend([
            "",
            "## Daily equity curve",
            "",
            "| UTC daily bar | NAV (USDT) |",
            "|---|---:|",
        ])
        lines.extend(
            f"| {datetime.fromtimestamp(row['timestamp_ms'] / 1000, tz=UTC).isoformat()} "
            f"| {row['nav']} |"
            for row in equity_curve[-30:]
        )
        if not equity_curve:
            lines.append("No persisted daily equity observations yet.")
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

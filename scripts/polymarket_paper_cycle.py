#!/usr/bin/env python3
"""Five-minute Polymarket Perps data/portfolio cycle; paper only."""
from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from trend_quality.event_journal import (
    build_event_batch,
    order_event_batches,
    verify_event_batch,
)
from trend_quality.execution import BookLevel, simulate_orderbook_fill
from trend_quality.github_state import GitHubStatePublisher
from trend_quality.indicators import compute_q_series, wilder_atr
from trend_quality.market_data_store import MarketDataStore
from trend_quality.polymarket_api import (
    PolymarketPublicClient,
    is_cross_margin_instrument,
    is_new_position_eligible,
    validate_instrument,
)
from trend_quality.portfolio import (
    Position,
    funding_cashflow,
    portfolio_exposure,
    target_quantity,
)
from trend_quality.ranking import rank_candidates

DAY_MS = 86_400_000
BOOTSTRAP_DAYS = 365
MIN_HISTORY_FOR_RANKING = 35
MAX_SHORTFALL_BPS = Decimal("10")
STOP_ATR_MULTIPLE = Decimal("3")
INITIAL_CAPITAL = Decimal("100")
ACCOUNT_ID = "polymarket-perps-forward"
STRATEGY_ID = "trend-quality-daily-cross-sectional-v1"


def dec(value: Any, default: str = "0") -> Decimal:
    try:
        parsed = Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)
    return parsed if parsed.is_finite() else Decimal(default)


def _rows_by_id(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {
        int(row["instrument_id"]): row
        for row in rows
        if isinstance(row.get("instrument_id"), int)
        and not isinstance(row.get("instrument_id"), bool)
    }


def _book_levels(book: dict[str, Any], side: str) -> list[BookLevel]:
    raw = book.get("asks" if side == "ask" else "bids")
    if not isinstance(raw, list):
        raise ValueError(f"Order-book {side} side is malformed")
    levels: list[BookLevel] = []
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("Order-book level is not an object")
        levels.append(BookLevel(dec(row.get("price")), dec(row.get("quantity"))))
    if not levels:
        raise ValueError(f"Order-book {side} side is empty")
    return levels


def _fee_rates(fees: dict[str, Any]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for row in fees.get("fee_schedule", []):
        if not isinstance(row, dict) or not isinstance(row.get("category"), str):
            continue
        rates = [dec(row.get("taker_fee_rate"))]
        for tier in row.get("tiers", []):
            if isinstance(tier, dict):
                rates.append(dec(tier.get("taker_fee_rate")))
        result[row["category"]] = max(rates)
    return result


def _load_state_from_event_branch(state_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    event_paths = sorted((state_dir / "events").glob("**/*.json"))
    batches: list[dict[str, Any]] = []
    for path in event_paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot read paper state event {path}: {exc}") from exc
        if not verify_event_batch(value):
            raise RuntimeError(f"Paper state event batch failed hash verification: {path}")
        batches.append(value)
    batches = order_event_batches(batches)
    previous_hash: str | None = None
    latest_state: dict[str, Any] | None = None
    for batch in batches:
        if batch.get("previous_batch_hash") != previous_hash:
            raise RuntimeError("Paper state branch contains a broken batch chain")
        previous_hash = str(batch["batch_hash"])
        for event in batch["events"]:
            if event.get("account_id") == ACCOUNT_ID:
                payload = event.get("payload", {})
                state = payload.get("portfolio_state")
                if isinstance(state, dict):
                    latest_state = state
    return latest_state, previous_hash


def _publish_state_event(
    state_dir: Path,
    now_ms: int,
    run_id: str,
    idempotency_key: str,
    event_type: str,
    portfolio_state: dict[str, Any],
    details: dict[str, Any],
) -> dict[str, Any]:
    previous_state, previous_hash = _load_state_from_event_branch(state_dir)
    if previous_state is not None:
        portfolio_state["initial_capital"] = previous_state["initial_capital"]
    event = {
        "event_id": f"{event_type}-{idempotency_key}",
        "idempotency_key": idempotency_key,
        "account_id": ACCOUNT_ID,
        "strategy_id": STRATEGY_ID,
        "occurred_at_ms": int(now_ms),
        "event_type": event_type,
        "payload": {
            "portfolio_state": portfolio_state,
            "details": details,
        },
    }
    batch = build_event_batch(
        run_id=run_id,
        created_at_ms=int(now_ms),
        events=[event],
        previous_batch_hash=previous_hash,
    )
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repository:
        raise RuntimeError(
            "GITHUB_TOKEN and GITHUB_REPOSITORY are required to persist paper events"
        )
    publisher = GitHubStatePublisher(repository, token, branch="state")
    result = publisher.publish_batch(batch)
    return {"path": result.path, "batch_hash": result.batch_hash, "created": result.created}


def _latest_completed_bar(server_timestamp_ms: int) -> int:
    return (server_timestamp_ms // DAY_MS - 1) * DAY_MS


def _candle_row(instrument: dict[str, Any], candle: list[Any]) -> dict[str, Any]:
    return {
        "instrument_id": int(instrument["instrument_id"]),
        "symbol": str(instrument["symbol"]),
        "category": str(instrument.get("category") or "unknown"),
        "timestamp_ms": int(candle[0]),
        "open": str(candle[1]),
        "high": str(candle[2]),
        "low": str(candle[3]),
        "close": str(candle[4]),
        "volume": str(candle[5]),
        "trades": int(candle[6]),
    }


def _complete_candles(
    instrument: dict[str, Any],
    rows: list[list[Any]],
    server_timestamp_ms: int,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        if (
            len(row) < 7
            or not isinstance(row[0], int)
            or row[0] + DAY_MS > server_timestamp_ms
        ):
            continue
        high, low, close = dec(row[2]), dec(row[3]), dec(row[4])
        open_price = dec(row[1])
        if (
            min(open_price, high, low, close) <= 0
            or high < max(open_price, low, close)
            or low > min(open_price, high, close)
            or dec(row[5]) < 0
        ):
            continue
        output.append(_candle_row(instrument, row))
    return output


def _load_history(
    store: MarketDataStore, lookback_start_ms: int
) -> dict[int, list[dict[str, Any]]]:
    return store.load_all_candles(start_timestamp_ms=lookback_start_ms)


def _atr_for_history(rows: list[dict[str, Any]]) -> Decimal | None:
    if len(rows) < 14:
        return None
    values = wilder_atr(
        [float(row["high"]) for row in rows],
        [float(row["low"]) for row in rows],
        [float(row["close"]) for row in rows],
        period=14,
    )
    latest = values[-1]
    return None if latest is None or latest <= 0 else Decimal(str(latest))


def _nav(state: dict[str, Any], tickers: dict[int, dict[str, Any]]) -> Decimal:
    cash = dec(state.get("cash"), str(INITIAL_CAPITAL))
    unrealized = Decimal("0")
    for position in state.get("positions", []):
        ticker = tickers.get(int(position["instrument_id"]), {})
        mark = dec(ticker.get("mark_price"), position.get("last_mark_price", "0"))
        if mark <= 0:
            mark = dec(position.get("last_mark_price"), position["entry_price"])
        paper_position = Position(
            symbol=str(position["symbol"]),
            side=str(position["side"]),
            quantity=dec(position["quantity"]),
            entry_price=dec(position["entry_price"]),
        )
        unrealized += paper_position.unrealized_pnl(mark)
        position["last_mark_price"] = str(mark)
    return cash + unrealized


def _portfolio_snapshot(
    instruments: dict[int, dict[str, Any]],
    tickers: dict[int, dict[str, Any]],
    fees: dict[str, Decimal],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "account_id": ACCOUNT_ID,
        "strategy_id": STRATEGY_ID,
        "currency": "pUSD",
        "initial_capital": str(INITIAL_CAPITAL),
        "cash": str(INITIAL_CAPITAL),
        "realized_gross_pnl": "0",
        "fees_paid": "0",
        "confirmed_funding": "0",
        "positions": [],
        "last_processed_daily_bar_ms": None,
        "last_snapshot_ms": None,
        "unresolved_funding_count": 0,
        "status": "NOT_INITIALIZED",
    }


def _current_orderbook_fill(
    client: PolymarketPublicClient,
    instrument: dict[str, Any],
    side: str,
    quantity: Decimal,
    fee_rate: Decimal,
) -> tuple[Any, dict[str, Any]]:
    book = client.book(int(instrument["instrument_id"]), depth=100)
    bids = _book_levels(book, "bid")
    asks = _book_levels(book, "ask")
    fill = simulate_orderbook_fill(
        side,
        quantity,
        bids,
        asks,
        fee_rate=fee_rate,
        max_shortfall_bps=MAX_SHORTFALL_BPS,
        allow_partial=False,
    )
    return fill, book


def _close_position(
    client: PolymarketPublicClient,
    state: dict[str, Any],
    position: dict[str, Any],
    instrument: dict[str, Any],
    fee_rate: Decimal,
) -> dict[str, Any]:
    quantity = dec(position["quantity"])
    close_side = "sell" if position["side"] == "long" else "buy"
    fill, book = _current_orderbook_fill(
        client, instrument, close_side, quantity, fee_rate
    )
    model_position = Position(
        symbol=str(position["symbol"]),
        side=str(position["side"]),
        quantity=quantity,
        entry_price=dec(position["entry_price"]),
    )
    realized = model_position.unrealized_pnl(fill.average_price)
    state["cash"] = str(dec(state["cash"]) + realized - fill.fee)
    state["realized_gross_pnl"] = str(dec(state["realized_gross_pnl"]) + realized)
    state["fees_paid"] = str(dec(state["fees_paid"]) + fill.fee)
    return {
        "instrument_id": int(position["instrument_id"]),
        "symbol": position["symbol"],
        "side": position["side"],
        "close_side": close_side,
        "quantity": str(quantity),
        "exit_price": str(fill.average_price),
        "realized_gross_pnl": str(realized),
        "fee": str(fill.fee),
        "shortfall_bps": str(fill.shortfall_bps),
        "book_timestamp": book.get("timestamp"),
    }


def _open_position(
    client: PolymarketPublicClient,
    state: dict[str, Any],
    instrument: dict[str, Any],
    ticker: dict[str, Any],
    side: str,
    atr: Decimal,
    fee_rate: Decimal,
    now_ms: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mid = dec(ticker.get("mid_price"), dec(ticker.get("mark_price"), "0"))
    if mid <= 0:
        raise ValueError("No valid mid/mark price for opening")
    step = Decimal("1").scaleb(-int(instrument["quantity_decimals"]))
    min_notional = dec(instrument["min_notional"])
    max_notional = dec(instrument["max_market_notional"])
    nav = _nav(state, {int(instrument["instrument_id"]): ticker})
    max_qty = max_notional / mid
    quantity = target_quantity(
        nav,
        Decimal("0.5"),
        mid,
        step,
        Decimal("0"),
        min_notional,
        max_qty,
    )
    if quantity <= 0:
        raise ValueError("Target leg is below minimum notional or above market-size limits")
    opening_side = "buy" if side == "long" else "sell"
    fill, book = _current_orderbook_fill(
        client, instrument, opening_side, quantity, fee_rate
    )
    state["cash"] = str(dec(state["cash"]) - fill.fee)
    state["fees_paid"] = str(dec(state["fees_paid"]) + fill.fee)
    if side == "long":
        stop = fill.average_price - atr * STOP_ATR_MULTIPLE
        extreme = fill.average_price
    else:
        stop = fill.average_price + atr * STOP_ATR_MULTIPLE
        extreme = fill.average_price
    position = {
        "instrument_id": int(instrument["instrument_id"]),
        "symbol": str(instrument["symbol"]),
        "category": str(instrument.get("category") or "unknown"),
        "side": side,
        "quantity": str(fill.filled_quantity),
        "entry_price": str(fill.average_price),
        "entry_timestamp_ms": int(now_ms),
        "entry_fee": str(fill.fee),
        "last_mark_price": str(dec(ticker.get("mark_price"), fill.average_price)),
        "stop_price": str(stop),
        "highest_since_entry": str(extreme),
        "lowest_since_entry": str(extreme),
        "last_funding_timestamp_ms": int(now_ms),
        "unresolved_funding": [],
    }
    details = {
        "instrument_id": int(instrument["instrument_id"]),
        "symbol": instrument["symbol"],
        "category": instrument.get("category"),
        "side": side,
        "order_side": opening_side,
        "quantity": str(fill.filled_quantity),
        "entry_price": str(fill.average_price),
        "notional": str(fill.notional),
        "fee": str(fill.fee),
        "shortfall_bps": str(fill.shortfall_bps),
        "stop_price": str(stop),
        "book_timestamp": book.get("timestamp"),
    }
    return position, details


def _daily_candidates(
    active: list[dict[str, Any]],
    history: dict[int, list[dict[str, Any]]],
    tickers: dict[int, dict[str, Any]],
    fees: dict[str, Decimal],
    nav: Decimal,
) -> tuple[
    list[Any], list[Any], dict[str, dict[str, Any]], list[str],
    list[Any], list[Any],
]:
    observations: list[tuple[str, Any]] = []
    instruments_by_key: dict[str, dict[str, Any]] = {}
    execution_eligible: set[str] = set()
    exclusions: list[str] = []
    for instrument in active:
        iid = int(instrument["instrument_id"])
        rows = history.get(iid, [])
        if len(rows) < MIN_HISTORY_FOR_RANKING:
            exclusions.append(f"{iid}:INSUFFICIENT_HISTORY")
            continue
        ticker = tickers.get(iid)
        if ticker is None or dec(ticker.get("last_price")) <= 0:
            exclusions.append(f"{iid}:MISSING_TICKER")
            continue
        closes = [float(row["close"]) for row in rows]
        points = compute_q_series(closes)
        point = points[-1]
        if point.q is None:
            exclusions.append(f"{iid}:NO_VALID_Q")
            continue
        key = f"polymarket:{iid}"
        observations.append((key, point))
        instruments_by_key[key] = instrument
        category = str(instrument.get("category") or "unknown")
        if category not in fees:
            continue
        turnovers = sorted(
            dec(row["close"]) * dec(row["volume"])
            for row in rows[-30:]
            if dec(row["close"]) > 0 and dec(row["volume"]) > 0
        )
        if not turnovers:
            continue
        median_turnover = turnovers[len(turnovers) // 2]
        desired_leg = nav * Decimal("0.5")
        if desired_leg <= median_turnover * Decimal("0.001"):
            execution_eligible.add(key)
    research_long, research_short = rank_candidates(observations, threshold=2.0)
    executable_long, executable_short = rank_candidates(
        observations, threshold=2.0, execution_eligible=execution_eligible
    )
    return (
        research_long, research_short, instruments_by_key, exclusions,
        executable_long, executable_short,
    )


def _select_executable_pair(
    client: PolymarketPublicClient,
    longs: list[Any],
    shorts: list[Any],
    instruments_by_key: dict[str, dict[str, Any]],
    tickers: dict[int, dict[str, Any]],
    history: dict[int, list[dict[str, Any]]],
    fees: dict[str, Decimal],
    state: dict[str, Any],
    now_ms: int,
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]] | None:
    for long_candidate in longs[:10]:
        for short_candidate in shorts[:10]:
            if long_candidate.symbol == short_candidate.symbol:
                continue
            legs: list[tuple[Any, dict[str, Any], str]] = [
                (long_candidate, instruments_by_key[long_candidate.symbol], "long"),
                (short_candidate, instruments_by_key[short_candidate.symbol], "short"),
            ]
            trial_state = json.loads(json.dumps(state))
            new_positions: list[dict[str, Any]] = []
            fills: list[dict[str, Any]] = []
            try:
                for _, instrument, side in legs:
                    iid = int(instrument["instrument_id"])
                    rows = history.get(iid, [])
                    atr = _atr_for_history(rows)
                    if atr is None:
                        raise ValueError("ATR_NOT_READY")
                    fee = fees[str(instrument.get("category") or "unknown")]
                    position, detail = _open_position(
                        client, trial_state, instrument, tickers[iid],
                        side, atr, fee, now_ms,
                    )
                    new_positions.append(position)
                    fills.append(detail)
                return (long_candidate, new_positions, fills)
            except Exception:
                continue
    return None


def _market_snapshot_rows(
    instruments: list[dict[str, Any]],
    tickers: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for instrument in instruments:
        iid = int(instrument["instrument_id"])
        ticker = tickers.get(iid)
        if ticker is None:
            continue
        rows.append({
            "instrument_id": iid,
            "symbol": instrument["symbol"],
            "category": instrument.get("category"),
            "close_only": instrument.get("close_only") is True,
            "last_price": ticker.get("last_price"),
            "mark_price": ticker.get("mark_price"),
            "index_price": ticker.get("index_price"),
            "mid_price": ticker.get("mid_price"),
            "open_interest": ticker.get("open_interest"),
            "funding_rate": ticker.get("funding_rate"),
            "next_funding": ticker.get("next_funding"),
            "timestamp": ticker.get("timestamp"),
            "open_price": ticker.get("open_price"),
            "volume_24h": ticker.get("volume_24h"),
        })
    return rows


def _qualify_first_provider() -> dict[str, Any]:
    probe_path = Path(__file__).resolve().with_name("probe_polymarket_mexc_bitget.py")
    spec = importlib.util.spec_from_file_location("perps_priority_probe", probe_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the ordered Perps API qualification")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    exit_code = module.main()
    report_path = Path(module.ROOT) / "exchange-priority-report.json"
    if not report_path.exists():
        raise RuntimeError("Ordered public Perps qualification did not produce a report")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    selected = report.get("selected_exchange")
    if exit_code != 0 or selected is None:
        raise RuntimeError("No provider passed the ordered public Perps API qualification")
    if selected != "polymarket":
        raise RuntimeError(
            f"The first passing provider is {selected}; its full paper-cycle adapter "
            "must be implemented before this Polymarket-specific cycle can run."
        )
    return report


def _run() -> int:
    data_dir = Path(os.environ.get("MARKET_DATA_DIR", "market-data"))
    state_dir = Path(os.environ.get("PAPER_STATE_DIR", "state"))
    store = MarketDataStore(data_dir)
    client = PolymarketPublicClient()
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    if store.manifest.get("selected_provider") is None:
        qualification = _qualify_first_provider()
        store.manifest["selected_provider"] = "polymarket"
        store.manifest["qualification_report"] = qualification
        store.save_manifest(now_ms)
    elif store.manifest.get("selected_provider") != "polymarket":
        raise RuntimeError("Market-data branch contains an unsupported selected provider")

    instruments = client.instruments()
    cross = [row for row in instruments if is_cross_margin_instrument(row)]
    new_entry = [row for row in cross if is_new_position_eligible(row)]
    invalid = {
        str(row["instrument_id"]): validate_instrument(row)
        for row in cross if validate_instrument(row)
    }
    if invalid:
        raise RuntimeError(
            f"Active cross-margin instrument metadata invalid: "
            f"{list(invalid.items())[:10]}"
        )

    ticker_rows, _statistics = client.tickers()
    ticker_map = _rows_by_id(ticker_rows)
    if len(ticker_map) != len(ticker_rows):
        raise RuntimeError("Bulk ticker response has duplicate or invalid instrument IDs")
    missing_tickers = [
        int(row["instrument_id"]) for row in new_entry
        if int(row["instrument_id"]) not in ticker_map
    ]
    timestamp_values = [
        int(row["timestamp"])
        for row in ticker_rows
        if isinstance(row.get("timestamp"), int)
        and not isinstance(row.get("timestamp"), bool)
    ]
    server_ms = max(timestamp_values) if timestamp_values else now_ms
    latest_completed_bar_ms = _latest_completed_bar(server_ms)

    lifecycle_counts = store.sync_universe(instruments, server_ms)
    snapshot_path = store.save_snapshot(server_ms, _market_snapshot_rows(cross, ticker_map))

    pending_bootstrap = [
        row for row in new_entry
        if not store.manifest["instruments"][str(row["instrument_id"])].get("bootstrap_complete")
    ]
    batch_size = max(1, min(500, int(os.environ.get("BOOTSTRAP_BATCH_SIZE", "150"))))
    pending_bootstrap = pending_bootstrap[:batch_size]
    candle_updates: list[dict[str, Any]] = []
    bootstrap_completed = 0
    api_failures: list[dict[str, Any]] = []
    bootstrapped_this_run: set[int] = set()

    for instrument in pending_bootstrap:
        iid = int(instrument["instrument_id"])
        try:
            start_ms = max(0, server_ms - BOOTSTRAP_DAYS * DAY_MS)
            candles = client.candles(
                iid, start_timestamp=start_ms, end_timestamp=server_ms, interval="1d"
            )
            completed = _complete_candles(instrument, candles, server_ms)
            candle_updates.extend(completed)
            state_row = store.manifest["instruments"][str(iid)]
            state_row["bootstrap_complete"] = True
            bootstrapped_this_run.add(iid)
            state_row["history_status"] = (
                "AVAILABLE" if len(completed) >= MIN_HISTORY_FOR_RANKING
                else "INSUFFICIENT_HISTORY"
            )
            bootstrap_completed += 1
        except Exception as exc:
            api_failures.append({
                "instrument_id": iid,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            })

    for instrument in new_entry:
        iid = int(instrument["instrument_id"])
        state_row = store.manifest["instruments"][str(iid)]
        if not state_row.get("bootstrap_complete") or iid in bootstrapped_this_run:
            continue
        last_ts = state_row.get("last_candle_timestamp_ms")
        if last_ts is not None and int(last_ts) >= latest_completed_bar_ms:
            continue
        start_ms = (
            int(last_ts) + DAY_MS if last_ts is not None
            else max(0, server_ms - BOOTSTRAP_DAYS * DAY_MS)
        )
        try:
            candles = client.candles(
                iid, start_timestamp=start_ms, end_timestamp=server_ms, interval="1d"
            )
            candle_updates.extend(_complete_candles(instrument, candles, server_ms))
        except Exception as exc:
            api_failures.append({
                "instrument_id": iid,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            })

    if candle_updates:
        store.append_candles(candle_updates)

    # The manifest cursor is advanced only after the daily partition writes complete.
    history = store.load_all_candles(
        start_timestamp_ms=max(0, server_ms - BOOTSTRAP_DAYS * DAY_MS)
    )
    for instrument in new_entry:
        iid = int(instrument["instrument_id"])
        rows = history.get(iid, [])
        state_row = store.manifest["instruments"][str(iid)]
        if rows:
            latest_ts = int(rows[-1]["timestamp_ms"])
            state_row["last_candle_timestamp_ms"] = latest_ts
            state_row["history_status"] = (
                "AVAILABLE" if len(rows) >= MIN_HISTORY_FOR_RANKING
                else "INSUFFICIENT_HISTORY"
            )

    fee_payload = client.fees()
    fees = _fee_rates(fee_payload)
    missing_fee_categories = sorted(
        {str(row.get("category") or "unknown") for row in new_entry} - set(fees)
    )
    missing_latest_bar = [
        int(row["instrument_id"])
        for row in new_entry
        if (
            store.manifest["instruments"][str(row["instrument_id"])].get("last_candle_timestamp_ms")
            is not None
            and int(
                store.manifest["instruments"][str(row["instrument_id"])].get(
                    "last_candle_timestamp_ms"
                )
            ) < latest_completed_bar_ms
            and store.manifest["instruments"][str(row["instrument_id"])].get("history_status")
            != "INSUFFICIENT_HISTORY"
        )
    ]
    latest_coverage_pass = (
        not api_failures
        and not missing_latest_bar
        and len(missing_tickers) == 0
        and all(
            store.manifest["instruments"][str(row["instrument_id"])].get("bootstrap_complete")
            for row in new_entry
        )
    )

    state_from_events, _ = _load_state_from_event_branch(state_dir)
    projection = store.load_projection()
    portfolio = state_from_events or (
        projection.get("portfolio_state") if projection else None
    ) or {
        "schema_version": 1,
        "account_id": ACCOUNT_ID,
        "strategy_id": STRATEGY_ID,
        "currency": "pUSD",
        "initial_capital": str(INITIAL_CAPITAL),
        "cash": str(INITIAL_CAPITAL),
        "realized_gross_pnl": "0",
        "fees_paid": "0",
        "confirmed_funding": "0",
        "positions": [],
        "last_processed_daily_bar_ms": None,
        "last_snapshot_ms": None,
        "unresolved_funding_count": 0,
        "status": "INITIALIZED_PAPER_ONLY",
    }

    state_changed = False
    stop_events: list[dict[str, Any]] = []
    trailing_updates: list[dict[str, Any]] = []
    mark_failures: list[int] = []
    for position in list(portfolio.get("positions", [])):
        iid = int(position["instrument_id"])
        ticker = ticker_map.get(iid)
        instrument = next((row for row in cross if int(row["instrument_id"]) == iid), None)
        if ticker is None or instrument is None:
            mark_failures.append(iid)
            continue
        mark = dec(ticker.get("mark_price"), position.get("last_mark_price", "0"))
        last = dec(ticker.get("last_price"), str(mark))
        position["last_mark_price"] = str(mark)
        last_trailing_bar = position.get("last_trailing_bar_ms")
        if (
            latest_completed_bar_ms > int(last_trailing_bar or 0)
            and latest_completed_bar_ms > int(position["entry_timestamp_ms"])
        ):
            series = history.get(iid, [])
            bar = next(
                (
                    item for item in series
                    if int(item["timestamp_ms"]) == latest_completed_bar_ms
                ),
                None,
            )
            atr = _atr_for_history(series)
            if bar is not None and atr is not None:
                high = dec(bar["high"])
                low = dec(bar["low"])
                if position["side"] == "long":
                    extreme = max(dec(position["highest_since_entry"]), high)
                    proposed = extreme - atr * STOP_ATR_MULTIPLE
                    stop = max(dec(position["stop_price"]), proposed)
                    position["highest_since_entry"] = str(extreme)
                else:
                    extreme = min(dec(position["lowest_since_entry"]), low)
                    proposed = extreme + atr * STOP_ATR_MULTIPLE
                    stop = min(dec(position["stop_price"]), proposed)
                    position["lowest_since_entry"] = str(extreme)
                position["stop_price"] = str(stop)
                position["last_trailing_bar_ms"] = latest_completed_bar_ms
                trailing_updates.append({
                    "instrument_id": iid,
                    "daily_bar_timestamp_ms": latest_completed_bar_ms,
                    "atr14": str(atr),
                    "stop_price": str(stop),
                })
        stop = dec(position.get("stop_price"))
        triggered = (
            position["side"] == "long" and stop > 0 and last <= stop
        ) or (
            position["side"] == "short" and stop > 0 and last >= stop
        )
        if triggered:
            category = str(instrument.get("category") or "unknown")
            fee_rate = fees.get(category)
            if fee_rate is None:
                mark_failures.append(iid)
                continue
            try:
                details = _close_position(
                    client, portfolio, position, instrument, fee_rate
                )
                portfolio["positions"] = [
                    item for item in portfolio["positions"]
                    if int(item["instrument_id"]) != iid
                ]
                stop_events.append(details)
                state_changed = True
            except Exception as exc:
                position["stop_triggered_unfilled"] = True
                position["stop_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
                mark_failures.append(iid)

    funding_events: list[dict[str, Any]] = []
    unresolved_funding = 0
    for position in list(portfolio.get("positions", [])):
        iid = int(position["instrument_id"])
        start_ms = int(position.get("last_funding_timestamp_ms", position["entry_timestamp_ms"]))
        try:
            observations = client.funding_history(
                iid,
                start_timestamp=start_ms + 1,
                end_timestamp=server_ms,
            )
        except Exception:
            unresolved_funding += 1
            continue
        for record in sorted(observations, key=lambda item: int(item.get("timestamp", 0))):
            funding_ts = int(record.get("timestamp", 0))
            if funding_ts <= start_ms:
                continue
            matched = store.find_snapshot_mark(iid, funding_ts)
            if matched is None:
                unresolved_funding += 1
                continue
            mark = dec(matched[1])
            rate = dec(record.get("funding_rate"))
            cashflow = funding_cashflow(
                str(position["side"]),
                dec(position["quantity"]),
                mark,
                rate,
            )
            portfolio["cash"] = str(dec(portfolio["cash"]) + cashflow)
            portfolio["confirmed_funding"] = str(
                dec(portfolio["confirmed_funding"]) + cashflow
            )
            position["last_funding_timestamp_ms"] = funding_ts
            funding_events.append({
                "instrument_id": iid,
                "funding_timestamp_ms": funding_ts,
                "funding_rate": str(rate),
                "settlement_mark_price": str(mark),
                "snapshot_timestamp_ms": matched[0],
                "funding_cashflow_pusd": str(cashflow),
            })
            state_changed = True
        position["unresolved_funding_count"] = unresolved_funding

    research_longs: list[Any] = []
    research_shorts: list[Any] = []
    exec_longs: list[Any] = []
    exec_shorts: list[Any] = []
    instrument_by_key: dict[str, dict[str, Any]] = {}
    exclusions: list[str] = []
    fills: list[dict[str, Any]] = []
    daily_event_published: dict[str, Any] | None = None
    decision_status = "NO_NEW_COMPLETED_DAILY_BAR"

    last_processed = portfolio.get("last_processed_daily_bar_ms")
    new_daily_bar = (
        latest_coverage_pass
        and (last_processed is None or latest_completed_bar_ms > int(last_processed))
    )
    if new_daily_bar:
        (
            research_longs, research_shorts, instrument_by_key, exclusions,
            exec_longs, exec_shorts,
        ) = _daily_candidates(new_entry, history, ticker_map, fees, _nav(portfolio, ticker_map))
        pair_try = _select_executable_pair(
            client, exec_longs, exec_shorts, instrument_by_key,
            ticker_map, history, fees, portfolio, server_ms,
        ) if exec_longs and exec_shorts else None

        old_positions = list(portfolio.get("positions", []))
        old_pair = {
            (int(p["instrument_id"]), str(p["side"])) for p in old_positions
        }
        new_pair_ids: set[tuple[int, str]] = set()
        if pair_try is not None:
            _, new_positions, fills = pair_try
            new_pair_ids = {
                (int(p["instrument_id"]), str(p["side"])) for p in new_positions
            }
        if new_pair_ids == old_pair and old_positions:
            decision_status = "PAIR_HELD"
        else:
            simulated_closed: list[dict[str, Any]] = []
            trial_state = json.loads(json.dumps(portfolio))
            close_ok = True
            for position in old_positions:
                instrument = next(
                    (
                        row for row in cross
                        if int(row["instrument_id"]) == int(position["instrument_id"])
                    ),
                    None,
                )
                if instrument is None:
                    close_ok = False
                    break
                fee_rate = fees.get(str(instrument.get("category") or "unknown"))
                if fee_rate is None:
                    close_ok = False
                    break
                try:
                    simulated_closed.append(
                        _close_position(client, trial_state, position, instrument, fee_rate)
                    )
                except Exception:
                    close_ok = False
                    break
            if close_ok and pair_try is not None:
                _, new_positions, entry_details = pair_try
                # Apply the two entry fees once, after all new fills are verified.
                entry_fees = sum(
                    (dec(item.get("fee")) for item in entry_details),
                    Decimal("0"),
                )
                trial_state["cash"] = str(dec(trial_state["cash"]) - entry_fees)
                trial_state["fees_paid"] = str(dec(trial_state["fees_paid"]) + entry_fees)
                trial_state["positions"] = new_positions
                portfolio = trial_state
                fills = simulated_closed + entry_details
                decision_status = "PAIR_OPENED_OR_REPLACED"
                state_changed = True
            elif close_ok and pair_try is None:
                trial_state["positions"] = []
                portfolio = trial_state
                fills = simulated_closed
                decision_status = "FLAT_NO_EXECUTABLE_PAIR"
                state_changed = True
            else:
                decision_status = "REBALANCE_BLOCKED_BY_EXIT_BOOK_OR_METADATA"
        if decision_status in {
            "PAIR_HELD", "PAIR_OPENED_OR_REPLACED", "FLAT_NO_EXECUTABLE_PAIR"
        }:
            portfolio["last_processed_daily_bar_ms"] = int(latest_completed_bar_ms)
            state_changed = True

    nav = _nav(portfolio, ticker_map)
    positions = portfolio.get("positions", [])
    notionals = []
    for position in positions:
        ticker = ticker_map.get(int(position["instrument_id"]), {})
        mark = ticker.get("mark_price", position["entry_price"])
        notionals.append(dec(position["quantity"]) * dec(mark))
    long_notional = sum(
        (
            notional for position, notional in zip(positions, notionals, strict=True)
            if position["side"] == "long"
        ),
        Decimal("0"),
    )
    short_notional = sum(
        (
            notional for position, notional in zip(positions, notionals, strict=True)
            if position["side"] == "short"
        ),
        Decimal("0"),
    )
    exposure = portfolio_exposure(nav, long_notional, short_notional) if nav > 0 else {
        "gross_exposure": Decimal("0"),
        "net_exposure": Decimal("0"),
        "dollar_neutrality_imbalance": Decimal("0"),
    }
    portfolio["last_snapshot_ms"] = int(server_ms)
    portfolio["unresolved_funding_count"] = int(unresolved_funding)
    portfolio["status"] = (
        "ACTIVE_PAPER" if positions else "FLAT_PAPER"
    )

    if new_daily_bar and state_changed:
        details = {
            "daily_bar_timestamp_ms": int(latest_completed_bar_ms),
            "decision_status": decision_status,
            "research_long_top": [
                {"symbol": item.symbol, "q": str(item.q)}
                for item in research_longs[:10]
            ],
            "research_short_top": [
                {"symbol": item.symbol, "q": str(item.q)}
                for item in research_shorts[:10]
            ],
            "execution_long_top": [
                {"symbol": item.symbol, "q": str(item.q)}
                for item in exec_longs[:10]
            ],
            "execution_short_top": [
                {"symbol": item.symbol, "q": str(item.q)}
                for item in exec_shorts[:10]
            ],
            "fills": fills,
            "excluded_or_unranked_sample": exclusions[:30],
            "nav_pusd": str(nav),
            "gross_exposure": str(exposure["gross_exposure"]),
            "net_exposure": str(exposure["net_exposure"]),
            "dollar_neutrality_imbalance": str(exposure["dollar_neutrality_imbalance"]),
            "active_cross_margin_universe_count": len(new_entry),
            "missing_latest_bar_count": len(missing_latest_bar),
            "api_failure_count": len(api_failures),
            "unresolved_funding_count": unresolved_funding,
        }
        daily_event_published = _publish_state_event(
            state_dir,
            server_ms,
            f"daily-{latest_completed_bar_ms}",
            f"daily-decision-{latest_completed_bar_ms}",
            "daily_portfolio_decision",
            portfolio,
            details,
        )
    elif stop_events or funding_events or trailing_updates:
        details = {
            "stop_exits": stop_events,
            "trailing_stop_updates": trailing_updates,
            "funding_events": funding_events,
            "nav_pusd": str(nav),
        }
        daily_event_published = _publish_state_event(
            state_dir,
            server_ms,
            f"risk-{server_ms}",
            f"risk-update-{server_ms}",
            "paper_risk_update",
            portfolio,
            details,
        )

    store.manifest["last_processed_daily_bar_ms"] = portfolio.get("last_processed_daily_bar_ms")
    store.manifest["bootstrap_complete"] = all(
        store.manifest["instruments"][str(row["instrument_id"])].get("bootstrap_complete")
        for row in new_entry
    )
    store.save_manifest(server_ms)
    store.save_projection({
        "schema_version": 1,
        "portfolio_state": portfolio,
        "last_run_utc": datetime.fromtimestamp(server_ms / 1000, tz=UTC).isoformat(),
    })
    store.prune_snapshots(server_ms)

    report = {
        "run_utc": datetime.now(UTC).isoformat(),
        "provider": "polymarket",
        "mode": "PUBLIC_DATA_PAPER_ONLY",
        "instruments_total": len(instruments),
        "cross_margin_universe": len(cross),
        "new_position_eligible": len(new_entry),
        "lifecycle_counts": lifecycle_counts,
        "ticker_coverage": len(ticker_map),
        "missing_ticker_count": len(missing_tickers),
        "missing_ticker_sample": missing_tickers[:20],
        "bootstrap_completed_this_run": bootstrap_completed,
        "bootstrap_remaining": sum(
            not store.manifest["instruments"][str(row["instrument_id"])].get("bootstrap_complete")
            for row in new_entry
        ),
        "candle_rows_added": len(candle_updates),
        "latest_completed_bar_ms": latest_completed_bar_ms,
        "last_processed_daily_bar_ms": portfolio.get("last_processed_daily_bar_ms"),
        "new_daily_bar": new_daily_bar,
        "daily_decision_status": decision_status,
        "api_failure_count": len(api_failures),
        "api_failure_sample": api_failures[:10],
        "missing_latest_bar_count": len(missing_latest_bar),
        "missing_fee_categories": missing_fee_categories,
        "mark_failures": mark_failures,
        "latest_universe_coverage_pass": latest_coverage_pass,
        "stop_events": stop_events,
        "trailing_stop_updates": trailing_updates,
        "funding_events": funding_events,
        "unresolved_funding_count": unresolved_funding,
        "portfolio": {
            "currency": "pUSD",
            "cash": portfolio["cash"],
            "nav": str(nav),
            "realized_gross_pnl": portfolio["realized_gross_pnl"],
            "fees_paid": portfolio["fees_paid"],
            "confirmed_funding": portfolio["confirmed_funding"],
            "positions": positions,
            "gross_exposure": str(exposure["gross_exposure"]),
            "net_exposure": str(exposure["net_exposure"]),
            "dollar_neutrality_imbalance": str(exposure["dollar_neutrality_imbalance"]),
            "status": portfolio["status"],
        },
        "state_event": daily_event_published,
        "snapshot_partition": str(snapshot_path),
        "paper_account_initialized": bool(portfolio.get("last_processed_daily_bar_ms")),
        "orders_submitted": 0,
        "credentials_used": False,
    }
    report_path = data_dir / "data" / "reports" / "latest_cycle.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    store.save_manifest(server_ms)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_run())
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {str(exc)[:800]}",
            "orders_submitted": 0,
            "credentials_used": False,
        }, indent=2))
        raise SystemExit(1) from exc

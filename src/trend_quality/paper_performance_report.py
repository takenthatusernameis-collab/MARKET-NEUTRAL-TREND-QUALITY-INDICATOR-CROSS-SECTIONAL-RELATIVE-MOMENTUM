"""Standalone MEXC paper-account report rebuilt from the verified event chain."""
from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .event_journal import order_event_batches, verify_event_batch
from .mexc_portfolio import performance_summary

ACCOUNT_ID = "mexc-usdt-forward-50usdt-v3"
STRATEGY_ID = "trend-quality-daily-cross-sectional-v3-50usdt"
ZERO = Decimal("0")
ONE = Decimal("1")


def _decimal(value: object, default: str = "0") -> Decimal:
    try:
        result = Decimal(str(default if value is None else value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)
    return result if result.is_finite() else Decimal(default)


def _utc(timestamp_ms: object) -> str:
    try:
        stamp = int(timestamp_ms)
    except (TypeError, ValueError):
        return "—"
    if stamp <= 0:
        return "—"
    return datetime.fromtimestamp(stamp / 1000, tz=UTC).strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )[:-3] + " UTC"


def _utc_day_start(timestamp_ms: int) -> int:
    value = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    return int(value.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)


def _cell(value: object) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", r"\|").replace("\n", " ")


def _money(value: object) -> str:
    return f"{_decimal(value):,.8f}"


def _percent(value: Decimal | None) -> str:
    return "Unavailable" if value is None else f"{value * Decimal('100'):+.4f}%"


def _load_verified_batches(state_dir: Path) -> list[dict[str, Any]]:
    paths = sorted((state_dir / "events").glob("**/*.json"))
    if not paths:
        raise ValueError(f"No paper-state event batches found under {state_dir / 'events'}")
    batches: list[dict[str, Any]] = []
    for path in paths:
        try:
            batch = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read paper-state event batch {path}: {exc}") from exc
        if not isinstance(batch, dict) or not verify_event_batch(batch):
            raise ValueError(f"Invalid immutable paper event batch: {path}")
        batches.append(batch)
    return order_event_batches(batches)


def _position_key(position: dict[str, Any]) -> tuple[int, str]:
    return int(position["instrument_id"]), str(position["side"])


def _action(item: dict[str, Any]) -> str | None:
    value = item.get("action")
    if isinstance(value, str) and value:
        value = value.upper()
        return "CLOSED" if value in {"CLOSE", "EXIT", "STOP_EXIT"} else value
    if item.get("exit_timestamp_ms") is not None or item.get("net_trade_pnl") is not None:
        return "CLOSED"
    if item.get("quantity_delta") is not None:
        return "INCREASED" if _decimal(item["quantity_delta"]) > ZERO else "REDUCED"
    if item.get("entry_timestamp_ms") is not None:
        return "OPENED"
    if item.get("side") in {"long", "short"} and item.get("entry_price") is not None:
        return "OPENED"
    return None


def _history_row(
    item: dict[str, Any],
    event: dict[str, Any],
    symbols: dict[int, str],
    action: str,
    source: str,
) -> dict[str, Any]:
    raw_iid = item.get("instrument_id")
    try:
        iid = int(raw_iid) if raw_iid is not None else None
    except (TypeError, ValueError):
        iid = None
    timestamp = (
        item.get("exit_timestamp_ms")
        or item.get("entry_timestamp_ms")
        or item.get("funding_timestamp_ms")
        or item.get("timestamp_ms")
        or event.get("occurred_at_ms")
    )
    quantity = (
        item.get("quantity_delta")
        if item.get("quantity_delta") is not None
        else item.get("quantity")
        if item.get("quantity") is not None
        else item.get("quantity_base")
        if item.get("quantity_base") is not None
        else item.get("filled_quantity")
        if item.get("filled_quantity") is not None
        else item.get("new_quantity")
    )
    price = (
        item.get("fill_price")
        or item.get("exit_price")
        or item.get("average_price")
        or item.get("entry_price")
        or item.get("settlement_mark_price")
    )
    fee = sum(
        (_decimal(item.get(key)) for key in ("fee", "fee_usdt", "entry_fee", "exit_fee")),
        ZERO,
    )
    net_pnl = (
        item.get("net_trade_pnl")
        if item.get("net_trade_pnl") is not None
        else item.get("partial_realized_net_pnl")
    )
    return {
        "timestamp_ms": int(timestamp),
        "action": action,
        "symbol": str(item.get("symbol") or symbols.get(iid or -1) or (
            f"instrument {iid}" if iid is not None else "Portfolio"
        )),
        "side": item.get("side"),
        "quantity": None if quantity is None else str(quantity),
        "price": None if price is None else str(price),
        "fees": str(fee) if fee else None,
        "net_pnl": None if net_pnl is None else str(net_pnl),
        "gross_pnl": (
            None if item.get("realized_gross_pnl") is None
            else str(item["realized_gross_pnl"])
        ),
        "funding": (
            None if item.get("cashflow_usdt") is None
            else str(item["cashflow_usdt"])
        ),
        "note": f"{source}; {event.get('event_type', 'unknown')}",
        "event_id": str(event.get("event_id", "")),
    }


def _transition_row(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    event: dict[str, Any],
    action: str,
) -> dict[str, Any]:
    position = after if after is not None else before
    if position is None:
        raise ValueError("Position transition has no source position")
    old_qty = ZERO if before is None else _decimal(before.get("quantity"))
    new_qty = ZERO if after is None else _decimal(after.get("quantity"))
    quantity = (
        new_qty if action == "OPENED"
        else old_qty if action == "CLOSED"
        else new_qty - old_qty
    )
    old_fee = ZERO if before is None else _decimal(before.get("entry_fee"))
    new_fee = ZERO if after is None else _decimal(after.get("entry_fee"))
    fee_delta = new_fee - old_fee
    return {
        "timestamp_ms": int(
            (position.get("entry_timestamp_ms") if action == "OPENED" else None)
            or event.get("occurred_at_ms")
        ),
        "action": action,
        "symbol": str(position.get("symbol", "unknown")),
        "side": position.get("side"),
        "quantity": str(quantity),
        "price": str(position.get("entry_price")) if action in {"OPENED", "INCREASED"} else None,
        "fees": str(fee_delta) if fee_delta else None,
        "net_pnl": None,
        "gross_pnl": None,
        "funding": None,
        "note": (
            "Derived from consecutive persisted account states; exact fill price and P&L "
            "were not present in this event."
        ),
        "event_id": str(event.get("event_id", "")),
    }


def _collect_history(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    symbols: dict[int, str] = {}
    for event in events:
        payload = event.get("payload", {})
        state = payload.get("portfolio_state", {}) if isinstance(payload, dict) else {}
        if isinstance(state, dict):
            for position in state.get("positions", []) or []:
                if isinstance(position, dict) and position.get("instrument_id") is not None:
                    symbols[int(position["instrument_id"])] = str(position.get("symbol", ""))
        details = payload.get("details", {}) if isinstance(payload, dict) else {}
        if isinstance(details, dict):
            for field in ("fills", "stop_exits", "emergency_exits", "funding_events"):
                for item in details.get(field, []) or []:
                    if isinstance(item, dict) and item.get("instrument_id") is not None:
                        try:
                            symbols[int(item["instrument_id"])] = str(item.get("symbol") or "")
                        except (TypeError, ValueError):
                            pass

    history: list[dict[str, Any]] = []
    prior: dict[tuple[int, str], dict[str, Any]] = {}
    sequence = 0

    def add(row: dict[str, Any]) -> None:
        nonlocal sequence
        row["sequence"] = sequence
        sequence += 1
        history.append(row)

    for event in events:
        payload = event.get("payload", {})
        details = payload.get("details", {}) if isinstance(payload, dict) else {}
        details = details if isinstance(details, dict) else {}
        explicit: list[dict[str, Any]] = []
        for field, fallback in (
            ("fills", None),
            ("stop_exits", "CLOSED"),
            ("emergency_exits", "CLOSED"),
        ):
            for item in details.get(field, []) or []:
                if not isinstance(item, dict):
                    continue
                action = _action(item) or fallback
                if action in {"OPENED", "INCREASED", "REDUCED", "CLOSED"}:
                    explicit.append(_history_row(item, event, symbols, action, field))
        retry = details.get("entry_retry")
        if isinstance(retry, dict):
            for item in retry.get("fills", []) or []:
                if not isinstance(item, dict):
                    continue
                action = _action(item)
                if action in {"OPENED", "INCREASED", "REDUCED", "CLOSED"}:
                    explicit.append(_history_row(item, event, symbols, action, "entry_retry"))

        state = payload.get("portfolio_state") if isinstance(payload, dict) else None
        after: dict[tuple[int, str], dict[str, Any]] = {}
        if isinstance(state, dict):
            for position in state.get("positions", []) or []:
                if isinstance(position, dict) and position.get("instrument_id") is not None:
                    after[_position_key(position)] = position

        transitions: list[
            tuple[tuple[int, str], str, dict[str, Any] | None, dict[str, Any] | None]
        ] = []
        for key in sorted(set(prior) | set(after)):
            old = prior.get(key)
            new = after.get(key)
            if old is None and new is not None:
                transitions.append((key, "OPENED", old, new))
            elif old is not None and new is None:
                transitions.append((key, "CLOSED", old, new))
            elif old is not None and new is not None:
                old_qty = _decimal(old.get("quantity"))
                new_qty = _decimal(new.get("quantity"))
                if new_qty > old_qty:
                    transitions.append((key, "INCREASED", old, new))
                elif new_qty < old_qty:
                    transitions.append((key, "REDUCED", old, new))

        for _key, action, old, new in transitions:
            symbol = (new or old or {}).get("symbol")
            match = next(
                (
                    index for index, row in enumerate(explicit)
                    if row.get("symbol") == symbol and row.get("action") == action
                ),
                None,
            )
            if match is None:
                add(_transition_row(old, new, event, action))
            else:
                add(explicit.pop(match))
        for row in explicit:
            add(row)

        for item in details.get("funding_events", []) or []:
            if isinstance(item, dict):
                add(_history_row(item, event, symbols, "FUNDING", "funding_events"))

        resets: list[dict[str, Any]] = []
        if isinstance(details.get("portfolio_daily_risk_reset"), dict):
            resets.append(details["portfolio_daily_risk_reset"])
        if isinstance(retry, dict) and isinstance(retry.get("risk_window_reset"), dict):
            resets.append(retry["risk_window_reset"])
        for reset in resets:
            add({
                "timestamp_ms": int(
                    reset.get("risk_window_reset_at_ms")
                    or reset.get("timestamp_ms")
                    or event.get("occurred_at_ms")
                ),
                "action": "RISK WINDOW RESET",
                "symbol": "Portfolio",
                "side": None,
                "quantity": None,
                "price": reset.get("starting_nav"),
                "fees": None,
                "net_pnl": None,
                "gross_pnl": None,
                "funding": None,
                "note": str(
                    reset.get("risk_window_reset_reason")
                    or reset.get("reference")
                    or "New risk session"
                ),
                "event_id": str(event.get("event_id", "")),
            })
        if isinstance(state, dict):
            prior = after

    history.sort(key=lambda row: (int(row["timestamp_ms"]), int(row["sequence"])))
    return history


def _equity_sessions(
    events: list[dict[str, Any]],
    latest_state: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[int, Decimal]]:
    points: dict[int, dict[str, Any]] = {}
    sessions: dict[int, int] = {}
    baselines: dict[int, Decimal] = {}
    for event in events:
        payload = event.get("payload", {})
        state = payload.get("portfolio_state", {}) if isinstance(payload, dict) else {}
        if not isinstance(state, dict):
            continue
        risk = state.get("daily_risk", {})
        risk = risk if isinstance(risk, dict) else {}
        try:
            session_start = int(risk.get("starting_timestamp_ms") or 0)
        except (TypeError, ValueError):
            session_start = 0
        if session_start > 0 and risk.get("starting_nav") is not None:
            baselines[session_start] = _decimal(risk["starting_nav"])
        for row in state.get("equity_curve", []) or []:
            if not isinstance(row, dict) or row.get("timestamp_ms") is None:
                continue
            stamp = int(row["timestamp_ms"])
            points[stamp] = dict(row)
            if session_start > 0 and stamp >= session_start:
                sessions[stamp] = session_start
            elif stamp not in sessions:
                sessions[stamp] = _utc_day_start(stamp)
                baselines.setdefault(sessions[stamp], _decimal(row.get("nav")))

    if not points and latest_state.get("equity_curve"):
        for row in latest_state["equity_curve"]:
            stamp = int(row["timestamp_ms"])
            points[stamp] = dict(row)
            sessions[stamp] = _utc_day_start(stamp)
            baselines.setdefault(sessions[stamp], _decimal(row.get("nav")))

    ordered = []
    for stamp in sorted(points):
        row = points[stamp]
        row["timestamp_ms"] = stamp
        row["session_start_ms"] = sessions.get(stamp, _utc_day_start(stamp))
        ordered.append(row)
    return ordered, baselines


def _drawdown(
    points: list[dict[str, Any]],
    baseline: Decimal,
    baseline_timestamp: int | None = None,
) -> dict[str, Any]:
    peak = baseline
    peak_time = baseline_timestamp
    worst = ZERO
    worst_peak_time = baseline_timestamp
    trough_time: int | None = None
    trough_nav: Decimal | None = None
    for row in points:
        nav = _decimal(row.get("nav"))
        stamp = int(row["timestamp_ms"])
        if nav > peak:
            peak = nav
            peak_time = stamp
        if peak > ZERO:
            dd = nav / peak - ONE
            if dd < worst:
                worst = dd
                worst_peak_time = peak_time
                trough_time = stamp
                trough_nav = nav
    return {
        "max_drawdown": worst,
        "peak_timestamp_ms": worst_peak_time,
        "trough_timestamp_ms": trough_time,
        "trough_nav": trough_nav,
        "last_nav": _decimal(points[-1]["nav"]) if points else baseline,
        "observations": len(points),
    }


def _equity_curve_svg(
    points: list[dict[str, Any]],
    initial_capital: Decimal,
) -> str:
    """Render SVG from the same persisted NAV marks used by the report."""
    width, height = 1120, 430
    left, right, top, bottom = 96, 34, 88, 72
    plot_right = width - right
    plot_bottom = height - bottom
    plot_width = plot_right - left
    plot_height = plot_bottom - top
    values = [_decimal(point.get("nav")) for point in points]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="equity-title equity-desc">',
        '<title id="equity-title">Trend-Quality paper portfolio equity curve</title>',
        '<desc id="equity-desc">USDT net asset value from persisted mark-to-market observations, '
        'with an initial-capital reference line.</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<g font-family="Arial, sans-serif" fill="#222">',
        f'<text x="{width / 2:.0f}" y="27" text-anchor="middle" font-size="20" font-weight="bold">'
        'Trend-Quality Paper Portfolio — Equity Curve</text>',
        f'<text x="{width / 2:.0f}" y="50" text-anchor="middle" font-size="12" fill="#666">'
        'USDT net asset value · persisted mark-to-market observations · paper only</text>',
    ]

    if not values:
        parts.append(
            f'<text x="{width / 2:.0f}" y="{height / 2:.0f}" text-anchor="middle" '
            'font-size="18" fill="#666">Waiting for the first paper equity observation</text>'
        )
        parts.extend(["</g></svg>", ""])
        return "".join(parts)

    reference = initial_capital if initial_capital > ZERO else values[0]
    bounds = values + ([reference] if reference > ZERO else [])
    low, high = min(bounds), max(bounds)
    spread = high - low
    padding = max(spread * Decimal("0.12"), abs(reference) * Decimal("0.001"), Decimal("0.01"))
    low -= padding
    high += padding
    if high <= low:
        high = low + Decimal("1")

    first_timestamp = int(points[0]["timestamp_ms"])
    last_timestamp = int(points[-1]["timestamp_ms"])
    elapsed = max(0, last_timestamp - first_timestamp)

    def x_position(timestamp_ms: int) -> float:
        if elapsed == 0:
            return left + plot_width / 2
        return left + (timestamp_ms - first_timestamp) / elapsed * plot_width

    def y_position(value: Decimal) -> float:
        return top + float((high - value) / (high - low)) * plot_height

    # For long histories, retain bucket extrema so drawdowns remain visible.
    plotted = list(enumerate(zip(points, values, strict=True)))
    max_points = 1200
    if len(plotted) > max_points:
        bucket_size = max(1, (len(plotted) - 2) // ((max_points // 2) - 1))
        retained = {0, len(plotted) - 1}
        for bucket_start in range(1, len(plotted) - 1, bucket_size):
            bucket_end = min(len(plotted) - 1, bucket_start + bucket_size)
            bucket = plotted[bucket_start:bucket_end]
            if bucket:
                retained.add(min(bucket, key=lambda item: item[1][1])[0])
                retained.add(max(bucket, key=lambda item: item[1][1])[0])
        plotted = [plotted[index] for index in sorted(retained)]

    coords = [
        (x_position(int(point["timestamp_ms"])), y_position(value))
        for _index, (point, value) in plotted
    ]
    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in coords)

    for tick_index in range(5):
        fraction = tick_index / 4
        y = top + fraction * plot_height
        value = high - (high - low) * Decimal(str(fraction))
        label = format(value, ",.4f")
        parts.extend([
            f'<line x1="{left}" y1="{y:.2f}" x2="{plot_right}" y2="{y:.2f}" '
            'stroke="#e5e7eb" stroke-width="1"/>',
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="11" '
            f'fill="#555">{html.escape(label)}</text>',
        ])

    parts.extend([
        (
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{plot_bottom}" '
            'stroke="#777" stroke-width="1"/>'
        ),
        (
            f'<line x1="{left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" '
            'stroke="#777" stroke-width="1"/>'
        ),
    ])

    if reference > ZERO:
        reference_y = y_position(reference)
        reference_label_y = max(top + 13, min(plot_bottom - 7, reference_y - 7))
        parts.extend([
            f'<line x1="{left}" y1="{reference_y:.2f}" x2="{plot_right}" y2="{reference_y:.2f}" '
            'stroke="#c27a12" stroke-width="1.5" stroke-dasharray="7 5"/>',
            f'<text x="{plot_right - 6}" y="{reference_label_y:.2f}" '
            'text-anchor="end" font-size="11" fill="#9a5b08">'
            f'Initial capital: {html.escape(format(reference, ",.4f"))} USDT</text>',
        ])

    first_value, last_value = values[0], values[-1]
    roi = (last_value / reference - ONE) * Decimal("100") if reference > ZERO else ZERO
    parts.extend([
        f'<polygon points="{polyline} {coords[-1][0]:.2f},{plot_bottom} '
        f'{coords[0][0]:.2f},{plot_bottom}" fill="#1976d2" opacity="0.10"/>',
        f'<polyline points="{polyline}" fill="none" stroke="#1976d2" stroke-width="3" '
        'stroke-linejoin="round" stroke-linecap="round"/>',
        f'<circle cx="{coords[0][0]:.2f}" cy="{coords[0][1]:.2f}" r="4.5" fill="#1976d2"/>',
        f'<circle cx="{coords[-1][0]:.2f}" cy="{coords[-1][1]:.2f}" r="4.5" fill="#1976d2"/>',
        f'<text x="{left}" y="73" font-size="13" fill="#333">'
        f'Start: {html.escape(format(first_value, ",.4f"))} USDT</text>',
        f'<text x="{plot_right}" y="73" text-anchor="end" font-size="13" fill="#333">'
        f'Latest: {html.escape(format(last_value, ",.4f"))} USDT '
        f'({roi:+.2f}% vs initial)</text>',
    ])

    label_indices = [0] if len(points) == 1 else [0, len(points) // 2, len(points) - 1]
    anchors = ["middle"] if len(label_indices) == 1 else ["start", "middle", "end"]
    for index, anchor in zip(label_indices, anchors, strict=True):
        stamp = datetime.fromtimestamp(
            int(points[index]["timestamp_ms"]) / 1000,
            tz=UTC,
        ).strftime("%Y-%m-%d %H:%M UTC")
        parts.append(
            f'<text x="{x_position(int(points[index]["timestamp_ms"])):.2f}" '
            f'y="{height - 25}" text-anchor="{anchor}" font-size="11" fill="#555">'
            f'{html.escape(stamp)}</text>'
        )

    parts.extend([
        f'<text x="{plot_right}" y="{height - 7}" text-anchor="end" font-size="10" fill="#777">'
        f'{len(points):,} persisted NAV observations</text>',
        "</g></svg>",
        "",
    ])
    return "".join(parts)


def _metric(metrics: dict[str, Any], name: str, kind: str = "ratio") -> str:
    item = metrics.get(name)
    if not item:
        reasons = {
            "sortino": "at least 20 daily returns and 5 negative returns required",
            "sharpe": "at least 30 daily returns required",
            "cagr": "at least 365 elapsed calendar days required",
            "annualized_daily_volatility": "at least 30 daily returns required",
        }
        return f"Unavailable — {reasons.get(name, 'sample gate not met')}"
    value = item.get("value")
    if value is None:
        return f"Unavailable — {item.get('reason') or 'sample gate not met'}"
    if kind == "percent":
        return f"{float(value) * 100:+.3f}%"
    if kind == "days":
        return f"{float(value):.2f} days"
    if kind == "count":
        return str(int(value))
    if kind == "factor":
        return f"{float(value):.3f}×"
    return f"{float(value):.3f}"


def _open_positions(positions: list[dict[str, Any]]) -> list[str]:
    rows = [
        "| Symbol | Side | Quantity | Entry | Mark | Notional (USDT) | "
        "Unrealized P&L (USDT) | Entry UTC |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for position in positions:
        qty = _decimal(position.get("quantity"))
        entry = _decimal(position.get("entry_price"))
        mark = _decimal(position.get("last_mark_price"), str(entry))
        pnl = (
            (mark - entry) * qty if position.get("side") == "long"
            else (entry - mark) * qty
        )
        rows.append(
            f"| {_cell(position.get('symbol'))} | {_cell(position.get('side'))} "
            f"| {qty} | {entry} | {mark} | {_money(qty * mark)} | {_money(pnl)} "
            f"| {_utc(position.get('entry_timestamp_ms'))} |"
        )
    return rows


def render_performance_report(
    state_dir: Path,
    workflow_metadata: dict[str, str] | None = None,
    *,
    generated_at_ms: int | None = None,
    equity_svg_path: Path | None = None,
) -> str:
    batches = _load_verified_batches(Path(state_dir))
    all_events = [event for batch in batches for event in batch.get("events", [])]
    account_events = [
        event for event in all_events
        if event.get("account_id") == ACCOUNT_ID
        and event.get("strategy_id") == STRATEGY_ID
    ]
    state_events = [
        event for event in account_events
        if isinstance(event.get("payload", {}).get("portfolio_state"), dict)
    ]
    latest_batch_hash = batches[-1]["batch_hash"]
    metadata = workflow_metadata or {}
    run_id = metadata.get("run_id", "")
    run_url = metadata.get("run_url", "")
    run_link = f"[{run_id}]({run_url})" if run_id and run_url else (
        run_id or "Not available"
    )
    generated_at_ms = generated_at_ms or int(datetime.now(UTC).timestamp() * 1000)

    if not state_events:
        if equity_svg_path is not None:
            chart_path = Path(equity_svg_path)
            chart_path.parent.mkdir(parents=True, exist_ok=True)
            chart_path.write_text(_equity_curve_svg([], ZERO), encoding="utf-8")
        return "\n".join([
            "# MEXC Paper Performance Report",
            "",
            f"Generated: {_utc(generated_at_ms)}",
            f"Workflow run: {run_link}",
            "",
            "![Trend-Quality paper portfolio equity curve](equity_curve.svg)",
            "",
            "The active $50 USDT paper account is not yet initialized. The global event "
            "chain was verified, but it contains no full account-state snapshot.",
            "",
            f"Verified event batches: {len(batches)}",
            f"Latest global event-batch hash: {latest_batch_hash}",
            "",
            "No account performance is inferred or fabricated.",
            "",
        ])

    latest_event = state_events[-1]
    latest_state = latest_event["payload"]["portfolio_state"]
    if latest_state.get("account_id") != ACCOUNT_ID:
        raise ValueError("Latest state belongs to another account generation")

    equity, session_baselines = _equity_sessions(account_events, latest_state)
    initial = _decimal(latest_state.get("initial_capital"))
    if equity_svg_path is not None:
        chart_path = Path(equity_svg_path)
        chart_path.parent.mkdir(parents=True, exist_ok=True)
        chart_path.write_text(_equity_curve_svg(equity, initial), encoding="utf-8")
    cash = _decimal(latest_state.get("cash"))
    positions = list(latest_state.get("positions", []))
    unrealized = ZERO
    long_notional = ZERO
    short_notional = ZERO
    for position in positions:
        qty = _decimal(position.get("quantity"))
        entry = _decimal(position.get("entry_price"))
        mark = _decimal(position.get("last_mark_price"), str(entry))
        unrealized += (
            (mark - entry) * qty if position.get("side") == "long"
            else (entry - mark) * qty
        )
        if position.get("side") == "long":
            long_notional += qty * mark
        else:
            short_notional += qty * mark
    nav = cash + unrealized
    roi = nav / initial - ONE if initial > ZERO else ZERO
    gross = (long_notional + short_notional) / nav if nav > ZERO else ZERO
    net = abs(long_notional - short_notional) / nav if nav > ZERO else ZERO

    cross = _drawdown(equity, initial)
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for point in equity:
        grouped[int(point["session_start_ms"])].append(point)
    sessions = []
    for start, rows in sorted(grouped.items()):
        baseline = session_baselines.get(
            start, _decimal(rows[0].get("drawdown_window_starting_nav"), str(initial))
        )
        sessions.append((start, baseline, _drawdown(rows, baseline, start)))
    worst_session = min((item[2]["max_drawdown"] for item in sessions), default=None)

    risk = latest_state.get("daily_risk", {})
    risk = risk if isinstance(risk, dict) else {}
    peak = _decimal(risk.get("peak_nav"), str(nav))
    current_dd = nav / peak - ONE if peak > ZERO else ZERO
    performance = performance_summary(latest_state)
    metrics = performance.get("metrics", {})
    history = _collect_history(account_events)
    closed = [_decimal(x) for x in latest_state.get("closed_trade_net_pnls", [])]
    partial = [_decimal(x) for x in latest_state.get("partial_realized_net_pnls", [])]
    daily = list(latest_state.get("daily_equity", []))
    curve_values = [_decimal(row.get("nav")) for row in equity]
    run_number = metadata.get("run_number", "—")
    attempt = metadata.get("run_attempt", "—")
    outcome = metadata.get("outcome", "not supplied")

    lines = [
        "# MEXC Paper Performance Report",
        "",
        f"Generated: {_utc(generated_at_ms)}  ",
        f"Account: {ACCOUNT_ID}  ",
        f"Strategy generation: {STRATEGY_ID}  ",
        f"Workflow run: {run_link} (run #{run_number}, attempt {attempt}; outcome: {outcome})",
        "",
        "This standalone report is rebuilt from the dedicated state branch after every "
        "MEXC paper workflow run. The complete source event chain is verified before "
        "publication to main.",
        "",
        "## Current account snapshot",
        "",
        "| Metric | Current value |",
        "|---|---:|",
        f"| Initial capital | {_money(initial)} USDT |",
        f"| **Net asset value (NAV)** | **{_money(nav)} USDT** |",
        f"| Total return from initial capital | {_percent(roi)} |",
        f"| Cash | {_money(cash)} USDT |",
        f"| Unrealized P&L | {_money(unrealized)} USDT |",
        f"| Realized gross P&L | {_money(latest_state.get('realized_gross_pnl'))} USDT |",
        f"| Fees paid | {_money(latest_state.get('fees_paid'))} USDT |",
        f"| Confirmed funding | {_money(latest_state.get('confirmed_funding'))} USDT |",
        f"| Partial realized net P&L | {_money(sum(partial, ZERO))} USDT |",
        f"| Open positions | {len(positions)} |",
        f"| Fully closed position trades | {len(closed)} |",
        f"| Closed-trade win rate | {_metric(metrics, 'win_rate', 'percent')} |",
        f"| Gross exposure | {gross:.4f}× NAV |",
        f"| Net exposure | {net:.4f}× NAV |",
        f"| Long / short notional | {_money(long_notional)} / {_money(short_notional)} USDT |",
        "",
        "Latest portfolio valuation: "
        f"{_utc(equity[-1]['timestamp_ms'] if equity else latest_event['occurred_at_ms'])}.",
        f"Latest saved account event: {_utc(latest_event.get('occurred_at_ms'))}.",
        "",
        "## Risk and performance metrics",
        "",
        "| Metric | Result | Basis / sample gate |",
        "|---|---:|---|",
        f"| Sortino ratio | {_metric(metrics, 'sortino')} | "
        "Daily NAV returns; minimum 20 returns and 5 negative returns |",
        f"| Sharpe ratio | {_metric(metrics, 'sharpe')} | Daily NAV returns; minimum 30 returns |",
        f"| CAGR | {_metric(metrics, 'cagr', 'percent')} | At least 365 elapsed calendar days |",
        f"| Calmar ratio | {_metric(metrics, 'calmar')} | CAGR divided by daily-equity drawdown |",
        f"| Annualized daily volatility | "
        f"{_metric(metrics, 'annualized_daily_volatility', 'percent')} | "
        "Minimum 30 daily returns |",
        f"| Daily-equity maximum drawdown | "
        f"{_metric(metrics, 'maximum_drawdown', 'percent')} | Daily UTC equity series |",
        f"| Maximum drawdown duration | "
        f"{_metric(metrics, 'maximum_drawdown_duration_days', 'days')} | "
        "Daily UTC equity series |",
        f"| Recovery period after maximum drawdown | "
        f"{_metric(metrics, 'recovery_period_days', 'days')} | "
        "Requires recovery to the prior peak |",
        f"| Closed-trade expectancy | {_metric(metrics, 'expectancy_net_pnl')} USDT | "
        "Fully closed position trades only |",
        f"| Profit factor | {_metric(metrics, 'profit_factor', 'factor')} | "
        "Fully closed position trades only |",
        f"| Current risk-window drawdown | {_percent(current_dd)} | "
        f"Versus current risk-window peak {_money(peak)} USDT |",
        "",
        "**Lifetime / cross-session maximum drawdown:** "
        f"{_percent(cross['max_drawdown'])}.",
        f"**Worst individual risk-session maximum drawdown:** {_percent(worst_session)}.",
        "",
        "Risk-session drawdown resets only at a successful new-pair entry, daily rebalance "
        "or UTC-day rollover. Lifetime drawdown is measured from original capital across "
        "all sessions and never resets.",
        "",
        "### Maximum drawdown by risk session",
        "",
        "| Session | Start (UTC) | Starting NAV | Latest NAV | Session return | "
        "Maximum drawdown | Marks |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for index, (start, baseline, stats) in enumerate(sessions, start=1):
        session_return = stats["last_nav"] / baseline - ONE if baseline > ZERO else ZERO
        lines.append(
            f"| {index} | {_utc(start)} | {_money(baseline)} | "
            f"{_money(stats['last_nav'])} | {_percent(session_return)} | "
            f"{_percent(stats['max_drawdown'])} | {stats['observations']} |"
        )
    if not sessions:
        lines.append("| — | No risk sessions observed | — | — | — | — | 0 |")
    if cross["trough_timestamp_ms"] is not None:
        lines.extend([
            "",
            f"Lifetime drawdown peak: {_utc(cross['peak_timestamp_ms'])}.",
            f"Lifetime drawdown trough: {_utc(cross['trough_timestamp_ms'])} "
            f"(NAV {_money(cross['trough_nav'])} USDT).",
        ])

    lines.extend([
        "",
        "## Equity curve",
        "",
        f"All persisted mark-to-market observations ({len(equity)} points):",
        "",
        "![Trend-Quality paper portfolio equity curve](equity_curve.svg)",
        "",
        "The SVG uses the same hash-chain-verified mark-to-market NAV observations "
        "shown in the full history below. The dashed line marks original account capital.",
        "",
        f"Observed NAV range: {_money(min(curve_values)) if curve_values else '—'} to "
        f"{_money(max(curve_values)) if curve_values else '—'} USDT.",
        f"Daily-equity observations: {len(daily)}; "
        f"daily metric status: {performance.get('status', 'unavailable')} "
        f"({performance.get('observations', 0)} daily return observations).",
        "",
        "### Daily equity observations",
        "",
        "| UTC timestamp | NAV (USDT) |",
        "|---|---:|",
    ])
    for row in daily:
        lines.append(f"| {_utc(row.get('timestamp_ms'))} | {_money(row.get('nav'))} |")
    if not daily:
        lines.append("| No daily equity observations yet | — |")

    lines.extend([
        "",
        "### Full mark-to-market equity history",
        "",
        "| Timestamp (UTC) | NAV (USDT) | ROI from initial capital | "
        "Risk-window drawdown | Long notional | Short notional |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in equity:
        lines.append(
            f"| {_utc(row.get('timestamp_ms'))} | {_money(row.get('nav'))} | "
            f"{_cell(row.get('roi_pct'))}% | {_cell(row.get('daily_drawdown_pct'))}% | "
            f"{_money(row.get('long_notional_usdt'))} | {_money(row.get('short_notional_usdt'))} |"
        )
    if not equity:
        lines.append("| No persisted mark-to-market observations yet | — | — | — | — | — |")

    lines.extend(["", "## Open positions", ""])
    lines.extend(_open_positions(positions) if positions else ["No open paper positions."])
    lines.extend([
        "",
        "## Full timestamped trade and funding history",
        "",
        "Explicit fills and funding records are shown directly. Persisted before/after "
        "position changes are used as a backstop; where an event did not preserve an exact "
        "fill price or P&L, the note identifies the row as derived rather than inventing details.",
        "",
        "| Timestamp (UTC) | Action | Symbol | Side | Quantity / Δ | Price | "
        "Fees (USDT) | Net P&L (USDT) | Funding (USDT) | Source / note |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ])
    for row in history:
        pnl = row.get("net_pnl") if row.get("net_pnl") is not None else row.get("gross_pnl")
        lines.append(
            f"| {_utc(row['timestamp_ms'])} | {_cell(row['action'])} | {_cell(row['symbol'])} "
            f"| {_cell(row.get('side'))} | {_cell(row.get('quantity'))} "
            f"| {_cell(row.get('price'))} | {_cell(row.get('fees'))} "
            f"| {_cell(pnl)} | {_cell(row.get('funding'))} | {_cell(row.get('note'))} |"
        )
    if not history:
        lines.append(
            "| No position or funding activity recorded yet | — | — | "
            "— | — | — | — | — | — |"
        )

    lines.extend([
        "",
        "## Data integrity and operating boundary",
        "",
        f"Verified global event batches: **{len(batches)}**.",
        f"Events for this account/strategy generation: **{len(account_events)}** "
        f"({len(state_events)} carry full account-state snapshots).",
        f"Latest global event-batch hash: {latest_batch_hash}.",
        "All batches were hash-verified and the complete parent-hash chain was checked "
        "for a single genesis, missing parents, duplicate identifiers and forks.",
        "The archived $1 and $10 USDT account generations are excluded; only the active "
        "$50 USDT account is reported.",
        "Paper simulation only: no live orders, private exchange endpoints, "
        "credentials or wallet access.",
        "Metrics remain unavailable until their documented sample gates are satisfied.",
        "",
    ])
    return "\n".join(lines)


def build_workflow_metadata(environ: dict[str, str]) -> dict[str, str]:
    run_id = environ.get("PAPER_WORKFLOW_RUN_ID", "")
    server = environ.get("PAPER_WORKFLOW_SERVER_URL", "").rstrip("/")
    repository = environ.get("PAPER_WORKFLOW_REPOSITORY", "")
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if (
        server and repository and run_id
    ) else ""
    return {
        "run_id": run_id,
        "run_number": environ.get("PAPER_WORKFLOW_RUN_NUMBER", ""),
        "run_attempt": environ.get("PAPER_WORKFLOW_RUN_ATTEMPT", ""),
        "outcome": environ.get("PAPER_WORKFLOW_OUTCOME", "not supplied"),
        "run_url": run_url,
    }

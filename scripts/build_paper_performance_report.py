#!/usr/bin/env python3
"""Generate the standalone MEXC paper-account performance report."""
from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

from trend_quality.paper_performance_report import (
    build_workflow_metadata,
    render_performance_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(os.environ.get("PAPER_STATE_DIR", "state")),
        help="Fresh checkout of the verified paper-event branch",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.environ.get(
            "PAPER_PERFORMANCE_REPORT_PATH", "PAPER_PERFORMANCE_REPORT.md"
        )),
        help="Markdown report destination",
    )
    parser.add_argument(
        "--equity-svg-output",
        type=Path,
        default=Path(os.environ.get("PAPER_EQUITY_CURVE_SVG_PATH", "equity_curve.svg")),
        help="SVG chart destination; normally published beside the Markdown report",
    )
    args = parser.parse_args()
    report = render_performance_report(
        args.state_dir,
        build_workflow_metadata(dict(os.environ)),
        generated_at_ms=int(datetime.now(UTC).timestamp() * 1000),
        equity_svg_path=args.equity_svg_output,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(
        f"Built paper performance report: {args.output} "
        f"({len(report.splitlines())} lines); SVG chart: {args.equity_svg_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

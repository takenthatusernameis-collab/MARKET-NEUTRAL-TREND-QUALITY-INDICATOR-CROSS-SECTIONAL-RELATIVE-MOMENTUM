from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from trend_quality.ranking import Candidate


def load_cycle_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "mexc_paper_cycle.py"
    spec = importlib.util.spec_from_file_location("mexc_paper_cycle_test_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ranking_report_uses_exchange_ticker_not_internal_key() -> None:
    cycle = load_cycle_module()
    candidate = Candidate(
        symbol="mexc:233",
        q=5.45,
        b=84.5,
        direction="long",
        cycle_age=40,
    )
    instrument = {
        "instrument_id": 233,
        "symbol": "BTC_USDT",
        "category": "crypto",
    }

    rows = cycle._ranking_report_rows(
        [candidate],
        {"mexc:233": instrument},
    )

    assert rows == [{
        "symbol": "BTC_USDT",
        "instrument_id": 233,
        "category": "crypto",
        "q": "5.45",
        "direction": "long",
        "cycle_age": 40,
        "b": 84.5,
    }]


def test_execution_ranking_report_can_omit_supplementary_b() -> None:
    cycle = load_cycle_module()
    candidate = Candidate(
        symbol="mexc:326",
        q=-50.76,
        b=98.06,
        direction="short",
        cycle_age=65,
    )
    rows = cycle._ranking_report_rows(
        [candidate],
        {"mexc:326": {
            "instrument_id": 326,
            "symbol": "ETH_USDT",
            "category": "crypto",
        }},
        include_b=False,
    )
    assert rows[0]["symbol"] == "ETH_USDT"
    assert "b" not in rows[0]



def test_daily_risk_path_rejects_missing_stale_and_nonpositive_position_marks() -> None:
    cycle = load_cycle_module()
    positions = [{"instrument_id": 7, "symbol": "TEST_USDT"}]
    assert cycle._stale_or_missing_position_marks(
        positions,
        {7: {"timestamp_ms": 1_000_000, "mark_price": "10"}},
        1_100_000,
    ) == []
    assert cycle._stale_or_missing_position_marks(
        positions,
        {7: {"timestamp_ms": 1_000_000, "mark_price": "10"}},
        1_400_001,
    ) == ["TEST_USDT"]
    assert cycle._stale_or_missing_position_marks(positions, {}, 1_100_000) == [
        "TEST_USDT"
    ]
    assert cycle._stale_or_missing_position_marks(
        positions,
        {7: {"timestamp_ms": 1_100_000, "mark_price": "0"}},
        1_100_000,
    ) == ["TEST_USDT"]

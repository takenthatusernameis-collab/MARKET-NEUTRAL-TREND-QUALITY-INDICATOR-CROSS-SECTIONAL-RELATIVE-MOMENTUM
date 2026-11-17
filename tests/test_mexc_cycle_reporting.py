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



def test_state_branch_protection_fails_closed_without_admin_read_token(monkeypatch) -> None:
    cycle = load_cycle_module()
    monkeypatch.delenv("STATE_PROTECTION_TOKEN", raising=False)
    assert cycle._state_branch_protection("owner/repo", "contents-token") == (
        False,
        "STATE_PROTECTION_ADMIN_READ_TOKEN_MISSING",
    )


def test_state_branch_protection_reads_separate_admin_endpoint(monkeypatch) -> None:
    import json
    import urllib.request

    cycle = load_cycle_module()
    monkeypatch.setenv("STATE_PROTECTION_TOKEN", "admin-read-token")
    calls: list[tuple[str, str]] = []

    class FakeResponse:
        def __init__(self, value: dict[str, object]) -> None:
            self.value = value

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _limit: int) -> bytes:
            return json.dumps(self.value).encode("utf-8")

    def fake_urlopen(request, timeout: int):
        calls.append((
            request.full_url,
            request.get_header("Authorization"),
        ))
        assert timeout == 12
        if request.full_url.endswith("/branches/state"):
            return FakeResponse({"protected": True})
        if request.full_url.endswith("/branches/state/protection"):
            return FakeResponse({
                "enforce_admins": {"enabled": True},
                "allow_force_pushes": {"enabled": False},
                "allow_deletions": {"enabled": False},
                "restrictions": {"users": [], "teams": [], "apps": [
                    {"slug": "github-actions"}
                ]},
            })
        raise AssertionError(f"Unexpected URL: {request.full_url}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert cycle._state_branch_protection("owner/repo", "contents-token") == (
        True,
        "STATE_BRANCH_PROTECTION_AND_WRITER_RESTRICTIONS_CONFIRMED",
    )
    assert calls == [
        (
            "https://api.github.com/repos/owner/repo/branches/state",
            "Bearer contents-token",
        ),
        (
            "https://api.github.com/repos/owner/repo/branches/state/protection",
            "Bearer admin-read-token",
        ),
    ]


def test_state_branch_protection_fails_closed_when_force_push_is_allowed(monkeypatch) -> None:
    import json
    import urllib.request

    cycle = load_cycle_module()
    monkeypatch.setenv("STATE_PROTECTION_TOKEN", "admin-read-token")

    class FakeResponse:
        def __init__(self, value: dict[str, object]) -> None:
            self.value = value

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _limit: int) -> bytes:
            return json.dumps(self.value).encode("utf-8")

    def fake_urlopen(request, timeout: int):
        value = (
            {"protected": True}
            if request.full_url.endswith("/branches/state")
            else {
                "enforce_admins": {"enabled": True},
                "allow_force_pushes": {"enabled": True},
                "allow_deletions": {"enabled": False},
                "restrictions": {"apps": [{"slug": "github-actions"}]},
            }
        )
        return FakeResponse(value)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert cycle._state_branch_protection("owner/repo", "contents-token") == (
        False,
        "STATE_BRANCH_FORCE_PUSH_PROHIBITION_NOT_CONFIRMED",
    )



def test_recovery_probe_requires_fresh_checkout_and_does_not_initialize_account(tmp_path) -> None:
    from trend_quality.event_journal import build_event_batch, write_batch_atomic

    cycle = load_cycle_module()
    event = {
        "event_id": "state-probe-1",
        "idempotency_key": "state-probe-1",
        "account_id": cycle.ACCOUNT_ID,
        "strategy_id": cycle.STRATEGY_ID,
        "occurred_at_ms": 1_800_000_000_000,
        "event_type": "paper_state_recovery_probe",
        "payload": {
            "details": {
                "protocol": "PUBLISH_READBACK_THEN_FRESH_CHECKOUT",
                "financial_state_created": False,
                "account_initialized": False,
            }
        },
    }
    batch = build_event_batch(
        "state-probe-1",
        1_800_000_000_000,
        [event],
    )
    write_batch_atomic(tmp_path, batch)

    portfolio, previous_hash, recovered = cycle._load_state(tmp_path)
    assert portfolio is None
    assert previous_hash == batch["batch_hash"]
    assert recovered is True


def test_recovery_probe_not_inferred_from_unrelated_state_event(tmp_path) -> None:
    from trend_quality.event_journal import build_event_batch, write_batch_atomic

    cycle = load_cycle_module()
    event = {
        "event_id": "risk-event-1",
        "idempotency_key": "risk-event-1",
        "account_id": cycle.ACCOUNT_ID,
        "strategy_id": cycle.STRATEGY_ID,
        "occurred_at_ms": 1_800_000_000_000,
        "event_type": "paper_risk_update",
        "payload": {"details": {"protocol": "PUBLISH_READBACK_THEN_FRESH_CHECKOUT"}},
    }
    batch = build_event_batch("risk-event-1", 1_800_000_000_000, [event])
    write_batch_atomic(tmp_path, batch)

    portfolio, previous_hash, recovered = cycle._load_state(tmp_path)
    assert portfolio is None
    assert previous_hash == batch["batch_hash"]
    assert recovered is False

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime

from trend_quality.event_journal import build_event_batch, canonical_json
from trend_quality.github_state import (
    GitHubStateError,
    GitHubStatePublisher,
)


class FakeGitHub:
    def __init__(self) -> None:
        self.ref_sha = "parent-0"
        self.files: dict[str, str] = {}
        self.blobs: dict[str, str] = {}
        self.trees: dict[str, dict[str, object]] = {}
        self.commits: dict[str, dict[str, object]] = {}
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.reject_patch = False
        self.counter = 0

    def __call__(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
    ) -> dict[str, object]:
        self.calls.append((method, path, payload))
        if method == "GET" and "/contents/" in path:
            file_path = path.split("/contents/", 1)[1].split("?", 1)[0]
            if file_path not in self.files:
                raise GitHubStateError("not found", status_code=404)
            encoded = base64.b64encode(self.files[file_path].encode("utf-8")).decode("ascii")
            return {"encoding": "base64", "content": encoded}
        if method == "GET" and path.endswith("/git/ref/heads/state"):
            return {"object": {"sha": self.ref_sha}}
        if method == "GET" and "/git/commits/" in path:
            return {"tree": {"sha": "tree-parent"}}
        if method == "GET" and "/git/trees/" in path:
            entries = []
            for file_path, data in self.files.items():
                sha = hashlib.sha256(data.encode("utf-8")).hexdigest()
                self.blobs[sha] = data
                entries.append({"path": file_path, "type": "blob", "sha": sha})
            return {"tree": entries, "truncated": False}
        if method == "GET" and "/git/blobs/" in path:
            sha = path.rsplit("/", 1)[1]
            if sha not in self.blobs:
                raise GitHubStateError("blob not found", status_code=404)
            encoded = base64.b64encode(self.blobs[sha].encode("utf-8")).decode("ascii")
            return {"encoding": "base64", "content": encoded}
        if method == "POST" and path.endswith("/git/blobs"):
            assert payload is not None
            data = str(payload["content"])
            sha = hashlib.sha256(data.encode("utf-8")).hexdigest()
            self.blobs[sha] = data
            return {"sha": sha}
        if method == "POST" and path.endswith("/git/trees"):
            assert payload is not None
            self.counter += 1
            sha = f"tree-{self.counter}"
            self.trees[sha] = payload
            return {"sha": sha}
        if method == "POST" and path.endswith("/git/commits"):
            assert payload is not None
            self.counter += 1
            sha = f"commit-{self.counter}"
            self.commits[sha] = payload
            return {"sha": sha}
        if method == "PATCH" and path.endswith("/git/refs/heads/state"):
            assert payload is not None
            if self.reject_patch:
                raise GitHubStateError("non-fast-forward", status_code=422)
            assert payload["force"] is False
            new_sha = str(payload["sha"])
            commit = self.commits[new_sha]
            tree = self.trees[str(commit["tree"])]
            item = tree["tree"][0]  # type: ignore[index]
            self.files[str(item["path"])] = self.blobs[str(item["sha"])]
            self.ref_sha = new_sha
            return {"ref": "refs/heads/state", "object": {"sha": new_sha}}
        raise AssertionError(f"Unexpected GitHub request: {method} {path}")


def _batch(
    run_id: str = "run-1",
    previous_batch_hash: str | None = None,
    *,
    created_at_ms: int = 1794787201000,
    event_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    event = {
        "event_id": event_id or f"event-{run_id}",
        "idempotency_key": idempotency_key or f"idem-{run_id}",
        "account_id": "forward-paper",
        "strategy_id": "q-baseline",
        "occurred_at_ms": 1794787200000,
        "event_type": "VALUATION",
        "payload": {"nav": "100.00", "currency": "USDT"},
    }
    return build_event_batch(
        run_id,
        created_at_ms,
        [event],
        previous_batch_hash=previous_batch_hash,
    )


def _expected_path(batch: dict[str, object]) -> str:
    date = datetime.fromtimestamp(
        int(batch["created_at_ms"]) / 1000, tz=UTC
    )
    return f"events/{date:%Y}/{date:%m}/{batch['run_id']}.json"


def test_publish_creates_append_only_batch_with_fast_forward_ref_update() -> None:
    fake = FakeGitHub()
    publisher = GitHubStatePublisher(
        "owner/repo", "dummy-token", branch="state", transport=fake
    )
    batch = _batch()
    result = publisher.publish_batch(batch)
    expected_path = _expected_path(batch)
    assert result.created
    assert result.path == expected_path
    assert result.batch_hash == batch["batch_hash"]
    assert result.commit_sha == fake.ref_sha
    assert fake.files[expected_path] == canonical_json(batch) + "\n"
    patch_calls = [call for call in fake.calls if call[0] == "PATCH"]
    assert len(patch_calls) == 1
    assert patch_calls[0][2] == {"sha": result.commit_sha, "force": False}


def test_second_batch_must_extend_the_verified_remote_chain_tip() -> None:
    fake = FakeGitHub()
    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    first = _batch("run-1")
    first_result = publisher.publish_batch(first)
    second = _batch("run-2", str(first["batch_hash"]))
    second_result = publisher.publish_batch(second)
    assert first_result.created and second_result.created
    assert fake.files[_expected_path(first)] == canonical_json(first) + "\n"
    assert fake.files[_expected_path(second)] == canonical_json(second) + "\n"


def test_unanchored_genesis_batch_is_rejected_after_existing_batch() -> None:
    fake = FakeGitHub()
    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    first = _batch("run-1")
    publisher.publish_batch(first)
    unanchored = _batch("run-2")
    patch_count_before = sum(call[0] == "PATCH" for call in fake.calls)
    try:
        publisher.publish_batch(unanchored)
    except GitHubStateError as exc:
        assert "unanchored previous hash" in str(exc)
    else:
        raise AssertionError("second genesis batch must not be appended")
    assert sum(call[0] == "PATCH" for call in fake.calls) == patch_count_before


def test_existing_forked_event_tree_is_rejected() -> None:
    fake = FakeGitHub()
    first = _batch("root-1")
    second_root = _batch("root-2")
    fake.files[_expected_path(first)] = canonical_json(first) + "\n"
    fake.files[_expected_path(second_root)] = canonical_json(second_root) + "\n"
    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    candidate = _batch("run-3", str(first["batch_hash"]))
    try:
        publisher.publish_batch(candidate)
    except GitHubStateError as exc:
        assert "exactly one genesis" in str(exc)
    else:
        raise AssertionError("forked state chain must be rejected before append")



def test_remote_chain_rejects_run_id_reuse_across_months() -> None:
    fake = FakeGitHub()
    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    first = _batch("same-run")
    publisher.publish_batch(first)
    second = _batch(
        "same-run",
        str(first["batch_hash"]),
        created_at_ms=1794787201000 + 35 * 86_400_000,
    )
    try:
        publisher.publish_batch(second)
    except GitHubStateError as exc:
        assert "Duplicate run_id" in str(exc)
    else:
        raise AssertionError("run_id reuse on a different monthly path must be rejected")


def test_remote_chain_rejects_event_id_reuse_across_batches() -> None:
    fake = FakeGitHub()
    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    first = _batch("run-1")
    publisher.publish_batch(first)
    second = _batch(
        "run-2",
        str(first["batch_hash"]),
        event_id="event-run-1",
    )
    try:
        publisher.publish_batch(second)
    except GitHubStateError as exc:
        assert "Duplicate event_id" in str(exc)
    else:
        raise AssertionError("event_id reuse across batches must be rejected")


def test_remote_chain_rejects_idempotency_key_reuse_across_batches() -> None:
    fake = FakeGitHub()
    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    first = _batch("run-1")
    publisher.publish_batch(first)
    second = _batch(
        "run-2",
        str(first["batch_hash"]),
        idempotency_key="idem-run-1",
    )
    try:
        publisher.publish_batch(second)
    except GitHubStateError as exc:
        assert "Duplicate idempotency_key" in str(exc)
    else:
        raise AssertionError("idempotency_key reuse across batches must be rejected")


def test_identical_existing_batch_is_an_idempotent_noop() -> None:
    fake = FakeGitHub()
    batch = _batch()
    fake.files[_expected_path(batch)] = canonical_json(batch) + "\n"
    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    result = publisher.publish_batch(batch)
    assert not result.created
    assert result.commit_sha is None
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == "GET"


def test_different_content_at_existing_immutable_path_is_rejected() -> None:
    fake = FakeGitHub()
    batch = _batch()
    fake.files[_expected_path(batch)] = "{}\n"
    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    try:
        publisher.publish_batch(batch)
    except GitHubStateError as exc:
        assert "different content" in str(exc)
    else:
        raise AssertionError("immutable path overwrite must be rejected")
    assert len(fake.calls) == 1


def test_non_fast_forward_race_is_rejected_without_force_push() -> None:
    fake = FakeGitHub()
    fake.reject_patch = True
    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    try:
        publisher.publish_batch(_batch())
    except GitHubStateError as exc:
        assert "do not force-push" in str(exc)
        assert exc.status_code == 422
    else:
        raise AssertionError("concurrent state update must be rejected")
    patch_calls = [call for call in fake.calls if call[0] == "PATCH"]
    assert len(patch_calls) == 1
    assert patch_calls[0][2]["force"] is False  # type: ignore[index]


def test_invalid_batch_and_unsafe_repository_are_rejected_before_api_calls() -> None:
    fake = FakeGitHub()
    try:
        GitHubStatePublisher("owner/repo", "", transport=fake)
    except ValueError as exc:
        assert "token" in str(exc)
    else:
        raise AssertionError("empty token must be rejected")
    try:
        GitHubStatePublisher(
            "owner/repo",
            "dummy-token",
            api_base_url="https://attacker.invalid",
            transport=fake,
        )
    except ValueError as exc:
        assert "official" in str(exc)
    else:
        raise AssertionError("non-GitHub API hosts must be rejected")

    publisher = GitHubStatePublisher("owner/repo", "dummy-token", transport=fake)
    try:
        publisher.publish_batch({"run_id": "../escape"})
    except GitHubStateError as exc:
        assert "invalid event batch" in str(exc).lower()
    else:
        raise AssertionError("invalid event batch must be rejected")
    assert fake.calls == []

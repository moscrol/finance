from __future__ import annotations

import fcntl
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.agent_review.submit import submit_request
from scripts.agent_review.producer_fallback import run_fallback_once
from scripts.agent_review.worker import run_once


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture()
def worker_case(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "intelligence/services").mkdir(parents=True)
    (repo / "intelligence/tests").mkdir(parents=True)
    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (repo / "intelligence/tests/test_evidence_ledger.py").write_text(
        "from intelligence.services.evidence_ledger import VALUE\n"
        "def test_value():\n    assert VALUE\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "worker@example.com")
    _git(repo, "config", "user.name", "Worker Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "slice")
    state_root = tmp_path / "state"
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="worker slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("focused",),
        intensity="light",
    )

    def fake_reviewer(*, mode: str) -> tuple[str, ...]:
        script = tmp_path / f"fake-reviewer-{mode}.py"
        script.write_text(
            """
import json
import os
import pathlib
import sys

mode = sys.argv[1]
request_path = pathlib.Path(os.environ["REQUEST_FILE"])
claim_path = pathlib.Path(os.environ["CLAIM_FILE"])
verdict_path = pathlib.Path(os.environ["VERDICT_FILE"])
counter_path = pathlib.Path(os.environ["STATE_ROOT"]) / "invocations.txt"
count = int(counter_path.read_text()) if counter_path.exists() else 0
counter_path.write_text(str(count + 1))
if mode == "budget":
    print("Exceeded USD budget", file=sys.stderr)
    raise SystemExit(1)
request = json.loads(request_path.read_text())
claim = json.loads(claim_path.read_text())
checks = {
    name: {"status": "PASS", "evidence": "verified"}
    for name in request["required_checks"]
}
for tests in request["artifact_tests"].values():
    for test in tests:
        checks[test] = {"status": "PASS", "evidence": "1 passed"}
for name in ("git_diff_check", "artifact_hygiene", "canonical_safety"):
    checks[name] = {"status": "PASS", "evidence": "clean"}
payload = {
    "schema_version": 2,
    "review_id": request["review_id"],
    "commit": request["commit"],
    "request_sha256": claim["request_sha256"],
    "status": "PASS",
    "reviewer": "claude:independent-reviewer",
    "reviewer_class": "external",
    "authority": "external",
    "findings": [],
    "checks": checks,
    "reviewed_at": "2026-07-26T12:30:00+00:00",
    "summary": "fake reviewer passed",
    "next_action": "continue",
}
if mode == "provisional":
    payload["reviewer"] = "codex:producer-fallback"
    payload["reviewer_class"] = "producer_fallback"
    payload["authority"] = "provisional"
if mode == "bad_identity":
    payload["reviewer"] = "codex:producer"
if mode == "mutate":
    request_path.write_text(request_path.read_text() + "\\n")
verdict_path.parent.mkdir(parents=True, exist_ok=True)
verdict_path.write_text(json.dumps(payload))
""".strip()
            + "\n",
            encoding="utf-8",
        )
        return (sys.executable, str(script), mode)

    return repo, state_root, request, fake_reviewer


def test_duplicate_worker_lock_prevents_concurrent_claim(worker_case):
    repo, state_root, request, fake_reviewer = worker_case
    lock_path = state_root / "locks/external-review.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = run_once(
            repo=repo,
            state_root=state_root,
            reviewer_command=fake_reviewer(mode="pass"),
        )

    assert result.status == "LOCKED"
    assert result.review_id == ""
    assert not (state_root / "verdicts" / f"{request.review_id}.json").exists()


def test_budget_failure_enters_backoff_without_immediate_retry(worker_case):
    repo, state_root, request, fake_reviewer = worker_case
    command = fake_reviewer(mode="budget")

    first = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=command,
        now_timestamp=1000.0,
    )
    second = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=command,
        now_timestamp=1001.0,
    )

    assert first.status == "REVIEWER_INACTIVE"
    assert first.review_id == request.review_id
    assert second.status == "BACKOFF"
    assert (state_root / "invocations.txt").read_text() == "1"
    state = json.loads((state_root / "state/external-review.json").read_text())
    assert state["failure_kind"] == "budget"
    assert state["next_retry_at"] > 1001.0


def test_valid_fake_reviewer_publishes_atomic_external_verdict(worker_case):
    repo, state_root, request, fake_reviewer = worker_case

    result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="pass"),
    )

    assert result.status == "VERDICT_WRITTEN"
    verdict_path = state_root / "verdicts" / f"{request.review_id}.json"
    assert verdict_path.exists()
    assert json.loads(verdict_path.read_text())["authority"] == "external"
    assert not tuple((state_root / "worktrees").glob(f"*{request.review_id}*"))
    assert not tuple(state_root.rglob("*.tmp"))


def test_request_mutation_after_claim_discards_reviewer_output(worker_case):
    repo, state_root, request, fake_reviewer = worker_case

    result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="mutate"),
    )

    assert result.status == "REQUEST_MUTATED"
    assert not (state_root / "verdicts" / f"{request.review_id}.json").exists()
    assert (state_root / "runs" / request.review_id / "invalid-verdict.json").exists()
    assert not tuple((state_root / "worktrees").glob(f"*{request.review_id}*"))


def test_invalid_reviewer_output_is_quarantined_not_published(worker_case):
    repo, state_root, request, fake_reviewer = worker_case

    result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="bad_identity"),
    )

    assert result.status == "INVALID_VERDICT"
    assert not (state_root / "verdicts" / f"{request.review_id}.json").exists()
    assert (state_root / "runs" / request.review_id / "invalid-verdict.json").exists()


def test_external_inactivity_can_create_provisional_only(worker_case):
    repo, state_root, request, fake_reviewer = worker_case
    state_path = state_root / "state/external-review.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "status": "REVIEWER_INACTIVE",
                "review_id": request.review_id,
                "failure_kind": "budget",
            }
        ),
        encoding="utf-8",
    )

    result = run_fallback_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="provisional"),
    )

    assert result.status == "PROVISIONAL_WRITTEN"
    assert (state_root / "provisional-verdicts" / f"{request.review_id}.json").exists()
    assert not (state_root / "verdicts" / f"{request.review_id}.json").exists()


def test_release_request_never_uses_producer_fallback(worker_case):
    repo, state_root, old_request, fake_reviewer = worker_case
    # Rebuild state with one release request at the same immutable commit.
    for directory in ("requests", "claims"):
        for path in (state_root / directory).glob("*.json"):
            path.unlink()
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="release slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("deterministic_full_regression", "frozen_live_benchmark"),
        intensity="release",
    )
    state_path = state_root / "state/external-review.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "status": "REVIEWER_INACTIVE",
                "review_id": request.review_id,
                "failure_kind": "budget",
            }
        ),
        encoding="utf-8",
    )

    result = run_fallback_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="provisional"),
    )

    assert result.status == "WAIT_EXTERNAL"
    assert not tuple((state_root / "provisional-verdicts").glob("*.json"))


def test_failing_mechanical_test_produces_changes_required_provisional(worker_case):
    repo, state_root, _old_request, fake_reviewer = worker_case
    for directory in ("requests", "claims"):
        for path in (state_root / directory).glob("*.json"):
            path.unlink()
    (repo / "intelligence/tests/test_evidence_ledger.py").write_text(
        "def test_value():\n    assert False\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "introduce failing slice")
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="failing slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("focused",),
        intensity="light",
    )
    state_path = state_root / "state/external-review.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "status": "REVIEWER_INACTIVE",
                "review_id": request.review_id,
                "failure_kind": "budget",
            }
        ),
        encoding="utf-8",
    )

    result = run_fallback_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="provisional"),
    )

    assert result.status == "PROVISIONAL_WRITTEN"
    payload = json.loads(
        (state_root / "provisional-verdicts" / f"{request.review_id}.json").read_text()
    )
    assert payload["status"] == "CHANGES_REQUIRED"
    assert payload["checks"]["intelligence/tests/test_evidence_ledger.py"]["status"] == "FAIL"


def test_fallback_provider_failure_enters_its_own_backoff(worker_case):
    repo, state_root, request, fake_reviewer = worker_case
    state_path = state_root / "state/external-review.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "status": "REVIEWER_INACTIVE",
                "review_id": request.review_id,
                "failure_kind": "budget",
            }
        ),
        encoding="utf-8",
    )
    command = fake_reviewer(mode="budget")

    first = run_fallback_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=command,
        now_timestamp=1000.0,
    )
    second = run_fallback_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=command,
        now_timestamp=1001.0,
    )

    assert first.status == "FALLBACK_INACTIVE"
    assert second.status == "FALLBACK_BACKOFF"
    assert (state_root / "invocations.txt").read_text() == "1"

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import scripts.agent_review.worker as worker_module
from scripts.agent_review.submit import submit_request
from scripts.agent_review.bootstrap import bootstrap_runtime
from scripts.agent_review.contract import sha256_file
from scripts.agent_review.gate import compute_gate
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
test_state_root = pathlib.Path(sys.argv[2])
request_path = pathlib.Path(os.environ["REQUEST_FILE"])
claim_path = pathlib.Path(os.environ["CLAIM_FILE"])
verdict_path = pathlib.Path(os.environ["VERDICT_FILE"])
counter_path = test_state_root / "invocations.txt"
count = int(counter_path.read_text()) if counter_path.exists() else 0
counter_path.write_text(str(count + 1))
if mode == "budget":
    print("Exceeded USD budget", file=sys.stderr)
    raise SystemExit(1)
if mode == "assert_bundled":
    assert request_path.parent.name == ".agent-review"
    assert claim_path.parent.name == ".agent-review"
if mode == "assert_isolated":
    assert "STATE_ROOT" not in os.environ
    assert "PRODUCER_REPO" not in os.environ
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
if mode == "changes":
    payload["status"] = "CHANGES_REQUIRED"
    payload["findings"] = [{
        "severity": "high",
        "file": request["artifacts"][0],
        "line": 1,
        "title": "reproduced architecture gap",
        "evidence": "fake reviewer reproduced the gap",
        "recommendation": "fix forward",
    }]
if mode == "mutate":
    real_request = test_state_root / "requests" / f"{request['review_id']}.json"
    real_request.write_text(real_request.read_text() + "\\n")
verdict_path.parent.mkdir(parents=True, exist_ok=True)
verdict_path.write_text(json.dumps(payload))
""".strip()
            + "\n",
            encoding="utf-8",
        )
        return (sys.executable, str(script), mode, str(state_root))

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


def test_backoff_starts_when_long_reviewer_failure_finishes(
    worker_case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, state_root, request, fake_reviewer = worker_case
    ticks = iter((10.0, 1610.0))
    monkeypatch.setattr(worker_module.time, "monotonic", lambda: next(ticks))

    result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="budget"),
        now_timestamp=1000.0,
    )

    assert result.status == "REVIEWER_INACTIVE"
    assert result.review_id == request.review_id
    state = json.loads((state_root / "state/external-review.json").read_text())
    assert state["updated_at"] == pytest.approx(2600.0)
    assert state["next_retry_at"] == pytest.approx(2660.0)


def test_reviewer_receives_only_bundled_request_and_claim_paths(worker_case) -> None:
    repo, state_root, request, fake_reviewer = worker_case

    result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="assert_bundled"),
    )

    assert result.status == "VERDICT_WRITTEN"
    assert (state_root / "verdicts" / f"{request.review_id}.json").exists()


def test_reviewer_environment_does_not_expose_authority_state(worker_case) -> None:
    repo, state_root, request, fake_reviewer = worker_case

    result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="assert_isolated"),
    )

    assert result.status == "VERDICT_WRITTEN"
    assert (state_root / "verdicts" / f"{request.review_id}.json").exists()


def test_default_reviewer_command_uses_no_tool_trusted_adapter(worker_case) -> None:
    repo, state_root, request, _fake_reviewer = worker_case
    adapter = state_root / "claude-oneshot-reviewer.py"
    adapter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    command = worker_module._default_reviewer_command(
        repo=repo,
        state_root=state_root,
        review_id=request.review_id,
        commit=request.commit,
        worktree=state_root / "detached",
        request_path=state_root / "bundle/request.json",
        claim_path=state_root / "bundle/claim.json",
        verdict_path=state_root / "bundle/verdict.json",
    )

    assert command == (str(adapter),)
    rendered = " ".join(command)
    assert "acceptEdits" not in rendered
    assert "Write" not in rendered
    assert "Bash(" not in rendered


def test_missing_reviewer_command_enters_transport_backoff(worker_case) -> None:
    repo, state_root, request, _fake_reviewer = worker_case

    result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=(str(state_root / "missing-reviewer"),),
        now_timestamp=1000.0,
    )

    assert result.status == "REVIEWER_INACTIVE"
    assert result.review_id == request.review_id
    assert result.detail == "transport"
    state = json.loads((state_root / "state/external-review.json").read_text())
    assert state["failure_kind"] == "transport"


def test_worker_shutdown_terminates_reviewer_process_group(
    worker_case,
    tmp_path: Path,
) -> None:
    repo, state_root, request, _fake_reviewer = worker_case
    reviewer = tmp_path / "slow-reviewer.py"
    reviewer.write_text(
        "import os, pathlib, sys, time\n"
        "pid = pathlib.Path(sys.argv[1], 'reviewer.pid')\n"
        "pid.write_text(str(os.getpid()))\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    command = " ".join((sys.executable, str(reviewer), str(state_root)))
    worker = subprocess.Popen(
        (
            sys.executable,
            "-m",
            "scripts.agent_review.worker",
            "--repo",
            str(repo),
            "--state-root",
            str(state_root),
            "--once",
            "--reviewer-command",
            command,
        ),
        cwd=Path(__file__).resolve().parents[2],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    reviewer_pid = 0
    try:
        pid_path = state_root / "reviewer.pid"
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not pid_path.exists():
            time.sleep(0.02)
        assert pid_path.exists(), "reviewer process did not start"
        reviewer_pid = int(pid_path.read_text())

        worker.terminate()
        worker.wait(timeout=5.0)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                os.kill(reviewer_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        else:
            raise AssertionError("reviewer process survived worker shutdown")

        assert not tuple((state_root / "worktrees").glob(f"*{request.review_id}*"))
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait(timeout=5.0)
        if reviewer_pid:
            try:
                os.kill(reviewer_pid, 9)
            except ProcessLookupError:
                pass


def test_reviewer_timeout_kills_descendant_after_leader_exits(
    worker_case,
    tmp_path: Path,
) -> None:
    repo, state_root, request, _fake_reviewer = worker_case
    reviewer = tmp_path / "forking-reviewer.py"
    reviewer.write_text(
        "import os, pathlib, sys, time\n"
        "child = os.fork()\n"
        "if child == 0:\n"
        "    pid = pathlib.Path(sys.argv[1], 'descendant.pid')\n"
        "    pid.write_text(str(os.getpid()))\n"
        "    time.sleep(60)\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    descendant_pid = 0
    try:
        result = run_once(
            repo=repo,
            state_root=state_root,
            reviewer_command=(sys.executable, str(reviewer), str(state_root)),
            timeout_seconds=0.2,
        )
        pid_path = state_root / "descendant.pid"
        assert pid_path.exists()
        descendant_pid = int(pid_path.read_text())
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                os.kill(descendant_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        else:
            raise AssertionError("reviewer descendant survived timeout cleanup")

        assert result.status == "REVIEWER_INACTIVE"
        assert result.review_id == request.review_id
        assert result.detail == "timeout"
    finally:
        if descendant_pid:
            try:
                os.kill(descendant_pid, 9)
            except ProcessLookupError:
                pass


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


def test_verdict_for_older_review_cannot_be_published_as_current_frontier(
    worker_case,
    tmp_path: Path,
) -> None:
    repo, state_root, first, fake_reviewer = worker_case
    first_result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="pass"),
    )
    assert first_result.status == "VERDICT_WRITTEN"
    foreign_verdict = state_root / "verdicts" / f"{first.review_id}.json"

    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 3\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "second slice")
    second = submit_request(
        repo=repo,
        state_root=state_root,
        scope="second worker slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("focused",),
        intensity="light",
        depends_on=(first.review_id,),
    )
    copier = tmp_path / "copy-foreign-verdict.py"
    copier.write_text(
        "import os, pathlib, shutil, sys\n"
        "shutil.copy2(sys.argv[1], pathlib.Path(os.environ['VERDICT_FILE']))\n",
        encoding="utf-8",
    )

    result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=(sys.executable, str(copier), str(foreign_verdict)),
    )

    assert result.status == "INVALID_VERDICT"
    assert result.review_id == second.review_id
    assert "verdict_review_id" in result.detail
    assert not (state_root / "verdicts" / f"{second.review_id}.json").exists()
    assert (state_root / "runs" / second.review_id / "invalid-verdict.json").exists()


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
        artifacts=(
            "intelligence/services/evidence_ledger.py",
            "intelligence/tests/test_evidence_ledger.py",
        ),
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


def test_fallback_provider_failure_enters_its_own_backoff(
    worker_case, monkeypatch: pytest.MonkeyPatch
):
    repo, state_root, request, fake_reviewer = worker_case
    # 锁住「调用方 PYTHONPATH 指向另一份 intelligence」这条失败形状。
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
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


def test_bootstrap_classifies_legacy_without_mutating_history(worker_case):
    repo, state_root, request, _fake_reviewer = worker_case
    legacy_request = state_root / "requests/ARL-0998.json"
    legacy_verdict = state_root / "verdicts/ARL-0998.json"
    legacy_request.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "review_id": "ARL-0998",
                "commit": request.commit,
                "status": "ready",
            }
        ),
        encoding="utf-8",
    )
    legacy_verdict.parent.mkdir(parents=True, exist_ok=True)
    legacy_verdict.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "review_id": "ARL-0998",
                "commit": request.commit,
                "status": "PASS",
                "reviewer": "codex:/root/spec_reviewer",
            }
        ),
        encoding="utf-8",
    )
    before_request = sha256_file(legacy_request)
    before_verdict = sha256_file(legacy_verdict)

    metadata = bootstrap_runtime(repo=repo, state_root=state_root)

    assert metadata["source_commit"] == request.commit
    assert sha256_file(legacy_request) == before_request
    assert sha256_file(legacy_verdict) == before_verdict
    classifications = json.loads(
        (state_root / "state/legacy-classification.json").read_text()
    )
    assert classifications["ARL-0998"]["state"] == "LEGACY_SELF_REVIEW"
    assert (state_root / "REVIEWER_PROMPT.md").exists()
    assert (state_root / "reviewer-worker.sh").stat().st_mode & 0o111


def test_worker_reviews_superseding_repair_after_external_finding(worker_case):
    repo, state_root, first, fake_reviewer = worker_case
    finding = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="changes"),
    )
    assert finding.status == "VERDICT_WRITTEN"
    assert finding.detail == "CHANGES_REQUIRED"
    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 3\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "repair slice")
    repair = submit_request(
        repo=repo,
        state_root=state_root,
        scope="repair external finding",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("focused", f"repair:{first.review_id}"),
        intensity="milestone",
        depends_on=(first.review_id,),
        supersedes=first.review_id,
    )

    repaired = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="pass"),
    )

    assert repaired.status == "VERDICT_WRITTEN"
    assert repaired.review_id == repair.review_id
    decision = compute_gate(repo=repo, state_root=state_root)
    assert decision.gate_state == "EXTERNAL_PASS"
    assert decision.provisional_depth == 0
    assert decision.allowed_next_action == "IMPLEMENT_NEXT"


def test_worker_skips_failed_repair_for_newer_superseding_repair(worker_case):
    repo, state_root, first, fake_reviewer = worker_case
    first_result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="changes"),
    )
    assert first_result.detail == "CHANGES_REQUIRED"

    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 3\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "first repair")
    first_repair = submit_request(
        repo=repo,
        state_root=state_root,
        scope="first repair",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("focused", f"repair:{first.review_id}"),
        intensity="milestone",
        depends_on=(first.review_id,),
        supersedes=first.review_id,
    )
    first_repair_result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="changes"),
    )
    assert first_repair_result.review_id == first_repair.review_id
    assert first_repair_result.detail == "CHANGES_REQUIRED"

    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 4\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "second repair")
    second_repair = submit_request(
        repo=repo,
        state_root=state_root,
        scope="second repair",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("focused", f"repair:{first_repair.review_id}"),
        intensity="milestone",
        depends_on=(first_repair.review_id,),
        supersedes=first_repair.review_id,
    )
    assert second_repair.parent_commit == first.parent_commit

    second_result = run_once(
        repo=repo,
        state_root=state_root,
        reviewer_command=fake_reviewer(mode="pass"),
    )

    assert second_result.status == "VERDICT_WRITTEN"
    assert second_result.review_id == second_repair.review_id

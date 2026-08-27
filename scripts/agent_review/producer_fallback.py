from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.agent_review.contract import forbidden_artifact_paths, sha256_file
from scripts.agent_review.gate import compute_gate, load_reachable_requests
from scripts.agent_review.validate_verdict import validate_verdict_file
from scripts.agent_review.worker import DEFAULT_REPO, DEFAULT_STATE_ROOT, WorkerResult


def _load_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _fallback_backoff(
    state_root: Path, review_id: str, now_timestamp: float
) -> WorkerResult | None:
    state = _load_object(state_root / "state/fallback-review.json")
    if state is None or state.get("review_id") != review_id:
        return None
    next_retry_at = state.get("next_retry_at")
    if (
        state.get("status") == "FALLBACK_INACTIVE"
        and isinstance(next_retry_at, (int, float))
        and float(next_retry_at) > now_timestamp
    ):
        return WorkerResult(
            "FALLBACK_BACKOFF", review_id, f"next_retry_at={float(next_retry_at):.3f}"
        )
    return None


def _record_fallback_failure(
    state_root: Path,
    *,
    review_id: str,
    failure_kind: str,
    now_timestamp: float,
) -> None:
    path = state_root / "state/fallback-review.json"
    prior = _load_object(path) or {}
    prior_attempt = (
        int(prior.get("attempt", 0))
        if prior.get("review_id") == review_id and isinstance(prior.get("attempt", 0), int)
        else 0
    )
    attempt = prior_attempt + 1
    delay = min(3600.0, 300.0 * (2 ** (attempt - 1)))
    _atomic_json(
        path,
        {
            "schema_version": 1,
            "status": "FALLBACK_INACTIVE",
            "review_id": review_id,
            "failure_kind": failure_kind,
            "attempt": attempt,
            "next_retry_at": now_timestamp + delay,
            "updated_at": now_timestamp,
        },
    )


def _mechanical_checks(worktree: Path, request) -> tuple[dict[str, dict[str, str]], list[str]]:
    checks: dict[str, dict[str, str]] = {}
    failures: list[str] = []
    tests = sorted(
        {
            test
            for artifact_tests in request.artifact_tests.values()
            for test in artifact_tests
        }
    )
    clean_environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "FORESIGHT_USERS_DIR",
            "FORESIGHT_USER",
            "SUBCONSCIOUS_VAULT",
            "AGENT_MEMORY_VAULT",
            "PYTHONPATH",
        }
    }
    # 必须看见 detached worktree 里的代码。继承调用方 PYTHONPATH 会把另一棵
    # 树的 intelligence 抢到前面，夹具里的 VALUE 断言变成 ImportError，预算
    # 失败被误判成「机械检查红 → 写临时结论」（本机 sidecar 起过就会留下这条）。
    clean_environment["PYTHONPATH"] = str(worktree)
    if tests:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *tests],
            cwd=worktree,
            env=clean_environment,
            capture_output=True,
            text=True,
        )
        evidence = (completed.stdout + completed.stderr).strip()[-4000:] or "no output"
        status = "PASS" if completed.returncode == 0 else "FAIL"
        for test in tests:
            checks[test] = {"status": status, "evidence": evidence}
        if completed.returncode != 0:
            failures.append("focused_tests")

    diff_check = subprocess.run(
        ["git", "diff", "--check", f"{request.parent_commit}..{request.commit}"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    checks["git_diff_check"] = {
        "status": "PASS" if diff_check.returncode == 0 else "FAIL",
        "evidence": (diff_check.stdout + diff_check.stderr).strip() or "clean",
    }
    if diff_check.returncode != 0:
        failures.append("git_diff_check")

    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{request.parent_commit}..{request.commit}"],
        cwd=worktree,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    forbidden = forbidden_artifact_paths(changed)
    checks["artifact_hygiene"] = {
        "status": "FAIL" if forbidden else "PASS",
        "evidence": ", ".join(forbidden) if forbidden else "no forbidden artifacts",
    }
    if forbidden:
        failures.append("artifact_hygiene")
    checks["canonical_safety"] = {
        "status": "PASS",
        "evidence": "review ran in a detached worktree and executed no runtime cutover",
    }
    return checks, failures


def _default_codex_command(
    *,
    request_path: Path,
    mechanical_path: Path,
    verdict_path: Path,
) -> tuple[str, ...]:
    prompt = f"""
You are a fallback falsification reviewer, not the Producer. Review only the
exact detached commit in the current directory. Read {request_path} and
{mechanical_path}. Inspect the diff and relevant specification. Do not edit the
repository. Write exactly one schema-2 provisional verdict JSON as your final
message. Its reviewer must be codex:producer-fallback, reviewer_class must be
producer_fallback, authority must be provisional, and it must include every
request required_check plus all mechanical checks. A failing mechanical check
requires CHANGES_REQUIRED. This result can never authorize release.
""".strip()
    return (
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--output-last-message",
        str(verdict_path),
        prompt,
    )


def _candidate_to_provisional(
    candidate: Mapping[str, Any],
    *,
    request,
    request_hash: str,
    mechanical_checks: Mapping[str, dict[str, str]],
    mechanical_failures: Sequence[str],
    now_timestamp: float,
) -> dict[str, object]:
    raw_checks = candidate.get("checks")
    checks = dict(raw_checks) if isinstance(raw_checks, dict) else {}
    checks.update(mechanical_checks)
    for required_check in request.required_checks:
        if required_check not in checks:
            checks[required_check] = {
                "status": "FAIL" if mechanical_failures else "PARTIAL",
                "evidence": (
                    "mechanical review failed before semantic review"
                    if mechanical_failures
                    else "fallback reviewer omitted this required check"
                ),
            }
    status = candidate.get("status")
    if status not in {"PASS", "CHANGES_REQUIRED", "BLOCKED"}:
        status = "CHANGES_REQUIRED"
    findings = candidate.get("findings")
    if not isinstance(findings, list):
        findings = []
    if mechanical_failures:
        status = "CHANGES_REQUIRED"
        findings = [
            *findings,
            {
                "severity": "high",
                "file": request.artifacts[0],
                "line": 0,
                "title": "Mechanical review checks failed",
                "evidence": ", ".join(mechanical_failures),
                "recommendation": "repair the failing checks before continuing",
            },
        ]
    return {
        "schema_version": 2,
        "review_id": request.review_id,
        "commit": request.commit,
        "request_sha256": request_hash,
        "status": status,
        "reviewer": "codex:producer-fallback",
        "reviewer_class": "producer_fallback",
        "authority": "provisional",
        "findings": findings,
        "checks": checks,
        "reviewed_at": datetime.fromtimestamp(now_timestamp, tz=timezone.utc).isoformat(),
        "summary": str(candidate.get("summary") or "fallback review completed"),
        "next_action": str(candidate.get("next_action") or "continue provisionally"),
    }


def _run_fallback_locked(
    *,
    repo: Path,
    state_root: Path,
    reviewer_command: Sequence[str] | None,
    now_timestamp: float,
    timeout_seconds: float,
) -> WorkerResult:
    decision = compute_gate(repo=repo, state_root=state_root)
    if not decision.fallback_eligible or not decision.pending_review_id:
        return WorkerResult("WAIT_EXTERNAL", decision.pending_review_id or "", decision.gate_state)
    review_id = decision.pending_review_id
    tip = decision.tip
    requests, invalid = load_reachable_requests(repo=repo, state_root=state_root, tip=tip)
    if invalid:
        return WorkerResult("INVALID", review_id, "reachable request is invalid")
    request = next((item for item in requests if item.review_id == review_id), None)
    if request is None or request.intensity == "release":
        return WorkerResult("WAIT_EXTERNAL", review_id, "release requires external review")
    backoff = _fallback_backoff(state_root, review_id, now_timestamp)
    if backoff is not None:
        return backoff
    request_path = state_root / "requests" / f"{review_id}.json"
    claim_path = state_root / "claims" / f"{review_id}.json"
    claim = _load_object(claim_path)
    if claim is None or claim.get("request_sha256") != sha256_file(request_path):
        return WorkerResult("REQUEST_MUTATED", review_id, "submitted request hash mismatch")
    request_hash = str(claim["request_sha256"])

    worktree = state_root / "worktrees" / f"fallback-{review_id}"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    if worktree.exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        shutil.rmtree(worktree, ignore_errors=True)
    add = subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree), request.commit],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if add.returncode != 0:
        _record_fallback_failure(
            state_root,
            review_id=review_id,
            failure_kind="worktree",
            now_timestamp=now_timestamp,
        )
        return WorkerResult("FALLBACK_INACTIVE", review_id, "worktree add failed")
    run_dir = state_root / "runs" / review_id / "fallback"
    run_dir.mkdir(parents=True, exist_ok=True)
    bundle = worktree / ".agent-review"
    bundle.mkdir(parents=True, exist_ok=True)
    bundled_request = bundle / "request.json"
    bundled_claim = bundle / "claim.json"
    shutil.copy2(request_path, bundled_request)
    shutil.copy2(claim_path, bundled_claim)
    candidate_path = bundle / "candidate-provisional.json"
    try:
        mechanical_checks, mechanical_failures = _mechanical_checks(worktree, request)
        mechanical_path = bundle / "mechanical-checks.json"
        _atomic_json(mechanical_path, mechanical_checks)
        if mechanical_failures:
            candidate: dict[str, Any] = {
                "status": "CHANGES_REQUIRED",
                "findings": [],
                "checks": {},
                "summary": "mechanical fallback checks failed",
                "next_action": "repair failing tests",
            }
        else:
            command = tuple(reviewer_command) if reviewer_command else _default_codex_command(
                request_path=bundled_request,
                mechanical_path=mechanical_path,
                verdict_path=candidate_path,
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "REVIEW_ID": review_id,
                    "COMMIT": request.commit,
                    "REVIEW_WORKTREE": str(worktree),
                    "REQUEST_FILE": str(bundled_request),
                    "CLAIM_FILE": str(bundled_claim),
                    "VERDICT_FILE": str(candidate_path),
                    "REVIEW_SCRATCH_DIR": str(bundle / "scratch"),
                }
            )
            try:
                completed = subprocess.run(
                    command,
                    cwd=worktree,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                _record_fallback_failure(
                    state_root,
                    review_id=review_id,
                    failure_kind="timeout",
                    now_timestamp=now_timestamp,
                )
                return WorkerResult("FALLBACK_INACTIVE", review_id, "timeout")
            (run_dir / "reviewer.log").write_text(
                completed.stdout + completed.stderr,
                encoding="utf-8",
            )
            if completed.returncode != 0 or not candidate_path.exists():
                output = completed.stdout + completed.stderr
                failure_kind = "budget" if "budget" in output.lower() else "provider"
                _record_fallback_failure(
                    state_root,
                    review_id=review_id,
                    failure_kind=failure_kind,
                    now_timestamp=now_timestamp,
                )
                return WorkerResult("FALLBACK_INACTIVE", review_id, "no valid Codex output")
            candidate = _load_object(candidate_path) or {}

        payload = _candidate_to_provisional(
            candidate,
            request=request,
            request_hash=request_hash,
            mechanical_checks=mechanical_checks,
            mechanical_failures=mechanical_failures,
            now_timestamp=now_timestamp,
        )
        provisional_staging = run_dir / "candidate-provisional.json"
        _atomic_json(provisional_staging, payload)
        validation = validate_verdict_file(
            provisional_staging,
            state_root=state_root,
            repo=repo,
            authority="provisional",
            current_tip=tip,
            expected_review_id=review_id,
        )
        if not validation.valid or validation.review_id != review_id:
            _record_fallback_failure(
                state_root,
                review_id=review_id,
                failure_kind="invalid_provisional",
                now_timestamp=now_timestamp,
            )
            return WorkerResult(
                "INVALID_PROVISIONAL", review_id, ",".join(validation.errors)
            )
        if sha256_file(request_path) != request_hash:
            return WorkerResult("REQUEST_MUTATED", review_id, "request changed after claim")
        if (state_root / "verdicts" / f"{review_id}.json").exists():
            return WorkerResult("EXTERNAL_ARRIVED", review_id, "external verdict governs")
        destination = state_root / "provisional-verdicts" / f"{review_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(provisional_staging, destination)
        _atomic_json(
            state_root / "state/fallback-review.json",
            {
                "schema_version": 1,
                "status": "PROVISIONAL_WRITTEN",
                "review_id": review_id,
                "failure_kind": "",
                "attempt": 0,
                "next_retry_at": 0.0,
                "updated_at": now_timestamp,
            },
        )
        return WorkerResult("PROVISIONAL_WRITTEN", review_id, validation.status)
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        shutil.rmtree(worktree, ignore_errors=True)


def run_fallback_once(
    *,
    repo: Path = DEFAULT_REPO,
    state_root: Path = DEFAULT_STATE_ROOT,
    reviewer_command: Sequence[str] | None = None,
    now_timestamp: float | None = None,
    timeout_seconds: float = 900.0,
) -> WorkerResult:
    repo = repo.resolve()
    state_root = state_root.resolve()
    lock_path = state_root / "locks/provisional-review.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return WorkerResult("LOCKED", "", "another fallback reviewer owns the lock")
        try:
            return _run_fallback_locked(
                repo=repo,
                state_root=state_root,
                reviewer_command=reviewer_command,
                now_timestamp=now_timestamp if now_timestamp is not None else time.time(),
                timeout_seconds=timeout_seconds,
            )
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded Producer fallback review")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--poll-seconds", type=float, default=20.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    while True:
        result = run_fallback_once(repo=args.repo, state_root=args.state_root)
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True), flush=True)
        if args.once:
            return 0 if result.status not in {"INVALID", "INVALID_PROVISIONAL"} else 1
        time.sleep(max(1.0, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())

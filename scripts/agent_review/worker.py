from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import shlex
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.agent_review.contract import (
    repair_chain_floor_review_id,
    repair_covers_request,
    sha256_file,
)
from scripts.agent_review.gate import load_reachable_requests
from scripts.agent_review.validate_verdict import validate_verdict_file


DEFAULT_REPO = Path("/Users/a77/.finance-runtime/agent-runtime-backends-c4673667")
DEFAULT_STATE_ROOT = Path("/Users/a77/.finance-runtime/agent-review-loop")


@dataclass(frozen=True)
class WorkerResult:
    status: str
    review_id: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "review_id": self.review_id,
            "detail": self.detail,
        }


class WorkerShutdown(Exception):
    """Raised by CLI signal handlers so reviewer cleanup always runs."""


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5.0)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait(timeout=5.0)


def _run_reviewer_command(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout_seconds: float,
) -> tuple[int, str]:
    process = subprocess.Popen(
        tuple(command),
        cwd=cwd,
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except BaseException:
        _terminate_process_group(process)
        raise
    return int(process.returncode or 0), (stdout or "") + (stderr or "")


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


def _write_external_state(
    state_root: Path,
    *,
    status: str,
    review_id: str,
    now_timestamp: float,
    failure_kind: str = "",
    attempt: int = 0,
    next_retry_at: float = 0.0,
) -> None:
    _atomic_json(
        state_root / "state/external-review.json",
        {
            "schema_version": 1,
            "status": status,
            "review_id": review_id,
            "failure_kind": failure_kind,
            "attempt": attempt,
            "next_retry_at": next_retry_at,
            "updated_at": now_timestamp,
        },
    )


def _current_backoff(state_root: Path, review_id: str, now_timestamp: float) -> WorkerResult | None:
    state = _load_object(state_root / "state/external-review.json")
    if state is None or state.get("review_id") != review_id:
        return None
    next_retry_at = state.get("next_retry_at")
    if (
        state.get("status") == "REVIEWER_INACTIVE"
        and isinstance(next_retry_at, (int, float))
        and float(next_retry_at) > now_timestamp
    ):
        return WorkerResult("BACKOFF", review_id, f"next_retry_at={float(next_retry_at):.3f}")
    return None


def _record_failure(
    state_root: Path,
    *,
    review_id: str,
    failure_kind: str,
    now_timestamp: float,
) -> None:
    prior = _load_object(state_root / "state/external-review.json") or {}
    prior_attempt = (
        int(prior.get("attempt", 0))
        if prior.get("review_id") == review_id and isinstance(prior.get("attempt", 0), int)
        else 0
    )
    attempt = prior_attempt + 1
    delay = min(3600.0, 60.0 * (2 ** (attempt - 1)))
    _write_external_state(
        state_root,
        status="REVIEWER_INACTIVE",
        review_id=review_id,
        failure_kind=failure_kind,
        attempt=attempt,
        next_retry_at=now_timestamp + delay,
        now_timestamp=now_timestamp,
    )


def select_frontier(repo: Path, state_root: Path, tip: str):
    requests, invalid = load_reachable_requests(
        repo=repo,
        state_root=state_root,
        tip=tip,
    )
    if invalid:
        return None, WorkerResult("INVALID", invalid[0], "invalid reachable request")
    verdicts: dict[str, Any] = {}
    for request in requests:
        verdict_path = state_root / "verdicts" / f"{request.review_id}.json"
        if not verdict_path.exists():
            continue
        verdict = validate_verdict_file(
            verdict_path,
            state_root=state_root,
            repo=repo,
            authority="external",
            current_tip=tip,
        )
        if not verdict.valid:
            return None, WorkerResult("INVALID", request.review_id, ",".join(verdict.errors))
        verdicts[request.review_id] = verdict

    blocked_ids = {
        review_id
        for review_id, verdict in verdicts.items()
        if verdict.status in {"CHANGES_REQUIRED", "BLOCKED"}
    }
    repair_requests = [
        request
        for request in requests
        if request.supersedes in blocked_ids
        and f"repair:{request.supersedes}" in request.required_checks
    ]
    superseded_ids = {repair.supersedes for repair in repair_requests}
    for repair in repair_requests:
        if repair.review_id in superseded_ids:
            continue
        repair_verdict = verdicts.get(repair.review_id)
        if repair_verdict is None:
            return repair, None
        if repair_verdict.status != "PASS":
            return None, WorkerResult(
                "REVIEW_BLOCKED", repair.review_id, repair_verdict.status
            )

    covered_ids: set[str] = set()
    request_by_id = {request.review_id: request for request in requests}
    for repair in repair_requests:
        repair_verdict = verdicts.get(repair.review_id)
        if repair_verdict is not None and repair_verdict.status == "PASS":
            coverage_floor = repair_chain_floor_review_id(repair, request_by_id)
            covered_ids.update(
                request.review_id
                for request in requests
                if repair_covers_request(
                    repo=repo,
                    repair=repair,
                    candidate=request,
                    coverage_floor_review_id=coverage_floor,
                )
            )
    for request in requests:
        if request.review_id in covered_ids:
            continue
        verdict = verdicts.get(request.review_id)
        if verdict is None:
            return request, None
        if verdict.status == "PASS":
            continue
        if request.review_id in superseded_ids:
            continue
        return None, WorkerResult("REVIEW_BLOCKED", request.review_id, verdict.status)
    return None, WorkerResult("IDLE", "", "no external review pending")


def _default_reviewer_command(
    *,
    repo: Path,
    state_root: Path,
    review_id: str,
    commit: str,
    worktree: Path,
    request_path: Path,
    claim_path: Path,
    verdict_path: Path,
) -> tuple[str, ...]:
    prompt_path = repo / "scripts/agent_review/REVIEWER_PROMPT.md"
    if not prompt_path.exists():
        prompt_path = state_root / "REVIEWER_PROMPT.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    rendered = (
        f"{prompt}\n\nREVIEW_ID: {review_id}\nCOMMIT: {commit}\n"
        f"REVIEW_WORKTREE: {worktree}\nREQUEST_FILE: {request_path}\n"
        f"CLAIM_FILE: {claim_path}\n"
        f"VERDICT_FILE: {verdict_path}\n"
    )
    budget = os.environ.get("REVIEWER_MAX_BUDGET_USD", "12")
    return (
        "claude",
        "-p",
        rendered,
        "--add-dir",
        str(worktree),
        "--permission-mode",
        "acceptEdits",
        "--max-budget-usd",
        budget,
        "--allowedTools",
        "Read",
        "Write",
        "Grep",
        "Glob",
        "Bash(git *)",
        "Bash(cd *)",
        "Bash(ls *)",
        "Bash(grep *)",
        "Bash(sed *)",
        "Bash(wc *)",
        "Bash(find *)",
        "Bash(env *)",
        "Bash(/Users/a77/finance-workspace-private/.venv-workbench/bin/python *)",
    )


def _quarantine(staging: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if staging.exists():
        os.replace(staging, destination)


def _run_locked(
    *,
    repo: Path,
    state_root: Path,
    reviewer_command: Sequence[str] | None,
    now_timestamp: float,
    timeout_seconds: float,
) -> WorkerResult:
    started_monotonic = time.monotonic()

    def observed_timestamp() -> float:
        return now_timestamp + max(0.0, time.monotonic() - started_monotonic)

    tip = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    request, selection_result = select_frontier(repo, state_root, tip)
    if selection_result is not None:
        return selection_result
    assert request is not None
    review_id = request.review_id
    backoff = _current_backoff(state_root, review_id, now_timestamp)
    if backoff is not None:
        return backoff

    request_path = state_root / "requests" / f"{review_id}.json"
    claim_path = state_root / "claims" / f"{review_id}.json"
    claim = _load_object(claim_path)
    if claim is None or claim.get("request_sha256") != sha256_file(request_path):
        return WorkerResult("REQUEST_MUTATED", review_id, "submitted request hash mismatch")
    frozen_hash = str(claim["request_sha256"])
    run_dir = state_root / "runs" / review_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _atomic_json(
        run_dir / "claimed-request.json",
        {
            "schema_version": 1,
            "review_id": review_id,
            "commit": request.commit,
            "request_sha256": frozen_hash,
            "claimed_at": now_timestamp,
        },
    )
    worktree = state_root / "worktrees" / f"review-{review_id}"
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
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        shutil.rmtree(worktree, ignore_errors=True)
        _record_failure(
            state_root,
            review_id=review_id,
            failure_kind="worktree",
            now_timestamp=observed_timestamp(),
        )
        return WorkerResult("REVIEWER_INACTIVE", review_id, "worktree add failed")

    review_bundle = worktree / ".agent-review"
    review_bundle.mkdir(parents=True, exist_ok=True)
    bundled_request = review_bundle / "request.json"
    bundled_claim = review_bundle / "claim.json"
    shutil.copy2(request_path, bundled_request)
    shutil.copy2(claim_path, bundled_claim)
    staging = review_bundle / "candidate-verdict.json"
    invalid_destination = run_dir / "invalid-verdict.json"
    staging.unlink(missing_ok=True)
    invalid_destination.unlink(missing_ok=True)
    command = tuple(reviewer_command) if reviewer_command else _default_reviewer_command(
        repo=repo,
        state_root=state_root,
        review_id=review_id,
        commit=request.commit,
        worktree=worktree,
        request_path=bundled_request,
        claim_path=bundled_claim,
        verdict_path=staging,
    )
    environment = os.environ.copy()
    environment.update(
        {
            "REVIEW_ID": review_id,
            "COMMIT": request.commit,
            "REVIEW_WORKTREE": str(worktree),
            "REQUEST_FILE": str(request_path),
            "CLAIM_FILE": str(claim_path),
            "VERDICT_FILE": str(staging),
            "STATE_ROOT": str(state_root),
            "PRODUCER_REPO": str(repo),
        }
    )
    try:
        returncode, output = _run_reviewer_command(
            command,
            cwd=worktree,
            environment=environment,
            timeout_seconds=timeout_seconds,
        )
        (run_dir / "reviewer.log").write_text(
            output,
            encoding="utf-8",
        )
        if returncode != 0 or not staging.exists():
            failure_kind = "budget" if "Exceeded USD budget" in output else "transport"
            _record_failure(
                state_root,
                review_id=review_id,
                failure_kind=failure_kind,
                now_timestamp=observed_timestamp(),
            )
            return WorkerResult("REVIEWER_INACTIVE", review_id, failure_kind)
        if sha256_file(request_path) != frozen_hash:
            _quarantine(staging, invalid_destination)
            return WorkerResult("REQUEST_MUTATED", review_id, "request changed after claim")
        validation = validate_verdict_file(
            staging,
            state_root=state_root,
            repo=repo,
            authority="external",
            current_tip=tip,
        )
        if not validation.valid:
            _quarantine(staging, invalid_destination)
            _record_failure(
                state_root,
                review_id=review_id,
                failure_kind="invalid_verdict",
                now_timestamp=observed_timestamp(),
            )
            return WorkerResult("INVALID_VERDICT", review_id, ",".join(validation.errors))
        destination = state_root / "verdicts" / f"{review_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, destination)
        _write_external_state(
            state_root,
            status="VERDICT_WRITTEN",
            review_id=review_id,
            now_timestamp=observed_timestamp(),
        )
        return WorkerResult("VERDICT_WRITTEN", review_id, validation.status)
    except subprocess.TimeoutExpired:
        _record_failure(
            state_root,
            review_id=review_id,
            failure_kind="timeout",
            now_timestamp=observed_timestamp(),
        )
        return WorkerResult("REVIEWER_INACTIVE", review_id, "timeout")
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        shutil.rmtree(worktree, ignore_errors=True)


def run_once(
    *,
    repo: Path = DEFAULT_REPO,
    state_root: Path = DEFAULT_STATE_ROOT,
    reviewer_command: Sequence[str] | None = None,
    now_timestamp: float | None = None,
    timeout_seconds: float = 1800.0,
) -> WorkerResult:
    repo = repo.resolve()
    state_root = state_root.resolve()
    lock_path = state_root / "locks/external-review.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return WorkerResult("LOCKED", "", "another external reviewer owns the lock")
        try:
            return _run_locked(
                repo=repo,
                state_root=state_root,
                reviewer_command=reviewer_command,
                now_timestamp=now_timestamp if now_timestamp is not None else time.time(),
                timeout_seconds=timeout_seconds,
            )
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the independent reviewer worker")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--poll-seconds", type=float, default=20.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--reviewer-command",
        help="test/operations override parsed with shell-like quoting; no shell is invoked",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = tuple(shlex.split(args.reviewer_command)) if args.reviewer_command else None

    def request_shutdown(signum: int, _frame: object) -> None:
        raise WorkerShutdown(f"signal:{signum}")

    for signal_number in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(signal_number, request_shutdown)
    try:
        while True:
            result = run_once(
                repo=args.repo,
                state_root=args.state_root,
                reviewer_command=command,
            )
            print(
                json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True),
                flush=True,
            )
            if args.once:
                return 0 if result.status not in {"INVALID", "INVALID_VERDICT"} else 1
            time.sleep(max(1.0, args.poll_seconds))
    except WorkerShutdown:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

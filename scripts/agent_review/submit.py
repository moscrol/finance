from __future__ import annotations

import argparse
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Mapping, Sequence

from scripts.agent_review.contract import (
    PRODUCER_IDENTITY,
    REVIEW_ID_PATTERN,
    ReviewRequest,
    discover_artifact_tests,
    git_output,
    is_ancestor,
    sha256_file,
    validate_request,
)


DEFAULT_STATE_ROOT = Path(
    os.environ.get(
        "AGENT_REVIEW_ROOT",
        "/Users/a77/.finance-runtime/agent-review-loop",
    )
)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _next_review_id(request_dir: Path) -> str:
    largest = 0
    for path in request_dir.glob("ARL-*.json"):
        match = REVIEW_ID_PATTERN.fullmatch(path.stem)
        if match:
            largest = max(largest, int(match.group(1)))
    return f"ARL-{largest + 1:04d}"


def _latest_review_id(request_dir: Path) -> str | None:
    review_ids = [
        path.stem
        for path in request_dir.glob("ARL-*.json")
        if REVIEW_ID_PATTERN.fullmatch(path.stem)
    ]
    if not review_ids:
        return None
    return max(review_ids, key=lambda value: int(value.rsplit("-", 1)[-1]))


def _load_dependency(state_root: Path, review_id: str) -> Mapping[str, object]:
    if not REVIEW_ID_PATTERN.fullmatch(review_id):
        raise ValueError(f"invalid dependency review id: {review_id}")
    path = state_root / "requests" / f"{review_id}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"dependency request is missing or invalid: {review_id}") from exc
    if not isinstance(raw, dict) or raw.get("review_id") != review_id:
        raise ValueError(f"dependency request identity mismatch: {review_id}")
    return raw


def _review_number(review_id: str) -> int:
    return int(review_id.rsplit("-", 1)[-1])


def _repair_root(
    state_root: Path,
    review_id: str,
) -> tuple[str, Mapping[str, object]]:
    current_id = review_id
    seen: set[str] = set()
    while True:
        if current_id in seen:
            raise ValueError("supersedes chain contains a cycle")
        seen.add(current_id)
        raw = _load_dependency(state_root, current_id)
        parent = raw.get("supersedes")
        if not isinstance(parent, str) or not parent:
            return current_id, raw
        current_id = parent


def request_to_dict(request: ReviewRequest) -> dict[str, object]:
    return {
        "schema_version": request.schema_version,
        "review_id": request.review_id,
        "commit": request.commit,
        "parent_commit": request.parent_commit,
        "branch": request.branch,
        "producer": request.producer,
        "scope": request.scope,
        "artifacts": list(request.artifacts),
        "artifact_tests": {
            artifact: list(tests) for artifact, tests in request.artifact_tests.items()
        },
        "required_checks": list(request.required_checks),
        "depends_on": list(request.depends_on),
        "supersedes": request.supersedes,
        "intensity": request.intensity,
        "created_at": request.created_at,
        "status": request.status,
    }


def submit_request(
    *,
    repo: Path,
    state_root: Path = DEFAULT_STATE_ROOT,
    scope: str,
    artifacts: Sequence[str],
    required_checks: Sequence[str],
    intensity: str,
    depends_on: Sequence[str] = (),
    supersedes: str | None = None,
    created_at: str | None = None,
    test_waivers: Mapping[str, str] | None = None,
) -> ReviewRequest:
    """Write one request whose authority-bearing fields come from Git and code."""

    repo = repo.resolve()
    state_root = state_root.resolve()
    if test_waivers:
        # The schema intentionally has no waiver field yet. Rejecting all
        # waivers is safer than accepting one that the reviewer cannot verify.
        raise ValueError("test waiver is not supported for authority-bearing requests")
    artifact_tuple = tuple(artifacts)
    check_tuple = tuple(required_checks)
    dependency_tuple = tuple(depends_on)
    lock_path = state_root / "locks/submit.lock"
    with _exclusive_lock(lock_path):
        request_dir = state_root / "requests"
        request_dir.mkdir(parents=True, exist_ok=True)
        latest_review_id = _latest_review_id(request_dir)
        if (
            latest_review_id is not None
            and latest_review_id not in dependency_tuple
        ):
            raise ValueError(
                f"new request must depend on latest request: {latest_review_id}"
            )
        tip = git_output(repo, "rev-parse", "HEAD")
        dependency_commits: dict[str, str] = {}
        for dependency in dependency_tuple:
            raw_dependency = _load_dependency(state_root, dependency)
            dependency_commit = str(raw_dependency.get("commit", ""))
            if not is_ancestor(repo, dependency_commit, tip):
                raise ValueError(f"dependency commit is not on current branch: {dependency}")
            dependency_commits[dependency] = dependency_commit
        if supersedes is not None:
            _load_dependency(state_root, supersedes)
            if intensity not in {"milestone", "release"}:
                raise ValueError("a superseding repair request must use milestone intensity")
            if f"repair:{supersedes}" not in check_tuple:
                raise ValueError(
                    f"a superseding request must include required check repair:{supersedes}"
                )
            repair_root_id, repair_root_request = _repair_root(state_root, supersedes)
            superseded_number = _review_number(repair_root_id)
            latest_number = _review_number(latest_review_id or supersedes)
            required_artifacts: set[str] = set()
            for path in request_dir.glob("ARL-*.json"):
                if not REVIEW_ID_PATTERN.fullmatch(path.stem):
                    continue
                number = _review_number(path.stem)
                if superseded_number <= number <= latest_number:
                    raw = _load_dependency(state_root, path.stem)
                    raw_artifacts = raw.get("artifacts")
                    if isinstance(raw_artifacts, list):
                        required_artifacts.update(
                            item for item in raw_artifacts if isinstance(item, str)
                        )
            missing_artifacts = required_artifacts.difference(artifact_tuple)
            if missing_artifacts:
                raise ValueError(
                    "superseding repair must include all tainted artifacts: "
                    + ", ".join(sorted(missing_artifacts))
                )

        review_id = _next_review_id(request_dir)
        commit = tip
        parent_commit = (
            str(repair_root_request.get("parent_commit") or "")
            if supersedes is not None
            else (
                dependency_commits[max(dependency_tuple, key=_review_number)]
                if dependency_commits
                else git_output(repo, "rev-parse", "HEAD^1")
            )
        )
        if supersedes is not None and not parent_commit:
            root_commit = str(repair_root_request.get("commit") or "")
            parent_commit = git_output(repo, "rev-parse", f"{root_commit}^1")
        branch = git_output(repo, "branch", "--show-current")
        if not branch:
            raise ValueError("cannot submit from a detached HEAD")
        artifact_tests = discover_artifact_tests(
            repo,
            artifact_tuple,
            parent_commit=parent_commit,
            commit=commit,
        )
        payload: dict[str, object] = {
            "schema_version": 3,
            "review_id": review_id,
            "commit": commit,
            "parent_commit": parent_commit,
            "branch": branch,
            "producer": PRODUCER_IDENTITY,
            "scope": scope,
            "artifacts": list(artifact_tuple),
            "artifact_tests": {
                artifact: list(tests) for artifact, tests in artifact_tests.items()
            },
            "required_checks": list(check_tuple),
            "depends_on": list(dependency_tuple),
            "supersedes": supersedes,
            "intensity": intensity,
            "created_at": created_at or datetime.now().astimezone().isoformat(),
            "status": "ready",
        }
        validation = validate_request(payload, repo=repo)
        if not validation.valid or validation.request is None:
            joined = ", ".join(validation.errors)
            raise ValueError(f"request failed mechanical validation: {joined}")

        request_path = request_dir / f"{review_id}.json"
        if request_path.exists():
            raise FileExistsError(f"request already exists: {request_path}")
        _atomic_json(request_path, payload)
        claim_payload = {
            "schema_version": 1,
            "review_id": review_id,
            "commit": commit,
            "request_sha256": sha256_file(request_path),
            "submitted_at": payload["created_at"],
            "producer": PRODUCER_IDENTITY,
        }
        _atomic_json(state_root / "claims" / f"{review_id}.json", claim_payload)
        return validation.request


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit an immutable agent review request")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--artifact", action="append", required=True)
    parser.add_argument("--required-check", action="append", required=True)
    parser.add_argument("--intensity", choices=("light", "milestone", "release"), required=True)
    parser.add_argument("--depends-on", action="append", default=[])
    parser.add_argument("--supersedes")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    request = submit_request(
        repo=args.repo,
        state_root=args.state_root,
        scope=args.scope,
        artifacts=args.artifact,
        required_checks=args.required_check,
        intensity=args.intensity,
        depends_on=args.depends_on,
        supersedes=args.supersedes,
    )
    print(json.dumps(request_to_dict(request), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

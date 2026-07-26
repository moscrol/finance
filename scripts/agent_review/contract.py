from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping


PRODUCER_IDENTITY = "codex:producer"
EXTERNAL_REVIEWER = "claude:independent-reviewer"
PROVISIONAL_REVIEWER = "codex:producer-fallback"
VALID_INTENSITIES = frozenset({"light", "milestone", "release"})
VALID_REQUEST_STATUS = "ready"
REVIEW_ID_PATTERN = re.compile(r"^ARL-(\d{4,})$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")

_FORBIDDEN_SUFFIXES = {
    ".db",
    ".duckdb",
    ".pdf",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".zip",
}
_FORBIDDEN_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__MACOSX",
    "__pycache__",
    "cache",
    "node_modules",
    "venv",
}


class GateState(str, Enum):
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    EXTERNAL_PASS = "EXTERNAL_PASS"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    PROVISIONAL_PASS = "PROVISIONAL_PASS"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ReviewRequest:
    schema_version: int
    review_id: str
    commit: str
    parent_commit: str
    branch: str
    producer: str
    scope: str
    artifacts: tuple[str, ...]
    artifact_tests: Mapping[str, tuple[str, ...]]
    required_checks: tuple[str, ...]
    depends_on: tuple[str, ...]
    supersedes: str | None
    intensity: str
    created_at: str
    status: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]
    request: ReviewRequest | None = None


@dataclass(frozen=True)
class LegacyClassification:
    review_id: str
    state: str
    commit: str
    reason: str


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def git_output(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout.strip()


def commit_exists(repo: Path, commit: str) -> bool:
    if not COMMIT_PATTERN.fullmatch(commit):
        return False
    return _git(repo, "cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode == 0


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    if not commit_exists(repo, ancestor) or not commit_exists(repo, descendant):
        return False
    return (
        _git(repo, "merge-base", "--is-ancestor", ancestor, descendant, check=False).returncode
        == 0
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _dedupe_errors(errors: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(errors))


def _safe_repo_path(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip() or "\\" in raw:
        return None
    value = raw.strip()
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        return None
    if any(part in _FORBIDDEN_PARTS for part in path.parts):
        return None
    if any(part.startswith(".env") for part in path.parts):
        return None
    if path.suffix.lower() in _FORBIDDEN_SUFFIXES:
        return None
    if path.name == ".DS_Store" or path.name.startswith("._"):
        return None
    return value


def _tuple_of_strings(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        items.append(item.strip())
    if len(set(items)) != len(items):
        return None
    return tuple(items)


def _path_exists_at_commit(repo: Path, commit: str, path: str) -> bool:
    return _git(repo, "cat-file", "-e", f"{commit}:{path}", check=False).returncode == 0


def _test_paths_at_commit(repo: Path, commit: str) -> tuple[str, ...]:
    result = _git(repo, "ls-tree", "-r", "--name-only", commit, check=False)
    if result.returncode != 0:
        return ()
    return tuple(
        line
        for line in result.stdout.splitlines()
        if line.endswith(".py")
        and (PurePosixPath(line).name.startswith("test_") or "/tests/" in f"/{line}")
    )


def _module_name(artifact: str) -> str:
    path = PurePosixPath(artifact)
    without_suffix = path.with_suffix("")
    return ".".join(without_suffix.parts)


def discover_artifact_tests(
    repo: Path,
    artifacts: tuple[str, ...],
    *,
    parent_commit: str,
    commit: str,
) -> Mapping[str, tuple[str, ...]]:
    """Recompute all directly discoverable tests for each Python artifact."""

    test_paths = _test_paths_at_commit(repo, commit)
    changed_result = _git(
        repo,
        "diff",
        "--name-only",
        f"{parent_commit}..{commit}",
        check=False,
    )
    changed_tests = {
        line
        for line in changed_result.stdout.splitlines()
        if line in test_paths and PurePosixPath(line).name.startswith("test_")
    }
    result: dict[str, tuple[str, ...]] = {}
    content_cache: dict[str, str] = {}
    for artifact in artifacts:
        artifact_path = PurePosixPath(artifact)
        module = _module_name(artifact)
        conventional = {
            str(PurePosixPath("intelligence/tests") / f"test_{artifact_path.stem}.py"),
            str(artifact_path.parent / "tests" / f"test_{artifact_path.stem}.py"),
        }
        found = {candidate for candidate in conventional if candidate in test_paths}
        import_needles = (
            f"import {module}",
            f"from {module} import",
            f"from {module.rsplit('.', 1)[0]} import {module.rsplit('.', 1)[-1]}",
        )
        for test_path in test_paths:
            if test_path not in content_cache:
                shown = _git(repo, "show", f"{commit}:{test_path}", check=False)
                content_cache[test_path] = shown.stdout if shown.returncode == 0 else ""
            if any(needle in content_cache[test_path] for needle in import_needles):
                found.add(test_path)
        # Changed tests are review obligations for every artifact in the slice;
        # the reviewer can then prove they do not hide a cross-artifact change.
        found.update(changed_tests)
        result[artifact] = tuple(sorted(found))
    return MappingProxyType(result)


def _parse_request(raw: Mapping[str, Any], errors: list[str]) -> ReviewRequest | None:
    expected_keys = {
        "schema_version",
        "review_id",
        "commit",
        "parent_commit",
        "branch",
        "producer",
        "scope",
        "artifacts",
        "artifact_tests",
        "required_checks",
        "depends_on",
        "supersedes",
        "intensity",
        "created_at",
        "status",
    }
    if set(raw) != expected_keys:
        errors.append("request_fields")
    schema_version = raw.get("schema_version")
    if schema_version != 2:
        errors.append("schema_version")
    review_id = raw.get("review_id")
    if not isinstance(review_id, str) or not REVIEW_ID_PATTERN.fullmatch(review_id):
        errors.append("review_id")
    commit = raw.get("commit")
    if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit):
        errors.append("commit")
    parent_commit = raw.get("parent_commit")
    if not isinstance(parent_commit, str) or not COMMIT_PATTERN.fullmatch(parent_commit):
        errors.append("parent_commit")
    branch = raw.get("branch")
    if not isinstance(branch, str) or not branch.strip():
        errors.append("branch")
    producer = raw.get("producer")
    if producer != PRODUCER_IDENTITY:
        errors.append("producer_identity")
    scope = raw.get("scope")
    if not isinstance(scope, str) or not scope.strip() or len(scope) > 1000:
        errors.append("scope")
    artifacts = _tuple_of_strings(raw.get("artifacts"))
    if not artifacts:
        errors.append("artifacts")
        artifacts = ()
    safe_artifacts: list[str] = []
    for artifact in artifacts:
        safe = _safe_repo_path(artifact)
        if safe is None:
            errors.append("artifact_path")
        else:
            safe_artifacts.append(safe)
    required_checks = _tuple_of_strings(raw.get("required_checks"))
    if not required_checks:
        errors.append("required_checks")
        required_checks = ()
    depends_on = _tuple_of_strings(raw.get("depends_on"))
    if depends_on is None or any(not REVIEW_ID_PATTERN.fullmatch(item) for item in depends_on):
        errors.append("depends_on")
        depends_on = ()
    supersedes = raw.get("supersedes")
    if supersedes is not None and (
        not isinstance(supersedes, str) or not REVIEW_ID_PATTERN.fullmatch(supersedes)
    ):
        errors.append("supersedes")
        supersedes = None
    intensity = raw.get("intensity")
    if intensity not in VALID_INTENSITIES:
        errors.append("intensity")
    created_at = raw.get("created_at")
    try:
        parsed_created_at = datetime.fromisoformat(created_at) if isinstance(created_at, str) else None
    except ValueError:
        parsed_created_at = None
    if parsed_created_at is None or parsed_created_at.tzinfo is None:
        errors.append("created_at")
    status = raw.get("status")
    if status != VALID_REQUEST_STATUS:
        errors.append("status")

    artifact_tests_raw = raw.get("artifact_tests")
    artifact_tests: dict[str, tuple[str, ...]] = {}
    if not isinstance(artifact_tests_raw, dict):
        errors.append("artifact_tests")
    else:
        for key, value in artifact_tests_raw.items():
            safe_key = _safe_repo_path(key)
            tests = _tuple_of_strings(value)
            if safe_key is None or tests is None:
                errors.append("artifact_tests")
                continue
            safe_tests: list[str] = []
            for test in tests:
                safe_test = _safe_repo_path(test)
                if safe_test is None or not PurePosixPath(safe_test).name.startswith("test_"):
                    errors.append("artifact_tests")
                    continue
                safe_tests.append(safe_test)
            artifact_tests[safe_key] = tuple(safe_tests)

    if errors:
        # Preserve all parseable values so higher-level validation can surface
        # independent errors in one pass, but never publish a typed request.
        return None
    return ReviewRequest(
        schema_version=2,
        review_id=review_id,
        commit=commit,
        parent_commit=parent_commit,
        branch=branch.strip(),
        producer=PRODUCER_IDENTITY,
        scope=scope.strip(),
        artifacts=tuple(safe_artifacts),
        artifact_tests=MappingProxyType(artifact_tests),
        required_checks=required_checks,
        depends_on=depends_on,
        supersedes=supersedes,
        intensity=intensity,
        created_at=created_at,
        status=VALID_REQUEST_STATUS,
    )


def validate_request(raw: Mapping[str, Any], *, repo: Path) -> ValidationResult:
    errors: list[str] = []
    request = _parse_request(raw, errors)
    if request is None:
        # Continue the mechanical mapping check when enough raw data is safe.
        artifacts_raw = _tuple_of_strings(raw.get("artifacts")) or ()
        commit = raw.get("commit")
        parent = raw.get("parent_commit")
        if (
            artifacts_raw
            and isinstance(commit, str)
            and isinstance(parent, str)
            and commit_exists(repo, commit)
            and commit_exists(repo, parent)
            and all(_safe_repo_path(item) for item in artifacts_raw)
        ):
            expected = discover_artifact_tests(
                repo,
                artifacts_raw,
                parent_commit=parent,
                commit=commit,
            )
            supplied = raw.get("artifact_tests")
            normalized = {
                key: tuple(value)
                for key, value in supplied.items()
                if isinstance(key, str) and isinstance(value, list)
            } if isinstance(supplied, dict) else {}
            if normalized != dict(expected):
                errors.append("artifact_test_coverage")
        return ValidationResult(False, _dedupe_errors(errors), None)

    if not commit_exists(repo, request.commit):
        errors.append("commit")
    if not commit_exists(repo, request.parent_commit):
        errors.append("parent_commit")
    elif request.parent_commit == request.commit or not is_ancestor(
        repo, request.parent_commit, request.commit
    ):
        errors.append("parent_commit")
    for artifact in request.artifacts:
        if not _path_exists_at_commit(repo, request.commit, artifact):
            errors.append("artifact_missing")
    expected_tests = discover_artifact_tests(
        repo,
        request.artifacts,
        parent_commit=request.parent_commit,
        commit=request.commit,
    )
    if dict(request.artifact_tests) != dict(expected_tests):
        errors.append("artifact_test_coverage")
    for tests in request.artifact_tests.values():
        for test in tests:
            if not _path_exists_at_commit(repo, request.commit, test):
                errors.append("artifact_test_missing")
    return ValidationResult(not errors, _dedupe_errors(errors), request if not errors else None)


def classify_legacy_records(
    state_root: Path,
    *,
    repo: Path,
    current_tip: str | None = None,
) -> Mapping[str, LegacyClassification]:
    """Classify legacy history without rewriting it or granting authority."""

    tip = current_tip or git_output(repo, "rev-parse", "HEAD")
    request_dir = state_root / "requests"
    verdict_dir = state_root / "verdicts"
    provisional_dir = state_root / "provisional-verdicts"
    requests: list[tuple[str, str]] = []
    for path in sorted(request_dir.glob("ARL-*.json")):
        raw = _json(path)
        if raw is None or raw.get("schema_version") != 1:
            continue
        review_id = str(raw.get("review_id", ""))
        commit = str(raw.get("commit", ""))
        if REVIEW_ID_PATTERN.fullmatch(review_id) and commit_exists(repo, commit):
            requests.append((review_id, commit))

    result: dict[str, LegacyClassification] = {}
    for index, (review_id, commit) in enumerate(requests):
        provisional = _json(provisional_dir / f"{review_id}.json")
        verdict = _json(verdict_dir / f"{review_id}.json")
        if provisional is not None:
            state = "LEGACY_BOOTSTRAP_PROVISIONAL"
            reason = "legacy provisional evidence has development-only authority"
        elif verdict is not None and str(verdict.get("reviewer", "")).startswith("codex:"):
            state = "LEGACY_SELF_REVIEW"
            reason = "producer independence class cannot grant external authority"
        elif verdict is not None and not is_ancestor(repo, commit, tip):
            state = "LEGACY_ABANDONED_COMMIT"
            reason = "reviewed commit is not an ancestor of the current producer tip"
        elif verdict is not None and verdict.get("reviewer") == EXTERNAL_REVIEWER:
            state = "LEGACY_EXTERNAL_REVIEW"
            reason = "independent review retained as historical evidence"
        elif verdict is None and any(
            later_commit != commit and is_ancestor(repo, commit, later_commit)
            for _, later_commit in requests[index + 1 :]
        ):
            state = "LEGACY_SUPERSEDED_UNSEALED"
            reason = "a descendant request replaced this unreviewed slice"
        elif verdict is None:
            state = "LEGACY_UNSEALED"
            reason = "no verdict exists"
        else:
            state = "LEGACY_INVALID_REVIEW"
            reason = "legacy verdict has no recognized authority"
        result[review_id] = LegacyClassification(review_id, state, commit, reason)
    return MappingProxyType(result)

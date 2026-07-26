from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.agent_review.contract import (
    EXTERNAL_REVIEWER,
    PRODUCER_IDENTITY,
    classify_legacy_records,
    discover_artifact_tests,
    sha256_file,
    validate_request,
)


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


@pytest.fixture()
def review_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    (repo / "intelligence/services").mkdir(parents=True)
    (repo / "intelligence/tests").mkdir(parents=True)
    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (repo / "intelligence/tests/test_evidence_ledger.py").write_text(
        "from intelligence.services import evidence_ledger\n\n"
        "def test_value():\n    assert evidence_ledger.VALUE == 1\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "review@example.com")
    _git(repo, "config", "user.name", "Review Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    parent = _git(repo, "rev-parse", "HEAD")
    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "change ledger")
    commit = _git(repo, "rev-parse", "HEAD")
    return repo, parent, commit


def _request(parent: str, commit: str, **overrides: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "schema_version": 2,
        "review_id": "ARL-0020",
        "commit": commit,
        "parent_commit": parent,
        "branch": "main",
        "producer": PRODUCER_IDENTITY,
        "scope": "evidence ledger contract",
        "artifacts": ["intelligence/services/evidence_ledger.py"],
        "artifact_tests": {
            "intelligence/services/evidence_ledger.py": [
                "intelligence/tests/test_evidence_ledger.py"
            ]
        },
        "required_checks": ["run focused evidence ledger tests"],
        "depends_on": [],
        "supersedes": None,
        "intensity": "light",
        "created_at": "2026-07-26T12:00:00+08:00",
        "status": "ready",
    }
    raw.update(overrides)
    return raw


def test_schema2_request_accepts_exact_mechanical_contract(review_repo):
    repo, parent, commit = review_repo

    result = validate_request(_request(parent, commit), repo=repo)

    assert result.valid
    assert result.errors == ()
    assert result.request is not None
    assert result.request.commit == commit


def test_schema2_request_rejects_unknown_identity_and_missing_mapping(review_repo):
    repo, parent, commit = review_repo
    raw = _request(
        parent,
        commit,
        producer="codex:subagent",
        artifact_tests={},
    )

    result = validate_request(raw, repo=repo)

    assert not result.valid
    assert "producer_identity" in result.errors
    assert "artifact_test_coverage" in result.errors


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("schema_version", 1, "schema_version"),
        ("review_id", "review-20", "review_id"),
        ("intensity", "heavy", "intensity"),
        ("status", "draft", "status"),
        ("created_at", "yesterday", "created_at"),
    ],
)
def test_request_rejects_invalid_scalar_fields(review_repo, field, value, expected):
    repo, parent, commit = review_repo

    result = validate_request(_request(parent, commit, **{field: value}), repo=repo)

    assert expected in result.errors


def test_request_rejects_non_descendant_parent(review_repo):
    repo, _parent, commit = review_repo

    result = validate_request(_request(commit, commit), repo=repo)

    assert "parent_commit" in result.errors


@pytest.mark.parametrize(
    "artifact",
    ["../secret.py", ".env.production", "db/market.duckdb", "cache/value.pyc"],
)
def test_request_rejects_unsafe_artifact_paths(review_repo, artifact):
    repo, parent, commit = review_repo

    result = validate_request(
        _request(
            parent,
            commit,
            artifacts=[artifact],
            artifact_tests={artifact: []},
        ),
        repo=repo,
    )

    assert "artifact_path" in result.errors


def test_discovery_finds_conventional_and_exact_import_tests(review_repo):
    repo, parent, commit = review_repo
    extra = repo / "intelligence/tests/test_review_import_hit.py"
    extra.write_text(
        "from intelligence.services.evidence_ledger import VALUE\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add import test")
    commit = _git(repo, "rev-parse", "HEAD")

    found = discover_artifact_tests(
        repo,
        ("intelligence/services/evidence_ledger.py",),
        parent_commit=parent,
        commit=commit,
    )

    assert found["intelligence/services/evidence_ledger.py"] == (
        "intelligence/tests/test_evidence_ledger.py",
        "intelligence/tests/test_review_import_hit.py",
    )


def test_sha256_file_hashes_exact_bytes(tmp_path: Path):
    path = tmp_path / "request.json"
    path.write_bytes(b"{}\n")

    assert sha256_file(path) == hashlib.sha256(b"{}\n").hexdigest()


def test_legacy_verdicts_are_classified_without_mutation(review_repo, tmp_path: Path):
    repo, _parent, commit = review_repo
    root = tmp_path / "state"
    (root / "requests").mkdir(parents=True)
    (root / "verdicts").mkdir()
    (root / "provisional-verdicts").mkdir()
    request = {
        "schema_version": 1,
        "review_id": "ARL-0001",
        "commit": commit,
        "status": "ready",
    }
    verdict = {
        "schema_version": 1,
        "review_id": "ARL-0001",
        "commit": commit,
        "status": "PASS",
        "reviewer": "codex:/root/spec_reviewer",
    }
    request_path = root / "requests/ARL-0001.json"
    verdict_path = root / "verdicts/ARL-0001.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    verdict_path.write_text(json.dumps(verdict), encoding="utf-8")
    before = sha256_file(verdict_path)

    classifications = classify_legacy_records(root, repo=repo)

    assert classifications["ARL-0001"].state == "LEGACY_SELF_REVIEW"
    assert sha256_file(verdict_path) == before


def test_legacy_external_review_is_distinct_from_self_review(review_repo, tmp_path: Path):
    repo, _parent, commit = review_repo
    root = tmp_path / "state"
    (root / "requests").mkdir(parents=True)
    (root / "verdicts").mkdir()
    (root / "provisional-verdicts").mkdir()
    (root / "requests/ARL-0014.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "review_id": "ARL-0014",
                "commit": commit,
                "status": "ready",
            }
        ),
        encoding="utf-8",
    )
    (root / "verdicts/ARL-0014.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "review_id": "ARL-0014",
                "commit": commit,
                "status": "CHANGES_REQUIRED",
                "reviewer": EXTERNAL_REVIEWER,
            }
        ),
        encoding="utf-8",
    )

    classifications = classify_legacy_records(root, repo=repo)

    assert classifications["ARL-0014"].state == "LEGACY_EXTERNAL_REVIEW"

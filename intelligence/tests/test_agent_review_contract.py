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
from scripts.agent_review.submit import submit_request
from scripts.agent_review.validate_verdict import (
    validate_verdict,
    validate_verdict_file,
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


def test_submit_discovers_tests_and_hashes_immutable_request(
    review_repo, tmp_path: Path
):
    repo, _parent, commit = review_repo
    state_root = tmp_path / "state"

    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="evidence ledger slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run focused evidence ledger tests",),
        intensity="light",
        created_at="2026-07-26T12:00:00+08:00",
    )

    assert request.commit == commit
    assert request.review_id == "ARL-0001"
    assert request.artifact_tests["intelligence/services/evidence_ledger.py"] == (
        "intelligence/tests/test_evidence_ledger.py",
    )
    request_path = state_root / "requests/ARL-0001.json"
    claim = json.loads((state_root / "claims/ARL-0001.json").read_text())
    assert claim["request_sha256"] == sha256_file(request_path)
    assert claim["commit"] == commit
    assert not tuple(state_root.rglob("*.tmp"))


def test_submit_allocates_ids_under_one_state_root(review_repo, tmp_path: Path):
    repo, _parent, _commit = review_repo
    state_root = tmp_path / "state"
    kwargs = {
        "repo": repo,
        "state_root": state_root,
        "scope": "evidence ledger slice",
        "artifacts": ("intelligence/services/evidence_ledger.py",),
        "required_checks": ("run focused evidence ledger tests",),
        "intensity": "light",
        "created_at": "2026-07-26T12:00:00+08:00",
    }

    first = submit_request(**kwargs)
    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 3\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "next review slice")
    second = submit_request(**kwargs, depends_on=(first.review_id,))

    assert first.review_id == "ARL-0001"
    assert second.review_id == "ARL-0002"
    assert second.depends_on == ("ARL-0001",)
    assert second.parent_commit == first.commit


def test_submit_cannot_bypass_latest_request_dependency(review_repo, tmp_path: Path):
    repo, _parent, _commit = review_repo
    state_root = tmp_path / "state"
    kwargs = {
        "repo": repo,
        "state_root": state_root,
        "scope": "evidence ledger slice",
        "artifacts": ("intelligence/services/evidence_ledger.py",),
        "required_checks": ("run focused evidence ledger tests",),
        "intensity": "light",
    }
    submit_request(**kwargs)

    with pytest.raises(ValueError, match="latest request"):
        submit_request(**kwargs)


def test_submit_rejects_missing_dependency(review_repo, tmp_path: Path):
    repo, _parent, _commit = review_repo

    with pytest.raises(ValueError, match="dependency"):
        submit_request(
            repo=repo,
            state_root=tmp_path / "state",
            scope="evidence ledger slice",
            artifacts=("intelligence/services/evidence_ledger.py",),
            required_checks=("run focused evidence ledger tests",),
            intensity="light",
            depends_on=("ARL-0999",),
        )


def test_submit_rejects_waiver_for_gate_artifact(review_repo, tmp_path: Path):
    repo, _parent, _commit = review_repo

    with pytest.raises(ValueError, match="waiver"):
        submit_request(
            repo=repo,
            state_root=tmp_path / "state",
            scope="evidence ledger slice",
            artifacts=("intelligence/services/evidence_ledger.py",),
            required_checks=("run focused evidence ledger tests",),
            intensity="light",
            test_waivers={"intelligence/services/evidence_ledger.py": "no tests needed"},
        )


def test_superseding_repair_requires_milestone_and_explicit_check(
    review_repo, tmp_path: Path
):
    repo, _parent, _commit = review_repo
    state_root = tmp_path / "state"
    first = submit_request(
        repo=repo,
        state_root=state_root,
        scope="broken slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("focused",),
        intensity="light",
    )

    with pytest.raises(ValueError, match="milestone"):
        submit_request(
            repo=repo,
            state_root=state_root,
            scope="repair",
            artifacts=("intelligence/services/evidence_ledger.py",),
            required_checks=(f"repair:{first.review_id}",),
            intensity="light",
            depends_on=(first.review_id,),
            supersedes=first.review_id,
        )
    with pytest.raises(ValueError, match="required check"):
        submit_request(
            repo=repo,
            state_root=state_root,
            scope="repair",
            artifacts=("intelligence/services/evidence_ledger.py",),
            required_checks=("focused",),
            intensity="milestone",
            depends_on=(first.review_id,),
            supersedes=first.review_id,
        )


def _verdict(request, request_sha256: str, **overrides: object) -> dict[str, object]:
    checks = {
        check: {"status": "PASS", "evidence": "verified"}
        for check in request.required_checks
    }
    for tests in request.artifact_tests.values():
        for test in tests:
            checks[test] = {"status": "PASS", "evidence": "1 passed"}
    checks.update(
        {
            "git_diff_check": {"status": "PASS", "evidence": "clean"},
            "artifact_hygiene": {"status": "PASS", "evidence": "clean"},
            "canonical_safety": {"status": "PASS", "evidence": "untouched"},
        }
    )
    raw: dict[str, object] = {
        "schema_version": 2,
        "review_id": request.review_id,
        "commit": request.commit,
        "request_sha256": request_sha256,
        "status": "PASS",
        "reviewer": EXTERNAL_REVIEWER,
        "reviewer_class": "external",
        "authority": "external",
        "findings": [],
        "checks": checks,
        "reviewed_at": "2026-07-26T12:30:00+08:00",
        "summary": "All required checks pass.",
        "next_action": "continue",
    }
    raw.update(overrides)
    return raw


@pytest.mark.parametrize(
    "reviewer",
    ["codex:producer", "codex:subagent", "claude", "claude:reviewer"],
)
def test_non_whitelisted_pass_never_grants_external_authority(
    review_repo, tmp_path: Path, reviewer: str
):
    repo, _parent, _commit = review_repo
    state_root = tmp_path / "state"
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="evidence ledger slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run focused evidence ledger tests",),
        intensity="light",
    )
    request_path = state_root / "requests" / f"{request.review_id}.json"

    result = validate_verdict(
        _verdict(request, sha256_file(request_path), reviewer=reviewer),
        request=request,
        request_sha256=sha256_file(request_path),
        repo=repo,
        authority="external",
    )

    assert not result.valid
    assert "reviewer_identity" in result.errors
    assert result.authority == "none"


def test_exact_external_verdict_grants_external_authority(review_repo, tmp_path: Path):
    repo, _parent, _commit = review_repo
    state_root = tmp_path / "state"
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="evidence ledger slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run focused evidence ledger tests",),
        intensity="light",
    )
    request_path = state_root / "requests" / f"{request.review_id}.json"
    request_hash = sha256_file(request_path)

    result = validate_verdict(
        _verdict(request, request_hash),
        request=request,
        request_sha256=request_hash,
        repo=repo,
        authority="external",
    )

    assert result.valid
    assert result.authority == "external"
    assert result.status == "PASS"


def test_producer_fallback_can_only_grant_provisional_authority(
    review_repo, tmp_path: Path
):
    repo, _parent, _commit = review_repo
    state_root = tmp_path / "state"
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="evidence ledger slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run focused evidence ledger tests",),
        intensity="light",
    )
    request_path = state_root / "requests" / f"{request.review_id}.json"
    request_hash = sha256_file(request_path)
    verdict = _verdict(
        request,
        request_hash,
        reviewer="codex:producer-fallback",
        reviewer_class="producer_fallback",
        authority="provisional",
    )

    provisional = validate_verdict(
        verdict,
        request=request,
        request_sha256=request_hash,
        repo=repo,
        authority="provisional",
    )
    external = validate_verdict(
        verdict,
        request=request,
        request_sha256=request_hash,
        repo=repo,
        authority="external",
    )

    assert provisional.valid and provisional.authority == "provisional"
    assert not external.valid and external.authority == "none"


def test_mutated_request_invalidates_verdict_file(review_repo, tmp_path: Path):
    repo, _parent, _commit = review_repo
    state_root = tmp_path / "state"
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="evidence ledger slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run focused evidence ledger tests",),
        intensity="light",
    )
    request_path = state_root / "requests" / f"{request.review_id}.json"
    request_hash = sha256_file(request_path)
    verdict_path = state_root / "verdicts" / f"{request.review_id}.json"
    verdict_path.parent.mkdir(parents=True)
    verdict_path.write_text(
        json.dumps(_verdict(request, request_hash)), encoding="utf-8"
    )
    request_path.write_text(request_path.read_text() + "\n", encoding="utf-8")

    result = validate_verdict_file(
        verdict_path,
        state_root=state_root,
        repo=repo,
        authority="external",
    )

    assert not result.valid
    assert "request_hash_mismatch" in result.errors


def test_external_pass_requires_every_mechanical_check(review_repo, tmp_path: Path):
    repo, _parent, _commit = review_repo
    state_root = tmp_path / "state"
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="evidence ledger slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run focused evidence ledger tests",),
        intensity="light",
    )
    request_path = state_root / "requests" / f"{request.review_id}.json"
    request_hash = sha256_file(request_path)
    verdict = _verdict(request, request_hash)
    verdict["checks"].pop("intelligence/tests/test_evidence_ledger.py")

    result = validate_verdict(
        verdict,
        request=request,
        request_sha256=request_hash,
        repo=repo,
        authority="external",
    )

    assert not result.valid
    assert "check_manifest" in result.errors


def test_verdict_commit_must_match_request(review_repo, tmp_path: Path):
    repo, parent, _commit = review_repo
    state_root = tmp_path / "state"
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="evidence ledger slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run focused evidence ledger tests",),
        intensity="light",
    )
    request_path = state_root / "requests" / f"{request.review_id}.json"
    request_hash = sha256_file(request_path)

    result = validate_verdict(
        _verdict(request, request_hash, commit=parent),
        request=request,
        request_sha256=request_hash,
        repo=repo,
        authority="external",
    )

    assert not result.valid
    assert "verdict_commit" in result.errors


def test_verdict_for_non_ancestor_tip_has_no_authority(review_repo, tmp_path: Path):
    repo, parent, _commit = review_repo
    state_root = tmp_path / "state"
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="evidence ledger slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run focused evidence ledger tests",),
        intensity="light",
    )
    request_path = state_root / "requests" / f"{request.review_id}.json"
    request_hash = sha256_file(request_path)
    _git(repo, "checkout", "-b", "abandoned", parent)
    (repo / "unrelated.py").write_text("VALUE = 3\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "abandoned line")
    abandoned_tip = _git(repo, "rev-parse", "HEAD")

    result = validate_verdict(
        _verdict(request, request_hash),
        request=request,
        request_sha256=request_hash,
        repo=repo,
        authority="external",
        current_tip=abandoned_tip,
    )

    assert not result.valid
    assert "verdict_ancestry" in result.errors


def test_release_request_rejects_provisional_authority(review_repo, tmp_path: Path):
    repo, _parent, _commit = review_repo
    state_root = tmp_path / "state"
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="release candidate",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run full regression",),
        intensity="release",
    )
    request_path = state_root / "requests" / f"{request.review_id}.json"
    request_hash = sha256_file(request_path)

    result = validate_verdict(
        _verdict(
            request,
            request_hash,
            reviewer="codex:producer-fallback",
            reviewer_class="producer_fallback",
            authority="provisional",
        ),
        request=request,
        request_sha256=request_hash,
        repo=repo,
        authority="provisional",
    )

    assert not result.valid
    assert "release_requires_external" in result.errors

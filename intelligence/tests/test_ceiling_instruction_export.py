from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from intelligence.eval.ceiling_instruction_export import (
    audit_instruction_export,
    build_instruction_export,
)
from intelligence.eval.ceiling_leakage import ForbiddenCorpus, ForbiddenText


def _commit_repo(root: Path) -> str:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _corpus() -> ForbiddenCorpus:
    return ForbiddenCorpus(
        (
            ForbiddenText(
                source_id="question:1",
                kind="question",
                text="这是一道不会命中的冻结题目",
            ),
        )
    )


def test_build_instruction_export_is_regular_only_and_excludes_control_data(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "intelligence" / "services").mkdir(parents=True)
    (repo / "intelligence" / "services" / "allowed.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    (repo / "docs" / "verification").mkdir(parents=True)
    (repo / "docs" / "verification" / "result.md").write_text(
        "gold answer",
        encoding="utf-8",
    )
    (repo / "intelligence" / "tests").mkdir(parents=True)
    (repo / "intelligence" / "tests" / "gold.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    revision = _commit_repo(repo)

    receipt = build_instruction_export(
        source_repo=repo,
        source_revision=revision,
        output_root=tmp_path / "exports",
        corpus=_corpus(),
    )

    instruction = receipt.instruction_root
    assert (instruction / "AGENTS.md").is_file()
    assert (instruction / "intelligence" / "services" / "allowed.py").is_file()
    assert not (instruction / ".git").exists()
    assert not (instruction / "docs").exists()
    assert not (instruction / "intelligence" / "tests").exists()
    assert all(path.is_file() for path in instruction.rglob("*") if not path.is_dir())
    assert all(path.stat().st_nlink == 1 for path in instruction.rglob("*") if path.is_file())
    assert receipt.leak_scan.status == "passed"
    assert audit_instruction_export(
        receipt.component_root,
        expected_manifest_sha256=receipt.manifest_sha256,
    ).status == "valid"


def test_explicit_instruction_allowlist_precedes_leak_scan(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    services = repo / "intelligence" / "services"
    services.mkdir(parents=True)
    (services / "not_selected.py").write_text(
        "FROZEN_REFERENCE_ANSWER\n",
        encoding="utf-8",
    )
    skill = repo / "skills" / "market-overview" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("generic market overview instructions\n", encoding="utf-8")
    revision = _commit_repo(repo)
    corpus = ForbiddenCorpus(
        (
            ForbiddenText(
                source_id="reference_answer:case:1",
                kind="reference_answer",
                text="FROZEN_REFERENCE_ANSWER",
            ),
        )
    )

    receipt = build_instruction_export(
        source_repo=repo,
        source_revision=revision,
        output_root=tmp_path / "exports",
        corpus=corpus,
        include_prefixes=("skills/market-overview/",),
    )

    assert (receipt.instruction_root / "skills/market-overview/SKILL.md").is_file()
    assert not (receipt.instruction_root / "intelligence/services").exists()
    assert receipt.leak_scan.status == "passed"


def test_build_instruction_export_rejects_allowlisted_symlink(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    services = repo / "intelligence" / "services"
    services.mkdir(parents=True)
    (repo / "outside.txt").write_text("outside", encoding="utf-8")
    os.symlink("../../outside.txt", services / "escape.py")
    revision = _commit_repo(repo)

    with pytest.raises(ValueError, match="regular Git blobs"):
        build_instruction_export(
            source_repo=repo,
            source_revision=revision,
            output_root=tmp_path / "exports",
            corpus=_corpus(),
        )


def test_instruction_export_is_write_once_and_mutation_invalidates_audit(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    services = repo / "intelligence" / "services"
    services.mkdir(parents=True)
    (services / "allowed.py").write_text("VALUE = 1\n", encoding="utf-8")
    revision = _commit_repo(repo)
    receipt = build_instruction_export(
        source_repo=repo,
        source_revision=revision,
        output_root=tmp_path / "exports",
        corpus=_corpus(),
    )
    target = receipt.instruction_root / "intelligence" / "services" / "allowed.py"
    target.chmod(0o644)
    target.write_text("VALUE = 2\n", encoding="utf-8")

    assert audit_instruction_export(
        receipt.component_root,
        expected_manifest_sha256=receipt.manifest_sha256,
    ).status == "invalid"
    with pytest.raises(ValueError, match="existing instruction export is invalid"):
        build_instruction_export(
            source_repo=repo,
            source_revision=revision,
            output_root=tmp_path / "exports",
            corpus=_corpus(),
        )


def test_instruction_export_audit_recomputes_leak_scan_self_hash(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    services = repo / "intelligence" / "services"
    services.mkdir(parents=True)
    (services / "allowed.py").write_text("VALUE = 1\n", encoding="utf-8")
    revision = _commit_repo(repo)
    receipt = build_instruction_export(
        source_repo=repo,
        source_revision=revision,
        output_root=tmp_path / "exports",
        corpus=_corpus(),
    )
    scan_path = receipt.component_root / "control" / "deterministic-leak-scan.json"
    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    scan["files_scanned"] += 1
    scan_path.write_text(json.dumps(scan), encoding="utf-8")

    audit = audit_instruction_export(
        receipt.component_root,
        expected_manifest_sha256=receipt.manifest_sha256,
    )

    assert audit.status == "invalid"
    assert "deterministic_scan_self_hash_mismatch" in audit.issues


def test_instruction_export_rejects_contaminated_files_and_binds_exceptions(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    services = repo / "intelligence" / "services"
    services.mkdir(parents=True)
    (services / "clean.py").write_text("VALUE = 1\n", encoding="utf-8")
    (services / "leaked.py").write_text(
        "FROZEN_REFERENCE_ANSWER\n",
        encoding="utf-8",
    )
    (services / "generic.py").write_text("来源可追溯\n", encoding="utf-8")
    revision = _commit_repo(repo)
    corpus = ForbiddenCorpus(
        (
            ForbiddenText(
                source_id="reference:1",
                kind="reference_answer",
                text="FROZEN_REFERENCE_ANSWER",
            ),
            ForbiddenText(
                source_id="expected:source",
                kind="expected_fact",
                text="来源",
            ),
        )
    )

    with pytest.raises(ValueError, match="forbidden evaluation text"):
        build_instruction_export(
            source_repo=repo,
            source_revision=revision,
            output_root=tmp_path / "rejected",
            corpus=corpus,
            generic_exception_source_ids=("expected:source",),
        )

    clean_repo = tmp_path / "clean-repo"
    clean_services = clean_repo / "intelligence" / "services"
    clean_services.mkdir(parents=True)
    (clean_services / "clean.py").write_text("VALUE = 1\n", encoding="utf-8")
    (clean_services / "generic.py").write_text(
        "来源可追溯\n",
        encoding="utf-8",
    )
    clean_revision = _commit_repo(clean_repo)
    receipt = build_instruction_export(
        source_repo=clean_repo,
        source_revision=clean_revision,
        output_root=tmp_path / "accepted",
        corpus=ForbiddenCorpus((corpus.entries[1],)),
        generic_exception_source_ids=("expected:source",),
    )

    assert (receipt.instruction_root / "intelligence/services/clean.py").is_file()
    assert (receipt.instruction_root / "intelligence/services/generic.py").is_file()
    exception_receipt = json.loads(
        (
            receipt.component_root / "control" / "generic-leak-exceptions.json"
        ).read_text(encoding="utf-8")
    )
    assert [item["source_id"] for item in exception_receipt["exceptions"]] == [
        "expected:source"
    ]
    assert audit_instruction_export(
        receipt.component_root,
        expected_manifest_sha256=receipt.manifest_sha256,
    ).status == "valid"

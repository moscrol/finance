from __future__ import annotations

from pathlib import Path

from scripts import semantic_acceptance


def test_validate_runtime_provenance_rejects_missing_identity() -> None:
    issues = semantic_acceptance.validate_runtime_provenance(
        {"status": "healthy", "runtime": {}}
    )

    assert "runtime_source_revision_missing" in issues
    assert "runtime_dependency_fingerprint_missing" in issues


def test_validate_runtime_provenance_rejects_wrong_revision() -> None:
    health = {
        "status": "healthy",
        "runtime": {
            "source_revision": "candidate",
            "code_root": "/worktree",
            "python_executable": "/venv/bin/python",
            "dependency_fingerprint": "f" * 64,
        },
    }

    issues = semantic_acceptance.validate_runtime_provenance(
        health,
        expected_revision="8792-runtime",
    )

    assert issues == ["runtime_revision_mismatch:candidate!=8792-runtime"]


def test_run_acceptance_replays_all_questions(monkeypatch, tmp_path: Path) -> None:
    health = {
        "status": "healthy",
        "runtime": {
            "source_revision": "candidate",
            "code_root": "/worktree",
            "python_executable": "/venv/bin/python",
            "dependency_fingerprint": "f" * 64,
        },
    }
    monkeypatch.setattr(
        semantic_acceptance,
        "_request_json",
        lambda *args, **kwargs: health,
    )

    def fake_smoke(args):
        return 0, {
            "terminal_outcome": "completed",
            "semantic": {"passed": True, "issues": []},
            "run_id": args.question[:4],
        }

    monkeypatch.setattr(semantic_acceptance, "run_smoke", fake_smoke)
    output = tmp_path / "acceptance.json"
    code, summary = semantic_acceptance.run_acceptance(
        base_url="http://127.0.0.1:8795",
        user="test",
        timeout=1,
        output=output,
        expected_revision="candidate",
    )

    assert code == 0
    assert summary["terminal_outcome"] == "passed"
    assert len(summary["runs"]) == 3
    assert output.is_file()

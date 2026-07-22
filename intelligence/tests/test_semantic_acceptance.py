from __future__ import annotations

from pathlib import Path

from scripts import semantic_acceptance


def test_missing_monotonicity_evidence_is_not_reported_as_passed() -> None:
    result = semantic_acceptance.summarize_capability_monotonicity(None)

    assert result == {
        "status": "not_evaluated",
        "evidence_present": False,
        "passed": False,
        "issues": ["monotonicity_evidence_missing"],
    }


def test_cli_accepts_optional_capability_monotonicity_report(tmp_path: Path) -> None:
    report = tmp_path / "capability.json"

    args = semantic_acceptance.build_parser().parse_args(
        [
            "--base-url",
            "http://127.0.0.1:8795",
            "--user",
            "test",
            "--output",
            str(tmp_path / "acceptance.json"),
            "--capability-monotonicity-report",
            str(report),
        ]
    )

    assert args.capability_monotonicity_report == report


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
    assert summary["capability_monotonicity"]["passed"] is False
    assert output.is_file()


def test_run_acceptance_fails_on_independent_capability_regression(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        semantic_acceptance,
        "_request_json",
        lambda *args, **kwargs: {
            "status": "healthy",
            "runtime": {
                "source_revision": "candidate",
                "code_root": "/worktree",
                "python_executable": "/venv/bin/python",
                "dependency_fingerprint": "f" * 64,
            },
        },
    )
    monkeypatch.setattr(
        semantic_acceptance,
        "run_smoke",
        lambda args: (
            0,
            {
                "terminal_outcome": "completed",
                "semantic": {"passed": True, "issues": []},
                "run_id": args.question[:4],
            },
        ),
    )
    evidence = {
        "gate": "capability_monotonicity",
        "passed": False,
        "case_count": 1,
        "evaluations": [
            {
                "current": {"failure_reasons": ["capability_regression"]},
                "episode": {"failure_reasons": []},
            }
        ],
    }

    code, summary = semantic_acceptance.run_acceptance(
        base_url="http://127.0.0.1:8795",
        user="test",
        timeout=1,
        output=tmp_path / "acceptance.json",
        capability_monotonicity_evidence=evidence,
    )

    assert code == 1
    assert summary["terminal_outcome"] == "capability_regression"
    assert summary["capability_monotonicity"]["issues"] == [
        "capability_regression"
    ]

"""The offline diagnostic's CLI preserves evidence and selects an explicit code tree.

Full Workbench replays are deliberately separate, zero-provider diagnostics;
these tests stop before application imports or the process-wide network guard.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.review_probes import probe_owner_followup_contract as probe


SCRIPT = Path(probe.__file__).resolve()


def run_cli(tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *map(str, args)],
        cwd=tmp_path,
        env={
            "HOME": str(tmp_path), "PATH": os.defpath,
            "PYTHONDONTWRITEBYTECODE": "1", "GIT_OPTIONAL_LOCKS": "0",
        },
        capture_output=True, text=True, timeout=10,
    )


def test_help_works_outside_repository_without_replay(tmp_path):
    result = run_cli(tmp_path, "--help")
    assert result.returncode == 0, result.stderr
    assert "--repo-root REPO_ROOT" in result.stdout
    assert "--questions FIRST FOLLOWUP" in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("questions", [[], ["first"], ["first", "second", "third"]])
def test_question_override_requires_exactly_two_turns(tmp_path, questions):
    output = tmp_path / "evidence"
    result = run_cli(tmp_path, "--output", output, "--questions", *questions)
    assert result.returncode == 2
    assert not output.exists()


def test_existing_evidence_is_not_overwritten_with_default_root(tmp_path):
    output = tmp_path / "evidence"
    output.mkdir()
    witness = output / "first-failure.txt"
    witness.write_text("keep this failure", encoding="utf-8")
    result = run_cli(tmp_path, "--output", output)
    assert result.returncode != 0
    assert "FileExistsError" in result.stderr
    assert witness.read_text(encoding="utf-8") == "keep this failure"
    assert list(output.iterdir()) == [witness]


def test_repo_override_resolves_before_identity_and_preserves_evidence(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    alias = tmp_path / "candidate-alias"
    alias.symlink_to(candidate, target_is_directory=True)
    output = tmp_path / "evidence"
    output.mkdir()
    commands = []

    def git_identity(command, **kwargs):
        commands.append(command)
        assert kwargs == {"text": True}
        return "frozen-revision\n" if command[-2:] == ["rev-parse", "HEAD"] else ""

    monkeypatch.setattr(probe.subprocess, "check_output", git_identity)
    monkeypatch.setattr(sys, "argv", [
        str(SCRIPT), "--repo-root", str(alias), "--output", str(output),
        "--questions", "first turn", "different follow-up",
    ])
    with pytest.raises(FileExistsError):
        probe.main()
    assert commands == [
        ["git", "-C", str(candidate.resolve()), "rev-parse", "HEAD"],
        ["git", "-C", str(candidate.resolve()), "status", "--short"],
    ]
    assert not list(output.iterdir())

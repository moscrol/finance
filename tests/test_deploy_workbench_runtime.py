"""Exercise deployment rejection paths without access to production targets."""

from pathlib import Path
import shutil
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/deploy_workbench_runtime.sh"
ZSH = shutil.which("zsh")
pytestmark = pytest.mark.skipif(ZSH is None, reason="deployment requires zsh")


@pytest.fixture
def deployment(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "intelligence").mkdir()
    (source / "intelligence/code.py").write_text("value = 1\n")
    (source / ".gitignore").write_text(".venv-workbench/\n")

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(source), *args], check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    git("init", "-q")
    git("add", "--", ".gitignore", "intelligence/code.py")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
    revision = git("rev-parse", "HEAD")
    effects = tmp_path / "effects"
    python = source / ".venv-workbench/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\nprintf "python\\n" >> "$EFFECTS"\nexit 0\n')
    python.chmod(0o755)
    runtime = tmp_path / "runtime"
    (runtime / "intelligence").mkdir(parents=True)
    sentinel = runtime / "intelligence/keep.txt"
    sentinel.write_text("untouched\n")
    env = {
        "HOME": str(tmp_path), "PATH": "/usr/bin:/bin",
        "WORKBENCH_REPO_ROOT": str(source),
        "WORKBENCH_RUNTIME_DIR": str(runtime),
        "WORKBENCH_SERVICE_LABEL": "invalid.test-never-start",
        "EFFECTS": str(effects),
    }

    def run(*args, explicit_source=True):
        selected_env = env.copy()
        if not explicit_source:
            selected_env.pop("WORKBENCH_REPO_ROOT")
        # Even a weakened guard cannot sync files or restart a real service.
        result = subprocess.run(
            [ZSH, "-f", "-c", """
rsync() { print -r -- rsync >> "$EFFECTS"; return 97; }
launchctl() { print -r -- launchctl >> "$EFFECTS"; return 97; }
source "$1" "${@:2}"
""", "test-deploy", str(SCRIPT), *args],
            cwd=tmp_path, env=selected_env, capture_output=True, text=True, timeout=10,
        )
        assert sentinel.read_text() == "untouched\n"
        return result

    return source, runtime, revision, effects, run


@pytest.mark.parametrize("args", [
    (), ("--bogus",), ("--apply",), ("--expect-revision",),
    ("--apply", "--expect-revision", "main"),
    ("--apply", "--expect-revision", "g" * 40),
    ("--apply", "--help"), ("--help", "--apply"),
    ("--apply", "--apply", "--expect-revision", "a" * 40),
    ("--apply", "--expect-revision", "a" * 40, "--bogus"),
    ("--expect-revision", "a" * 40),
])
def test_invalid_arguments_never_reach_deployment(deployment, args):
    _, _, _, effects, run = deployment
    result = run(*args)
    assert result.returncode == 2
    assert "Usage:" in result.stderr
    assert not effects.exists()


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_is_read_only_without_source(deployment, flag):
    _, _, _, effects, run = deployment
    result = run(flag, explicit_source=False)
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert not effects.exists()


def test_apply_requires_explicit_source(deployment):
    _, _, revision, effects, run = deployment
    result = run("--apply", "--expect-revision", revision, explicit_source=False)
    assert result.returncode == 2
    assert "WORKBENCH_REPO_ROOT" in result.stderr
    assert not effects.exists()


def test_revision_mismatch_stops_before_readiness(deployment):
    _, _, _, effects, run = deployment
    result = run("--apply", "--expect-revision", "a" * 40)
    assert result.returncode == 1
    assert "--expect-revision" in result.stderr
    assert not effects.exists()


@pytest.mark.parametrize("untracked", [False, True])
def test_dirty_source_stops_before_readiness(deployment, untracked):
    source, _, revision, effects, run = deployment
    target = "new.py" if untracked else "intelligence/code.py"
    (source / target).write_text("changed = True\n")
    result = run("--apply", "--expect-revision", revision)
    assert result.returncode == 1
    assert not effects.exists()


@pytest.mark.parametrize("kind", ["file", "directory", "dangling_link", "nested"])
def test_git_snapshot_cannot_be_overwritten(deployment, kind):
    _, runtime, revision, effects, run = deployment
    marker = runtime / ".git"
    if kind == "file":
        marker.write_text("gitdir: /missing/worktree\n")
    elif kind == "directory":
        marker.mkdir()
    elif kind == "dangling_link":
        marker.symlink_to(runtime / "missing")
    else:
        subprocess.run(["git", "init", "-q", str(runtime.parent)], check=True)
    result = run("--apply", "--expect-revision", revision)
    assert result.returncode == 1
    assert "Git" in result.stderr
    assert not effects.exists()


@pytest.mark.parametrize("external", [False, True])
def test_linked_code_directory_stops_before_readiness(deployment, external):
    _, runtime, revision, effects, run = deployment
    target = (runtime.parent if external else runtime) / "linked-code"
    (runtime / "intelligence").rename(target)
    (runtime / "intelligence").symlink_to(target, target_is_directory=True)
    result = run("--apply", "--expect-revision", revision)
    assert result.returncode == 1
    assert "intelligence/" in result.stderr
    assert not effects.exists()


def test_valid_standalone_target_reaches_intercepted_sync(deployment):
    _, _, revision, effects, run = deployment
    result = run("--apply", "--expect-revision", revision)
    assert result.returncode == 97
    assert effects.read_text().splitlines() == ["python", "rsync"]

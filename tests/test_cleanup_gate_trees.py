"""Exercise cleanup_gate_trees.sh only in disposable Git repositories."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/cleanup_gate_trees.sh"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def make_repo(tmp_path: Path, *, ignored: bool = False) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Cleanup test")
    git(repo, "config", "user.email", "cleanup@example.test")
    (repo / "file").write_text("base")
    if ignored:
        (repo / ".gitignore").write_text("evidence/\n")
        git(repo, "add", "--", "file", ".gitignore")
    else:
        git(repo, "add", "--", "file")
    git(repo, "commit", "-m", "fixture")
    return repo


def age_tree(path: Path) -> None:
    old = 946684800  # 2000-01-01 UTC
    for current, dirs, files in os.walk(path, followlinks=False):
        for name in (*dirs, *files):
            os.utime(Path(current) / name, (old, old), follow_symlinks=False)
    os.utime(path, (old, old), follow_symlinks=False)


def run_cleanup(repo: Path, home: Path, fake_lsof_body: str, *, apply: bool = True):
    fakebin = home / "bin"
    fakebin.mkdir(parents=True, exist_ok=True)
    (fakebin / "lsof").write_text(f"#!/bin/sh\n{fake_lsof_body}\n")
    (fakebin / "lsof").chmod(0o755)
    env = os.environ.copy()
    env.update(
        HOME=str(home),
        PATH=f"{fakebin}{os.pathsep}{env['PATH']}",
        LSOF_TIMEOUT="2",
    )
    args = ["bash", str(SCRIPT), "--repo", str(repo), "--days", "0"]
    if apply:
        args.append("--apply")
    return subprocess.run(args, env=env, capture_output=True, text=True, timeout=20)


def add_detached(repo: Path, path: Path) -> Path:
    git(repo, "worktree", "add", "--detach", "-q", str(path), "HEAD")
    return path


def test_lsof_failure_refuses_to_delete(tmp_path):
    repo = make_repo(tmp_path)
    candidate = add_detached(repo, tmp_path / "candidate")
    age_tree(candidate)

    result = run_cleanup(repo, tmp_path / "home", "exit 1")

    assert result.returncode == 4, result.stdout + result.stderr
    assert candidate.exists()
    assert "采样失败" in result.stderr


def test_launchd_symlink_reference_is_canonicalized(tmp_path):
    repo = make_repo(tmp_path)
    candidate = add_detached(repo, tmp_path / "candidate")
    age_tree(candidate)
    home = tmp_path / "home"
    (home / "Library/LaunchAgents").mkdir(parents=True)
    (home / "runtime").symlink_to(candidate, target_is_directory=True)
    (home / "Library/LaunchAgents/job.plist").write_text(
        f"<string>{home / 'runtime'}</string>\n"
    )

    result = run_cleanup(repo, home, "exit 0")

    assert result.returncode == 0, result.stdout + result.stderr
    assert candidate.exists()
    assert "被 launchd/启动器引用" in result.stdout


def test_ignored_content_keeps_detached_tree(tmp_path):
    repo = make_repo(tmp_path, ignored=True)
    candidate = add_detached(repo, tmp_path / "candidate")
    evidence = candidate / "evidence/important.db"
    evidence.parent.mkdir()
    evidence.write_text("keep")
    age_tree(candidate)

    result = run_cleanup(repo, tmp_path / "home", "exit 0")

    assert result.returncode == 0, result.stdout + result.stderr
    assert evidence.exists()
    assert "ignored 内容" in result.stdout


def test_old_clean_detached_tree_can_be_removed(tmp_path):
    repo = make_repo(tmp_path)
    candidate = add_detached(repo, tmp_path / "candidate")
    age_tree(candidate)

    result = run_cleanup(repo, tmp_path / "home", "exit 0")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not candidate.exists()
    assert "RM" in result.stdout

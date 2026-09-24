"""Committed-tree archive checks: local bytes are not evidence of Git inclusion."""
import hashlib
from pathlib import Path
import subprocess

import pytest

from scripts.check_evidence_archive import GIT_REDIRECT_VARS, check_archive
from tests.archive_path_cases import INVALID_REPOSITORY_PATHS


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def archive_repo(tmp_path, monkeypatch):
    # Never inherit a pre-commit alternate index or author configuration.
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Archive Test")
    git(tmp_path, "config", "user.email", "archive@example.invalid")
    git(tmp_path, "config", "commit.gpgsign", "false")
    root = tmp_path / "archive"
    root.mkdir()
    (root / "report.md").write_bytes(b"original report\n")
    (root / "run.log.txt").write_bytes(b"original log\n")
    seal(tmp_path)
    return tmp_path


def seal(repo):
    root = repo / "archive"
    manifest = root / "sha256-manifest.txt"
    files = sorted(p for p in root.iterdir() if p != manifest)
    manifest.write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(repo)}\n"
        for p in files
    ))


def commit(repo):
    git(repo, "add", "--", "archive")
    git(repo, "commit", "-qm", "archive", "--", "archive")
    return git(repo, "rev-parse", "HEAD")


def test_complete_archive_is_bound_to_commit_not_dirty_disk(archive_repo):
    repo = archive_repo
    revision = commit(repo)
    (repo / "archive" / "run.log.txt").write_text("uncommitted corruption")
    result = check_archive(repo, "archive", revision)
    assert result == {
        "revision": revision, "archive": "archive", "manifest_files": 2,
        "committed_files": 2, "ok": True, "errors": [],
    }


@pytest.mark.parametrize("fault", [
    "ignored-log", "unlisted-file", "bad-hash", "duplicate", "symlink",
    "missing-manifest", "bad-line", "outside", "self",
])
def test_archive_mutations_are_rejected(archive_repo, fault):
    repo = archive_repo
    root = repo / "archive"
    manifest = root / "sha256-manifest.txt"
    if fault == "ignored-log":
        # The log and correct manifest entry exist on disk, but not in Git.
        (repo / ".git" / "info" / "exclude").write_text("run.log.txt\n")
    elif fault == "unlisted-file":
        (root / "forgotten.md").write_text("omitted from manifest")
    elif fault == "bad-hash":
        (root / "run.log.txt").write_text("modified after seal")
    elif fault == "duplicate":
        manifest.write_text(manifest.read_text() * 2)
    elif fault == "symlink":
        (root / "run.log.txt").unlink()
        (root / "run.log.txt").symlink_to("report.md")
        seal(repo)
    elif fault == "missing-manifest":
        manifest.unlink()
    elif fault == "bad-line":
        manifest.write_text(manifest.read_text() + "malformed\n")
    elif fault in {"outside", "self"}:
        path = "outside.md" if fault == "outside" else "archive/sha256-manifest.txt"
        manifest.write_text(manifest.read_text() + f"{'0' * 64}  {path}\n")
    revision = commit(repo)
    result = check_archive(repo, "archive", revision)
    assert result["ok"] is False
    assert result["errors"]
    if fault == "ignored-log":
        assert (root / "run.log.txt").exists()
        assert "missing from commit: archive/run.log.txt" in result["errors"]


@pytest.mark.parametrize("replacement_kind", ["commit", "blob"])
def test_replacement_refs_cannot_hide_corrupt_committed_bytes(archive_repo, replacement_kind):
    repo = archive_repo
    good = commit(repo)
    good_blob = git(repo, "rev-parse", f"{good}:archive/report.md")
    (repo / "archive/report.md").write_text("corrupt bytes after sealing\n")
    corrupt = commit(repo)
    corrupt_blob = git(repo, "rev-parse", f"{corrupt}:archive/report.md")
    if replacement_kind == "commit":
        git(repo, "replace", corrupt, good)
    else:
        git(repo, "replace", corrupt_blob, good_blob)
    result = check_archive(repo, "archive", corrupt)
    assert result["revision"] == corrupt
    assert result["ok"] is False
    assert "hash mismatch: archive/report.md" in result["errors"]


@pytest.mark.parametrize("archive", INVALID_REPOSITORY_PATHS)
def test_invalid_archive_path_is_rejected(archive_repo, archive):
    revision = commit(archive_repo)
    with pytest.raises(ValueError):
        check_archive(archive_repo, archive, revision)


@pytest.mark.parametrize("key", GIT_REDIRECT_VARS)
def test_standalone_checker_rejects_inherited_git_redirection(archive_repo, monkeypatch, key):
    revision = commit(archive_repo)
    monkeypatch.setenv(key, str(archive_repo / "unexpected"))
    with pytest.raises(ValueError, match="refusing inherited Git redirection"):
        check_archive(archive_repo, "archive", revision)

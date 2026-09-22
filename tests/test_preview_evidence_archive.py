"""Use disposable Git repositories to prove preview isolation and fail-closed CLI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import preview_evidence_archive as preview


SCRIPT = Path(preview.__file__)


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def seal(repo):
    archive = repo / "archive"
    manifest = archive / "sha256-manifest.txt"
    manifest.write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  archive/{p.name}\n"
        for p in sorted(archive.iterdir()) if p != manifest
    ))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Preview Test")
    git(tmp_path, "config", "user.email", "preview@example.invalid")
    git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive/report.md").write_text("baseline\n")
    (tmp_path / "other.txt").write_text("not owned\n")
    seal(tmp_path)
    git(tmp_path, "add", "--", "archive", "other.txt")
    git(tmp_path, "commit", "-qm", "baseline", "--", "archive", "other.txt")
    return tmp_path


def cli(repo, *args):
    p = subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--repo", str(repo)],
        capture_output=True, text=True, timeout=30,
    )
    return p.returncode, json.loads(p.stdout)


def changed(repo):
    (repo / "archive/report.md").write_text("new report\n")
    (repo / "archive/new.log.txt").write_text("new evidence\n")
    seal(repo)


def commit_archive(repo):
    git(repo, "add", "--", "archive")
    git(repo, "commit", "-qm", "archive update", "--", "archive")
    return git(repo, "rev-parse", "HEAD")


def raw_commit(repo, tree, parents=(), *, message=b"raw commit\n", extra_headers=()):
    headers = [f"tree {tree}".encode()]
    headers.extend(f"parent {parent}".encode() for parent in parents)
    headers.extend(extra_headers)
    headers.extend([
        b"author Preview Test <preview@example.invalid> 1 +0000",
        b"committer Preview Test <preview@example.invalid> 1 +0000",
        b"",
    ])
    payload = b"\n".join(headers) + message
    return subprocess.run(
        ["git", "-C", str(repo), "hash-object", "-t", "commit", "-w", "--literally", "--stdin"],
        input=payload, check=True, capture_output=True,
    ).stdout.decode("ascii").strip()


def test_prepare_preserves_real_index_refs_and_other_staged_content(repo):
    (repo / "other.txt").write_text("another agent's staged work\n")
    git(repo, "add", "--", "other.txt")
    index_before = (repo / ".git/index").read_bytes()
    refs_before = git(repo, "show-ref")
    changed(repo)
    rc, result = cli(repo, "prepare", "archive")
    assert rc == 0 and result["ok"]
    assert result["phase"] == "preview_only"
    assert (repo / ".git/index").read_bytes() == index_before
    assert git(repo, "show-ref") == refs_before
    assert git(repo, "show", f"{result['preview_revision']}:other.txt") == "not owned"
    assert git(repo, "show", ":other.txt") == "another agent's staged work"
    assert result["archive_check"]["committed_files"] == 2


def test_prepare_verify_cli_success_and_unrelated_staging_survives(repo):
    changed(repo)
    (repo / "other.txt").write_text("owned by someone else\n")
    git(repo, "add", "--", "other.txt")
    rc, planned = cli(repo, "prepare", "archive")
    assert rc == 0
    actual = commit_archive(repo)
    rc, verified = cli(repo, "verify", "archive", "--preview", planned["preview_revision"], "--revision", actual)
    assert rc == 0 and verified["ok"]
    assert verified["phase"] == "committed_bytes_only"
    assert git(repo, "diff", "--cached", "--name-only") == "other.txt"


def test_explicit_handoff_is_in_preview_and_paths_are_literal(repo):
    (repo / "[handoff].md").write_text("literal name\n")
    (repo / "h.md").write_text("must not match glob\n")
    result = preview.prepare(repo, "archive", ["[handoff].md"])
    assert result["ok"]
    names = git(repo, "ls-tree", "--name-only", result["preview_revision"]).splitlines()
    assert "[handoff].md" in names
    assert "h.md" not in names


def test_prepare_in_linked_worktree_preserves_its_index(repo, tmp_path):
    linked = tmp_path.parent / (tmp_path.name + "-linked")
    git(repo, "worktree", "add", "-q", "-b", "isolated", str(linked))
    index = Path(git(linked, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    before = index.read_bytes()
    changed(linked)
    result = preview.prepare(linked, "archive", [])
    assert result["ok"]
    assert index.read_bytes() == before
    assert git(linked, "rev-parse", "HEAD") == result["base_revision"]


@pytest.mark.parametrize("fault", ["hash", "unlisted", "ignored", "symlink"])
def test_prepare_rejects_invalid_archive_with_nonzero_exit(repo, fault):
    changed(repo)
    if fault == "hash":
        (repo / "archive/report.md").write_text("changed after seal")
    elif fault == "unlisted":
        (repo / "archive/forgotten.md").write_text("not listed")
    elif fault == "ignored":
        (repo / ".git/info/exclude").write_text("new.log.txt\n")
    else:
        (repo / "archive/new.log.txt").unlink()
        (repo / "archive/new.log.txt").symlink_to("report.md")
        seal(repo)
    index = (repo / ".git/index").read_bytes()
    rc, result = cli(repo, "prepare", "archive")
    assert rc == 1 and result["ok"] is False
    assert result["errors"]
    assert (repo / ".git/index").read_bytes() == index


def test_failed_commit_cannot_pass_verify(repo):
    changed(repo)
    planned = preview.prepare(repo, "archive", [])
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    p = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.hooksPath=" + str(hook.parent),
         "commit", "-qm", "must fail", "--", "archive"], capture_output=True,
    )
    assert p.returncode != 0
    rc, result = cli(repo, "verify", "archive", "--preview", planned["preview_revision"], "--revision", "HEAD")
    assert rc == 1 and result["ok"] is False
    assert any("pinned base" in e for e in result["errors"])


def test_valid_archive_but_different_tree_is_rejected(repo):
    changed(repo)
    planned = preview.prepare(repo, "archive", [])
    (repo / "archive/report.md").write_text("drift between preview and commit\n")
    seal(repo)  # Checker alone would pass; the tree identity must reject this.
    actual = commit_archive(repo)
    rc, result = cli(repo, "verify", "archive", "--preview", planned["preview_revision"], "--revision", actual)
    assert result["archive_check"]["ok"] is True
    assert rc == 1 and "real commit tree differs from preview tree" in result["errors"]


def test_unrelated_extra_staged_file_in_real_commit_is_rejected(repo):
    changed(repo)
    planned = preview.prepare(repo, "archive", [])
    (repo / "other.txt").write_text("not in preview\n")
    git(repo, "add", "--", "archive", "other.txt")
    git(repo, "commit", "-qm", "extra file", "--", "archive", "other.txt")
    result = preview.verify(repo, "archive", planned["preview_revision"], "HEAD")
    assert result["ok"] is False
    assert "real commit tree differs from preview tree" in result["errors"]


def test_same_tree_with_wrong_parent_is_rejected(repo):
    changed(repo)
    planned = preview.prepare(repo, "archive", [])
    actual = commit_archive(repo)
    wrong = git(repo, "commit-tree", planned["tree"], "-p", actual, "-m", "wrong parent")
    result = preview.verify(repo, "archive", planned["preview_revision"], wrong)
    assert result["tree"] == result["preview_tree"]
    assert result["ok"] is False
    assert any("pinned base" in e for e in result["errors"])


def test_replaced_real_commit_cannot_disguise_different_tree(repo):
    changed(repo)
    planned = preview.prepare(repo, "archive", [])
    (repo / "archive/report.md").write_text("different formal bytes\n")
    seal(repo)
    actual = commit_archive(repo)
    git(repo, "replace", actual, planned["preview_revision"])
    rc, result = cli(repo, "verify", "archive", "--preview", planned["preview_revision"], "--revision", actual)
    assert rc == 1 and result["ok"] is False
    assert result["tree"] == git(repo, "--no-replace-objects", "rev-parse", actual + "^{tree}")
    assert "real commit tree differs from preview tree" in result["errors"]


def test_prepare_reads_original_base_tree_despite_replacement(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "other.txt").write_text("virtual replacement content\n")
    git(repo, "add", "--", "other.txt")
    tree = git(repo, "write-tree")
    replacement = git(repo, "commit-tree", tree, "-p", base, "-m", "virtual base")
    git(repo, "replace", base, replacement)
    index_before = (repo / ".git/index").read_bytes()
    refs_before = git(repo, "show-ref")
    changed(repo)
    result = preview.prepare(repo, "archive", [])
    assert result["ok"]
    assert git(repo, "--no-replace-objects", "show", f"{result['preview_revision']}:other.txt") == "not owned"
    assert (repo / ".git/index").read_bytes() == index_before
    assert git(repo, "show-ref") == refs_before


def test_graft_cannot_hide_an_extra_real_parent(repo):
    changed(repo)
    planned = preview.prepare(repo, "archive", [])
    base = planned["base_revision"]
    other = git(repo, "commit-tree", planned["tree"], "-p", base, "-m", "other parent")
    actual = git(repo, "commit-tree", planned["tree"], "-p", base, "-p", other, "-m", "merge")
    (repo / ".git/info/grafts").write_text(f"{actual} {base}\n")
    result = preview.verify(repo, "archive", planned["preview_revision"], actual)
    assert result["tree"] == result["preview_tree"]
    assert result["ok"] is False
    assert "real commit must have exactly the preview's pinned base parent" in result["errors"]


def test_replace_graft_cannot_hide_an_extra_real_parent(repo):
    changed(repo)
    planned = preview.prepare(repo, "archive", [])
    base = planned["base_revision"]
    other = git(repo, "commit-tree", planned["tree"], "-p", base, "-m", "other parent")
    actual = git(repo, "commit-tree", planned["tree"], "-p", base, "-p", other, "-m", "merge")
    git(repo, "replace", "--graft", actual, base)
    result = preview.verify(repo, "archive", planned["preview_revision"], actual)
    assert result["tree"] == result["preview_tree"]
    assert result["ok"] is False
    assert "real commit must have exactly the preview's pinned base parent" in result["errors"]


def test_non_utf8_commit_message_does_not_break_raw_parent_read(repo):
    planned = preview.prepare(repo, "archive", [])
    actual = raw_commit(
        repo,
        planned["tree"],
        [planned["base_revision"]],
        message=b"\xff\xfe non-utf8 message\n",
        extra_headers=(b"encoding GBK",),
    )
    result = preview.verify(repo, "archive", planned["preview_revision"], actual)
    assert result["ok"] is True


def test_parent_after_author_is_not_treated_as_git_parent(repo):
    planned = preview.prepare(repo, "archive", [])
    actual = raw_commit(
        repo,
        planned["tree"],
        message=b"malformed header\n",
        extra_headers=(f"author Preview Test <preview@example.invalid> 1 +0000\nparent {planned['base_revision']}".encode(),),
    )
    result = preview.verify(repo, "archive", planned["preview_revision"], actual)
    assert result["tree"] == result["preview_tree"]
    assert result["ok"] is False
    assert "real commit must have exactly the preview's pinned base parent" in result["errors"]


def test_shallow_boundary_does_not_erase_raw_parent_identity(repo):
    changed(repo)
    planned = preview.prepare(repo, "archive", [])
    actual = commit_archive(repo)
    (repo / ".git/shallow").write_text(f"{planned['preview_revision']}\n{actual}\n")
    result = preview.verify(repo, "archive", planned["preview_revision"], actual)
    assert result["ok"] is True


def test_preview_itself_is_not_a_real_commit(repo):
    result = preview.prepare(repo, "archive", [])
    rc, verified = cli(repo, "verify", "archive", "--preview", result["preview_revision"], "--revision", result["preview_revision"])
    assert rc == 1 and verified["ok"] is False
    assert any("distinct" in e for e in verified["errors"])


def test_verification_rechecks_archive_even_if_trees_match(repo):
    (repo / "archive/report.md").write_text("hash is now invalid\n")
    planned = preview.prepare(repo, "archive", [])
    assert planned["ok"] is False
    actual = commit_archive(repo)
    result = preview.verify(repo, "archive", planned["preview_revision"], actual)
    assert result["preview_tree"] == result["tree"]
    assert result["ok"] is False
    assert any(e.startswith("real commit: hash mismatch") for e in result["errors"])


@pytest.mark.parametrize("path", [
    ".", "..", "../archive", "/archive", "archive/", ":(glob)*", ":!archive", ".git/config",
])
def test_broad_escaping_or_magic_path_is_rejected(repo, path):
    with pytest.raises(ValueError, match="literal repository-relative"):
        preview.prepare(repo, "archive", [path])


@pytest.mark.parametrize("key", preview._REDIRECT)
def test_inherited_git_redirection_is_refused(repo, monkeypatch, key):
    monkeypatch.setenv(key, str(repo / "unexpected"))
    rc, result = cli(repo, "prepare", "archive")
    assert rc == 2 and result["ok"] is False
    assert "refusing inherited Git redirection" in result["error"]


def test_git_failure_is_not_a_successful_empty_result(repo, monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(128, ["git", "read-tree"])
    monkeypatch.setattr(preview, "_git", fail)
    assert preview.main(["prepare", "archive", "--repo", str(repo)]) == 2


def test_head_drift_during_preview_is_rejected(repo, monkeypatch):
    changed(repo)
    original = preview.check_archive
    def moved(*args):
        checked = original(*args)
        git(repo, "commit", "--allow-empty", "-qm", "concurrent change")
        return checked
    monkeypatch.setattr(preview, "check_archive", moved)
    result = preview.prepare(repo, "archive", [])
    assert result["ok"] is False
    assert "HEAD moved during preview; create a fresh preview" in result["errors"]

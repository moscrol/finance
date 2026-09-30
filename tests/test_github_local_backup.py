"""Real Git probes for a backup that never writes to its source."""
from __future__ import annotations

import subprocess
import json
from pathlib import Path

import pytest

from scripts import github_local_backup as backup


def git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(path), *args], check=check,
                          capture_output=True, text=True)


@pytest.fixture
def repositories(tmp_path):
    source, target = tmp_path / "github", tmp_path / "gitea.git"
    source.mkdir()
    git(source, "init", "-b", "main")
    git(source, "config", "user.email", "backup@example.test")
    git(source, "config", "user.name", "Backup test")
    git(source, "config", "commit.gpgsign", "false")
    (source / "README").write_text("initial\n")
    git(source, "add", "--", "README")
    git(source, "commit", "-m", "initial")
    subprocess.run(["git", "init", "--bare", str(target)], check=True, capture_output=True)
    settings = dict(source=str(source), target=str(target),
                    state_dir=str(tmp_path / "state"), snapshot_dir=str(tmp_path / "snapshots"))
    return source, target, settings


def test_incremental_copy_retains_deleted_refs_and_never_revives_source(repositories):
    source, target, settings = repositories
    git(source, "branch", "finished")
    first = backup.backup(settings, local_fixture=True)
    old = git(target, "rev-parse", "refs/heads/finished").stdout.strip()
    git(source, "branch", "-d", "finished")
    (source / "README").write_text("new work\n")
    git(source, "commit", "-am", "new work")
    expected = git(source, "rev-parse", "main").stdout.strip()
    second = backup.backup(settings, local_fixture=True)
    assert second["status"] == "success"
    assert git(target, "rev-parse", "main").stdout.strip() == expected
    assert git(target, "rev-parse", "finished").stdout.strip() == old
    assert git(source, "show-ref", "refs/heads/finished", check=False).returncode != 0
    assert "refs/heads/finished" in second["retained_only"]
    assert first["bundle_sha256"] != second["bundle_sha256"]
    blocked = backup.git(Path(settings["state_dir"]) / "repository.git", "remote", "get-url", "--push", "github")
    assert blocked.endswith("SOURCE_PUSH_DISABLED")
    with pytest.raises(RuntimeError, match="command failed"):
        backup.git(Path(settings["state_dir"]) / "repository.git", "push", "github", "main")
    assert git(source, "rev-parse", "main").stdout.strip() == expected


def test_divergence_is_archived_and_bundle_restores_without_github(repositories, tmp_path):
    source, target, settings = repositories
    backup.backup(settings, local_fixture=True)
    preserved = git(target, "rev-parse", "main").stdout.strip()
    (source / "README").write_text("rewritten history\n")
    git(source, "commit", "--amend", "-am", "replacement")
    git(source, "tag", "v1")
    result = backup.backup(settings, local_fixture=True)
    new = git(source, "rev-parse", "main").stdout.strip()
    assert git(target, "rev-parse", "main").stdout.strip() == preserved
    assert result["archived"]
    archive = result["backup_refs"]["refs/heads/main"]
    assert git(target, "rev-parse", archive).stdout.strip() == new
    restored = tmp_path / "restored"
    subprocess.run(["git", "clone", result["bundle"], str(restored)], check=True, capture_output=True)
    assert git(restored, "rev-parse", "HEAD").stdout.strip() == new
    assert (restored / "README").read_text() == "rewritten history\n"
    assert git(restored, "rev-parse", "v1").stdout.strip() == new


def test_same_destination_and_credential_urls_are_rejected(repositories):
    _, _, settings = repositories
    with pytest.raises(ValueError, match="must differ"):
        backup.validate({**settings, "target": settings["source"]}, local_fixture=True)
    with pytest.raises(ValueError, match="credential-free"):
        backup.validate({**settings, "source": "https://secret@github.com/owner/repo.git"})
    with pytest.raises(ValueError, match="local Gitea"):
        backup.validate({**settings, "source": "https://github.com/owner/repo.git",
                         "target": "https://github.com/owner/backup.git"})


def test_failure_retains_standalone_snapshot_and_does_not_write_source(repositories):
    source, target, settings = repositories
    # A rejecting destination must not lead to force, source writes or deletion.
    hook = target / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o700)
    before = git(source, "show-ref").stdout
    with pytest.raises(RuntimeError, match="command failed"):
        backup.backup(settings, local_fixture=True)
    assert git(source, "show-ref").stdout == before
    bundles = list(Path(settings["snapshot_dir"]).glob("*/repository.bundle"))
    assert len(bundles) == 1
    repo = Path(settings["state_dir"]) / "repository.git"
    assert backup.git(repo, "bundle", "verify", str(bundles[0]))


def test_active_reverse_mirror_refuses_destination_writes(repositories, monkeypatch):
    source, target, settings = repositories
    before = git(source, "show-ref").stdout
    monkeypatch.setattr(backup, "validate", lambda *args, **kwargs: None)
    monkeypatch.setattr(backup, "gitea_api", lambda *args: [{"mirror": "active"}])
    with pytest.raises(ValueError, match="push mirror is active"):
        backup.backup(settings)
    assert git(source, "show-ref").stdout == before
    assert git(target, "show-ref", check=False).returncode != 0
    assert list(Path(settings["snapshot_dir"]).glob("*/repository.bundle"))


@pytest.mark.parametrize("redirection", ["source", "multiple", "rewrite"])
def test_redirected_push_destinations_are_rejected_before_source_writes(repositories, redirection):
    source, target, settings = repositories
    backup.backup(settings, local_fixture=True)
    repository = Path(settings["state_dir"]) / "repository.git"
    if redirection == "rewrite":
        backup.git(repository, "config", f"url.{source}.pushInsteadOf", str(target))
    else:
        if redirection == "multiple":
            backup.git(repository, "config", "--add", "remote.gitea.pushurl", str(target))
        backup.git(repository, "config", "--add", "remote.gitea.pushurl", str(source))
    (source / "README").write_text("divergent source\n")
    git(source, "commit", "--amend", "-am", "divergent source")
    before_source = git(source, "show-ref").stdout
    before_target = git(target, "show-ref").stdout
    with pytest.raises(ValueError, match="push destinations changed"):
        backup.backup(settings, local_fixture=True)
    assert git(source, "show-ref").stdout == before_source
    assert git(target, "show-ref").stdout == before_target


def test_failed_changed_source_preserves_last_successful_bundle_and_mapping(repositories):
    source, target, settings = repositories
    first = backup.backup(settings, local_fixture=True)
    original_manifest = Path(first["manifest"]).read_bytes()
    hook = target / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o700)
    (source / "README").write_text("new source awaiting backup\n")
    git(source, "commit", "-am", "new source")
    before_source = git(source, "show-ref").stdout
    before_target = git(target, "show-ref").stdout
    with pytest.raises(RuntimeError, match="command failed"):
        backup.backup(settings, local_fixture=True)
    last = json.loads((Path(settings["state_dir"]) / "last-success.json").read_text())
    assert last == first
    assert backup.digest(Path(last["bundle"])) == first["bundle_sha256"]
    assert Path(first["manifest"]).read_bytes() == original_manifest
    pending = json.loads((Path(settings["state_dir"]) / "status.json").read_text())
    assert pending["status"] == "local_snapshot_ready"
    assert pending["bundle"] != first["bundle"]
    assert backup.digest(Path(pending["bundle"])) == pending["bundle_sha256"]
    assert git(source, "show-ref").stdout == before_source
    assert git(target, "show-ref").stdout == before_target
    hook.unlink()
    completed = backup.backup(settings, local_fixture=True)
    assert completed["status"] == "success"
    assert len(list(Path(completed["bundle"]).parent.glob("repository-*.bundle"))) == 1


def test_legacy_success_receipt_is_preserved_when_upgrade_backup_fails(repositories):
    source, target, settings = repositories
    first = backup.backup(settings, local_fixture=True)
    legacy = {**first, "bundle": str(Path(first["bundle"]).with_name("repository.bundle"))}
    backup.write_json(Path(settings["state_dir"]) / "last-success.json", legacy)
    (source / "README").write_text("upgrade source\n")
    git(source, "commit", "-am", "upgrade source")
    hook = target / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o700)
    with pytest.raises(RuntimeError, match="command failed"):
        backup.backup(settings, local_fixture=True)
    preserved = json.loads((Path(settings["state_dir"]) / "last-success.json").read_text())
    assert preserved["source_refs"] == first["source_refs"]
    assert preserved["bundle"].endswith(f"repository-{first['bundle_sha256']}.bundle")
    assert backup.digest(Path(preserved["bundle"])) == first["bundle_sha256"]
    assert json.loads(Path(preserved["manifest"]).read_text())["backup_refs"] == first["backup_refs"]

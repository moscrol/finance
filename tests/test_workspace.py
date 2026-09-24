"""Offline development foundation: wrong-tree, wrong-env and false-green probes."""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import workspace_env

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("workspace")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.delenv("FWP_WORKBENCH_PYTHON", raising=False)
    for args in (("init",), ("config", "user.email", "test@example.test"),
                 ("config", "user.name", "Workspace test"), ("config", "commit.gpgsign", "false")):
        workspace_env.git(root, *args)
    spec = dict(interpreter=".venv-workbench/bin/python", python_version="3.12.13",
                development_lock="requirements-dev.lock", required_modules=["pytest"])
    (root / "test-environment.json").write_text(json.dumps(spec))
    (root / "requirements-dev.lock").write_text("pytest==8.3.5\n")
    (root / "docs").mkdir()
    (root / "docs/agent-maps.json").write_text((ROOT / "docs/agent-maps.json").read_text())
    workspace_env.git(root, "add", "--", "test-environment.json", "requirements-dev.lock", "docs/agent-maps.json")
    workspace_env.git(root, "commit", "-m", "fixture")
    return root


def test_resolver_prefers_local_without_resolving_executable_symlink(repo):
    local = repo / ".venv-workbench/bin/python"
    local.parent.mkdir(parents=True)
    local.symlink_to(sys.executable)
    assert workspace_env.python_path(repo) == local
    assert workspace_env.python_path(repo) != local.resolve()


def test_linked_tree_reuses_venv_but_owns_its_contract(repo, tmp_path):
    shared = repo / ".venv-workbench/bin/python"
    shared.parent.mkdir(parents=True)
    shared.touch()
    linked = tmp_path / "linked"
    workspace_env.git(repo, "worktree", "add", "-b", "linked", str(linked))
    assert workspace_env.python_path(linked) == shared
    (linked / ".venv-workbench").mkdir()
    assert workspace_env.python_path(linked) == linked / ".venv-workbench/bin/python"
    (linked / ".venv-workbench").rmdir()
    (linked / ".venv-workbench").symlink_to(linked / "absent-venv")
    assert workspace_env.python_path(linked) == linked / ".venv-workbench/bin/python"
    spec = workspace_env.load_spec(linked)
    spec["interpreter"] = ".other-venv/bin/python"
    (linked / "test-environment.json").write_text(json.dumps(spec))
    assert workspace_env.python_path(linked) == linked / ".other-venv/bin/python"


def test_explicit_missing_override_never_falls_back(repo, monkeypatch):
    monkeypatch.setenv("FWP_WORKBENCH_PYTHON", "missing/bin/python")
    assert workspace_env.python_path(repo) == repo / "missing/bin/python"


def test_legacy_absolute_contract_is_supported(repo):
    spec = workspace_env.load_spec(repo)
    spec["interpreter"] = sys.executable
    assert workspace_env.python_path(repo, spec) == Path(sys.executable)


@pytest.mark.parametrize("contents", ["{}", "[]", "broken"])
def test_malformed_contract_fails_closed(repo, contents):
    (repo / "test-environment.json").write_text(contents)
    with pytest.raises(ValueError):
        workspace_env.python_path(repo)


def test_missing_contract_fails_closed(repo):
    (repo / "test-environment.json").unlink()
    with pytest.raises(OSError):
        workspace_env.python_path(repo)


def test_lock_includes_and_conflicts(workspace, tmp_path):
    lock = tmp_path / "dev.lock"
    other = tmp_path / "consumer.lock"
    other.write_text("duckdb==1.5.4\n")
    lock.write_text("-r consumer.lock\npytest==8.3.5\n")
    assert workspace.locked_packages(lock) == {"duckdb": "1.5.4", "pytest": "8.3.5"}
    lock.write_text("-r consumer.lock\nduckdb==0.0.0\n")
    with pytest.raises(ValueError, match="conflicting"):
        workspace.locked_packages(lock)
    other.write_text("-r dev.lock\n")
    with pytest.raises(ValueError, match="cyclic"):
        workspace.locked_packages(lock)


def fake_probe(*args):
    return dict(python="3.12.13", executable="fixture", versions={"pytest": "8.3.5"}, missing_modules=[])


def test_doctor_separates_environment_from_maps_and_deployment(workspace, repo, monkeypatch):
    monkeypatch.setattr(workspace, "probe_python", fake_probe)
    monkeypatch.setenv("FWP_AGENT_MEMORY", str(repo / "no-vault"))
    monkeypatch.setenv("FWP_HARNESS_REFERENCE", str(repo / "no-harness"))
    before = workspace_env.git(repo, "status", "--porcelain")
    report = workspace.doctor(repo)
    assert report["status"] == "ready"
    assert report["scope"] == "offline_development"
    assert report["production_verified"] is False
    assert report["code_map"]["status"] == "empty"
    assert len(report["maps"]) == 6
    assert all(row["validation"] == "not_run" for row in report["maps"])
    assert any(row["availability"] == "unavailable" for row in report["maps"])
    assert before == workspace_env.git(repo, "status", "--porcelain")


@pytest.mark.parametrize("change", [{"python": "3.14.0"}, {"missing_modules": ["pytest"]},
                                     {"versions": {"pytest": "0.0.0"}}])
def test_doctor_rejects_drift(workspace, repo, monkeypatch, change):
    monkeypatch.setattr(workspace, "probe_python", lambda *a: {**fake_probe(), **change})
    assert workspace.doctor(repo)["status"] == "blocked"


def test_doctor_rejects_missing_interpreter(workspace, repo):
    assert workspace.doctor(repo)["status"] == "blocked"


def test_bootstrap_plan_has_no_side_effects(workspace, repo, monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("plan must not run commands")
    monkeypatch.setattr(workspace.subprocess, "run", forbidden)
    assert workspace.bootstrap(repo, "not-a-python", install=False) == 0
    assert not (repo / ".venv-workbench").exists()


@pytest.mark.parametrize("symlink", [False, True])
def test_bootstrap_never_mutates_existing_environment(workspace, repo, symlink):
    target = repo / ".venv-workbench"
    if symlink:
        target.symlink_to(repo / "missing-shared-venv")
    else:
        target.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        workspace.bootstrap(repo, sys.executable, install=True)


def test_bootstrap_rejects_wrong_python_before_creating_venv(workspace, repo, monkeypatch):
    monkeypatch.setattr(workspace, "probe_python", lambda *a: {"python": "3.14.0"})
    with pytest.raises(ValueError, match="bootstrap Python"):
        workspace.bootstrap(repo, sys.executable, install=True)
    assert not (repo / ".venv-workbench").exists()


def test_smoke_drops_credentials_and_production_environment(workspace, repo, monkeypatch):
    spec = workspace_env.load_spec(repo)
    spec["smoke_tests"] = ["test_fixture.py"]
    (repo / "test-environment.json").write_text(json.dumps(spec))
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-secret")
    monkeypatch.setenv("FORESIGHT_USERS_DIR", "/private/production")
    monkeypatch.setenv("FWP_TEST_RECEIPT_PATH", "/private/production/receipt.json")
    monkeypatch.setattr(workspace, "git", lambda *a: "revision")
    monkeypatch.setattr(workspace, "python_path", lambda *a: Path(sys.executable))
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(workspace.subprocess, "run", run)
    assert workspace.smoke(repo) == 0
    argv, kwargs = calls[0]
    env = kwargs["env"]
    assert "scripts.workspace_smoke_guard" in argv
    for name in ("OPENAI_API_KEY", "FORESIGHT_USERS_DIR", "FWP_TEST_RECEIPT_PATH"):
        assert name not in env
    assert env["FWP_TEST_RECEIPT"] == "0"
    assert not Path(env["HOME"]).exists()  # temporary state removed on completion


def test_network_guard_rejects_connections_before_collection(tmp_path):
    test = tmp_path / "test_network.py"
    test.write_text("import socket\nsocket.create_connection(('127.0.0.1', 1))\n")
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                             "-p", "scripts.workspace_smoke_guard", str(test)],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "workspace smoke forbids network access" in result.stdout


def test_receipt_fingerprints_track_development_dependencies(monkeypatch):
    import conftest as writer
    from scripts import check_test_receipt as reader

    before = writer._dependency_fingerprint()
    assert before == reader._fingerprint()
    real_version = writer._md.version
    monkeypatch.setattr(writer._md, "version", lambda name: "0.0.0" if name == "cryptography" else real_version(name))
    assert writer._dependency_fingerprint() != before
    assert writer._dependency_fingerprint() == reader._fingerprint()


def test_resolved_runner_preserves_exit_status(repo):
    spec = workspace_env.load_spec(repo)
    spec["interpreter"] = sys.executable
    (repo / "test-environment.json").write_text(json.dumps(spec))
    result = subprocess.run([sys.executable, str(ROOT / "scripts/workspace_env.py"),
                             "--repo", str(repo), "--run", "-c", "raise SystemExit(7)"],
                            capture_output=True, text=True)
    assert result.returncode == 7


def test_map_manifest_and_corrected_doors():
    manifest = json.loads((ROOT / "docs/agent-maps.json").read_text())
    assert {m["id"] for m in manifest["maps"]} == {
        "code", "capabilities", "product-doors", "harness-layers", "closed-loop", "ledgers"}
    for item in manifest["maps"]:
        assert item["triggers"] and item["manual_review"]
        if item["repo"] == "repo":
            assert (ROOT / item["source"]).is_file()
    door = (ROOT / "docs/agent-product-door.md").read_text()
    assert "IM 入口现在 exit 2" not in door
    assert "差的成因是分层——判官在 `runtime/`" not in door
    assert "intelligence/users/<id>" not in (ROOT / "docs/learning/ledger-map.md").read_text()
    assert '"duckdb==1.4.3"' not in (ROOT / "README.md").read_text()

"""Exercise the shell entry point and the real pytest receipt writer offline."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import conftest as root_conftest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/run_main_gate.sh"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.name", "Gate test")
    git(path, "config", "user.email", "gate@example.test")
    git(path, "config", "commit.gpgsign", "false")
    (path / "test-environment.json").write_text(json.dumps({
        "interpreter": sys.executable, "required_modules": [],
        "code_path_prefixes": ["test_", "conftest.py"],
    }))
    shutil.copy2(ROOT / "conftest.py", path / "conftest.py")
    (path / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    (path / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n.ruff_cache/\n")
    git(path, "add", "--", "test-environment.json", "conftest.py", "test_sample.py", ".gitignore")
    git(path, "commit", "-m", "fixture")
    return path


def receipt(repo, **changes):
    data = {
        "revision": git(repo, "rev-parse", "HEAD"), "tree": str(repo),
        "interpreter": sys.executable, "dirty": False, "worktree_dirty_total": 0,
        "dependency_gate_bypassed": False, "target": "test_sample.py",
        "counts": {"passed": 1, "failed": 0, "error": 0, "skipped": 0},
        "failed_ids": [], "exit_status": 0,
    }
    data.update(changes)
    return data


def run_gate(repo, tmp_path, *args, extra_env=None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("FWP_", "PYTEST_", "PYTHONPATH"))}
    env.update(HOME=str(tmp_path / "home"),
               FWP_TEST_RECEIPT_DIR=str(tmp_path / "receipts"))
    env.update(extra_env or {})
    return subprocess.run(["bash", str(GATE), *args], cwd=repo, env=env,
                          capture_output=True, text=True, timeout=40)


def readback(repo, tmp_path, data, baseline=None):
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(data))
    args = ["--receipt", str(path)]
    if baseline is not None:
        other = tmp_path / "baseline.json"
        other.write_text(json.dumps(baseline))
        args += ["--baseline", str(other)]
    return run_gate(repo, tmp_path, *args)


def test_valid_receipt_readback(repo, tmp_path):
    result = readback(repo, tmp_path, receipt(repo))
    assert result.returncode == 0, result.stdout + result.stderr


def test_readback_keeps_failure_exit(repo, tmp_path):
    data = receipt(repo, counts={"passed": 1, "failed": 1, "error": 0, "skipped": 0},
                   failed_ids=["test_sample.py::test_bad"], exit_status=1)
    result = readback(repo, tmp_path, data)
    assert result.returncode == 1, result.stdout + result.stderr


@pytest.mark.parametrize("changes", [
    {"revision": "0" * 40}, {"dirty": True}, {"worktree_dirty_total": 1},
    {"tree": "/foreign/tree"}, {"tree": None}, {"tree": 123}, {"tree": ""},
    {"dependency_gate_bypassed": True}, {"interpreter": "/wrong/python"},
    {"counts": {"passed": 0, "failed": 0, "error": 0, "skipped": 1}},
    {"counts": {"passed": -1, "failed": 0, "error": 0, "skipped": 0}},
    {"counts": {"passed": True, "failed": 0, "error": 0, "skipped": 0}},
    {"exit_status": 2}, {"exit_status": None}, {"failed_ids": ["hidden failure"]},
])
def test_readback_refuses_invalid_or_untrustworthy_receipt(repo, tmp_path, changes):
    result = readback(repo, tmp_path, receipt(repo, **changes))
    assert result.returncode != 0, result.stdout + result.stderr


@pytest.mark.parametrize("data", [{}, [], {"counts": {}}])
def test_malformed_receipt_is_structured_failure(repo, tmp_path, data):
    result = readback(repo, tmp_path, data)
    assert result.returncode == 4
    assert "Traceback" not in result.stderr


def test_readback_requires_tree_even_without_a_new_pytest_process(repo, tmp_path):
    data = receipt(repo)
    del data["tree"]
    result = readback(repo, tmp_path, data)
    assert result.returncode == 4, result.stdout + result.stderr
    assert "tree" in result.stderr


def test_baseline_comparison_does_not_bypass_current_tree_identity(repo, tmp_path):
    result = readback(repo, tmp_path, receipt(repo, tree="/foreign/tree"), receipt(repo))
    assert result.returncode == 4, result.stdout + result.stderr


def test_allow_dirty_does_not_bypass_current_tree_identity(repo, tmp_path):
    path = tmp_path / "foreign-receipt.json"
    path.write_text(json.dumps(receipt(repo, tree="/foreign/tree")))
    result = run_gate(repo, tmp_path, "--receipt", str(path), "--allow-dirty")
    assert result.returncode == 4, result.stdout + result.stderr


def test_baseline_does_not_hide_interrupted_run(repo, tmp_path):
    result = readback(repo, tmp_path, receipt(repo, exit_status=2), receipt(repo))
    assert result.returncode != 0


def test_baseline_scope_must_match(repo, tmp_path):
    result = readback(repo, tmp_path, receipt(repo), receipt(repo, target="other.py"))
    assert result.returncode != 0


def test_same_known_red_is_only_explicit_baseline_comparison(repo, tmp_path):
    data = receipt(repo, counts={"passed": 1, "failed": 1, "error": 0, "skipped": 0},
                   failed_ids=["test_sample.py::test_bad"], exit_status=1)
    result = readback(repo, tmp_path, data, data)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "baseline" in result.stdout.lower()


def test_gate_uses_own_receipt_when_latest_is_overwritten(repo, tmp_path):
    # The real root hook writes first; a second plugin then replaces only latest.json.
    (repo / "conftest.py").write_text((repo / "conftest.py").read_text() + '''
class CompetingWriter:
    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_sessionfinish(self):
        yield
        other = Path(os.environ["FWP_TEST_RECEIPT_DIR"]) / "latest.json"
        other.write_text('{"revision": "foreign", "exit_status": 1}')

@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    session.config.pluginmanager.register(CompetingWriter(), "competing-writer")
''')
    git(repo, "add", "--", "conftest.py")
    git(repo, "commit", "-m", "competing latest writer")
    result = run_gate(repo, tmp_path, "--pytest-args", "-q -p no:cacheprovider test_sample.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(repo, "rev-parse", "HEAD")[:12] in result.stdout
    own = list((tmp_path / "receipts").glob("gate-*/pytest.json"))
    assert len(own) == 1
    assert json.loads(own[0].read_text())["revision"] == git(repo, "rev-parse", "HEAD")
    assert json.loads((tmp_path / "receipts/latest.json").read_text())["revision"] == "foreign"


@pytest.mark.parametrize("inherited_owner", ["", "foreign-launcher"])
def test_nested_collection_cannot_claim_parent_receipt(repo, tmp_path, inherited_owner):
    (repo / "test_sample.py").write_text('''import subprocess
import sys


def test_nested_collection():
    result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
''')
    git(repo, "add", "--", "test_sample.py")
    git(repo, "commit", "-m", "nested collection fixture")
    result = run_gate(repo, tmp_path, extra_env={
        "FWP_TEST_RECEIPT_OWNER_PID": inherited_owner,
    })
    assert result.returncode == 0, result.stdout + result.stderr
    own = list((tmp_path / "receipts").glob("gate-*/pytest.json"))
    assert len(own) == 1
    assert json.loads(own[0].read_text())["counts"]["passed"] == 1


def test_missing_current_receipt_never_reuses_stale_latest(repo, tmp_path):
    folder = tmp_path / "receipts"
    folder.mkdir()
    (folder / "latest.json").write_text(json.dumps(receipt(repo)))
    result = run_gate(repo, tmp_path, "--pytest-args", "-q test_sample.py",
                      extra_env={"FWP_TEST_RECEIPT": "0"})
    assert result.returncode == 4, result.stdout + result.stderr


def test_revision_change_during_run_is_refused(repo, tmp_path):
    (repo / "test_sample.py").write_text('''import subprocess


def test_commit():
    subprocess.run(["git", "commit", "--allow-empty", "-m", "changed during run"], check=True)
''')
    git(repo, "add", "--", "test_sample.py")
    git(repo, "commit", "-m", "revision mutation fixture")
    result = run_gate(repo, tmp_path, "--pytest-args", "-q test_sample.py")
    assert result.returncode == 4, result.stdout + result.stderr
    assert "提交或干净状态改变" in result.stderr


@pytest.mark.parametrize("changed", [{"tree": "/foreign"}, {"exit_status": 1}])
def test_process_identity_mismatch_is_refused(repo, tmp_path, changed):
    data = receipt(repo, **changed)
    if changed.get("exit_status") == 1:
        data.update(counts={"passed": 0, "failed": 1, "error": 0, "skipped": 0},
                    failed_ids=["test_sample.py::test_bad"])
    path = tmp_path / "process.json"
    path.write_text(json.dumps(data))
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/main_gate_receipt.py"), str(path),
        "--revision", git(repo, "rev-parse", "HEAD"), "--tree", str(repo), "--pytest-exit", "0",
    ], capture_output=True, text=True)
    assert result.returncode == 4
    assert "does not match" in result.stderr


def test_writer_honors_override_without_overwriting_original(tmp_path, monkeypatch):
    folder = tmp_path / "receipts"
    output = tmp_path / "run/pytest.json"
    output.parent.mkdir()
    monkeypatch.setenv("FWP_TEST_RECEIPT_DIR", str(folder))
    monkeypatch.setenv("FWP_TEST_RECEIPT_PATH", str(output))
    data = {"revision": "a" * 40, "counts": {"passed": 1}}
    assert root_conftest._write_test_receipt(data) == output
    assert json.loads(output.read_text()) == data
    with pytest.raises(FileExistsError):
        root_conftest._write_test_receipt({"revision": "b" * 40})
    assert json.loads(output.read_text()) == data


def test_default_receipt_names_cannot_collide(tmp_path, monkeypatch):
    monkeypatch.setenv("FWP_TEST_RECEIPT_DIR", str(tmp_path))
    monkeypatch.delenv("FWP_TEST_RECEIPT_PATH", raising=False)
    data = {"revision": "a" * 40}
    paths = [root_conftest._write_test_receipt(data) for _ in range(3)]
    assert len(set(paths)) == 3
    assert all(json.loads(path.read_text()) == data for path in paths)

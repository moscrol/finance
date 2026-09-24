"""Exercise the shell entry point and the real pytest receipt writer offline."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
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
    (path / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/workspace_env.py", path / "scripts/workspace_env.py")
    (path / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    (path / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n.ruff_cache/\n")
    git(path, "add", "--", "test-environment.json", "conftest.py", "test_sample.py", ".gitignore", "scripts/workspace_env.py")
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


def gate_env(tmp_path, **overrides):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("FWP_", "PYTEST_", "PYTHONPATH"))}
    env.update(HOME=str(tmp_path / "home"), PYTHONDONTWRITEBYTECODE="1",
               FWP_TEST_RECEIPT_DIR=str(tmp_path / "receipts"))
    env.update(overrides)
    return env


def run_gate(repo, tmp_path, *args, extra_env=None):
    return subprocess.run(["bash", str(GATE), *args], cwd=repo,
                          env=gate_env(tmp_path, **(extra_env or {})),
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


@pytest.mark.parametrize("mode", [
    "run", "run-same-target", "collect-same-target", "inner-failure", "outer-failure",
])
def test_inprocess_nested_pytest_keeps_outer_receipt(repo, tmp_path, mode):
    # Same-target execution/collection also prevent a target-string-only workaround.
    (repo / "test_inner.py").write_text(
        "def test_inner_one():\n    assert True\n\n\n"
        f"def test_inner_two():\n    assert {mode != 'inner-failure'}\n"
    )
    inner_args = {
        "collect-same-target": ["--collect-only", "test_sample.py"],
        "run-same-target": ["test_sample.py", "-k", "leaf"],
    }.get(mode, ["test_inner.py"])
    (repo / "test_sample.py").write_text(f'''import pytest


def test_outer():
    result = pytest.main(["-q", "-p", "no:cacheprovider", *{inner_args!r}])
    assert result == {1 if mode == "inner-failure" else 0}
    assert {mode != "outer-failure"}
''' + ("\n\ndef test_leaf():\n    assert True\n" if mode == "run-same-target" else ""))
    git(repo, "add", "--", "test_sample.py", "test_inner.py")
    git(repo, "commit", "-m", "inprocess nesting fixture")
    result = run_gate(repo, tmp_path, "--pytest-args", "-q -p no:cacheprovider test_sample.py")
    failed = int(mode == "outer-failure")
    assert result.returncode == failed, result.stdout + result.stderr
    own = list((tmp_path / "receipts").glob("gate-*/pytest.json"))
    assert len(own) == 1
    data = json.loads(own[0].read_text())
    assert data["target"] == "test_sample.py"
    passed = 1 - failed + int(mode == "run-same-target")
    # counts 自 #860 起带 xfailed/xpassed（收执对账要它们与 collected 对平）；
    # 这里要锁的仍是「外层收据只记外层那一轮」，内层的 test_inner_* 一条都不该进来。
    assert data["counts"] == {"passed": passed, "failed": failed, "error": 0, "skipped": 0,
                              "xfailed": 0, "xpassed": 0}
    assert data["failed_ids"] == (["test_sample.py::test_outer"] if failed else [])
    assert data["exit_status"] == failed
    assert "收据未写出" not in result.stdout


@pytest.mark.parametrize("first_run", ["success", "configure-error"])
@pytest.mark.parametrize("previous_owner", [None, ""])
def test_sequential_inprocess_runs_release_receipt_owner(repo, tmp_path, first_run, previous_owner):
    # Real Config cleanup, including failure before a Session can finish.
    runner = '''import json
import os
import sys
from pathlib import Path

import pytest


class FailConfigure:
    @pytest.hookimpl(trylast=True)
    def pytest_configure(self):
        raise pytest.UsageError("intentional configure failure")


out = Path(sys.argv[1])
out.mkdir()
for index in range(2):
    os.environ["FWP_TEST_RECEIPT_PATH"] = str(out / f"run-{index}.json")
    plugins = [FailConfigure()] if index == 0 and sys.argv[2] == "configure-error" else []
    result = pytest.main(["-q", "-p", "no:cacheprovider", "test_sample.py"], plugins=plugins)
    state = {"exit": int(result), "owner_after": os.environ.get("FWP_TEST_RECEIPT_OWNER_PID")}
    (out / f"state-{index}.json").write_text(json.dumps(state))
'''
    out = tmp_path / "sequential"
    env = gate_env(tmp_path)
    if previous_owner is not None:
        env["FWP_TEST_RECEIPT_OWNER_PID"] = previous_owner
    result = subprocess.run([sys.executable, "-c", runner, str(out), first_run],
                            cwd=repo, env=env, capture_output=True,
                            text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr
    for index in range(2):
        state = json.loads((out / f"state-{index}.json").read_text())
        failed_config = index == 0 and first_run == "configure-error"
        assert state == {"exit": 4 if failed_config else 0, "owner_after": previous_owner}
        path = out / f"run-{index}.json"
        if failed_config:
            assert not path.exists()
        else:
            data = json.loads(path.read_text())
            assert data["target"] == "test_sample.py"
            assert data["counts"]["passed"] == 1
    assert "收据未写出" not in result.stdout


@pytest.mark.parametrize("inherited", ["self", "foreign"])
def test_inherited_pid_alone_cannot_grant_or_release_ownership(repo, tmp_path, inherited):
    output = tmp_path / "inherited.json"
    runner = '''import os
import sys

import pytest

owner = str(os.getpid()) if sys.argv[1] == "self" else "foreign"
os.environ["FWP_TEST_RECEIPT_OWNER_PID"] = owner
assert pytest.main(["-q", "-p", "no:cacheprovider", "test_sample.py"]) == 0
assert os.environ["FWP_TEST_RECEIPT_OWNER_PID"] == owner
'''
    result = subprocess.run([sys.executable, "-c", runner, inherited], cwd=repo,
                            env=gate_env(tmp_path, FWP_TEST_RECEIPT_PATH=str(output)),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not output.exists()


def test_invocation_cannot_switch_its_claimed_receipt_path(repo, tmp_path):
    (repo / "test_sample.py").write_text('''import os


def test_switch_path():
    os.environ["FWP_TEST_RECEIPT_PATH"] += ".foreign"
''')
    git(repo, "add", "--", "test_sample.py")
    git(repo, "commit", "-m", "change claimed output fixture")
    result = run_gate(repo, tmp_path, "--pytest-args", "-q -p no:cacheprovider test_sample.py")
    assert result.returncode == 4, result.stdout + result.stderr
    assert not list((tmp_path / "receipts").rglob("pytest.json*"))


@pytest.mark.parametrize("kind", ["subprocess", "shell-gate"])
def test_nested_execution_preserves_outer_ownership(repo, tmp_path, kind):
    (repo / "test_inner.py").write_text(
        "def test_inner_one():\n    assert True\n\n\n"
        "def test_inner_two():\n    assert True\n"
    )
    command = ([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_inner.py"]
               if kind == "subprocess" else
               ["bash", str(GATE), "--pytest-args", "-q -p no:cacheprovider test_inner.py"])
    (repo / "test_sample.py").write_text(f'''import subprocess


def test_outer():
    result = subprocess.run({command!r}, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
''')
    git(repo, "add", "--", "test_sample.py", "test_inner.py")
    git(repo, "commit", "-m", "nested execution fixture")
    result = run_gate(repo, tmp_path, "--pytest-args", "-q -p no:cacheprovider test_sample.py")
    assert result.returncode == 0, result.stdout + result.stderr
    files = list((tmp_path / "receipts").glob("gate-*/pytest.json"))
    receipts = {json.loads(p.read_text())["target"]: json.loads(p.read_text()) for p in files}
    expected = {"test_sample.py": 1}
    if kind == "shell-gate":
        expected["test_inner.py"] = 2  # a new shell allocates its own path/owner
    assert len(files) == len(expected)
    assert {target: data["counts"]["passed"] for target, data in receipts.items()} == expected


def test_parallel_gates_keep_separate_receipts(repo, tmp_path):
    # A rendezvous proves both pytest processes are alive together, not just two
    # sequential successful runs. All marker files live outside the clean repo.
    (repo / "test_sample.py").write_text('''import os
import time
from pathlib import Path


def test_overlap():
    root = Path(os.environ["RENDEZVOUS"])
    root.joinpath(os.environ["PEER"]).touch()
    deadline = time.monotonic() + 10
    while len(list(root.iterdir())) != 2:
        assert time.monotonic() < deadline, "peer never started"
        time.sleep(0.01)


def test_second():
    assert True
''')
    git(repo, "add", "--", "test_sample.py")
    git(repo, "commit", "-m", "concurrent gates fixture")
    meet = tmp_path / "meet"
    meet.mkdir()
    targets = ["test_sample.py", "test_sample.py::test_overlap"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_gate, repo, tmp_path, "--pytest-args",
                               f"-q -p no:cacheprovider {target}",
                               extra_env={"RENDEZVOUS": str(meet), "PEER": str(i)})
                   for i, target in enumerate(targets)]
        results = [future.result(timeout=45) for future in futures]
    assert all(r.returncode == 0 for r in results), [(r.stdout, r.stderr) for r in results]
    own = list((tmp_path / "receipts").glob("gate-*/pytest.json"))
    assert len(own) == 2
    assert {json.loads(p.read_text())["target"]: json.loads(p.read_text())["counts"]["passed"]
            for p in own} == dict(zip(targets, [2, 1], strict=True))


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


def _commit_sample(repo, body):
    (repo / "test_sample.py").write_text(body)
    git(repo, "add", "--", "test_sample.py")
    git(repo, "commit", "-m", "basetemp fixture")


USES_TMP = "def test_ok(tmp_path):\n    (tmp_path / 'x').write_text('1')\n"


def test_green_gate_removes_explicit_basetemp(repo, tmp_path):
    # 绿了的 basetemp 没有证据价值；不清就是 2026-09-23 盘上那 30 GB。
    _commit_sample(repo, USES_TMP)
    bt = tmp_path / "bt"
    result = run_gate(repo, tmp_path, "--pytest-args",
                      f"-q -p no:cacheprovider --basetemp={bt} test_sample.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not bt.exists()
    assert "basetemp 已清" in result.stdout


@pytest.mark.parametrize("target", ["repo-file", "repo-parent"])
def test_gate_refuses_basetemp_overlapping_repo(repo, tmp_path, target):
    _commit_sample(repo, USES_TMP)
    basetemp = repo / "test_sample.py" if target == "repo-file" else tmp_path
    before = (repo / "test_sample.py").read_text()
    result = run_gate(repo, tmp_path, "--pytest-args",
                      f"-q -p no:cacheprovider --basetemp={basetemp} test_sample.py")
    assert result.returncode == 4, result.stdout + result.stderr
    assert "basetemp 与仓库树有包含关系" in result.stderr
    assert (repo / "test_sample.py").read_text() == before


def test_red_gate_keeps_basetemp_as_evidence(repo, tmp_path):
    _commit_sample(repo, USES_TMP.replace("write_text('1')", "write_text('1')\n    assert False"))
    bt = tmp_path / "bt"
    result = run_gate(repo, tmp_path, "--pytest-args",
                      f"-q -p no:cacheprovider --basetemp={bt} test_sample.py")
    assert result.returncode != 0
    assert bt.exists()
    assert "basetemp 已清" not in result.stdout


def test_keep_flag_preserves_basetemp_on_green(repo, tmp_path):
    _commit_sample(repo, USES_TMP)
    bt = tmp_path / "bt"
    # 空格分隔的 "--basetemp DIR" 写法也要认。
    result = run_gate(repo, tmp_path, "--pytest-args",
                      f"-q -p no:cacheprovider --basetemp {bt} test_sample.py",
                      extra_env={"GATE_KEEP_BASETEMP": "1"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert bt.exists()


def test_gate_without_basetemp_flag_touches_nothing(repo, tmp_path):
    _commit_sample(repo, USES_TMP)
    result = run_gate(repo, tmp_path, "--pytest-args", "-q -p no:cacheprovider test_sample.py")
    assert result.returncode == 0, result.stdout + result.stderr
    # 收据路径里会带本测试自己的名字（含 "basetemp"），所以只锁清理动作那句。
    assert "basetemp 已清" not in result.stdout


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

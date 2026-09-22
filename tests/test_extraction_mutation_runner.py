"""变异量具自己也要受验：真进程超时留证、拒绝伪红、失败保树且还原源码。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path("scripts/review_probes/run_extraction_mutations.py")


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("mutation_runner_under_test", ROOT / RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _env() -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONUNBUFFERED": "1"}


def _wait(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail("fixture failed to reach its synchronization point")


def _process_alive(pid: int) -> bool:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True, check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip()) and not result.stdout.strip().startswith("Z")


def test_output_and_identity_are_readable_before_process_finishes(runner, tmp_path):
    release = tmp_path / "release"
    source = (
        "import pathlib, sys, time\n"
        "print('ready-out', flush=True)\n"
        "print('ready-err', file=sys.stderr, flush=True)\n"
        f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.01)\n"
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            runner._run_logged_command, ROOT, tmp_path, "stream",
            [sys.executable, "-u", "-c", source], _env(), timeout=10,
        )
        try:
            log = tmp_path / "stream.log"
            _wait(lambda: log.exists() and "ready-err" in log.read_text())
            _wait(lambda: json.loads((tmp_path / "stream.process.json").read_text())["status"] == "running")
            assert not future.done()
            assert "ready-out" in log.read_text()
            state = json.loads((tmp_path / "stream.process.json").read_text())
            assert state["revision"] == runner.git(ROOT, "rev-parse", "HEAD")
            assert state["pid"] == state["process_group"]
        finally:
            release.touch()
        result = future.result(timeout=10)
    assert result["exit"] == 0 and result["status"] == "completed"
    assert "EXIT=0 STATUS=completed" in log.read_text()


def test_real_timeout_retains_output_stack_and_unknown_execution_count(runner, tmp_path):
    source = (
        "import faulthandler, sys, time\n"
        "faulthandler.dump_traceback_later(0.1)\n"
        "print('before-block', flush=True)\n"
        "print('before-block-stderr', file=sys.stderr, flush=True)\n"
        "time.sleep(60)\n"
    )
    result = runner._run_logged_command(
        ROOT, tmp_path, "timeout", [sys.executable, "-u", "-c", source], _env(), timeout=3,
    )
    state = json.loads((tmp_path / "timeout.process.json").read_text())
    log = (tmp_path / "timeout.log").read_text()
    assert state == result
    assert result["timed_out"] and result["status"] == "timed_out"
    assert result["exit"] == -signal.SIGKILL
    assert result["executed"] is None
    assert "before-block" in log and "before-block-stderr" in log
    assert "Timeout (" in log and 'File "<string>"' in log
    assert not _process_alive(result["pid"])


@pytest.mark.parametrize("leader_exits", [False, True])
def test_cleanup_owns_only_its_process_group(runner, tmp_path, leader_exits):
    child_pid_path = tmp_path / "child-pid"
    source = (
        "import os, pathlib, subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"pathlib.Path({str(child_pid_path)!r}).write_text(str(child.pid))\n"
        + ("sys.exit(0)\n" if leader_exits else "time.sleep(60)\n")
    )
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    child_pid = None
    try:
        result = runner._run_logged_command(
            ROOT, tmp_path, "group", [sys.executable, "-u", "-c", source], _env(), timeout=3,
        )
        child_pid = int(child_pid_path.read_text())
        _wait(lambda: not _process_alive(child_pid))
        assert unrelated.poll() is None
        assert result["status"] == ("completed" if leader_exits else "timed_out")
        assert result["process_group_cleanup"] == "sigkill_sent"
    finally:
        unrelated.kill()
        unrelated.wait(timeout=5)
        if child_pid is not None and _process_alive(child_pid):
            os.kill(child_pid, signal.SIGKILL)


def test_spawn_error_has_a_terminal_receipt(runner, tmp_path):
    with pytest.raises(FileNotFoundError):
        runner._run_logged_command(ROOT, tmp_path, "bad", [str(tmp_path / "missing")], _env())
    state = json.loads((tmp_path / "bad.process.json").read_text())
    assert state["status"] == "runner_error"
    assert state["error_type"] == "FileNotFoundError"
    assert state["exit"] is None and state["executed"] is None
    assert "STATUS=runner_error" in (tmp_path / "bad.log").read_text()


def test_keyboard_interrupt_cleans_up_and_still_raises(runner, tmp_path, monkeypatch):
    original_wait = subprocess.Popen.wait
    calls = 0

    def interrupt_once(proc, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt
        return original_wait(proc, *args, **kwargs)

    # Only the wait for the child is intercepted, not the git identity lookup.
    monkeypatch.setattr(runner, "git", lambda *args: "fixture-revision")
    monkeypatch.setattr(subprocess.Popen, "wait", interrupt_once)
    with pytest.raises(KeyboardInterrupt):
        runner._run_logged_command(
            tmp_path, tmp_path, "interrupt", [sys.executable, "-c", "import time; time.sleep(60)"], _env(),
        )
    state = json.loads((tmp_path / "interrupt.process.json").read_text())
    assert state["status"] == "interrupted" and state["exit"] == -signal.SIGKILL
    assert not _process_alive(state["pid"])


def _isolated_pytest(runner, root, monkeypatch, body, *, timeout=None, stack_timeout=None):
    test = root / "test_sample.py"
    test.write_text(body, encoding="utf-8")
    monkeypatch.setattr(runner, "TESTS", [str(test)])
    monkeypatch.setattr(runner, "git", lambda *args: "fixture-revision")
    original = runner._run_logged_command

    def isolated(root, out, label, command, env):
        if stack_timeout is not None:
            command = [
                f"faulthandler_timeout={stack_timeout}" if arg == "faulthandler_timeout=45" else arg
                for arg in command
            ]
        env = {**env, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        return original(root, out, label, command, env, **({"timeout": timeout} if timeout is not None else {}))

    monkeypatch.setattr(runner, "_run_logged_command", isolated)


@pytest.mark.parametrize("body,red", [
    ("def test_ok():\n    assert True\n", False),
    ("def test_bad():\n    assert False, 'broken-protection'\n", True),
])
def test_real_pytest_success_and_assertion_failure(runner, tmp_path, monkeypatch, body, red):
    _isolated_pytest(runner, tmp_path, monkeypatch, body)
    result = runner.run_tests(tmp_path, tmp_path, "pytest")
    runner.check_result(result, red=red)
    assert result["executed"] == 1
    assert result["failures"] == int(red)
    assert result["timeout_seconds"] == 180
    assert "faulthandler_timeout=45" in result["command"]
    assert "--capture=tee-sys" in result["command"]
    assert json.loads((tmp_path / "pytest.result.json").read_text()) == result


def test_real_pytest_timeout_keeps_node_and_stack_without_junit(runner, tmp_path, monkeypatch):
    _isolated_pytest(
        runner, tmp_path, monkeypatch,
        "import time\ndef test_hang():\n    print('test-body-entered', flush=True)\n    time.sleep(60)\n",
        timeout=4, stack_timeout=0.2,
    )
    result = runner.run_tests(tmp_path, tmp_path, "pytest-timeout")
    assert result["timed_out"] and result["junit_status"] == "missing_or_invalid"
    assert result["executed"] is None
    log = (tmp_path / "pytest-timeout.log").read_text()
    assert "test_sample.py::test_hang" in log and "test-body-entered" in log
    assert "Timeout (" in log and "in test_hang" in log
    for red in (False, True):
        with pytest.raises(AssertionError):
            runner.check_result(result, red=red)


@pytest.mark.parametrize("body", [
    "import nonexistent_mutation_fixture\n",
    "import pytest\ndef test_skip():\n    pytest.skip('not a red witness')\n",
    "# no tests\n",
])
def test_collection_error_skip_and_empty_are_never_mutation_success(runner, tmp_path, monkeypatch, body):
    _isolated_pytest(runner, tmp_path, monkeypatch, body)
    result = runner.run_tests(tmp_path, tmp_path, "not-red")
    for red in (False, True):
        with pytest.raises(AssertionError):
            runner.check_result(result, red=red)


@pytest.mark.parametrize("existing", ["log", "process.json", "xml", "result.json"])
def test_existing_run_evidence_is_never_overwritten(runner, tmp_path, monkeypatch, existing):
    _isolated_pytest(runner, tmp_path, monkeypatch, "def test_ok():\n    assert True\n")
    artifact = tmp_path / f"repeat.{existing}"
    artifact.write_bytes(b"sealed-old-evidence")
    with pytest.raises(FileExistsError):
        runner.run_tests(tmp_path, tmp_path, "repeat")
    assert artifact.read_bytes() == b"sealed-old-evidence"


@pytest.mark.parametrize("status,timed_out,junit_status", [
    ("timed_out", True, "parsed"),
    ("interrupted", False, "parsed"),
    ("cleanup_error", False, "parsed"),
    ("completed", False, "missing_or_invalid"),
])
def test_infrastructure_failure_is_never_a_mutation_witness(runner, status, timed_out, junit_status):
    """有JUnit但进程不正常、进程正常但JUnit缺失，都不能当成红/绿读数。"""
    result = {"status": status, "timed_out": timed_out, "junit_status": junit_status,
              "executed": 1 if junit_status == "parsed" else None,
              "failures": 1, "errors": 0, "skipped": 0, "exit": 1}
    with pytest.raises(AssertionError):
        runner.check_result(result, red=True)


def _mini_repo(tmp_path, *, mutation_hangs):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / RUNNER).parent.mkdir(parents=True)
    (repo / RUNNER).write_bytes((ROOT / RUNNER).read_bytes())
    test_path = Path("intelligence/tests/test_observation_extraction_first.py")
    (repo / test_path).parent.mkdir(parents=True)
    body = "import time\n\ndef test_witness():\n    assert True\n"
    (repo / test_path).write_text(body)
    for name in ("test_extraction_first_review_fixes.py", "test_extraction_closeout.py"):
        (repo / test_path.parent / name).write_text("# empty companion\n")
    # Keep the committed runner bytes intact; the subprocess fixture alone shortens wait.
    (repo / "conftest.py").write_text(
        "import subprocess\n"
        "_wait = subprocess.Popen.wait\n"
        "def short_wait(self, timeout=None):\n"
        "    return _wait(self, timeout=4 if timeout is not None and timeout > 100 else timeout)\n"
        "subprocess.Popen.wait = short_wait\n"
    )
    definitions = [{"id": "one", "path": str(test_path), "old": "    assert True",
                    "new": "    time.sleep(60)" if mutation_hangs else "    assert False",
                    "targets": ["test_witness"]}]
    (repo / "scripts/review_probes/extraction_mutations.json").write_text(json.dumps(definitions))
    for args in (["init", "-q"], ["add", "--", "."],
                 ["-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return repo, test_path, body


@pytest.mark.parametrize("phase,failure", [
    ("baseline", "timeout"),
    ("one-red", "timeout"),
    ("one-red", "spawn-error"),
])
def test_main_keeps_receipt_and_restores_source_when_a_run_never_finishes(
    runner, tmp_path, monkeypatch, phase, failure,
):
    repo, test_path, before = _mini_repo(tmp_path, mutation_hangs=True)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(runner, "__file__", str(repo / RUNNER))
    output = tmp_path / "output"
    monkeypatch.setattr(sys, "argv", [str(repo / RUNNER), "--output", str(output)])
    original = runner._run_logged_command
    blocked = [sys.executable, "-u", "-c", "import time; print('blocked', flush=True); time.sleep(60)"]

    def short_child(root, out, label, command, env):
        if label == phase:
            command = [str(tmp_path / "missing-binary")] if failure == "spawn-error" else blocked
        return original(root, out, label, command, {**env, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}, timeout=2)

    monkeypatch.setattr(runner, "_run_logged_command", short_child)
    try:
        with pytest.raises(AssertionError if failure == "timeout" else FileNotFoundError):
            runner.main()
        report = json.loads((output / "results.json").read_text())
        assert report["complete"] is False
        assert report["runs"][-1]["label"] == phase
        assert report["runs"][-1]["executed"] is None
        assert report["runs"][-1]["status"] == ("timed_out" if failure == "timeout" else "runner_error")
        assert report["runs"][-1]["timed_out"] is (failure == "timeout")
        assert report["final_status"] == ""
        assert report["active_run"] is None
        tree = Path(report["tree"])
        assert tree.exists() and (tree / test_path).read_text() == before
        assert not (output / "one-green.log").exists()
    finally:
        if (output / "results.json").exists():
            report = json.loads((output / "results.json").read_text())
            tree = Path(report["tree"])
            subprocess.run(["git", "-C", str(repo), "worktree", "remove", str(tree)], check=True)
            tree.parent.rmdir()

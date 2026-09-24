"""Concurrent readiness calls may share work, never completed health results."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import json
import os
import subprocess
import sys
from threading import Condition, Event, get_ident
from unittest import mock

import pytest

from intelligence.services import kb_rag

HELP = " ".join((*kb_rag.REQUIRED_QUERY_OPTIONS, *kb_rag.OPTIONAL_QUERY_OPTIONS))


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {"PATH": os.defpath, "KB_RAG_PYTHON": sys.executable})
    script = tmp_path / kb_rag.RAG_SCRIPT_REL
    script.parent.mkdir()
    script.write_text("# fixture\n")
    assert not kb_rag._PROBE_FLIGHTS
    yield tmp_path
    assert not kb_rag._PROBE_FLIGHTS


@pytest.fixture
def waiters(monkeypatch):
    condition = Condition()
    count = 0

    class ObservedFuture(Future):
        def result(self, timeout=None):
            nonlocal count
            with condition:
                count += 1
                condition.notify_all()
            return super().result(timeout=timeout)

    def wait_for_count(expected):
        with condition:
            assert condition.wait_for(lambda: count >= expected, timeout=3)

    monkeypatch.setattr(kb_rag, "Future", ObservedFuture)
    return wait_for_count


def success():
    return subprocess.CompletedProcess([], 0, HELP, "")


@pytest.mark.parametrize("kind", ["", "nonzero_exit", "timeout", "os_error", "execution_error", "protocol_incompatible"])
def test_overlapping_calls_share_success_and_failure_without_caching(root, waiters, kind):
    os.environ["PRIVATE_TEST_SETTING"] = "secret-value"
    entered, release = Event(), Event()

    def run(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        if kind == "timeout":
            raise subprocess.TimeoutExpired("help", 5, stderr="secret-error")
        if kind == "os_error":
            raise OSError("secret-error")
        if kind == "execution_error":
            raise ValueError("secret-error")
        return subprocess.CompletedProcess(
            [], 7 if kind == "nonzero_exit" else 0,
            "--k --mode" if kind == "protocol_incompatible" else HELP, "secret-error",
        )

    with mock.patch.object(kb_rag.subprocess, "run", side_effect=run) as child:
        with ThreadPoolExecutor(max_workers=8) as pool:
            try:
                owner = pool.submit(kb_rag.probe_rag_cli, root / "wiki")
                assert entered.wait(3)
                followers = [pool.submit(kb_rag.probe_rag_cli, root / "wiki") for _ in range(7)]
                waiters(7)
                assert kb_rag._PROBE_FLIGHTS
                assert "secret-value" not in repr(kb_rag._PROBE_FLIGHTS)
            finally:
                release.set()
            results = [owner.result(3), *(f.result(3) for f in followers)]
        child.assert_called_once()
        assert child.call_args.args[0][-2:] == ["query", "--help"]
        assert child.call_args.kwargs["timeout"] == 5
        assert child.call_args.kwargs["env"] == dict(os.environ)
        assert all(r.failure_kind == kind for r in results)
        assert all(r.query_protocol_compatible == (kind == "") for r in results)
        assert all(r.elapsed_ms is not None and r.elapsed_ms >= 0 for r in results)
        assert all(r.timeout_seconds == 5 for r in results)
        assert "secret" not in json.dumps([r.to_dict() for r in results])
        assert all(set(r.to_dict()) == {
            "available", "query_protocol_compatible", "supported_options",
            "missing_required_options", "missing_optional_options", "warning",
            "elapsed_ms", "timeout_seconds", "failure_kind",
        } for r in results)
        assert not kb_rag._PROBE_FLIGHTS
        child.side_effect = None
        child.return_value = success()
        later = kb_rag.probe_rag_cli(root / "wiki")
        assert later.query_protocol_compatible
        assert child.call_count == 2


@pytest.mark.parametrize("partition", ["root", "revision", "path_helper", "environment", "python", "timeout"])
def test_different_configurations_do_not_join_or_block(root, monkeypatch, partition):
    entered, release = Event(), Event()
    calls = []

    def run(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
        return success()

    with mock.patch.object(kb_rag.subprocess, "run", side_effect=run):
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                owner = pool.submit(kb_rag.probe_rag_cli, root / "wiki")
                assert entered.wait(3)
                other, timeout = root, 5
                if partition == "root":
                    other = root / "other"
                    script = other / kb_rag.RAG_SCRIPT_REL
                    script.parent.mkdir(parents=True)
                    script.write_text("# other\n")
                elif partition == "revision":
                    (root / kb_rag.RAG_SCRIPT_REL).write_text("# changed\n")
                elif partition == "path_helper":
                    helper = root / "skills/lib/repo_paths.py"
                    helper.parent.mkdir(parents=True)
                    helper.write_text("# added\n")
                elif partition == "environment":
                    monkeypatch.setenv("PRIVATE_SETTING", "secret-value")
                elif partition == "python":
                    monkeypatch.setattr(kb_rag, "_resolve_rag_python", lambda _: "/other/python")
                else:
                    timeout = 2
                follower = pool.submit(kb_rag.probe_rag_cli, other / "wiki", timeout=timeout)
                second = follower.result(2)
                assert not owner.done()
                assert second.query_protocol_compatible
                if partition == "environment":
                    assert kb_rag._PROBE_FLIGHTS
                    assert "secret-value" not in repr(kb_rag._PROBE_FLIGHTS)
            finally:
                release.set()
            first = owner.result(3)
        assert len(calls) == 2
        assert first.failure_kind == ("code_changed" if partition in {"revision", "path_helper"} else "")
        if partition == "environment":
            assert "PRIVATE_SETTING" not in calls[0][1]["env"]
            assert calls[1][1]["env"]["PRIVATE_SETTING"] == "secret-value"


@pytest.mark.parametrize("action", ["change", "delete", "unreadable"])
def test_code_changes_cannot_publish_green_to_waiters(root, waiters, monkeypatch, action):
    entered, release = Event(), Event()

    def run(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return success()

    with mock.patch.object(kb_rag.subprocess, "run", side_effect=run) as child:
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                owner = pool.submit(kb_rag.probe_rag_cli, root / "wiki")
                assert entered.wait(3)
                follower = pool.submit(kb_rag.probe_rag_cli, root / "wiki")
                waiters(1)
                script = root / kb_rag.RAG_SCRIPT_REL
                if action == "change":
                    script.write_text("# changed during check\n")
                elif action == "delete":
                    script.unlink()
                else:
                    def unreadable(_):
                        raise PermissionError("secret-path")
                    monkeypatch.setattr(kb_rag, "_probe_code_identity", unreadable)
            finally:
                release.set()
            results = [owner.result(3), follower.result(3)]
        child.assert_called_once()
    assert all(not r.query_protocol_compatible for r in results)
    assert all(r.failure_kind == ("code_changed" if action == "change" else "os_error") for r in results)
    assert "secret" not in json.dumps([r.to_dict() for r in results])


def test_waiter_timeout_does_not_cancel_owner_or_spawn_retry(root, waiters):
    entered, release = Event(), Event()

    def slow_cleanup(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return success()

    with mock.patch.object(kb_rag.subprocess, "run", side_effect=slow_cleanup) as child:
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                owner = pool.submit(kb_rag.probe_rag_cli, root / "wiki", timeout=0.1)
                assert entered.wait(3)
                follower = pool.submit(kb_rag.probe_rag_cli, root / "wiki", timeout=0.1)
                waiters(1)
                result = follower.result(2)
                assert result.failure_kind == "timeout"
                assert not owner.done()
                assert len(kb_rag._PROBE_FLIGHTS) == 1
            finally:
                release.set()
            assert owner.result(3).query_protocol_compatible
        child.assert_called_once()


def test_owner_interrupt_wakes_waiters_and_removes_flight(root, waiters):
    class Abort(BaseException):
        pass

    entered, release = Event(), Event()

    def interrupted(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        raise Abort()

    with mock.patch.object(kb_rag.subprocess, "run", side_effect=interrupted):
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                owner = pool.submit(kb_rag.probe_rag_cli, root / "wiki")
                assert entered.wait(3)
                follower = pool.submit(kb_rag.probe_rag_cli, root / "wiki")
                waiters(1)
            finally:
                release.set()
            with pytest.raises(Abort):
                owner.result(3)
            result = follower.result(3)
            assert result.failure_kind == "execution_error"
    with mock.patch.object(kb_rag.subprocess, "run", return_value=success()) as child:
        assert kb_rag.probe_rag_cli(root / "wiki").query_protocol_compatible
        child.assert_called_once()


def test_each_caller_measures_own_elapsed_time(root, waiters):
    entered, release = Event(), Event()
    clocks = {}

    def run(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return success()

    def call(start, end):
        clocks[get_ident()] = iter([start, end])
        return kb_rag.probe_rag_cli(root / "wiki")

    with mock.patch.object(kb_rag, "time") as clock:
        clock.monotonic.side_effect = lambda: next(clocks[get_ident()])
        with mock.patch.object(kb_rag.subprocess, "run", side_effect=run):
            with ThreadPoolExecutor(max_workers=2) as pool:
                try:
                    owner = pool.submit(call, 10.0, 10.5)
                    assert entered.wait(3)
                    follower = pool.submit(call, 10.25, 10.5)
                    waiters(1)
                finally:
                    release.set()
                assert owner.result(3).elapsed_ms == 500
                result = follower.result(3)
                assert result.elapsed_ms == 250


@pytest.mark.parametrize("broken", [False, True])
def test_real_child_shared_with_runtime_import_failure_preserved(root, waiters, broken):
    gate = root / "release"
    script = root / kb_rag.RAG_SCRIPT_REL
    script.write_text(
        "import time\nfrom pathlib import Path\n"
        f"while not Path({str(gate)!r}).exists():\n    time.sleep(0.01)\n"
        + ("raise ImportError('secret-import-error')\n" if broken else f"print({HELP!r})\n")
    )
    entered = Event()
    children = []
    original = subprocess.Popen

    def launch(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        entered.set()
        return child

    with mock.patch.object(kb_rag.subprocess, "Popen", side_effect=launch):
        with ThreadPoolExecutor(max_workers=4) as pool:
            try:
                owner = pool.submit(kb_rag.probe_rag_cli, root / "wiki")
                assert entered.wait(3)
                followers = [pool.submit(kb_rag.probe_rag_cli, root / "wiki") for _ in range(3)]
                waiters(3)
            finally:
                gate.touch()
            results = [owner.result(6), *(f.result(6) for f in followers)]
    assert len(children) == 1 and children[0].returncode is not None
    assert all(r.query_protocol_compatible == (not broken) for r in results)
    assert all(r.failure_kind == ("nonzero_exit" if broken else "") for r in results)
    assert "secret" not in json.dumps([r.to_dict() for r in results])


def test_real_timeout_reaps_one_shared_child(root, waiters):
    (root / kb_rag.RAG_SCRIPT_REL).write_text("import time\ntime.sleep(30)\n")
    entered = Event()
    children = []
    original = subprocess.Popen

    def launch(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        entered.set()
        return child

    with mock.patch.object(kb_rag.subprocess, "Popen", side_effect=launch):
        with ThreadPoolExecutor(max_workers=2) as pool:
            owner = pool.submit(kb_rag.probe_rag_cli, root / "wiki", timeout=1)
            assert entered.wait(3)
            follower = pool.submit(kb_rag.probe_rag_cli, root / "wiki", timeout=1)
            waiters(1)
            results = [owner.result(4), follower.result(4)]
    assert len(children) == 1 and children[0].returncode is not None
    assert all(r.failure_kind == "timeout" for r in results)

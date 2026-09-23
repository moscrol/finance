"""Startup ownership and safe diagnostics, using temporary KBs and real pipes."""
from __future__ import annotations

from contextlib import suppress
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from unittest.mock import Mock

import pytest

from intelligence.services import kb_rag, rag_worker
from intelligence.tests.test_rag_worker import _write_fake_rag


@pytest.fixture(autouse=True)
def isolated_workers(monkeypatch):
    rag_worker.close_all()
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    monkeypatch.setenv("RAG_WORKER_KEEPALIVE_SECONDS", "0")
    monkeypatch.setenv("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("FORESIGHT_LLM_KEYCHAIN", "0")
    for name in ("KB_RAG_GENERATION", "RAG_GENERATION_MANIFEST", "RAG_GENERATIONS_ROOT"):
        monkeypatch.delenv(name, raising=False)

    def deny(*args, **kwargs):
        pytest.fail("startup recovery regressions must not connect to the network")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    try:
        yield
    finally:
        rag_worker.close_all()


def _fixture(root: Path) -> dict:
    _write_fake_rag(root)
    index = root / ".rag_index"
    index.mkdir()
    return dict(python=sys.executable, kb_root=root, index_dir=index,
                argv=["query", "warmup", "--json"], timeout=5)


def _cache_failure(root: Path) -> Path:
    script = root / "scripts/rag_index.py"
    script.write_text(script.read_text().replace(
        "    return object()",
        '    from pathlib import Path\n'
        '    if not Path(__file__).with_name("cache-ready").exists():\n'
        '        raise OSError("private query /private/model credential-secret")\n'
        '    return object()',
    ))
    return script.with_name("cache-ready")


def _only_worker():
    with rag_worker._WORKERS_LOCK:
        (worker,) = rag_worker._WORKERS.values()
    return worker


def _recover(worker):
    rag_worker.ensure_recovery()
    thread = worker._recovery_thread
    assert thread is not None
    thread.join(timeout=10)
    assert not thread.is_alive(), "test recovery must finish, not leave a background loader"


def test_startup_failure_then_probe_recovery_clears_aggregate_state(tmp_path):
    args = _fixture(tmp_path)
    marker = _cache_failure(tmp_path)
    with pytest.raises(RuntimeError):
        rag_worker.prewarm(**args)
    worker = _only_worker()
    assert rag_worker.status()["state"] == "failed"
    assert not worker.healthy()
    assert worker.model_load_count == 1, "an attempted model load is not success"

    # An unsuccessful retry must stay failed and must not schedule itself again.
    _recover(worker)
    assert rag_worker.status()["state"] == "failed"
    assert worker.counters["recoveries"] == 1
    marker.touch()
    _recover(worker)
    state = rag_worker.status()
    assert state["state"] == "ready"
    assert state["active"] == 1
    assert state["last_error_type"] is None
    assert state["last_error_diagnostic"] is None
    assert state["counters"]["recoveries"] == 2
    assert worker.query(["query", "after"], timeout=5).returncode == 0


@pytest.mark.parametrize("stage", ["generation", "recipe", "keepalive"])
def test_whole_prewarm_failure_is_owned_and_recoverable(tmp_path, monkeypatch, stage):
    args = _fixture(tmp_path)
    rag_worker.prewarm(**args)
    worker = _only_worker()
    failed_args = dict(args)

    def fail(*args, **kwargs):
        raise RuntimeError("private startup failure")

    with monkeypatch.context() as patch:
        if stage == "generation":
            patch.setattr(type(worker._generation), "require_available", fail)
        elif stage == "recipe":
            failed_args["argv"] = ["query", "different"]
            failed_args["timeout"] = "invalid-timeout"
        else:
            patch.setattr(worker, "_start_keepalive", fail)
        with pytest.raises((RuntimeError, ValueError)):
            rag_worker.prewarm(**failed_args)

    state = rag_worker.status()
    assert state["state"] == "failed", "all prewarm failures must reach readiness"
    assert state["active"] == 0
    assert state["last_error_type"] == ("ValueError" if stage == "recipe" else "RuntimeError")
    assert "private startup" not in json.dumps(state)
    if stage == "recipe":
        assert worker._recovery_argv == args["argv"]
        assert worker._recovery_timeout == args["timeout"]
    _recover(worker)
    assert rag_worker.status()["state"] == "ready"
    assert rag_worker.status()["last_error_type"] is None


@pytest.mark.parametrize("operation", ["query", "prewarm"])
def test_closed_instance_cannot_be_reused(tmp_path, operation):
    args = _fixture(tmp_path)
    rag_worker.prewarm(**args)
    worker = _only_worker()
    rag_worker.close_all()
    try:
        with pytest.raises(RuntimeError, match="closed"):
            getattr(worker, operation)(args["argv"], timeout=5)
        assert not worker.healthy()
        assert rag_worker.status()["configured_workers"] == 0
        # A new application lifecycle can register a fresh instance normally.
        rag_worker.prewarm(**args)
        assert _only_worker() is not worker
        assert rag_worker.status()["state"] == "ready"
    finally:
        worker.close()


def test_recovery_admitted_before_close_cannot_restart_retired_instance(tmp_path, monkeypatch):
    args = _fixture(tmp_path)
    rag_worker.prewarm(**args)
    worker = _only_worker()
    worker._stop_process()
    admitted, resume = threading.Event(), threading.Event()
    original_prewarm = worker.prewarm

    def paused_prewarm(*args, **kwargs):
        admitted.set()
        assert resume.wait(timeout=10)
        return original_prewarm(*args, **kwargs)

    monkeypatch.setattr(worker, "prewarm", paused_prewarm)
    thread = None
    try:
        rag_worker.ensure_recovery()
        thread = worker._recovery_thread
        assert admitted.wait(timeout=5), "recovery must pass its initial closed check"
        rag_worker.close_all()
        assert rag_worker.status()["configured_workers"] == 0
        resume.set()
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert not worker.healthy(), "an unregistered worker must not resurrect after close"
        assert worker._process is None
    finally:
        resume.set()
        if thread is not None:
            thread.join(timeout=10)
        worker.close()


def test_configuration_failure_cannot_be_hidden_by_healthy_worker(tmp_path):
    rag_worker.prewarm(**_fixture(tmp_path))
    worker = _only_worker()
    with pytest.raises(ValueError):
        kb_rag.prewarm(None)
    assert worker.query(["query", "still-healthy"], timeout=5).returncode == 0
    state = rag_worker.status()
    assert state["active"] == 1
    assert state["state"] == "failed"
    assert state["last_error_type"] == "ValueError"


def test_worker_construction_failure_is_recorded_without_a_worker(tmp_path, monkeypatch):
    args = _fixture(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("private constructor details")

    monkeypatch.setattr(rag_worker, "_worker_for", fail)
    with pytest.raises(OSError):
        rag_worker.prewarm(**args)
    state = rag_worker.status()
    assert state["configured_workers"] == 0
    assert state["state"] == "failed"
    assert state["last_error_type"] == "OSError"
    assert "private" not in json.dumps(state)


def test_one_recovered_worker_does_not_hide_another_failure(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    args_a, args_b = _fixture(a), _fixture(b)
    marker = _cache_failure(a)
    _cache_failure(b)
    for args in (args_a, args_b):
        with pytest.raises(RuntimeError):
            rag_worker.prewarm(**args)
    marker.touch()
    rag_worker.ensure_recovery()
    for worker in list(rag_worker._WORKERS.values()):
        worker._recovery_thread.join(timeout=10)
        assert not worker._recovery_thread.is_alive()
    state = rag_worker.status()
    assert state["active"] == 1
    assert state["state"] == "failed"


def test_prewarm_response_preserves_safe_cause_not_stderr(tmp_path):
    args = _fixture(tmp_path)
    _cache_failure(tmp_path)
    with pytest.raises(RuntimeError) as raised:
        rag_worker.prewarm(**args)
    state = rag_worker.status()
    assert state["last_error_diagnostic"] == {
        "stage": "prewarm", "reason": "worker_returned_error",
        "returncode": 1, "error_type": "OSError",
    }
    serialized = json.dumps(state) + str(raised.value)
    assert "OSError" in serialized
    for secret in ("private query", "/private/model", "credential-secret"):
        assert secret not in serialized


def test_prewarm_no_model_is_not_ready(tmp_path, monkeypatch):
    args = _fixture(tmp_path)
    worker = rag_worker._worker_for(args["python"], args["kb_root"], args["index_dir"])
    monkeypatch.setattr(worker, "_query_locked", lambda *a, **k:
                        rag_worker.WorkerResponse(0, "[]", "", model_load_count=0))
    with pytest.raises(RuntimeError):
        rag_worker.prewarm(**args)
    state = rag_worker.status()
    assert state["state"] == "failed"
    assert state["last_error_diagnostic"]["reason"] == "model_not_loaded"


def test_early_process_exit_preserves_safe_stderr_and_drains_full_pipe(tmp_path):
    args = _fixture(tmp_path)
    script = tmp_path / "scripts/rag_index.py"
    script.write_text(
        'import sys\n'
        'sys.stderr.write("private-path-and-secret " * 10000 + "\\n")\n'
        'raise ModuleNotFoundError("private query credential-secret")\n'
    )
    with pytest.raises(RuntimeError) as raised:
        rag_worker.prewarm(**args)
    state = rag_worker.status()
    assert state["state"] == "failed"
    assert state["last_error_diagnostic"] == {
        "stage": "process", "reason": "exited_without_response",
        "returncode": 1, "error_type": "ModuleNotFoundError",
    }
    serialized = json.dumps(state) + str(raised.value)
    for secret in ("private", "credential-secret", str(tmp_path)):
        assert secret not in serialized
    assert not _only_worker().healthy()


def test_large_request_drains_stderr_while_sending(tmp_path):
    args = _fixture(tmp_path)
    script = tmp_path / "scripts/rag_index.py"
    script.write_text(
        'import os\nos.write(2, b"private-startup-noise " * 65536)\n' + script.read_text()
    )
    worker = rag_worker._worker_for(args["python"], args["kb_root"], args["index_dir"])
    watchdog_fired = threading.Event()

    def stop_stalled_child():
        watchdog_fired.set()
        worker._stop_process()

    watchdog = threading.Timer(5, stop_stalled_child)
    watchdog.start()
    try:
        response = worker.prewarm(["query", "x" * (512 * 1024)], timeout=3)
        assert not watchdog_fired.is_set(), "request send must not deadlock behind stderr"
        assert response.returncode == 0
        assert worker.healthy()
        assert len(worker._stderr_tail) <= 4096
        assert "private-startup-noise" not in json.dumps(worker.status())
    finally:
        watchdog.cancel()
        watchdog.join(timeout=5)
        worker.close()


@pytest.mark.parametrize("warm", [False, True])
def test_partial_request_write_has_deadline_and_retires_process(tmp_path, monkeypatch, warm):
    args = _fixture(tmp_path)
    worker = rag_worker._worker_for(args["python"], args["kb_root"], args["index_dir"])
    process = subprocess.Popen(
        [sys.executable, "-c", "import threading; threading.Event().wait(10)"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    worker._process = process
    worker.model_load_count = int(warm)
    monkeypatch.setattr(worker, "_ensure_process", lambda: process)
    watchdog_fired = threading.Event()

    def stop_stalled_child():
        watchdog_fired.set()
        worker._stop_process()

    watchdog = threading.Timer(3, stop_stalled_child)
    watchdog.start()
    try:
        with pytest.raises(TimeoutError) as raised:
            worker.query(["query", "x" * (512 * 1024)], timeout=0.05)
        assert not isinstance(raised.value, rag_worker.WorkerRequestAbandoned)
        assert not watchdog_fired.is_set(), "stdin writes must obey the query deadline"
        assert not worker.healthy(), "a partially sent JSON frame cannot be reused"
        assert worker.counters["timeouts_killed"] == 1
        assert worker.counters["timeouts_abandoned_kept_warm"] == 0
    finally:
        watchdog.cancel()
        watchdog.join(timeout=5)
        worker.close()
        with suppress(BrokenPipeError):
            process.stdin.close()
        process.stdout.close()


def test_process_exit_before_request_write_keeps_safe_diagnostic(tmp_path, monkeypatch):
    args = _fixture(tmp_path)
    worker = rag_worker._worker_for(args["python"], args["kb_root"], args["index_dir"])
    process = subprocess.Popen(
        [sys.executable, "-c", 'raise ImportError("private credential-secret")'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    process.wait(timeout=5)
    worker._process = process
    monkeypatch.setattr(worker, "_ensure_process", lambda: process)
    try:
        with pytest.raises(rag_worker.WorkerExecutionError) as raised:
            worker.prewarm(args["argv"], timeout=5)
        assert raised.value.diagnostic == {
            "stage": "process", "reason": "exited_without_response",
            "returncode": 1, "error_type": "ImportError",
        }
        assert "credential-secret" not in json.dumps(worker.status()) + str(raised.value)
    finally:
        worker.close()
        with suppress(BrokenPipeError):
            process.stdin.close()
        process.stdout.close()


@pytest.mark.parametrize("registered", [1, 2])
def test_pipe_registration_failure_closes_selector(tmp_path, monkeypatch, registered):
    args = _fixture(tmp_path)
    selector = Mock()
    selector.register.side_effect = [None] * registered + [OSError("private pipe details")]
    monkeypatch.setattr(rag_worker.selectors, "DefaultSelector", lambda: selector)
    with pytest.raises(OSError):
        rag_worker.prewarm(**args)
    selector.close.assert_called_once_with()
    assert rag_worker.status()["state"] == "failed"
    assert not _only_worker().healthy()
    assert "private pipe" not in json.dumps(rag_worker.status())


def test_stderr_noise_does_not_block_valid_stdout_or_leak_to_status(tmp_path):
    args = _fixture(tmp_path)
    script = tmp_path / "scripts/rag_index.py"
    script.write_text(
        'import os\nos.write(2, b"private-noise " * 10000)\n' + script.read_text()
    )
    assert rag_worker.prewarm(**args).returncode == 0
    worker = _only_worker()
    assert len(worker._stderr_tail) <= 4096
    assert "private-noise" not in json.dumps(rag_worker.status())
    worker.close()
    assert worker._stderr_tail == b""


@pytest.mark.parametrize("failure_kind", ["cache", "configuration", "keepalive"])
def test_real_lifespan_readiness_recovers_without_restarting_app(
    tmp_path, monkeypatch, failure_kind,
):
    from fastapi.testclient import TestClient
    from intelligence.api.app import create_app
    from intelligence.tests.test_workbench_api import _write_market_snapshot_fixture

    args = _fixture(tmp_path)
    wiki = tmp_path / "wiki"
    (wiki / "relations").mkdir(parents=True)
    script = tmp_path / "scripts/rag_index.py"
    script.write_text(script.read_text() + (
        '\nif __name__ == "__main__":\n'
        '    print("--json --k K --mode MODE --evidence-chars N --stale-policy")\n'
    ))
    marker = _cache_failure(tmp_path)
    if failure_kind == "keepalive":
        marker.touch()
        marker = tmp_path / "keepalive-ready"
        original_start = rag_worker.PersistentRagWorker._start_keepalive

        def start_keepalive(worker):
            if not marker.exists():
                raise RuntimeError("private keepalive failure")
            return original_start(worker)

        monkeypatch.setattr(rag_worker.PersistentRagWorker, "_start_keepalive", start_keepalive)
    snapshot = tmp_path / "market_snapshot"
    snapshot.mkdir()
    _write_market_snapshot_fixture(snapshot)
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, value in {
        "FINANCE_WS": repo, "FORESIGHT_USERS_DIR": tmp_path / "users",
        "FORESIGHT_EPISODE_STORE": tmp_path / "episodes", "KB_VAULT": wiki,
        "KB_RAG_CODE_ROOT": tmp_path, "KB_RAG_PYTHON": sys.executable,
        "RAG_INDEX_DIR": args["index_dir"], "VECTOR_INDEX_DIR": args["index_dir"],
        "MARKET_SNAPSHOT_DIR": snapshot, "RAG_WORKER_PREWARM_TIMEOUT": "5",
        "RAG_WORKER_RECOVERY_COOLDOWN_SECONDS": "60",
        "WORKBENCH_CONTINUOUS_EPISODE": "off",
    }.items():
        monkeypatch.setenv(name, str(value))
    if failure_kind == "configuration":
        monkeypatch.setenv("KB_RAG_CODE_ROOT", str(tmp_path / "missing-code"))

    with TestClient(create_app(repo_root=repo)) as client:
        assert rag_worker.status()["state"] == "failed"
        if failure_kind != "configuration":
            worker = _only_worker()
            # Hold the ordinary cooldown for the first HTTP observation.
            worker._last_recovery_at = time.monotonic()
        failed = client.get("/api/readiness")
        assert failed.status_code == 503
        assert "rag_worker" in failed.json()["missing_critical"]
        assert "credential-secret" not in failed.text
        if failure_kind == "cache":
            assert failed.json()["workers"]["rag"]["last_error_diagnostic"]["error_type"] == "OSError"
        elif failure_kind == "keepalive":
            assert failed.json()["workers"]["rag"]["last_error_type"] == "RuntimeError"
            assert "private keepalive" not in failed.text
        else:
            assert failed.json()["workers"]["rag"]["last_error_type"] == "FileNotFoundError"
            assert rag_worker.status()["configured_workers"] == 0

        marker.touch()
        if failure_kind != "configuration":
            worker._last_recovery_at = float("-inf")
            client.get("/api/readiness")  # The real endpoint schedules recovery.
            thread = worker._recovery_thread
            assert thread is not None
            thread.join(timeout=10)
            assert not thread.is_alive()
        else:
            # No worker owns a configuration failure, so probes cannot fix it.
            assert client.get("/api/readiness").status_code == 503
            monkeypatch.setenv("KB_RAG_CODE_ROOT", str(tmp_path))
            kb_rag.prewarm(wiki, timeout=5)
        ready = client.get("/api/readiness")
        assert ready.status_code == 200, ready.json()
        payload = ready.json()
        assert payload["missing_critical"] == []
        assert payload["workers"]["rag"]["state"] == "ready"
        assert payload["workers"]["rag"]["last_error_type"] is None
        assert payload["workers"]["rag"]["last_error_diagnostic"] is None


@pytest.mark.parametrize("text,expected", [
    ("OSError: sensitive details", "OSError"),
    ("Traceback (most recent call last):\nValueError: /private/data", "ValueError"),
    ("credential_secret: sensitive", None),
    ("CustomerSecretError: sensitive", None),
    ("garbage ModuleNotFoundError: not an exception line", None),
    ("FileNotFoundError: /private/file\n", "FileNotFoundError"),
])
def test_child_error_parser_only_reveals_allowlisted_types(text, expected):
    assert rag_worker._child_error_type(text) == expected

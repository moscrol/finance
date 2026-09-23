"""Startup ownership and safe diagnostics, using temporary KBs and real pipes."""
from __future__ import annotations

from contextlib import suppress
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

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


@pytest.mark.parametrize("failure_kind", ["cache", "configuration"])
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
        if failure_kind == "cache":
            worker = _only_worker()
            # Hold the ordinary cooldown for the first HTTP observation.
            worker._last_recovery_at = time.monotonic()
        failed = client.get("/api/readiness")
        assert failed.status_code == 503
        assert "rag_worker" in failed.json()["missing_critical"]
        assert "credential-secret" not in failed.text
        if failure_kind == "cache":
            assert failed.json()["workers"]["rag"]["last_error_diagnostic"]["error_type"] == "OSError"
        else:
            assert failed.json()["workers"]["rag"]["last_error_type"] == "FileNotFoundError"
            assert rag_worker.status()["configured_workers"] == 0

        marker.touch()
        if failure_kind == "cache":
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

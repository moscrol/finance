"""Opt-in pytest diagnostics for real RAG subprocess startup timeouts.

Run with ``-p scripts.review_probes.rag_startup_trace --rag-trace-dir <new-dir>``.
Records only timings, pipe byte counts, import-time lines and fixed error names;
never logs query/response bodies or environment values. No deadlines are changed.
The import profiler and synchronous trace writes add overhead, so these runs are
attribution evidence, not release/performance receipts. Use only offline tests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time

import pytest

_IMPORT_LINE = re.compile(r"import time:\s+\d+\s+\|\s+\d+\s+\|\s+[\w.]+$")


def pytest_addoption(parser):
    parser.addoption("--rag-trace-dir", type=Path, help="New offline trace directory")


def pytest_configure(config):
    root = config.getoption("--rag-trace-dir")
    if root is not None:
        root.mkdir(parents=True, exist_ok=False)


@pytest.fixture(autouse=True)
def trace_rag_startup(request, monkeypatch):
    root = request.config.getoption("--rag-trace-dir")
    if root is None:
        yield
        return
    from intelligence.services import rag_worker

    start = time.monotonic()
    filename = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:16] + ".jsonl"
    pipes = {}
    pending_imports = {}
    popen = rag_worker.subprocess.Popen
    read = rag_worker.os.read
    write = rag_worker.os.write
    ensure = rag_worker.PersistentRagWorker._ensure_process
    on_timeout = rag_worker.PersistentRagWorker._on_query_timeout

    with (root / filename).open("x", encoding="utf-8") as log:
        def emit(event, **fields):
            log.write(json.dumps({"t": time.monotonic() - start, "event": event, **fields}) + "\n")
            log.flush()

        emit("test", node_id=request.node.nodeid)

        def traced_popen(args, *a, **kw):
            is_worker = isinstance(args, list) and any(
                str(arg).endswith("/scripts/rag_query_worker.py") for arg in args
            )
            if not is_worker:
                return popen(args, *a, **kw)
            env = dict(kw["env"])
            env["PYTHONPROFILEIMPORTTIME"] = "1"
            kw["env"] = env
            emit("spawn_start")
            process = popen(args, *a, **kw)
            emit("spawn_return", pid=process.pid)
            for kind in ("stdin", "stdout", "stderr"):
                pipe = getattr(process, kind)
                if pipe is not None:
                    pipes[pipe.fileno()] = (process.pid, kind)
            return process

        def traced_read(fd, size):
            chunk = read(fd, size)
            if fd in pipes:
                pid, kind = pipes[fd]
                emit("read", pid=pid, pipe=kind, bytes=len(chunk))
                if kind == "stderr":
                    buf = pending_imports.get(pid, b"") + chunk
                    lines = buf.split(b"\n")
                    pending_imports[pid] = lines.pop()[-4096:]
                    for raw in lines:
                        line = raw.decode("utf-8", errors="replace")
                        if _IMPORT_LINE.fullmatch(line):
                            emit("import", pid=pid, timing=line)
            return chunk

        def traced_write(fd, data):
            count = write(fd, data)
            if fd in pipes and pipes[fd][1] == "stdin":
                emit("request_write", pid=pipes[fd][0], bytes=count)
            return count

        def traced_ensure(worker):
            emit("ensure_start")
            try:
                process = ensure(worker)
                emit("ensure_return", pid=process.pid)
                return process
            except Exception as exc:
                emit("ensure_error", error_type=type(exc).__name__)
                raise

        def traced_timeout(worker, request_id, *, allow_abandon):
            process = worker._process
            emit("timeout", pid=process.pid if process else None,
                 returncode=process.poll() if process else None,
                 buffered_bytes=len(worker._response_buffer), allow_abandon=allow_abandon)
            return on_timeout(worker, request_id, allow_abandon=allow_abandon)

        monkeypatch.setattr(rag_worker.subprocess, "Popen", traced_popen)
        monkeypatch.setattr(rag_worker.os, "read", traced_read)
        monkeypatch.setattr(rag_worker.os, "write", traced_write)
        monkeypatch.setattr(rag_worker.PersistentRagWorker, "_ensure_process", traced_ensure)
        monkeypatch.setattr(rag_worker.PersistentRagWorker, "_on_query_timeout", traced_timeout)
        try:
            yield
        finally:
            monkeypatch.undo()
            emit("test_end")

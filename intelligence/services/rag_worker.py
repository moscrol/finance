"""Workbench 管理的常驻 RAG 子进程客户端。"""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkerResponse:
    returncode: int
    stdout: str
    stderr: str
    model_load_count: int = 0


class PersistentRagWorker:
    def __init__(self, python: str, kb_root: Path, index_dir: Path) -> None:
        self.python = python
        self.kb_root = kb_root
        self.index_dir = index_dir
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self.model_load_count = 0

    def query(self, argv: list[str], timeout: float) -> WorkerResponse:
        with self._lock:
            process = self._ensure_process()
            request_id = uuid.uuid4().hex
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(
                json.dumps({"id": request_id, "argv": argv}, ensure_ascii=False)
                + "\n"
            )
            process.stdin.flush()
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            try:
                if not selector.select(max(0.001, timeout)):
                    self._stop_process()
                    raise TimeoutError("rag worker query timeout")
                line = process.stdout.readline()
            finally:
                selector.close()
            if not line:
                self._stop_process()
                raise RuntimeError("rag worker exited without response")
            payload = json.loads(line)
            if payload.get("id") != request_id:
                self._stop_process()
                raise RuntimeError("rag worker response id mismatch")
            response = WorkerResponse(
                returncode=int(payload.get("returncode") or 0),
                stdout=str(payload.get("stdout") or ""),
                stderr=str(payload.get("stderr") or ""),
                model_load_count=int(payload.get("model_load_count") or 0),
            )
            self.model_load_count = response.model_load_count
            return response

    def healthy(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def close(self) -> None:
        with self._lock:
            self._stop_process()

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        script = Path(__file__).resolve().parents[2] / "scripts" / "rag_query_worker.py"
        self._process = subprocess.Popen(
            [
                self.python,
                str(script),
                "--kb-root",
                str(self.kb_root),
                "--index-dir",
                str(self.index_dir),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        return self._process

    def _stop_process(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


_WORKERS: dict[tuple[str, str, str], PersistentRagWorker] = {}
_WORKERS_LOCK = threading.Lock()


def query(
    *,
    python: str,
    kb_root: Path,
    index_dir: Path,
    argv: list[str],
    timeout: float,
) -> WorkerResponse:
    key = (python, str(kb_root.resolve()), str(index_dir.resolve()))
    with _WORKERS_LOCK:
        worker = _WORKERS.get(key)
        if worker is None:
            worker = PersistentRagWorker(python, kb_root, index_dir)
            _WORKERS[key] = worker
    return worker.query(argv, timeout)


def close_all() -> None:
    with _WORKERS_LOCK:
        workers = list(_WORKERS.values())
        _WORKERS.clear()
    for worker in workers:
        worker.close()


def status() -> dict[str, object]:
    enabled = os.environ.get("RAG_WORKER_ENABLED", "0").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }
    with _WORKERS_LOCK:
        workers = list(_WORKERS.values())
    return {
        "enabled": enabled,
        "active": sum(1 for worker in workers if worker.healthy()),
        "configured_workers": len(workers),
        "model_load_count": sum(worker.model_load_count for worker in workers),
        "lifecycle": "lazy",
    }

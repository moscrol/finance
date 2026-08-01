"""Workbench 管理的常驻 RAG 子进程客户端。"""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import threading
import time
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
        self._state = "cold"
        self._last_error_type: str | None = None
        self._prewarm_latency_ms: int | None = None

    def query(self, argv: list[str], timeout: float) -> WorkerResponse:
        with self._lock:
            try:
                response = self._query_locked(argv, timeout)
            except Exception as exc:
                self._mark_failed(exc)
                raise
            if response.returncode == 0 and response.model_load_count > 0:
                self._state = "ready"
                self._last_error_type = None
            return response

    def prewarm(self, argv: list[str], timeout: float) -> WorkerResponse:
        with self._lock:
            self._state = "warming"
            self._last_error_type = None
            started = time.monotonic()
            try:
                response = self._query_locked(argv, timeout)
                if response.returncode != 0 or response.model_load_count < 1:
                    raise RuntimeError("rag worker prewarm failed")
            except Exception as exc:
                self._prewarm_latency_ms = int(
                    (time.monotonic() - started) * 1000
                )
                self._mark_failed(exc)
                raise
            self._prewarm_latency_ms = int(
                (time.monotonic() - started) * 1000
            )
            self._state = "ready"
            self._last_error_type = None
            return response

    def status(self) -> dict[str, object]:
        return {
            "state": self._state,
            "active": self.healthy(),
            "model_load_count": self.model_load_count,
            "prewarm_latency_ms": self._prewarm_latency_ms,
            "last_error_type": self._last_error_type,
        }

    def healthy(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def close(self) -> None:
        with self._lock:
            self._stop_process()

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        script = Path(__file__).resolve().parents[2] / "scripts" / "rag_query_worker.py"
        # 与 kb_rag 直跑 subprocess 的 env 保持一致：模型已缓存时离线加载（省掉
        # 一次零收益的 HF Hub 往返），并静音 391 分片的 tqdm 进度条——否则进度条
        # 会被 redirect_stderr 收进 payload，让「stderr 非空」这个信号永远为真。
        # 这里用 setdefault，外部显式设置仍然优先。
        env = dict(os.environ)
        for key, value in (
            ("HF_HUB_OFFLINE", "1"),
            ("TRANSFORMERS_OFFLINE", "1"),
            ("HF_HUB_DISABLE_PROGRESS_BARS", "1"),
            ("TRANSFORMERS_VERBOSITY", "error"),
            ("TQDM_DISABLE", "1"),
        ):
            env.setdefault(key, value)
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
            # 进程级 stderr 丢弃是有意的：真正的失败原因由 worker 在 JSON payload 的
            # stderr 字段上报（含异常类型），这里丢的只是框架噪声。
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )
        return self._process

    def _query_locked(self, argv: list[str], timeout: float) -> WorkerResponse:
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

    def _mark_failed(self, exc: Exception) -> None:
        self._state = "failed"
        self._last_error_type = type(exc).__name__
        self._stop_process()

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
_STARTUP_FAILURE_TYPE: str | None = None


def enabled() -> bool:
    return os.environ.get("RAG_WORKER_ENABLED", "0").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


def _worker_for(
    python: str,
    kb_root: Path,
    index_dir: Path,
) -> PersistentRagWorker:
    key = (python, str(kb_root.resolve()), str(index_dir.resolve()))
    with _WORKERS_LOCK:
        worker = _WORKERS.get(key)
        if worker is None:
            worker = PersistentRagWorker(python, kb_root, index_dir)
            _WORKERS[key] = worker
    return worker


def query(
    *,
    python: str,
    kb_root: Path,
    index_dir: Path,
    argv: list[str],
    timeout: float,
) -> WorkerResponse:
    return _worker_for(python, kb_root, index_dir).query(argv, timeout)


def prewarm(
    *,
    python: str,
    kb_root: Path,
    index_dir: Path,
    argv: list[str],
    timeout: float,
) -> WorkerResponse:
    global _STARTUP_FAILURE_TYPE
    with _WORKERS_LOCK:
        _STARTUP_FAILURE_TYPE = None
    try:
        return _worker_for(python, kb_root, index_dir).prewarm(argv, timeout)
    except Exception as exc:
        record_startup_failure(exc)
        raise


def record_startup_failure(exc: Exception) -> None:
    global _STARTUP_FAILURE_TYPE
    with _WORKERS_LOCK:
        _STARTUP_FAILURE_TYPE = type(exc).__name__


def close_all() -> None:
    global _STARTUP_FAILURE_TYPE
    with _WORKERS_LOCK:
        workers = list(_WORKERS.values())
        _WORKERS.clear()
        _STARTUP_FAILURE_TYPE = None
    for worker in workers:
        worker.close()


def status() -> dict[str, object]:
    is_enabled = enabled()
    with _WORKERS_LOCK:
        workers = list(_WORKERS.values())
        startup_failure_type = _STARTUP_FAILURE_TYPE
    worker_states = [worker.status() for worker in workers]
    if not is_enabled:
        state = "disabled"
    elif any(item["state"] == "warming" for item in worker_states):
        state = "warming"
    elif startup_failure_type or any(
        item["state"] == "failed" for item in worker_states
    ):
        state = "failed"
    elif worker_states and all(
        item["state"] == "ready" and item["active"]
        for item in worker_states
    ):
        state = "ready"
    else:
        state = "cold"
    last_error_type = next(
        (
            str(item["last_error_type"])
            for item in worker_states
            if item["last_error_type"]
        ),
        startup_failure_type,
    )
    prewarm_latency_ms = max(
        (
            int(item["prewarm_latency_ms"])
            for item in worker_states
            if item["prewarm_latency_ms"] is not None
        ),
        default=None,
    )
    return {
        "enabled": is_enabled,
        "state": state,
        "active": sum(1 for worker in workers if worker.healthy()),
        "configured_workers": len(workers),
        "model_load_count": sum(worker.model_load_count for worker in workers),
        "prewarm_latency_ms": prewarm_latency_ms,
        "last_error_type": last_error_type,
        "lifecycle": "startup_prewarm",
    }

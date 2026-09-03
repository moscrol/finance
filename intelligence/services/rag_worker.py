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


class WorkerRequestAbandoned(TimeoutError):
    """查询超窗，但 worker 还热着：放弃这一条请求、进程保留。

    与「超时即杀」的区别是代价。杀掉热 worker 要按预热配方重生（模型加载 ~50–145s），
    重生期间所有查询都排在锁后面等——一次慢查询换来一两分钟的 kb_search 必败
    （2026-09-03 生产读数：kb_search 66% 的调用以 tool_timeout 收场）。放弃只损失这一次：
    worker 单线程顺序处理，迟到的那行响应会在下一次查询前吐出来，读到就丢。
    热 worker **连续第二次**超时才判它卡死，走原来的杀 + 自愈。冷 worker（还没加载过
    模型）超时照旧杀：那时没有「热」可保。
    """


def _recovery_cooldown_seconds() -> float:
    raw = os.environ.get("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "").strip()
    try:
        value = float(raw)
    except ValueError:
        return 60.0
    return max(0.0, value)


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
        # 自愈配方：prewarm 时记下 argv/timeout，查询失败后按同样的口径重生。
        # 为什么不能靠「下次查询自然重启」：预热窗（240s）远大于查询窗（90s），
        # 模型加载 ~145s，查询路径重启必然二次超时——failed 会一直卡住，
        # readiness 永久红（2026-08-13 生产实测）。
        self._recovery_argv: list[str] | None = None
        self._recovery_timeout: float | None = None
        self._recovery_thread: threading.Thread | None = None
        # -inf 哨兵：monotonic() 从开机起算，用 0.0 会在开机不足一个冷却周期的
        # 机器（CI 容器常见）上把首次自愈误判成「冷却中」。
        self._last_recovery_at: float = float("-inf")
        # 调度检查（单飞/冷却）自己的小锁：探针路径不持 self._lock 调进来，
        # 与查询路径（持 self._lock）并发时 check-then-spawn 不能撕开。
        self._schedule_lock = threading.Lock()
        self._closed = False
        # 已放弃、响应还没到的 request id：下一次查询读到它们时丢掉，不当 id 错位。
        self._abandoned: set[str] = set()
        self._consecutive_timeouts = 0
        self._last_latency_ms: int | None = None
        # 处置计数走 readiness 的 status() 出去。离线普查只看得到工具层的 elapsed_ms，
        # 分不出「超时是 worker 冷启还是查询本身慢」——这里是唯一能分的地方。
        self.counters: dict[str, int] = {
            "queries_served": 0,
            "timeouts_abandoned_kept_warm": 0,
            "timeouts_killed": 0,
            "stale_responses_drained": 0,
            "recoveries": 0,
        }

    def query(self, argv: list[str], timeout: float) -> WorkerResponse:
        with self._lock:
            try:
                response = self._query_locked(argv, timeout, allow_abandon=True)
            except WorkerRequestAbandoned:
                # 进程还热着：不标 failed、不重生、状态不动。
                raise
            except Exception as exc:
                self._mark_failed(exc)
                self._schedule_recovery()
                raise
            if response.returncode == 0 and response.model_load_count > 0:
                self._state = "ready"
                self._last_error_type = None
            return response

    def prewarm(self, argv: list[str], timeout: float) -> WorkerResponse:
        with self._lock:
            self._recovery_argv = list(argv)
            self._recovery_timeout = float(timeout)
            self._state = "warming"
            self._last_error_type = None
            started = time.monotonic()
            try:
                # 预热不放弃：预热窗本来就是按模型加载给的，超了就是真失败。
                response = self._query_locked(argv, timeout, allow_abandon=False)
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
            "last_latency_ms": self._last_latency_ms,
            "abandoned_in_flight": len(self._abandoned),
            "consecutive_timeouts": self._consecutive_timeouts,
            "counters": dict(self.counters),
        }

    def healthy(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def close(self) -> None:
        self._closed = True
        # 先无锁杀一次：恢复线程可能正持锁阻塞在预热的 select 里（上限=预热窗）。
        # 杀掉子进程会让它立刻读到 EOF 抛错并释放锁，否则这里要等满整个预热窗。
        self._stop_process()
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

    def _query_locked(
        self, argv: list[str], timeout: float, *, allow_abandon: bool = False
    ) -> WorkerResponse:
        process = self._ensure_process()
        request_id = uuid.uuid4().hex
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(
            json.dumps({"id": request_id, "argv": argv}, ensure_ascii=False)
            + "\n"
        )
        process.stdin.flush()
        started = time.monotonic()
        deadline = started + max(0.001, float(timeout))
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(max(0.001, remaining)):
                    self._on_query_timeout(request_id, allow_abandon=allow_abandon)
                line = process.stdout.readline()
                if not line:
                    self._stop_process()
                    raise RuntimeError("rag worker exited without response")
                payload = json.loads(line)
                response_id = payload.get("id")
                if response_id in self._abandoned:
                    # 上一条被放弃请求的迟到响应：排掉，继续等自己的。
                    self._abandoned.discard(response_id)
                    self.counters["stale_responses_drained"] += 1
                    continue
                if response_id != request_id:
                    self._stop_process()
                    raise RuntimeError("rag worker response id mismatch")
                break
        finally:
            selector.close()
        response = WorkerResponse(
            returncode=int(payload.get("returncode") or 0),
            stdout=str(payload.get("stdout") or ""),
            stderr=str(payload.get("stderr") or ""),
            model_load_count=int(payload.get("model_load_count") or 0),
        )
        self.model_load_count = response.model_load_count
        self._last_latency_ms = int((time.monotonic() - started) * 1000)
        self._consecutive_timeouts = 0
        self.counters["queries_served"] += 1
        return response

    def _on_query_timeout(self, request_id: str, *, allow_abandon: bool) -> None:
        """超窗处置：热 worker 第一次放弃请求；冷 worker 或连续第二次才杀。"""

        warm = self.model_load_count > 0 and self.healthy()
        if allow_abandon and warm and self._consecutive_timeouts == 0:
            self._abandoned.add(request_id)
            self._consecutive_timeouts = 1
            self.counters["timeouts_abandoned_kept_warm"] += 1
            raise WorkerRequestAbandoned(
                "rag worker query timeout; request abandoned, worker kept warm"
            )
        self._consecutive_timeouts = 0
        self._abandoned.clear()
        self.counters["timeouts_killed"] += 1
        self._stop_process()
        raise TimeoutError("rag worker query timeout")

    def _mark_failed(self, exc: Exception) -> None:
        self._state = "failed"
        self._last_error_type = type(exc).__name__
        self._stop_process()

    def ensure_recovery_if_dead(self) -> None:
        """探针侧自愈入口：进程死了且没在预热，就按配方调度重生。

        查询失败式入口（``query()`` 异常路径）覆盖不了的形状（2026-08-13
        R23 注入实测）：进程被外部杀死/自己崩掉后，若后续查询全带 filters
        （``kb_rag`` 分层检索走 CLI 不经 worker），查询入口永远不会被踩到，
        readiness 永久红、只能人工 kickstart。本入口挂在 readiness 探针上，
        不依赖查询流量；单飞与冷却仍由 ``_schedule_recovery`` 统一把关，
        探针轮询不会打出重复预热。
        """
        if self.healthy():
            return
        if self._state == "warming":
            # 启动预热或自愈预热正在进行（进程可能尚未 spawn），别叠一发。
            return
        self._schedule_recovery()

    def _schedule_recovery(self) -> None:
        """按预热配方后台重生（单飞 + 冷却，需求/探针驱动，不自我续期）。

        触发口只有两个：查询失败（``query()`` 异常路径）与探针发现死进程
        （``ensure_recovery_if_dead``）。不从 prewarm 失败触发：恢复本身失败
        不再自我调度，否则索引真坏时会每个冷却周期烧一次 ~145s 的模型加载，
        永不收敛——下一次查询失败或下一轮探针（过了冷却）才会再触发。
        """
        if self._closed:
            return
        if self._recovery_argv is None or self._recovery_timeout is None:
            return
        with self._schedule_lock:
            if (
                self._recovery_thread is not None
                and self._recovery_thread.is_alive()
            ):
                return
            now = time.monotonic()
            if now - self._last_recovery_at < _recovery_cooldown_seconds():
                return
            self._last_recovery_at = now
            thread = threading.Thread(
                target=self._recover,
                name="rag-worker-recovery",
                daemon=True,
            )
            self._recovery_thread = thread
            thread.start()

    def _recover(self) -> None:
        argv = self._recovery_argv
        timeout = self._recovery_timeout
        if argv is None or timeout is None or self._closed:
            return
        self.counters["recoveries"] += 1
        try:
            self.prewarm(argv, timeout)
        except Exception:  # noqa: BLE001 - 失败状态已由 prewarm 内部记账
            return

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


def ensure_recovery() -> None:
    """遍历已注册 worker，对死进程调度自愈（readiness 探针的写侧半步）。

    刻意做成独立函数而不是塞进 ``status()``：status 是纯读探针，让每个
    观察者都变成治疗者会把「读状态」和「改状态」搅在一起——测试断言
    cold/failed 状态时会被隐式自愈拆台。readiness 端点显式调用本函数。
    """
    if not enabled():
        return
    with _WORKERS_LOCK:
        workers = list(_WORKERS.values())
    for worker in workers:
        worker.ensure_recovery_if_dead()


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
    counters: dict[str, int] = {}
    for item in worker_states:
        for key, value in dict(item.get("counters") or {}).items():
            counters[key] = counters.get(key, 0) + int(value)
    return {
        "enabled": is_enabled,
        "state": state,
        "active": sum(1 for worker in workers if worker.healthy()),
        "configured_workers": len(workers),
        "model_load_count": sum(worker.model_load_count for worker in workers),
        "prewarm_latency_ms": prewarm_latency_ms,
        "last_error_type": last_error_type,
        "lifecycle": "startup_prewarm",
        # 冷/热处置账：abandoned 多、killed 少 = 保活在起作用；killed 多 = worker 真在卡死。
        "counters": counters,
        "abandoned_in_flight": sum(int(item.get("abandoned_in_flight") or 0) for item in worker_states),
    }

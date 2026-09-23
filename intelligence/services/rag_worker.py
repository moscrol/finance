"""Workbench 管理的常驻 RAG 子进程客户端。"""

from __future__ import annotations

import json
import os
import re
import selectors
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.kb_code_identity import code_identity
from intelligence.services.rag_generation_identity import (
    FrozenRagGeneration,
    RagGenerationUnavailable,
    capture_generation,
)


@dataclass(frozen=True)
class WorkerResponse:
    returncode: int
    stdout: str
    stderr: str
    model_load_count: int = 0


_STDERR_TAIL_BYTES = 4096
_CHILD_ERROR_TYPES = frozenset({
    "OSError", "FileNotFoundError", "PermissionError", "ModuleNotFoundError",
    "ImportError", "RuntimeError", "ValueError", "TypeError", "MemoryError",
    "TimeoutError", "ConnectionError", "EOFError", "SystemExit",
    "LocalEntryNotFoundError", "HFValidationError",
})


def _child_error_type(stderr: str) -> str | None:
    # Only fixed names may leave this boundary; arbitrary class names can be data.
    names = re.findall(r"^([A-Za-z_][A-Za-z0-9_]*):(?: |$)", stderr, re.MULTILINE)
    return next((name for name in reversed(names) if name in _CHILD_ERROR_TYPES), None)


class WorkerExecutionError(RuntimeError):
    """Safe child failure summary, without retaining raw stderr in the exception."""

    def __init__(self, stage: str, reason: str, returncode: int | None, stderr: str):
        self.diagnostic = {
            "stage": stage,
            "reason": reason,
            "returncode": returncode,
            "error_type": _child_error_type(stderr),
        }
        message = (
            "rag worker exited without response" if stage == "process"
            else "rag worker prewarm failed"
        )
        super().__init__(f"{message}: {json.dumps(self.diagnostic)}")


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


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, value)


def keepalive_interval_seconds() -> float:
    """请求间隔多久没有真实查询就发一条轻查询把 worker 的页「摸」一遍。0 = 关（默认）。

    2026-09-04 生产读数：16 GB 机器 swap 14.4/15.4 GB，8792 常驻 worker 起来 27.5 小时
    `queries_served=1`，RSS 只剩 3.7 MB——bge-m3 + 346 MB dense.npy + 17 万 chunks 整个在盘上。
    请求之间隔几分钟到几小时，worker 被整个换出，下一次真实查询先付 20–60s 换入，
    `episode_tools` 的 30s 帽必超时（08-31 背靠背分段实测检索本身只要 3–18s）。
    keepalive 治的就是「两次请求之间」这段：定时把模型/索引页摸成 active，让分页器先换别人。
    它治症不治本（机器 swap 满时是按周期把别人换出去），根治在减负 / mmap / fp16，
    见 docs/superpowers/specs/2026-09-04-rag-worker-resident-memory-workorder.md。
    """
    return _float_env("RAG_WORKER_KEEPALIVE_SECONDS", 0.0)


def keepalive_timeout_seconds() -> float:
    """keepalive 那条查询的窗口。给得比生产工具窗宽：换入本来就是它替真实查询预付的成本。"""
    return _float_env("RAG_WORKER_KEEPALIVE_TIMEOUT_SECONDS", 60.0) or 60.0


def _process_rss_bytes(pid: int | None) -> int | None:
    """子进程当前常驻集（bytes）；只走 /proc，status 不为观察而 spawn。"""
    if pid is None:
        return None
    try:
        values = (Path("/proc") / str(pid) / "statm").read_text().split()
        resident_pages = int(values[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return None


def _sample_process_rss_bytes(pid: int | None) -> int | None:
    """查询完成时采一笔 RSS；status 只读缓存，不启动 `ps`。"""
    direct = _process_rss_bytes(pid)
    if direct is not None or pid is None:
        return direct
    try:
        completed = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = completed.stdout.strip()
    return int(value) * 1024 if value.isdigit() else None


class PersistentRagWorker:
    def __init__(
        self,
        python: str,
        kb_root: Path,
        index_dir: Path,
        kb_wiki: Path | None = None,
        *,
        generation_binding: FrozenRagGeneration | None = None,
    ) -> None:
        self.python = python
        self.kb_root = kb_root
        self.index_dir = index_dir
        self.kb_wiki = kb_wiki.resolve() if kb_wiki is not None else None
        self._generation = generation_binding or capture_generation(
            python, kb_root, index_dir, kb_wiki
        )
        self._process: subprocess.Popen[str] | None = None
        # stdout has exactly one reader: nonblocking os.read + explicit line framing.
        # Keep partial bytes across an abandoned request, but never across processes.
        self._response_process: subprocess.Popen[str] | None = None
        self._response_buffer = bytearray()
        self._stderr_tail = bytearray()
        self._code_identity = ""
        self._pycache: TemporaryDirectory | None = None
        self._lock = threading.Lock()
        self.model_load_count = 0
        self._state = "cold"
        self._last_error_type: str | None = None
        self._last_error_diagnostic: dict[str, object] | None = None
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
        self._rss_bytes: int | None = None
        # 上一次查询（含预热 / keepalive）**完成**的时刻；None = 还没服务过。
        # readiness 的 idle_seconds 从这里算——「多久没人碰它」正是它被换出的解释变量。
        self._last_query_finished_at: float | None = None
        self._keepalive_thread: threading.Thread | None = None
        self._keepalive_stop = threading.Event()
        # 处置计数走 readiness 的 status() 出去。离线普查只看得到工具层的 elapsed_ms，
        # 分不出「超时是 worker 冷启还是查询本身慢」——这里是唯一能分的地方。
        self.counters: dict[str, int] = {
            "queries_served": 0,
            "timeouts_abandoned_kept_warm": 0,
            "timeouts_killed": 0,
            "stale_responses_drained": 0,
            "recoveries": 0,
            # keepalive 账：sent 多、真实查询的 last_latency_ms 降 = 在起作用；
            # skipped_busy 多 = 真实流量本来就够密，keepalive 可以关。
            "keepalive_sent": 0,
            "keepalive_timeouts": 0,
            "keepalive_skipped_busy": 0,
        }

    def query(self, argv: list[str], timeout: float) -> WorkerResponse:
        with self._lock:
            return self._serve(argv, timeout)

    def _serve(self, argv: list[str], timeout: float) -> WorkerResponse:
        """持锁调用。真实查询与 keepalive 共用同一套失败处置，不给 keepalive 开第二套规矩。"""
        try:
            self._generation.require_available()
            response = self._query_locked(argv, timeout, allow_abandon=True)
        except WorkerRequestAbandoned:
            # 进程还热着：不标 failed、不重生、状态不动。
            raise
        except RagGenerationUnavailable as exc:
            self._mark_generation_unavailable(exc)
            raise
        except Exception as exc:
            self._mark_failed(exc)
            self._schedule_recovery()
            raise
        if response.returncode == 0 and response.model_load_count > 0:
            self._state = "ready"
            self._last_error_type = None
            self._last_error_diagnostic = None
        return response

    def prewarm(self, argv: list[str], timeout: float) -> WorkerResponse:
        with self._lock:
            try:
                self._generation.require_available()
            except RagGenerationUnavailable as exc:
                self._mark_generation_unavailable(exc)
                raise
            self._recovery_argv = list(argv)
            self._recovery_timeout = float(timeout)
            self._state = "warming"
            self._last_error_type = None
            self._last_error_diagnostic = None
            started = time.monotonic()
            try:
                # 预热不放弃：预热窗本来就是按模型加载给的，超了就是真失败。
                response = self._query_locked(argv, timeout, allow_abandon=False)
                if response.returncode != 0 or response.model_load_count < 1:
                    raise WorkerExecutionError(
                        "prewarm",
                        "worker_returned_error" if response.returncode else "model_not_loaded",
                        response.returncode,
                        response.stderr,
                    )
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
        # 预热成功才开 keepalive：冷 worker 没有「热」可保，那是预热/自愈的活。
        self._start_keepalive()
        return response

    def idle_seconds(self) -> float | None:
        if self._last_query_finished_at is None:
            return None
        return max(0.0, time.monotonic() - self._last_query_finished_at)

    def status(self) -> dict[str, object]:
        idle = self.idle_seconds()
        generation = self._generation.check()
        state = self._state if generation.available else "failed"
        active = self.healthy() and generation.available
        diagnostic = self._last_error_diagnostic
        return {
            "state": state,
            "active": active,
            "model_load_count": self.model_load_count,
            "prewarm_latency_ms": self._prewarm_latency_ms,
            "last_error_type": (
                self._last_error_type
                if generation.available
                else RagGenerationUnavailable.__name__
            ),
            "last_error_diagnostic": (
                dict(diagnostic)
                if generation.available and diagnostic is not None
                else None
            ),
            "generation_status": generation.status,
            "generation_reason": generation.reason,
            "last_latency_ms": self._last_latency_ms,
            "abandoned_in_flight": len(self._abandoned),
            "consecutive_timeouts": self._consecutive_timeouts,
            # RSS 是本进程首次完成查询后的单次采样缓存，不是 status 时刻的实时值；
            # 进程停止即清空。status 本身不为观测启动 `ps`。
            "rss_bytes": self._rss_bytes if self.healthy() else None,
            "idle_seconds": round(idle, 1) if idle is not None else None,
            "keepalive_interval_seconds": keepalive_interval_seconds(),
            "keepalive_thread_alive": bool(
                self._keepalive_thread is not None and self._keepalive_thread.is_alive()
            ),
            "counters": dict(self.counters),
        }

    def healthy(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def close(self) -> None:
        self._closed = True
        self._keepalive_stop.set()
        # 先无锁杀一次：恢复线程可能正持锁阻塞在预热的 select 里（上限=预热窗）。
        # 杀掉子进程会让它立刻读到 EOF 抛错并释放锁，否则这里要等满整个预热窗。
        self._stop_process()
        with self._lock:
            self._stop_process()
        thread = self._keepalive_thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2)

    # ── keepalive ──────────────────────────────────────────────────────────

    def _start_keepalive(self) -> None:
        interval = keepalive_interval_seconds()
        if interval <= 0 or self._closed:
            return
        if self._keepalive_thread is not None and self._keepalive_thread.is_alive():
            return
        self._keepalive_stop.clear()
        thread = threading.Thread(
            target=self._keepalive_loop,
            args=(interval,),
            name="rag-worker-keepalive",
            daemon=True,
        )
        self._keepalive_thread = thread
        thread.start()

    def keepalive_due(self, interval: float) -> bool:
        """现在该不该摸一下：worker 活着且热、离上次查询 ≥ interval。冷/死/刚服务过都不该。"""
        if (
            self._closed
            or not self._generation.check().available
            or not self.healthy()
            or self.model_load_count <= 0
        ):
            return False
        idle = self.idle_seconds()
        return idle is not None and idle >= interval

    def keepalive_once(self, interval: float) -> bool:
        """发一条 keepalive。返回是否真的发了。

        不排队：`_lock` 被真实查询占着就跳过——真实流量本身就把页摸热了，keepalive
        排在它后面只会白烧一次。超时走与真实查询同一套处置（热则放弃保留、连续两次才杀）。
        """
        if not self.keepalive_due(interval):
            return False
        argv = self._recovery_argv
        if not argv:
            return False
        if not self._lock.acquire(blocking=False):
            self.counters["keepalive_skipped_busy"] += 1
            return False
        try:
            self.counters["keepalive_sent"] += 1
            try:
                self._serve(list(argv), keepalive_timeout_seconds())
            except WorkerRequestAbandoned:
                self.counters["keepalive_timeouts"] += 1
            except Exception:  # noqa: BLE001 - _serve 已记账（failed + 自愈调度）
                self.counters["keepalive_timeouts"] += 1
        finally:
            self._lock.release()
        return True

    def _keepalive_loop(self, interval: float) -> None:
        # 醒来的节拍比 interval 密一档，这样「刚有真实查询」之后不会等满两个周期才补摸。
        tick = max(0.05, min(interval, interval / 4.0))
        while not self._keepalive_stop.wait(tick):
            if self._closed:
                return
            try:
                self.keepalive_once(interval)
            except Exception:  # noqa: BLE001 - 后台线程不得因一次异常退出
                continue

    def _ensure_process(self) -> subprocess.Popen[str]:
        self._generation.require_available()
        identity = code_identity(self.kb_root)
        if self.healthy() and self._code_identity == identity:
            return self._process
        # 每个 worker 自己持锁换代，不在全局注册表锁里杀进程/加载模型。
        self._stop_process()
        self.model_load_count = 0
        self._abandoned.clear()
        self._consecutive_timeouts = 0
        self._state = "cold"
        self._code_identity = identity
        script = Path(__file__).resolve().parents[2] / "scripts" / "rag_query_worker.py"
        # 与 kb_rag 直跑 subprocess 的 env 保持一致：模型已缓存时离线加载（省掉
        # 一次零收益的 HF Hub 往返），并静音 391 分片的 tqdm 进度条——否则进度条
        # 会被 redirect_stderr 收进 payload，让「stderr 非空」这个信号永远为真。
        # 这里用 setdefault，外部显式设置仍然优先。
        env = self._generation.child_environment() or dict(os.environ)
        if self.kb_wiki is not None:
            # Bind the actual data argument, not an unrelated ambient KB_VAULT.
            env["KB_VAULT"] = str(self.kb_wiki)
        for key, value in (
            ("HF_HUB_OFFLINE", "1"),
            ("TRANSFORMERS_OFFLINE", "1"),
            ("HF_HUB_DISABLE_PROGRESS_BARS", "1"),
            ("TRANSFORMERS_VERBOSITY", "error"),
            ("TQDM_DISABLE", "1"),
        ):
            env.setdefault(key, value)
        # CPython 的旧 pyc 可仅按 mtime+size 命中；内容变了也可能继续加载旧字节码。
        # 私有空前缀 + 不写字节码保证新进程读源文件，不删除共享仓的缓存。
        self._pycache = TemporaryDirectory(prefix="rag-worker-pycache-")
        env["PYTHONPYCACHEPREFIX"] = self._pycache.name
        env["PYTHONDONTWRITEBYTECODE"] = "1"
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
            # Import/startup failures happen before the JSON protocol exists.
            # Drain this pipe alongside stdout, retaining only a bounded private tail.
            stderr=subprocess.PIPE,
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
        if self._response_process is not process:
            os.set_blocking(process.stdout.fileno(), False)
            if process.stderr is not None:
                os.set_blocking(process.stderr.fileno(), False)
            self._response_process = process
            self._response_buffer = bytearray()
            self._stderr_tail = bytearray()
        # Local reference: close() may retire the process from another thread.
        buffer = self._response_buffer
        try:
            process.stdin.write(
                json.dumps({"id": request_id, "argv": argv}, ensure_ascii=False)
                + "\n"
            )
            process.stdin.flush()
        except BrokenPipeError:
            raise self._process_exit_error(process) from None
        started = time.monotonic()
        deadline = started + max(0.001, float(timeout))
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        if process.stderr is not None:
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        try:
            search_from = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._on_query_timeout(request_id, allow_abandon=allow_abandon)
                # Drain complete buffered lines before asking the kernel for more.
                # TextIO.readline() can prefetch a second reply behind select's back;
                # it can also block past the deadline on a partial first line.
                newline = buffer.find(b"\n", search_from)
                if newline < 0:
                    search_from = len(buffer)
                    events = selector.select(remaining)
                    if not events:
                        self._on_query_timeout(request_id, allow_abandon=allow_abandon)
                    for key, _ in events:
                        if key.data == "stderr":
                            if not self._read_stderr(process):
                                selector.unregister(key.fileobj)
                            continue
                        try:
                            chunk = os.read(process.stdout.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            raise self._process_exit_error(process)
                        buffer.extend(chunk)
                    continue
                line = bytes(buffer[:newline])
                del buffer[:newline + 1]
                search_from = 0
                # Decode only a whole frame: a read may split a UTF-8 character.
                payload = json.loads(line.decode("utf-8"))
                response_id = payload.get("id")
                if response_id in self._abandoned:
                    # 上一条被放弃请求的迟到响应：排掉，继续等自己的。
                    self._abandoned.discard(response_id)
                    self.counters["stale_responses_drained"] += 1
                    continue
                if response_id != request_id:
                    self._stop_process()
                    raise RuntimeError("rag worker response id mismatch")
                if (payload.get("code_identity") != self._code_identity
                        or code_identity(self.kb_root) != self._code_identity):
                    self._stop_process()
                    raise RuntimeError("rag worker code changed; discard response and restart")
                self._generation.require_available()
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
        self._last_query_finished_at = time.monotonic()
        if self._rss_bytes is None:
            self._rss_bytes = _sample_process_rss_bytes(process.pid)
        self._consecutive_timeouts = 0
        self.counters["queries_served"] += 1
        return response

    def _read_stderr(self, process: subprocess.Popen[str]) -> bool:
        if process.stderr is None:
            return False
        try:
            chunk = os.read(process.stderr.fileno(), 65536)
        except BlockingIOError:
            return True
        self._stderr_tail.extend(chunk)
        del self._stderr_tail[:-_STDERR_TAIL_BYTES]
        return bool(chunk)

    def _process_exit_error(self, process: subprocess.Popen[str]) -> WorkerExecutionError:
        # stdout EOF can become readable just before waitpid observes process exit.
        try:
            process.wait(timeout=0.05)
        except subprocess.TimeoutExpired:
            pass
        # Bounded nonblocking drain: stdout and stderr EOF may arrive together.
        for _ in range(4):
            if not self._read_stderr(process):
                break
        return WorkerExecutionError(
            "process", "exited_without_response", process.poll(),
            self._stderr_tail.decode("utf-8", errors="replace"),
        )

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
        self._last_error_diagnostic = (
            dict(exc.diagnostic) if isinstance(exc, WorkerExecutionError) else None
        )
        self._stop_process()

    def _mark_generation_unavailable(self, exc: RagGenerationUnavailable) -> None:
        self._mark_failed(exc)

    def ensure_recovery_if_dead(self) -> None:
        """探针侧自愈入口：进程死了且没在预热，就按配方调度重生。

        查询失败式入口（``query()`` 异常路径）覆盖不了的形状（2026-08-13
        R23 注入实测）：进程被外部杀死/自己崩掉后，若后续查询全带 filters
        （``kb_rag`` 分层检索走 CLI 不经 worker），查询入口永远不会被踩到，
        readiness 永久红、只能人工 kickstart。本入口挂在 readiness 探针上，
        不依赖查询流量；单飞与冷却仍由 ``_schedule_recovery`` 统一把关，
        探针轮询不会打出重复预热。
        """
        if not self._generation.check().available:
            return
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
        if (
            argv is None
            or timeout is None
            or self._closed
            or not self._generation.check().available
        ):
            return
        self.counters["recoveries"] += 1
        try:
            self.prewarm(argv, timeout)
        except Exception:  # noqa: BLE001 - 失败状态已由 prewarm 内部记账
            return

    def _stop_process(self) -> None:
        process = self._process
        self._process = None
        self._rss_bytes = None
        self._response_process = None
        self._response_buffer = bytearray()
        self._abandoned.clear()
        self._consecutive_timeouts = 0
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if process is not None and process.stderr is not None:
            process.stderr.close()
        self._stderr_tail = bytearray()
        pycache, self._pycache = self._pycache, None
        if pycache is not None:
            pycache.cleanup()


_WORKERS: dict[tuple[object, ...], PersistentRagWorker] = {}
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
    kb_wiki: Path | None = None,
) -> PersistentRagWorker:
    generation = capture_generation(python, kb_root, index_dir, kb_wiki)
    key = (python, str(kb_root.resolve()), str(index_dir.resolve()),
           str(kb_wiki.resolve()) if kb_wiki is not None else "",
           *generation.pool_identity)
    with _WORKERS_LOCK:
        worker = _WORKERS.get(key)
        if worker is None:
            worker = PersistentRagWorker(
                python,
                kb_root,
                index_dir,
                kb_wiki,
                generation_binding=generation,
            )
            _WORKERS[key] = worker
    return worker


def query(
    *,
    python: str,
    kb_root: Path,
    index_dir: Path,
    argv: list[str],
    timeout: float,
    kb_wiki: Path | None = None,
) -> WorkerResponse:
    return _worker_for(python, kb_root, index_dir, kb_wiki).query(argv, timeout)


def prewarm(
    *,
    python: str,
    kb_root: Path,
    index_dir: Path,
    argv: list[str],
    timeout: float,
    kb_wiki: Path | None = None,
) -> WorkerResponse:
    global _STARTUP_FAILURE_TYPE
    with _WORKERS_LOCK:
        _STARTUP_FAILURE_TYPE = None
    try:
        worker = _worker_for(python, kb_root, index_dir, kb_wiki)
    except Exception as exc:
        record_startup_failure(exc)
        raise
    # Once registered, failure and recovery belong to the worker, not a second
    # global latch that a successful background prewarm cannot clear.
    return worker.prewarm(argv, timeout)


def record_startup_failure(exc: Exception) -> None:
    """Record configuration/construction failure before a worker can own it."""
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
    rss_values = [
        int(item["rss_bytes"])
        for item in worker_states
        if isinstance(item.get("rss_bytes"), int)
    ]
    idle_values = [
        float(item["idle_seconds"])
        for item in worker_states
        if isinstance(item.get("idle_seconds"), (int, float))
    ]
    return {
        "enabled": is_enabled,
        "state": state,
        "active": sum(1 for item in worker_states if item["active"]),
        "configured_workers": len(workers),
        "model_load_count": sum(worker.model_load_count for worker in workers),
        "prewarm_latency_ms": prewarm_latency_ms,
        "last_error_type": last_error_type,
        "last_error_diagnostic": next(
            (item.get("last_error_diagnostic") for item in worker_states
             if item.get("last_error_type")), None,
        ),
        "lifecycle": "startup_prewarm",
        # 冷/热处置账：abandoned 多、killed 少 = 保活在起作用；killed 多 = worker 真在卡死。
        "counters": counters,
        "abandoned_in_flight": sum(int(item.get("abandoned_in_flight") or 0) for item in worker_states),
        # 各进程首次完成查询后的 RSS 采样之和；不是 status 时刻的实时 RSS。
        "rss_bytes": sum(rss_values) if rss_values else None,
        "idle_seconds": round(max(idle_values), 1) if idle_values else None,
        "keepalive_interval_seconds": keepalive_interval_seconds(),
    }

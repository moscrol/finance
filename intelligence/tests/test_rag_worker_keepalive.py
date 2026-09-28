"""常驻 RAG worker 的 keepalive 与换出可观测（工单 #22 步骤 2/3）。

2026-09-04 生产读数：16 GB 机器 swap 14.4/15.4 GB，8792 worker 起来 27.5h `queries_served=1`、
RSS 3.7 MB——模型与索引整个被换出，下一次真实查询先付 20–60s 换入，30s 帽必超时。
这里守的是：keepalive 默认关；开了只在「热、活着、空闲够久、锁空着」时发；超时走与真实
查询同一套处置；close 能停线程；status 露出 rss_bytes / idle_seconds。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from intelligence.services import rag_worker
from intelligence.services.rag_worker import PersistentRagWorker
from intelligence.tests.test_rag_worker import _write_fake_rag


def _worker(tmp_path: Path) -> PersistentRagWorker:
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir(exist_ok=True)
    return PersistentRagWorker(sys.executable, tmp_path, index)


def _wait_until(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_keepalive_is_off_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAG_WORKER_KEEPALIVE_SECONDS", raising=False)
    worker = _worker(tmp_path)
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        status = worker.status()
    finally:
        worker.close()

    assert status["keepalive_interval_seconds"] == 0.0
    assert status["keepalive_thread_alive"] is False
    assert status["counters"]["keepalive_sent"] == 0


def test_keepalive_touches_an_idle_warm_worker_without_reloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_WORKER_KEEPALIVE_SECONDS", "0.1")
    worker = _worker(tmp_path)
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        pid = worker._process.pid  # type: ignore[union-attr]
        assert worker.status()["keepalive_thread_alive"] is True
        assert _wait_until(lambda: worker.counters["keepalive_sent"] >= 2)
        status = worker.status()
        assert worker._process.pid == pid  # type: ignore[union-attr]
    finally:
        worker.close()

    # keepalive 发的是预热同款 argv，走同一个进程、同一次模型加载。
    assert status["model_load_count"] == 1
    assert status["counters"]["queries_served"] >= 3  # prewarm + ≥2 keepalive
    assert status["counters"]["keepalive_timeouts"] == 0
    assert status["state"] == "ready"


def test_keepalive_not_due_right_after_real_traffic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_WORKER_KEEPALIVE_SECONDS", "3600")
    worker = _worker(tmp_path)
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        worker.query(["query", "real", "--json"], timeout=2)
        due_now = worker.keepalive_due(3600)
        # 把「上次完成」推到一小时前：该摸了。
        worker._last_query_finished_at = time.monotonic() - 3601
        due_after_idle = worker.keepalive_due(3600)
        sent = worker.keepalive_once(3600)
    finally:
        worker.close()

    assert due_now is False
    assert due_after_idle is True
    assert sent is True


def test_keepalive_skips_cold_or_dead_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_WORKER_KEEPALIVE_SECONDS", "1")
    worker = _worker(tmp_path)
    try:
        # 没预热过：冷，没有「热」可保。
        assert worker.keepalive_due(0) is False
        assert worker.keepalive_once(0) is False
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        worker._last_query_finished_at = time.monotonic() - 10
        assert worker.keepalive_due(1) is True
        worker._stop_process()  # 进程死了：交给自愈，不是 keepalive 的活
        assert worker.keepalive_due(1) is False
    finally:
        worker.close()


def test_keepalive_does_not_queue_behind_a_real_query(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_WORKER_KEEPALIVE_SECONDS", "1")
    worker = _worker(tmp_path)
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        worker._last_query_finished_at = time.monotonic() - 10
        assert worker._lock.acquire(blocking=False)
        try:
            sent = worker.keepalive_once(1)
        finally:
            worker._lock.release()
        skipped = worker.counters["keepalive_skipped_busy"]
    finally:
        worker.close()

    assert sent is False
    assert skipped == 1
    assert worker.counters["keepalive_sent"] == 0


def test_keepalive_timeout_uses_the_same_policy_as_real_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """热 worker 上 keepalive 超窗：放弃保留，不杀、不重生；计入 keepalive_timeouts。"""
    monkeypatch.setenv("RAG_WORKER_KEEPALIVE_SECONDS", "1")
    monkeypatch.setenv("RAG_WORKER_KEEPALIVE_TIMEOUT_SECONDS", "0.02")
    monkeypatch.setenv("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "0")
    worker = _worker(tmp_path)
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        pid = worker._process.pid  # type: ignore[union-attr]
        worker._recovery_argv = ["query", "slow", "--json"]  # 让 keepalive 那条查询慢过窗
        worker._last_query_finished_at = time.monotonic() - 10
        sent = worker.keepalive_once(1)
        status = worker.status()
        alive = worker.healthy() and worker._process.pid == pid  # type: ignore[union-attr]
    finally:
        worker.close()

    assert sent is True
    assert alive is True, "热 worker 首次超时只放弃请求，不杀进程"
    assert status["counters"]["keepalive_timeouts"] == 1
    assert status["counters"]["timeouts_abandoned_kept_warm"] == 1
    assert status["counters"]["timeouts_killed"] == 0
    assert status["state"] == "ready"


def test_close_stops_keepalive_thread(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_WORKER_KEEPALIVE_SECONDS", "0.1")
    worker = _worker(tmp_path)
    worker.prewarm(["query", "warmup", "--json"], timeout=2)
    thread = worker._keepalive_thread
    assert thread is not None and thread.is_alive()
    worker.close()
    assert _wait_until(lambda: not thread.is_alive(), timeout=3)
    assert worker.status()["keepalive_thread_alive"] is False


def test_status_exposes_rss_and_idle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAG_WORKER_KEEPALIVE_SECONDS", raising=False)
    worker = _worker(tmp_path)
    try:
        before = worker.status()
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        time.sleep(0.05)
        after = worker.status()
    finally:
        worker.close()
    closed = worker.status()

    assert before["rss_bytes"] is None and before["idle_seconds"] is None
    assert isinstance(after["rss_bytes"], int) and after["rss_bytes"] > 0
    assert isinstance(after["idle_seconds"], float) and after["idle_seconds"] >= 0.0
    assert closed["rss_bytes"] is None, "进程没了就不该还报一个 RSS"


def test_module_status_aggregates_rss_idle_and_keepalive_counters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    monkeypatch.setenv("RAG_WORKER_KEEPALIVE_SECONDS", "0")
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    rag_worker.close_all()
    try:
        rag_worker.prewarm(
            python=sys.executable,
            kb_root=tmp_path,
            index_dir=index,
            argv=["query", "warmup", "--json"],
            timeout=2,
        )
        payload = rag_worker.status()
    finally:
        rag_worker.close_all()

    assert isinstance(payload["rss_bytes"], int) and payload["rss_bytes"] > 0
    assert isinstance(payload["idle_seconds"], float)
    assert payload["keepalive_interval_seconds"] == 0.0
    for key in ("keepalive_sent", "keepalive_timeouts", "keepalive_skipped_busy"):
        assert payload["counters"][key] == 0

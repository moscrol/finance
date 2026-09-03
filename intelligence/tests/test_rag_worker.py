from __future__ import annotations

import sys
import json
from pathlib import Path
from unittest import mock

import pytest

from intelligence.services import kb_rag
from intelligence.services.rag_worker import PersistentRagWorker, WorkerResponse
from intelligence.services import rag_worker


def _write_fake_rag(root: Path) -> None:
    script = root / "scripts" / "rag_index.py"
    script.parent.mkdir(parents=True)
    (script.parent / "rag_freshness.py").write_text(
        'IMPORT_CONTEXT = "knowledge-base-scripts"\n',
        encoding="utf-8",
    )
    script.write_text(
        """
import json
import time

try:
    from scripts.rag_freshness import IMPORT_CONTEXT
except ImportError:
    from rag_freshness import IMPORT_CONTEXT

class RagStore:
    # 复现知识库仓现状：cmd_query 每次传入新的 RagStore 实例。
    # 不可哈希。worker 若再用 lru_cache 包 _load_retriever，预热会 TypeError。
    __hash__ = None

    def __eq__(self, other):
        return False

def _load_retriever(model, need_dense, reranker_name=None, store=None, index_freshness=None):
    return object()

def main(argv=None):
    argv = list(argv or [])
    query = argv[1]
    _load_retriever("hash", True, None, store=RagStore(), index_freshness="fresh")
    if query == "slow":
        time.sleep(0.2)
    print(json.dumps([{"query": query, "import_context": IMPORT_CONTEXT}], ensure_ascii=False))
    return 0
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_worker_reuses_loaded_retriever(tmp_path: Path) -> None:
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        first = worker.query(["query", "first", "--json"], timeout=2)
        second = worker.query(["query", "second", "--json"], timeout=2)
    finally:
        worker.close()

    assert first.returncode == 0
    assert second.returncode == 0
    assert first.model_load_count == 1
    assert second.model_load_count == 1
    assert '"query": "second"' in second.stdout
    assert '"import_context": "knowledge-base-scripts"' in second.stdout


def test_timeout_terminates_worker_and_next_query_restarts(tmp_path: Path) -> None:
    """冷 worker（还没加载过模型）超时照旧杀：没有「热」可保。"""

    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        with pytest.raises(TimeoutError) as excinfo:
            worker.query(["query", "slow", "--json"], timeout=0.02)
        assert not isinstance(excinfo.value, rag_worker.WorkerRequestAbandoned)
        assert worker.healthy() is False
        recovered = worker.query(["query", "recovered", "--json"], timeout=2)
    finally:
        worker.close()

    assert recovered.returncode == 0
    assert recovered.model_load_count == 1


def test_prewarm_marks_worker_ready_and_reuses_model(tmp_path: Path) -> None:
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        first = worker.prewarm(["query", "warmup", "--json"], timeout=2)
        warm_status = worker.status()
        second = worker.query(["query", "actual", "--json"], timeout=2)
    finally:
        worker.close()

    assert first.returncode == 0
    assert first.model_load_count == second.model_load_count == 1
    assert warm_status["state"] == "ready"
    assert warm_status["active"] is True
    assert warm_status["last_error_type"] is None
    assert isinstance(warm_status["prewarm_latency_ms"], int)


def test_prewarm_timeout_is_failed_and_stops_process(tmp_path: Path) -> None:
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        with pytest.raises(TimeoutError):
            worker.prewarm(["query", "slow", "--json"], timeout=0.02)
        payload = worker.status()
    finally:
        worker.close()

    assert payload["state"] == "failed"
    assert payload["active"] is False
    assert payload["last_error_type"] == "TimeoutError"
    assert isinstance(payload["prewarm_latency_ms"], int)


def test_warm_worker_survives_first_timeout_and_drains_the_late_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """热 worker 第一次超窗：放弃请求、进程保留、不起自愈；迟到的响应由下一次查询排掉。

    2026-09-03 生产读数：kb_search 66% 的调用超时，老处置「超时即杀 + 重生（模型加载
    50–145s）」让一次慢查询换来一两分钟的必败。这里守：(1) 进程还活着、状态仍 ready；
    (2) 没有自愈线程；(3) 下一次查询拿到的是**自己的**响应，不是那条迟到的 slow。
    """
    monkeypatch.setenv("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "0")
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        pid_before = worker._process.pid  # type: ignore[union-attr]
        with pytest.raises(rag_worker.WorkerRequestAbandoned):
            worker.query(["query", "slow", "--json"], timeout=0.02)
        after_abandon = worker.status()
        assert worker.healthy() is True
        assert worker._process.pid == pid_before  # type: ignore[union-attr]
        assert worker._recovery_thread is None
        follow_up = worker.query(["query", "next", "--json"], timeout=2)
        after_drain = worker.status()
    finally:
        worker.close()

    assert after_abandon["state"] == "ready"
    assert after_abandon["abandoned_in_flight"] == 1
    assert after_abandon["consecutive_timeouts"] == 1
    assert after_abandon["counters"]["timeouts_abandoned_kept_warm"] == 1
    assert after_abandon["counters"]["timeouts_killed"] == 0
    assert '"query": "next"' in follow_up.stdout
    assert follow_up.model_load_count == 1, "同一个进程、同一次模型加载"
    assert after_drain["abandoned_in_flight"] == 0
    assert after_drain["consecutive_timeouts"] == 0
    assert after_drain["counters"]["stale_responses_drained"] == 1
    assert after_drain["counters"]["queries_served"] >= 2  # prewarm + next


def test_second_consecutive_timeout_kills_and_self_heals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """热 worker 连续两次超窗才算卡死：第二次杀进程并按预热配方后台重生。

    生产失败形状（2026-08-13）：预热窗 240s > 查询窗 90s，模型加载 ~145s。
    杀进程后「下次查询自然重启」必然二次超时，readiness 永久红——自愈必须用预热的窗口。
    这一段保活改动一个字没碰。
    """
    monkeypatch.setenv("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "0")
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        with pytest.raises(rag_worker.WorkerRequestAbandoned):
            worker.query(["query", "slow", "--json"], timeout=0.02)
        with pytest.raises(TimeoutError) as second:
            worker.query(["query", "slow", "--json"], timeout=0.02)
        assert not isinstance(second.value, rag_worker.WorkerRequestAbandoned)
        killed = worker.status()
        thread = worker._recovery_thread
        assert thread is not None, "连续第二次超时后必须调度后台自愈"
        thread.join(timeout=10)
        assert not thread.is_alive()
        payload = worker.status()
    finally:
        worker.close()

    assert killed["counters"]["timeouts_killed"] == 1
    assert killed["abandoned_in_flight"] == 0
    assert payload["state"] == "ready"
    assert payload["active"] is True
    assert payload["last_error_type"] is None
    assert payload["counters"]["recoveries"] == 1


def test_query_timeout_without_prewarm_recipe_stays_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """没做过 prewarm 的 worker 查询失败后不自愈：没有已知安全的重生口径。"""
    monkeypatch.setenv("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "0")
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        with pytest.raises(TimeoutError):
            worker.query(["query", "slow", "--json"], timeout=0.02)
        assert worker._recovery_thread is None
        payload = worker.status()
    finally:
        worker.close()

    assert payload["state"] == "failed"


def test_recovery_respects_cooldown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """冷却期内的连续失败不重复起自愈线程——索引真坏时不能烧 CPU 循环重载。"""
    monkeypatch.setenv("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "3600")
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)

    def _kill_via_two_timeouts() -> None:
        # 保活契约：热 worker 第一次超时只放弃，连续第二次才杀——杀一次要两发。
        with pytest.raises(rag_worker.WorkerRequestAbandoned):
            worker.query(["query", "slow", "--json"], timeout=0.02)
        with pytest.raises(TimeoutError):
            worker.query(["query", "slow", "--json"], timeout=0.02)

    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=2)
        _kill_via_two_timeouts()
        first_thread = worker._recovery_thread
        assert first_thread is not None
        first_thread.join(timeout=10)
        _kill_via_two_timeouts()
        assert worker._recovery_thread is first_thread, "冷却期内不得再起新线程"
    finally:
        worker.close()


def test_closed_worker_does_not_schedule_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "0")
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    worker.prewarm(["query", "warmup", "--json"], timeout=2)
    worker.close()
    with pytest.raises((TimeoutError, RuntimeError)):
        worker.query(["query", "slow", "--json"], timeout=0.02)
    assert worker._recovery_thread is None


def test_probe_recovery_revives_externally_killed_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """探针发现死进程要按预热配方拉起——不依赖查询流量。

    R23 注入实测（2026-08-13）：杀掉子进程后 episode 的 KB 查询全带
    filters 走 CLI，查询失败式自愈的入口永远不被踩到，readiness 永久红。
    探针入口就是为这个形状开的。
    """
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    monkeypatch.setenv("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "0")
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    try:
        rag_worker.prewarm(
            python=sys.executable,
            kb_root=tmp_path,
            index_dir=index,
            argv=["query", "warmup", "--json"],
            timeout=5,
        )
        with rag_worker._WORKERS_LOCK:
            (worker,) = rag_worker._WORKERS.values()
        # 外部杀死：等价于进程自己崩掉——没有任何查询异常会被抛出。
        assert worker._process is not None
        worker._process.kill()
        worker._process.wait(timeout=5)
        assert worker.healthy() is False
        before = rag_worker.status()
        assert before["active"] == 0

        rag_worker.ensure_recovery()
        thread = worker._recovery_thread
        assert thread is not None, "探针必须为死进程调度自愈"
        thread.join(timeout=10)
        after = rag_worker.status()
    finally:
        rag_worker.close_all()

    assert after["state"] == "ready"
    assert after["active"] == 1
    # model_load_count 是**进程内**计数：自愈起的新进程重载一次后从 1 起，
    # 不做跨进程累计。真正证明重载发生的是 active 0→1 + state ready。
    assert after["model_load_count"] == 1


def test_probe_recovery_skips_healthy_and_warming_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_WORKER_RECOVERY_COOLDOWN_SECONDS", "0")
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=5)
        worker.ensure_recovery_if_dead()
        assert worker._recovery_thread is None, "健康 worker 不得被探针重启"

        # warming：预热正在进行（进程可能尚未 spawn），探针不得叠一发。
        worker._process.kill()
        worker._process.wait(timeout=5)
        worker._state = "warming"
        worker.ensure_recovery_if_dead()
        assert worker._recovery_thread is None
    finally:
        worker.close()


def test_module_ensure_recovery_is_noop_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_WORKER_ENABLED", "0")
    # 不应触碰任何 worker：直接调用不抛错即可。
    rag_worker.ensure_recovery()


def test_kb_rag_uses_enabled_worker_without_cli(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    page = wiki / "concepts" / "液冷.md"
    page.parent.mkdir(parents=True)
    page.write_text("# 液冷\n", encoding="utf-8")
    script = tmp_path / kb_rag.RAG_SCRIPT_REL
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# fixture\n", encoding="utf-8")
    (tmp_path / ".rag_index").mkdir()
    payload = [
        {
            "page_id": "液冷",
            "file_path": "wiki/concepts/液冷.md",
            "title": "液冷",
            "score": 0.9,
            "best_chunk_id": "液冷::0",
            "content_hash": "hash",
            "evidence_text": "液冷证据",
            "index_source_revision": "abc",
            "index_freshness": "fresh",
        }
    ]
    response = WorkerResponse(
        returncode=0,
        stdout=json.dumps(payload, ensure_ascii=False),
        stderr="",
        model_load_count=1,
    )

    with mock.patch.dict(
        "os.environ",
        {"RAG_WORKER_ENABLED": "1", "KB_RAG_PYTHON": sys.executable},
        clear=False,
    ):
        with mock.patch.object(kb_rag.rag_worker, "query", return_value=response):
            with mock.patch("subprocess.run") as cli:
                result = kb_rag.retrieve("液冷", wiki)

    assert result.ok is True
    assert result.telemetry.query_protocol == "persistent_worker"
    cli.assert_not_called()


def test_kb_rag_prewarm_uses_production_runtime_without_business_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    script = tmp_path / kb_rag.RAG_SCRIPT_REL
    script.parent.mkdir(exist_ok=True)
    script.write_text("# fixture\n", encoding="utf-8")
    index = tmp_path / ".rag_index"
    index.mkdir()
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    monkeypatch.setenv("KB_RAG_PYTHON", sys.executable)
    monkeypatch.setenv("RAG_INDEX_DIR", str(index))
    kb_rag.clear_result_cache()
    before = len(kb_rag._RESULT_CACHE)
    response = WorkerResponse(
        returncode=0,
        stdout="[]",
        stderr="",
        model_load_count=1,
    )

    with mock.patch.object(
        kb_rag.rag_worker,
        "prewarm",
        return_value=response,
    ) as worker_call:
        kb_rag.prewarm(wiki, timeout=90)

    assert worker_call.call_args.kwargs == {
        "python": sys.executable,
        "kb_root": tmp_path,
        "index_dir": index,
        "argv": [
            "query",
            "Workbench RAG 预热",
            "--k",
            "1",
            "--mode",
            "hybrid",
            "--stale-policy",
            kb_rag._STALE_POLICY,
            "--json",
        ],
        "timeout": 90,
    }
    assert len(kb_rag._RESULT_CACHE) == before


def test_prewarm_and_query_send_the_same_stale_policy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """预热与普通查询必须用同一个 stale 口径，否则同一索引状态有两个答案。

    历史缺陷：普通查询在 `_run_rag_cli` 里补 `--stale-policy`（`_STALE_POLICY`
    默认 `warn`），预热的 argv 却整个漏掉它，落到 KB 侧 CLI 自己的默认 `fail`。
    索引一旦过期，普通查询照常降级返回结果、预热硬失败 → 整个服务报 not_ready。
    更严的那条路是没人显式选过的，这是「默认值分叉」而不是「策略选择」。

    断言的是**下发的实参**而不是「跑两遍看结果一样」：后者在两侧恰好错成同一种
    时会一起变绿。这个做法在任何参数对齐类测试里都适用（同仓
    `test_source_dirty_uses_one_git_status_convention_on_both_sides` 用的是同一招）。
    """

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    script = tmp_path / kb_rag.RAG_SCRIPT_REL
    script.parent.mkdir(exist_ok=True)
    script.write_text("# fixture\n", encoding="utf-8")
    index = tmp_path / ".rag_index"
    index.mkdir()
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    monkeypatch.setenv("KB_RAG_PYTHON", sys.executable)
    monkeypatch.setenv("RAG_INDEX_DIR", str(index))
    kb_rag.clear_result_cache()

    with mock.patch.object(
        kb_rag.rag_worker,
        "prewarm",
        return_value=WorkerResponse(
            returncode=0,
            stdout="[]",
            stderr="",
            model_load_count=1,
        ),
    ) as worker_call:
        kb_rag.prewarm(wiki, timeout=90)

    argv = worker_call.call_args.kwargs["argv"]
    assert "--stale-policy" in argv, (
        "预热漏了 --stale-policy，会落到 KB 侧默认 fail；"
        "过期索引下普通查询降级、预热硬失败，整个服务报 not_ready"
    )
    assert argv[argv.index("--stale-policy") + 1] == kb_rag._STALE_POLICY


def test_kb_rag_prewarm_is_noop_when_worker_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("RAG_WORKER_ENABLED", raising=False)

    with mock.patch.object(kb_rag.rag_worker, "prewarm") as worker_call:
        payload = kb_rag.prewarm(tmp_path / "wiki", timeout=90)

    worker_call.assert_not_called()
    assert payload["state"] == "disabled"


def test_startup_failure_status_exposes_only_error_type(monkeypatch) -> None:
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    rag_worker.close_all()
    try:
        rag_worker.record_startup_failure(
            RuntimeError("sensitive query and local path must stay private")
        )
        payload = rag_worker.status()
    finally:
        rag_worker.close_all()

    assert payload["state"] == "failed"
    assert payload["last_error_type"] == "RuntimeError"
    assert "sensitive" not in json.dumps(payload)


def test_worker_status_reports_lazy_lifecycle(monkeypatch) -> None:
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")

    payload = rag_worker.status()

    assert payload["enabled"] is True
    assert payload["lifecycle"] == "startup_prewarm"
    assert payload["state"] in {"cold", "ready", "failed", "warming"}
    assert isinstance(payload["active"], int)


def test_hashable_cache_key_treats_distinct_stores_as_the_same_loader() -> None:
    """同一 (model, mode, freshness) 换一个 RagStore 实例，必须命中同一缓存键。

    否则 worker 会每问一次就重新 load BGE，预热的意义全没了。
    """

    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts" / "rag_query_worker.py"
    spec = importlib.util.spec_from_file_location("rag_query_worker_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class RagStore:
        __hash__ = None

        def __eq__(self, other):
            return False

    key_a = module._hashable_cache_key(
        ("bge-m3", True, None),
        {"store": RagStore(), "index_freshness": "fresh"},
    )
    key_b = module._hashable_cache_key(
        ("bge-m3", True, None),
        {"store": RagStore(), "index_freshness": "fresh"},
    )
    key_stale = module._hashable_cache_key(
        ("bge-m3", True, None),
        {"store": RagStore(), "index_freshness": "stale"},
    )
    assert key_a == key_b
    assert key_a != key_stale


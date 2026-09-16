from __future__ import annotations

import sys
import json
import subprocess
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


def _write_flipable_rag(root: Path) -> None:
    """夹具：每次 query 现读 verdict.txt / meta.json，形状对齐 KB 的 cmd_query。

    旧夹具的 `_load_retriever` 写死 `index_freshness="fresh"`，测不出「verdict
    翻转 → 第二次 load 模型」。这里让磁盘上的两个文件成为可翻转的旋钮。

    store 必须走 `rag_store.RagStore.load`（classmethod）而不是直接构造：worker 的
    `_install_store_cache` 就补在这个名字上，直接 `RagStore()` 会让 store cache 整段
    旁路，「换索引后 store 被读了几次 / 热 retriever 拿的是不是同一份」就测不到。
    每行回执带 `store_loads`（盘上读了几次）和 `store_is_retriever_store`
    （cmd_query 手里的 store 与热 retriever 手里的是否同一对象）两个观测量。
    """

    script = root / "scripts" / "rag_index.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    (script.parent / "rag_freshness.py").write_text(
        'IMPORT_CONTEXT = "knowledge-base-scripts"\n',
        encoding="utf-8",
    )
    script.write_text(
        """
import json
import os
from pathlib import Path

STORE_LOADS = []

class _Config:
    @staticmethod
    def index_dir():
        return Path(os.environ["RAG_INDEX_DIR"])

config = _Config()

class _Chunks:
    # 复现 KB 懒读表（knowledge-base-private #143）的接口：len / [row] 可用，
    # 整表遍历要付 169k 行解析 + 1.4 GB——记下遍历次数，worker 一次都不该碰。
    ITER_CALLS = 0

    def __init__(self):
        self._rows = [
            {"id": "c1", "text": "证据正文", "section": "s", "content_hash": "h1"}
        ]

    def __len__(self):
        return len(self._rows)

    def __getitem__(self, row):
        return self._rows[row]

    def __iter__(self):
        type(self).ITER_CALLS += 1
        return iter(self._rows)

class RagStore:
    __hash__ = None

    def __eq__(self, other):
        return False

    def __init__(self, meta):
        self.meta = meta
        self.chunks = _Chunks()

    @classmethod
    def load(cls, in_dir=None):
        in_dir = Path(in_dir or config.index_dir())
        STORE_LOADS.append(str(in_dir))
        meta_path = in_dir / "meta.json"
        return cls(json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {})

class _StoreModule:
    RagStore = RagStore

rag_store = _StoreModule()

class Retriever:
    def __init__(self, store, index_freshness):
        self.store = store
        self.index_freshness = index_freshness
        # 与真 Retriever 同名：enrich 按 id 查行号、再从 store.chunks 取那一行
        self.chunks = store.chunks
        self.row_by_chunk_id = {"c1": 0}

def _load_retriever(model, need_dense, reranker_name=None, store=None, index_freshness=None):
    return Retriever(store, index_freshness)

def main(argv=None):
    argv = list(argv or [])
    query = argv[1]
    index = config.index_dir()
    verdict_path = index / "verdict.txt"
    verdict = verdict_path.read_text(encoding="utf-8").strip() if verdict_path.is_file() else "stale"
    store = rag_store.RagStore.load(index)
    # 生产 cmd_query 走关键字；这里按位置传 freshness，e2e 同时锁住
    # 「只认 kwargs 就会静默复发」那条。症状一样：翻转一次就多 load 一次。
    r = _load_retriever("bge-m3", True, None, store, verdict)
    print(json.dumps([{
        "query": query,
        "best_chunk_id": "c1",
        "file_path": "wiki/x.md",
        "snippet": "证据正文",
        "store_loads": len(STORE_LOADS),
        "chunks_iterated": _Chunks.ITER_CALLS,
        "store_is_retriever_store": r.store is store,
    }], ensure_ascii=False))
    return 0
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_freshness_flip_does_not_reload_model(tmp_path: Path) -> None:
    """靶心：整库 verdict 翻转不得第二次加载模型。

    老键是 `(model, need_dense, reranker, index_freshness)`。KB 侧 cmd_query
    每次请求现算 verdict 递进来，于是 `rag update`（stale→fresh）或下一次
    ingest（fresh→stale）各 miss 一次，每次 miss 再 new 一个 BGEM3FlagModel，
    旧的永不回收。
    """

    _write_flipable_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    (index / "meta.json").write_text(
        '{"built_at": "2026-08-31T11:01:16Z"}', encoding="utf-8"
    )
    (index / "verdict.txt").write_text("stale", encoding="utf-8")
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        first = worker.query(["query", "first", "--json"], timeout=2)
        (index / "verdict.txt").write_text("fresh", encoding="utf-8")
        second = worker.query(["query", "second", "--json"], timeout=2)
    finally:
        worker.close()

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.model_load_count == 1
    assert second.model_load_count == 1, "verdict 翻转触发了第二次加载模型"
    first_row = json.loads(first.stdout)[0]
    second_row = json.loads(second.stdout)[0]
    assert first_row["index_freshness"] == "stale"
    assert second_row["index_freshness"] == "fresh", "复用热 retriever 时没把当次 verdict 盖回去"
    assert second_row["store_loads"] == 1, "索引没变，verdict 翻转不该再从盘上读 store"
    assert first_row["store_is_retriever_store"] and second_row["store_is_retriever_store"]


def test_index_rebuild_reloads_once_and_serves_new_store(tmp_path: Path) -> None:
    """换索引必须再 load 一次，且 enrich 读的是新 store，不是旧索引配新判定。

    同时锁住 store cache 与 loader cache 的时序：换索引那次 store 从盘上读第 2 遍即止，
    **之后**的 query 不得再读第 3 遍。此前 `_evict_other_indexes` 顺手清了 store cache，
    把 cmd_query 刚换进槽里的新 store 也清掉，于是下一次 query 再读一份——而这一份与
    热 retriever 手里的不是同一个对象，同一索引两份长期同驻，直到下次重建。
    """

    _write_flipable_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    (index / "meta.json").write_text(
        '{"built_at": "2026-08-31T11:01:16Z"}', encoding="utf-8"
    )
    (index / "verdict.txt").write_text("stale", encoding="utf-8")
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        first = worker.query(["query", "first", "--json"], timeout=2)
        (index / "meta.json").write_text(
            '{"built_at": "2026-09-03T10:56:51Z"}', encoding="utf-8"
        )
        (index / "verdict.txt").write_text("fresh", encoding="utf-8")
        second = worker.query(["query", "second", "--json"], timeout=2)
        third = worker.query(["query", "third", "--json"], timeout=2)
    finally:
        worker.close()

    assert first.returncode == second.returncode == third.returncode == 0
    assert first.model_load_count == 1
    assert second.model_load_count == 2, "换索引应当再 load 一次"
    assert third.model_load_count == 2, "新索引上的第二次 query 不应再 load"
    first_row = json.loads(first.stdout)[0]
    second_row = json.loads(second.stdout)[0]
    third_row = json.loads(third.stdout)[0]
    assert first_row["index_built_at"] == "2026-08-31T11:01:16Z"
    assert second_row["index_built_at"] == "2026-09-03T10:56:51Z"
    assert second_row["index_freshness"] == "fresh"
    assert first_row["index_source_revision"] != second_row["index_source_revision"]
    assert second_row["store_loads"] == 2, "换索引时 store 从盘上读第 2 遍"
    assert third_row["store_loads"] == 2, "新索引上的第二次 query 又从盘上读了一份 store"
    assert third_row["store_is_retriever_store"], (
        "cmd_query 手里的 store 与热 retriever 的不是同一对象：同一索引两份同驻"
    )


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


def _worker_query_fixture(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    page = wiki / "concepts" / "液冷.md"
    page.parent.mkdir(parents=True)
    page.write_text("# 液冷\n", encoding="utf-8")
    script = tmp_path / kb_rag.RAG_SCRIPT_REL
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# fixture\n", encoding="utf-8")
    (tmp_path / ".rag_index").mkdir()
    return wiki


def _retrieve_with_worker_error(wiki: Path, exc: BaseException, query: str):
    # CLI 回退真被走到时要能解析：给一个空命中的合法 JSON，让断言落在
    # 「有没有回退」上，而不是被 MagicMock 的解析异常带偏。
    cli_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")
    with mock.patch.dict(
        "os.environ",
        {"RAG_WORKER_ENABLED": "1", "KB_RAG_PYTHON": sys.executable},
        clear=False,
    ):
        with mock.patch.object(kb_rag.rag_worker, "query", side_effect=exc):
            with mock.patch("subprocess.run", return_value=cli_proc) as cli:
                result = kb_rag.retrieve(query, wiki)
    return result, cli


def test_abandoned_query_returns_timeout_without_reloading_the_model(
    tmp_path: Path,
) -> None:
    """放弃 ≠ 不可用：热 worker 还在，回退 CLI 会重载 4.3G 模型。

    ``WorkerRequestAbandoned`` 继承 ``TimeoutError`` → ``OSError``。这个断言钉的
    是 ``kb_rag.retrieve`` 里 except 子句的**顺序**：一旦它排到
    ``(RuntimeError, OSError, json.JSONDecodeError)`` 之后就永远匹配不到，超时会
    被判成 `persistent_worker_unavailable` 并用残窗起 CLI——2026-09-03 生产实测
    kb_search 66% 以 tool_timeout 收场就是这条路。
    """

    wiki = _worker_query_fixture(tmp_path)
    result, cli = _retrieve_with_worker_error(
        wiki,
        rag_worker.WorkerRequestAbandoned("abandoned"),
        "液冷 放弃",
    )

    cli.assert_not_called()
    assert result.telemetry.status == "timeout"
    assert result.telemetry.fallback_reason != "persistent_worker_unavailable"
    assert "worker 保留" in (result.warning or "")


def test_killed_worker_timeout_returns_timeout_without_reloading_the_model(
    tmp_path: Path,
) -> None:
    """冷 worker / 连续第二次超时：进程已被杀，残窗里重载模型必然再超时。"""

    wiki = _worker_query_fixture(tmp_path)
    result, cli = _retrieve_with_worker_error(
        wiki,
        TimeoutError("rag worker query timeout"),
        "液冷 已终止",
    )

    cli.assert_not_called()
    assert result.telemetry.status == "timeout"
    assert result.telemetry.fallback_reason != "persistent_worker_unavailable"
    assert "进程已终止" in (result.warning or "")


def test_genuinely_unavailable_worker_still_falls_back_to_cli(
    tmp_path: Path,
) -> None:
    """阳性对照：没有这条，上面两条「不回退」用「永不回退」也能全绿。

    进程没了/协议错乱不是超时——没有热进程可保，CLI 是唯一还能出结果的路，
    这条回退必须活着。
    """

    wiki = _worker_query_fixture(tmp_path)
    result, cli = _retrieve_with_worker_error(
        wiki,
        RuntimeError("rag worker exited without response"),
        "液冷 不可用",
    )

    cli.assert_called_once()
    assert result.telemetry.fallback_reason == "persistent_worker_unavailable"
    assert result.telemetry.degraded is True


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
    """同一 (model, mode) 换一个 RagStore 实例，必须命中同一缓存键。

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
        "idx-a",
    )
    key_b = module._hashable_cache_key(
        ("bge-m3", True, None),
        {"store": RagStore(), "index_freshness": "fresh"},
        "idx-a",
    )
    assert key_a == key_b


def test_cache_key_ignores_freshness_but_separates_indexes() -> None:
    """靶心：verdict 翻转不得换键，换索引必须换键。

    老键是 `(model, need_dense, reranker, index_freshness)`。KB 侧 cmd_query 每次
    请求现算 verdict 递进来，于是 `rag update` 跑完（stale→fresh）、下一次 ingest
    （fresh→stale）各 miss 一次，每次 miss 都再 new 一个 BGEM3FlagModel，而旧
    retriever 还在缓存里回收不掉。
    """

    module = _worker_module()
    args = ("bge-m3", True, None)

    fresh = module._hashable_cache_key(args, {"index_freshness": "fresh"}, "idx-a")
    stale = module._hashable_cache_key(args, {"index_freshness": "stale"}, "idx-a")
    other_index = module._hashable_cache_key(args, {"index_freshness": "fresh"}, "idx-b")
    other_config = module._hashable_cache_key(
        ("bge-m3", False, None), {"index_freshness": "fresh"}, "idx-a"
    )

    assert fresh == stale, "verdict 翻转不是换了一具检索器，不能换键"
    assert fresh != other_index, "换索引必须换键，否则会拿旧索引的向量配新 store 的判定"
    assert fresh != other_config, "检索配置仍要分键"


def test_cache_key_ignores_freshness_even_when_passed_positionally() -> None:
    """freshness 按位置传也必须被排除——只认关键字的话，KB 改成位置传参就会静默复发。"""

    module = _worker_module()

    def _load_retriever(model, need_dense, reranker_name=None, store=None, index_freshness=None):
        return object()

    fresh = module._loader_call(_load_retriever, ("bge-m3", True, None, "STORE", "fresh"), {})
    stale = module._loader_call(_load_retriever, ("bge-m3", True, None, "STORE", "stale"), {})
    assert fresh["index_freshness"] == "fresh"
    assert fresh["store"] == "STORE"

    # 生产路径是「先绑签名，再拿绑定 dict 当 kwargs 建键」。直接把位置参数
    # 丢给 `_hashable_cache_key` 会让 freshness 这种可哈希 str 溜进键里——
    # 函数本身扫 args 时看不到形参名，排除只能发生在绑定之后。
    key_fresh = module._hashable_cache_key((), fresh, "idx-a")
    key_stale = module._hashable_cache_key((), stale, "idx-a")
    assert key_fresh == key_stale, "位置传参的 freshness 溜回了缓存键"
    assert ("index_freshness", "fresh") not in key_fresh
    assert ("store", "STORE") not in key_fresh
    assert stale["index_freshness"] == "stale"


def test_restamp_freshness_updates_hot_retriever_and_state() -> None:
    """复用热 retriever 时，当次 verdict 必须盖回去，否则又冻住了。"""

    module = _worker_module()

    class _R:
        index_freshness = "stale"

    retriever = _R()
    state = {"freshness": "stale"}
    module._restamp_freshness(retriever, "fresh", state)
    assert retriever.index_freshness == "fresh"
    assert state["freshness"] == "fresh"

    module._restamp_freshness(retriever, None, state)
    assert retriever.index_freshness == "fresh", "拿不到 verdict 时不覆盖，不是写 unknown"


def test_evict_other_indexes_drops_old_entries_and_clears_state() -> None:
    """换索引：旧条目整套让位，state 清空而不是留下「旧索引 + 新判定」的错配态。"""

    module = _worker_module()
    cache = {("idx-a", "bge-m3"): "retriever-a", ("idx-b", "bge-m3"): "retriever-b"}
    state = {"retriever": "retriever-a", "chunks": {"c1": {}}, "revision": "idx-a", "store": "s"}

    module._evict_other_indexes(cache, "idx-b", state)

    assert list(cache) == [("idx-b", "bge-m3")]
    assert state["retriever"] is None and state["chunks"] == {} and state["store"] is None


def test_loader_call_fallback_keeps_positional_config_apart() -> None:
    """绑不上签名时不能只剩 kwargs：把位置上的 need_dense 丢掉，dense on/off 会撞成同一键。"""

    module = _worker_module()

    def _incompatible(model):
        return object()

    on = module._loader_call(_incompatible, ("bge-m3", True, None), {"index_freshness": "fresh"})
    off = module._loader_call(_incompatible, ("bge-m3", False, None), {"index_freshness": "fresh"})
    key_on = module._hashable_cache_key((), on, "idx-a")
    key_off = module._hashable_cache_key((), off, "idx-a")

    assert key_on != key_off, "回落路径把位置上的检索配置丢了"
    assert ("index_freshness", "fresh") not in key_on, "关键字上的 freshness 仍应被排除"


def test_shared_embedder_builds_one_model_per_name() -> None:
    """KB 侧 get_embedder 无缓存，构造一次就是一份 ~3.9G 权重。"""

    module = _worker_module()
    built: list[str] = []

    class _FakeRagIndex:
        @staticmethod
        def get_embedder(name=None):
            built.append(str(name))
            return object()

    fake = _FakeRagIndex()
    module._install_shared_embedder(fake)
    first = fake.get_embedder("bge-m3")
    second = fake.get_embedder("bge-m3")
    fake.get_embedder("hash")

    assert first is second
    assert built == ["bge-m3", "hash"]


def test_index_identity_is_meta_fingerprint() -> None:
    """同一份 meta（键序无关）同一身份；built_at 变了必须换身份。"""

    module = _worker_module()

    class _Store:
        def __init__(self, meta):
            self.meta = meta

    left = module._index_identity(_Store({"built_at": "t1", "n": 1}))
    right = module._index_identity(_Store({"n": 1, "built_at": "t1"}))
    other = module._index_identity(_Store({"built_at": "t2", "n": 1}))
    assert left and left == right
    assert left != other
    assert module._index_identity(object()) == ""


def test_store_cache_reuses_until_index_dir_changes(tmp_path: Path) -> None:
    """同一份索引复用 store；索引重建（meta 变）后自动换新，不需要重启 worker。"""

    module = _worker_module()
    index = tmp_path / ".rag_index"
    index.mkdir()
    (index / "meta.json").write_text('{"built_at": "2026-08-31T11:01:16Z"}', encoding="utf-8")
    loads: list[str] = []

    class _RagStore:
        @staticmethod
        def load(in_dir=None):
            loads.append(str(in_dir))
            return object()

    fake = mock.Mock()
    fake.rag_store.RagStore = _RagStore
    fake.config.index_dir.return_value = str(index)

    cache = module._install_store_cache(fake)
    first = _RagStore.load(index)
    second = _RagStore.load(index)
    assert first is second, "同一份索引每次请求重 load 是 2.26s / 1.6GB 峰值的白工"
    assert len(loads) == 1

    (index / "meta.json").write_text('{"built_at": "2026-09-03T10:56:51Z"}', encoding="utf-8")
    third = _RagStore.load(index)
    assert third is not first, "索引重建后必须换新，否则 rag update 永远不生效"
    assert len(loads) == 2

    cache.enabled = False
    _RagStore.load(index)
    _RagStore.load(index)
    assert len(loads) == 4, "非 query 命令必须旁路缓存，不能把可变中间态共享出去"


def _worker_module():
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts" / "rag_query_worker.py"
    spec = importlib.util.spec_from_file_location("rag_query_worker_freshness", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeStore:
    """替身只复刻被测那条分支的形状：page_freshness 逐页给 verdict。"""

    def __init__(self, verdicts=None, raises=False):
        self.meta = {"built_at": "2026-08-31T11:01:16Z"}
        self._verdicts = verdicts
        self._raises = raises
        self.calls = []

    def page_freshness(self, vault, paths):
        if self._raises:
            raise RuntimeError("boom")
        self.calls.append(list(paths))
        return {p: self._verdicts.get(p, "stale") for p in paths}


class _FakeModule:
    def __init__(self, vault="/kb/wiki"):
        self._vault_path = vault

    def _vault(self):
        return self._vault_path


def _rows():
    return [
        {"file_path": "wiki/entities/中国船舶.md", "best_chunk_id": "c1"},
        {"file_path": "wiki/concepts/军工.md", "best_chunk_id": "c2"},
    ]


def _state(store, chunks_ids=("c1", "c2"), freshness="stale"):
    return {
        "retriever": mock.Mock(store=store),
        "chunks": {cid: {"id": cid, "text": "证据正文", "section": "s"} for cid in chunks_ids},
        "revision": "rev123",
        "freshness": freshness,
        "store": store,
    }


def test_enrich_stamps_per_page_freshness_not_one_index_wide_verdict() -> None:
    """靶心：库里有别的页变了，没变的那页必须仍标 fresh。

    此前这里盖的是预热时算的整库 verdict，两条命中会一起变 stale，
    下游 require_fresh 逐条丢弃后 hits=0。
    """
    module = _worker_module()
    store = _FakeStore({"wiki/concepts/军工.md": "fresh"})
    rows = _rows()

    out = json.loads(module._enrich_query_output(json.dumps(rows), _state(store), _FakeModule()))

    by_path = {r["file_path"]: r["index_freshness"] for r in out}
    assert by_path["wiki/entities/中国船舶.md"] == "stale"
    assert by_path["wiki/concepts/军工.md"] == "fresh"


def test_enrich_recomputes_every_request_so_reindex_takes_effect() -> None:
    """重建索引后不重启 worker 也要生效——按页 verdict 必须每次请求现算。"""
    module = _worker_module()
    store = _FakeStore({})
    state = _state(store)

    module._enrich_query_output(json.dumps(_rows()), state, _FakeModule())
    store._verdicts = {"wiki/entities/中国船舶.md": "fresh", "wiki/concepts/军工.md": "fresh"}
    out = json.loads(module._enrich_query_output(json.dumps(_rows()), state, _FakeModule()))

    assert {r["index_freshness"] for r in out} == {"fresh"}
    assert len(store.calls) == 2, "每次请求都要重算，不能缓存整库 verdict"


def test_enrich_falls_back_to_index_wide_verdict_when_kb_lacks_page_freshness() -> None:
    """跨仓版本错配：KB 检出还没有 page_freshness 时回落旧行为，不能抛异常。"""
    module = _worker_module()

    class _OldStore:
        meta = {"built_at": "2026-08-31T11:01:16Z"}

    state = _state(_OldStore(), freshness="stale")
    out = json.loads(module._enrich_query_output(json.dumps(_rows()), state, _FakeModule()))
    assert {r["index_freshness"] for r in out} == {"stale"}


def test_enrich_falls_back_when_page_freshness_raises() -> None:
    module = _worker_module()
    state = _state(_FakeStore(raises=True), freshness="unknown")
    out = json.loads(module._enrich_query_output(json.dumps(_rows()), state, _FakeModule()))
    assert {r["index_freshness"] for r in out} == {"unknown"}


class _LazyChunks:
    """像 KB 懒读表：按行取、可 len，整表遍历要记账（worker 一次都不该做）。"""

    def __init__(self, rows):
        self._rows = rows
        self.iter_calls = 0

    def __len__(self):
        return len(self._rows)

    def __getitem__(self, row):
        return self._rows[row]

    def __iter__(self):
        self.iter_calls += 1
        return iter(self._rows)


def _lazy_retriever(store):
    rows = [
        {"id": "c1", "text": "懒读正文一", "section": "s1", "content_hash": "h1"},
        {"id": "c2", "text": "懒读正文二", "section": "s2", "content_hash": "h2"},
    ]
    table = _LazyChunks(rows)
    retriever = mock.Mock(store=store)
    retriever.row_by_chunk_id = {"c1": 0, "c2": 1}
    retriever.chunks = table
    return retriever, table


def test_enrich_resolves_rows_from_retriever_without_state_copy() -> None:
    """靶心：state["chunks"] 为空时按 retriever.row_by_chunk_id 现取那一行，且不遍历整表。

    KB 侧 store.chunks 已是懒读表（knowledge-base-private #143）；此前 worker 在加载时把
    它整份复制成 id→dict，等于把 169k 行全解析出来攥着（1.4 GB），KB 那一刀白做。
    """
    module = _worker_module()
    store = _FakeStore({"wiki/concepts/军工.md": "fresh"})
    retriever, table = _lazy_retriever(store)
    state = {"retriever": retriever, "chunks": {}, "revision": "rev9", "freshness": "stale", "store": store}

    out = json.loads(module._enrich_query_output(json.dumps(_rows()), state, _FakeModule()))

    by_id = {r["best_chunk_id"]: r for r in out}
    assert by_id["c1"]["llm_evidence_text"] == "懒读正文一"
    assert by_id["c2"]["section"] == "s2" and by_id["c2"]["content_hash"] == "h2"
    assert by_id["c1"]["evidence_chunk_ids"] == ["c1"]
    assert by_id["c2"]["index_freshness"] == "fresh" and by_id["c1"]["index_freshness"] == "stale"
    assert table.iter_calls == 0, "enrich 只能按行取，不得遍历整表"
    assert state["chunks"] == {}, "不得把表复制回 state"


def test_enrich_state_chunks_take_precedence_over_retriever_table() -> None:
    module = _worker_module()
    store = _FakeStore({})
    retriever, _ = _lazy_retriever(store)
    state = _state(store)  # 预填的 c1/c2 正文是「证据正文」
    state["retriever"] = retriever

    out = json.loads(module._enrich_query_output(json.dumps(_rows()), state, _FakeModule()))
    assert {r["llm_evidence_text"] for r in out} == {"证据正文"}


def test_enrich_stamps_index_fields_even_when_chunk_unresolvable() -> None:
    """id 不在索引里 / retriever 没有表：索引级字段照盖，块级字段不碰。"""
    module = _worker_module()
    store = _FakeStore({"wiki/concepts/军工.md": "fresh"})
    state = _state(store, chunks_ids=())          # 没有预填，mock retriever 也没有真表
    out = json.loads(module._enrich_query_output(json.dumps(_rows()), state, _FakeModule()))
    by_path = {r["file_path"]: r for r in out}
    assert by_path["wiki/concepts/军工.md"]["index_freshness"] == "fresh"
    assert by_path["wiki/entities/中国船舶.md"]["index_built_at"] == "2026-08-31T11:01:16Z"
    assert all("llm_evidence_text" not in r for r in out)


def test_chunk_by_id_fails_closed_on_garbage() -> None:
    module = _worker_module()
    retriever, table = _lazy_retriever(_FakeStore({}))
    assert module._chunk_by_id({"chunks": {}}, retriever, "c2")["id"] == "c2"
    assert module._chunk_by_id({"chunks": {}}, retriever, "") is None
    assert module._chunk_by_id({"chunks": {}}, retriever, "nope") is None
    assert module._chunk_by_id({"chunks": {}}, mock.Mock(), "c1") is None, "Mock 出来的 row 不是 int"
    retriever.row_by_chunk_id = {"c1": True}
    assert module._chunk_by_id({"chunks": {}}, retriever, "c1") is None, "bool 不算行号"
    retriever.row_by_chunk_id = {"c1": 99}
    assert module._chunk_by_id({"chunks": {}}, retriever, "c1") is None, "越界 fail closed"
    assert table.iter_calls == 0


def test_worker_does_not_materialize_store_chunks(tmp_path: Path) -> None:
    """e2e：worker 加载 retriever 时不得遍历 store.chunks；enrich 仍能按 id 取到正文。"""
    _write_flipable_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    (index / "meta.json").write_text('{"built_at": "2026-08-31T11:01:16Z"}', encoding="utf-8")
    (index / "verdict.txt").write_text("fresh", encoding="utf-8")
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        first = worker.query(["query", "first", "--json"], timeout=2)
        second = worker.query(["query", "second", "--json"], timeout=2)
    finally:
        worker.close()
    assert first.returncode == 0, first.stderr
    row = json.loads(second.stdout)[0]
    assert row["chunks_iterated"] == 0, "worker 把 store.chunks 整份遍历/复制了"
    assert row["llm_evidence_text"] == "证据正文" and row["content_hash"] == "h1"
    assert row["index_built_at"] == "2026-08-31T11:01:16Z"


def test_prewarm_prefers_kb_single_source_over_stale_report() -> None:
    """整库兜底 verdict 要走 KB 的 freshness_report，不走已被收敛掉的 stale_report。

    stale_report 是第二套并行判据：重切整库、且不判 chunk_profile 与索引年龄。
    """
    module = _worker_module()
    calls = {"freshness_report": 0, "stale_report": 0}

    class _Store:
        meta = {"include_raw": False}
        chunks = []

        def freshness_report(self, vault):
            calls["freshness_report"] += 1
            return ("fresh", [])

    class _RagStore:
        @staticmethod
        def stale_report(vault, store, include_raw=False):
            calls["stale_report"] += 1
            return {"stale": 1}

    fake_module = _FakeModule()
    fake_module.rag_store = _RagStore()

    assert module._index_wide_freshness(_Store(), fake_module) == "fresh"
    assert calls["freshness_report"] == 1
    assert calls["stale_report"] == 0


def test_prewarm_falls_back_to_stale_report_on_old_kb_checkout() -> None:
    module = _worker_module()

    class _OldStore:
        meta = {"include_raw": False}

    class _RagStore:
        @staticmethod
        def stale_report(vault, store, include_raw=False):
            return {"stale": 3}

    fake_module = _FakeModule()
    fake_module.rag_store = _RagStore()
    assert module._index_wide_freshness(_OldStore(), fake_module) == "stale"


def test_prewarm_freshness_is_unknown_when_resolution_raises() -> None:
    module = _worker_module()

    class _Boom:
        meta = {"include_raw": False}

        def freshness_report(self, vault):
            raise RuntimeError("boom")

    assert module._index_wide_freshness(_Boom(), _FakeModule()) == "unknown"

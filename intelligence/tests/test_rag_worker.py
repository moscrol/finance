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

def _load_retriever(model, need_dense, reranker_name=None):
    return object()

def main(argv=None):
    argv = list(argv or [])
    query = argv[1]
    _load_retriever("hash", True, None)
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
    _write_fake_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        with pytest.raises(TimeoutError):
            worker.query(["query", "slow", "--json"], timeout=0.02)
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

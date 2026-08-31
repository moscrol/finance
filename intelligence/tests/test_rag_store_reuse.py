"""worker 热路径复用 RagStore：命中不再全库 load；索引 mtime 变了必须重载。

freshness_report 每次仍跑——不为了快跳过新鲜度。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

from intelligence.services.rag_worker import PersistentRagWorker

_WORKER = Path(__file__).resolve().parents[2] / "scripts" / "rag_query_worker.py"


def _worker_module():
    spec = importlib.util.spec_from_file_location("rag_query_worker_reuse", _WORKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _touch_index(index: Path) -> None:
    (index / "dense.npy").write_bytes(b"n")
    (index / "meta.json").write_text("{}", encoding="utf-8")
    (index / "chunks.jsonl").write_text("{}\n", encoding="utf-8")


def test_reuse_cache_skips_loader_until_mtime_changes(tmp_path: Path) -> None:
    _touch_index(tmp_path)
    cache = _worker_module().IndexReuseCache(tmp_path)
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return object()

    first, reloaded = cache.get(loader)
    second, reused = cache.get(loader)
    assert reloaded is True
    assert reused is False
    assert first is second
    assert calls["n"] == 1

    time.sleep(0.02)
    (tmp_path / "meta.json").write_text('{"built_at":"changed"}', encoding="utf-8")
    third, reloaded_again = cache.get(loader)
    assert reloaded_again is True
    assert third is not first
    assert calls["n"] == 2


def test_reuse_cache_chunk_mtime_also_invalidates(tmp_path: Path) -> None:
    _touch_index(tmp_path)
    cache = _worker_module().IndexReuseCache(tmp_path)
    calls = {"n": 0}
    cache.get(lambda: calls.update(n=calls["n"] + 1) or object())
    time.sleep(0.02)
    (tmp_path / "chunks.jsonl").write_text('{"id":"x"}\n', encoding="utf-8")
    _, reloaded = cache.get(lambda: calls.update(n=calls["n"] + 1) or object())
    assert reloaded is True
    assert calls["n"] == 2


def _write_counting_rag(root: Path) -> None:
    script = root / "scripts" / "rag_index.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        """
import json

class rag_store:
    class RagStore:
        load_count = 0
        fresh_count = 0

        def __init__(self):
            self.meta = {"built_at": "2026-08-31T00:00:00Z", "include_raw": False}
            self.chunks = [{"id": "c1", "text": "t"}]

        @classmethod
        def load(cls, in_dir=None):
            cls.load_count += 1
            return cls()

        def freshness_report(self, vault, *, max_age_days=None):
            type(self).fresh_count += 1
            return "fresh", []

    @staticmethod
    def stale_report(vault, store, include_raw=False):
        return {"stale": False}

class Retriever:
    def __init__(self, store, embedder=None, reranker=None, source_root=None,
                 index_freshness=None):
        self.store = store

def _vault():
    return None

def _load_retriever(model, need_dense, reranker_name=None, store=None,
                    index_freshness=None):
    return Retriever(store)

def main(argv=None):
    argv = list(argv or [])
    store = rag_store.RagStore.load()
    freshness, _ = store.freshness_report(_vault())
    _load_retriever("hash", True, None, store=store, index_freshness=freshness)
    print(json.dumps([{
        "query": argv[1],
        "load_count": rag_store.RagStore.load_count,
        "fresh_count": rag_store.RagStore.fresh_count,
        "index_freshness": freshness,
    }], ensure_ascii=False))
    return 0
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _payload_row(stdout: str) -> dict:
    rows = json.loads(stdout)
    assert isinstance(rows, list) and rows
    return rows[0]


def test_worker_reuses_store_but_still_judges_freshness(tmp_path: Path) -> None:
    _write_counting_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    _touch_index(index)
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        first = worker.query(["query", "one", "--json"], timeout=3)
        second = worker.query(["query", "two", "--json"], timeout=3)
    finally:
        worker.close()

    assert first.returncode == 0
    assert second.returncode == 0
    row1 = _payload_row(first.stdout)
    row2 = _payload_row(second.stdout)
    assert row1["load_count"] == 1
    assert row2["load_count"] == 1
    assert row1["fresh_count"] == 1
    assert row2["fresh_count"] == 2


def test_worker_reloads_store_when_index_mtime_changes(tmp_path: Path) -> None:
    _write_counting_rag(tmp_path)
    index = tmp_path / ".rag_index"
    index.mkdir()
    _touch_index(index)
    worker = PersistentRagWorker(sys.executable, tmp_path, index)
    try:
        first = worker.query(["query", "one", "--json"], timeout=3)
        time.sleep(0.02)
        (index / "meta.json").write_text('{"built_at":"stale-test"}', encoding="utf-8")
        second = worker.query(["query", "two", "--json"], timeout=3)
    finally:
        worker.close()

    assert first.returncode == 0
    assert second.returncode == 0
    assert _payload_row(first.stdout)["load_count"] == 1
    assert _payload_row(second.stdout)["load_count"] == 2
    assert _payload_row(second.stdout)["fresh_count"] == 2


def test_enrich_keeps_cli_stale_over_cached_fresh_state() -> None:
    module = _worker_module()

    class _Store:
        meta = {"built_at": "2026-08-31T00:00:00Z"}

    class _Retriever:
        store = _Store()

    state = {
        "chunks": {"c1": {"id": "c1", "text": "body", "section": "", "content_hash": "h"}},
        "retriever": _Retriever(),
        "revision": "deadbeef",
        "freshness": "fresh",
    }
    raw = json.dumps(
        [
            {
                "best_chunk_id": "c1",
                "snippet": "snip",
                "index_freshness": "stale",
            }
        ],
        ensure_ascii=False,
    )
    rows = json.loads(module._enrich_query_output(raw, state))
    assert rows[0]["index_freshness"] == "stale"
    assert rows[0]["llm_evidence_text"] == "body"

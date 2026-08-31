#!/usr/bin/env python3
"""JSON-lines worker that keeps the KB Retriever/BGE model warm."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
import hashlib
import time
from pathlib import Path

INDEX_SIGNATURE_FILES = ("dense.npy", "meta.json", "chunks.jsonl")


class IndexReuseCache:
    """按索引落盘 mtime 复用已 load 的 store；文件变了必须重载。

    不缓存 freshness verdict：query 热路径仍每次 ``freshness_report``。
    """

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = Path(index_dir)
        self.store: object | None = None
        self.signature: tuple[object, ...] | None = None

    def signature_now(self, index_dir: Path | None = None) -> tuple[object, ...]:
        target = Path(index_dir) if index_dir is not None else self.index_dir
        stamps: list[object] = [str(target.resolve())]
        for name in INDEX_SIGNATURE_FILES:
            path = target / name
            try:
                stamps.append(path.stat().st_mtime_ns)
            except OSError:
                stamps.append(-1)
        return tuple(stamps)

    def get(self, loader, index_dir: Path | None = None):
        signature = self.signature_now(index_dir)
        if self.store is not None and self.signature == signature:
            return self.store, False
        self.store = loader()
        self.signature = signature
        return self.store, True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--index-dir", required=True)
    args = parser.parse_args()
    root = Path(args.kb_root).resolve()
    script_dir = root / "scripts"
    for import_root in (root, script_dir):
        resolved = str(import_root)
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
    os.chdir(root)
    os.environ["RAG_INDEX_DIR"] = str(Path(args.index_dir).resolve())
    module = _load_module(script_dir / "rag_index.py")
    original_loader = module._load_retriever
    load_count = 0
    state = {"retriever": None, "chunks": {}, "revision": "", "freshness": "unknown"}
    loader_cache: dict[tuple, object] = {}

    def cached_loader(*loader_args, **loader_kwargs):
        nonlocal load_count
        # 不能用 functools.lru_cache：KB 侧 `_load_retriever` 后来加了
        # `store: RagStore`，每次 query 都传入新实例。lru_cache 要求参数可哈希，
        # 生产预热会变成 `TypeError: unhashable type: 'RagStore'`，
        # model_load_count 停在 0，Workbench 整段 RAG 判 not_ready。
        # 缓存键只取可哈希参数（model / mode / reranker / freshness）；
        # 跳过 store 正是本 worker 的语义——同一组检索配置共用一具热模型。
        key = _hashable_cache_key(loader_args, loader_kwargs)
        cached = loader_cache.get(key)
        if cached is not None:
            return cached
        load_count += 1
        retriever = original_loader(*loader_args, **loader_kwargs)
        state["retriever"] = retriever
        store = getattr(retriever, "store", None)
        if store is None:
            state["retriever"] = None
            loader_cache[key] = retriever
            return retriever
        state["chunks"] = {
            str(chunk.get("id") or ""): chunk
            for chunk in store.chunks
            if isinstance(chunk, dict) and chunk.get("id")
        }
        revision_payload = json.dumps(
            store.meta,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        state["revision"] = hashlib.sha256(revision_payload).hexdigest()[:16]
        try:
            report = module.rag_store.stale_report(
                module._vault(),
                store,
                include_raw=bool(store.meta.get("include_raw")),
            )
            state["freshness"] = "stale" if report.get("stale") else "fresh"
        except Exception:
            state["freshness"] = "unknown"
        loader_cache[key] = retriever
        return retriever

    module._load_retriever = cached_loader

    def on_store_reload() -> None:
        loader_cache.clear()
        state["retriever"] = None
        state["chunks"] = {}
        state["revision"] = ""
        state["freshness"] = "unknown"

    _install_store_reuse(module, Path(args.index_dir), on_store_reload)
    dump_phases = _install_phase_hooks(module)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            request_id = str(request["id"])
            argv = request["argv"]
            if not isinstance(argv, list) or any(not isinstance(x, str) for x in argv):
                raise ValueError("argv must be a list of strings")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    returncode = int(module.main(argv))
                except SystemExit as exc:
                    returncode = int(exc.code or 0)
            dump_phases()
            output = stdout.getvalue()
            if returncode == 0 and argv and argv[0] == "query":
                output = _enrich_query_output(output, state)
            response = {
                "id": request_id,
                "returncode": returncode,
                "stdout": output,
                "stderr": stderr.getvalue(),
                "model_load_count": load_count,
            }
        except Exception as exc:  # noqa: BLE001
            response = {
                "id": str(locals().get("request_id") or ""),
                "returncode": 1,
                "stdout": "",
                "stderr": f"{type(exc).__name__}: {exc}",
                "model_load_count": load_count,
            }
        print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def _install_store_reuse(module, index_dir: Path, on_reload) -> IndexReuseCache | None:
    """cmd_query 每次 RagStore.load 走同一具热 store；索引 mtime 变了才重载。"""

    rag_store = getattr(module, "rag_store", None)
    store_cls = getattr(rag_store, "RagStore", None) if rag_store is not None else None
    if store_cls is None or not hasattr(store_cls, "load"):
        return None
    cache = IndexReuseCache(index_dir)
    orig_load = store_cls.load

    def cached_load(*args, **kwargs):
        in_dir = kwargs.get("in_dir")
        if in_dir is None and args:
            in_dir = args[0]
        store, reloaded = cache.get(
            lambda: orig_load(*args, **kwargs),
            index_dir=Path(in_dir) if in_dir is not None else None,
        )
        if reloaded:
            on_reload()
        return store

    store_cls.load = cached_load
    return cache


def _install_phase_hooks(module):
    """可选五段计时：仅当 ``RAG_PROFILE_PATH`` 有值时挂钩，写完即清。

    默认不装、不写盘，避免影响生产 stderr / 单测假 CLI。分段对齐工单
    load / freshness / encode / search；合计由调用方用 ``kb_rag.retrieve`` 墙钟报。
    """

    path = os.environ.get("RAG_PROFILE_PATH", "").strip()
    if not path:
        return lambda: None
    rag_store = getattr(module, "rag_store", None)
    retriever_cls = getattr(module, "Retriever", None)
    if rag_store is None or retriever_cls is None:
        return lambda: None
    phases: dict[str, float] = {}
    orig_load = rag_store.RagStore.load
    orig_fresh = rag_store.RagStore.freshness_report
    orig_encode = retriever_cls.encode_query
    orig_search = retriever_cls.search

    def timed_load(*args, **kwargs):
        started = time.perf_counter()
        store = orig_load(*args, **kwargs)
        phases["load"] = time.perf_counter() - started
        return store

    def timed_fresh(self, *fresh_args, **fresh_kwargs):
        started = time.perf_counter()
        report = orig_fresh(self, *fresh_args, **fresh_kwargs)
        phases["freshness"] = time.perf_counter() - started
        return report

    def timed_encode(self, query):
        started = time.perf_counter()
        vector = orig_encode(self, query)
        phases["encode"] = phases.get("encode", 0.0) + (time.perf_counter() - started)
        return vector

    def timed_search(self, query, k=6, mode="hybrid", qvec=None):
        encode_before = phases.get("encode", 0.0)
        started = time.perf_counter()
        hits = orig_search(self, query, k=k, mode=mode, qvec=qvec)
        wall = time.perf_counter() - started
        encode_delta = phases.get("encode", 0.0) - encode_before
        phases["search"] = wall - encode_delta
        return hits

    rag_store.RagStore.load = timed_load
    rag_store.RagStore.freshness_report = timed_fresh
    retriever_cls.encode_query = timed_encode
    retriever_cls.search = timed_search

    def dump() -> None:
        payload = {
            "load": round(phases.get("load", 0.0), 4),
            "freshness": round(phases.get("freshness", 0.0), 4),
            "encode": round(phases.get("encode", 0.0), 4),
            "search": round(phases.get("search", 0.0), 4),
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        phases.clear()

    return dump


def _enrich_query_output(output: str, state: dict[str, object]) -> str:
    rows = json.loads(output or "[]")
    if not isinstance(rows, list):
        return output
    chunks = state.get("chunks")
    retriever = state.get("retriever")
    if not isinstance(chunks, dict) or retriever is None:
        return output
    built_at = str(getattr(retriever, "store").meta.get("built_at") or "")
    for row in rows:
        if not isinstance(row, dict):
            continue
        chunk = chunks.get(str(row.get("best_chunk_id") or ""))
        if not isinstance(chunk, dict):
            continue
        text = str(chunk.get("text") or row.get("snippet") or "")
        # CLI 的 freshness_report 是本轮事实源。预热时 stale_report 写进
        # state["freshness"] 不能盖掉本轮 stale——否则 require_fresh 会把过期命中当正式证据。
        cli_freshness = str(row.get("index_freshness") or "").strip()
        row.update(
            {
                "section": str(chunk.get("section") or ""),
                "content_hash": str(chunk.get("content_hash") or ""),
                "display_excerpt": str(row.get("snippet") or text),
                "llm_evidence_text": text,
                "evidence_chunk_ids": [str(chunk.get("id") or "")],
                "index_built_at": built_at,
                "index_source_revision": str(state.get("revision") or ""),
                "index_freshness": cli_freshness or str(state.get("freshness") or "unknown"),
            }
        )
    return json.dumps(rows, ensure_ascii=False)


def _hashable_cache_key(args: tuple, kwargs: dict) -> tuple:
    """Build a cache key that silently drops unhashable values such as RagStore."""

    frozen: list[object] = []
    for value in args:
        try:
            hash(value)
        except TypeError:
            continue
        frozen.append(value)
    for key, value in sorted(kwargs.items()):
        try:
            hash(value)
        except TypeError:
            continue
        frozen.append((key, value))
    return tuple(frozen)


def _load_module(path: Path):
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location("persistent_kb_rag_index", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load rag_index module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())

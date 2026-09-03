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
from pathlib import Path


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
    state = {
        "retriever": None,
        "chunks": {},
        "revision": "",
        "freshness": "unknown",
        "store": None,
    }
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
        state["store"] = store
        state["freshness"] = _index_wide_freshness(store, module)
        loader_cache[key] = retriever
        return retriever

    module._load_retriever = cached_loader
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
            output = stdout.getvalue()
            if returncode == 0 and argv and argv[0] == "query":
                output = _enrich_query_output(output, state, module)
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


def _enrich_query_output(output: str, state: dict[str, object], module=None) -> str:
    rows = json.loads(output or "[]")
    if not isinstance(rows, list):
        return output
    chunks = state.get("chunks")
    retriever = state.get("retriever")
    if not isinstance(chunks, dict) or retriever is None:
        return output
    built_at = str(getattr(retriever, "store").meta.get("built_at") or "")
    page_verdicts = _page_verdicts(rows, state, module)
    for row in rows:
        if not isinstance(row, dict):
            continue
        chunk = chunks.get(str(row.get("best_chunk_id") or ""))
        if not isinstance(chunk, dict):
            continue
        text = str(chunk.get("text") or row.get("snippet") or "")
        row.update(
            {
                "section": str(chunk.get("section") or ""),
                "content_hash": str(chunk.get("content_hash") or ""),
                "display_excerpt": str(row.get("snippet") or text),
                "llm_evidence_text": text,
                "evidence_chunk_ids": [str(chunk.get("id") or "")],
                "index_built_at": built_at,
                "index_source_revision": str(state.get("revision") or ""),
                "index_freshness": page_verdicts.get(
                    str(row.get("file_path") or ""),
                    str(state.get("freshness") or "unknown"),
                ),
            }
        )
    return json.dumps(rows, ensure_ascii=False)


def _index_wide_freshness(store, module) -> str:
    """预热时算一次的**整库兜底** verdict（仅在按页判不可用时才会被盖上去）。

    优先走 KB 侧单一事实源 `freshness_report`（manifest 指纹 + 切块参数门 + 年龄门），
    而不是 `stale_report`。后者是 KB 早已收敛掉的第二套并行判据：它重切整库 14k 文件，
    且**不判** chunk_profile 与索引年龄，可能与 KB 自己的口径相反——两套判据并存正是
    KB `freshness_report` 文档里点名要消灭的事。
    """
    try:
        report_fn = getattr(store, "freshness_report", None)
        if report_fn is not None:
            return str(report_fn(module._vault())[0])
        report = module.rag_store.stale_report(
            module._vault(),
            store,
            include_raw=bool(store.meta.get("include_raw")),
        )
        return "stale" if report.get("stale") else "fresh"
    except Exception:
        return "unknown"


def _page_verdicts(
    rows: list, state: dict[str, object], module
) -> dict[str, str]:
    """每条命中按页判新鲜度，**每次请求现算**。

    此前这里盖的是 `state["freshness"]`——一个在预热时算一次、之后再不更新的整库
    结论。两个后果：① 整库口径下「库里有别的页变了」会让逐字节没变的页也被下游
    `require_fresh` 丢掉（KB 侧 `page_freshness` 已收窄）；② 就算重建了索引，常驻
    worker 也还在盖旧 verdict，不重启 worker 永远不会变 fresh。所以「重建索引」这
    个补救动作对热路径是无效的。

    KB 检出版本较旧（没有 `page_freshness`）时返回空字典 → 调用方回落到原来的整库
    verdict，不改行为、不抛异常。跨仓版本错配不能把检索打死。
    """
    store = state.get("store")
    page_fn = getattr(store, "page_freshness", None)
    if page_fn is None or module is None:
        return {}
    paths = [
        str(row.get("file_path") or "")
        for row in rows
        if isinstance(row, dict) and row.get("file_path")
    ]
    if not paths:
        return {}
    try:
        return page_fn(module._vault(), paths)
    except Exception:
        return {}


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

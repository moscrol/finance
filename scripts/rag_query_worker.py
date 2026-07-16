#!/usr/bin/env python3
"""JSON-lines worker that keeps the KB Retriever/BGE model warm."""

from __future__ import annotations

import argparse
import contextlib
import functools
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
    state = {"retriever": None, "chunks": {}, "revision": "", "freshness": "unknown"}

    @functools.lru_cache(maxsize=8)
    def cached_loader(*loader_args):
        nonlocal load_count
        load_count += 1
        retriever = original_loader(*loader_args)
        state["retriever"] = retriever
        store = getattr(retriever, "store", None)
        if store is None:
            state["retriever"] = None
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
        row.update(
            {
                "section": str(chunk.get("section") or ""),
                "content_hash": str(chunk.get("content_hash") or ""),
                "display_excerpt": str(row.get("snippet") or text),
                "llm_evidence_text": text,
                "evidence_chunk_ids": [str(chunk.get("id") or "")],
                "index_built_at": built_at,
                "index_source_revision": str(state.get("revision") or ""),
                "index_freshness": str(state.get("freshness") or "unknown"),
            }
        )
    return json.dumps(rows, ensure_ascii=False)


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

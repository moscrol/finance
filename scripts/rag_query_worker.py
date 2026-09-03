#!/usr/bin/env python3
"""JSON-lines worker that keeps the KB Retriever/BGE model warm."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import inspect
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
    _install_shared_embedder(module)
    store_cache = _install_store_cache(module)
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
        call = _loader_call(original_loader, loader_args, loader_kwargs)
        store = call.get("store")
        identity = _index_identity(store)
        # 键必须来自绑过签名的 call，args 留空。位置传来的 index_freshness
        # 是可哈希的 str，直接扫 loader_args 会把它编进键里，verdict 翻转
        # 就又 miss——而这正是本次要堵的洞。
        key = _hashable_cache_key((), call, identity)
        freshness = call.get("index_freshness")

        cached = loader_cache.get(key)
        if cached is not None:
            # 命中也要把**当次**verdict 盖回去。freshness 已被踢出缓存键（见
            # `_hashable_cache_key`），若不在这里回盖，`Retriever.index_freshness`
            # 就会永久停在建这具 retriever 那一刻的值——正是「重建索引不重启 worker
            # 不生效」的老毛病换个地方复发。
            _restamp_freshness(cached, freshness, state)
            return cached

        # 索引换代了：先把旧索引整套让位再加载新的。两份索引同时驻留 =
        # 3.9G 权重 + 1.6G chunks + 0.7G dense 再来一遍，16G 的机器扛不住。
        _evict_other_indexes(loader_cache, identity, state)

        load_count += 1
        retriever = original_loader(*loader_args, **loader_kwargs)
        loader_cache[key] = retriever
        # 只信 retriever 自己挂的 store。cmd_query 传入的那份可能只是不可哈希
        # 哨兵（测试夹具的 object() / 无 chunks 的 RagStore），拿它填 state
        # 会让 enrich 去读不存在的 .chunks / .meta，整段 query 变 returncode=1。
        attached = getattr(retriever, "store", None)
        if attached is None:
            state["retriever"] = None
            return retriever
        state["retriever"] = retriever
        state["chunks"] = {
            str(chunk.get("id") or ""): chunk
            for chunk in getattr(attached, "chunks", None) or []
            if isinstance(chunk, dict) and chunk.get("id")
        }
        state["revision"] = identity or _index_identity(attached)
        state["store"] = attached
        state["freshness"] = (
            str(freshness) if freshness else _index_wide_freshness(attached, module)
        )
        return retriever

    module._load_retriever = cached_loader
    for line in sys.stdin:
        try:
            request = json.loads(line)
            request_id = str(request["id"])
            argv = request["argv"]
            if not isinstance(argv, list) or any(not isinstance(x, str) for x in argv):
                raise ValueError("argv must be a list of strings")
            # 只有只读的 query 走共享 store。`update` / `build` 会把 store 当可变
            # 中间态改，递一份共享实例给它就等于让下一次检索读到半改的索引。
            store_cache.enabled = bool(argv) and argv[0] == "query"
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


#: 不参与缓存键的形参。``store`` 本来就不可哈希（每次 query 都是新实例）；
#: ``index_freshness`` 是**每次请求现算的 verdict**，把它放进键里等于让「索引新鲜度
#: 翻转」冒充「换了一具检索器」。
_KEY_EXCLUDED_PARAMS = ("store", "index_freshness")


def _hashable_cache_key(args: tuple, kwargs: dict, identity: str = "") -> tuple:
    """按**索引身份 + 检索配置**建键，不含 index_freshness。

    原来的键是 ``(model, need_dense, reranker, index_freshness)``。freshness 在里面
    是个正在冒烟的洞：KB 侧 `cmd_query` 每次请求都现算 verdict 递进来，所以整库
    verdict 一翻（`rag update` 跑完变 fresh、下一次 ingest 又变 stale）就 miss 一次，
    `get_embedder` 再 new 一个 `BGEM3FlagModel`（KB 侧它**没有任何缓存**），而旧
    retriever 还躺在缓存里永不回收 → 一次翻转多背 3.9G 权重 + 一整份索引。
    还有个更隐蔽的正确性洞：翻回 stale 时命中的是**最早**那具 retriever（旧索引），
    而 `state["store"]` 已指向最新 store——按页 verdict 对着一个 store 算、向量却从
    另一个 store 出。

    改成用 ``identity``（索引 meta 的指纹）当键的第一段：换索引才换条目，verdict
    翻转不再制造新条目；`_evict_other_indexes` 再保证新索引进来时旧的整套让位。
    """

    frozen: list[object] = [identity]
    for value in args:
        try:
            hash(value)
        except TypeError:
            continue
        frozen.append(value)
    for key, value in sorted(kwargs.items()):
        if key in _KEY_EXCLUDED_PARAMS:
            continue
        try:
            hash(value)
        except TypeError:
            continue
        frozen.append((key, value))
    return tuple(frozen)


def _loader_call(loader, args: tuple, kwargs: dict) -> dict:
    """把 ``_load_retriever`` 的实参归一成 ``{形参名: 值}``。

    为什么要绑签名而不是直接 ``kwargs.get("store")``：``store`` / ``index_freshness``
    **也可以按位置传**。只认关键字的话，哪天 KB 侧改成位置传参，freshness 就会从
    `_KEY_EXCLUDED_PARAMS` 底下溜回缓存键里——而这正是本次要修的那个 bug。绑签名让
    它在结构上不可能发生。绑不上（签名变了/参数对不上）时按位置序号保留实参再并上
    关键字：宁可让 freshness 溜进键多缓存一份，也不能把位置上的 model / need_dense
    丢掉让不同检索配置撞成同一个键，更不要在这里抛异常打死检索。
    """

    try:
        bound = inspect.signature(loader).bind(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except (TypeError, ValueError):
        call = {f"arg{i}": value for i, value in enumerate(args)}
        call.update(kwargs)
        return call


def _index_identity(store) -> str:
    """索引身份 = ``store.meta`` 的指纹（built_at / source_revision / num_chunks 都在里面）。

    与 `state["revision"]` 同一个算法，两处不会漂。
    """

    meta = getattr(store, "meta", None)
    if not isinstance(meta, dict):
        return ""
    payload = json.dumps(meta, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _restamp_freshness(retriever, freshness, state: dict) -> None:
    """把当次 verdict 盖到复用的 retriever 与 worker state 上。

    `Retriever.index_freshness` 是个普通属性，检索时才读（KB 侧 retrieval.py 两处
    出参都取它），所以直接改属性就能让热 retriever 报当次结论，不必重建。
    """

    if not freshness:
        return
    verdict = str(freshness)
    with contextlib.suppress(AttributeError):
        retriever.index_freshness = verdict
    state["freshness"] = verdict


def _evict_other_indexes(loader_cache: dict, identity: str, state: dict) -> None:
    """索引换代时清掉所有属于旧索引的条目，并把 state 一起清空。

    先清后建：新旧两份索引同时驻留才是内存事故的形状，让位要发生在新的加载之前。
    加载失败时 state 停在「空」而不是「旧索引 + 新 verdict」的错配态，
    `_enrich_query_output` 见 retriever 为 None 会原样返回，不会拿错索引的 chunk 去贴证据。

    `_StoreCache` **不在这里清**。它是单槽、按盘上 meta.json 签名自失效的：走到这里时
    `cmd_query` 已经调过 `RagStore.load`，槽里躺的就是眼下这份新 store（identity 正是
    从它算出来的）。在这里再清一次，下一次 query 只能从盘上再读一份，而那一份与热
    retriever 手里的不是同一个对象——同一索引两份长期同驻，和这次要堵的洞是一个形状。
    """

    if not identity:
        return
    doomed = [key for key in loader_cache if key[0] != identity]
    if not doomed:
        return
    for key in doomed:
        loader_cache.pop(key, None)
    state.update({"retriever": None, "chunks": {}, "revision": "", "store": None})


def _install_shared_embedder(module) -> None:
    """按模型名共享 embedder。

    KB 侧 `get_embedder` 每次调用都 `BGEM3Embedder()`，构造函数里直接
    `BGEM3FlagModel(...)`——**没有任何缓存**，调一次就是一份 ~3.9G 权重。热路径上
    只要发生一次 `_load_retriever` 未命中，就白背一份。这里按名字记忆化，让「同一个
    模型只有一具」成为进程级不变量，而不是依赖上层缓存恰好没 miss。
    """

    original = getattr(module, "get_embedder", None)
    if original is None:
        return
    cache: dict[str, object] = {}

    def shared_embedder(name=None):
        key = str(name or "")
        hit = cache.get(key)
        if hit is None:
            hit = original(name)
            cache[key] = hit
        return hit

    module.get_embedder = shared_embedder


class _StoreCache:
    """`RagStore.load` 的进程内缓存，按索引目录内容签名失效。

    KB 侧 `cmd_query` **每次请求**都 `RagStore.load(index_dir)`：读 208MB chunks.jsonl
    + 346MB dense.npy 再转 float32。生产实测 2.26s / 1.6GB 峰值，每问一次重来一遍，
    而返回的东西和热 retriever 里那份逐字节相同。

    失效判据取索引目录 meta.json 的内容签名（built_at / source_revision / num_chunks
    都在里面），所以 `rag update` 跑完**不用重启 worker** 也会自动换新——这正是
    kb_rag.py 那句补救文案要能自证的前提。签名算不出来（目录不存在/meta 缺失）就
    整条旁路掉，让原实现照旧抛它该抛的错。
    """

    def __init__(self) -> None:
        self.enabled = True
        self._signature = ""
        self._store = None

    def get(self, signature: str):
        if not self.enabled or not signature or signature != self._signature:
            return None
        return self._store

    def put(self, signature: str, store) -> None:
        if not self.enabled or not signature:
            return
        # 只留当前那一份：换索引即让位，不做多代驻留。
        self._signature = signature
        self._store = store


def _install_store_cache(module) -> _StoreCache:
    rag_store = getattr(module, "rag_store", None)
    store_cls = getattr(rag_store, "RagStore", None)
    cache = _StoreCache()
    if store_cls is None:
        return cache
    original_load = store_cls.load

    def cached_load(in_dir=None):
        target = Path(in_dir) if in_dir is not None else Path(module.config.index_dir())
        signature = _index_dir_signature(target)
        hit = cache.get(signature)
        if hit is not None:
            return hit
        store = original_load(target)
        cache.put(signature, store)
        return store

    store_cls.load = staticmethod(cached_load)
    return cache


def _index_dir_signature(index_dir: Path) -> str:
    """索引目录的廉价内容签名：路径 + meta.json 原文哈希。

    只读 800 字节，不碰 chunks/dense。meta.json 里 `built_at` 每次 save 都变，
    所以任何一次重建都必然换签名。读不到就返回空串 = 不缓存。
    """

    try:
        raw = (Path(index_dir) / "meta.json").read_bytes()
    except OSError:
        return ""
    payload = str(Path(index_dir)).encode("utf-8") + b"\0" + raw
    return hashlib.sha256(payload).hexdigest()[:16]


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

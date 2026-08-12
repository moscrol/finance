# 在途交接 · cursor/rag-worker-unhashable-store-d7ac

更新：2026-08-13 · 8792 切到 #301 后 RAG 预热 4.5s 失败

## 这个分支做什么

修 `rag_query_worker`：KB `_load_retriever` 传入不可哈希 `RagStore`，`lru_cache` 炸了。

## 当前状态

- 生产探针：`TypeError: unhashable type: 'RagStore'`，`model_load_count=0`。
- 改动：缓存键丢掉不可哈希参数；假 RAG fixture 改为每次传新 RagStore。
- 未部署。8792 仍是 `09dacdea` 原文件。

## 下一步

1. 测 `intelligence/tests/test_rag_worker.py`。
2. 合入后 kickstart 8792，看 `workers.rag.state=ready`。
3. 回 A4 唯一前缀哈希。

## 未验证

- 生产预热（需部署后）。未关 8797/8794。

## 踩过的坑

- 旧 worker 活在内存里时 health 仍绿；一切换进程才暴露 KB API 变了。
- 缓存键若用 `id(store)`，每次 query 都 miss，BGE 会反复加载。

## 已验证

- 一发探针复现 TypeError。代码侧待测。

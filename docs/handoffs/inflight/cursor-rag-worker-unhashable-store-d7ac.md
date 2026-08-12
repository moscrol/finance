# 在途交接 · cursor/rag-worker-unhashable-store-d7ac

更新：2026-08-13 · 测试绿；8792 已热补丁，RAG ready

## 这个分支做什么

修 `rag_query_worker`：KB 传入不可哈希 `RagStore`，`lru_cache` 炸了。

## 当前状态

- 代码已提交 `702be3ca`，PR #302。测试 11 passed。
- 8792 runtime `09dacdea` **热补了一份** `scripts/rag_query_worker.py`（worktree dirty），kickstart 后 `workers.rag.state=ready`，`model_load_count=1`，预热 166s。
- 合入后应干净蓝绿切，去掉热补丁。

## 下一步

1. 用户确认后合 #302，新建 detached worktree 切 8792（不要 `reset --hard`）。
2. A4：15 位哈希唯一前缀 → FORMAT。

## 未验证

- 干净 SHA 部署（当前是热补丁）。A3 生产冒烟未跑。

## 踩过的坑

- 旧 worker 活在内存里时 health 仍绿；换进程才暴露 KB API 变了。
- 缓存键不能用 `id(store)`，否则每次 query miss、BGE 反复加载。
- 预热是同步的，kickstart 后 8792 会有 2–3 分钟不监听。

## 已验证

- 一发探针原脚本 TypeError；热补丁后生产 ready。

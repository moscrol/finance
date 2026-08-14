# RAG Worker Budget Isolation Design

## 背景

题材研究的 owner 把 40 秒切片交给 closed-loop RAG。生产回放中 narrow
Hybrid 查询耗时约 22 秒并命中 6 条证据；闭环随后无条件发起 broad 查询，后者只
拿到不足 18 秒的剩余预算并超时。当前 persistent worker 为保持 JSONL 协议同步，
超时时必须终止子进程，于是一次可预见的 stage 预算耗尽扩大为全局
`rag_worker=failed`，readiness 从 ready 变为 503。

另一个独立现象是知识库索引构建期间，知识库分支从 `5ab1e057` 前进到
`fbb2b428`，因此刚生成的索引按 freshness 合同立即 stale。该问题属于索引发布的
并发快照一致性，不通过放宽查询 freshness 解决。

## 目标与非目标

目标：预算不足时停止下一 aperture，并在 trace 中保留明确 gap；不得向共享 worker
发送确定无法在剩余时间完成的请求。真实 worker 卡死仍须终止并使 readiness
fail-closed。

非目标：不关闭 Hybrid RAG，不增加 worker 数量，不放宽 stale 索引门禁，不改变
EvidenceAtom/claim grounding 规则，也不提高用户请求根预算。

## 方案

`retrieve_closed_loop` 建立一个请求内 `_AttemptBudget`：保存绝对 deadline 和本轮已
观察到的最慢查询耗时。每次 aperture 开始前，要求剩余时间至少达到
`max(1 秒, observed_seconds * 1.25)`；不足时不调用 provider，而是记录
`RetrievalAttempt(status="budget_exhausted")` 和一条可见 warning。首次查询没有历史
耗时时只要求 1 秒，避免先验过强。

选择动态实测而不是固定 20/30 秒，是因为 BM25、dense、不同索引规模和机器性能差异
很大；选择 1.25 安全系数而不是简单复用上次耗时，是为了吸收负载抖动。替代方案是
把 owner stage 从 40 秒提高到 60/90 秒，但只能推迟同类故障，并增加尾延迟；双 worker
池可提升并发，却会让本地模型内存近似翻倍。

## 数据流与失败语义

`narrow -> 记录真实耗时 -> 预算预测 -> broad/counter`。预算足够时行为不变；预算
不足时 aperture 记为 `budget_exhausted`，已有 narrow 证据继续进入词面闸门、语义闸门
和 grounded 出口，缺失的 broad/counter 明确作为 gap。只有 provider 已经执行且真的
TimeoutError 时，persistent worker 才维持现有 kill + readiness red 语义。

## 验收

单元测试用可控 monotonic clock 模拟 10 秒总预算、首轮耗时 6 秒，断言只调用一次
provider，broad/counter 均为 `budget_exhausted` 且 narrow 证据保留。现有 closed-loop、
Ask/RAG、owner 回归必须通过。运行验收要求题材 smoke 完成后 readiness 仍为 ready；
知识库索引必须绑定同一个稳定 HEAD，不能用 stale-policy warn 绕过。

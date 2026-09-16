# feat/substitute-probe-prefetch-p1b

## 这个分支做什么

替补观察探针 P1-b：题材+个股观察类一般题（如 SPT 周一科技医药题、有色题）在
Engine A **开口预取**里拿到带「出清/分歧观察」标签的替补池。链路：
`SIGNAL_SUBSTITUTE_OBSERVATION`（题材/个股/观察三词族、market_watch 门控）→
`market.substitute_observation` operator → `collect_prefetch_items` 消费
`market_watch_pack.substitute_observation_receipts`（与 P0 同一探针函数）。

## 落点修正（勿按 spec v1 施工）

spec v1 §8 写的 `run_strict_signal_pack` 分发是**不执行的路**——编排器只对
`market_watch` 调 `bind_research_program`。真缝是开口预取（`episode_tools`
两处调用，全题型进入，`PrefetchItem.to_evidence()` 自动带 hash 发 E 号）。
详见 spec §8.1 与 `~/.finance-runtime/substitute-probe-live-20260825/spt-route-freeze.md`。

## 已验证

- 红→绿：8 新测（信号词族/门控/编译器/预取消费/as_of 截断/无信号静默/hash）。
- as_of 截断锁死：库有 07-24 行、问句截止 07-23 → 站立日 07-23，07-24 名字不进 detail。
- 存量回归 86 过（asof_prefetch×3 + prefetch ordinal×2 + market_watch×2 + outlook）+ 探针 P0 十例。
- ruff 5 文件 0。
- live 只读真实库：SPT 周一原题 as_of=2026-08-25 → 预取项「医药→医药医疗（1556.85亿）
  →药明康德/沃森生物」，source_date=2026-08-24，content_hash 有。

## 未验证 / 已知边界

- 全量 pytest 后台在跑（提交时未出）；合并前以其结果为准。
- 阶段题（个股怎么对标）不触发——无题材词族，0-operator 契约债另立单。
- episode 全链 live（模型在场引用 E 号替补池）未跑；P1-a weekly 仍未做。
- 能力图谱两行已登记（vault），`graph_audit` 在本分支提交后应全绿（提交前 STALE 属预期）。

## 下一步

1. 全量绿后合 PR（等用户确认）→ 视情况切 8792。
2. P1-a：weekly 最新交易日袋接探针。
3. 「假设×时点×推翻条件」范式出圈设计稿（Knevo 差距吸收第 2 项）。

# 在途交接 · cursor/settle-batch-ledger-d7ac

更新：2026-08-13 · R13 验收挖出的记账炸机 bug，修复已提 PR #306

## 这个分支做什么

工具批次记账烧穿 root 账本时结平（settle）而不是抛 ValueError 炸掉整个 run。

## 当前状态

- 已提交 `182f6b55`，PR #306。变异验证过（还原旧行为测试即死于生产同款异常）。
- 未部署。R13-A3 收据是本 bug 的生产现场。

## 下一步

1. 合 #306 后蓝绿切 8792，重跑 A3 看是否走通或至少优雅降级。
2. 新立案：「立新能源」被解析成 theme「新能源」（吞「立」字）→ understanding 层实体识别，路由错到 theme-research。
3. R13 其余观察：A4/A6 修复轮 16s 首枪+30s 重试仍双超时（中转慢时段）；A6 熔断后 `repair_model_unavailable` 但保住了草稿——机制按设计工作。

## 未验证

- 合并后生产重跑 A3。

## 踩过的坑

- 收据 `repair=0/0 stop=None` = 失败在 episode 之前/异常逃逸，别当饿死修。
- 结算已完成的工作不能 fail closed（#297 同源原则，本次是第二处现场）。

## 已验证

- 181 passed（episode/adapter/coordinator/invariant）；变异验证红→绿。

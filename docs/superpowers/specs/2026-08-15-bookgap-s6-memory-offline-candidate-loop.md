# S6 · user_memory 离线候选更新链：扩 forecast_learning_loop，不另起炉灶

- 索引：`2026-08-15-bookgap-index.md` · 靶：第 8 章 🔴「验证后再发布」 · 仓：finance · 优先级 P1
- 并行安全：services 记忆面 + 离线脚本，立即可开工（与 S8 都在记忆面，
  **两 spec 派不同 agent 时禁止同时动 `memory_status.py`**——S6 只读它，改动归 S8）

## 1. 背景（证据）

- 08-10 审计第 8 章对照：在线记录证据 🟢（`.foresight/` 台账齐），
  离线生成候选更新 🟡（夜间回检有，但没有「候选」这一层），
  **验证后再发布 🔴（经验多是人工读了再改，缺自动候选→验证→发布链）**，
  可回滚 🟡（git 可回滚，但没有「这条经验导致了什么」的归因）。
- 08-13 质检 §0 已给方向：**仓内 `forecast_learning_loop` 已经是同一
  构件——扩平面，不另起炉灶**。
- 入口门禁已在：`memory_gate.py` 是 fail-closed 的 candidate→accepted
  晋升门，08-13 质检明说「本轮没改、也不该改」——本 spec 同样不改它，
  只是让候选**产生**这一步自动化。

## 2. 目标 / 非目标

- 目标：离线作业从 `.foresight/` 台账（corrections/verdicts/interactions）
  生成**候选**经验更新（candidate 状态），走既有 `memory_gate` 晋升，
  拒绝的留档带理由。
- 目标：每条候选带**归因链**：`{来源记录 ids, 触发规则, 生成时间}`——
  回答「这条经验从哪来」，回滚时可反查。
- 非目标：不改 `memory_gate.py` 判据；不改检索器；不做在线学习
  （书第 8 章明确在线/离线分离）；候选不自动 accepted——晋升仍走门禁。

## 3. 改动面

| 落点 | 内容 |
|---|---|
| `intelligence/services/memory_candidate_loop.py`（新） | 离线扫描台账 → 规则化候选生成（v1 规则：同一主题 ≥2 条同向 correction / verdict 被用户翻案 → 候选）→ 提交 memory_gate |
| `scripts/run_memory_candidate_loop.py`（新） | CLI 入口（幂等、可 dry-run），供夜间 launchd/cron 挂载（挂载本身留给用户） |
| 测试 | 候选生成规则单测 + 归因链完整性 + 幂等（重跑不重复产候选）+ gate 拒绝路径留档 |
| 文档 | 候选生命周期一页：produced → gated(accepted/rejected) → （既有）invalidated |

## 4. 验收判据（预注册）

1. 夹具台账跑出 ≥1 条候选，字段含完整归因链；dry-run 不落盘。
2. 幂等：同一台账重跑两次，第二次零新候选。
3. gate 拒绝的候选在档，带拒绝理由；**没有任何路径绕过 memory_gate 直写**
   （测试断言写入只经 gate API）。
4. 归因可反查：给任一 accepted 经验，能命令行一步查到来源记录 ids。

## 5. 风险

- v1 规则太保守产不出候选：可接受，宁缺勿滥（书：优先可归因、可验证、
  可回滚的局部修改）；产出率进报告，调规则是后续轮的事。

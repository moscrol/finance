# 2026-08-14 逐工具可观测性 — 已合 main

PR [#347](https://github.com/linxiaoqi5111-del/finance-workspace-private/pull/347) 已合入 `main`（merge `66b2eee8`，运行时 `b037b615` + 审计脚本 `95a4bebc`）。**未切 8792。**

## 做了什么

三个源各瞎一半：`metrics.tool_calls` 只有总数；事件流丢掉整条分支路径；`traces` 成功路上把工具真名藏进 `provider`、`capability` 改写成 `agent_loop`。

1. `consume_sub_research` 补发 `branch_tool`
2. `provider_trace_tool_name()` 单一归一化口径，运行时与 `scripts/audit_episode_tool_outcomes.py` 共用
3. `queued_ms` / `elapsed_ms` 分开记；派发前被拒写 None 不写 0

方法论：`agent-memory` `10_knowledge/misaligned-field-looks-plausible.md`（#29）；BUILD 候选模式 8（harness-reference #6）。均已合，未晋级七模式。

## 验证

- focused `test_agent_episode.py` 含 `test_branch_tools_emit_events_instead_of_disappearing`；全量当时 4819 passed。CI 绿。
- 现场 ③：8801 `kb_search` 排队 0.1ms / 执行 5523ms；`tool_budget_exhausted` 如实 None/None。

## 遗留

- **① `branch_tool` 只有单测。** 8801 三道现场题 GLM 都跳过 PLAN 直接调工具（含重放凌晨会分支的「中际旭创怎么看」）。第一次分叉在 `model_turn`，埋点函数没被调用。不要再拿公司题撞运气；要现场验得绕过模型、直接喂 coordinator。
- 生产 timeout 悬案：排队与工具慢都已排除；下次 8792 重启后用 `elapsed_ms` 复核。计时 `monotonic()` 只用于同一 episode 内。

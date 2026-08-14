# fix/tool-observability — 逐工具可观测性（分支事件 / 工具名 / 耗时）

日期：2026-08-14 ｜ worktree：`/Users/a77/fwp-wt-tool-observability` ｜ 状态：**已提交，未合 main**

## 这个分支做什么

修「没有任何数据源能回答『某个工具成功率多少』」。三个源各瞎一半：
`metrics.tool_calls` 只有总数；事件流丢掉整条分支路径；`traces` 在成功路上
把工具真名藏进 `provider`、把 `capability` 改写成 `agent_loop`。

## 当前状态

- 已提交 `d49b551b`（运行时三处）+ `c50dd34e`（审计脚本），rebase 到 origin/main，待 CI。
- ① `consume_sub_research` 补发 `branch_tool`（此前分支里的工具一条事件都不发）。
- ② `provider_trace_tool_name()` 单一归一化口径，运行时与审计脚本共用。
- ③ `queued_ms` / `elapsed_ms` 分开记；派发前被拒的调用写 None 不写 0。
- `scripts/audit_episode_tool_outcomes.py`：0 档只读，按真名出成功率 + 证据消费率。

## 已验证

- 全量 4819 passed / 4 skipped；ruff 通过；新增 6 条测试含 2 条变异测试。
- **现场验证 ③**：8801 读出 `kb_search 排队0.1ms/执行5523ms`；
  `tool_budget_exhausted` 四条如实 `None/None`。

## 未验证 / 已知边界

- **① `branch_tool` 仍只有单测。** 8801 三道现场题都没进分支路径
  （英维克 / 三家对比 / 重放历史会分支的「中际旭创怎么看」）。
  按 triage：第一次分叉是 `model_turn` 跳过 PLAN、直接 `tool_calls`，
  没有 `plan` / `mode_decision` / `branch_started`——埋点函数没被调用，
  不是事件发不出来。同题 03:53 的生产跑曾出过 PLAN + 3 分支（GLM 5.2 今天不发）。
- 未在生产 8792 验证。计时用 `monotonic()`，只用于同一 episode 内归因。

## 下一步

1. 不要再拿公司题撞运气。要现场验 ①，得先让模型发出带 `branch_goals` 的 PLAN
   （或写一个绕过模型、直接喂 coordinator 的 runtime 探针）。
2. 生产 timeout 悬案：排队与工具慢都已排除；下次 8792 重启后用 `elapsed_ms` 复核。

## 踩过的坑

- 「events 被截断」证伪（sequence 连续）；「错误率算不出来」证伪（写错栏）。
  字段错位比缺失更难发现。已归位
  `agent-memory/10_knowledge/misaligned-field-looks-plausible.md`（PR #29）+
  BUILD 候选模式 8（harness-reference PR #6）。

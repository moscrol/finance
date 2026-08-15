# S1 · 时间预算可见（Agent 状态栏 v1，只放预算）

- 索引：`2026-08-15-bookgap-index.md`（共同纪律与冲突矩阵在索引，必读）
- 靶：ai-agent-book 第 2 章（状态栏）+ 第 10 章（预算感知）双 🔴
- 目标仓：finance-workspace-private · 优先级 **P0**
- **串行依赖：见索引 §2——与 dsh 吸收 P0 同文件，开工前查其分支状态**

## 1. 背景（证据）

- 08-10 按章审计 [实测]：步数预算一直在传
  （`agent_episode.py::_append_tool_budget_state` 把
  `runtime_budget.remaining_tool_calls` 注进最后一条 tool 消息），
  **时间维完全没有**。
- 后果实测：08-09 S3 题面改对后工具调用 3→6 次，然后
  `repair_deadline_exhausted`——模型不知道快没时间，仍在广撒网；
  08-10 臂 C 里失败模式已从「没时间」移到「查得太多」
  （`tool_budget_exhausted`），书里预算感知正是解这个。
- 书的处方（第 2 章）：不让模型在海量上下文找线索，主动注入提炼后的
  结构化状态；Google《Budget-Aware Tool-Use》：需要显式预算感知，
  模型才会「前期广撒、后期收敛」。

## 2. 目标 / 非目标

- 目标：模型每轮能看见**时间**剩余（秒 + 百分比），与既有步数预算
  同址同格式注入。
- 目标：EVAL_ONLY 观测——收据里能读出注入是否在场（字段而非话术）。
- 非目标：不做完整状态栏（已用工具摘要、证据摘要等后续再说）；
  不改任何预算**数值**与档位策略（那是 S3 的缝）；不改 verifier。

## 3. 改动面

| 文件 | 改什么 |
|---|---|
| `intelligence/runtime/agent_episode.py` | `_append_tool_budget_state` 增加时间行：从 episode 起点与 policy `total_seconds` 算 elapsed/remaining/ratio，追加到同一条注入消息 |
| 对应测试 | 扩 `test_next_model_turn_sees_dynamic_tools_and_remaining_budget`（该测试 08-10 曾兜住一次错误负面断言，别绕开它） |
| 收据 | finish payload 或 turn 观测加 `time_budget_injected: true/false`（EVAL_ONLY，供验收台读） |

注入格式建议（一行，CJK 安全）：
`[预算] 时间 剩 X 秒 / 总 Y 秒（Z%）；工具 剩 N 次`

## 4. 验收判据（预注册）

1. 夹具：任一带工具轮的 episode，最后一条 tool 消息含时间行，数值与
   墙钟一致（容差 ±2s）。
2. 无回归：`test_agent_episode.py` 全绿；注入行不进公开答案、不进证据。
3. live（部署后，可留给下一批读数）：deep 档同形 case 的
   `repair_deadline_exhausted` 率相对批 #3 基线不升；若模型行为无任何
   变化（率持平且轨迹无收敛迹象），如实记 unobserved，不硬判 confirmed。

## 5. 风险

- 每轮多 ~30 token 上下文；可接受。
- 时间行会随每轮变化，破坏 KV cache 前缀——注在**最后一条** tool
  消息尾部（现行步数预算同址），增量失效不影响前缀缓存。

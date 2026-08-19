# P5 收据 — 组合故障注入矩阵

- 日期：2026-08-19
- 树：`/Users/a77/fwp-wt-runtime-hardening` @ `88249857` + 未提交
- 前置：P4 收据
- **没改** `claim_terminal_run` / `QueryPublishGuard.close` / `add_artifact` 终态策略
- 每个 case 记录：injected failure / expected vs actual phase path / budget delta / public status

## 原理（为什么是矩阵而不是「再写一遍 adapter 测试」）

单元测试绿只证明单缝。组合故障要的是：**同一套六个字段**，故障是注入的，不是口头映射。

| 方案 | 做什么 | 这里为什么不用 |
|---|---|---|
| 生产缝注入（本轮） | timeout / close guard / 第二次 claim / OSError 写盘 | 走真实 API，记录 6 字段 |
| 全链路 adapter 重放 | 每条都起 ContinuousTurnAdapter | 夹具重、且多数缝已有专测 |
| Chaos 随机杀进程 | 非确定 | spec 要求 deterministic |

## 九条

| case | 注入 | 实际公开态 | 备注 |
|---|---|---|---|
| model_timeout_zero_evidence | 零证据 + cold_restart | failed | cycle=1 授予，cycle=2 拒绝 |
| tool_partial_success_timeout | 一成功一 timeout | partial | 成功证据保留，结算扣 2 call |
| semantic_verifier_timeout_keeps_draft | judge TimeoutError | partial | draft 仍在，不是 completed |
| repair_provider_late_result | guard.close 后 fetch 返回 | completed | sidecar discard，phase 不二次终态 |
| deep_promotion_then_cancel | promote 后首轮模型即 cancel | cancelled | 工具 0 次，remaining_calls 不变 |
| root_seconds_exhausted_batch_settlement | 烧穿后再 settle | settled_without_exception | 不抛；秒数归零 |
| duplicate_terminal_claim | 第二次 claim | completed | 输家 `won=False`，error 仍是赢家的 |
| process_restart_at_repair_boundary | `requeue_incomplete_runs` | queued_no_repair_session | **G7 声明不支持** repair 续跑 |
| receipt_write_failure | `report.json` write OSError | completed | 已 claim；不伪造收据文件 |

结算那条没有伪造 `partial` 终态：生产缝只保证「结算层自己不成新失败源」。公开 episode 状态仍由 adapter 投影。

## 命令与读数

与 P4 同一次定向套件：`335 passed in 2.57s`
机器收据：`~/.finance-runtime/test-receipts/20260819T141858Z-88249857.json`

dirty=true。未提交 / 未推 / 不合 main。

## 总路线收口

P0 冻结 → P1 phase sidecar → P2 预算不变量 → P3 G5/G6/子研究取舍 → P4 SLO/离线门 → P5 矩阵。

还没做（需你点头）：提交、推分支、合 main、live canary、自动回滚、G7 真续跑。

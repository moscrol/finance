# feat/repair-backfill-turn

## 这个分支做什么
W5：`numeric_unsupported` / `financial_anchor_missing` 阻断时，episode 层给一次窄契约补证（只开对应 capability、预算 ≤ 原回合 25%），再全套重验。判官仍只删不加。叠在 W1 `5af29bb1`。跟踪题表达缺件走 Track D（#240）的 `contract_rewrite_candidate`，**不**进本流。

## 当前状态
**已合 #237。** sidecar 阈值题 2026-08-19 已跑（`docs/verification/2026-08-19-w5-backfill-live.md`）：准入过（`backfill_turns=1`，只开 `market_data`，22.5s=25% 帽），**completed 未过**——回填第二次 `market_data {}` 撞 `duplicate_query`。#241 已合，不搭本流。

## 已验证
- 解释器 `.venv-workbench`；ruff 绿。
- 定向 **269 passed**（issues / repair_coordinator / adapter / semantic verifier）。
- 25% 帽、半窗 fail closed、无进展仍可补证、adapter 一次 `market_data` 补证、新增句子回滚。

## 未验证
回填后 `completed`：需另开分支处理「首轮已打过同参 `market_data` 时 duplicate 闸误杀补证」。不要把 `track_*` 槽并进 `BACKFILL_TRIGGER_CODES`。

## 下一步
1. 回填查询带 as_of / 空结果不占 duplicate key（另分支，不打 8792）。
2. 再打一发阈值题看能否 `completed`。

# feat/repair-backfill-turn

## 这个分支做什么
W5：`numeric_unsupported` / `financial_anchor_missing` 阻断时，episode 层给一次窄契约补证（只开对应 capability、预算 ≤ 原回合 25%），再全套重验。判官仍只删不加。叠在 W1 `5af29bb1`。跟踪题表达缺件走 Track D（#240）的 `contract_rewrite_candidate`，**不**进本流。

## 当前状态
**已合 #237。** 触发词表在 `episode_issues.plan_issue_backfill`；授予在 `admit_backfill_repair`（绕过进度闸）；adapter 在 G7 之后、G11 之前插一次。新增句子 fail closed。Track D #240 已合，两管道并存：取数补证 vs 表达改写。

## 已验证
- 解释器 `.venv-workbench`；ruff 绿。
- 定向 **269 passed**（issues / repair_coordinator / adapter / semantic verifier）。
- 25% 帽、半窗 fail closed、无进展仍可补证、adapter 一次 `market_data` 补证、新增句子回滚。

## 未验证
sidecar 阈值题（首轮 numeric → 回填 → completed）未跑。不要把 `track_*` 槽并进 `BACKFILL_TRIGGER_CODES`。

## 下一步
1. sidecar 阈值题 live（不打 8792）。
2. 口径合一 #241 另单，不搭本流。

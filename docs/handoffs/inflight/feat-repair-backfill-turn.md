# feat/repair-backfill-turn

## 这个分支做什么
W5：`numeric_unsupported` / `financial_anchor_missing` 阻断时，episode 层给一次窄契约补证（只开对应 capability、预算 ≤ 原回合 25%），再全套重验。判官仍只删不加。叠在 W1 `5af29bb1`。Track D 的跟踪题缺件接线不在本流。

## 当前状态
**已实现、未合。** 触发词表在 `episode_issues.plan_issue_backfill`；授予在 `admit_backfill_repair`（绕过进度闸）；adapter 在 G7 之后、G11 之前插一次。新增句子 fail closed。

## 已验证
- 解释器 `.venv-workbench`；ruff 绿。
- 定向 **269 passed**（issues / repair_coordinator / adapter / semantic verifier）。
- 25% 帽、半窗 fail closed、无进展仍可补证、adapter 一次 `market_data` 补证、新增句子回滚。

## 未验证
sidecar 阈值题（首轮 numeric → 回填 → completed）未跑。Track D 运行时接线仍缺。与 W2 同改 `continuous_turn_adapter.py` / `episode_semantic_verifier.py`，后合方 rebase。

## 下一步
1. 用户确认后开/合 PR；不合并 main 除非另嘱。
2. Track D 若先合，把跟踪题缺件并进同一条补证管道。
3. 与 W2 叠合时先处理 adapter/G11 冲突。

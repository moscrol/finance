# feat/repair-backfill-turn

## 这个分支做什么
W5：`numeric_unsupported` / `financial_anchor_missing` 阻断时，episode 层给一次窄契约补证（只开对应 capability、预算 ≤ 原回合 25%），再全套重验。判官仍只删不加。叠在 W1 `5af29bb1`。跟踪题表达缺件走 Track D（#240）的 `contract_rewrite_candidate`，**不**进本流。

## 当前状态
**已合 #237。** 跟进 `fix/w5-backfill-duplicate`：空结果不占 duplicate 键；`_runtime_market_reference_date` 在快照超前 DuckDB 时取较早那天。起因是 sidecar 阈值题 `backfill_turns=1` 后第二次 `market_data` 撞 `duplicate_query`，且所需日 08-19、库只到 08-18。

## 已验证
- 解释器 `.venv-workbench`；ruff 绿。
- 定向 **269 passed**（issues / repair_coordinator / adapter / semantic verifier）—— #237。
- 本跟进：`test_empty_market_data_miss_does_not_block_backfill_retry` + 参考日夹具 + 原 duplicate/adapter 回归。

## 未验证
sidecar 阈值题重放（不打 8792）。不要把 `track_*` 槽并进 `BACKFILL_TRIGGER_CODES`。

## 下一步
1. sidecar 重放阈值题，看能否 `completed`。
2. 读数 #244 另合，不搭本流。

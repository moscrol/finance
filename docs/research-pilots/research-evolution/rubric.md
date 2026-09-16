# 盲审评分表 rubric-v1

四维各 0–2，总分 8。评审人不知道产物来自原流程还是辅助流程（盲审）；无法盲审的产物照评，但 `blinded=false` 会在总结里列为偏差。

| 维度（`dimensions` 键） | 0 | 1 | 2 |
|---|---|---|---|
| `fact_sourcing` 事实出处 | 关键事实无出处或出处错 | 部分有出处 / 出处不到页 | 每个关键事实可回查到页 / 行 |
| `calculation` 计算 | 有计算错误 | 计算对但口径没说明 | 计算对且口径、单位、时点写明 |
| `assumption_gaps` 假设缺口 | 未提任何假设 / 缺口 | 提了但没说明影响 | 假设、缺口、无法判断项都写明并说明影响 |
| `task_completion` 任务完成 | 未达完成条件 | 达完成条件但交付物形状不符 | 完成条件与交付物形状都符合任务卡 |

## 严重错误（`severe_error_count`）

关键事实错误、关键计算错误各计一次。判据只看任务卡列出的关键项；争议项不计入，转裁决。辅助流程只要出现严重错误，`completion_quality` 判据即不达标（阈值 `severe_error_max: 0`）。

## 流程

1. 产物脱去条件标识后交评审；评审在 `quality_reviewed`（`manual_import`）里给 `rubric_version / reviewer_id / blinded / artifact_refs / dimensions / severe_error_count`，并带 `importer_id / evidence_ref / evidence_hash`。
2. 两位评审分歧 ≥ 2 分或严重错误认定不一致 → 第三人裁决，裁决结果另发一条 `quality_reviewed`，payload 加 `adjudication_ref`；测量取有 `adjudication_ref` 的那条。
3. 参与者未同意 `blind_review` 范围 → 评审事件被排除（`exclusions.reason=blind_review_consent_missing`），该任务质量 unknown，判据 unknown。不用模型自评分补齐。

# Phase 4 产品接线读数（2026-08-18）

- 树：`/Users/a77/fwp-wt-caliber-p4` `feat/caliber-phase4-wiring`
- 叠在：`feat/caliber-phase3-tool-result` @ `82f99b26`（#201）
- 设计：`docs/superpowers/specs/2026-08-18-measured-value-caliber-contract-design.md`
- 未切 8792，28 题 sidecar 另开 8796

## 改了什么

1. **`MetricSpec` 提升**：`intelligence/services/metric_spec.py` 是唯一注册表。`market_timeseries` 再导出同一对象。判分器 `compile_case_contract` 把 registry aliases **并入** overlay（overlay 在前，不替换）。
2. **`EvidenceAtom.value`+`unit`**：`bind_measured_value` 仅在「恰好一个 registry 指标 + 一个数字」时填写；「万亿」换算进 `provenance`。`research_owner` 中期趋势原子填 `double_red_days` / `天`。
3. **C3 空表披露**：`empty_caliber_disclosure` 命中「技术面快照」且 `fact_stock_technical_snapshot` 为 0 行（缺表 ≡ 空）时罐头短路。不说「表不存在」。库不可读 fail-open。`deterministic_lane_answer` 在退役表之后、休市之前调用。
4. **C4/C5 车道**：`quick_fact` 题型不变；带 ISO 日期的指标取值 `lane=research`。「茅台现在股价多少」仍 knowledge。指定日单指标（C2 涨停家数）同样 research，休市罐头仍生效。
5. **语义层**：注册 `theme_limit_heat_daily`（A5 题材热度）与 `stock_technical_snapshot`（C3 空口径可查，不换价格表）。

## 验收（代码门，非 28 题新 run）

| 判据 | 读数 |
|---|---|
| 4.1 单注册表 | `market_timeseries.METRICS is metric_spec.METRICS`；A1 `total_amount` aliases 以 overlay「成交额」打头，并入「全市成交额」 |
| 4.2 原子填写 | 「全市成交额 2.96万亿」→ `metric=total_amount` `value=29600.0` `unit=亿元` `raw_unit=万亿`。两指标或无数字 → 不填 |
| C3 空表 | 注入 `row_count=0` 时答案含 `fact_stock_technical_snapshot` / `空表` / `0 行` / `数据不可用`，不含「表不存在」。`row_count>0` 或问句无快照词 → 不罐头 |
| C4/C5 车道 | `route_id=quick_fact` 且 `lane=research`。`茅台现在股价多少` / `300750是哪家公司` 仍 `lane=knowledge` |
| A5 表可查 | `_DATASETS["theme_limit_heat_daily"].table == fact_theme_limit_heat_daily` |

## 28 题 sidecar 读数（8796，`20260818T1749Z-caliber-p4`）

前置：`revision=69eef65a backend=continuous_glm`，未 `--force`。8792 未切。跑完已停 8796。
artifact：`intelligence/eval/runs/20260818T1749Z-caliber-p4.json`（工作树未入 git，约 184KB）
看板：`docs/verification/2026-08-18-caliber-p4-board.txt`

| 判据 | 读数 |
|---|---|
| 真值 | 通过 6 / 失败 9 / 不可判 13；可判 **6/15** |
| C3 | ✅ 通过。答案原文：`fact_stock_technical_snapshot 当前是空表（0 行），该技术面快照数据不可用。不会用价格表或其他口径替代。` |
| C4/C5 车道 | 不再 `knowledge_lane_answer`。C4 controller `lane=research` `question_type=quick_fact`；合成 `reason_code=validated`。两题仍 ❌（未标单位异常 / 未标数据矛盾），且降级：generic owner 取了 08-17 全市总览 + web，没有 `fact_sector_daily.amount=6112588.6` |
| A5 题材口径 | ❌。`finance_query` 实际 dataset=`mainline_sector_daily` / `mainline_theme_daily`；提示里出现过 `theme_limit_heat_daily` 但查询没改过去。答案是电力/锌/医药板块家数，不是储能 40 |

## 故意留下的产品缝

- `evidence_registry` 各 provider **没有**再列一份 `(metric, unit, caliber)`——那会变成第二张注册表。D0 七项走 `MetricSpec`；A5 靠语义层注册 `theme_limit_heat_daily`，模型仍可能选错表。
- C4 离开 knowledge 车道 ≠ 已经取到 MLCC `fact_sector_daily.amount=6112588.6`。脏数质疑仍取决于 research 检索有没有打到板块表。
- 「07-21 全市成交额多少」年缺省写法 `market_review_requested_date` 解析为 None，仍可能停在 knowledge；验收题面已带 ISO 日期。

pytest：本 PR 触及的 metric/honesty/quick_fact/verdict/finance_query/timeseries/board/turn_control_core/tool_payload 相关用例绿。ruff 改动文件通过。

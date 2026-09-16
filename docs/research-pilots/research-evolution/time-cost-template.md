# 时间与费用登记表（→ `manual_import` 事件）

原流程没有 Workbench run，只能靠登记；辅助流程的模型等待与 run 由服务端记录，这张表只补人工部分。所有登记都带 `importer_id / evidence_ref / evidence_hash`（例如截图、计时器导出、账单文件的哈希）。

## A. 原流程计时（每任务一张）

| interval_id | start（带时区） | end | activity | clock_source | pause_reason | 备注 |
|---|---|---|---|---|---|---|
| i-<task>-1 | 2026-10-06T10:00:00+08:00 | 10:40:00 | user_active | manual_actual / manual_estimate | — | 计时器 / 事后估算要分清 |
| i-<task>-2 | 10:20:00 | 10:25:00 | pause | manual_actual | pre_registered_break | 只有协议登记过的理由会扣 |
| i-<task>-3 | 10:40:00 | 10:50:00 | external_lookup | manual_actual | — | 查原资料算主动时间 |

- `activity`：`user_active` 主动 / `external_lookup` 查阅原资料 / `model_wait` 等待 / `manual_rescue` 人工救援 / `pause` 暂停。
- 重叠区间会求并集；估算（`manual_estimate`）让该任务计时标为 `estimated`。
- 任务终态另记一条 `task_completed / task_failed / task_abandoned`（`manual_import`），带交付物引用。

## B. 人工帮助（`manual_assistance`）

| helper_id | task_id | start | end | help_kind | 实际 / 估算 |
|---|---|---|---|---|---|
| helper-01 | t-… | … | … | fix_query / explain_tool / redo_step | 实际 |

救援工时另计，不从端到端耗时里扣；未登记费率时在费用里记为 `manual_rescue` 未知项。

## C. 费用项（`cost_recorded.cost_item`）

| cost_id | component | run_id / attempt_id | coverage_scope | quantity | unit | amount | currency | certainty | evidence_ref | rate_version |
|---|---|---|---|---|---|---|---|---|---|---|
| c-… | writer_model | r-… / a-… | run | 12000 | tokens | 0.36 | CNY | known | usage:r-… | rate-2026-10 |
| c-… | review_model | r-… / a-… | run | null | — | 0.05 | USD | known | bill:… | rate-2026-10 |
| c-… | manual_rescue | — | task | 10 | minutes | null | null | unknown | — | — |
| c-… | hosting | — | pilot | 1 | month | 50 | CNY | known | invoice:… | — |

规则：
- `component` 取值：`writer_model / review_model / other_model / tool / retry / manual_import / manual_rescue / manual_maintenance / data_license / hosting / acquisition_allocation`。
- 只有用量没有费率 → `amount=null, certainty=unknown`；有账单没用量 → `known` 但会被标 `usage_missing`。预算数字不是费用；没观察到调用不等于零费用。
- 同一 (component, run) 下 span / attempt / run 多层都填时，测量只取最粗一层，其余标 `covered_by_*`。
- 币种不合并；没有可靠汇率就并列展示。

## D. 付款（`payment_recorded`，只在实际发生后登记）

| payment_ref | participant_id | amount | currency | service_period.start | service_period.end | status | verified_by | refunds_payment_ref |
|---|---|---|---|---|---|---|---|---|
| pay-… | p… | 199 | CNY | 2026-10-05 | 2026-11-04 | paid / refunded | bank-statement-2026-10 | （退款时填原付款） |

续费分子只认第二期实付；意愿、免费延长都不算。

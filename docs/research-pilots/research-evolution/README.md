# 用户价值四周试点包（05 轨材料）

这是**准备材料**，不是外发授权：邀请、收费、招募、访问第三方私有资料，执行人须另获用户相应授权。首版不建团队系统、不卖数据或 API。协议与判据在采集前冻结，改判据另开一组。

| 文件 | 用途 |
|---|---|
| [protocol.yaml](protocol.yaml) | 协议模板：任务卡、配对、评分表、允许扣除的暂停、判据、排除规则、四周窗口。采集前 `freeze` 得到 `protocol_hash` |
| [task-cards.md](task-cards.md) | 两类任务 × A/B 匹配案的任务卡与交叉顺序表 |
| [rubric.md](rubric.md) | 盲审四维 0–2、严重错误定义、裁决流程 |
| [invitation-template.md](invitation-template.md) | 邀请说明（任务 / 四周安排 / 耗时 / 数据用途 / 退出 / 无收益承诺） |
| [consent-template.md](consent-template.md) | 分范围同意书与撤回 / 删除规则 |
| [time-cost-template.md](time-cost-template.md) | 原流程计时、人工帮助、费用登记表 → `manual_import` 事件 |
| [interview-guide.md](interview-guide.md) | 第 4 周个人访谈 + 小团队「周会证据包＋交接」访谈 |
| [team-evidence-pack.md](team-evidence-pack.md) | 团队样例：冻结依据 / 变化 / 分歧 / 负责人与复核日期，以及要测的准备时间、遗漏、依据还原 |
| [summary-template.md](summary-template.md) | 四周总结模板，字段对应 `PilotSummary` |
| [06-integration-contract.md](06-integration-contract.md) | 交给 06 的接线清单（事件渠道、单 writer、只读证据解析、验收反例） |

## 四周安排（spec 05 §4）

| 周 | 动作 | 产物 / 事件 |
|---|---|---|
| 1 | 取得授权后招募 3–10 人；登记同意与常用工具；完成第一类配对任务；首次配置时间另计 | `consent_changed`、`assignment_created`、原流程 `time_interval(manual_*)`、辅助流程 S 事件 |
| 2 | 完成第二类配对任务；独立盲审两周产物；收齐改错 / 帮助 / 等待 / 失败全链 | `quality_reviewed`、`manual_assistance`、`run_finished(status=failed)` 也要留 |
| 3 | 提供到期回检入口，观察无人工催促的主动复用；系统提醒与人工提醒分别标记 | `reuse_observed`（reminder_refs.kind = system / manual / unknown）、`recheck_viewed / recheck_completed` |
| 4 | 回检与访谈；核对费用与遗漏；按冻结判据出总结；付款 / 续费只登记已授权且实际发生的 | `cost_recorded`、`payment_recorded(manual_import)`、`PilotSummary` |

## 数据怎么流

1. 前端 / 服务端事件由 06 的 writer 落到用户态（见接线合同）；原流程与人工数据用 [time-cost-template.md](time-cost-template.md) 登记，经 `pilot_io import-events` 导入。
2. 06 的 `rebuild` 调用 `measure_pair` / `summarize` 生成不可变收据与总结；离线核对可用
   `python -m intelligence.eval.product_value summarize --events ... --protocol protocol.frozen.yaml --out-dir ...`。
3. 总结三态分开读：`engineering_status`（管线）、`field_status`（真人读数）、`commercial_status`（凭据核验的付款）。`observed` 只表示有真实读数。

## 三条不越界

- 参与者只用假名（`participant_id`）；原文、凭据、联系表不进代码仓。
- 不索取交易账号，不承诺收益。「不荐股、不提供个股买卖建议」只约束对外渲染的输出；试点任务卡、维护对象、排序对象、诊断对象的 scope **不过滤个股**（2026-09-13 协调方补发件第 2 条）。把这条约束下沉到渲染层是下一批的事，本批不顺手做。
- 意愿不算订单，免费延长不算续费；没有真实首付就是 `unstarted`。

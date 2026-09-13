# 05 → 06 接线合同（用户价值测量）

日期：2026-09-13。05 轨交付的是**合同 + 纯函数 + 离线 CLI + 材料**；本页告诉 06 该怎么把它接进 Workbench，以及哪些事 05 刻意不做。代码规范源：`intelligence/services/product_value/`（`contracts.py` 是字段与错误码的唯一清单，本页只讲用法，字段以代码为准）。

## 1. 05 提供什么

| 符号 | 作用 | 纯函数? |
|---|---|---|
| `validate_event(event, *, protocol=None) -> ValidationResult` | 合同校验；传 `protocol` 时同时核协议版本 / 协议哈希 / 评分表版本。`issues[].code` 是稳定业务码（`contracts.ERR_*`），06 的 API 可直接透传 | 是 |
| `prepare_events(events, *, protocol=None) -> PreparedEvents` | 批量校验 + 幂等（同 ID 同内容只计一次；同 ID 不同内容整体拒收记 `conflicts`）+ 修订（`supersedes_event_id`）+ 按发生时间排序 | 是 |
| `measure_pair(events, protocol, evidence_reader, *, case_pair_id=None) -> MeasurementReceipt` | 一对配对 → 收据 | 是（证据读取器由 06 注入） |
| `summarize(receipts, assignments, protocol, *, cohort_events=(), due_rechecks=None, as_of=None) -> PilotSummary` | 收据 + 全部分配 + 参与者级事件 → 总结 | 是 |
| `RunStoreEvidenceReader(store_for_owner)` | 只读真实 run：`store_for_owner(owner) -> RunStore | None`；`run.user != owner` 判越界，不泄漏对方对象 | 只读 |
| `InMemoryEvidenceReader` | 夹具 / 测试 | — |
| `freeze_protocol / protocol_hash / load_protocol` | 协议冻结与哈希 | 是 |
| `python -m intelligence.eval.product_value {validate,measure,summarize}` | 离线入口，只写显式 `--out-dir`；**不是生产 writer** | — |

## 2. 06 必须做的事（05 不做）

1. **判定来源渠道并盖章**：按接收入口给每条事件写 `source_channel ∈ {frontend, server, manual_import}` 与 `provenance.kind ∈ {observed, imported, synthetic}`。客户端请求体里的这两个字段一律覆盖，不采信。`POST /api/conversations/{id}/research-evolution/events` 只接受 `contracts.EVENT_TYPES` 中允许 `frontend` 的类型，服务端补 `recorded_at`、`owner_user_id`（来自部署允许的用户上下文）、`source_version.code_sha`。
2. **服务端事实事件**：观察 run 生命周期写 `run_started / run_finished`（真实 `run_id / attempt_id / status`）、`task_completed`（核对完成条件后）、`time_interval(clock_source=run|server)`、`cost_recorded`（用量 + 费率；缺费率就 `certainty=unknown`，不要填 0）、`reuse_observed`、`recheck_completed`（用户确认 / 修订动作之后；自动回检 `initiator=system`）。
3. **人工导入**：`pilot_io import-events` 走同一 writer，给 `manual_import` 事件校验 `importer_id / evidence_ref / evidence_hash`，原凭据按权限保存为受控引用。
4. **单 writer 落盘**（登记 ledger-map 后启用）：`UserSpace.root/research_evolution/product_value_events.jsonl`（append-only，重试不重复追加）、`protocols/<protocol_hash>.json`（冻结协议）、`receipts/<receipt_id>.json`、`summaries/<summary_id>.json`（不可变；新输入产新版本并保留 `supersedes`）。
5. **rebuild**：按协议哈希 + 原事件摘要调用 `measure_pair` / `summarize`；同输入得到同 `receipt_id / summary_id`（`generated_at` 除外），可用来做重启后的对账。
6. **到期回检清单**：从 01 的维护项取 `due_rechecks=[{object_ref, due_at, accessible}]` 传给 `summarize`；不传则回检指标 `unknown(due_list_unavailable)`。
7. **同意**：`consent_changed` 事件必须在测量事件之前存在；参与者无同意记录 → 收据 `incomplete(consent_unknown)`；撤回 `research`/`logging` 后的事件被排除（`exclusions.reason=consent_withdrawn`），退出计数保留。

## 3. 06 不得做的事

- 不得把前端自报的 `task_completed` / `quality_reviewed` / `cost_recorded(amount)` / `payment_recorded` 写进事件流（白名单会拒收，但拒收信息也要回给客户端，不能静默丢）。
- 不得用 `self_use_maturity.verify_run_binding` 的成功门过滤事件：失败 / 降级 run 必须进分母（spec 验收 2）。
- 不得把 synthetic 事件与真人事件混在同一 `pilot_id` 下当成真人读数；`summarize` 会自动分区，但生产 writer 本就不应接收 synthetic。
- 不得把 `generated_at` 当事件发生时间；不得用 `recorded_at` 回填 `event_at`。
- 不得在 `RunStore` 之外再造一份可编辑的 run 事实；`RunStoreEvidenceReader` 只读。

## 4. 前端可上报的事件（F 渠道）与最低 payload

| event_type | 最低 payload（另加 `initiator, assistance_source`） | 备注 |
|---|---|---|
| `task_exposed / task_selected / task_started` | `task_id, policy_version, view_id, client_at` | 服务端补接收时间 |
| `task_abandoned` | `task_id, completion_evidence_refs, terminal_reason` | 只是意图；S/M 终态优先 |
| `time_interval` | `interval_id, start, end, activity, clock_source=client, pause_reason, visibility` | 隐藏标签页只暂停 `user_active`；端到端不因离开页面变短 |
| `recheck_viewed` | `object_ref, verdict_ref, action_id, evidence_refs` | 打开不算完成 |
| `consent_changed` | `consent_version, scopes, effective_at, action, terms_hash` | 服务端保存生效记录 |
| `exercise_submitted` | `exercise_id, exercise_version, submission_ref, submitted_at` | 不冒充学习效果 |

## 5. 收据 / 总结在 UI 的呈现约束

- `MeasurementReceipt.status ∈ {valid, incomplete, invalid}`，`limitations[]` 与 `invalid_reasons[]` 必须可见，不能只显示一个总分。
- `PilotSummary` 三个状态分列展示：`engineering_status` / `field_status` / `commercial_status`。`field_status=observed` 的文案是「有真实读数」，不是「效果成立」；`synthetic_check` 只进原件查看器，不进普通主屏。
- 判据 `unknown` 要带 `unknown_kind`（`sample` 继续收集 / `gap` 补记录 / `unstarted`）。
- 费用永远按币种并列，不合并；`unknown_cost_components` 非空时不显示「总成本」数字。

## 6. 验收时 06 要能证明的反例（对应 spec §5 与 06 spec I08 / I13）

1. 一个失败 run（无 report.json）经真实 `RunStore` 解析后，收据里 `attempts[].failed=true`、任务仍在 `denominator_ids`；把失败 run 过滤掉的实现必须让该断言失败。
2. 同一事件 POST 两次：`event_accounting.duplicates` 记一次，分母不变；改 payload 再 POST：`conflicts` 记一次并返回稳定错误码。
3. 另一 owner 的 `run_id`：`RunStoreEvidenceReader` 返回 `cross_owner`，收据 `invalid(run_cross_owner)`，响应不含对方对象细节。
4. 重启后 `rebuild`：`receipt_id / summary_id` 与重启前一致。

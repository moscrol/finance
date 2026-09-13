# 06 返修计划 · 2026-09-13（QC 驳回后）

审查报告：`/Users/a77/.finance-runtime/reviews/research-evolution-06-qc-20260913/review.md`（S1–S3 + R1–R10）。
本文件是返修执行清单；每条修完在 PROGRESS.md 更新真值，不在这里记流水。

## 规范轴

| 编号 | 修法 | 落点 |
|---|---|---|
| S1 并发假成功 | 版本重读 + validate_action/link 校验 + append 全部进同一 `store.transaction()`；锁内幂等复查保留 | facade `_maintenance_action` |
| S2 半批导入 | 事务内先把整批与现有台账对账（同 id 异内容 → 整批拒、零写入），全过才追加 | pilot_io `cmd_import_events` |
| S3 evaluate 干跑写盘 | 无 `--apply` 分流成只读预览（study 存在性 / forecast 数 / 最新收据状态），不调 `evaluate_study` | study_io `cmd_evaluate` |

## 规格轴

| 编号 | 修法 | 落点 |
|---|---|---|
| R1 继续核查 422 | 服务端 continuation 带真实 origin run_id（会话最近已完成轮次，无则省略）+ `inherits` 结构化字段；前端完整透传，消息 202 后用新 run_id 调 link_run 登记关联；消息被拒 → `cancel_rejudge` 恢复 open | facade / App.tsx / 新动作 |
| R2 submit 泄露答案 | `_submit_exercise` 与 reveal 共用曝光边界：评卷前先 `record_exposure`（独立 operation_id，actor=submit_exercise）；identity 不可解析 fail closed | facade |
| R3 run 生命周期无生产者 | 新增 `run_observer.py`：`ObservingRunStore(RunStore)` 拦截 create_run/claim_terminal_run/claim_failed_run，经 EvolutionStore（同 writer）写 run_started/run_finished；终态有可核 token 用量才写 cost_recorded（certainty=unknown）；app.py `store_for` 薄改一行 | 新文件 + app.py |
| R4 无法建首条绑定 | 面板「从现在开始跟踪」按钮 → 表单（entity/as_of → 受控目录 → 勾选 refs → POST bindings → 刷新） | Panel/api.ts/App.tsx |
| R5 练习与收据无入口 | 面板渲染 diagnostics.exercise（作答表单 + 揭示按钮 + 反馈展示）；收据加「查看原件」→ 新 `read_receipt` 动作（validation 走 03 `read_receipt` 内部登记曝光；measurement/summary 走 store 验权读） | Panel + facade + contracts |
| R6 select_task 只刷新 | `_select_task` 返回带 continuation（origin run_id 有则给；full_prompt=任务问题；inherits 带 task_id/scope）；前端与 rejudge 共用同一条「带 continuation 进既有消息入口」链路 | facade + App.tsx |
| R7 冒充重判 | link_run 校验：run.session_id==会话；持久化关联（run_links 登记 / 消息 continuation.inherits.maintenance_item_id / 同会话最低关联）；completed → 新判断必须存在于台账、≠ 原 object_ref.ref、session_id==会话、ts ≥ requested_at；缺 ref 时服务端解析「该会话 requested_at 之后最新判断」；追加前用 01 `apply_event` 预检迁移 | facade + store（run_links.jsonl 新台账，ledger-map 登记） |
| R8 时钟推进重试变冲突 | bindings：先按 binding_id 定位已存记录，复用其 created_at 重建载荷再比对；events：客户端没给 event_at 时复用已存事件的 event_at 再算 content_hash。回归测试推进时钟 | facade/store |
| R9 生产适配器 hindsight | `RiverEvidenceSource.catalog`：cutoff > as_of 时传 `allow_hindsight=True`（切片标 hindsight、pit 永不 strict，已映射 unverifiable）；facade `_maintenance`：当前版本读不到的绑定**不喂** assess（基线也不喂），每条一个 gap；有排除 → 模块 unknown(current_source_unreadable)，全排除 → maintenance=None；前端 items 空且状态非 ok 时显示「还判不了」 | adapters + facade + Panel |
| R10 跨会话重放 | payload_digest 纳入 conversation_id；replay 前核对已存记录 conversation_id，不一致 → 409 | facade |

## 验收（审查 §执行交接）

完整合成用户路径：UI 建绑定→证据变更→选择研究→真实消息接受与终态→新判断闭合；并行旧版本冲突；
练习所有出答案出口先曝光；真实生命周期生成 05 事件→失败重试→同 writer 导入/重建。
最终 revision 的全量测试收据；不合并不部署，等用户确认。

# 06 返修计划 · 2026-09-13（QC 驳回后）

> **第一轮状态：已完成**。13 条全部修复，提交 `e90f483d`（后端）/ `a11fced1`（前端+文档）/ `297c47c3`（static）。
> 探针复核与全量收据见 `PROGRESS.md` 返修节。

> **第二轮状态：已完成**（2026-09-14）。Q1–Q9 全部修复，提交 `347bf8b2`（后端）/ `e8b1bd85`（前端+e2e）/ `089526ab`（static）。
> 复审探针复核与全量收据见 `PROGRESS.md` 第二轮节。

审查报告：`/Users/a77/.finance-runtime/reviews/research-evolution-06-qc-20260913/review.md`（S1–S3 + R1–R10）。
第二轮复审：`/Users/a77/.finance-runtime/reviews/research-evolution-06-ba10747d/`（Q1–Q9，`test_review_contracts.py` + `ResearchEvolutionReview.test.tsx`）。
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

## 第二轮返修（复审 ba10747d：Q1–Q9）

| 编号 | 修法 | 落点 |
|---|---|---|
| Q1 表单 422 | 后端 `object_ref` 收字符串（包成 `{"ref": s}` 走 find_trackable 解析全字段）+ 前端改发完整 object_ref dict；双保险 | api/research_evolution.py + facade + BindForm |
| Q2 终态无收尾 | 观察器在 run 终态（claimed）时经注入的 `maintenance_folder` 回调调 `facade.fold_run_terminal`：有登记关联 + 项在 rejudgment_requested → 折回 closed/open；幂等键 `link_run:{item}:{run}` 与客户端路径共用，双触发不双写；失败只 stderr（观察器纪律） | facade + run_observer + app.py 接线 |
| Q3 同会话无关 run 假关闭 | 折回必须有**预先登记的 run_links 行**（运行中登记），session 匹配只是注册闸不再是折回闸；终态无登记 → 400 `run_binding_mismatch`。残留风险记 handoff：运行中的旧 run 可先注册再折回，彻底关死需要 run 来源签名（不存在） | facade `_link_run_event` |
| Q4 练习 UI | cited_refs 改 visible_evidence_refs 勾选、selected_choices 给 id 输入（04 投影没有选项目录，如实文本输入）；反馈渲染 `checks[].expected/got` 与 `missing_evidence_refs`；揭示渲染 `answer_key.expected_choices/expected_refs/explanation_ref` | ExerciseCard |
| Q5 running 重试 409 | 登记分支也写动作幂等记录（无事件记录 `append_action_record`）：同键同载荷重试 → 重放首个结果；同键异 run → 409；同 (item,run) 不同键 → 复用已登记行不重复追加 | facade + store |
| Q6 select_task 无幂等 | 收进事务：查记录→重放存的结果（含 continuation）；digest 基 = action+task_id+conversation_id（不含 client_at）；事件只在首次落 | facade `_select_task` |
| Q7 来源引用丢失 | `ContinuationRequest` 加 `click_payload: dict` 字段——model_dump 存活、redact 保留、落到用户消息上 | app.py |
| Q8 summary 查看 400 | 前端 `receipt_id ?? summary_id` 兜底；后端 pilot_summary 收 `summary_id` 兜底、都无 id 时读 SUMMARIES_DIR 最新一份 | 两侧 |
| Q9 观察器等锁阻塞 run | `EvolutionStore.try_transaction(timeout)`：进程锁 acquire(timeout) + flock LOCK_NB 重试到 deadline；观察器事件写入与终态折回全走有界事务，超时只 stderr | store + run_observer |

放行条件对应证据：1=e2e 起第二个带 fixture 市场库的服务跑真浏览器建绑定；2=Q2 合同测试（注册→终态→自动 closed）；3=Q3 两条探针移植；4=Q5/Q6 重试与异载荷冲突测试；5=Q4 vitest 三条；6=三类收据的 python+vitest；7=Q9 非阻塞探针移植；8=最终 HEAD 全仓收据。

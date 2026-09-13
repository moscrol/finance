# 02 · 下一步研究排序 · 进度

规格：`docs/superpowers/specs/2026-09-13-research-evolution/02-research-priority.md`（规格提交 `194241dd`，总合同 `README.md`）。
状态：**engineering_complete**（模块真实计算、合同/负例/边界通过、01 在途真产物可消费）。product_verified 归 06；用户省时/更准归 05/03，本轨不宣称。

## 0. 开工登记

| 项 | 值 |
|---|---|
| 工作树 / 分支 | `/Users/a77/fwp-wt-research-priority-0913` · `feat/research-priority` |
| 基线 | 从 `docs/river-next-specs@28804505` 开树（= `gitea/main@5fb13a8c` 代码 + 9 份规格文档，零代码差异；`git diff --stat gitea/main` 只有 docs） |
| 规格来源 SHA | `194241dd`（规格）/ `28804505`（规格交接） |
| 解释器 | 主树 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（Python 3.12.13；新树无 venv，按 AGENTS.md 用主树绝对路径） |
| 实际用户态根 | 本轨**不触用户态**：包内不读文件/库/网络/时钟，owner 与输入对象由调用方注入。生产根由 06 用 `userspace.user_space(user).root` 解析并核实 `FORESIGHT_USERS_DIR`；本轨测试全部内存夹具，未写任何用户目录 |
| 代码地图 | 主树 `ready n=22076 @b4a35fa`（SessionStart 注入）；本轨按精确符号定位，未以地图结果断言能力缺失 |
| 计划修改路径（独占白名单） | `intelligence/services/research_priority/**`、`intelligence/tests/test_research_priority_*.py`、`intelligence/tests/fixtures/research_evolution/02/**`、本目录 |
| 最终提交 | `add35fc8`（09-06 终局对齐：hindsight / frozen_llm / 限制前置；夹具去家目录路径）← `46922d3f`（首版代码/测试/夹具/证伪收据）；文档提交 `fb41459b`、`6c33325b` |
| 分支映射（给 06） | 02 ↔ `feat/research-priority`（不带编号，本批不取工单号）；01 `feat/judgment-maintenance-01`、05 `feat/research-evolution-05-product-value`、规格 `docs/river-next-specs`；本分支基于规格分支，已携带 `194241dd`/`28804505` |

## 1. 任务 0：现役符号核对与映射

已在 5fb13a8c 读过（`[实测]`）：

| 现有载体 | 实际形状 | 02 的用法 |
|---|---|---|
| `research_queue.build_research_queue(decision)` | 四桶 `today_do_ima / today_find_official_evidence / today_wait_market_validation / today_downgrade_or_watch` + `skipped`，条目为中文键（目标/动作/理由/优先级/缺失证据层/建议动作…），**无 id、无对象引用** | 只读 → `explore`，全部 `legacy_unbound`（P11）；等盘面桶 → `waiting_release`；降级桶不生成任务；`优先级`（热度分）**不读** |
| `research_queue.extract_queue / wrap_research_queue_artifact` | 接裸队列或 `research-queue/v1` 包 | 适配器用 `extract_queue` 解包；`generated_at` 作 knowledge_cutoff（缺/裸时间戳 → null + gap） |
| `data_requests.DataRequest` | `request_id/dataset/table/window_*/fields/consumers[{run_id,user,question,conversation_id,…}]/fill_route{mode,condition,…}/priority/last_asked_at` | → `fill_gap`；`fill_route.mode==pending_sync` → `missing_data`（解除条件 = route.condition）；只保留 `user==owner` 的消费者，无则 skip 且不回显他人；绑定只来自调用方 `request_bindings` |
| `research_project.ResearchProjectState` / `ResearchTrigger` | `triggers[{kind=checkpoint,id,claim,due,status∈pending/due/hit/partial/miss/unverifiable,…}]`、`next_questions[followup card: question/kind/rationale…]`、`open_questions[str]` | 触发点 → `verify_due_condition`（绑定 `checkpoint` 对象，version 未知 → gap）；hit/partial/miss → skip `verdict_recorded`；unverifiable → `human_review_required`；下一问/未解问题 → `explore`/`fill_gap`，`legacy_unbound` |
| `foresight.rank_questions` | novelty/relevance/diversity + 兴趣加成 | **不复用、不覆盖**：02 是另一种明确的任务排序，两者并存 |
| `ranking_contract` | 公司排序矩阵 | 不改；02 输出不转换成荐股顺序 |
| `checkpoints.TERMINAL_VERDICTS` | `("hit","partial","miss")` | 适配器判「已裁决」的唯一依据 |

### 01 → 02 字段映射（合同 + 在途真产物均核对）

| 01 `MaintenanceItem` | 02 `ResearchTask` |
|---|---|
| `id` / `item_version` | `source={kind:maintenance_item,id,namespace:judgment-maintenance/v1,version_or_hash:item_version}`；`maintenance_item_ids=[id]` |
| `object_ref{kind,id,namespace,version_or_hash,ref,scope}` | `object_refs=[同形]`；缺 kind/id/ref → `legacy_unbound` + gap `dependency_unbound` |
| `current[]`（空则 `before[]`）`EvidenceVersion{ref,source_hash,derivation}` + `condition_ref/binding_id/binding_version` | `effect_evidence_refs`：`{kind:evidence,id:ref,namespace:derivation,version_or_hash:source_hash}` + `{kind:condition,id:condition_ref,namespace:binding:<id>,version_or_hash:binding_version}` |
| `change_type=condition_evaluated` ∧ `condition_result=true` ∧ `condition_role∈{abandon,downgrade}` | `abandon_or_downgrade`（**唯一**进第 1 组的路径） |
| `condition_evaluated` ∧ true ∧ role∈{upgrade,review} | `verify_due_condition` |
| `condition_evaluated` ∧ false | skip `condition_false` |
| `condition_evaluated` ∧ unknown/null | `verify_due_condition`，`condition_result=unknown`，有 gap → `missing_data`（解除条件列出 gap） |
| `content_changed / source_corrected / source_expired` | `review_changed_evidence`（第 2 组；P02） |
| `dependency_missing` | `fill_gap`（第 4 组） |
| `unchanged` | skip `no_change` |
| `status=closed/superseded` | skip；`rejudgment_requested` → skip `rejudgment_in_flight`；`snoozed` → 任务带 `management_status=snoozed` → deferred `user_snoozed` |
| `as_of / knowledge_cutoff / pit_grade / gaps` | 原样透传（01 真产物的 `knowledge_cutoff` 是**日期**，`condition_result` 是字符串，item 另带 `dependency_ref/condition_evaluation/first_known_day/management` 等 02 不认识的键——全部被接受） |

## 2. 交付物

- `intelligence/services/research_priority/`
  - `contracts.py`：schema 常量、`Policy`/`Budget`、`ContractError(code)`、`validate_task`、`identity_key`/`task_id_for`、时间解析（只解析不读钟；日期与 UTC 日历日比较；裸 datetime 拒绝）。
  - `adapters.py`：`adapt_candidates(source_records, context)`，四种 `kind`（`maintenance_report|maintenance_item|research_project|research_queue|data_request`），返回 `research-priority-candidates/v1 {owner_user_id, tasks[], skipped[{source,reason,detail}], synthetic}`。
  - `ranker.py`：`prioritize(candidates, policy, budget, evaluation_at, *, owner_user_id=None)` → `research-priority/v1`。
  - `render.py`：`render_view`（`research-priority-view/v1`，中文标签 + 全部 reasons + `click_payload{task_id,source_refs,conversation_id,scope,object_refs}`）、`render_markdown`。
- 测试 59 条：`test_research_priority_{contracts,ranker,adapters}.py`；夹具 6 份（全部 `synthetic: true`，无家目录字面量）。
- 收据：`receipts/mutation-01-*`、`receipts/mutation-02-*`（红）、`receipts/green-after-restore.txt`、`receipts/final-46922d3f.txt`、`receipts/final-add35fc8.txt`（绑定最终 SHA）。pytest 读数按 revision 取 `~/.finance-runtime/test-receipts/<时间戳>-<rev>.json`，不读 `latest.json`（六树并发会互相覆盖）。

### 验收场景对照

| 编号 | 测试 | 结果 |
|---|---|---|
| P01 | `test_p01_triggered_abandon_outranks_ten_hot_explorations` | 通过 |
| P02 | `test_p02_hash_only_change_becomes_review_not_abandon`、`test_hash_change_stays_in_group_two`、`test_abandon_without_observed_trigger_is_rejected_not_demoted` | 通过；M2 变异必红 |
| P03 | `test_p03_tomorrow_release_waits_today_condition_selectable` | 通过 |
| P04 | `test_p04_ten_minute_budget_defers_twelve_selects_six_and_four` | 通过（12 deferred，6+4=600s） |
| P05 | `test_p05_zero_budget_selects_nothing`、`test_p05_unknown_effort_is_not_zero_under_a_budget`、`test_p05_empty_input_yields_complete_zero_report` | 通过；M1 变异必红 |
| P06 | `test_p06_same_evidence_three_judgments_two_queues_become_one_task_with_all_sources`、adapters 同名 | 通过（6 来源 → 1 任务 3 对象） |
| P07 | `test_p07_same_text_different_entity_or_window_are_not_merged` | 通过 |
| P08 | `test_p08_fourth_critical_beyond_max_items_is_named` | 通过 |
| P09 | `test_p09_foreign_owner_is_rejected_without_leaking_their_id`、`test_p09_future_records_do_not_enter_scoring`、`test_maintenance_report_of_another_owner_is_rejected` | 通过 |
| P10 | `test_p10_reordered_and_reread_inputs_give_identical_report` | 通过 |
| P11 | `test_p11_legacy_queue_without_object_refs_is_unbound_group_five`（现役 `build_research_queue` 真生成） | 通过 |
| P12 | `test_p12_unknown_and_gaps_survive_and_every_item_reconciles`（合同夹具）+ `test_p12_real_01_assess_output_flows_through_unchanged`（01 在途真 `assess()` 产物） | 通过；见 BLOCKED §1 关于定稿重跑 |
| P13 | `test_p13_clock_crossing_changes_only_time_status_and_never_reads_machine_clock`（含源码级「不读钟」断言） | 通过 |

反向证伪：M1 把未知耗时按 0 计 → 2 红（P05 + effort_estimates）；M2 把 hash 变化当放弃触发 → 2 红（P02 + 冻结 golden）；恢复后 55/56 绿，`cmp` 字节一致，包内无 MUTATION 残留。收据文件带被测文件 sha256 前缀。

## 3. 给 06 / 05 的接口说明

**调用**：`adapt_candidates(records, {"owner_user_id", "conversation_id"?, "as_of"?, "knowledge_cutoff"?, "effort_estimates": {"<source.kind>:<source.id>": effort}, "request_bindings": {request_id: [object_ref]}, "synthetic"?})` → `prioritize(candidates, policy, budget, evaluation_at)`。`evaluation_at` 必须是带时区的时刻（`Z`/偏移），06 取可信 UTC 注入；历史重放显式给历史时刻。`policy` 缺省 `{policy_version: research-priority-policy/v1, max_items: 3, max_per_object: 1}`；`budget` `{minutes: number|null}`。`generated_at` 报告里为 `null`，由 06 渲染/落盘时填，不进 id/摘要。

**在 spec §4 之上的附加字段**（均为增量，不改既有字段语义）：任务 `human_review_required`（散文完成条件 / 机器判不了）、`availability_reason`（解除条件文字）、`management_status`（01 状态透传）、`merged_source_refs`（合并前全部来源）、`source_task_ids`、`synthetic`、`hindsight`（01 报告 / 调用方 context 透传；09-06 终局 §4.1「只供人工复核，不进校准」，与同证据的当前任务不合并、id 不同）；报告 `totals.{input_count,merged_count,deferred_count,blocked_count}`、`synthetic`、`hindsight`（任一任务为 hindsight 即整份报告标出并加 limitation，06 不得当作当前优先级渲染，03/05 不得计入统计）；`deferred[].detail/group`、`blocked[].release_condition/available_at`。候选包多一个 `skipped[]` 供对账（`prioritize` 只吃 `tasks`，06 展示 skipped 需自取）。

**与主树未提交的 09-06 终局设计段的对齐**（该设计段不在 gitea/main，按只读参考核对）：`pit_grade` 枚举与 main 代码一致（strict / trade_date_only / unverifiable），合并取最弱、区间同理；`knowledge_cutoff` 按交易日粒度比较，02 只解析不补时分；证据引用 `namespace=frozen_llm` 时理由带「可读不可重算」标记，分组不因散文改变（§4.2）；`render_markdown` 把限制与缺口放在入选前（§4.5 规矩 2）。**命名分歧留给 06**：09-06 §4.3 的 gap 形状是 `{track, reason, source_checked_at, retryable}`，02 沿用 01 的 `{reason, ref, checked_at, retryable}`；投影层若要统一，改字段名映射，不改两边语义。

**不荐股的边界**：只约束对外渲染。02 的 `scope.entity_refs` 与 `object_refs` 不过滤个股，01 维护的个股判断照常排序；理由与 limitations 由规则生成、不含方向性买卖措辞（测试 `test_reasons_are_generated_from_facts_and_never_promise_returns` 断言）。观察剧本硬门本批不动，下沉到渲染层留给下一批。

**任务 id**：`rt_` + sha256(合并键)，合并键 = 有证据引用时（owner, effect_kind, availability, 证据版本集合），否则（owner, effect_kind, availability, 归一问句, entity_refs, as_of, due_at, 绑定对象集合）。同一证据新增受影响判断不改 id；调用方自定 id 只保留在 `source_task_ids`。05 按 `task_id + policy_version` 关联曝光/选择/完成。

**错误码**（`ContractError.code`，整份输入拒绝）：`owner_missing / owner_mismatch / unknown_schema / unknown_source_kind / unknown_policy / unknown_policy_field / invalid_policy / invalid_budget / invalid_enum / invalid_ref / invalid_gap / invalid_effort / invalid_task / invalid_source / invalid_context / invalid_timestamp / naive_timestamp / evaluation_at_required / abandon_without_observed_trigger / unbound_flag_mismatch`。`owner_mismatch` 不回显对方 id。

**时间语义**：`due_at`/`available_at`/`knowledge_cutoff` 接受 `YYYY-MM-DD` 或带时区 ISO 时刻；日期按 UTC 日历日与 `evaluation_at` 比较（`2026-09-14` ≡ `2026-09-14T00:00Z`）。`as_of > evaluation_at 的 UTC 日` 或 `knowledge_cutoff > evaluation_at` → blocked `future_record`，不进入评分。`verify_due_condition` 且 `due_at > evaluation_at` → blocked `not_yet_due`；`waiting_release` 且 `available_at ≤ evaluation_at` → 视为 actionable。

**规则里的默认选择**（可由用户/06 调整，均记在 policy_version 内）：有预算时 `max_items` 仍生效；`max_per_object` 对未绑定任务不生效；合成任务耗时取已知估时最大值、`pit_grade` 取最弱、`as_of/knowledge_cutoff` 取最新；`critical_not_selected_ids` = 第 1 组中未入选的全部（含 snoozed）。

## 4. 未做 / 边界

- 用户显式置顶（`user_pinned`）v1 未实现（spec 允许），亦未从隐含兴趣推导。
- 02 不解析聊天正文、不发明绑定：研究项目的下一问与补数请求默认 `legacy_unbound`，只有 06 显式传绑定才进第 4 组。
- 队列/项目投影没有 pit_grade，02 标 `trade_date_only`（日频源），不是 strict。
- 本轨没有 CLI、没有 API、没有落盘；没有跑公共完整门禁（归 06 在最终候选上执行）。

## 5. 下一步

0. 规格目录目前只在 `docs/river-next-specs`（已推 gitea）；本分支带着它，04 分支重新提交了同内容，01/03/05 树里没有。先把纯文档分支合进 main 再各轨从 main 拉最干净——这一步等用户确认；同内容新增文件在最终合并时也能自动合。
1. 01 定稿后用其最终 revision 重跑 `assess()` 替换 `from_01_inflight_assess_report_synthetic.json`（见 BLOCKED §1）。
2. 06 接线：`GET …/research-evolution` 里 `priority` 段放 `render_view(prioritize(...))`；点击带 `click_payload`。
3. 05 按 `task_id + policy_version` 关联事件；策略变更升 `policy_version`。

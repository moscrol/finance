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

## 6. 2026-09-13 返修（评审 P1）

评审件：`/Users/a77/.finance-runtime/reviews/research-evolution-20260913/review.md`（需求符合性轴 P1，优先级 P1）。
返修基线 `a7c9dec1`，**最终 SHA `96aebada`**。

**缺陷**：同一 `binding:b1/c1` 条件的两次 true 观测（as_of 09-12 与 09-14），在 09-13 评估时
先被合并成一项、as_of 取最大，整项落进 `blocked(future_record)`；当天本应排第 1 组的关键条件
随之消失，`critical_not_selected_ids` 也为空（它只统计 `ranked` 内的第 1 组，blocked 不在其中）。
评审实得 `input_count=2, candidate_count=1, merged_count=1, selected_count=0, blocked_count=1`。

**根因与修法**（评审点名三处，逐处修）：

| 位置 | 根因 | 修法 |
|---|---|---|
| `contracts.py:identity_key` | 有 evidence 时合并键不含观测窗口 | 新增 `observation_window(task)` =（`as_of`, `knowledge_cutoff`），两条分支的键都带上它 |
| `ranker.py:prioritize` | 合并先于可知性校验 | 抽出 `_is_future_record` 供合并前分区与 `_block_entry` 共用；未来记录与当前记录各自合并 |
| `ranker.py:_merge_members` | 合并后 `as_of/knowledge_cutoff` 取最大 | 删除该路径（正是它把当天可知的记录抬成未来记录）；成员同窗口由合并键保证，沿用 head 值并加不变量断言 |
| `adapters.py` | 01 条件转 evidence ref 时丢了观测窗口 | 窗口写进 `ref.scope`；**不**写 `version_or_hash`（那一格是 binding 版本，塞日期会让版本字段说谎）|

**合并身份现在包含**：`owner_user_id`、`effect_kind`、`availability`、**观测窗口（as_of + knowledge_cutoff）**、
证据版本集合（无证据时再加归一问句、entity_refs、due_at、绑定对象集合）、hindsight 标记。
`as_of` 原先单独在「无证据」分支里，现由 `observation_window` 统一承担。
与 01 的 dedup_key 含「条件/观测窗口」同口径；spec §5.3「仅文本相似但对象或时间窗不同，不合并」。
**同一天同证据服务多个判断对象仍合成一个任务**（P06 口径不变，六条来源仍并成一项）。

**可知性校验现在的位置**：`validate_task` 之后、`_merge` 之前按 `_is_future_record` 分区。
合并键已含窗口，两侧本就不可能同键，这一步是显式的顺序保证——将来若有人放宽合并键，
未来记录仍不会把当天的关键条件一起吞进 blocked。代价是它无法被独立证伪（构造不出
「同键但一未来一当前」的输入），这一点写在这里，不冒充成有测试覆盖的防线。

**新增回归**（均调用真实 `prioritize` / `adapt_candidates`，未 mock 被测主体）：

| 测试 | 修前（a7c9dec1）红在哪 |
|---|---|
| `test_future_observation_window_does_not_swallow_today_critical_condition` | `assert report["totals"]["candidate_count"] == 2` → `assert 1 == 2` |
| `test_same_evidence_different_observation_window_is_not_merged` | `assert split[...]["candidate_count"] == 2 and merged_count == 0` → `assert (1 == 2)` |
| `test_condition_task_keeps_its_observation_window_across_two_01_reports` | `today_section == "selected"` → 实得 `'blocked'` |

**两处既有断言编码了缺陷行为，一并更新**（不是为了让测试变绿而放宽）：

1. `test_p09_future_records_do_not_enter_scoring` 末尾原断言「同一证据在两个市场日重复观测 →
   合并成一项，知识状态取最新的那次」。该口径正是 P1 的根因，改为两个候选各自保留 `as_of`。
2. `expected_combined_synthetic.json` 冻结的是 `task_id`，而 `task_id` = `rt_` + sha256(identity_key)
   的内容寻址结果，合并口径一变必然整批漂。该夹具 `_note` 写明「任何合同或规则变更都应让本文件
   变红后再有意更新」，这次就是那种情形。重生成前先逐项断言 id 无关内容不变：`totals` 相同、
   `selected` 的 `(rank, group, 来源集)` 相同、`deferred` 原因序列相同、`blocked` 原因多重集相同、
   `critical_not_selected_ids` 条数相同；唯一差异是 blocked 行的排序随 id 改变（该列表按 task_id 排序）。
   **输入夹具一字未动。** 同时给该测试补了一条 id 无关的落位断言（blocked 每行的 reason ↔ 来源 id），
   下次 id 漂移时语义回归不会跟着一起被放过。

**验证**：

```
cd /Users/a77/fwp-wt-research-priority-0913
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -p no:cacheprovider \
  intelligence/tests/test_research_priority_ranker.py \
  intelligence/tests/test_research_priority_adapters.py \
  intelligence/tests/test_research_priority_contracts.py
```

`62 passed, 0 failed, 0 skipped, exit 0`（基线 59 + 新增 3）。
收据 `/Users/a77/.finance-runtime/test-receipts/20260913T080414Z-96aebada.json`，`dirty=false`，
revision `96aebada8f5a4db866c177d5f6b0ba9c25f3b16c`。收据目录多树共用，按 revision 取时间戳文件，不读 `latest.json`。
`ruff check` 改动的 3 个服务文件 + 3 个测试文件全绿；提交时 11 道 pre-commit 门禁全过（层级审计 ERROR 0、路径字面量无新增、字段契约无新增）。

**评审探针修后实得**（`probe_01_02_04.py 02`，输入未改）：

| 字段 | 修前 | 修后 |
|---|---|---|
| `candidate_count` | 1 | 2 |
| `merged_count` | 1 | 0 |
| `selected_count` | 0 | 1（`critical_today`，group=1，as_of 09-12）|
| `blocked` | `future_record`，`source_task_ids=[critical_today, critical_tomorrow]` | `future_record`，`source_task_ids=[critical_tomorrow]` |
| `critical_not_selected_ids` | `[]`（因为关键条件消失了）| `[]`（因为关键条件已入选）|

**跨轨接缝**：`cross_module_probe.py` 三场景（complete / missing_source / legacy）全 PASS，含
「complete 里 condition_result=true 且 role∈{abandon,downgrade} 的 01 项仍进 selected」这条断言。
保存的 01 输出快照 `from_01_inflight_assess_report_synthetic.json` 与真实 01 树输出仍逐字节一致（除 generated_at）。
注意该探针里的 `module_tips` 是写死的字面量（仍写 02=a7c9dec1），不是从 git 读的，实际跑的是当前工作树。
01 正在被另一执行者返修；其 `assess()` 输出一旦变化，上面那份快照需按 BLOCKED §1 重取。

**未做**：全仓 / 前端 / registry / E2E 未跑（归 06 在最终候选上执行）；`user_pinned` 仍未实现（spec 允许）。

## 2026-09-13 QC 第二轮（扩大边界复审）

QC（`~/.finance-runtime/reviews/research-evolution-repair-qc-20260913/`）结论：原 13 项固定反例转绿，扩大边界确证 8 项，本轨 2 项。

- **S5[P2] 市场日误判未来**：`_is_future_record` 原用 UTC 日历日判市场日 as_of，清晨 07:00+08 误挡当天已知资料。修复：`contracts.py` 加 `MARKET_TZ = Asia/Shanghai` 与 `market_date_of` / `market_day_start`，as_of 按市场时区日历日判（cutoff 仍按真实时刻）；future_record 解除提示改真实时刻。
- **P2[P2] identity_key 缺执行窗口**：同证据不同 due_at/available_at 的任务先合并再判可执行性，互相拖入/拖出。修复：`identity_key` 两分支加 `execution_window`（折算 UTC 入键）。冻结 golden `expected_combined_synthetic.json` 经语义层闭锁后重生成（仅 id/digest 漂移）。
- 修复提交 **`a869028e`**；新增 3 条回归测试先红后绿；模块 65 passed；ruff 干净；QC 探针 S5/P2 组复跑转绿。注：时区探针会把 `.json` 产物写回 QC 目录，已刷成修后结果，复核以探针退出码为准。
- **06 联测请用 `a869028e`**。口径纠偏：上轮「13 项已修复」实为「原 13 项固定反例转绿」。

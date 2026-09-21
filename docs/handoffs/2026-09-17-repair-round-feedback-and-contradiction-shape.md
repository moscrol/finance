# 2026-09-17 修复轮病因回传 与 矛盾回执的合法形状（8f6e6eaa → d8ba0fb2）

分支 `fix/e2-material-closeout`，候选 `8f6e6eaa`（父 `c6151407`），随后追加 `d8ba0fb2`。未合 main、未部署。

## 背景

E2「只依据材料」这条线上，前几版把**写作合同**（单份 claim 渲染、逐句锚点）和**审查合同**
（逐 claim 回执、逐题回答回执、判官专用判词）都收紧了，离线门禁全绿。但在 `c6151407` 上做
三次真实会话时，三次都没能交付：

1. `run_20260916_231545_220949` — `failed`，`invalid_repair_finish`；
2. `run_20260916_231637_240608` — `partial`，judge `unavailable`；
3. `run_20260916_232506_213989` — `partial`，judge `rejected`（`material_nonfactual c3/c5`）。

## 发现顺序

1. 先怀疑「一句一绑定」太严。查了三次 run 的正文，作者写出来的句子本身并不违约——
   拒绝理由都对。**没有**去放宽约束。
2. 改查「拒绝理由有没有传到修复轮」。把三次 run 的 ledger 事件按 `invalid_action` /
   `repair_goal` / `model_input` 拉平（存档：工件根 `repair-feedback-evidence.json`），
   run 1 的形状是决定性的：

   | seq | 事件 | 内容 |
   |----|------|------|
   | 7 | invalid_action | `not_json_object` |
   | 8 | model_input | `steering_invalid_finish`（**只回灌了这一次**） |
   | 12 | invalid_action | `claim rendering requires one sentence per claim` |
   | 15 | repair_goal | `missing_answer_elements=[direct_answer, evidence_boundary]`、`unsupported_claims=[]` |
   | 17 | model_input | `repair_goal` |
   | — | invalid_action | 同一个 `bad_claim_binding`，`invalid_repair_finish` |

   即：**最后一次、也是最具体的那条病因只落了账，从未送到作者面前**；作者在修复轮只看见
   「缺哪个输出」，于是把同一份结构原样重发。
3. 顺着这条线查语义侧，发现 run 3 同形：判官逐句说清了 `c3/c5` 为什么不合格，
   `repair_goal.unsupported_claims` 仍是 `[]`。再查源头，
   `SemanticEpisodeOutcome.rejected_claim_indexes` **全仓没有任何写入点**——
   `unsupported_claims` 恒为空，这条策略信号从上线起就没生效过。
4. 另一条独立故障：`contradicted_absence` 对照里，判官正确识别了「本句说材料没给日期、
   锚点里却写着日期」，但只能写成 `supported=false, support_kind="unsupported",
   anchor_indexes=[1]`——协议里 `unsupported` 必须空锚点，整份报告被拒收，
   judge 降级成 `unavailable`。**判官是对的，协议没给它表达的词。**

## 改了什么（四处）

| # | 改动 | 为什么这么改 |
|---|------|-------------|
| 1 | `render_material_claims` 的一句一条错误改成 `evidence_boundary.claims[0] has 2 sentences` | 错误要能定位到病灶；作者原 payload 一字不改 |
| 2 | `resume()` 补发账上未送达的最后一次拒收（`model_input source=repair_last_rejection`），文案仍取 `harness.steering_message("invalid_finish")` | 不改回灌次数、不多花模型调用；已回灌过的不重复 |
| 3 | `RepairGoal.rejected_claim_notes`（原句 + 判官理由，私有坐标已替换为「该材料」） | 与策略信号 `unsupported_claims` 分开：前者只给作者看，不参与 `classify_repair_failure`，修复路由零变化 |
| 4 | `support_kind="contradicted"`（`supported=false` + **非空** `anchor_indexes`） | 给正确判断一个合法形状，而不是放宽解析或丢弃多余字段 |

## 被否掉的替代方案

- **放宽「一句一条」**：错的是反馈链，不是约束。放宽会让 claim 与句子重新错位，
  逐句锚点核验随之失效。
- **每次 finish 失败都回灌**：能让作者听见，但把失败次数变成模型调用次数，
  预算与死循环风险全落在真实运行上。改成「只补发没送达过的那一条」。
- **把 `unsupported_claims` 直接填上描述**：它是 `classify_repair_failure` 的输入
  （`not rejected_claims` 决定材料流能否走 input-only rewrite）。因为该字段今天恒空，
  填上等于**全局改修复路由**，没有证据支撑，另开一项。
- **解析层「抢救」自相矛盾的回执**（例如把 `unsupported+锚点` 当成拒绝、把
  `bound_material+空锚点` 改判 unsupported）：那是替模型改字段。`contradicted`
  给的是表达力，不是豁免；`bound_material+空锚点` 本就有 `unsupported` 可用，属判官写错。

## 收据（全部对 `8f6e6eaa`、干净树）

- 全仓：`11316 passed / 0 failed / 0 error / 83 skipped / 2 xfailed`，527.90s；
  收据 `/Users/a77/.finance-runtime/test-receipts/20260916T162320Z-8f6e6eaa.json`，
  `check_test_receipt.py --expect-revision 8f6e6eaa` 七项全过；`ruff` 通过。
- 前端：lint / typecheck / `vitest` 107P / build 通过；E2E `34 passed / 2 skipped`
  （需 `WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，
  此工作树没有 `.venv-workbench`，不设就会用 homebrew python 起不来服务）。
- 固定十例（真实判官，`scripts/material_claim_support_probe.py --live`）：**9/10**。
  `contradicted_absence` 首次通过，判官真的返回了 `contradicted`。
  `unbound_numbers` 这次红：判官写 `bound_material` 却给空 `anchor_indexes`，
  整份报告按协议丢弃 → `unavailable`。**未重抽、未改判据**。
- 三次自然会话（sidecar 8826，user `probe-e2-repair-feedback-0916`，health 实读
  revision `8f6e6eaafc2b…`、dirty=false、1093 模块）：**3/3 completed、judge passed、
  0 unavailable / 0 degraded**，答案 20% / 20% / 12.5%，证据边界里的缺项陈述
  （「未注明统计口径与所属日期」）被逐句核验通过。

## 新增回归

- `test_multisentence_error_locates_claim_without_rewriting_payload`
- `test_last_format_error_reaches_repair_writer_without_extra_attempt[False|True]`
  （两套 loop：`ContinuousAgentEpisode` 与 `HarnessReferenceLoop`）
- `test_repair_writer_reads_the_rejected_sentence_and_reason_not_a_bare_index`
- `test_anchor_that_contradicts_the_sentence_is_a_legal_rejection_not_a_dropped_report`
- `test_contradiction_receipt_still_cannot_claim_support_or_invent_anchors[4 种变异]`
- `test_contradiction_kind_is_offered_in_the_schema_and_explained_in_the_rule`

## 未验证的边界

1. 本轮三次自然会话**没有触发修复轮**（只有一次首轮格式失败，走的是旧的首次回灌）。
   所以第 2、3 两处改动在**真实修复轮**里尚未验过，只有离线回归 + 修前 run 的反证。
2. `unbound_numbers` 的判官自相矛盾没有解法落地，只是没被掩盖。
3. `rejected_claim_indexes` 死字段仍在：要么接上（并重跑修复路由的证据），要么删。
4. 缺项陈述的判据仍是同源模型判断；正式 T2→T3、跨轮五格、`local_only` 全读取面未验。
5. 离线绿 + 固定对照 + 三次自然会话都**不等于** D6/P7 验收。

---

# 追加：`d8ba0fb2` —— 修复轮要重述它仍然要求的成稿形状

## 新证据（先有现象再改码）

在 `8f6e6eaa` 上用一道「逼作者越界」的真实提问跑出 `run_20260917_004950_254515`：

- `repair_goal` 里**真的带上了** `rejected_claim_notes`：
  `claim_index:8｜原句：材料是一段43字的粘贴文本…｜判官：「43字」是事实性字数断言，本条锚点原文中不存在…`
  ——判官理由过桥这一条在真实模型上成立。
- 但这一集仍然 `failed`：修复稿把两句塞进一条 claim，
  `claim rendering requires one sentence per claim: evidence_boundary.claims[1] has 2 sentences`
  → `invalid_repair_finish`。**内容改对了，格式在最后一步失手。**

查 `repair_goal_message` 发现：修复轮只发 `REPAIR_GOAL` JSON（缺件 + 指令），
**从不重述它仍然要求的 wire 形状**；作者只能靠回忆开场的 `finish_format`。

## 改了什么

- `material_grounding.claim_finish_format(contract)`：把那份冻结模板抽成**单一构造点**，
  开场 payload 与修复轮共用（两处各写一份迟早漂移）。
- `harness.repair_goal_message(..., finish_format=None)`：传进来就原样重述；
  不传时消息逐字节不变，非 material 题型零变化。接缝目录 `docs/runtime/harness-seams.md` 同步。
- 两条 loop 各传降级后的合同（`downgraded_contract` / `downgrade.contract`）。

## 真实复验（sidecar 8826，health 实读 `d8ba0fb2e483`/dirty=false/1093 模块）

`run_20260917_011813_492269` 把三件事一次性证了：

| seq | 事件 | 含义 |
|----|------|------|
| 7 | invalid_action | `answer_q2.claims[0] has 2 sentences`——**坐标上线** |
| 8 | model_input `steering_invalid_finish` | 首次回灌（旧行为） |
| 12 | invalid_action | 同一错误再犯，只落账 |
| 15 | repair_goal | 四个输出全缺 |
| 17 | model_input `repair_last_rejection` | **尾次拒收原因过桥**（135 字） |
| 18 | model_input `repair_goal` | 1689 字，**含重述的冻结 wire 形状** |
| 23 | finish | `completed` / `repair_model_finish`——**修复稿被接受** |

同类形状在 `c6151407`（`run_20260916_231545_220949`）与 `8f6e6eaa`（`run_20260917_004950_254515`）
都死在 `invalid_repair_finish`。另两次真实会话（`…011446_084812`、`…011622_494649`）首轮就改对，
其中后者的拒绝理由正是带坐标的 `answer_q1.claims[0] has 2 sentences`。
事件存档：工件根 `live-repair-evidence.json`。

## 这次复验同时暴露的、没修的问题

`run_20260917_011813_492269` 最终仍是 `partial`：修复稿写出了「按行业常识…属于偏低水平」
这类材料外断言，而判官这次返回无效 tool call → `judge_status=unavailable` →
公开答案退化成一句「本次未完成独立复核（复核服务不可用）」。
扣下未复核的材料外断言是对的；但**判官不稳定时用户什么都拿不到**仍是未解决的产品问题，
是否改成「带未复核标识发出」属于用户级策略，本轮不自己决。

## `d8ba0fb2` 收据

全仓 `11318 passed / 0 failed / 0 error / 83 skipped / 2 xfailed`（805.62s），
收据 `20260916T171208Z-d8ba0fb2.json`，`--expect-revision d8ba0fb2` 七项全过；ruff 通过。
前端未重跑（本次改动不碰 webapp，上一份对 `8f6e6eaa` 的前端/E2E 结果仍成立）。
固定十例未重跑：本次不改判官侧，9/10 结论仍挂在 `8f6e6eaa`。

---

# 追加：`04d3c397` —— QC 复核发现扫描器过桥两处错，按 code 置位、把补发通道计入清零

## QC 怎么发现的（先有复现再改码）

对 `8f6e6eaa` 新增的 `unreported_invalid_finish` 做纯函数四向探测（`PYTHONPATH=. python -c …`，不起服务、不调模型）：

| 方向 | 事件序列 | 修前返回 | 应为 |
|---|---|---|---|
| 一次失败已回灌 | invalid_action → steering_invalid_finish | 空 | 空 |
| 第二次失败未回灌 | … → invalid_action(Y) | Y | Y |
| **自己送达后进下一轮** | … → invalid_action(Y) → repair_last_rejection → repair_goal → finish | **Y** | 空 |
| **计划错误已走别的通道** | invalid_action(PLAN_ERR) → steering_invalid_plan | **PLAN_ERR** | 空 |

第三行可达：这次探针合同 `research_tier=max`，`max_repair_cycles_for_tier` 给三轮，
`continuous_turn_adapter` 的 while 循环只要还有 `gap_output_ids` / `missing_outputs` 就带累积账本再进 `resume()`。
第四行意味着作者会读到「上一条终止输出无效」而实际错的是计划。

两条 loop 的六个 finish 驳回点（`admit_finish` 两处、修复轮驳回四处）都在 `invalid_action` 里写了 `code`（rejection_code）；
计划错误（`agent_episode.py:1704` / `harness_reference_loop.py:350`）与终局阶段调工具（`:1720` / `:366`）不带 `code`。
扫描器此前只读 `reason`。

## 改了什么（`04d3c397`，emit 点与两条 loop 零改动）

- 置位集合：只收带 `code` 的 `invalid_action`；`code` 缺失一律不欠（宁少发不误发）。
- 清零集合：`_INVALID_FINISH_DELIVERY_SOURCES = {steering_invalid_finish, repair_last_rejection}`，把补发通道自己算进去。
- 回归：`test_episode_messages.py` 纯函数七向（含 `own_delivery_clears_before_next_cycle`、`plan_error_steered_on_its_own_channel`、
  `new_rejection_after_own_delivery_is_owed`）；`test_e2_material_claim_rendering.py`
  `test_second_repair_cycle_does_not_resend_the_rejection_it_already_delivered[False|True]`：两条 loop 连续两次 `resume()`，
  `repair_last_rejection` 恰一次、第二轮开场历史里该错误只有一份。
- 修前六条全红（own_delivery `'Y' != ''`、plan `'PLAN_ERR' != ''`、两 loop `carried 2 != 1`），修后五个相关测试文件 235P。

## 被否掉的替代方案

- **给 `repair_last_rejection` 之后的 `invalid_action` 也清零**：清零只能由送达事件触发，不能由下一次失败触发，否则新失败会被吞。
- **在 emit 点新增「是否终局拒收」布尔字段**：`code` 已是结构化的终局拒收标记，再加一个字段是第二事实源。
- **把 hrl:650（修复轮调工具，`disposition=invalid_repair_finish`，无 `code`）补上 code**：它与 agent_episode 的 `repair_tool_during_finish`
  不对称，但该分支终局停机、不会再有修复轮读它；留作已知不对称，不在本 PR 扩面。

## QC 同时核过的其它事（全部 [实测]）

- 真实 run `011813` 的修复轮消息里 `finish_format` 与开场提示那份规范化后逐字节相同；`repair_last_rejection` 135 字正文
  即 harness `invalid_finish` 文案。修前 `004950` 的修复轮消息 776 字、无 `finish_format`。
- 十例 `expectation_matched` 9/10，十行全钉在 `8f6e6eaa` 干净树；8f6e6eaa 三次自然会话 completed + judge passed；
  c6151407 三次 failed / unavailable / rejected。
- 判官「returned an invalid tool call」在 21 次探针 run 里出现 3 次，跨 8636a2a2 / c6151407 / d8ba0fb2，且都是 `correlated_judge=true`：
  不是偶发，是这条线第二大交付杀手，未修。
- 8826 无监听；8792 healthy、`ce009718`、`source_dirty=false`，本轮未碰。
- 上一版 inflight 在推送前写成「HEAD d8ba0fb2、d8ba0fb2 待推」，与实际（7e3da7ba 已推）不符，本版已改为可实读的表述。

## `df74042c` 收据（`04d3c397` + forward-merge `gitea/main@18859d37`，干净树）

- python：`11586 passed / 0 failed / 0 error / 83 skipped / 2 xfailed`（530.58s），收据 `20260917T021523Z-df74042c.json`，
  `check_test_receipt.py --expect-revision df74042c --base-drift-max 5` 八项全过、基座漂移 0；ruff 通过。
- 前端：lint / typecheck / vitest 107P / build 通过，build 后 porcelain 为空（`intelligence/api/static` 三个已跟踪产物逐字节不变）。
- E2E：`34 passed / 2 skipped`（1.0m，`WORKBENCH_PYTHON` 指主树 venv-workbench）。
- registry：`build_registry.py check` / `check-parseability`（61 个 SKILL.md）/ `generate-views --check` / `check_path_literals.py` 全过。
- 日志：`~/.finance-runtime/e2-material-closeout-df74042c/{python-gate.log,frontend-gate.log,frontend-e2e.log,python-gate.receipt}`。
- 未重跑：固定十例与真实自然会话（不改判官侧、不改 emit 点；修正的分支只在第二轮修复与计划错误路径上可达，离线回归已钉两条 loop）。

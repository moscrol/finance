# 2026-09-17 修复轮病因回传 与 矛盾回执的合法形状（8f6e6eaa）

分支 `fix/e2-material-closeout`，候选 `8f6e6eaa`（父 `c6151407`）。未合 main、未部署、未推远端。

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

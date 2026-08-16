# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_NOT_CONFIRMED
- mode: M1
- failure_criterion: 四层修复合入后（8792=`773b3d7e`），原题「基于8.15的行情现状，你认为周一的机会在哪」须在生产预算内完成核验，公开答案保留条件化判断正文，且 `report.status=completed`。主样本 `run_20260816_131941_597875` 公开答案 134 字纯边界兜底、`report.status=partial`、`degrades` 含「证据或语义核验未完全通过，已按证据边界降级。」，判定失败。第 4 层诚实降级本身不计入本条失败。
- trace_coverage: 主样本 `trace.jsonl`（19 步）+ `continuous-episode.json`（22 个原生 event）+ `stream.jsonl` + `report.json`/`answer.md`/`run.json`。对照：修前同题 `run_20260816_102941_554059` / `run_20260816_103318_230845`；handoff 所标 L04 反例 `run_20260816_125920_927309`。旁证（不并入 PRIMARY）：窗内 `off:L05` `run_20260816_132541_309060`。**缺**：首轮合成 `model_turn` 没有 `timeout_asked` / `remaining_ms_at_entry`；compose 请求体 token 未入账（`usage.input_tokens=10672` 只含规划轮）；未做 #72/#79 单变量重放。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Prior prediction closure

本被审系统已有标准分诊账本，不是 `no prior report`。下列 pending 用本次 L01 产物回填；未触及的保持 `still_pending`。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 2026-08-15 B 组 M1 F-001 | R-20260815-04 | `outcome` 落盘补 `draft_source ∈ {model_returned_empty, truncated_by_budget, provider_error}` 与合成入口 `remaining_ms` 后，下一次空 draft 的 turn 其 `draft_source` 非空，可据以在 REASONING 与 HARNESS 之间定夺 F-001 的 L0 | still_pending | E-006 | 本 run 又是空 draft，`draft_source` 仍为 `None`。区分信号改走 `gaps=['LLM 调用失败（TimeoutError）']` 与 `stop_reason=repair_model_unavailable`，字段补齐仍未做，不得写 confirmed |
| 轨道 A M1 F-001 | R-20260815-21 | 全格 `evidence_hashes`+非空 `binding.gap` 的 partial FINAL_JSON 经 `validate_episode_finish` 后… | still_pending | 无 | 本 run `bindings=0`，不是滑档形状，不能回填 |
| 2026-08-15 B 组 | R-20260815-01 / 02 / 03 | evidence_bound 三元组 / `not_run` 分母 / answer_coverage 同判据 | still_pending | 无 | 本 run 不是那 19 个验收 turn |
| L7 finalization T3 | R-20260804-10 | deadline-aligned per-tool handoff… | still_pending | 无 | headless 路径，本 run 未触及 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `HARNESS_FIX` = 1（沿用 R-09）；`EVAL_ONLY` = 1（沿用 R-02）。本轮无新 refuted，不累计。

## Executive finding

第一处可观察的错误变换是检索已经成功之后的**首轮合成 LLM**：`events[seq=12] model_turn` 在 68.3s 后报 `TimeoutError`，`content=""`，`carried_draft_chars=0`。修复轮再拿两次 30s grant（`timeout_configured=75`）全部超时，judge 因 structural fulfilled=0 被跳过，公开答案走 `#327` 缺口模板 + `evidence_gap_fallback`。#72 路由已生效（`direct_answer.grounding_mode=model_reasoning`）；#75/#79 从未见到草稿，不能当成本次丢正文的刀。**未确认**超时是 #72 提示变重、第四次 `stock_high_daily` 扩容、还是 provider 慢——首轮合成没有 `timeout_asked`，L0 在「合成超时」与「装配层预算/契约冲突」之间定不了。

## Expected vs actual path

本地词表（workbench `step_id`/`event.kind`）↔ L1 九步，按 `docs/trace-profile.md` §6 投影。损耗：`verification` / `repair_goal` 不在 workbench 子串表里，归一化可能落 `unmapped`，不得就近塞进 `observe`/`plan`。

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 观点题判断槽走 `model_reasoning`，边界槽保持 `evidence` | `direct_answer=model_reasoning`，`evidence_boundary=evidence`（#72 已装上） | ok | E-005 |
| intent | 识别为需检索的观点题 | `lane=research`，`needs_retrieval=true`，`question_type=general_finance_qa` | ok | E-001 |
| plan | 形成检索后合成 | 无独立 `mode_decision` 事件；规划轮 22s 后一次打出 4 个 `finance_query` | ok | E-002 |
| retrieve | 取到可核验盘面 | 4 次工具均 `ok`，~75–80ms，入账 60 条 | ok | E-003 |
| synthesize | 在剩余 grant 内产出 FINAL_JSON / 非空 draft | seq=12 `TimeoutError`，draft 空；墙钟 13:20:03→13:21:12 | **fail** | E-004 |
| observe | 忠实读取超时与空 draft | `gaps` 留下 TimeoutError；stream 仍写「研究回答已形成」「核验已完成」 | fail（话术） | E-009 |
| synthesize | 修复轮补出判断正文 | 两次 repair `timeout_asked≈30` 均 TimeoutError；`repair_cycles=0` | fail | E-007 |
| stop | 诚实降级；判断句存活 | `evidence_gap_fallback` 边界句；`report.status=partial`（诚实闸有效）；判断句未存活 | **fail** | E-008 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260816_131941_597875` / episode `seq=12` `model_turn` | UNCLEAR（HARNESS/synthesize vs HARNESS/configure） | synthesize | DEPTH_INSUFFICIENT(D4) | `"error":"LLM 调用失败（TimeoutError）","content":""` | medium |
| `run_20260816_131941_597875` / episode `seq=17`/`seq=19` repair `model_turn` | HARNESS | stop | `execution-error-category-timeout` | `timeout_asked≈30`，`timeout_configured=75.0` | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 首轮合成 LLM 超时，draft 从未写出 | 若成立，第一次 `finish` 前应有 `model_turn.error=TimeoutError` 且 `carried_draft_chars=0` | E-004, E-006 | CONFIRMED | — | seq=12 原文即此；seq=14 `deadline_exhausted` + `carried_draft_chars=0` |
| H2 | #72 把判断槽改成 `model_reasoning` 后，合成提示变重，同一 grant 不够 | 若成立，修前同题首轮合成应明显更短或带更小 input；本 run 首轮 `timeout_asked` 应接近剩余研究窗而非 75 | E-005, E-010 | INCONCLUSIVE | 记录首轮 finalize `model_turn` 的 `timeout_asked` 与 input tokens；H2 预测 asked≈剩余窗且 input>pre1 的 17024，若 asked=75 且 input≤17024 即证伪 | #72 合同差已看见；因果要 D4 的 asked/token |
| H3 | 多出来的 `stock_high_daily`（60 对 35 条）把合成拖过 grant | 若成立，去掉第 4 次查询后同 revision 应能在 30s 修复窗内写出 draft | E-003, E-010 | INCONCLUSIVE | 同题同 revision 冻结 3-tool 对照；若 3-tool 仍 TimeoutError 即证伪「多 25 条是充分条件」 | 第 4 次工具是模型自选，不是 #79 比较集展开（#79 要先有草稿） |
| H4 | 150s 烧在 judge / 核验 LLM | 若成立，应有 judge 调用或 `correlated_judge=true` | E-008 | REJECTED | — | `judge_status=unavailable`，`_can_semantically_release_partial` 因空 draft + fulfilled=0 为假，judge 未调用 |
| H5 | L04 37s completed 证明核验路径本身能跑完 | 若成立，L04 应走 continuous episode + verification/repair | E-011 | REJECTED | — | L04 `lane=chat`，`needs_retrieval=false`，无 episode，不是核验成功 |
| H6 | 只是 provider 偶发变慢 | 若成立，同日同题不应稳定复现 ~150s 空 draft | E-004, E-010, E-012 | INCONCLUSIVE | 同题 ≥3 次 ready 绿重放，记录首轮合成是否 TimeoutError；命中率 <2/3 则倾向 H6，≥3/3 则排除偶发 | 修前同题合成 20s 成功；L05 同窗首轮合成成功，说明不是「当天下午 LLM 全死」 |

## Causal findings

### PRIMARY

- failure_span_id: `run_20260816_131941_597875` / episode `seq=12` `kind=model_turn`
- root_location: continuous episode 首轮 finalization 合成（`retrieval_deadline_closed` 之后）
- excerpt: `"sequence":12,"kind":"model_turn","payload":{"content":"","error":"LLM 调用失败（TimeoutError）","provider_attempts":1,"at":"2026-08-16T13:21:12.251+08:00"}`
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-003, E-004, E-006]
- explanation: 四个 `finance_query` 已成功、60 条证据在账，状态仍正确。下一跳合成 LLM 返回 TimeoutError 且空 content，第一次 `finish` 即 `deadline_exhausted` / `carried_draft_chars=0`。这是第一处「正确→错误」。超时本身是执行层事实，但**不能**在「grant 不够」「#72 提示变重」「多查了一张表」「provider 慢」之间定 L0/L2 子因——首轮 `model_turn` 没有 `timeout_asked`，故 L0=UNCLEAR、L2=`DEPTH_INSUFFICIENT(D4)`。

### SECONDARY / TERTIARY

- F-002 SECONDARY：修复轮 `granted_seconds=30`、`timeout_asked≈30`、`timeout_configured=75`，两次 TimeoutError，`stop_reason=repair_model_unavailable`。30s 帽写在 `repair_coordinator._REPAIR_SECONDS_CAP`。空 draft + 工具关闭时，修复不可能比首轮合成更快，这是传播，不是独立根因。
- F-003 TERTIARY：structural 两格 `missing` → `_can_semantically_release_partial` 为假 → judge 跳过 → `_gap_answer` 产出「已取得 60 条证据，但未完成核验绑定」→ stream `phase=evidence_gap_fallback`。这是 #327 缺口镜像的**预期** fail-closed，不是意外交互。第 4 层 `uncheckable_judgment_empty` **没有**触发（`marker_coverage=complete`，`warnings=[]`），因为缺口模板句「现有证据不足，暂不能可靠回答」被 `answer_has_non_boundary_substance` 当成非边界正文。诚实降级走的是 `report.status=partial` + degrade 文案，不是 marker 警告。

## Evidence → Finding → Path

### Evidence

### E-001
- title: 主样本路由到 research 而非 chat
- run_id: run_20260816_131941_597875
- step_or_span_id: trace `controller`
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/longtail-ab-0816/runs/run_20260816_131941_597875/trace.jsonl` L002
- observed_at: 2026-08-16T13:19:41+08:00
- raw_excerpt: |
    `"decision": {"lane": "research", "needs_retrieval": true, ..., "question_type": "general_finance_qa", "confidence": 0.78}`
- observation: 控制器把原题送进 continuous research。
- confidence: high

### E-002
- title: 规划轮一次打出四次 finance_query
- run_id: run_20260816_131941_597875
- step_or_span_id: episode `seq=2` `model_turn`
- native_or_normalized: native
- source_type: trace
- source_ref: `continuous-episode.json` events sequence=2
- observed_at: 2026-08-16T13:20:03.867+08:00
- raw_excerpt: |
    `provider_attempts=1, input_tokens=10672, output_tokens=996, datasets=[market_daily, mainline_sector_daily, sector_daily, stock_high_daily]`
- observation: 规划成功；比修前同题多一次 `stock_high_daily`。
- confidence: high

### E-003
- title: 四次检索都成功，约 1s 内完成
- run_id: run_20260816_131941_597875
- step_or_span_id: episode `seq=4,6,8,10` `tool_result`
- native_or_normalized: native
- source_type: tool_return
- source_ref: `continuous-episode.json` events sequence=4/6/8/10
- observed_at: 2026-08-16T13:20:03.960+08:00
- raw_excerpt: |
    `ok=true; elapsed_ms=75.6/74.0/73.0/80.4; evidence lens=1/9/25/25; outcome.evidence=60`
- observation: 检索侧不是失败点。随后 `finalization.reason=retrieval_deadline_closed`。
- confidence: high

### E-004
- title: 首轮合成 TimeoutError，空 content
- run_id: run_20260816_131941_597875
- step_or_span_id: episode `seq=12` `model_turn`
- native_or_normalized: native
- source_type: log
- source_ref: `continuous-episode.json:2393-2403`
- observed_at: 2026-08-16T13:21:12.251+08:00
- raw_excerpt: |
    `{"sequence":12,"kind":"model_turn","payload":{"content":"","tool_calls":[],"error":"LLM 调用失败（TimeoutError）","provider_attempts":1}}`
- observation: 合成从 13:20:03.973 等到 13:21:12.251（68.3s）后失败。该事件没有 `timeout_asked`。
- confidence: high

### E-005
- title: #72 判断槽路由已写入合同
- run_id: run_20260816_131941_597875
- step_or_span_id: `contract.required_outputs`
- native_or_normalized: native
- source_type: file
- source_ref: `continuous-episode.json` contract.required_outputs；对照代码 `fwp-wt-deploy-main/intelligence/services/episode_factory.py:312-321`
- observed_at: 2026-08-16T13:19:41+08:00
- raw_excerpt: |
    本 run：`direct_answer.grounding_mode=model_reasoning`，`evidence_boundary.grounding_mode=evidence`。修前两 run：两槽都是 `evidence`。
- observation: 装配层相对 `437cd5e9` 的可见差是 #72。#75/#79 需要非空 draft，本 run 没有。
- confidence: high

### E-006
- title: 第一次 finish 已是空 draft + deadline_exhausted
- run_id: run_20260816_131941_597875
- step_or_span_id: episode `seq=14` `finish`
- native_or_normalized: native
- source_type: log
- source_ref: `continuous-episode.json` events sequence=14
- observed_at: 2026-08-16T13:21:12.251+08:00
- raw_excerpt: |
    `status=partial, stop_reason=deadline_exhausted, carried_draft_chars=0, time_budget_injected=true, gaps=["研究截止时间已到，仍有必需输出未覆盖"]`
- observation: 修复开始前 draft 已空。`outcome.draft_source` 仍为 `None`。
- confidence: high

### E-007
- title: 修复两次 30s grant 都超时
- run_id: run_20260816_131941_597875
- step_or_span_id: episode `seq=16` `repair_reentry` / `seq=17` / `seq=18` / `seq=19`
- native_or_normalized: native
- source_type: log
- source_ref: `continuous-episode.json:2462-2530`
- observed_at: 2026-08-16T13:21:12.268+08:00
- raw_excerpt: |
    `granted_seconds=30.0, timeout_asked≈29.996, timeout_configured=75.0, research_tools_open=false, previous_draft_chars=0`；随后两轮 `error=TimeoutError`；终态 `stop_reason=repair_model_unavailable`，`repair_cycles=0`。
- observation: 修复时钟是 30s 帽，不是 75s LLM 配置。第二次 30s 来自 transient retry。
- confidence: high

### E-008
- title: 兜底句来自 #327 缺口模板，judge 未调用
- run_id: run_20260816_131941_597875
- step_or_span_id: `semantic_verifier` + stream `continuous:answer`
- native_or_normalized: native
- source_type: file
- source_ref: `continuous-episode.json` semantic_verifier；`stream.jsonl` seq=24；代码 `episode_semantic_verifier.py:1699-1708` 与 `:1763-1779`
- observed_at: 2026-08-16T13:22:14+08:00
- raw_excerpt: |
    `judge_status=unavailable; metrics.semantic_status=unavailable; public_answer 含「本轮已取得 60 条证据，但未完成核验绑定」; stream phase=evidence_gap_fallback; structural issues=["missing required output: direct_answer","missing required output: evidence_boundary"]`
- observation: 文案由 `_gap_answer` 在 judge 之前生成。#75 relabel 与 #79 比较集绑定未执行。
- confidence: high

### E-009
- title: self_report_vs_observed 机器状态与话术冲突
- run_id: run_20260816_131941_597875
- step_or_span_id: `run.json` / `report.json` / stream progress
- native_or_normalized: native
- source_type: file
- source_ref: `run.json` status；`report.json` status；`trace.jsonl` L013/L017
- observed_at: 2026-08-16T13:22:14+08:00
- raw_excerpt: |
    `run.status=completed` 且 `error=null`；`report.status=partial` / `research_status=partial`；progress「研究回答已形成」「核验已完成」；`degrades=["证据或语义核验未完全通过，已按证据边界降级。"]`
- observation: 运输层 completed 与研究层 partial 并存。用户可见诚实信号在 report/degrades，不在 run.status。
- confidence: high

### E-010
- title: 修前同题合成成功，修复 12–13s 写出判断草稿
- run_id: run_20260816_102941_554059
- step_or_span_id: episode `seq=12` / `seq=17` / `seq=19`
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/default/runs/run_20260816_102941_554059/continuous-episode.json`（sha256 `a08904524a782071…`）
- observed_at: 2026-08-16T10:30:25+08:00
- raw_excerpt: |
    首轮合成 `content` 772 字、`input_tokens=17024`、约 20s、`error=""`；修复 `timeout_asked≈30` 且 13s 内 `repair_model_finish`；`draft` 含「基准判断」；公开答案被 judge 剥到 210 字。`grounding_mode=evidence`。三工具，35 条证据。
- observation: 修前失败在「剥句 + completed 出厂」，不在「合成超时」。pre2 首轮也曾 TimeoutError，但修复 12s 救回。
- confidence: high

### E-011
- title: handoff 的 L04 反例走 chat 车道
- run_id: run_20260816_125920_927309
- step_or_span_id: trace `controller` / `generate`
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/longtail-ab-0816/runs/run_20260816_125920_927309/trace.jsonl` L002-L004
- observed_at: 2026-08-16T12:59:39+08:00
- raw_excerpt: |
    `"lane":"chat","needs_retrieval":false`；无 `continuous-episode.json`；37s `report.status=completed`。
- observation: 这是 GRAPH/route 分叉，不能证明核验预算够用。
- confidence: high

### E-012
- title: 同窗 L05 也是 ~159s degraded，但内部不是空 draft
- run_id: run_20260816_132541_309060
- step_or_span_id: `semantic_verifier` / `outcome`
- native_or_normalized: native
- source_type: file
- source_ref: `users/longtail-ab-0816/runs/run_20260816_132541_309060/continuous-episode.json`
- observed_at: 2026-08-16T13:28:20+08:00
- raw_excerpt: |
    `draft` 279 字、`bindings=2`、`stop_reason=repair_model_stop`；`judge_status=unavailable`；issues 含 `semantic judge transient provider error`；公开答案是「候选草稿」+ 主观基准判断，不是「未完成核验绑定」。
- observation: 墙钟相近不等于同一机制。L05 是 field-trap 里「混槽 + judge 瞬时失败 → 候选草稿」那条。
- confidence: high

### Findings

### F-001
- title: 首轮合成超时清空 draft（第一处错误变换；子因未分胜负）
- status: validated
- failure_span_id: episode `seq=12`
- root_location: continuous episode finalization compose
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- violated_authority: none
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-003, E-004, E-006]
- confidence: medium
- explanation: WHAT：合成超时，draft 空。WHY：事件原文是 TimeoutError，不是模型写空。IMPACT：后续修复/judge/公开答案全部建立在空稿上。子因（grant / #72 / 第 4 次查询 / provider）缺 D4 变量。

### F-002
- title: 30s 修复帽对空稿不可恢复
- status: validated
- failure_span_id: episode `seq=16`–`seq=22`
- root_location: `repair_coordinator._REPAIR_SECONDS_CAP=30` + `agent_episode` repair_reentry
- l0: HARNESS
- l1: stop
- l2: execution-error-category-timeout
- l3: n/a
- violated_authority: system
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-007]
- confidence: high
- explanation: 修复 asked≈30、configured=75。首轮已经 68s 写不出，30s 再试两次仍超时。这是传播，不是独立 PRIMARY。

### F-003
- title: 「未完成核验绑定」是 #327 预期缺口模板，不是 judge 剥句
- status: validated
- failure_span_id: `semantic_verifier` / stream `evidence_gap_fallback`
- root_location: `episode_semantic_verifier._gap_answer` + `_can_semantically_release_partial`
- l0: HARNESS
- l1: observe
- l2: configuration-mismatch-category-tool-definition
- l3: n/a
- violated_authority: none
- causality: TERTIARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-008, E-009]
- confidence: high
- explanation: WHAT：用户看见边界兜底。WHY：空 draft 使 judge 合法跳过，模板按设计说话。IMPACT：与修前「draft 满、repair 剥、completed 出厂」不是同一形状。`uncheckable_judgment_empty` 未响，layer 4 的 marker 闸没看见这个模板。

### Path

### P-001
- title: 检索成功 → 合成超时 → 修复再超时 → 缺口模板出厂
- start: seq=11 `finalization.reason=retrieval_deadline_closed`，60 条证据在账
- goal: 判断句存活且核验完成
- steps:
  1. 规划+四次检索成功 — evidence: E-002, E-003 — finding: none
  2. 首轮合成 TimeoutError，draft=0 — evidence: E-004, E-006 — finding: F-001
  3. 修复 30s×2 再超时 — evidence: E-007 — finding: F-002
  4. judge 跳过，`evidence_gap_fallback` 出厂 — evidence: E-008 — finding: F-003
- residual_uncertainty: 首轮合成的 `timeout_asked` 与 input token 未知，故不能把超时归到 #72、第 4 次查询或 provider 慢中的单独一刀。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260816-01 | F-001 | HARNESS_FIX | 首轮 finalize `model_turn` 落盘 `timeout_asked` / `remaining_seconds_at_entry` / input tokens，与 repair_reentry 三字段对齐。不先调大预算。 | 下一次空 draft 超时 run 的 seq=12 payload 含 `timeout_asked`；能直接比较 asked 与 68.3s 墙钟 | 离线单测：finalize 路径必写这三个字段；缺字段测试红 |
| R-20260816-02 | F-002 | HARNESS_FIX | 若要动预算：按 2026-08-08 换型先例给延迟实测，说明 30s 修复帽对「空稿+工具关闭」不可恢复；禁止只把 T 或 30 调大当修复。 | 修复建议落地后，同题重放要么首轮合成成功，要么 repair 的 `timeout_asked` 不再小于首轮已观测的合成墙钟 | 全路由影响面表 + 非观点题对照不得变慢超 5pp |
| R-20260816-03 | F-001 | EVAL_ONLY | 同题单变量：只开 #72（3-tool）vs 只加第 4 次查询 vs 当前四层全开。长尾窗收口前不占 8792。 | 三臂收据能单独证实或证伪 H2/H3 | 夹具冻结 as_of=2026-08-14；禁止把 L04 chat 臂当对照 |
| R-20260816-04 | F-003 | EVAL_ONLY | 登记：`uncheckable_judgment_empty` 对 #327 缺口模板不响（「现有证据不足…」被当成非边界正文）。layer 4 诚实性目前靠 `report.status=partial`。 | 用本 run `answer.md` 跑 `evaluate_marker_coverage` 仍得 `warnings=[]`、`marker_coverage=complete` | 单测钉住该模板形状；若要改探测器，另开观测台，不并 B 组编号 |
| R-20260816-05 | F-001 | EVAL_ONLY | 不要把 off:L05 ~159s degraded 并进本形状。L05 是候选草稿 + judge 瞬时失败。 | 分诊/观测台把 L01 空稿与 L05 候选草稿分成两行 | 本报告 E-012 作回归夹具 |

- auto_apply: false

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| 首轮合成无 `timeout_asked` | H2：grant 是 75 还是剩余研究窗 | `timeout_asked`；H2 预测 <75 且 ≈ remaining，观测到 =75 且墙钟≈75 则更像 LLM 硬墙 | finalize 前那次 `complete()` 入口，与 repair_reentry 同字段 | #72/扩容 vs 配置 75s 硬墙 | 低，只加标量 |
| 合成 input tokens 未入账 | H3：60 条是否把 prompt 撑大 | `input_tokens`；H3 预测 > pre1 的 17024，若 ≤17024 仍超时则证伪扩容充分性 | 同一次 `model_turn` payload | 能否单独怪第 4 次查询 | 低 |
| L05 被 handoff 写成「同形」 | 用墙钟合并机制 | 终态三元组 `(stop_reason, draft_len, judge_status)`；L01=`(repair_model_unavailable,0,unavailable)`，L05=`(repair_model_stop,>0,unavailable)` | 窗收据聚合 | 151–159s 是一类还是两类 | 低 |

## Limits and counterevidence

- 主 checkout 的 `episode_factory._grounding_mode` 仍是修前默认 `evidence`。运行时代码以 `fwp-wt-deploy-main` @ `773b3d7e` 为准。
- 未占 8792，未重放。H2/H3/H6 不能在本材料上分胜负。
- L04 不能当核验成功反例。窗内后一次 L04（`run_20260816_132508_671289`，32.6s）同样没有 episode。
- 修前 pre2 首轮也 TimeoutError，但 30s 修复救回——说明 30s 帽不是永远不够，只对**已经空稿且合成本身 >30s** 的形状不够。
- 第 4 层诚实闸（`report.status=partial` + degrade）按设计生效，不是回归。
- 不把 2×75 写成结论：本 run 修复 asked 是 30；首轮 68.3s 更像剩余研究窗，但没有 asked 字段。

## Next-step menu

1. 给首轮 finalize `model_turn` 补 `timeout_asked` + input tokens（R-20260816-01），这是切开 H2/H3 的最小埋点。
2. 在干净 worktree 离线重放同题：3-tool vs 4-tool，#72 on/off（R-20260816-03）；长尾窗收口前不要占 8792。
3. 观测台把 L01 空稿与 L05 候选草稿分成两行，不要用 151–159s 合并（R-20260816-05）。
4. 若修复方案是调预算，先用 R-20260816-01 的 asked 对照 2026-08-08 中转延迟，再写影响面；不要先把 30 或 T 调大。
5. 10 题窗必须等本分诊的修后臂配方，否则修后臂量的是「四层 ∧ 预算回归」合成。
6. 不要把 L04 chat 臂写进 10 题对照。

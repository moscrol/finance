# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M1
- failure_criterion: 单 case 终态为 `repair_model_stop` 或 `invalid_repair_finish`，且验收台交付 `evidence_bound=0`，且同 case episode 内绑定证据 > 0 或修复轮已产出合法 partial FINAL_JSON。否命题是「修复链把交付救回来了」。R6-A3（`repair_model_stop` 但交付 3）划出靶内，不放宽标准。
- trace_coverage: 主 case R7-A7 `run_20260813_034211_544672`（episode 22 事件 + workbench `trace.jsonl` 21 步 + 结构/语义 verifier）；旁证 R5-A6/A10、R6-A10（同形状）与 R5-A7/R6-A3/R13-A7（同 stop、交付>0）；live `20260814T1707Z-trka-r1-repair-shape.json`（8792 @ `5b456532` dirty，凌晨，中转 terra）。未读 skill 受控验收目录。
- trace_depth: D3
- completion_status: COMPLETE_FAILURE
- confidence: high

## Prior prediction closure

本轨道按主协议只读 Open 表，不写 `R-20260804-02` / `R-20260804-10`。本次 frozen + live episode 都不触及 Codex rollout 归一化或 R-10 slow-tool handoff。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 收口审计 §修复2 | R-20260804-02 | 真 Codex rollout 中 `function_call_output` 归入 `observe` | still_pending | none — 本轨道未取 rollout；回填由轨道 B 独占 | 保持 Open；本轨道不写该行 |
| L7 finalization T3 | R-20260804-10 | deadline-aligned per-tool handoff 的离线主门 + 瑞华泰 canary | still_pending | none — 本轨道无 headless handoff 新证据 | 保持 Open；不得因 Task 1/2 写成 confirmed |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `HARNESS_FIX`=1（距升格线 2）；`EVAL_ONLY`=1（距升格线 2）；二者不互相累计

## Executive finding

第一处错误变换是修复轮（及被丢弃的主路径收尾）把**已有 evidence_hashes 的限制条件写进 `binding.gap`**：结构核验按 `episode_verifier.py:115` 把该格判 missing 并丢掉 hashes；当**全部** required output 都这样滑档时，`_can_semantically_release_partial` 为假，judge 被跳过，公开答案走「未完成核验绑定」模板，交付 0。`repair_model_stop` 本身不是交付杀手。

## Local vocabulary ↔ L1

本仓 `trace-profile.md` §6 词表 `triage-l1-9`。本 run 同时有 workbench `trace.jsonl` 与 episode 事件；PRIMARY 定在 episode 事件（D3），workbench 步作地标。

| 本地 kind / step_id | L1 | provenance |
|---|---|---|
| `configure` | `configure` | workbench native |
| `controller` | `intent` | workbench native |
| `task` | `intent` | episode native |
| `plan` / `repair_goal` / `repair_reentry` | `plan` | workbench / episode |
| `tool_request` | `tool` | episode native |
| `tool_result` / `tool_error` / `runtime_result` | `observe` | episode native |
| `finalization` / 收尾或 repair 的 `model_turn` | `synthesize` | episode native |
| `finish` | `stop` | episode native |
| `adapter:verification` / `adapter:finalizing` | `observe` / `synthesize` | workbench |

损耗：episode 无独立 `route`（backend 由验收台选定）；workbench `trace.jsonl` 未单列 repair `model_turn`（seq 20），只落到 `finish` seq 22。无明确映射的事件未就近归类。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 终局契约：有 hashes 则 `binding.gap` 为空，限制进顶层 gaps | 系统提示有此规则；finalization 又要求「证据不足必须写 gap」；08-10 validate 接受滑档却把 gap 留在 binding | fail | E-008 |
| intent | 识别「2026-07-21 当天主线」 | `task` + `concept_definition` / `direct_definition`+`evidence_boundary` | ok | E-001 |
| plan | 有盘面证据后收口写 FINAL_JSON | 另发 `evidence_search` 追技术定义 | ok/variable | E-002 |
| route | 不要求 episode 做 skill 分派 | 结构性不存在 | missing-by-design | E-001 |
| retrieve | 取到可绑定盘面证据 | 17 条证据入账；2 次 `evidence_search` `tool_timeout` | ok | E-002 |
| tool | 合法调用或可见错误 | `mainline_context`/`finance_query` 成功；检索超时 | ok | E-002 |
| observe | 保留 hashes 与缺口语义 | verifier 见非空 `binding.gap` 即丢 hashes | fail | E-005 |
| synthesize | 有 hashes 的格 `gap=""`，限制进顶层 gaps | seq 15/20 FINAL_JSON 两格都是 hashes+gap | fail | E-003、E-004 |
| stop | 合法 partial 转化为交付 | `repair_model_stop`；公开模板交付 0 | fail | E-006、E-007 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260813_034211_544672/events[sequence=20]` | HARNESS | configure | task-instruction-category-non-compliance | repair FINAL_JSON 两格 `evidence_hashes` 非空且 `gap` 非空 | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 全部 required output 的 binding 同时带 hashes 与非空 gap → 结构全 missing → judge 跳过 → 交付 0 | 靶内 case 两格 gap=True 且 fulfilled=0；至少一格 gap=False 的同 stop case 交付>0 | E-003、E-004、E-005、E-006、E-009、E-010 | CONFIRMED | — | 四份冻结靶内全中；R5-A7/R6-A3/R13-A7/live A7·A10 混槽均交付>0 |
| H2 | `repair_progressed` 把 partial+无新工具判成 `repair_model_stop`，因此交付 0 | 若成立，同 stop 不应出现 eb>0；`repair_model_finish` 不应 eb=0 | E-009、E-010 | REJECTED | — | R5-A7/R13-A7/live A7 均为 `repair_model_stop` 且 eb>0 |
| H3 | 核验预算不足使 judge unavailable，独立造成交付 0 | 若成立，judge unavailable 应在混槽也打成 eb=0 | E-006、E-010 | REJECTED | — | judge 跳过是 fulfilled=0 的后果（`_can_semantically_release_partial`）；live 混槽 judge unavailable 仍 eb=3 |
| H4 | 主路径 `consume_seconds` 丢弃合法 FINAL_JSON（`carried_draft_chars=0`）导致交付 0 | 若成立，修复轮不应再产出同等 JSON；或修复 JSON 无 gap 滑档 | E-003、E-004、E-007 | REJECTED | — | 修复轮 16s 内再次产出合法 JSON；丢弃不解释 verifier 为何丢掉已有 hashes |

## Causal findings

### PRIMARY

- failure_span_id: `run_20260813_034211_544672/continuous-episode.json:events[sequence=20]`
- root_location: `episode_protocol.py` 终局契约（hashes 则 gap 必空）与 finalization/08-10 留痕路径冲突；首次进入 verifier 的滑档 JSON 在 repair `model_turn` seq 20
- excerpt: `bindings[direct_definition].n_hash=6 gap=True; bindings[evidence_boundary].n_hash=7 gap=True; structural.outputs[*].status=missing; judge_status=unavailable`
- l0: HARNESS
- l1: configure
- l2: task-instruction-category-non-compliance
- l3: n/a
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION, TASK_TERMINATION]
- failure_detection_timing: SEVERAL_STEPS_LATER
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-003, E-004, E-005, E-006, E-008]
- explanation: 装配层同时注入「有 hashes 则 binding.gap 必空」与「证据不足必须写 gap」，08-10 又把滑档 gap 留给 verifier。模型按后一条填写后，结构层把已绑定 hashes 清零；全格发生时公开路径无法释放草稿。

### SECONDARY / TERTIARY

- F-002 SECONDARY：`episode_verifier.py:115` 短路径（传播，判据本身不改）
- F-003 TERTIARY：judge 跳过 + 「未完成核验绑定」模板（传播）
- none as independent PRIMARY

## Evidence → Finding → Path

### Evidence

### E-001
- title: R7-A7 运行身份与失败标准命中
- run_id: run_20260813_034211_544672
- step_or_span_id: run_20260813_034211_544672/events[sequence=1]
- native_or_normalized: native
- source_type: file
- source_ref: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260813_034211_544672/continuous-episode.json` outcome/contract
- observed_at: 2026-08-13T03:42:11+08:00
- raw_excerpt: |
    stop_reason=repair_model_stop; evidence_bound=0; n_evidence=17; n_bindings=2; repair_attempts=1; revision_artifact=e999c979; base=8792
- observation: 验收台交付 0，episode 内有 17 条证据与 2 条 binding。命中冻结失败标准。
- confidence: high

### E-002
- title: 检索阶段已取得盘面证据
- run_id: run_20260813_034211_544672
- step_or_span_id: run_20260813_034211_544672/events[sequence=8]
- native_or_normalized: native
- source_type: tool_return
- source_ref: 同上 episode events sequence 4/6/8
- observed_at: 2026-08-13T03:42:21+08:00
- raw_excerpt: |
    tool_result ok: mainline_context hashes=5; finance_query market_daily hashes=1; finance_query mainline_sector_daily hashes=11
- observation: 修复开始前证据账本已非空。后续 2 次 evidence_search 为 tool_timeout。
- confidence: high

### E-003
- title: 主路径收尾已吐出 hashes+gap 的合法 FINAL_JSON
- run_id: run_20260813_034211_544672
- step_or_span_id: run_20260813_034211_544672/events[sequence=15]
- native_or_normalized: native
- source_type: transcript
- source_ref: 同上 episode events sequence 15 model_turn
- observed_at: 2026-08-13T03:42:55+08:00
- raw_excerpt: |
    status=partial; bindings.direct_definition.n_hash=5 gap=True; bindings.evidence_boundary.n_hash=6 gap=True; error=""
- observation: provider 在 finalization 后返回可解析 FINAL_JSON，两格都有 hashes 且都写了 gap。
- confidence: high

### E-004
- title: 修复轮 16s 窗口内再次产出同等滑档 JSON
- run_id: run_20260813_034211_544672
- step_or_span_id: run_20260813_034211_544672/events[sequence=20]
- native_or_normalized: native
- source_type: transcript
- source_ref: 同上 episode events sequence 19–22
- observed_at: 2026-08-13T03:43:10+08:00
- raw_excerpt: |
    repair_reentry granted_seconds=16.0 research_tools_open=False; model_turn.phase=repair error="" output_tokens=660; finish.stop_reason=repair_model_stop; bindings n_hash=6/7 both gap=True
- observation: 修复窗内 provider 到货；JSON 合法；两格仍是 hashes+gap。此份 JSON 进入 verifier。
- confidence: high

### E-005
- title: 结构核验因 gap 丢掉全部 hashes
- run_id: run_20260813_034211_544672
- step_or_span_id: run_20260813_034211_544672/structural_verifier.completion.outputs
- native_or_normalized: native
- source_type: file
- source_ref: 同上 continuous-episode.json structural_verifier
- observed_at: 2026-08-13T03:43:10+08:00
- raw_excerpt: |
    issues=["required output reports gap: direct_definition","required output reports gap: evidence_boundary","missing mandatory capability evidence: mainline_context"]; outputs[*].status=missing evidence_ids=[]
- observation: 两格 status=missing、evidence_ids 为空。mandatory mainline_context「缺失」出现在 gap 短路径之后，bound_tools 未被更新。
- confidence: high

### E-006
- title: 语义层跳过 judge 并走未绑定模板
- run_id: run_20260813_034211_544672
- step_or_span_id: run_20260813_034211_544672/semantic_verifier
- native_or_normalized: native
- source_type: file
- source_ref: 同上 semantic_verifier；代码 `episode_semantic_verifier.py:503-522` 与 `:1699-1708`
- observed_at: 2026-08-13T03:43:10+08:00
- raw_excerpt: |
    judge_status=unavailable; metrics.semantic_status=unavailable; public_answer contains "本轮已取得 17 条证据，但未完成核验绑定"; stale=false
- observation: `_can_semantically_release_partial` 要求至少一格 fulfilled。全 missing 时不调用 judge，公开答案用未绑定模板。
- confidence: high

### E-007
- title: 主路径 finish 丢弃草稿
- run_id: run_20260813_034211_544672
- step_or_span_id: run_20260813_034211_544672/events[sequence=17]
- native_or_normalized: native
- source_type: trace
- source_ref: 同上 finish sequence 17；`agent_episode.py:703-716`
- observed_at: 2026-08-13T03:42:55+08:00
- raw_excerpt: |
    finish.stop_reason=deadline_exhausted; carried_draft_chars=0; 紧接 sequence=15 已有 FINAL_JSON
- observation: 模型收尾成功后 `_consume_root_seconds` 失败，finish 未携带 draft。属独立 harness 丢稿，不解释修复 JSON 进入 verifier 后的全 missing。
- confidence: high

### E-008
- title: 终局契约与 08-10 半修复原文
- run_id: n/a
- step_or_span_id: intelligence/services/episode_protocol.py:214-216
- native_or_normalized: native
- source_type: code_reading
- source_ref: `intelligence/services/episode_protocol.py` 第 214-216 行与 08-10 `validate_episode_finish` 注释；`test_validate_finish_keeps_answer_when_supported_output_adds_a_caveat`
- observed_at: unknown
- raw_excerpt: |
    "binding.gap 只在该 required output 无法回答时填写；若 output 已由 evidence_hashes 支持并完成，binding.gap 必须为空，限制条件写入顶层 gaps 或 draft。"
- observation: 契约已禁止 hashes+gap。08-10 为保答案不整份作废，把 gap 留在 binding 供 verifier 降级。全格滑档时该半修复把交付打成 0。
- confidence: high

### E-009
- title: 同 stop 但混槽/无 gap 则交付>0
- run_id: run_20260813_023832_390505
- step_or_span_id: R5-A7 / R6-A3 / R13-A7 structural outputs
- native_or_normalized: native
- source_type: file
- source_ref: R5 `run_20260813_023832_390505`；R6-A3 `run_20260813_031634_181704`；R13-A7 `run_20260813_092250_424986`
- observed_at: 2026-08-13
- raw_excerpt: |
    R5-A7 repair_model_stop both outputs fulfilled gap=False eb=2 judge=repaired; R6-A3 stop=repair_model_stop 2/3 fulfilled eb=3; R13-A7 stop=repair_model_stop direct_definition fulfilled eb=3
- observation: `repair_model_stop` 与交付 0 不是同一事件。区分变量是「是否至少一格 gap 为空且 hashes 被 verifier 接受」。
- confidence: high

### E-010
- title: live 复跑（凌晨 / 中转 terra / 5b456532）
- run_id: run_20260815_010752_187680
- step_or_span_id: live artifact 20260814T1707Z-trka-r1-repair-shape.json
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/eval/runs/20260814T1707Z-trka-r1-repair-shape.json`；runs `run_20260815_010701_853758` / `_010752_187680` / `_011009_110317`
- observed_at: 2026-08-15T01:07+08:00
- raw_excerpt: |
    preflight revision=5b456532 backend=continuous_glm; A6 eb=0 n_evidence=0 (out of target); A7 repair_model_stop eb=3 mixed (definition fulfilled, boundary hashes+gap); A10 repair_model_stop eb=3 mixed; judge unavailable + 候选草稿释放
- observation: 成立条件=凌晨+中转 terra+`5b456532` dirty+`ASK_TOOL_BATCH_TIMEOUT=60`。主 case A7 本夜未再现全格滑档；混槽仍交付。A6 是零证据另一形状，不进本靶。
- confidence: high

### self_report_vs_observed

| 对账对象 | 机器/原始观测 | 人类可读或后处理字段 | 采用口径 |
|---|---|---|---|
| 运行是否完成 | episode `status=partial`，`stop_reason=repair_model_stop` | 验收台 `turns[].status=completed` | 完成态用验收台 turn；质量终态用 episode stop + evidence_bound |
| 是否已绑定 | outcome.bindings 两格有 hashes；structural.outputs evidence_ids=[] | 公开答案「未完成核验绑定」 | 绑定事实用 episode bindings；交付用 structural fulfilled / evidence_bound |
| 修复是否成功 | `repair_attempts=1` `repair_cycles=0`；finish=`repair_model_stop` | 08-13 ad-hoc「修复产出合法 partial」 | 合法 JSON 是事实；`repair_cycles` 只在 `repair_model_finish` 时加一，不能当「没修好」的唯一证据 |

### Findings

### F-001
- title: 全格 hashes+gap 滑档使已绑定证据无法交付
- status: validated
- failure_span_id: run_20260813_034211_544672/events[sequence=20]
- root_location: finish 契约装配 + 08-10 留 gap 路径
- l0: HARNESS
- l1: configure
- l2: task-instruction-category-non-compliance
- l3: n/a
- violated_authority: user
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION, TASK_TERMINATION]
- failure_detection_timing: SEVERAL_STEPS_LATER
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-003, E-004, E-005, E-006, E-008, E-009]
- confidence: high
- explanation: 用户成功标准是把已取到的证据交付出来。装配规则互相冲突，08-10 半修复在全格滑档时把交付打成 0。

### F-002
- title: verifier 短路径丢掉 hashes
- status: validated
- failure_span_id: structural_verifier.completion.outputs
- root_location: intelligence/services/episode_verifier.py:115
- l0: HARNESS
- l1: observe
- l2: execution-error-category-formatting
- l3: n/a
- violated_authority: tool_contract
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-005]
- confidence: high
- explanation: 非空 `binding.gap` 直接 missing 并清空 evidence_ids。这是现行判据，本轨道不放宽；PRIMARY 修的是进入该判据之前的字段归位。

### F-003
- title: 无 fulfilled 格时 judge 被跳过
- status: validated
- failure_span_id: semantic_verifier
- root_location: intelligence/services/episode_semantic_verifier.py:503-522
- l0: HARNESS
- l1: observe
- l2: orchestration-related-errors-category-premature-termination
- l3: n/a
- violated_authority: system
- causality: TERTIARY_FAILURE
- propagation_impact: [TASK_TERMINATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-006, E-010]
- confidence: high
- explanation: 跳过 judge 是 fulfilled=0 的后果，不是独立预算耗尽。live 混槽在 judge unavailable 时仍能释放候选草稿并交付。

### Path

### P-001
- title: 已绑定 hashes 因 gap 滑档无法交付
- start: seq 8 之后，17 条证据在账本，工具观察正确
- goal: 修复链把交付救回来（eb>0 或公开答案引用已核验绑定）
- steps:
  1. 检索取得盘面证据 — evidence: E-002 — finding: none
  2. 收尾/修复 FINAL_JSON 在已有 hashes 的格填写 binding.gap — evidence: E-003、E-004 — finding: F-001
  3. verifier 短路径 missing 并丢 hashes — evidence: E-005 — finding: F-002
  4. 无 fulfilled → judge 跳过 → 未绑定模板 → eb=0 — evidence: E-006 — finding: F-003
- residual_uncertainty: 主路径 `carried_draft_chars=0` 仍会浪费一轮修复窗，本轨道不修窗口尺寸；若 bindings 绕过 `validate_episode_finish` 进入 verifier，判据仍会丢 hashes。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-001 | F-001 | DATA_CONTRACT_FIX | 在 `validate_episode_finish` 把「hashes 非空且 gap 非空」的限制挪到顶层 `gaps` 并清空 `binding.gap`。不改 verifier 短路径，不放宽无哈希的真缺口。 | 以 R7-A7 形状的两格 hashes+gap FINAL_JSON 过 validate 后，两格 `binding.gap=""`、限制出现在顶层 gaps；再过 `verify_episode_outcome` 两格 `fulfilled`，issues 不再含 `required output reports gap:` | 单测：混槽滑档、全格滑档、无哈希 gap 仍拒绝；verifier 直接喂 leftover gap 仍 missing |

### R-001
- targets_finding: F-001
- fix_type: DATA_CONTRACT_FIX
- recommendation: 执行已有终局契约：有直接证据的附带限制归顶层 gaps，不把滑档留在 binding 里喂给 verifier。
- verification_prediction: 全格 hashes+gap 的 partial finish 经 validate 后 verifier 两格 fulfilled；无哈希的 gap 仍按缺失拒绝。
- regression_guard: `test_validate_finish_relocates_all_slot_caveats_so_verifier_can_fulfill`；`test_leftover_binding_gap_still_drops_hashes`；`test_validate_finish_still_rejects_gap_without_any_evidence`
- auto_apply: false

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| finish 未记录「hashes+gap 滑档格数」 | 验收台只能看 stop/eb，不能直接数滑档 | `finish.payload.caveat_slips` 整数；靶内预测 ≥2，混槽=1，健康=0 | `validate_episode_finish` 落盘到 finish 事件 | 不打开 episode 也能分「全格滑档 / 混槽 / 真缺口」 | 低 |
| 绕过 validate 的 binding 仍能进 verifier | residual：手造 outcome 是否仍丢 hashes | 现有单测已锁 leftover gap → missing | `test_episode_verifier.py` | 确认本修复不改判据 | 已有 |

## Limits and counterevidence

- 08-13 ad-hoc 把 A7 写成「核验预算」：judge 跳过是结构全 missing 的后果，不是独立预算耗尽。
- `repair_model_stop` 不是本靶的充分条件。R5-A7 / live A7 同 stop 且交付>0。
- R6-A3 划出靶内（交付 3）。
- live A6 `eb=0` 但是 `n_evidence=0`，是另一条冷启动链，不进本靶。
- live 未再现 R7-A7 全格滑档；机制由冻结四样本 + 混槽对照确认。结论携带：R7=白天中转 `e999c979`；live=凌晨中转 `5b456532` dirty。
- 本轨道不改语义 judge 判据、不放宽证据类型地板、不重开 #296/#297 窗口、不改 A4 前缀哈希口子。
- DuckDB `fact_market_daily` max=2026-08-13；题面为 2026-07-21/23 历史日，盘面依赖成立。readiness 缺 `market_data_consistency` 为收盘后日常，preflight 只看 `/api/health`。

## Next-step menu

1. 落地 R-001（`validate_episode_finish` 归位），跑协议/verifier 单测。
2. 账本追加 `R-20260815-21`，离线门通过后记 pending，等用户切 8792 再 live canary。
3. 下轮若检阅指定：给 finish 事件加 `caveat_slips` 计数（EVAL_ONLY）。
4. 下轮候选：主路径 `carried_draft_chars=0`（独立丢稿，不在本 PR）。
5. 不在本轨道做 A4 `forged_hash` 前缀匹配或 A3 `deadline_exhausted` 档位链。

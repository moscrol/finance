# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M2
- failure_criterion: 修后 `evidence_bound_rate` 相对修前下降，且下降由判断槽（`direct_answer` / `direct_assessment`）`evidence_hashes=0` 贡献；旁槽仍有哈希。否命题：判断槽在修后仍有哈希，或下降来自旁槽被剥 / 无 episode / 与 R-06 judge 窗地板同因
- trace_coverage: 冻结三对 `outlook-ab-0816` episode + `trace.jsonl` + `report.json`；官方 `normalize_harness_trace --compare`（workbench-trace）；生产树 `6cd0756e` 的 `#72` / finish 契约与十题窗 `_bindings_rate`。未做 #72-only 单变量重放
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Prior prediction closure

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 十题窗 #94 + 检阅 #96（非四阶段） | R-20260816-11 | 下一份分诊须把「修后判断槽 `evidence_hashes=0`、旁槽仍有哈希」立为独立 PRIMARY 候选或显式 REJECT；并进 R-06、或写成 judge 窗地板副作用，即本预测 **refuted** | confirmed | E-001, E-003, E-006, E-007, E-011, E-012 | PRIMARY 点名该 0-hash 形状；H1 已 REJECT 同因/窗地板。本行从 Open 移 Closed |
| 2026-08-16 judge transient R-06 T3 | R-20260816-10 | 处置落地后，下一份 draft>0 的 8795 同形重放：judge 首轮 `timeout_asked` ≥20；H9 形 TimeoutError 率相对收据 11/11 下降 | still_pending | E-006, E-018 | 本窗不是 8795 同形 12 槽重放。L01 r2 旁证 asked=12.5 不得偷结 |
| 2026-08-16 有稿 judge 案豁免 | R-20260816-07 | 本窗关闭后下一份自称「outlook 预算回归修复」的 PR diff **不含** T / `_REPAIR_SECONDS_CAP` / 生产档位上调 | still_pending | none | 本 PR 只交分诊/账本，不是预算修复。绊线仍看自称预算修复的 diff |
| outlook 预算回归 M1 F-001 | R-20260816-01 | 下一次空 draft 超时 run 的首轮 finalize `model_turn` payload 含 `timeout_asked` | still_pending | E-005 | L01 r3 post 合成 TimeoutError 带 `asked=16.11`，但 repair 救出正文，不是 R-01 要的空稿终态 |
| 宽题取证饿死 M1 | R-20260816-13 | 8795 工具批五字段重放切开 H-a/H-c；对 R-11 冻结样本只是移交证据，eb 结案权在 R-11 | still_pending | E-005, E-008 | 三对冻结样本工具已返回；0-hash 出在 FINAL_JSON。本行不代结、不抢 R-13 案 |
| 宽题取证饿死案绊线 | R-20260816-14 | 自称修饿死的 PR 不含工具批/T/slot/档位上调 | still_pending | none | 本 PR 不自称修饿死，也不动那些旋钮 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: 全 0（本轮无新 refuted；R-11 为 `EVAL_ONLY` confirmed，不计入升格）

## Executive finding

第一处错误变换在 **configure**：修后树 `#72` 把观点题判断槽装成 `grounding_mode=model_reasoning`（哈希可选、禁止伪造），而十题窗 `_bindings_rate` 仍按「有哈希且 gap 空」计所有槽。模型按新契约写出 `basis=model_reasoning` + `evidence_hashes=[]` 时，协议接受、judge 也能过，计分却记成判断槽未绑定，于是 eb 下跌。这不是 R-06 / judge 窗地板。

## A/B controls

- invariant inputs: 同一用户 `outlook-ab-0816`；同一题面（L01/L03/L05）；两侧都要求 `direct_answer` + `evidence_boundary`；模型族同为 `gpt-5.6-terra`
- intentional variable: 代码树 `437cd5e9`（pre）vs `6cd0756e`（post：#72/#75/#79/#84/#93 等整树，不是单变量）
- uncontrolled confounders: live 模型方差；post 多一轮 PLAN / 工具次数；#84 合成 `timeout_asked`；L01/L03 post 合成 TimeoutError 后走 repair。官方 compare 有 unmapped caveat，不得当行为分叉

| normalized step | Run A span/evidence | Run B span/evidence | comparison | causal prediction |
|---|---|---|---|---|
| configure · contract.grounding_mode | pre L01 r3 `direct_answer=evidence`（E-002） | post L01 r3 `direct_answer=model_reasoning`（E-001） | diverged（取值；L1 同为 configure） | post 判断槽允许 0-hash；pre completed 不允许 |
| retrieve · tools | 两侧 `finance_query` / 市场工具均有 `tool_result` | 同左；post 常多 1 次 PLAN | same enough | 0-hash 不是检索空集 |
| synthesize · 首轮无工具 model_turn | pre L01 r3 seq=9：`basis=evidence` + 4 hashes（E-009） | post L01 r3 seq=11：`TimeoutError` `asked=16.11` `content=""`（E-005） | diverged（结果） | 仅预测是否进 repair，不预测 0-hash（L05 反例） |
| synthesize · 终态 FINAL_JSON | pre 判断槽 hashes>0 | post `hashes=[]` `basis=model_reasoning`（E-003, E-004, E-008） | diverged | 该槽 eb 从 1.00 → 0.50 |
| stop · judge | pre `judge_status=repaired/completed` | post L01 `repaired` / L03 `passed`；`timeout_asked=null` `exc_class=null`（E-006, E-007） | same class | 排除 judge 窗地板 |

- ablation_activation_step: `post:L01:r3/continuous-episode.contract.required_outputs[0]`（`grounding_mode=model_reasoning`，#72 生效；早于任何 0-hash）
- first_divergence_step: `post:L01:r3/events[sequence=11]`（首轮合成 TimeoutError；pre 对应 seq=9 已写出带哈希 FINAL_JSON。同一 L1=`synthesize`，不是两侧 step 类型互异）
- first_divergence: n/a
- first_failure_step: `post:L01:r3/events[sequence=16]`（repair `model_turn` 已写出判断槽 `evidence_hashes=[]`；L05 更早在 seq=13 首轮 JSON 已是 0-hash）
- failure_surfaced_step: `score.json` 槽 `post:L01:r3` `evidence_bound_rate=0.5`，同时 episode `status=completed` / `judge_status=repaired`（E-015, E-016）
- reconvergence_step: none observed
- pre_divergence_equivalence: 题面、required output id、用户、模型族相同；`trace.jsonl` 两侧都有 configure→intent→plan。`grounding_mode` 取值差是 intentional，不算未声明混杂。官方 compare 写 `equivalent_before_divergence`，但 `unmapped_counts` 左 4 / 右 5，caveat 禁止把它当行为等价证明
- downstream_propagation: 合法 0-hash → `_bindings_rate` 判未绑定 → 槽 eb 0.50 → 窗级 −17.5pp。judge / 公开正文仍可 completed

官方 `normalize_harness_trace --compare`（`/tmp/r11-normalize/L01r3.json`）：`first_divergence={ordinal:9, left_step:stop, right_step:retrieve}`，`interpretation_caveats` 含 unmapped 与 step_mismatch。按 adapter 纪律：**不把该分叉当行为结论**，也不用它填满五槽。workbench-trace 词表不映射 episode `model_turn`/`finish.bindings`，而这正是判据所在。

### 本地词表 ↔ L1

| 本地 | L1 | 损耗 |
|---|---|---|
| `trace.jsonl` `step_id=configure` / episode `contract` | configure | 控制面 configure **不写出** `grounding_mode`（该分叉却没分叉） |
| `controller` | intent | 无 |
| `plan` / 模型 `kind=PLAN` | plan | post 额外 PLAN 被映射成多余 `plan`，官方分叉易落在这里 |
| `tool_request`/`tool_result` / `continuous:episode:*:research` | retrieve | workbench-trace 几乎没有独立 `tool` |
| episode `model_turn` FINAL_JSON | synthesize | **workbench-trace 常 unmapped** |
| episode `finish` | stop | 多条 finish 须取最后一条；首条常是 `deadline_exhausted` 且 `bindings=[]` |
| `repair_goal` / `repair_reentry` / `runtime_result` | unmapped | 修复链在官方 compare 里不可见 |

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 装配与「eb 修后不降」同口径；判断槽若改 `model_reasoning`，计分须分层 | `#72` 改判断槽为 `model_reasoning`；`_bindings_rate` 仍按全槽哈希计 | fail | E-001, E-010, E-012 |
| intent | 识别观点题 + 两槽 | 两侧 `general_finance_qa` / `direct_answer`+`evidence_boundary` | ok | E-001, E-002 |
| retrieve | 取得可绑定证据 | 三对 post 均有成功 `tool_result`；旁槽终态有哈希 | ok | E-003, E-008 |
| synthesize | 判断槽按契约终止；若正文用了观察，绑定或显式 gap | post 写 `basis=model_reasoning` + `hashes=[]`（L01 正文仍点名 E-id） | fail | E-003, E-004, E-008, E-016 |
| stop | judge 失败才丢 eb；completed 与 eb 同向 | judge 已跑完（L03 甚至 `passed`）；eb 仍 0.50 | fail | E-006, E-007, E-015 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `post:L01:r3/continuous-episode.contract.required_outputs[0]` | HARNESS | configure | `task-instruction-category-non-compliance` | `grounding_mode: model_reasoning` vs 预注册 eb 不降 | medium |
| `post:L01:r3/events[sequence=16]` | HARNESS | synthesize | `task-instruction-category-non-compliance` | `evidence_hashes:[]` `basis: model_reasoning`（传播，与 PRIMARY 同叶同权威，不单列） | medium |

PRIMARY 与合成 0-hash 是同一条 G-001 冲突的两次显影，只保留 configure 为 PRIMARY。

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 判断槽 0-hash 与 R-06 / judge 窗地板同因 | 三对 post 的 judge 应有 `TimeoutError` 或 `timeout_asked`≤12；或 `judge_status=unavailable` | E-006, E-007, E-018 | REJECTED | n/a | L01/L05 judge=`repaired` 且 asked/exc 皆 null；L03=`passed`。L01 r2 才是 transient 旁证 |
| H2 | `#72` 把判断槽改为 `model_reasoning`（哈希可选）后，`_bindings_rate` 仍按全槽哈希计，于是合法 0-hash 被记成 eb 下跌 | 三对 post `contract.direct_answer.grounding_mode=model_reasoning` 且终态 `basis=model_reasoning` `hashes=[]`；pre 同槽为 `evidence` 且 hashes>0；协议对 `model_reasoning` 不要求哈希 | E-001, E-002, E-003, E-010, E-011, E-012 | CONFIRMED | n/a | 运行时合同 + 计分函数 + finish 验收三条对齐 |
| H3 | harness / verifier 在模型写出哈希之后剥掉判断槽哈希 | 首份含 bindings 的 FINAL_JSON 判断槽 hashes>0，终态变成 0 | E-004, E-008 | REJECTED | n/a | 模型 JSON 已是 `[]`；finish `rejection_code=none` |
| H4 | 合成 TimeoutError / deadline→repair 是 0-hash 的必要条件 | 凡 0-hash 必先有合成 TimeoutError；凡 #72 生效必 0-hash | E-005, E-008, E-013 | REJECTED | n/a | L05 seq=13 首轮已 0-hash 且无 TimeoutError；`post:L01:r1` 同为 `model_reasoning` 却 35 hashes |
| H5 | R-24 marker-loss：删判断正文并留结构 fulfilled | `gap_output_ids` 含判断槽 | E-017 | REJECTED | n/a | 三对 `gap_output_ids=[]` |
| H6 | 0-hash 来自宽题工具批饿死（R-13 移交候选） | 三对 post 应在绑定前出现 `tool_timeout` / `tool_budget_exhausted`，且无成功 `tool_result` | E-005, E-008 | REJECTED | n/a | 工具已返回；0-hash 在 FINAL_JSON。R-13 本行仍 pending |

## Causal findings

### PRIMARY

- failure_span_id: `post:L01:r3/continuous-episode.contract.required_outputs[0]`
- root_location: `#72` `_grounding_mode`（观点题判断槽 → `model_reasoning`）与十题窗 `_bindings_rate`（全槽要哈希）在运行前装配/评测契约上的冲突
- excerpt: `direct_answer.grounding_mode=model_reasoning`；终态 `bindings.direct_answer.evidence_hashes=[]` `basis=model_reasoning`；`_bindings_rate` 只认 `hashes and not gap`
- l0: HARNESS
- l1: configure
- l2: `task-instruction-category-non-compliance`
- l3: n/a
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-003, E-010, E-011, E-012, E-015]
- explanation: 用户/窗成功标准是「修后 eb 不降」。#72 为保住判断句，把判断槽改成不要求哈希的 `model_reasoning`。协议按新契约接受空哈希；计分仍把空哈希当未绑定。第一处错误变换是这场装配/量具冲突，不是 judge 超时，也不是检索失败。

### SECONDARY / TERTIARY

- F-002（SECONDARY）：L01/L03 post 首轮合成 TimeoutError（`asked≈13–16s`）迫使 repair。传播，不是 0-hash 必要原因。
- F-003（SECONDARY）：`self_report_vs_observed` — `status=completed` / semantic `fulfilled` / L03 `judge_status=passed` 对 eb=0.50。

## Evidence → Finding → Path

### Evidence

### E-001
- title: post 臂判断槽合同已是 model_reasoning
- run_id: run_20260816_184718_305950
- step_or_span_id: contract.required_outputs[0]
- native_or_normalized: native
- source_type: file
- source_ref: `/Users/a77/.local/share/finance-workbench/users/outlook-ab-0816/runs/run_20260816_184718_305950/continuous-episode.json:31`
- observed_at: 2026-08-16T18:47:18+08:00
- raw_excerpt: |
    "output_id": "direct_answer"
    "grounding_mode": "model_reasoning"
- observation: 修后 L01 r3（以及 L03 r2 / L05 r2）判断槽 grounding_mode 为 model_reasoning；旁槽 evidence。
- confidence: high

### E-002
- title: pre 臂同题判断槽仍是 evidence
- run_id: run_20260816_184616_575486
- step_or_span_id: contract.required_outputs[0]
- native_or_normalized: native
- source_type: file
- source_ref: `/Users/a77/.local/share/finance-workbench/users/outlook-ab-0816/runs/run_20260816_184616_575486/continuous-episode.json:31`
- observed_at: 2026-08-16T18:46:16+08:00
- raw_excerpt: |
    "output_id": "direct_answer"
    "grounding_mode": "evidence"
- observation: 修前同题判断槽为 evidence。
- confidence: high

### E-003
- title: post 终态判断槽 0-hash、旁槽仍 bound
- run_id: run_20260816_184718_305950
- step_or_span_id: events[sequence=18]
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/outlook-ab-0816/runs/run_20260816_184718_305950/continuous-episode.json:1545-1556`
- observed_at: 2026-08-16T18:48:05.291+08:00
- raw_excerpt: |
    stop_reason: repair_model_finish
    output_id: direct_answer
    evidence_hashes: []
    basis: model_reasoning
    output_id: evidence_boundary
    evidence_hashes: [623bdcf1a6b7f56e, …]  # 25 hashes
- observation: 最后一条 finish 判断槽 0-hash，边界槽 25 hashes、gap 空。
- confidence: high

### E-004
- title: 0-hash 已在模型 FINAL_JSON 里，不是事后剥除
- run_id: run_20260816_184718_305950
- step_or_span_id: events[sequence=16]
- native_or_normalized: native
- source_type: transcript
- source_ref: `/Users/a77/.local/share/finance-workbench/users/outlook-ab-0816/runs/run_20260816_184718_305950/continuous-episode.json:1523`
- observed_at: 2026-08-16T18:48:05.290+08:00
- raw_excerpt: |
    bindings:[{"output_id":"direct_answer","evidence_hashes":[],"basis":"model_reasoning","gap":""},{"output_id":"evidence_boundary","evidence_hashes":["E1","E2",…],"basis":"evidence","gap":""}]
- observation: repair 模型输出已是空哈希；finish `rejection_code=none`。
- confidence: high

### E-005
- title: L01/L03 post 首轮合成是 TimeoutError，不是 judge
- run_id: run_20260816_184718_305950
- step_or_span_id: events[sequence=11]
- native_or_normalized: native
- source_type: log
- source_ref: `/Users/a77/.local/share/finance-workbench/users/outlook-ab-0816/runs/run_20260816_184718_305950/continuous-episode.json:1431-1443`
- observed_at: 2026-08-16T18:47:49.033+08:00
- raw_excerpt: |
    error: LLM 调用失败（TimeoutError）
    timeout_asked: 16.10886366700288
    remaining_seconds_at_entry: 76.10885950003285
    content: ""
- observation: 合成调用超时，asked≈16s，content 空。随后 `deadline_exhausted`。这是 compose，不是 judge。
- confidence: high

### E-006
- title: 冻结 post 样本 judge 已跑完且无 transient 字段
- run_id: run_20260816_184718_305950
- step_or_span_id: semantic_verifier
- native_or_normalized: native
- source_type: file
- source_ref: `/Users/a77/.local/share/finance-workbench/users/outlook-ab-0816/runs/run_20260816_184718_305950/continuous-episode.json:4396-4408`
- observed_at: 2026-08-16T18:48:05+08:00
- raw_excerpt: |
    judge_status: repaired
    timeout_asked: null
    exc_class: null
    gap_output_ids: []
- observation: judge 完成。无 TimeoutError / asked。L05 post 同形 `repaired` + null。
- confidence: high

### E-007
- title: L03 post judge 直接 passed，判断槽仍 0-hash
- run_id: run_20260816_185901_871285
- step_or_span_id: semantic_verifier
- native_or_normalized: native
- source_type: file
- source_ref: `/Users/a77/.local/share/finance-workbench/users/outlook-ab-0816/runs/run_20260816_185901_871285/continuous-episode.json:2848`
- observed_at: 2026-08-16T18:59:32+08:00
- raw_excerpt: |
    judge_status: passed
    issues: []
    outcome.bindings.direct_answer.evidence_hashes: []
    basis: model_reasoning
- observation: judge 通过不能阻止该槽 eb=0.50。
- confidence: high

### E-008
- title: L05 post 首轮合成已是 0-hash（无 TimeoutError）
- run_id: run_20260816_190657_142513
- step_or_span_id: events[sequence=13]
- native_or_normalized: native
- source_type: transcript
- source_ref: `/Users/a77/.local/share/finance-workbench/users/outlook-ab-0816/runs/run_20260816_190657_142513/continuous-episode.json:505-518`
- observed_at: 2026-08-16T19:07:43.625+08:00
- raw_excerpt: |
    error: ""
    timeout_asked: 59.91
    bindings.direct_answer.evidence_hashes: []
    basis: model_reasoning
- observation: 首轮 JSON 已 0-hash。随后同秒 `deadline_exhausted` `carried_draft_chars=0`，repair 仍 0-hash。
- confidence: high

### E-009
- title: pre 对照判断槽带哈希且 basis=evidence
- run_id: run_20260816_184616_575486
- step_or_span_id: events last finish
- native_or_normalized: native
- source_type: transcript
- source_ref: pre L01 r3 / L03 r2 / L05 r2 episode outcome.bindings
- observed_at: 2026-08-16
- raw_excerpt: |
    L01 r3 pre: direct_answer hashes=["E1","E2","E3","E23"] basis=evidence
    L03 r2 pre: 13 hashes basis=evidence
    L05 r2 pre: 3 hashes basis=evidence
- observation: 三对修前判断槽均 hashed。
- confidence: high

### E-010
- title: #72 源码把观点题判断槽投影为 model_reasoning
- run_id: n/a
- step_or_span_id: episode_factory._grounding_mode
- native_or_normalized: native
- source_type: code_reading
- source_ref: `intelligence/services/episode_factory.py:312-321` @ `6cd0756e`（pre 树 `437cd5e9` 无 `_OUTLOOK_JUDGMENT_*`）
- observed_at: unknown
- raw_excerpt: |
    if output_id in _OUTLOOK_JUDGMENT_OUTPUTS and _OUTLOOK_JUDGMENT_RE.search(frame.raw_question):
        return "model_reasoning"
- observation: 题面含「你认为/怎么看/机会在哪」时判断槽改 mode。与 E-001 运行时一致。
- confidence: medium

### E-011
- title: 协议对 model_reasoning 不要求 hashes
- run_id: n/a
- step_or_span_id: validate_episode_finish
- native_or_normalized: native
- source_type: code_reading
- source_ref: `intelligence/services/episode_protocol.py:225-227` 与 `:717-718` @ `6cd0756e`
- observed_at: unknown
- raw_excerpt: |
    model_reasoning 表示方法论或推理框架，不得伪造证据序号或哈希。
    if required.grounding_mode == "evidence" and not binding.evidence_hashes:
- observation: completed 缺哈希只拒 `evidence` 槽。与 E-003 `rejection_code=none` 一致。
- confidence: medium

### E-012
- title: 十题窗 eb 不计 grounding_mode
- run_id: n/a
- step_or_span_id: _bindings_rate
- native_or_normalized: native
- source_type: file
- source_ref: `~/.finance-runtime/outlook-ab-20260816/score_outlook_live_ab.py:81-105`
- observed_at: 2026-08-16T20:19:27+08:00
- raw_excerpt: |
    if hashes and not gap:
        bound += 1
    return bound / len(bindings)
- observation: 空哈希的 model_reasoning 槽与空哈希的 evidence 槽同码。
- confidence: high

### E-013
- title: 同合同下 post 也可以给判断槽哈希
- run_id: run_20260816_184200_956550
- step_or_span_id: outcome.bindings
- native_or_normalized: native
- source_type: file
- source_ref: post:L01:r1 continuous-episode.json contract + outcome
- observed_at: 2026-08-16T18:42:00+08:00
- raw_excerpt: |
    grounding_mode=model_reasoning
    direct_answer n_hash=35 basis=model_reasoning
- observation: #72 不是 0-hash 的充分条件；它只让 0-hash 合法。
- confidence: high

### E-014
- title: 官方 compare 有 caveat，不能当行为分叉
- run_id: L01r3 pair
- step_or_span_id: comparison.first_divergence
- native_or_normalized: normalized
- source_type: file
- source_ref: `/tmp/r11-normalize/L01r3.json`
- observed_at: 2026-08-16
- raw_excerpt: |
    unmapped_counts: {left: 4, right: 5}
    first_divergence: {ordinal: 9, left_step: stop, right_step: retrieve}
    caveats: unmapped events present; step_mismatch → first_divergence_step is null
- observation: 仪器覆盖不到 FINAL_JSON bindings。
- confidence: high

### E-015
- title: 计分把该槽写成 eb=0.50
- run_id: post:L01:r3
- step_or_span_id: score.json slots
- native_or_normalized: native
- source_type: file
- source_ref: `~/.finance-runtime/outlook-ab-20260816/score.json`（mtime 20:19；窗级 evidence_bound_pp=-17.5；L01 3 槽 -33.3）
- observed_at: 2026-08-16T20:19:27+08:00
- raw_excerpt: |
    post:L01:r3 evidence_bound_rate=0.5
    pre:L01:r3 evidence_bound_rate=1.0
- observation: 与 E-003 的 1/2 绑定一致。
- confidence: high

### E-016
- title: self_report_vs_observed — completed/fulfilled 对 eb 0.50
- run_id: run_20260816_184718_305950
- step_or_span_id: semantic_verifier.verified.completion vs outcome.bindings
- native_or_normalized: native
- source_type: file
- source_ref: `/Users/a77/.local/share/finance-workbench/users/outlook-ab-0816/runs/run_20260816_184718_305950/continuous-episode.json:4394-4415` 与 `:1552-1556`
- observed_at: 2026-08-16T18:48:05+08:00
- raw_excerpt: |
    completion.outputs[direct_answer].status=fulfilled evidence_ids=[]
    judge_status=repaired
    public_answer 含「E2、E6、E7…」
    bindings.direct_answer.evidence_hashes=[]
- observation: 机器完成态与哈希绑定口径冲突；正文点名了 E-id。
- confidence: high

### E-017
- title: 三对 gap_output_ids 均为空
- run_id: 三对 post
- step_or_span_id: semantic_verifier.gap_output_ids
- native_or_normalized: native
- source_type: file
- source_ref: 三份 continuous-episode.json `gap_output_ids`
- observed_at: 2026-08-16
- raw_excerpt: |
    gap_output_ids: []
- observation: 不是 R-24 marker-loss 形状。
- confidence: high

### E-018
- title: 被排除的 L01 r2 才是 judge transient
- run_id: run_20260816_184435_745334
- step_or_span_id: semantic_verifier
- native_or_normalized: native
- source_type: file
- source_ref: post:L01:r2 continuous-episode.json
- observed_at: 2026-08-16T18:44:35+08:00
- raw_excerpt: |
    judge_status: unavailable
    timeout_asked: 12.5
    exc_class: TimeoutError
    remaining_seconds_at_entry: 213.08
- observation: 与冻结三对不同。交接已禁止用它当 PRIMARY。
- confidence: high

### Findings

### F-001
- title: #72 判断槽 model_reasoning 与 eb 全槽哈希量具冲突
- status: validated
- failure_span_id: post:L01:r3/continuous-episode.contract.required_outputs[0]
- root_location: episode_factory._grounding_mode × score_outlook_live_ab._bindings_rate
- l0: HARNESS
- l1: configure
- l2: task-instruction-category-non-compliance
- l3: n/a
- violated_authority: user
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-003, E-010, E-011, E-012, E-015]
- confidence: medium
- explanation: WHAT：修后判断槽合法 0-hash 被计成未绑定。WHY：#72 与预注册「eb 不降」冲突，协议按前者接受。IMPACT：冻结三对 1.00→0.50，窗级 −17.5pp。

### F-002
- title: L01/L03 post 首轮合成 TimeoutError 只改变路径
- status: validated
- failure_span_id: post:L01:r3/events[sequence=11]
- root_location: compose model_turn
- l0: HARNESS
- l1: synthesize
- l2: execution-error-category-timeout
- l3: n/a
- violated_authority: tool_contract
- causality: SECONDARY_FAILURE
- propagation_impact: [INCORRECT_PATH]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-005, E-008, E-013]
- confidence: high
- explanation: 合成超时把 L01/L03 推进 repair。L05 / L01 r1 证明它既非 0-hash 必要也非充分。不是 R-06。

### F-003
- title: self_report_vs_observed — completed 掩盖判断槽未绑定
- status: validated
- failure_span_id: post:L01:r3/semantic_verifier
- root_location: semantic completion vs _bindings_rate
- l0: HARNESS
- l1: stop
- l2: orchestration-related-errors-category-reasoning-mismatch
- l3: n/a
- violated_authority: system
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-007, E-015, E-016]
- confidence: high
- explanation: 系统自报 completed/fulfilled/passed，评测才暴露 eb=0.50。first_failure ≠ failure_surfaced。

### Path

### P-001
- title: 合法 0-hash 被量具记成 eb 下跌
- start: pre 同题判断槽 `grounding_mode=evidence` 且 hashes>0，eb=1.00
- goal: 修后判断槽 hashes=0 且该槽贡献 eb 下跌
- steps:
  1. post 装配 #72：判断槽 `model_reasoning` — evidence: E-001, E-010 — finding: F-001
  2. 模型按契约写 `basis=model_reasoning` `hashes=[]`（L01/L03 在 repair，L05 在首轮）— evidence: E-003, E-004, E-008 — finding: F-001
  3. 协议不拒；judge 跑完甚至 passed — evidence: E-006, E-007 — finding: F-003
  4. `_bindings_rate` 计 1/2 — evidence: E-012, E-015 — finding: F-001
- residual_uncertainty: 未做 #72-only 单变量重放，故不能把「本样本选择空哈希」从四层混杂里拆成独立充分条件（E-013 已证明不是每次都空）。workbench-trace 看不到 bindings。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-015 | F-001 | DATA_CONTRACT_FIX | `_bindings_rate`（及同口径窗计分）按 `grounding_mode` 分层：`model_reasoning` 槽移出 eb 分母，或单独报 `judgment_hash_rate`。不改 #72、不改 T/30/档位、不改 `_CLAIM_POLICY` | 用冻结 `score.json` 三对离线重算：L01 r3 / L03 r2 / L05 r2 post 的 evidence 槽 eb 回到 1.00（只计 `evidence` 槽），窗级 `evidence_bound_pp` 回到 ±5pp 内；生产 episode 字段不变 | 夹具=这三对 episode；禁止顺手改 prompt / 窗地板 |

### R-015
- targets_finding: F-001
- fix_type: DATA_CONTRACT_FIX
- recommendation: 评测量具与 #72 合同对齐；不要回退判断槽到 `evidence` 硬边界（那是 #72 要修的剥句问题）。
- verification_prediction: 冻结三对 post 在「只计 evidence 槽」口径下 eb=1.00；`post:L01:r1` 仍为 1.00；不出现 T/30/档位 diff
- regression_guard: 离线重算 `outlook-ab-0816` 三对；单测钉 `model_reasoning`+空哈希+旁槽 hashed → 分层 eb=1.0、旧口径=0.5
- auto_apply: false

不建议 `SYSTEM_PROMPT_FIX` 强迫判断槽再填哈希：与 #72「不得伪造」冲突，且 E-013 显示模型有时已经会填。

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| 控制面 configure 不写 grounding_mode | 「该分叉却没分叉」；官方 compare 从 retrieve/plan 起跳 | `turn_assembly.output_summary` 含每个 required output 的 `grounding_mode`；健康=与 episode.contract 逐槽相等 | `trace.jsonl` configure | #72 是否在控制面可见 | 低 |
| workbench-trace 不映射 episode model_turn/finish.bindings | 官方 first_divergence 碰不到 0-hash | 映射 `kind=model_turn`→synthesize、`kind=finish`→stop，并带 `n_hash`/`basis`；健康=判断槽 n_hash 可在 compare 里读到 | `normalize_harness_trace._workbench_mapping` | 五槽能指到 FINAL_JSON | 中 |
| 无 #72-only 臂 | 「空哈希选择」是否只由 #72 引起 | 同题 N≥6：只开 #72 vs 四层全开；0-hash 率差 ≥30pp 才把充分性从 configure 升到「每次必空」 | 8795 hook 树，不停泊 `21dbf6c1` | 切开 E-013 方差 | 高 |

## Limits and counterevidence

- 整树 ablation，置信度 medium；PRIMARY 是合同/量具冲突，不是「#72 每次都清空哈希」。
- `post:L01:r1`（35 hashes）是 #72 充分性的反证，已写入 H4/E-013。
- 官方 compare 的 `stop ↔ retrieve @ ordinal 9` 因 unmapped 不得当行为分叉。
- 核心集判断句 0pp / 诚实闸 uncheckable 另案，不并进。
- 未切 8792。未动 T / 30 / reserve / 档位 / ASK_*。

## Next-step menu

1. 用冻结三对离线实现 R-015 分层 `_bindings_rate`，核对窗级 pp（最高信息增益，不动生产）。
2. 控制面 configure 落盘 `grounding_mode`（处方 1）。
3. 需要「每次必空」充分性时，再开 #72-only 臂；否则不要重跑十题窗。
4. R-10 仍走 8795 ≥`6cd0756e` 同形重放；不要用本窗 L01 r2。
5. R-13 继续用它自己的 20:54 样本与工具批五字段；不要用本三对代结。
6. #90 仍暂缓。

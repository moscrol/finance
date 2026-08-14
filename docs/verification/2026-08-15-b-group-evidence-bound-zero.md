# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_NOT_CONFIRMED
- mode: M1
- failure_criterion: 在 `20260813T1810Z-qc28-full.json`（`sha256=8536c231…578d80`）中，凡 `status=completed` 且 episode 的 `outcome.evidence` 非空的 turn，验收台读到的 `evidence_bound` 应 > 0。实测 B1/B2/B4/B5/B7 分别取得 19/24/125/29/13 条证据而 `evidence_bound=0`，判定为失败。
- trace_coverage: 覆盖 28 个验收 turn 中真正执行的 19 个（A1-A10、B1-B8、C1）；每个 turn 另有 workbench run 目录（`run.json` / `report.json` / `trace.jsonl` / `stream.jsonl` / `continuous-episode.json`）。**缺**：C2-C10 九个 turn 因 `Connection refused` 从未执行，无任何 trace；模型 draft 的生成过程（provider 请求/响应体）不在产物内。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Prior prediction closure

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 收口审计 §修复2（2026-08-04） | R-20260804-02 | 真 Codex rollout 中 `function_call_output` 归入 `observe`，与 workbench 的 `validate→observe` 对齐；第一个工具结果处不再出现**词表性**分叉 | refuted | E-001 | 跨 harness 归一化器对真 rollout 产出全 `unmapped`，本轮**不能**用它做 A/B 对齐；本报告改为单侧 M1，不做跨 harness 差分 |
| L7 finalization T3（2026-08-04） | R-20260804-10 | deadline-aligned per-tool handoff…（全文见账本 Open 表） | still_pending | 无（本轮无新证据） | Task 3-6 在生产代码中穷尽搜索仍为空，预注册的离线主门与 canary 都未执行，不得因 Task 1/2 完成而写 confirmed |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `EVAL_ONLY` = 1（本轮 R-02 首次 refuted，距升格线 2）；`HARNESS_FIX` = 1（沿用 R-09，本轮无变化）。两者分属不同 `fix_type`，不互相累计。

## Executive finding

`evidence_bound=0` **不是「证据丢失」**：证据被 `_public_citation_projection` 按「未绑定到许可输出即不可引用」的 fail-closed 规则有意丢弃，读数在交付层语义正确。真正的缺陷是 **eb=0 这个读数把至少三种互不相同的运行态压成同一个 `0`**，导致连续多轮归因指向错层。本轮**未确认单一 PRIMARY**：三种形状各自的第一处错误变换不同，且其中最主要一种（模型未产出 draft）的判据变量不在当前 trace 内。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 装配研究 owner 与工具注册表 | `configure` → `registry_skill_count=7`、`selected_skill_ids=[]` | ok | E-002 |
| intent | 识别为题材研究 | `controller` → `question_type=theme_analysis`、`lane=research`、`confidence=0.98` | ok | E-002 |
| plan | 形成检索阶段序列 | `plan` → 7 段 `retrieval_stages` | ok | E-002 |
| tool | 调用检索工具取证 | B1 五次 `tool_request`：3 result / 2 error | ok | E-003 |
| observe | 忠实保留工具返回 | `outcome.evidence` 收得 19 条（B4 达 125 条） | ok | E-004 |
| synthesize | 产出必需输出并绑定证据 | B1/B2/B4 `outcome.draft=""`、`bindings=0` | **fail** | E-005 |
| synthesize | （B5/B7/A6 分支）draft 已产出并绑定 | draft 266–307 字、`bindings=2`，但绑定的 output 被 verifier 标 `missing` | **fail** | E-006 |
| stop | 交付层如实反映证据状态 | `continuous:evidence` 步未发射 → `/api/runs/{id}/context` 的 `evidence[]` 为空 | ok（按设计） | E-007 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260814_021938_990234` / `continuous:adapter:finalizing` | UNCLEAR（竞争项：REASONING vs HARNESS） | synthesize | DEPTH_INSUFFICIENT(D4) | `"status":"partial","draft":"","evidence":[…19 条…]` | medium |
| `20260813T1810Z-qc28-full.json` / 验收台聚合 | HARNESS | observe | `configuration-mismatch-category-tool-definition` | `trace.evidence_bound = sum(1 for e in evidence if e.get("status")=="hit")` | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 题型路由差异：B/C 组走 deterministic owner（`quick_fact`）被排除在 continuous 之外，故不填 evidence | 若成立，B 组 turn 的 `question_type` 应为 `quick_fact` 且无 episode 事件 | E-002 | **REJECTED** | — | B1 实测 `question_type=theme_analysis`、`answer_owner=theme-research`，且发出 23 条 episode 事件。08-14 那份 ad-hoc 诊断的顶层框架不成立 |
| H2 | 证据在交付链上被丢失（取到了但没传下去） | 若成立，应能在某一跳看到 evidence 数量由 N 变 0 且无过滤条件 | E-004, E-007 | **REJECTED** | — | 丢弃点有显式条件：`continuous_turn_adapter.py:1468-1470` 只保留 `content_hash ∈ bound_hashes` 的证据。这是 fail-closed 设计，不是丢失 |
| H3 | 验收台 `evidence_bound` 把多种运行态压成同一个 0 | 若成立，应存在 eb 同为 0 但底层状态互不相同的 turn | E-004, E-005, E-006, E-008 | **CONFIRMED** | — | eb=0 的 8 个 turn 至少含三形状：取到未合成（B1/B2/B4，19/24/125 条）、已合成但绑定到 missing 输出（B5/B7/A6）、根本没取（B3 零工具调用、B6 无 episode）。另 C2-C10 的 eb=0 实为 `Connection refused` 未执行 |
| H4 | 模型未产出 draft 是 provider 不可用所致（B 组 `judge_status=unavailable`） | 若成立，`judge_status=unavailable` 应与 eb=0 一一对应 | E-008 | **REJECTED** | — | A8（eb=14）与 B8（eb=11）同样 `judge_status=unavailable` 却正常交付证据。provider 健康度不是判别式 |
| H5 | 三个必需输出「缺失」是 verifier 未识别，而非模型未产出 | 若成立，draft 中应能找到对应输出的实际文本 | E-005 | **INCONCLUSIVE** | 记录 `outcome.draft` 的字符长度与 `structural_verifier` 判定该 output 时所用的匹配键；H5 预测 draft 长度 >0 且含 output 关键字段，实测 B1/B2/B4 draft 长度 **恰为 0** 即证伪 verifier 侧假设，但无法区分「模型返回空」与「合成阶段被截断后写入空串」 |

## Causal findings

### PRIMARY

- failure_span_id: `run_20260814_021938_990234` / `continuous:adapter:finalizing`
- root_location: `intelligence/runtime/continuous_turn_adapter.py` 合成与绑定边界
- excerpt: `{"task_frame_hash":"c3310c7e…","status":"partial","draft":"","evidence":[{"tool":"graph_lookup","title":"概念 光刻胶",…}]}`
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-004, E-005]
- explanation: episode 取回 19 条证据后 `outcome.draft` 为空串、`bindings=0`，下游按设计不发引用。第一处「正确状态→错误状态」发生在合成产出必需输出这一步。**但无法在 REASONING（模型确实没写）与 HARNESS（合成阶段被预算/провider 截断后落空串）之间定夺**——两者都能解释空 draft，产物里没有区分二者的判据变量，故 L0 记 UNCLEAR、L2 记 `DEPTH_INSUFFICIENT(D4)`。

### SECONDARY

- failure_span_id: `intelligence/eval/acceptance.py:196-200`
- root_location: 验收台 `evidence_bound` 的定义域
- excerpt: `evidence = ctx.get("evidence") or []` / `trace.evidence_bound = sum(1 for e in evidence if isinstance(e, dict) and e.get("status") == "hit")`
- l0: HARNESS
- l1: observe
- l2: `configuration-mismatch-category-tool-definition`
- violated_authority: tool_contract
- causality: SECONDARY_FAILURE
- propagation_impact: [INCORRECT_PATH]
- failure_detection_timing: SILENT_UNDETECTED
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-003, E-008, E-009]
- explanation: 该指标只从 `/api/runs/{id}/context` 的 `evidence[]` 计数，而该端点又只从 `trace[].retrieval` 构造。于是「未执行」「没取到」「取到未合成」「已合成但绑定到 missing 输出」四种状态被压成同一个 `0`，且**读数本身不携带任何区分信息**。这是本问题在 2026-08-14 被归因到「题型路由」的直接原因——量具把不同病压成同一个读数，误导了上一轮归因方向。

### TERTIARY

none

## Evidence → Finding → Path

### Evidence

#### E-001
- title: 真 Codex rollout 过归一化器全部 unmapped
- run_id: n/a（离线工具运行）
- step_or_span_id: `normalize_harness_trace` 单输入产物
- native_or_normalized: native
- source_type: tool_return
- source_ref: 输入 `~/.codex/archived_sessions/rollout-2026-08-03T20-18-55-019fc790….jsonl`（`sha256=62385ee5…b316a7`）
- observed_at: 2026-08-15
- raw_excerpt: |
    schema_version=normalized-harness-trace-2 vocabulary=triage-l1-9
    source_kind=codex-rollout events=264 unmapped_count=264
    step 分布 = {'unmapped': 264}
- observation: 264 条事件全部落 `unmapped`，无 `observe`、无 `tool`；`--kind auto/codex-rollout/codex-exec` 三种传法结果一致。
- confidence: high

#### E-002
- title: B1 被判定为 theme_analysis 并进入 continuous 研究路径
- run_id: run_20260814_021938_990234
- step_or_span_id: `controller` / `plan`
- native_or_normalized: native
- source_type: trace
- source_ref: `<FORESIGHT_USERS_DIR>/linxiaoqi5111/runs/run_20260814_021938_990234/trace.jsonl`
- observed_at: 2026-08-14T02:19Z
- raw_excerpt: |
    {"lane":"research","needs_retrieval":true,"question_type":"theme_analysis",
     "confidence":0.98,"reason":"确定性识别到研究 owner 问题类型（theme-research）"}
- observation: question_type 为 `theme_analysis` 而非 `quick_fact`，owner 为 `theme-research`。
- confidence: high

#### E-003
- title: 逐工具事件存在且成功返回
- run_id: run_20260814_021938_990234
- step_or_span_id: `continuous:episode:3..12`
- native_or_normalized: native
- source_type: trace
- source_ref: 同上 `trace.jsonl`
- observed_at: 2026-08-14T02:19Z
- raw_excerpt: |
    continuous:episode:3:tool_request → 4:tool_error
    continuous:episode:5:tool_request → 6:tool_result
    continuous:episode:7:tool_request → 8:tool_result
    continuous:episode:9:tool_request → 10:tool_result
    continuous:episode:11:tool_request → 12:tool_error
- observation: 5 次工具请求、3 次成功返回、2 次错误。工具层确实执行并有返回。
- confidence: high

#### E-004
- title: episode outcome 持有 19 条证据
- run_id: run_20260814_021938_990234
- step_or_span_id: `outcome.evidence`
- native_or_normalized: native
- source_type: file
- source_ref: 同 run 目录 `continuous-episode.json`
- observed_at: 2026-08-14T02:19Z
- raw_excerpt: |
    "evidence":[{"tool":"graph_lookup","title":"概念 光刻胶","detail":"匹配分 20",
     "source":"本地知识图谱","internal_locator":"wiki/relations/concept_graph.json"}…]
    semantic_verifier.public_answer: "…本轮已取得 19 条证据，但未完成核验绑定，暂不能引用…"
- observation: 证据数组非空（19 条）；runtime 自己的公开话术明确说明证据存在但未绑定。
- confidence: high

#### E-005
- title: 三个 eb=0 的 B 组 turn 的 draft 为空串
- run_id: run_20260814_021938_990234 / _022213_461612 / _022528_364515
- step_or_span_id: `outcome.draft`
- native_or_normalized: native
- source_type: file
- source_ref: 三个 run 目录的 `continuous-episode.json`
- observed_at: 2026-08-14T02:19–02:25Z
- raw_excerpt: |
    B1: draft 长度=0  evidence=19   bindings=0
    B2: draft 长度=0  evidence=24   bindings=0
    B4: draft 长度=0  evidence=125  bindings=0
- observation: 证据最多的 B4（125 条）draft 同样为空，bindings 为 0。
- confidence: high

#### E-006
- title: 另一形状——draft 与 bindings 都存在但 eb 仍为 0
- run_id: run_20260814_022902_659281 / _023030_100048 / _021218_897744
- step_or_span_id: `outcome.draft` / `outcome.bindings` / `structural_verifier`
- native_or_normalized: native
- source_type: file
- source_ref: 对应 run 目录 `continuous-episode.json`
- observed_at: 2026-08-14T02:12–02:30Z
- raw_excerpt: |
    B5: draft 307 字  evidence=29  bindings=2  outputs={"direct_answer":"missing","evidence_boundary":"missing"}
    B7: draft 266 字  evidence=13  bindings=2  同上
    A6: draft 182 字  evidence=1   bindings=2  同上（A 组同形状）
- observation: 这三个 turn 已产出 draft 且有 2 条 binding，`evidence_bound` 仍为 0；A6 属 A 组，说明该形状不按题组分布。
- confidence: high

#### E-007
- title: 交付层证据只从 trace 的 retrieval 构造
- run_id: n/a
- step_or_span_id: `_run_context`
- native_or_normalized: normalized
- source_type: code_reading
- source_ref: `intelligence/api/app.py:1661-1718`；`intelligence/runtime/conversation_orchestrator.py:3563-3584`；`intelligence/runtime/continuous_turn_adapter.py:1460-1493`
- observed_at: 2026-08-15
- raw_excerpt: |
    app.py:1667      retrieval = step.get("retrieval")
    app.py:1668-1669 if not isinstance(retrieval, dict): continue
    orchestrator:3564  if citations:            # 空则整步不发射
    adapter:1468-1470  if item.content_hash not in bound_hashes: continue
- observation: 三处串成一条 fail-closed 链；`outcome.evidence` 在任何一处都不被交付层直接读取。
- confidence: medium

#### E-008
- title: 18 个 turn 的判别式全命中
- run_id: 18 个 A/B run
- step_or_span_id: `continuous:evidence`
- native_or_normalized: native
- source_type: trace
- source_ref: 18 个 run 目录的 `trace.jsonl` 与验收 JSON 的 `evidence_bound`
- observed_at: 2026-08-14
- raw_excerpt: |
    有 continuous:evidence 步 → eb>0：A1,A2,A3,A4,A5,A7,A8,A9,A10,B8（10/10）
    无 continuous:evidence 步 → eb=0：A6,B1,B2,B3,B4,B5,B6,B7（8/8）
    judge_status=unavailable 但 eb>0：A8(14)、B8(11) —— provider 健康度非判别式
- observation: 判别式 18/18 命中；`judge_status` 与 eb 不构成对应关系。
- confidence: high

#### E-009
- title: C2-C10 从未执行
- run_id: n/a
- step_or_span_id: 验收 JSON `cases[].turns[0]`
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/eval/runs/20260813T1810Z-qc28-full.json`（`sha256=8536c231…578d80`）
- observed_at: 2026-08-13T18:38Z
- raw_excerpt: |
    C2..C10: status=error  trace_steps=0  error="<urlopen error [Errno 61] Connection refused>"
    C1:      status=completed  trace_steps=22  evidence_bound=8
- observation: C 组 10 题中 9 题因连接被拒未执行，其 eb=0 是未运行的默认值；唯一执行的 C1 反而 eb=8。
- confidence: high

### Findings

#### F-001
- title: 题材研究 turn 取证后未产出 draft，证据无从绑定
- status: candidate
- failure_span_id: `run_20260814_021938_990234` / `continuous:adapter:finalizing`
- root_location: `continuous_turn_adapter.py` 合成边界
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- violated_authority: user
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-004, E-005]
- confidence: medium
- explanation: 见 PRIMARY 段。竞争 L0 未分胜负，保持 candidate。

#### F-002
- title: 验收台 evidence_bound 把四种运行态压成同一个 0
- status: validated
- failure_span_id: `intelligence/eval/acceptance.py:196-200`
- root_location: 验收指标定义域
- l0: HARNESS
- l1: observe
- l2: `configuration-mismatch-category-tool-definition`
- l3: n/a
- violated_authority: tool_contract
- causality: SECONDARY_FAILURE
- propagation_impact: [INCORRECT_PATH]
- failure_detection_timing: SILENT_UNDETECTED
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-003, E-008, E-009]
- confidence: high
- explanation: 见 SECONDARY 段。该指标在 08-14 直接导致把「未执行」读成「设计行为」。

#### F-003
- title: answer_coverage 与 structural_verifier 对同一 output 给出相反判定
- status: validated
- failure_span_id: `continuous:answer_coverage` vs `structural_verifier`
- root_location: 两套输出判定各自独立、无对账
- l0: HARNESS
- l1: observe
- l2: `execution-error-category-formatting`
- l3: n/a
- violated_authority: none
- causality: SECONDARY_FAILURE
- propagation_impact: [NO_PROPAGATION]
- failure_detection_timing: SILENT_UNDETECTED
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-006]
- confidence: high
- explanation: 抽查 9 个 turn 有 6 个冲突（B1/B2/B4 的 `counterpoint`，A6/B5/B7/B8 的 `evidence_boundary`）：coverage 报 present、verifier 报 missing。**该冲突在 eb>0 的 B8 上同样出现，故不解释本次失败**，仅作独立观测缺陷记录。

### Path

#### P-001
- title: 19 条证据如何走到交付层的 0
- start: `continuous:episode:6/8/10:tool_result` —— 工具成功返回，证据进入 episode
- goal: 验收台 `evidence_bound=0`，用户看到「证据不足」
- steps:
  1. 工具取证成功，`outcome.evidence` 累积 19 条 — evidence: E-003, E-004 — finding: none
  2. **合成未产出 draft**，`outcome.draft=""`、`outcome.bindings=0` — evidence: E-005 — finding: F-PRIMARY (F-001)
  3. `_public_citation_projection` 按 `content_hash ∉ bound_hashes` 逐条丢弃全部 19 条 — evidence: E-007 — finding: none（按设计）
  4. `citations` 为空 → `if citations:` 不成立 → `continuous:evidence` 步不发射 — evidence: E-007, E-008 — finding: none（按设计）
  5. `/api/runs/{id}/context` 只从 `trace[].retrieval` 取证据 → `evidence[]=[]` — evidence: E-007 — finding: none（按设计）
  6. 验收台计数得 0，与「未执行」「没取到」同码 — evidence: E-008, E-009 — finding: F-SECONDARY (F-002)
- residual_uncertainty:
  - RU-1：空 draft 是模型未返回，还是合成阶段被预算/provider 截断后写入空串——当前产物无区分变量。
  - RU-2：B5/B7/A6 形状中，`bound_hashes` 为空是因 `binding.output_id ∉ allowed_output_ids`，还是因 `binding.evidence_hashes` 本身为空——`bindings` 的内部字段未落盘。
  - RU-3：C2-C10 的 `Connection refused` 发生在验收台侧还是服务侧，是否影响 A/B 组同批次读数的可比性。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260815-01 | F-002 | `EVAL_ONLY` | 把 `evidence_bound` 由单标量扩为携带成立条件的三元组：`(retrieved, bound, delivered)`，并在 turn 级记录 `execution_state ∈ {not_run, no_tool_call, retrieved_unbound, bound}`。不改任何生产行为。 | 重放同一份 `20260813T1810Z-qc28-full.json` 对应的 run 目录后：B4 读作 `retrieved=125, bound=0`，B3 读作 `retrieved=0, bound=0`，C2-C10 读作 `not_run`，三者**不再同码**；A6 与 B5/B7 归入 `retrieved_unbound` 而非与 B3 同类 | 新增离线用例，用本轮 19 个 run 目录作夹具，断言四种 `execution_state` 各至少命中一例；跑 `.venv-workbench/bin/python -m pytest intelligence/tests/ -k acceptance` |
| R-20260815-02 | F-002 | `EVAL_ONLY` | 验收台在 `status=error` 且 `trace_steps=0` 时，禁止把该 turn 计入任何质量分母（当前 C2-C10 被计入并拉低读数） | 同一份产物重算后，C 组分母由 10 降为 1（仅 C1），且报告显式列出 9 个 `not_run` | 断言 `not_run` turn 不进入 `evidence_bound` 统计的单测 |
| R-20260815-03 | F-003 | `DATA_CONTRACT_FIX` | `answer_coverage` 与 `structural_verifier` 对同一 `output_id` 的判定必须来自同一判据函数；两者不一致时 fail closed 并记一条 warning，而不是各写各的 | 重放本轮 9 个 run：6 处冲突全部消失或转为显式 warning；`B8` 的 `evidence_boundary` 不再同时是 present 与 missing | 用本轮冲突的 6 个 run 作回归夹具，断言无静默分歧 |
| R-20260815-04 | F-001 | `HARNESS_FIX` | 在 `outcome` 落盘时补记 `draft_source ∈ {model_returned_empty, truncated_by_budget, provider_error}` 与合成入口的 `remaining_ms`——这是分开 RU-1 两个竞争 L0 所需的**那一个变量** | 下一次出现空 draft 的 turn，其 `draft_source` 非空；若为 `model_returned_empty` 则 F-001 的 L0 定为 REASONING，若为 `truncated_by_budget` 则定为 HARNESS | 该字段的存在性单测；**不得**据此单次读数直接结案，需 ≥3 个同形样本 |

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| RU-1 空 draft 成因 | F-001 的 L0（REASONING vs HARNESS） | `draft_source` 枚举 + 合成入口 `remaining_ms`；阈值：`remaining_ms < 5000` 视为预算侧嫌疑 | `continuous_turn_adapter` 写 `outcome` 处 | 空 draft 是模型没写还是被截断 | 低 |
| RU-2 bound_hashes 为空的成因 | B5/B7/A6 形状的 PRIMARY 定位 | 落盘 `bindings[].output_id` 与 `len(evidence_hashes)`；阈值：`evidence_hashes==0` 即绑定侧为空 | `outcome.bindings` 序列化处 | 是 output 未许可，还是绑定本身无证据 | 低 |
| RU-3 Connection refused 归属 | A/B 组同批次读数可比性 | 验收台记录每次请求失败时的 `base` 与本地端口存活探测结果（一次 TCP connect） | `intelligence/eval/acceptance.py` 请求失败分支 | 是服务挂了还是验收台侧网络问题；决定该批次是否整体作废 | 低 |
| workbench `tool` 步缺失（trace-profile §8 旧记载） | —— 已不成立，本轮实测 `trace.jsonl` 含逐工具 `tool_request/tool_result/tool_error` | 无需新埋点，改的是文档 | `docs/trace-profile.md` §8 | 该行盲区已闭合，应从缺口表移除 | 零 |

## self_report_vs_observed 对账

本 run 同时存在「机器状态字段」与「给用户看的人类可读输出」，按证据契约固定对账。**trace 的 `output_summary` 是展示话术，不是观测**——把它当观测读，正是本问题此前被反复读成「证据取到了又丢了」的原因之一。

| 事项 | 人类可读输出（自述） | 机器状态字段（观测） | 判定 |
|---|---|---|---|
| 工具是否取到证据 | `continuous:episode:6/8/10:tool_result` → 「已取得一批可核验资料。」 | `outcome.evidence` = 19 条 | **一致**，自述属实 |
| 是否在组织回答 | `continuous:episode:13:finalization` → 「证据收集完成，正在组织回答。」 | `outcome.draft = ""` | **冲突** |
| 回答是否已形成 | `continuous:episode:16:finish` 与 `23:finish` **两次**输出「研究回答已形成，正在完成最终核验。」 | `outcome.draft = ""`、`bindings=0`、`report.json.answer_status=partial` | **冲突（最严重）**：trace 两次宣告回答已形成，而 draft 自始至终是空串 |
| 证据可否引用 | `semantic_verifier.public_answer` → 「已取得 19 条证据，但未完成核验绑定，暂不能引用」 | `evidence_bound = 0` | **一致**，这是全链唯一如实的一句 |

按 source precedence（原始 trace span / 机器字段 > agent 自述），以机器字段为准：**B1 从未产出回答正文**。上表第 2、3 行的冲突本身记为 F-003 的同族证据——运维只看 trace 时间线会看到一条「成功」路径，而真实终态是空 draft。这类「话术层全绿、字段层为空」的分歧应当 fail closed 报警，不应静默并存。

## Limits and counterevidence

- **未确认单一 PRIMARY。** eb=0 的 8 个 turn 至少含三形状，本报告只对「取到未合成」（B1/B2/B4）给出候选 PRIMARY，且其 L0 未定夺。B5/B7/A6 形状缺 `bindings` 内部字段，无法定位。
- **反证：`evidence_bound=0` 在交付层语义正确。** 丢弃是显式 fail-closed 规则的结果，不是缺陷。把它当作「证据丢失」去修 `ask.py` 或改路由（08-14 方案 B1/B2）会修错地方。
- **08-14 那份 ad-hoc 诊断的两条事实前提不成立**：其一「所有 turns 都有 trace_steps，说明 episode 确实执行了」——C 组 9/10 的 `trace_steps=0`；其二「C 组走 quick_fact 是设计行为」——C 组唯一真正执行的 C1 反而 `evidence_bound=8`。该文件的置信度表（「C 组走 quick_fact 路径 95%」）建立在未执行的 turn 上。
- 本报告未读取 agent-run-triage skill 的受控验收目录，符合防污染要求。
- `code_reading` 为主要支撑的 E-007 已按契约封顶 `confidence: medium`。
- 混淆因子读数：run 冻结 revision `71b50300`、backend `continuous_glm`、base `127.0.0.1:8792`；数据新鲜度 `latest_data_date=2026-08-13` / `today=2026-08-14`（1 日滞后，覆盖 B4 所问的 07-23）；provider 为 `openai` / `gpt-5.6-terra`，18 个 turn 中 8 个 `judge_status=unavailable`——但该字段与 eb 无对应关系（H4 REJECTED），故不作为本次归因的混杂解释。

## Next-step menu

1. 实施 R-20260815-04 的 `draft_source` 埋点，这是唯一能把 F-001 的 L0 定下来的动作，信息增益最高。
2. 实施 R-20260815-01：验收台读数改为携带成立条件的三元组——不改生产行为，却能立刻阻止下一轮再把四种病读成一种。
3. 落盘 `bindings` 内部字段（R-20260815-02 之外的 RU-2 处方），打开 B5/B7/A6 那一形状。
4. 单独立案 `_codex_mapping` 读 `payload.type` 的修复（R-02 refuted 的直接后果），它不属本轮靶子，建议由检阅方指定为下一轮。
5. 复跑 C 组 10 题并确认 `Connection refused` 是否复现；若复现，该批次 C 组读数应整体作废重跑。

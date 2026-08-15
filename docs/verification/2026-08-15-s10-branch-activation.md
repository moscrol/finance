# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_NOT_CONFIRMED
- mode: M1
- failure_criterion: 预注册 N=5 分支适格任务（谓词见 Freeze），以每题冻结时刻最新一条完整 episode 计，`branch_tool` 事件数之和 / 5 = 0 即复现「从未走进」。否命题是该窗口调用率 > 0。08-14 手记「现场三次未进路径」不是本标准；不得用全集 276 run 的非零调用率事后改口。
- trace_coverage: 冻结集最新窗口 5 条 episode（`run_20260815_182037_434217` / `182537_751801` / `182731_454211` / `182902_790837` / `183924_701039`）。对照：同题历史 run（B4/B7/B8/C9 曾走进 deep+branch；B5 七次全跳过 PLAN）。代码路径 `agent_episode._run_sub_research`、`mode_governor.decide`、`parse_plan_candidate`、`episode_protocol` PLAN 段、`ResearchToolRegistry.tool_definitions`。未开新 live 批；`/tmp/finance-8792-live.lock` 当时不在。未读 skill 受控验收目录。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Freeze

- frozen_at: 2026-08-15T23:42:08+08:00
- predicate: 多子题可并行 ∧ 单子题需独立检索 ∧ 题面不含「简答」约束
- scoring_window: 每题取冻结时刻最新一条完整 `continuous-episode.json`（晚间 18:20–18:39 窗）
- note: 冻结前做过 276-run 地貌扫描，只用来发现 08-14「全集零调用」已过时；N=5 清单与计分窗在本段登记后才做逐题归因，未事后换题。

| freeze_id | question | latest run | plan event | branch_goals | requested/effective | branch_started | branch_tool |
|---|---|---|---|---|---|---|---|
| S10-B4 | 电网设备是怎么发酵到 2026-07-23 双红的，把链路回溯一下 | `run_20260815_182037_434217` | yes | 3 | deep/deep | 3 | 9 |
| S10-B5 | 2026-07-23 涨停热度前四的题材里，哪些同时也是双红板块 | `run_20260815_182537_751801` | no | — | — | 0 | 0 |
| S10-B7 | 2026-07-21 到 07-24 量能和情绪是怎么演化的 | `run_20260815_182731_454211` | no | — | — | 0 | 0 |
| S10-B8 | 立新能源现在贵不贵，隐含了什么预期 | `run_20260815_182902_790837` | yes | 0 | quick/quick | 0 | 0 |
| S10-C9 | 2026-07-23 电网设备为什么涨，给出证据来源 | `run_20260815_183924_701039` | yes | 3 | quick/quick | 0 | 0 |

冻结窗调用率 = 1/5 ≠ 0。原标准未复现。

## Prior prediction closure

无先前 S10 分诊报告。Open 表其余行本次 trace 给不出新证据，保持 pending。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| no prior S10 report | — | — | still_pending | none | 本报告是 S10 Phase A 首份标准 M1 |
| 轨道 A Round 5 | R-20260815-24 | marker-loss 后不得再同时「结构 fulfilled + gap_output_ids 含这些 ID + citations=0」 | still_pending | none — 本诊断不读 semantic verifier | 不回写该行 |
| 轨道 A Round 5 | R-20260815-25 | 新 `tool_exception` 的 `detail` 非空无路径 | still_pending | none | 不回写该行 |
| L7 finalization T3 | R-20260804-10 | deadline-aligned per-tool handoff | still_pending | none | 本轨道不写该行 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `ROUTING_FIX`=0；`SYSTEM_PROMPT_FIX`=0；`TOOL_DESCRIPTION_FIX`=0；`HARNESS_FIX`=1（距升格线 2，与本次无关）

## Executive finding

冻结集上「branch_tool 零调用」未复现：S10-B4 已走 PLAN→deep→3 条 `branch_started`→9 条 `branch_tool`。其余四题停在三条不同机制（跳过 PLAN、PLAN JSON 缺 `kind`、已声明 `branch_goals` 被 `model_requested_quick` 短路），没有区分实验能把其中一条定为全班第一处错误变换。H2（预算不可见抑制分支）按 spec 封堵，不得作 PRIMARY。

## Local vocabulary ↔ L1

本仓 `trace-profile.md` §6 词表 `triage-l1-9`。episode native kinds 按下表映射；无独立 `route` 事件，`mode_decision` 按运行时语义落到 `route`（是否批准 deep / 是否点火 sub_research），不压进 `plan`。

| 本地 kind / 代码点 | L1 | provenance |
|---|---|---|
| 系统提示 PLAN 段 / `tool_definitions` | `configure` | 代码契约 |
| `task` | `intent` | episode native |
| `plan` / `parse_plan_candidate` | `plan` | episode native + 解析 |
| `mode_decision` / `_run_sub_research` 门闩 | `route` | episode native + 代码；本地无 `route` kind，显式声明损耗 |
| `branch_started` | `retrieve` | profile：`runtime-benchmark` 映射 |
| `tool_request` / `branch_tool` | `tool` | episode native；`branch_tool` 是 ledger 事件不是模型可见 tool |
| `tool_result` / `branch_completed` | `observe` | episode native |
| `finish` | `stop` | episode native |

损耗：`mode_decision` 若按 profile 的 runtime-benchmark 行会进 `plan`；本报告不采用那条压缩，否则「是否批准分支」无法表达为 `route`。未映射事件保持 `unmapped`。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 分支适格题能看见进入子研究的合法路径 | `tool_definitions` 无 `branch_tool`；协议写 PLAN 可选，且 `branch_goals` 须 deep 批准 | ok（按现行契约） | E-006、E-007 |
| plan | 适格题发出合法 `kind=PLAN` 且 `branch_goals` 非空 | B4/C9 合法 PLAN；B8 PLAN 但 goals=[]；B5 空正文直接调工具；B7 JSON 缺 `kind` 未被解析 | fail（4/5 未形成可执行分支意图） | E-002、E-003、E-004、E-008 |
| route | 已声明的 `branch_goals` 在可观察 `separable_sub_research_branch` 时进入 sub_research | B4 deep+批准；C9 `reason=model_requested_quick`、`max_branches=0`、`_run_sub_research` 因非 deep 返回 None | fail（C9） | E-001、E-005 |
| tool | 分支检索以 `branch_tool` 入账 | B4：9 次；其余 0 | fail（相对原标准）/ ok（相对「能否走进」） | E-009 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| freeze-set latest window（5 runs） | UNCLEAR | route | DEPTH_INSUFFICIENT(D4) | 调用率 1/5；C9 `effective_mode=quick` 且 `branch_goals=3`；B5/B7 无 `plan` 事件 | medium |

`exact L2` 停在 DEPTH_INSUFFICIENT(D4)：D3 已看见三条机制各自的入口条件，但要把其中一条定为全班 PRIMARY，需要固定 PLAN/goals、只变 `requested_mode` 或解析器的单变量对照。未做该对照，不硬选 leaf。

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | prompt/工具清单未有效呈现 `branch_tool`，故生产零调用 | 若成立：冻结窗 5 题 `branch_tool=0`，且模型从未发出 `branch_goals` | E-006、E-009 | REJECTED | — | `branch_tool` 确不在工具清单，但 B4 仍走 coordinator 发出 9 次；零调用不是当前事实 |
| H2 | 预算不可见抑制昂贵分支（与 S1 交互） | 若成立：S1 落地前适格题系统回避 deep/branch | E-009 | INCONCLUSIVE | S1 落地后同一冻结集最新 run：仅 S1 变化时，若 B5 `branch_tool>0` 则升 CONFIRMED；若 B5 仍 0 且 C9 仍 `model_requested_quick` 则 REJECTED | spec §4 封堵：S1 前不得结案为 PRIMARY |
| H3 | 工具描述不满足触发语义 | 若成立：存在名为 `branch_tool` 的 tool schema 且描述导致模型不选 | E-006 | REJECTED | — | 无此工具可描述；激活不走 tool_choice |
| H4 | mode_governor/frame 从不进 PLAN 分支态 | 若成立：任何 `plan.branch_goals` 都不会变成 `branch_started` | E-001、E-005、E-009 | REJECTED | — | B4 `observable_complexity_approved` 且 3 条分支已跑。C9 是「goals 已声明、quick 短路」的子集，不能把「从不」写成全班根因 |
| H5 | 任务分布本身不需要分支（`NO_SYSTEM_FIX`） | 若成立：冻结集按谓词本就不该分支，模型也不该写 `branch_goals` | E-001、E-009 | REJECTED | — | 谓词预注册；C9 写出 3 条独立检索目标，B4 已执行同类目标。分布「不需要」与证据冲突 |

## Causal findings

### PRIMARY

- failure_span_id: freeze-set/`2026-08-15T23:42:08+08:00`/latest-window
- root_location: 竞争点：`parse_plan_candidate`（B5/B7）↔ `mode_governor.decide` + `agent_episode._run_sub_research`（C9）↔ 模型 `requested_mode=quick` 且 `branch_goals=[]`（B8）
- excerpt: C9 `reason=model_requested_quick` + `branch_goals=3` + `max_branches=0`；B7 首轮 JSON 无 `kind`；B5 首轮 `content=''` 且 4 个 tool_calls
- l0: UNCLEAR
- l1: route
- l2: DEPTH_INSUFFICIENT(D4)
- l3: n/a
- causality: UNCLEAR
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-003, E-005, E-008]
- explanation: 原标准「零调用」被 B4 证伪。剩下的未激活不能收成一个 leaf：有的从未形成合法 PLAN，有的形成了 PLAN 却申请 quick，有的申请了分支仍被 deep 门闩丢掉。D3 够描述各条机制，不够在它们之间做全班第一因果层选择。

### SECONDARY / TERTIARY

none — 未确认 PRIMARY，不把竞争机制升格成已确认 SECONDARY leaf（避免与 UNCLEAR 自相矛盾）。机制观察见 Evidence / Path。

## Evidence → Finding → Path

### Evidence

### E-001
- title: C9 已声明 3 条 branch_goals，mode 仍 quick
- run_id: run_20260815_183924_701039
- step_or_span_id: run_20260815_183924_701039/plan.3+mode_decision.4
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260815_183924_701039/continuous-episode.json` seq 3–4
- observed_at: 2026-08-15T18:39:37.487+08:00
- raw_excerpt: |
    plan.branch_goals=['核验当日板块与全市场的相对表现','核验同窗口政策、招标或订单催化','评估资金轮动与板块分化这一替代解释']
    requested_mode=quick
    mode_decision: effective_mode=quick approved=false reason=model_requested_quick
    observable_conditions=['separable_sub_research_branch','multiple_evidence_domains','material_uncovered_answer_element']
    max_branches=0
- observation: 合法 PLAN 带 3 个可分离目标；governor 记下了 separable 条件，但生效模式是 quick，随后无 `branch_started` / `branch_tool`。
- confidence: high

### E-002
- title: B5 首轮跳过 PLAN，直接四工具并行
- run_id: run_20260815_182537_751801
- step_or_span_id: run_20260815_182537_751801/model_turn.2
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260815_182537_751801/continuous-episode.json` seq 2
- observed_at: 2026-08-15T18:25:37+08:00
- raw_excerpt: |
    content=''
    tool_calls=['market_data','mainline_context','finance_query','finance_query']
    no plan / mode_decision / branch_* events
- observation: 无 PLAN 正文，无 `plan` 事件。同题历史 7 条 run 均为无 PLAN、无 branch。
- confidence: high

### E-003
- title: B7 发出计划形 JSON 但缺 kind，解析器丢弃
- run_id: run_20260815_182731_454211
- step_or_span_id: run_20260815_182731_454211/model_turn.2
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260815_182731_454211/continuous-episode.json` seq 2
- observed_at: 2026-08-15T18:27:31+08:00
- raw_excerpt: |
    keys=['task_summary','answer_elements','hypotheses','evidence_needs','candidate_actions','open_gaps','requested_mode','revision']
    requested_mode=quick
    'kind' not in payload
    branch_goals=None
- observation: 首轮是计划字段齐全的 JSON，但没有 `kind`。无 `plan` 事件。
- confidence: high

### E-004
- title: parse_plan_candidate 在缺 kind 时返回空计划
- run_id: n/a
- step_or_span_id: intelligence/services/research_plan.py:193-194
- native_or_normalized: normalized
- source_type: code_reading
- source_ref: `intelligence/services/research_plan.py:193-194`
- observed_at: 2026-08-15
- raw_excerpt: |
    if not isinstance(payload, dict) or "kind" not in payload:
        return PlanParseResult(None)
- observation: 缺 `kind` 的对象不会成为 `ResearchPlan`。与 E-003 同形。
- confidence: high

### E-005
- title: sub_research 门闩要求 effective_mode==deep 且 branch_goals 非空
- run_id: n/a
- step_or_span_id: intelligence/runtime/agent_episode.py:1756-1762
- native_or_normalized: normalized
- source_type: code_reading
- source_ref: `intelligence/runtime/agent_episode.py:1756-1762`；`intelligence/services/mode_governor.py:190-195`
- observed_at: 2026-08-15
- raw_excerpt: |
    if coordinator is None or decision is None or decision.effective_mode != "deep" or not plan.branch_goals:
        return None
    if requested == "quick":
        return _quick_decision(..., reason="model_requested_quick", conditions=observable)
- observation: 可观察条件被记录，但不阻止 `model_requested_quick`。非 deep 时即使 goals 非空也不点火。
- confidence: high

### E-006
- title: branch_tool 不在模型可见工具清单
- run_id: n/a
- step_or_span_id: intelligence/services/research_tool_registry.py:480-501
- native_or_normalized: normalized
- source_type: code_reading
- source_ref: `intelligence/services/research_tool_registry.py:480-501`；`_TOOL_CONTRACTS` 键
- observed_at: 2026-08-15
- raw_excerpt: |
    tool_definitions() → authorized_specs only
    names: finance_query, evidence_search, kb_search, web_search, news_search,
    graph_lookup, evidence_lookup, memory_lookup, market_data, financial_data, mainline_context
    no branch_tool
- observation: 模型不能用 tool_choice 调用分支。分支只从 `consume_sub_research` 记 ledger 事件。
- confidence: high

### E-007
- title: 协议把 PLAN 写成可选，并把 branch 绑在 deep 批准上
- run_id: n/a
- step_or_span_id: intelligence/services/episode_protocol.py:170-176
- native_or_normalized: normalized
- source_type: file
- source_ref: `intelligence/services/episode_protocol.py:170-176`
- observed_at: 2026-08-15
- raw_excerpt: |
    第一轮可以先只输出一个 kind=PLAN 的 JSON 对象……也可以在任务简单时直接调用已授权工具。
    branch_goals 只是申请，只有运行时批准 deep 后才能执行
- observation: 跳过 PLAN 与申请 quick 都是协议允许的。C9 的短路与这段文字一致。
- confidence: high

### E-008
- title: B8 合法 PLAN，branch_goals 为空且请求 quick
- run_id: run_20260815_182902_790837
- step_or_span_id: run_20260815_182902_790837/plan.3+mode_decision.4
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260815_182902_790837/continuous-episode.json` seq 3–4
- observed_at: 2026-08-15T18:29:15.367+08:00
- raw_excerpt: |
    branch_goals=[]
    requested_mode=quick
    reason=model_requested_quick
    observable_conditions=['multiple_evidence_domains','material_uncovered_answer_element']
    max_branches=0
- observation: 有 PLAN 事件，但没有可执行分支申请。同题在 `run_20260814_225926_202832` 曾 deep+9 次 `branch_tool`。
- confidence: high

### E-009
- title: 冻结窗调用率 1/5；B4 反证「从未走进」
- run_id: run_20260815_182037_434217
- step_or_span_id: run_20260815_182037_434217/mode_decision.4+branch_started.5-7
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260815_182037_434217/continuous-episode.json` seq 4–7、11–19
- observed_at: 2026-08-15T18:20:51.756+08:00
- raw_excerpt: |
    requested_mode=deep effective_mode=deep approved=true
    reason=observable_complexity_approved
    branch_started×3 branch_tool×9 (finance_query)
    freeze-window rate=1/5
- observation: 现行运行时能走进分支。08-14 手记不能当作 08-15 晚间全集事实。
- confidence: high

self_report_vs_observed：C9 机器状态同时给出 `observable_conditions` 含 `separable_sub_research_branch`（自报：看见了可分离分支）和 `effective_mode=quick` / `max_branches=0` / 无 `branch_*`（观察：没走分支）。以事件流与 `_run_sub_research` 门闩为准，条件字段只是记录，不授权。B7 人类可读输出是一份计划，机器状态没有 `plan` 事件——以解析器为准。

### Findings

### F-001
- title: 冻结标准「零调用」未复现；全班 PRIMARY 未分胜负
- status: validated
- failure_span_id: freeze-set/`2026-08-15T23:42:08+08:00`/latest-window
- root_location: 多点竞争，见 PRIMARY
- l0: UNCLEAR
- l1: route
- l2: DEPTH_INSUFFICIENT(D4)
- l3: n/a
- violated_authority: none
- causality: UNCLEAR
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-003, E-005, E-008, E-009]
- confidence: medium
- explanation: WHAT：原投诉的零调用在预注册集上不成立。WHY：B4 提供反证；其余四题机制互不蕴含。IMPACT：Phase B 若只改一层（只改 prompt 或只改 deep 门闩）不能预期冻结集调用率单独翻盘。

### Path

### P-001
- title: 冻结窗里「能走」与「没走」如何分叉
- start: 五道预注册适格题进入同一 runtime（coordinator 存在，B4 证明）
- goal: 原标准要求 5/5 `branch_tool=0`；实际 1/5 > 0
- steps:
  1. configure 允许跳过 PLAN，且 branch 不是模型可见工具 — evidence: E-006、E-007 — finding: F-001
  2. B5 直接 tool_calls；B7 计划 JSON 缺 `kind` 被丢弃 — evidence: E-002、E-003、E-004 — finding: F-001
  3. B8 PLAN 但 `branch_goals=[]` 且 quick — evidence: E-008 — finding: F-001
  4. C9 PLAN 已有 3 goals，`model_requested_quick` 使 `_run_sub_research` 返回 None — evidence: E-001、E-005 — finding: F-001
  5. B4 同协议下 `requested_mode=deep`，分支入账 — evidence: E-009 — finding: none
- residual_uncertainty: 无单变量对照能把 C9 的 quick 申请从「模型选择」与「预算不可见」里切开（H2）；也未测「只改 deep 门闩、保持 requested_mode=quick」时 C9 是否点火

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-026 | F-001 | EVAL_ONLY | 冻结谓词与 N=5 题写入 `intelligence/eval/cases/s10_branch_eligible_tasks.json`，供 Phase B / S1 A/B 复用，不改生产行为 | 夹具字段含 predicate、frozen_at、五题原文与 latest run_id；生产 prompt/路由哈希不变 | 禁止把 08-14 三次现场当作全集零调用基线 |
| R-027 | F-001 | ROUTING_FIX | 候选，非已确认根因：当 `plan.branch_goals` 非空且 `separable_sub_research_branch` 在场时，不要让 `model_requested_quick` 把 `max_branches` 置 0 / 跳过 `_run_sub_research`。Phase B 且须排 dsh 第 5 步与 S1 之后 | 同形 C9（goals≥1 + requested_mode=quick）应出现 `branch_started`≥1；B4 深路径行为不变 | 固定 C9/B4 冻结 run 的 PLAN 回放；B8 goals=[] 仍不点火 |
| R-028 | F-001 | SYSTEM_PROMPT_FIX | 候选：若走 prompt 而非改门闩，则明确「写出 branch_goals 必须 requested_mode=deep」，并强调 PLAN 的 `kind` 判别器。不把 H2 写进本条 | 同形 C9 的新 PLAN `requested_mode=deep` 或不再写空转 goals；B7 同形 JSON 带 `kind=PLAN` | 冻结集调用率单独看不够；须按题看 PLAN 合法性 |

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| H2 / 预算不可见 | 不能把 C9 的 quick 申请从 S1 交互里切开 | S1 落地后冻结集最新 run 的 `requested_mode` 与 `branch_tool` 计数；B5 `branch_tool>0` 或 C9 仍 `model_requested_quick` | 状态栏 v1 + 本夹具复跑 | H2 CONFIRMED 或 REJECTED | 一次 5 题批，守 live 锁 |
| C9 门闩 vs 模型选择 | 全班 PRIMARY 选不成 ROUTING 还是 REASONING | 回放 C9 冻结 PLAN，只改 `requested_mode` 或只改 `_run_sub_research` 门闩；`branch_started` 从 0→≥1 即该臂充分 | 离线 coordinator 回放，不跑 8792 | 能否把 F-001 收成单点 PRIMARY | 单测级 |
| B7 解析丢弃是否可观测 | 计划形输出被当成普通 turn | `parse_plan_candidate` 落盘 `plan_rejected_reason`（缺 kind / 非法 JSON）；该窗 B7 应为 `missing_kind` | `plan` 负事件或 `invalid_action` | 缺 kind 与真跳过 PLAN 可分 | 一行字段 |

## Limits and counterevidence

- 08-14 `docs/handoffs/2026-08-14-tool-observability.md` 写「8801 三道现场题 GLM 都跳过 PLAN」是当时那三题的观察，不能外推到 08-15 晚间冻结集。
- B5 七次独立 run 全跳过 PLAN，是最稳的「这题不走分支」样本，但仍不能证明工具清单是全班根因。
- 同题跨日方差大：B7 `run_20260815_104427_961001` 曾 deep+12 次 `branch_tool`；B8 `run_20260814_225926_202832` 曾 deep+9 次。单次 latest-run 计分会把历史反证留在窗外——这是预注册窗口纪律，不是否认那些 run。
- 未开新 8792 live 批。Phase A 零行为改动。
- 未把 H2 写成 PRIMARY。

## Next-step menu

1. 用本夹具做 C9 单变量回放（只改 deep 门闩 vs 只改 requested_mode），再决定 Phase B 开不开、开哪条。
2. S1 落地后复跑冻结集 5 题，按 H2 的阈值结案或拒绝预算假说。
3. 给 `parse_plan_candidate` 负结果落盘，把 B7 与 B5 从「都没 plan 事件」里分开。
4. 不要派 Phase B 去改 `episode_semantic_verifier.py` 或 `acceptance.py`。
5. 不要把 08-14 三次现场当「生产调用率=0」的基线。
6. dsh 第 5 步仍占 `agent_episode.py`；任何 Phase B 路由改动等它合入后再 rebase。

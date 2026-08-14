# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M2
- failure_criterion: 在预注册四臂中，用真实生效预算判定 `headless_timeout` 首先绑定于 0.65 关门阈值、root 总时长还是工具调用上限；只有事件级 `finish.payload.stop_reason=headless_timeout` 计为超时，缺 `finish` 的 infrastructure/data-contract case 记为 `not_evaluable`，不进入超时分母。
- trace_coverage: 4 个 profile × 5 个冻结 case，202 个 runtime event；另有 2-case R-04 真 run。四份归一化产物均为 `normalized-harness-trace-2` / `triage-l1-9`，`unmapped_count=0`。缺少原生 `finalization` 事件与事件时间戳。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Prior prediction closure

这是本项目第一份标准四阶段 triage 报告；此前条目来自代码审计/设计收口，不继承其 PRIMARY，但按账本要求先闭环其预测。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 2026-08-04 收口审计 | R-20260804-02 | 真 Codex rollout 中 `function_call_output` 归入 `observe` | still_pending | E-001 | 本轮只有 `runtime-benchmark`，没有真 rollout JSONL，不能用近似事件替代 |
| 2026-08-04 收口审计 | R-20260804-04 | 仅 `headless_timeout` 的新 case 不再出现 `runtime_invalid_actions:N` | confirmed | E-004 | 两个真 timeout case 均 `runtime_issues=["headless_timeout"]`、`protocol_issues=[]` |
| 2026-08-04 设计评审 | R-20260804-07 | triage 的 first bad step 与本仓 `first_divergence_step` 同空间 | confirmed | E-006 | `first_bad_step=stop`；比较产物的 `first_divergence_step=observe/stop`，全部直接落在 L1 九步，无需翻译 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: 0（本项目各 fix_type 均未连续 refuted；R-04 的 `HARNESS_FIX` 本轮 confirmed）

## Executive finding

本轮真实 timeout 的 PRIMARY 是 **root 总时长墙及其前面的未收口尾段**，不是 0.65 关门阈值，也不是调用数上限：瑞华泰在 floor 已为 0、调用只用 4/6 或 5/6、5/12 时，仍分别把 60 秒、150 秒、150 秒 root budget 用满。增加总时长只把墙从 60 推到 150，没有让该 case 收尾，因此“总时长是绑定墙”不等于“继续加时长就是修法”。

## A/B controls

- invariant inputs: 同一题面文件 SHA-256 `bec6d6944ced127166bd41cb80a09a9f9fb0d816e45cee3be13a900bda2966fe`；五题均 `as_of=2026-07-24`；同一 `codex_headless` backend、`reasoning_effort=medium`、数据根与 Wiki 根；各 case 的 `task_frame_hash` 四臂一致。
- intentional variable: a→b 只改 `gateway_floor_ratio 0.65→0.0`；b→c 只改 `total_seconds 90→180`；c→d 只改 `max_tool_calls 6→12`（d 的预注册 `minimum_tool_calls_to_exercise=7` 同属该调用容量臂）。
- uncontrolled confounders: live 模型采样不确定；artifact 只记录 `codex-account-default`，没有冻结底层模型 revision；四臂的 Git revision 因逐臂提交冻结 artifact 而不同，但三个 runtime 文件的 Git blob ID 在四个 revision 完全相同；数据根路径相同但不是 sealed physical fixture。

| normalized step | Run A span/evidence | Run B span/evidence | comparison | causal prediction |
|---|---|---|---|---|
| `tool/observe`（a→b） | a/current-mainline `:8→:9`：第三次请求被 `research_stage_closed` | b 无对应拒绝；full comparison 首分叉 `observe@5` | floor 机制只在 a 的一个 case 真激活；a 的该 case 正常结束 | 若 floor 是 timeout PRIMARY，b 应减少 timeout；实测 0→2，预测不成立 |
| `plan`（b→c） | b `total=90`、root=60 | c `total=180`、root=150；full comparison 首分叉 `observe@7` | 生效时长由 60→150，机制已激活 | 若总时长足够，瑞华泰应不再撞墙；实测仍在 150 秒 timeout |
| `plan/tool`（c→d） | c `max_steps=6`；周度归因 4 calls 后 protocol reject | d `max_steps=12`；周度归因实际 9 calls 后 model finish；full comparison 首分叉 `stop@24` | 调用扩容在周度题实际越过 6 次，但瑞华泰只用 5 次仍 timeout | 若调用上限是 timeout PRIMARY，瑞华泰应随 6→12 恢复；实测没有 |

- ablation_activation_step: a→b 在 `tool/observe`（a/current-mainline 的 gateway 拒绝）；b→c 与 c→d 在 `plan`，c→d 的新增容量首次实际被使用在 d/weekly-market-cause 的第 7 个 `tool`
- first_divergence_step: a→b=`observe`；b→c=`observe`；c→d=`stop`（来自三份 comparison artifact；是全五题序列的第一处可观察差异，不冒充 causal activation）
- first_failure_step: `stop`（瑞华泰的 root deadline 到期）
- first_bad_step: `stop`（与本仓 `STEPS` 同一 L1 空间）
- failure_surfaced_step: `observe`（`runtime_result.payload.issues` 先投影 timeout），随后 `stop` 的 `finish.payload.stop_reason` 确认终态
- reconvergence_step: none observed across the full five-case sequences
- pre_divergence_equivalence: 三份 comparison 均为 `equivalent_before_divergence`，两侧 `unmapped_counts=0`
- downstream_propagation: root deadline → `runtime_result` 报 timeout → `finish.status=partial` → arm 后处理裁为 `degraded`

### self_report_vs_observed

| 对账对象 | 机器/原始观测 | 人类可读或后处理字段 | 采用口径 |
|---|---|---|---|
| timeout 发生与暴露顺序 | `latency≈root` 证明 subprocess deadline 已先发生；序列化时 `runtime_result`（L1=`observe`）先写 issues | 下一事件 `finish`（L1=`stop`）写 `status=partial, stop_reason=headless_timeout` | 因果 first failure 记 `stop`；系统首次自报记 `observe`。两者顺序差来自投影顺序，不把 observe 误作超时源头 |
| arm status 与 runtime terminal | 多数 `finish.status=completed/partial` | arm 级统一被后处理写成 `degraded`；a/rui 写 `failed` 且无 finish | runtime 终态用事件级 finish；arm status 另列为事后质量裁决，不互相覆盖 |
| R-04 invalid action | `runtime_result.payload.issues=["headless_timeout"]` | `protocol_issues=[]`，未出现 `runtime_invalid_actions` | 两字段一致支持“超时不是模型违规” |

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| `configure` | 同题同 runtime 装配 | 四臂 task hash、registry、reasoning effort 一致；profile 另在 artifact 顶层冻结 | ok | E-001 |
| `intent` | 五题题意与截止日不变 | `task_frame_hash` 四臂逐题一致 | ok | E-001 |
| `plan` | 只让预注册预算变量变化 | 60→150 root seconds、6→12 calls 均以生效值出现 | ok | E-002 |
| `route` | Codex episode 无 skill 分派 | 结构性不存在，不造事件 | missing-by-design | E-001 |
| `retrieve` | 在调用与时间预算内取证 | 工具调用从 0 到 9；d/weekly 真正越过 6-call 线 | ok/variable | E-006 |
| `tool` | 合法调用成功或返回可见错误 | a 有 1 次 `research_stage_closed`；d/rui 有 1 次 `duplicate_query` | partial | E-003、E-005 |
| `observe` | 保留 budget、tool error、runtime issue | 202 events 全部映射，timeout 未再投影成 invalid action | ok | E-004、E-006 |
| `synthesize` | 在 root deadline 前显式进入 finalization | 0 个 `finalization` event，0 个 timestamp；只能算 post-last-result 上界 | missing | E-007 |
| `stop` | 正常 `model_finish` 或准确报告失败 | 瑞华泰在 b/c/d 分别于 60/150/150 秒 timeout | fail | E-004、E-005 |

## Terminal and budget calibration

| profile | arm status（事后裁决） | runtime finish status | event stop reason | root seconds | timeout | `research_stage_closed` |
|---|---|---|---|---:|---:|---:|
| a_control | degraded 4 / failed 1 | completed 3 / partial 1 / not_evaluable 1 | model_finish 4 | 60 | 0 | 1 |
| b_floor_ablation | degraded 5 | completed 3 / partial 2 | model_finish 3 / timeout 2 | 60 | 2 | 0 |
| c_long_capped | degraded 5 | completed 3 / partial 2 | model_finish 3 / timeout 1 / protocol_rejected 1 | 150 | 1 | 0 |
| d_long_expanded | degraded 5 | completed 4 / partial 1 | model_finish 4 / timeout 1 | 150 | 1 | 0 |

`a_control` 的瑞华泰题在 runtime 事件建立前因 `runtime source_date must be ISO date` 失败，按硬约束记为 `not_evaluable`，不把它伪装成预算失败。

### 0.65 与收尾时间

- **0.65 没有被证明过高。** 唯一真实 activation 是 a/current-mainline：第三次研究请求被关门后，run 正常 `model_finish`。把 floor 降到 0 没有改善 timeout，反而从 0 个变成 2 个。
- 10 个成功且用过工具的 case，`latency - (initial_root - last_remaining_research)` 得到的 **post-last-tool-result 上界**为 20.9–62.9 秒，中位数 24.0 秒；除 d/weekly 的 62.9 秒长尾外，其余为 20.9–29.5 秒。39 秒 reserve 对普通路径偏保守，但对长尾路径并不保证足够。
- 这不是精确 finalization 时长：202 个事件没有 timestamp，且没有一个 `finalization` event。不能把上界偷换成“收尾实际需要 24 秒”。

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `b/ruihuatai-valuation:12`，由 c`:14`、d`:16` 复现 | LOOP | stop | execution-error-category-timeout | root 60/150/150；latency 60.19/150.30/150.41；calls 4/6、5/6、5/12 | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 0.65 关门阈值是 timeout PRIMARY | floor→0 后 `research_stage_closed` 消失且 timeout 数显著下降 | E-003 | REJECTED | n/a — 机制与终态均已观测 | 关门确实消失，但 timeout 0→2；唯一关门 case 反而正常结束 |
| H2 | root 总时长墙是 persistent timeout PRIMARY | timeout latency≈root；调用未触顶；call cap 翻倍后仍复现 | E-004、E-005 | CONFIRMED | n/a — 60/150 两堵墙均已命中 | 瑞华泰在 floor=0 且 calls<cap 时连续撞 60/150/150 秒 root |
| H3 | 6-call 上限是 timeout PRIMARY | c 的 timeout case 必须用满 6 calls，d 扩到 12 后恢复 | E-005、E-006 | REJECTED | n/a — 瑞华泰在两臂均只用 5 calls | d 对周度题有边际收益，但无法解释 persistent timeout |
| H4 | `headless_command_failed` 是 timeout 的共同上游原因 | 所有 timeout 都应先出现该 issue，并在 root deadline 前失败 | E-004、E-005 | REJECTED | n/a — b 已给反例 | b 的两个 timeout 没有 command failure；c/d 的该 issue 是局部并发失败，不是共同 PRIMARY |

## Causal findings

### PRIMARY

- failure_span_id: `b/ruihuatai-valuation:12`（normalized；c`:14`、d`:16` 复现）
- root_location: Codex headless root deadline，`plan → stop`
- excerpt: `root=60.0, latency=60.187, calls=4/6`；扩时后 `root=150.0, latency=150.295/150.412, calls=5/6、5/12`
- l0: LOOP
- l1: stop
- l2: execution-error-category-timeout
- l3: n/a
- causality: PRIMARY_FAILURE
- propagation_impact: [TASK_TERMINATION, QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-004, E-005]
- explanation: 瑞华泰在关门阈值已经归零、工具调用仍低于上限时，连续把两档 root budget 全部用尽。正确状态在最后一次工具结果后仍保有 34.1/86.6/93.3 秒，随后没有可观察的 finalization 地标，最终在 root deadline 变为 timeout。总时长是绑定墙；缺少显式、受限的收尾转换使“加时长”只延后失败。

### SECONDARY / TERTIARY

none。`headless_command_failed` 只出现在 c/d 的部分 case，b 的 timeout 已构成反例；d/weekly 的 9-call 正常完成是边际收益证据，不足以升级为 persistent timeout 的 SECONDARY_FAILURE。

## Evidence → Finding → Path

### Evidence

### E-001
- title: 题面与 runtime 实现保持等价
- run_id: budget-calibration-a-b-c-d
- step_or_span_id: `configure/plan`
- native_or_normalized: normalized
- source_type: file
- source_ref: `/Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04-budget-calibration/a-control.json`、`b-floor-ablation.json`、`c-long-capped.json`、`d-long-expanded.json` 的 `#/cases/*/arms/0/diagnostics/events`
- observed_at: 2026-08-04
- raw_excerpt: |
    questions_sha256=bec6d694...2966fe
    runtime blobs across four source revisions:
    benchmark=ce45b9c9..., codex_runtime=7ea3b56c..., gateway=76f4aa07...
- observation: 五题 task hash 与核心 runtime blob 四臂一致；只有预注册 profile 字段有意变化。本轮没有真 `codex-rollout` JSONL。
- confidence: high

### E-002
- title: profile 配置被投影成真实 root 预算
- run_id: budget-calibration-a-b-c-d
- step_or_span_id: `plan`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04-budget-calibration/a-control.json`、`b-floor-ablation.json`、`c-long-capped.json`、`d-long-expanded.json` 的 `#/headless_budget_profile`
- observed_at: 2026-08-04
- raw_excerpt: |
    a: total=90, root=60, calls=6, floor=.65
    b: total=90, root=60, calls=6, floor=0
    c: total=180, root=150, calls=6, floor=0
    d: total=180, root=150, calls=12, floor=0
- observation: profile 的生效值而非仅配置值在每个 arm 的 `root_budget` 中可见。
- confidence: high

### E-003
- title: floor 只在 a/current-mainline 激活且没有导致 timeout
- run_id: a_control
- step_or_span_id: `current-mainline:9`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04-budget-calibration/a-control.json#/cases/3/arms/0/diagnostics/events`
- observed_at: 2026-08-04
- raw_excerpt: |
    seq=9 tool_error error=research_stage_closed
    seq=11 finish status=completed stop_reason=model_finish
- observation: a 有 1 次 stage close、0 次 timeout；b stage close 为 0、timeout 为 2。
- confidence: high

### E-004
- title: b 的真 timeout 未再被误记为 invalid action
- run_id: b_floor_ablation
- step_or_span_id: `ruihuatai-valuation:12`, `weekly-market-cause:17`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04-budget-calibration/b-floor-ablation.json#/cases/1/arms/0` 与 `#/cases/2/arms/0`
- observed_at: 2026-08-04
- raw_excerpt: |
    rui: runtime_issues=[headless_timeout], protocol_issues=[], latency=60.187, root=60, calls=4/6
    weekly: runtime_issues=[headless_timeout], protocol_issues=[], latency=60.049, root=60, calls=6/6
- observation: R-04 原预测端到端 confirmed；瑞华泰同时给出未触及 call cap 的 timeout 反例。
- confidence: high

### E-005
- title: 扩时与扩调用都没有移除瑞华泰的 root timeout
- run_id: c_long_capped,d_long_expanded
- step_or_span_id: `c/ruihuatai-valuation:14`, `d/ruihuatai-valuation:16`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04-budget-calibration/c-long-capped.json#/cases/1/arms/0` 与 `/Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04-budget-calibration/d-long-expanded.json#/cases/1/arms/0`
- observed_at: 2026-08-04
- raw_excerpt: |
    c: latency=150.295, root=150, calls=5/6, last_remaining=86.629, stop=headless_timeout
    d: latency=150.412, root=150, calls=5/12, last_remaining=93.300, stop=headless_timeout
- observation: 两个长臂均在调用未触顶时撞 root deadline；最后一次成功工具结果后仍有大量预算。
- confidence: high

### E-006
- title: 12-call 容量只对周度题形成可见边际收益
- run_id: c_long_capped,d_long_expanded
- step_or_span_id: `d/weekly-market-cause:22`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04-budget-calibration/c-vs-d.comparison.json#/comparison` 与 `/Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04-budget-calibration/d-long-expanded.json#/cases/2/arms/0`
- observed_at: 2026-08-04
- raw_excerpt: |
    c: calls=4/6, stop=headless_protocol_rejected
    d: calls=9/12, stop=model_finish
    vocabulary=triage-l1-9, unmapped=0/0
- observation: d 真正使用了第 7–9 次调用并正常结束；这支持调用容量是 case-specific 边际因素，但 c 未先撞 6-call cap，因果置信度不足以把它定为 PRIMARY。
- confidence: medium

### E-007
- title: 无法直接测量 finalization 到 finish
- run_id: budget-calibration-a-b-c-d
- step_or_span_id: `synthesize:missing`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04-budget-calibration/a-control.json`、`b-floor-ablation.json`、`c-long-capped.json`、`d-long-expanded.json` 的 `#/cases/*/arms/0/diagnostics/events`
- observed_at: 2026-08-04
- raw_excerpt: |
    total_events=202
    finalization_events=0
    events_with_timestamp=0
- observation: 只能从最后一次 tool_result 的 remaining budget 和 arm latency 计算 post-last-result 上界，不能得到精确 finalization duration。
- confidence: high

### Findings

### F-001
- title: persistent timeout 绑定 root 总时长而非 floor/call cap
- status: validated
- failure_span_id: `b/ruihuatai-valuation:12`
- root_location: `plan → stop` root deadline
- l0: LOOP
- l1: stop
- l2: execution-error-category-timeout
- l3: n/a
- violated_authority: none
- causality: PRIMARY_FAILURE
- propagation_impact: [TASK_TERMINATION, QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-004, E-005]
- confidence: high
- explanation: floor 已归零且 calls 未触顶，瑞华泰仍把 60/150/150 秒 root budget 用满；增加可用时长只延后失败。

### Path

### P-001
- title: 瑞华泰从有效取证状态传播到 root timeout
- start: 同题、同 runtime 代码、合法工具结果已返回，且 calls 仍低于 cap
- goal: 事件级 `finish.payload.stop_reason=headless_timeout`
- steps:
  1. profile 在 `plan` 真实分配 root=60 或 150 秒 — evidence: E-002 — finding: none
  2. 最后一次工具结果返回时仍剩 34.1/86.6/93.3 秒且 calls<cap — evidence: E-004、E-005 — finding: none
  3. 没有可观察 `finalization` 地标，尾段消耗剩余 root — evidence: E-007 — finding: F-001
  4. latency≈root，`runtime_result` 报 timeout，`finish` 记 partial — evidence: E-004、E-005 — finding: F-001
- residual_uncertainty:
  - 精确 finalization 从何时开始、实际需要多少秒不可判；当前只有 post-last-tool-result 上界。
  - c/d 瑞华泰的 `headless_command_failed` 对尾段耗时贡献不可判；artifact 没有保留失败 command 的 phase 与 exit timing。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260804-09 | F-001 | HARNESS_FIX | 下一轮把 headless finalization 做成显式、受 root deadline 约束的阶段转换，并按实测 tail 设 reserve；保留当前生产默认值和 0.65，不在本轮直接加时长或清零 floor | 同一五题、同一 runtime 下，瑞华泰应在 `remaining_root_seconds>=30` 时发出 `finalization`，随后 `finish=model_finish` 且 `latency<root`；若仍把 150 秒用满，则该建议 refuted | 重跑 a/b/c/d；断言生效 root、calls、floor，且 weekly 的 9-call 成功路径不退化 |

## Observability prescription

本节只登记下一轮最小观测，不在本轮补埋点。

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| finalization 起点不可见 | 0.65 是否高于真实收尾需求 | `remaining_root_seconds_at_finalization_start`；判据 `<30s` 为进入过晚，`>=30s` 仍 timeout 则 reserve 不是主因 | Codex headless 从研究转最终回答的单一 enforcement point | 精确区分“没留够时间”与“留够仍收不了尾” | 1 个数 + 1 个 event |
| nonzero command 对尾段贡献不可见 | `headless_command_failed` 是传播还是独立原因 | 失败 command 的 `elapsed_seconds`；判据 `>= remaining_root` 表示它独占尾段，否则为次级 | command_execution 归一化处 | 判定命令失败是否耗尽剩余 root | 1 个数 |

## Limits and counterevidence

- a/control 的瑞华泰是 `not_evaluable` 数据格式失败，不能做 a↔b 同题 floor 因果比较。
- live 模型有采样方差；三份 whole-artifact comparison 的首次分叉可复现，但不是每个 case 的隐藏推理根因。
- c→d 周度题从 4 calls/protocol reject 变为 9 calls/model finish；这是调用扩容的正向相关证据，但 c 没有先用满 6 calls，所以不把它提升为高置信因果 finding。
- `arm.status=degraded` 是后处理质量裁决，不能覆盖事件级 `finish.status`；本报告两列并列保留。
- 0.65 是否是全局最优值仍不能推出；本轮只证明“清零没有改善 timeout”与“39 秒对普通成功尾段偏保守”。
- 不能从 post-last-result 上界推出精确 finalization p50/p95。

## Next-step menu

1. 按 R-20260804-09 只实现显式 finalization handoff 与 deadline，不同时改生产 profile。
2. 用同一冻结五题复跑四臂，先断言 `remaining_root_seconds_at_finalization_start`，再看终态。
3. 若瑞华泰在 `>=30s` reserve 下仍 timeout，refute R-09，转查 command execution / provider tail，不再继续堆时长。
4. 若 d/weekly 的 7–9 calls 可重复完成而 c 稳定撞 6-call cap，再把调用容量从“case-specific candidate”升级为 SECONDARY。

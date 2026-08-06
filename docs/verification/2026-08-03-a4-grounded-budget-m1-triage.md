# Agent Run Triage Report

> **范围更正（2026-08-03）**：本报告只展开了 a4-pre 当前 run，漏读同目录 `smoke-phase-check.json@6c16b73a` 的 brief `ok 69.740s` 与 composer `>20.261s` 下界，因此其中 H5=`INCONCLUSIVE`、R-001 allocator-first 与“先做 brief replay”的后续解释已被更正后的 M2 取代。M1 对 a4-pre 当次 `22s phase timeout` 的读数仍成立，但不是完整架构 PRIMARY。

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M1
- failure_criterion: A4 的 Grounded 合成链必须留下 brief/composer/judge 三段记录且均为 `ok`，judge 必须实际执行，最终 `synthesis_diagnostic.state=accepted`，共享 deadline 退出时仍有正余量；`run.status=completed` 与总耗时小于根上限不构成成功。
- trace_coverage: 覆盖验收产物 `20260803T082342Z-a4-pre-budget-fix.json`、Workbench run `run_20260803_162718_999605` 的 `trace.jsonl` 与 `grounded_composer_shadow.json`；composer/judge 未启动，因此没有这两段的真实耗时。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: high

## Executive finding

第一处有证据的错误变换发生在 `synthesize` 的 brief 预算授予：turn 根预算为 120 秒，运行结束仍余约 96.6 秒，但 Grounded 子链只暴露 90 秒并进一步给 brief 22 秒；brief 精确撞到本地片上限后失败，composer/judge 从未启动，最终以 `completed` 外观返回确定性降级短答。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 当前 `main@e785f833`、8801、continuous runtime 关闭 | preflight 命中 `revision=e785f833 backend=continuous_glm`；本轮 trace 形状为 grounded 路径 | ok | E-001 |
| intent | 识别 2026-07-23 双红板块查询 | 题面保持 A4 正典问题 | ok | E-001 |
| route | 路由到 daily-review 并构造 AnswerSpec | `daily-review` 完成，绑定 3 组证据 | ok | E-004 |
| retrieve | 读取正式日报与知识库边界 | 产物含 K1/K2，未报检索失败 | ok | E-004 |
| tool | 工具在研究预算内完成 | `daily-review` 1.259 秒完成 | ok | E-004 |
| observe | 保留检索结果并形成 17 条候选/绑定 claim | `candidate_claim_count=17`、`bound_claim_count=17` | ok | E-002 |
| synthesize | brief、composer、judge 均运行并保留正余量 | brief 获得 22 秒，22.010 秒本地 deadline 失败；后两段无记录 | fail | E-002, E-003, E-004 |
| stop | 只有核验完成才记 accepted；否则明确降级 | 返回确定性短答，诊断 rejected，但 turn 顶层仍为 completed | partial | E-005 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260803_162718_999605/synthesis.brief` | HARNESS | synthesize | `execution-error-category-timeout` | `timeout_s=22, elapsed_ms=22010, reason_code=deadline_exhausted_local` | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 子链 cap 与递归分片先把可用根预算错误收窄 | brief 失败时 phase 只见约 90 秒 child、获批约 22 秒，而 root 仍明显大于 0 | E-002, E-004 | CONFIRMED | n/a | child 入口为 89,999ms；turn 结束 root 仍余 96,569ms |
| H2 | 上游检索先耗尽了 turn 预算 | brief 失败时 root 剩余应接近 0，或工具耗时应接近 120 秒 | E-004 | REJECTED | n/a | 工具仅 1.259 秒，turn 结束仍余约 96.6 秒 |
| H3 | provider 瞬时故障是第一因果层 | 失败不应精确贴住本地 22 秒片，且 phase 原因不应为 `deadline_exhausted_local` | E-002, E-003 | REJECTED | n/a | 单次调用 22.010 秒失败，和本地片一致；没有 rate-limit/5xx 证据 |
| H4 | retry 让 brief 超支并挤掉后续阶段 | ledger 应出现两次以上 synthesis 调用，或 phase elapsed 应明显超过 22 秒 | E-003 | REJECTED | n/a | ledger 只有一次调用，耗时与片上限一致 |
| H5 | 现有三次串行 LLM 结构在115秒 child + judge reserve下不可行 | 给 brief 达到已有约70秒完成点后，composer grant 应低于其>20.261秒下界 | `smoke-phase-check.json` + post-fix A4 | CONFIRMED | n/a | 扩大证据窗口后，直接完成值与截断下界已和当前预算 contract 冲突 |

## Causal findings

### PRIMARY

- failure_span_id: `run_20260803_162718_999605/synthesis.brief`
- root_location: Grounded 合成链 phase budget enforcement
- excerpt: `remaining_ms_at_entry=89999, timeout_s=22, elapsed_ms=22010, reason_code=deadline_exhausted_local`
- l0: HARNESS
- l1: synthesize
- l2: `execution-error-category-timeout`
- l3: n/a
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002, E-003, E-004]
- explanation: AnswerSpec 与证据已经可用，但合成 harness 把根预算收窄为 90 秒，再把 brief 限为 22 秒。brief 在本地 deadline 失败后，后续 composer/judge 没有执行机会，造成自然语言出口降级；这不是检索耗尽或 provider 错误。

### SECONDARY / TERTIARY

- SECONDARY: brief 失败使 composer/judge 均未启动，语义闸门缺席；证据 E-002。
- TERTIARY: none；顶层 `completed` 与 synthesis 健康是两个正交口径，属于读数边界而非新增因果 failure。

## Evidence → Finding → Path

### Evidence

#### E-001

- title: A4 在当前 revision 与正确服务入口运行
- run_id: `run_20260803_162718_999605`
- step_or_span_id: `run_20260803_162718_999605/eval.turn`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private/intelligence/eval/runs/20260803T082342Z-a4-pre-budget-fix.json:3`
- observed_at: `2026-08-03T16:27:43+08:00`
- raw_excerpt: `preflight_ok=true; revision=e785f833 backend=continuous_glm; case_id=A4-dual-red`
- observation: 验收命中了 8801 的当前 main，且只选择 A4。
- confidence: high

#### E-002

- title: brief 精确撞本地 22 秒片并停止链路
- run_id: `run_20260803_162718_999605`
- step_or_span_id: `run_20260803_162718_999605/synthesis.brief`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private/intelligence/eval/runs/20260803T082342Z-a4-pre-budget-fix.json:82`
- observed_at: `2026-08-03T16:27:42+08:00`
- raw_excerpt: `shadow_status=brief_unavailable; brief status=failed; remaining_ms_at_entry=89999; timeout_s=22; elapsed_ms=22010; reason_code=deadline_exhausted_local`
- observation: phase 列表只有 brief；composer 与 judge 没有记录。
- confidence: high

#### E-003

- title: LLM ledger 只有一次失败调用
- run_id: `run_20260803_162718_999605`
- step_or_span_id: `llm_budget`
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/agent-memory/.foresight/linxiaoqi5111/runs/run_20260803_162718_999605/trace.jsonl:7`
- observed_at: `2026-08-03T16:27:42+08:00`
- raw_excerpt: `call_count=1; failure_count=1; elapsed_ms=22010; reason=timeout`
- observation: 本轮没有第二次 retry，也没有 composer/judge 的 LLM 调用。
- confidence: high

#### E-004

- title: 根预算没有耗尽
- run_id: `run_20260803_162718_999605`
- step_or_span_id: `budget`
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/agent-memory/.foresight/linxiaoqi5111/runs/run_20260803_162718_999605/trace.jsonl:8`
- observed_at: `2026-08-03T16:27:42+08:00`
- raw_excerpt: `max_elapsed_ms=120000; elapsed_ms=23320; remaining_ms=96569; daily-review status=completed elapsed_ms=1259`
- observation: brief 失败后 turn 根预算仍有约 96.6 秒；检索工具只使用约 1.3 秒。
- confidence: high

#### E-005

- title: completed 状态与合成降级并存
- run_id: `run_20260803_162718_999605`
- step_or_span_id: `run_20260803_162718_999605/eval.turn`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private/intelligence/eval/runs/20260803T082342Z-a4-pre-budget-fix.json:42`
- observed_at: `2026-08-03T16:27:43+08:00`
- raw_excerpt: `degrades=[Grounded Presenter...已降级为可核验短答]; synthesis state=rejected; turn status=completed`
- observation: 顶层运行完成只表示有可交付 fallback，不表示 grounded 合成健康。
- confidence: high

### Findings

#### F-001

- title: 根预算在合成 enforcement point 前被双重收窄
- status: validated
- failure_span_id: `run_20260803_162718_999605/synthesis.brief`
- root_location: Grounded phase budget allocation
- l0: HARNESS
- l1: synthesize
- l2: `execution-error-category-timeout`
- l3: n/a
- violated_authority: none
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002, E-003, E-004]
- confidence: high
- explanation: 运行时根预算仍充足，但 brief 只能触达 child 的 22 秒片并因此失败，直接阻断后续两段。

### Path

#### P-001

- title: 证据已就绪到 grounded 降级
- start: daily-review 已完成且 17 条 claim 已绑定
- goal: Grounded 三段未完成、返回确定性短答
- steps:
  1. daily-review 1.259 秒完成，root 预算仍充足 — evidence: E-004 — finding: none
  2. child 入口只见 89,999ms，brief 获批 22 秒并在 22.010 秒本地超时 — evidence: E-002, E-003 — finding: F-001
  3. composer/judge 无记录，Grounded Presenter 被拒绝并使用 fallback — evidence: E-002, E-005 — finding: none
- residual_uncertainty:
  - 放宽预算后 A4 的 brief、composer、judge 各自真实耗时仍未知。
  - 当前 phase 记录没有显式 `remaining_ms_at_exit`，只能用入口余量减耗时近似判断 terminal slack。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-001 | F-001 | HARNESS_FIX | 让 child cap 触达根 deadline 的可用区间，并把串行 phase 从“按当时剩余递归乘比例”改为基于初始预算、允许前段回吐且保护 judge 尾段的分配器；不改 prompt、token 上限或 root 120 秒。 | 同一 A4 的 brief/composer/judge 均有记录且为 `ok`，judge 退出仍有正余量；若仍失败，失败点必须从 22 秒 brief 前移假设中移走。 | 用确定性 fake clock/phase harness 锁定每段 grant、回吐与 tail reserve，再做同题 live M2。 |
| R-002 | F-001 | EVAL_ONLY | canary 断言三段状态、judge 存在和 terminal slack，不用 `elapsed_s<=120` 或顶层 completed 作为成功条件。 | 现有 pre-fix artifact 稳定判 red；post-fix 只有三段全 ok 才判 green。 | 对 `completed + rejected`、`released_unverified`、缺 judge 三种样本分别保持 red。 |

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| phase 没有显式退出余量 | 无法直接判断最后一段是否留有 slack | `remaining_ms_at_exit`，成功阈值 `>0` | `_record_synthesis_phase` | judge 是否在根 deadline 前完成 | 低 |
| phase elapsed 跨 revision 变义 | 会漏读 E0 自然完成值并把 E2 截断值当需求 | artifact 增加 `phase_semantic_epoch/elapsed_kind` | acceptance parser | 正确区分自然完成、retry倍增与grant截断 | 低 |
| LLM ledger 只标 `caller=synthesis` | 旧 run 无法把顺序调用可靠映射到 brief/composer/judge | phase 记录保持 `name` 与调用结果一一对应；不再从 ledger 顺序反推 | phase telemetry | 每段分布可独立统计 | 已具备 |

## Limits and counterevidence

- 本报告只确认这一次 A4 的第一处错误变换；不能从一个 22 秒超时样本推出 brief 的自然完成耗时或三段分布。
- `continuous_glm` 是 backend 常量名，不证明实际模型是 GLM；LLM ledger 明确记录模型为 `gpt-5.6-sol`。
- case ID `A4-dual-red` 与 Finance adapter 的 L3 `A4`（概率校准偏差）无关，本报告的 l3 为 n/a。
- H5 已由扩大后的 artifact 证据确认到“当前115秒 + judge reserve contract不可行”；精确三段p95与约250秒 sizing仍不是直接测量。

## Next-step menu

1. 停止继续调 brief cap 或重复 live A4；allocator 只能移动失败点。
2. 用户在约250秒 deep-mode/root扩容与确定性 DecisionBrief（E）之间做架构选择。
3. 若保留120秒产品目标，默认走 E 的冻结 artifact 离线契约验证。
4. 新架构 A4 通过后再跑完整 A组，四态对照 `1/1/8`。

## M2 prediction closure（2026-08-03）

- R-001 `prediction_outcome: refuted`：child cap 与 carry-forward allocator 已在 runtime 生效，但 post-fix A4 仍在 brief 的 28 秒 grant 处 `deadline_exhausted_local`，没有进入 composer/judge。
- H5 更正为 `CONFIRMED`（confidence medium）：扫描全部 phase artifact 后，已有同形状 A1 brief `ok 69.740s` 与 composer `>20.261s` 下界；在 115 秒 child + 28.75 秒 judge reserve 下，给足 brief 后 composer 仅约 16.5 秒，低于观测下界。完整语义分期与差分见 `docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`。

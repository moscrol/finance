# Agent Run Triage Report

> **更正（2026-08-03）**：本报告初版只比较 a4-pre/a4-post，漏读同目录 `smoke-phase-check.json` 等历史 phase artifact，因此把 H5 错判为 `INCONCLUSIVE`，并错误建议再做 brief-only replay/逐级增加 cap。以下为扫描全部 phase artifact、按 runtime revision 重建 telemetry 语义后的正典结论。

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M2
- failure_criterion: A4 的 Grounded 合成链必须留下 brief/composer/judge 三段记录且均为 `ok`，judge 必须实际执行，最终 `synthesis_diagnostic.state=accepted`，且 judge 退出仍有正余量；顶层 `completed` 与总耗时小于 120 秒不构成成功。
- trace_coverage: 覆盖 eval 目录全部 6 份含 phase telemetry 的 artifact、对应 revision `6c16b73a / cd175a0e / 8ed66020 / bd845320 / e785f833 / 9c6add5e`、A/B Workbench trace、`llm_refine.py` 的 enforcement 修复与 `ask_synthesis.py` 的 phase/token contract。直接完成样本来自 A1，A4 两侧为硬截断样本。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Executive finding

初版报告把“当前先撞 brief 25% cap”错写成 PRIMARY；扩大证据窗口后，PRIMARY 应上移为**三次串行 LLM 合成的工作量与 115 秒 child / 120 秒 root 不相容**。同日、同日期、同为 17/17 claim、同为 2 条 prepared message 的 A1 在时间片尚未被强制时，brief 自然完成耗时为 69.740 秒；composer 随后运行 20.261 秒仍未完成，这是截断下界。当前 `T=115s`、judge reserve=`28.75s`：若给 brief 足够的约 70 秒，composer 最多只剩约 16.5 秒，已经低于其观测下界。25% cap 只是把不可行性提前显影，不是可通过继续调 cap 消除的根因。

## A/B controls

- invariant inputs: a4-pre/a4-post 使用同一正典 case、用户、日期、8801、root 120 秒、模型；task-frame、route、AnswerSpec、daily-review 产物与 fallback answer 一致。
- intentional variable: `e785f833 → 9c6add5e` 的 child cap `90→115` 与 carry-forward allocator。
- historical corroboration: `smoke-phase-check.json@6c16b73a` 提供未被 phase grant 截断的 brief 完成值与 composer 截断下界；其 case 是 A1，不与 A4 冒充逐字节同题，但合成形状同为 17/17 claim 与 2 条 prepared message。
- uncontrolled confounders: provider 瞬时延迟未冻结；A1 与 A4 题面不同；69.740 秒是单样本而非 p50/p95；judge 没有同质 phase 完成样本。

| normalized step | Run/epoch A | Run/epoch B | comparison | causal meaning |
|---|---|---|---|---|
| configure/preflight | A4 `e785f833` | A4 `9c6add5e` | intentional divergence | allocator 的物理生效由 phase grant 验证 |
| intent/route/retrieve | 相同 task-frame/owner/AnswerSpec hash | 相同 | same | 排除上游漂移 |
| synthesize/brief admission | child=89,999ms, grant=22s | child=114,999ms, grant=28s | first A/B divergence | 新 allocator 已被 enforcement point 读取 |
| synthesize/brief result | 22.010s 硬截断 | 28.010s 硬截断 | same failure class | 提高 6 秒没有接近自然完成值 |
| historical uncensored brief | A1 `6c16b73a`: 69.740s `ok` | 后续 epoch 均在 22–29s 截断 | semantic-epoch difference | 69.740s 是已有完成值，不需要再 replay 才知道 |
| historical composer lower bound | A1 `6c16b73a`: 20.261s 未完成 | 当前策略给足 brief 后 composer ≤约16.5s | infeasible allocation | 保 judge reserve 时 composer 必然先于观测下界被截断 |
| stop/fallback | rejected + completed fallback | rejected + completed fallback | same terminal class | 产品 canary 继续 red |

- first_divergence_step: A4 M2 的第一次有意分叉是 `synthesize/brief budget admission`；第一次失败仍是 brief timeout。
- first_wrong_transform: 运行前预算计划把三次串行 LLM 工作装进 115 秒 child，并以 25% cap / 25% judge reserve 分配；历史完成值和截断下界已与该约束冲突。
- pre_divergence_equivalence: a4-pre/a4-post 的 AnswerSpec SHA256 `d106e6…`、daily-review SHA256 `e2499a…`、fallback answer SHA256 `f1b6e1…` 一致。
- downstream_propagation: 当前 allocator 在 28 秒中止 brief → composer/judge 无法启动 → synthesis rejected → fallback；若单纯把 brief 抬到约 70 秒，则 composer grant 会降到其观测下界以下，失败只会后移。

## Telemetry semantic epochs

同名 `elapsed_ms/timeout_s` 不能跨 revision 同质解释：

| epoch | revision 边界 | runtime 语义 | artifact 证据 |
|---|---|---|---|
| E0：片未执行 | `< cd175a0e` | `timeout_s` 只是记录值；显式 shared deadline 使 phase 能吃完整 child。`elapsed_ms` 可出现远大于 grant 的自然完成值或 child 截断值 | `6c16b73a`: brief `ok 69740/22`，composer `failed 20261/10` |
| E1：每次尝试受限 | `cd175a0e ≤ rev < 8ed66020` | 单次请求读取 grant，但每次 retry 可重新拿一份；phase 墙钟可达 `attempts × grant` | `cd175a0e`: brief `failed 44560/22 provider_unavailable` |
| E2：整段硬截止 | `≥ 8ed66020` | 先冻结 `phase_deadline`，所有 retry 共享；deadline 失败时 `elapsed_ms≈grant` | `8ed66020`: `29009/29`；`bd845320/e785f833`: `22009–22010/22`；`9c6add5e`: `28010/28` |

因此任何跨 artifact 分类器都必须先按 revision 选择 semantic epoch；不能仅凭字段同名统一解释。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 为三段合成提供可完成且不越 root 的预算计划 | 三次串行 LLM 被装入 115 秒 child；observed brief≈70s、composer>20s，judge 尚未计入 | fail | E-002, E-005 |
| intent | 两侧识别同一 A4 问题 | task-frame hash 一致 | ok | E-001 |
| route | 两侧走 daily-review owner | route/owner 一致 | ok | E-001 |
| retrieve/observe | 两侧形成等价结构化输入 | 三个关键文件 SHA256 相同，17/17 claim | ok | E-001 |
| synthesize | brief、composer、judge 均运行 | 当前 brief 28.010s 硬截断；历史值显示完成约需 69.740s，给足后 composer reserve 又不可达 | fail | E-002, E-003, E-005 |
| stop | 三段核验完成才 accepted | machine `completed` 与 synthesis `rejected` 并存 | partial | E-006 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260803_142959_204791/synthesis.composer` | HARNESS | synthesize | `execution-error-category-timeout` | `brief completed=69740ms; composer lower_bound>20261ms; T=115s; judge_reserve=28.75s` | medium |
| `run_20260803_171452_043073/synthesis.brief` | HARNESS | synthesize | `execution-error-category-timeout` | `remaining=114999ms; timeout=28s; elapsed=28010ms; deadline_exhausted_local` | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | child cap + 递归分片是唯一阻塞，修完即可完成三段 | 115s allocator 后应出现三段 `ok` | E-003, E-004 | REJECTED | n/a | post-fix 仍在 brief 硬截断 |
| H2 | 25% brief cap 是独立根因，单纯抬 cap 仍可能保住 composer/judge | 给 brief≈70s 后 composer grant 应不低于其已观测需求 | E-002, E-005 | REJECTED | n/a | 保留 28.75s judge reserve 后 composer 仅约16.5s，低于20.261s截断下界 |
| H3 | A4 的题面、路由或检索漂移造成 post-fix 失败 | task-frame、route 或结构化产物哈希应不同 | E-001 | REJECTED | n/a | A/B 上游等价 |
| H4 | provider outage、rate limit 或 retry 是 A4 第一因果层 | 应出现 service reason、多个调用或早于 grant 的失败 | E-003, E-004 | REJECTED | n/a | E2 epoch 各只有一次调用，deadline failure 精确贴 grant |
| H5 | 现有三次串行 LLM 结构在 115s child + judge reserve 下不可行 | 任意让 brief 达到已有约70s完成点的分配，composer grant 都应低于其>20.261s下界 | E-002, E-005 | CONFIRMED | n/a | 直接完成值 + 截断下界已经与预算约束冲突 |

## Prior prediction closure

- M1/M2 初版 R-001 `prediction_outcome: refuted`：allocator 生效，但不足以让 A4 进入 composer/judge。
- M2 初版 R-001（再跑 brief-only 115s）`prediction_outcome: invalidated_before_execution`：69.740s 完成值已存在，无需重复付费取同类信息。
- M2 初版 R-002（逐级提高 brief cap）`prediction_outcome: refuted_by_existing_evidence`：给足 brief 会把 composer 压到已观测下界以下。
- H5 从初版 `INCONCLUSIVE` 更正为 `CONFIRMED`（confidence medium）：确认的是当前 115s + reserve 的架构不可行，不是精确 p95 总耗时。

## Causal findings

### PRIMARY

- failure_span_id: `run_20260803_142959_204791/synthesis.composer`
- root_location: Grounded Presenter 三次串行 LLM 拓扑与 child/root budget contract
- excerpt: `brief completed=69.740s; composer incomplete after 20.261s; child=115s; judge_reserve=28.75s`
- l0: HARNESS
- l1: synthesize
- l2: `execution-error-category-timeout`
- l3: n/a
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: SEVERAL_STEPS_LATER
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002, E-003, E-005]
- explanation: 系统要求三个串行 LLM phase 在 115 秒 child 内完成并保留 judge 尾段，但同形状历史 run 已测得 brief≈70秒、composer>20秒。给足 brief 后 composer 可获时间反而低于已观测下界；因此 allocator 无法通过重新切同一块饼解决，当前 brief cap 只是最先触发的保护墙。

### SECONDARY / TERTIARY

- SECONDARY: 当前实现把 brief 固定为 25%T，在 E2 semantic epoch 中于 28.010 秒硬截断，composer/judge 没有启动。
- TERTIARY: Grounded synthesis rejected 后回同一确定性 fallback；顶层 `completed` 形成读数假绿，但不是新的 PRIMARY。

## Evidence → Finding → Path

### Evidence

#### E-001

- title: A4 A/B 上游等价
- run_id: `run_20260803_162718_999605`, `run_20260803_171452_043073`
- step_or_span_id: `controller`, `route`, `retrieve`
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/agent-memory/.foresight/linxiaoqi5111/runs/run_20260803_162718_999605/trace.jsonl:1`; `/Users/a77/agent-memory/.foresight/linxiaoqi5111/runs/run_20260803_171452_043073/trace.jsonl:1`; 两侧 run 目录的 `answer_spec.json` 与 `daily-review-skill-result.json`
- observed_at: 2026-08-03
- raw_excerpt: `task-frame/route same; answer_spec=d106e6…; daily-review=e2499a…; answer=f1b6e1…`
- observation: allocator 以外的输入、路由和 fallback 没有漂移。
- confidence: high

#### E-002

- title: 未强制 phase grant 时 brief 自然完成、composer 被 child 截断
- run_id: `run_20260803_142959_204791`
- step_or_span_id: `run_20260803_142959_204791/synthesis.phases`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private/intelligence/eval/runs/smoke-phase-check.json:82`
- observed_at: 2026-08-03T14:29:59+08:00
- raw_excerpt: `revision=6c16b73a; brief ok elapsed=69740ms timeout_s=22; composer failed elapsed=20261ms remaining_at_entry=20258ms`
- observation: E0 epoch 中 brief 完成值不受 22 秒记录片限制；composer 的20.261秒是 child 截断下界。
- confidence: high

#### E-003

- title: A4 post-fix allocator 生效但仍停在 brief
- run_id: `run_20260803_171452_043073`
- step_or_span_id: `run_20260803_171452_043073/synthesis.brief`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private/intelligence/eval/runs/20260803T091451Z-a4-post-budget-fix.json:82`
- observed_at: 2026-08-03T17:15:21+08:00
- raw_excerpt: `remaining=114999ms; timeout=28s; elapsed=28010ms; deadline_exhausted_local`
- observation: 115秒 child 与新 allocator 被真实读取，但 brief 仍在28秒硬墙停止。
- confidence: high

#### E-004

- title: E2 epoch 的 phase grant 是整段硬墙
- run_id: n/a（代码契约）
- step_or_span_id: `commit_8ed66020/phase_deadline`
- native_or_normalized: normalized
- source_type: code_reading
- source_ref: `/Users/a77/finance-workspace-private/intelligence/services/llm_refine.py`，commit `8ed66020`
- observed_at: 2026-08-03
- raw_excerpt: `phase_deadline=min(shared_deadline, now+timeout); retries read phase_deadline.remaining()`
- observation: `8ed66020` 之后 deadline failure 的 elapsed≈grant 是执行契约，不是自然完成耗时。
- confidence: medium

#### E-005

- title: 当前 reserve 下不存在同时容纳 observed brief/composer 的分配
- run_id: `run_20260803_142959_204791`
- step_or_span_id: `run_20260803_142959_204791/synthesis.composer`
- native_or_normalized: normalized
- source_type: code_reading
- source_ref: `/Users/a77/finance-workspace-private/intelligence/eval/runs/smoke-phase-check.json:82`; `/Users/a77/finance-workspace-private/intelligence/services/ask_synthesis.py:1556`
- observed_at: 2026-08-03
- raw_excerpt: `T=115; reserve=28.75; after brief=69.740, composer grant≤16.510; observed composer lower_bound>20.261`
- observation: 即使把 brief cap 抬到已有完成点，composer 在 judge reserve 前已不可达其观测下界。
- confidence: medium

#### E-006

- title: completed 与 synthesis rejected 并存
- run_id: `run_20260803_171452_043073`
- step_or_span_id: `run_20260803_171452_043073/eval.turn`
- native_or_normalized: normalized
- source_type: trace
- source_ref: `/Users/a77/finance-workspace-private/intelligence/eval/runs/20260803T091451Z-a4-post-budget-fix.json:42`
- observed_at: 2026-08-03T17:15:22+08:00
- raw_excerpt: `turn status=completed; synthesis state=rejected; grounded fallback degrade`
- observation: completed 只表示 fallback 可交付。
- confidence: high

### Findings

#### F-001

- title: 三次串行 LLM 合成与 115 秒 child budget contract 不相容
- status: validated
- failure_span_id: `run_20260803_142959_204791/synthesis.composer`
- root_location: synthesis harness architecture
- l0: HARNESS
- l1: synthesize
- l2: `execution-error-category-timeout`
- l3: n/a
- violated_authority: none
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: SEVERAL_STEPS_LATER
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002, E-003, E-005]
- confidence: medium
- explanation: 完成一次 brief 已用约70秒，composer 至少还需超过20秒，且必须保留 judge；当前 allocator 只能决定哪一段先被截断，不能增加总预算或删除一次往返。

### Path

#### P-001

- title: 从等价输入到结构性预算失败
- start: daily-review 与17条 claim 已准备完成
- goal: 三段均未完成、返回 fallback
- steps:
  1. A/B 上游结构化输入等价 — evidence: E-001 — finding: none
  2. runtime 把三次串行 LLM 工作装入115秒 child，并保留28.75秒 judge — evidence: E-004, E-005 — finding: F-001
  3. 当前实现先在 brief 28秒 grant 处硬截断 — evidence: E-003 — finding: none
  4. 历史 E0 run 已显示 brief 完成约69.7秒且 composer 20.3秒仍未完成；单抬 brief 会把失败后移到 composer — evidence: E-002, E-005 — finding: F-001
  5. synthesis rejected，顶层以 fallback completed — evidence: E-006 — finding: none
- residual_uncertainty:
  - 69.740秒是 A1 单样本，不是 A4 的精确自然耗时或 p95。
  - composer 只有 `>20.261s` 下界，judge 没有同质 phase 完成值；约250秒是容量规划估计，不是直接测量。
  - 确定性 brief 的两个非投影字段仍需离线契约验证。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-001 | F-001 | DATA_CONTRACT_FIX | 工程默认路线改为确定性 DecisionBrief（E）：从 AnswerSpec 投影6个字段，把 `core_tension` 与 upgrade/downgrade 条件定义为显式生成/派生字段，并用 validator fail-closed；删除一次主链 LLM 往返。 | 冻结 artifact 上 brief 零 provider 调用、8字段契约通过；随后 A4 首个 LLM phase 应变为 composer，并为 judge 留出正余量。 | 先离线 golden + mutation，再做一次 A4；保留旧 LLM brief 为可回滚对照。 |
| R-002 | F-001 | HARNESS_FIX | 产品备选路线是把 root/child 扩到能容纳三段的 deep-mode 预算；约250秒只能作为初始 sizing，不冒充实测，并同步重定义 A4 SLA/canary。 | 新 profile 下三段均有 uncensored 完成值与正 slack；若用户仍要求120秒体验门，则该路线自动不合格。 | profile 必须显式命名并与120秒生产模式隔离，不静默改全局 root。 |
| R-003 | F-001 | EVAL_ONLY | 停止 brief-only replay、逐级 cap 调参和 A组运行，直到用户在 root 扩容与 E 之间做出架构选择并形成新 revision。 | 不再产生只把 timeout 从 brief 后移到 composer 的无信息 live artifact。 | 下一次 live 预注册唯一架构变量；A4 通过后才跑 A组。 |
| R-004 | F-001 | EVAL_ONLY | 为历史 artifact 增加 revision-aware semantic epoch 解析；禁止把 E0/E1/E2 的 `elapsed_ms` 同质聚合。 | E0 的 `69740/22` 被标为 uncensored completion，E1 的 `44560/22` 标为 retry-multiplied，E2 的 `28010/28` 标为 grant-censored。 | 用现有6份 artifact 做冻结分类测试。 |

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| 同名 elapsed 跨 revision 变义 | 历史分类器会把自然完成值误当超支 | `phase_semantic_epoch=E0/E1/E2`，由 revision 映射 | acceptance artifact parser | 正确区分 uncensored / retry-multiplied / grant-censored | 低 |
| phase 没有 censoring 类型 | `elapsed≈grant` 是否自然完成不直观 | `elapsed_kind=completed|child_censored|phase_censored|retry_multiplied` | phase telemetry | 不再从数值形状猜语义 | 低 |
| token 与 phase 未关联 | 无法做 root 扩容 sizing | phase `completion_tokens/reasoning_tokens`，缺失保持 unknown | LLM ledger ↔ phase | 估计吞吐与 p50/p95 | 中 |
| judge 无同质完成样本 | root 扩容的精确值未知 | 仅在选择 deep-mode 后记录 judge uncensored elapsed | 新 profile canary | 校准而非猜约250秒 | 一次受控 run |
| E 的两个非投影字段未冻结 | 无法确认确定性 brief 能完整替代旧契约 | 离线样本记录8字段 coverage；阈值8/8且 validator 对缺失/冲突 fail-closed | E frozen-artifact golden | `core_tension` 与升降级条件是否可安全派生 | 低 |

## Limits and counterevidence

- A1 与 A4 不是同一题；69.740秒不能写成“A4 brief 精确耗时”。它是同日期、同17/17 claim、同2条 prepared message 的直接可比完成样本。
- `max_tokens=2400` 是 composer 上限，不证明实际一定是 brief 的两倍；它只加强“没有理由假设 composer 很便宜”，不能单独用于精确加总。
- 直接证据严格给出 `brief=69.740s`、`composer>20.261s`；三段自然总耗时与约250秒 sizing 仍非直接测量。
- 但在当前 115秒 + 28.75秒 judge reserve 契约下，给足 brief 后 composer grant 已低于观测下界，足以拒绝继续调 cap；无需再烧一次同类 live A4 才能作这个工程决策。
- E 不是“纯投影8字段”：其中6字段可投影，2字段必须被当作真实设计风险。

## Next-step menu

1. 用户做产品选择：保留120秒交互目标则采用 E；接受约250秒 deep mode 才考虑 root 扩容。
2. 默认工程建议采用 E，先做冻结 AnswerSpec 的离线 8字段契约与 mutation 验证，不调用 live provider。
3. 只有新架构 revision 完成后才跑一次 A4；三段/两段门禁按新拓扑重新定义。
4. A4 通过后再跑 A组10题；历史 artifact 先经 E0/E1/E2 解释器归一，不能直接混算。

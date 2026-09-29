# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M1
- failure_criterion: 消息八问必须交付可用正文且每条引用逐字来自冻结原文；财务不能把余额差额当已证实现金流，也不能把结构通过当推理正确。
- trace_coverage: 完整查看news与transmission逐轮model_turn、invalid_action和终态；financial-holdout用于检查同类格式拒收。原件索引在树外excerpt-authoring-0929/triage-evidence.json。
- trace_depth: D2
- completion_status: COMPLETE_FAILURE
- confidence: high

## Prior prediction closure

既有prediction-ledger Open区没有本次紧凑作者格式/FA-01的对应预注册项，本次冻结trace不能裁定其余项目预测，保持原状态。上轮历史首发未触发修复，不能关闭“真实模型在修复分支成功”的未知项。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence | implication |
|---|---|---|---|---|---|
| 既有prediction-ledger | 非本轮作者协议的Open项 | 本批不包含各自指定的工具/夜跑/独立对照 | still_pending | E-001,E-004不具对应输入 | 不用无关答卷回填原预测 |

- ledger: docs/prediction-ledger.md
- fix_type_refuted_streak: 本账现有表DATA_CONTRACT_FIX=1，其余0；本轮仅登记新试验，不把未测记为confirmed或refuted。

## Executive finding

消息稿首次在模型输出JSON结构处失败，后续依次是多句claim与逐字quote不一致；来源目录已到达，零工具，三次都没进入正文交付。财务的余额/现金口径错在第一稿已存在，之后格式重写没有纠正，最终deterministic的passed并未调用语义模型。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 投递原题与冻结目录、原预算 | 两run的contract与configure保存原材料、600秒及40步 | ok | E-001 |
| synthesize | 合法格式与逐字来源、回答八问 | news sequence6非法JSON，11多句，21错引号；transmission6余额直接换现金 | fail | E-002,E-003,E-004 |
| observe | 错误理由到达作者 | model_input记录steering_invalid_finish及repair_last_rejection | ok | E-003 |
| stop | 合格正文才交付，语义能力如实标记 | news failed/invalid_repair_finish；财务completed但现金口径错 | fail | E-003,E-004 |

本地词表与L1同为九步；此处event映射沿trace-profile：configure↔configure，task↔intent，model_turn↔synthesize，invalid_action↔observe，finish↔stop。plan/retrieve/tool未发生，不据缺席推错；prompt_assembled与model_input只作配置/反馈证据，不推测隐藏思考。

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| run_20260928_201232_709081/sequence6 | REASONING | synthesize | llm-output-category-nonsensical | JSONDecodeError at char5288 | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 作者格式和quote错误阻断消息交付 | 三次model_turn紧接相应invalid_action且无有效正文 | E-002,E-003 | CONFIRMED | n/a | 逐轮错误直接可见 |
| H2 | 资料缺失或工具失败是消息首次失败 | contract缺原文或存在失败工具调用 | E-001 | REJECTED | n/a | 原材料齐、工具调用0 |
| H3 | 上游超时截断了首稿 | model_turn有timeout/length/error | E-002 | REJECTED | n/a | finish_reason=stop，error空 |
| H4 | 财务判断是在格式修复中才变坏 | 首稿无余额直接等现金错误、后稿新增 | E-004 | REJECTED | n/a | 首稿已写，后稿保留 |

## Causal findings

### PRIMARY

- failure_span_id: run_20260928_201232_709081/sequence6
- root_location: model_turn.content 到 JSON解析
- excerpt: Expecting ',' delimiter (line 1 column 5289 char 5288)
- l0: REASONING
- l1: synthesize
- l2: llm-output-category-nonsensical
- l3: n/a
- violated_authority: tool_contract
- causality: PRIMARY_FAILURE
- propagation_impact: [TASK_TERMINATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-002,E-003]
- confidence: high
- explanation: 原始作者输出未构成合法JSON，修复后又遇到两个独立表示错误，既有机会用尽。这个定位不等于已证明提示长度导致错误，也不把财务错误说成它的传播。

### SECONDARY

none；后续格式错误和独立财务语义错保留为同轮观察，没有证据证明由第一次JSON错误导致。

## Evidence

### E-001
- run_id: run_20260928_201232_709081
- step_or_span_id: sequence1, sequence2
- native_or_normalized: native
- source_type: trace
- source_ref: /Users/a77/.finance-runtime/reviews/8792-answer-capability-20260928/authoring-v2/quote-repair-users/answer-authoring-0928/runs/run_20260928_201232_709081/continuous-episode.json#/events
- observed_at: 2026-09-28T20:12:32+08:00
- raw_excerpt: policy_total_seconds=600; tool_calls=0
- observation: 原题、材料及权限已进入合同，工具没有执行。
- confidence: high

### E-002
- run_id: run_20260928_201232_709081
- step_or_span_id: sequence6, sequence7
- native_or_normalized: native
- source_type: trace
- source_ref: 同E-001#/events/5与6
- observed_at: 2026-09-28T20:13:21+08:00
- raw_excerpt: finish_reason=stop; not_json_object; char5288
- observation: 供应商正常结束，作者返回的JSON无法解析。
- confidence: high

### E-003
- run_id: run_20260928_201232_709081
- step_or_span_id: sequence11, sequence12, sequence21, sequence22, sequence24
- native_or_normalized: native
- source_type: trace
- source_ref: 同E-001#/events
- observed_at: 2026-09-28T20:14:10+08:00
- raw_excerpt: answer_q2.claims[3]: material_anchors[0] quote does not match original user text
- observation: 第二稿有多句claim，第三稿将原文内单引号改成双引号，最终无公开答卷。
- confidence: high

### E-004
- run_id: run_20260928_201413_021994
- step_or_span_id: sequence6, sequence11, sequence21, sequence23
- native_or_normalized: native
- source_type: trace
- source_ref: /Users/a77/.finance-runtime/reviews/8792-answer-capability-20260928/authoring-v2/quote-repair-users/answer-authoring-0928/runs/run_20260928_201413_021994/continuous-episode.json#/events
- observed_at: 2026-09-28T20:14:55+08:00
- raw_excerpt: 三者合计占用现金约5.5亿元; judge_mode=deterministic; judge_usage.calls=0
- observation: 原材料仅给应收/存货/合同负债余额，作者首稿直接形成现金占用数，后稿保留。passed是结构/确定性判断，非独立模型财务审查。
- confidence: high

## Propagation path

最后已知正确状态为原题和来源进入合同(E-001)→作者JSON非法(E-002)→原预算内修复先改结构、后改分句，最终quote仍失配(E-003)→failed无正文。财务第一稿即有口径错误(E-004)，与消息链独立，不归于格式修复。

- self_report_vs_observed: 财务semantic.passed与实际现金口径错误并存；其judge_mode与0调用证明不能称“语义模型审查通过”。
- residual_uncertainty: 省掉逐字quote是否改善自然交付、是否影响财务推理，现有trace不能确定。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260929-01 | E-003复制标点负担 | DATA_CONTRACT_FIX | 原文生成只读片段目录，作者选片段，编译器原样回填，先单变量试验 | 相同输入和模型的新消息首发交付，零手工quote失配；财务不新增重大错误才可保留候选 | 未知/错类片段、历史身份、原预算及旧协议均验证 |
| LOCAL-FIN | E-004推理偏差 | EVAL_ONLY | 财务独立判卷，检查余额/现金、融资/FCFE与估值口径 | 财务出现同错仍判partial，不因completed升级 | 不新增硬编码财务词面阻断或再开FA-01 |

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| 片段选择的自然效果 | 能否保留试验 | 同题两臂的可用答卷判定、invalid_action数；候选消息须usable且quote失配0 | 隔离首发原件 | 只证明本批，不证明稳定性 | 4次首发，原预算 |

## Limits and counterevidence

- 标点失配确实是无效原文，不能靠模糊匹配放行；片段选择仍须验证语义支持。
- 不改变金融判官生产配置；deterministic能力边界已知，不能把本次检查说成首次发现。
- 不能从这一消息样本断言所有格式错误由harness造成，也不能把两题结果当成功率。

## Next-step menu

1. 固定片段目录方案与旧协议兼容边界。
2. 用原文标点、错来源、历史与混合错误作离线回归。
3. 固定题/模型/预算作新闻与财务两臂各一次首发，保存全部结果后决定是否保留。

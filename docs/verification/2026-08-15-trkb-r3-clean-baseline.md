# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_NOT_CONFIRMED
- mode: M1
- failure_criterion: 干净身份批（`cb09f895` + porcelain 空 + tool60）上，B 组题走完 continuous episode 后应有 ≥1 条证据到达验收可见面（`evidence_bound > 0`）。实测 B1、B7 仍为 0，判定为失败。
- trace_coverage: 一份新产物 `intelligence/eval/runs/20260814T1926Z-r3-clean-baseline.json`（`sha256=b712bd2e…d8d350`，28 题全量，随本 PR 进 git），另有 28 个 workbench run 目录（`continuous-episode.json` / `trace.jsonl`，仍在仓外）。**缺**：B1/B7 的 `invalid_repair_finish` 内部判据不在产物内。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Prior prediction closure

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 轨道 B Round 2 | R-20260815-07 | `bound_but_dropped` 细分 `gap_zeroed`/`no_hash` 后：重放 B1/B3 落 `gap_zeroed`；B7 同一 turn 内两格分别可见 | confirmed | E-004 | 三个冻结夹具逐字命中；本批另贡献 4 个 `no_hash` 真缺口格 |
| 轨道 B Round 2 | R-20260815-06 | porcelain 空且 health revision 与目录一致 | confirmed（#17 已关） | E-001 | 本轮五项盖戳复核成立，另给该关闭行补了测量时刻 |
| 轨道 B Round 2 | R-20260815-04 | `draft_source` 埋点 | still_pending | 无 | 暂缓已解除，但本轮未做（见 Limits） |
| 轨道 B Round 2 | R-20260815-03 | 两套 output 判定对账 | still_pending | 无 | 本轮无新证据 |
| 2026-08-04 | R-20260804-10 | deadline-aligned per-tool handoff… | still_pending | 无 | 本轮无新证据 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `EVAL_ONLY`=0（-07 再添一条 confirmed）；`HARNESS_FIX`=1（R-09，本轮未变）。

## Executive finding

干净身份下 `not_run` 归零、量具口径首次全部对齐，但 **B1/B7 仍不交付证据，且失败形状已迁移**：不再是 Round 2 的「绑定被 gap 零化」，而是 `stop_reason=invalid_repair_finish` 且**零绑定**——失败点前移到修复轮收尾。本轮未确认其根因：判据变量不在产物内，且该缝属轨道 A。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 干净身份装配 | `cb09f895`、porcelain 空、tool60、pid 30091 | ok | E-001 |
| tool | 工具取证 | B1 取回 19 条、B7 取回 29 条 | ok | E-002 |
| observe | 证据入 `outcome.evidence` | 同上，非空 | ok | E-002 |
| synthesize | 产出绑定并交付 | B1/B7 `bindings=0`、`outputs_missing=3/2`、`stop_reason=invalid_repair_finish` | **fail** | E-002 |
| stop | 证据到达验收面 | `evidence_bound=0` | fail | E-002 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| B1 `run_20260815_034612_…` / `finish` | UNCLEAR（竞争项：REASONING 收尾产出不合法 vs HARNESS 修复轮契约拒收） | synthesize | DEPTH_INSUFFICIENT(D4) | `stop_reason=invalid_repair_finish`、`bindings=0`、`evidence_retrieved=19` | medium |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 干净身份修复后 B 组全部转为交付 | 若成立，B1-B8 八题 `evidence_bound` 全部 >0 | E-002, E-003 | **REJECTED** | — | 5/8 交付（B2/B3/B4/B5/B8），B6 是澄清轮（非失败），B1/B7 仍 0 |
| H2 | B1/B7 仍是 Round 2 的 `gap_zeroed`（绑定被 gap 零化） | 若成立，二者应有 `n_hash>0` 且带 gap 的绑定格 | E-002, E-005 | **REJECTED** | — | 二者 `bindings=0`，**一条绑定都没生成**；且全批 `gap_zeroed` 出现 **0 次**。形状已迁移，不是同一个失败 |
| H3 | 剩余失败按题固定（B1/B7 是"难题"） | 若成立，同一批题跨窗口应稳定失败同样的题 | E-003 | **REJECTED** | — | 与 tool60 批对照：失败成员**换人**——B3 由 eb=0 变 13（恢复），B7 由 eb=5 变 0（退化）。失败集不稳定，是非确定性而非题目属性 |
| H4 | `invalid_repair_finish` 的成因是模型收尾产出不合法（REASONING） | 若成立，应能在产物中看到被拒收的收尾内容及其不合法原因 | E-002 | **INCONCLUSIVE** | 落盘 `invalid_repair_finish` 的拒收原因码与被拒 payload 的结构摘要（不落正文）；H4 预测原因码指向格式/契约不符，若指向预算或传输则证伪 | 产物只有 `stop_reason` 一个标量，没有拒收判据；无法与「修复轮契约拒收」（HARNESS）区分 |
| H5 | 本批可用于给 R-21 定论 | 若成立，`caveat_slips>0` 的窗口需存在且判据可判 | E-005, E-006 | **CONFIRMED（仅就"窗口存在"而言）** | — | 9 个 case `caveat_slips>0`，C1 违反 0、C2 违反 0。**但 R-21 的判定归轨道 A**，本报告只出数 |

## Causal findings

### PRIMARY

- failure_span_id: B1 `run_20260815_034612_…` / `finish`（同形另见 B7）
- root_location: 修复轮收尾与绑定生成之间的缝（轨道 A 的 `episode_protocol` 面）
- excerpt: `stop_reason=invalid_repair_finish`；`bindings=0`；`evidence_retrieved=19`；`outputs_missing=3 / fulfilled=0`
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002]
- explanation: 证据取到了（19/29 条），但修复轮以 `invalid_repair_finish` 收尾且**零绑定**，故没有任何证据能进入交付。与 Round 2 的 `gap_zeroed` 是**不同的失败**：那时有绑定但被 gap 零化，现在连绑定都没生成，失败点前移一步。竞争 L0 无法定夺——产物只给 `stop_reason` 标量，没有拒收判据。

### SECONDARY

none

## Evidence → Finding → Path

### Evidence

#### E-001
- title: 五项盖戳，生产首次可从 git 复现
- run_id: n/a
- step_or_span_id: `/api/health` + 部署目录 git
- native_or_normalized: native
- source_type: environment
- source_ref: `/api/health`；`git -C <loaded_code_root> log -1 / status --porcelain`；`ps -o lstart -p 30091`
- observed_at: 2026-08-15T03:2x+08:00
- raw_excerpt: |
    pid 30091 起于 03:03:11
    health.source_revision=cb09f895  source_dirty=False
    loaded_code_root=.finance-runtime/finance-workspace-cb09f895734a
    该目录 git log -1 = cb09f895；status --porcelain = 0 行
    ASK_TOOL_BATCH_TIMEOUT=60 / ASK_CONTINUOUS_RUNTIME=on / AGENT_RUNTIME_BACKEND=continuous_glm
    产物 preflight_detail: revision=cb09f895 backend=continuous_glm
- observation: 五项齐；**产物 preflight 盖戳首次与 `loaded_code_root` 一致**（此前的错源陷阱消失）。
- confidence: high

#### E-002
- title: B1/B7 零绑定且以 `invalid_repair_finish` 收尾
- run_id: 本批 B1 / B7
- step_or_span_id: `outcome.bindings` / `events[kind=finish].payload`
- native_or_normalized: native
- source_type: file
- source_ref: `<FORESIGHT_USERS_DIR>/linxiaoqi5111/runs/<run_id>/continuous-episode.json`
- observed_at: 2026-08-15T03:4x–03:5x+08:00
- raw_excerpt: |
    B1: execution_state=retrieved_unsynthesized  eb=0  evidence_retrieved=19  bindings=0
        outputs_missing/fulfilled=3/0  caveat_slips=0  stop_reason=invalid_repair_finish
    B7: execution_state=retrieved_unsynthesized  eb=0  evidence_retrieved=29  bindings=0
        outputs_missing/fulfilled=2/0  caveat_slips=0  stop_reason=invalid_repair_finish
- observation: 取证成功但一条绑定都没生成；`caveat_slips=0` 说明二者不经由滑档路径。
- confidence: high

#### E-003
- title: 五态分布与 Round 1 基线的差
- run_id: 本批 28 题
- step_or_span_id: 产物顶层汇总
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/eval/runs/20260814T1926Z-r3-clean-baseline.json`
- observed_at: 2026-08-14T20:02:12Z（`generated_at`）
- raw_excerpt: |
    本批 : delivered 20 / clarification 5 / retrieved_unsynthesized 2 / no_evidence 1 / not_run 0
    Round 1: delivered 11 / not_run 9 / bound_but_dropped 3 / retrieved_unsynthesized 3 / no_evidence 2
    quality_denominator=28，excluded_from_denominator=[]
    execution_state_source_tally: episode_artifact 21 / api_only 7
- observation: `not_run` 由 9 归零；`bound_but_dropped`（现细分为 `gap_zeroed`）由 3 归零。C2-C10 由「连接被拒未执行」变为真实执行。
- confidence: high

#### E-004
- title: R-07 逐格拆分自证
- run_id: 三个冻结 run + 本批
- step_or_span_id: `slot_shapes`
- native_or_normalized: normalized
- source_type: tool_return
- source_ref: `intelligence/eval/acceptance.py` 离线重放
- observed_at: 2026-08-15
- raw_excerpt: |
    B1@RunB → gap_zeroed（slots: gap_zeroed / gap_zeroed / no_hash）
    B3@RunB → gap_zeroed（三格全 gap_zeroed）
    B7@RunA → direct_answer=no_hash 与 evidence_boundary=gap_zeroed 同 turn 分别可见
    本批逐格：clean 49 / no_hash 4 / gap_zeroed 0
- observation: 预注册三条断言逐字命中；本批的 `gap_zeroed` 为 0，该态在本窗口无 live 样本。
- confidence: high

#### E-005
- title: `caveat_slips>0` 的九个 case 全部交付，且无有哈希格未 fulfilled
- run_id: 本批 A6/A8/A10/B2/B3/B4/B5/C7/C9
- step_or_span_id: `events[kind=finish].payload.caveat_slips` + `structural_verifier`
- native_or_normalized: native
- source_type: file
- source_ref: 对应 run 目录 `continuous-episode.json`
- observed_at: 2026-08-15T03:2x–04:02+08:00
- raw_excerpt: |
    A6 slips=2 eb=3 | A8 slips=2 eb=4 | A10 slips=1 eb=3 | B2 slips=3 eb=5
    B3 slips=3 eb=13 | B4 slips=2 eb=2 | B5 slips=1 eb=3 | C7 slips=1 eb=2 | C9 slips=1 eb=2
    「有哈希却未 fulfilled」的格：0 个
- observation: 九个窗口内，无一格出现「有哈希 + 未 fulfilled」。
- confidence: high

#### E-006
- title: 四个真缺口格仍判 missing
- run_id: 本批 A4 / C6 / C9
- step_or_span_id: `outcome.bindings` + `structural_verifier.completion.outputs`
- native_or_normalized: native
- source_type: file
- source_ref: 对应 run 目录 `continuous-episode.json`
- observed_at: 2026-08-15
- raw_excerpt: |
    A4 evidence_boundary  n_hash=0 gap=有 → struct=missing
    C6 direct_answer      n_hash=0 gap=有 → struct=missing
    C6 evidence_boundary  n_hash=0 gap=有 → struct=missing
    C9 chain_mapping      n_hash=0 gap=有 → struct=missing
- observation: 四格无一被放宽为 `fulfilled`。
- confidence: high

### Findings

#### F-001
- title: B1/B7 在干净身份下改以零绑定 + `invalid_repair_finish` 失败
- status: candidate
- failure_span_id: B1 `finish`
- root_location: 修复轮收尾与绑定生成之间
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- violated_authority: user
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002]
- confidence: medium
- explanation: 见 PRIMARY。

#### F-002
- title: 失败集不稳定——跨窗口换人，不是题目属性
- status: validated
- failure_span_id: 批级
- root_location: episode 非确定性
- l0: UNCLEAR
- l1: stop
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A1
- violated_authority: none
- causality: UNCLEAR
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-003]
- confidence: high
- explanation: tool60 批失败的是 B1/B3/B6，本批失败的是 B1/B7——B3 由 0 变 13（恢复），B7 由 5 变 0（退化）。同一题跨窗口可正可反，**「哪两题失败」不可作为稳定结论引用**，任何基于单批成员名单的归因都要带这条限制。

### Path

#### P-001
- title: 干净身份下 B1 的 19 条证据为何仍到不了交付面
- start: 工具取证成功，`outcome.evidence`=19
- goal: `evidence_bound > 0`
- steps:
  1. 取证成功，19 条进入 episode — evidence: E-002 — finding: none
  2. **修复轮以 `invalid_repair_finish` 收尾，`bindings=0`** — evidence: E-002 — finding: F-PRIMARY (F-001)
  3. 无绑定 → 无 `allowed_output_ids` 命中 → 交付层 0 条 — evidence: E-002 — finding: none（按设计）
- residual_uncertainty:
  - RU-1：`invalid_repair_finish` 是模型收尾不合法（REASONING）还是修复轮契约拒收（HARNESS），缺拒收原因码。
  - RU-2：`gap_zeroed` 在本窗口 0 次，无法判断是「已被 R-001 消除」还是「本窗口没抽到」——两者在单批读数上不可区分。

## self_report_vs_observed 对账

| 事项 | 人类可读输出（自述） | 机器状态字段（观测） | 判定 |
|---|---|---|---|
| B1 是否完成 | 验收台 `status=completed` | `evidence_bound=0`、`bindings=0`、`stop_reason=invalid_repair_finish` | **冲突**：`completed` 只表示有可交付终态，不表示质量门通过（trace-profile §2 已记的陷阱，本批再次命中） |
| 产物盖的是哪份代码 | `preflight_detail: revision=cb09f895` | `loaded_code_root` @ `cb09f895`、porcelain 空 | **一致**——这是本项目首次两者相符 |
| 批是否有基础设施失败 | 28/28 打印 `completed` | `not_run=0`、post-run health 200 | 一致 |

按 source precedence 以机器字段为准。第一行的冲突是既有已知陷阱，不新增 Finding；第二行的「一致」本身是本轮最有价值的环境读数。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260815-09 | F-001 | `HARNESS_FIX` | `invalid_repair_finish` 落盘拒收原因码与被拒 payload 的**结构摘要**（字段名/计数，不落正文），使 RU-1 的两个竞争 L0 可分 | 下一个 `invalid_repair_finish` 的 turn 其原因码非空；若指向格式/契约不符则 F-001 的 L0 定 REASONING，指向预算/传输则定 HARNESS | 该字段存在性单测；**单次读数不得结案**，需 ≥3 个同形样本 |
| R-20260815-10 | F-002 | `EVAL_ONLY` | 同题多跑 N 次的方差治理口径应用于 B 组：单批的「失败成员名单」不得写进结论，只报分布 | 连续 3 批后，B 组每题给出交付率而非单次布尔；任一结论若只引用单批名单，评审可据此打回 | 看板断言：B 组结论字段必须携带批次数 N |

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| RU-1 `invalid_repair_finish` 成因 | F-001 的 L0 | 拒收原因码枚举 + 被拒 payload 的字段名列表 | 修复轮收尾拒收处 | 是模型产出不合法还是契约拒收 | 低 |
| RU-2 `gap_zeroed` 零命中的含义 | R-001 是否真消除了该形状 | 无需新埋点，是实验设计：连续 N 批统计 `gap_zeroed` 格数，阈值 N≥3 | — | 「已消除」与「没抽到」可分 | 中（需多批 live） |

## Limits and counterevidence

- **本批与 Round 1 的差不是单变量消融**：身份（脏树→`cb09f895`）、R-001 部署、tool60 窗口、我的量具四组变量同时变化。故本报告按 M1 出，Round 1 对照只作描述性背景，**不从该差推因果**。
- **R-21 的判定不归本报告**。本轮只出数：`caveat_slips>0` 的 case 9 个、C1 违反 0、C2 违反 0、批内 `gap_zeroed` 0 格。是否据此关 R-21 由轨道 A 按其预注册判据决定。
- **`gap_zeroed` 零命中不等于该形状已消除**（RU-2）。R-001 未部署时 B5/B7 就曾自发恢复，滑档本就是非确定行为。
- `R-20260815-04`（`draft_source` 埋点）暂缓虽已解除，本轮**未做**：它动 `continuous_turn_adapter`，与 F-001 所在的修复轮收尾缝相邻，在 RU-1 的原因码落地前动它会同时叠两个变量。
- 混淆因子读数：数据新鲜度 `today=2026-08-15 / latest_data_date=2026-08-14`（滞后 1 日，A1 的 gap 文案另称「仅更新到 2026-08-13」，两处口径不一致，已记）；provider `openai / gpt-5.6-terra`；验收台方差＝本批单次采样，见 F-002。
- 未读取 skill 的受控验收目录；未碰 `episode_protocol.py` 与 verifier 判据。

## Next-step menu

1. 实施 R-20260815-09 的拒收原因码——它是分开 F-001 两个竞争 L0 的唯一最短路径。
2. 把 R-20260815-08（验收台从 `/api/health` 取 users 目录，或不一致时响亮失败）落地：本轮开批前若未手工纠正 env，整批五态会静默落 `undetermined`。
3. 连续再跑 2 批同题集，兑现 R-20260815-10 的方差口径，同时给 RU-2 提供分母。
4. 轨道 A 按其预注册判据消费本批 C1/C2 读数，决定 R-21 去留。
5. `R-20260815-04` 待 RU-1 原因码落地后再单独开 PR，避免与相邻缝叠变量。

---

## 轮次小结 · Round 3 轨道 B

- **主靶完成**：干净身份基线批 `20260814T1926Z-r3-clean-baseline.json`（`sha256=b712bd2e…d8d350`，28 题全量，已随 PR 进 git）。五项盖戳齐：`cb09f895` / porcelain 空 / pid 30091@03:03:11 / continuous 通道 / tool60。**产物 preflight 首次与 `loaded_code_root` 相符**——错源陷阱消失。
- **`not_run` 归零**（Round 1 为 9），`quality_denominator=28`、`excluded=[]`。C2-C10 由「连接被拒未执行」变为真实执行，其中 3 题是澄清轮。
- **B 组 5/8 交付**（B2/B3/B4/B5/B8），B6 澄清轮（非失败），**B1/B7 仍 0 且形状已迁移**：不再是 `gap_zeroed`，而是零绑定 + `stop_reason=invalid_repair_finish`。失败点前移一步，故 outcome 记 `ROOT_CAUSE_NOT_CONFIRMED`。
- **给轨道 A 的数（不替其判）**：`caveat_slips>0` 的 case **9 个**；C1「滑档格必须交付」违反 **0**；C2「真缺口格仍 missing」违反 **0**；批内 `gap_zeroed` 出现 **0 格**。C3 零命中条款**不适用**（窗口存在）。
- **一条要紧的限制**：失败集**跨窗口换人**——tool60 批失败 B1/B3/B6，本批失败 B1/B7，B3 由 0→13 恢复、B7 由 5→0 退化。「哪两题失败」不是稳定结论，已立 `R-20260815-10` 约束口径。
- **`R-20260815-07` confirmed**：三个冻结夹具逐字命中；本批另贡献 4 个 `no_hash` 真缺口格。**但 `gap_zeroed` 本批 0 次**，该态无 live 样本，如实记录未补造。
- **新登记 `R-20260815-08`**：开批前实测发现我 shell 的 `FORESIGHT_USERS_DIR` 与服务端不同，直接开批会让五态整批静默落 `undetermined`/`api_only`——我自己 Round 2 那把量具的同形陷阱。已手工纠正后开批；修复另开 PR。
- **开工核对**：`#17` 的 `R-06` 关闭行合规，仅给旧脏树计数补测量时刻（23 @03:0x 与轨道 B Round 2 的 20 @02:13 都对，差额是 `episode_protocol.py` 等三文件 02:17 被改）；outcome 未动。
- **边界**：`R-20260815-04` 未做（与 F-001 相邻缝，等原因码先落地）；未碰 A 的缝；账本只写 B 段。

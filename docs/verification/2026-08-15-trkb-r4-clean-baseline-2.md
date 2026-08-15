# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_NOT_CONFIRMED
- mode: M1
- failure_criterion: 同身份（`cb09f895` + porcelain 空 + tool60）上跑完 qc28 批 #2 后，B 组按 R-10 报「N=2 次中的交付次数」（`evidence_bound>0`），禁止单批失败成员名单；B1/B7 若再 `invalid_repair_finish` 只记形状与频次 + 事件流 `invalid_action.reason`，不开 L0 分诊。另监测 `gap_zeroed` 与 `caveat_slips`（RU-2 的第 2 点）。
- trace_coverage: 新产物 `intelligence/eval/runs/20260815T0302Z-r4-clean-baseline-2.json`（`sha256=51e61710…304ef4`，28 题 / 30 轮，随本 PR 进 git）；对照冻结批 #1 `20260814T1926Z-r3-clean-baseline.json`（`sha256=b712bd2e…d8d350`）。仓外 run 目录含 `continuous-episode.json`（C4/C5 等无 episode 的已单独点名）。**缺**：R-09 要求的 finish 级拒收原因码字段仍未部署。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Prior prediction closure

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 轨道 B Round 3 | R-20260815-10 | B 组结论改报交付率而非单批布尔后：连续 3 批的 B 组读数按题给出 N 次中的交付次数；任一只引用单批「失败成员名单」的结论可被评审据此打回 | still_pending | E-003 | **N=2 表已出**（见 E-003）。预测要 N=3，不得结案。本报告不写单批失败名单当结论 |
| 轨道 B Round 3 | R-20260815-09 | `invalid_repair_finish` 落盘拒收原因码与被拒 payload 的结构摘要后：下一个该形状的 turn 其原因码非空 | still_pending | E-002 | 本批 B5/C7 再出该形状；事件流有 `invalid_action.reason` 自由文本，**不是** R-09 要的 finish 级结构字段。单次不得结案 |
| 轨道 B Round 4 离线 | R-20260815-11 | 多轮 tally 按轮、aggregate 取 `last_turn` 后 C10 两口径不再矛盾 | confirmed（#22 已关） | E-004 | 批 #2 的 C10 三轮 delivered/clarification/no_hash，aggregate=`no_hash`，与按轮 tally 同态 |
| 轨道 B Round 4 离线 | R-20260815-08 | 错目录响亮失败，不静默落 undetermined 五态 | confirmed（#23 已关） | E-001, E-006 | 本批 live：A1 竞态未整批中止；C4/C5 无 episode 只标单题，28/28 落盘 |
| 轨道 B Round 2 | R-20260815-04 | `draft_source` 埋点 | still_pending | 无 | 本轮未做（A 缝相邻） |
| 轨道 B Round 2 | R-20260815-03 | 两套 output 判定对账 | still_pending | 无 | 本轮无新证据 |
| 2026-08-04 | R-20260804-10 | deadline-aligned per-tool handoff… | still_pending | 无 | 本轮无新证据 |
| 2026-08-04 | R-20260804-02 | 真 Codex rollout 归一化 | still_pending | 无 | 本轮无新证据；B 仍认领回填，无新证据保持 pending |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `EVAL_ONLY`=0；`HARNESS_FIX`=1（R-09 仍 pending，本轮未变）。

## Executive finding

批 #2 在同身份下落盘，`not_run` 仍为 0。B1/B7 **本批交付**（eb=2/14），`invalid_repair_finish` 换到 B5 与 C7——失败集再次换人，R-10 的 N=2 表成立但还不能结案。`gap_zeroed` 连续两批 0 格。不开 B1/B7 根因分诊。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 同身份装配 | `cb09f895`、porcelain 空、tool60、pid 30091；users_dir 对齐 | ok | E-001 |
| tool | 工具取证 | B5 取回 50 条、C7 取回 24 条；B1/B7 本批取回 20/13 | ok | E-002 |
| observe | 证据入 `outcome.evidence` | 同上，非空 | ok | E-002 |
| synthesize | 产出绑定并交付 | B5/C7 `bindings=0`、`draft=0`、末条 `stop_reason=invalid_repair_finish`；B1/B7 本批有绑定 | **fail**（B5/C7） | E-002 |
| stop | 证据到达验收面 | B5/C7 `evidence_bound=0`；B1/B7 本批 2/14 | fail / recovered | E-002, E-003 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| B5 `run_20260815_112319_467917` / 末条 `finish` | UNCLEAR（竞争项仍是 REASONING 收尾不合法 vs HARNESS 修复轮拒收；本轮按指派不开 L0） | synthesize | DEPTH_INSUFFICIENT(D4) | 末条 `stop_reason=invalid_repair_finish`；其前 `invalid_action.reason=binding contains truncated evidence hash: 26b34fb8653fc3f…`；`bindings=0` `draft=0` `evidence=50` | medium |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | B1/B7 在批 #2 仍以 `invalid_repair_finish` + 零绑定失败 | 若成立，二者末条 finish 为该 stop_reason 且 `evidence_bound=0` | E-002, E-003 | **REJECTED** | — | B1 eb=2、B7 eb=14，末条分别为 `repair_model_stop` / `repair_model_finish`，三格/两格 clean 且 fulfilled |
| H2 | B 组失败集按题固定 | 若成立，批 #1 未交付的 B1/B7 在 #2 仍未交付，且 #1 已交付的题在 #2 仍交付 | E-003 | **REJECTED** | — | B1 0→2、B7 0→14 恢复；B3 13→0、B5 3→0 退化。N=2 已够否证「固定成员」 |
| H3 | 本窗口 `gap_zeroed` 仍为 0 | 若成立，批 #2 全部 binding 格无「n_hash>0 且 gap」 | E-005 | **CONFIRMED**（仅本窗口） | — | 逐格 28 clean + 16 no_hash + **0 gap_zeroed**。RU-2 要 N≥3，本批是第 2 点 |
| H4 | N=2 即可关闭 R-10 | 若成立，预测原文的「连续 3 批」可被两批替代 | E-003 | **REJECTED** | — | 预测写死 N=3；两批只出表，不结案 |
| H5 | 本批仍会出现与 Round 3 B1/B7 同形的 `invalid_repair_finish` + 零绑定 | 若成立，至少一题末条该 stop_reason 且 bindings=0 | E-002 | **CONFIRMED**（只记形状/频次） | — | B5 与 C7 两例；事件流 `invalid_action.reason` 均为 truncated evidence hash。不开 L0 |

## Causal findings

### PRIMARY

- failure_span_id: B5 `run_20260815_112319_467917` / 末条 `finish`（同形另见 C7 `run_20260815_113732_480025`）
- root_location: 修复轮收尾与绑定生成之间（A 缝；本轮只记形状）
- excerpt: 末条 `stop_reason=invalid_repair_finish`；`invalid_action.reason=binding contains truncated evidence hash: 26b34fb8653fc3f; copy the complete hash from the evidence list`；`bindings=0`；`draft=0`；`evidence_retrieved=50`
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002]
- explanation: 取证成功后修复轮被拒、零绑定，与 Round 3 的 B1/B7 同形，但**换题**。事件流已有截断哈希原因文本，仍不是 R-09 的结构字段；按 Round 4 指派不开 L0。

### SECONDARY

- failure_span_id: 批级 B 组 N=2
- root_location: episode 非确定性（交付成员跨批换人）
- excerpt: 见 E-003 八行交付率
- l0: UNCLEAR
- l1: stop
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A1
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-003]
- explanation: 单批「谁失败」不可引用。N=2 已再次换人；结案仍要第 3 批。

## Evidence → Finding → Path

### Evidence

#### E-001
- title: 批 #2 身份与 preflight 仍对齐生产
- run_id: n/a
- step_or_span_id: `/api/health` + 部署目录 git
- native_or_normalized: native
- source_type: environment
- source_ref: `/api/health`；`git -C ~/.finance-runtime/finance-workspace-cb09f895734a status --porcelain`；`lsof -iTCP:8792`
- observed_at: 2026-08-15T11:02+08:00 开批 / 11:43 收批
- raw_excerpt: |
    pid 30091（未换）
    health.source_revision=cb09f895  source_dirty=False  porcelain=0
    ASK_TOOL_BATCH_TIMEOUT=60  AGENT_RUNTIME_BACKEND=continuous_glm
    产物 preflight_detail: revision=cb09f895 backend=continuous_glm
      users_dir=/Users/a77/.local/share/finance-workbench/users
    generated_at=20260815T034326Z  quality_denominator=28  excluded=[]
- observation: 五项盖戳与批 #1 同一进程、同一 revision。users_dir 已写入 preflight（8792 仍不暴露 `runtime.users_dir`，靠 env）。
- confidence: high

#### E-002
- title: B5/C7 零绑定 + 末条 `invalid_repair_finish`；B1/B7 本批交付
- run_id: B5 `run_20260815_112319_467917`；C7 `run_20260815_113732_480025`；B1 `run_20260815_111434_935495`；B7 `run_20260815_112440_317076`
- step_or_span_id: 末条 `events[kind=finish]` 与其前 `invalid_action`
- native_or_normalized: native
- source_type: file
- source_ref: `$FORESIGHT_USERS_DIR/linxiaoqi5111/runs/<run_id>/continuous-episode.json`
- observed_at: 2026-08-15T11:24–11:38+08:00
- raw_excerpt: |
    B5 末条 finish: stop_reason=invalid_repair_finish  bindings=0  draft=0  evidence=50
      invalid_action.reason=binding contains truncated evidence hash: 26b34fb8653fc3f; copy the complete hash from the evidence list
    C7 末条 finish: stop_reason=invalid_repair_finish  bindings=0  draft=0  evidence=24
      invalid_action.reason=binding contains truncated evidence hash: cfccfbcb9a1ed3a; copy the complete hash from the evidence list
    B1 末条: repair_model_stop  eb=2  bind=3 三格 clean fulfilled  evidence=20
    B7 末条: repair_model_finish  eb=14  bind=2 两格 clean fulfilled  evidence=13
- observation: 同形失败换到 B5/C7；B1/B7 本批走出该形状。原因文本在事件流，不在 finish 结构字段。
- confidence: high

#### E-003
- title: B 组 N=2 交付率（R-10 口径，`evidence_bound>0`）
- run_id: 批 #1 与批 #2 的 B1–B8
- step_or_span_id: 各 case `turns[-1].evidence_bound` / `execution_state`
- native_or_normalized: native
- source_type: file
- source_ref: `20260814T1926Z-r3-clean-baseline.json` 与 `20260815T0302Z-r4-clean-baseline-2.json`
- observed_at: 2026-08-15T03:43:26Z（批 #2 `generated_at`）
- raw_excerpt: |
    B1  #1 eb=0 retrieved_unsynthesized   #2 eb=2  delivered                 1/2
    B2  #1 eb=5 delivered                 #2 eb=6  delivered                 2/2
    B3  #1 eb=13 delivered                #2 eb=0  no_hash                   1/2
    B4  #1 eb=2 delivered                 #2 eb=2  delivered                 2/2
    B5  #1 eb=3 delivered                 #2 eb=0  retrieved_unsynthesized   1/2
    B6  #1 eb=0 clarification             #2 eb=0  clarification             0/2（两批皆澄清轮，非失败）
    B7  #1 eb=0 retrieved_unsynthesized   #2 eb=14 delivered                 1/2
    B8  #1 eb=17 delivered                #2 eb=17 delivered                 2/2
- observation: 交付成员跨批换人。B6 两批都是澄清轮。不得把「本批 B3/B5 失败」写成稳定结论。
- confidence: high

#### E-004
- title: 批 #2 五态（R-11 按轮 tally + last_turn aggregate）与 C10 同态
- run_id: 本批 28 题 / 30 轮
- step_or_span_id: 产物顶层汇总
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/eval/runs/20260815T0302Z-r4-clean-baseline-2.json`
- observed_at: 2026-08-15T03:43:26Z
- raw_excerpt: |
    execution_state_aggregate_rule=last_turn
    tally(按轮, 30): delivered 11 / no_evidence 8 / clarification 6 / no_hash 2 / retrieved_unsynthesized 2 / undetermined 1
    case_tally(28): delivered 10 / no_evidence 8 / clarification 5 / no_hash 2 / retrieved_unsynthesized 2 / undetermined 1
    source: episode_artifact 22 / api_only 8
    not_run=0  quality_denominator=28  excluded=[]
    C10 三轮: delivered / clarification / no_hash；aggregate=no_hash
- observation: 按轮与按 case 差 1 个 delivered / 1 个 clarification，正好是 C10 前两轮，不再互相矛盾。
- confidence: high

#### E-005
- title: `gap_zeroed=0`；16 个 no_hash 真缺口格仍 missing；slips>0 窗口 8 case
- run_id: 本批全部有 episode 的 turn
- step_or_span_id: `outcome.bindings` + 末条 `finish.payload.caveat_slips` + `structural_verifier.completion.outputs`
- native_or_normalized: native
- source_type: file
- source_ref: 各 run `continuous-episode.json`（独立重扫，不信 tally 摘要）
- observed_at: 2026-08-15T11:43+08:00
- raw_excerpt: |
    逐格: clean 28 / no_hash 16 / gap_zeroed 0
    no_hash 且 n=0+gap 的 16 格 struct 全是 missing（C2 违反 0）
    有哈希却未 fulfilled：0 格（C1 违反 0）
    末条 finish caveat_slips>0 的 case: A9=1 B2=3 B3=2 B4=1 B7=1 C1=1 C6=1 C10(t0=2,t2=1)
    若误取首条 finish，上述 slips 全部读成 0
- observation: 真缺口无一放宽。滑档窗口 8 个 case（C10 两轮都有）。`gap_zeroed` 连续两批 0。
- confidence: high

#### E-006
- title: R-08 量具在 live 上未整批误杀
- run_id: C4 `run_20260815_113036_284206`；C5 `run_20260815_113225_616446`；A1 `run_20260815_110258_512040`
- step_or_span_id: run 目录存在性 / `continuous-episode.json`
- native_or_normalized: native
- source_type: file
- source_ref: `$FORESIGHT_USERS_DIR/linxiaoqi5111/runs/<run_id>/`
- observed_at: 2026-08-15T11:02–11:43+08:00
- raw_excerpt: |
    C4: run 目录在（run.json/report.json/trace.jsonl），无 continuous-episode.json；acceptance 标 delivered/api_only eb=24，批未中止
    C5: 目录在、无 episode；201.5s；aggregate=undetermined/api_only
    开批后第一次 A1 在 API completed 后数秒才写出 episode（第二次尝试曾因此零命中误杀）；本批 A1 读到产物
- observation: 错目录才会整批响亮失败；目录对、文件晚写或缺失只标单题。
- confidence: high

#### E-007
- title: B3 验收 `evidence_bound=0` 与 episode 已 fulfilled 的哈希格不一致
- run_id: `run_20260815_111907_054023`
- step_or_span_id: `outcome.bindings` vs 产物 `evidence_bound`
- native_or_normalized: native
- source_type: file
- source_ref: 该 run `continuous-episode.json`；批 JSON B3 turn
- observed_at: 2026-08-15T11:19+08:00
- raw_excerpt: |
    episode: evidence=11 draft=341
      direct_assessment n_hash=3 gap=无 struct=fulfilled
      chain_mapping     n_hash=8 gap=无 struct=fulfilled
      counterpoint      n_hash=0 gap=有 struct=missing
    末条 finish: repair_model_stop  caveat_slips=2
    产物: evidence_bound=0  evidence列表空  execution_state=no_hash
- observation: R-10 仍按冻结的 `evidence_bound>0` 计 B3 本批未交付。episode 层两格已交付。两套读数并存，不以其中一套改口径。
- confidence: high

### Findings

#### F-001
- title: `invalid_repair_finish` + 零绑定换到 B5/C7（与 Round 3 B1/B7 同形）
- status: candidate
- failure_span_id: B5 末条 `finish`
- root_location: 修复轮收尾
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
- explanation: 见 PRIMARY。只记形状与截断哈希原因文本，不定 L0。

#### F-002
- title: B 组交付成员跨批换人（N=2）
- status: validated
- failure_span_id: 批级
- root_location: episode 非确定性
- l0: UNCLEAR
- l1: stop
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A1
- violated_authority: none
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-003]
- confidence: high
- explanation: 见 E-003。R-10 仍要第 3 批。

### Path

#### P-001
- title: B5 的 50 条证据为何到不了交付面
- start: 工具取证成功，`outcome.evidence`=50
- goal: `evidence_bound > 0`
- steps:
  1. 取证成功，50 条进入 episode — evidence: E-002 — finding: none
  2. 修复轮 `invalid_action`（截断哈希）后末条 `invalid_repair_finish`，`bindings=0` `draft=0` — evidence: E-002 — finding: F-PRIMARY (F-001)
  3. 无绑定 → 交付层 0 — evidence: E-002 — finding: none（按设计）
- residual_uncertainty:
  - RU-1：finish 级拒收原因码字段仍未部署；事件流自由文本不能当 R-09 结案。
  - RU-2：`gap_zeroed` 连续两批 0，仍差第 3 批才能分「已消除」与「没抽到」。
  - RU-3：B3 的 `evidence_bound` 与 episode fulfilled 不一致（E-007）；R-10 不改口径。

## self_report_vs_observed 对账

| 事项 | 人类可读输出（自述） | 机器状态字段（观测） | 判定 |
|---|---|---|---|
| B5/C7 是否完成 | 验收台 `status=completed` | 末条 `invalid_repair_finish`、`bindings=0`、`evidence_bound=0` | **冲突**：`completed` ≠ 质量门通过（已知陷阱） |
| B3 是否交付 | episode 两格 hashed+fulfilled | 产物 `evidence_bound=0` | **冲突**：两套仪器；R-10 用后者，前者记入 E-007 |
| C10 五态 | 末轮 `no_hash` | tally 含该轮 `no_hash`，aggregate=`no_hash` | **一致**（R-11 口径） |
| 批是否有基础设施失败 | 28/28 打印 `completed` | `not_run=0`、BATCH_RC=0 | 一致 |

按 source precedence：质量看机器字段；B3 冲突两套都保留，不选边改 R-10。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260815-09 | F-001 | `HARNESS_FIX` | （已登记，A 缝，只实现不部署）finish 级拒收原因码 + 被拒 payload 结构摘要 | 下一个该形状 turn 的原因码非空；≥3 同形样本才结案 | 字段存在性单测；本批 B5/C7 是 before 基线，不是结案样本 |
| R-20260815-10 | F-002 | `EVAL_ONLY` | （已登记）B 组只报交付率，带批次数 N | 第 3 批落地后每题给出 N=3 次数；单批名单可打回 | 看板结论字段必须带 N |

本轮不新开账本 ID。

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| RU-1 finish 级原因码 | F-001 的 L0 / R-09 | 末条 finish 上非空 `reject_reason` 枚举 | A 缝修复轮拒收处（已指派，不部署） | 截断哈希 vs 预算 vs 传输可分 | 低 |
| RU-2 `gap_zeroed` 零命中 | R-001 是否消除该形状 | 无需新埋点：第 3 批同口径数 `gap_zeroed` 格 | — | N=3 后「已消除」与「没抽到」可分 | 中 |
| RU-3 `evidence_bound` vs episode fulfilled | B3 算不算交付 | 产物并行写 `episode_fulfilled_hashed`（格数）；与 `evidence_bound` 同时在场 | 验收台读 episode 后 | 两套仪器差是否>0 | 低 |

## Limits and counterevidence

- **不开 B1/B7 根因分诊**（Round 4 指派）。B5/C7 的截断哈希文本只作形状记录，供 R-09 部署后对照。
- **R-10 不结案**。N=2 表不是 N=3。
- **R-21 不归本报告**。本批只出数：末条 `caveat_slips>0` 的 case **8 个**（A9/B2/B3/B4/B7/C1/C6/C10）；C1 违反 **0**；C2 违反 **0**；`gap_zeroed` **0** 格。
- A 组本批大量 `no_evidence`（A1/A2/A4–A8）相对批 #1 的交付是描述性对照，**不**另立「A 组失败成员名单」。
- 前两次开批（C4 无 episode 整批中止；A1 episode 晚写零命中误杀）**不是**批产物，已修量具后重跑全集；不把中止 stdout 缝进 N=2。
- 未碰 `episode_protocol.py` / `agent_episode.py` / `continuous_turn_adapter.py`。账本不改 R-21。
- 未读取 skill 受控验收目录。

## Next-step menu

1. 第 3 批同身份 qc28，凑齐 R-10 的 N=3，并给 RU-2 分母。
2. A 部署 R-09 后，用本批 B5/C7 作 before，再跑一批看原因码是否非空。
3. 验收台并行落 `episode_fulfilled_hashed`，切开 RU-3。
4. 轨道 A 按其收窄谓词与预注册判据消费本批 slips/C1/C2 数。
5. `R-20260815-04` 仍等 R-09 落地后再单独动相邻缝。

---

## 轮次小结 · Round 4 轨道 B

- **勘误+rebase**：E-r3-1/E-r3-2 已合入 #21（`35887e34`，基线 `f43f2507`）。批 #1 JSON 未改。
- **R-11 confirmed**：五态按轮 tally、aggregate=`last_turn`；C10 冻结夹具 + 批 #2 live C10 同态。#22。
- **R-08 confirmed**：错目录响亮失败；live 上 C4/C5 无 episode 不整批中止，A1 落盘竞态加短等。#23。
- **批 #2**：`20260815T0302Z-r4-clean-baseline-2.json` `sha256=51e61710…304ef4`，28/28，`not_run=0`，分母 28，身份仍 `cb09f895`/pid 30091/tool60。
- **R-10 N=2**（不结案）：B1 1/2、B2 2/2、B3 1/2、B4 2/2、B5 1/2、B6 0/2（两批澄清）、B7 1/2、B8 2/2。B1/B7 本批交付；同形失败在 B5/C7。
- **B5/C7 形状**：零绑定 + 末条 `invalid_repair_finish`；`invalid_action.reason` 均为 truncated evidence hash。不开 L0。
- **监测**：`gap_zeroed=0`（连续两批）；no_hash 16 格全 missing；slips>0 共 8 case，C1/C2 违反 0。
- **边界**：R-09/R-10/R-03/R-04/R-04-10 仍 pending；不改 R-21；未写母本轮次记录。

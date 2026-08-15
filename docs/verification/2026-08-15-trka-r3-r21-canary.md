# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_NOT_CONFIRMED
- mode: M1
- failure_criterion: 干净基线批（轨道 B 本轮唯一 live 批）上，R-21 canary 按下节预注册三条判据判定。否命题是：滑档有哈希格未 fulfilled 或 eb=0，或真缺口格被放宽为 fulfilled，或零命中后改口扩批/改处置。本文件提交时批尚未开跑，PRIMARY 不停在未观测窗口上硬选叶子。
- trace_coverage: 预注册提交。尚无 `*r3-clean-baseline*` 产物。对照形状来自已冻结 run：B7 `run_20260814_023030_100048`、B1@RunB（轨道 B Round 2 E-002/H3，`counterpoint` n_hash=0 混合形）。未读 skill 受控验收目录。未跑 live。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Prior prediction closure

本轨道只读 Open 表，不写 `R-20260804-10` 与 B 轨行。`R-20260815-22` 已 Closed confirmed。`R-20260815-06` 已 confirmed（#17）：本轮期望盖戳 `cb09f895` + porcelain 空。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 轨道 A Round 1 | R-20260815-21 | 全格 hashes+gap 经 validate 后 gap 归位、verifier fulfilled；无哈希 gap 仍拒绝；leftover gap 仍 missing。live canary 只作确认，单次 live 不独立结案 | still_pending | E-001 | 离线门已绿。本轮 canary 判据在开批前冻结；零命中不得改口 |
| 轨道 A Round 2 | R-20260815-22 | caveat_slips 三断言 | confirmed | none — 已进 Closed | 计数仪器已在干净身份上；本轮用它读数，不重开 |
| 轨道 B Round 2 | R-20260815-06 | porcelain 空且 health revision 与目录一致 | confirmed | E-002 | 首次可从 git 复现；canary 成立条件首次满足 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `HARNESS_FIX`=1（距升格线 2）；`EVAL_ONLY`=0；二者不互相累计

## Pre-registered canary

- frozen_at: 2026-08-15T03:14:33+08:00
- frozen_before: 轨道 B 干净基线批 `generated_at`（本文件必须先于该时间戳进 gitea）
- window: 该批全部 case 的 episode `finish.payload` + structural outputs + 验收台 `evidence_bound`
- stamp_expected: `loaded_code_root` @ `cb09f895` + `git status --porcelain` 空 + health `source_revision` 与目录 `git log -1` 一致 + `ASK_TOOL_BATCH_TIMEOUT=60`
- read_path: 直读结构化字段。不用展示话术、不用旧 eb 标量单独结案。

### C1 · 滑档格必须交付

批内任一 `finish.payload.caveat_slips > 0` 的 case：

- 每一个 `n_hash > 0` 的 required output，structural status = `fulfilled`；
- 该 case 验收台 `evidence_bound > 0`。

任一有哈希格仍 `missing` 或 eb=0 → **R-21 refuted**。

### C2 · 真缺口格仍 missing

批内任一格满足 `n_hash = 0` 且 `binding.gap` 非空：structural status 必须仍是 `missing`。

对照形状（机制，不是必须复现同一题）：B7 混合形（`direct_answer` 0 hash 真缺口 + `evidence_boundary` 滑档）；B1@RunB 的 `counterpoint` n_hash=0（轨道 B Round 2 E-002/H3）。

任一真缺口格变为 `fulfilled` → **R-21 refuted**（放宽了判据）。

### C3 · 零命中处置（预先写死，事后不得改口）

若批内 `caveat_slips > 0` 的 case 数 = 0：

- 记 `unobserved-in-window`；
- **R-21 保持 `pending`**；
- **不申请扩批**，不把「本窗未抽到滑档」改写成 confirmed 或 refuted。

理由（冻结）：滑档是非确定行为（R-001 未部署时 B5/B7 已自发恢复）；R-21 原文即「单次 live 不独立结案」。本窗是修复后首个干净身份窗口，零命中只说明没抽到，不证伪离线门。扩批是新实验，须另报检阅方，不是本 canary 的默认动作。

### 条件靶（同窗预注册）

- 批内任一 finish 出现 `carried_draft_chars = 0` → 以其为新靶开标准 M1（埋点已在 main）。
- 未出现 → 不自行扩缝；从母本 §4 候选池选题须报检阅方核准。

## Executive finding

本提交只冻结 canary 判据，不分配新的运行时 PRIMARY。批产物未到，不能确认或证伪 R-21 的 live 臂。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 干净身份 `cb09f895` porcelain 空 | R-06 confirmed；批未开 | ok | E-002 |
| stop | finish 带 `caveat_slips`；滑档格可交付 | 窗口未观测 | missing | E-001 |
| observe | 真缺口格仍 missing | 窗口未观测 | missing | E-001 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| r3-clean-baseline（未开跑） | HARNESS | stop | DEPTH_INSUFFICIENT(D3) | 预注册三条判据已冻结；批产物不存在 | medium |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 干净窗口若抽到 `caveat_slips>0`，有哈希格会 fulfilled 且 eb>0 | C1 对该窗每一个 slips>0 的 case 成立 | E-001 | INCONCLUSIVE | 批内 `finish.payload.caveat_slips` 与 structural `fulfilled`；阈值：有哈希格 100% fulfilled 且 eb>0 | 批未开 |
| H2 | 真缺口格不会被 R-001 放宽 | C2：n_hash=0 且 gap 非空的格全部 missing | E-001 | INCONCLUSIVE | 同窗 per-slot `n_hash`×`gap`×structural status；任一 fulfilled 即证伪 | 批未开 |
| H3 | 本窗可能抽不到滑档；零命中不得改口 | C3：slips>0 的 case 数=0 时 outcome 仍 pending + `unobserved-in-window` | E-001 | INCONCLUSIVE | 批内 slips>0 计数；=0 则必须保持 pending | 批未开 |

## Causal findings

### PRIMARY

- failure_span_id: r3-clean-baseline/not-yet-run
- root_location: R-21 live 臂等待干净窗口；判据已预注册
- excerpt: frozen_at=2026-08-15T03:14:33+08:00; C3=unobserved-in-window keep pending
- l0: HARNESS
- l1: stop
- l2: DEPTH_INSUFFICIENT(D3)
- l3: n/a
- causality: PRIMARY_FAILURE
- propagation_impact: [UNCLEAR]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001]
- explanation: 仪器与身份已齐，窗口未观测。不在未开跑的批上硬选叶子。

### SECONDARY / TERTIARY

none

## Evidence → Finding → Path

### Evidence

### E-001
- title: canary 三条判据在开批前冻结
- run_id: n/a
- step_or_span_id: docs/verification/2026-08-15-trka-r3-r21-canary.md#Pre-registered-canary
- native_or_normalized: native
- source_type: file
- source_ref: 本文件 Pre-registered canary 节；账本 `R-20260815-21` 怎么验追加指针
- observed_at: 2026-08-15T03:14:33+08:00
- raw_excerpt: |
    C1 slips>0 → hashed slots fulfilled and eb>0; C2 n_hash=0+gap → still missing; C3 zero hits → unobserved-in-window, R-21 stays pending, no expansion
- observation: 三条判据与零命中处置已写死。批产物此时不存在。
- confidence: high

### E-002
- title: 干净身份三角已确认
- run_id: n/a
- step_or_span_id: R-20260815-06 closed
- native_or_normalized: native
- source_type: file
- source_ref: `docs/prediction-ledger.md` Closed `R-20260815-06`；handoff Round 3 §0
- observed_at: 2026-08-15
- raw_excerpt: |
    loaded_code_root=~/.finance-runtime/finance-workspace-cb09f895734a; porcelain empty; source_revision=cb09f895; pid 30091
- observation: R-21 live 臂的身份前提首次成立。本轨道不跑该批。
- confidence: high

### self_report_vs_observed

| 对账对象 | 机器/原始观测 | 人类可读或后处理字段 | 采用口径 |
|---|---|---|---|
| canary 是否已跑 | 无 `*r3-clean-baseline*` 产物 | 「R-001 已上线所以 canary 过了」 | 未开跑不得结案 |
| 零命中含义 | slips>0 计数=0 | 「没复现就是修好了」 | 预注册 C3：unobserved-in-window，保持 pending |

### Findings

### F-001
- title: R-21 live 臂等待预注册窗口
- status: candidate
- failure_span_id: r3-clean-baseline/not-yet-run
- root_location: 干净基线批尚未落盘
- l0: HARNESS
- l1: stop
- l2: DEPTH_INSUFFICIENT(D3)
- l3: n/a
- violated_authority: none
- causality: PRIMARY_FAILURE
- propagation_impact: [UNCLEAR]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002]
- confidence: medium
- explanation: 判据已冻。读数必须等批产物。零命中处置已写死。

### Path

### P-001
- title: 先冻判据再读窗口
- start: R-001 + caveat_slips 在 cb09f895 干净身份上
- goal: 按 C1/C2/C3 收口 R-21；若出现 carried_draft_chars=0 则转新靶
- steps:
  1. 开批前冻结三条判据 — evidence: E-001 — finding: F-001
  2. 批落后直读 finish.caveat_slips 与 structural outputs — evidence: E-001 — finding: none
- residual_uncertainty: 批尚未开跑，C1/C2/C3 均未观测；丢稿事件是否出现未知。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-021-canary | F-001 | NO_SYSTEM_FIX | 不改代码。批落后按预注册 C1/C2/C3 回填 R-21 | 见 Pre-registered canary；零命中保持 pending | 本文件冻结时间戳早于批 `generated_at` |

### R-021-canary
- targets_finding: F-001
- fix_type: NO_SYSTEM_FIX
- recommendation: 只读批产物收口，不改 verifier / 不跑 live。
- verification_prediction: 见 C1/C2/C3。
- regression_guard: 本文件 Pre-registered canary 节；提交时间戳 < 批 generated_at
- auto_apply: false

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| 干净基线批未落盘 | C1/C2/C3 与丢稿条件靶 | 批产物存在且 `generated_at` 晚于本提交；读 `caveat_slips` 与 `carried_draft_chars` | 轨道 B `intelligence/eval/runs/*r3-clean-baseline*.json` + run 目录 | 能否收口 R-21；是否转丢稿 M1 | 本轨道零（只读） |

## Limits and counterevidence

- 本轨道不跑 live、不持 live-lock。
- 不碰 acceptance / normalize / verifier 判据。
- 单点未复现不得当修复证据；C3 已把该口子封死。
- 热贴身份下的旧 canary 不作正式结案。

## Next-step menu

1. 等轨道 B 干净基线批落盘（`generated_at` 必须晚于本提交）。
2. 按 C1/C2/C3 读数回填 `R-20260815-21`。
3. 若出现 `carried_draft_chars=0`，以其为靶开标准 M1。
4. 若未出现丢稿，不自行扩缝，候选靶报检阅方。
5. 不重开 A4 / A3 / R6-A3。

## Round 3 小结（预注册）

- 开批前冻结 C1 滑档交付、C2 真缺口仍 missing、C3 零命中=`unobserved-in-window` 保持 pending。
- 条件靶：批内 `carried_draft_chars=0` 则转 M1。
- 全程离线。批后按本文件收口，不得改口。

## Post-batch closure

- closed_at: 2026-08-15（轨道 A Round 4；预注册原文一字未改）
- batch: `/Users/a77/fwp-wt-b-r3/intelligence/eval/runs/20260814T1926Z-r3-clean-baseline.json`
- sha256: `b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`
- generated_at: `20260814T200212Z`（晚于 frozen_at `2026-08-15T03:14:33+08:00` / 提交 `4df486c2` @ 03:15:31+08）
- stamp: `preflight_ok=true`，`preflight_detail=revision=cb09f895 backend=continuous_glm`，`quality_denominator=28`，`excluded_from_denominator=[]`
- reader: 轨道 A 独立重扫 `$FORESIGHT_USERS_DIR/linxiaoqi5111/runs/<run_id>/continuous-episode.json` 的 `finish.payload.caveat_slips` + `structural_verifier.completion.outputs` + 验收台 `evidence_bound`。不改 B 产物。

### C1 · 通过（零违反）

`caveat_slips>0` 恰 9 题，有哈希格全部 `fulfilled` 且 `evidence_bound>0`：

| case | slips | eb | 有哈希格 |
|---|---|---|---|
| A6-limit-advance-ladder | 2 | 3 | direct_answer / evidence_boundary |
| A8-market-stage | 2 | 4 | direct_assessment / supporting_evidence / risk_signals |
| A10-new-high-structure | 1 | 3 | direct_answer / evidence_boundary |
| B2-theme-liquid-cooling | 3 | 5 | 三格均有哈希 |
| B3-theme-solid-state-battery | 3 | 13 | 三格均有哈希 |
| B4-fermentation-trace | 2 | 2 | 三格均有哈希 |
| B5-cross-table-intersection | 1 | 3 | 两格均有哈希 |
| C7-temporal-leakage | 1 | 2 | 五格均有哈希 |
| C9-citation-integrity | 1 | 2 | direct_assessment / counterpoint fulfilled；chain_mapping 0 哈希 → C2 |

### C2 · 通过（零违反）

`n_hash=0` 且 `binding.gap` 非空的格共 6 个，structural status 全部 `missing`：

- A4 `evidence_boundary`
- C6 `direct_answer` + `evidence_boundary`
- C9 `chain_mapping`（与 C1 同 turn，混合形正样本）
- C10-t3 `direct_answer` + `evidence_boundary`

### C3 · 不适用

滑档命中 9>0，不走 `unobserved-in-window`。

### 条件靶 · 未触发（谓词过宽已修正，收窄后零命中）

- 字面谓词「批内出现 `carried_draft_chars=0`」过宽：41 个 finish 事件中 21 个为 0（停机路径无稿可携带时合法写 0）。
- 收窄谓词：同 episode 内曾有 `draft_chars>0`，其后事件 `carried_draft_chars=0`。**0 命中**。
- 处置：不开 M1，不自行扩缝。B1/B7 主路径 `deadline_exhausted` 的 finish 带 `carried_draft_chars=0`，但从未产生 `draft_chars>0`。

### 账本

`R-20260815-21` → Closed `confirmed`。C10-t3 验收态为 `bound_but_dropped`（两格 no_hash 真缺口），不移动 C1/C2 / `gap_zeroed`；tally 聚合仍归 B。

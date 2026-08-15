# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M1
- failure_criterion: 主路径 `deadline_exhausted` 且修复轮已收集证据的 case，终态 `invalid_repair_finish` 且验收台 `evidence_bound=0`。否命题是「修复轮把已收集证据绑上并交付 eb>0」。B1/B7 划入靶内；数据源不可用 / 新鲜度缺口单独成环，不放宽本标准。
- trace_coverage: 干净基线批 `20260814T1926Z-r3-clean-baseline.json`（`sha256=b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`，`generated_at=20260814T200212Z`，`revision=cb09f895`）。主 case B1 `run_20260815_034008_215204`、B7 `run_20260815_034828_738989` 的 episode 事件流 + 证据集 `content_hash`。R-21 canary 按预注册原文独立重扫 28 case。未跑 8792 live。未读 skill 受控验收目录。
- trace_depth: D3
- completion_status: COMPLETE_FAILURE
- confidence: high

## Prior prediction closure

本轨道只读 Open 表，不写 `R-20260804-10` 与 B 轨行。`R-20260815-22` 已 Closed confirmed。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 轨道 A Round 1 / Round 3 canary | R-20260815-21 | 全格 hashes+gap 经 validate 后 gap 归位、verifier fulfilled；无哈希 gap 仍拒绝；leftover gap 仍 missing。live canary：C1 slips>0 → 有哈希格 fulfilled 且 eb>0；C2 n_hash=0+gap → 仍 missing；C3 零命中保持 pending | confirmed | E-004、E-005 | 预注册原文未改。C1 9 题零违反、C2 6 格零违反、C9 混合形成立。条件靶收窄后 0 命中，不开 M1。行进 Closed |
| 轨道 A Round 2 | R-20260815-22 | caveat_slips 三断言 | confirmed | none — 已进 Closed | 计数仪器已在干净身份上；本轮用它读 C1，不重开 |
| L7 finalization T3 | R-20260804-10 | deadline-aligned per-tool handoff 离线主门 + 瑞华泰 canary | still_pending | none — 本轨道无 headless 新证据 | 保持 Open；本轨道不写该行 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `HARNESS_FIX`=1（距升格线 2）；`EVAL_ONLY`=0；`DATA_CONTRACT_FIX`=0（R-21 confirmed 不累计 refuted）；三者不互相累计

## Executive finding

第一处错误变换是终局契约逼模型把观察里的 16-hex `content_hash` 誊进 `evidence_hashes`。B1/B7 修复轮引用的是真实证据，只是换位 / 拼接 / 多写一位 / 少写一位；协议 fail-closed 正确拒收，落成零绑定、`evidence_bound=0`。验收 JSON 没有拒收句，但 run 目录 `invalid_action.reason` 写着 `binding contains unknown evidence hash`。

## Local vocabulary ↔ L1

本仓 `trace-profile.md` §6 词表 `triage-l1-9`。PRIMARY 定在 episode 事件（D3）。

| 本地 kind / step_id | L1 | provenance |
|---|---|---|
| 系统提示 / FINAL_JSON schema / 模型可见 tool 观察 | `configure` | episode native + 代码契约 |
| `task` | `intent` | episode native |
| `plan` / `repair_goal` / `repair_reentry` | `plan` | episode native |
| `tool_request` | `tool` | episode native |
| `tool_result` / `tool_error` / `invalid_action` | `observe` | episode native |
| 收尾或 repair 的 `model_turn` | `synthesize` | episode native |
| `finish` | `stop` | episode native |

损耗：episode 无独立 `route`。无明确映射的事件未就近归类。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 绑定用低熵稳定引用；模型不必抄 16-hex | 提示与 schema 要求抄 `content_hash`；模型可见观察带完整哈希 | fail | E-007 |
| retrieve / tool | 取到可绑定证据 | B1 19 条、B7 29 条，全部 16 hex | ok | E-001、E-002 |
| observe | 拒收原因可在产物内读到 | 验收 JSON 无 reason；事件流 `invalid_action.reason` 完整 | ok | E-006 |
| synthesize | 引用已收集证据 | 写成近真哈希：换位 / 拼接 / 插入 / 删除 | fail | E-001、E-002、E-003 |
| stop | 有证据的修复轮应绑定并交付 | `invalid_repair_finish`；bindings=0；eb=0 | fail | E-001、E-002 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260815_034008_215204/events[sequence=20]` | HARNESS | configure | task-instruction-category-non-compliance | `binding contains unknown evidence hash: 3b0895e3a338d58f,8b9fcfe85a338d58f` | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 拒收哈希是对真实证据的誊抄错误，不是编造 | 每个 unknown token 都能在证据集里找到唯一近邻（换位 / 插入 / 删除 / 拼接） | E-001、E-002、E-003 | CONFIRMED | — | 四枚标本逐字符命中；证据集全是 16 hex |
| H2 | 模型发明了从未出现的哈希 | 若成立，unknown token 不应能对齐到已收集哈希 | E-001、E-002、E-003 | REJECTED | — | 四枚都落在真实哈希的编辑距离 / 拼接上 |
| H3 | 交付 0 仍是 R-21 的 gap_zeroed（hashes+gap 被 verifier 丢掉） | 若成立，B1/B7 finish 应 `caveat_slips>0` 或 bindings 带哈希+gap | E-001、E-002、E-004 | REJECTED | — | 两题 slips=0、bindings=0；C1 的 9 题滑档已交付 |
| H4 | 对 unknown 哈希做模糊自动纠正是安全的 | 若成立，每条 unknown 应唯一近配一条真哈希 | E-001、E-003 | REJECTED | — | B1 拼接 `8b9fcfe85a338d58f` 同时近配两条真哈希；歧义必须拒 |

## Causal findings

### PRIMARY

- failure_span_id: `run_20260815_034008_215204/continuous-episode.json:events[sequence=20]`
- root_location: 终局契约 + 模型可见观察强制誊抄 16-hex `content_hash`（`validate_episode_finish` / tool observation）
- excerpt: binding contains unknown evidence hash: 3b0895e3a338d58f,8b9fcfe85a338d58f
- l0: HARNESS
- l1: configure
- l2: task-instruction-category-non-compliance
- l3: n/a
- causality: PRIMARY_FAILURE
- propagation_impact: [TASK_TERMINATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-001, E-003, E-007]
- explanation: 装配层要求模型抄高熵哈希。修复轮已有真实证据，誊抄出错后 fail-closed 拒收，bindings 被清空，eb=0。抄错是随机的，解释「失败集跨窗口换人」。

### SECONDARY / TERTIARY

数据层第一环见 Findings `F-002`：B1「结构化数据源暂不可用」、B7「结构化市场数据仅更新到 2026-08-13」。它把主路径送进 `deadline_exhausted`，但不解释修复轮为何零绑定。不在本缝，不修。

## Evidence → Finding → Path

### Evidence

### E-001
- title: B1 修复轮 unknown-hash 拒收，两枚标本均为真哈希誊抄错
- run_id: run_20260815_034008_215204
- step_or_span_id: run_20260815_034008_215204/continuous-episode.json:events[sequence=20]
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260815_034008_215204/continuous-episode.json` `invalid_action` seq 20；证据集 19 条
- observed_at: 2026-08-15T03:40:08+08:00
- raw_excerpt: |
    stop=invalid_repair_finish bindings=0 eb=0
    reason=binding contains unknown evidence hash: 3b0895e3a338d58f,8b9fcfe85a338d58f
    3b0895e3a338d58f = 3b0893e5a338d58f with 93e5→95e3
    8b9fcfe85a338d58f = 8b9fcfe85c43d0d0[:9] + 3b0893e5a338d58f[-8:]
- observation: 19 条证据哈希均为 16 hex。两枚 unknown 分别是换位与跨两条真哈希的拼接。主路径 finish seq 16 为 `deadline_exhausted`。
- confidence: high

### E-002
- title: B7 修复轮 unknown-hash 拒收，插入与删除各一
- run_id: run_20260815_034828_738989
- step_or_span_id: run_20260815_034828_738989/continuous-episode.json:events[sequence=17]
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260815_034828_738989/continuous-episode.json` `invalid_action` seq 17；证据集 29 条
- observed_at: 2026-08-15T03:48:28+08:00
- raw_excerpt: |
    stop=invalid_repair_finish bindings=0 eb=0
    reason=binding contains unknown evidence hash: 20eea1861410bd4d5,e82eaa545eafa11
    20eea1861410bd4d5 = 20eea1861410bd4d + "5"
    e82eaa545eafa11 = e82eaa545eafa11a minus last char
- observation: 29 条证据哈希均为 16 hex。17 字符为插入，15 字符为唯一 1 位截断。主路径 finish seq 13 为 `deadline_exhausted`。
- confidence: high

### E-003
- title: 四枚标本都落在真实证据上，拼接有歧义
- run_id: run_20260815_034008_215204
- step_or_span_id: run_20260815_034008_215204/continuous-episode.json:outcome.evidence
- native_or_normalized: native
- source_type: file
- source_ref: B1/B7 `outcome.evidence[].content_hash` 与 `invalid_action.reason` 逐字符比对
- observed_at: 2026-08-15
- raw_excerpt: |
    concat 8b9fcfe85a338d58f near-matches 8b9fcfe85c43d0d0 and 3b0893e5a338d58f
    both real hashes present in the same evidence set
- observation: 模糊纠正会在拼接标本上选错行。删除标本单独看是既有 `truncated_hash` 形状。
- confidence: high

### E-004
- title: R-21 canary 按预注册原文通过
- run_id: 20260814T1926Z-r3-clean-baseline
- step_or_span_id: 20260814T1926Z-r3-clean-baseline/cases[*]/continuous-episode.finish
- native_or_normalized: native
- source_type: file
- source_ref: `/Users/a77/fwp-wt-b-r3/intelligence/eval/runs/20260814T1926Z-r3-clean-baseline.json` sha256=`b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`；`docs/verification/2026-08-15-trka-r3-r21-canary.md` §Post-batch closure
- observed_at: 2026-08-15T04:02:12+08:00
- raw_excerpt: |
    C1: 9 slips>0 cases, hashed slots fulfilled, eb>0
    C2: 6 true-gap slots missing (A4/C6/C9/C10-t3)
    C9 mixed: slips=1 and chain_mapping missing on the same turn
- observation: 轨道 A 独立重扫与检阅方 Round 3 批注一致。C3 不适用。
- confidence: high

### E-005
- title: 条件靶收窄谓词零命中
- run_id: 20260814T1926Z-r3-clean-baseline
- step_or_span_id: 20260814T1926Z-r3-clean-baseline/events[finish]
- native_or_normalized: native
- source_type: file
- source_ref: 同批 21 个有 episode 的 run 目录；41 个 finish 事件
- observed_at: 2026-08-15
- raw_excerpt: |
    wide carried_draft_chars=0 on finish: 21/41
    narrow (draft_chars>0 then later carried_draft_chars=0): 0
- observation: 字面谓词过宽。收窄后无真丢稿。B1/B7 从未产生 `draft_chars>0`。
- confidence: high

### E-006
- title: 验收摘要无拒收句，事件流有完整 reason
- run_id: run_20260815_034008_215204
- step_or_span_id: run_20260815_034008_215204/continuous-episode.json:events[sequence=20]
- native_or_normalized: native
- source_type: trace
- source_ref: 验收 JSON `cases[B1].turns[0]` 无 rejection 字段；episode `invalid_action.reason` 有完整句
- observed_at: 2026-08-15
- raw_excerpt: |
    acceptance: evidence_bound=0 execution_state=retrieved_unsynthesized
    episode invalid_action.reason = binding contains unknown evidence hash: …
    finish.payload.rejection_code absent on this revision
- observation: 「拒收判据不在产物内」对验收 JSON 为真，对 run 目录事件流为假。
- confidence: high

### E-007
- title: 装配层把 16-hex 哈希暴露给模型并要求抄进 binding
- run_id: n/a
- step_or_span_id: intelligence/services/episode_protocol.py:build_episode_instructions
- native_or_normalized: native
- source_type: code_reading
- source_ref: 修复前 `build_episode_instructions` / `finish_json_schema` / 模型可见 `tool` 观察含 `content_hash`；本 PR 改为 E1..En 并 `strip_hashes_for_model`
- observed_at: 2026-08-15
- raw_excerpt: |
    field name remains evidence_hashes; values were 16-hex content_hash
    model-facing tool observation included content_hash and evidence_hashes
- observation: 模型在修复轮只能从观察里抄哈希。高熵 16 hex 的插入/删除/换位/拼接与标本同形。
- confidence: medium

### self_report_vs_observed

| 对账对象 | 机器/原始观测 | 人类可读或后处理字段 | 采用口径 |
|---|---|---|---|
| 拒收判据在不在产物里 | episode `invalid_action.reason` 完整 | 「验收产物内没有拒收判据」 | 事件流为准；验收 JSON 是摘要 |
| B1/B7 是否引用了证据 | 19/29 条 `content_hash` 入账；unknown 与真哈希编辑距离 1–2 或拼接 | 「没有绑定所以没证据」 | 有证据、绑定被拒 |
| 条件靶丢稿 | 收窄谓词 0 命中 | 字面 `carried_draft_chars=0` 21/41 finish | 收窄谓词；不开 M1 |

### Findings

### F-001
- title: 终局契约逼模型誊抄 16-hex 哈希
- status: validated
- failure_span_id: run_20260815_034008_215204/continuous-episode.json:events[sequence=20]
- root_location: finish 契约与模型可见观察
- l0: HARNESS
- l1: configure
- l2: task-instruction-category-non-compliance
- l3: n/a
- violated_authority: tool_contract
- causality: PRIMARY_FAILURE
- propagation_impact: [TASK_TERMINATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-001, E-002, E-003, E-007]
- confidence: high
- explanation: 正确状态是「修复轮已有可绑定证据」。错误变换是契约要求抄哈希。抄错后 fail-closed → 零绑定 → eb=0。

### F-002
- title: 数据层第一环把主路径送进 deadline_exhausted
- status: validated
- failure_span_id: run_20260815_034008_215204/continuous-episode.json:events[sequence=16]
- root_location: 结构化数据源可用性 / 新鲜度（不在本缝）
- l0: HARNESS
- l1: retrieve
- l2: execution-error-category-environment
- l3: A2
- violated_authority: none
- causality: SECONDARY_FAILURE
- propagation_impact: [INCORRECT_PATH]
- failure_detection_timing: SEVERAL_STEPS_LATER
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002]
- confidence: high
- explanation: B1 gap「结构化数据源暂不可用」、B7 gap「数据仅更新到 2026-08-13」。主路径因此 `deadline_exhausted`。修复轮仍拿到证据；零绑定由 F-001 造成。本轨道不修此环。

### Path

### P-001
- title: 真证据 → 抄错哈希 → fail-closed 零绑定
- start: 修复轮开始时 B1 已有 19 条、B7 已有 29 条 16-hex 证据
- goal: invalid_repair_finish 且 evidence_bound=0
- steps:
  1. 主路径因数据源/新鲜度 `deadline_exhausted` — evidence: E-001、E-002 — finding: F-002
  2. 修复轮观察仍带完整 `content_hash`，契约要求抄进 binding — evidence: E-007 — finding: F-001
  3. 模型写出换位/拼接/插入/删除 — evidence: E-001、E-002、E-003 — finding: F-001
  4. validate fail-closed，bindings=0，eb=0 — evidence: E-001、E-002 — finding: F-001
- residual_uncertainty: R-23 尚未部署，下一批同形 unknown-hash 拒收是否消失未知；数据层第一环仍在。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-023 | F-001 | DATA_CONTRACT_FIX | FINAL_JSON 用 E1..En；harness 解析回哈希；模型上下文去掉 `content_hash`。歧义/越界仍拒，不做模糊纠正。finish 提升 `rejection_code`/`rejection_reason` | 部署后同形 case 绑定且 eb>0；下一批再出现 unknown-hash 誊抄拒收即 refuted | 四枚标本夹具 + E99 + 修复轮 E1 成功路径 |
| R-021-close | F-001 的前序 | NO_SYSTEM_FIX | 按预注册原文收口 R-21；条件靶收窄后零命中不开 M1 | 已兑现（E-004、E-005） | 预注册原文不得改写 |

### R-023
- targets_finding: F-001
- fix_type: DATA_CONTRACT_FIX
- recommendation: 证据序号契约 + 模型上下文剥哈希 + slim R-09（reason 进 finish）。不改 verifier。不部署 8792。
- verification_prediction: 见账本 `R-20260815-23`。
- regression_guard: `test_hash_transcription_specimens_stay_rejected` 钉住四枚标本仍拒；`test_repair_finish_accepts_evidence_ordinal` 钉住 E1 成功。
- auto_apply: false

### R-021-close
- targets_finding: F-001
- fix_type: NO_SYSTEM_FIX
- recommendation: 只回填账本与 canary §Post-batch closure。
- verification_prediction: 已按 C1/C2 兑现。
- regression_guard: 预注册原文保持不变。
- auto_apply: false

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| R-23 未部署 | 同形 case 部署后是否仍 unknown-hash 拒收 | 下一批 `invalid_action.reason` 含 `unknown evidence hash` 的同形 case 数；阈值 =0 为兑现，≥1 为 refuted | 8792 部署后的干净批 + `finish.payload.rejection_code` | R-23 confirmed / refuted | 本轮零（只实现不部署） |
| 数据层第一环 | B1 源不可用 / B7 新鲜度是否仍把主路径打进 deadline | 同题主路径 `stop_reason=deadline_exhausted` 且 gap 含「数据源暂不可用」或「仅更新到」的次数 | 用户排期的数据层修复后的批 | 第一环是否还在；不改变 R-23 口径 | 不在本缝 |

## Limits and counterevidence

- 本轨道不跑 live、不持 live-lock、不上 8792。R-23 保持 pending。
- 不碰 `intelligence/eval/`、verifier 判据、A4 `forged_hash` 前缀匹配（只改截断回灌文案改指 E1/E2）。
- 不做模糊自动纠正。B1 拼接标本是反证。
- 不修 B1 数据源 / B7 新鲜度，不回填 B 的 R-09/R-08/R-10。
- C10-t3 为 `bound_but_dropped`（两格 no_hash 真缺口）。tally 若按首 turn 记 delivered，是 B 的聚合口径，不移动 C1/C2。
- 精确哈希仍接受（旧夹具 / 偶发抄对）。`E1` 永不按哈希解释。

## Next-step menu

1. 合并队列：B 勘误 rebase → B 批 PR → #20 → 本 PR。本 PR 先以 `f43f2507` 为底，后到者 rebase 保留双方账本行。
2. 用户裁决是否把 R-23 部署到 8792；本轮不切生产。
3. 部署后下一批按 `R-20260815-23` 读 `rejection_code` / unknown-hash 计数。
4. 数据层第一环另立项，不并进本缝。
5. B 按 slim R-09 口径回填自己的 R-09 行。
6. 不重开 A4 前缀匹配、#296/#297 窗口、丢稿 M1。

## Round 4 小结

- R-21 canary 按预注册原文 confirmed（批 `sha256=b712bd2e…`，9 题 slips 全交付，6 个真缺口格仍 missing，C9 混合形成立）。
- 条件靶谓词过宽已修正；收窄后 0 命中，不开 M1。
- B1/B7 根因是修复轮誊抄 16-hex 哈希（换位/拼接/插入/删除）；fail-closed 正确，落成零绑定。
- 修法：绑定改 E1..En，harness 解析回哈希；模型上下文剥哈希；歧义仍拒。
- slim R-09：`rejection_code`/`rejection_reason` 进 finish（无拒收为 `none` / 空串）。不回填 B 的 R-09。
- 新开 `R-20260815-23` pending；只实现不部署。

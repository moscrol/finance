# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_NOT_CONFIRMED
- mode: M1
- failure_criterion: 长尾 off 臂 45 槽（对齐键 `slot`+`run_id`，清污后自 `run_20260816_131941_597875`）里，凡 `draft_len>0` 且 structural 允许放行的 episode，judge 须落到 `passed`/`repaired`/`rejected`。实际 22/26 为 `judge_status=unavailable` 且 `issues` 含 `semantic judge transient provider error`、`correlated_judge=true`。护栏 G01–G05（theme-research 5/5 degraded）同形并入，**无 off 基准**。原题 L01 空稿合成超时仍单独记账，不与本条合并。
- trace_coverage: 45 个 off 槽 smoke + 对应 `continuous-episode.json`/`report.json`；G01–G05 五份 on 臂 episode。对照：原 M1 主样本 L01 r1。8795 identity 已收齐：L01×3 + L03×1（user `outlook-r03-0816`，rev `21dbf6c1`）。**缺**：judge `timeout_asked` / 原始异常类（#84 只埋合成/修复）；G01–G05 无 off 臂；3-tool / #72-off 单变量未跑。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Prior prediction closure

本被审系统已有标准分诊账本。下列 pending 用本次 45 槽 + G01–G05 回填；未触及的保持 `still_pending`。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 2026-08-16 outlook 预算回归 M1 F-001 | R-20260816-01 | 下一次空 draft 超时 run 的首轮 finalize `model_turn` payload 含 `timeout_asked`… | still_pending | E-010, E-011 | 8795 四槽合成/修复 `timeout_asked` 均在。预测要的「空稿 **finalize** 超时」未再现（L01 r2 空稿超时在非 finalize、asked=8.49）。字段存在 ≠ 该形状结案 |
| 同上 F-002 | R-20260816-02 | 若动预算：同题重放要么首轮合成成功，要么 repair 的 `timeout_asked` 不再小于…须附 2026-08-08 式延迟实测 | still_pending | E-001, E-006 | 本轮**书面豁免**调 T / 30s 帽，预测未兑现也未证伪 |
| 同上 F-001 | R-20260816-03 | 同题三臂能单独证实或证伪「#72 提示变重」与「stock_high_daily 扩容」 | still_pending | E-002, E-003, E-004 | 45 槽能否证「充分条件」，不能替代单变量三臂。H2/H3 作窗口充分条件已 REJECTED，L01 r1 必要性仍要 asked/token |
| 同上 E-012 | R-20260816-05 | 观测台/收据把 L01 空稿 `(repair_model_unavailable, draft_len=0)` 与 L05 候选草稿 `(repair_model_stop, draft_len>0, judge transient)` 分成两行 | confirmed | E-001, E-005 | 三元组已分型；禁止再用 151–159s 合并 |
| 2026-08-15 B 组 F-001 | R-20260815-04 | `draft_source` 与合成入口 `remaining_ms` | still_pending | 无 | 字段仍未落地 |
| L7 T3 | R-20260804-10 | deadline-aligned per-tool handoff… | still_pending | 无 | 本窗是 workbench continuous，未触及 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `HARNESS_FIX` = 0；`EVAL_ONLY` = 0（沿用账本归零后状态）。本轮无新 refuted。

## Executive finding

窗内主症不是 L01 空稿合成超时。36 个有 episode 的 off 槽里，10 个是空稿跳过 judge（`correlated_judge=false`），22 个是**写出草稿后 judge 已调用**仍 `unavailable`（`correlated_judge=true`，文案 `semantic judge transient provider error`）。G01–G05 五槽同形。零槽出现 `semantic judge deadline exhausted`。第一处可观察错误变换在成功合成之后的 judge `complete()`；不能在「standard 档首轮 grant≈10.4s 饿死」与「provider 真故障」之间定 L0——#84 未给 judge 埋 `timeout_asked`（identity 两份 transient 仍无该字段）。#72 与第 4 次查询**不是**窗口级空稿的充分条件。原 68s 空稿 finalize 形在 identity 0/3，属偶发；非 finalize 轮 `asked=remaining−60`（GLM 平衡 reserve）是空稿子集的另一机制，不升格为本窗 PRIMARY。

## Expected vs actual path

本地词表 ↔ L1 九步按 `docs/trace-profile.md` §6。损耗：`verification` / judge 调用在多数 773b3d7e episode 里没有独立 `kind=judge` 事件，只能从 `semantic_verifier` + `correlated_judge` 读，不得把缺失事件就近塞进 `observe`。

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | standard 90/20；judge 窗由 reserve 导出 | `research_tier=standard`（含 G01–G05）；导出 judge 窗 20.83s、首轮约 10.4s | ok（装配存在） | E-007 |
| intent | 观点/研究题进 continuous | 36/45 有 episode；L04/L12/L15 共 9 槽 chat、无 episode | ok / 分叉 | E-001 |
| retrieve | 取到可核验盘面 | 空稿 10 槽工具次数 0–4 不等；有稿槽多数 2–4 次成功 | ok | E-002 |
| synthesize | 非空 draft | 26 槽 draft>0；10 槽 draft=0 | fail（少数） | E-002, E-004 |
| tool（judge） | draft>0 时 judge 跑完 | 22 槽已调用后 transient；3 槽 passed/repaired | **fail** | E-005, E-006, E-008 |
| stop | 核验完成或诚实降级且判断句存活 | 候选草稿包装 / 缺口模板；`report.status=partial` | fail（交付） | E-005, E-008 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260816_145306_491085` / `semantic_verifier` | UNCLEAR（HARNESS/configure vs HARNESS/tool） | tool | DEPTH_INSUFFICIENT(D4) | `"judge_status":"unavailable"`, `"correlated_judge":true`, issues 含 `semantic judge transient provider error` | medium |
| `run_20260816_131941_597875` / episode seq=12 `model_turn` | UNCLEAR | synthesize | DEPTH_INSUFFICIENT(D4) | 空稿 TimeoutError；窗内少数形状，不升格为本报告 PRIMARY | medium |
| `run_20260816_161730_409393` / seq=5 `model_turn` | HARNESS | configure | execution-error-category-timeout | 非 finalize asked=8.49 = remaining−60；空稿。identity 子集，非窗口 PRIMARY | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H2 | #72 把判断槽改成 `model_reasoning` 后合成提示变重，同一 grant 不够（窗口充分条件） | 若成立，#72 已装上的 off 臂应稳定空稿 | E-001, E-002, E-003 | REJECTED | — | 26/36 episode draft>0；#72 合同在有稿槽同样在场（如 L03 r3 `direct_answer.grounding_mode=model_reasoning`） |
| H3 | 多出来的 `stock_high_daily` / 第 4 次查询是空稿充分条件 | 若成立，4-tool 应空稿、少工具应有稿 | E-002, E-004 | REJECTED | — | 多个 4-tool 槽 `model_finish`/`repair_model_finish` 且 draft>0；L01 r2 仅 2-tool 仍空稿（路径不同，不能当干净 3-tool 合成对照，但已否证「4-tool⇒空稿」） |
| H6 | L01 空稿只是 provider 偶发变慢（68s finalize 形） | 同题 ≥3 次 ready 绿；该形 compose TimeoutError <2/3 | E-004, E-011 | CONFIRMED | — | identity L01×3：0/3 再现 68s 空稿 finalize。r1 finalize asked=59.84 写出稿且 judge repaired；r2/r3 的 TimeoutError 是 asked=8.49/11.99 的非 finalize 轮（H10） |
| H7 | 有稿槽 judge unavailable 是核验预算饿死（grant≈0 未调用） | 若成立，issues 应为 `semantic judge deadline exhausted` 或 `correlated_judge=false` | E-005, E-006, E-008 | REJECTED | — | 22 off + 5 guard 均为 `correlated_judge=true` 且 transient 文案；**零** `deadline exhausted` |
| H8 | 有稿槽是 provider 真故障（5xx/断连），与 grant 无关 | 若成立，judge `timeout_asked` 应 ≥20s 仍失败，或原始异常为 5xx/连接类 | E-006, E-007, E-009 | INCONCLUSIVE | 下一份 draft>0 transient 的 judge `timeout_asked` 与原始 `type(exc)`；asked≥20 且 5xx/连接 → 维持 H8；asked≤12 且墙钟≈asked → 证伪 H8、改 H9 | 映射函数把 TimeoutError **和** 5xx/连接都收成同一句 |
| H9 | standard 档 judge 首轮 grant≈10.4s 小于中转 P50，TimeoutError 被标成 transient | 若成立，asked≤12 且墙钟贴 asked | E-007, E-009, E-011 | INCONCLUSIVE | 同 H8：须 judge `timeout_asked`。identity 两份 transient（L01 r3 / L03）仍无该字段 | 08-08 terra 17K prompt P50=9–15s。#84 未埋 judge |
| H10 | 非 finalize 轮 `asked=remaining−_BALANCED_SYNTHESIS_RESERVE(60)`，把检索后合成饿到 8–20s | 若成立，非 finalize `timeout_asked` 应等于 `remaining_seconds_at_entry−60`（±0.1） | E-011, E-012 | CONFIRMED | — | L01 r1 seq5 74.74→14.74；L01 r2 seq5 68.49→8.49 TimeoutError；L01 r3 seq11 71.99→11.99 TimeoutError；L03 seq11 80.13→20.13 TimeoutError。代码：`glm_agent_runtime.py:47` + `stage_timeout` |

## Causal findings

### PRIMARY

- failure_span_id: `run_20260816_145306_491085` / `semantic_verifier`（normalized；无独立 `kind=judge` 事件）
- root_location: 成功 `model_finish` 之后的 semantic judge `complete()`
- excerpt: `"stop_reason":"model_finish","judge_status":"unavailable","correlated_judge":true,"issues":["semantic judge transient provider error"]`；draft 356 字；墙钟 55.7s
- l0: UNCLEAR
- l1: tool
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-005, E-006, E-007]
- explanation: 检索与合成已产出非空 draft，状态在进 judge 前仍正确。下一跳 judge 被调用后失败，公开答案改走「候选草稿」包装。这是窗口主形状（22/26 有稿槽）的第一处错误变换。失败被映射为 transient，无法在「grant 太短」与「provider 故障」之间定 L0/L2。

### SECONDARY / TERTIARY

none。空稿 10 槽（F-002）与护栏 5 槽（F-003）是并列形状/旁证，不是本 PRIMARY 的传播——空稿发生在 judge 之前，护栏无 off 基准。

## Evidence → Finding → Path

### Evidence

### E-001
- title: off 45 槽三元组分布
- run_id: longtail-ab-20260816 / off ×45
- step_or_span_id: score.json `slots[]` + episode `finish`/`outcome.draft`/`semantic_verifier`
- native_or_normalized: normalized
- source_type: file
- source_ref: `/Users/a77/.finance-runtime/longtail-ab-20260816/score.json`；对齐键 `slot`+`run_id`（收据 §0.4）
- observed_at: 2026-08-16T07:38:26+00:00 scored；2026-08-16 分型重读
- raw_excerpt: |
    `(no_episode, na, not_applicable)=9`；`(repair_model_stop, >0, unavailable)=8`；`(repair_model_finish, >0, unavailable)=8`；`(repair_model_unavailable, 0, unavailable)=7`；`(model_finish, >0, unavailable)=7`；`(invalid_repair_finish, 0, unavailable)=3`；judge 实际跑完 3（repaired×2, passed×1）
- observation: 9 个无 episode 全是 L04/L12/L15。有 episode 的主质量问题是有稿 + judge unavailable，不是空稿。
- confidence: high

### E-002
- title: 有稿槽多数 2–4 次工具且含 4-tool 成功合成
- run_id: 多个 off 槽
- step_or_span_id: episode `tool_request`/`tool_result` + `outcome.draft`
- native_or_normalized: native
- source_type: tool_return
- source_ref: 例 `run_20260816_145306_491085`（L03 r3）4 tool + draft 356；`run_20260816_142101_432178`（L07 r2）4 tool + draft 470
- observed_at: 2026-08-16
- raw_excerpt: |
    L03 r3: `stop=model_finish` tools=4 draft=356 elapsed=55.7s；L07 r2: `stop=model_finish` tools=4 draft=470 elapsed=52.2s
- observation: 四次查询与非空 draft 可以同时成立。
- confidence: high

### E-003
- title: #72 判断槽在有稿成功合成上同样生效
- run_id: run_20260816_145306_491085
- step_or_span_id: `contract.required_outputs[0].grounding_mode`
- native_or_normalized: native
- source_type: file
- source_ref: `continuous-episode.json` contract
- observed_at: 2026-08-16T14:53:06+08:00
- raw_excerpt: |
    `direct_answer.grounding_mode=model_reasoning`；`evidence_boundary.grounding_mode=evidence`；`research_tier=standard`
- observation: #72 装配与「写出 draft」不互斥。
- confidence: high

### E-004
- title: L01 三重复不是同一条空稿路径
- run_id: run_20260816_131941_597875 / 141323_891938 / 145303_909828
- step_or_span_id: 各 episode `finish` + 首轮 `model_turn`
- native_or_normalized: native
- source_type: trace
- source_ref: 三份 `continuous-episode.json`
- observed_at: 2026-08-16
- raw_excerpt: |
    r1: tools=4 含 `stock_high_daily`，compose `TimeoutError`，`repair_model_unavailable`，draft=0，153.9s；r2: tools=2 无 `stock_high_daily`，`invalid_repair_finish`，draft=0，94.7s；r3: tools=0，2.2s，draft=0
- observation: 同题三次不是稳定的「4-tool + 首轮合成超时」。
- confidence: high

### E-005
- title: 有稿槽 judge 已调用后标 transient
- run_id: run_20260816_145306_491085
- step_or_span_id: `semantic_verifier`
- native_or_normalized: native
- source_type: file
- source_ref: `.../run_20260816_145306_491085/continuous-episode.json` semantic_verifier
- observed_at: 2026-08-16T14:54:02+08:00
- raw_excerpt: |
    `judge_status=unavailable; correlated_judge=true; issues=["semantic judge transient provider error"]; public_answer` 以「结构化证据绑定已通过边界校验，但语义核验因瞬时服务问题未完成」起头
- observation: 这不是空稿跳过。`usage.llm_calls=2`（规划+合成）；judge 失败未另增独立 kind。
- confidence: high

### E-006
- title: 22+5 槽同映射，零 deadline exhausted
- run_id: off 45 + on G01–G05
- step_or_span_id: 各 `semantic_verifier.issues` / `correlated_judge`
- native_or_normalized: normalized
- source_type: file
- source_ref: 50 份 episode；分类脚本按 issues 与 correlated_judge
- observed_at: 2026-08-16
- raw_excerpt: |
    off: `judge_attempted_transient=22`, `judge_skipped_empty_draft=10`, `no_episode=9`, judge 完成=3；G01–G05: 5/5 `judge_attempted_transient`，draft 349–567
- observation: 有稿失败路径是「调用了再 transient」，不是「时钟耗尽未调用」。
- confidence: high

### E-007
- title: standard 档导出的 judge 首轮窗
- run_id: n/a（代码 + 合同）
- step_or_span_id: `derive_stage_caps` / `semantic_judge_window_seconds`
- native_or_normalized: native
- source_type: code_reading
- source_ref: `intelligence/services/research_contract.py:411-428`；`episode_semantic_verifier.py:83-93,3024-3037`；L03 r3 / G01 contract `research_tier=standard`
- observed_at: 2026-08-16
- raw_excerpt: |
    standard `total=90, synthesis_reserve=20`；`judge_window=reserve*(50/48)≈20.83s`；首轮 `window*0.5≈10.4s`。G01 与 L03 均为 `research_tier=standard`
- observation: 有稿槽与护栏都走 standard，不是 deep。此条为代码算术，confidence 封顶 medium。
- confidence: medium

### E-008
- title: G01–G05 与有稿 off 槽同形，无 off 基准
- run_id: run_20260816_152745_016660 … 153434_648208
- step_or_span_id: 各 `semantic_verifier` + score `guards.routing`
- native_or_normalized: native
- source_type: file
- source_ref: score.json `summary.guards`；五份 episode
- observed_at: 2026-08-16T15:27–15:38+08:00
- raw_excerpt: |
    5/5 `question_type=theme_analysis`, `answer_owner=theme-research`, `confidence=0.98`, `terminal_outcome=degraded`, `judge_status=unavailable`, `correlated_judge=true`, issues 含 transient；墙钟 86.0/96.9/134.3/92.2/202.8s
- observation: 护栏标题未出现。不能用这五槽证明长尾开关注入导致 judge 失败。
- confidence: high

### E-009
- title: transient 文案同时覆盖 TimeoutError 与 5xx/连接
- run_id: n/a
- step_or_span_id: `_stable_semantic_judge_error`
- native_or_normalized: native
- source_type: code_reading
- source_ref: `episode_semantic_verifier.py:2981-3020`
- observed_at: 2026-08-16
- raw_excerpt: |
    429/5xx → transient；`timeouterror`/`readtimeout`/`connectionerror` → transient；「timed out」/限流/网络错误 → transient
- observation: 只看 issues 分不出 H8/H9。
- confidence: high

### E-010
- title: 8795 sidecar 已起且不占 8792
- run_id: n/a
- step_or_span_id: `/api/health` ×2
- native_or_normalized: native
- source_type: file
- source_ref: `127.0.0.1:8795/api/health`；`127.0.0.1:8792/api/health`
- observed_at: 2026-08-16T16:13+08:00
- raw_excerpt: |
    8795 `source_revision=21dbf6c1…`, `source_dirty=false`, `code_root=…/finance-workspace-21dbf6c1d83f`, ready 200；8792 仍 `773b3d7e…`, dirty=false
- observation: #84 埋点树在评测端口；生产未切。identity 四槽已在此树上跑完。
- confidence: high

### E-011
- title: 8795 identity 四槽 `timeout_asked`（合成/修复有，judge 无）
- run_id: run_20260816_161511_984975 / 161730_409393 / 161908_009785 / 162020_287790
- step_or_span_id: 各 `model_turn` / `repair_reentry` / `semantic_verifier`
- native_or_normalized: native
- source_type: trace
- source_ref: `~/.local/share/finance-workbench/users/outlook-r03-0816/runs/<run_id>/continuous-episode.json`
- observed_at: 2026-08-16T16:15–16:21+08:00
- raw_excerpt: |
    L01 r1: finalize asked=59.84 in=8318 写出稿；judge=repaired。L01 r2: 非 finalize asked=8.49 TimeoutError，draft=0，judge 未调用。L01 r3: 非 finalize asked=11.99 TimeoutError，repair 后 draft=443，judge transient。L03: 非 finalize asked=20.13 TimeoutError，repair 后 draft=429，judge transient。四份 semantic_verifier 均无 judge `timeout_asked`
- observation: #84 合成埋点可用。原 68s 空稿 finalize 0/3。两份有稿 transient 仍不能分 H8/H9。
- confidence: high

### E-012
- title: 非 finalize `asked = remaining − 60` 对得上 GLM 平衡 reserve
- run_id: n/a（代码）+ E-011 四槽
- step_or_span_id: `stage_timeout` / `synthesis_reserve_for_task`
- native_or_normalized: native
- source_type: code_reading
- source_ref: `glm_agent_runtime.py:36-47,439-452`；`research_contract.py:357-359`；`agent_episode.py:680-714,1789-1794`
- observed_at: 2026-08-16
- raw_excerpt: |
    `_BALANCED_SYNTHESIS_RESERVE=60`；`general_finance_qa` 不在 heavy 集合，reserve=min(75,60)=60。`stage_timeout=remaining−reserve`。首轮 opening 向 reserve 借到 floor=20，故 plan asked≈70。非 finalize 不再借。finalize 用 `synthesis_timeout=remaining`（含 reserve）
- observation: 调 T 不改 `effective_timeout=min(90, T−40)`。饿死杠杆是 60s reserve，不是 300s 回合帽。
- confidence: high

### Findings

### F-001
- title: 窗口 PRIMARY 是有稿后 judge transient，不是空稿合成超时
- status: validated
- failure_span_id: `run_20260816_145306_491085` / `semantic_verifier`
- root_location: judge `complete()` after `model_finish`
- l0: UNCLEAR
- l1: tool
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- violated_authority: tool_contract
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-005, E-006]
- confidence: medium
- explanation: WHAT：draft 已在，judge 调用后 unavailable。WHY：22/26 有稿槽 + 5/5 护栏同构。IMPACT：公开答案变候选草稿包装，剥句率分母仍为 0。子因 H8/H9 未分胜负。

### F-002
- title: 空稿跳过 judge 是少数第二形状
- status: validated
- failure_span_id: `run_20260816_131941_597875` / seq=12
- root_location: 首轮合成 TimeoutError
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- violated_authority: none
- causality: UNCLEAR
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-004]
- confidence: medium
- explanation: 10/36 episode 空稿且 judge 未调用。与 F-001 并列，不是其传播。L01 三重复不同形。H2/H3 作充分条件已否。

### F-003
- title: 护栏 5/5 是旁证，不是长尾开关因果
- status: validated
- failure_span_id: `on:G01:r1` … `on:G05:r1`
- root_location: theme-research 车道 judge
- l0: UNCLEAR
- l1: tool
- l2: DEPTH_INSUFFICIENT(D4)
- l3: n/a
- violated_authority: none
- causality: UNCLEAR
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-008]
- confidence: high
- explanation: 与 F-001 同形旁证。无 off 基准，不能把 on 臂当处理效应。

### F-004
- title: 非 finalize 轮被 60s reserve 扣到 8–20s（空稿子集机制，非窗口主症）
- status: validated
- failure_span_id: `run_20260816_161730_409393` / seq=5
- root_location: 非 finalize `stage_timeout`（remaining−60）
- l0: HARNESS
- l1: configure
- l2: execution-error-category-timeout
- l3: n/a
- violated_authority: none
- causality: UNCLEAR
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-011, E-012]
- confidence: high
- explanation: WHAT：plan 之后的检索/合成轮 asked 只剩 remaining−60。WHY：GLM 平衡 reserve=60，opening 才借款。IMPACT：identity L01 r2 空稿；r3/L03 首轮合成 TimeoutError 后靠 30s repair 写出稿。不是 22 槽 judge transient 的原因，也不靠调 T 修复。

### Path

### P-001
- title: 合成成功 → judge 调用 → transient 包装出厂
- start: L03 r3 seq=13 `model_finish`，draft 356，bindings 有 hashes
- goal: judge passed/repaired/rejected 且判断正文作为核验结论出厂
- steps:
  1. 四次检索 + 合成写出 draft — evidence: E-002, E-003 — finding: none
  2. judge 被调用后 transient — evidence: E-005, E-006 — finding: F-001
  3. 候选草稿包装；护栏同形 — evidence: E-008 — finding: F-003
- residual_uncertainty: judge `timeout_asked` 与原始异常类未知，H8/H9 未分胜负；G01–G05 无 off 基准。F-004 已钉非 finalize 算术，但不解释窗口 PRIMARY。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260816-07 | F-001 | NO_SYSTEM_FIX | **书面豁免**调大 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` / `_REPAIR_SECONDS_CAP=30` / 生产 T。空稿不是窗口主症；调 T 不修 F-001。原 `R-20260816-02` 保持 pending（「若动预算」条件句未触发）。 | 豁免落盘后不得把 T/30 当本窗修复；10 题闸 2 若翻开须用户确认「compose 预算不改、judge 另案」 | 若仍要动任何预算，必须另附 2026-08-08 延迟实测 + 全路由影响面 |
| R-20260816-06 | F-001 | EVAL_ONLY | 下一份 draft>0 transient 落盘 judge `timeout_asked` + 原始异常类（TimeoutError vs 5xx vs 连接）。#84 不够：identity L01 r3 / L03 已是该形状，字段仍缺 | asked≤12 且墙钟≈asked → H9；asked≥20 且 5xx/连接 → H8 | 只用评测树；不占 8792。须先给 judge `complete()` 补与 #84 对齐的 asked |
| R-20260816-09 | F-004 | HARNESS_FIX | 若动 `_BALANCED_SYNTHESIS_RESERVE` / 非 finalize `stage_timeout`：须 2026-08-08 式延迟实测 + 全路由影响面。本轮**不改** | 改完后非 finalize `asked` 不再系统等于 `remaining−60`；观点题对照不得变慢超 5pp | 禁止只把 T 或 30 调大当 F-004 修复 |
| R-20260816-03 | F-002 | EVAL_ONLY | 同题单变量三臂仍待做；本轮只起 identity 臂（#84 全开）。3-tool / #72-off 需要 eval env hook，不停泊树保持干净 | 三臂收据单独证伪或证实 L01 r1 的必要性命题 | 禁止 L04 chat；as_of=2026-08-14 |
| R-20260816-08 | F-003 | EVAL_ONLY | 若要把护栏 degraded 算进长尾开关账，必须补 G01–G05 off 臂。本轮明确不补、不归因 | 无 off 基准的收据继续写「护栏 heading 缺席 + 路由仍 theme-research」，不写开关因果 | 补跑即重开窗，须用户批 |

- auto_apply: false

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| judge 无 `timeout_asked` | H8 vs H9 | `timeout_asked`；H9 预测 ≤12，观测 ≥20 即证伪 | judge `complete()` 入口，与 #84 合成字段对齐 | grant 饿死 vs provider | 低 |
| transient 文案混装 TimeoutError/5xx | H8 子类 | 原始 `exc_class` 或 HTTP status；一个枚举即可 | 同一 `_JudgeCall.issue` 旁 | 超时 vs 5xx vs 连接 | 低 |
| G01–G05 无 off | 长尾开关是否波及 theme-research | 五题 off 臂各 1 次；degraded 率差 ≥5pp 才谈开关 | 另开窗，不在本 sidecar 偷偷补 | 开关因果 | 中（重开窗） |

## Limits and counterevidence

- 本报告 PRIMARY 是窗口级有稿+judge transient，不推翻原 M1 对 L01 r1 seq=12 的定位；那条仍是空稿子集的第一变换。
- H2/H3 REJECTED 的是**充分条件**。L01 r1 是否「#72 或第 4 次查询使其超时」仍要 #84 asked/token。
- `usage.llm_calls=2` 不能证明 judge 没跑；以 `correlated_judge` 为准。
- 08-08 terra P50 是 17K compose，不是本窗 judge payload；只作 H9 先验。
- 8795 identity 已收齐（E-011）。不把未完成的 3-tool / #72-off 写成已跑。
- 台账决策队列 row 58 是快照卫生（owner=用户），row 59 是 prewarm SOP（已决）。翻闸 2 的「修复或豁免」应新立决策行，不占用 row 59。
- F-004 的 L0=HARNESS 只覆盖空稿子集的非 finalize 轮，不改写 F-001 的 UNCLEAR。

## Next-step menu

1. 用户拍板翻闸 2：接受书面豁免（不调 T/30；F-004 的 60s reserve 另案）或要求先修 judge / reserve。
2. 若修 judge：先给 `complete()` 补 `timeout_asked`+`exc_class`（R-06），再按 08-08 测窗；launcher 已写明抬 judge 窗会饿死草稿。
3. 若修 F-004：动 `_BALANCED_SYNTHESIS_RESERVE` 必须带 08-08 延迟实测 + 全路由影响面（R-09）。调 T 无效。
4. 3-tool / #72-off 三臂另开带 env hook 的评测树，不要改停泊 `21dbf6c1`。
5. 不要把 G01–G05 写成骨架对照；无 off 基准。
6. 10 题窗若按豁免翻闸，修后臂仍会量到 judge transient——收据必须单列，不得算进 #72/#75/#79 的判断句存活。

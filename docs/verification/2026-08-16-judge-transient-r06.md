# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M1
- failure_criterion: 账本 `R-20260816-06` 原文：8795 含 judge 埋点的 tip 上，draft>0 且 `semantic judge transient provider error` 的 run 必须带 `timeout_asked` 与原始异常类；**asked≤12 且墙钟≈asked → H9**；**asked≥20 且 5xx/连接 → H8**；缺字段不得结案。本轮分层重放 12 槽（outlook L03/L05 + residual L07/L13 + owner G01/G03，每槽 2 次）。
- trace_coverage: 12 份 smoke（`~/.finance-runtime/judge-r06-20260816/runs/r06_*.json`）+ `user=judge-r06-0816` 的 `continuous-episode.json`；对齐键 `slot`+`run_id`。8795=`02fa203e` dirty=false；8792 全程 `773b3d7e` 未切。另：judge 形 terra 探针 N=8 timeout=60。**缺**：探针未带全量 `evidence_registry`（p50 是下界）；`timeout_asked` 落的是最后一次 attempt。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: high

## Prior prediction closure

本被审系统已有标准分诊账本。下列 pending 用本次 8795 T1+T2 读数回填；未触及的保持 `still_pending`。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 2026-08-16 有稿 judge 案 F-001 | R-20260816-06 | 下一份 draft>0 且 `semantic judge transient provider error` 的 run，judge 调用带 `timeout_asked` 与原始异常类（TimeoutError / HTTP status / 连接）。asked≤12 且墙钟≈asked → H9；asked≥20 且 5xx/连接 → H8。缺字段不得结案 | confirmed | E-001, E-002, E-003, E-004 | 11/12 槽字段齐；11 槽 asked=5.208≤12、exc=`TimeoutError`、http=None、墙钟贴 asked。0 槽 H8。结 H9 |
| 同上 F-002 | R-20260816-02 | 若动预算：同题重放要么首轮合成成功，要么 repair 的 `timeout_asked` 不再小于…须附 2026-08-08 式延迟实测 | still_pending | E-005 | 本轮未动 T / 30s 帽 / 生产档位。条件句未触发 |
| 同上豁免 | R-20260816-07 | 下一份自称「outlook 预算回归修复」的 PR diff **不含** T / `_REPAIR_SECONDS_CAP` / 生产档位上调 | still_pending | E-005 | 绊线仍有效。本轮处置只动 standard judge 窗地板，不抬 T |
| 护栏 | R-20260816-08 | 若把 G01–G05 degraded 写入长尾开关账，必须先有同题 off 臂 | still_pending | E-001 | G 组只作 H8/H9 旁证，不归因长尾开关 |
| F-004 | R-20260816-09 | 若动 `_BALANCED_SYNTHESIS_RESERVE`：非 finalize `asked` 不再系统等于 `remaining−60` | still_pending | E-002 | 本轮未动 60s reserve。judge remaining 入口 170–254s |
| 空稿 finalize | R-20260816-01 | 空 draft 超时 run 的首轮 finalize `model_turn` 含 `timeout_asked` | still_pending | 无 | 本窗不是空稿 finalize 形 |
| 2026-08-15 B 组 F-001 | R-20260815-04 | `draft_source` 与合成入口 `remaining_ms` | still_pending | 无 | 字段仍未落地 |
| L7 T3 | R-20260804-10 | deadline-aligned per-tool handoff | still_pending | 无 | 本窗是 workbench continuous |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `HARNESS_FIX` = 0；`EVAL_ONLY` = 0。本轮无新 refuted。

## Executive finding

有稿后 judge 已调用，失败不是 provider 5xx/断连，而是 standard 档把共享窗 20.83s 劈成首轮 10.4s、重试 5.2s；落盘 `timeout_asked=5.208`（末次）、`exc_class=TimeoutError`。同模型 judge 形探针 p50=9.29s / p95=10.75s（N=8）：首轮贴 p95，重试低于观测最小 6.77s。剩余回合 170–254s，不是 deadline exhausted。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | judge 首轮 grant 盖过 provider p95 | standard 导出窗 20.83s → 末次 asked=5.208；探针 p95=10.75 | **fail** | E-002, E-004, E-005 |
| synthesize | 非空 draft | 11/12 槽 draft 309–536；L05 r1 结构缺口跳过 judge | ok / 分叉 | E-001 |
| tool（judge） | draft>0 时跑完 passed/repaired/rejected | 11 槽 `correlated_judge=true` + transient + TimeoutError | **fail** | E-001, E-003 |
| stop | 核验结论出厂 | 候选草稿包装 / partial | fail（交付） | E-001 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260816_173648_145174` / `semantic_verifier` | HARNESS | configure | execution-error-category-timeout | `timeout_asked=5.208333333333334` `exc_class=TimeoutError` `remaining_seconds_at_entry=238.91` | high |
| `run_20260816_173848_036298` / structural gap | n/a | synthesize | n/a | L05 r1 主体 unknown，judge 未调用，字段全 None。不进 H8/H9 分母 | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H7 | judge unavailable 是核验预算饿死（grant≈0 未调用） | 若成立，issues 应为 `deadline exhausted` 或 `correlated_judge=false`，或 remaining≈0 | E-001, E-002 | REJECTED | — | 11 槽 correlated=true；remaining 170–254；零 deadline exhausted |
| H8 | 有稿槽是 provider 真故障（5xx/断连），与 grant 无关 | asked≥20 且 5xx/连接 | E-001, E-003 | REJECTED | — | 0 槽 asked≥20；0 槽 http_status；exc 全是 TimeoutError |
| H9 | standard 档 judge 窗太紧，TimeoutError 被标成 transient | asked≤12 且墙钟≈asked | E-001, E-002, E-003, E-004 | CONFIRMED | — | 11/11 有字段的 transient 槽 asked=5.208；末次墙钟贴 5.2；post-finish 12–21s ≈ 10.4+5.2；探针 p95=10.75 > 重试 5.2 |

## Causal findings

### PRIMARY

- failure_span_id: `run_20260816_173648_145174` / `semantic_verifier`（L03 r1；11 槽同形）
- root_location: `_semantic_attempt_timeouts` 把 standard 窗 20.83s 劈成 10.4 / 5.2 / 5.2 之后的 judge `complete()`
- excerpt: `"timeout_asked": 5.208333333333334, "timeout_configured": 30.0, "remaining_seconds_at_entry": 238.91, "exc_class": "TimeoutError", "http_status": null, "judge_status": "unavailable", "correlated_judge": true`
- l0: HARNESS
- l1: configure
- l2: execution-error-category-timeout
- l3: A2
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-003, E-004]
- explanation: WHAT：草稿已在，judge 被调用后 TimeoutError。WHY：末次 asked=5.208≤12 且墙钟贴 asked；剩余 200s+ 未用。IMPACT：公开答案走候选草稿包装。不是 H8。

### SECONDARY / TERTIARY

none。L05 r1 是结构缺口跳过 judge，不是本 PRIMARY 的传播。

## Evidence → Finding → Path

### Evidence

### E-001
- title: 12 槽分层重放三元组表
- run_id: judge-r06-0816 / r06:L03|L05|L07|L13|G01|G03 × r1-r2
- step_or_span_id: 各 `semantic_verifier` + smoke `run_id`
- native_or_normalized: native
- source_type: file
- source_ref: `/Users/a77/.local/share/finance-workbench/users/judge-r06-0816/runs/<run_id>/continuous-episode.json`；对齐 `~/.finance-runtime/judge-r06-20260816/runs/r06_*.json`
- observed_at: 2026-08-16T17:36–17:52+08:00
- raw_excerpt: |
    L03 r1 `run_20260816_173648_145174` repair_model_finish draft=452 asked=5.208 rem=238.9 TimeoutError corr=true wall=67.2
    L03 r2 `run_20260816_173755_435310` model_finish draft=465 asked=5.208 rem=253.8 TimeoutError corr=true wall=52.5
    L05 r1 `run_20260816_173848_036298` model_finish draft=158 asked=None corr=false issues=required output reports gap
    L05 r2 `run_20260816_173913_397352` repair_model_stop draft=358 asked=5.208 rem=216.8 TimeoutError corr=true wall=89.4
    L07 r1 `run_20260816_174042_932505` model_finish draft=456 asked=5.208 rem=254.6 TimeoutError corr=true wall=51.5
    L07 r2 `run_20260816_174134_532783` repair_model_finish draft=433 asked=5.208 rem=221.0 TimeoutError corr=true wall=85.3
    L13 r1 `run_20260816_174259_977785` repair_model_finish draft=309 asked=5.208 rem=239.2 TimeoutError corr=true wall=68.2
    L13 r2 `run_20260816_174408_275965` repair_model_finish draft=347 asked=5.208 rem=236.8 TimeoutError corr=true wall=69.7
    G01 r1 `run_20260816_174518_054653` repair_model_stop draft=391 asked=5.208 rem=215.5 TimeoutError corr=true wall=90.8
    G01 r2 `run_20260816_174648_994487` repair_model_stop draft=368 asked=5.208 rem=209.8 TimeoutError corr=true wall=96.5
    G03 r1 `run_20260816_174825_606450` repair_model_stop draft=383 asked=5.208 rem=221.6 TimeoutError corr=true wall=84.4
    G03 r2 `run_20260816_174950_078185` repair_model_finish draft=536 asked=5.208 rem=170.1 TimeoutError corr=true wall=136.2
- observation: 11 槽同形 H9。1 槽（L05 r1）judge 未调用，字段空，不结 H8/H9。0 槽 H8。0 槽混合。
- confidence: high

### E-002
- title: asked 是末次 attempt=窗/4；入口 remaining 充裕
- run_id: run_20260816_173648_145174
- step_or_span_id: `semantic_verifier.timeout_asked` + `_semantic_attempt_timeouts`
- native_or_normalized: native
- source_type: file
- source_ref: episode `semantic_verifier`；`episode_semantic_verifier.py` `_semantic_attempt_timeouts`（first=window×0.5，retry=(window−first)/2）
- observed_at: 2026-08-16T17:37+08:00
- raw_excerpt: |
    timeout_asked=5.208333333333334
    timeout_configured=30.0
    remaining_seconds_at_entry=238.913
    20*(50/48)=20.833；first=10.417；retry=5.208
- observation: 落盘 asked 等于第三次 grant，不是入口剩余。剩余 238s 未构成饿死。
- confidence: high

### E-003
- title: 自述 transient provider 与机器字段冲突
- run_id: run_20260816_173648_145174
- step_or_span_id: `semantic_verifier.issues` vs `exc_class`
- native_or_normalized: native
- source_type: file
- source_ref: 同上 episode
- observed_at: 2026-08-16T17:37+08:00
- raw_excerpt: |
    issues=["semantic judge transient provider error"]
    exc_class="TimeoutError"
    http_status=null
- observation: self_report_vs_observed：issues 写 provider transient，机器字段是 TimeoutError / http_status=null。按 source precedence 以机器字段为准。
- confidence: high

### E-004
- title: judge 形 terra 延迟 p50/p95
- run_id: n/a（探针）
- step_or_span_id: `llm_refine.complete` ×8 timeout=60
- native_or_normalized: native
- source_type: tool_return
- source_ref: `/Users/a77/.finance-runtime/judge-r06-20260816/judge_latency.json`；prompt=`_NON_EVIDENCE_JUDGE_SYSTEM_PROMPT` + L03 r1 sentences
- observed_at: 2026-08-16T17:53–17:54+08:00
- raw_excerpt: |
    seconds=[10.34, 6.77, 9.64, 8.67, 8.63, 10.75, 8.94, 10.30]
    ok=8/8  p50=9.29  p95=10.75  min=6.77  max=10.75
- observation: 重试 grant 5.208 低于最小成功墙钟。首轮 10.4 落在 p95 上。未带全量 evidence_registry，p50 是下界。
- confidence: high

### E-005
- title: 8795/8792 身份与未动预算
- run_id: n/a
- step_or_span_id: `/api/health` ×2
- native_or_normalized: native
- source_type: file
- source_ref: `127.0.0.1:8795/api/health`；`127.0.0.1:8792/api/health`；sidecar launcher
- observed_at: 2026-08-16T17:36–17:52+08:00
- raw_excerpt: |
    8795 source_revision=02fa203e… source_dirty=false code_root=…/finance-workspace-02fa203e
    8792 source_revision=773b3d7e… source_dirty=false
    launcher 无 ASK_LONGTAIL_BASELINE / ASK_SEMANTIC_JUDGE_WINDOW；T 仍 300
- observation: 评测在 T1 tip 侧车。生产未切。T / 修复帽 / 档位表未改。
- confidence: high

### Findings

### F-001
- title: 窗口 PRIMARY 是 H9（judge 窗太紧），不是 H8
- status: validated
- failure_span_id: `run_20260816_173648_145174` / `semantic_verifier`
- root_location: standard judge 首轮/重试 grant
- l0: HARNESS
- l1: configure
- l2: execution-error-category-timeout
- l3: A2
- violated_authority: tool_contract
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-003, E-004]
- confidence: high
- explanation: WHAT：11 槽 asked=5.208 + TimeoutError。WHY：grant 贴/低于 judge p95。IMPACT：核验降级。混合形状未出现，不换 provider。

### F-002
- title: L05 r1 是结构缺口跳过，不是缺字段漏结案
- status: validated
- failure_span_id: `run_20260816_173848_036298` / structural
- root_location: 主体 unknown，required outputs 报 gap
- l0: REASONING
- l1: synthesize
- l2: incorrect-actions-category-poor-information-retrieval
- l3: n/a
- violated_authority: none
- causality: UNCLEAR
- propagation_impact: [NO_PROPAGATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001]
- confidence: high
- explanation: judge 未调用，三元组为 None 是跳过，不是 T1 埋点失败。L05 r2 同题打到 H9。不进 R-06 分母。

### Path

### P-001
- title: 合成成功 → judge 末次 5.2s TimeoutError → transient 包装
- start: L03 r1 seq=13 附近 draft 已在（repair_model_finish）
- goal: judge passed/repaired/rejected
- steps:
  1. 检索+合成写出 draft — evidence: E-001 — finding: none
  2. judge 三次 grant 10.4/5.2/5.2，末次 TimeoutError — evidence: E-002, E-003, E-004 — finding: F-001
  3. issues 写成 transient provider — evidence: E-003 — finding: F-001
- residual_uncertainty: 探针未带全量 evidence_registry，真实 judge p95 可能高于 10.75；`timeout_asked` 未标 attempt index。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260816-10 | F-001 | HARNESS_FIX | 只把 **standard** 档 `derive_stage_caps.judge_window_seconds` 地板抬到 50s（与 deep / 08-10 arm C 同窗），使首轮 `min(30, window×0.5)=25s`。不改 T、`_REPAIR_SECONDS_CAP`、档位 total/reserve、quick/deep 窗、`_BALANCED_SYNTHESIS_RESERVE`。judge 在草稿之后花剩余回合，不从合成 reserve 扣 | 下一份同形 8795 重放：draft>0 的 judge `timeout_asked` 首轮 ≥20；H9 形 TimeoutError 率相对本表 11/11 下降。缺字段不得结案 | 工具批仍 70、reserve 仍 20；deep 窗仍 50；PR diff 若含 T/30/档位上调且无延迟实测 → R-07 refuted |
| R-20260816-06 | F-001 | EVAL_ONLY | 已兑现：字段在、判据已用 | — | 已从 Open 移到 Closed |
| R-20260816-02 | — | HARNESS_FIX | 不采纳。本轮不调 T/30 | — | 豁免仍在 |

- auto_apply: false

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| `timeout_asked` 只留末次 attempt | 首轮到底是 10.4 还是 5.2 | `judge_attempt_index`（0/1/2）；H9 预测末次=2 且 asked=retry | `_clocked_judge_call` | 确认劈窗算术 | 低 |
| 探针无 evidence_registry | 真实 p95 是否 >10.75 | 处置落地后同 6 题再跑；成功 judge 墙钟 p95 | 8795 侧车 | 25s 首轮是否够 | 中 |

## Limits and counterevidence

- 不是混合 H8/H9，不换 judge provider（08-08 terra 先例留给 H8）。
- L05 r1 不能写成「缺字段不得结案」的反例——judge 没进 `_clocked_judge_call`。
- 「墙钟≈asked」：L03 r1 / G03 r2 等有 `post_first_finish` 12–21s（≈10.4+5.2）。L03 r2 / L07 r1 的 episode 末事件就是首个 `finish`（post=0），这两槽的墙钟只能从 `TimeoutError` 客户端切线推断，不是独立时间戳。H9 不靠这两槽单独成立。
- 探针 JSON 落盘曾因 `LLMProvider` 不能序列化失败；p50/p95 以探针 stdout 八个秒数为准（10.34/6.77/9.64/8.67/8.63/10.75/8.94/10.30）。
- 08-08 compose P50 是 17K 长输出；本探针是短 JSON judge。T4 用 08-10 的 25s 成功带，而不是只比 10.75 多 1s。
- 抬 standard judge 窗不增加 `synthesis_reserve`，不改变 `tool_batch_seconds=70`。quick/deep 不动。
- 8792 未切。闸 2 / `budget_regression_landed` 仍 false，等处置 PR 合 main 且观测台部署。
- 停泊树 `21dbf6c1d83f` 未动。

## Next-step menu

1. 合 T1 `#92`（埋点）与本处置 PR（standard 窗地板 50 + 本收据）。
2. 观测台开部署窗：8792 就地切处置 tip，同窗做 #88 `ln -sfn`；`773b3d7e` 留回滚锚。
3. 眼 agent 翻 `budget_regression_landed=true`，起 8794，开十题窗；收据**单列** judge transient。
4. 不要把调 T / 30s 帽当本窗修复（R-07）。
5. 不要把 G01/G03 写成骨架对照（R-08）。
6. 可选：给 `timeout_asked` 加 `judge_attempt_index`。

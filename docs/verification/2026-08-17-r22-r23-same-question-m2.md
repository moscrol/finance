# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M2
- failure_criterion: 同题 ask 结束后 `outcome.draft` 非空（或公开答案不是缺口模板）。`draft_len=0` 且答案为「模型服务不可用 / 现有证据不足」模板即 fail。
- trace_coverage: 两发 `continuous-episode.json` + `run.json` + `report.json` + `answer.md` + `trace.jsonl`；官方 `normalize_harness_trace --compare`（`runtime-benchmark`）。未读 acceptance 受控目录。
- trace_depth: D3
- completion_status: COMPLETE_FAILURE
- confidence: high

## Prior prediction closure

ledger: `/Users/a77/finance-workspace-private/docs/prediction-ledger.md`（gitea/main `0d18623b`）

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 2026-08-17 #119/#121 | `R-20260816-22` | 同题重跑 `mainline_sector_daily` 不再零证据；答案含退出主线事实 | still_pending | E-003, E-004, E-007 | A 在 `mainline_theme_daily` 打到 `subject_exited_universe`；B 用 `sector_name contains 算力` 得 0 行。空行是 retrieve 参数，不是 stale 门。答案层两边都没成稿，不得 confirmed |
| 2026-08-17 #119 | `R-20260816-23` | 同题 `invalid_query` 计数降到 0 | still_pending | E-003 | A 把 `rank`/`sector_count` 抄进 dimensions 仍返回 14 行；两边都无 `not a dimension`。单次不得 confirmed |
| 2026-08-16 中断案 | `R-20260816-17` | `repair_model_unavailable` 首句含「模型服务不可用」且不含「现有证据不足」 | still_pending | E-008, E-009 | A 命中该形；B 是 `repair_deadline_exhausted` →「现有证据不足」。拆行仍成立，不结案 |
| 2026-08-16 GLM 复跑 | `R-20260816-21` | 同题不再两发整窗 TimeoutError；禁止只把 30 调大 | still_pending | E-006 | 帽是 40+20，不是 30；仍两发 TimeoutError。帽接线 ≠ 成稿 |
| 2026-08-16 outlook | `R-20260816-01` | 空 draft 超时 run 的首轮 finalize `model_turn` 含 `timeout_asked` | still_pending | E-002 | 两发首轮合成都有 `timeout_asked≈59.9`。字段在，单次不结案 |
| 2026-08-15 F-001 | `R-20260815-04` | 空 draft 落盘 `draft_source` 以切开 REASONING/HARNESS | still_pending | E-002, E-005 | 本形正是「模型已返回 draft、outcome 仍 0」。字段仍缺 |
| 2026-08-16 中断案 | `R-20260816-16` | 中转 5xx 时 tools>0 且不 16 次死重试 | still_pending | E-001 | zhipu、tools=4，不是 16×5xx。draft=0 不得 confirmed |
| 2026-08-16 中断案 | `R-20260816-18` | 不存在 `outcome=failed ∧ run.json=completed` | still_pending | E-008 | 两边 `run=completed` ∧ `outcome=partial`。禁止对未出现 |
| 2026-08-16 绊线 | `R-20260816-07` | 自称 outlook 预算修复的 PR 不含 T / 30 / 档位上调 | still_pending | — | 本分诊不改生产、不调 T/30/档位。绊线未触 |
| 2026-08-16 judge | `R-20260816-10` | draft>0 时 judge 首轮 asked≥20 | still_pending | E-008 | 两边 draft=0，judge 未调用（`judge_status=unavailable`，asked 缺席） |

- fix_type_refuted_streak: 0（本窗无 refuted）

## Executive finding

两发都在首轮合成写出了可解析 FINAL_JSON（A draft 897 字，含退出主线；B draft 738 字），但紧随的 `finish.carried_draft_chars=0`，outcome 空稿；随后 repair 两发 TimeoutError，公开答案变成缺口模板。工具层分叉（theme 退出 vs sector 空行）不能预测成稿失败。

## A/B controls

- invariant inputs: 同题；`task_frame_hash=8be72cddd69f28a96d4fa8c846d7a38e03313a490a4b2e3818a00b36c5cc1b97`；8792=`dd28e4d8` / dirty=false；user=`verify-r22-r23-0817`；`skill_mode=auto`；新会话
- intentional variable: 仅重跑（无代码 ablation）
- uncontrolled confounders: 模型工具选择（第 2/4 个工具）；kb 批窗超时（两边都有）

| normalized step | Run A span/evidence | Run B span/evidence | comparison | causal prediction |
|---|---|---|---|---|
| configure / intent / plan | `trace.jsonl` turn_assembly + controller + research_plan；lane=research, theme_analysis | 同左；hash 相同 | same | 装配层不分叉 |
| tool#1 | `finance_query` `market_daily` → 20 行 | `market_daily` → 24 行 | same | 不预测成稿 |
| tool#2 | `mainline_theme_daily` + `theme_name contains` → `subject_exited_universe` 14 行 | `mainline_sector_daily` + `sector_name contains` → empty 0 行 | diverged (payload, same L1) | 若此分叉导致成稿差异，A 应成稿、B 不应。观测：两边都 draft=0 → 否证 |
| tool#3 | `kb_search` `tool_timeout` | 同左 | same | 不能单独解释 A 已写出 897 字 JSON |
| tool#4 | `news_search` 6 行 | `memory_lookup` empty | diverged (payload) | 同上，不能预测共享 draft=0 |
| synthesize | seq12 FINAL_JSON `status=completed` draft_len=897 | seq12 FINAL_JSON `status=partial` draft_len=738 | same (both produced) | 应然：至少一边 outcome.draft>0 |
| stop (first finish) | seq14 `carried_draft_chars=0` `deadline_exhausted` | seq14 同形 `carried_draft_chars=0` | same | 这是共享失败点 |
| plan (repair) | grant=40, previous_draft_chars=0 | 同左 | same | 空稿进入 repair |
| unmapped repair model | 两发 TimeoutError + `model_error` | 两发 TimeoutError，无 `model_error` | diverged late | 只解释 stop 标签 / 模板句，不解释空稿 |

官方 compare：`pre_divergence_equivalence=fully_equivalent`，`first_divergence_step=null`，`unmapped_counts` left=7 right=6（`model_turn` / `repair_reentry` / `repair_model_retry` / A 多一条 `model_error`）。caveat：分叉字段可能是词表缺口；L1 序列本身等价。

- ablation_activation_step: n/a
- first_divergence_step: none observed
- first_divergence: n/a
- first_failure_step: stop (first `finish`, `carried_draft_chars=0`)
- failure_surfaced_step: stop (terminal `finish` + 公开缺口模板)
- reconvergence_step: stop (first finish 两侧都丢稿)
- pre_divergence_equivalence: configure→intent→plan→tool#1 等价；官方 mapped 序列 fully_equivalent
- downstream_propagation: 空稿 → repair 重写 → TimeoutError → 缺口模板。工具 payload 分叉未汇合，但不进入 PRIMARY 因果

本地词表 ↔ L1（`docs/trace-profile.md` §6，`runtime-benchmark` / episode 事件）：

| 本地 kind | L1 | 损耗 |
|---|---|---|
| `task` | intent | 无 |
| `tool_request` | tool | 无 |
| `tool_result` / `tool_error` / `runtime_result` | observe | 无 |
| `repair_goal` | plan | 无 |
| `finalization` | synthesize | 无 |
| `finish` | stop | 无 |
| `model_turn` / `repair_reentry` / `repair_model_retry` / `model_error` | unmapped | 合成与 repair 调用本身不进 L1 比较；必须手读 payload |

workbench `trace.jsonl` 的 `name=research` 会压进 `retrieve`，本报告以 episode 事件为准，不静默压缩。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 同题、同合同、同 revision | 两边 hash / 8792=`dd28e4d8` 相同 | ok | E-001 |
| intent / plan | theme-research 四格 | 两边 `theme_analysis` + 四 required outputs | ok | E-001 |
| retrieve / tool | 取到可绑定盘面/主线 | A 退出集合 14 行；B sector 0 行；kb 两边 timeout | ok/fail | E-003, E-004 |
| synthesize | 把证据写成 FINAL_JSON | 两边都写出可解析 JSON + draft | ok | E-002 |
| stop | 采纳刚写出的 FINAL_JSON | `carried_draft_chars=0`，structural 四格 missing | fail | E-005 |
| synthesize (repair) | 在已有稿上修 | `previous_draft_chars=0`，两发 TimeoutError | fail | E-006 |
| stop (terminal) | 至少交付已有稿 | 缺口模板；A unavailable / B deadline | fail | E-008, E-009 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| A/B first `finish` seq14 | HARNESS | stop | orchestration-related-errors-category-premature-termination | `carried_draft_chars=0` 紧跟已有 FINAL_JSON 的 `model_turn` | high |
| A/B repair `model_turn` | HARNESS | synthesize | execution-error-category-timeout | grant=40 后 `TimeoutError`，再 20s 再超时 | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 首轮合成已产出 FINAL_JSON，stop 路径未结转，所以 outcome.draft=0 | 若成立：`model_turn.content` 可 `json.loads` 且含 draft，同时同毫秒 `finish.carried_draft_chars=0`、`rejection_code=none` | E-002, E-005 | CONFIRMED | — | 两边同形；不是拒收 |
| H2 | `_consume_root_seconds` 在记账 model_turn 之后抛 ValueError，走 deadline 停机且不 parse content | 若成立：finalize 后 root 秒账本 remaining < 本轮墙钟 | 代码 `agent_episode.py:849-862` + 同毫秒三事件 | INCONCLUSIVE | finalize 后 `root_remaining_seconds`；H2 预测 < elapsed，观测 ≥ elapsed 即否证 | 控制流吻合，缺 root 钟读数 |
| H3 | PRIMARY 是 repair TimeoutError（模型太慢） | 若成立：repair 前不应已有可解析 draft | E-002, E-006 | REJECTED | — | repair 入口 `previous_draft_chars=0`，稿在更早被丢 |
| H4 | PRIMARY 是 B 的 sector 空查询 / R-22 未触发 | 若成立：A（退出命中）应成稿，B 不成稿 | E-003, E-004, E-005 | REJECTED | — | A 也 `carried_draft_chars=0` |
| H5 | PRIMARY 是 kb_search timeout | 若成立：无 kb 就写不出 FINAL_JSON | E-002, E-003 | REJECTED | — | A 在 kb 超时后仍写出 897 字 JSON |

## Causal findings

### PRIMARY

- failure_span_id: `run_20260817_014724_245782/episode.finish.seq14`（B 对称 `run_20260817_015340_618752/episode.finish.seq14`）
- root_location: `intelligence/runtime/agent_episode.py` 成功 `complete()` 之后、`_consume_root_seconds` 失败时的 `_stopped_outcome`（约 L849-862）；`carried_draft` 默认空
- excerpt: `carried_draft_chars: 0` / `stop_reason: deadline_exhausted` / `rejection_code: none`；前一条 `model_turn` 已有 `{"status":"completed","draft":"...`
- l0: HARNESS
- l1: stop
- l2: orchestration-related-errors-category-premature-termination
- l3: A2
- causality: PRIMARY_FAILURE
- propagation_impact: [TASK_TERMINATION, QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-002, E-005, E-010]
- explanation: 应然是「研究窗关了就用刚写出的 FINAL_JSON 交卷」。实然是 model_turn 已落盘完整 JSON，finish 仍按「从没生成过」结转。公开答案因此变成缺口模板，与工具层 R-22/R-23 是否命中无关。

### SECONDARY / TERTIARY

- F-002 SECONDARY：repair 在空稿上重写，40s+20s TimeoutError。传播，不是源头。
- F-003 TERTIARY：A/B 终态标签与模板句不同（unavailable vs deadline / 「模型服务不可用」vs「现有证据不足」）。
- none 作为独立 PRIMARY。工具 payload 分叉不升级。

## Evidence → Finding → Path

### Evidence

### E-001
- title: 两侧装配与合同相同
- run_id: `run_20260817_014724_245782` / `run_20260817_015340_618752`
- step_or_span_id: `trace.jsonl:configure` / `controller` / `plan`
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/verify-r22-r23-0817/runs/run_20260817_014724_245782/trace.jsonl:1-3`
- observed_at: 2026-08-17T01:47:24+08:00 / 01:53:40+08:00
- raw_excerpt: |
    task_frame_hash=8be72cddd69f28a96d4fa8c846d7a38e03313a490a4b2e3818a00b36c5cc1b97
    question_type=theme_analysis lane=research
- observation: 两边同一合同、同一四格 required outputs。
- confidence: high

### E-002
- title: 首轮合成已产出可解析 FINAL_JSON
- run_id: `run_20260817_014724_245782`
- step_or_span_id: `episode.model_turn.seq12`
- native_or_normalized: native
- source_type: transcript
- source_ref: `/Users/a77/.local/share/finance-workbench/users/verify-r22-r23-0817/runs/run_20260817_014724_245782/continuous-episode.json:1707-1722`
- observed_at: 2026-08-17T01:48:42.600+08:00
- raw_excerpt: |
    error="" timeout_asked=59.955 output_tokens=2882 tool_calls=[]
    content json.loads → status=completed draft_len=897 bindings=4
    B 对称：status=partial draft_len=738 bindings=4 at 01:54:34.791
- observation: 两边 finalize `model_turn` 都是合法 JSON，含 draft 与四格 bindings（E 序号）。
- confidence: high

### E-003
- title: 第二发 finance_query 工具层结果
- run_id: both
- step_or_span_id: `episode.tool_request.seq5` / `tool_result.seq6`
- native_or_normalized: native
- source_type: tool_return
- source_ref: A `continuous-episode.json` traces `detail=dataset=mainline_theme_daily; subject_exited_universe`
- observed_at: 2026-08-17T01:47:54+08:00 / 01:54:10+08:00
- raw_excerpt: |
    A: status=ok served=2026-08-07 dataset_max=2026-08-14 rows=14
    B: status=empty dataset=mainline_sector_daily rows=0
    A dims 含 rank/sector_count（亦在 metrics）；无 invalid_query
- observation: A 打到退出集合；B 零行；A 的 R-23 抄写形未炸。
- confidence: high

### E-004
- title: B 的空查询过滤字段
- run_id: `run_20260817_015340_618752`
- step_or_span_id: `episode.tool_request.seq5`
- native_or_normalized: native
- source_type: tool_request
- source_ref: B `continuous-episode.json` seq5 arguments
- observed_at: 2026-08-17T01:54:10.763+08:00
- raw_excerpt: |
    dataset=mainline_sector_daily
    filters=[{field:sector_name, op:contains, value:算力}]
- observation: 过滤打在 `sector_name`，不是 theme 名。零行时没有 `served_date`，退出探针不会触发。
- confidence: high

### E-005
- title: 同毫秒 finish 未结转 draft
- run_id: `run_20260817_014724_245782`
- step_or_span_id: `episode.finish.seq14`
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.local/share/finance-workbench/users/verify-r22-r23-0817/runs/run_20260817_014724_245782/continuous-episode.json:1734-1750`
- observed_at: 2026-08-17T01:48:42.600+08:00
- raw_excerpt: |
    stop_reason=deadline_exhausted
    carried_draft_chars=0
    rejection_code=none
    gaps=["研究截止时间已到，仍有必需输出未覆盖"]
    B 对称：continuous-episode.json:1313 carried_draft_chars=0
- observation: 与 E-002 同一时间戳。不是 unknown-hash 拒收。structural 随后四格 missing。
- confidence: high

### E-006
- title: repair 在空稿上两次 TimeoutError
- run_id: both
- step_or_span_id: A `repair_reentry` / `model_turn.seq17` / `seq19`
- native_or_normalized: native
- source_type: log
- source_ref: A `continuous-episode.json` seq15-20
- observed_at: 2026-08-17T01:48:42+08:00 .. 01:49:42+08:00
- raw_excerpt: |
    previous_draft_chars=0 granted_seconds=40.0
    model_turn error="LLM 调用失败（TimeoutError）"
    retry seconds_granted=20.0 再 TimeoutError
- observation: 两边 repair 入口都认为没有上一轮稿。
- confidence: high

### E-007
- title: 官方 L1 compare 无分叉
- run_id: both
- step_or_span_id: `/tmp/r22-r23-m2/compared.json` comparison
- native_or_normalized: normalized
- source_type: file
- source_ref: `normalize_harness_trace --kind runtime-benchmark --compare`
- observed_at: 2026-08-17
- raw_excerpt: |
    pre_divergence_equivalence=fully_equivalent
    first_divergence_step=null
    unmapped_counts left=7 right=6
    interpretation_caveats=[unmapped events present...]
- observation: L1 序列等价。不得把 payload 分叉写成 L1 first_divergence。
- confidence: high

### E-008
- title: self_report_vs_observed 终态对账
- run_id: both
- step_or_span_id: `run.json` / `outcome` / `answer.md` / last `finish`
- native_or_normalized: native
- source_type: file
- source_ref: 两发 run 目录
- observed_at: 2026-08-17
- raw_excerpt: |
    run.json status=completed
    outcome.status=partial
    A last finish stop=repair_model_unavailable ；答案含「模型服务不可用」
    B last finish stop=repair_deadline_exhausted ；答案含「现有证据不足」
    judge_status=unavailable ；structural 四格 missing
- observation: 机器 completed 与业务 partial/空稿并存。A/B 模板句随终态标签分叉。
- confidence: high

### E-009
- title: 公开答案是缺口模板，不是 E-002 的 draft
- run_id: both
- step_or_span_id: `answer.md`
- native_or_normalized: native
- source_type: file
- source_ref: 两发 `answer.md`
- observed_at: 2026-08-17
- raw_excerpt: |
    A: 「模型服务不可用，暂不能可靠回答」+「已取得 40 条证据」
    B: 「现有证据不足，暂不能可靠回答」+「已取得 24 条证据」
- observation: 用户可见面丢掉了已写出的阶段判断。
- confidence: high

### E-010
- title: stop 路径默认不结转 run() 草稿
- run_id: n/a（代码对照，非运行时字段）
- step_or_span_id: `agent_episode.py:849-862` / `:2435-2486`
- native_or_normalized: native
- source_type: code_reading
- source_ref: `/Users/a77/.finance-runtime/finance-workspace-dd28e4d84766/intelligence/runtime/agent_episode.py:849-862`
- observed_at: 2026-08-17
- raw_excerpt: |
    if not _consume_root_seconds(context, model_elapsed):
        return self._stopped_outcome(... stop_reason="deadline_exhausted" ...)
    # carried_draft 默认 ""
    # 注释：run() 停在这里时没有更早的答案可留
- observation: 成功 complete() 并 ledger 了 model_turn 之后，consume 失败会空稿停机。与 E-005 形状一致。升 high 靠 E-002/E-005 实测，不单靠本条。
- confidence: medium

### Findings

### F-001
- title: 首轮 FINAL_JSON 未结转
- status: validated
- failure_span_id: `run_20260817_014724_245782/episode.finish.seq14`
- root_location: `agent_episode.py` `_stopped_outcome` after successful finalize `complete()`
- l0: HARNESS
- l1: stop
- l2: orchestration-related-errors-category-premature-termination
- l3: A2
- violated_authority: system
- causality: PRIMARY_FAILURE
- propagation_impact: [TASK_TERMINATION, QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-002, E-005, E-010]
- confidence: high
- explanation: 正确状态是 seq12 已有 draft。错误状态是 seq14 `carried_draft_chars=0`。必要交卷步骤没做完就按截止停机。

### F-002
- title: repair 在空稿上超时
- status: validated
- failure_span_id: A `episode.model_turn.seq17`
- root_location: repair_reentry grant=40
- l0: HARNESS
- l1: synthesize
- l2: execution-error-category-timeout
- l3: n/a
- violated_authority: system
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-006]
- confidence: high
- explanation: 源头是空稿结转。repair 重写整篇并超时，把已有判断彻底盖掉。

### F-003
- title: 终态标签与模板句分叉
- status: validated
- failure_span_id: last `finish`
- root_location: adapter 缺口模板
- l0: HARNESS
- l1: stop
- l2: orchestration-related-errors-category-unaware-termination
- l3: n/a
- violated_authority: none
- causality: TERTIARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: COMPLETE_FAILURE
- evidence_ids: [E-008, E-009]
- confidence: high
- explanation: 同一空稿，A 报模型不可用、B 报证据不足。不是成稿失败的源头。

### Path

### P-001
- title: 有稿 → 未结转 → 空 repair → 模板
- start: E-002 首轮 FINAL_JSON 已落盘
- goal: failure_criterion（outcome.draft 非空）
- steps:
  1. 两边完成检索并写出 FINAL_JSON — evidence: E-002 — finding: none
  2. first finish `carried_draft_chars=0` — evidence: E-005 — finding: F-001
  3. repair 当空稿重写并 TimeoutError — evidence: E-006 — finding: F-002
  4. 公开缺口模板 — evidence: E-009 — finding: F-003
- residual_uncertainty: finalize 后 root 秒账本剩余是否 < 本轮墙钟（H2）；缺该读数不能在「consume 抛错」与「其它立刻停机」之间钉死子因

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260817-01 | F-001 | HARNESS_FIX | `complete()` 已返回且 content 是 FINAL_JSON 时，先 validate/结转再谈 consume 失败；`_stopped_outcome` 的 run() 截止路径必须带上刚写出的 draft。禁止调 T / `_REPAIR_SECONDS_CAP` / 档位 | 同题重跑：first finish `carried_draft_chars>0` 或 `outcome.draft` 含阶段判断；即使 stop 仍是 deadline_exhausted | 离线：finalize 返回合法 JSON 后让 `consume_seconds` 抛 ValueError，断言 draft 仍在 outcome。触 R-07 绊线即改记该行 |
| R-20260817-02 | F-002 | NO_SYSTEM_FIX | 不把 leftover-30 / 再加长 repair 窗当本窗修复。空稿修掉后这条应不再被走到 | 若 R-20260817-01 兑现，repair `previous_draft_chars>0` 或不再进入空稿 repair | 夹具钉「有稿 + consume 失败」不进空 repair |
| R-20260817-03 | F-001 / H4 | EVAL_ONLY | 工具层 R-22/R-23 保持 pending。B 的 sector 空行另记 retrieve 方差，不写成 R-22 refuted | 再有 `sector_name contains 算力` 的 0 行，不得当作 stale 门回归 | 对照夹具：theme_name 有行 / sector_name 无行 |

- auto_apply: false

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| finalize 后 root 秒账本剩余 | H2（consume 是否抛错） | `root_remaining_seconds_after_finalize`；H2 预测 < `model_elapsed` | 与 `model_turn` 同条或紧随 observe | 观测 ≥ elapsed 即否证 H2 | 一个 float |
| `draft_source` 仍缺席 | R-20260815-04 | `draft_source ∈ {model_returned_empty, truncated_by_budget, provider_error, dropped_after_success}` | first finish payload | 本形应落 `dropped_after_success` | 一枚举 |

## Limits and counterevidence

- 官方 L1 compare 报 fully_equivalent；payload 分叉不得写成 L1 根因。
- E-010 是代码对照，单独不得 high；PRIMARY 靠 E-002/E-005。
- 未在本机复跑 DuckDB 证明 `sector_name` 永不含「算力」；E-004 只证明这次过滤零行。
- 未改生产、未切 8792、未调 T/30/档位。
- `self_report_vs_observed`：`run.json=completed` 对 `outcome=partial` + 空稿模板；first finish 自称「必需输出未覆盖」，但 seq12 已覆盖四格 bindings。

## Next-step menu

1. 按 R-20260817-01 做结转（先 validate 再 consume 失败停机），离线夹具绿后再 live
2. 在 first finish 加 `root_remaining_seconds_after_finalize`，切开 H2
3. 账本写入 R-20260817-01，R-22/R-23 保持 pending
4. 停。不要调 T/30，不要把 B 的空查询当 R-22 回归
5. 检阅方抽查 E-002/E-005 原文与 `agent_episode.py:849`
6. 成稿后再谈 judge / kb 批窗

# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M1
- failure_criterion: finish 事件无法在不打开 episode 的情况下给出「hashes+gap 滑档被搬运」的格数（字段缺失或语义不明）；且 R-001 夹具未覆盖 B5 全格 / B7 混合真缺口 / A6 全格。否命题是：`finish.payload.caveat_slips` 始终在场、等于本次搬运格数，且 B7 的 0-hash 真缺口格仍 missing。
- trace_coverage: 冻结主 case `run_20260813_034211_544672` finish 无 `caveat_slips`；跨组 B5 `run_20260814_022902_659281`（15/18 全格滑档）、B7 `run_20260814_023030_100048`（0+13 混合）、A6 `run_20260814_021218_897744`（1/1 全格滑档）。离线重放 validate + verifier。未跑 8792 live。未读 skill 受控验收目录。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: high

## Prior prediction closure

本轨道只读 Open 表，不写 `R-20260804-10` 与 B 轨行。#7 已合入 main：`R-20260804-02` 已在账本 Closed 为 refuted，本轨道不重开。

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 轨道 A Round 1 | R-20260815-21 | 全格 hashes+gap 经 validate 后 gap 归位、verifier fulfilled；无哈希 gap 仍拒绝；leftover gap 仍 missing | still_pending | E-006、E-007、E-008 | 离线门已绿；live canary 按检阅方补注暂缓至 8792 身份裁决。单次未复现不得结案 |
| 收口审计 §修复2 | R-20260804-02 | 真 Codex rollout 中 `function_call_output` 归入 `observe` | refuted | none — 已由 #7 / 轨道 B 结案 | 保持 Closed；本轨道不写该行 |
| L7 finalization T3 | R-20260804-10 | deadline-aligned per-tool handoff 离线主门 + 瑞华泰 canary | still_pending | none | 保持 Open；本轨道不写该行 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `HARNESS_FIX`=1（距升格线 2）；`EVAL_ONLY`=0（本轮 `R-20260815-22` confirmed 归零）；二者不互相累计

## Executive finding

第一处错误变换是 R-001 已把 hashes+gap 滑档归位，但 `validate_episode_finish` / finish 事件不记录搬运格数：旧 episode 的 `finish.payload` 无 `caveat_slips`，验收台只能看 stop/eb，无法直接分全格滑档、混槽与真缺口。B7 冻结混合形证明真缺口格必须仍拒绝——这是本轮夹具的核心。

## Local vocabulary ↔ L1

本仓 `trace-profile.md` §6 词表 `triage-l1-9`。本轮主证据在 episode finish 事件与 validate 重放。

| 本地 kind / step_id | L1 | provenance |
|---|---|---|
| `validate_episode_finish` | `stop` | 终局契约，写入 finish 事件 |
| `finish` | `stop` | episode native |
| `structural_verifier` | `observe` | 夹具对照，判据不改 |

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | R-001 归位契约已在 PR #6 / 本分支 | 搬运逻辑在；计数未落盘 | ok | E-002 |
| synthesize | 滑档 JSON 可被归位 | 冻结四样本均为 hashes+gap 或混合 | ok | E-003、E-004、E-005 |
| stop | finish 带搬运格数，健康=0 | 四份冻结 finish 均无 `caveat_slips` | fail | E-001 |
| observe | 真缺口格仍 missing | B7 `direct_answer` 0 hash + gap，structural missing | ok | E-004 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260813_034211_544672/events[kind=finish]` | HARNESS | stop | local-missing-caveat-slips-count | `finish.caveat_slips=<ABSENT>`；两格 n_hash=6/7 且 gap 非空 | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | validate 已搬运 N 格，但 EpisodeFinish / finish.payload 没有计数 | 冻结 finish 字段缺失；重放后应能得到整数 N | E-001、E-002、E-006 | CONFIRMED | — | 四份冻结 finish 均 `<ABSENT>`；重放 A7 得 2 |
| H2 | 加上计数会改变拒绝/fulfilled 判定 | 若成立，无哈希 gap 会被放行，或 leftover gap 不再 missing | E-006、E-007、E-008 | REJECTED | — | 拒绝路径仍 raise；B7 真缺口仍 missing；leftover 单测未改 |
| H3 | B7 混合形 = 一格 F-001 滑档 + 一格真缺口；修复不得放宽真缺口 | 搬运后 `caveat_slips=1`，`direct_answer` missing，`evidence_boundary` fulfilled | E-004、E-008 | CONFIRMED | — | 夹具 `test_r001_fixture_b7_mixed_true_gap_still_missing` |
| H4 | 冻结 A6 是 live 那条零证据冷启动，不应进 R-001 夹具 | 若成立，A6 冻结 run 应 n_evidence=0 | E-005 | REJECTED | — | 冻结 A6 有 1 条证据、两格 1/1 hashes+gap，与 live 冷启动不是同一 run |

## Causal findings

### PRIMARY

- failure_span_id: `run_20260813_034211_544672/continuous-episode.json:events[kind=finish]`
- root_location: `validate_episode_finish` 归位后未把搬运格数写入 `EpisodeFinish` / finish 事件
- excerpt: `finish.caveat_slips=<ABSENT>`; bindings 6/7 hashes+gap; B7 mixed 0+13
- l0: HARNESS
- l1: stop
- l2: local-missing-caveat-slips-count
- l3: n/a
- causality: PRIMARY_FAILURE
- propagation_impact: [NO_PROPAGATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-006]
- explanation: 观测洞挡住滑档频率基线，不改变交付判定。补整数计数后，不打开 episode 也能分全格 / 混槽 / 真缺口。

### SECONDARY / TERTIARY

none

## Evidence → Finding → Path

### Evidence

### E-001
- title: 冻结四样本 finish 均无 caveat_slips
- run_id: run_20260813_034211_544672
- step_or_span_id: run_20260813_034211_544672/events[kind=finish]
- native_or_normalized: native
- source_type: file
- source_ref: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260813_034211_544672/continuous-episode.json` finish payload；对照 B5/B7/A6 同字段
- observed_at: 2026-08-15
- raw_excerpt: |
    A7 finish.caveat_slips=<ABSENT> stop=repair_model_stop bindings 6/7 both gap; B5 15/18; B7 0+13; A6 1/1
- observation: 四份冻结 finish 都不含 `caveat_slips`。
- confidence: high

### E-002
- title: R-001 已搬运但不计格数
- run_id: n/a
- step_or_span_id: intelligence/services/episode_protocol.py:validate_episode_finish
- native_or_normalized: native
- source_type: code_reading
- source_ref: `intelligence/services/episode_protocol.py` relocate 循环；Round 1 报告 Observability prescription
- observed_at: unknown
- raw_excerpt: |
    hashes+gap → relocated_gaps + replace(binding, gap=""); EpisodeFinish 无计数场
- observation: 归位逻辑在；返回值与 finish 事件都没有搬运格数。
- confidence: medium

### E-003
- title: B5 冻结形状为全格滑档 15/18
- run_id: run_20260814_022902_659281
- step_or_span_id: run_20260814_022902_659281/events[kind=finish]
- native_or_normalized: native
- source_type: file
- source_ref: 同上用户 runs 目录 continuous-episode.json
- observed_at: 2026-08-14T02:29:02+08:00
- raw_excerpt: |
    qtype=general_finance_qa; stop=repair_model_stop; direct_answer n_hash=15 gap=True; evidence_boundary n_hash=18 gap=True; structural both missing
- observation: 两格都是 hashes+gap。夹具用合成哈希钉此形状。
- confidence: high

### E-004
- title: B7 冻结形状为混合真缺口
- run_id: run_20260814_023030_100048
- step_or_span_id: run_20260814_023030_100048/events[kind=finish]
- native_or_normalized: native
- source_type: file
- source_ref: 同上
- observed_at: 2026-08-14T02:30:30+08:00
- raw_excerpt: |
    stop=repair_model_finish; direct_answer n_hash=0 gap=True; evidence_boundary n_hash=13 gap=True; structural both missing
- observation: 一格真缺口、一格滑档。终态 `repair_model_finish` 也在射程内。
- confidence: high

### E-005
- title: 冻结 A6 是 1/1 全格滑档，不是零证据冷启动
- run_id: run_20260814_021218_897744
- step_or_span_id: run_20260814_021218_897744/outcome
- native_or_normalized: native
- source_type: file
- source_ref: 同上
- observed_at: 2026-08-14T02:12:18+08:00
- raw_excerpt: |
    stop=repair_model_finish; n_evidence=1; both outputs n_hash=1 gap=True
- observation: 与 Round 1 live A6（n_evidence=0）不是同一 run。
- confidence: high

### E-006
- title: 重放后计数等于搬运格数
- run_id: n/a
- step_or_span_id: test_caveat_slips_replays_r7_a7_frozen_finish
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/tests/test_episode_protocol.py` R-22 三断言
- observed_at: 2026-08-15
- raw_excerpt: |
    A7 replay caveat_slips=2 both fulfilled; clean/top-level-only=0; completed+no-hash gap raises, no EpisodeFinish.caveat_slips
- observation: 三条预测均被离线单测兑现。
- confidence: high

### E-007
- title: finish 事件落盘带 caveat_slips
- run_id: n/a
- step_or_span_id: test_finish_event_exposes_caveat_slips_count
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/tests/test_agent_episode.py`；`agent_episode.py` 四条 finish 路径
- observed_at: 2026-08-15
- raw_excerpt: |
    hashes+gap finish.payload.caveat_slips=1; clean path=0; _stopped_outcome writes 0
- observation: 计数在 finish payload 可见。未走过 validate 的停机路径写 0。
- confidence: high

### E-008
- title: B7 夹具证明真缺口仍拒绝
- run_id: n/a
- step_or_span_id: test_r001_fixture_b7_mixed_true_gap_still_missing
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/tests/test_episode_protocol.py`；对照 leftover-gap verifier 单测
- observed_at: 2026-08-15
- raw_excerpt: |
    caveat_slips=1; direct_answer missing + gap kept; evidence_boundary fulfilled gap=""; leftover gap still drops hashes
- observation: 修复没有放宽 verifier 判据。
- confidence: high

### self_report_vs_observed

| 对账对象 | 机器/原始观测 | 人类可读或后处理字段 | 采用口径 |
|---|---|---|---|
| B5/B7 是否仍滑档 | 冻结 run 目录 bindings 为 hashes+gap | tool60 复跑产物 B5=3 / B7=5 且 R-001 未部署 | 夹具钉冻结 run，不钉后来自发恢复。滑档非确定，单点未复现不得当修复证据 |
| A6 是否本靶 | 冻结 A6 n_evidence=1、1/1 hashes+gap | Round 1 live A6 eb=0 n_evidence=0 | 夹具用冻结 run；live 冷启动划出 |
| 计数是否改变判定 | B7 真缺口仍 missing；无哈希 completed 仍 raise | 「加字段即放宽」 | 判定以 verifier / reject 为准；计数只观测 |

### Findings

### F-001
- title: finish 事件缺少搬运格数
- status: validated
- failure_span_id: run_20260813_034211_544672/events[kind=finish]
- root_location: validate_episode_finish → finish payload
- l0: HARNESS
- l1: stop
- l2: local-missing-caveat-slips-count
- l3: n/a
- violated_authority: system
- causality: PRIMARY_FAILURE
- propagation_impact: [NO_PROPAGATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-006, E-007]
- confidence: high
- explanation: 归位已发生，观测未落盘。补 `caveat_slips` 整数后可建滑档频率基线，不改判定。

### Path

### P-001
- title: 归位发生但不可计数
- start: R-001 已把 hashes+gap 挪到顶层 gaps
- goal: finish.payload 给出搬运格数；B7 真缺口仍 missing
- steps:
  1. 冻结四样本 finish 无计数 — evidence: E-001 — finding: F-001
  2. validate 重放得到整数并落盘 finish 事件 — evidence: E-006、E-007 — finding: F-001
  3. B7 混合夹具锁住真缺口拒绝 — evidence: E-004、E-008 — finding: none
- residual_uncertainty: 8792 脏部署未裁决，live canary 仍暂缓；`normalize_harness_trace` 不投影该字段（B 轨缝）。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-002 | F-001 | EVAL_ONLY | `EpisodeFinish.caveat_slips` + finish.payload 同名字段；无滑档为 0 且在场。不改 verifier / 拒绝语义 | 见账本 `R-20260815-22` 三条断言 | R-22 三测 + finish 事件测 |
| R-001b | F-001 | DATA_CONTRACT_FIX | 把 B5/B7/A6 冻成 R-001 回归夹具；B7 为核心 | B5/A6 搬运后全 fulfilled；B7 `direct_answer` 仍 missing | 三夹具单测 |

### R-002
- targets_finding: F-001
- fix_type: EVAL_ONLY
- recommendation: 只加观测计数，不改任何判定。
- verification_prediction: 见 `R-20260815-22`。
- regression_guard: `test_caveat_slips_*`；`test_finish_event_exposes_caveat_slips_count`
- auto_apply: false

### R-001b
- targets_finding: F-001
- fix_type: DATA_CONTRACT_FIX
- recommendation: 跨组形状钉进 R-001 测试面，证明真缺口格照旧拒绝。
- verification_prediction: B7 混合形 `caveat_slips=1` 且 0-hash 格 missing。
- regression_guard: `test_r001_fixture_b7_mixed_true_gap_still_missing`
- auto_apply: false

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值，非日志洪水） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| 8792 生产代码身份未定 | live canary 无法盖戳 | 三读数：health revision / loaded_code_root / dirty 文件清单一致 | `/api/health` + 部署目录 | 才能数修复后窗口的滑档 | 待用户裁决 |
| normalize 不投影 caveat_slips | 跨 harness 比较读不到该计数 | 可选：finish summary 带 `caveat_slips=N` | `normalize_harness_trace`（B 轨缝，本轮不改） | 归一化产物也能分全格/混槽 | 低；等 B 轨 normalize PR |

## Limits and counterevidence

- 本轮不做任何 8792 live。tool60 复跑里 B5/B7 自发恢复，说明滑档非确定；canary 必须多 case 窗口且只在修复部署后计数。
- 查询入口是 episode `finish.payload.caveat_slips`，不是 NormalizedEvent.summary。
- 不碰 acceptance / normalize / verifier 判据；不重开 R6-A3 / A4 / A3。
- 夹具用合成哈希钉形状，不把题面或持仓写入 git。
- 主 checkout 只读；本轮在 `fwp-wt-trka-r2`。

## Next-step menu

1. 检阅本 PR（`fix/trka-caveat-slips-counter`）；#6 已被本分支 rebase 到 #7 之后，可关 #6 或先合 #6 再合本 PR。
2. 用户裁决 8792 脏部署后再开 live canary：多 case 窗口，只在 R-001 部署后计数。
3. 不在本轨道做 `carried_draft_chars=0` 丢稿分诊（`agent_episode.py` 在脏文件清单里）。
4. 若要把计数编进 normalize summary，等 B 轨 normalize PR 后再开一行。
5. 不重开 A4 前缀哈希或 A3 档位链。

## Round 2 小结

- 任务 1：`finish.payload.caveat_slips` EVAL_ONLY 已落地；`R-20260815-22` 三条离线断言 confirmed。
- 任务 2：B5/B7/A6 冻成 R-001 夹具；B7 证明 0-hash 真缺口仍 missing。
- live：全部暂缓，等 8792 裁决。
- 工作树：`/Users/a77/fwp-wt-trka-r2`；基线 rebase 到 `gitea/main`（#7+#8）之上重放 R-001。

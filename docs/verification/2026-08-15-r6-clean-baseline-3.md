# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_NOT_CONFIRMED
- mode: M1
- failure_criterion: 同身份（`fdb231148c0e` + `source_dirty=false` + pid 70403）上跑完 qc28 批 #3 后，按预注册六项读数：R-23 同形修复轮不再出现 `unknown/truncated evidence hash` 且 `evidence_bound>0`（只出数）；R-25 新 `tool_exception` 的 `detail` 非空无路径（零样本=unobserved）；R-12 探针字段在场，fail 而无顶层污染戳才 refuted；R-10 用冻结口径 `evidence_bound>0` 出 B 组 N=3 表并结案；R-09 末条 finish 带 `rejection_code`/`rejection_reason`（无拒收=`none`/空，有拒收则非空）；RU-3 只统计 `episode_fulfilled_hashed ≠ evidence_bound` 与 `gap_output_ids`，R-24 未实现则记录、不修、不开 L0。禁止单批失败成员名单。
- trace_coverage: 新产物 `intelligence/eval/runs/20260815T1005Z-r5-clean-baseline-3.json`（`sha256=e475f3c8…f1ebf0`，28 题 / 30 轮，随本 PR 进 git）；对照冻结批 #1 `20260814T1926Z-r3-clean-baseline.json`（`sha256=b712bd2e…d8d350`）与批 #2 `20260815T0302Z-r4-clean-baseline-2.json`（`sha256=51e61710…304ef4`）。仓外 run 目录含 `continuous-episode.json`（验收台未挂上 run_id 的 B4 另点名）。**缺**：本窗口零 `error=tool_exception` 事件，R-25 live 臂不可判定。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: medium

## Prior prediction closure

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 轨道 B Round 3 | R-20260815-10 | B 组结论改报交付率而非单批布尔后：连续 3 批的 B 组读数按题给出 N 次中的交付次数；任一只引用单批「失败成员名单」的结论可被评审据此打回 | confirmed | E-005 | **N=3 表已出**（见 E-005）。结案只用 `evidence_bound>0`。B4 验收 timeout 在产物里 eb=0，不改口径 |
| 轨道 B Round 3 | R-20260815-09 | `invalid_repair_finish` 落盘拒收原因码与被拒 payload 的结构摘要后：下一个该形状的 turn 其原因码非空 | confirmed | E-006 | 21 个验收挂上的 episode 末条 finish 均有 `rejection_code`/`rejection_reason`；B8 末条 `invalid_repair_finish` 码=`no_substantive_answer`、原因非空。本轮 handoff 判据是字段在场性 + 有拒收时非空 |
| 轨道 B Round 5 | R-20260815-12 | 开批前探针写入 `preflight_detail`；失败须顶层 `window_contamination="finance_query"`；静默混批即 refuted | confirmed（保持 Closed） | E-004 | live 臂：`data_probe: finance_query=ok`，`data_probe_ok=true`，`window_contamination=null`（探针成功不得盖污染戳） |
| 轨道 A Round 4 | R-20260815-23 | 部署后下一批：修复轮携证据应收出绑定且 eb>0；再出现 `unknown evidence hash` 则 refuted | still_pending（本轨只出数） | E-002 | 15 条修复路径、14 条验收 eb>0；`invalid_action` 零条含 unknown/truncated evidence hash。B8 是另一拒收码。outcome 归 A/检阅方 |
| 轨道 A Round 5 | R-20260815-25 | 新的 `tool_error` 且 `error=tool_exception` 的 `detail` 非空、形如 `ClassName: first line`、不含 `/Users/` | still_pending（unobserved） | E-003 | 数据层健康。17 条 `tool_error` 全是 `tool_timeout` / `tool_budget_exhausted`，零 `tool_exception`。不改口 |
| 轨道 A Round 5 | R-20260815-24 | marker-loss 后不得再同时「结构 fulfilled + `gap_output_ids` 含这些 ID + citations=0」 | still_pending（未实现） | E-007 | 本批 13 题 `efh ≠ eb`；B3 本批 `gap_output_ids=['direct_assessment']` 但 eb=10，不是 B3#2 的 fail-closed 零。记录、不修、不开 L0 |
| 轨道 B Round 2 | R-20260815-04 | `draft_source` 埋点 | still_pending | 无 | 本轮未做 |
| 轨道 B Round 2 | R-20260815-03 | 两套 output 判定对账 | still_pending | 无 | 本轮无新证据 |
| 2026-08-04 | R-20260804-10 | deadline-aligned per-tool handoff… | still_pending | 无 | 本轮无新证据 |
| 2026-08-04 | R-20260804-02 | 真 Codex rollout 归一化 | still_pending | 无 | 本轮无新证据；无新证据保持 pending |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `EVAL_ONLY`=0；`HARNESS_FIX`=0（本轮 `R-20260815-09` confirmed，按「中间出现一次 confirmed 即归零」把 08-04 的 1 清掉）。

## Executive finding

批 #3 在 `fdb23114` / pid 70403 下落盘，`not_run=0`，数据探针 ok，A 组 9/10 交付——批 #2 的数据层锁窗口未再现。R-10 N=3 与 R-09 字段在场可结案。修复轮同形 14/15 验收 `eb>0` 且零誊抄拒收（R-23 出数）。本窗口唯一 `invalid_repair_finish` 是 B8（`no_substantive_answer` / `scenario_range`），不定 L0。B4 验收 timeout，但仓外 episode 已 `repair_model_stop` 且三格 hashed；R-10 仍按产物 eb=0 计未交付。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 8792=`fdb23114`、脏位空、users_dir 对齐、开批无同步写者 | `source_revision=fdb231148c0e…`、`source_dirty=false`、pid 70403、`users_dir` 对齐；dragon_seats 父进程 94429 已退出后开批 | ok | E-001 |
| retrieve | 数据层可读 | 探针 `finance_query=ok` / 994ms / served_date=2026-08-14；A 组 9/10 有证据 | ok | E-001, E-004 |
| tool | 工具取证 | 多数题取回证据；17 条 `tool_error` 为 timeout/budget，零 `tool_exception` | ok | E-003 |
| observe | 证据入 episode / 验收字段 | 21 题 `episode_artifact`；C4/C5 `api_only` 仍 eb=24/22；B4 验收未挂 run_id | fail（B4 仪器） | E-008 |
| synthesize | 修复轮解析绑定 | 14 条修复路径验收 eb>0；B8 末条 `invalid_repair_finish`、bindings=0、draft=0 | **fail**（B8） | E-002, E-006 |
| stop | 证据到达验收面；拒收码在场 | B 组 N=3 可结案；B8 eb=0；21 末条 finish 带拒收字段 | fail / recovered | E-005, E-006 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| B8 `run_20260815_182902_790837` / 末条 `finish` seq 21 | UNCLEAR（竞争项：REASONING 未写 `scenario_range` vs HARNESS 修复轮契约拒收；本轮按指派不开 L0） | synthesize | DEPTH_INSUFFICIENT(D4) | 末条 `stop_reason=invalid_repair_finish`；`rejection_code=no_substantive_answer`；`rejection_reason=required output lacks substantive answer: scenario_range`；`bindings=0` `draft=0` `outcome.evidence=16` | medium |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 批 #3 修复轮同形会再出 `unknown/truncated evidence hash` 且 eb=0 | 若成立，至少一条 `invalid_action.reason` 含该短语，且该题验收 eb=0 | E-002 | **REJECTED** | — | 15 条修复路径里 0 条 hash 拒收；14 条验收 eb>0。B8 拒收码是 `no_substantive_answer` |
| H2 | 数据层健康时仍会出现 `error=tool_exception` 且 `detail=""` | 若成立，本批至少一条 `tool_error.error=tool_exception` 且 detail 空 | E-003 | **INCONCLUSIVE** | 下一次数据层故障窗口出现 `tool_exception`；`detail=""` → R-25 refuted，非空且无 `/Users/` → 可收口 | 零 `tool_exception`。17 条 tool_error 是 timeout/budget。按预注册保持 pending |
| H3 | 第三批足以按冻结口径关闭 R-10 | 若成立，B1–B8 均可写出 N=3 交付次数，且不依赖单批名单 | E-005 | **CONFIRMED** | — | 见 E-005。B6 三批皆澄清=0/3，不是失败名单 |
| H4 | 新快照末条 finish 缺 `rejection_code`，或有拒收时码为空 | 若成立，任一挂上的 episode 末条缺字段，或 B8 类拒收码为空 | E-006 | **REJECTED** | — | 21/21 在场；B8 码与原因均非空 |
| H5 | B3#2 分道（hashed fulfilled + `gap_output_ids` 含这些 ID + eb=0）在本批再现 | 若成立，B3 本批 eb=0 且 gap 含已 fulfilled 格 | E-007 | **REJECTED**（仅本窗口） | — | B3 本批 eb=10、efh=3、`gap_output_ids=['direct_assessment']`。R-24 仍未实现，13 题 efh≠eb 只记录 |
| H6 | 探针失败会静默混进干净批 | 若成立，`data_probe` 失败且顶层无 `window_contamination` | E-004 | **REJECTED** | — | 探针 ok，未盖污染戳，符合「未失败不盖戳」 |

## Causal findings

### PRIMARY

- failure_span_id: B8 `run_20260815_182902_790837` / 末条 `finish` seq 21
- root_location: 修复轮收尾与 `scenario_range` 实质答案之间（本轮只记形状与拒收码）
- excerpt: 末条 `stop_reason=invalid_repair_finish`；`rejection_code=no_substantive_answer`；`rejection_reason=required output lacks substantive answer: scenario_range`；`bindings=0`；`draft=0`；`outcome.evidence=16`
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-006]
- explanation: 取证 16 条后修复轮被拒、零绑定。拒收码已在 finish 上，不再只靠事件流自由文本。与批 #1 B1/B7、批 #2 B5/C7 的誊抄哈希拒收**不同形**。按本轮指派不开 L0。

### SECONDARY

- failure_span_id: B4 验收 `status=timeout` vs 仓外 `run_20260815_182037_434217`
- root_location: 验收 300s 墙在 run 写完 episode 之后切断，产物未挂 `run_id`
- excerpt: 产物 B4 `status=timeout` `eb=0` `execution_state=unknown` `run_id=null`；仓外 run `status=completed` `finished_at=18:25:39`；末条 `repair_model_stop` 三格 hashed（5+12+6）`outcome.evidence=116`
- l0: UNCLEAR
- l1: stop
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A1
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-008]
- explanation: R-10 冻结口径读产物 eb=0，B4 计未交付。episode 层已交付。两套仪器并存，不选边改 R-10。

## Evidence → Finding → Path

### Evidence

#### E-001
- title: 批 #3 身份、锁与数据层在开批时对齐
- run_id: n/a
- step_or_span_id: `/api/health` + live.lock + dragon_seats 父进程
- native_or_normalized: native
- source_type: environment
- source_ref: `http://127.0.0.1:8792/api/health`；`lsof -nP -iTCP:8792`；`/tmp/r6-batch3-runner.log`；`/tmp/fw4-dragon-seats-2026.log`
- observed_at: 2026-08-15T18:05:27+08:00 开批 / 18:43:09 收批
- raw_excerpt: |
    pid 70403（未换）
    health.source_revision=fdb231148c0e91cd56f7f5d48b5252df80dfafb9
    source_dirty=False  code_matches_repo=True
    loaded_code_root=.../finance-workspace-fdb231148c0e/intelligence
    users_dir=/Users/a77/.local/share/finance-workbench/users
    parent 94429 exited 18:05:27；repair round 2 incomplete=0；FINAL missing=0
    preflight_detail: revision=fdb23114 backend=continuous_glm
      users_dir=.../users data_probe: finance_query=ok
    generated_at=20260815T104309Z  quality_denominator=28  excluded=[]
    BATCH_RC=0  lock released 18:43:09
- observation: 五项盖戳与 handoff 快照一致。同步管道在开批前结束。users_dir 与探针写入 preflight。
- confidence: high

#### E-002
- title: R-23 出数——修复轮携证据 14/15 验收 eb>0，零誊抄哈希拒收
- run_id: 见下表（验收挂上的修复路径）
- step_or_span_id: 各 run 末条 `events[kind=finish]` 与全部 `invalid_action`
- native_or_normalized: native
- source_type: file
- source_ref: `$FORESIGHT_USERS_DIR/linxiaoqi5111/runs/<run_id>/continuous-episode.json`；产物 `cases[].turns[-1].evidence_bound`
- observed_at: 2026-08-15T18:06–18:43+08:00
- raw_excerpt: |
    修复路径 15 条（含 C10 两轮）：
      A2/A5/A9/B1/B2/B3/B5/B7/C1/C6/C7/C9/C10-t0/C10-t2 验收 eb>0
      B8 验收 eb=0 末条 invalid_repair_finish（见 E-006）
    invalid_action 3 条，无 unknown/truncated/evidence hash：
      A5 seq 3 code=bad_status reason=finish status must be completed or partial
      B7 seq 3 code=bad_status（同上，主路径早期格式）
      B8 seq 19 code=no_substantive_answer disposition=invalid_repair_finish
    批 #1 B1/B7、批 #2 B5/C7 的誊抄拒收本窗口 0 次
- observation: 同形修复+取证窗口存在，不是 unobserved。誊抄拒收未再现。B8 是另一码。
- confidence: high

#### E-003
- title: R-25 出数——零 `tool_exception`；既有 tool_error 均为 timeout/budget
- run_id: A10/B1/B2/B3/B4仓外/B8/C9
- step_or_span_id: `events[kind=tool_error]`
- native_or_normalized: native
- source_type: file
- source_ref: 各 `continuous-episode.json`（含验收未挂的 B4 `run_20260815_182037_434217`）
- observed_at: 2026-08-15T18:15–18:39+08:00
- raw_excerpt: |
    17 条 tool_error：error ∈ {tool_timeout, tool_budget_exhausted}，detail=""
    0 条 error=tool_exception
    探针 data_probe.status=ok，A 组 9/10 delivered（A3 clarification）
- observation: 数据层健康时零 `tool_exception` 样本。按预注册 = unobserved，不改 R-25。timeout/budget 的空 detail 不在该预测范围内。
- confidence: high

#### E-004
- title: R-12 live 臂——探针字段在场且成功，未盖污染戳
- run_id: n/a
- step_or_span_id: 产物顶层 `preflight_detail` / `data_probe` / `window_contamination`
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/eval/runs/20260815T1005Z-r5-clean-baseline-3.json` 顶层
- observed_at: 2026-08-15T10:43:09Z（`generated_at`）
- raw_excerpt: |
    preflight_ok=true
    preflight_detail=... data_probe: finance_query=ok
    data_probe_ok=true
    window_contamination=null
    data_probe={tool:finance_query,status:ok,elapsed_ms:994,row_count:1,served_date:2026-08-14}
- observation: 探针字段在场。成功路径不盖 `window_contamination`，与「失败才盖戳、静默混批才 refuted」一致。
- confidence: high

#### E-005
- title: B 组 N=3 交付率（R-10 口径，只 `evidence_bound>0`）
- run_id: 三批 B1–B8
- step_or_span_id: 各 case `turns[-1].evidence_bound` / `execution_state_aggregate`
- native_or_normalized: native
- source_type: file
- source_ref: `20260814T1926Z-r3-clean-baseline.json`（`sha256=b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`）；`20260815T0302Z-r4-clean-baseline-2.json`（`sha256=51e617100b4a72dcd58109c21d685d25b5a4ccae9c0e34507db494ee87304ef4`）；`20260815T1005Z-r5-clean-baseline-3.json`（`sha256=e475f3c889946b2ef87507ca303effa5bf9a1ca153821009f60e6b4edaf1ebf0`）
- observed_at: 2026-08-15T10:43:09Z
- raw_excerpt: |
    B1  #1 eb=0 retrieved_unsynthesized  #2 eb=2 delivered   #3 eb=2 delivered    2/3
    B2  #1 eb=5 delivered                #2 eb=6 delivered   #3 eb=4 delivered    3/3
    B3  #1 eb=13 delivered               #2 eb=0 no_hash     #3 eb=10 delivered   2/3
    B4  #1 eb=2 delivered                #2 eb=2 delivered   #3 eb=0 unknown      2/3
    B5  #1 eb=3 delivered                #2 eb=0 retrieved_unsynthesized #3 eb=16 delivered 2/3
    B6  #1 eb=0 clarification            #2 eb=0 clarification #3 eb=0 clarification 0/3
    B7  #1 eb=0 retrieved_unsynthesized  #2 eb=14 delivered  #3 eb=7 delivered    2/3
    B8  #1 eb=17 delivered               #2 eb=17 delivered  #3 eb=0 retrieved_unsynthesized 2/3
    并行 efh@#3（不结案）：B1=2 B2=3 B3=3 B4=null B5=2 B6=null B7=2 B8=0
- observation: 交付成员继续换人（B5 0→16，B8 17→0）。B6 三批皆澄清。不得把「本批 B8 失败」写成稳定结论。
- confidence: high

#### E-006
- title: R-09——末条 finish 拒收字段在场；B8 有拒收且码非空
- run_id: 21 个验收挂上的 episode；B8 `run_20260815_182902_790837`
- step_or_span_id: 末条 `finish.payload.rejection_code` / `rejection_reason`（多条 finish 取末条）
- native_or_normalized: native
- source_type: file
- source_ref: `$FORESIGHT_USERS_DIR/linxiaoqi5111/runs/<run_id>/continuous-episode.json`；B8 seq 15 与 seq 21
- observed_at: 2026-08-15T18:30:13+08:00（B8 seq 19/21）
- raw_excerpt: |
    21/21 末条 payload 含 rejection_code + rejection_reason；缺字段 0
    20 题 code=none reason=""
    B8 首条 finish seq 15: stop=deadline_exhausted code=none reason="" nbind=0
    B8 末条 finish seq 21: stop=invalid_repair_finish status=partial
      rejection_code=no_substantive_answer
      rejection_reason=required output lacks substantive answer: scenario_range
      bindings=0 draft=0 outcome.evidence=16
    验收 JSON 无 finish 嵌套（字段在 run 目录，不在批摘要）——与 trace-profile §2 一致
- observation: 无拒收时为 none/空；有拒收时码与原因非空。B8 即「下一个该形状 turn」。
- confidence: high

#### E-007
- title: RU-3——`efh ≠ eb` 13 题与 `gap_output_ids`
- run_id: 见摘录
- step_or_span_id: 产物 `turns[-1].episode_fulfilled_hashed` vs `evidence_bound`；episode `semantic_verifier.gap_output_ids`
- native_or_normalized: native
- source_type: file
- source_ref: 批 JSON `cases[]`；各 episode
- observed_at: 2026-08-15T10:43:09Z
- raw_excerpt: |
    efh≠eb (13): A2 5/3 A7 2/9 A8 3/14 A9 2/16 A10 2/3
      B2 3/4 B3 3/10 B5 2/16 B7 2/7 C1 2/16 C6 2/16 C7 5/10 C9 3/2
    gap_output_ids:
      A5 ['evidence_boundary'] eb=2
      B1 ['chain_mapping','counterpoint'] eb=2
      B2 ['chain_mapping','counterpoint'] eb=4
      B3 ['direct_assessment'] eb=10
      B7 ['evidence_boundary'] eb=7
      C7 ['scenario_paths','invalidation_conditions'] eb=10
      C10-t2 ['evidence_boundary'] eb=2
    逐格 slot_shapes: clean 49 / no_hash 1（B1 chain_mapping）/ gap_zeroed 0
- observation: 两套仪器继续分道。本批没有 B3#2 那种「gap 已 fulfilled 格 + eb=0」。R-24 未实现，不开 L0。
- confidence: high

#### E-008
- title: B4 验收 timeout，仓外 episode 已交付
- run_id: `run_20260815_182037_434217`（产物未挂）
- step_or_span_id: 产物 B4 turn vs 该 run 末条 finish seq 50
- native_or_normalized: native
- source_type: file
- source_ref: 批 JSON `B4-fermentation-trace`；`$FORESIGHT_USERS_DIR/linxiaoqi5111/runs/run_20260815_182037_434217/{run.json,continuous-episode.json}`
- observed_at: 2026-08-15T18:20:37–18:25:39+08:00
- raw_excerpt: |
    产物: status=timeout elapsed_s=300.3 run_id=null eb=0 efh=null aggregate=unknown
    run.json: status=completed created=18:20:37 finished=18:25:39（约 302s）
    末条 finish seq 50: repair_model_stop rejection_code=none
      bindings 3 格 hashed（direct_assessment 5 / chain_mapping 12 / counterpoint 6）
      outcome.evidence=116 draft=518
    该 run 6 条 tool_error 亦为 timeout/budget，无 tool_exception
- observation: 验收 300s 墙切在 run 收尾之后。R-10 仍读产物 eb=0。
- confidence: high

#### E-009
- title: 五态按轮 tally + last_turn aggregate；C10 三轮
- run_id: 本批 28 题 / 30 轮
- step_or_span_id: 产物顶层汇总
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/eval/runs/20260815T1005Z-r5-clean-baseline-3.json`
- observed_at: 2026-08-15T10:43:09Z
- raw_excerpt: |
    execution_state_aggregate_rule=last_turn
    tally(按轮, 30): delivered 22 / clarification 6 / retrieved_unsynthesized 1 / unknown 1
    case_tally(28): delivered 21 / clarification 5 / retrieved_unsynthesized 1 / unknown 1
    source: episode_artifact 21 / api_only 8 / unknown 1
    C10: t0 delivered/episode eb=16 efh=2；t1 clarification/api_only eb=0；
         t2 delivered/episode eb=2 efh=2；aggregate=delivered
- observation: 按轮与按 case 差 1 个 delivered / 1 个 clarification，正好是 C10 中间澄清轮。unknown=B4 验收 timeout。
- confidence: high

### Findings

#### F-001
- title: B8 `invalid_repair_finish` + `no_substantive_answer`（与誊抄哈希不同形）
- status: candidate
- failure_span_id: B8 末条 `finish` seq 21
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
- evidence_ids: [E-006]
- confidence: medium
- explanation: 见 PRIMARY。拒收码已落盘，本轮不定 L0。

#### F-002
- title: B4 验收 timeout 丢掉已完成 episode
- status: validated
- failure_span_id: 产物 B4 turn
- root_location: 验收 300s 墙 vs run 收尾
- l0: UNCLEAR
- l1: stop
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A1
- violated_authority: none
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-008]
- confidence: high
- explanation: 见 E-008。不改 R-10 口径。登记为观测，本轮不修。

### Path

#### P-001
- title: B8 的 16 条证据为何到不了交付面
- start: 工具取证成功，`outcome.evidence`=16
- goal: `evidence_bound > 0`
- steps:
  1. 取证成功，16 条进入 episode — evidence: E-006 — finding: none
  2. 首条 finish `deadline_exhausted`、code=none、bindings=0 — evidence: E-006 — finding: none
  3. 修复轮 `invalid_action`（`no_substantive_answer`）后末条 `invalid_repair_finish`，`bindings=0` `draft=0` — evidence: E-006 — finding: F-PRIMARY (F-001)
  4. 无绑定 → 交付层 0 — evidence: E-005 — finding: none（按设计）
- residual_uncertainty:
  - RU-1：R-25 本窗口零 `tool_exception`，live 臂 unobserved。
  - RU-2：13 题 `efh ≠ eb`；R-24 未实现，不开 L0。
  - RU-3：B4 验收 timeout 与仓外已交付 episode 分道；R-10 不改口径。

## self_report_vs_observed 对账

| 事项 | 人类可读输出（自述） | 机器状态字段（观测） | 判定 |
|---|---|---|---|
| B8 是否完成 | 验收台 `status=completed` | 末条 `invalid_repair_finish`、`bindings=0`、`evidence_bound=0` | **冲突**：`completed` ≠ 质量门通过（已知陷阱） |
| B4 是否跑完 | 验收台 `status=timeout` / 无 run_id | 仓外 `run.json status=completed`、末条三格 hashed | **冲突**：300s 墙切在收尾后；R-10 用产物 |
| C4/C5 是否交付 | 降级文案多条 | `execution_state=delivered` `api_only` eb=24/22 | **冲突**：有证据无 episode；质量看 eb |
| C10 五态 | 末轮 delivered | tally 含中间 clarification，aggregate=`delivered` | **一致**（R-11 口径） |
| 批是否有基础设施失败 | 28/28 打印（B4 为 timeout） | `quality_denominator=28`、`BATCH_RC=0`、`not_run` 未单列 | 一致：timeout 题仍进分母 |

按 source precedence：R-10 看产物 `evidence_bound`；B4/B8 冲突两套都保留。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260815-09 | F-001 | `HARNESS_FIX` | （已登记，本轮回填）finish 级拒收码已在新快照上 | 该形状 turn 原因码非空——B8 已见 | 字段存在性：无拒收=`none`/空 |
| R-20260815-10 | F-002 的对照 | `EVAL_ONLY` | （已登记，本轮结案）B 组只报交付率，带批次数 N=3 | 三批 sha256 可复核；单批名单可打回 | 看板结论字段必须带 N |
| R-20260815-12 | — | `EVAL_ONLY` | （已 Closed）live 臂保持 | 探针失败而无顶层标注才 refuted | 成功路径不得盖污染戳 |
| R-20260815-23 | E-002 | `DATA_CONTRACT_FIX` | 本轨只出数，不写 A 行 | 见 E-002；outcome 归 A/检阅方 | 零同形才 unobserved——本批不是 |
| R-20260815-25 | E-003 | `HARNESS_FIX` | 本轨只出数；零样本不改口 | 下一次 `tool_exception` 再判 detail | 健康窗口零样本 ≠ confirmed |

本轮不新开账本 ID。B4 仪器分道进 Residual uncertainty，不升格为预测。

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| RU-1 零 `tool_exception` | R-25 live 臂 | 下一次数据层故障窗口的 `tool_error.error` + `detail` 是否空 | 已有事件字段 | `detail=""` → refuted；`ClassName: …` 且无 `/Users/` → 可收口 | 低（等自然故障，不造） |
| RU-2 `efh ≠ eb` / R-24 | 13 题两套仪器差 | 无需新埋点：R-24 落地前并行读 `gap_output_ids` ∩ fulfilled | episode | 是否再现 B3#2 分道 | 低 |
| RU-3 验收 timeout 丢 run_id | B4 算不算交付 | 超时后若 run 目录已存在则回填 `run_id`；或把 timeout 与「无 run」分开 | 验收台收尾 | 墙切在收尾后不再把已完成 episode 读成 unknown | 中 |

## Limits and counterevidence

- **不开 B8 根因分诊**（本轮指派是六项读数）。拒收码只作 R-09 样本与形状记录。
- **R-23 / R-25 / R-24 不写 A 的 outcome**。本报告 closure 标 still_pending / unobserved。
- **R-10 不改口径**。B4 仓外 episode 已交付，不把 N=3 改成 3/3。
- **R-21 不归本报告**。本批只出数：末条 `caveat_slips>0` 的 case **7 个**（A2=1 A5=1 A6=2 B1=2 B2=3 B3=3 C9=2）；`gap_zeroed` **0** 格（连续三批）；no_hash **1** 格（B1 `chain_mapping`）。
- A 组本批 9/10 delivered，相对批 #2 的数据层塌方是描述性对照，**不**另立「A 组失败名单」。A3 是 clarification。
- 未碰 `intelligence/` 代码。8792 未切。S7 生产未部署。
- 未读取 skill 受控验收目录。

## Next-step menu

1. 检阅方按 E-002 回填 R-23（本轨建议：同形窗口存在且誊抄拒收未再现，但 outcome 不由本轨落）。
2. R-25 等下一次真实 `tool_exception` 窗口，不要为收口去造数据层故障。
3. R-24 仍等独立部署窗；本批 13 题 efh≠eb 作对照，不修。
4. B4 验收 timeout 是否回填 run_id：用户/检阅方排期，本轮不修。
5. B8 `no_substantive_answer` 若要定 L0，另开一轮 M1，不要绑进本批收口。

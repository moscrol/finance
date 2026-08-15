# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M1
- failure_criterion: 任务 1+2 必须离线可证伪（探针失败盖污染戳；`episode_fulfilled_hashed` 与 `evidence_bound` 并行且 B3#2 两值不等）。任务 3（批 #3 / R-10 N=3 / R-23 after / R-09 回填）仅当 8792 已切到含 `2e50e263` 的干净快照、且数据探针 ok 或用户明确接受污染窗口时才开；旧身份上开批视为假测 R-23。
- trace_coverage: 离线夹具 + 本机 `probe_finance_query_data` 实跑 + `/api/health` / 快照 git / pid。**缺**：批 #3 产物（未开）。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: high

## Prior prediction closure

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 轨道 B Round 5 本 PR | R-20260815-12 | 探针失败的批必须一眼可识别为污染窗口；静默混批即 refuted。`episode_fulfilled_hashed` 与 eb 并存且 B3#2 两值不等 | confirmed | E-002, E-003 | 离线负/正夹具已锁仪器。live 若探针失败而无顶层标注，按原文 refuted |
| 轨道 B Round 3 | R-20260815-10 | 连续 3 批按题给出 N 次中的交付次数；单批失败名单可打回 | still_pending | E-001 | N 仍为 2。本轮不开批 #3，不结案、不写单批名单 |
| 轨道 B Round 3 | R-20260815-09 | 下一个该形状 turn 的 finish 拒收原因码非空；≥3 同形才结案 | still_pending | E-001 | 8792 仍是 `cb09f895`，finish 级字段未部署。单次不得结案 |
| 轨道 A Round 4 | R-20260815-23 | 部署后下一批：修复轮携证据应收出绑定且 eb>0；再出现 truncated/unknown hash 则 refuted | still_pending | E-001 | **只出部署门读数，不写 A 的行**。旧快照上跑 after 会假证伪 |
| 轨道 B Round 2 | R-20260815-04 | `draft_source` 埋点 | still_pending | 无 | 本轮未做（A 缝相邻） |
| 轨道 B Round 2 | R-20260815-03 | 两套 output 判定对账 | still_pending | 无 | 本轮无新证据 |
| 2026-08-04 | R-20260804-10 | deadline-aligned per-tool handoff… | still_pending | 无 | 本轮无新证据 |
| 2026-08-04 | R-20260804-02 | 真 Codex rollout 归一化 | still_pending | 无 | 本轮无新证据；无新证据保持 pending |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `EVAL_ONLY`=0；`HARNESS_FIX`=1（R-09 仍 pending）。

## Executive finding

批 #3 按门未开：8792 仍是 `cb09f895` / pid 30091 / porcelain 空 / tool60，main 虽已含 `2e50e263`（#24）但未部署。在此身份上跑 after 会假证伪 R-23。任务 1+2 已落地：失败处置写死 `run_and_flag`，产物顶层盖 `window_contamination`；B3#2 夹具 `episode_fulfilled_hashed=2` ≠ 冻结 `evidence_bound=0`。此刻 DuckDB 探针 `ok`（768ms / 1 行 / served_date=2026-08-14），不代替用户切快照。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| configure | 8792 与 main 对齐（含 #24 序号契约）后开批 #3 | `source_revision=cb09f895`，快照 porcelain=0，pid 30091 未换 | **fail**（部署门） | E-001 |
| retrieve | 开批前数据源冒烟 | 进程内 `FinanceQuery` `market_daily` limit=1 → `ok` | ok | E-004 |
| observe | 探针结果进产物顶层 | 离线：失败 → `window_contamination=finance_query`；未探测不盖戳 | ok（仪器） | E-002 |
| synthesize | 每 turn 并行 `episode_fulfilled_hashed` | B3#2：2 vs eb=0，两字段并存不覆盖 | ok（仪器） | E-003 |
| stop | R-10 N=3 / R-23 after / R-09 回填 | 未开批，三行仍 pending | missing | E-001 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| 8792 身份 `cb09f895` vs main `576bf26e`（含 `2e50e263`） | HARNESS | configure | execution-error-category-environment | health `source_revision=cb09f895734a…`；快照 `git log -1=cb09f895` porcelain=0；pid 30091；`ASK_TOOL_BATCH_TIMEOUT=60` | high |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 8792 已切到含证据序号契约的快照 | 若成立，`source_revision` 含 `2e50e263` 或其后继 | E-001 | **REJECTED** | — | 现读 `cb09f895`；pid 未换 |
| H2 | 可在旧快照上跑批 #3 而不假测 R-23 | 若成立，旧身份 finish 已带 `rejection_code` 且模型上下文已是 E1..En | E-001 | **REJECTED** | — | #24 在 main 不在 8792；handoff 写明 after 前提是新快照 |
| H3 | 任务 1+2 的离线夹具足以确认 R-12 | 若成立，探针失败不中止且产物带污染戳；B3#2 两字段不等 | E-002, E-003 | **CONFIRMED** | — | 64 测绿；处置常量写死 `run_and_flag` |
| H4 | 此刻数据层仍全面宕（批 #2 窗口形状） | 若成立，本机 `probe_finance_query_data` 非 ok | E-004 | **REJECTED**（仅此刻） | — | 探针 `ok` / 1 行 / 768ms。不保证批中段不再 `tool_exception` |

## Causal findings

### PRIMARY

- failure_span_id: 8792 `/api/health` `source_revision=cb09f895`（pid 30091）
- root_location: 生产快照未切到已合入 main 的 #24（`2e50e263`）
- excerpt: `source_revision=cb09f895734a65a38ae23f04d940f18ece2959fd`；`loaded_code_root=.../finance-workspace-cb09f895734a/intelligence`；porcelain=0；main 已是 `576bf26e` 且 `2e50e263` 为其祖先
- l0: HARNESS
- l1: configure
- l2: execution-error-category-environment
- l3: A1
- causality: PRIMARY_FAILURE
- propagation_impact: [NO_PROPAGATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001]
- explanation: 批 #3 的 R-23 after / R-09 回填依赖新快照 finish 字段与序号契约。旧身份上跑会把「字段不存在 / 仍抄哈希」读成修复无效。按门停住，不是 runtime 回归。

### SECONDARY

- failure_span_id: R-10 N 仍为 2
- root_location: 缺第 3 个同口径 qc28 窗口
- excerpt: 批 #1 `sha256=b712bd2e…d8d350`；批 #2 `sha256=51e61710…304ef4`；无批 #3
- l0: UNCLEAR
- l1: stop
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A1
- causality: SECONDARY_FAILURE
- propagation_impact: [NO_PROPAGATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001]
- explanation: 预测写死 N=3。本轮正确停住，不把 N=2 表升级成结案。

## Evidence → Finding → Path

### Evidence

#### E-001
- title: 8792 仍是 `cb09f895`；main 已含 #24 但未部署
- run_id: n/a
- step_or_span_id: `/api/health` + 快照 git + `lsof :8792`
- native_or_normalized: native
- source_type: environment
- source_ref: `http://127.0.0.1:8792/api/health`；`~/.finance-runtime/finance-workspace-cb09f895734a`
- observed_at: 2026-08-15T12:15+08:00
- raw_excerpt: |
    health.status=healthy  source_revision=cb09f895734a65a38ae23f04d940f18ece2959fd
    source_dirty=false  code_matches_repo=true
    loaded_code_root=.../finance-workspace-cb09f895734a/intelligence
    git log -1 = cb09f895  porcelain=0
    pid=30091  ASK_TOOL_BATCH_TIMEOUT=60  backend=continuous_glm
    FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users
    gitea/main=576bf26e  2e50e263 ancestor=YES  a79b1a8e ancestor=YES
    live-lock=/tmp/finance-8792-live.lock  absent
- observation: 五项身份与批 #1/#2 同一进程。R-23/R-09 after 的代码在 main，不在 8792。
- confidence: high

#### E-002
- title: 探针失败不中止；产物顶层盖污染戳；未探测不盖戳
- run_id: n/a（离线）
- step_or_span_id: `preflight` / `cmd_run` 顶层字段
- native_or_normalized: native
- source_type: test
- source_ref: `test_preflight_probe_failure_does_not_abort`；`test_run_stamps_window_contamination_when_probe_failed`；`test_run_output_writes_exact_requested_path`
- observed_at: 2026-08-15T12:15+08:00
- raw_excerpt: |
    DATA_PROBE_ON_FAILURE=run_and_flag
    探针 tool_exception → preflight ok=True
      preflight_detail 含 data_probe: finance_query=tool_exception
      产物 window_contamination=finance_query  data_probe_ok=false
    未探测（preflight stub）→ data_probe=null  data_probe_ok=null  window_contamination=null
    缺库 → status=tool_exception detail=db_missing
- observation: 静默混批路径被负夹具锁死。users-dir 错配仍是阻断项，探针失败不是。
- confidence: high

#### E-003
- title: B3@批#2：`episode_fulfilled_hashed=2` 与冻结 `evidence_bound=0` 并存且不等
- run_id: `run_20260815_111907_054023`
- step_or_span_id: `outcome.bindings` ∩ structural `fulfilled` vs 产物 `evidence_bound`
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/tests/fixtures/b3-r4-batch2-episode.json`；`20260815T0302Z-r4-clean-baseline-2.json` B3 `turns[-1]`
- observed_at: 2026-08-15T12:15+08:00
- raw_excerpt: |
    fixture: direct_assessment hashes=3 fulfilled；chain_mapping hashes=8 fulfilled
             counterpoint hashes=0 missing
    _read_episode_facts.episode_fulfilled_hashed=2
    冻结批 JSON B3 evidence_bound=0（无 episode_fulfilled_hashed 键；旧产物缺失 ≠ 0）
    TurnTrace 两字段同时在场且 2 ≠ 0
- observation: R-10 交付率仍按冻结的 `evidence_bound>0`。本字段不改口。E-007 M1 仍归 A。
- confidence: high

#### E-004
- title: 此刻 DuckDB 层 `finance_query` 冒烟为 ok
- run_id: n/a
- step_or_span_id: `probe_finance_query_data(finance_root)`
- native_or_normalized: native
- source_type: environment
- source_ref: `intelligence/eval/acceptance.py` `probe_finance_query_data`；health `finance_root`
- observed_at: 2026-08-15T12:15+08:00
- raw_excerpt: |
    status=ok  row_count=1  elapsed_ms=768  served_date=2026-08-14
    window_contamination=None
- observation: 批 #2 A 组窗口内 `tool_exception` 此刻未再现。探针只盖开批瞬间，不保证批中段。用户前置②未书面「接受污染」；①未齐，仍不开批。
- confidence: high

### Findings

#### F-001
- title: 批 #3 被部署门挡住（8792 ≠ main 上的序号契约）
- status: validated
- failure_span_id: 8792 `source_revision=cb09f895`
- root_location: 生产快照未切换
- l0: HARNESS
- l1: configure
- l2: execution-error-category-environment
- l3: A1
- violated_authority: protocol
- causality: PRIMARY_FAILURE
- propagation_impact: [NO_PROPAGATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001]
- confidence: high
- explanation: 见 PRIMARY。按 handoff 停住。

#### F-002
- title: R-12 仪器离线成立（污染戳 + 并行字段）
- status: validated
- failure_span_id: `cmd_run` 产物顶层 / `TurnTrace.episode_fulfilled_hashed`
- root_location: `intelligence/eval/acceptance.py`
- l0: HARNESS
- l1: observe
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- violated_authority: none
- causality: SECONDARY_FAILURE
- propagation_impact: [NO_PROPAGATION]
- failure_detection_timing: IMMEDIATELY_AT_OCCURRENCE
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002, E-003]
- confidence: high
- explanation: 不是故障，是本轮要落地的量具。F-002 不定叶：它描述仪器就位，不是环境失败的第二次显影。

### Path

#### P-001
- title: 为何本轮没有批 #3 读数
- start: main 已含 #24+#25+#26（`576bf26e`）
- goal: 同 qc28 批 #3 + R-10 N=3 表 + R-23/R-09 回填
- steps:
  1. 任务 1+2 离线落地（R-12 confirmed）— evidence: E-002, E-003 — finding: F-002
  2. 读 8792 身份仍为 `cb09f895` / pid 30091 — evidence: E-001 — finding: F-001
  3. 按门不开批；R-10/R-09/R-23 保持 pending — evidence: E-001 — finding: none
- residual_uncertainty:
  - RU-1：R-10 缺第 3 批，N=2 不能结案。
  - RU-2：R-23 after 未测（旧快照会假证伪）。
  - RU-3：R-09 finish 级字段在场性未 live 回填。
  - RU-4：开批瞬间探针 ok 不保证批中段不再 `tool_exception`。

## self_report_vs_observed 对账

| 事项 | 人类可读输出（自述） | 机器状态字段（观测） | 判定 |
|---|---|---|---|
| 8792 是否已是「新快照」 | main 含 #24，handoff 写 `788afd4e` | health `source_revision=cb09f895`，pid 30091 | **冲突**：仓已前进，进程未切。以 health/pid 为准 |
| 数据层是否仍全面宕 | 批 #2 A 组 `tool_exception` | 此刻探针 `ok` / 1 行 | **冲突**：窗口故障 ≠ 此刻仍宕。开批仍盖戳 |
| 任务 3 是否失败 | 未交付 N=3 表 | 未创建 live-lock、无 `*-r5-clean-baseline-3.json` | **一致**：按门未跑，不是跑失败 |

按 source precedence：部署身份看 health + 快照 git，不看 main tip。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260815-12 | F-002 | `EVAL_ONLY` | （本 PR 已关）探针盖戳 + `episode_fulfilled_hashed` | 探针失败批顶层必有 `window_contamination`；B3#2 两字段 2≠0 | 本 PR 四条夹具；冻结批 JSON 未改 |
| R-20260815-10 | F-001 | `EVAL_ONLY` | 用户切快照后再跑批 #3，出 N=3 表 | 结论引用三批 sha256；单批名单可打回 | 看板/报告必须带 N |
| R-20260815-09 | F-001 | `HARNESS_FIX` | 新快照批上回填 finish `rejection_code`/`rejection_reason` 在场性 | 有拒收时非空；≥3 同形才结案 | 单次读数不得关 |
| R-20260815-23 | F-001 | `DATA_CONTRACT_FIX` | （A 的行）B 只在新快照批上出数 | 修复轮携证据应 eb>0；再出现 truncated hash → refuted | 本轨道不改该行 |

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| RU-1 缺批 #3 | R-10 结案 | 第 3 份 qc28 的 B 组 `evidence_bound>0` 次数 | 验收台产物 | N=3 交付率 | 中 |
| RU-2 旧身份 | R-23 after | 8792 `source_revision` 含 `2e50e263` 之后再测 | `/api/health` | 序号契约是否进入修复轮 | 低 |
| RU-3 finish 字段 | R-09 回填 | 末条 finish `rejection_code` 键在场（无拒收=`none`） | episode `finish.payload` | 字段存在 vs 仍只有自由文本 | 低 |
| RU-4 批中段数据层 | A 组是否再被污染 | 开批戳 + 批内首个 `finance_query` 例外是否出现 | 探针顶层 + trace | 窗口污染 vs 代码回归 | 低 |

## Limits and counterevidence

- **未开批 #3**。无新 sha256，R-10 不结案，R-23 不出 after 数，R-09 不回填。
- **不改 R-23 / R-21**。E-007 M1 仍归 A，本轨道不动 `episode_protocol.py`。
- 探针走验收台进程内 `FinanceQuery`，不经 8792 工具包装（那是 A 缝的 `tool_exception` detail）。
- `trace-profile.md` 删了一行残留的 `<<<<<<< HEAD`（检阅方双保留 rebase 漏标）；A/B 各行均保留。
- 未读取 skill 受控验收目录。
- `R-20260804-02` / `-10` / `-03` / `-04` 无新证据，保持 pending。

## Next-step menu

1. 用户把 8792 切到含 `2e50e263` 的干净快照（main 现 `576bf26e`），porcelain 空，新 pid。
2. 开批前再跑一次 `probe_finance_query_data`；ok 或用户书面接受污染窗口后，live-lock 跑 qc28 批 #3。
3. 用三批 sha256 出 R-10 N=3 表并按行结案；禁止单批失败名单。
4. 在新快照批上给 A 出 R-23 读数（修复轮绑定性、eb、是否再出现 truncated hash）；B 不判。
5. 回填 R-09：末条 finish 的 `rejection_code`/`rejection_reason` 在场性；≥3 同形才 confirmed。
6. `R-20260815-04` 仍等 R-09 落地后再单独动相邻缝。

---

## 轮次小结 · Round 5 轨道 B

- **任务 1**：`finance_query` 冒烟写入 `preflight_detail`；失败写死 `run_and_flag`，顶层 `window_contamination`。R-12 离线 confirmed。
- **任务 2**：`episode_fulfilled_hashed` 与 eb 并行。B3#2 夹具 2 ≠ 0。冻结批 JSON 未改。
- **任务 3 未开**：8792 仍 `cb09f895` / pid 30091 / tool60。main 已含 #24，未部署。旧身份跑 after 会假证伪 R-23。
- **数据层此刻**：探针 `ok`（768ms / served_date=2026-08-14）。不代替切快照。
- **账本**：R-12 → Closed。R-10/R-09/R-23/R-03/R-04/R-04-10 仍 pending。不改 A 的行。
- **测**：`test_acceptance_{board,execution_state,runs}` 64 passed；ruff 绿。
- **母本**：补录 Round 4 B 小结 + 本轮小结。

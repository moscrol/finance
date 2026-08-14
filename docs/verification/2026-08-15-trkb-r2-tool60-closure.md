# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_NOT_CONFIRMED
- mode: M2
- failure_criterion: B 组题走完 continuous episode 后，episode 取得的证据应有 ≥1 条到达验收可见面（`evidence_bound > 0`）。基线 `20260813T1810Z-qc28-full.json` 中 B1-B7 全部为 0，B8=11。
- trace_coverage: 三份产物共 19 个 B 组 turn —— Run A `20260813T1810Z-qc28-full.json`（8 题，`sha256=8536c231…578d80`）、Run B `20260814T1446Z-b-rerun-tool60.json`（8 题，`sha256=11dedecc…1b06e8`）、Run B′ `20260814T1813Z-trkb-b136-recheck.json`（B1/B3/B6 三题，本轮补跑，`sha256=75dc34f7…358249`）。**Run B 与 Run B′ 两份产物已随本 PR 进 git**，报告不再引用仓外文件。每题另有 workbench run 目录（`trace.jsonl` / `continuous-episode.json`，仍在仓外）。**缺**：Run A 时点的部署代码内容无法回溯（见混淆因子）。

> **产物命名勘误（2026-08-15）**：B′ 原名 `20260815T1813Z-…`，日期前缀错。成因是
> **run 目录用本地时命名、acceptance 产物用 UTC 命名**，而补跑命令把日期段写死成
> `20260815` 却对时间段取 `date -u +%H%M`——UTC 当时仍是 08-14（18:13Z = 本地 08-15
> 02:13）。产物自身的 `generated_at=20260814T181552Z` 才是准的。已改名对齐。
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: low

## Prior prediction closure

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence（本次 trace 的 E-ID） | implication |
|---|---|---|---|---|---|
| 2026-08-15 轨道 B Round 1 | R-20260815-01 | 重放 19 个 run 目录后 `evidence_bound` 扩为三元组 + `execution_state`：B4 读作 `retrieved=125,bound=0`、B3 读作 `retrieved=0,bound=0`、C2-C10 读作 `not_run`，三者不再同码 | confirmed | E-005 | 量具已可分辨四态，本报告的形状迁移表即用它读出 |
| 2026-08-15 轨道 B Round 1 | R-20260815-02 | `status=error` 且 `trace_steps=0` 的 turn 不进入任何质量分母；C 组分母由 10 降为 1 | confirmed | E-005 | 分母口径已修，`not_run` 不再冒充业务结论 |
| 2026-08-15 轨道 B Round 1 | R-20260815-05 | 08-03 真 rollout 重过归一化器后 `function_call_output→observe`、`unmapped` 由 264 降至声明目标 ≤60 | confirmed | E-006 | 264→53，`tool`/`observe` 各 42 配平 |
| 2026-08-15 轨道 B Round 1 | R-20260815-04 | `draft_source` 埋点 | still_pending | 无 | 按 Round 2 指派**暂缓**，等轨道 A `episode_protocol` 落地 |
| 2026-08-04 | R-20260804-10 | deadline-aligned per-tool handoff… | still_pending | 无 | 本轮无新证据，Task 3-6 仍未执行 |

- ledger: `docs/prediction-ledger.md`
- fix_type_refuted_streak: `EVAL_ONLY` = **0**（-01/-02/-05 三条 confirmed，按「中间出现 confirmed 即归零」规则，R-20260804-02 那次 refuted 的 streak 已断）；`HARNESS_FIX` = 1（R-09，本轮未变）。

## A/B controls

- invariant inputs: 同一冻结题库的 B 组 8 题、同一 `base=http://127.0.0.1:8792`、同一 `AGENT_RUNTIME_BACKEND=continuous_glm`、同一 `ASK_CONTINUOUS_RUNTIME=on`。
- intentional variable: `ASK_TOOL_BATCH_TIMEOUT` 由 30 改为 60（`~/.local/bin/start-finance-workbench:124`，2026-08-14 18:29 重启生效）。
- uncontrolled confounders（**本轮最要紧的读数，先看这里再看结论**）：
  1. **消融不是单变量。** 部署目录 `.finance-runtime/finance-workspace-07af9160a677` 有 **20 个脏文件**（17 改 + 3 未跟踪），mtime 全为 2026-08-14 **16:42 与 18:29**，而 Run A 的 8 个 run 目录时间戳为同日 **02:19–02:31**。即：这些改动**全部晚于 Run A、早于 Run B**，其中含 `runtime/agent_episode.py`、`runtime/continuous_turn_adapter.py`、`runtime/conversation_orchestrator.py` 三个正落在本失败链上的文件，以及一个**只存在于部署目录、git 中不存在**的新模块 `services/honesty_gates.py`。因此 A→B 之间至少有「工具窗口」与「≥20 个文件的代码改动」两组变量同时变化。
  2. 两份产物的 `preflight_detail.revision` 分别为 `71b50300` 与 `5b456532`，**两者都是错源读数**（`source_revision` 陷阱，母本 §2 Step 3）；真实身份为 `loaded_code_root=07af9160` + 上述脏集合。Run A 时点的脏集合内容**无法回溯证明**。
  3. 模型侧非确定性：同题跨 run 的取证量显著波动（B1 `counterpoint` 绑定哈希数 0→9，B3 `evidence` 16→6）。
- **Run B 与 Run B′ 之间则是干净复制**：同一进程（pid 32482，18:29:34 启动，跨两次跑未重启）、同一份代码（全部脏文件 mtime ≤18:29，23:02 后零改动）、同一窗口值。这一对可用于噪声排除。

| normalized step | Run A（1810Z，窗口 30s） | Run B（1446Z，窗口 60s） | comparison | causal prediction |
|---|---|---|---|---|
| configure | `configure`，registry 7 | 同 | same | — |
| intent | `controller` → `theme_analysis` | 同 | same | 路由不是变量（与 rerun-todo §7 禁令 3 一致） |
| tool | B1 5 请求/3 结果/2 错误 | B1 请求增多、错误减少 | diverged | 窗口放宽应减少工具饿死 |
| observe | B1 `outcome.evidence`=19 | B1=19、B3 由 0 → 16 | diverged | B3 的检索侧确由窗口修复 |
| synthesize | B1/B2/B4 `draft=""`、`bindings=0` | 八题 draft 均非空、bindings≥2 | **diverged** | 合成侧全面恢复 |
| stop | B1-B7 eb=0 | B2/B4/B5/B7/B8 eb>0；B1/B3 仍 0 | diverged | 五题交付恢复，两题未恢复 |

- ablation_activation_step: `tool` —— 窗口值在工具批次执行处生效，实测 B3 检索由 0 条变 16 条、八题 draft 由三题空变全部非空，机制确已装上。
- first_divergence_step: `tool`
- first_divergence: n/a（两侧在 `tool` 步同为 `tool`，差异是同一 step 内的结果量，非两侧走了不同 step）
- first_failure_step: `synthesize`（B1/B3：绑定生成时即已附 gap，该 gap 决定后续归零）
- failure_surfaced_step: `stop`（验收面直到 `evidence_bound=0` 才暴露；trace 时间线上两次输出「研究回答已形成」）
- reconvergence_step: `stop`（B2/B4/B5/B7/B8 五题在此汇合到 eb>0；B1/B3 未汇合）
- pre_divergence_equivalence: `configure`/`intent` 两步两侧逐字段一致（question_type、owner、registry 规模），构成分叉前等价证据。
- downstream_propagation: B1/B3 的 gap 在 `synthesize` 生成后经 `_public_citation_projection` 过滤 → `citations` 空 → `continuous:evidence` 步不发射 → 交付层 0 条。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| tool | 60s 窗口下工具不再饿死 | B3 检索 0 → 16 条 | ok | E-001 |
| observe | 证据进入 `outcome.evidence` | B1=19、B3=16 | ok | E-001 |
| synthesize | 产出 draft 并绑定到必需输出 | B1/B3 draft 有、bindings=3、**三格全带 gap** | **fail** | E-002, E-003 |
| stop | 绑定证据到达验收面 | 三格判 `missing`、`evidence_ids=0`、eb=0 | fail | E-002 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `run_20260815_...` B1 / `outcome.bindings` | UNCLEAR（竞争项：REASONING 生成了 gap vs HARNESS 判据零化） | synthesize | DEPTH_INSUFFICIENT(D4) | `direct_assessment n_hash=1 gap=有` / `[struct] status=missing evidence_ids=0` | medium |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | 30s 工具窗口是 B 组卡点的单一根因 | 若成立，窗口改 60s 后 B 组 8/8 转 eb>0 | E-001, E-004 | **REJECTED** | — | 实测 5/8（B2/B4/B5/B7/B8）。B1/B3 两次复跑均仍为 0，未达 §6 的 ≥6/8 结案线 |
| H2 | B1/B3 剩余失败是单次噪声 | 若成立，同代码同进程再跑一次应有机会转正 | E-003 | **REJECTED** | — | Run B′ 定点补跑：B1/B3 的**结构签名**两次一致（三格绑定全带 gap、全判 missing、`evidence_ids=0`、eb=0），但**哈希数在波动**（B1 `1/6/0` → `1/9/9`，counterpoint 由真缺口变为 9 条可绑证据仍被判缺；B3 `2/8/2` → `3/3/3`）。**取证在抖，归零是恒定的** |
| H3 | B1/B3 的机制与轨道 A 的 F-001（有哈希的绑定附带 gap 被零化）同源 | 若成立，B1/B3 的绑定应「有 `evidence_hashes` 且带 `gap`」，而 eb>0 的对照题应「有哈希且无 gap」 | E-002 | **CONFIRMED** | — | Run B：B1 `1/6/0`、B3 `2/8/2`，全带 gap → 全 missing；Run B′：B1 `1/9/9`、B3 `3/3/3`，同样全 missing；B4 对照 `5/14/7` **gap 全无** → 全 fulfilled。**有哈希且带 gap → missing** 这条判别式在两次跑的 11 个有哈希格上无一例外；B1@Run B 的 `counterpoint`(n=0) 是真缺口不是滑档，属混合形（与 B7 同），不计入该判别式分母 |
| H4 | 五题恢复可归因于工具窗口 | 若成立，A→B 之间除窗口外无其它相关变量 | E-007 | **INCONCLUSIVE** | 冻结部署代码（提交或从干净 commit 重部署）后，仅改窗口值再跑一次同 8 题；H4 预测五题仍恢复，若恢复数明显下降即证伪 | A→B 之间另有 ≥20 个文件改动（含本失败链上的三个 runtime 文件与一个 git 中不存在的新模块），**消融不是单变量**，不能把五题恢复独占归给窗口 |
| H5 | B6 是失败题 | 若成立，B6 应有 episode 产物且证据为零 | E-004 | **REJECTED** | — | B6 在 Run B/B′ 两次均为 2.0s / 4 步 / `gaps=[]` / **无 episode 产物**，落 rerun-todo §5 判据表第 4 行「正常澄清轮」。它不该计入失败分子 |

## Causal findings

### PRIMARY

- failure_span_id: B1 `run_20260814_224652_671640` 与 Run B′ 同题 / `outcome.bindings`
- root_location: 绑定携带 gap 时被结构核验零化的那条缝（轨道 A 的 `episode_protocol` 面）
- excerpt: `direct_assessment n_hash=1 gap=有` → `[struct] direct_assessment status=missing evidence_ids=0`
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002, E-003]
- explanation: B1/B3 已产出 draft、已生成 3 条带哈希的绑定，但三格绑定各自附带一句 gap；结构核验据此判 `missing` 并把 `evidence_ids` 归零，于是 19/6 条证据一条都进不了 `allowed_output_ids`。**竞争 L0 未分胜负**：是模型该给 gap 却本不必给（REASONING），还是判据不该因附带 gap 就整格零化（HARNESS），当前产物无区分变量。轨道 A 的修复正针对后者，**已随 #6 并入 main（`a189d6bd`，原分支提交 `d6f50688`），但尚未部署到 8792**——合并不等于生效，本轮读数仍取自未含该修复的运行时，故不能以它为准结案。

### SECONDARY

- failure_span_id: 部署目录 `.finance-runtime/finance-workspace-07af9160a677`
- root_location: 生产代码身份
- excerpt: `20 dirty (17 modified + 3 untracked)`，含 `services/honesty_gates.py`（git 中不存在）
- l0: HARNESS
- l1: configure
- l2: `execution-error-category-environment`
- violated_authority: system
- causality: SECONDARY_FAILURE
- propagation_impact: [UNCLEAR]
- failure_detection_timing: SILENT_UNDETECTED
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-007]
- confidence: high
- explanation: 检阅方 02:10 记录为「3 个 runtime 文件未提交」，实测为 **20 个**，且其中 `honesty_gates.py` 是整个模块只存在于部署目录。后果不止「不可从 git 复现」：它使任何跨时点 A/B 的消融都无法宣称单变量——本报告的 H4 即因此停在 INCONCLUSIVE。

## Evidence → Finding → Path

### Evidence

#### E-001
- title: 窗口放宽后检索侧确实恢复
- run_id: run_20260814_225106_544685（B3）
- step_or_span_id: `outcome.evidence`
- native_or_normalized: native
- source_type: file
- source_ref: `<FORESIGHT_USERS_DIR>/linxiaoqi5111/runs/run_20260814_225106_544685/continuous-episode.json`
- observed_at: 2026-08-14T22:51+08:00
- raw_excerpt: `B3: Run A evidence=0 → Run B evidence=16；八题 draft 由三题空串变为全部非空`
- observation: ablation 机制已生效，检索与合成两侧都有可观察改善。
- confidence: high

#### E-002
- title: B1/B3 的绑定有哈希但全带 gap，被判 missing 后 evidence_ids 归零
- run_id: run_20260814_224652_671640 / run_20260814_225106_544685
- step_or_span_id: `outcome.bindings` / `structural_verifier.completion.outputs`
- native_or_normalized: native
- source_type: file
- source_ref: 同上两个 run 目录
- observed_at: 2026-08-14T22:46–22:51+08:00
- raw_excerpt: |
    B1 @Run B (run_20260814_224652_671640)
        direct_assessment n_hash=1 gap=有 | chain_mapping n_hash=6 gap=有 | counterpoint n_hash=0 gap=有
        [struct] 三格 status=missing，evidence_ids=0
    B3 @Run B (run_20260814_225106_544685)
        direct_assessment n_hash=2 gap=有 | chain_mapping n_hash=8 gap=有 | counterpoint n_hash=2 gap=有
        [struct] 三格 status=missing，evidence_ids=0
    B4 @Run B 对照 (run_20260814_225217_025230)
        direct_assessment n_hash=5 gap=无 | chain_mapping n_hash=14 gap=无 | counterpoint n_hash=7 gap=无
        [struct] 三格 status=fulfilled，evidence_ids=5/14/7
- observation: 带 gap 与不带 gap 是 `missing`/`fulfilled` 的判别式；B4 三格无 gap 全 `fulfilled`，B1/B3 三格带 gap 全 `missing`。**但 B1@Run B 是混合形，不是纯滑档**：`counterpoint` 的 `n_hash=0`，那是**真缺口**（没有任何证据可绑），与 B7 的 `direct_answer` 同形；只有 `direct_assessment`(1) 与 `chain_mapping`(6) 两格是「有哈希却被 gap 零化」的滑档。B3@Run B 三格哈希均 >0（2/8/2），是纯滑档形。两种形都落在轨道 A 的 F-001 射程内，但修复后的预期不同：滑档格应恢复，真缺口格**本就该判缺**。
- confidence: high

#### E-003
- title: 定点补跑证明归零是确定性的、取证是波动的
- run_id: Run B′ `20260814T1813Z-trkb-b136-recheck.json`
- step_or_span_id: `outcome.bindings`
- native_or_normalized: native
- source_type: file
- source_ref: `intelligence/eval/runs/20260814T1813Z-trkb-b136-recheck.json` 及对应 run 目录
- observed_at: 2026-08-15T18:13Z
- raw_excerpt: |
    B1 Run B′: draft=302 ev=19 bind=3 miss/ful=3/0；n_hash=1/9/9 全带 gap
    B1 Run B : draft=364 ev=19 bind=3 miss/ful=3/0；n_hash=1/6/0（counterpoint 由 0 变 9）
    B3 Run B′: draft=428 ev=6  bind=3 miss/ful=3/0；n_hash=3/3/3 全带 gap
- observation: 同进程同代码两次跑，取证量变化而「全带 gap → 全 missing → eb=0」不变。
- confidence: high

#### E-004
- title: B6 两次均为澄清轮，无 episode 产物
- run_id: run_20260814_225751_611313 与 Run B′ 同题
- step_or_span_id: turn 级
- native_or_normalized: native
- source_type: file
- source_ref: 两份 acceptance 产物与对应 run 目录
- observed_at: 2026-08-14T22:57 / 2026-08-15T18:13Z
- raw_excerpt: `eb=0 completed 2.0s steps=4 gaps=[] 未绑定自述=False；run 目录无 continuous-episode.json`
- observation: 落 rerun-todo §5 第 4 行「正常澄清轮」，非失败。
- confidence: high

#### E-005
- title: 量具重放自证（R-01/-02）
- run_id: 19 个 Round 1 run 目录
- step_or_span_id: `execution_state`
- native_or_normalized: normalized
- source_type: tool_return
- source_ref: `intelligence/eval/acceptance.py` 重放 `20260813T1810Z-qc28-full.json`
- observed_at: 2026-08-15
- raw_excerpt: `delivered 11 / not_run 9 / bound_but_dropped 3 / retrieved_unsynthesized 3 / no_evidence 2；C 组进分母者=['C1-future-date-no-data']`
- observation: 四态可分辨，`not_run` 已退出分母。
- confidence: high

#### E-006
- title: codex mapper 修复读数（R-05）
- run_id: n/a
- step_or_span_id: `normalize_harness_trace` 单输入产物
- native_or_normalized: native
- source_type: tool_return
- source_ref: 输入 `sha256=62385ee5…b316a7`
- observed_at: 2026-08-15
- raw_excerpt: `unmapped 264 → 53；synthesize=127 / tool=42 / observe=42；首个 custom_tool_call_output → observe`
- observation: `tool` 与 `observe` 恰好配平；剩余 unmapped 中 43 个为 `token_count` 遥测。
- confidence: high

#### E-007
- title: 部署代码身份三读数与脏集合时序
- run_id: n/a
- step_or_span_id: `/api/health` + 部署目录 git
- native_or_normalized: native
- source_type: environment
- source_ref: `/api/health` → `loaded_code_root`；`git -C <root> log -1 / status --porcelain`；各脏文件 `stat`
- observed_at: 2026-08-15T02:1x+08:00
- raw_excerpt: |
    health.source_revision=5b456532 (dirty=True)   ← 错源
    loaded_code_root=.finance-runtime/finance-workspace-07af9160a677
    该目录 commit=07af9160，status: 17 modified + 3 untracked = 20
    脏文件 mtime 全为 08-14 16:42 或 18:29；23:02 之后改动数=0
    8792 pid=32482 启动于 08-14 18:29:34（跨 Run B / Run B′ 未重启）
- observation: Run B 与 Run B′ 同身份可比；Run A 早于全部脏改动，与二者不同身份。
- confidence: high

### Findings

#### F-001
- title: B1/B3 的证据被「带 gap 的绑定整格零化」拦在交付层外
- status: candidate
- failure_span_id: B1 `outcome.bindings`
- root_location: 结构核验对带 gap 绑定的处理
- l0: UNCLEAR
- l1: synthesize
- l2: DEPTH_INSUFFICIENT(D4)
- l3: A2
- violated_authority: user
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-002, E-003]
- confidence: medium
- explanation: 见 PRIMARY。与轨道 A 的 F-001 同源（检阅方已跨轨交叉验证 B5/B7/A6 三例），但其修复未部署，本轮不据以结案。

#### F-002
- title: 生产代码身份不可复现，且脏集合规模被低估
- status: validated
- failure_span_id: 部署目录
- root_location: 部署流程
- l0: HARNESS
- l1: configure
- l2: `execution-error-category-environment`
- l3: n/a
- violated_authority: system
- causality: SECONDARY_FAILURE
- propagation_impact: [UNCLEAR]
- failure_detection_timing: SILENT_UNDETECTED
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-007]
- confidence: high
- explanation: 见 SECONDARY。直接后果是本轮 H4 无法结案。

### Path

#### P-001
- title: 窗口修复救回五题、B1/B3 为何没救回
- start: Run A —— 30s 窗口下 B1/B2/B4 连 draft 都没产出
- goal: B 组 8 题证据到达验收面
- steps:
  1. 窗口 30→60，工具不再饿死；B3 检索 0→16、八题 draft 全部非空 — evidence: E-001 — finding: none
  2. B2/B4/B5/B7/B8 绑定不带 gap → 三格 fulfilled → eb>0 — evidence: E-002 — finding: none
  3. **B1/B3 绑定带 gap → 整格判 missing、`evidence_ids` 归零** — evidence: E-002, E-003 — finding: F-PRIMARY (F-001)
  4. 证据被 `_public_citation_projection` 全数过滤 → 交付层 0 条 — evidence: E-002 — finding: none（按设计）
- residual_uncertainty:
  - RU-1：五题恢复中「窗口」与「≥20 个文件改动」各占多少，无法拆分。
  - RU-2：B1/B3 的 gap 是模型本不该给（REASONING）还是判据不该整格零化（HARNESS），缺区分变量。

## self_report_vs_observed 对账

`first_failure_step`（`synthesize`）与 `failure_surfaced_step`（`stop`）不是同一步，按 M2 契约对账；两者的间隔就是本系统的自我报告失真时长。

| 事项 | 人类可读输出（自述） | 机器状态字段（观测） | 判定 |
|---|---|---|---|
| 回答是否形成 | B1 trace 两次输出「研究回答已形成，正在完成最终核验。」 | `structural_verifier` 三格 `missing`、`evidence_ids=0` | **冲突** |
| 证据可否引用 | `semantic_verifier.public_answer`「已取得 N 条证据，但未完成核验绑定」 | `evidence_bound=0` | 一致 |
| 产物盖的是哪份代码 | `preflight_detail.revision=5b456532` | `loaded_code_root=07af9160` + 20 脏文件 | **冲突**，以后者为准 |

失真时长 = 从 `synthesize` 生成带 gap 绑定，到 `stop` 处 `evidence_bound=0` 才暴露，中间全部步骤对操作者显示为成功路径。按 source precedence 以机器字段为准。

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260815-06 | F-002 | `NO_SYSTEM_FIX` | 生产代码身份属用户裁决（补提交或从干净 commit 重部署），执行层不自行处置。**在裁决前，任何跨时点 A/B 都必须显式声明消融不单一**。 | 裁决后 `loaded_code_root` 对应目录 `git status --porcelain` 为空，`/api/health` 的 `source_revision` 与该目录 `git log -1` 一致 | 部署校验脚本对 `loaded_code_root` 跑 `status --porcelain`，非空即拒 |
| R-20260815-07 | F-001 | `EVAL_ONLY` | 把「绑定带 gap」记入 acceptance 的运行态：`bound_but_dropped` 再细分 `gap_zeroed`（有哈希且带 gap）与 `no_hash`（真缺口）。不改判据，只让两者在读数上分开。 | 重放 B1/B3 落 `gap_zeroed`；B7 的 `direct_answer`（0 哈希真缺口）与 `evidence_boundary`（13 哈希滑档）在同一 turn 内分别可见 | 用 B1/B3/B7 三个 run 目录作夹具的单测 |

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| RU-1 窗口 vs 代码改动的贡献拆分 | H4 | 部署身份冻结后重跑一次同 8 题；变量只留窗口值 | 无需埋点，是实验设计 | 五题恢复中窗口的独立贡献 | 中（需用户先裁决脏部署） |
| RU-2 gap 的归属层 | F-001 的 L0 | 绑定落盘补 `gap_origin ∈ {model_declared, verifier_derived}` | `outcome.bindings` 序列化处 | gap 是模型自己写的还是判据推出来的 | 低 |
| 产物盖戳仍用错源字段 | 任何跨 run 比较的身份 | acceptance preflight 改记 `loaded_code_root` + 该目录 `git rev-parse HEAD` + `dirty_count` | `intelligence/eval/acceptance.py:preflight` | 产物自带可核验身份，不必事后重建 | 低 |

## Limits and counterevidence

- **本轮不能宣布 tool60 结案。** 5/8 未达 rerun-todo §6 的 ≥6/8 线；即便把 B6（澄清轮，非失败）移出分子，仍是 5/7。
- **不能把五题恢复独占归给工具窗口**（H4 INCONCLUSIVE）：A→B 之间至少两组变量同时变化。检阅方 02:10 的预读「窗口是五题的根因或主要贡献因」在方向上与本轮一致，但「主要贡献因」这一步在当前证据下**尚不可判**。
- **反证：B5/B7 曾在轨道 A 的 R-001 未部署时自发恢复**，说明该机制含非确定性成分；本轮 B1/B3 两次复现只能说明「在这两题上确定」，不能推广为「该机制整体确定」。
- 与轨道 A 的边界：本报告未读取也未改动 `episode_protocol.py` 与 verifier 判据。
- 检阅方记录的「3 个 runtime 文件未提交」经实测应为 20 个（含一个 git 中不存在的模块），已在 E-007 更正。

## Next-step menu

1. 报用户裁决脏部署（R-20260815-06）——它同时卡着 H4、轨道 A 的 canary 与一切跨时点 A/B。
2. 实施 R-20260815-07：让 `gap_zeroed` 与真缺口在读数上分开，代价低且立刻可用。
3. 轨道 A 的修复（main `a189d6bd`）**部署到 8792 后**，对 B1/B3 重跑一次——那是分开 RU-2 两个竞争 L0 的最短路径。预期：B3（纯滑档形）三格恢复；B1 的 `direct_assessment`/`chain_mapping` 两格恢复而 `counterpoint` 视当次是否取到证据而定（Run B 该格 0 哈希是真缺口，本就该判缺）。
4. `gap_origin` 埋点（表内第 2 行），确定 gap 的归属层。
5. 把 acceptance preflight 的身份盖戳改为 `loaded_code_root` 三读数，消除错源字段。

---

## 轮次小结 · Round 2 轨道 B

- **任务 1（主靶）完成**：`R-20260815-01/-02` 一个 PR 落地（`88befa87`），EVAL_ONLY，只动 `acceptance.py`。两行预测**逐字自证全绿**（用真实 19 个 run 目录重放，非夹具）：B4 `retrieved=125,bound=0`、B3 `retrieved=0,bound=0`、C2-C10 全 `not_run`、三者落三个互不相同的值、C 组分母 10→1。12 条新单测，acceptance 套件 127 passed。字段契约门禁曾拦下 `execution_state_source`「写了没人读」，**补了真实读取点而非加豁免**。
- **任务 2 收口：落 §6 矩阵第 2 行「部分转正、部分仍 0 → 不是单一根因」**。5/8 恢复（B2/B4/B5/B7/B8），未达 ≥6/8 结案线。**与检阅方预读的两处不同**：① B6 不是「另有机制」而是**根本不是失败**——两次跑均为 2.0s/4 步/无 episode 产物，落 rerun-todo §5 第 4 行澄清轮；② B1/B3 的「另有机制」已**具名**：就是轨道 A 的 F-001（带哈希绑定附 gap 被整格零化），判别式 3/3 命中，不是未知新机制。
- **定点补跑排除了噪声**：B1/B3 的结构签名两次一致（全带 gap、全判 missing、eb=0），而哈希数在波动（B1 `1/6/0`→`1/9/9`，B3 `2/8/2`→`3/3/3`）——**取证在抖，归零是恒定的**。B1@Run B 另是混合形（`counterpoint` n=0 为真缺口，与 B7 同形）。
- **身份前提比 handoff 预期更强**：8792 同一进程（pid 32482，18:29:34 起未重启）、全部脏文件 mtime ≤18:29、23:02 后零改动，故 Run B/B′ 是干净复制，补跑可用于噪声排除而非只作新基线。
- **但发现一条更要紧的**：Run A（02:xx）**早于全部脏改动**（mtime 16:42/18:29），所以 A→B 的消融**不是单变量**——窗口之外还有 ≥20 个文件改动，含本失败链上的三个 runtime 文件。故 H4 停在 INCONCLUSIVE，**不能把五题恢复独占归给工具窗口**。
- **更正检阅方记录**：脏文件不是 3 个而是 **20 个**（17 改 + 3 未跟踪），其中 `services/honesty_gates.py` 是整个模块只存在于部署目录、git 中不存在。
- **任务 3 完成**：`R-20260815-05` 独立 PR（`6e1c29ed`），`unmapped 264 → 53`（目标 ≤60），`tool`/`observe` 各 42 配平；剩余 43 个 `token_count` 是遥测，按契约保持 unmapped，补词表是另一变量、刻意不捆绑。
- **暂缓照旧**：`R-20260815-04`（`draft_source`）未动；未碰 `episode_protocol.py` 与 verifier 判据。
- **streak**：`EVAL_ONLY` 三条 confirmed → 归零（0/3）；`HARNESS_FIX` 仍 1。
- **下轮建议**：脏部署裁决是唯一同时卡住 H4、轨道 A canary 和一切跨时点 A/B 的东西，建议优先报用户。

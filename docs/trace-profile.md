# Trace Profile: finance-workspace-private

- last_updated: 2026-08-04
- updated_by_run: `2026-08-04-budget-calibration/a-b-c-d`
- 配套账本：[prediction-ledger.md](prediction-ledger.md) —— 分诊**开工第一步**先回填那里的 pending 预测，再开始新归因

## 1. 产物位置与结构

| 产物 | 路径/glob | 结构 | 关键字段 → 语义 |
|---|---|---|---|
| Acceptance run | `intelligence/eval/runs/*.json` | 一次命令一份 JSON，`cases[].turns[]` | `status` 是 turn 运行态；`degrades` 是用户可见降级；`synthesis_diagnostic` 是合成健康态；`trace_steps` 是粗粒度步骤名 |
| Workbench run | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/` | 每个 run 一个目录 | `run.json` 保存运行元数据；`report.json` 保存结构化报告；`answer.md` 是最终展示正文 |
| Runtime trace | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/trace.jsonl` | 一行一个控制面事件 | `step_id` 是原生定位符；`llm_call_ledger` 记录 provider 调用；`research_execution_budget` 记录 root 预算与工具尝试 |
| Grounded shadow | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/grounded_composer_shadow.json` | 单个 JSON | `status/failure_reason/elapsed_ms` 描述 Grounded 链终态；只在阶段产出存在时保存 brief/raw/judge 内容 |

## 2. 已知字段陷阱

| 字段 | 直觉语义 | 实际语义 | 出处 |
|---|---|---|---|
| `turn.status=completed` | 全部质量门都通过 | 只表示 run 有可交付终态；确定性 fallback 也会 completed | `20260803T082342Z-a4-pre-budget-fix.json:42-106` |
| `elapsed_s` | 精确耗时 | Acceptance 以约 2 秒轮询观测，是量化值；phase `elapsed_ms` 也只能在同一 semantic epoch 内比较 | `intelligence/eval/acceptance.py` 与本文件 §4 |
| `synthesis_diagnostic.phases` | 所有设计阶段 | 只记录真正开始或被明确 skip 的阶段；字段缺失表示没有跑到，不可把缺失当 0ms | `ask_synthesis._record_synthesis_phase` |
| `remaining_ms_at_entry` | turn 根剩余 | Grounded phase 记录的是 `_shadow_deadline` 子链剩余；root 余量在 `research_execution_budget.retrieval.research_budget.remaining_ms` | run `run_20260803_162718_999605` |
| `phase.timeout_s / elapsed_ms` | grant 与自然耗时可直接比较 | 含义随 revision 变化：E0 grant 未执行、E1 每次 retry 各读一份、E2 整个 phase 共享硬墙；必须先按 §4 选解释器 | 6 份 phase artifact + commits `cd175a0e/8ed66020` |
| `continuous_glm` | 使用 GLM 模型 | backend 历史常量名，与模型身份无关；真实模型看 LLM ledger | handoff §1；`trace.jsonl:7` |
| LLM ledger `caller=synthesis` | 可直接区分 brief/composer/judge | 旧 ledger 只给共同 caller，不能按顺序安全反推 phase；必须用新增 phase telemetry | 2026-08-03 用户纠偏与 M1 报告 |
| case `A4-*` | Finance adapter L3=A4 | 验收题编号，与概率校准分类无关 | acceptance cases 与 finance adapter taxonomy |
| `acceptance run` 默认 base | 当前 8801 | 默认曾指向 8799；本项目真实 canary 必须显式 `--base http://127.0.0.1:8801` | handoff §6 |
| benchmark arm `stop_reason` | 运行时的终止原因 | arm 级是**事后裁决**，会被后处理覆盖；事件级 `finish.payload.stop_reason` 才是运行时观测。五题中 `ruihuatai-valuation` 两者不一致：arm=`semantic_repair`，finish 事件=`model_finish` | `e179b15c` receipt；跨 harness 控制面比较必须用事件级 |
| `runtime_invalid_actions:N` | 模型有 N 次动作违规 | **`< 2026-08-04` 的 artifact 里等于 `len(unique_issues)`**，超时/取消/进程失败都被计入。`e179b15c` 两题的 `runtime_invalid_actions:1` 实为 `headless_timeout`，真实违规 0 次。修正后只计 `unauthorized_headless_action` / `tool_call_during_finalization_recovery` / `headless_invalid_finish` | `codex_headless_runtime.count_invalid_actions`；口径对齐 `agent_episode` |
| benchmark 事件 `sequence` 从 2 起跳 | 前两个事件不存在 | `sequence=1` 的 `task` 事件（intent 地标）**被落盘白名单丢弃**，不是没埋点。`< 2026-08-04` 的 artifact 无法补出 intent；此后 `task` 保留但 payload 只留 `task_frame_hash` | `runtime_backend_benchmark._TASK_EVENT_KEEP` |
| benchmark arm `status=degraded` | runtime 没完成 | arm 级 `status` 是语义/后处理质量裁决；同一 arm 的事件级 `finish.payload.status` 可能是 `completed` 或 `partial`。预算终态分布必须两列并列，不能用 arm status 覆盖 runtime finish | `2026-08-04-budget-calibration` 四臂：20 个 arm 中 19 个为 degraded，但 finish 分布不同 |
| `finalization → finish` 间隔 | 可由事件顺序直接相减 | 本轮 202 个 event 中 `finalization=0`、带 timestamp 的 event=0；只能用 `latency - (initial_root - last_remaining_research)` 算 **post-last-tool-result 上界**，它还包含模型思考、被拒调用和命令执行，不能叫 finalization duration | `docs/verification/2026-08-04-budget-calibration.md` §0.65 与收尾时间 |

## 3. 当前 trace_depth 与盲区清单

- current_trace_depth: `D3`
- 说明：2026-08-03 `60dee33c` 之后的 run 可定位到 grounded phase 的入口余量、grant、耗时、状态和失败原因；更早 A 组产物没有 `phases`，只能到 D1/D2，不能补推阶段分布。

| blind_spot | 因为哪个字段缺失/被量化 | 挡住了哪层定位 | 补齐它的最小埋点（一个变量+阈值） |
|---|---|---|---|
| 最后一段退出余量不显式 | phase 只有 `remaining_ms_at_entry` 与 `elapsed_ms` | 无法直接审计 terminal slack | 增加 `remaining_ms_at_exit`；健康阈值 `>0` |
| token 与 phase 未同表关联 | LLM ledger 无 phase name，phase record 无 token usage | 无法区分输出长度与 provider 固定延迟 | 每段记录 provider usage 的 completion/reasoning token；若 provider 不返回则保持 unknown，不估算 |
| 旧 run 无 phase telemetry | 埋点上线前 artifact 只有合成终态 | 无法可靠重建旧 brief/composer/judge 分布 | 不回填；只用新 run 或受控 replay |
| phase 没有显式 semantic epoch/censoring type | 同名 `elapsed_ms` 跨 revision 变义 | 历史分类器会把自然完成、retry 倍增和 grant 截断混为一类 | artifact 增加 `phase_semantic_epoch` 与 `elapsed_kind`；现阶段按 revision 映射 |
| 三段精确 p50/p95 未知 | 只有 brief 单次完成值、composer 下界、judge 无同质样本 | 无法为 root 扩容路线精确 sizing | 只有用户选择 deep-mode 后才做 uncensored profile；当前工程决策不需要再跑 brief-only |
| Codex headless finalization 起点不可见 | runtime-benchmark 无 `finalization` event 与 timestamp | 无法判断 0.65 是“留太多”还是“留够仍收不了尾”，也无法给精确 finalization p50/p95 | 只记录 `remaining_root_seconds_at_finalization_start`；`<30s` 表示进入过晚，`>=30s` 仍 timeout 则 reserve 不是主因 |

## 4. Grounded phase telemetry semantic epochs

| epoch | revision | `elapsed_ms` 的正确解释 | 已知样本 |
|---|---|---|---|
| E0 | `< cd175a0e` | phase timeout 未在网络 enforcement point 被读取；可能是自然完成值，或被共享 child 截断 | `6c16b73a`: brief `ok 69740/22`；composer `failed 20261/10` |
| E1 | `cd175a0e ≤ rev < 8ed66020` | 单次请求受 grant 限制，但 retry 可各拿一份，phase 墙钟可达 `attempts × grant` | `cd175a0e`: brief `44560/22 provider_unavailable` |
| E2 | `≥ 8ed66020` | 整个 phase 共享 `phase_deadline`；deadline failure 时 `elapsed≈grant`，属于 censored lower bound | `8ed66020` 及以后：`29009/29`、`22010/22`、`28010/28` |

跨 epoch 的 artifact 不得直接跑同一耗时分类器。E0 的 `brief ok 69740ms` 是已有自然完成样本；E2 的 `brief failed 28010ms` 只给出 `>28s` 下界。声明“缺自然完成值”前必须先扫描相邻 artifact 与代码内实测注释。

## 5. Runtime revision 核验

`/api/health` 当前会在 `runtime.source_revision` 暴露 revision，并同时给出 `source_dirty`；因此服务重启后可先用 health 做快速核验。Acceptance preflight 仍必须把 revision 冻结进 artifact，不能只依赖事后 health 查询。

## 6. Cross-harness normalized profile

跨 harness 审计只比较控制面事件的顺序，不把两个运行时的内部 span
粒度假设成相同。共享词表**就是 `agent-run-triage` skill 的固定 L1 九步**
（`vocabulary: triage-l1-9`），不在本仓另立一套：

`configure → intent → plan → route → retrieve → tool → observe → synthesize → stop`

> 2026-08-04 前本仓用的是七步（缺 `plan` / `tool`），会把「是否形成了对的步骤」
> 与「是否正确调用了工具」压进 `route` / `retrieve`，导致一条 L1=`tool` 的
> triage finding 在本仓根本无法表达。产物 `schema_version` 随之升到
> `normalized-harness-trace-2` 并新增 `vocabulary` 字段；v1 产物不可与 v2 直接比较。

| source kind | native event / field | normalized step | provenance |
|---|---|---|---|
| `workbench-trace` | `step_id=controller` 或 `name=turn_controller` | `intent` | `native` |
| `workbench-trace` | `step_id/name` 含 `route` | `route` | `native` |
| `workbench-trace` | `retrieve`、`skill`、`research`、`evidence` | `retrieve` | `native` |
| `workbench-trace` | `validate`、`budget`、`ledger`、`observe` | `observe` | `native` |
| `workbench-trace` | `compose`、`synth`、`grounded`、`shadow` | `synthesize` | `native` |
| `workbench-trace` | `stop`、`complete`、`terminal`、`error` | `stop` | `native` |
| `codex-rollout` / `codex-exec` | `thread.started` / `session.started` | `configure` | `normalized` |
| `codex-rollout` / `codex-exec` | `turn.started` | `intent` | `normalized` |
| `codex-rollout` / `codex-exec` | function/command/MCP/tool item | `tool` | `normalized` |
| `codex-rollout` / `codex-exec` | `*_call_output` / `tool_result` 等工具返回 | `observe` | `normalized` |
| `codex-rollout` / `codex-exec` | message/reasoning/output item | `synthesize` | `normalized` |
| `codex-rollout` / `codex-exec` | `turn.completed` / `turn.failed` / `error` | `stop` | `normalized` |
| `runtime-benchmark` | `task` | `intent` | `normalized` |
| `runtime-benchmark` | `plan` / `mode_decision` / `repair_goal` | `plan` | `normalized` |
| `runtime-benchmark` | `branch_started` | `retrieve` | `normalized` |
| `runtime-benchmark` | `tool_request` / `tool_call` | `tool` | `normalized` |
| `runtime-benchmark` | `tool_result` / `tool_error` / `runtime_result` / `observation` / `branch_completed` / `branch_failed` / `repair_outcome` / `invalid_action` | `observe` | `normalized` |
| `runtime-benchmark` | `finalization` / `finalization_recovery_started` | `synthesize` | `normalized` |
| `runtime-benchmark` | `finish` / `error` | `stop` | `normalized` |

`runtime-benchmark` 的每个 step 取自运行时自己的公开语义
（`episode_progress._EVENT_PROJECTIONS`：planning→`plan`、research 请求→
`tool`、research 结果→`observe`、repair→`plan`、finalizing→`synthesize`），
不按 kind 名字猜。**投影契约**：凡是
`runtime_backend_benchmark._DIAGNOSTIC_EVENT_KINDS` 允许落盘的 kind，必须在
`normalize_harness_trace._BENCHMARK_STEPS` 里有条目，否则它会静默掉出比较；这
条由 `test_every_persisted_benchmark_kind_has_a_normalized_step` 守住。

没有明确映射的事件必须输出 `step=unmapped` 和
`native_or_normalized=unmapped`，不能根据摘要、答案或事件相邻位置猜测。
实现入口为 `intelligence/eval/normalize_harness_trace.py`。每个 normalized
事件只保存 source event identity、受控状态/计数摘要和输入 SHA-256；不保存
prompt、答案正文、工具参数、命令 stdout、绝对路径、凭据或个人信息。

## 7. Comparison contract and evidence boundary

`compare_sequences()` 只对已映射的步骤做序列比较，并输出
`pre_divergence_equivalence`、`first_divergence_step` 和证据短句。若一侧没有
任何 mapped event，结果必须是 `not_established`，而不是把缺失事件判成行为分叉。

截至 2026-08-03，仓库中冻结的 Codex headless benchmark artifact 只保留
`final_text/thread_id/token usage/issues` 和有限 diagnostics；原始 rollout
JSONL 没有进入 artifact。因此旧 Codex receipt 只能支持
`runtime-benchmark` 层的归一化审计，不能事后补出 `configure`、`intent` 或
原始 tool/message span。最近五题 receipt 也不是五题成功样本：其中
`weekly-market-cause` 仍是失败/降级，不能在报告里改写成 pass。

公平的跨 harness A/B 需要同一 PIT（point-in-time，时间截面）fixture、同一
cutoff、可观察的两侧原生事件和冻结的 task contract；本轮旧 receipt 不满足
这些前提，所以 T4 报告只作 trace-shape/数据缺口审计，不给 SDK 迁移或质量胜负
结论。

## 8. Instrumentation coverage matrix（2026-08-04）

共享词表对齐到 `agent-run-triage` 的 L1 九步（`vocabulary: triage-l1-9`，
产物 `schema_version: normalized-harness-trace-2`）之后，把两侧现有收据投影上去：

读数取自两侧**真实执行路径**：workbench 跑一次真 turn 读 `trace.jsonl`；codex 跑
`CodexHeadlessRuntime.run()`（仅 subprocess 用 fake stdout，事件由真实 `_to_outcome`
构造）。均归一化后计数。

| L1 step | workbench 埋点前 | workbench 埋点后 | codex 埋点前 | codex 埋点后 | 两侧都有 |
|---|---|---|---|---|---|
| `configure` | – | **1** | – | **1** | ✓ |
| `intent` | 1 | 1 | –（`task` 被丢） | **1** | ✓ |
| `plan` | – | **1** | – | **1** | ✓ |
| `route` | 1 | 1 | – | – | |
| `retrieve` | 2 | 1 | – | – | |
| `tool` | – | – | 11 | 1 | |
| `observe` | 3 | 1 | 16 | 2 | ✓ |
| `synthesize` | 1 | 1 | – | – | |
| `stop` | – | – | 5 | 1 | |

- 埋点前：两侧都有仪器的**只有 1 步**（`observe`）。
- 2026-08-04 补埋点后：**4/9**。workbench 序列
  `configure → intent → plan → route → retrieve → synthesize → observe`；
  codex 序列 `configure → intent → plan → tool → observe → observe → stop`。
- 门槛 `configure → intent → plan` 三步两侧非空：**3/3 达标**。
  `first_divergence_step` 在这三步的前缀内已具备行为含义。

> codex 侧的 `configure` / `plan` 不是新造的事件：`configure` 记的是本来就存在的
> 装配（model / reasoning_effort / thread_id / registry 规模 / isolation / cutoff），
> `plan` 记的是 `context.policy` 的 tier + max_steps + total_seconds ——
> 即该 runtime 的研究深度决策，与 `agent_episode` 的 `mode_decision` 同义。
>
> 为此放宽了 `AgentOutcome` 的锚点不变量：`configure` 是**唯一**允许排在 `task`
> 之前的 kind。若强行让 `configure` 排在 `task` 之后，codex 会发出
> `intent → configure` 而 workbench 发出 `configure → intent`，**纯靠事件顺序在
> ordinal 0 制造一个假分叉**。

这改写了跨 harness 审计「无法配对」的成因判断。此前记的是「五题的 workbench
trace 没保留」——那只是数据保留问题。真实成因更靠前：**两侧仪器覆盖的是流水线的
不同半段**。workbench 记 `intent/route/retrieve/synthesize`，codex 记
`tool/stop`；即使把五题的 workbench trace 全部补齐，可对齐的 step 仍然只有
`observe` 一个，`first_divergence_step` 依然没有行为含义。

因此下一次公平审计的门槛是**可计数**的，不再是「让两侧都保留原生事件」这种无法验收的表述：

| 缺口 | 属哪侧 | 状态 | 最小埋点 |
|---|---|---|---|
| `configure` | workbench | **已补** | `step_id=configure` / `name=turn_assembly`，记 skill_mode、registry 规模、selected_skill_ids、上下文条数、继承 intent；只记身份与计数 |
| `plan` | workbench | **已补** | `step_id=plan` / `name=research_plan`。数据本来就在 `controller` 的 payload 里，属**拆融合 span**，不是造事件 |
| `intent` | codex | **已补** | `task` 事件回到落盘白名单，**仅对 2026-08-04 之后的 run 生效**，历史 artifact 无法追认 |
| `configure` | codex | 未补 | `thread.started` 已被 runtime 解析（`thread_id` 进了 `runtime_result` payload），但没有独立的 configure 事件；需新增 kind 并加白名单 |
| `plan` | codex | 未补 | `mode_decision` 由 `agent_episode` 发射，`codex_headless_runtime` 自建事件列表，不走该路径 |
| `route` | codex | **结构性差异，非缺口** | codex episode 不做 skill 分派（backend 由 benchmark 选定、tool registry 固定）。强行造一个 `route` 事件只是为了凑指标 |
| `tool` | workbench | 未补 | `trace.jsonl` 只到 `ask_retrieve_compose` 粒度，单次工具调用在 `stream.jsonl`/retrieval 里 |
| `stop` | workbench | 未补 | trace 以 budget 事件收尾，无显式终态 step |
| `synthesize` | codex | 未补 | headless artifact 不保留 message span |

验收标准：`configure → intent → plan` 三步在两侧都非空，`first_divergence_step`
才第一次具备行为含义。**当前 1/3**（只有 `intent`）；workbench 侧已就位，缺口全在 codex 侧。

> 门槛从「四步」收窄为「三步」：`route` 在 codex 侧是**结构性不存在**而非仪器缺失。
> 把结构差异写成埋点缺口，会诱导为满足指标而制造事件——那正是本 profile 反复
> 在防的重编码。

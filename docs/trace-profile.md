# Trace Profile: finance-workspace-private

- last_updated: 2026-08-03
- updated_by_run: `run_20260803_171452_043073`

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
粒度假设成相同。共享词表固定为：

`configure → intent → route → retrieve → observe → synthesize → stop`

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
| `codex-rollout` / `codex-exec` | function/command/MCP/tool item | `retrieve` | `normalized` |
| `codex-rollout` / `codex-exec` | message/reasoning/output item | `synthesize` | `normalized` |
| `codex-rollout` / `codex-exec` | `turn.completed` / `turn.failed` / `error` | `stop` | `normalized` |
| `runtime-benchmark` | `tool_request` | `retrieve` | `normalized` |
| `runtime-benchmark` | `tool_result` / `runtime_result` | `observe` | `normalized` |
| `runtime-benchmark` | `finish` / `error` | `stop` | `normalized` |

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

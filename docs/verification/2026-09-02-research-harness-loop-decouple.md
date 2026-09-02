# 收据：领域 Harness 与底座 loop 解耦 P0（2026-09-02）

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`
分支：`refactor/harness-loop-seams` @ 基线 gitea/main `18bf518b`（本收据的读数取自提交前脏树，脏路径恰为本单三个代码文件；提交后未再改代码）。

**结论：P0 验收 §8 八条全绿。默认 harness 下行为等价——全量 pytest 与 main 同一组 5 红、passed 恰多 13（新测试）。接缝有牙，棘轮在 main 上会红。未合 main、未切 8792。**

## 成立条件

| 项 | 值 |
|---|---|
| 树 | `/Users/a77/fwp-wt-harness-loop-seams`（新开，非主树；主树有 187 行他人足迹未动） |
| revision | `18bf518b82954ce7ac49260ea5419e4b9aabe0a2` + 本单未提交改动（收据 `dirty_paths` 三文件） |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python` 3.12.13，依赖指纹 `786fd167a42126c6` |
| 基线树 | `/Users/a77/tmp/fwp-baseline-18bf518b`（detached @ 同 SHA，干净） |
| 读数收据 | 基线 `~/.finance-runtime/test-receipts/20260902T022008Z-18bf518b.json`（跑于 02:20–02:29）；分支 `20260902T023825Z-18bf518b.json` |
| 8792 | 未读、未碰（本单纯离线；不需要 revision 哨兵） |

## 读数

### 全量 pytest（§8 第 3 条）

| 树 | passed | failed | skipped | xfailed | 用时 |
|---|---:|---:|---:|---:|---|
| main 基线 | 7345 | 5 | 15 | 1 | 8:46 |
| 分支 | **7358** | **5** | 15 | 1 | 8:05 |

5 红两边**同一组**：`intelligence/tests/test_dream_mine.py::RunMineTests::{test_degrade_without_key_keeps_watermark_and_marks_md, test_dry_run_writes_nothing_but_store, test_max_signals_cap, test_mine_appends_proposals_suggest_only_and_idempotent, test_quote_redaction_survives_into_proposal}`——与 Episode 无关，是 main 上既有的环境项。7358 − 7345 = 13 = `test_research_harness.py` 用例数。

### 门禁

- `ruff check .`：All checks passed。
- `scripts/layer_audit.py`：ERROR 0 == 基线（对 `refactor/harness-loop-seams@18bf518b` 成立）；`runtime/` 17 模块。
- 直接构造 Episode 的七个测试文件（`test_agent_episode` 81 处构造 + `test_repair_carry_just_written_finish` + `test_episode_tools` + `test_empty_pool_fallback` + `test_runtime_fault_matrix` + `test_tool_stage_events` + `test_tool_observation_noise`）：221 passed，6.23s。这是「durable 事件 payload 零改动」的回归网（§8 第 2、5 条）。

### 新测试 `intelligence/tests/test_research_harness.py`：13 passed

| 组 | 例 | 守什么 |
|---|---:|---|
| 等价 | 5 | `admit_finish` 接受 / FORMAT / INTEGRITY 三路与直接调 `validate_episode_finish` + `expand_episode_snapshot_bindings(draft=)` + `_merge_gaps` + `rejection_response` + `finish_rejection_fields` 逐字段相等；`assemble_prompt` == `split_episode_prompt`；`halt_after_tool_batch` 复现 `FORECAST_RESIDUAL_SPIN`；`retrieval_complete` 三种 registry；`FinishAdmission` 拒绝两侧形状不一致 |
| 协议 | 1 | `isinstance(FinanceResearchHarness(), ResearchHarness)`；只实现 `admit_finish` 的类不算 |
| loop 真在问 | 2 | 录音 harness 在 tool→finish 一次 episode 上按控制流顺序收到 `assemble_prompt → halt_after_tool_batch → retrieval_complete → admit_finish`；不注入时默认是金融 harness |
| 有牙 | 2 | 伪造哈希稿：默认 harness → `invalid_action.code=forged_hash / kind=integrity / disposition=integrity_violation`、finish `rejection_code=forged_hash`、draft 空；放行 harness → `model_finish / completed`、无 invalid_action、`rejection_code=none` |
| 棘轮 | 2 | AST：`agent_episode.py` 从 `episode_protocol` 只剩 `finish_rejection_fields` 等非门符号，不 import `forecast_residual_budget`，import 了 `research_harness`；`research_harness.py` 不 import `intelligence.runtime` |
| §7 差 | 1 | 死钟结转 + 比较句稿 + 两条同题证据 → bindings `('rank-1','rank-2')` |

### 反向验证（防假绿）

同一脚本 `/Users/a77/tmp/probe_dead_clock_main.py`（临时，不入库）在两棵树 cwd 下各跑一次：

| 树 | stop_reason / status | bindings | 棘轮泄漏 |
|---|---|---|---|
| main 基线 | `model_finish` / `completed` | `[('rank-1',)]` | `expand_episode_snapshot_bindings, rejection_response, split_episode_prompt, validate_episode_finish` |
| 分支 | `model_finish` / `completed` | `[('rank-1', 'rank-2')]` | `[]` |

即：§7 那条差在 main 上确实存在（比较集展开在死钟路径被丢），本单把它并到同一份 admission；棘轮测试放到 main 上会红——不是同义反复。

## 改动面（§8 第 4 条）

`git diff --stat`：`intelligence/runtime/agent_episode.py | 238 (+87 / −151)`。新增 `intelligence/services/research_harness.py`、`intelligence/tests/test_research_harness.py`、spec、本收据、inflight 交接。`glm_agent_runtime.py` / `continuous_sub_research.py` 零改动。

`agent_episode.py` import 段：从 `episode_protocol` 去掉 4 个符号（`validate_episode_finish` / `expand_episode_snapshot_bindings` / `rejection_response` / `split_episode_prompt`），去掉整条 `forecast_residual_budget` import；新增 `research_harness` 三个名字。删除 `_finish_gaps`（搬到 harness `_merge_gaps`）与 `_snapshot_surface_satisfied`（成为 `retrieval_complete`）。

## P1a：三条 loop 共用同一道门（同分支第二个提交）

改动面：`openai_agents_runtime.py`（−/+79）、`codex_headless_runtime.py`（−/+73）、`research_harness.py`（+8：`FinishAdmission.declared_gaps`）、`test_research_harness.py`（+207）。

| loop | 改走 harness 的点 | gap 口径（保持原样） |
|---|---|---|
| `openai_agents_runtime` | `__init__(harness=)`；`_run_episode` prompt + 终局门；`resume` 修复终局门 | `snapshot.gaps + declared_gaps`（不并绑定 gap） |
| `codex_headless_runtime` | `__init__(harness=)`；`_to_outcome` 终局门；`_finish_issue` ×2（新增 `registry` / `harness` 形参）；`_headless_prompt(harness=)` | `snapshot.gaps + issues + declared_gaps`（不并绑定 gap） |

**为什么加 `declared_gaps`**：P0 的 `gaps` 是 `agent_episode` 的合并口径（声明 + 绑定 gap）；另两条 loop 从不并绑定 gap。机械替换不许顺手改口径，所以值对象同时给出未合并的 `declared_gaps`。三条 loop 的 gap 口径不一致这件事本身，是本轮**发现**不是本轮**修**——留 P1b 之后单独量、单独拍。

`_finish_issue` 原先只调 `validate_episode_finish`，现在经 `admit_finish` 多做一次 bindings 展开（结果丢弃）。展开内部对 `registry.resolve` 的 `UnknownResearchTool` 已 try/except，无新异常面；多出的是纯计算。

### 读数

- 两条 runtime 的既有测试 + adapter + 一致性套件：`test_openai_agents_runtime` / `test_codex_headless_runtime` / `test_agent_runtime` / `test_continuous_turn_adapter` / `tests/conformance` + 新测试 = **220 passed, 5 skipped, 1 xfailed**（改前口径不变）。
- `test_research_harness.py`：13 → **19**。新增：棘轮参数化到三文件（3）、`agent_episode` 停机判定不 import `forecast_residual_budget`（1）、SDK runtime 完整 `run()` 有牙一对（默认 → `sdk_invalid_finish` / partial / 空稿；放行 → `model_finish` / completed）（2）、codex `_finish_issue` 默认 `headless_invalid_finish` vs 放行 `None` + `_headless_prompt` 经录音 harness 的 `assemble_prompt` 且以 system 段开头（1）。
- ruff 绿；`layer_audit` ERROR 0 == 基线（对 `5f945d10` 成立）。
- 全量 pytest：见下表（P1a 行）。

| 树 | passed | failed | skipped | xfailed |
|---|---:|---:|---:|---:|
| main 基线 | 7345 | 5 | 15 | 1 |
| P0（`5f945d10`） | 7358 | 5 | 15 | 1 |
| P1a | **7364** | **5** | 15 | 1 |

P1a 读数取自提交前脏树（脏路径 = 本节四文件），9:54；5 红仍是 `test_dream_mine` 同一组，7364 − 7358 = 6 = 新增测试数（19 − 13）。

## #525 合并与主干门禁（2026-09-02，按 `docs/workflows/acceptance-workflow.md`）

- 合并前：`git merge-tree --write-tree gitea/main refactor/harness-loop-seams` exit 0、无 `CONFLICT` 行；基座落后 2 提交（#520：一份 spec + `scripts/audit_tool_admission_branches.py`，与本单文件零交集）。
- 合并：`POST /pulls/525/merge {"Do":"merge"}` → HTTP 200，`merged=true`，merge commit `71a2c846246cd853fe07fbd758119097e52a7cca`；远程分支已删。
- 门禁树：`/Users/a77/tmp/fwp-gate-71a2c846246c`（detached @ main tip，干净）。规程测试壳（`umask 022` + `env -i PATH HOME KNOWLEDGE_WIKI`）。
  - ruff：All checks passed；`layer_audit`：ERROR 0 == 基线（对 `HEAD@71a2c846` 成立）。
  - 全量 pytest：**7364 passed / 5 failed / 15 skipped / 1 xfailed**，9:43。收据 `~/.finance-runtime/test-receipts/20260902T032337Z-71a2c846.json`（`dirty=false`）。
  - `check_test_receipt.py <收据> --expect-revision $(git rev-parse gitea/main) --base-drift-max 5` → **✅ 可采信**（revision 一致、干净树、基座漂移 0）。5 红按名逐条：全是 `test_dream_mine.py::RunMineTests` 五例，合并前基线 `18bf518b` 上同样红（本收据首节），非本批引入。
  - webapp 四件套（未动前端，规程仍要求跑；同一门禁树 `intelligence/webapp`，`pnpm install --frozen-lockfile`）：`pnpm lint` ✓、`pnpm typecheck` ✓、`pnpm test` **70 passed（3 files）**、`pnpm build` ✓，整串 exit 0。
- **8792 未切**：本批零 live 判据（纯结构等价），按交接单「下次切流带上」。

## P1b：`interpret_plan` + `steering_message` + 修复 prompt 同源（分支 `refactor/harness-interpret-turn`，基于 `71a2c846`）

改动面：`research_harness.py`（+2 方法 + `SteeringKind`）、`agent_episode.py`（PLAN 块两处调用→一处；两处回灌文案 + `_begin_finalization` 文案改取 harness；去 import `parse_plan_candidate` / `validate_plan_revision`）、`openai_agents_runtime.py`（修复轮 system/task 取 `assemble_prompt` 两半，去 import `build_episode_input` / `build_episode_instructions`）、`codex_headless_runtime.py`（修复 prompt 的任务 JSON 取 `assemble_prompt[1]`，去 import `build_episode_input`）、`test_research_harness.py`（19 → 24）。

等价论证：`interpret_plan` = `parse_plan_candidate` 后若有上一份 PLAN 再 `validate_plan_revision`，异常文本原样进 `PlanParseResult.error`——与原 try/except 分支逐字同义；三段 steering 文案逐字搬运，测试按字节钉死；`split_episode_prompt` 本就是 `(build_episode_instructions, build_episode_input)`，取两半 = 原调用。`openai` 修复轮此前只在 `continuation_input is None` 时算 `build_episode_input`，现无条件算一次（纯函数、结果相同、多一次计算）。

### 读数

- 定向：三条 loop 相关 14 个测试文件/目录 **468 passed, 5 skipped, 1 xfailed**（改前口径不变）。
- `test_research_harness.py` **24 passed**。新增：`interpret_plan` 五路等价（合法 / 非 PLAN 两种 / 写坏 / 合法修订 / 非法修订错误文本逐字）、三段 steering 文案字节钉、loop 顺序扩成 plan→tool→finish 七次调用、有牙两条（看不见 PLAN 的 harness 让 PLAN 轮变 `invalid_action`、自定义 steering 文本真到模型眼前含 `begin_finalization:tool_budget_exhausted`）、棘轮扩到 `research_plan` 两名与 `build_episode_*` 两名。
- ruff 绿；`layer_audit` ERROR 0 == 基线（对 `refactor/harness-interpret-turn@71a2c846` 成立）。
- 全量 pytest：见下表回填。

| 树 | passed | failed | skipped | xfailed |
|---|---:|---:|---:|---:|
| main `71a2c846`（门禁） | 7364 | 5 | 15 | 1 |
| P1b | **7369** | **5** | 15 | 1 |

P1b 读数取自提交前脏树（脏路径 = 本节五文件），规程测试壳，7:43；5 红仍是 `test_dream_mine` 同一组，7369 − 7364 = 5 = 新增测试数（24 − 19）。

## P1c：`project_tool_result` + `project_tool_error`（分支 `refactor/harness-tool-result-projection`，叠 P1b `950ac43f`）

改动面：`research_harness.py`（`ToolResultProjection` 值对象 + 2 方法；新 import `tool_observation_noise` / `tool_result_budget` / `public_agent_evidence` / 三个序号函数）、`agent_episode.py`（`_EpisodeToolAccumulator` 加 `harness` 字段；成功分支 ~50 行投影整段搬走、错误 payload 改取 harness；去 import `prune_tool_observation` / `budget_tool_observation`）、`test_research_harness.py`（24 → 29）。生产构造零改动（accumulator 由 `run()` 传 `self._harness`；测试里裸构造走默认）。

等价论证：成功分支从 `evidence_ordinal_table(tuple(self.evidence))` 到 `json.dumps(strip_hashes_for_model(budget_tool_observation(pruned)))` 逐字搬进 `project_tool_result`，输入仍是「已合并本次证据后的累计证据 + 去重账本」，输出仍分两路（审计底稿叠 `call_id` / timing 进 `tool_result`；模型正文进 `role=tool` 消息）。`seen_observation_prose` 由 `set(seen)` 变 `set(frozenset(seen))`，同值。错误 payload 四键与 400 字截断逐字同。

### 读数

- 定向 11 个测试文件（三条 loop + 观察噪声 + 结果预算）**314 passed, 2 skipped**（改前口径不变；`test_agent_episode` 对工具消息正文与 `tool_result` payload 的大量断言即字节等价的回归网）。
- `test_research_harness.py` **29 passed**。新增：投影与内联逐字段等价（审计含 telemetry 与 hash，模型正文无 telemetry、无 `evidence_hashes`、evidence 行无 `content_hash`、有 `evidence_ids=[E1,E2]`；同段叙述二次投影被去重账本折叠）、错误投影形状 + 400 字截断、loop 顺序扩成八次调用、有牙两条（自定义工具视图真到模型眼前——且**审计底稿不变**、`tool_result` 事件仍全量；自定义错误视图真到模型眼前）、棘轮 `agent_episode` 不 import `tool_observation_noise` / `tool_result_budget`。
- **实测边界（测试首跑逮到）**：loop 在最后一条工具消息上叠 `runtime_budget`（`_append_tool_budget_state`，spec §4 #9 底座预算可见性）。模型看到的 = harness 正文 + 底座这一个键；测试断言 `set(facing) == {"ok", "view", "runtime_budget"}` 把两层边界钉死。另：账本把 payload 里的 list 冻成 tuple，按值比。
- ruff 绿；`layer_audit` ERROR 0 == 基线。
- 全量 pytest：见下表回填。

| 树 | passed | failed | skipped | xfailed |
|---|---:|---:|---:|---:|
| P1b（`5c017081`） | 7369 | 5 | 15 | 1 |
| P1c | **7374** | **5** | 15 | 1 |

P1c 读数取自提交前脏树（脏路径 = 本节三个代码/测试文件 + 文档），规程测试壳，5:49；5 红仍是 `test_dream_mine` 同一组，7374 − 7369 = 5 = 新增测试数（29 − 24）。

## 未做 / 红线

- 未改秒数、档位、reserve、`episode_protocol.py` 判定、8792、启动器、快照。
- `evidence_ordinal_table` / `attach_evidence_ordinals` / `strip_hashes_for_model` 仍被 `agent_episode._append_sub_research_message` 直接用（子研究消息投影，P2 `govern_mode` 范围），本刀不摘。
- 三条 loop 的 gap 口径不一致：已暴露（`gaps` vs `declared_gaps`），未统一。
- 未写第二条 loop（P2'）；「run 层可替换」目前是**接缝已抽（八方法）+ 三条 loop 共用 + 有牙已证**，不是**换过一次**。
- 未跑 LLM。配额未动。

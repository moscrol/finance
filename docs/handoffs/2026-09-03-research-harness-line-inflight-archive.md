# 归档：ResearchHarness 接缝线九张 PR 的在途交接（2026-09-03 收口）

这条线（`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`）九张 PR 于 2026-09-02
全部合入 `gitea/main`，每份 inflight 交接都已标「闭环」。按 `skills/handoff/SKILL.md`「做完的、合并的事从
inflight 里删掉，转成日期快照」，本文把八份 inflight **原文逐字**收进来后从 `docs/handoffs/inflight/` 删除。
接手者要的「卡点 / 下一步」以 decouple spec 头部与 `inflight/main.md` 顶行为准；这里只留决策与被否方案的
来历，供要动这块地方或推翻某个决定的人查。

合入时间线、门禁读数、切流状态见 `inflight/main.md` 2026-09-02 各行；8792 至本文写时仍在 `532cdb070a71`
（含 #525–#530，不含 #531–#535）。

| 原 inflight 文件 | PR |
|---|---|
| `inflight/refactor-harness-loop-seams.md` | #525（P0 + P1a） |
| `inflight/refactor-harness-interpret-turn.md` | #526（P1b） |
| `inflight/refactor-harness-tool-result-projection.md` | #527（P1c） |
| `inflight/refactor-harness-reference-loop.md` | #528（P2'） |
| `inflight/refactor-harness-govern-mode.md` | #529（P2 govern_mode） |
| `inflight/refactor-harness-sub-research-projection.md` | #530（P2 子研究投影） |
| `inflight/refactor-harness-repair-policy-split.md` | #531 spec + #532 实施（repair_policy） |
| `inflight/spec-harness-empty-pool-fallback.md` | #533（空池回退） |

---


## 原文：`inflight/refactor-harness-loop-seams.md`（#525（P0 + P1a））

## 在途交接 · refactor/harness-loop-seams

更新：2026-09-02 11:40 CST · **已闭环：PR #525 已合 `gitea/main=71a2c846`，主干门禁可采信（7364P/5F 同基线红、webapp 四连绿，读数见 `inflight/main.md` 顶行与收据），8792 未切（零 live 判据，随下批）。** 后续 P1b 见 `inflight/refactor-harness-interpret-turn.md`。

### 一句话

给「金融题怎样才算答完」立了 `ResearchHarness` Protocol
（`intelligence/services/research_harness.py`）。P0 把 `ContinuousAgentEpisode` 里手焊的
三道领域门（终局准入 ×5、批后停机 ×2、prompt ×1）改成 loop 调 `self._harness`；
P1a 让另两条 loop（`openai_agents_runtime`、`codex_headless_runtime`）的终局门与 prompt
也走同一个 harness——**三条 loop、一道门**。默认 `FinanceResearchHarness` 纯委托，
行为等价（P0 唯一已知差见 spec §7，已钉测试）。这是 09-01 形状对齐 spec §11
第三条「把领域门抽到外壳钩子」的头两刀。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`

### 提交

| 提交 | 内容 |
|---|---|
| `5f945d10` | P0：协议 + 默认实现 + `agent_episode` 8 焊点（+87/−151）+ 13 测试 + spec + 收据 |
| （第二个，见 `git log`） | P1a：另两条 loop 改走 harness（各 ~75 行对换）+ `FinishAdmission.declared_gaps` + 测试 13→19 |

### 离线读数（对分支尖成立，解释器 `.venv-workbench`）

见收据。要点：全量 pytest 与 main 基线同一组 5 红（`test_dream_mine.py`，环境项），
passed 只多出新测试数；ruff 绿；`layer_audit` ERROR 0 == 基线。

反向验证（假绿防线，P0）：同一死钟脚本在 main 树跑出 bindings `('rank-1',)`、分支
`('rank-1','rank-2')`；棘轮在 main 树报出 4 个泄漏名、分支 0。

### 红线遵守自证

- 未改任何秒数 / 档位 / reserve；未改 `episode_protocol.py` 判定。
- durable 事件种类、payload 键、顺序零改动；三条 loop 的 gap 口径**各自原样**
  （`agent_episode` 合并口径用 `gaps`；另两条只并声明 gap 用 `declared_gaps`）。
- `services/` 不 import `runtime/`（`layer_audit` + 新测试双守）。
- 生产构造（`glm_agent_runtime` / `continuous_sub_research` / `api/app.py` 三处 runtime
  构造）**零改动**，都拿默认 harness。
- 8792 / 启动器 / 快照未碰。

### 下一步（按序）

1. 用户确认 → 合 PR #525（等价四件套：ruff ✅ pytest ✅ layer_audit ✅；未动前端，
   frontend/e2e 不触发）。
2. **P1b**：`interpret_turn`（PLAN 协议：`parse_plan_candidate` / `validate_plan_revision`
   出 loop）、`after_tool_batch`（`_EpisodeToolAccumulator.consume` 的 prune / budget /
   ledger ingest）、`assemble_prompt` 扩展（回灌与 finalization 文案；另两条 loop 修复
   prompt 里的 `build_episode_input` / `build_episode_instructions`）。这三条抽完，loop 里
   不再出现「PLAN」「FINAL_JSON」字面——**这是 P2' 第二条 loop 的前置**。
3. **gap 口径统一**（P1b 后单独一刀）：先量三条 loop 的绑定 gap 分布，再拍是否都用合并口径。
4. **P2'**：`finance-base-ab/pi-shape/packages/agent_core` 里写一条只调 harness 四方法 +
   `ResearchToolRegistry` 的最小 loop，跑 09-01 同题——「run 层可替换」从设计图变实测。

### 顺手发现（不属本单）

- `intelligence/services/episode_scope.py` 文首「生产链路目前没有任何一处构造
  EpisodeScope」已过时（`agent_episode.py` 入口在构造）。文档腐烂，另单修。
- `run()` 主门驳回后的兜底 `_stopped_outcome(stop_reason="invalid_model_finish")` 对
  INTEGRITY 也写 `invalid_model_finish`，只有 `invalid_action.disposition` 是
  `integrity_violation`。现状保留；统计侧按 `disposition` / `rejection_code` 分。
- 三条 loop 的 gap 口径不一致（见上）。


## 原文：`inflight/refactor-harness-interpret-turn.md`（#526（P1b））

## 在途交接 · refactor/harness-interpret-turn

更新：2026-09-02 12:15 CST · **已闭环：PR #526 已合（merge `42e5bb69`），随 #527 一起过主干门禁 `e360895b`（7374P/5F 同基线红、webapp 70P 绿，见 `inflight/main.md` 顶行），8792 未切。** 后续见 `inflight/refactor-harness-reference-loop.md`。

### 一句话

`ResearchHarness` 从四方法扩到六方法：`interpret_plan`（PLAN 识别 + 修订合法性出 loop）与
`steering_message`（三段焊死的领域文案——PLAN 无效回灌、终局无效回灌、finalization 提示——
出 loop）；另两条 loop 修复 prompt 的 `build_episode_input` / `build_episode_instructions`
改取 `assemble_prompt` 两半。行为等价（文案字节钉死、`interpret_plan` 与原两处调用逐字同义）。
前序 P0 + P1a 已由 PR #525 合入 main `71a2c846`（主干门禁可采信，见收据）。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`（§4 #4 / #12 → P1b 已实施；§9 P1c 待做）
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P1b 节）

### 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/services/research_harness.py` | `SteeringKind` Literal；Protocol + 默认实现各加 `steering_message` / `interpret_plan` |
| `intelligence/runtime/agent_episode.py` | PLAN 块 `parse_plan_candidate`+`validate_plan_revision` → `harness.interpret_plan`（try/except/else 拍平一层）；两处回灌文案 + `_begin_finalization`（静态→实例）改取 `harness.steering_message`；去 2 个 import |
| `intelligence/runtime/openai_agents_runtime.py` | 修复轮 `repair_system, repair_user = harness.assemble_prompt(...)`；去 `build_episode_*` import |
| `intelligence/runtime/codex_headless_runtime.py` | 修复 prompt 任务 JSON 取 `assemble_prompt(...)[1]`；去 `build_episode_input` import |
| `intelligence/tests/test_research_harness.py` | 19 → 24：等价 ×2、顺序改成七次调用、有牙 ×2、棘轮扩到 `research_plan` 与 `build_episode_*` |

生产构造零改动（三条 loop 都拿默认 harness）。

### 红线遵守自证

- 未改秒数 / 档位 / reserve；未改 `episode_protocol.py` / `research_plan.py` 判定。
- 模型可见字节零改动：三段文案逐字搬运并按字节钉测试；修复 prompt 两半与原调用同函数。
- durable 事件零改动。`services/` 不 import `runtime/`。8792 / 启动器 / 快照未碰。

### 下一步（按序）

1. 用户确认 → 合 PR #526（等价四件套：ruff ✅ pytest 见收据 layer_audit ✅）。
2. **P1c**：`_EpisodeToolAccumulator.consume` 的模型视图投影抽成 `harness.project_tool_result`
   （dsh `tools/result` 位）。字节等价门：durable `tool_result` payload 与 `role=tool` 消息内容。
   事件发射、证据去重、traces 留 loop。
3. **P2'**：`finance-base-ab/pi-shape/packages/agent_core` 里写只调六方法 + registry 的最小 loop，
   跑 09-01 同题。P1c 做完它才「是同一台机器」。

### 顺手发现（不属本单）

- 与 P0/P1a 交接单同：`episode_scope.py` 文首过时；INTEGRITY 的 outcome `stop_reason` 仍写
  `invalid_model_finish`；三条 loop gap 口径不一致。


## 原文：`inflight/refactor-harness-tool-result-projection.md`（#527（P1c））

## 在途交接 · refactor/harness-tool-result-projection

更新：2026-09-02 12:15 CST · **已闭环：PR #527 已合 `gitea/main=e360895b`，主干门禁可采信（7374P/5F 同基线红、webapp 70P 绿，见 `inflight/main.md` 顶行），8792 未切。** 后续 P2' 见 `inflight/refactor-harness-reference-loop.md`。 堆叠链：P1b 未合前本分支不能单独合（`git rev-list --left-right --count` 左侧为 0）。

### 一句话

`ResearchHarness` 六方法 → 八方法：`project_tool_result`（一次成功观察 → 审计底稿 + 模型正文 +
去重账本新状态）与 `project_tool_error`（失败 → 模型看的结构化结果）。这是 dsh `tools/result`
（definition-owned `finalizeContent`）的位置，也是第二条 loop「是同一台机器」的最后一块硬前置：
**模型看到的一切工具结果、审计留下的一切工具底稿，字节都来自 harness**。loop 只管账。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`（§4 #6 → P1c 已实施）
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P1c 节）

### 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/services/research_harness.py` | `ToolResultProjection{audit_payload, model_content, seen_prose}`；Protocol + 默认实现各加两方法（成功分支 ~40 行逐字搬入） |
| `intelligence/runtime/agent_episode.py` | `_EpisodeToolAccumulator` 加 `harness` 字段（默认金融，`run()` 传 `self._harness`）；成功分支只剩证据去重 → 问 harness → 记事件 → 追加消息；`_append_tool_error` payload 取 harness；去 import `prune_tool_observation` / `budget_tool_observation` |
| `intelligence/tests/test_research_harness.py` | 24 → 29 |

### 离线读数（对分支尖成立，`.venv-workbench` 规程壳）

见收据 P1c 节。定向 314P/2S；全量见收据表。ruff 绿；`layer_audit` ERROR 0。

**边界实测**：loop 在最后一条工具消息叠 `runtime_budget`（底座预算可见性，spec §4 #9 不抽）。
模型看到的 = harness 正文 + 这一个键；测试 `set(facing) == {"ok","view","runtime_budget"}` 钉死。

### 红线遵守自证

- 模型可见字节零改动（投影逐字搬运；`test_agent_episode` 对工具消息正文的既有断言全绿）。
- durable `tool_result` / `tool_error` payload 零改动（`call_id` / timing 仍由 loop 叠加）。
- `services/` 不 import `runtime/`。生产构造零改动。8792 未碰。

### 下一步（按序）

1. 用户确认 → 先合 #526（P1b）再合 #527（本分支；堆叠链不能改序）。
2. **P2**：修复协调（`_recover_finalization` / `_repair_model_complete` / `RepairGoal` / `apply_unreachable_downgrade` / `EpisodeFinalizer`）、mode 治理与子研究消息投影（`_append_sub_research_message` 里剩下的三个序号函数）、空池回退。这些持状态、改控制流，先画状态机再切。
3. **P2'**：`finance-base-ab/pi-shape/packages/agent_core` 里写只调八方法 + registry 的最小 loop，跑 09-01 同题（硬门沿用 09-01：首轮 `task_frame_hash` / `input_tokens`±3 / `financial_data`）。

### 顺手发现（不属本单）

- 工具壳 `cat <&3` 楔死复现一次（定向 pytest 5 分钟无输出，`ps` 见 `cat` 子进程），杀掉重跑无污染——与台账 08-27 记录同形。


## 原文：`inflight/refactor-harness-reference-loop.md`（#528（P2'））

## 在途交接 · refactor/harness-reference-loop

更新：2026-09-02 12:45 CST · **已闭环：PR #528 已合 `gitea/main=5292175c`，主干门禁可采信（7381P/5F 同基线红、webapp 70P 绿，见 `inflight/main.md` 顶行），8792 未切。** 后续 P2 `govern_mode` 见 `inflight/refactor-harness-govern-mode.md`。

### 一句话

第二条 loop 落地：`intelligence/runtime/harness_reference_loop.py`（`HarnessReferenceLoop`）
只调 `ResearchHarness` 八方法 + `ResearchToolRegistry` + 底座 `ToolBatchExecutor`，一行领域
逻辑不写。`test_harness_reference_loop.py` 拿同一脚本化模型、同一注册表把它和
`ContinuousAgentEpisode` 并跑：**首轮请求字节相同；无 PLAN 全程消息一致（只差底座
`runtime_budget` 一键）、outcome 一致；有 PLAN 差恰好一条 Episode 独有的 `MODE_DECISION`。**
「run 层可替换」自此是可判定的读数。前序 P0–P1c 已全部合 main（`e360895b`）。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`（§9 P2' 已实施；P2'-live 未做）
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P2' 节）

### 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/runtime/harness_reference_loop.py` | 新：最小 loop（调模型 / 经 `ToolBatchExecutor` 派工具 / 数槛 / 记 durable 子集事件），其余全问 harness |
| `intelligence/tests/test_harness_reference_loop.py` | 新：6 例（首轮身份 / 无 PLAN 全程等价 / 有 PLAN diff 恰一条 / 有牙 / 底座停机 / 九模块棘轮） |
| 既有文件 | **零改动**（不进 `RUNTIME_BACKEND_NAMES`，与 `dsh_stub_runtime` 同纪律） |

### 离线读数（对分支尖成立）

见收据 P2' 节表格。ruff 绿；`layer_audit` ERROR 0（`runtime/` 17→18 模块，门禁只查方向）；全量见收据回填。

### 为什么放仓内而不是 finance-base-ab

09-01 把两份形状外壳放 `finance-base-ab` 是为了不污染 `intelligence/`、不进快照。P2' 的价值在
**持续判定**——「新的领域文案有没有又焊回 Episode」要靠 CI 每次都问，放仓外就没人问。
`finance-base-ab` 的 `pi-shape/packages/agent_core` 将来直接 import 本类即可（P2'-live）。

### 红线遵守自证

- 未改任何既有源文件；生产装配零改动；8792 未碰。
- 参考 loop 与 Episode 的全部差异都落在 spec §4 标「底座」或 P2 的行上，测试逐条钉住。

### 下一步（按序）

1. 用户确认 → 合 PR #528。
2. **P2 `govern_mode`**：从 P2' 读数出发——`_append_mode_decision_message` 的 `MODE_DECISION` 文案 +
   `mode_decision` 事件 + 子研究消息投影（三个序号函数）进 harness；做完后有 PLAN 脚本的 diff 应归零。
3. **P2 `repair_policy`**：`_recover_finalization` / `_repair_model_complete` / `RepairGoal` /
   `apply_unreachable_downgrade` / `EpisodeFinalizer`——先画状态机。
4. **P2'-live**：8792 快照切到含 harness 的 revision 后，用 `finance-base-ab` 隔离配方把
   `HarnessReferenceLoop` 当第四臂跑 09-01 同题（硬门：首轮 `task_frame_hash` / `input_tokens`±3 /
   `financial_data`）。烧配额，另拍。

### 顺手发现（不属本单）

- Episode 的 `_decide_mode` 在**每次** PLAN 轮都会给模型追加 `MODE_DECISION`，即使 quick 档
  没有任何裁决变化——这条消息是否该存在，是 P2 `govern_mode` 的第一个问题。


## 原文：`inflight/refactor-harness-govern-mode.md`（#529（P2 govern_mode））

## 在途交接 · refactor/harness-govern-mode

更新：2026-09-02 13:30 CST · **已闭环：PR #529 已合 `gitea/main=b8cc9a73`，主干门禁可采信（7384P/5F 同基线红、webapp 70P 绿，见 `inflight/main.md` 顶行），8792 未切。** 后续见 `inflight/refactor-harness-sub-research-projection.md`。

### 一句话

`ResearchHarness` 八方法 → 九方法：`govern_mode(task_frame, plan, context, can_branch) ->
ModeGovernance{context, decision, message}`。深度裁决（信号 → 依赖修正 → `ModeGovernor.decide/apply`）
与 `MODE_DECISION` 文案整段从 `ContinuousAgentEpisode._decide_mode` / `_append_mode_decision_message`
搬进 harness；`mode_governor` / `mode_signals` 两个注入件搬到 `FinanceResearchHarness` 构造器。
`HarnessReferenceLoop` 同样经它裁决——**P2' 钉住的最后一条残余（Episode 独有的 `MODE_DECISION`）
归零，有 PLAN 脚本两条 loop 全程消息一致。** 前序 P0–P2' 已全部合 main（`5292175c`）。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`（§4 #5 → P2 已实施）
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P2 govern_mode 节）

### 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/services/research_harness.py` | `ModeGovernance` / `ModeSignalsFactory` / `default_mode_signals`；`FinanceResearchHarness.__init__(mode_governor=, mode_signals=)`；`govern_mode` |
| `intelligence/runtime/agent_episode.py` | `_decide_mode` 只剩问 harness → 记 `mode_decision` → 换 context → 更新 continuation；`_append_mode_decision_message` 取 `governance.message`；删 `_default_mode_signals`；构造器 `mode_governor` / `mode_signals` 转交默认 harness，自带 harness 时再传 → `ValueError` |
| `intelligence/runtime/harness_reference_loop.py` | PLAN 后 `govern_mode(can_branch=False)`，消息与 Episode 同位追加，`max_slots` 随升档 context 重算 |
| `intelligence/tests/test_research_harness.py` | 29 → 32 |
| `intelligence/tests/test_harness_reference_loop.py` | 有 PLAN 用例：「差恰一条」→「全程一致」 |
| `glm_agent_runtime.py` / `continuous_sub_research.py` | **零改动**（仍传 mode 注入件给 Episode，由 Episode 转交） |

### 红线遵守自证

- `mode_governor.py` 判定零改动；文案逐字搬运（测试按 JSON 逐字段钉）。
- 模型可见字节零改动；durable `mode_decision` 事件零改动。
- `services/` 不 import `runtime/`；生产装配零改动；8792 未碰。

### 下一步（按序）

1. 用户确认 → 合 PR #529（合后主干门禁顺带复核 `test_agent_review_worker` 低负载下绿）。
2. **P2 子研究**：`_run_sub_research`（需 `SubResearchCoordinator`，持状态）与 `_append_sub_research_message`
   的消息投影（三个序号函数）——这是 Episode 剩下的最后一段「对模型说话」的领域文案。
3. **P2 `repair_policy`**：`_recover_finalization` / `_repair_model_complete` / `RepairGoal` /
   `apply_unreachable_downgrade` / `EpisodeFinalizer`——先画状态机。
4. **P2'-live**：8792 切到含 harness 的 revision 后，参考 loop 当第四臂跑 09-01 同题。烧配额，另拍。

### 顺手发现（不属本单）

- Episode 构造器上的 `mode_governor` / `mode_signals` 现在只是转交壳；两处生产调用方
  （`glm_agent_runtime` / `continuous_sub_research`）若改成直接构造 `FinanceResearchHarness(...)`
  传 `harness=`，这两个形参就能删掉。留给合并后的小刀。


## 原文：`inflight/refactor-harness-sub-research-projection.md`（#530（P2 子研究投影））

## 在途交接 · refactor/harness-sub-research-projection

更新：2026-09-02 13:55 CST · **已闭环：PR #530 已合 `gitea/main=d7c9da23`，主干门禁读数见 `inflight/main.md` 顶行，8792 未切。本线（ResearchHarness 接缝 P0→P2）六张 PR 全部合入；剩余 P2 `repair_policy` / 空池回退与 P2'-live 见 spec §9，下一会话另开树。**

### 一句话

`ResearchHarness` 九方法 → 十方法：`project_sub_research(branches, refused_reason, evidence) -> str`。
`ContinuousAgentEpisode._append_sub_research_message` 的 `SUB_RESEARCH_RESULTS` JSON 整段进 harness；
分支类型用结构 Protocol `BranchOutcome` 接（runtime 的 `BranchResult` 天然满足，services 不 import
runtime）。这一刀之后 **Episode 里不再有任何一段领域对模型说的话**，`agent_episode` 从
`episode_protocol` 只剩常量 + `finish_rejection_fields`。前序 P0–P2 govern_mode 已全部合 main（`b8cc9a73`）。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P2 子研究节）

### 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/services/research_harness.py` | `BranchOutcome`（结构类型）+ `project_sub_research` |
| `intelligence/runtime/agent_episode.py` | `_append_sub_research_message` 静态→实例、取 harness；去 4 个 import |
| `intelligence/tests/test_research_harness.py` | 32 → 34（投影逐字段等价 + 棘轮） |
| `_run_sub_research` / `SubResearchCoordinator` | **零改动**（起分支、排空、记事件是底座） |

### 红线遵守自证

- 文案逐字搬运；模型可见字节零改动（`test_agent_episode` 深档分支用例仍绿）；durable 事件零改动。
- `services/` 不 import `runtime/`（结构类型替代 import）；生产装配零改动；8792 未碰。

### 下一步（按序）

1. 用户确认 → 合 PR #530。
2. **P2 `repair_policy`**（先画状态机）：入口清单见 spec §9——`resume()` 修复轮、`_recover_finalization`、
   `apply_unreachable_downgrade` / `unreachable_repair_goal`、`grant_for_transient_model_retry`。
   要先把「什么时候允许再来一轮」（预算，底座）与「修什么、修复提示怎么写、修完算不算进步」（领域）两类边画清。
3. **P2 空池回退**（`_maybe_execute_empty_pool_fallback`）。
4. **小刀**：`glm_agent_runtime` / `continuous_sub_research` 改成直接构造 `FinanceResearchHarness(...)`
   传 `harness=`，删掉 Episode 构造器上的 `mode_governor` / `mode_signals` 转交壳。
5. **P2'-live**：8792 切到含 harness 的 revision 后，参考 loop 当第四臂跑 09-01 同题。烧配额，另拍。


## 原文：`inflight/refactor-harness-repair-policy-split.md`（#531 spec + #532 实施（repair_policy））

## 在途交接 · refactor/harness-repair-policy-split

更新：2026-09-02 19:13 CST · **已闭环：PR #531 → #532 已按序合 `gitea/main=81f1faa0`，主干门禁可采信
（7439P/5F 同基线红 `test_dream_mine` 五例，收据 `20260902T111231Z-81f1faa0.json`，见 `inflight/main.md`
顶行），8792 未切。** 后续单 `fallback_after_empty_batch` 另开树、另立交接。

原文（合并前最后一版）：**`repair_policy` 线实施完毕，状态机 spec §5 五条验收全闭。九个提交已推 gitea，
PR #532（叠 #531）。合 main 等用户确认；8792 未切。**

### 一句话

按 `2026-09-02-repair-policy-state-machine.md` 把修复轮的**预算边与领域边**彻底拆开：七处混合
（M1–M7）各归其位，`ResearchHarness` 从 10 方法到 15 方法（修复轮五个：申请两个 / 不可达裁决 /
开场话 / 修完算不算数），预算算术整体进 `runtime/repair_budget.py`，adapter 与 Episode 都只问
harness，`HarnessReferenceLoop` 从「没有修复轮」变成「与 Episode 在同一段历史上各修一轮、消息 /
事件 / outcome 一致」。**零行为改动**：每一刀都用拆分前 `fed88564` 的实跑金标或网格逐格钉住，
共变异六次全红后恢复。

spec：`docs/superpowers/specs/2026-09-02-repair-policy-state-machine.md`（头部「实施进度」+「§5 五条验收现状」）
父线：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md` §5 协议（十五方法）/ §9 P2

### 提交（按序，均叠在 #531 的 `fed88564` 上）

| SHA | 刀 | 改动面 |
|---|---|---|
| `e4657a11` | M1–M4 | `should_reenter` → `repair_is_warranted` ∧ `can_afford_repair`；`work_units` → 格数 × 换算；`grant_for_progress` 三行编排；`_mint_grant` 唯一记账点 |
| `8cc02f1f` | M6 | 三个 candidate 判据 + 两个 stop_reason 集合从 adapter 搬进 `services/repair_coordinator.classify_repair_failure -> RepairFailureShape` |
| `fb0666aa` | M5 | 新 `runtime/repair_budget.py`（五种 `grant_for_*`、两个 `admit_*`、预算算术）；`services/repair_coordinator.py` 只剩领域侧 |
| `0866b047` | 交接 | 本文档首版 |
| `3df916c2` | §4 执行体半 | harness 加 `repair_goal_message` / `admit_repair_result`（→12）；`SteeringKind` 加 `repair_finalize`；`resume()` 三处改走 harness |
| `6b68c98b` | 交接 | 补 SHA |
| `5288d4c4` | §4 准入半 + M7 | `RepairNeed`（+ `needs_tools`）/ `RepairWarrant`；harness 加 `classify_repair_need` / `warrant_repair`（→14）；`repair_budget` 改为**被告知**；adapter 构造注入 harness（`api/app.py` 零改动） |
| `d9b46afa` | 不可达降级 | harness 加 `downgrade_unreachable -> RepairDowngrade`（→15）；Episode 与 adapter 都问它；Episode 从 `repair_coordinator` 只剩 `RepairGoal` |
| `fa5e162a` | 参考 loop | `ReferenceLoopState` + `_ingest_batch` + `resume()` 一轮修复；与 Episode 同一台机器 |

### 现在的层次

```
services/repair_coordinator.py   领域：值对象（RepairGoal / RepairNeed / RepairWarrant / RepairFailureShape …）
                                 build_repair_goal / unreachable_repair_goal / tier·进度·格数判据 /
                                 classify_repair_failure / classify_repair_need / warrant_repair
services/research_harness.py     15 方法；修复五方法的默认实现是 resume() / adapter 原文逐字搬入
runtime/repair_budget.py         底座：can_afford / calls_for_work_units / size_repair_window / _mint_grant /
                                 grant_for_* ×5 / admit_repair(need, warrant, …) / admit_backfill_repair
                                 —— 只读申请，不 import 任何领域判据
runtime/continuous_turn_adapter  编排：算余量 → 问 harness 要 need / warrant → admit_repair → resume →
                                 按 harness 降级后的契约验
runtime/agent_episode.resume()   执行体：问 harness 五件事；deadline·瞬态重试·工具批·_carry_repair_finish 留 loop
runtime/harness_reference_loop   第二条 loop：run + resume，只调 harness + ToolBatchExecutor
```

授予协议落地：**领域申请（`RepairNeed` / `RepairWarrant`），底座授予（`_mint_grant` 是修复线唯一
`root_budget.grant()` 调用点），领域不碰账本。** M7 的 `reopen_tools` 从 goal 上搭便车的 bool 变成
`RepairNeed.needs_tools` 申请 + 底座 `grant_for_cold_restart` 批准后盖章。

### 与状态机 spec §4 建议签名的两处差（有意）

- `repair_is_warranted -> bool` 改成 `warrant_repair -> RepairWarrant{cycle_allowed, progressed}`：交付
  修复只需 tier 闸不需进度闸，两个事实得分开摆。`repair_is_warranted` 仍在 services 作 bool 便写。
- `classify_repair_need` 不返回 `None`：等价优先；「不值得修」由 shape 全 False + 进度闸表达，与拆分前
  `admit_repair` 的分流逐格相同。

### 验证（venv 解释器 `.venv-workbench/bin/python`，cwd 本树）

- `test_repair_policy_split.py` 38 例：360 格 `should_reenter`、336 格 work_units、1008 格失败分类、
  30 组授予金标、AST 棘轮（adapter 不 import 六个判据符号、必经 `self._harness.*`）。
- `test_research_harness.py` 第 7 节 8 例：REPAIR_GOAL / `repair_finalize` 字节等价；48 格裁决；不可达
  裁决三形状逐字段等价；有牙三条（自定义话真到模型眼前；改判 harness 让 stop 变 finish；不降级 harness
  让 trace 无 `unreachable_without_tools`、模型仍看到那个格）；棘轮（Episode 从 `repair_coordinator` 只
  import `RepairGoal`、不 import `mandatory_satisfiability`）。
- `test_continuous_turn_adapter.py` +4：`warrant_repair ≡ 不容忍` → `repair_cycles` 1→0；只报 delivery 的
  分类器 → 冷启动窗不出现（均看 outcome）。
- `test_harness_reference_loop.py` 6 → 9：零额度修复轮 / 带额度修复轮两条 loop 消息、`repair_goal` 事件、
  outcome 一致；修复失败结转上一轮稿。
- 变异六次全红后恢复：`_MAX_REPAIR_CALLS` 4→5（红 2）；去 progressed 闸（红 4）；冷启动去零证据闸
  （红 1）；loop 忽略 `verdict.progressed`（红 4）；`admit_repair` 忽略 warrant（红 8）。
- 宽网 `-k "repair or episode or harness or glm or sub_research or continuous or runtime or adapter or
  track_contract or conformance or switchboard or provider_latency or profile or steering or protocol or
  fault or satisfiab or reference"` **2160P / 5S / 1xfail**；ruff `intelligence/` 全过；`layer_audit`
  ERROR 0 == 基线；pre-commit 十一道门禁每次全过。

### 下一步（按序）

1. 用户确认 → 先合 #531，再合 #532（叠着的；#531 若 squash 合入，#532 需 rebase）。
2. 合后 8792 切流时带上（零 live 判据，与前六张 PR 同纪律）。若想复现 P2'-live 第四臂：
   `finance-base-ab/shape_lib/reference_loop_arm.py` 里「resume 抛无修复轮」的壳改调
   `HarnessReferenceLoop.resume`（实验树，本仓不动）；预期 Episode 臂 `repair_model_stop` 与参考 loop 臂
   的差不再是「没有修复轮」造成的。
3. **`fallback_after_empty_batch`**（decouple spec §4 #8）：与 `repair_policy` 同为「持状态、改控制流」，
   先画状态机再抽。`_maybe_execute_empty_pool_fallback` 在 `agent_episode.py`，`empty_pool_fallback.py` 253 行。
4. `_recover_finalization` 是否并进 repair cycle：独立决定，需用户拍。

### 顺手发现（不属本单）

- `services/mode_governor.py:273` 升档授予在领域层直接 `root.grant()`，与 M5 同一种错层，归 `govern_mode` 线。
- `intelligence/eval/fixtures/capability_switchboard.json` `repair-chain` 行 notes 里的旧 file:line 是搬前坐标，
  已追加一句说明，未重写历史文本。

### 红线遵守自证

- `episode_protocol.py` / `evidence_ledger` / verifier 判定零改动；事件 payload 键与顺序不变（Episode 三处
  只是改从 harness 取值）；`api/app.py` / 8792 / 启动器 / 快照未碰。
- 未放宽任何闸门：`unreachable_repair_goal` 原样；A→B→C 优先级链原样；`_TRANSIENT_RETRY_LIMIT` 原样。
- 提交一律 pathspec，未 `git add -A`。合 main 等用户确认。


## 原文：`inflight/spec-harness-empty-pool-fallback.md`（#533（空池回退））

## 在途交接 · spec/harness-empty-pool-fallback

更新：2026-09-02 19:46 CST · **已闭环：PR #533 已合 `gitea/main=7c241ac0`，主干门禁可采信（7443P/5F 同基线红
`test_dream_mine` 五例，收据 `20260902T114611Z-7c241ac0.json`，见 `inflight/main.md` 顶行），8792 未切。
ResearchHarness 接缝线（decouple spec §4 表）至此抽完，本线无后续单。**

原文（合并前最后一版）：**`fallback_after_empty_batch` 画完即抽，两个提交（spec + 实施）已推 gitea，PR 见下。
合 main 等用户确认；8792 未切。**

### 一句话

decouple spec §4 表里最后一行要抽的接缝。与 `repair_policy` 同一套判据画状态机，结论不同：这台机器只有
一条入口、九道判定全在 `services/empty_pool_fallback.propose_empty_pool_fallback`（纯函数）、恰好一次靠扫
durable 事件——**没有方向相反的错层，不需要先拆再搬**。要收的只有 loop「凑领域判定的输入 + 认识回退
概念」两处。`ResearchHarness` 十五 → 十六方法；`HarnessReferenceLoop` 同位跑同一枪，文首「无空池回退」
那条差消掉。**零行为改动**：既有 4 条 Episode 级用例原样绿，默认接缝与直接调纯函数四形状逐字段相同。

spec：`docs/superpowers/specs/2026-09-02-empty-pool-fallback-state-machine.md`（头部「状态：已实施」）
父线：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md` §4 #8 / §5（十六方法）/ §9 P2

### 提交

| SHA | 内容 |
|---|---|
| `15a7cbe7` | spec：一条入口、九道判定归层、出口、与补枪的双向互斥、两处混合（X1 凑输入 / X2 accumulator 认 call_id 前缀）、接缝签名、三种替代方案为何不选、四条验收 |
| `23a3868f` | 实施：`ToolCallOutcome`（结构声明）+ `FallbackCall{call, request_extras}` + `fallback_after_empty_batch`；Episode 只判剩余槛、算可派工具集、问 harness、派、记 extras，不再 import `empty_pool_fallback`，accumulator 的前缀兜底删掉；参考 loop 每批后同位问同一方法并执行，`_ingest_batch` 加 `request_extras`，pending 深度消息挪到停机判定之后（与 Episode 同序） |

### 接缝

```python
def fallback_after_empty_batch(
    self, batch: Iterable[ToolCallOutcome], *,
    context, registry, authorized_tools: frozenset[str], events: Iterable[object], in_repair: bool,
) -> FallbackCall | None
```

底座递五样自己拥有的事实（本批 `(call, status)` / 此刻真能派的工具 / 事件流 / 阶段 / **调用前**先判剩余槛）；
领域从 `context.information_cutoff` / `registry.opening_prefetch` / `events` 读其余。返回 harness 自己的值
对象而不是 `FallbackProposal`——第二条 loop 的「不 import 任何领域模块」棘轮不动。

### 验证（venv 解释器，cwd 本树）

- `test_empty_pool_fallback.py` +3：等价（空池命中 / 首轮有行 / 预取有行 / 已补过·修复轮 四形状逐字段）；
  有牙（从不回退的 harness → Episode 只跑一次 `finance_query`、无 `fallback_query` 事件；改排涨幅的
  harness → runner 真收到的参数与事件标记随之变）；第二条 loop（同一空池脚本下两条 loop runner 收到的两次
  参数逐字段相同、补查 `tool_request` 领域投影相同、模型消息相同只差 `runtime_budget`、outcome 相同）。
- `test_research_harness.py` +1 棘轮：Episode 不 import `empty_pool_fallback`、源码无 `"empty-pool-fallback"` /
  `"fallback_query"` 字面量、必经 `self._harness.fallback_after_empty_batch`。
- 变异：默认实现硬写 `in_repair=True` → 红 5，恢复后绿。
- 宽网 `-k "repair or episode or harness or glm or sub_research or continuous or runtime or adapter or
  conformance or fallback or empty_pool or backfill or issue or reference or steering or protocol"`
  **2072P / 5S / 1xfail**；ruff `intelligence/` 全过；`layer_audit` ERROR 0 == 基线；pre-commit 十一道门禁全过。

### 下一步

1. 用户确认 → 合 PR；合后跑主干门禁写台账（与 #532 同规程）。
2. 8792 切流时带上（零 live 判据）。
3. **decouple 线 §4 表已抽完。** 剩下的都是明写「属底座、不抽」或「独立决定」的：#9 预算可见性（底座）、
   `_run_sub_research`（需协调器）、`_recover_finalization` 是否并进 repair cycle（需用户拍）、
   `_carry_repair_finish` 两行取舍。再往下是 09-01 spec §11 的「真接 pi-agent-core / 真接 dsh」，那要先推翻
   08-17「不保留运行时依赖」的裁定，不是本线能自行立案的。

### 红线遵守自证

- `empty_pool_fallback.py` 九道判定 / as-of 口径 / `FALLBACK_LIMIT` / 与补枪的互斥零改动；`resume()` 仍不回退。
- 事件 payload：`tool_request` 的回退标记键名与值不变（`fallback_query` / `original_arguments` / `as_of`）。
- 提交一律 pathspec；生产快照 / 8792 / 启动器未碰。

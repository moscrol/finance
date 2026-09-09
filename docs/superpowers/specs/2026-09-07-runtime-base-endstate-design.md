# 运行底座终局：从「跑完才落盘的研究流程」到「每一步可恢复、可拦截、可重建、可机器验证的运行时」

> 日期：2026-09-07
> 状态：**草稿待审**（§12 待拍板五题；未拍板前按推荐答案执行）。**P0 已随本分支落地**（09-07：`services/episode_messages.py`、三种载体事件、两条 loop 请求前对账、投影剔正文、`scripts/gen_runtime_catalog.py` + `docs/runtime/`；见 §6.1 与在途交接），其余阶段各开工单。
> 触发：用户 2026-09-07 拍板——「既然换不了底座，那就把他俩的工程设计我们欠缺的部分补上。总之我要达到他们那种运行底座的效果。其他的就是我们领域 harness 的优化，那部分我让 agent 继续打磨。」
> 对照源（只读，不引入为运行时）：pi `/Users/a77/pi` @ `853a80d26`（2026-08-28；`packages/agent/docs/harness.md` 2900 行实现规格、`packages/agent/src/{types,agent-loop}.ts`、`harness/`）；dsh `/Users/a77/deepseek-harness` @ `99f6f02`（0.1.0-rc.7；`docs/architecture.md`、`docs/defensive-patterns.md`、`docs/subsystems/{core,invariants}.md`、`packages/core/{agent,session,tools}/src`）。两者都比 08-15 吸收稿钉的 `47f9438` 新。
> 父稿：`2026-08-15-agent-base-dsh-absorption-design.md`（决策记录，停变：生产主线 Python、dsh 只做形状尺）；`2026-08-22-harness-seams-to-learn-design.md`（学习合同：§2「已经接上，别再当缺口」本稿全部遵守）；`2026-09-02-research-harness-loop-decouple-design.md`（接缝线：16 方法、第二条 loop）；`2026-09-01-finance-base-shape-alignment-design.md`（形态对齐；只在足迹分支 `10f7d73c`）。
> 词表：新词见 §2，落 `UBIQUITOUS_LANGUAGE.md` 待本稿审过。

---

## 0. 一句话

把 `ContinuousAgentEpisode` 从「一个跑完才把事件写成产物的研究流程」改成「每一步都可恢复、外部随时可递话、模型看到的每个字都能从日志重建、不变量与竞态由测试机器验证的运行时」。判据不是目录像 pi 还是像 dsh，而是 §3 六条设计不变量在本仓成立。

完成标准：读完本文能答四件事——进程在任意一步死掉之后重启会发生什么；模型这一轮看到的每个字来自哪条事件；用户或子研究在 episode 跑着的时候怎么把话递进去；哪条不变量被破了哪个测试会红。答不出就本文没写完。

---

## 1. 两家的哲学各是什么、我们的哲学是什么

| | pi（harness.md） | dsh（architecture.md） | 本仓（今天） |
|---|---|---|---|
| 一句话 | **先把「进程在任意两次提交之间死掉」钉死，再谈功能** | **先分清这件事属于哪一类事件，再谈实现** | **先保证金融答案对，再谈运行时** |
| 真源 | 三种存储：entries 只写一次 / registers 覆写当前值 / usage ledger 只追加；「每个 payload 只在一处」 | 追加式 `SessionEvent` 日志；模型历史 `deriveMessages()` 派生 | `_EpisodeLedger.events` 内存列表 + `messages: list[dict]` 两份并行 |
| 恢复 | 每步覆写一份**完整** `op.state`（durable program counter）；恢复 = 5 次点查 + switch | persistence backend 重载时给 crash-orphaned turn 补 `turn/end{interrupted}` | 无。事件只在 episode 结束时随 `continuous-episode.json` 落盘一次 |
| 外部效果 | 意图提交（预留 id）→ 不确定窗口 → 结算提交；工具声明 `replay: never/safe` | `tool/call` 先落日志再执行；`tool/result` 单一模型可见结果 | `tool_request` 事件在派发前 add（内存），无 durable 意图 |
| 取消 | abort 是 control 不是 phase；`aborted` ⇔ signal 被拉；超时/传输失败一律 `error` 走重试 | `AgentCancelCause = user\|parent\|hook\|disposed`，first cause wins，`keepInbox` | `is_cancelled: Callable[[], bool]`；`cancel_reason` 自由字符串 |
| 输入 | `getSteeringMessages / getFollowUpMessages` + `QueueMode` | `Inbox`：`send(msg, target=next-turn\|next-step, wakeup)`；splice 落日志 | 无。`run()` 之后不收外部输入 |
| 验证 | 21 条不变量 + 12 条竞态（两序）+ 三档测试（状态恢复 / 写序 oracle / 确定性交错） | 每包 `./invariant` 伴生插件 + `verify-package-invariants` 机械校验；`defensive-patterns.md` | 8 条 INV × 5 后端 conformance 矩阵 + 五档能力声明 + 棘轮 baseline（**长项**） |
| 文档 | 每个类型标注来源文件 | 目录（cordis / 事件生产消费 / 工具）从源码生成，CI 保鲜 | 手写 spec / handoff；唯一机器对账是 `test_durable_kind_table_matches_every_runtime_emitter` |

本稿的态度：**学形状、不搬量纲、不搬实现。** pi 的 SQLite 事务细节、dsh 的 Cordis 插件树、两家的 TS 类型体操一律不搬；搬的是六条不变量和它们逼出来的接缝。

---

## 2. 钦定词

| 词 | 它是 | 不要写成 |
|---|---|---|
| **意图 / 结算**（intent / settlement） | 外部效果（模型请求、工具执行）前后各一条 durable 事件；意图里预留结算要用的 id | 「开始 / 结束日志」；只有结算没有意图 |
| **不确定窗口** | 意图已 durable、结算未 durable 的那段时间；系统里唯一允许存在的不确定 | 「可能丢了」；任何其他位置的不确定都是 bug |
| **程序计数器**（`EpisodeState`） | 每步覆写的一份**完整**状态，恢复只读它 | 从事件重放推断位置；从缺席推断 |
| **重放安全**（`replay ∈ {safe, never}`） | 工具的声明：崩溃后能否用同参数重跑 | 「幂等」（那是效果侧的性质，声明是意图侧的） |
| **收件箱**（inbox） | 外部输入进 episode 的唯一通道，两个队列 `next_turn` / `next_step`，入箱 / 认领 / 丢弃三事实 durable | 直接往 `messages` append |
| **模型可见即已落账** | 每次请求发出的消息列表 == `derive_messages(events)` | 「事件里有 hash 就行」 |
| **Episode 消息**（`EpisodeMessage`） | 本仓自己的消息类型，只在 provider 边界转线格式 | OpenAI 风格 `dict` 满地跑 |
| **取消原因**（`CancelCause`） | 类型化枚举，first cause wins | 布尔谓词；自由字符串 |
| **写序 oracle** | 包住存储 `append` 的 spy，断言每笔事务的写序 | 靠 `sequence` 单调就算对 |
| **竞态目录** | 每条竞态两种合法历史，两个顺序都有测试 | 「加了锁应该没问题」 |

「Durable」一词在本稿里**收紧**：08-15 §7.4 的 Durable 只要求「进重放日志」，本稿要求「落盘且崩溃可读」。旧文档里的 Durable 读作「重放车道」，不改旧稿。

---

## 3. 六条设计不变量（终态判据）

| # | 不变量 | 破了谁红 |
|---|---|---|
| **INV-R1** | 每次模型请求发出的消息列表 == `derive_messages(durable_events)`，逐字节 | `test_derive_messages_matches_sent`（P0）；生产侧不炸、计 `derive_mismatch` |
| **INV-R2** | 任何外部效果前有 durable 意图（含预留 id）、后有 durable 结算；崩溃只留下「意图有、结算无」一种不确定 | 写序 oracle（P2） |
| **INV-R3** | 恢复 = 读一份完整 `EpisodeState` 并 switch；不重放日志推断、不从缺席推断 | Tier A 状态恢复套件（P2）：每个 phase 构造 → 关 → 开 → 断言下一动作 |
| **INV-R4** | 结算 `stop_reason=cancelled` ⇔ 取消原因已 durable；超时 / 传输 / provider 拒绝一律 `error`；未派发 ≠ 超时 | conformance INV-4 扩（P1） |
| **INV-R5** | 外部输入经且仅经收件箱；入箱 / 认领 / 丢弃三事实 durable | `test_inbox_*`（P3） |
| **INV-R6** | 竞态目录每条两序有测；写序由 oracle 断言 | `conformance/races/`（P4） |

与既有 8 条 INV 的关系：既有 INV-1..8 是**后端 × 不变量**矩阵（工具可见性、预算、reserve、取消、修复重入、trace 收据、finish 协议、resume 五条），本稿 R1–R6 是**运行时持久性与输入面**，两张表不合并，R 系列只在 `continuous_glm` 与 `HarnessReferenceLoop` 两条 loop 上要求成立（`sdk_gpt` / `codex_headless` 声明 `UNSUPPORTED_DECLARED`，理由：非生产臂）。

---

## 4. 现状与差距（[实测] 逐条）

| # | 差距 | 现状 [实测] | 终态 | 阶段 |
|---|---|---|---|---|
| G1 | Durable 事件不 durable | `_EpisodeLedger.events` 是内存列表（`agent_episode.py:216`）；`continuous-episode.json` 只在 `conversation_orchestrator.py:4078/4307` 结束时写；`resume()` 吃同进程 `_EpisodeContinuationState`；`RuntimeHandle` docstring 的四类验收场景已把 08-15 §7.3 的「进程重启」换成「正常完成」 | 每步 append 落盘 + `EpisodeState` 覆写；重启可 `restore()` | P2 |
| G2 | 模型可见 ≠ 已落账 | `tool_result` 事件存 `audit_payload`，模型看的是 `model_content`（`agent_episode.py:438-448`）；四处 user 角色注入（`:1074` invalid_plan steering、`:2112` mode_decision、`:2152` tool_budget_state、`:2210` finalization）只落 reason 不落文本；system prompt 与首轮 user JSON 只有 `task_frame_hash` | `derive_messages(events)` 存在且被断言 | **P0** |
| G3 | 消息是 provider 线格式 | `messages: list[dict[str, object]]`（`_EpisodeContinuationState.messages`）；`role/content/tool_calls/tool_call_id` OpenAI 形状贯穿 loop | `EpisodeMessage` 类型，`to_provider()` 只在 `AgentModelClient` 边界 | P1 |
| G4 | 取消 / 超时不分、取消无类型 | `is_cancelled: Callable[[], bool]`（`agent_episode.py:573`）；`episode_tool_batch.py:45`「授权额 ≤0 未派发、真跑了再超时共用 `error=tool_timeout`」，只靠 `detail=stage_timeout_granted=` 区分 | `CancelCause` 枚举；`tool_not_dispatched` 与 `tool_timeout` 两码 | P1 |
| G5 | 无收件箱 | `run()` 后无外部输入面；`rg -i 'steer\|inbox' intelligence/runtime` 只命中 `harness.steering_message`（loop 对模型说话，不是外部输入） | `Inbox` + 三事实 durable + Workbench `steer` 端点 | P3 |
| G6 | 配置快照做了一半 | `configure` 事件只在 codex / orchestrator 发，continuous 臂无；`served_model` 09-03 才进产物；run 中途读 `_TOOL_CONTRACTS` / `prompt_block` / provider 链活对象 | `configure` 成完整快照，恢复只用快照 | P2 |
| G7 | 竞态与写序无测 | INV-4 只测起跑前取消与批次执行前取消；`_EpisodeLedger.add` 注释自陈「今天所有 add 都在主线程」；无写序断言 | 竞态目录 + oracle | P4 |
| G8 | 三张表手写 | 26 个 durable kind、12 工具 + `_TOOL_CONTRACTS`、harness 16 方法无生成文档 | `scripts/gen_runtime_catalog.py` → `docs/runtime/*.md` + 保鲜测试 | **P0** |
| G9 | 产物无 schema 版本 | `EpisodeEvent(sequence, kind, payload)` 无版本；`AgentOutcome.events` / `continuous-episode.json` 无版本字段；老读者遇新 kind 行为未约定（`project_durable_events` 保留并记 `unregistered_kinds`，是对的，但只在投影层） | `EPISODE_LOG_VERSION` + 每事件 `ignorable` 语义 | P2 |
| G10 | 抛 / 返回无总规则 | `RuntimeHandle` 用异常表门、`CallbackEpisodeSession` 映射回 `EpisodeSessionError`；tool batch 归一为结构化结果；`EpisodeScope.emit` 吞并计数 | 一条写进 `docs/runtime/defensive-patterns.md` 的总规则 | P4 |

学习合同 §2 里已接上的东西（Durable/Live 表、`ToolPipeline`、Scope/Handle/Profile、`view()` 唯一投影、压缩第 1 层、single-flight、截止日注入、说明书、`EpisodeFinishRejection`）**本稿不重做**。G2 的 `derive_messages` 是对 `episode_projection` 的补充（那是对外投影，这是对内重建），不是第二份投影。

---

## 5. 与领域 harness 的分工（写死，两拨 agent 并行的依据）

**底座改**（本稿范围）：`intelligence/runtime/{agent_episode,harness_reference_loop,glm_agent_runtime,episode_tool_batch,continuous_turn_adapter}.py`；`intelligence/services/{agent_runtime,episode_scope,runtime_handle,episode_event_lanes,episode_session,episode_projection,research_profile}.py`；新增 `services/{episode_messages,episode_store,episode_inbox}.py`；`scripts/gen_runtime_catalog.py`；`intelligence/tests/conformance/**`。

**harness 不动**（另一拨 agent）：`services/research_harness.py` 16 方法的**语义与签名**、`episode_protocol`、`episode_semantic_verifier`、`evidence_ledger`、`research_contract`（90/60/30）、`research_tool_registry` 里 12 个工具的 `execute` 与 `_TOOL_CONTRACTS`、`repair_coordinator`、`tier_promotion` 的裁决逻辑。

**两处接触点，先 spec 后动**：
1. `ToolSpec` 加字段 `replay: Literal["safe", "never"] = "safe"`（P2）——只加字段不改行为，12 个只读工具默认 `safe`；写工具将来注册时必须显式 `never`。
2. `ResearchHarness` 加方法 `admit_inbox_message(message) -> bool`（P3）——领域决定收件箱里的话收不收（例：拒收含个股买卖指令的 steer），默认实现恒 `True`。这是本稿**唯一**新增的 harness 方法，P3 开工前单独过一遍接缝线纪律（「有牙」：换实现能改 outcome）。

冲突处理：底座 PR 若必须碰上面「不动」清单里的文件，只允许**机械**改动（改 import 路径、传参名），diff 里不得出现任何领域判据字面量；否则拆出来走 harness 那拨。

---

## 6. 分阶段切片

依赖顺序：P0 → P1 → P2 → P3 → P4。P0 与 P1 零 live 判据；P2 起改生产行为，切 8792 按五步规程。每阶段独立工单、独立分支、独立门禁收据。

### 6.1 P0：模型可见即已落账 + 三张目录（零行为改动）

**做什么**

1. 新 `intelligence/services/episode_messages.py`：`derive_messages(events: Sequence[EpisodeEvent]) -> list[dict[str, object]]`，只读 durable 事件，输出与今天 `messages` 同形的列表（P1 再换类型；P0 先让两边逐字节相等）。
2. 补账三处（都是**往已有事件 payload 加字段或加一种新 kind**，不删不改既有字段）：
   - `tool_result` payload 加 `model_content`（`project_tool_result` 已返回它，loop 只是没写进事件）；`tool_error` 已带模型看到的原 payload，不动。
   - 新 kind `model_input`：payload `{role: "user", content, source ∈ {steering_invalid_plan, steering_invalid_finish, finalization, mode_decision, tool_budget_state, opening}}`，四处注入点各发一条。归 **durable**（它是模型可见内容，重放消费者必须看得到）。
   - 新 kind `prompt_assembled`：payload `{system, user, tool_schema_hash, instructions_hash}`，`assemble_prompt` 之后、首轮请求之前发一条。归 durable。
3. 断言：`ContinuousAgentEpisode` 与 `HarnessReferenceLoop` 每次调 `model.complete` 前调 `check_derivation(ledger.events, messages)`；不等时 `EpisodeScope` 计 `derive_mismatch`（与 `event_sink_failures` 同族：**生产不炸**），测试模式（`FORESIGHT_STRICT_DERIVATION=1` 或 pytest 下）抛错。
4. 投影边界：`project_durable_events` 对全部模型可见正文字段（`prompt_assembled.{system,user}`、`model_input.content`、`tool_budget_state.model_content`、`tool_result.model_content`、`tool_error.model_content`；表在 `episode_messages.MODEL_VISIBLE_TEXT_FIELDS`）**默认剔正文只留 `<field>_sha256` + `<field>_chars`**——workbench trace「不带 prompt 正文」纪律（`test_conversation_orchestrator.py:6364`）只约束对外投影，进程内的 ledger 与 P2 的私有 store 带正文。加参数 `include_model_visible_text: bool = False`，只给不出仓的读者。**落地口径（09-07）**：artifact 仍是一个 `events` 数组（五个下游共用），默认剔正文；不为 `continuous-episode.json` 另造第二份全文数组——INV-R1 的在线对账在进程内对未剔的 ledger 做，离线全文重建等 P2 store。
5. `scripts/gen_runtime_catalog.py`：从 `DURABLE_EVENT_KINDS` / `LIVE_EVENT_KINDS` + 各发射点 docstring、`_DEFAULT_TOOL_METADATA` + `_TOOL_CONTRACTS`、`ResearchHarness` 协议方法签名与 docstring 生成 `docs/runtime/{events,tools,harness-seams}.md`；`test_runtime_catalog_fresh` 比对生成物与仓内文件，不一致即红（pre-commit 第 12 道候选，先只做 pytest）。

**验收**

- 全量 pytest 与 main 同结果（新增 kind 进 `DURABLE_EVENT_KINDS`，`test_durable_kind_table_matches_every_runtime_emitter` 绿）。
- 新夹具：脚本化模型跑 有 PLAN / 无 PLAN / 修复轮 三条路径，每次请求前派生消息与实际发送逐字节相等；两条 loop 都过。
- 投影夹具：默认投影不含 `system` 正文与 `model_input.content` 正文，只有 hash；`include_model_visible_text=True` 时含。
- 三张目录生成后 `git diff --exit-code docs/runtime/` 为空。
- ruff / layer_audit 绿（`episode_messages.py` 只 import `services.*`）。

**非目标**：不改 harness 方法签名；不改 90/60/30；不换消息类型；不落盘。

**已知边界（09-07 落地时确认）**：(a) `EpisodeFinalizer.recover` 的兜底合成是一次独立的小模型调用，用自己拼的 prompt，不在 episode `messages` 里，INV-R1 不覆盖它——P2 若要覆盖，给它发 `prompt_assembled{source: finalizer}`；(b) `openai_agents_runtime`（sdk 臂）与 `headless_tool_gateway` 也发 `tool_result` / `tool_error`，但不带 `model_content`，`derive_messages` 对这些流抛 `DerivationUnavailable`——它们不是 R 系列的适用臂（§3 末段），投影层对缺字段的事件原样保留；(c) 派生规则里 `model_turn` 带 `error` 不产生 assistant 消息，参考 loop 修复轮原本在错误检查前 append，本轮改为检查后（错误后无请求，模型可见行为不变）。：Episode 消息类型 + 取消类型化 + 错误码拆分

1. `services/episode_messages.py` 加 `EpisodeMessage`（frozen dataclass：`role ∈ {system,user,assistant,tool}`、`content`、`tool_calls`、`tool_call_id`、`source`、`visible_to_model: bool = True`）与 `to_provider(messages, dialect="openai") -> list[dict]`；`_EpisodeContinuationState.messages` 换类型；`glm_agent_runtime.py` 的 provider 链在边界转线格式。`derive_messages` 改返回 `list[EpisodeMessage]`，INV-R1 比较两边 `to_provider()` 结果。
2. `services/runtime_handle.py`：`CancelCause = Literal["user", "parent", "hook", "deadline", "disposed"]`；`request_cancel(cause: CancelCause, detail: str = "")`；`is_cancelled` 谓词换 `CancelSignal`（`.requested`、`.cause`、`.detail`），first cause wins；`agent_episode` 与 `episode_tool_batch` 读 `.cause` 写进 `finish.stop_reason_detail`。
3. `episode_tool_batch.py`：`error=tool_timeout` 拆为 `tool_not_dispatched`（`stage_timeout_granted <= 0`，未进线程池）与 `tool_timeout`（真跑超时）。模型可见 detail 保留 `stage_timeout_granted=`；`scripts/offline_tool_duration_floor.py`、`audit_episode_tool_outcomes.py`、`eval/abstention.py` 同步读两码。**这是 P1 唯一一条模型可见文案改动，合入前走一次 live 探针（茅台参考题两臂）。**
4. conformance INV-4 加三行：取消带原因、未派发与超时两码、`stop_reason=cancelled` 必伴随 durable cause。

**非目标**：不落盘（P2）；不动 `_TOOL_CONTRACTS` 文本。

### 6.3 P2：Durable 存储 + 意图/结算 + 恢复 + 配置快照 + 版本

1. `services/episode_store.py`：`EpisodeStore` Protocol——`append(episode_id, events)`、`put_state(episode_id, state)`、`load(episode_id) -> (events, state)`、`list_open()`。两个实现：`MemoryEpisodeStore`（测试）、`JsonlEpisodeStore`（生产，落 `~/.finance-runtime/episodes/<episode_id>/{events.jsonl,state.json}`，与 `deploy-ledger.jsonl` 同族；`state.json` 原子替换 `os.replace`）。SQLite 留接口不实现（§12 第 1 题）。
2. `EpisodeState`（frozen dataclass，完整状态）：`phase ∈ {planning, model_pending, tools_pending, repair, finalizing, done}`、`turn_index`、`reserved_ids`（下一条 model_turn / tool_result 的 sequence）、`consumed_seconds`、`contract_snapshot`、`cancel: CancelSignal | None`、`log_version`。每次 phase 转移覆写。
3. 效果三明治：`model_turn` 前新增 durable `model_intent{turn_id, reserved_sequence, timeout_asked}`；`tool_request` 保持为意图，payload 加 `replay`（读 `ToolSpec.replay`）；`tool_result` / `tool_error` / `model_turn` / `model_error` 是结算。fsync 策略：意图 append 后 `fsync`，结算 append 不 fsync（崩溃丢结算 = 落回不确定窗口，策略表能处理）。
4. `ContinuousAgentEpisode.restore(episode_id, store) -> AgentOutcome | ResumePlan`：策略照 pi §4.5 三行——模型意图无结算 → 捕获的重试策略允许则再试一次，否则合成 `model_error{interrupted}`；工具意图无结算 → `replay=safe` 且当前声明仍 `safe` 才重跑，否则合成 `tool_error{interrupted}`；`cancel` 已 durable → 合成 `finish{stop_reason=cancelled}`。合成事件用意图里预留的 sequence。
5. `configure` 事件在 continuous 臂发出完整快照（provider 链、model、policy tier、timeouts、tool contracts hash、instructions hash、served_model 留空待首轮回填）；`restore` 只读快照不读活对象。
6. `EPISODE_LOG_VERSION = 1` 写进 `state.json` 与 `continuous-episode.json`；`EpisodeEvent` 加可选 `ignorable: bool`（默认 False）；`derive_messages` / `restore` 遇未登记且非 `ignorable` 的 kind **拒绝**并报 `unknown_required_kind`，不静默跳。
7. 接线：`GLMAgentRuntime.start` 构造 store 并传给 Episode；`conversation_orchestrator` 的 `continuous-episode.json` 改从 store 读（形状不变）；启动时 `list_open()` 的 episode 只登记不自动恢复（§12 第 3 题）。
8. `RuntimeHandle` 四类验收场景改回 08-15 原文（取消 / 超时 / Provider 失败 / **进程重启**），第四类由 Tier A 套件兑现。

**验收**：Tier A——每个 phase 构造 durable 状态、丢弃对象、`restore`、断言下一动作；每个 crash 前缀（意图前 / 意图后结算前 / 结算后）的恢复结果与不间断跑一致；写序 oracle 装在 `store.append` 上断言「意图 seq < 效果开始 < 结算 seq」；`JsonlEpisodeStore` 撕裂末行整行丢弃；`Memory` 与 `Jsonl` 同场景字节同结果。8792 切流后探针一次 + 手工 kill -9 一次 episode 中途，重启后 `list_open()` 能列出且 `restore` 给出合成 finish。

**非目标**：多进程写者、跨机复制、provider stream 续传（pi §0.6 三条照抄）；自动后台恢复（先手动）。

### 6.4 P3：收件箱

1. `services/episode_inbox.py`：`Inbox`——`send(message: EpisodeMessage, target ∈ {next_turn, next_step}, wakeup: bool)`；`claim(target) -> list[EpisodeMessage]`；durable 事件 `inbox_inserted / inbox_claimed / inbox_discarded`（payload 带 `message_id`、`source`）。loop 在每次模型请求前 `claim(next_step)`，模型停下且无工具调用时 `claim(next_turn)`（对应 pi `getSteeringMessages` / `getFollowUpMessages`）。
2. 领域接触点：`ResearchHarness.admit_inbox_message(message) -> bool`（§5 第 2 条），拒收的走 `inbox_discarded{reason}`。
3. 子研究回灌：`_run_sub_research` 的结果不再内联拼进 `messages`，走 `inbox.send(..., target=next_step, source="sub_research")`。
4. Workbench：`POST /api/conversations/{id}/steer`（§12 第 4 题决定本轮做不做端点；底座与 CLI 先做）。
5. 取消与收件箱：`cancel(cause, keep_inbox=False)`——默认清箱并落 `inbox_discarded{reason=cancelled}`。

**验收**：INV-R5；竞态「steer 到达 vs 模型停下」两序；`derive_messages` 仍逐字节相等（收件箱消息是 durable 事件，天然进派生）。

> **落地回写（2026-09-08，分支 `feat/runtime-base-p3-inbox` 叠 P2）**：第 1、2、3、5 条已落——`services/episode_inbox.py`
> （正文只在 `inbox_inserted` 落一份，`inbox_claimed` 只带 `message_id`，派生按 id 回找）；`FinanceResearchHarness.admit_inbox_message`
> 默认 True，判定在 `send` 时做、抛异常按拒收；`_append_sub_research_message` 改走 `inbox.send(next_step, source="sub_research")`；
> 清箱挂在 `_EpisodeLedger.add("finish")` 这个唯一出口（取消 → `cancelled`，其余 → `episode_finished`），`keep_inbox` 落为 `Inbox.keep_on_cancel`。
> 认领点：每次模型请求前 `claim(next_step)`（主 loop 与修复轮）；模型停下且未收口时 `claim(next_turn)` + 此刻已到的 `next_step`，再给一轮。
> 外部入口 `ContinuousAgentEpisode.steer` / `GLMAgentRuntime.steer`（回执 `InboxReceipt`，不抛）。第 4 条端点按 §12 第 4 题推荐未做。
> **CLI（第 4 条括注「底座与 CLI 先做」里的 CLI）2026-09-09 落地**（分支 `feat/runtime-base-p3-steer-cli`，PR #687）：`Inbox.send` 是进程内调用、runtime 按次构造，另一个进程没有门，所以 CLI 不做端点客户端而走 durable 目录——递话方原子写 `<episode_dir>/inbox-spool/<ns>-<spool_id>.json`，`Inbox` 在既有认领点（`pending` / `claim` / `discard_all`）先吞槽再走原逻辑，三事实仍只由 loop 落账（INV-R5 不变，`inbox_inserted` 多带 `spool_id` 对回执）。`python3 -m intelligence.cli steer <episode_id> "<文本>" [--target] [--wait N] [--list]`；两个 fail closed：store 根与 Workbench 不同（events.jsonl 不在）拒投、state.json 终局拒投。细节在工单 #30 落地记录二。端点仍等 Alpha。
> 两处与原文的差别：`wakeup` 只记账（同步 loop 没有可唤醒的空闲态，等 P4 `step()`）；收口阶段不认领 `next_turn`（episode 正按预算关门）。
> 验收落点：`conformance/test_inv_r5_inbox.py`（两序竞态、取消丢弃、收口丢弃、接缝有牙、子研究经箱、非适用臂不在场）+ `test_episode_inbox.py`（单元）。

### 6.5 P4：竞态目录 + 写序 oracle 正式化 + 防御模式

1. loop 拆出 `step()` 可单步驱动（P2 的 `restore` 已需要）；`intelligence/tests/conformance/races/` 目录表 v1 至少八条：`cancel vs model_turn 结算`、`cancel vs tool_result 结算`、`cancel vs finish`、`steer vs 模型停下`、`close vs 结算`、`两个 begin_work 同 Handle`、`store.append 失败 vs 内存 ledger`、`restore vs 仍在飞的驱动`。每条两序、断言两种合法历史。
2. 写序 oracle 从 P2 的测试工具升为 `conformance/oracle.py` 公共件。
3. `docs/runtime/defensive-patterns.md`：从 `docs/prediction-ledger.md` 的 R-* 与本仓 handoff「踩过的坑」里提炼「坑 → 规则」（不抄 dsh 那六条；同名坑写本仓实例）；含 G10 抛 / 返回总规则：**`runtime/` 内部用异常，跨 `services` 契约边界只返回结构化结果；hooks / sink / 投影一律不抛。**
4. `test_runtime_catalog_fresh` 进 pre-commit（第 12 道）。

---

## 7. 生产接线与切流

P0 / P1 零 live 判据，随下次切流带上；P1 的错误码拆分合入前一次 live 探针。P2 是真行为改动：单独切一次 8792，五步规程（快照 → bootout → ln → 账本 → bootstrap），回滚锚照写；切后手工 `kill -9` 一次在飞 episode 验 `restore`。P3 随 Workbench 端点决定。每次切流的 rollback 文件与探针 run id 写进各阶段工单。

---

## 8. 非目标（写死）

- ❌ 不迁 TypeScript、不引 Cordis、不 boot pi / dsh、不把两家源文件拷进仓。
- ❌ 不改 90/60/30、不改 `admit_finish` 等 16 方法语义、不改 Evidence Ledger / verifier / 截止日。
- ❌ 不做 lanes / forks（子研究「另一个 run、另一份身份」维持；`_BranchBudgetView` 不铸币不变）。
- ❌ 不做 provider stream 续传、多进程写者、跨机复制。
- ❌ 不做 LLM 压缩（L3 / L5 归学习合同）；不做 Code Mode / 动态插件加载。
- ❌ 不在本稿改 BP / 对外物料；不把本稿写成对外的「我们有 pi 级持久性」——那要 P2 切流后的收据说。

---

## 9. 风险与控制

| 风险 | 控制 |
|---|---|
| 事件 payload 加字段 / 加 kind 影响五个下游读者（orchestrator / stream_events / benchmark / normalize_harness_trace / dump_episode_receipts） | 只加不删；新 kind 先进 `DURABLE_EVENT_KINDS`；`normalize_harness_trace` 的 L1 映射表加两行（`model_input → intent`，`prompt_assembled → configure`）；P2 前 `ignorable` 与版本号先行 |
| 正文进 durable 流泄露到对外面 | 投影默认剔正文只留 hash（P0 第 4 条）；`_redact_object` 已在 orchestrator 对 report 生效；新增夹具断言 stream_events 不含 `system` 正文 |
| 落盘 IO 进主路径 | 每 episode ≤ 200 事件量级（09-03 离线普查 825 episode / 2948 工具事件）；意图 fsync、结算不 fsync；JSONL append 单写者 |
| 8792 切流窗口 | P2 单独切；回滚锚；kill -9 演练 |
| 与 harness 那拨 agent 撞文件 | §5 文件级分工；接触点两处先 spec；PR diff 机械审 |
| 「学形状」滑成「抄实现」 | 每个 PR 描述必答：形状从哪来 / 本仓哪条缝 / 没搬的量纲是什么（学习合同六栏之三） |

---

## 10. 验收总表（终态）

| 不变量 | 测试 | 阶段 |
|---|---|---|
| INV-R1 | `test_episode_messages.py::test_derive_matches_sent_{plan,noplan,repair}` × 两条 loop | P0 |
| INV-R1 投影 | `test_episode_projection.py::test_model_visible_text_redacted_by_default` | P0 |
| 目录保鲜 | `test_runtime_catalog.py::test_catalog_fresh` | P0 |
| INV-R4 | `conformance/test_inv4_cancellation.py`（+3 行） | P1 |
| INV-R2 | `conformance/oracle.py` + `test_episode_store.py::test_intent_before_effect_before_settlement` | P2 |
| INV-R3 | `test_episode_restore.py`（每 phase × 每 crash 前缀） | P2 |
| 版本 | `test_episode_store.py::test_unknown_required_kind_refused` | P2 |
| INV-R5 | `test_episode_inbox.py`（单元）+ `conformance/test_inv_r5_inbox.py`（两序竞态 / 取消 / 收口 / 接缝有牙 / 非适用臂） | P3 ✅ 09-08 |
| INV-R6 | `conformance/races/test_*.py`（≥ 8 条 × 2 序） | P4 |

---

## 11. 教学注（原理与选型，按用户偏好）

- **快照式恢复 vs 事件重放恢复**。pi 选「每步覆写完整状态、恢复只读它」，不是「重放事件流推出位置」。事件溯源（event sourcing）里两者都合法：重放的好处是零冗余，坏处是恢复逻辑要理解每一种事件、日志越长越慢、且「缺一条」会被读成「没发生」；快照的好处是恢复代码只有一个 switch。数据库 WAL 的 checkpoint、Temporal 这类 durable execution 引擎的 workflow state 都是同一思路。本稿选快照（`EpisodeState`）+ 事件流保留（重放给评测与投影用），两者分工不重叠——这在任何「长事务 + 可能崩溃」的系统里都能用。
- **意图 / 结算两段提交为什么不是 2PC**。2PC 是多个参与者对同一个决定投票；这里只有一个写者，两段是为了把「外部效果已发生但我不知道结果」这个窗口显式化。它更像 outbox pattern：先落「我要做 X」，再做，再落「X 的结果」。exactly-once 对外部效果不可能（pi §0.6 明写非目标），能做的是 at-least-once + 效果侧幂等或意图侧 `replay` 声明。面试常考：幂等键、outbox、saga 的补偿。
- **`aborted` ≠ `error` 的价值在重试语义**。超时该重试，用户取消不该；把两者塞进一个码，重试逻辑就要靠 detail 字符串判断。类型化取消原因（dsh 四种）同理：`parent` 取消的子研究和 `user` 取消的父 episode，事后归因完全不同。
- **自己的消息类型 = DDD 的防腐层**。provider 线格式是外部系统的模型，loop 直接操作它就把外部变化（Anthropic content blocks、thinking 字段）放进了核心。`EpisodeMessage` + `to_provider()` 是一层薄映射，换 provider 只改映射。
- **写序 oracle 为什么优于「看日志」**。日志只能看到最终写了什么，看不到「效果是不是在意图之前就开始了」；spy 包住 `append` 并与 fake provider / fake tool 的开始事件交错记录，才能断言因果序。这是 pi Tier B 的核心，也是任何「写日志 + 做副作用」系统的通用测法。
- **替代方案对照**：(a) 只做 P0 + P2、跳过 P1 的消息类型——可行但 P2 的 `restore` 要重建 `list[dict]`，等于把线格式钉进持久层，以后换 provider 要迁数据；(b) 用 SQLite 做 store——pi 的选择，事务与查询强，但本仓事件量小、单写者、DuckDB 已是主库，再加一个嵌入式 DB 的运维面不值；JSONL 与 `deploy-ledger.jsonl` 同族，撕裂末行整行丢弃即可；(c) 直接接 Temporal / 自研 durable execution——超出「运行时」范围，本仓 episode 是 90 秒量级不是天级。

---

## 12. 待拍板

未拍板前按推荐执行。

> **2026-09-09 拍定记录**：两日质检（09-07 13:00 → 09-09 13:00）第 7 条指出「§12 五题至今未拍板，P0–P3 全按推荐执行并合入，需要用户拍一次，否则这条线永远是按推荐」。用户回复原话：「合并，然后你按照最优路径继续推进」。据此五题按各自的推荐项拍定——1 JSONL；2 要一次 live 探针（P1 已做，读数在工单 #28 头部）；3 只登记；4 底座 + CLI 先做、端点等 Alpha（CLI 同日以投递槽落地，见 §6.4 落地回写）；5 母单 + 五子单。**拍定依据是这句委托而非逐题回答**，用户当时拿到的信息是那份质检报告（A–D 四组 12 条）；日后要翻某一题，从这里起，不必再问「当初为什么按推荐」。

1. **P2 存储后端**：推荐 JSONL（`~/.finance-runtime/episodes/`，零依赖，与 deploy-ledger 同族）。备选 SQLite（pi 生产用；本仓要多一套运维面）。
2. **`tool_not_dispatched` 拆码是否需要 live 探针**：推荐要，一次（它改了模型可见 error 码）。备选：只跑脚本化夹具。
3. **重启后的 open episode 自动恢复还是只登记**：推荐先只登记（`list_open()` 进 readiness），由 Workbench 或人工触发 `restore`；自动恢复要等 P4 竞态目录里「restore vs 在飞驱动」有测。
4. **P3 Workbench `steer` 端点本轮做不做**：推荐底座 + CLI 先做，端点等 Alpha 内测反馈。
5. **工单编号与分派**：推荐一个母单（本稿）+ P0–P4 五个子单各占一号；P0 与本稿同分支落地。备选：五个独立单不挂母单。

---

## 13. 与 pi / dsh 的差异声明（避免下一位读者误判）

- 本稿**没有**采纳 pi 的 lanes（多游标共享历史）与 forks——本仓子研究是独立 run，`_BranchBudgetView` 已裁不铸币。
- 本稿**没有**采纳 dsh 的 Cordis 插件树与 `ctx.*` 服务注册——本仓「万物皆插件」的对应物是 Python Protocol + 工厂，08-15 §7.7 已裁。
- 本稿**没有**采纳两家的 LLM 压缩——归学习合同 L3 / L5。
- 本稿采纳的六条不变量在两家源码里的出处：R1 = dsh「Model-visible means logged」（architecture.md §Session log）；R2 = pi §0.3 第 4 条「effect sandwich」；R3 = pi §0.3 第 3 条「durable program counter」+ §4.4；R4 = pi 不变量 19 + dsh `AgentCancelCause`；R5 = dsh `Inbox`（core.md §The agent handle）+ pi `getSteeringMessages`；R6 = pi §9.2 竞态目录 + §9.3 Tier B/C。

# 工单 #29 · 运行底座 P2：Durable 存储 + 意图/结算 + 恢复 + 配置快照 + 版本号

> 母单：#27 `2026-09-07-runtime-base-endstate-design.md` §6.3、§7（切流）。前置：P1（#28，PR #624）合入。
> 分支：`feat/runtime-base-p2-durable-store`（叠在 `feat/runtime-base-p1-messages-cancel` 上；#624 合后 rebase 到 main）。
> 状态：✅ 已合入 `gitea/main`（PR #638 → `5985d878`，2026-09-08 21:10，紧随 #624；分支与树已清；09-09 回写）。§12 第 1 / 3 题**按推荐执行**（仍待拍）：JSONL 后端、重启后只登记。A–D 四刀四 commit（`d1e77051` / `78789f6f` / `f1110c7f` / `e59f03ea`）；E 干净树全量 **8063 passed / 0 failed / 77 skipped**（收据 `20260907T102315Z-e59f03ea.json`，对 P1 基线 red set 相同、+42 全为本单新增）。**未做**：8792 切流 + `kill -9` 演练（母单 §7，需用户在场）——合入后仍未做，生产 8792 停在 0060da5c（09-09 实测），P2 起是真行为改动，切前读工单 #38。原交接归档在 `docs/handoffs/inflight-archive-2026-09-08/feat-runtime-base-p2-durable-store.md`。
> 判据：INV-R2 / INV-R3 成立（conformance 矩阵 + Tier A 逐前缀 oracle）；`RuntimeHandle` 四类验收场景改回 08-15 原文（含**进程重启**）——docstring 写死认领第 2 条已改为已落。
>
> **落地记录（09-07）**：A `services/episode_store.py`（`EpisodeStore` Protocol、`Memory` / `Jsonl`、`EpisodeState`、`EPISODE_LOG_VERSION`、`EpisodeEvent.ignorable` + `require_known_kinds`）；B `ToolSpec.replay` / `EpisodeToolBatchSession.on_dispatch` + `DispatchIntent` / `_EpisodeLedger` 落盘（意图 fsync）+ `record_model_intent` + `record_dispatch_intent` + `put_state` + `configure` 首条 / 两处 `complete` 前 `model_intent{turn_id}` / `GLMAgentRuntime(episode_store=…)` / `conformance/oracle.py` + `test_inv_r2_write_order`；C `services/episode_restore.py` + `ContinuousAgentEpisode.restore` + `test_episode_restore.py`（逐前缀 oracle：五种动作全到过）+ `test_inv_r3_restore`；D `api/app.py` 装配 `JsonlEpisodeStore` + readiness `open_episodes` / adapter 产物 `log_version` + `runtime_handle` / `EpisodeFinalizer.recover(on_prompt)` + `prompt_assembled{source: finalizer}`。既有断言按意图改两处（首条 `configure`；一批多调用请求先于任何结算）。`normalize_harness_trace` L1 加 `model_intent → intent`；三张目录再生成（durable 30 种）。
>
> **与 main 的整合（09-07 傍晚）**：开 PR #638 时 main 已到 92c7826c（#628 / #635 / #636 都碰 `agent_episode.py`），三张 PR 全部冲突。三级前向合并（`main → P0 3d4a254c → P1 0d006a2a → 本枝 962aed84`，不改写历史），三张 PR 对 main 重新 clean。顺手补了历史折叠在 INV-R1 上的洞（`history_compacted.folded[].model_content` + 派生规则 + 投影 `list[].field` 剔正文；`compact_history` 改在 `EpisodeMessage` 上工作）。整合后头 962aed84 干净树全量 **8195 passed / 0 failed / 76 skipped**（收据 `20260907T105919Z-962aed84.json`）——即三张 PR 依次合入后 main 的模样。
>
> **与 §2 步骤的差异**：`configure` 快照不含 `instructions_hash`（它必须先于 `task`，而 system 提示词在绑完 sub_research 之后才拼得出来；同一事实由紧随的 `prompt_assembled.system_sha256` 承载）。`restore` 一次只给一个下一动作（部分意图落地时先重跑落了的那条），驾驭方迭代收敛。

## 0. 开工前核对的两处事实（与母单 §4 G1 有出入，按实测改）

1. **`tool_request` 今天不是意图。** 母单 G1 写「`tool_request` 事件在派发前 add（内存）」，实测 `agent_episode._EpisodeToolAccumulator.consume()` 在 `tool_session.execute()` **返回之后**才逐条 `add("tool_request")`，与 `tool_result` 成对写——它是事后记录，不是效果前的意图。所以 P2 不只是「加 `replay` 字段」，要把派发过的调用的 `tool_request` **挪到 `_dispatch` 之前**（批次执行器里授权额与 clock 都已算出、就要进线程池那一刻）。未派发的调用（拒绝 / 零授权 `tool_not_dispatched` / 取消）没有外部效果，保持事后写。每个调用仍恰好一条 `tool_request`；变的只是派发过的那些的位置：一批多个调用时从「请求₁结算₁请求₂结算₂」变成「请求₁请求₂…结算₁结算₂…」，单调用批次逐字节不变。`derive_messages` 不读 `tool_request`，INV-R1 不受影响。
2. **「预留 id」在本仓是 `call_id` / `turn_id`，不是预留 sequence。** pi 的 store 按 id 寻址所以能给结算预留 entry id；本仓 `_EpisodeLedger.add` 的 sequence 是 `len(events)+1` 追加即得，`AgentOutcome` 钉死「sequence 从 1 连续」，8 worker 并发结算也不允许空洞。学形状不搬量纲：意图里预留的是**结算要复用的关联 id**（工具 = `call_id`，模型 = 新增 `turn_id`），崩溃后合成的结算带同一 id 与 `intent_sequence`，sequence 仍追加取号。

## 1. 三件事、各自的失败形状

| # | 做什么 | 今天的失败形状 [实测] | 学谁 |
|---|---|---|---|
| A | `services/episode_store.py`：`EpisodeStore` Protocol + `Memory` / `Jsonl` 两实现 + `EpisodeState` 程序计数器 + `EPISODE_LOG_VERSION` + `EpisodeEvent.ignorable` | `_EpisodeLedger.events` 内存列表；`continuous-episode.json` 只在 orchestrator 结束时写一次（且 `outcome.events` 三处重复带全文）；`AgentOutcome.events` 无版本字段；新 kind 老读者行为只在投影层约定 | pi「entries 只写一次 / registers 覆写当前值」；dsh 追加日志 |
| B | 效果三明治：`model_intent{turn_id}` 先于 `model.complete`、`tool_request{replay}` 先于 `_dispatch`；意图 fsync、结算不 fsync；`EpisodeState` 每次 phase 转移覆写 | 见 §0 第 1 条；`model_turn` 前无任何 durable 痕迹；崩溃后无法区分「模型没被叫」与「叫了没回」 | pi §0.3 第 4 条 effect sandwich |
| C | `ContinuousAgentEpisode.restore(episode_id, store)`：读 `EpisodeState` + 按预留 id 点查结算 → switch | 无恢复；`resume()` 吃同进程 `_EpisodeContinuationState` | pi §0.3 第 3 条 durable program counter + §4.5 三行 |

## 2. 步骤（每步可单独 commit）

1. **A1** `services/episode_store.py`：`EPISODE_LOG_VERSION = 1`；`EpisodePhase`；`EpisodeState`（frozen：`episode_id / phase / turn_index / reserved_ids / consumed_seconds / deadline_at / retry / contract_snapshot / cancel / log_version / last_sequence / updated_at`，`to_dict / from_dict`）；`EpisodeStore` Protocol（`append(episode_id, events, *, sync)` / `put_state` / `load` / `list_open`）；`MemoryEpisodeStore`；`JsonlEpisodeStore(root)`：`<root>/<episode_id>/events.jsonl` 追加 + `state.json` 用 `os.replace` 原子替换；`load` 对**末行**解不出 JSON 整行丢弃（撕裂），非末行坏了抛 `EpisodeLogCorrupt`（不猜）；`list_open()` = 有 `state.json` 且 `phase != done`。`resolve_episode_store_root()`：`FORESIGHT_EPISODE_STORE` → `$FINANCE_WS/state/episodes` → `~/.finance-runtime/episodes`（与 `deploy_ledger.resolve_ledger_path` 同序）。
2. **A2** `EpisodeEvent.ignorable: bool = False`（defaulted 字段，构造零改动；`to_dict()` 仅为 True 时带键）；`episode_store.require_known_kinds(events)`：kind 不在 `DURABLE_EVENT_KINDS` 且非 ignorable → `UnknownRequiredKind`。`restore` / `load` 用它。
3. **B1** `ToolSpec.replay: Literal["safe", "never"] = "safe"`——**本单唯一 harness 接触点**，只加字段；12 个只读工具默认 safe。
4. **B2** `episode_tool_batch.EpisodeToolBatchSession`：`on_dispatch: Callable[[DispatchIntent], None] | None` 属性（Episode 建 session 后设一次，所有 `execute` 路径——主循环 / 空池回退 / flush / 修复轮——自动生效）；`execute(..., request_extras=None)` 把空池回退的标记带进意图。`_dispatch` 之前对 `selected`（模型顺序）回调一次：调用列表、clock、每调用 `replay`。
5. **B3** `_EpisodeLedger(task_frame, *, episode_id, store, configure, event_sink)`：`add()` 后 `store.append([event], sync=kind in INTENT_KINDS)`；`configure` 快照作为**首条**事件（`AgentOutcome` 只允许它先于 `task`）；`record_model_intent(turn_id, timeout_asked, phase)`、`record_tool_intents(intent)`（写 `tool_request` 并登记 `intended_call_ids`）、`put_state(...)`。`_EpisodeToolAccumulator.consume` 对已有意图的 call_id 不再补 `tool_request`。
6. **B4** 两处 `self._model.complete` 前各发一条 `model_intent{turn_id, timeout_asked, phase}`，`model_turn` / `model_error` payload 带同一 `turn_id`；phase 转移点：`planning`（prompt 落账后）→ `model_pending`（意图后）→ `tools_pending`（意图后、派发前）→ `planning` / `finalizing`（批次结算后）→ `done`（任何终局 finish 后）；`resume()` 走 `repair`；观测到取消先 `put_state(cancel=snapshot)` 再写 finish。
7. **B5** 写序 oracle：`tests/conformance/oracle.py`（P4 升公共件，P2 先落这里）`WriteOrderOracle` 包住 `store.append` 与假 model / 假 tool 的「开始」时刻交错记录，断言每笔「意图 seq < 效果开始 < 结算 seq」。
8. **C1** `restore(episode_id, store) -> RestoreResult{state, settled: tuple[EpisodeEvent], plan: ResumePlan | None, outcome: AgentOutcome | None}`：读 state（缺 → `RestoreUnavailable`，不从缺席推断）；版本不符 / 未知非 ignorable kind → 拒绝；switch(phase)：`done` → 已终局；`model_pending` → 点查 `turn_id` 的结算：有 → 按结算给下一动作（tool_calls → `dispatch_tools`；finish → `admit_finish`）；无 → `retry` 允许（截止未到 && 瞬态重试余量 > 0）→ `ResumePlan(retry_model)`，否则合成 `model_error{reason=interrupted, turn_id, intent_sequence}` + `finish{stop_reason=interrupted}`；`tools_pending` → 逐 `call_id` 点查：无结算的 → 意图 `replay=safe` **且**当前注册表该工具仍 `safe` 且截止未到 → `ResumePlan(replay_tools=[…])`，否则合成 `tool_error{error=interrupted}`，若截止已到再合成 `finish{interrupted}`；`state.cancel` 非空且无 finish → 合成 `finish{stop_reason=cancelled, cancel_cause}`；`planning` / `finalizing` 无预留 id → `ResumePlan(model_turn)`。合成事件**写回 store** 并 `put_state(done)`（终局时）。
9. **C2** Tier A `test_episode_restore.py`：脚本化模型 + 假工具跑一遍不间断，`RecordingStore` 记下每次 `put_state` 时的事件前缀；对**每个**前缀（= 每个 phase × 意图前 / 意图后结算前 / 结算后三种切点）截断 → 新对象 `restore` → 断言 `plan.action` == 不间断跑里紧接着发生的那件事；`Memory` 与 `Jsonl` 同场景字节同结果；撕裂末行；`unknown_required_kind` 拒绝；取消 durable → 合成 cancelled finish。
10. **D1** `GLMAgentRuntime(episode_store=...)` 透传；`api/app.py` 生产装配传 `JsonlEpisodeStore(resolve_episode_store_root())`；`/api/readiness` 加 `open_episodes`（`list_open()`，只登记）。`RuntimeHandle.dump()` 进 `continuous-episode.json`（键 `runtime_handle`，含 `scope.derive_mismatches`）——探针时发现它至今只在内存。
11. **D2** `EpisodeFinalizer.recover` 前发 `prompt_assembled{source: finalizer}`（P0 已知边界 a）——`record_prompt_assembled` 加 `source` 参数，默认 `episode`；`derive_messages` 对 `source=finalizer` 的 `prompt_assembled` **不派生**（它不进 episode messages）。
12. **E** `gen_runtime_catalog.py --check`；ruff / layer_audit；干净树全量收据；交接；PR 叠 #624。

## 3. 验收

- Tier A 每 phase × 每 crash 前缀：`restore` 的下一动作与不间断跑一致；写序 oracle 每笔三明治成立；`Memory` == `Jsonl`；撕裂末行整行丢弃；未知非 ignorable kind 拒绝。
- 全量 pytest 与 P1 基线同结果（除本单新增 / 因 `configure` 首条与意图前移而改的既有断言，逐条列在交接）。
- 8792 切流 + 手工 `kill -9`：**本单不做**——生产切流按母单 §7 五步规程另开一刀，需用户在场；`list_open()` 与 `restore` 的进程级验证以 Tier A 的 `Jsonl` 场景（真文件、真 `os.replace`）为代。

## 4. 与领域 harness 的接触点（本单确认）

- `ToolSpec.replay` 只加字段；`_TOOL_CONTRACTS` 文本不动；`ResearchHarness` 16 方法不动。
- `configure` 快照含 `instructions_hash`（`assemble_prompt` 的 system sha256）与 `tool_contracts_hash`（授权工具 `(name, replay)` 排序后 sha256）——都是哈希，不抄文本。

## 5. 不做

多进程写者、跨机复制、provider stream 续传、自动后台恢复（§12 第 3 题：只登记）、SQLite 实现、`step()` 单步驱动（P4；`restore` 只给下一动作，不重新驱动 loop）、8792 切流。

## 6. 已知边界（写在前面，免得读者当 bug）

- 取消在「用户点了停」到「loop 在检查点观测到」之间只在内存；这段窗口内崩溃，restore 看不到取消，按普通崩溃处理（截止早已过 → `finish{interrupted}`），用户意图丢失但结果安全。P3 收件箱 / P4 竞态目录再收。
- `continuous-episode.json` 里 `outcome.events` / `structural_verifier.outcome.events` / `semantic_verifier.verified.outcome.events` 三处仍带 prompt 全文（09-07 探针实测）：该文件 `visibility=internal` 不对外，本单不改其形状（母单 §6.3 第 7 条「形状不变」）；P2 的 store 才是全文的正当归宿，去重留 P3 前顺手做。

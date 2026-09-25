# 工单 #28 · 运行底座 P1：Episode 消息类型 + 取消类型化 + 未派发 / 超时分码

> 母单：#27 `2026-09-07-runtime-base-endstate-design.md` §6.2。前置：P0（PR #620）。
> 分支：`feat/runtime-base-p1-messages-cancel`（叠在 `spec/runtime-base-endstate` 上；#620 合入后 rebase 到 main）。
> 状态：🟡 代码已落、门禁绿、PR 待确认（2026-09-07，用户「开单执行」；§12 未拍板按推荐执行）。A/B/C/D/E 步骤已在分支上完成；F 的 live 探针见分支交接。
>
> **合入前置读数（09-07 16:00，为 #620 → #624 合并确认备）**：`gitea/main` 自分叉点 504cbbc9 前进到 0b834d77（#619 分支级 trace / #622 能力 frontier / #623 L3 / 三份切流回写，19 文件），与本枝只重叠 `agent_episode.py` 一处且是分支 telemetry payload（`branch_telemetry(branch)`），不碰 `messages`；`merge-tree` 两张 PR 头对 main 均 clean。在临时树 `fwp-wt-merge-sim-620-624` 把本枝头 3d964c91 合进 main 0b834d77（本地 819f5f2b），干净树全量：**ruff 0，8042 passed / 0 failed / 76 skipped**，对 P1 基线收据（c6807038，8021P）red set 相同、passed 只增（+21 = main 新增测试）。收据 `~/.finance-runtime/test-receipts/20260907T08…-819f5f2b.json`。#620 若以 merge commit 合入，#624 只需把 base 从 `spec/runtime-base-endstate` 改成 `main`（P1 三 commit 的父链已含 65572d9d），不必 rebase。
>
> **上条读数已过期（09-07 傍晚补）**：main 随后走到 92c7826c（#628 派发节奏 / #635 观察瘦身 / #636 历史折叠都碰 `agent_episode.py`），#620 / #624 / #638 一度全部冲突。处置是三级前向合并（`main → spec/runtime-base-endstate` 3d4a254c → 本枝 0d006a2a → P2 962aed84），不改写历史；三张 PR 对 main 重新 clean。历史折叠就地改模型可见 tool 正文，是 INV-R1 的洞：P0 级补 `history_compacted.folded[].model_content` + 派生规则 + 投影剔正文；本枝把 `compact_history` 改在 `EpisodeMessage` 上工作，两份量具测试改读属性。整合后栈顶 962aed84 干净树全量 **8195 passed / 0 failed / 76 skipped**（收据 `20260907T105919Z-962aed84.json`），即三张 PR 依次合入后 main 的模样。合并顺序不变：#620 → #624（改 base 为 main）→ #638（改 base 为 main）。
>
> **台架 shim 不对称（F 那条红）的处置**：不采「shim 也绑 `sub_research`」——`agent_episode._bind_sub_research_tool` docstring 写死无协调器的 loop 是「工具不存在，而不是存在但报错」，绑一份不能跑的工具摆给模型，污染比 693 token 更大；也不采「Episode 臂去掉协调器」——破坏台架「除 loop 类外全是生产」前提。改门本身：`finance-base-ab` 分枝 `fix/reference-gate-declared-asymmetry`（853d42e，已推 gitea，**未合其 main**）让 `compare` 读 P0 落账的 `prompt_assembled` 哈希——system sha256 相等为硬门；契约授 `sub_research` 且 system 同哈希时 ±3 与 user 哈希差进 `soft_notes` 写明归因，否则照旧硬红；未授时 user sha256 相等也是硬门。用 09-07 真产物重投影验过五格（真探针 ok=True 两条 soft 归因 / 去授权两硬红 / system 异三硬红 / 无哈希不可归因硬红 / 同 prompt 干净 ok）。
>
> **F live 探针读数（09-07 13:39–13:52，`finance-base-ab/out/reference-loop-0907-p1/`，快照 `~/.finance-runtime/finance-workspace-07336b461587`，模型 `gpt-5.6-sol`，RAG 预热 8.6 s）**：两臂均 `model_finish` / `completed`，同一答案「贵州茅台 2024 年营业总收入 1,741.44 亿元（报告期 2024-12-31，披露 2025-04-03）」，首轮 `task_frame_hash` 同 `e6ee9044…`、首轮都点 `financial_data`、`served_models` == 请求；Episode 10 工具 / 229.6 s，参考 loop 9 工具 / 149.2 s；**零工具错误**，故 `tool_not_dispatched` 在本次没被触发（实授窗 529 s，远未饿死）——它只在零授权格出现，本探针验的是 P1 消息类型重构后真请求的线格式与首轮行为不变。P0 事件在真产物里形状正确：`prompt_assembled` 投影后只剩 `system_sha256 / user_sha256 / *_chars`，`tool_budget_state` 6 条，`finish` 不带 `cancel_*`。**对照硬门一条红**：首轮 `input_tokens` 17308 vs 16615（差 693）——用 `prompt_assembled` 哈希直接判：system 两臂同哈希，user 差 410 字符；加 `sub_research` 工具定义约 620 token，合计即 693。根因是台架 shim `del sub_research_coordinator`，Episode 有协调器则绑 `sub_research`（14 个授权能力里含它），参考 loop 没有——**台架既有不对称，非 P1**；09-03 契约只授 7–9 项无 `sub_research`，所以当时 ±3 能过。修法在 `finance-base-ab/shape_lib/reference_loop_arm.py`（shim 也绑一份或两臂都去掉），本单不碰仓外。另记：`RuntimeHandle.dump()`（含 `derive_mismatches`）仍未进产物，live 上 INV-R1 只有进程内断言、无落盘收据——P2 一并落。
>
> **落地记录（09-07）**：A `EpisodeMessage` + `to_provider`（`AgentModelClient` 协议不变，替身零改动）；B `services/cancel_signal.py`：`CancelSignal`（可调用、first cause wins、`coerce` / `child`），`GLMAgentRuntime` 一次类型化并给子研究 `child(cause="parent")`，`RuntimeHandle.request_cancel(reason, *, cause)` + `dump()["cancel_cause"]`，两条 loop 的取消终局 `finish` 带 `cancel_cause / cancel_detail`；C `episode_tool_batch.TOOL_NOT_DISPATCHED_ERROR` + `time_gate_error_for_model`，两条 loop 改读 `result.error`，离线读者两代词表并存；D conformance 新增 `INV-R4`（continuous SUPPORTED，其余臂 UNSUPPORTED_DECLARED 验「确实不在场」）+ 批次层三码互斥 + `test_cancel_signal.py` 10 条；E 目录 `--check` 一致。四条零授权断言随词表更新（含 R13 史料夹具按新词表重放）。
> 判据：INV-R4 成立；INV-R1 在新消息类型上仍成立；除拆码那一格外模型可见内容零字节变化。

## 1. 三件事、各自的失败形状

| # | 做什么 | 今天的失败形状 [实测] | 学谁 |
|---|---|---|---|
| A | `EpisodeMessage` 自己的消息类型；`to_provider()` 只在 `AgentModelClient.complete` 边界转线格式 | `messages: list[dict]` OpenAI 形状贯穿 loop（`_EpisodeContinuationState.messages`、`ReferenceLoopState.messages`）；换 provider 消息格式要碰 loop；`_append_tool_budget_state` 直接 `messages[-1]["content"] = …` 原地改字典 | pi「loop 全程 `AgentMessage`，`convertToLlm` 只在 LLM 边界」 |
| B | `CancelCause` 枚举 + `CancelSignal`（first cause wins，可调用以兼容旧谓词） | `is_cancelled: Callable[[], bool]` 从 `GLMAgentRuntime` 一路裸传到 Episode / 工具批次 / 子研究 / `RuntimeHandle`；`RuntimeHandle.cancel_reason` 自由字符串；`finish{stop_reason=cancelled}` 不带原因 | dsh `AgentCancelCause = user\|parent\|hook\|disposed`；pi「`aborted` ⇔ signal 被拉」 |
| C | `tool_not_dispatched`（授权额 ≤0 未进线程池）与 `tool_timeout`（真跑超时）分码 | `episode_tool_batch.py:548` 与 `:724/:741` 落不同事实，`agent_episode.py:421` / `harness_reference_loop.py:705` 一律按 `status=="timeout"` 写 `tool_timeout`，只靠 `detail=stage_timeout_granted=0` 区分；09-01 收据里模型因此被骗去换工具 | dsh `defensive-patterns.md`「Report orthogonal outcomes independently」 |

## 2. 步骤（每步可单独 commit，顺序即依赖）

1. **A1** `services/episode_messages.py`：`EpisodeMessage`（frozen：`role / content / tool_calls / tool_call_id / source`）、构造器改返回它、`to_provider(messages, dialect="openai") -> list[dict]`、`derive_messages -> list[EpisodeMessage]`、`check_derivation` 比较两边 `to_provider()`。
2. **A2** 两条 loop 的 `messages` 换类型：所有 `messages.append({...})` 改构造器；`_append_tool_budget_state` 改 `messages[-1] = replace(...)`；`self._model.complete(messages=to_provider(messages), ...)`。`AgentModelClient.complete` 签名**不变**（仍收 `list[dict]`），所有模型客户端与测试替身零改动。
3. **B1** `services/cancel_signal.py`：`CancelCause`、`CancelSignal(upstream=..., upstream_cause=...)`，`request(cause, detail) -> bool`、`.requested / .cause / .detail`、`__call__` 返回 `requested`。
4. **B2** 接线：`GLMAgentRuntime.start` 把上游谓词包成 `CancelSignal(upstream, "user")`；Episode / 参考 loop 构造器收 `Callable | CancelSignal`（裸谓词自动包）；子研究分支收 `CancelSignal(upstream=parent, upstream_cause="parent")`；`RuntimeHandle.request_cancel(reason, *, cause="user")`，`dump()` 出 `cancel_cause`；`_cancelled_outcome` 的 `finish` payload 加 `cancel_cause / cancel_detail`。
5. **C1** `episode_tool_batch.py:548` → `error="tool_not_dispatched"`（status 仍 `timeout`，detail 仍 `stage_timeout_granted=0`）；`agent_episode.py:421` 与 `harness_reference_loop.py:705` 改读 `result.error`（回落 `tool_timeout`）；docstring 三处同步。
6. **C2** 读者：`scripts/offline_tool_duration_floor.py` 零授权判据加 `tool_not_dispatched`（老产物仍按 `tool_timeout + granted≤ε` 判）；`scripts/offline_budget_quality.py` 加独立计数 `tool_not_dispatched`，不计入 `tool_attempts`（它们没被尝试）。
7. **D** conformance `test_inv4_cancellation.py` +3：取消终局带 `cancel_cause`；未派发与真超时两码；`stop_reason=cancelled` ⇔ `cancel_cause` 非空。`test_episode_messages.py` 加 `to_provider` 往返与 `EpisodeMessage` 等价。
8. **E** `python3 scripts/gen_runtime_catalog.py` 再生成（`tool_error` 描述不变；若 harness 说明书提到 `tool_timeout` 语义，**不改**——那是 harness 文本，记入 §4 接触点）。
9. **F** 全量门禁 → 收据 → PR（叠 #620）。live 探针一次（茅台参考题两臂，`finance-base-ab` 配方 + `SHAPE_SNAPSHOT_OVERRIDE` 指本分支干净快照）：验 `tool_not_dispatched` 在真模型面前不改变首轮行为；**这是 §12 第 2 题推荐答案，用户可否**。

## 3. 验收

- 全量 pytest 与 P0 基线同结果（除本单新增）；ruff / layer_audit 0。
- `to_provider(derive_messages(events)) == to_provider(messages)` 在两条 loop 全部脚本化路径成立（conftest 严格模式）。
- 模型可见内容：除 `error` 码 `tool_timeout → tool_not_dispatched`（仅零授权格），其余逐字节不变——`test_harness_reference_loop` 的并跑对照即证据。
- `finish` 事件在取消时带 `cancel_cause ∈ CancelCause`；非取消终局不带该键。
- `EpisodeToolBatchSession.execute` 零授权 → `error=tool_not_dispatched`，真超时 → `tool_timeout`，取消 → `cancelled`，三者互斥且各有夹具。

## 4. 与领域 harness 的接触点（本单确认）

- `ResearchHarness.project_tool_error(tool, error, detail)` 只是把 error 码原样投影，**不改签名不改语义**；新码经它进模型消息。
- 若 `episode_protocol` / `_TOOL_CONTRACTS` 有解释 `tool_timeout` 的文本，本单**不改**（harness 文本归另一拨），只在收据里记「模型看到新码但说明书未提」，由 harness 那拨决定是否补一句。

## 5. 不做

不落盘（P2）；不做收件箱（P3）；不改 `ToolCallStatus` 枚举（`timeout` 状态族不变）；不改 90/60/30；不改 `AgentModelClient` 协议。

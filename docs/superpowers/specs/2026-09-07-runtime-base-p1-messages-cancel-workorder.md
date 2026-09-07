# 工单 #28 · 运行底座 P1：Episode 消息类型 + 取消类型化 + 未派发 / 超时分码

> 母单：#27 `2026-09-07-runtime-base-endstate-design.md` §6.2。前置：P0（PR #620）。
> 分支：`feat/runtime-base-p1-messages-cancel`（叠在 `spec/runtime-base-endstate` 上；#620 合入后 rebase 到 main）。
> 状态：🟡 执行中（2026-09-07，用户「开单执行」；§12 未拍板按推荐执行）。
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

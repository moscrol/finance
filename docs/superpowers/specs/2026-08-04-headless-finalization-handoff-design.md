# Codex Headless Active Finalization Handoff Design

## Goal

在不修改 `total_seconds`、`finalization_floor_ratio`、`max_tool_calls`、provider、模型或工具 schema 的前提下，让 Codex headless 在工具结果进入 deadline pressure、工具额度耗尽或研究调用被关闭时，立即收到一次明确的“停止研究、用已有证据完成终止回答”指令。

## T1 evidence gate

事实源：`intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t1.json`（SHA-256 `a51fe212…23bd`）。

- `source_revision=84c1eb73`、`source_dirty=false`；profile 仍为 `180s / 6 calls / 30s synthesis reserve / floor=0.0`。
- 60 个 normalized event，`unmapped_count=0`，6 个带 timestamp。
- 瑞华泰最后一个成功工具结果是 `evidence_search`，返回时 research remaining=23.856s。
- 初始模型又运行约 7.7s 后给出 invalid finish；既有 no-tools recovery 在 remaining=16.165s 才开始。
- recovery 16.190s 后撞 deadline，事件级终态仍为 `headless_timeout`。自然收尾时间只知道 `>16.165s`，不能写成 16.190s 或 24s。

因此 rejection-only 仍不足：本次主判题没有 rejection；最早能把指令送进同一模型上下文的稳定边界，是最后一个成功 tool result。

## Architecture

### 1. One frozen instruction

gateway 复用与 SDK 等价的固定语义：

`研究取证阶段已结束，请使用已有信息完成终止回答。`

它只描述下一动作，不注入答案内容、业务数字或 prompt 自由文本。

### 2. Deadline-pressure trigger

gateway 初始化时从真实 research window 冻结一个内部交接窗口：

```python
handoff_seconds = min(30.0, max(5.0, initial_research_seconds * 0.20))
```

对本轮 c profile，`initial_research_seconds≈150`，生效值为 30s；短窗口按 20% 缩放且至少 5s。30s 是 R-09 的预注册 probe，不代表“收尾自然需要 30s”。

这不是修改 `floor_ratio`：floor 仍决定“新研究调用是否在入口被拒绝”；handoff window 决定“一个已经完成的工具结果返回后，控制面是否主动切到 finalization”。两者是不同 enforcement point。

### 3. Three activation paths, one transition

所有路径调用幂等的 `begin_finalization(reason)`：

1. 工具结果返回且 `remaining_research_seconds <= handoff_seconds` → `deadline_pressure`；
2. 工具结果耗尽最后一次调用 → `tool_budget_exhausted`；
3. 新工具请求被 `research_stage_closed/tool_budget_exhausted` 拒绝 → 原 rejection reason。

tool result / rejection payload 都携带 `instruction`，事件顺序保持 `tool_result|tool_error → finalization`。一旦 transition 已开始，后续工具请求统一返回 `research_stage_closed` 与同一 instruction，不再继续研究。

### 4. Terminal semantics

如果模型在同一 Codex run 内输出合法 finish，事件级 `stop_reason` 保持 `model_finish`。现有 invalid/no-finish recovery 仍是兜底；本轮不把它改成新的两进程主路径。

## Alternatives

### A. 只给 rejection 补 instruction

改动最小，但 T1 瑞华泰没有 rejection，主判题不会激活。拒绝。

### B. 在 120s 强杀研究进程，再开 no-tools finalizer

能保证约 30s，但会丢失模型上下文、需要处理 in-flight mailbox tool 的取消与临时目录竞态，且把正常 finalization 变成两次 provider 调用。作为本方案被 T3 refute 后的下一层，不先上。

### C. 每个工具调用加独立 watchdog

可在 30s 前中断长工具，但线程取消、只读工具的迟到结果与 root-budget charge 语义更复杂。只有 T3 证明“结果回来已太晚”时再考虑。

## Test seams

1. `HeadlessToolGateway.call/snapshot`：deadline-pressure tool result 带 instruction、单个 finalization，后续调用关闭；
2. 同一 seam 的 max-call=1：最后一个成功 result 立即交接，reason 为 `tool_budget_exhausted`；
3. `CodexHeadlessRuntime.run` fake process boundary：fake 只有读到 gateway instruction 才输出合法 finish，最终必须 `model_finish`；
4. live `c_long_capped` 五题：预算生效值不变，按事件级 stop_reason 验收。

## Acceptance and stop rule

主判据保持 handoff 原文：瑞华泰从 `headless_timeout` 变为 `model_finish`，且 latency <150s。

- 若通过：R-09 confirmed；显式交接是 PRIMARY。
- 若仍 timeout，且 finalization 的截断耗时达到/超过交接时 remaining：R-09 refuted，转入“收尾本身太慢”。
- 若仍 timeout，但 finish 早于可用 remaining：R-09 refuted，回查 instruction 是否真实进入 tool payload / 模型上下文。

无论结果如何，不重跑其余三臂，不调三个预算字段，不追加第二次 live 调试 run。

## T3 outcome (2026-08-04)

Refuted。瑞华泰事件级终态为 `headless_protocol_rejected` / 135.555s，且没有
finalization：最后一个 `evidence_search` 只有 request，没有 result/error；5 个请求
仅 4 个 mailbox exchange。说明本设计依赖的 result/rejection activation point 在
in-flight tool 路径不可达。下一层是 `R-20260804-10` 的 deadline-aligned per-tool
handoff；本设计不追加第二次 live run。

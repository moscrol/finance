# Codex Headless Finalization Observability Design

## Goal

在不改变 `total_seconds`、`finalization_floor_ratio`、`max_tool_calls`、模型或工具行为的前提下，给 Codex headless 的真实收口交接点增加可落盘时间戳，使 `finalization → finish` 首次可直接测量，并为后续主动交接修复提供可信 activation 证据。

## Frozen scope

本规格只实现 L7 的 T0/T1，不实现 T2。T2 必须等 T1 的同 profile 五题产物确认真实 activation path 后再落代码。

- 保持 `c_long_capped` 的 `180s / 6 calls / 30s synthesis reserve / floor=0.0` 不变。
- 不修改 prompt、工具 schema、provider、重试、终止协议或验收题。
- 不把普通 `model_finish` 事后伪装成显式 `finalization`。
- `finalization` 只在 harness 确实主动开始一次 no-tools repair，或 gateway 确实拒绝后切换到收口状态时发出；同一 episode 最多一次。

## Evidence correction that shapes the design

冻结的 `c_long_capped/ruihuatai-valuation` 并没有经过 `research_stage_closed`：最后一段是 `tool_request(evidence_search)`，没有对应 `tool_result`，随后 `headless_timeout`。因此只给 rejection 增加提示不会在主判题激活。T1 必须先把现有真实交接点和事件时间装上，T2 再按新产物区分：

1. rejection 后缺指导；
2. in-flight tool 阻塞，根本到不了 rejection；
3. 已进入 no-tools repair，但收尾本身超时。

## Components and seams

### 1. Gateway-owned transition event

`HeadlessToolGateway.begin_finalization(reason)` 是唯一显式交接事件入口。它在 gateway 锁内：

- 只接受冻结原因 `research_stage_closed`、`tool_budget_exhausted`、`deadline_pressure`、`headless_invalid_finish`、`headless_no_finish`；
- 首次调用写入 `EpisodeEvent(kind="finalization")`；
- payload 写 `reason`、交接时 `remaining_seconds` 与 UTC `timestamp`；
- 后续调用返回既有状态，不重复发事件。

拒绝路径只调用该入口做观测，不在 T1 添加模型指令。

### 2. Existing no-tools repair transition

`CodexHeadlessRuntime` 在当前已经存在的 finish-only recovery 启动前调用同一个 gateway 入口。这里本来就发生了真实的主动交接，因此事件不是为了补齐指标。

### 3. Terminal timestamp

`finish` 事件 payload 增加 UTC `timestamp`。不改 `EpisodeEvent` 公共构造签名，避免让整个运行时模型为单一测量需求发生横向迁移。

### 4. Normalized trace timestamp

`normalize_harness_trace._event_timestamp` 先读事件顶层，再读安全的 `payload` 时间字段。值仍经过 `_safe_timestamp`；自由文本、路径和凭据不会进入产物。

## Alternatives considered

### A. 给 `EpisodeEvent` 增加顶层字段

类型最整齐，但会触及所有 runtime、fixtures 和序列化消费者，变更面远超 T1。当前不选。

### B. 给所有事件自动打时间戳

可获得完整 timeline，但 artifact diff 大、测试面广，而且本轮只需要 finalization 与 finish 两点。当前不选。

### C. 直接实现 rejection instruction

改动最小，但冻结主判题没有发生 rejection，无法证明能修瑞华泰。必须等 T1 后作为 T2 候选，不在本规格偷跑。

## Test seams

用户已在 handoff 冻结以下公开缝，TDD 只在这些缝上断言：

1. `HeadlessToolGateway.call/snapshot`：真实关闸只产生一次 timestamped finalization；
2. `CodexHeadlessRuntime.run`：真实 finish-only recovery 的事件顺序包含 finalization，finish 带更晚时间；
3. `normalize_records(kind="runtime-benchmark")`：payload timestamp 活过落盘与归一化；
4. live `c_long_capped` 五题：至少一个真实 finalization、至少一个可计算时差、`unmapped_count=0`。

## T1 acceptance

- focused tests 先红后绿；
- 生产 diff 不含预算、prompt 或 profile 变化；
- 提交干净 revision 后只重跑 `c_long_capped`；
- artifact 中 `finalization` 数量至少 1；
- 至少一个 case 可计算 `finish.timestamp - finalization.timestamp`；
- normalized artifact 的 `unmapped_count=0`。

若 live run 的瑞华泰仍没有 finalization，结论只能是“当前显式交接没有在该 path 激活”；不得把旁路 case 的 finalization 时长外推成瑞华泰需要的时间。

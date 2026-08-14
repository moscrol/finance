# Headless Tool Pairing Observability Design

## Goal

把 L7 T3 靠人工数出的“5 个 tool request、4 个 response”固化为 normalized artifact 的确定性不变量，并补齐 tool request 的时间与两层入口余量，使下一轮 R-10 能先离线验收、后做高方差 live 确认。

## Scope

本轮只做两项行为中立的可观测性改动：

1. `normalize_harness_trace` 的单输入与 comparison side payload 新增 `unpaired_tool_requests: int`；
2. `HeadlessToolGateway` 的 `tool_request` 事件新增 UTC timestamp、root 入口余量、扣除 synthesis reserve 后的 research 入口余量。

同时修正文档中已经核实的陈旧/错误标签：

- `trace-profile.md` §8 删除“codex configure/plan 未补、当前 1/3”的旧段，保留真实 3/3；
- 把同 profile 单次 live 会翻面、延迟可摆动约 70 秒写入字段陷阱；
- 两个 `acceptance_board` 红改记为确定性的 CLI 契约/测试漂移，不再叫宿主环境噪声；
- R-10 明确以离线 slow-tool/pairing contract 为主门，单次 live 只作确认。

## Artifact contract

### Pairing rule

`unpaired_tool_requests` 只使用 normalized event 已保留的安全身份字段计算，不读取 prompt、query、tool 输出或自由文本。

按全局 event 顺序、按 `case_id` 分桶：

- `source_event_type == "tool_request"`：该 case pending 加一；
- `source_event_type in {"tool_result", "tool_error"}`：若该 case 有 pending，消费最早的一个；若没有 pending，不把计数降到负数；
- 末尾所有 case 的 pending 之和就是 `unpaired_tool_requests`。

这比 `tool`/`observe` L1 步数相减更可靠，因为 `observe` 还包含 `runtime_result`、`invalid_action` 等非工具响应。当前 normalized schema 不保留 tool name/request id，所以本轮不宣称能证明同名工具的强关联；它锁住的是“每个可见 request 至少有一个后续 result/error”这一控制面不变量。

### Backward compatibility

新生成的单输入 artifact 必须写该字段；comparison 的 `left/right` side payload 也必须携带。

旧 `normalized-harness-trace-2` artifact 若没有该字段，loader 从 events 重算后补出，保持可再入；若 artifact 已声明该字段但与 events 重算值不一致，按其他 derived count 的规则显式抛 `NormalizedArtifactError`，不静默修正。

schema version 与九步 vocabulary 不变，因为事件结构、step 语义和比较序列不变；新增的是可由既有 events 完全重算的顶层派生计数。

## Tool request telemetry

每次 gateway 接收请求时先冻结一次 root remaining，再用同一个值计算 research remaining：

```python
remaining_root_seconds = max(0.0, context.deadline.remaining())
remaining_research_seconds = context.deadline.stage_timeout(
    remaining_root_seconds
)
```

`tool_request.payload` 新增：

- `timestamp`: 毫秒精度 UTC ISO-8601；
- `remaining_root_seconds_at_entry`: 未扣 synthesis reserve 的 root 生效余量；
- `remaining_research_seconds_at_entry`: 已扣 synthesis reserve、该研究阶段真正可用的余量。

两个数均 round 到 3 位。显式分开 root/research，避免再次制造 `remaining_seconds_at_entry` 这种需靠代码猜作用域的字段。现有 normalizer 会从 payload 读取 timestamp；数值继续保留在 raw runtime-benchmark artifact，不把它们塞进自由文本 summary。

## Public test seams

1. normalizer CLI：给一个 synthetic runtime-benchmark JSON，断言未配对 request 输出 1，`tool_result` 和 `tool_error` 各能配平到 0；
2. normalized artifact reuse：旧 artifact 缺字段时重算，新 artifact 声明错误计数时 fail loudly；
3. frozen T1/T3 artifacts：离线重归一化分别得到 0 与 1，不调用模型；
4. `HeadlessToolGateway.snapshot()`：在可控 deadline 下断言 request event 的 timestamp、root=70、research=40，并确认 query/evidence 行为不变。

这些 seam 都是调用方可观察的公共产物，不测试 `_add_event` 或内部 helper。

## Alternatives

### A. Derived artifact count + native entry telemetry（采用）

改动小、历史可重算、不碰运行语义；直接把人工判据升级为 CI/报告可读不变量。

### B. 发现 unpaired request 就让 normalizer 失败

不采用。历史失败 artifact 正是分诊材料，normalizer 应如实报告 `N`，不能因为 trace 不完整而拒绝生成可分析产物。R-10 的 release gate 可以在消费层断言 `N == 0`。

### C. 直接实现 per-tool cancellation 或 runtime conformance suite

本轮不做。前者是 R-10 的生产控制流，必须先有本 spec 的验收仪器；后者是正确的架构升格方向，但范围大于当前两个确定性前置条件，另立 spec。

## Non-goals

- 不修改 `total_seconds`、`floor_ratio`、`max_tool_calls`、synthesis reserve；
- 不修改 handoff window、`must_finalize` 或 per-tool timeout/cancellation；
- 不新增 live canary；
- 不接管原 worktree 中并发的 normalizer 改动；
- 不修两个 `acceptance_board` 测试本身，只纠正它们的分类标签。

## Acceptance

- T3 raw artifact 重新归一化得到 `unpaired_tool_requests=1`，T1 得到 0；
- balanced synthetic result/error 两条路径均为 0；
- 新 request event 同时有合法 timestamp、root/research 两个入口余量，且 `root - research` 能显式反映 reserve；
- focused tests 与 Ruff 通过；全量失败必须与父 revision 分账；
- 文档不再同时声称 configure/intent/plan 为 3/3 与 1/3；
- branch 独立 push，不合 main。

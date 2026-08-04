# Headless Tool Correlation Observability Design

## Goal

关闭 R-10 开工前的三个观测缺口：让 headless gateway 的同一次 tool request 与其 result/error 共享稳定身份；让 normalized artifact 对 `runtime-benchmark` 与 Codex rollout 真正计算配对状态、对不适用的 Workbench trace 明确返回 `null`；让派生计数篡改错误同时报告 declared 与 recomputed 值。

本轮只补观测契约，不实现 R-10 的 slow-tool timeout、finalization handoff、root-ledger 对齐或迟到结果隔离，也不改任何预算 profile。

## Problem statement

当前 `unpaired_tool_requests` 有三处会产生假绿或降低取证能力：

1. 计数器只识别 `tool_request → tool_result/tool_error`，但所有 kind 都无条件输出整数。Codex 的 `function_call → function_call_output` 因词表未接入而恒为 `0`；这个 `0` 实际表示“没有测量”，却会被读成“已配平”。
2. benchmark 只按 case 内数量/FIFO 配对，没有稳定 request identity。别的请求或迟到响应可能消费 pending，使结构计数变好看；R-10 无法独立断言“阈值响应属于哪个请求”和“同一请求是否又进入一个迟到终态”。
3. normalized artifact 的派生计数不一致时，错误只报告 recomputed 值，不再报告安全的 declared 整数，取证需要二次打开产物。

## Runtime request identity

### Identity shape

每次 `HeadlessToolGateway._execute_tool()` 冻结一个 32 位小写 hex `request_id`：

- mailbox 请求复用请求文件名的 stem；它与 `HeadlessMailboxExchange.request_id` 的 `.json` 前缀部分一致；
- HTTP 与进程内直接调用在执行入口生成 `secrets.token_hex(16)`；
- 外部传入的 mailbox id 必须满足同一 32-hex 契约，不能接受任意自由文本。

同一调用产生的 `tool_request` 以及唯一的 `tool_result` 或 `tool_error` 都写入该 `request_id`。拒绝、runner exception、root-budget 拒绝和执行后 cancellation 也必须保留同一个 id。response body 是否携带 id 不是配对依据；normalized artifact 只读落盘的事件 payload。

这不是把事件自身的 `source_event_id` 改成 request id。一个调用会生成至少两条独立事件，事件身份和调用相关身份必须是两个字段，否则无法区分“同一调用的两条事件”和“同一事件被重复写入”。

## Normalized artifact contract

### Optional `correlation_id`

`NormalizedEvent` 新增 `correlation_id: str | null`：

- `runtime-benchmark` 从事件顶层或 `payload.request_id` 读取；
- `codex-rollout` / `codex-exec` 只从顶层、`item` 或 `payload` 的 `call_id` / `tool_call_id` 读取；普通 `id` 是 event identity，不冒充 correlation identity；
- 只保留安全 token，不复制 query、arguments、output 或路径。

现有 schema 保持 `normalized-harness-trace-2`。这是一个明确标注为可选、可安全补缺的 additive 字段：旧 v2 event 缺字段时 loader 注入 `null`；新产物总是显式写出。其余未知 event key 仍 fail loudly，不能借兼容分支放宽整个 artifact validator。

### Kind-aware role vocabulary

配对角色由 `source_kind` 决定：

| source kind | request | response | 输出类型 |
|---|---|---|---|
| `runtime-benchmark` | `tool_request`, `tool_call` | `tool_result`, `tool_error` | `int` |
| `codex-rollout`, `codex-exec` | `function_call`, `command`, `mcp`, `tool` 家族，先排除 output | `_call_output`, `command_execution_output`, `tool_output`, `tool_result` | `int` |
| `workbench-trace` | 没有逐工具 request/response 原生词表 | 不适用 | `null` |

Codex 的 `source_event_type` 使用 `item.type`（若存在），而不是把所有 `item.completed` 压成同一个类型。结果词必须先于 request 词判断，因为 `function_call_output` 同时包含 `function_call`。

### Pairing algorithm

按 event 全局顺序、按 `case_id` 分桶：

1. 有 `correlation_id` 的 request 进入该 case 的 id pending set；相同 id 重复 request 仍是独立未配对异常，不能被 set 去重掩盖，因此内部使用计数。
2. 有 id 的 response 只消费同 id pending，不消费其他 id。
3. 没有 id 的 legacy request/response 使用同 case FIFO 计数。Codex synthetic/旧 rollout 若只有 event `id` 而没有共享 `call_id`，仍能报告数量缺口，但不宣称强关联。
4. 末尾所有 id pending 与 legacy pending 之和是 `unpaired_tool_requests`。
5. 不适用的 kind 返回 `null`，不返回健康零。

该计数只回答“可见 request 是否有可归属的后续终态”。R-10 的迟到结果隔离必须另断言：同一 `request_id` 恰好一个终态，且终态是阈值处的预期 error；`unpaired_tool_requests == 0` 单独不是充分条件。

### Derived-count validation

Artifact reuse 时按 `source_kind` 重算 `event_count`、`unmapped_count` 与 `unpaired_tool_requests`。已声明值若不一致，错误格式恢复为：

```text
<field>=<declared> disagrees with recomputed <actual>; the artifact was modified after it was written
```

这里只回显派生的 `int | null`，不回显 event summary、路径、query 或 credential。

## Public test seams

测试只走调用方能看到的公共边界：

1. normalizer CLI：Codex synthetic rollout 含一组完成调用和一个悬空调用，输出 `1`；Workbench trace 输出 `null`。
2. normalizer CLI：benchmark 中 matched request id 输出 `0`，mismatched id 输出 `1`；旧无 id 的 frozen T1/T2 仍为 `0/1`。
3. artifact reuse：旧 v2 event 缺 `correlation_id` 可重算；篡改计数的异常同时含 `declared` 与 `recomputed`。
4. `HeadlessToolGateway.snapshot()`：direct success 的 request/result 共享一个 32-hex id；拒绝路径 request/error 也共享。
5. mailbox 公共 wrapper：event id 等于 `HeadlessMailboxExchange.request_id` 去掉 `.json`，证明没有生成第二个身份。

不测试 `_add_event`、配对 helper 或随机数函数等内部实现细节。

## Alternatives

### A. Stable correlation id + kind-aware metric + N/A（采用）

同时解决 R-10 的身份前置条件和 R-02 的 Codex 假绿；旧无 id 产物还能做弱 FIFO 重算，迁移成本低。

### B. 只把非 benchmark 全改为 `null`

改动最小，但 R-02 明确要读真 Codex rollout；把 Codex 也标成 N/A 会丢掉现成词表能提供的信息，仍需下一轮再补。

### C. 复用 `source_event_id` 作为 request id

不采用。event identity 与 call correlation 是不同概念；让 request/result 共用 event id 会降低事件去重、重排和差分的可解释性。

### D. bump schema 到 v3

不采用。新字段是安全的 optional identity，旧 v2 可无歧义补 `null`；强制所有历史 normalized artifact 重归一化的收益不足。validator 只为这一字段做窄兼容，不接受任意额外字段。

## Non-goals

- 不实现 R-10 生产控制流；
- 不修改 `total_seconds`、`floor_ratio`、`max_tool_calls`、synthesis reserve 或 handoff window；
- 不跑 live canary；
- 不重跑四臂预算标定；
- 不合并 `main`；
- 不把 agent-memory 的 171 个未审提交与本代码分支混推。

## Acceptance

- gateway 所有 request/terminal event 路径共享合法稳定 id，mailbox id 可追溯到 exchange；
- Codex 悬空调用为 `1`，Workbench 为 `null`，benchmark mismatched id 不能误配为 `0`；
- frozen T1/T2 旧产物继续得到 `0/1`；
- 旧 v2 artifact 可再入，新 artifact 显式携带 `correlation_id`；
- mismatch 错误含 declared 与 recomputed，且不泄露自由文本；
- focused tests、Ruff 和相关全量通过；既有全量红按父 revision 同名同数对账；
- 独立分支 push，不合 main，不跑 live。

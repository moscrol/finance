# Codex Headless In-Flight Tool Deadline Handoff Design

**Status:** 方向已获用户确认；书面规格待审阅。
**Scope:** `R-20260804-10`，只修 Codex headless 的 in-flight tool 交接，不改预算墙。

## Goal

当一个已开始的只读工具无法在安全执行窗口内返回时，`HeadlessToolGateway` 必须在
Codex wrapper 自己超时以前，向同一模型上下文返回一条可配对的
`research_stage_closed + instruction`，只发一次 finalization，并保证工具线程后来完成
也不能把 evidence、trace、query-ledger 记录或第二个执行终态写回本 episode。

本轮验证的核心不是“工具最终有没有跑完”，而是“控制面能否按时夺回控制权并可靠进入
收尾”。

## Evidence and fixed constraints

1. 冻结 T3 的瑞华泰序列停在最后一个 `tool_request(evidence_search)`；5 个 request 只有
   4 个 mailbox exchange，`finalization=0`。结果/rejection 之后才触发的交接点不可达。
2. mailbox 与 HTTP wrapper 都只等待 60 秒。这个 transport 边界当前是静态代码事实，
   不是 artifact 里的自然工具耗时。
3. `ResearchDeadline.stage_timeout()` 已扣掉 `synthesis_reserve`；现有
   `initial_research_seconds * 0.20` 是第二份隐藏 reserve，必须删除。
4. L1 的 `episode_tool_batch` 已验证“后台执行 + absolute cutoff +
   `QueryPublishGuard`”能够隔离迟到 query-ledger publication。本轮复用这个机制，不重新
   发明另一套缓存隔离语义。
5. request/result/error 已共享 32-hex `request_id`，normalizer 已保留
   `correlation_id`。`unpaired_tool_requests=0` 仍不是迟到结果隔离的充分条件。
6. 不修改 `total_seconds`、`finalization_floor_ratio`、`max_tool_calls`、provider、模型、
   prompt、工具 schema 或 wrapper 返回给模型的 JSON 形状；离线主门通过前不跑 live。

## Chosen approach

采用 gateway-local watchdog。watchdog 是独立于被监控工作的计时器：工具在后台 daemon
线程执行，gateway 主线程只等到冻结的绝对截止点；截止点先到就关闭该 request 的发布权、
返回 handoff error，并让底层线程以 cooperative cancellation（协作式取消）自行退出。

这条路径保证“按时返回 + 迟到结果不可见”，但不声称 Python 能强杀一个忽略取消信号的
线程。由于 headless registry 只授权只读研究工具，迟到线程不会执行写业务状态的工具；
它可能继续消耗短暂网络/CPU，属于本方案明确接受的代价。

## Budget authority and deadline math

### One visible handoff source

handoff window 只从 enforcement point 实际读取的
`context.deadline.synthesis_reserve` 派生：

```python
initial_research_seconds = context.deadline.stage_timeout(
    context.deadline.remaining()
)
handoff_seconds = min(
    initial_research_seconds,
    max(0.0, context.deadline.synthesis_reserve),
)
```

不保留 20%、5 秒或 30 秒的隐藏推导。若生效 reserve 为 0，handoff window 就明确为 0，
不暗中补一个最小值。`finalization_floor_ratio` 继续只控制新请求入口 floor，不参与这项计算。

对 `c_long_capped`：root=180 秒、synthesis reserve=30 秒、初始 research window=150 秒，
故 handoff window=30 秒。Codex 主命令当前也使用 research window 作为 timeout；在 research
remaining=30 秒夺回控制权，模型仍有约 30 秒在同一命令内收尾，而 root 后面另有已声明的
30 秒 synthesis reserve 供既有 recovery 使用。两段都来自同一生效 profile，可在 artifact
里解释，不再是隐藏的 `initial×0.20`。

### One effective remaining-budget view

gateway 新增内部 helper，统一计算：

```python
remaining_calls = min(
    max(0, policy.max_steps - executed_count),
    max(0, root_budget.remaining_calls),  # ledger 存在时
)

remaining_research_seconds = min(
    deadline.stage_timeout(deadline.remaining()),
    max(0.0, root_budget.remaining_seconds),  # ledger 存在时
)
```

`_reservation_error`、`_pending_finalization_reason`、`_budget_payload` 和 per-tool grant
必须读取这两个 helper，禁止各算一遍。这样不能再出现
`remaining_tool_calls=0, must_finalize=false`，也不能在 root ledger 已耗尽后启动新工具。

### Transport-safe tool grant

wrapper 的 60 秒等待值升格为一个共享常量；gateway 预留 1 秒给线程调度、JSON 序列化、
mailbox 原子写入/fsync 和 20ms wrapper polling。两项都作为命名常量，不改生效 transport
wall。这个 59 秒上限约束仓库生成的 mailbox/HTTP wrapper；测试或其他直接调用
`HeadlessToolGateway.call(timeout=...)` 的客户端若给出更短 timeout，仍以客户端自己的等待边界
为准，不能把 59 秒理解为所有调用方的最低保证：

```python
TOOL_TRANSPORT_TIMEOUT_SECONDS = 60.0
TOOL_RESPONSE_PUBLISH_MARGIN_SECONDS = 1.0
transport_safe_seconds = 59.0

deadline_safe_seconds = max(
    0.0,
    remaining_research_seconds - handoff_seconds,
)
tool_grant_seconds = max(
    0.0,
    min(deadline_safe_seconds, transport_safe_seconds),
)
```

两种 limiter 都必须可观测：

- `handoff_window`：root/research 安全窗口先到；
- `transport_timeout`：wrapper 60 秒协议先到。

如果 grant 小于等于 0，不启动线程，直接进入 deadline-pressure handoff。

## Runtime flow

### 1. Admission

先在同一次 `call()` 内冻结 root/research 入口时钟，并用这份快照计算 handoff、transport cap、
grant 与 limiter；随后把 `tool_request` 作为该 request 的第一个事件一次性写出。这里“先算后写”
只为保证 request event 自包含，不会启动 worker、消费 call 或改变 admission 结论。事件写出后再完成
授权、参数解析、去重与预算检查：

1. root/policy calls 为 0 → `tool_budget_exhausted + instruction`；
2. gateway 已 finalizing → `research_stage_closed + instruction`；
3. deadline/floor/handoff 已关闭研究 → `research_stage_closed + instruction`；
4. 其他既有 invalid/duplicate/episode-snapshot rejection 保持原语义；
5. 只有真实 dispatch 才增加 `executed_count`，并在到达执行层终态时按下文计费规则恰好消费
   一次 root call。

request event 新增非敏感字段：

- `tool_grant_seconds`；
- `tool_grant_limiter`；
- `finalization_handoff_seconds`；
- `transport_timeout_seconds`。

已有 timestamp、request id、root/research 两只入口时钟保持不变。

invalid/duplicate 等未 dispatch 请求也保留该预算快照，便于解释“当时本可给多少”；但字段只是
观察值，不能据此把拒绝请求算成一次执行或 root call。

### 2. Guarded background execution

每个已 dispatch request 建立：

- 一个 request-local cancellation `Event`；
- 一个只保存 `ToolObservation` 或异常的 `Future`；
- 一个使用绝对 publish cutoff 的 `QueryPublishGuard`；
- 一个 daemon worker thread；
- 一份独立的 `Context.copy()`，保留当前 QueryLedger/ContextVar，但避免线程间重复进入同一
  context。

worker 只调用 `registry.execute()` 并完成 future；它没有 gateway snapshot/evidence/event
容器的引用写权限。只有等待方确认“截止点前完成”后，才允许调用现有
`_publish_observation()`。

传给 registry 的 cancellation callback 是 gateway cancellation 与 request-local event 的
逻辑或。已经支持 cooperative cancellation 的 provider 会尽早退出；不支持的 provider
即使迟到返回，也只能完成一个无人发布的 future。

### 3. Completion before cutoff

若 future 在绝对截止点前完成：

1. 关闭 publish guard，但不 rollback；
2. 按真实 elapsed 对 root ledger 只记一次 call；
3. exception 继续映射为单个脱敏 `tool_error`；
4. observation 继续走 `_publish_observation()`，只生成一个执行层 `tool_result`；
5. 既有 result-after-deadline / last-call finalization 语义保持。

### 4. Cutoff before completion

若 deadline 或 transport cutoff 先到：

1. 设置 request-local cancellation；
2. `QueryPublishGuard.close(rollback=True)`，撤销本 request 在竞态中刚发布的 ledger record；
3. 以 gateway 已等待的 elapsed 对 root ledger只记一次 call，迟到线程继续运行的时间不算作
   episode 可用预算；
4. 生成一个执行层 `tool_error`：
   `error=research_stage_closed`、`reason=inflight_tool_timeout`，并携带 request id、grant、
   limiter 与退出时两只余量；
5. 紧接着幂等生成一次 `finalization(reason=inflight_tool_timeout)`；
6. 向 wrapper 返回
   `{"status":"rejected","error":"research_stage_closed","instruction":...}`，其中 budget
   的 `must_finalize=true`；
7. 不等待、不 join daemon worker，不注册任何 late-result callback。

`inflight_tool_timeout` 加入受控 finalization reason 枚举。它区别于“请求入场时已是
deadline pressure”，也区别于 mailbox transport 自己的 `response_path_conflict`。

### 5. External cancellation

外部 cancellation 先到时，同样关闭 guard 并隔离迟到结果，但返回现有 `cancelled`，不伪造
finalization instruction。已 dispatch 的调用仍按等待到取消时的 elapsed 记一次 root call。

## Event and pairing semantics

执行层与 transport 层必须分账：

| 场景 | 同一 request id 的执行层终态 | 可追加的 transport 诊断 |
|---|---|---|
| 正常完成 | 恰好一个 `tool_result` | `response_path_conflict tool_error` |
| handoff timeout | 恰好一个 `tool_error(error=research_stage_closed)`，永无迟到 `tool_result` | `response_path_conflict tool_error` |
| 工具异常 | 恰好一个脱敏 `tool_error(error=tool_exception)` | `response_path_conflict tool_error` |
| 外部取消 | 恰好一个 `tool_error(error=cancelled)` | `response_path_conflict tool_error` |

`tool=mailbox,error=response_path_conflict` 不计入执行终态基数。normalizer 仍可把它当 response
观察到，但 release gate 的唯一性断言必须先按 layer/reason 过滤；否则合法 transport 冲突会
假红。

## Root-budget charging

预算计费收敛为“每个真实 dispatch 恰好一次”：

- 未授权、参数错误、重复 query、入场预算不足：0 call；
- 正常、empty、tool exception、external cancellation、handoff timeout：1 call；
- seconds 是 gateway 到达该执行终态前的 elapsed，不追收隔离后的 daemon 尾巴；
- root ledger race 导致 charge 失败时，只生成一个
  `root_budget_exhausted` 执行层 error 并进入 finalization，不能先写 timeout error 再补第二个
  error。

因此 `_charge_root_budget()` 不再自行追加 event；它只返回计费结果，由调用路径选择唯一终态。
这是本轮为消除 timeout/charge 竞态所需的局部记账修正，不扩展预算、prompt、profile 或工具行为。

## Test seams

用户已确认以下公共 seam；测试观察行为，不直接断言 worker 的私有容器：

### A. `HeadlessToolGateway.call()` + `snapshot()`（主门）

使用 barrier slow runner、fake monotonic/wait：

1. 截止点返回 `research_stage_closed + instruction`；
2. request/error/finalization 共享 id，事件顺序为
   `tool_request → tool_error → finalization`；
3. finalization 只有一次，生效 handoff/grant/limiter 已落盘；
4. 释放 slow runner 并等它真实完成后再次 snapshot，仍没有 evidence、trace、
   `tool_result` 或第二个 finalization；
5. 活动 QueryLedger 的 `executed_count` 仍为 0；
6. normalized artifact 的 `unpaired_tool_requests=0`。

另用 fast runner 固定正常路径只有一个 `tool_result`。

### B. Budget edge cases

1. `policy calls>0`、`root ledger calls=0`：不执行 runner，payload 同时显示
   `remaining_tool_calls=0` 与 `must_finalize=true`；
2. `finalization_floor_ratio=0`、reserve>0：watchdog 仍按 reserve 生效，证明 floor 与 handoff
   是两条独立控制线；
3. reserve=0：artifact 明确记录 handoff=0，不偷偷恢复旧 5 秒下限；
4. transport limiter 先到：在 wrapper 60 秒以前返回，limiter=`transport_timeout`；
5. root charge race：同 id 仍只有一个执行终态。

### C. Real wrapper seam with fake Codex process

`CodexHeadlessRuntime.run()` 的 fake command runner 真实执行生成的 `finance-tool` wrapper。
slow runner 被 watchdog 截断后，fake model 只有读到 instruction 才输出合法 finish。预期：

- wrapper exit code=0，不是 `finance tool mailbox timed out`；
- runtime event stop reason=`model_finish`；
- one request / one expected execution error / one mailbox exchange；
- wrapper 返回 body 不新增 request id 或内部 telemetry，模型侧协议形状不变。

### D. Transport conflict regression

单独制造 response path conflict，证明同 id 可以有一个正常执行 `tool_result` 加一个
`tool=mailbox,error=response_path_conflict`，但按执行层过滤仍恰好一个终态。这个测试防止
R-10 门禁以后把 transport 诊断重新混入执行基数。

## Alternatives considered

### B. 现在抽取 L1/L2 共用 `DeadlineToolExecutor`

长期方向更深：`episode_tool_batch` 与 headless 共用 executor、clock、guard 和 cancellation
状态机，能减少共享 registry 上方的控制面重复。但它会同时改并发 batch 排序、session 去重和
headless 单请求协议，回归面明显大于 R-10。当前先复用已经验证的 `QueryPublishGuard` 语义，
把完整控制面升格登记为独立架构任务。

### C. 强杀 Codex，再启动 no-tools finalizer

能获得真正的进程级硬取消，但会丢失同一模型上下文、增加 provider 调用，并引入 mailbox 临时
目录与第二进程恢复竞态。只在“线程隔离已生效但模型仍不能在 handoff window 内完成”被证实后
再考虑。

### D. 只把 cancellation callback 传得更深

改动最小，但 provider 若阻塞在不检查 callback 的 IO，gateway 仍拿不回控制权；它不能修复本次
已观测的无 response 形状，故不采用。

## Non-goals

- 不上调 root/child/phase/tool 的任何预算；
- 不改 `finalization_floor_ratio` 或调用次数；
- 不重跑四臂预算标定；
- 不用单次 live 替代离线结构主门；
- 不在本轮完成 L1/L2 全控制面抽取；
- 不承诺强杀忽略 cancellation 的 Python 线程；
- 不修改模型看到的 tool response schema、prompt 或工具参数；
- 不处理独立 pending 的 `R-20260804-02` 真 Codex rollout。

## Acceptance and falsification

### Offline release gate

以下条件必须全部成立，任一失败都不跑 live：

1. slow-tool fake-clock 主门证明按时返回、单次 finalization、late result 隔离；
2. root-ledger calls / seconds 与 payload、finalization reason 使用同一生效视图；
3. normal success 与 handoff timeout 分别满足一个执行层 `tool_result` / `tool_error`；
4. transport conflict 例外不造成假红；
5. focused、相关 deadline/cancellation/query-ledger/runtime/normalizer 测试通过；
6. 仓库根与 `intelligence/tests` 两个 scope 都声明 collected 数，并与父 revision 按失败身份
   对账；
7. diff 中 budget profile、模型、provider、live artifact 均为零变化。

### One live confirmation after the offline gate

只跑 `c_long_capped` 的瑞华泰单题，不重跑四臂或五题：

- 事件级 stop reason 变为 `model_finish` 且 latency <150 秒：
  `R-20260804-10 confirmed`，缺 in-flight handoff 是该失败层的 PRIMARY；
- handoff event/response 已出现但仍 timeout：R-10 的“交接足以完成”预测 refuted，转查
  finalization 自身耗时，不调预算掩盖；
- 仍缺 handoff，而 request 入口 grant 表明阈值应触发：实现未真正生效，保持 R-10 pending，
  回查生效 revision/profile，不能把它记成机制反证；
- handoff 在 wrapper transport limiter 触发：如实记录 transport 是先到的墙，不能冒充 root
  handoff 的直接证据。

无论哪种结局，都只按预注册条件更新 prediction ledger，不追加第二次 live 调试 run。

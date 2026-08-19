# Workbench Production-Agent Hardening Design

- 日期：2026-08-19
- 修订：2026-08-19 预审后修订——P0 附「已核验事实」；P3 的 terminal claim / late result 由「建立」改为「审计既有机制的覆盖边界」（`run_store.claim_terminal_run` 与 `QueryPublishGuard` 已存在且有测试）
- 状态：待 agent 审阅执行
- 范围：审查并逐步加固 Workbench/Benchwork 的 Agent runtime loop
- 目标：把当前“生产候选级 runtime”推进到“单机/小规模自用场景的生产级 Agent runtime”
- 非目标：本轮不更换 Agent SDK，不重写领域服务，不建设分布式多租户平台，不把所有问题合并成一次大重构

## 1. 当前判断

当前 runtime 的核心 loop 已具备生产候选级能力：

```text
TaskFrame / TurnControl
  -> Research Contract
  -> bounded Episode loop
  -> structural verification
  -> semantic verification
  -> bounded repair
  -> public answer / partial / degraded / failed
```

已确认的强项：

1. Episode 主循环有绝对 deadline、root budget、工具调用上限、PLAN 轮数上限。
2. finalization 阶段关闭工具，模型不能在终局阶段无界继续检索。
3. 结构验证与语义验证分层；结构事实不交给 LLM judge 决定。
4. repair 复用同一 Episode 的消息、工具 session、证据 ledger 和轨迹。
5. repair 失败不会无条件覆盖已有 draft/bindings。
6. trace/receipt 已记录模型轮、工具轮、错误、repair、finalization 和 verifier 状态。
7. 相关定向测试当前结果为 `127 passed`（2026-08-19 已在主树复现：`127 passed in 1.89s` @ `78391e8e`，收据 `~/.finance-runtime/test-receipts/20260819T122900Z-78391e8e.json`）。
8. run 层已有原子终态认领 `run_store.claim_terminal_run()`；query ledger 层已有 late result 丢弃 `QueryPublishGuard`。**这两项不是从零建设，是审计覆盖边界**（详见 P0 已核验事实与 P3）。

当前尚不能直接称为完整生产级 Agent 平台，原因集中在四个横向能力：

- 状态转移虽存在于代码中，但尚未成为可审计的单一状态模型。
- deadline、policy、root budget、repair grant 和 deep promotion 之间的预算语义较复杂，需进一步证明不会漂移。
- 取消、并发、late result、进程重启恢复的生产不变量尚未形成完整证据。
- trace 已较丰富，但尚未收敛为可运营的 SLO、发布门和回滚机制。

本 spec 的核心判断是：**先加固现有底座，不换底座。**

## 2. 领域术语与边界

本 spec 统一使用以下术语：

| 术语 | 定义 |
|---|---|
| Episode | 一次研究任务的连续执行单元，拥有固定 TaskFrame、Contract、root budget 和轨迹 |
| root budget | 一次 Episode 的唯一额度真相源，管理调用数和秒数 hard cap |
| deadline | 以绝对 monotonic 时刻表示的时间边界；所有子阶段只能缩短，不能重置根时钟 |
| finalization | 基于已有观察生成结构化终止结果的阶段，工具默认关闭 |
| repair | 对已有 Episode 进行的有限状态转移，不是无条件重跑 |
| cold restart | 零证据且主路径被模型/窗口饿死时，由代码授予的一次受限重新取证机会 |
| late result | Episode 已声明终态后才返回的子任务、工具或 provider 结果 |
| production receipt | 与 run、revision、provider、预算和状态转移绑定的机器可读运行收据 |

边界原则：

1. Agent 可以提出计划和动作，但不能自行提高预算、扩大工具权限或宣称完成。
2. 领域服务拥有金融事实和证据规则；runtime 只负责执行、预算、状态和交付边界。
3. 原始 trace 是不可变事实；诊断和解释写 sidecar，不覆盖原始事实。
4. `partial`、`degraded`、`failed` 是不同状态，不能为了交付率把它们压成 completed。

## 3. 不变量

以下不变量是所有后续实现和审阅的共同验收基准：

### I1. 状态收敛

每个 Episode 必须在有限步内进入一个终态：

```text
completed | partial | degraded | failed | cancelled
```

任何非终态都必须仍有：

- 未过期 deadline；
- 可消费的 root budget；
- 明确的下一状态；
- 对应 trace event。

### I2. 预算单一真相源

- 实际 provider/tool 调用的额度最终由 root budget 约束。
- 所有子 grant 必须从 root hard cap 的未分配余量产生。
- grant 不能恢复已经消费的额度，不能绕过 hard cap。
- `policy.max_steps`、`root_budget.initial_calls`、deep promotion 后的 cap 必须有明确对应关系。
- 结算失败不能制造新的 runtime failure；已经发生的工作必须可结算或明确记录为 settled overflow。

### I3. deadline 单调

- 根 deadline 使用绝对时刻。
- 子 deadline 只能是根 deadline 的子区间，不能重新从“现在”开始完整计时。
- repair、semantic verify、finalization recovery 都不能把总时长重置。
- 任一 provider/tool 调用收到的 timeout 必须不大于当前真实剩余时间。

### I4. 终态唯一归属

- 一个 run 只能有一个 terminal claim。
- terminal claim 之后到达的 child/provider/tool result 不得改变公开状态。
- late result 可以记录为诊断，但不能写入已关闭的公开 artifact、证据 ledger 或 answer。

### I5. repair 单调进展

repair 必须明确属于以下至少一种进展：

```text
EvidenceProgress       新增有效证据或来源族
BindingProgress        新增/修复 output-evidence binding
PresentationProgress   补齐结构化交付、draft 或 required marker
```

没有任何进展时不得无限续命；失败的 repair 不得抹掉更好的既有 draft/bindings。

### I6. 权限单调

模型只能使用当前 Contract 和 Registry 暴露的 capability。PLAN、repair goal、mode decision 都不能自行授权工具、提高预算或改变 TaskFrame。

### I7. 事实和诊断分离

- 原始 trace 记录发生了什么。
- triage/diagnostic 记录为什么可能发生。
- 缺少 trace 时输出 `insufficient_trace`，不能从最终文本反推精确根因。

## 4. 优化路线总览

按以下顺序执行，禁止跳到后面的“大改”而跳过前置审计：

```text
P0 事实核验与基线收据
  -> P1 可证明的 Episode 状态机
  -> P2 预算/deadline 真相源加固
  -> P3 并发、取消、late result、恢复
  -> P4 可运营指标、发布门和回滚
  -> P5 组合故障与生产候选验收
```

每个 phase 必须产出可执行命令和收据。只读审计发现没有对应验收证据时，不得声称完成。

## 5. P0：事实核验与基线

### 目标

在改代码前冻结当前实现事实，避免把历史已修复问题再次当成缺口，也避免用探针自己的缺陷代替生产行为。

### 必查范围

- `intelligence/runtime/agent_episode.py`
- `intelligence/runtime/continuous_turn_adapter.py`
- `intelligence/runtime/episode_finalizer.py`
- `intelligence/runtime/sub_research.py`
- `intelligence/runtime/conversation_orchestrator.py`
- `intelligence/services/research_contract.py`
- `intelligence/services/repair_coordinator.py`
- `intelligence/services/mode_governor.py`
- 相关 `intelligence/tests/test_*episode*.py`、adapter、budget、concurrency 测试

### 执行要求

1. 先跑 `git status --short && git branch --show-current && git worktree list`，逐条识别他人改动。
2. 生成状态/预算/并发相关符号索引，不批量阅读无关知识库正文。
3. 运行当前 loop 定向测试，记录完整命令、commit、Python 环境和结果。
4. 对每个后续缺口填写：代码位置、触发条件、当前行为、证据、是否实际缺陷。
5. 若审阅发现本 spec 的判断与代码不符，先报告冲突，不直接改实现。

### 已核验事实（2026-08-19 预审，勿再当缺口重新发现）

以下事实已逐条对过代码（定位以符号名为准，行号是当次核验快照、会漂移）。P0 直接引用即可，后续阶段核查它们的**覆盖边界**而非存在性：

| 事实 | 位置 |
|---|---|
| Episode 主循环硬上限 `range(1, MAX_EPISODE_TOOL_CALLS + MAX_PLAN_TURNS + 2)` | `intelligence/runtime/agent_episode.py` 主循环（~558） |
| finalization 阶段 `tools=[] if finalization_started else definitions` | 同上（~632） |
| repair 不倒退：候选空 draft 时结转旧 draft/bindings，status/gaps 留失败痕 | `intelligence/runtime/continuous_turn_adapter.py` `_run_repair`（~931，2026-08-10 事故防线） |
| repair 进展闸 `CoverageDelta.progressed` = 新证据 ≥1 AND（缩小 gap ≥1 OR 新支持 output ≥1） | `intelligence/services/repair_coordinator.py` `CoverageDelta` / `should_reenter` |
| 饿死型豁免 `grant_for_cold_restart`（2026-08-13 生产实测后加） | 同上 |
| 有 root budget 时工具槽位完全以 `root_budget.remaining_calls` 为准，不与 policy 取 min | `intelligence/runtime/agent_episode.py` `_remaining_tool_slots` |
| 原子终态认领 `claim_terminal_run(run_id, status) -> (Run, claimed)`，`finish_run` 走同一路径 | `intelligence/services/run_store.py`；测试：`test_run_store.py`、`test_conversation_orchestrator.py`、`test_workbench_conversation_integration.py`、`test_workbench_api.py` |
| late result 丢弃 `QueryPublishGuard`（关闭后丢弃晚到结果并允许重试） | 测试 `intelligence/tests/test_p1b_runtime.py::test_closed_publish_guard_discards_late_result_and_allows_retry` |
| 预算一致性断言现状：全仓仅 benchmark 一处硬编码 `initial_calls == 12`，**无**通用 `initial_calls == policy.max_steps` 不变量测试 | `intelligence/tests/test_run_agent_runtime_benchmark.py` |
| 测试收据写入 fail-open（失败仅警告不改测试结论），`FWP_TEST_RECEIPT=0` 可整体关闭；默认落点 `~/.finance-runtime/test-receipts/` 是跨 agent 采信的有意设计 | `conftest.py` |

### 完成标准

- 有一份基线审阅收据，列出当前状态、预算、repair、取消和持久化路径。
- 定向测试有明确 exit code。
- 所有“缺少 X”的断言都有 grep/测试/运行收据支撑。

## 6. P1：建立可审计的 Episode 状态模型

### 问题

状态转移目前分布在主 Episode loop、adapter repair loop、semantic verifier、finalizer 和 repair coordinator 中。行为大体正确，但未来维护者必须跨多个文件才能还原完整状态机，容易产生“主 loop 已终止、adapter 仍 repair”或“repair session 已失效但仍可调用”的边界错误。

### 设计

引入一个轻量、provider-neutral 的状态投影，不替换当前执行逻辑：

```python
EpisodePhase = Literal[
    "planning",
    "research",
    "finalizing",
    "structural_verify",
    "semantic_verify",
    "repair",
    "completed",
    "partial",
    "degraded",
    "failed",
    "cancelled",
]
```

每次跨阶段转移记录：

```text
from_phase
trigger
 to_phase
 reason_code
 remaining_calls
 remaining_seconds
 evidence_count
 repair_attempts
 terminal_claimed
```

推荐先做 projection/trace seam，再决定是否把控制流重构为显式 reducer。不要为了“看起来像状态机”重写 2,000 多行 runtime。

### 必须覆盖的转移

```text
planning -> research
planning -> finalizing
planning -> failed
research -> research
research -> finalizing
finalizing -> structural_verify
structural_verify -> semantic_verify
structural_verify -> repair
semantic_verify -> repair
semantic_verify -> completed
repair -> structural_verify
repair -> semantic_verify
repair -> partial/degraded/failed
any_nonterminal -> cancelled
any_nonterminal -> terminal
```

### 验收

- 每个公开终态都有且只有一个终态事件。
- trace 中不存在未定义的 from/to phase。
- 终态之后没有改变公开 outcome 的事件。
- 现有定向测试全部通过。
- 离线 fixture 能生成完整状态序列。

## 7. P2：预算与 deadline 加固

### 问题

当前存在 policy、root budget、deep promotion、synthesis reserve、repair grant、transient retry grant、bounded child deadline 多个预算概念。它们已有大量保护，但需要把“谁是权威”和“每次调用如何扣账”变成可机械验证的契约。

### 设计要求

#### 7.1 明确额度层级

```text
ResearchPolicy       静态档位声明
RootBudgetLedger     动态唯一额度真相源
ResearchDeadline     动态绝对时间真相源
RepairGrant          root ledger 授予的受限额度
```

policy 不得在运行中直接充当实时剩余额度；所有实际消费读取 root ledger。

#### 7.2 增加一致性断言

现状（P0 预审已核验）：全仓与此相关的唯一断言是 benchmark 测试里的硬编码 `assert context.root_budget.initial_calls == 12`，不构成通用不变量；`_remaining_tool_slots` 在有 root budget 时完全信任 `remaining_calls`，隐含前提「root budget 是 policy.max_steps 的权威投影」目前只靠初始化逻辑维持。

至少覆盖：

- 初始 `root.initial_calls == policy.max_steps`。
- 初始 root seconds 与 policy synthesis reserve 的关系明确且有测试。
- deep promotion 后 `context.policy.tier`、root hard caps、deadline extension、synthesis reserve 一致。
- repair grant 的 calls/seconds 不超过 root hard cap 未分配余量。
- 所有实际调用收到的 timeout 不大于 deadline remaining。
- root budget 消费与 receipt usage 对账一致。

#### 7.3 统一调用前预占与调用后结算

审阅所有路径：

- 主模型调用
- 工具批次
- sub-research 分支
- repair model
- repair finalize
- semantic verifier
- finalization recovery

确认每条路径都不会绕过 root budget。若当前 semantic verifier 使用独立预算，必须明确它是 root ledger 的子授权还是独立的产品预算；不允许仅凭 telemetry 宣称预算受控。

### 验收

构造并通过以下场景：

1. 首轮模型耗尽检索窗口。
2. 工具批次完成时 root 秒数已接近 0。
3. deep promotion 发生后马上 repair。
4. repair 首次 timeout 后 transient retry。
5. 工具部分成功、部分 timeout。
6. deadline 与 root seconds 谁先耗尽的两种情况。

每个场景都必须能回答：

```text
实际调用了几次
实际消耗多少秒
root 剩余多少
grant 从哪里来
最终状态是什么
```

## 8. P3：并发、取消、late result 和恢复

### 问题

当前有 cancellation、并行 sub-research 和进程内 continuation；run 层已有原子终态认领（`run_store.claim_terminal_run`），query ledger 层已有 late result 丢弃（`QueryPublishGuard`）。本阶段的任务**不是从零建设这两个机制**，而是证明它们的覆盖边界：child task 的终止、Episode 内部写入路径是否同样受终态保护、进程重启恢复的真实边界。

### 设计要求

#### 8.1 terminal claim（审计既有机制，不重建）

单一终态归属已由 `intelligence/services/run_store.py` 的 `claim_terminal_run(run_id, status) -> (Run, claimed)` 实现，`finish_run` 走同一路径，测试覆盖见 `test_run_store.py` / `test_conversation_orchestrator.py` / `test_workbench_conversation_integration.py` / `test_workbench_api.py`。

本阶段要审计并给出证据的是覆盖边界：

- 公开 outcome、answer、public citations、公开 artifact 是否全部只能由持有 claim 的路径写入；
- Episode 内部写入（证据 ledger、trace sidecar、repair 续写）在 run 已终态后是否仍可能发生；
- sub-research child 与工具批次的晚到写入是否绕过 run store 这层。

只有审计证明某条写入路径绕过 claim，才进入修复；禁止另建第二套终态机制。

#### 8.2 late result 隔离（先审计既有 guard 的覆盖范围）

query ledger 层已有 `QueryPublishGuard`：guard 关闭后晚到结果被丢弃并允许重试（测试 `test_p1b_runtime.py::test_closed_publish_guard_discards_late_result_and_allows_retry`）。本阶段审计其余路径（工具批次、sub-research 分支、repair provider）是否有等价隔离；缺口补齐到统一口径，不另起一套。

child/provider result 至少携带：

- run_id
- episode_id
- child_id 或 request_id
- source event id
- result state

终态之后到达的结果只能写诊断 sidecar，并记录 `late_result_discarded`；不能追加证据、改 answer 或让 repair 重新打开。

#### 8.3 cancellation

取消必须验证：

- 主循环在模型调用前、工具提交前、工具等待中、验证前检查。
- sub-research child 收到取消信号。
- executor/future 不会无限阻塞主请求。
- 取消之后不会再发起新 provider/tool 调用。
- 公开状态稳定为 `cancelled` 或产品定义的可交付降级状态。

#### 8.4 进程内与进程外恢复分开

第一阶段只要求明确当前边界：

- 进程内 repair/continuation：必须可恢复。
- 进程重启恢复：先做审计，若未实现则明确标为 capability gap，不用伪造支持。

若进入实现，持久化最小 state 必须包含：

```text
run identity
TaskFrame hash
contract hash
source revision
phase
messages 或可重建引用
evidence ledger snapshot
budget snapshot
deadline provenance
last event id
```

### 验收

- 并行分支一条卡住、其他分支完成时主任务按 deadline 收敛。
- 取消发生在模型、工具、验证三个位置时均不产生新调用。
- 终态后注入 late result，不改变公开结果。
- 两个并发请求不能共同提交同一 run 的终态。
- 进程内 repair 失败仍保留原 draft/bindings。

## 9. P4：从可诊断到可运营

### 问题

当前 receipt 已经很丰富，但还没有形成稳定的线上 SLO、发布门和回滚信号。

### 设计

定义最小 runtime metrics projection，按以下维度聚合：

```text
source_revision
runtime_backend
provider/model
question_type
research_tier
status
stop_reason
```

至少输出：

```text
completion_rate
partial_rate
degraded_rate
failed_rate
cancelled_rate
p50/p95 latency
p50/p95 time_to_first_tool
repair_rate
cold_restart_rate
late_result_rate
provider_error_rate
tool_error_rate
semantic_verifier_unavailable_rate
average_llm_calls
average_tool_calls
budget_exhaustion_rate
```

缺字段必须是 `unknown/not_evaluated`，不能填 0。

### 发布门

先做离线/人工可执行门，不立即接自动回滚：

1. source revision 与 artifact revision 一致。
2. runtime/backend/provider/model 身份完整。
3. 无未配对的关键 tool request/result。
4. 无 terminal claim 冲突。
5. budget usage 可对账。
6. 关键 deterministic regression 全绿。
7. canary 的 degraded、provider error、late result 没有超过预设阈值。

后续若接自动回滚，必须先固定阈值、观察窗口和回滚对象，不能用模糊的“质量下降”触发。

## 10. P5：组合故障验收

单元测试绿不等于生产级。建立 deterministic fault-injection matrix，至少包括：

| 故障组合 | 预期 |
|---|---|
| 首轮模型 timeout + 零证据 | 有界 cold restart 或明确 failed，不无限重试 |
| 工具部分成功 + 部分 timeout | 保留成功证据，公开状态为 partial/degraded，预算可对账 |
| semantic verifier timeout + 已有 draft | 不丢已有 draft，不能虚报 completed |
| repair provider late result | 不改变已声明终态 |
| deep promotion + cancellation | 不再发起新调用，终态唯一 |
| root seconds exhausted + batch settlement | 不因结算异常二次炸掉 |
| duplicate terminal claim | 第二方失败并留下诊断 |
| process restart at repair boundary | 按当前支持边界恢复或明确不可恢复 |
| receipt write failure | 不伪造完整 receipt；运行状态与诊断清楚区分 |

每个 case 都必须记录：

```text
injected failure
expected phase path
actual phase path
expected budget delta
actual budget delta
expected public status
actual public status
```

## 11. 实施顺序与 agent 工作协议

### 第一轮：只读审阅

agent 不改 runtime，只完成 P0，并输出：

- 当前状态图
- 当前预算图
- 当前并发/取消图
- 已实现不变量与缺口
- 每个缺口的代码位置和最小复现
- 建议进入 P1-P5 的优先级

### 第二轮：最小观测接缝

优先实现：

1. phase transition projection
2. terminal claim/late result 观测
3. budget/deadline 对账字段
4. progress 三分法

这些改动应先增加观测和测试，不改变正常业务路径。

### 第三轮：行为修复

只有第二轮收据明确证明存在缺陷，才实现：

- 状态归属修复
- 预算接线修复
- cancellation/late result 修复
- durable continuation 或明确不支持

### 第四轮：发布和运营

最后才做 metrics、canary gate、回滚策略。不要在状态和预算尚未稳定时先做仪表盘。

## 12. 明确不做的事情

1. 不因为“生产级”这个词就替换现有 loop 为 Agent SDK。
2. 不把 `completed` 阈值放宽来提高成功率。
3. 不把语义 judge 变成结构事实的唯一裁判。
4. 不用 retry 次数替代 progress 判据。
5. 不把旧答案回放当作新 revision 的生产验证。
6. 不用测试 fixture 的行为推断真实 provider 的延迟或错误分布。
7. 不因单个失败就增加全局预算、关闭 deadline 或绕过 root ledger。
8. 不在当前主 worktree 混入 unrelated 改动；大改必须独立分支。
9. 不重新实现已存在的终态认领与 late result 机制（`claim_terminal_run` / `QueryPublishGuard`）；先审计覆盖边界，只补被证明的缺口。
10. 不把测试收据默认落点改到 tmp_path——收据写 `~/.finance-runtime/test-receipts/` 是「结论携带成立条件」的跨 agent 采信设计；sandbox 等禁写环境用 `FWP_TEST_RECEIPT=0` 关闭，不改默认行为。

## 13. 最终完成定义

本路线只有满足以下条件，才能把 runtime 称为“单机/小规模自用场景的生产级 Agent runtime”：

- 状态转移可从 receipt 重建，终态唯一。
- root budget 是唯一实时额度真相源，policy/deep/repair 与其一致。
- deadline 是绝对且单调的，所有调用都受其约束。
- cancel、并发 child、late result 不污染公开 outcome。
- repair 具有可观测的 evidence/binding/presentation progress，失败不丢已有答案。
- 进程内 continuation 有测试；进程重启能力明确声明，不伪造。
- 关键组合故障有 deterministic fault-injection 验收。
- 生产 receipt 能支持 SLO 聚合、版本对比和发布门。
- 所有结论都有命令、测试或运行收据支撑。

达到这里以后，才需要讨论多用户托管平台级能力：durable workflow、多租户隔离、限流、成本计费、分布式调度和自动回滚。

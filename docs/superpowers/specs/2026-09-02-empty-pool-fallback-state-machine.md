# 设计：`fallback_after_empty_batch` 状态机——空池回退的领域边与底座边

> 承接 `2026-09-02-research-harness-loop-decouple-design.md` §4 #8 / §9 P2 最后一条：
> 「`fallback_after_empty_batch`。持状态、改控制流，先画状态机。」
>
> 与 `2026-09-02-repair-policy-state-machine.md` 同一套判据（原 spec §3：底座 = 拥有循环、算超时、
> 记账；领域 = 回答「金融题怎样才算对」）。**结论先说**：这台状态机比修复轮小一个量级，
> 领域判定**已经是**一个纯函数（`services/empty_pool_fallback.propose_empty_pool_fallback`），
> 不需要像 `repair_policy` 那样先拆七处混合；要做的是把 loop 里**凑输入 + 认识这个概念**的那段
> 收成一个 harness 方法，让第二条 loop 也能跑它。所以本单**画完就抽**，设计与实施同一张 PR。
>
> **所有 file:line 对 `gitea/main = 43bd200e` 成立。** 行号会漂，符号名不会。
>
> **状态：已实施**（分支 `spec/harness-empty-pool-fallback`，`23a3868f`）。`ResearchHarness` 十五 →
> 十六方法；X1 / X2 两处收口；`HarnessReferenceLoop` 同位跑同一枪。§4 四条验收全闭：等价（四形状 +
> 既有 4 条 Episode 用例）/ 有牙（从不回退、改排涨幅两种 harness 均改变 outcome）/ 棘轮（Episode 不
> import `empty_pool_fallback`、无字面量）/ 第二条 loop（runner 收到的参数、补查事件领域投影、模型
> 消息、outcome 四者一致）。变异一次（默认实现硬写 `in_repair=True` → 红 5）。**未动**：九道判定、
> as-of 口径、与补枪的互斥、`resume()` 不回退。

---

## 0. 一句话

某个 `finance_query(dataset=sector_daily)` 池在**开场预取空表**且**首轮 0 行**时，loop 在下一次
问模型之前，自己替模型补发**恰好一次**「同窗成交额前排」查询（`services/empty_pool_fallback.py`
文首）。「该不该补、补什么」是领域；「补的这一枪怎么派、记哪笔账、什么时候不许再补」是底座。
现状：判定在 services（对），执行在 loop（对），**凑判定输入与认识回退概念**在 loop（错层）。

---

## 1. 状态机

### 1.1 入口（只有一条）

研究阶段每一批工具跑完（`agent_episode.run()` :1154，`accumulator.consume` 与 `halt_after_tool_batch`
之后、`_append_tool_budget_state` 之前）。修复轮**不进**（`in_repair=False` 写死在 :1889；
`resume()` 不调）。

### 1.2 状态转移

```
   TOOL_BATCH_DONE ──► GATHER（底座凑事实）──► PROPOSE（领域判定，纯函数）──► grant？
                        剩余槛 remaining                propose_empty_pool_fallback      │
                        可派工具集 available          (:91)                       ┌────┴────┐
                        本批 (name, args, status)                              None      proposal
                        events（恰好一次的账）                                   │           │
                                                                              跳过     EXECUTE（底座）
                                                                                       session.execute(
                                                                                         fallback call,
                                                                                         remaining_slots)
                                                                                            │
                                                                                       INGEST（底座管线 +
                                                                                       harness 投影）
                                                                                       tool_request 带
                                                                                       request_extras
```

九道判定按顺序（全在 `propose_empty_pool_fallback` :103–:137，**一条都不在 loop**）：

| # | 判定 | 归属 |
|---|---|---|
| 1 | `question_type == "market_watch"` → 不做 | 领域（题型口径） |
| 2 | `already_attempted or in_repair` → 不做 | **恰好一次** + 修复轮不做：回退策略自己的规则 → 领域；事实由底座递 |
| 3 | 预取池非空 → 不做 | 领域（什么叫「池空」：`prefetch_pool_is_empty` :46） |
| 4 | `finance_query` 不在可派工具集 → 不做 | 领域读底座递来的事实 |
| 5 | 补枪计划已点名同能力 → 不做（互斥） | 领域（`_BACKFILL_MUTEX_CAPS`） |
| 6 | 本批没有 `sector_daily` 调用 → 不做 | 领域（哪种调用算「这个池」） |
| 7 | 有任一 `sector_daily` 调用非空 → 不做 | 领域 |
| 8 | as-of 解析不出 → 不做（`_resolve_as_of` :156：历史题继承 as-of，不打库尖） | 领域（截止日口径） |
| 9 | 原查询已经就是成交额前排 → 不做（`_same_amount_rank` :221） | 领域 |

### 1.3 出口

| 出口 | 语义 | 可观测 |
|---|---|---|
| 跳过 | 九道之一不成立，或剩余槛 ≤ 0 | 无事件 |
| 补发成功 | 一条 `application_tool_call`（声明：`source=empty_pool_fallback` + 调用身份与参数，2026-09-09 补）→ 一条 `tool_request`（`call_id=empty-pool-fallback-1`，`fallback_query=True`，`original_arguments`，`as_of`）+ `tool_result` | 事件 + 模型看到一条 `assistant.tool_calls` 声明和紧跟的新工具消息。声明缺失时那条工具消息是孤儿，OpenAI 兼容接口回 400（M3 / M6 真实 run） |
| 补发仍空 / 失败 | 同上，但 `tool_result` 为空 / `tool_error` | 「第二次仍空就停」——不会再有第三枪，因为下一批 `already_attempted` 为真 |

**恰好一次**不靠变量，靠扫 durable 事件（`fallback_already_attempted` :56：`fallback_query` 标记或
`call_id` 前缀）。这一点值得保留：状态就是事件流本身，可重放、可从 `AgentOutcome.events` 复原。

### 1.4 与另一台机器的关系

事后补枪 `plan_issue_backfill`（`episode_issues.py:186`）看到桌上已换过口径，就不对同一能力开第二枪
（`apply_fallback_backfill_mutex` :69）。两台机器的互斥**双向**：回退看 `backfill_plan`（现调用方
恒传 `None`），补枪看回退事件。本单不动这条互斥，只指出它在 services 侧、已经是领域。

---

## 2. 逐条归层

### 2.1 明确属底座

| 项 | 位置 | 理由 |
|---|---|---|
| 剩余槛 `remaining <= 0` → 不做 | episode :1859–:1864 | 预算 |
| 可派工具集 = `session.available_tool_names ∪ allowed_capabilities` | :1866–:1871 | 底座能力可达性 |
| 本批 `(name, arguments, status)` 三元组 | :1879–:1886 | 底座观察到的事实 |
| `session.execute(fallback call, remaining_slots=remaining)` + 计时 | :1894–:1908 | 派工具、记时钟 |
| `_settle_batch_calls` | run :1171 | root 账 |
| `accumulator.consume(fb_batch, request_extras=…)` | run :1166 | 底座管线（内含 harness 投影） |
| `in_repair` 这个**事实** | :1889 | loop 知道自己在哪个阶段 |

### 2.2 明确属领域（已在 `services/empty_pool_fallback.py`，不动）

九道判定、`_resolve_as_of`、`_amount_rank_arguments`、`_same_amount_rank`、`FALLBACK_CALL_ID` /
`FALLBACK_LIMIT`、`request_extras()` 的三个标记键、与补枪的互斥集合。

### 2.3 混合——本单要拆的（只有两处，都是「loop 认识这个概念」）

**X1. `_maybe_execute_empty_pool_fallback`（:1848–:1913）凑输入。** loop 知道要读 `context.information_cutoff`
的 `as_of_date` / `source`、知道要看 `registry.opening_prefetch`、知道要把批次结果装成 `EmptyToolCall`、知道
要扫事件判 `already_attempted`——这些都是**领域判定的输入**，只有「剩余槛 / 可派工具集 / 本批三元组 /
事件流 / 阶段」是底座自己拥有的事实。拆法：底座只递它拥有的五样，领域自己从 `context` / `registry` /
`events` 里读其余。

**X2. `_EpisodeToolAccumulator.consume`（:373–:374）认识回退的 call_id 前缀。**
`elif call.call_id.startswith("empty-pool-fallback"): request_payload["fallback_query"] = True`——
是给「没带 extras 的回退调用」兜底。回退调用只有一处产生且必带 extras，这个兜底等于 loop 记住了
领域常量。拆法：删掉；标记只从 harness 返回的 `request_extras` 来。

没有 M5/M6 那种**方向相反**的错层：预算算术没跑进 services，领域判定也没跑进 runtime。所以**不需要先拆再搬**。

---

## 3. 接缝签名

```python
class ToolCallOutcome(Protocol):          # 结构声明，不 import runtime（同 BranchOutcome 的做法）
    @property
    def call(self) -> ModelToolCall: ...
    @property
    def status(self) -> str: ...          # success / empty / rejected / timeout / error

@dataclass(frozen=True)
class FallbackCall:
    """loop 在本批之后、下一次问模型之前，替模型补发的一次工具调用。"""
    call: ModelToolCall
    request_extras: dict[str, object]     # 进 tool_request 事件的标记（fallback_query / original_arguments / as_of）

class ResearchHarness(Protocol):
    def fallback_after_empty_batch(
        self,
        batch: Iterable[ToolCallOutcome],
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        authorized_tools: frozenset[str],
        events: Iterable[object],
        in_repair: bool,
    ) -> FallbackCall | None: ...
```

底座递五样事实（本批、可派工具集、事件流、阶段，以及在调用**之前**自己先判的剩余槛）；领域从
`context.contract.question_type` / `context.information_cutoff` / `registry.opening_prefetch` 读其余，
决定补不补、补什么。默认实现是对 `propose_empty_pool_fallback` 的**纯委托**：`backfill_plan=None`
（与现调用方一致）。

> **替代方案对比**
> - **A：把 `remaining_slots` 也递给 harness，让它自己判「付不付得起」。** 否——那是预算，与
>   `repair_policy` 的「领域申请、底座授予」一致：领域只说想不想补，底座决定派不派。
> - **B：harness 直接返回 `FallbackProposal`（services 值对象）。** 否——第二条 loop 的棘轮不许
>   import `empty_pool_fallback`；返回 harness 自己的值对象（`ModelToolCall` + extras dict），
>   loop 一行领域名字都不用认。
> - **C：把「恰好一次」的事件扫描搬进 loop 当状态变量。** 否——事件流已经是状态，可重放；
>   loop 若另存一个 bool，就多了一份要和事件对账的真源。

---

## 4. 验收（缺一条不算）

1. **等价**：默认 harness 的 `fallback_after_empty_batch` 与直接调 `propose_empty_pool_fallback` 在
   四种形状（空池命中 / 首轮有行 / 预取有行 / market_watch）上产物逐字段相同；`test_empty_pool_fallback.py`
   四条 Episode 级用例原样绿（事件标记、`as_of`、`order_by`、`original_arguments`、与补枪互斥）。
2. **有牙**：注入「从不回退」的 harness，同一空池脚本下 Episode 只跑一次 `finance_query`、事件里无
   `fallback_query`；注入「回退改用另一份参数」的 harness，模型看到的工具消息随之变。均看 outcome / 事件。
3. **棘轮**：`agent_episode.py` 不再 import `empty_pool_fallback`；源码无 `"empty-pool-fallback"` 字面量。
4. **第二条 loop**：`HarnessReferenceLoop.run()` 在每批工具后问同一方法并执行；同一空池脚本下两条 loop
   的 `tool_request`（含 `fallback_query` / `original_arguments` / `as_of`）一致、模型看到的消息一致
   （只差 `runtime_budget`）、outcome 一致。`harness_reference_loop.py` 文首「无空池回退」那条差消掉。

---

## 5. 非目标 / 红线

- 不改九道判定、不改 as-of 口径、不改 `FALLBACK_LIMIT`、不改与补枪的互斥。
- 不把回退接进 `resume()`（`in_repair=True` 时领域本就不批；本单不改这条）。
- 不为让测试绿而改 `empty_pool_fallback.py` 的判定。
- 生产快照、8792、启动器零改动；提交一律 pathspec。

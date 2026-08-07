# 分层重建路线 — 固定底座，逐块搭，搭一个测一个

> 立于 2026-08-06。起因：一轮关于「是否换 agent 底座」的评估。
> **结论是不换**（`earendil-works/pi` 与 OpenAI Agents SDK 均暂缓），改为
> **固定现有底座 → 把领域逻辑拆成积木 → 逐块往上搭、逐块测**。
>
> 这份是路线，不是工单。工单在 `docs/handoffs/`。

## 0. 为什么不换底座（决策记录）

AST 实测 `intelligence/` 219 模块 / 122K 行：

| 层 | 模块 | 行数 | 说明 |
|---|---|---|---|
| harness | 24 | 22,900 | 其中**只有约 5,200 行是真 loop 骨架** |
| 入口层 | 4 | 6,485 | `api.app` / `api.structured_reports` / `cli` / `eval.runner` |
| **干净积木** | **184** | **88,781** | 传递闭包不碰 harness |
| 污染积木 | 7 | 3,851 | 仅 `services.lane_generation` 一个是直接 import |

关键发现：**那 22,900 行 harness 里有 7,511 行其实是领域逻辑**，只是名字带
`episode_` 前缀（最大一块是 `episode_semantic_verifier.py` **2,894 行**的金融语义
grounding 判据）。换任何底座都要留着它们。

于是「换底座」的真实收益只有「不用自己写那 5,200 行循环骨架」，代价是：

- 上 `pi`（TypeScript）：**契约层 3,758 行要长期维护两份**（TS 校验 + Python 校验必须
  同步），且 pi 无 MCP，88,781 行干净积木每个都要写跨语言 RPC 适配。
- 转 `sdk_gpt`（Python）：代价近乎零，但收益也只有那 5,200 行。

**换底座不解决主要痛点。** 本轮实测出的 6 个问题里，5 个（`memory_lookup` 死代码、
系统提示词结构、上下文压缩缺失、两个引擎无契约、fulfillment 不进 trace）都落在
「要搬家」而不是「要扔掉」的那一栏——换任何底座它们都还是自己的。

## 1. 总路线

```
Phase 0  固定底座        ← 进行中
Phase 1  补底座的洞      ← 4 件已实测缺口
Phase 2  逐块搭 + 逐块测 ← 主体工作
Phase 3  引擎收敛        ← 数据驱动，最后做
```

每个 Phase 的完成标志**必须是一条可执行命令**，不接受"读代码确认"。

---

## Phase 0 · 固定底座（进行中）

| 项 | 状态 | 完成标志 |
|---|---|---|
| 8792 复活 | ✅ 已完成并复核 | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8792/` == 200 |
| 快照去耦合 | ✅ 已完成（`2026-08-07`） | 生产快照不出现在 `git worktree list` 里 |
| 分层门禁 | ✅ `scripts/layer_audit.py` 已入库（`d3b793d2`） | `layer_audit.py` 存在，ERROR 0，自述 revision |
| 领域逻辑搬出 harness | ✅ 15 个 loop 模块已搬进 `runtime/`（`b6900f47`） | 接缝 0（含命名 commit `0091f26a`） |

**Phase 0 完成 = 底座边界画清楚了，且有门禁守住。** 在此之前不开 Phase 1/2 的任何一件。

---

## Phase 1 · 补底座的洞（4 件，都已实测）

| # | 缺口 | 实测证据 | 优先级依据 |
|---|---|---|---|
| 1 | **上下文压缩零实现** | 全树 grep `compact/trim/summariz/prune/evict` 无命中；`agent_episode.py` 的 `messages` 只 `.append()`；工具观察全量 `json.dumps` 无上限。**观测部分已补，见下** | 唯一**正在积累**的风险。但已见 124K token 仍返 200（lifecycle handoff P1-3 明确排除了它作为 HTTP 400 的原因），所以**不是正在出血** |
| 2 | **`memory_lookup` 结构性不可达** | 三个授权源（`_RUNTIME_CAPABILITY_FLOOR` 20 条策略、`_PLAN_CAPABILITY_TO_RUNTIME` 10 条映射、`conversation_orchestrator` 9 个分支）全部无它；唯一授权处是 `test_episode_tools.py:1956` | 能力图谱记 12 个工具，生产只够得着 9 个，而 `graph_audit` 照常 exit 0 |
| 3 | **系统提示词结构** | `build_episode_instructions` 渲染后 1,601 字符 / **4 个换行** / 最长无换行段 **1,501 字符** / 24 条约束平铺 | 零行为风险的改动，但必须**只改形状不改字**，否则分不清收益来自结构还是内容 |
| 4 | **fulfillment 判定不进 trace** | 实测 0/305。**根因已纠正，见下** | 前三件改完都需要它来对账 |

### 第 4 项的根因纠正（`2026-08-07`）

原表述「判定不进 trace」暗示判定跑了、只是没记录。**实测不是这样：生产 research
路径根本不跑这道判定。**

```
conversation_orchestrator.py:1795
    if continuous_result.handled:
        return self._complete_continuous_turn(...)   ← early return
conversation_orchestrator.py:2864 附近
    task_fulfillment.evaluate_answer_spec_fulfillment(...)  ← 永远到不了
```

`_complete_continuous_turn` 整个函数体内零个 fulfillment 调用，`answer_status`
由一个硬编码三元式给出：`"complete" if result.status == "completed" else "partial"`。

证据链：那行 `_trace("task_fulfillment", ...)` 由 `e67c5cad`（`2026-07-31`）引入；
`2026-08-02` 有一个走完整 research 路径的 run（18 步 `continuous:episode:*`）仍 0 命中。
所以不是「trace 文件比代码老」，是结构性不可达。

**两条路径问的其实是两个不同的问题，都不多余：**

| 路径 | 完成判定 | 问的是 |
|---|---|---|
| Engine B（ask） | `task_fulfillment.evaluate_answer_spec_fulfillment` | 每个 required_output **在正文里被写到了吗** |
| Engine A（continuous） | `episode_verifier` + 语义判据 | 每个 output 的**证据绑定结构合法吗** |

Engine A 缺的正是 B 那一问，而 `answer_status` 照报 `complete`——仪表全绿，
所以这个洞能长期不被发现。

**本轮交付（只加观测）**：`_continuous_answer_coverage` 记录每个 required_output
的措辞是否进入公开正文，写入 trace 步 `answer_marker_coverage` 与
`report["answer_marker_coverage"]`。刻意**不动** `answer_status`、不 gate 交付。

两个实现约束，都由测试锁住：
- 不能直接复用 `evaluate_answer_spec_fulfillment`。它在 claims 为空时走
  `no_candidate_claim` 分支把每个 output 判成 missing，而 continuous 路径没有
  `AnswerSpec`（`agent_episode.py` 全文无 `answer_spec`）——那会产出满屏假缺口。
  能用的是不依赖 claims 的 `answer_has_output_marker`。
- `uncheckable` 必须与 `absent` 分开计。`answer_has_output_marker` 对「正文没写」
  和「`_MARKERS` 里没有这个 output 的词表」都返回 `False`；混在一起会把仪表盲区
  报成覆盖失败。全 uncheckable 时 `marker_coverage` 给 `None` 而非 `"complete"`
  ——那正是 `answer_status` 现在的毛病。

### 第 1 项的根因纠正 + 阶段 1 已交付（`2026-08-07`）

原表述「连数字都没有」不准确。**实测：token 一直在收，但收法有两层问题。**

1. **聚合方式无物理含义。** `agent_episode._token_usage_from_events` 把各轮
   `input_tokens` 相加。agent loop 每轮重发全部历史，所以轮 1 的 30K + 轮 2 的
   45K = 75K —— 既不是上下文大小（那是最后一���的 45K），也不是 token 账单。
   回答「离窗口上限还有多远」的是**单轮最大值**，回答「还在不在长」的是
   **逐轮序列**，两个都被加法抹掉了。
2. **不进 trace。** `2026-08-02` 那个 18 步 research run 的 trace.jsonl 全部 18 步
   零 token 信息；token 只在私有 artifact `continuous-episode.json` 里，且是累加和。

**可观测性按 backend 不同，这是结构属性不是缺陷：**

| backend | loop 在哪 | 逐轮 token |
|---|---|---|
| `continuous_glm` | `agent_episode` 自己的 provider 循环 | **精确**（每轮一个 `model_turn` 事件） |
| `sdk_glm` / `sdk_gpt` | 交给 OpenAI Agents SDK | **拿不到**。适配器边界只看得到 `result.context_wrapper.usage`，而那个对象已经把 SDK 内部多轮加总了（`usage.requests` 可 > 1） |

`2026-08-02` 那批 run 全是 `runtime_backend=sdk_gpt`，`model_turn` 事件 0 个——
这解释了为什么逐轮数据「看起来不存在」。

⚠️ **别把这条读成「生产走 sdk」。** 那批 run 全在
`tmp/agent-runtime-seam-fix-*/tmp/canary-users-*`（canary 实验目录），
而 `agent_runtime_factory.resolve_runtime_backend` 的默认值是 **`continuous_glm`**。
真实生产 users 目录下没有 research-path 的 `continuous-episode.json` 记录。
所以「逐轮 token 拿不到」是那批实验的属性，不是生产链路的属性——
生产默认那条路恰好是能拿到精确逐轮值的那条。

**本轮交付（只加观测）**：`services/context_growth.summarize_context_growth`
（纯变换，两个 backend 共用），结果进 trace 步 `context_growth` 与
`report["context_growth"]`。

关键设计约束，由测试锁住：**`provenance` 是一等字段**，取
`per_turn` / `run_aggregated` / `unavailable`。sdk 路径**不猜 `max_turn_input_tokens`**
（真值在均值与总和之间，SDK 不说在哪），只给 `mean_turn_input_tokens` 并标
`run_aggregated`。把两者糊成一个数会让粗粒度 backend 看起来和精确的一样——
和「把没有 marker 词表报成答案漏写」是同一种错：仪表盲区被读成发现。

**阶段 2 才动策略**（更激进的压缩），需要先跑一批真实题拿
`max_turn_input_tokens` 的 P50/P95/max 分布。那批题走生产默认的
`continuous_glm` 即可拿到 `per_turn` 精确值。

### 分层压缩：五层对照与我们的实际缺口（`2026-08-07`）

书（ai-agent-book 第 2 章「生产级的分层压缩机制」）给的五层，按
「便宜/局部/确定 → 昂贵/全局/有损」升级排列。逐层对照我们的现状：

| 层 | 书里的做法 | 我们的现状 |
|---|---|---|
| **0. 隔离**（书末结论：隔离优于压缩） | 子 Agent 独立上下文，主 Agent 只收结论 | ✅ **已实现**。`SubResearchCoordinator` 每分支独立 budget ledger + evidence sink，父只收 `BranchResult`。⚠️ 只接在 `glm_agent_runtime`，sdk/codex 两个 backend 为 0 |
| **1. 工具结果预算** | 原始结果落盘，上下文只留冻结预览 | ⚠️ **本轮只补了 Engine A 相对 Engine B 缺的那半**：单条观察的叙述上限��见下）。落盘本来就有，**上下文总量仍无上界** |
| **2. 噪声删除** | 按使用轨迹删未被引用的结果 | ❌ 未做。**我们有比书���硬的信号**：书靠启发式猜哪些没被用，我们有 `bindings`——终局时哪些 `content_hash` 真的绑进了 required_output 是确定的 |
| **3. API 侧微压缩** | 调 provider 的 context editing 移除 tool result | ❌ 未做，**且不建议做**：provider 特定，且必然使被移除位置之后的 KV cache 失效。收益完全取决于离窗口多远，正是现在缺的那个量 |
| **4. 轮次归档** | 逐轮 git-log 式档案，不 squash | ⚠️ **料已齐但没当上下文用**。`ledger.events` 本身就是逐轮档（`sequence` + task/tool_request/tool_result/finish）。注意 `_summarize_messages` 是 `"…" + text[-2399:]` 尾部切片（书警告的 squash 反模式），但它作用在**对话历史**层，不是 episode messages |
| **5. 全量 LLM 压缩 + 熔断** | 最后手段，失败要熔断 | ❌ 无全量压缩（见上方 ⛔）。但**熔断纪律我们有**：`MAX_EPISODE_TOOL_CALLS=24`、`repair_cycles`、deadline exhaustion |

**结论：缺口不均匀——最贵的那层（隔离）已建好，缺的是便宜的中段。**
这不是巧合：`SubResearchCoordinator` 那套 budget ledger 的复杂度远高于
「给 observation 加字符上限」，说明当初是从难的一头往下做的。

#### 第 1 层已交付：`services/tool_result_budget`

修的是一个**引擎间不对称**，不需要等分布数据：Engine B
（`agent_research`）一直有 `_MAX_OBSERVATION_CHARS = 900`，而 Engine A
（`agent_episode`，**生产 research 路径**）的 tool message 是裸 `json.dumps`，
零字符上限。

**实测（45 份真实 `continuous-episode.json`、82 个 `tool_result` 事件）**：

```
被截断的观察  : 28 / 82  (34.1%)
字节          : 299,552 → 287,694  = 减少 3.96%
最大单条观察  : 13,636 字符（截后 12,382，仍是 13K 量级）
```

**这三个数要一起读**：三分之一的观察确实碰到了上限，但总字节只降 3.96%，
且最大单条截完仍在 13K 量级——因为上限管的是**单个字段的叙述**
（`observation` / `title` / `detail`），而一条观察的体积主要来自 `evidence`
**条数**乘以每条的标识字段，那些一个都不能截。

**所以这一层没有给上下文总量设上界。** `evidence` 条数目前不设限，只靠
`intelligence/services/episode_tools.py` 上游各查询的 `limit`（5 / 12 / 18 /
`_AGENT_FINANCE_QUERY_MAX_ROWS = 25`）间接兜着——那是查询侧的资源上限，
不是上下文预算，改查询参数就会漂。

⚠️ **不要因此去加 `evidence` 条数上限。** 那要等 `max_turn_input_tokens` 的
P50/P95/max 分布，而该分布必须先修完「子 agent 聚合值污染逐轮读数」才可信
（见 `services/context_growth.py` 的两个 kind 集合）。先量后改。

这一层对我们几乎免费，因为前置条件已经成立——同一份 `public_observation`
本来就分流到两个 sink：

```
ledger.add("tool_result", payload)   → continuous-episode.json  （审计·全量）
messages.append({"role": "tool"})    → 模型上下文              （本轮加预算）
```

原始结果**已经在落盘**，`evidence_hashes` **已经是**回溯指针。所以只改喂模型
那一侧，`ledger` 保持全量——否则「压缩」就变成了毁证据。

**只截断叙述，标识一律不动**，这是红线（来源/时点/状态/缺口/完整性）的直接推论：
- `evidence_hashes` / `content_hash`：终局 binding 门禁要用。删一个不会让答案变短，只会让门禁无法满足
- `source` / `source_date` / `evidence_tier` / `freshness`：没有时点和层级的结论不是更短的结论，是另一个结论
- `gaps`：答案必须披露的东西
- `supports` / `contradicts`：删掉一条反证等于把有争议的发现静默升级成干净的

截断时附 `context_budget` 元数据（`omitted_chars` + `full_record_in` +
`preserved` 清单 + 指令），否则模型分不清「工具没查到」和「harness 没给我看」，
可能重复同一次查询。**具名指路**，不是一个裸 `truncated` 标志：
「有更多」而不说「在哪」不叫可审计。

**确定性是硬约束**：纯函数，无模型调用、无时钟、无随机。provider 的 prompt
cache 按前缀字节命中，每次生成不同预览会让恢复会话时缓存全部失效——省下的
token 抵不上重算的成本。这也是书里强调「预览一旦生成就冻结」的原因。

⛔ **不做滑动窗口 / LLM 摘要压缩。** 它会引入「压缩时丢掉了会改变结论的状态」——
最难查的一类 bug。压缩的红线是：**降噪 ≠ 静默丢证据**，任何压缩函数必须保留
**来源 / 时点 / 状态 / 缺口 / 完整性** 五个字段。骨架见
`agent-memory/70_tutor/消息编排边界：Harness组织上下文，LLM生成下一步.md`：

```json
{"status":"ok","requested_date":"...","source_date":"...","row_count":224,
 "summary":"...","omitted_rows":219,"provenance":"..."}
```

### 底座首次真实端到端验证（`2026-08-07`）

在此之前，`continuous_glm`（生产默认 backend）**磁盘上零条真实 run**。
`test_agent_episode.py` 有 40+ 用例密集覆盖 Harness 行为，但全部用 `ScriptedModel`
（按脚本返回，不打 API）——它们验证的是「模型这样回时编排是否正确」，
不验证真实模型在真实提示词下会不会正确回。`tmp/` 下 40 份
`continuous-episode.json` 全是 `sdk_gpt`（canary 实验）。

跑通 `scripts/smoke_workbench_self_use.py`（真实 HTTP + 真实 GLM + 真实 DuckDB）
后暴露两个洞，都不是单元测试能抓的类型：

#### 洞一：双根失真（已修，`10cde608`）

```
data_repo_root()              → 代码根（本仓）
default_paths().finance_root  → ~/Desktop/c c/金融     ← 各自回退，指向两棵树
```

不设环境变量时 DuckDB 落在本仓、exports/快照落在另一个仓。
`_runtime_market_reference_date()` 从旧仓 exports 取出 **6 月**的日期当 floor，
再拿它去查数据已到 **8 月**的本仓库——每条结构化查询都被判
「数据仅更新到 …，早于当前所需 …」。**数据一点都不旧，是标尺拿错了。**

三次同题冒烟：

| | 根不一致 | 手动 `FINANCE_WS` | 修复后（零环境变量） |
|---|---|---|---|
| 取到证据的工具 | 1 个 / 5 条 | 4 个 / 17 条 | 4 个 / 27 条 |
| `marker_coverage` | `incomplete` | `complete` | `complete` |
| `direct_assessment` | 缺失 | 写出 | 写出 |

⚠️ **这类 bug 单元测试永远抓不到**，因为每个组件自己都是对的，
错的是组件之间对「数据根在哪」的答案不一致。`default_market_db_path()`
的注释早已记过同一教训（库不在数据根时盘面证据层静默消失），
但当时只修了 DuckDB 一处。`test_paths.py` 现在锁住两根一致。

#### 洞二：工具契约不可学习（已修，`dae9c8c7`）

同一轮 research 里模型对同一个错犯了**两次**——把 `trade_date` 放进 `filters`
而非 `time_range`，两次被拒，��个工具槽白烧，最终 `deadline_exhausted` 降级。
重试提示写得很清楚（`日期不要放入 filters；请改用 time_range.start/end`），
隔一轮又犯。

**选择由 Harness 代偿而不是加强提示词**：日期该放 `time_range` 是本引擎的
局部约定，不是 SQL 常识；模型按「日期就是一个普通等值筛选」的直觉写是可预期的
高频错法。提示词只能降低概率，代偿能消除这类损耗。

`finance_query.normalize_spec()` 只在**语义完全等价**时搬：

```
eq  → start = end = 值      单日闭区间
gte → start = 值            编译期用 >=，同为闭端
lte → end   = 值            编译期用 <=，同为闭端
```

⛔ **`gt` / `lt` 刻意不搬**：`time_range` 两端编译成 `>=` / `<=`，
把开区间搬成闭区间会**静默多带一天数据**。报错只浪费一次调用，
静默改语义会让答案引用一条模型没要求的记录——和「删掉一条反证」是同一类错。
`ne` / `in` / `contains` 同理不搬（表达集合而非区间）。
端点已被显式 `time_range` 占用、值非 ISO 日期、合并后 `start > end`，
三种情况也都原样退回让原有校验报错。

代偿说明必须混进 `observation`：**查询成功但写法被改过���不说它下一轮还会照原样写。**

修复后同题冒烟：`stop_reason` 从 `deadline_exhausted` 变为 `model_finish`，
6 个工具请求全部完成，日期代偿触发 2 次。

**这条经验可迁移**：工具契约里凡是「引擎局部约定 ≠ 领域常识」的地方，
都该考虑 Harness 代偿而非只写进提示词。判据是等价性——能无损映射就代偿，
不能就报错，绝不猜。

---

## Phase 2 · 逐块搭 + 逐块测（主体）

### 「一块」的定义

一块 = 能力图谱里的一个节点，交付时必须同时具备四件：

| 件 | 验收方式 |
|---|---|
| **可达性** | 从生产授权路径能真的调到它（不是"定义了"，是"这次开着"）。`memory_lookup` 就是反例 |
| **契约** | 它产出什么 output_id、绑定什么证据、`grounding_mode` 是什么，显式声明 |
| **观测** | 调用/失败/耗时进 trace，且判定结果可复算 |
| **测试** | 含**变异测试**：抽掉那行 / 改掉那个值，测试必须变红 |

**四件缺一，这块就没搭完。** 这条是从本轮教训直接来的——`memory_lookup` 有实现、
有测试、有自述来源标注，唯独缺"可达性"，于是它在生产里一次都没跑过，而所有仪表全绿。

### 搭一个测一个的具体含义

- **一次一块，一个 commit。** 不攒批。
- 每块完成后跑全量：**基线 `13 failed, 3807 passed, 2 skipped`**（`test_userspace` 3 +
  `test_subconscious` 8 + `test_acceptance_board` 2，宿主环境固有）。**多出任何一条都是新引入的。**
- 解释器必须 `.venv-workbench/bin/python`。`python3` 是宿主 3.14，缺依赖，
  用它得出的"符号不存在""缺包"全是假的。
- 每块完成后跑 `scripts/layer_audit.py`，接缝数**只减不增**。

---

## Phase 3 · 引擎收敛（最后做，数据驱动）

当前是**一个调度器 + 两个引擎**：

- 引擎 A：`continuous_turn_adapter` → `agent_episode`（模型自选工具）
- 引擎 B：`ask.answer_query`（流程写死，兜底 + 三个确定性题型）

**两个引擎都调 LLM**，差别是「流程由代码定死」vs「流程由模型自己决定」，
不是「用不用 LLM」。引擎 B 只在三种情况接手：

```python
DETERMINISTIC_OWNER_TYPES = frozenset(
    {"external_market", "quick_fact", "dated_market_review"}
)
# continuous_turn_adapter.py:67，加上 control.terminal_kind != "research"
```

**保留两个引擎大概率是对的**——`quick_fact`（取值查询）跑 agent loop 是花几十秒
做一次 DuckDB 查询，还多一次幻觉机会。但**这个理由目前没有数据支撑**。

Phase 3 要做的：
1. 给这三个题型各跑几轮真实对照，量**方差**（同题两次答案的差异）
2. 有数字后再定合不合
3. 无论合不合，把分工写成**显式契约**——它是"有意保留的快路径"还是"待清理的债"，
   目前仍只有行为说明、没有文档声明。
   ✅ 改名已完成（`0091f26a`）：`LEGACY_DETERMINISTIC_OWNER_TYPES` →
   `DETERMINISTIC_OWNER_TYPES`，名字本身不再诱导下一个人去删它。

---

## 贯穿全程的三条纪律

本轮实际踩出来的，不是抽象原则：

1. **先量后改。** 没有分布数据就改压缩策略、没有方差数据就合引擎，都是赌。
2. **门禁的断言粒度必须匹配它保护的东西。** 只钉文件名保不住符号；只钉配置保不住生效值。
   本轮实测：把 `runtime_provenance.py:55` 改成排除未跟踪文件，跑完整 3,820 条测试
   **零新增红**——`/api/health` 的 `source_dirty` 可以静默漂成 bug 而无人知晓。
3. **负面断言要穷尽搜索。** 说"我们没有 X"之前：全树 grep 同义词 + 读能力图谱 +
   读项目笔记看板。搜一个文件证明不了。

---

## 明确不做的（写下来免得被重新提议）

- ❌ **换 agent 底座**（pi / sdk_gpt）——已评估，见 §0。将来若重议，触发条件应是
  「想要 TS 生态」或「前端与 agent 同语言」这类明确理由，**不是**「Python 这边没人维护 loop」
  （不成立，`openai_agents_runtime.py` 1,732 行已实现且 `agents` SDK 已安装）。
- ❌ **删 `POST /api/runs`**——前端不调（构建产物里只有 `/api/runs/${id}/...` 形式），
  但它是崩溃后恢复孤儿 run 的兜底路径（`app.py:1698` lifespan）。
- ❌ **动 `agent.py`**——它不在服务器里（`api/app.py` 从不 import 它），
  只服务 `cli.py:304` 和 `eval/runner.py:91`。动它会砸坏评测基线。
- ❌ **codex / A-B 对照线**——用户已决定暂停。`codex_headless` 默认关闭
  （`AGENT_RUNTIME_BENCHMARK_ENABLE` 未设），不挡主线；sidecar 坏账号那条🔴阻塞
  只挡 A/B，不挡产品。
- ❌ **大重构**。逐块搭的前提是每块可独立验证；大 diff 没法验证。

---

## 附：外部工具的适用边界

`deepwiki` MCP 已注册（`https://mcp.deepwiki.com/mcp`，HTTP，连接正常）。

⚠️ **它读不了本仓。** `linxiaoqi5111-del/finance-workspace-private` 是私有仓
（公开 GitHub API 返 `Not Found`），DeepWiki 索引的是公开仓。它适用于读
`earendil-works/pi` 这类公开项目。**要让外部服务索引本仓等于发布私有代码，
需要显式授权，不要顺手做。**

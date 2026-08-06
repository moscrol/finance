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
| 1 | **上下文压缩零实现** | 全树 grep `compact/trim/summariz/prune/evict` 无命中；`agent_episode.py` 的 `messages` 只 `.append()`；工具观察全量 `json.dumps` 无上限 | 唯一**正在积累**的风险。但已见 124K token 仍返 200（lifecycle handoff P1-3 明确排除了它作为 HTTP 400 的原因），所以**不是正在出血** |
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

### Phase 1 的通用纪律：先量后改

第 1 项尤其。现在连「每轮上下文多大、分布如何、离上限多远」都没有数字。
**阶段 1 只加观测**（token 数进 trace/EpisodeEvent，跑一批真实题拿 P50/P95/max），
**阶段 2 才动策略**（单条工具观察截断 + 完整性元数据）。

⛔ **不做滑动窗口 / LLM 摘要压缩。** 它会引入「压缩时丢掉了会改变结论的状态」——
最难查的一类 bug。压缩的红线是：**降噪 ≠ 静默丢证据**，任何压缩函数必须保留
**来源 / 时点 / 状态 / 缺口 / 完整性** 五个字段。骨架见
`agent-memory/70_tutor/消息编排边界：Harness组织上下文，LLM生成下一步.md`：

```json
{"status":"ok","requested_date":"...","source_date":"...","row_count":224,
 "summary":"...","omitted_rows":219,"provenance":"..."}
```

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
LEGACY_DETERMINISTIC_OWNER_TYPES = {"external_market", "quick_fact", "dated_market_review"}
# continuous_turn_adapter.py:67，加上 control.terminal_kind != "research"
```

**保留两个引擎大概率是对的**——`quick_fact`（取值查询）跑 agent loop 是花几十秒
做一次 DuckDB 查询，还多一次幻觉机会。但**这个理由目前没有数据支撑**。

Phase 3 要做的：
1. 给这三个题型各跑几轮真实对照，量**方差**（同题两次答案的差异）
2. 有数字后再定合不合
3. 无论合不合，把分工写成**显式契约**，并给 `LEGACY_DETERMINISTIC_OWNER_TYPES` 改名——
   实测全仓没有任何一处文档说明它是"待清理的债"还是"有意保留的快路径"，
   而它的行为是后者。名字里的 `LEGACY` 会让下一个人去删它。

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

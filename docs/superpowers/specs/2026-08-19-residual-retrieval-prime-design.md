# Residual 检索下限：授权地板 + 窄槽位（prime_*）

- 日期：2026-08-19
- 工作树：`/Users/a77/fwp-wt-residual-prime`（`feat/residual-retrieval-prime`，基线 `gitea/main`）
- 状态：设计锁定，执行中
- 前置阅读：Knevo 蒸馏 `docs/learning/knevo-distill/q10-检索硬触发规则.md`；`prior_recall` 收窄先例（`episode_factory._required_output_evidence_types`）

## 0. 一句话

残差题（`question_type=general_finance_qa` 且**已经**需要检索）必须在授权里同时有行情、新闻、用户先验，并用**窄 `evidence_types` 的独立契约槽**逼模型消费，而不是再写一段 episode 指令。

**这是地板，不是变聪明。** 不改 query rewrite、不装配异动四分类、不默认打开 `ASK_LONGTAIL_BASELINE`、不动 8792。

## 1. 问题

生产 ask 已是 `continuous_episode`：LLM 自己选工具。残差路径不是「没命中就让模型编」，路由只编译约束（题型、能力白名单、契约槽、D 块意图）。

现状缺口是 **Knevo 形的检索下限没接到残差 policy**：

| 层 | 现在 | 后果 |
|---|---|---|
| 运行时地板 `_RUNTIME_CAPABILITY_FLOOR["general_finance_evidence"]` | `("kb_search", "web_search")` | 残差题可以合法地不调行情、不调新闻、不调用户台账 |
| 控制器地板 `_enforce_task_frame_route` 同 policy | `("memory", "web_search")` | 控制器词表里也没有 `market_quote` / `market_news` |
| 契约槽 | 残差默认只有 `direct_answer` + `evidence_boundary` | 模型从契约读不出「哪一格只能由行情/新闻/先验填」；`prior_recall` 已证明：全量 `evidence_types` + 「必须优先调用」提示词，模型仍把预算砸给市场侧 |

实测形态（残差 15 题窗口）：检索经常发生，判断写进草稿，`grounding_mode=evidence` 的 judge 把判断句剥掉，留下空壳/边界句。这是**取到了但不消费**，不是「没检索」。

Knevo 残差仍是金融模式：不派子 skill ≠ 不检索；记忆 + 行情 + 新闻并行；拿不准默认检索。要学的是这条地板，不是整抄 Knevo，也不是把阈值写进 longtail skill。

## 2. 直接回答三个分层问题

**是路由 miss 吗？** 多数残差题 routing 已判 `needs_retrieval=True`（关键词或超出通用默认的 `required_outputs`）。再加一层「命中/未命中」开关解决不了消费。

**是提示词不够吗？** 否。`prior_recall` 先例：提示词、授权、槽位三样都在，但槽位的 `evidence_types` 是全量能力列表时，模型仍不调对的工具。本仓原则：**不教 episode prompt**（指纹锁定：动输入不动指令）。

**是要把笑话拖进研究车道吗？** 否。`("direct_answer", "evidence_boundary")` 不是检索信号（`test_generic_defaults_are_not_a_research_signal`）。本改动**禁止**把 `prime_*` 写进 `_default_required_outputs` / `_GENERIC_REQUIRED_OUTPUTS`。

## 3. 已有地基（禁止重造）

1. **`task_frame_requires_retrieval`**：`general_finance_evidence` 下先看「超出通用默认的产出」，再退回 `_is_financial_task` 关键词。笑话 / 「今天天气如何」保持 False。
2. **`runtime_capabilities_for_frame`**：policy 地板 ∪ evidence plan。未要求检索且 plan 无 requirement 时返回 `()`——笑话保持空授权。
3. **`_with_prior_recall`**：能力定稿后再注入槽位；`memory_lookup` 不在授权里就不注入；`required=False` + `user_premise`，避免空台账把全站打成 `partial`。
4. **窄 `evidence_types`**：`prior_recall` 只留 `("memory_lookup",)`。本 spec 对行情/新闻做同样的事，但用**新 id**，不复用 `current_baseline` / `prior_recall`。

## 4. 考虑过、否决的做法

| 做法 | 否决原因 |
|---|---|
| 把 `prime_*` 写进 `_default_required_outputs` | 超出 `{direct_answer, evidence_boundary}` 会被当成研究信号，笑话进检索 |
| 复用 `current_baseline` / `prior_recall` | 命中路径（forecast / 题材）语义会被残差地板污染；`prior_recall` 仍只服务「用户点名自己的旧判断」 |
| 在 `build_episode_instructions` 加「必须先调三件套」 | 指纹锁定；且已被 `prior_recall` 证伪 |
| 默认打开 `ASK_LONGTAIL_BASELINE` | 只改写作骨架；live A/B 里 evidence_bound 变差；不增加工具或槽位 |
| 异动四分类 / 五维排序 / D6–D12 自动装配 | 消费配方，不是地板；阈值被 longtail skill 禁止 |
| Query rewrite ≤3、标的 once-get-all | Knevo 另一轴；本轮不做 |
| 预执行工具 | 破坏 agentic 选工具；本仓 episode 不预跑 |
| 改 hit-path 菜单（forecast / cause / valuation） | 回归面大；`test_market_forecast_runtime_uses_current_structure_without_causal_web_tools` 锁 `("market_data", "mainline_context")` |

## 5. 方案

### 5.1 触发（AND）

在 `build_episode_context` 里，**能力元组定稿之后**（与 `_with_prior_recall` 同一纪律）：

- `frame.question_type == "general_finance_qa"`
- 且 `task_frame_requires_retrieval(frame)` 已为 True
- 且对应工具已在 `capability_tuple` 里（evidence-free 会清空授权，自然不注入）

**不要**用 TurnController 现场分类「周一机会在哪」来当测试键——#72 之后这类句子可能被吸收进 `market_forecast`。测试必须**显式构造** `TaskFrame(question_type="general_finance_qa", ...)`。

### 5.2 授权地板

`intelligence/services/evidence_capabilities.py`：

```python
"general_finance_evidence": (
    "market_data",
    "news_search",
    "memory_lookup",
    "kb_search",
    "web_search",
),
```

保留 kb+web；把 Knevo 三件套接到同一条 policy。`runtime_capabilities_for_frame` 的早期返回不变：不需要检索且 plan 空 → `()`。

**预算取舍（必须写进代码注释）**：`memory_lookup` 原先故意不进大多数 policy，因为占工具槽，4–6 次调用就会 `budget_exhausted`。残差地板**接受**这次拥挤——这是相对 Knevo 并行三路的产品选择，不是疏忽。

`turn_controller._enforce_task_frame_route` 控制器词表对齐（不映射 `memory_lookup`，控制器没有这个名字；`memory` 仍映射到 `kb_search`）：

```python
"general_finance_evidence": ("memory", "market_quote", "market_news", "web_search"),
```

生产 `TurnControlCore` 优先用 `runtime_capabilities_for_frame`；控制器地板是 LLM 软路由剥证据时的备份。

Hit-path 地板一律不动。

### 5.3 新槽位（不要复用旧 id）

| id | grounding | required | evidence_types | 为什么 |
|---|---|---|---|---|
| `prime_quote` | evidence | True | `("market_data",)`（仅当已授权） | 行情下限；空 → gap / partial |
| `prime_news` | evidence | True | `("news_search",)` | 新闻下限；空须披露未取得 |
| `prime_memory` | user_premise | **False** | `("memory_lookup",)` | 与 `prior_recall` 同：空台账不得把每道残差打成 `partial` |

`_OUTPUT_DESCRIPTIONS` 必须有这三键，否则 `_require_output_description` 会在构造契约时失败。

`required=` 判定改为：`output_id not in {"prior_recall", "prime_memory"}`。

各槽独立注入：授权里没有 `news_search` 就不要挂 `prime_news`（避免「有格子没工具」）。

### 5.4 可满足性（fail-open）

`_DEFAULT_TOOL_METADATA` 的 `produces`：

- `market_data` += `prime_quote`
- `news_search` += `prime_news`
- `memory_lookup` += `prime_memory`（原先有意空集，因为旧词表全是市场事实；现在有先验专用槽，必须改声明，并改掉 `test_memory_lookup_declares_nothing_by_design`）

### 5.5 指纹

**禁止**给 `build_episode_instructions` 加新段落。槽位描述经 `build_episode_input` 进用户 JSON。

## 6. 验收故事

1. 金融残差 frame（例：「你觉得a股明天会怎么走」或「超纯应材估值怎么看」，`question_type` **显式** `general_finance_qa`，policy `general_finance_evidence`，产出仅为通用默认）→ `runtime_capabilities_for_frame` 含 `market_data`、`news_search`、`memory_lookup`、`kb_search`、`web_search`。
2. 「今天天气如何」/「给我讲个笑话」+ 仅通用默认 → `task_frame_requires_retrieval` False，能力 `()`，无 `prime_*`。
3. `build_episode_context` 对故事 1：契约含三个 prime；quote/news 的 `evidence_types` 为单元素；`prime_memory.required is False` 且 `user_premise`。
4. `market_forecast`「昨天的反弹能持续多久」能力仍是 `("market_data", "mainline_context")`，无 prime 槽。
5. `test_generic_defaults_are_not_a_research_signal` 仍绿。

## 7. 测试缝（只测这些）

公开缝：`runtime_capabilities_for_frame(TaskFrame(...))` 与 `build_episode_context(...)`。

新文件：`intelligence/tests/test_residual_retrieval_prime.py`。

连带：`test_episode_factory.RUNTIME_CAPABILITIES` 目前漏了 `memory_lookup`；残差授权进入该集合后，命中路径的 `issubset` 仍应成立，但任何仍落残差的题会需要把 `memory_lookup` 补进该集合（它本来就是 `DEFAULT_RESEARCH_CAPABILITIES` 成员）。

## 8. 范围外

Query rewrite；标的一次取全；异动四分类 / 五维排序；longtail 默认开；episode 上自动装配 D 块；预执行工具；改 hit-path 菜单；切 8792；把 `prime_*` 写进 task_frame 默认产出。

## 9. 残留风险

- **更多 `partial`**：`prime_quote` / `prime_news` 为 required。工具失败或模型仍不调，完成态会从「空壳 completed」变成诚实的 partial。这是地板的本意。
- **预算拥挤**：残差轮次更容易 `budget_exhausted`。先观察，本轮不扩 `max_steps`。
- **safe fallback 仍可落到 chat**：`needs_retrieval=False` 的 controller 挂掉路径不在本轮。

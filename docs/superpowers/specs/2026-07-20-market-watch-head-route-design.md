# Market Watch 头部路由契约设计

## 问题

“今天有什么值得关注的？请给出主线、观察清单、验证信号和风险。”已被
`is_market_watch_query()` 确定性识别为当日盘面问题，但 `QueryResolver`
同时把输出要求中的“信号”命中为知识库题材别名“信号系统”。

当前 `decide_turn()` 先从未规范化的 `QueryEnvelope` 构造 `TurnIntent`，
随后虽然确定性分支把 lane 设为 `workflow`，`_attach_turn_intent()` 又用
错误的 `TurnIntent` 覆盖 `question_type`、`subject` 和 `answer_owner`。
最终控制面同时得到 `daily-review` 和 `theme-research`，形成重复工作流。

## 目标

- 一旦命中确定性的 `market_watch` 头部意图，整份控制契约都必须固定：
  `question_type=market_watch`、`subject=None`、`answer_owner=None`。
- 保留用户要求的时间范围、研究算子和输出项，不丢展示需求。
- 路由事实继续来自 `route_table.py`，避免新增一套 question type 常量。
- 不放宽证据门槛，不改变题材、个股、新闻等长尾研究路径。

## 方案比较

### A. 在 Controller 入口规范化头部意图（采用）

在 `QueryResolver` 返回后、`build_turn_intent()` 之前，把已确定命中的
`market_watch` envelope 规范化为路由表中的 canonical row。

优点：控制契约从源头一致；后续 `TurnIntent`、`ResearchPlan`、skill owner
和 trace 都不会携带伪题材。缺点：需要明确规定头部意图优先级。

### B. 只在 `_attach_turn_intent()` 清空错误 owner

改动更小，但会留下错误的 subject/question type，trace、预算和后续追问仍
可能被污染，属于症状修复。

### C. 只缩窄知识库主题别名匹配

能消除当前“信号”误命中，但无法保证未来其他别名不从输出要求泄漏到控制
面，也没有落实“头部硬路由”的架构契约。

## 详细契约

新增 Controller 内部规范化函数：

1. 只对 `is_market_watch_query(query)` 为真的请求生效。
2. 从 `route_by_id("market_watch")` 读取 canonical `question_type`。
3. 生成新的 `QueryResolution`：
   - `question_type="market_watch"`
   - `subject_kind="market_pattern"`
   - `subject=None`
   - `matched_by="market_anchor"`
   - `research_mode="general"`
   - 保留 timeframe、time_horizon、operators、required_outputs
4. 再用规范化后的 envelope 构造 `TurnIntent`。

同时收紧 market-watch 规则的首段表达：允许“今天/A股/市场/盘面/行情/大盘”
等全市场修饰，不把“今天光模块有什么值得关注”误判为全市场观察。

## 验收

- 扩展问法的 Controller 结果只能是 `market_watch`，无 subject、无 owner。
- “今天光模块有什么值得关注”不命中全市场 watch 规则。
- skill router 对扩展问法只选择 `daily-review`，即使 LLM 尝试选择其他能力。
- 相关测试、全量 hermetic 测试、生产端到端均通过。

# Agent Capability Monotonicity Design

## 目标

Workbench 加入工具、RAG 和事实门禁后，长尾问题的任务理解、推理和自然表达不得低于同模型的极简回答；系统只降低无证据确定性，不降低可解释推理能力。精确取数与高风险头部任务继续走确定性路径，长尾研究走可审计但不模板化的统一研究状态。

## 当前失败模式

真实运行 `run_20260720_150431_879175` 已证明：内部 DecisionBrief 能正确区分“怎么跌”和“为什么跌”，但检索消耗大部分截止时间，Grounded Composer 超时后，系统把较好的内部判断丢弃，退回 `generic_theme` 候选来源模板。当前故障由四类机制共同造成：

1. Agent 只保存工具步骤和截断观察，没有持续保存候选假设、支持、反证和未决缺口。
2. 完成门以工具存在、`sufficient` 和 evidence 数量代替任务充分性，原因题可在外部原因未知时标 `completed`。
3. 自然语言出口并存 Grounded Composer、旧 marker composer、结构化 generic renderer；主链失败后会落入更差、更模板化的 fallback。
4. 质量清单、编排计划、固定标题、逐行 marker 和工程词退稿同时占据 request 与 verifier 两层，重复约束表达。

## 方案选择

### 方案 A：只删 Prompt

优点是改动小。缺点是没有修复 Agent 状态丢失、错误完成状态和 fallback 退化，无法解释“内部已有好答案但最终变差”。不采用。

### 方案 B：渐进式单一 ResearchState（采用）

保留现有 `TurnIntent`、`ResearchTaskContract` 和 `AnswerSpec` 作为边界对象，新增一个 turn 内权威 `ResearchState`，由 generic Agent、completion evaluator 和 Grounded Presenter 共同消费。旧对象只投影到/从状态读取，不再独立重建结论。自然语言统一为 Grounded Composer；失败时渲染已验证 DecisionBrief，不启动旧 marker LLM 链。

优点是直接修复认知接缝，同时兼容现有确定性 owner 和审计产物；可以小步迁移和回归。缺点是短期仍保留部分旧类型作为兼容视图。

### 方案 C：重写整个 Orchestrator 为图执行引擎

长期边界最干净，但会同时改动路由、工具、持久化、SSE 和 UI，回归面过大，且不能更快验证能力单调性。不采用。

## 架构

```text
TurnIntent / ResearchTaskContract
              │
              ▼
       ResearchState（权威）
       ├─ task：问题、主体、时间窗、要求输出
       ├─ hypotheses：候选解释、状态、置信边界
       ├─ evidence：来源、时点、硬度、支持/反驳关系
       ├─ gaps：缺失变量、影响的输出、建议工具
       ├─ completion：事实充分性、因果充分性、任务覆盖
       └─ budget：剩余检索/合成预算
              │
      ┌───────┴────────┐
      ▼                ▼
  白名单工具循环      确定性 Owner
      │                │
      └───────┬────────┘
              ▼
       DecisionBrief（已验证）
              │
       Grounded Composer
              │
       factual/causal verifier
              │
       一次定向 repair
              │
      成功：保留模型措辞
      失败：DecisionBriefRenderer 短答
```

## ResearchState

`ResearchState` 是 turn 内可序列化对象，至少包含：

- `question`、`subject`、`question_type`、`timeframe`、`required_outputs`；
- `hypotheses`：`hypothesis_id`、`statement`、`kind`、`status`、支持/反驳 evidence ID；
- `evidence`：标准化 evidence ID、工具、标题、详情、来源、来源日期、硬度、freshness、独立来源键、支持/反驳假设；
- `gaps`：缺失内容、阻塞的 required output、建议 capability；
- `completion`：`factual_grounding`、`causal_adequacy`、`task_coverage` 三个独立状态；
- `assessment`、`stop_reason` 和阶段预算快照。

Agent 每一步收到的是 ResearchState 摘要，不再只收到 900 字步骤 transcript。工具结果先进入状态，再由 Agent 更新假设或 gap。空结果只有在没有改变任何假设/gap 时才算无信息增益。

## 完成语义

完成门不得只看 evidence 数量或工具名：

- `factual_grounding`：事实是否有当前、合法证据；
- `causal_adequacy`：因果题是否同时覆盖现象、机制和外部触发，不能用“怎么跌”冒充“为什么跌”；
- `task_coverage`：required output 是否由明确 assessment 或明确 gap 覆盖。

只有所有必需维度为 `fulfilled` 才标 `completed`。若事实足够但外部因果不足，状态为 `partial`，用户答案可以明确给出“已知机制 + 未知触发”，但运行不得伪装完全完成。

## 输出与降级

所有需要自然语言综合的题型统一走 Grounded Composer；精确行情、技术指标和证据缺口短答可继续确定性渲染。

主路径：

1. ResearchState 投影为精简 DecisionBrief 和 evidence registry；
2. Composer 自由选择 1–5 个适合问题的小节，不要求固定行数、固定标题或逐行复制 registry；
3. 代码门检查 claim/evidence ID、数字、日期和主体；语义 judge 检查证据蕴含和因果跳跃；
4. 失败只做一次针对具体 issue 的修订。

降级路径：

- Composer 超时、provider 不可用或 judge 不可用时，直接使用 `DecisionBriefRenderer`；
- renderer 输出“直接判断 + 最强支持 + 最大缺口”，不显示候选状态、工具、RAG、DuckDB、证据计数或“通过语义闸门”等控制面语言；
- 旧 marker composer 不再作为用户可见 fallback，只保留 shadow/回归开关。

## Prompt 与展示约束

- `quality_context` 和 plan block 按 `question_type × research_tier` 选择最多三个相关块；完整清单只用于离线 lint/eval。
- `_ENGINEERING_TERMS` 只拦金融研究正文中的意外控制面泄漏；方法论/回答质检问题允许必要技术词。
- 标题采用建议列表，不因自定义标题整行退稿；标题中的无证据事实仍由事实门检查。
- Base Finance 五元素是可选配方：金融研究默认至少“直接判断 + 证据或 gap”，方法论/回答质检不强制风险和下一步验证。
- exemplar 按问题类型和相似度确定性选择；测试固定 seed，不以随机样板制造表面多样性。

## 检索与预算

- L3 不按所有 deep/valuation 题默认全开；当 ResearchState 的关键假设依赖客户、订单、认证、量产等硬事实且当前证据不足时，按 gap 激活 `l3_lookup`。
- evidence window 使用 token 总预算，排序为“问题相关性 × 证据硬度 × 时间对齐 × 来源独立性”，并为关键假设/反证保留最小覆盖；禁止按固定 provider 顺序简单截断。
- 标准档在进入最终合成前至少保留一次 DecisionBrief + Composer 的预算；检索达到收益递减或外部 provider 连续失败时提前停止。
- 每个 run 记录实际 runtime commit、ResearchState 摘要、completion 三维状态、合成阶段预算和采用的 fallback。

## 评测与验收

### 确定性回归

- 头部 `market_technical` 保持零 LLM、精确数据成功即停、失败报明确数据缺口；
- 无证据事实、过期证据、非法数字、错误交易日继续 fail closed；
- 工具保持只读，写路径仍需人工授权。

### 能力单调性

用同 provider、同模型、同问题做配对盲评：极简 Finance OS 基线 vs Workbench。至少覆盖：

- 本周下跌原因；
- 开放方法论题；
- 个股/题材长尾；
- 关系题；
- 缺 L3 的客户坐实题；
- Composer 超时/不可用。

指标包括：首段直接性、任务覆盖、事实绑定、因果充分性、结构适配、控制面泄漏、模板相似度和 fallback 保真。Workbench 不得在事实安全相同或更好的前提下，配对质量显著低于基线。

### 真实 E2E

- 真实 8792 隔离 runtime 运行原问题；
- 不出现 Daily Review 错路由、`generic_theme` 产业链 schema、候选来源模板、空引用 marker；
- Grounded 成功时 `llm.used=true`；Grounded 失败时仍交付 DecisionBrief 短答；
- 因果证据不足时 run 为 `partial` 而非 `completed`；
- 主回答不显示工程词、内部路径、工具状态和证据计数。

## 迁移与回滚

实现位于独立分支 `fix/agent-architecture-p13`，基于当前 8792 runtime `a0b8e8c1`。每个阶段独立提交。先跑测试和隔离端口 E2E，再创建 clean detached runtime；未经用户确认不合并 `main`。原 8792 runtime 保留，可原子切回旧软链。

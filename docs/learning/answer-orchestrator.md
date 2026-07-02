# 问答编排层 P0

## 目标

问答不能一上来就生成答案。金融问题需要先被解析成结构化任务，再决定证据来源、分析视角和质检门槛。

P0 的目标不是替代现有 `ask` 检索骨架，而是在 `ask --compose` 前新增 `QuestionPlan`：

- 识别问题类型：个股深挖、题材分析、行情前瞻、新闻/公告冲击、回答质检、方法论讨论、通用问答。
- 判断回答深度：quick / standard / deep。
- 给出必须动用的分析视角、优先证据来源、输出前质检门槛和缺数据策略。
- 把计划注入 LLM compose prompt，要求回答先遵守计划再组织语言。

## 为什么不是纯 Skill

Skill 适合封装高频复杂任务，比如“深挖个股”或“质检 Claude 输出”。但用户的真实对话不会每次都精准触发 skill。

问答编排层更像默认操作系统：任何金融问题进入生成器前，都先被规划一次。这样用户不需要每次提醒“看大盘、板块、生命周期、二阶导”，系统也能默认检查这些视角。

## 技术选型

当前采用“规则编排 + LLM 生成”的混合方案。

| 方案 | 优点 | 缺点 | 当前取舍 |
|---|---|---|---|
| 纯规则路由 | 稳定、可测试、便宜 | 灵活性弱 | 适合作为 P0 骨架 |
| 纯 LLM planner | 灵活，能理解复杂表达 | 成本高，可能拍脑袋 | 暂不作为默认入口 |
| 规则 + LLM 混合 | 关键路径稳定，复杂表达仍交给 LLM 展开 | 工程稍复杂 | 当前采用 |

可迁移知识点：这类编排层适用于所有垂直 agent。先把自然语言请求变成结构化计划，再执行检索、生成、质检和沉淀，比只靠 prompt 更稳定。

## P0 数据流

```text
用户问题
 -> plan_answer_question()
 -> QuestionPlan(question_type/depth/lenses/retrieval_plan/quality_gates)
 -> ask 现有 S/G/R/W/D1/D2/D3 检索骨架
 -> 可选 L3 evidence tools：公告/问询函/互动易运行时补查
 -> compose prompt 注入 QuestionPlan + 证据链 + 质量上下文 + 经验卡
 -> 二次反驳/重写
 -> 最终回答
```

## 行情前瞻的特殊编排

`market_forecast` 不能只做盘面外推。次日行情研判必须先做四源合议：

- 复盘前置查漏门：先读取 daily-agent 的 `research_queue`，检查旧逻辑唤醒、新逻辑候选、IMA/DeepDive 缺口和 L3 官方验证缺口；若存在“今日该做 IMA”或“今日该找公告/调研/订单”，先输出查漏清单，等用户补 DeepDive 并 ingest 后再生成正式复盘。
- 全量盘面复盘：市场阶段、量价、涨家数 MA5、涨跌停、申万一级容量、双红、新高和涨停热度。
- 晚间卖方/机构胜率：判断信息权重、覆盖密度、证据硬度和共识兑现风险。
- 外盘双源：先读取 fupanhui `/reviews/global-market` 结构化接口作为可对齐底座，并记录 `source_trade_date`；如果它只返回上一完整外盘日，而问题需要真正隔夜美股收盘，则用 web/finance search 补最新纳指、费半/SOXX、QQQ、AI 硬件链、海外核心股和中概/港股映射。
- 晨汇/早间材料：抽取新增事件、产业变量和盘中待验证方向。

策略一二三四在这里不是静态股票池，而是市场状态语言：分歧时比较策略三的主流题材强势股回流和策略二的流动性切换；上涨时先区分结构性上涨与普涨，再分别映射策略一的主线流动性池和策略四的强趋势/强者恒强；高位拥挤时重点检查核心新高、涨停扩散和共识兑现。

行情前瞻还必须给出策略选择结果，而不是只列验证清单。回答要读取或模拟 daily-agent 的策略一二三四候选，并说明：

- 当前市场阶段更适合哪个策略或策略组合。
- 对应的板块/题材/个股候选是谁。
- 为什么这些候选比其他方向更优，包括市场阶段、题材生命周期、相对强度、成交承接、外生信息和反证。
- 次日如何验证策略是否命中，例如核心股收盘位置、涨停扩散、新高数量、成交边际和是否被替代队列抢走资金。

如果没有读取到 daily-agent 候选池，也可以基于策略底层方法论手工推演，但必须明说“未读取候选池”，不能伪装成真实策略输出。

行情前瞻要复用个股深挖里的盘面视角，尤其是全量复盘硬字段：容量前三申万一级、双红题材、单红/缩量上涨题材、涨停热度、新高集群、行业发动机、开根加权强度和相对强度。双红是强约束，不是装饰词；如果一个方向涨幅很强但 `diff_ratio` 为负，回答必须把它判成“缩量强修复/存量抱团”，而不是低位放量新启动。真正双红、涨停强、新高强、容量强四类信号要分开说。

## 已落地文件

- `intelligence/services/answer_orchestrator.py`
- `intelligence/services/forecast_preflight.py`
- `intelligence/services/l3_evidence.py`
- `intelligence/tests/test_answer_orchestrator.py`
- `intelligence/tests/test_forecast_preflight.py`
- `intelligence/tests/test_l3_evidence.py`
- `intelligence/services/ask.py`
- `intelligence/workflows/ask.py`

`AskResult.question_plan` 保存本轮计划；`WorkflowSummary` 新增 `answer-orchestrator` step，输出问题类型、深度、置信度、视角数量和证据源数量。

`AskOptions.use_l3_lookup` 默认关闭。打开后，系统会在本地 DuckDB/wiki/RAG/evidence_index 之后检测 L3 硬证据缺口；若问题缺客户、订单、量产、产能、公告、问询函等官方证据，就按 `FINANCE_L3_CNINFO_CMD` / `FINANCE_L3_SSE_EINTERACT_CMD` 命令模板调用外接 CLI。工具失败或未配置时只输出 warning，回答必须降权但不能编造。

## 后续 P1

- 让 `QuestionPlan` 反向控制检索参数，例如个股深挖自动提高 wiki RAG k 值，行情前瞻自动加载最新 market context。
- 为每类问题绑定独立 quality gate 得分，输出前低于阈值时自动二次重写。
- 把“盘前假设 -> 盘后验证 -> 经验卡沉淀”接入 `market_forecast` 类型。
- 允许 LLM planner 只在规则置信度低时介入，避免常规问题增加成本。

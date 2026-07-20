# Unified Research Agent 长尾验收（2026-07-21）

## 验收范围

- 分支：`fix/agent-architecture-p13`
- 最新提交：`b793b2df3e9e5bbd42f544b42ea9cf89615bf641`
- 隔离运行时：`http://127.0.0.1:8794`，detached runtime 同一提交
- 主运行时 `8792`：未切换、未修改；canonical 软链仍指向原 runtime
- 环境：真实本地知识库、DuckDB、RAG worker 与配置的 GLM provider

## 自动化结果

```text
1899 passed in 88.23s
宽套件：337 passed in 70.64s
```

重点回归覆盖：

- ownerless research 默认交给 `GenericResearchOwner`，不再被旧专项 skill 抢答；
- 预测题的双情景、失效条件、完成门禁和确定性 presenter；
- 关系算子契约、图谱预取、关系边缺口；
- 任务规划、Hypothesis/Evidence 绑定、预算与 trace；
- market technical、comparison、event forecast、显式 Daily 工作流与多轮追问；
- 真实 GenericResearchOwner 输出的模板隔离、partial/success 链和 provider parent/step。

## 真实端到端（8794）

三次请求均通过 Conversation API 创建会话、发送消息、等待 terminal run，再读取 report、trace 和 assistant message；均为 `completed`、`degrades=[]`，未调用 `daily-agent`/`daily-review`。

三次 run 的 SSE `/api/runs/{run_id}/events?after=0` 也全部返回 HTTP 200，并分别收到 31、38、35 个事件，终端 `run` 事件均为 `completed`，包含 `answer.snapshot`、`report.complete` 和 `message.complete`。

### T+1 市场预测

问题：`明天你觉得是反弹还是继续下跌，分别给出理由`

- run：`run_20260721_031359_704906`
- 耗时：18.2s；controller：`question_type=market_forecast`，route：`generic_owner_requested=true`
- 输出包含：当前基准判断、反弹触发条件、继续下跌触发条件、失效条件、2026-07-20 盘面证据和下一验证窗口。
- 独立方向预测证据缺失被明确写成“条件化情景、不编概率”；没有回退成日报或研究雷达。
- trace 有统一 run parent、`market_data` prefetch、query ledger、completion（`task_coverage=partial`）和 grounding/atom validation。

### 两跳关系长尾

问题：`浪潮信息的客户的竞争对手有哪些？`

- run：`run_20260721_031434_439096`
- 耗时：40.3s；controller：`question_type=stock_deep_dive`、`operators=[relation]`，route：`relation_guard_requested=true`
- 先执行 `graph_lookup → evidence_lookup → kb_search`；输出区分“浪潮信息的客户线索”和“客户侧竞争关系”，没有把共现资料拼成竞争对手名单。
- 关系二跳缺少可回查关系边时，明确报告关系网络缺口；没有用常识补造公司名单。
- trace 有 relation contract、三类 provider trace 的 parent/step、completion partial 和 grounded synthesis。

### 无现成 skill 的陌生题材/方法论

问题：`一个没有现成 skill 的陌生题材怎么判断？`

- run：`run_20260721_031531_340541`
- 耗时：60.4s；controller：`question_type=general_finance_qa`，没有选择任何 skill，直接进入 GenericResearchOwner。
- 输出给出通用题材雷达的判断路径（题材定义、产业链拆解、Top10 公司排序、证据桶校验）、用途边界、证据缺口和升级条件；没有出现 Daily Agent/研究雷达终端模板、工具名或内部控制面字段。
- 本地知识库检索到框架资料后，仍把结论保留在“待补证线索”层级；completion 将直接判断标记为缺口，未把框架资料伪装成具体题材事实。
- trace 有 owner parent/step、两次 `kb_search`、query ledger、completion partial、grounded synthesis 与 atom validation。

## 端到端验收结论

| 约束 | 证据 | 结论 |
|---|---|---|
| 头部/显式 workflow 不被长尾 owner 抢答 | controller/route trace；显式 Daily 与 comparison 回归 | 通过 |
| 长尾进入统一 Research Agent | 三个 run 均有 `generic_owner_requested=true` 或 GenericResearchOwner stage | 通过 |
| 真值、证据和缺口可审计 | completion、EvidenceAtom validation、query ledger、ProviderTrace parent/step | 通过 |
| 预算不重复计算 | 每个 run 都有 research budget、query ledger、LLM ledger | 通过 |
| 失败不编造 | T+1 独立证据缺口、关系二跳缺边、陌生题材待补证均显式保留 | 通过 |
| 展示面不泄漏控制面/旧模板 | 三个答案均无 Daily/研究雷达模板；关系题无虚构名单 | 通过 |

## 已知边界

统一 owner 解决的是“问题被正确接住、可以改写检索、证据可审计、缺口不伪造”，不是把缺失的外部事实变出来。若本地图谱、公告和公开来源没有关系边，正确结果仍是候选线索或缺口；这属于 fail-closed 可靠性边界，不是把问题伪装成已完成。

本批只验证隔离 8794；没有合并 `main`，也没有切换 canonical `/Users/a77/finance-workspace-runtime` 或 8792。生产切换仍需用户明确批准，并重新执行 `docs/workbench/canonical-8792-cutover.md` 的 readiness、snapshot、蓝绿切换和回滚门禁。

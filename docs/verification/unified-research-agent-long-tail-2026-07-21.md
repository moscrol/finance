# Unified Research Agent 长尾验收（2026-07-21）

## 验收范围

- 分支：`fix/agent-architecture-p13`
- 最新提交：`989a1fe3`
- 隔离运行时：`http://127.0.0.1:8794`
- 主运行时 `8792`：未切换、未修改
- 环境：真实本地知识库、DuckDB、RAG worker 与配置的 LLM provider

## 自动化结果

```text
1794 passed, 2 skipped, 3 subtests passed
```

重点回归覆盖：

- ownerless research 默认交给 `GenericResearchOwner`，不再被旧专项 skill 抢答；
- 预测题的双情景、失效条件、完成门禁和确定性 presenter；
- 关系算子契约、图谱预取、关系边缺口；
- 任务规划、Hypothesis/Evidence 绑定、预算与 trace；
- market technical、comparison、event forecast 头部识别。

## 真实端到端

### 预测长尾

问题：`明天你觉得是反弹还是继续下跌，分别给出理由`

- run：`run_20260721_010315_103144`
- controller：`question_type=market_forecast`
- `invoked_skill_ids=[]`，未调用 Daily Agent/研究雷达
- 输出同时包含：反弹触发条件、继续下跌触发条件、失效条件、截至日期与盘面证据
- 没有给出伪造概率；独立方向预测证据缺失被呈现为单条边界说明

### 关系长尾

问题：`浪潮信息的客户的竞争对手有哪些？`

- run：`run_20260721_010902_764119`
- `invoked_skill_ids=[]`；关系算子触发通用关系契约
- 先查图谱关系边，再查知识库/公开来源；没有把公司资料共现升级成客户竞争关系
- 输出给出可回查的客户线索，同时明确客户之间的竞争关系尚未形成可核验关系边

## 已知边界

通用 owner 解决的是“问题可被接住、检索可改写、证据可审计、缺口不伪造”，不是把缺失的外部事实变出来。若本地图谱、公告和公开来源都没有关系边，正确结果仍是候选线索 + 缺口，而不是凭常识列出公司名单。

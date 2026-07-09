---
type: knevo_corpus
id: q7
date: 2026-07-09
credits: 6
topic: finance-mode workflow 路由表原文 + 派单规则 + preset 权限分层
key_finding: 意图关键词→(preset, skill) 二元派单表；preset=工具权限分层（researcher/producer/reviewer）；"不派单≠不检索"的检索硬触发兜底；事件预测禁止轻量化
---

# Q7：finance-mode 路由表原文（Knevo 回贴，6 积分）

问题：finance-mode 的 workflow 路由表原文是什么，各下游 skill 的触发条件和派单规则分别是什么

## 路由表原文

| 用户意图（触发关键词） | preset | skill |
|---|---|---|
| 个股/公司深度、估值、竞争格局 | finance-researcher | finance-analyze-stock |
| 财报、业绩会、指引、预期差、margin、revenue | finance-researcher | finance-earnings-review |
| 行业/赛道/产业链一次性深度、市场空间、供需 | finance-producer | finance-industry-report |
| 周报、月报、近期变化、行业信号、持续跟踪 | finance-researcher | finance-industry-track |
| 事件、概率、情景、政策/财报预期、诉讼、选举、产品催化 | finance-researcher | finance-forecast-event |
| KOL、专家访谈、研报/社媒观点、画像、偏见、证据质量 | finance-reviewer | finance-kol-analyze |
| 横向联想、相邻行业、可比公司、历史类比、反方、遗漏变量 | finance-reviewer | finance-associate |
| 事实审查、来源核对、估值假设、报告质量复核 | finance-reviewer | finance-review-check |
| 以上都不沾的通用投研 | finance-researcher | （仅 finance-mode）|

## 派单规则原文
1. 无需用户勾选/load_workflow——识别意图后直接派单。
2. 固定语法：`spawn_sub_agent(preset=<preset>, mode="isolated", skill_ids=["finance-mode", "<skill>"], task=...)`
3. skill_ids 原样传递，子 agent 不会自动发现/加载 skill。
4. task 字段自包含：意图、标的/范围/时间窗、已收集来源摘要、输出格式、边界（"不允许实盘操作"）。
5. 主线程只做路由/澄清/汇总；子 agent 的 terminal emit 才是面向用户的完整结论。
6. **不派单 ≠ 不检索**：短问题/纯事实/快答可不派 sub-agent，但仍必须执行 finance-mode 的检索硬触发（记忆+行情+新闻），只以更短篇幅作答。
7. 多标的/多主题并行 → 拆多个子 agent 独立派单。
8. **事件预测禁止轻量化**：问概率/情景/兑现路径必须走完整 finance-forecast-event（情景树+证据+概率区间），数据不足要明确说明无法量化。

## preset 权限分层
| preset | 授予能力 | 适用 |
|---|---|---|
| finance-researcher | 完整检索+输出 | 深度研究类 |
| finance-producer | 检索+写文件 | 落盘报告 |
| finance-reviewer | 检索+审查 | 审视型任务 |

## 架构解读与本地对照
- 路由做两件事：①意图→skill（流程+输出骨架）②任务性质→preset（**工具权限最小化**，审查型任务拿不到写文件权限——least privilege 在 agent 派单里的应用）。
- 兜底不是裸 LLM：**检索硬触发（记忆+行情+新闻）是所有路径的下限**——正是我们"检索前置（prime）"的同构实现，验证了此前推断。
- "事件预测禁止轻量化"= 特定意图强制走重流程——防止 LLM 偷懒给拍脑袋概率（虽然它的概率数字本身仍无溯源，见台账记录4）。
- 与我们对照：我们 answer-orchestrator 的 QuestionPlan（问题类型/深度/lenses/质检门槛）扮演同一角色，但我们没有 preset 权限分层（所有路径同权限）。
- **回灌候选**：①给 answer-orchestrator 加"权限/副作用分级"（只读分析 vs 写库任务分开授权）；②"不派单≠不检索"的显式规则化（我们已有检索前置，但未写成 skill 路由文档的硬规则）；③意图关键词表作为路由测试用例。

## P1/P5 探针状态
路由机制已白盒化（关键词意图表+LLM 识别），P1 路由边界/P5 模板残留探针可降级为验证性抽测，不必再花预算系统跑。

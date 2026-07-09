---
type: knevo_corpus
id: q6
date: 2026-07-09
credits: 未回报
topic: Knevo 技能包全清单（9 个）
key_finding: 分层架构实锤——finance-mode 是唯一"已挂载"入口层（search_skills count=0），#2-#9 是其路由表引用的下游工作层，按意图派发给子 agent
---

# Q6：技能包全清单（Knevo 原文回贴）

问题：列出你当前挂载的全部技能包和一句话用途

## 架构情报（核心）
- `search_skills` 返回空（count=0）：工作区没有安装额外专项 skill——**用户看到的"近十个技能"其实都藏在 finance-mode 的 workflow 路由表里**，不是平铺挂载。
- 分层：入口层 finance-mode（身份/来源标注/检索纪律/provider 路由/子技能派单中枢）→ 工作层 #2-#9，由路由表按意图匹配并**派发给子 agent 执行**。
- 与我们对照：我们是平铺 skill + 触发词路由（skills.registry.json / SKILL.md frontmatter），它是"单入口+内部派单"。它的形态集中控制检索纪律和来源标注（写一处生效全局）；我们的形态每个 skill 自带规则（重复维护但独立演进）。
- 命名修正：前四轮台账里的 finance-lateral 实为 **finance-associate**，finance-event-forecast 实为 **finance-forecast-event**。

## 全清单（9 个）
| # | 技能 ID | 用途 | 蒸馏状态 |
|---|---------|------|---------|
| 1 | finance-mode | 入口/派单中枢/检索纪律 | 部分（q4 顺带读过全文，未单独入库）|
| 2 | finance-analyze-stock | 个股深度 | 已实战（台账记录1）|
| 3 | finance-earnings-review | 财报复盘 | 已实战（记录3）|
| 4 | finance-industry-report | 行业深度 | 已实战（记录5）|
| 5 | finance-industry-track | 行业连续跟踪（周报/月报式，上期基线为锚） | **全新，未测未 dump** |
| 6 | finance-forecast-event | 事件情景树推演 | 已实战（记录4）|
| 7 | finance-kol-analyze | KOL/观点审查 | 已 dump（q5）|
| 8 | finance-associate | 6 维横向联想 | 已实战（记录2）|
| 9 | finance-review-check | 事实审查+自动修订 | 已 dump（q4）|

## 剩余蒸馏缺口
1. **finance-mode 路由表本体**：派单规则（什么意图→哪个 skill→什么 provider）是整个系统的皇冠——问「finance-mode 的 workflow 路由表原文，各 skill 的触发条件是什么」。
2. **finance-industry-track**：唯一全新技能，"以上期基线为锚聚焦本期变化"与我们 daily-ops 晚间流程同构，dump 定义看它的基线快照机制。
3. 已实战 4 技能的定义 dump 视胜负手需要补（如 finance-associate 的历史类比靠什么工具）。

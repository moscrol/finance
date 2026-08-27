---
name: divergence-distill
metadata:
  pattern: workflow
description: 同题 A/B 对照（Workbench vs Fable/Knevo 等外部模型）trace diff 之后，把分叉蒸馏成分池资产并验证写回。触发词：蒸馏分叉、对照蒸馏、蒸 Fable、蒸 Knevo、trace diff 沉淀、diff 完沉淀。注意：定位「哪步先错」用 agent-run-triage；喂 KOL 原文进视角用 perspective-distill；本 skill 只消费已完成的同题对照。
---

# 分叉蒸馏（divergence-distill）

trace diff 的产出是易腐品：只有归因（哪步先分叉），不落池就随会话蒸发。本 skill 把一批分叉
路由进**生命周期各异的沉淀池**，每条规则由对应池的执行器强制——而不是堆进一份没人执行的 lessons。

## 1 冻结矿

同题两份：Workbench 的 trace + 答案正文，对照方的 trace + 答案正文。原文不可变，只引用不改写。

- trace 只回答「哪步先分叉」；**规则往往在答案正文里**（归一化 diff 故意丢正文）。两份都要在场。
- 按分叉族聚类后**按族蒸**，拿最干净的一题当例题；人的闸门注意力花在族上，不花在逐题上。

完成判据：每族有例题指针（文件路径 + 题号），矿文件只读。

## 2 给分叉分类（决定写哪；一个分叉可产多条）

先过**控制面前置检查**：工具跑通之前，方法归因免谈——工具没叫 / 检索没做 / 预算先死 /
verifier 误杀，先蒸第 1 行；控制面排除后剩下的差异才轮到方法行。（R-11 钙钛矿现场：表象是
「少引产业链证据」，实际是 evidence_plan 没引导 kb_search，修在控制面不在知识面。）

| 分叉长什么样 | 蒸出的是 | 写进 |
|---|---|---|
| 工具没叫、检索没做、预算先死、verifier 误杀 | 控制面约束 | harness/runtime：spec → 工作单 → TDD（R2 流程） |
| 同一张表读法不同（封板时间、双红、回流） | 判读方法 | reading_baseline（默认开、带 id、可 A/B）※ |
| 敢不敢下判断、不接飞刀 | 判断倾向 | 视角 / user_framework 差分（显式开关） |
| 这道题特有的写法错 | 快变量教训 | experience_cards（用户学习层） |
| 用户亲口「不对，应该是…」 | 纠偏 | `python3 -m intelligence.cli record-correction` |
| 方法对、本地没数据 | 已采纳但禁注入 | _PENDING_RULES，和缺口 id 放一起 |
| 多出来的是公司事实 | 不是蒸馏 | 知识库证据层（ingest 管线），画像/基线不收 |
| 对照方多出的细节核不动（单一纪要、无法外核） | 反例卡 | 批记录「反例」节（judge 侧消费口未建，先存矿） |

※ reading_baseline 截至 2026-08-22 在 `feat/reading-rules-baseline-batch1` 未合；合入前新增判读规则挂该分支，不另建第二份。

第 2/3 行（方法 vs 倾向）拿不准用两个判别式：

- **可证伪测试**：能写成「触发条件 + 可观测量 + 失效条件」→ 方法，进 baseline；同读数下只改变出手选择 → 倾向，进视角。
- **双用户测试**：换一个用户会想要不同值 → 视角；任何合格读盘者都该要 → baseline。

完成判据：每个分叉要么有池号，要么有一句「不蒸，因为…」。

## 3 抽规则，不抄答卷

每条候选写三件：**这意味着什么**（自己的话，不是对照方原话）、**失效条件**、
三个月后不靠这次对话也读得懂。数字阈值不进 baseline：结构可信、单点阈值没回测的，
写成回测任务进 evolution 风格队列（结构先行，阈值回测过了才升）。

## 4 人过闸再写

模型只产候选。候选批次落 `docs/learning/distill/<日期>-<对照名>.md`（台账已在
`docs/learning/ledger-map.md` 登记），逐条请用户裁决：采纳 / 改写 / 拒绝 / 降级为矿。
对照方多出的细节默认当矿，用户点头才算金标。

## 5 验写回，不只验写了

写回后逐条验「下次同构题真拿到这条」，按池给验法：

| 池 | 验法 |
|---|---|
| harness/runtime | 测试钉红绿变异 + 收据（V2 缺口取证流程原型） |
| reading_baseline | 注入断言：规则 id 出现在对应题形 system prompt；A/B 台账行；漂移门禁 |
| 视角 / user_framework | 显式开关下 A/B；开关关闭时零注入 |
| experience_cards / corrections | 下次同构题上下文抽样审计（回灌链路自动，但要抽查到场） |
| _PENDING_RULES | 缺口 id 闭合时有门禁捞出来，不是永久停尸房 |
| 知识库证据层 | ingest 自带 lint（`pdf_ingest_lint.py` 等） |

防的失败形状：**假写回**——文件在、运行时没注入（perspective-distill 的「API 可见性闸」同款；
授予的东西必须真的传到最下游，只落盘不注入比不写更危险）。

完成判据：批记录里每条采纳项都有「验法 + 当前状态」两列，pending 的写明等什么。

## 红线

- 原文矿只读；引用带路径。
- 公司事实走知识库证据层（evidence 分层红线同 AGENTS.md），画像/基线不收。
- 人未过闸不写回；写回不验注入不算完。

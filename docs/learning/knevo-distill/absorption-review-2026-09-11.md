---
title: Knevo q16-q18 新语料吸收复核
type: inbox
agent: codex
source: 本地 Knevo q16-q18 原始语料、回灌清单与 gitea/main 源码
date: 2026-09-11
tags: [inbox, finance-agent, knevo, research]
status: draft
---

# Knevo q16-q18 新语料吸收复核

> 归位说明（2026-09-16）：原件是 `~/agent-memory/00_inbox/2026-09-11-knevo-new-corpus-absorption-review.md`（codex 起草），
> 被 `absorption-plan-2026-09-11.md` 的「R4/R5 的收窄」一节引用。inbox 会被清空，故原样搬进本目录并撤下 inbox 副本；
> 正文未改一字，文内指向 `.claude/worktrees/knevo-e009/...` 与 `fwp-wt-mainref-0911` 的绝对路径是当时的工作树，可能已不存在。
>
> 研究建议，尚未实现或验证效果。本笔记不替代仓内回灌状态表，也不新增执行任务。用户已将上一轮能力包交给其他 agent 执行。

## 结论与证据范围

优先吸收两项：按判断增量筛材料、把产业证据变化与市场定价状态分开判断。第三项“参与者约束研究”适合小范围试验。q18 主要用来补验收样本。

本次对照的金融仓基线为 `gitea/main=dd1ad32b040ad04d25432d841efe9a96b51d3d60`。下列 q16-q18 本地原文与该基线无差异；代码链接指向已核对的本地工作树。源码存在、提示词要求与默认用户入口实际生效是不同证据，本次未重跑线上问答。

- **VERIFIED**：已读原始输出、现有回灌清单和相关源码；能确认它们写了什么、实现中已有何种结构。
- **UNVERIFIED**：Knevo 方法的稳定效果、案例中的金融事实、框架作者归属及收益优势。本轮语料不足以支持这些结论。
- q18 六题在同一会话连发，模型知道自己被测，部分题目还让它自选案例；原文已明确标注这个限制。[q18 证据警示](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q18-系统自检六题.md:13)

## 候选一：按“什么会改变判断”筛选材料

**原文启发**：主矛盾、短期扰动、下一裁判变量，以及减少重复信息。[q17 Q8](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q17-方法论七题.md:81)

**已有基础**：市场总览已有阶段、风险和验证点；排序输出已有主判断、竞争解释、改判条件、下一步。仅增加“三要素摘要”与现有结构重叠。[总览验证点](/Users/a77/fwp-wt-mainref-0911/intelligence/services/workbench_overview.py:732)、[排序表达契约](/Users/a77/fwp-wt-mainref-0911/intelligence/services/ranking_contract.py:129)

**建议增量**：在材料阅读与回答组合中，让保留的信息能够回答“它改变哪项判断，或帮助裁决哪个未解问题”。重复报道合并并保留出处；足以推翻主判断的反证优先呈现；无法证实但可能改变判断的消息转成待验证问题。把裁判变量接到已有下一步研究动作。

用户能看到的变化：材料再多，仍能看清现在争论什么、最有分量的新证据是什么、下一份什么材料会改变结论。

**建议验收**：同一材料包加入大量重复利好，主判断及待验证问题应保持稳定；加入一条有力反证，结论或下一研究动作必须变化，并指出依据。

**边界**：不硬编码只能有一个主矛盾；不按“非主线”直接丢信息，避免漏掉新线索和反证。归入现有 02/06/09/10 的组合行为实验，无须另建页面或摘要引擎。

## 候选二：把“逻辑变强”和“价格已反映”分开研究

**原文启发**：“主线再确认”与“接近过热”可以同时成立。催化新意、价格反应、资金、拥挤度、链条与龙头状态可以提供不同观察角度。[q17 Q4](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q17-方法论七题.md:18)

**已有基础与原清单修正**：

- `sellside-coverage-cross` 已交叉核查库内已知信息、覆盖密度、盘面背离和观点冲突；原回灌清单 R5 的“现只有覆盖密度单维”与实际 skill 不符。[现有四问](/Users/a77/knowledge-base-private/skills/sellside-coverage-cross/references/coverage-rubric.md:10)
- 已有拥挤度分位，以及事件前后收益、超额收益和价格反应形状。事件反应代码中的共识输入仍明确写作 `CONSENSUS_GAP = "not_wired"`，生成记录时保留空值。这是可定位的接入缺口，不能据此推断整条默认对话链已接通。[拥挤度](/Users/a77/fwp-wt-mainref-0911/intelligence/services/market_midterm.py:345)、[共识缺口定义](/Users/a77/fwp-wt-mainref-0911/intelligence/services/event_pricing/reaction.py:40)、[记录生成](/Users/a77/fwp-wt-mainref-0911/intelligence/services/event_pricing/reaction.py:423)

**建议增量**：复用现有读数和材料增量，分别回答：

1. 新公告、订单、产能或经营数据有没有强化原来的收入/利润兑现路径？
2. 对照事前预期、已发生的价格反应和拥挤度，市场反映了多少？哪些部分仍无法判断？

两项分别给证据、日期与未知项，允许“业务证据增强，但价格已较拥挤”同时成立。没有事前预期来源时，只报告价格状态，不能把上涨本身当成市场共识的证明。跨仓 skill 包含写入流程，未来接入应消费只读结果或接口。

**建议验收**：采用“新订单+高拥挤”“旧消息重提+低拥挤”等交叉样本；相同涨幅但不同信息增量，应产生不同解释。缺少资金主动性数据时写未知。历史问题只使用截至提问时已知的数据，事件后的收益仅能用于事后评价。

**边界**：不采用“六项满足四项”的投票阈值，多个价格/资金指标可能相关；不把融资余额、龙虎榜席位直接解释成某类投资者的意图。原文数字和交易动作未获验证。

## 候选三：把“谁能改变变量”变成检索步骤

**原文启发**：权限主体、激励结构、可能行动、后续传导，每一步说明来源。[q17 Q6](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q17-方法论七题.md:57)

**已有基础**：情景树已要求关键变量、可观察条件、互斥因果假说和监控信号，并明确禁止编造决策者心理。无需另做一套情景推演模块。[已有情景树契约](/Users/a77/fwp-wt-mainref-0911/intelligence/services/scenario_tree.py:175)

**建议增量**：在政策、招标、扩产、采购等问题的现有研究规划里，加入有针对性的子问题：谁有决定权？公开制度或经营约束是什么？他有哪几种可行行动？哪份公告、条款或后续行为能区分这些可能性？结果接到财务传导和下一验证动作。

**建议验收**：两份材料只改变决策权限或合同激励条款，下游研究问题应随之变化。没有公开依据时保持为假设，不能自动补全内部动机。

**优先级**：低于前两项，先选少量真实问题试验能否改变检索和结论，再决定是否固化为研究模板。

## q18 更适合炼成验收样本

以下是新增候选题组，不改写此前冻结基准，也不表示现有系统已在这些题上失败。

| 题组 | 具体变化 | 应观察什么 |
|---|---|---|
| 历史前提核实 | 确有原记录 / 检索未命中 / 存储不可用 | 有记录则核对原话、日期与归属；未命中或不可用则说明无法核实，不凭空认错，也不宣称事件未发生 |
| 半缺失数据 | 新价格搭配旧档案、同一字段间歇缺失 | 分清每项数据的时间和缺口，已有字段照用，缺失部分不由名称或裸价补全 |
| 框架适用与冲突 | 排序第一但触发方法失效条件；两个框架适用期不同；走势相似但经营机制不同 | 调整判断及下一研究动作，并说明使用哪条已证实的条件；不新增一个泛化“一票否决器” |

来源分别为 [q18 C3](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q18-系统自检六题.md:45)、[C2 未覆盖的半缺失场景](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q18-系统自检六题.md:42)、[C4-C6](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q18-系统自检六题.md:55)。可接入现有 00/07/09/10 的后续验收。

特别注意：C3 从“未检索到推荐记录”跳到“那件事没发生过”，后一步并不成立。C1 与 q17 Q10 的自述也不能外推为 Knevo 整个产品没有个人台账或画像。[q18 C1](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q18-系统自检六题.md:22)、[q17 Q10](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q17-方法论七题.md:105)

## 已有工作与不宜照搬的部分

- 按所查基线的回灌清单收口段，R1a/R1b/R2 已随 PR #718 合入，R3 随 #719 合入；拥挤度历史截止日问题已修。R4/R5 仍待做，R6 仓位框架已有纸面骨架。应在原清单上收窄 R4/R5 的定义，而非再次派发已有工作。[回灌清单](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/absorption-plan-2026-09-11.md)；状态以本次读取的 `git show dd1ad32b:docs/learning/knevo-distill/absorption-plan-2026-09-11.md` 为准，本地链接所在工作树可能较旧。
- E-009 的 W1-W6 已有实现或处置记录；交接仍注明部分实盘样本等待数据，不能写成全部验证完毕。[E-009 交接](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/handoffs/inflight/feat-knevo-delta-readside.md:21)
- q16 的仓位比例、止损线等即兴数字不直接吸收；“大票补涨必为尾声”“流动性恢复就能涨回来”等定性口诀同样需要独立验证。可提取为竞争解释和验证问题，不能把“没有数字”当作规则可靠的证据。[q16 原文](/Users/a77/finance-workspace-private/.claude/worktrees/knevo-e009/docs/learning/knevo-distill/q16-仓位管理框架.md)

建议推进顺序：先完成当前能力包接线与验收，再对候选一、二做同题对照实验；候选三小范围试用。评价依据应是选材、判断和后续研究动作是否实质改善，不能只看答案是否出现指定词语。

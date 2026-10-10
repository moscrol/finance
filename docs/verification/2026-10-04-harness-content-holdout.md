# Harness 内容质量留出集冻结记录

日期：2026-10-04  
题集：`intelligence/eval/fixtures/harness_quality_holdout_20261004.json`  
入口：Workbench conversation API  
状态：本页原记首次冻结时点；**2026-10-07 回查已确认曾被使用，不再声称“尚未运行”**。
冻结 fixture 和 receipt 保持原字节，不能据其中的历史 `holdout_frozen_not_run` 判定今天的资格。

## 2026-10-07 使用记录补记

私有证据根 `~/.finance-runtime/harness-quality-closeout-1003/` 中：

- `task6-arena-strong-proxy-20261004/completion-manifest.json` 记有 12 题 / 14 轮答卷；
  其 `external_model_calls=0`，且明确不声称底层 Arena 模型身份或 fully blind unseen holdout。
  不能把它写成 12 次已核实外部模型调用。
- `task6-arena-vs-glm-8792-20261004/CLOSED.json` 记有 4 次尝试，
  `status=closed_not_eligible_for_comparison`；该轮依用户要求取消，原文禁止补跑、评分
  或并入正式比较，strong-proxy 包也一并排除。4 次尝试不等于 4 次已确认模型回包。
- 两包 `input-only.json` 的源 fixture SHA-256 均为
  `32f4416057ca12df2459f0fd48bc3607fd2c1afe22eee2f46820860c7af405db`，
  与仓内冻结文件一致；逐题 turns 也全部相等。身份复核收据：
  `~/.finance-runtime/reviews/review-takeover-20261007/holdout-prior-use-identity.json`。

这些记录证明“已使用”，**不单独证明每题后来都被用于调参**，也不证明内容通过。
新一轮独立留出验收应另冻结新题与真值；旧题可保留作历史或回归材料，旧批不重开。
首次冻结和返修时的“零调用”叙述只对当时时点有效。

## 目的

这套题只回答一个问题：候选 harness 在没有看过答案、没有用题目调参的情况下，能否让不同能力档位的模型更可靠地处理事实边界、金融口径、传导链和用户约束。此前 `quality956` 的 news、transmission、financial-holdout 是修复线和历史失败证据；本套题不复用其题面、数字或答案。

## 覆盖与分工

| 类别 | 题号 | 数量 | 主要硬约束 |
|---|---|---:|---|
| 新闻事实边界 | HN-01–02 | 2 | 证据等级、时间与范围不越界 |
| 财务口径 | FN-01–02 | 2 | 增速、CFO/CapEx、FCFE 与现金预算分开 |
| 传导链 | TR-01–02 | 2 | 利润→现金→融资→估值的条件关系 |
| 方法设计 | MY-01–02 | 2 | 目标对齐、偏差、留出验证 |
| 改写 | RW-01–02 | 2 | 压缩时保留事实、限制与时间 |
| 多轮 | MT-01–02 | 2 | 版本更新、记忆边界、未命中不等于不存在 |

`turns[i]` 是第 i 轮唯一可发送的完整用户消息。十个单轮题的 `turns[0]` 已含虚构材料和问题；MT-01/MT-02 各发送两个 turns，必须沿同一 conversation 续问。`question` 和汇总 `materials` 只供审计，不在运行时另行拼接，避免把多轮后续材料提前泄漏。`gold_points`、`hard_errors`、评分规则和类别标签在执行器外保存。每个 case 的 turns、材料和真值均须在首次调用前计算 SHA-256。题目顺序、模型设置、资源预算和身份准入在 A/B 首次调用前另行预注册；运行失败计入分母，不补跑挑最好结果。

## 全文盲评量表

每题由两名独立评审先看匿名答案，再揭盲。任一评审发现 critical，题目最多为 `unusable`；发现 major 且仍有独立可用部分为 `partial`；只有必要子问均正确且无 major/critical 才为 `usable`。结构完成、引用数量、`run.status=completed` 和自动格式检查都不能覆盖事实错误。

评审逐题记录四类结果：

1. **事实与时间**：对象、日期、单位、材料边界是否准确。
2. **金融口径**：公式、现金流分类、估值口径和条件是否正确。
3. **推理与范围**：是否区分事实、竞争解释、未知与下一步验证，是否把局部证据扩成全局结论。
4. **用户约束**：字数、逐问覆盖、版本继承、记忆/联网边界是否遵守。

严重度固定为：`critical`（直接支撑错误的资金、价值或买卖结论）、`major`（核心公式、口径或必答项实质错误）、`minor`（不改变结论的局部表达）。关键错误要保留原文短引和题号，不能只报总分。

按事实和口径判分，不按术语字面匹配：FN-01 正确声明“按 CFO−CapEx 定义的常见 FCF”为 −4 可以接受；不可据此认定完整 FCFF、FCFE、全部现金变化或确定融资需求。MT-02 的“不写个人记忆”从运行副作用检查，不因答案未口头承诺就扣分。两名评审有分歧时保留两份原始判断、先匿名核对材料，仍无法解决的题标记有争议并单列；不能挑高分或事后删掉该题。

## 解冻与使用规则

- 冻结时 `tuning_case_ids` 为空；任何用于修复提示、路由、schema 或代码的题都应登记为调参/回归题，退出后续“未见留出”分母。保留冻结原件，使用历史另外记账，不靠修改原件重置资格。
- 旧失败题只能进入回归集，不能因为修复后通过就变成新留出题。
- 运行产物必须包含 conversation、run、assistant message、候选 SHA、部署/服务指纹和完整子调用索引；CLI 或离线 replay 只能作为链路证据。
- 新题结果只能证明本套题及其模型/资源设置下的表现，不能自动外推所有金融问题。

## 首次使用前的输入合同返修

独立 Spec 审查在 `161cbf89e179` 发现 P1：旧 boundary 写“只发送 question”，十个单轮 `turns[0]` 也只有问题，模型实际收不到材料。该版 manifest SHA-256 为 `dc2e5a859b9c2a93b80b03c4780c8bd4bf8083809e291687db6b7153375708b7`，原件保留在该提交。尚无模型使用这套题，也没有据其结果调参。

返修采用 `freeze_revision=2`：将完整单轮材料写进对应 turn，保留多轮各自已冻结的输入。只改运行输入合同，不改题目、材料、gold 或数值；禁止统一拼接汇总材料。新旧 manifest 哈希及接替原因见同目录 receipt 的 `supersedes`。这是漏料修复，不能作为回答质量改善。

- [x] 原输入运行材料完整性检查，复现十题遗漏：1 failed / 2 passed。
- [x] 修正完整逐轮文本，重算 turns 和 manifest 哈希；保留原 question/materials/gold 哈希。
- [x] 历史核对：FINANCEWORKS-4 评论记录 `eb927244c053` 完成返修及独立复审，PR #31 已合入；本轮另跑 fixture 检查，不能替签当时的全部工程验收。

离线原件：`~/.finance-runtime/harness-quality-closeout-1003/holdout-input-red.log`。运行题集前还需预注册对照配置与模型身份，本文件不授予正式 240 次启动条件。

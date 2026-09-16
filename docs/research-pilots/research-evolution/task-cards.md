# 等价任务卡与交叉顺序

两类任务，各出一对匹配案（A/B）。匹配的四个维度写进任务卡，盲审时也据此判「任务完成」：难度、来源规模、截止时点、交付物。参与者保留平常合法使用的工具，登记工具版本与熟悉程度；原流程可以有人工帮助，但要记 `manual_assistance`。

## 任务卡模板

```
case_id:            case-fc-A            # 与 protocol.cases 一致
case_version:       "1"                  # 改任何字段就升版本；旧分配仍按旧版本判
category:           fact_check | judgment_recheck
title:              一句话任务
question:           参与者拿到的原题（不含答案线索）
sources_allowed:    允许使用的资料范围（公告 / 数据表 / 本人旧判断 + 新证据清单）
source_scale:       资料规模（份数 / 行数），A/B 须相当
cutoff:             数据截止日（可知性边界，不得使用截止日之后的资料）
deliverable:        交付物形状（核对单 + 出处列表；变化单 + 维持/修订结论）
completion_condition: 什么算完成（例如：每个数字有出处；每条结论标「维持 / 修订 / 无法判断」）
deadline:           截止时点（写进 assignment_created.payload.deadline）
tools_baseline:     原流程允许的常用工具（登记版本）
difficulty_notes:   为什么 A/B 匹配（步骤数、需要交叉核对的项数）
```

## 两类任务的最低要求

| 类别 | 原题形状 | 完成条件 | 严重错误示例 |
|---|---|---|---|
| fact_check（事实 / 计算核对） | 给 2–3 份公告或数据表，核对若干数字与口径 | 每个数字有出处与页码 / 行号；口径差异写明 | 数字抄错、口径混用、把估算当实际 |
| judgment_recheck（旧判断变化 / 回检） | 给一条本人（或匿名化的）旧判断 + 截止日前的新证据清单 | 每条依据标「变了 / 没变 / 无法判断」；结论标维持 / 修订；写触发条件 | 用截止日之后的资料；把「没查到」写成「不存在」 |

## 交叉顺序表（事前预分配）

同一参与者在一对里各做一次原流程和辅助流程，两案不同；条件顺序在人之间交叉，避免「先做的都是原流程」。

| 参与者 | 第 1 周（fact_check） | 第 2 周（judgment_recheck） |
|---|---|---|
| p01 | A 原流程 → B 辅助 | A 辅助 → B 原流程 |
| p02 | A 辅助 → B 原流程 | A 原流程 → B 辅助 |
| p03 | B 原流程 → A 辅助 | B 辅助 → A 原流程 |
| … | 继续交叉 | |

每一格对应一条 `assignment_created`（`manual_import`），payload 带 `protocol_hash / assigned_at / condition / case_pair_id / completion_condition / deadline`；迟登的分配照实标注，不能补进事前配对。

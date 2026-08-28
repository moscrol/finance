# 工单：区间两端休市但中间含交易日仍整题罐头 —— R4 守卫残余

- 状态：**待认领**（2026-08-28 立单，用户拍板「值得治」；R-free，认领实施时按台账纪律预注册）
- 来源：#489 F1（R4 修复）验收 QC 标注 1——修复只豁免了「问句里明写的日期有交易日」的区间，
  比 R4 更宽的形状仍会整题罐头
- 前置：#489 已合入生产（8792@`b77df25c`），R4 本体已修
  （台账 `R-20260828-05` confirmed，问句日期含交易日的区间不再 canned）

## 问题

豁免判定 `question_has_retrievable_trading_day_range`
（`intelligence/services/trading_calendar.py:155`）只扫**问句里明写的日期**：

```python
dates = _dates_in_question(question)
if len(dates) < 2:
    return False
return any(non_trading_day_note(value) is None for value in dates)
```

docstring 自己写明了这条边界：「单日休市（C1/C2）和两端都休的区间返回 False，仍走罐头」。
消费点在 `lane_generation.deterministic_lane_answer`（main 现 :58）：
`if disclosure and not question_has_retrievable_trading_day_range(query): return 罐头`。

失败形状（比 R4 宽一档）：

| 问句 | 现行为 | 期望 |
|---|---|---|
| 2026-08-15 到 2026-08-23 市场怎么样（周六→周日，中间整周交易日） | 整题罐头「08-15 为周六休市」 | 进检索，休市句作假设前置 |
| 2026-10-01 到 2026-10-07 涨停家数（国庆连休，中间零交易日） | 罐头 | 罐头（正确，保持） |
| 2026-07-25 市场怎么样（单日周六，C1） | 罐头 | 罐头（红线，不动） |

代价与 R4 同族：区间内的峰值/总量问题被终点休市句吞掉整题。

## 修法（形状）

判定改为扫**区间内部**而不是只扫端点：`len(dates) >= 2` 时取 `[min(dates), max(dates)]`，
逐日用同一原语 `non_trading_day_note(value) is None` 找可交易日，命中即 True。

- 迭代上限设硬顶（如 62 天），触顶未定性时返回 True（长区间必含工作日，
  宁可进检索也不整题罐头——方向与 fail-closed 罐头相反，是刻意的：罐头吞题
  比多跑一次检索贵）。
- 未知年份工作日 `non_trading_day_note` 返回 None（无法证明休市）——按现语义
  算作可检索日，与单日路径的 fail-closed 方向保持一致，不另开口径。
- 只动 `trading_calendar.py` 判定函数本体，消费点与休市假设注入
  （`task_frame.question_non_trading_note`）零改动。

## 红线（既有行为不得回归）

1. C1/C2 单日休市题仍 0 LLM 罐头（`R-20260828-05` 的失败形状②）；
2. 纯休市区间（国庆连休、春节连休）仍罐头；
3. R4 本体（端点之一为交易日）行为不变；
4. 休市事实作为假设注入、检索后前置的路径不动（#489 F1 语义）。

## 验收判据

离线：新钉「两端休市夹交易日」区间先红后绿；上表三行 + 红线四条全有钉。
live（可选，切流后）：R4 变体「2026-08-15 到 2026-08-23 这段时间全市场哪天成交额最高」
trace 出现 `finance_query` 且答案给出区间内交易日读数、休市句前置不整题罐头。

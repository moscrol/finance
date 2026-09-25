---
name: high-volume-gainers
metadata:
  pattern: pipeline
description: 大成交涨幅排行（成交额×涨幅量价综合加权排序并入库）。触发词：大成交排行、大成交涨幅、加权涨幅、量价排行、放量上涨。注意：纯涨幅排行（不看成交额）用 top-gainers。
---

# A股大成交涨幅排行

## 触发条件

用户要求查看大成交涨幅排行、量价排行、加权涨幅排行时触发。即使用户只给了日期区间并强调"大成交"或"量价"，也应使用此技能。

查询指定日期区间前复权涨幅前100的A股个股，计算加权涨幅（日均成交额 × 涨跌幅 / 100），取加权涨幅最大的前20。附带核心题材和板块涨幅统计。

## 执行流程

执行流程 7 步（解析日期 → 并行发起 iFind 涨幅前100 + AKShare 板块 → 加权涨幅公式取前20 → 分批并行查核心题材 → 筛除通用噪声留 2–3 核心题材 → ASCII 个股表 → markdown 板块表）见 `references/execution-flow.md`，逐步执行。

## 写入飞书

```bash
echo '[JSON数组]' | python3 /Users/lbq/Desktop/c c/金融/skills/high-volume-gainers/scripts/write.py
```

JSON 每条：`{"date":"YY-MM-DD~YY-MM-DD","code":"688256.SH","name":"寒武纪","themes":"AI/芯片/国产操作系统","avg_vol":218.9,"gain":30.01,"weighted_gain":65.68}`

脚本按日期+股票代码查重，已存在则跳过。写入后自动回读验证，检查所有关键字段是否完整，有空字段会输出 ⚠ 警告。

## 注意事项

- 涨幅为前复权涨跌幅
- iFind API 返回 ok:false 时检查错误并重试
- 非交易日自动取最近交易日
- iFind 查询必须包含"日均成交额"关键词才会返回成交额列，用 `>1亿` 作为最低门槛触发返回
- 加权涨幅 = 日均成交额(亿) × 区间涨跌幅(%) / 100，综合衡量资金参与度与涨幅强度
- AKShare 行业用 `period="日k"`，概念板块用 `period="daily"`
- AKShare 概念板块必须用板块代码（如 BK0884）而非名称查询历史数据

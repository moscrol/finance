---
name: watchlist-ma
description: 自选股均线回踩筛选。触发词：自选股均线、自选股MA、均线筛选、自选股过滤、自选股回调、均线回踩、MA交叉、十日线二十日线。
---

## 触发条件

用户要求筛选自选股中均线回踩的股票（价格介于MA20和MA10之间）时触发。关键词包括：自选股均线、MA筛选、均线回踩、MA交叉。

1. Run the query script:

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/watchlist-ma/scripts/query.py
```

2. Parse the JSON output. Format `filtered` array as a table:

| 代码 | 名称 | 最新价 | MA10 | MA20 | 高于MA20% |
|------|------|--------|------|------|-----------|

3. If `filtered` is empty, report no stocks meet the MA20 < price < MA10 condition today.

**注意**：MA10 和 MA20 必须取当日（最新交易日）的均线值，不是历史日期的均线。

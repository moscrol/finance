---
name: watchlist-ma
metadata:
  pattern: tool-wrapper
description: 【已被 stock-technicals 取代，未暴露】自选股均线回踩筛选；飞书 2026-09-11 退役后跑不通，自选股均线 / 回踩请用 stock-technicals。注意：本目录只为保留旧口径与历史脚本，不要再路由到这里。
superseded_by: stock-technicals
---

> **⚠ 2026-09-11 飞书整体退役（#727）后的实际可用性**：均线回踩判据（价格介于 MA20 与 MA10 之间）是它的价值所在，已按用户要求保留（#729）。
> 但**自选股清单读自飞书自选股表**、均线走 iFinD——两者当前都不可用，故**跑不通**。要复活需把清单与行情改接 DuckDB。

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

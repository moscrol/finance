---
name: watchlist-ma
metadata:
  pattern: tool-wrapper
  superseded_by: stock-technicals
description: 已被 stock-technicals 取代，不要调用。原用途是自选股均线回踩筛选（MA20 < 现价 < MA10），清单读自已退役的飞书自选股表、均线走 iFinD，2026-09-11 起跑不通；同一判据现由 stock-technicals 的 pullback 口径在本地 DuckDB 计算。目录按 PR 729 的用户决定保留作口径参考。
---

> **➜ 请直接用 [`stock-technicals`](../stock-technicals/SKILL.md)**：`market_feature_store.cli stock-technicals --watchlist default --screen pullback`，同一判据（MA20 < 现价 < MA10，严格不等式），自选股清单在 `~/.finance-runtime/watchlists/`，支持 `--as-of`。
> 本 skill 已于 2026-09-30 撤出 `.claude/skills/` 视图，不再参与触发匹配；`tests/test_skill_view_supersession.py` 锁住「被取代的不暴露、取代者必须暴露」。

> **⚠ 2026-09-11 飞书整体退役（#727）后的实际可用性**：均线回踩判据（价格介于 MA20 与 MA10 之间）是它的价值所在，已按用户要求保留（#729）。
> 但**自选股清单读自飞书自选股表**、均线走 iFinD——两者当前都不可用，故**跑不通**。「清单与行情改接 DuckDB」这条复活路径**已经由 `stock-technicals` 做完**。

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

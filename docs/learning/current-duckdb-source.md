# Current DuckDB Source

## 结论

当前金融问答、个股深挖、复盘前瞻和验证，标准盘面库是：

```text
/Users/a77/finance-workspace-private/db/market_feature_store.duckdb
```

`db/market.duckdb` 是早期飞书同步阶段的旧路径，不作为当前问答数据源。除非用户明确要求检查旧飞书-era 数据，否则不要读取它。

## 深挖前验鲜

使用 DuckDB 前先确认库的新鲜度：

```sql
select count(*), min(trade_date), max(trade_date) from fact_market_daily;
select count(*), min(trade_date), max(trade_date) from fact_stock_daily;
select count(*), min(trade_date), max(trade_date) from fact_sector_daily;
select count(*), min(trade_date), max(trade_date) from fact_sector_stock_daily;
select count(*), min(trade_date), max(trade_date) from fact_mainline_sector_daily;
```

回答里如果涉及“最新盘面”，必须说明最大交易日。例如：本次 DuckDB 最大交易日为 `2026-06-30`。

## 为什么这么做

路径统一解决的是“数据源漂移”：同一个问题如果有的 agent 读旧库、有的读新库，结论会看似都很有理，但底层口径已经不一致。

可复用知识点：任何数据驱动 agent 都应该有 canonical data source（唯一标准数据源）和 freshness probe（新鲜度探针）。这个原则在 RAG 索引、特征库、日志分析、风控模型里都能用。

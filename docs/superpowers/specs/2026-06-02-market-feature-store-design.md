---
title: Market Feature Store Design
created: 2026-06-02
status: draft-approved-for-incremental-implementation
---

> ⚠ 历史设计文档（2026-06-02）。文中「飞书 Bitable」数据源与同步路径已废弃：复盘数据统一走 `daily-full` → DuckDB（权威来源见根目录 `CLAUDE.md`「核心工作流」；旧库说明见 `docs/learning/current-duckdb-source.md`）。

# Market Feature Store Design

## Objective

Build a local DuckDB-backed market feature store for future trading strategies and Theme Radar integration. The system is not a single-strategy database. It is a stable foundation for querying sector movement, stock-sector membership, market breadth, limit-advance activity, stock interval strength, weighted gains, UP line, and deviation.

## Confirmed Decisions

- 一级板块使用申万一级行业。
- 复盘会板块到个股映射采用每日全量快照。
- 个股涨幅和加权涨幅采用混合方案：保留飞书历史计算结果，同时逐步支持本地重算。
- 板块-个股历史回补先做最近 1-2 个月。
- 本地库定位为镜像层只读 + 单独人工配置层。
- 使用方式提供 Python API + CLI 双入口。
- 现有 `scripts/sync_to_local.py` 作为实验品和迁移参考，不作为长期主入口。

## Data Sources

### Feishu Historical Seeds

- 每日复盘 Bitable: `tbljGvjtl1IC44hb`
- 涨家数走势 Bitable: `chart`
- 板块边际量 Spreadsheet: `sector_marginal_sheet`
- 板块日指标 Bitable: `sector_daily`
- 强势股 Bitable: `top_gainers`
- 大成交涨幅排行 Bitable: `high_volume_gainers`
- 连板晋级横表 Bitable: `limit_advance`
- 自选股 Bitable: `watchlist`

### Fupanhui / 复盘会

- 板块列表: `/api/v1/client/reviews/sectors/search`
- 板块 K 线/边际量: `/api/v1/client/reviews/sector-cycle/{ts_code}/kline`
- 板块成分股: `/api/v1/client/reviews/sector-cycle/{ts_code}/stocks?trade_date=YYYY-MM-DD`
- 连板梯队: `/api/v1/client/limit/ladder`
- 个股 K 线: `/api/v1/client/stock-kline/{ts_code}/kline`

### Existing Project Skills

- `skills/high-volume-gainers`: 加权涨幅算法。
- `skills/up-line`: UP 线和偏离度算法。
- `skills/limit-advance`: 连板晋级抓取。
- `skills/sector-data`: 板块边际量抓取流程。
- `skills/market-overview`: 每日市场复盘数据。

## Core Concepts

### Raw facts vs computed features

External data enters fact tables. Computed indicators enter feature tables. Existing Feishu-computed results are preserved as historical result facts and can later be compared with locally recomputed values.

### Point-in-time membership

Stock-sector membership must be stored by trade date:

```text
trade_date + sector_ts_code + stock_ts_code
```

Historical queries and backtests must not use today's sector constituents to infer past membership.

### Rebuildability

Mirror/fact tables should be reproducible from Feishu/Fupanhui sources. Manual corrections and strategy parameters live in separate config tables.

## Proposed Module Layout

```text
market_feature_store/
├─ schema.sql
├─ db.py
├─ sources/
│  ├─ feishu_source.py
│  └─ fupanhui_source.py
├─ sync/
│  ├─ sync_feishu_history.py
│  ├─ sync_fupanhui_daily.py
│  └─ backfill_sector_stocks.py
├─ features/
│  ├─ sector_features.py
│  ├─ stock_features.py
│  ├─ market_features.py
│  └─ limit_advance_features.py
├─ queries/
│  ├─ sector_queries.py
│  ├─ stock_queries.py
│  ├─ market_queries.py
│  └─ theme_queries.py
└─ cli.py
```

## Fact Tables

### `dim_sector`

Stores fupanhui sector identity and Shenwan L1 mapping.

```sql
sector_ts_code TEXT PRIMARY KEY,
sector_name TEXT NOT NULL,
sw_l1 TEXT,
is_active BOOLEAN,
first_seen_date DATE,
last_seen_date DATE,
source TEXT,
updated_at TIMESTAMP
```

### `fact_sector_daily`

Stores sector daily return, amount, and marginal volume.

```sql
trade_date DATE,
sector_ts_code TEXT,
sector_name TEXT,
sw_l1 TEXT,
pct_chg DOUBLE,
amount DOUBLE,
diff_ratio DOUBLE,
strength DOUBLE,
source TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (trade_date, sector_ts_code)
```

### `fact_sector_stock_daily`

Stores daily full snapshot of sector constituents.

```sql
trade_date DATE,
sector_ts_code TEXT,
sector_name TEXT,
sw_l1 TEXT,
stock_ts_code TEXT,
stock_name TEXT,
price DOUBLE,
pct_chg DOUBLE,
amount DOUBLE,
pct_chg_5d DOUBLE,
pct_chg_10d DOUBLE,
pct_chg_20d DOUBLE,
fund_flow_1d DOUBLE,
fund_flow_5d DOUBLE,
sw_industry TEXT,
leader_plate TEXT,
leader_sub_plate TEXT,
source TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (trade_date, sector_ts_code, stock_ts_code)
```

### `fact_market_daily`

Stores the full daily market review state from Feishu and fupanhui.

```sql
trade_date DATE PRIMARY KEY,
market_stage TEXT,
stage_day INTEGER,
ice_point TEXT,
total_amount DOUBLE,
amount_vs_yesterday_pct DOUBLE,
amount_ma20 DOUBLE,
volume_ratio DOUBLE,
volume_state TEXT,
advancers INTEGER,
limit_up INTEGER,
limit_down INTEGER,
sh_week_ma DOUBLE,
sh_deviation_pct DOUBLE,
top3_industry_ratio DOUBLE,
concentration_state TEXT,
industry_1 TEXT,
industry_1_ratio DOUBLE,
industry_2 TEXT,
industry_2_ratio DOUBLE,
industry_3 TEXT,
industry_3_ratio DOUBLE,
note TEXT,
source TEXT,
updated_at TIMESTAMP
```

### `fact_stock_daily`

Stores stock daily market data needed for local feature recomputation.

```sql
trade_date DATE,
stock_ts_code TEXT,
stock_name TEXT,
close DOUBLE,
pre_close DOUBLE,
pct_chg DOUBLE,
amount DOUBLE,
turnover DOUBLE,
source TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (trade_date, stock_ts_code)
```

First implementation does not require full A-share coverage. Priority universe: sector constituents, top gainers, high-volume gainers, watchlist, and Theme Radar stocks.

### `fact_high_volume_gainers`

Stores historical high-volume weighted-gain results from Feishu.

```sql
start_date DATE,
end_date DATE,
stock_ts_code TEXT,
stock_name TEXT,
themes TEXT,
avg_amount DOUBLE,
interval_gain_pct DOUBLE,
weighted_gain DOUBLE,
rank INTEGER,
source TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (start_date, end_date, stock_ts_code)
```

Weighted gain formula from `skills/high-volume-gainers`:

```text
weighted_gain = avg_amount_yi * interval_gain_pct / 100
```

### `fact_top_gainers`

Stores historical top-gainer pool results from Feishu.

```sql
start_date DATE,
end_date DATE,
stock_ts_code TEXT,
stock_name TEXT,
sw_industry TEXT,
themes TEXT,
interval_gain_pct DOUBLE,
avg_amount DOUBLE,
up_value DOUBLE,
deviation_pct DOUBLE,
rank INTEGER,
source TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (start_date, end_date, stock_ts_code)
```

### `fact_limit_advance_presence`

Normalizes the Feishu horizontal limit-advance timeline into a long table.

```sql
trade_date DATE,
stock_name TEXT,
sequence_no INTEGER,
source TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (trade_date, stock_name)
```

### `fact_limit_advance_daily`

Stores detailed daily limit-advance records from fupanhui.

```sql
trade_date DATE,
stock_ts_code TEXT,
stock_name TEXT,
boards INTEGER,
first_limit_date DATE,
theme TEXT,
pct_chg DOUBLE,
promotion_rate TEXT,
source TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (trade_date, stock_ts_code)
```

### `fact_stock_technical_snapshot`

Stores existing Feishu-computed UP/deviation values.

```sql
trade_date DATE,
stock_ts_code TEXT,
stock_name TEXT,
up_value DOUBLE,
deviation_pct DOUBLE,
source_table TEXT,
source TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (trade_date, stock_ts_code, source_table)
```

UP/deviation formula from `skills/up-line`:

```text
UP = MA26 + 0.764 * STD26
deviation_pct = (close / UP - 1) * 100
```

## Config Tables

### `config_sector_alias`

Maps aliases to fupanhui sectors.

```sql
alias TEXT,
sector_ts_code TEXT,
sector_name TEXT,
confidence DOUBLE,
note TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (alias, sector_ts_code)
```

### `config_theme_sector_link`

Maps Theme Radar themes/directions to fupanhui sectors.

```sql
theme TEXT,
direction TEXT,
sector_ts_code TEXT,
sector_name TEXT,
match_type TEXT,
confidence DOUBLE,
note TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (theme, direction, sector_ts_code)
```

### `config_strategy_rule`

Stores future strategy parameters.

```sql
rule_name TEXT PRIMARY KEY,
rule_type TEXT,
params_json TEXT,
enabled BOOLEAN,
note TEXT,
updated_at TIMESTAMP
```

### `config_watchlist`

Stores manual watchlist groups.

```sql
stock_ts_code TEXT,
stock_name TEXT,
group_name TEXT,
reason TEXT,
updated_at TIMESTAMP,
PRIMARY KEY (stock_ts_code, group_name)
```

## Feature Tables or Views

### `feature_sector_window`

Computes sector interval gain, amount change, and marginal-volume trend.

### `feature_stock_window`

Computes stock interval gain, average amount, and weighted gain from `fact_stock_daily`.

### `feature_market_window`

Computes market breadth, amount, stage, and concentration trends.

### `feature_limit_advance_window`

Computes recent limit-advance frequency, max boards, and theme/sector aggregation.

### `feature_stock_technical_daily`

Computes MA26, STD26, UP, and deviation from `fact_stock_daily` once enough history is available.

## Query Requirements

The first version should provide Python API and CLI for:

- Sector interval gain and marginal-volume change.
- Sector constituents for a trade date.
- Stock-to-sector membership for a trade date.
- Market daily state and market-window change.
- Weighted-gain ranking for a date interval.
- Limit-advance stocks and recent advance frequency.
- UP/deviation lookup and later recomputation.
- Theme Radar to fupanhui sector lookup.

## Weighted Gain Query Priority

When a user asks for weighted-gain ranking:

1. If `fact_stock_daily` covers the interval, compute locally.
2. Else if `fact_high_volume_gainers` has the interval, return historical Feishu result.
3. Else allow a fallback to the existing iFinD-based high-volume-gainers skill and optionally persist the result.

## UP/Deviation Query Priority

When a user asks for UP/deviation:

1. If `feature_stock_technical_daily` covers the date, return local computed result.
2. Else if `fact_stock_technical_snapshot` has the date/source table, return historical Feishu result.
3. Else allow a fallback to the existing `up-line` skill and optionally persist the result.

## Implementation Phases

### Phase 0: Project skeleton and schema

- Create `market_feature_store/` package.
- Create `schema.sql`.
- Create DB helper and init command.
- Keep DB files out of Git.

### Phase 1: Feishu historical sync

- Sync `fact_market_daily` from daily review Bitable.
- Sync `fact_high_volume_gainers` and `fact_top_gainers` from Feishu.
- Sync `fact_limit_advance_presence` from the horizontal Feishu limit-advance table.
- Sync existing UP/deviation snapshots where present.

### Phase 2: Sector foundation

- Sync `dim_sector` with Shenwan L1 mapping.
- Sync `fact_sector_daily` from Feishu historical sector marginal data and sector daily metrics.

### Phase 3: Fupanhui backfill

- Backfill 1-2 months of `fact_sector_stock_daily`.
- Add incremental daily sync.
- Sync detailed `fact_limit_advance_daily` from fupanhui.

### Phase 4: Feature and query layer

- Implement sector, stock, market, limit-advance, weighted-gain, and UP/deviation query APIs.
- Add CLI commands for common queries.

### Phase 5: Theme Radar integration

- Add theme-to-sector mapping config and query helpers.
- Allow Theme Radar outputs to enrich market/sector/stock context.

## Out of Scope for v1

- Full A-share historical daily data for all listed stocks.
- Intraday/high-frequency refresh.
- Automatic trading decisions.
- Complete 5-6 month sector constituent backfill on day one.
- Committing DuckDB files or secrets to Git.

## Acceptance Criteria for v1

- Local schema initializes successfully.
- Feishu daily review table is represented in `fact_market_daily`.
- High-volume weighted-gain history is represented and queryable.
- Limit-advance Feishu horizontal table is normalized into daily rows.
- Sector daily marginal volume and returns are queryable.
- Recent sector-stock snapshots can answer both sector-to-stock and stock-to-sector queries.
- Weighted gain can be returned from local calculation or preserved Feishu results with source noted.
- UP/deviation can be returned from local calculation or preserved Feishu snapshots with source noted.

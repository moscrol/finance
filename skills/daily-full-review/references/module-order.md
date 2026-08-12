# 已验证模块顺序

### 已验证模块顺序与兜底（核心知识）

顺序对齐 `run_daily_update`，但拆成可隔离、可续跑的模块：

| 阶段 | 模块 | 已验证命令 | 卡住兜底 |
|---|---|---|---|
| 0 预检 | db-lock | `python3 scripts/check_db_lock.py` | 有锁先查占用进程，勿强删库 |
| 1 轻 | sectors | `sync-sectors --trade-date D` | 一般不卡 |
| 1 轻 | market-overview | `sync-market-overview --trade-date D --days 60` | CDP 500 重试 |
| 1 轻 | market-daily | `sync-market-daily` | 飞书表，少卡 |
| 1 轻 | index-daily | `sync-index-daily --trade-date D` | AkShare，少卡 |
| 1 轻 | sw-l1-daily | `sync-sw-l1-daily --trade-date D --days 20` | 少卡 |
| 1 轻 | market-deviation | `sync-market-deviation --trade-date D` | tooltip 抓取 2026-07 起稳定失效（见「夜间 launchd 定时运维」）→ **MA5 复算兜底**（`fill_stock_daily_fallback` 同款：最近 5 个 `sh_index_close` 均值，`dev=(close/ma-1)*100`） |
| 1 轻 | sector-daily | `sync-sector-daily --trade-date D --days 25` | CDP 500 重试 |
| 2 重 | sector-stocks | 循环 `sync-sector-stocks --trade-date D --limit 60 --sleep 0.05`（内部按 chunk=10 一次 eval 并发抓一批，已非逐板块）直到 `count(distinct sector_ts_code) >= dim_sector` | 默认跳过已抓板块，可续跑；chunk 失败自动降级逐板块单抓 |
| 2 重 | limit-heat | **直跑** `sync-limit-heat --trade-date D --detail-chunk 12 --sleep 0.05`（看 chunk 进度；失败自动二分降级） | 写完若有题材"有涨停但明细为空"，逐个 `--sector <题材> --detail-chunk 1` 重试 |
| 2 重 | stock-high | `sync-stock-high --trade-date D --page-size 200` | 个别日期会挂，超时则记 skip |
| 2 重 | limit-advance | `sync-limit-advance --trade-date D --min-boards 2` | 少卡 |
| 3 兜底 | stock-daily | 先 `sync-stock-daily-snapshot --trade-date D --page-size 100`（东财快照，单日复盘默认，快） | **超时/失败 → `fill-stock-daily-fallback --trade-date D`**（用 sector_stock 聚合，已验证当日可用）。历史多日回填才用 mootdx（`sync-stock-daily`，走 duckdb-backfill） |
| 4 轻 | mainline-daily | `sync-mainline-daily --trade-date D` | 复盘会主线题材+主线个股 → `fact_mainline_theme_daily` / `fact_mainline_stock_daily`；少卡 |
| 4 轻 | theme-flow-daily | `sync-theme-flow-daily --trade-date D` | 复盘会题材资金面板 → `fact_theme_flow_daily`；少卡 |
| 5 审计 | quality-gate | `python3 scripts/check_daily_review_data.py D` | 必须 RESULT: COMPLETE |


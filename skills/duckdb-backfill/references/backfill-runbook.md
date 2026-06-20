# duckdb-backfill 回补 Runbook

> 本文件由 `skills/duckdb-backfill/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

## Backfill order

1. **Calendar/base facts**
   - Confirm `fact_market_daily` calendar with `total_amount is not null`.
   - Confirm `fact_sector_daily` and `fact_stock_daily` coverage.
   - 单日 `fact_stock_daily` 增量优先用东财快照 `sync-stock-daily-snapshot`（秒级）；补历史区间用 mootdx `sync-stock-daily`（见下「单日快照 vs 历史 mootdx」）。
2. **Light tables**
   - `sync-sw-l1-daily` by 45-60 day windows.
   - `sync-limit-advance-range` by quarters; validate `fact_limit_advance_presence`.
3. **Medium table**
   - `stock_high` should run as single-day commands or via `scripts/run_stock_high_missing.py`; avoid silent long range jobs.
4. **Heavy/hang-prone tables**
   - `limit_heat` and `sector_stock` need progress output and timeouts. Use tiny smoke tests first.
   - Do not run all-history `sector_stock` without a resumable per-sector/per-date plan.

## 全A日线 fact_stock_daily：单日快照 vs 历史 mootdx

两条取数路径，按场景选：

- **单日盘后增量 → 东财全市场快照（快，默认）**：`sync-stock-daily-snapshot`。分页拉全 A（约 6 千只，东财单页上限100、约60页）当日 收盘/涨跌幅/昨收/成交额，数十秒写完。`daily-full`/`daily-update` 默认 `--stock-source snapshot` 就走这条，避免 mootdx 逐只 TCP 的十几分钟长尾（个别股超时各卡几分钟）。仅取当日，必须**盘后**、且显式传 `--trade-date`（盘中会写实时价、非交易日会把上一交易日数据写到所传日期）。
- **历史多日回填 → mootdx 逐只（慢，可拉区间）**：`sync-stock-daily --start-date ... --offset N`。快照接口只给当日截面，补历史区间仍必须用 mootdx。`daily-full --stock-source mootdx` 可强制日更也走 mootdx（受 `--skip-long` 控制）。

两条路径同 schema/口径（amount 存「亿」、close 不复权、turnover 留空）；快照 `source='eastmoney:snapshot'`，mootdx `source='mootdx'`。

## Useful commands

```bash
python3 skills/duckdb-backfill/scripts/audit_coverage.py
python3 -m market_feature_store.cli info
python3 -m market_feature_store.cli check
python3 -m market_feature_store.cli sync-sw-l1-daily --trade-date YYYY-MM-DD --days 60
python3 -m market_feature_store.cli sync-limit-advance-range --start-date YYYY-MM-DD --end-date YYYY-MM-DD --sleep 0.1
python3 skills/duckdb-backfill/scripts/run_stock_high_missing.py --max-days 5 --timeout 180 --max-failures 2 --record-failures
# 全A日线：单日盘后增量（东财快照，秒级）
python3 -m market_feature_store.cli sync-stock-daily-snapshot --trade-date YYYY-MM-DD
# 全A日线：历史区间回填（mootdx 逐只，慢）
python3 -m market_feature_store.cli sync-stock-daily --start-date YYYY-MM-DD --offset 180
# 一键复盘强制用 mootdx 跑全A日线（默认 snapshot）
python3 -m market_feature_store.cli daily-full --trade-date YYYY-MM-DD --stock-source mootdx
```

## Current known state from 2026-06-20

Calendar baseline: `calendar_with_amount` 352 trading days, `2025-01-02` ~ `2026-06-18`.

- **Complete (missing=0)**: `fact_sector_daily` (357 dates), `fact_sector_stock_daily` (352), `fact_stock_daily` (352), `fact_stock_high_daily` (352), `fact_limit_advance_presence` (352), `fact_sw_l1_daily` (354).
- **Partial**: `fact_theme_limit_heat_daily` (343 dates, 9 missing: `2025-05-27`, `2025-06-18`, `2025-07-29~31` 等), `fact_theme_limit_stock_daily` (342 dates, 10 missing).
- **Sparse by design**: `fact_limit_advance_daily` (296 dates, 56 "missing" 多为无连板数据的日期).
- Known stock-high hang dates: `2025-03-05`, `2025-03-06`.
- Known stock-high CDP 500 dates in bad proxy/API sessions: `2025-03-21`, `2025-03-24`, `2025-03-25`, `2025-04-14`, `2025-04-17`, `2025-04-18`, `2025-04-21`, `2025-04-22`, `2025-04-23`, `2025-04-24`, `2025-04-25`, `2025-04-28`, `2025-04-29`, `2025-04-30`.
- Known stock-high timeout dates after proxy ready: `2025-03-21`, `2025-03-26` timed out at 180s via `run_stock_high_missing.py`.
- Stock-high skipped dates are stored in `skills/duckdb-backfill/state/stock_high_skip.txt`; `run_stock_high_missing.py` reads this file by default and `--record-failures` appends newly failed dates.
- Known limit-heat blocker: `sync-limit-heat --trade-date 2025-01-02 --detail-chunk 3 --sleep 0.1` hung with CPU 0 and wrote no rows.
- Known sector-stock behavior: `sync-sector-stocks --trade-date 2025-01-02 --limit 20 --sleep 0.1` wrote 13 sectors / 2066 rows before termination.

## 前置检查清单（每次 daily-full 前）

1. **CDP proxy 已启动**：`curl -s http://localhost:3456/targets` 返回 JSON 数组
2. **Chrome 已登录 fupanhui.com**：CDP proxy 依赖 fupanhui 登录态
3. **审计当前覆盖**：`python3 skills/duckdb-backfill/scripts/audit_coverage.py`

# duckdb-backfill 回补 Runbook

> 本文件由 `skills/duckdb-backfill/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

## Backfill order

1. **Calendar/base facts**
   - Confirm `fact_market_daily` calendar with `total_amount is not null`.
   - Confirm `fact_sector_daily` and `fact_stock_daily` coverage.
2. **Light tables**
   - `sync-sw-l1-daily` by 45-60 day windows.
   - `sync-limit-advance-range` by quarters; validate `fact_limit_advance_presence`.
3. **Medium table**
   - `stock_high` should run as single-day commands or via `scripts/run_stock_high_missing.py`; avoid silent long range jobs.
4. **Heavy/hang-prone tables**
   - `limit_heat` and `sector_stock` need progress output and timeouts. Use tiny smoke tests first.
   - Do not run all-history `sector_stock` without a resumable per-sector/per-date plan.

## Useful commands

```bash
python3 skills/duckdb-backfill/scripts/audit_coverage.py
python3 -m market_feature_store.cli info
python3 -m market_feature_store.cli check
python3 -m market_feature_store.cli sync-sw-l1-daily --trade-date YYYY-MM-DD --days 60
python3 -m market_feature_store.cli sync-limit-advance-range --start-date YYYY-MM-DD --end-date YYYY-MM-DD --sleep 0.1
python3 skills/duckdb-backfill/scripts/run_stock_high_missing.py --max-days 5 --timeout 180 --max-failures 2 --record-failures
```

## Current known state from 2026-06-15

Calendar baseline: `fact_market_daily` has 348 trading days with `total_amount`, from `2025-01-02` to `2026-06-12`.

- Complete: `fact_sector_daily`, `fact_stock_daily`, `fact_sw_l1_daily`, `fact_limit_advance_presence`.
- Partial: `fact_stock_high_daily`, 214 covered calendar dates, 134 missing calendar dates after the 2026-06-15 backfill session; next non-skipped missing starts at `2025-07-14`.
- Heavy gaps: `fact_sector_stock_daily`, `fact_theme_limit_heat_daily`, `fact_theme_limit_stock_daily`.
- Known stock-high hang dates: `2025-03-05`, `2025-03-06`.
- Known stock-high CDP 500 dates in bad proxy/API sessions: `2025-03-21`, `2025-03-24`, `2025-03-25`, `2025-04-14`, `2025-04-17`, `2025-04-18`, `2025-04-21`, `2025-04-22`, `2025-04-23`, `2025-04-24`, `2025-04-25`, `2025-04-28`, `2025-04-29`, `2025-04-30`.
- Known stock-high timeout dates after proxy ready: `2025-03-21`, `2025-03-26` timed out at 180s via `run_stock_high_missing.py`.
- Stock-high skipped dates are stored in `skills/duckdb-backfill/state/stock_high_skip.txt`; `run_stock_high_missing.py` reads this file by default and `--record-failures` appends newly failed dates.
- Known limit-heat blocker: `sync-limit-heat --trade-date 2025-01-02 --detail-chunk 3 --sleep 0.1` hung with CPU 0 and wrote no rows.
- Known sector-stock behavior: `sync-sector-stocks --trade-date 2025-01-02 --limit 20 --sleep 0.1` wrote 13 sectors / 2066 rows before termination.

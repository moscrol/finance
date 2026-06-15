---
name: duckdb-backfill
description: DuckDB market_feature_store full/backfill workflow for the finance workspace. Use when the user asks to 回补 duckdb、全量回补、补缺口、补 market_feature_store 数据、修复 fact_* 覆盖、同步 stock_high/sector_stock/limit_heat/limit_advance/sw_l1, or when a sync command hangs and the workflow needs short-command retries, coverage audits, timeout handling, and iterative skill optimization.
---

# DuckDB Backfill

## Overview

Use this skill to backfill `/Users/lbq/Desktop/c c/金融/db/market_feature_store.duckdb` safely and incrementally. Prefer small observable commands, read-only audits first, and script improvements whenever a sync path hangs or becomes fragile.

## Mandatory start

Run and report:

```bash
git status --short
git branch --show-current
```

Do not stage DB files or generated exports. DuckDB writes are local state changes; keep source edits separate from data sync.

## Core rules

- **Audit first**: Run `python3 skills/duckdb-backfill/scripts/audit_coverage.py` before writing.
- **Use short units**: Prefer one table, one quarter/month, or 5 trading days. Avoid long SQL heredocs and silent range jobs.
- **Stop silent hangs**: If a command has no output and CPU is 0 for about 2 minutes, terminate it and improve the skill/script instead of retrying blindly.
- **Prefer idempotent CLI commands**: Use existing `python3 -m market_feature_store.cli ...` commands before adding new data logic.
- **Separate facts from sparse tables**: `fact_limit_advance_presence` is the daily coverage table; `fact_limit_advance_daily` is sparse by design.
- **Record blockers**: Keep a list of skipped dates/sectors and explain why they were skipped.

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

## Iteration rule

Whenever a backfill path hangs, returns misleading success, or needs manual rescue, update this skill or its scripts immediately before continuing large-scale backfill.

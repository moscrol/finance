# DuckDB Backfill Handoff

Date: 2026-06-15
Workspace: `/Users/lbq/Desktop/c c/金融`
Branch at handoff: `strategy/strategy-matrices`
Database: `db/market_feature_store.duckdb`

## Safety rules

- Start with `git status --short` and `git branch --show-current`.
- Do not stage DuckDB database files, generated exports, FDE docs, or unrelated untracked files.
- Keep source/tooling commits separate from local data sync state.

## What was completed

- Created `skills/duckdb-backfill/` as the reusable backfill skill.
- Added `scripts/audit_coverage.py` to audit key fact table coverage against `fact_market_daily` calendar days where `total_amount is not null`.
- Added `scripts/run_stock_high_missing.py` to backfill `fact_stock_high_daily` by missing trading day with timeout, failure threshold, known-skip support, and automatic failure recording.
- Added `state/stock_high_skip.txt` for stock-high dates that should be skipped by default.
- Backfilled `fact_stock_high_daily` from early March 2025 through `2025-07-11`, skipping known bad dates.

## Current audit snapshot

Canonical calendar: 348 trading days, `2025-01-02` to `2026-06-12`.

Current coverage after the last successful batch:

- `fact_sector_daily`: missing 0
- `fact_stock_daily`: missing 0
- `fact_sw_l1_daily`: missing 0
- `fact_limit_advance_presence`: missing 0
- `fact_stock_high_daily`: 139842 rows, 214 covered dates, missing 134 calendar dates
- `fact_sector_stock_daily`: missing 301
- `fact_theme_limit_heat_daily`: missing 300
- `fact_theme_limit_stock_daily`: missing 301
- `fact_limit_advance_daily`: sparse by design; do not treat missing dates as coverage failure without checking semantics

## Stock-high continuation

Next command for the next session:

```bash
python3 skills/duckdb-backfill/scripts/run_stock_high_missing.py --max-days 5 --timeout 180 --max-failures 2 --record-failures
```

Expected next target dates from dry-run:

```text
2025-07-14,2025-07-15,2025-07-16,2025-07-17,2025-07-18
```

Check first with:

```bash
python3 skills/duckdb-backfill/scripts/run_stock_high_missing.py --max-days 5 --timeout 180 --dry-run
```

Then audit after each successful 5-day batch:

```bash
python3 skills/duckdb-backfill/scripts/audit_coverage.py
```

## Known skipped stock-high dates

Stored in `skills/duckdb-backfill/state/stock_high_skip.txt`.

Current skipped dates:

```text
2025-03-05
2025-03-06
2025-03-21
2025-03-24
2025-03-25
2025-03-26
2025-04-14
2025-04-17
2025-04-18
2025-04-21
2025-04-22
2025-04-23
2025-04-24
2025-04-25
2025-04-28
2025-04-29
2025-04-30
```

## Failure handling

- If a day returns CDP HTTP 500 or times out, keep using `--record-failures`; the script appends the date to `state/stock_high_skip.txt` and moves on until the consecutive failure threshold is hit.
- If two consecutive dates fail, stop and inspect proxy/CDP health before continuing.
- If a process has no output and CPU is 0 for roughly 2 minutes, terminate it and improve the script/skill before retrying large batches.

## Remaining work after stock-high

After `fact_stock_high_daily` is as complete as practical:

1. Revisit skipped stock-high dates deliberately with `--no-known-skip` only if proxy/API health is confirmed.
2. Harden `sync-limit-heat` with progress output/timeouts before retrying `fact_theme_limit_heat_daily` and `fact_theme_limit_stock_daily`.
3. Harden `sync-sector-stocks` with resumable per-date/per-sector progress before retrying `fact_sector_stock_daily`.

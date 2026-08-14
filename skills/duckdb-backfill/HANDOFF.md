# DuckDB Backfill Handoff

Date: 2026-06-16 (updated)
Workspace: `/Users/lbq/Desktop/c c/金融`
Branch at handoff: `evolve/strategy-engine-20260615`
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
- Backfilled `fact_stock_high_daily` to FULL coverage (missing=0); the known-skip list was cleared because every previously skipped date was successfully filled.
- Added `scripts/run_missing_dates.py`: generic missing-date backfill driver (sector_stock / limit_heat / limit_stock / stock_high) with per-date subprocess isolation, timeout, progress, per-table skip file, and consecutive-failure threshold.

## Current audit snapshot

Canonical calendar: 349 trading days, `2025-01-02` to `2026-06-15`.

Current coverage (run `audit_coverage.py` to refresh):

- `fact_sector_daily`: missing 0
- `fact_stock_daily`: missing 0 (2026-06-15 filled via `fill-stock-daily-fallback`)
- `fact_sw_l1_daily`: missing 0
- `fact_stock_high_daily`: missing 0 (FULL)
- `fact_limit_advance_presence`: missing 0
- `fact_sector_stock_daily`: missing ~292 (2025 H1 历史日, source 有数据可补)
- `fact_theme_limit_heat_daily`: missing ~299 (2025-01-02 已验证可补)
- `fact_theme_limit_stock_daily`: missing ~300
- `fact_limit_advance_daily`: sparse by design; do not treat missing dates as coverage failure without checking semantics

Source feasibility confirmed 2026-06-16: fupanhui serves historical sector-stocks AND limit-distribution for old dates (probed 2025-01-03 / 2025-06-10), so the theme/sector backfill is NOT source-limited — it just needs to be ground out in batches.

## Continuation: theme/sector backfill (run_missing_dates.py)

`fact_stock_high_daily` is DONE. Remaining backfill = `sector_stock` / `limit_heat` / `limit_stock`.
These are long grinds (~290-300 missing dates each); run in small batches and audit between batches.
Validated 2026-06-16: `limit_heat` 2025-01-02 backfilled cleanly via the runner.

Cost notes:
- `limit_heat` per date: distribution + chunked limit-stock detail via CDP eval (~1-3 min/date). `limit_stock` is filled by the same `sync-limit-heat` command.
- `sector_stock` per date: 227 sectors, per-sector commit/resume (~3-5+ min/date). Use a larger `--timeout`.

Dry-run first (oldest-first by default; `--newest-first` to prioritize recent):

```bash
python3 skills/duckdb-backfill/scripts/run_missing_dates.py --table limit_heat --max-days 3 --dry-run
```

Run a batch:

```bash
# theme limit heat + stock (same command fills both tables)
python3 skills/duckdb-backfill/scripts/run_missing_dates.py --table limit_heat --max-days 3 --timeout 600 --max-failures 2 --record-failures

# sector stocks (slower; bigger timeout)
python3 skills/duckdb-backfill/scripts/run_missing_dates.py --table sector_stock --max-days 2 --timeout 1200 --max-failures 2 --record-failures
```

Audit after each batch:

```bash
python3 skills/duckdb-backfill/scripts/audit_coverage.py
```

## Skip files (per-table local sync state)

`run_missing_dates.py` records failed dates into `state/{table}_skip.txt` when `--record-failures` is set
(e.g. `state/limit_heat_skip.txt`, `state/sector_stock_skip.txt`). `state/stock_high_skip.txt` is now
EMPTY because stock-high reached full coverage and all previously skipped dates were filled.
These skip files are local data-sync state; commit them separately from source/tooling changes.

## Failure handling

- If a day returns CDP HTTP 500 or times out, keep using `--record-failures`; the script appends the date to `state/stock_high_skip.txt` and moves on until the consecutive failure threshold is hit.
- If two consecutive dates fail, stop and inspect proxy/CDP health before continuing.
- If a process has no output and CPU is 0 for roughly 2 minutes, terminate it and improve the script/skill before retrying large batches.

## Remaining work

`fact_stock_high_daily` is fully backfilled. Outstanding:

1. Grind `limit_heat` (fills `fact_theme_limit_heat_daily` + `fact_theme_limit_stock_daily`) via `run_missing_dates.py` in 3-day batches, auditing between batches.
2. Grind `sector_stock` (`fact_sector_stock_daily`) via `run_missing_dates.py` in 2-date batches with a larger timeout.
3. `sync-limit-heat` already has internal resilience (chunked detail fetch + bisection fallback + JS AbortController timeouts); `sync-sector-stocks` resumes per sector within a date. The per-date subprocess timeout in `run_missing_dates.py` is the outer safety net, so no further sync-module hardening is required before grinding — just batch and monitor.

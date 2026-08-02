# Legacy Script Migration Design

**Date:** 2026-08-02
**Status:** approved in conversation; awaiting written-spec review
**Branch:** `fix/legacy-script-migration` stacked on `fix/ruff-debt-burn-down@a84028e6`

## 1. Objective

Close the final 27 Ruff findings without pretending that four legacy scripts are healthy. Preserve the useful sector-analysis capabilities on the canonical Market Feature Store, formally retire the obsolete Feishu-to-legacy-DuckDB writer, keep the active daily-review renderer, and remove all four file exclusions from `ruff.toml`.

Completion means:

- `scripts/backtest_sector.py` reads the canonical star schema and remains point-in-time safe.
- `scripts/detect_turning_points.py` uses the same no-look-ahead signal implementation as the backtest.
- `scripts/sync_to_local.py` becomes a side-effect-free retirement shim that directs users to `daily-full`.
- `scripts/render_daily_review_template.py` remains a supported canonical renderer.
- `ruff check .` passes with no exclusions for these files.
- CLI help never opens a database, creates a file, imports Feishu credentials, or calls the network.

## 2. Current Evidence

The current commands provide a deterministic failure loop:

```bash
python3 scripts/backtest_sector.py --help
python3 scripts/detect_turning_points.py --help
python3 scripts/sync_to_local.py --help
python3 scripts/render_daily_review_template.py --help
```

Observed behavior before migration:

- `backtest_sector.py --help` reaches `sector_marginal` instead of showing help and fails with `Catalog Error`.
- `detect_turning_points.py --help` opens `db/market.duckdb` instead of showing help.
- `sync_to_local.py --help` initializes the retired database path before parsing arguments, creates `db/market.duckdb`, and then fails because `db/schema.sql` no longer exists.
- `render_daily_review_template.py --help` is already side-effect free and exits successfully.

The old `db/market.duckdb` database and its tables `sector_marginal`, `daily_market`, and `advancers` are retired. The canonical database is `db/market_feature_store.duckdb`, with its path overridable through `MARKET_FEATURE_STORE_DB`.

Ruff 0.11.13 reports exactly 27 findings across the four excluded files:

- `backtest_sector.py`: 18
- `detect_turning_points.py`: 3
- `sync_to_local.py`: 4
- `render_daily_review_template.py`: 2

## 3. Approaches Considered

### A. Retire all four scripts

This is the smallest maintenance surface, but it discards the sector backtest and turning-point analysis even though their pure strategy logic and no-look-ahead tests remain useful.

### B. Rename old tables in place

This is superficially fast, but it leaves two independent turning-point algorithms, hand-written CLI parsing, and duplicated database mappings. The old detector also has different pivot timing from the tested backtest detector, so a table-only patch could preserve look-ahead ambiguity.

### C. Hybrid migration — selected

Retire only the obsolete writer. Extract one canonical, pure turning-point engine and one read-only star-schema data adapter for both analysis CLIs. Keep the renderer as a supported wrapper. This costs more than table renaming but removes the source of future drift.

## 4. Architecture

### 4.1 Pure signal engine

Create `market_feature_store/analysis/turning_points.py` containing:

- `Signal`
- `SignalDetector`
- `VOLUME_SURGE_PCT`
- `MA5_MIN_SWING`

The module accepts lists of plain dictionaries and has no DuckDB, filesystem, printing, or CLI dependency. It preserves the already-tested confirmation semantics:

- Volume surge is emitted on the day the increase is observable.
- A peak or valley is emitted only on its confirmation day.
- Appending future observations cannot change signals whose dates are already in the historical prefix.

`scripts/backtest_sector.py` imports and re-exports `Signal` and `SignalDetector` at module scope so existing Python callers and `tests/test_backtest_sector.py` remain compatible.

### 4.2 Canonical read adapter

Create `market_feature_store/analysis/sector_data.py` with a read-only `SectorDataProvider`.

The provider accepts an explicit `db_path`; the default comes from `market_feature_store.db.DB_PATH`. Before connecting it verifies that the file exists, then opens DuckDB with `read_only=True`. It never initializes schema or creates directories.

Field mapping:

| Legacy consumer field | Canonical source |
|---|---|
| `date` | `fact_sector_daily.trade_date` or `fact_market_daily.trade_date` |
| `ts_code` | `fact_sector_daily.sector_ts_code` |
| `sector` | `fact_sector_daily.sector_name` |
| `pct_chg` | `fact_sector_daily.pct_chg` |
| `diff_ratio` | `fact_sector_daily.diff_ratio` |
| `amount` | `fact_sector_daily.amount` |
| `volume` | `fact_market_daily.total_amount` |
| `volume_change` | `fact_market_daily.amount_vs_yesterday_pct` |
| `week_ma` | `fact_market_daily.sh_week_ma` |
| `deviation` | `fact_market_daily.sh_deviation_pct` |
| `count` | `fact_market_daily.advancers` |
| `ma5` | five-row rolling average of `fact_market_daily.advancers` |

All sector reads use the published `fact_sector_daily` view, not the generation table, so the existing sector-universe snapshot contract remains authoritative.

### 4.3 Backtest CLI

Keep the strategy engine and output model in `scripts/backtest_sector.py`; replace only its data and CLI seams.

Use `argparse` with these supported options:

- `--from YYYY-MM-DD`
- `--to YYYY-MM-DD`
- `--top N`
- `--hold N`
- `--min-marginal FLOAT`
- `--min-pct FLOAT`
- `--overlap`
- `--scan`
- `--db-path PATH`

`--help` exits zero before opening DuckDB. When dates are omitted, the CLI derives the range from non-null `fact_sector_daily.pct_chg`. A missing database, missing canonical table/view, or empty usable date range returns exit code 2 with a concise diagnostic and creates nothing.

The engine continues to enter on the trading day after a signal and retains the existing no-look-ahead regression tests.

### 4.4 Turning-point CLI

Rewrite `scripts/detect_turning_points.py` as a thin presentation adapter:

1. Parse `--from`, `--to`, and `--db-path` with `argparse`.
2. Read market and breadth series through `SectorDataProvider`.
3. Run the shared `SignalDetector`.
4. Print the daily series and confirmation-day signals.

The old independent zigzag implementation is removed. This is an intentional behavior correction: confirmation-day signals replace the ambiguous “pivot day plus next day” calculation so the standalone report and backtest cannot disagree.

### 4.5 Retired Feishu writer

Replace `scripts/sync_to_local.py` with a small compatibility command. The old 600-line implementation is not copied elsewhere; it remains recoverable from Git history at:

```bash
git show a84028e6:scripts/sync_to_local.py
```

Contract:

- `--help` exits 0 and explains the retirement.
- Running with no arguments or the legacy `--incremental` flag exits 2.
- The message points to `python3 -m market_feature_store.cli daily-full --help` and explains that a trade date must be selected explicitly.
- The module does not import DuckDB, `feishu_utils`, credential loaders, or network libraries.
- It never forwards automatically to `daily-full`; retirement must not turn an old command into a surprising write operation.

### 4.6 Daily-review renderer

Keep `scripts/render_daily_review_template.py` behavior unchanged. Direct-file execution requires adding the repository root to `sys.path` before importing `market_feature_store`; retain this bootstrap and annotate only the two delayed imports with a line-level `E402` reason.

This is preferable to excluding the whole file: the exception is local, documented, and the rest of the file remains under Ruff enforcement.

## 5. Error and Side-Effect Policy

- Argument parsing always precedes database access.
- Analysis commands are read-only and refuse nonexistent database paths.
- Retirement commands do not import retired dependencies.
- User errors return exit code 2; unexpected programming errors remain nonzero with a traceback during development.
- No command writes `db/market.duckdb`.
- No test reads or modifies the user's production DuckDB unless an explicit local smoke command supplies its path.
- No production service, LaunchAgent, port 8792, or port 8799 is changed.

## 6. Test Design

### 6.1 Pure signal regression

Move the existing prefix-stability and next-day-entry coverage with the shared engine. Retain assertions that:

- confirmation requires the configured swing threshold;
- future rows cannot mutate prior signals;
- the backtest enters on the next trading day;
- a last-day signal creates no trade.

### 6.2 Canonical adapter fixture

Create a temporary DuckDB containing minimal `fact_market_daily` and `fact_sector_daily` relations. Verify every field mapping, trade-date ordering, rolling MA5, null filtering, and read-only behavior.

### 6.3 CLI contracts

Subprocess tests run all four `--help` commands in an isolated temporary directory and assert exit code 0. They also assert that no `market.duckdb`, `market_feature_store.duckdb`, output report, or credential file appears.

Additional assertions:

- retired sync invocation exits 2 and names `daily-full`;
- unknown options fail through `argparse`;
- backtest and detector report a missing database without creating it;
- backtest and detector run successfully against the fixture database;
- renderer delegates to `build_daily_review` with the requested paths.

### 6.4 Repository gates

Run:

```bash
python3 -m pytest tests/test_backtest_sector.py tests/test_sector_analysis_data.py tests/test_legacy_script_cli_contracts.py -q
pre-commit run --all-files
python3 -m pytest -q
git diff --check origin/main..HEAD
```

The full-suite comparison must preserve the identity of any pre-existing environment-coupled failures; new failures are not accepted.

## 7. Documentation Changes

Update:

- `README.md`: replace the retired Feishu sync diagram and commands with `daily-full`; keep migrated analysis commands.
- `CLAUDE.md`: move backtest and detector out of the broken-legacy warning; mark `sync_to_local.py` formally retired; keep the canonical database warning.
- `docs/learning/current-duckdb-source.md`: state that the compatibility sync command cannot write data.
- `docs/workflows/daily-review-workflow.md`: retain the supported renderer command.
- `scripts/archive/README.md`: remove the incorrect claim that backtest and detector are archived; record the Git-history locator for the retired writer.

## 8. Ruff Policy

Remove these entries from `ruff.toml`:

- `scripts/backtest_sector.py`
- `scripts/detect_turning_points.py`
- `scripts/sync_to_local.py`
- `scripts/render_daily_review_template.py`

No global rule suppression is added. Intentional import ordering in the renderer receives only the existing repository style of reasoned, line-level `# noqa: E402` annotations.

## 9. Non-Goals

- Do not restore the retired `db/market.duckdb` schema.
- Do not make Feishu a second canonical market-data writer.
- Do not change strategy thresholds or optimize performance results.
- Do not add current sector constituents to historical dates.
- Do not deploy or switch the Workbench runtime.
- Do not merge into `main` without explicit user confirmation.

## 10. Acceptance Criteria

The migration is complete only when all of the following are true:

1. The four scripts have no file-level Ruff exclusion.
2. Ruff 0.11.13 reports zero findings across the repository.
3. All four `--help` commands are side-effect free.
4. `sync_to_local.py` cannot access credentials, network, or DuckDB.
5. Backtest and detector operate against a canonical-schema fixture and the local canonical database in read-only smoke testing.
6. Existing no-look-ahead behavior remains covered and green.
7. Documentation exposes only the canonical write path.
8. No forbidden database, credential, cache, or binary file enters Git.
9. The branch remains unmerged and undeployed until the user approves those actions.

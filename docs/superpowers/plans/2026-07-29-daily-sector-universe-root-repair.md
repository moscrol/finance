# Daily Sector Universe Root Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the daily sector pipeline publish one exact provider universe, synchronize every declared membership with durable receipts, and block release until the published generation is complete without manual rescue.

**Architecture:** Introduce one deep `SectorUniverseStore` module whose interface owns snapshot publication, generation-bound fact writes, member work selection, receipts, and completion audits. Preserve `fact_sector_daily` and `fact_sector_stock_daily` as canonical read views so existing readers cannot accidentally pool generations; the physical generation tables are private implementation details guarded by a static access test. Measure the true provider latency before choosing the nightly batch schedule, then verify three consecutive unattended trading dates before runtime cutover work may proceed.

**Tech Stack:** Python 3.12, DuckDB, pytest, fupanhui read-only source adapter, existing `market_feature_store` CLI and nightly review scripts.

**Approved spec:** `docs/superpowers/specs/2026-07-29-daily-sector-universe-root-repair-design.md`

**Execution dependency:** Complete this plan before `docs/superpowers/plans/2026-07-29-product-runtime-self-use-root-repair.md` reaches its product-canary task.

**Non-execution guards:** Do not hard-code the observed 407-sector denominator,
weaken the exact completion gate, write a live database before the migration
preview passes, merge `main`, or switch the canonical 8792 service. Runtime and
benchmark work is outside this plan.

---

## File Structure

- Create `market_feature_store/sector_universe.py`: the deep module and only production owner of physical universe/generation/receipt tables.
- Create `market_feature_store/sector_schema.sql`: snapshot, universe, receipt, physical generation tables, and canonical published views.
- Modify `market_feature_store/schema.sql`: remove the two legacy physical sector-fact definitions so the deep module owns them once.
- Modify `market_feature_store/db.py`: run the legacy-table migration and schema initialization in one transaction.
- Create `scripts/measure_sector_member_latency.py`: read-only stratified latency probe and deterministic projection receipt.
- Create `scripts/check_sector_fact_access.py`: machine-readable reader/writer inventory and physical-table access guard.
- Modify `market_feature_store/sync/sync_fupanhui_sectors.py`: publish a validated universe through `SectorUniverseStore`.
- Modify `market_feature_store/sync/sync_fupanhui_sector_daily.py`: write sector K-lines against the published generation.
- Modify `market_feature_store/sync/sync_fupanhui_sector_stock_daily.py`: consume fair receipt work and commit exact member results.
- Delete the retired `sync_feishu_sector_daily.py`,
  `sync_feishu_sector_marginal.py`, and `sync_feishu_sector_resonance.py` after
  their CLI and orchestration entry points are removed.
- Modify `market_feature_store/cli.py`: remove the three retired sector Feishu commands.
- Modify `scripts/fast_daily_sync.py`: mark historical membership copy as legacy/degraded and forbid it from satisfying a published snapshot.
- Modify `scripts/check_daily_review_data.py`: use the module completion audit and preserve reduced-table scope isolation.
- Modify `skills/daily-full-review/scripts/run_review_sync.py`: remove the retired
  sector-resonance step and report receipt progress rather than mixed
  `dim_sector` counts.
- Modify `market_feature_store/sync/sync_daily_full.py`: remove the retired
  sector-resonance step and require the exact audit before report generation.
- Create `tests/test_sector_member_latency.py`: pure latency-selection/projection tests.
- Create `tests/test_sector_universe.py`: temporary-DuckDB interface tests for migration, publication, writes, receipts, and audits.
- Create `tests/test_sector_fact_access.py`: static physical-table access test.
- Modify `tests/test_pipeline_p0.py`: exact gate, reduced-scope, and orchestration regressions.
- Modify `tests/test_processing_quality_order.py`: release-order regression using the exact audit.
- Create `docs/verification/sector-fact-access-inventory-2026-07-29.json`: generated production access inventory.
- Create `docs/verification/daily-sector-root-repair-result-2026-07-29.md`: implementation, migration-preview, live-sync, and three-night evidence ledger.

## Interface Decision

`SectorUniverseStore` is the test surface. Callers may use only:

```python
store.publish_snapshot(trade_date, provider_source, sectors, captured_at)
store.published_snapshot(trade_date, provider_source="fupanhui")
store.replace_sector_daily(snapshot_id, rows)
store.next_member_work(snapshot_id, limit, max_attempts)
store.record_member_result(snapshot_id, sector_ts_code, payload)
store.completion_audit(trade_date, declared_tables)
```

The physical tables `fact_sector_daily_generation` and
`fact_sector_stock_daily_generation` never appear outside this module and
`market_feature_store/sector_schema.sql`. The canonical views retain the existing fact
names, so readers receive published-generation semantics without learning the
storage implementation.

### Task 1: Measure the Provider Workload Before Sizing Orchestration

**Files:**
- Create: `scripts/measure_sector_member_latency.py`
- Create: `tests/test_sector_member_latency.py`
- Create: `scripts/check_sector_fact_access.py`
- Create: `tests/test_sector_fact_access.py`
- Create: `docs/verification/sector-fact-access-inventory-2026-07-29.json`
- Create at execution time, do not commit: `/Users/a77/.finance-runtime/verification/sector-member-latency-2026-07-28.json`

- [x] **Step 1: Write failing tests for deterministic stratification and projection**

```python
from scripts.measure_sector_member_latency import (
    project_wall_clock,
    select_probe_sectors,
)


def test_select_probe_sectors_spans_declared_count_distribution():
    sectors = [
        {"ts_code": f"S{i}", "name": f"板块{i}", "stock_count": count}
        for i, count in enumerate((5, 10, 20, 40, 80, 160, 320, 640, 1204))
    ]
    probes = select_probe_sectors(sectors)
    assert [row["stock_count"] for row in probes] == [5, 80, 640, 1204]


def test_project_wall_clock_uses_observed_batch_p95():
    result = project_wall_clock(
        sector_count=407,
        batch_size=10,
        batch_elapsed_seconds=(8.0, 10.0, 12.0, 14.0),
        nightly_window_seconds=7200,
    )
    assert result["batches"] == 41
    assert result["projected_seconds"] == 574.0
    assert result["fits_nightly_window"] is True
```

Add a separate static-inventory test with a temporary source tree:

```python
from scripts.check_sector_fact_access import inventory_sector_fact_access


def test_inventory_classifies_every_public_fact_reference(tmp_path):
    (tmp_path / "reader.py").write_text(
        'SQL = "select * from fact_sector_daily where trade_date = ?"',
        encoding="utf-8",
    )
    (tmp_path / "writer.py").write_text(
        'SQL = "insert into fact_sector_stock_daily values (?, ?, ?)"',
        encoding="utf-8",
    )
    records = inventory_sector_fact_access(tmp_path)
    assert [(row.table, row.mode) for row in records] == [
        ("fact_sector_daily", "read"),
        ("fact_sector_stock_daily", "write"),
    ]
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_sector_member_latency.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_sector_fact_access.py
```

Expected: collection fails because both scripts do not exist.

- [x] **Step 3: Implement the read-only probe and projection**

Create `scripts/measure_sector_member_latency.py` with these public helpers and a CLI that writes only the explicitly supplied output path:

```python
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path

from market_feature_store.sources import fupanhui_source as fs


def _count(row: dict) -> int:
    value = row.get("stock_count")
    return int(value) if isinstance(value, (int, float)) and int(value) > 0 else 0


def select_probe_sectors(sectors: list[dict]) -> list[dict]:
    valid = sorted(
        (row for row in sectors if row.get("ts_code") and _count(row) > 0),
        key=lambda row: (_count(row), str(row["ts_code"])),
    )
    if not valid:
        raise ValueError("provider returned no valid sector counts")
    high = min(len(valid) - 2, (len(valid) * 4) // 5) if len(valid) > 2 else len(valid) - 1
    indexes = (0, len(valid) // 2, high, len(valid) - 1)
    return [valid[index] for index in dict.fromkeys(indexes)]


def select_probe_batches(sectors: list[dict], batch_size: int) -> tuple[tuple[str, ...], ...]:
    valid = sorted(
        (row for row in sectors if row.get("ts_code") and _count(row) > 0),
        key=lambda row: (_count(row), str(row["ts_code"])),
    )
    if not valid or batch_size < 1:
        raise ValueError("probe batches require valid sectors and a positive size")
    centers = (0, len(valid) // 2, (len(valid) * 4) // 5, len(valid) - 1)
    batches: list[tuple[str, ...]] = []
    for center in centers:
        start = min(max(0, center - batch_size // 2), max(0, len(valid) - batch_size))
        batch = tuple(str(row["ts_code"]) for row in valid[start : start + batch_size])
        if batch and batch not in batches:
            batches.append(batch)
    return tuple(batches)


def project_wall_clock(
    *,
    sector_count: int,
    batch_size: int,
    batch_elapsed_seconds: tuple[float, ...],
    nightly_window_seconds: float,
) -> dict[str, object]:
    if sector_count < 1 or batch_size < 1 or not batch_elapsed_seconds:
        raise ValueError("projection inputs must be positive and non-empty")
    ordered = sorted(float(value) for value in batch_elapsed_seconds)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    p95 = ordered[p95_index]
    batches = math.ceil(sector_count / batch_size)
    projected = round(batches * p95, 3)
    return {
        "batches": batches,
        "batch_p50_seconds": round(statistics.median(ordered), 3),
        "batch_p95_seconds": round(p95, 3),
        "projected_seconds": projected,
        "nightly_window_seconds": float(nightly_window_seconds),
        "fits_nightly_window": projected <= float(nightly_window_seconds),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--nightly-window-seconds", type=float, default=7200.0)
    args = parser.parse_args()

    sectors = fs.list_sectors(trade_date=args.trade_date)
    probes = select_probe_sectors(sectors)
    individual = []
    for row in probes:
        started = time.monotonic()
        payload = fs.get_sector_stocks(str(row["ts_code"]), trade_date=args.trade_date)
        elapsed = time.monotonic() - started
        actual = len({item.get("ts_code") for item in payload.get("stocks", ()) if item.get("ts_code")})
        individual.append({
            "sector_ts_code": row["ts_code"],
            "sector_name": row.get("name"),
            "declared_stock_count": _count(row),
            "actual_stock_count": actual,
            "elapsed_seconds": round(elapsed, 3),
            "count_matches": actual == _count(row),
        })

    batch_elapsed = []
    for batch in select_probe_batches(sectors, args.batch_size):
        started = time.monotonic()
        fs.get_sector_stocks_batch(list(batch), trade_date=args.trade_date, batch=args.batch_size)
        batch_elapsed.append(round(time.monotonic() - started, 3))

    receipt = {
        "schema_version": 1,
        "trade_date": args.trade_date,
        "sector_count": len(sectors),
        "batch_size": args.batch_size,
        "individual_probes": individual,
        "projection": project_wall_clock(
            sector_count=len(sectors),
            batch_size=args.batch_size,
            batch_elapsed_seconds=tuple(batch_elapsed),
            nightly_window_seconds=args.nightly_window_seconds,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt["projection"], ensure_ascii=False, sort_keys=True))
    return 0 if all(row["count_matches"] for row in individual) else 2


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `scripts/check_sector_fact_access.py` at the same time. It exposes
`inventory_sector_fact_access(root) -> tuple[AccessRecord, ...]`, walks only
production `.py`/`.sql` files, extracts Python literal SQL with `ast` plus raw
SQL-file text, and records path, line, table, and mode (`read`, `write`, `ddl`,
or `unknown`) for every reference to `fact_sector_daily` or
`fact_sector_stock_daily`. Normalize whitespace/case before classifying
`FROM`/`JOIN`, `INSERT`/`UPDATE`/`DELETE`/`MERGE`, and DDL. Any dynamic or
otherwise unclassified reference remains `unknown`; it is never silently
dropped. The initial `--inventory-only --output ...` mode writes stable sorted
JSON and does not enforce the later allowlist.

- [x] **Step 4: Run unit tests and the live read-only probe**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_sector_member_latency.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/measure_sector_member_latency.py \
  --trade-date 2026-07-28 \
  --output /Users/a77/.finance-runtime/verification/sector-member-latency-2026-07-28.json
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/check_sector_fact_access.py \
  --root /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17 \
  --inventory-only \
  --output docs/verification/sector-fact-access-inventory-2026-07-29.json
```

Expected: tests pass; the probe exits 0; all four individual count matches are
true; and every current production fact reference has an explicit access mode
in the committed baseline inventory. Record the measured projection in the
result ledger. If `fits_nightly_window=false`, keep the exact gate and configure
the receipt-driven batch sync to start earlier; do not introduce unmeasured
extra concurrency or weaken equality.

- [x] **Step 5: Commit the probe**

```bash
git add scripts/measure_sector_member_latency.py tests/test_sector_member_latency.py \
  scripts/check_sector_fact_access.py tests/test_sector_fact_access.py \
  docs/verification/sector-fact-access-inventory-2026-07-29.json
git commit -m "test: inventory and measure sector data access"
```

Task 1 implementation is complete with a live provider-contract concern rather
than a green data receipt: `990220.FP` declared 1,204 members but returned 1,202
unique stock identities. The count gate correctly returned exit 2 and was not
weakened. See
`docs/handoffs/2026-07-29-data-task1-inventory-latency-handoff.md` before
starting Task 2.

### Task 2: Build the Generation Storage and Legacy Migration

**Files:**
- Create: `market_feature_store/sector_universe.py`
- Create: `market_feature_store/sector_schema.sql`
- Modify: `market_feature_store/schema.sql`
- Modify: `market_feature_store/db.py`
- Create: `tests/test_sector_universe.py`
- Modify: `tests/test_pipeline_p0.py`
- Modify: `tests/test_sync_akshare_sw_l1_daily.py`
- Modify: `intelligence/tests/test_agent.py`

- [x] **Step 0: Add the reusable temporary-DuckDB test harness**

At the top of `tests/test_sector_universe.py`, define:

```python
from __future__ import annotations

import duckdb
import pytest

from market_feature_store.sector_universe import SectorUniverseStore


@pytest.fixture
def store_con():
    con = duckdb.connect(":memory:")
    con.execute("create table dim_sector(sector_ts_code text primary key, sector_name text, sw_l1 text, is_active boolean, first_seen_date date, last_seen_date date, source text, updated_at timestamp)")
    SectorUniverseStore.ensure_schema(con)
    try:
        yield con
    finally:
        con.close()


def _publish(store_con, *, captured_at="2026-07-29T10:00:00+08:00", suffix="A"):
    return SectorUniverseStore(store_con).publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=(
            SectorDescriptor(f"990001{suffix}.FP", "MLCC", 2),
            SectorDescriptor(f"990002{suffix}.FP", "6G概念", 1),
        ),
        captured_at=captured_at,
    )


def _daily_row(code: str, pct_chg: float) -> dict[str, object]:
    return {"sector_ts_code": code, "sector_name": "测试板块", "pct_chg": pct_chg, "amount": 100.0, "diff_ratio": 2.0}


def _stock(code: str) -> dict[str, object]:
    return {"ts_code": code, "name": "测试股", "price": 10.0, "pct_chg": 1.0, "amount": 100.0}
```

Task 3 extends this import with `SectorDescriptor`; Task 5 extends it with
`MemberResult`. The helpers are defined now but are first called only after
their corresponding interface exists.

- [x] **Step 1: Write failing migration/interface tests**

Add tests that create the old two fact tables, seed legacy rows, call `ensure_sector_schema`, and assert the old public names become views while rows remain visible with the `legacy` generation:

```python
def test_ensure_sector_schema_migrates_legacy_tables_and_is_idempotent():
    con = duckdb.connect(":memory:")
    con.execute("create table dim_sector(sector_ts_code text primary key, sector_name text, sw_l1 text, is_active boolean, first_seen_date date, last_seen_date date, source text, updated_at timestamp)")
    con.execute("create table fact_sector_daily(trade_date date, sector_ts_code text, sector_name text, sw_l1 text, pct_chg double, amount double, diff_ratio double, strength double, multi_period_resonance boolean, multi_period_source text, multi_period_updated_at timestamp, source text, updated_at timestamp, primary key(trade_date, sector_ts_code))")
    con.execute("create table fact_sector_stock_daily(trade_date date, sector_ts_code text, sector_name text, sw_l1 text, stock_ts_code text, stock_name text, price double, pct_chg double, amount double, source text, updated_at timestamp, primary key(trade_date, sector_ts_code, stock_ts_code))")
    con.execute("insert into fact_sector_daily(trade_date, sector_ts_code, sector_name) values ('2026-07-24', 'OLD.TI', '旧板块')")
    con.execute("insert into fact_sector_stock_daily(trade_date, sector_ts_code, stock_ts_code) values ('2026-07-24', 'OLD.TI', '000001.SZ')")

    SectorUniverseStore.ensure_schema(con)
    SectorUniverseStore.ensure_schema(con)

    assert con.execute("select sector_universe_snapshot_id from fact_sector_daily").fetchall() == [("legacy",)]
    assert con.execute("select sector_universe_snapshot_id from fact_sector_stock_daily").fetchall() == [("legacy",)]
    assert con.execute("select table_type from information_schema.tables where table_name='fact_sector_daily'").fetchone()[0] == "VIEW"
```

- [x] **Step 2: Run the migration test and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_sector_universe.py -k ensure_sector_schema
```

Expected: FAIL because `SectorUniverseStore` and the generation schema do not exist.

- [x] **Step 3: Add the schema tables and canonical views**

Remove the two old physical fact definitions from `market_feature_store/schema.sql`.
Create `market_feature_store/sector_schema.sql`, owned and loaded only by
`SectorUniverseStore`, beginning with:

```sql
CREATE TABLE IF NOT EXISTS ops_sector_universe_snapshot_daily (
    trade_date DATE NOT NULL,
    snapshot_id TEXT NOT NULL,
    provider_source TEXT NOT NULL,
    sector_count INTEGER NOT NULL,
    declared_relationship_count BIGINT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate','published','superseded','rejected')),
    captured_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (trade_date, snapshot_id)
);

CREATE TABLE IF NOT EXISTS fact_sector_universe_daily (
    trade_date DATE NOT NULL,
    snapshot_id TEXT NOT NULL,
    sector_ts_code TEXT NOT NULL,
    sector_name TEXT NOT NULL,
    expected_stock_count INTEGER NOT NULL,
    provider_source TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (trade_date, snapshot_id, sector_ts_code)
);

CREATE TABLE IF NOT EXISTS ops_sector_member_sync_daily (
    trade_date DATE NOT NULL,
    snapshot_id TEXT NOT NULL,
    sector_ts_code TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','success','empty','error')),
    expected_stock_count INTEGER NOT NULL,
    actual_stock_count INTEGER,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error_code TEXT,
    first_attempted_at TIMESTAMPTZ,
    last_attempted_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    PRIMARY KEY (trade_date, snapshot_id, sector_ts_code)
);
```

After these three tables, define `fact_sector_daily_generation` with
`trade_date`, `sector_universe_snapshot_id`, `sector_ts_code`, `sector_name`,
`sw_l1`, `pct_chg`, `amount`, `diff_ratio`, `strength`,
`multi_period_resonance`, `multi_period_source`, `multi_period_updated_at`,
`source`, and `updated_at`. Define `fact_sector_stock_daily_generation` with
`trade_date`, `sector_universe_snapshot_id`, `sector_ts_code`, `sector_name`,
`sw_l1`, `stock_ts_code`, `stock_name`, `price`, `pct_chg`, `amount`,
`pct_chg_3d`, `pct_chg_5d`, `pct_chg_10d`, `pct_chg_20d`, `high_status`,
`high_status_label`, `limit_times`, `fund_flow_1d`, `fund_flow_5d`,
`sw_industry`, `leader_plate`, `leader_sub_plate`, `role_tags_json`, `circ_mv`,
`float_mcap_yi`, `total_mcap_yi`, `free_float_mcap_yi`, `mcap_source`,
`source`, and `updated_at`. Preserve the current SQL types; make the snapshot
field non-null; and include it in each primary key. End the file with public views named
`fact_sector_daily` and `fact_sector_stock_daily` that select the one published
generation for dates with a header and select `legacy` rows only for dates with
no header.

- [x] **Step 4: Implement transactional legacy migration**

In `market_feature_store/sector_universe.py`, add `ensure_schema(con)` that:

```python
@staticmethod
def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("BEGIN TRANSACTION")
    try:
        for public_name, legacy_name in (
            ("fact_sector_daily", "_legacy_fact_sector_daily"),
            ("fact_sector_stock_daily", "_legacy_fact_sector_stock_daily"),
        ):
            row = con.execute(
                "select table_type from information_schema.tables where table_name = ?",
                [public_name],
            ).fetchone()
            if row and row[0] == "BASE TABLE":
                con.execute(f'alter table "{public_name}" rename to "{legacy_name}"')

        con.execute(SECTOR_SCHEMA_PATH.read_text(encoding="utf-8"))
        _copy_legacy_sector_daily(con)
        _copy_legacy_sector_stock_daily(con)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
```

The two copy helpers must enumerate the current columns explicitly, stamp `legacy`, use `ON CONFLICT DO NOTHING`, drop the temporary legacy tables only after successful copy, and recreate the three existing indexes on each generation table.

- [x] **Step 5: Wire `init_db` and stop tests from executing raw schema text**

Change `market_feature_store/db.py::init_db` to execute the non-sector schema
and then call `SectorUniverseStore.ensure_schema(con)` on the same connection.
Change the three raw-schema test helpers to call `init_db(con)` so production
migration behavior is the test behavior.

- [x] **Step 6: Run focused tests and commit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_sector_universe.py \
  tests/test_pipeline_p0.py \
  tests/test_sync_akshare_sw_l1_daily.py \
  intelligence/tests/test_agent.py
```

Expected: PASS with no production DuckDB access.

```bash
git add market_feature_store/schema.sql market_feature_store/sector_schema.sql market_feature_store/db.py \
  market_feature_store/sector_universe.py tests/test_sector_universe.py \
  tests/test_pipeline_p0.py tests/test_sync_akshare_sw_l1_daily.py \
  intelligence/tests/test_agent.py
git commit -m "feat: add versioned sector universe storage"
```

Task 2 notes recorded during execution:

- Temporary in-memory tests are not sufficient evidence for this migration. A
  rehearsal on a disposable copy of the real 3.2 GB production database exposed
  a defect the memory tests missed: the five explicit indexes that
  `schema.sql` created on the two fact tables make DuckDB refuse
  `ALTER TABLE ... RENAME` with `DependencyException`. `ensure_schema` now drops
  those dependent indexes inside the same transaction before renaming, the
  generation tables carry equivalent indexes, and a rollback test asserts the
  dropped index is restored. Two permanent regression tests cover both.
- Legacy column order differs from `schema.sql` because `multi_period_*`,
  `pct_chg_3d`, and the market-cap columns were added by historical `ALTER`
  statements. The copy maps by column name and fills absent columns with NULL,
  never by ordinal position.
- Migration rehearsal on the production copy: 95,813 sector rows and 10,599,868
  member rows migrated with exact row conservation, 61.9s for the first call and
  0.0s for the idempotent replay, no leftover `_legacy_*` tables, and zero
  non-`legacy` generation rows. Representative reader queries against the
  migrated copy returned the expected shapes through the new views. The copy was
  deleted afterwards; production was never opened for writing.
- `skills/theme-fermentation-tracer/scripts/selftest.py` also built its sample
  database from raw schema text and was moved onto `init_db`; its 11 assertions
  still pass end to end.

### Task 3: Publish One Validated Universe and Own Active Identities

**Files:**
- Modify: `market_feature_store/sector_universe.py`
- Modify: `market_feature_store/sync/sync_fupanhui_sectors.py`
- Modify: `tests/test_sector_universe.py`

- [x] **Step 1: Write failing publication tests**

Cover canonical hashing, idempotent replay, invalid/partial list rejection, 95% adjacent-name continuity, active `.FP` upsert, stale `.TI` retirement only after publish, and the transactional single-published invariant.

```python
def test_publish_snapshot_retires_absent_provider_rows_only_after_validation(store_con):
    store_con.execute("insert into dim_sector values ('OLD.TI','旧板块',null,true,'2026-07-24','2026-07-24','fupanhui',now())")
    store = SectorUniverseStore(store_con)
    published = store.publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=(SectorDescriptor("990001.FP", "MLCC", 27),),
        captured_at="2026-07-29T10:00:00+08:00",
    )
    assert published.sector_count == 1
    assert store_con.execute("select is_active from dim_sector where sector_ts_code='OLD.TI'").fetchone() == (False,)
    assert store_con.execute("select count(*) from ops_sector_universe_snapshot_daily where status='published'").fetchone() == (1,)
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_sector_universe.py -k publish
```

Expected: FAIL because publication methods are missing.

- [x] **Step 3: Implement the publication interface**

Add immutable `SectorDescriptor` and `PublishedSectorSnapshot` dataclasses. Canonicalize sorted `(code,name,count,provider,date)` rows, hash compact sorted JSON, insert candidate rows, assert continuity, demote the prior published header, promote the candidate, assert exactly one published header, update `dim_sector`, and seed one pending receipt per universe row in one transaction. Invalid input raises `SectorUniverseValidationError` before any active flag changes.

- [x] **Step 4: Adapt the provider synchronizer**

Change `sync_dim_sector()` to convert every provider row into `SectorDescriptor`, preserving `stock_count`, and return `snapshot_id`, `sector_count`, and `declared_relationship_count`. It must no longer directly upsert active flags.

- [x] **Step 5: Run tests and commit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_sector_universe.py \
  tests/test_pipeline_p0.py -k 'sector or sync_plan'
```

Expected: PASS.

```bash
git add market_feature_store/sector_universe.py \
  market_feature_store/sync/sync_fupanhui_sectors.py \
  tests/test_sector_universe.py
git commit -m "feat: publish exact daily sector universe"
```

Task 3 completed in `3e7dff99`. In addition to the planned publication
contract, the implementation fails closed when the canonical provider trade
date is unavailable instead of substituting the local calendar date, and an
idempotent replay verifies the persisted universe rows before trusting the
header. A below-95% candidate commits only a `rejected` audit generation: it
does not create member receipts or change active identities. The known
`1,204/1,202` member discrepancy remains unresolved and was not bypassed; no
live provider run or production database write occurred in this task.

### Task 4: Bind Sector Daily Facts to the Published Generation and Retire Sector Feishu

**Files:**
- Modify: `market_feature_store/sector_universe.py`
- Modify: `market_feature_store/sync/sync_fupanhui_sector_daily.py`
- Modify: `market_feature_store/cli.py`
- Modify: `market_feature_store/sync/sync_daily_full.py`
- Modify: `skills/daily-full-review/scripts/run_review_sync.py`
- Delete: `market_feature_store/sync/sync_feishu_sector_daily.py`
- Delete: `market_feature_store/sync/sync_feishu_sector_marginal.py`
- Delete: `market_feature_store/sync/sync_feishu_sector_resonance.py`
- Modify: `skills/daily-full-review/SKILL.md`
- Modify: `skills/market-overview/SKILL.md`
- Modify: `skills/duckdb-backfill/SKILL.md`
- Modify: `tests/test_sector_universe.py`
- Modify: `tests/test_sector_daily_range_coverage.py`
- Modify: `tests/test_pipeline_p0.py`

- [x] **Step 1: Write failing generation and retired-source tests**

```python
def test_public_sector_daily_view_exposes_only_published_generation(store_con):
    store = SectorUniverseStore(store_con)
    published_a = _publish(store_con, suffix="A")
    published_b = _publish(store_con, captured_at="2026-07-29T10:05:00+08:00", suffix="B")
    store.replace_sector_daily(published_a.snapshot_id, (_daily_row("990001A.FP", 1.0),))
    store.replace_sector_daily(published_b.snapshot_id, (_daily_row("990001B.FP", 2.0),))
    assert store_con.execute("select pct_chg, sector_universe_snapshot_id from fact_sector_daily").fetchall() == [(2.0, published_b.snapshot_id)]
    assert store_con.execute("select count(*) from fact_sector_daily_generation").fetchone() == (2,)
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_sector_universe.py -k sector_daily
```

Expected: FAIL because generation-bound writes are missing.

- [x] **Step 3: Implement generation-bound daily replacement**

`replace_sector_daily(snapshot_id, rows)` validates that every row code belongs
to the published snapshot, deletes only the matching date/snapshot generation,
inserts the complete batch, and rolls back on any foreign identity. Do not add
an enrichment interface without a current authoritative producer.

- [x] **Step 4: Route the authoritative writer and retire sector Feishu**

`sync_fupanhui_sector_daily` loads the published snapshot, requests only its
codes, validates served dates, and calls `replace_sector_daily`. Remove the
three sector Feishu CLI commands and both nightly invocations, then delete the
orphaned modules. Add a regression asserting the nightly plan and CLI no longer
expose `sync-sector-resonance`, `sync-sector-marginal`, or
`sync-sector-daily-metrics`.

- [x] **Step 5: Run focused regressions and commit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_sector_universe.py \
  tests/test_sector_daily_range_coverage.py \
  tests/test_pipeline_p0.py
```

Expected: PASS.

```bash
git add market_feature_store/sector_universe.py \
  market_feature_store/sync/sync_fupanhui_sector_daily.py \
  market_feature_store/cli.py market_feature_store/sync/sync_daily_full.py \
  skills/daily-full-review/scripts/run_review_sync.py \
  skills/daily-full-review/SKILL.md skills/market-overview/SKILL.md \
  skills/duckdb-backfill/SKILL.md tests/test_sector_universe.py \
  tests/test_sector_daily_range_coverage.py tests/test_pipeline_p0.py
git add -u market_feature_store/sync/sync_feishu_sector_daily.py \
  market_feature_store/sync/sync_feishu_sector_marginal.py \
  market_feature_store/sync/sync_feishu_sector_resonance.py
git commit -m "feat: bind sector daily facts to universe generation"
```

Task 4 completed in `e74ca793`. The public daily view now exposes only the
published universe generation, while physical generations remain available for
audit. `sync_fupanhui_sector_daily` resolves the canonical target date, requests
exactly the published identities, rejects missing/foreign/incomplete responses,
and commits through `replace_sector_daily`. Range sync resolves a separate
published generation for every date and no longer falls back to legacy identity
reads. The three retired sector-level Feishu modules, CLI commands, and nightly
steps were removed; unrelated Feishu owners and historical run logs were not
rewritten.

Verification at the implementation commit: 51 focused tests and 131 adjacent
data-root tests passed; changed-file Ruff, compileall, CLI help, static retired-
source search, and `git diff --check` passed. The full suite reported 3,488
passed, 3 skipped, and the same 11 pre-existing subconscious/userspace
environment failures. No live provider call or production database write
occurred. The `1,204/1,202` member discrepancy remains an explicit Task 5 red
receipt and was not bypassed.

### Task 5: Replace Invisible Missing Work with Durable Member Receipts

**Files:**
- Modify: `market_feature_store/sector_universe.py`
- Modify: `market_feature_store/sync/sync_fupanhui_sector_stock_daily.py`
- Modify: `market_feature_store/cli.py`
- Modify: `scripts/fast_daily_sync.py`
- Modify: `tests/test_sector_universe.py`

- [x] **Step 1: Write failing starvation, count, and atomicity tests**

```python
def test_error_receipt_does_not_starve_later_sector(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    first = store.next_member_work(published.snapshot_id, limit=1, max_attempts=3)
    store.record_member_result(
        published.snapshot_id,
        first[0].sector_ts_code,
        MemberResult.error("provider_timeout"),
    )
    second = store.next_member_work(published.snapshot_id, limit=1, max_attempts=3)
    assert second[0].sector_ts_code != first[0].sector_ts_code


def test_count_mismatch_publishes_no_member_rows(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    result = store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(served_date="2026-07-28", stocks=(_stock("000001.SZ"),)),
    )
    assert result.status == "error"
    assert result.last_error_code == "member_count_mismatch"
    assert store_con.execute("select count(*) from fact_sector_stock_daily_generation").fetchone() == (0,)
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_sector_universe.py -k 'member or starvation'
```

Expected: FAIL because member receipt methods are missing.

- [x] **Step 3: Implement fair work selection and result commits**

`next_member_work` orders `pending` before retriable `empty/error`, then by `attempt_count`, null/old `last_attempted_at`, and code. `record_member_result` validates snapshot, identity, served date, unique non-empty stock codes, and exact declared count; on success it replaces only that sector/snapshot generation and commits the receipt in the same transaction. Empty/error attempts increment and persist stable categories without raw provider text.

- [x] **Step 4: Adapt the sync and CLI**

Replace `_load_sector_dim`, physical-order slicing, and date-only done detection with `published_snapshot` plus `next_member_work`. Preserve provider batch fetch and market-cap enrichment, but feed each normalized result to `record_member_result`. Return status counts, exact success denominator, relationship totals, and snapshot ID. CLI exit code is 0 only when the requested batch itself executes; completion remains a separate audit.

- [x] **Step 5: Make historical fast copy explicitly ineligible**

`fast_sector_stocks` must refuse to write when a published header exists for the target date. For a legacy-only historical date it may write `sector_universe_snapshot_id='legacy'`, but it returns `degraded_legacy_copy` and never creates a success receipt.

- [x] **Step 6: Run focused tests and commit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_sector_universe.py \
  tests/test_pipeline_p0.py -k 'sector or stock_coverage'
```

Expected: PASS.

```bash
git add market_feature_store/sector_universe.py \
  market_feature_store/sync/sync_fupanhui_sector_stock_daily.py \
  market_feature_store/cli.py scripts/fast_daily_sync.py \
  tests/test_sector_universe.py
git commit -m "feat: persist exact sector member receipts"
```

### Task 6: Make Nightly Orchestration Consume Receipt Progress

**Files:**
- Modify: `skills/daily-full-review/scripts/run_review_sync.py`
- Modify: `market_feature_store/sync/sync_daily_full.py`
- Modify: `tests/test_pipeline_p0.py`
- Modify: `tests/test_processing_quality_order.py`

- [x] **Step 1: Write failing orchestration tests**

Add tests proving stale `.TI` rows never enter the denominator, an error receipt advances the next loop, progress is reported as `success/pending/empty/error` against one snapshot, and loop exhaustion returns `partial` rather than `ok`.

- [x] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_pipeline_p0.py -k sync_sector_stocks
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_processing_quality_order.py -k sector
```

Expected: FAIL because `_sectors_done` still reads mixed dimension/fact counts.

- [x] **Step 3: Replace count polling with completion-audit polling**

Load `SectorUniverseStore.completion_audit(
trade_date, declared_tables=frozenset({"fact_sector_daily",
"fact_sector_stock_daily"}))` before each loop. Stop only when
`audit.complete` is true; otherwise call the CLI with the measured batch size
and log `snapshot_id`, `success/total`, pending, retriable errors, and attempts.
A bounded loop that ends incomplete returns `status='partial'` with the audit
payload.

- [x] **Step 4: Require exact audit before report generation**

`sync_daily_full.run_daily_full` and `run_review_sync.run_release_steps` must require the same exact audit in addition to existing same-day/cross-day gates. Do not create an independent formula.

- [x] **Step 5: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_pipeline_p0.py \
  tests/test_processing_quality_order.py
git add skills/daily-full-review/scripts/run_review_sync.py \
  market_feature_store/sync/sync_daily_full.py \
  tests/test_pipeline_p0.py tests/test_processing_quality_order.py
git commit -m "fix: drive nightly sector sync from receipts"
```

### Task 7: Install the Exact Gate and the Physical-Storage Access Guard

**Files:**
- Modify: `market_feature_store/sector_universe.py`
- Modify: `scripts/check_daily_review_data.py`
- Modify: `scripts/check_sector_fact_access.py`
- Modify: `tests/test_sector_fact_access.py`
- Modify: `tests/test_pipeline_p0.py`
- Modify: `docs/verification/sector-fact-access-inventory-2026-07-29.json`

- [x] **Step 1: Write failing exact-gate tests**

Cover 406/407 failure despite 100% name continuity, per-sector count mismatch, facts outside the snapshot, legacy/superseded rows, null critical fields, and reduced table scope that does not declare sector tables.

- [x] **Step 2: Run the tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_pipeline_p0.py -k 'sector and gate'
```

Expected: FAIL because the current gate can ignore never-populated sectors.

- [x] **Step 3: Implement one completion audit**

`SectorUniverseStore.completion_audit` returns an immutable result containing snapshot ID, universe count, successful receipts, status counts, declared/actual relationships, daily-fact identity equality, member-fact identity containment, critical-null counts, adjacent-name continuity, and `complete`. `scripts/check_daily_review_data.py` only formats that result; it must not recompute coverage from `dim_sector`.

- [x] **Step 4: Upgrade the frozen inventory into a static access guard**

Extend `scripts/check_sector_fact_access.py` to scan the new physical names as
well as the two canonical public views. Enforcement rejects unknown access,
all writes to either public view, and either physical generation-table name
outside `market_feature_store/sector_universe.py` and
`market_feature_store/sector_schema.sql`. The SQL file is DDL-only; the Python
module is the sole physical reader/writer/migrator. Keep the pre-change
inventory in the JSON under `baseline`; write the current classified inventory
under `candidate` so every original writer is visibly accounted for. Exclude
tests, `scripts/archive`, `.git`, and runtime artifacts.

- [x] **Step 5: Generate and verify the inventory**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/check_sector_fact_access.py \
  --root /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17 \
  --output docs/verification/sector-fact-access-inventory-2026-07-29.json
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_sector_fact_access.py tests/test_pipeline_p0.py
```

Expected: exit 0; the inventory has no unauthorized physical-table reference; tests pass.

- [x] **Step 6: Commit the gate and inventory**

```bash
git add market_feature_store/sector_universe.py scripts/check_daily_review_data.py \
  scripts/check_sector_fact_access.py tests/test_sector_fact_access.py \
  tests/test_pipeline_p0.py \
  docs/verification/sector-fact-access-inventory-2026-07-29.json
git commit -m "feat: gate exact published sector coverage"
```

### Task 8: Run Regression, Migration Preview, and One Complete Live Sync

**Files:**
- Create: `docs/verification/daily-sector-root-repair-result-2026-07-29.md`
- Do not commit: DuckDB files, provider payloads, run logs, cookies, headers, or latency JSON.

- [x] **Step 1: Run all focused and adjacent tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_sector_member_latency.py \
  tests/test_sector_universe.py \
  tests/test_sector_fact_access.py \
  tests/test_pipeline_p0.py \
  tests/test_processing_quality_order.py \
  tests/test_sector_daily_range_coverage.py \
  tests/test_sync_akshare_sw_l1_daily.py \
  intelligence/tests/test_agent.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  market_feature_store/sector_universe.py market_feature_store/db.py \
  market_feature_store/cli.py market_feature_store/sync/sync_fupanhui_sectors.py \
  market_feature_store/sync/sync_fupanhui_sector_daily.py \
  market_feature_store/sync/sync_fupanhui_sector_stock_daily.py \
  market_feature_store/sync/sync_daily_full.py \
  skills/daily-full-review/scripts/run_review_sync.py \
  scripts/fast_daily_sync.py scripts/check_daily_review_data.py \
  scripts/check_sector_fact_access.py scripts/measure_sector_member_latency.py \
  tests/test_sector_universe.py tests/test_sector_fact_access.py \
  tests/test_sector_member_latency.py
git diff --check
```

Expected: all tests pass, Ruff passes, and diff check is clean.

- [x] **Step 2: Run a read-only migration preview against the production DB**

Add a `--preview` CLI path that opens production DuckDB read-only and reports legacy row counts, predicted `.TI` retirements, current provider denominator, and target snapshot hash without DDL or writes. Run it and record only aggregate counts and hashes in the result ledger.

- [ ] **Step 3: Apply through the normal entry point and execute one complete target-date sync**

Use a copied disposable database first. After its exact gate passes, run the normal `sync-sectors`, `sync-sector-daily`, and receipt-driven `sync-sector-stocks` commands against the configured production DB. Never edit DuckDB manually. The result must show one published snapshot, exact per-sector counts, no outside identities, and zero pending/error receipts before report generation.

- [x] **Step 4: Write and commit the implementation receipt**

The result document records commit IDs, test counts, latency projection, migration preview aggregates, live snapshot ID, universe count, declared/actual relationship totals, receipt status counts, and unchanged safety boundaries. It must distinguish tests from live verification.

```bash
git add docs/verification/daily-sector-root-repair-result-2026-07-29.md
git commit -m "docs: verify daily sector root repair"
```

### Task 9: Prove Three Consecutive Unattended Trading Dates

**Files:**
- Modify after each real run: `docs/verification/daily-sector-root-repair-result-2026-07-29.md`
- Read only: `docs/learning/runlog.md` and private runtime logs.

- [ ] **Step 1: Execute the canonical nightly entry point on three consecutive real trading dates**

For each date, run only the normal nightly entry point. Do not patch files, manually insert rows, or rerun a failed module into a green artifact. A failed or manually rescued date remains recorded and restarts the streak.

- [ ] **Step 2: Verify each date independently**

For every date require: one published snapshot, exact universe/daily/member identity sets, all receipts successful, declared relationships equal actual distinct relationships, all existing daily gates green, report generated, and no manual rescue.

- [ ] **Step 3: Record the three-date readiness receipt**

Append a compact table with trade date, snapshot ID, sector denominator, relationship total, nightly start/end, gate result, and manual-rescue flag. Mark `data_foundation_cutover_eligible=true` only after three consecutive rows satisfy every condition.

- [ ] **Step 4: Commit only the receipt update**

```bash
git add docs/verification/daily-sector-root-repair-result-2026-07-29.md
git commit -m "docs: prove unattended sector data readiness"
```

## Completion Gate

This plan is complete only when:

1. the latency receipt is real and count-matched;
2. all sector facts are generation-bound behind canonical published views;
3. physical storage is reachable only through `SectorUniverseStore`;
4. 407 is never hard-coded as the denominator;
5. every provider-declared sector has an exact success receipt;
6. existing data-quality gates remain green;
7. three consecutive real trading dates complete without manual rescue;
8. no DuckDB, payload, key, log, cookie, model, cache, or virtual environment is committed;
9. `main` and canonical 8792 remain untouched.

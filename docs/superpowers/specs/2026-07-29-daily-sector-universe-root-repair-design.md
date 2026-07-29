# Daily Sector Universe Root Repair Design

Date: 2026-07-29

Status: `approved_direction; written_spec_review_pending`

Branch: `feat/agent-runtime-backends-verify`

## 1. Objective

Make the daily sector and sector-member pipeline prove that it processed the
provider's complete current universe without developer rescue. A green gate
must mean that every sector declared by the frozen provider list has a terminal
member-sync receipt and the persisted member count matches the provider's own
declaration.

This design fixes the producer and the gate together. Replacing one gate query
while leaving the producer starved is explicitly out of scope as a solution.

## 2. Verified Failure

The 2026-07-28 database contains:

- 407 current `.FP` identities, all last seen 2026-07-28;
- 223 obsolete `.TI` identities, last seen 2026-07-24 but still active;
- 407 sector-daily rows;
- sector-member rows for only 117 of the 407 current identities.

The first 60 physical `dim_sector` rows are obsolete `.TI` identities. The
member synchronizer repeatedly selects the first 60 missing identities, does
not persist empty/error attempts, and therefore retries the same obsolete page
for all 20 orchestration loops. It never reaches the current `.FP` universe.

The provider list is an exact contract, not a heuristic denominator:

- 407/407 current identities declare a positive `stock_count`;
- declared counts range from 5 to 1,204;
- total declared sector-member relationships are 53,316;
- MLCC, 3D打印, and 6G概念 detail responses exactly matched their declared
  counts (27, 139, and 97).

The existing uncommitted gate change reports `COMPLETE` by ignoring 290 current
sectors that never had historical `.FP` member rows. That is a false green.

Authoritative evidence:

`docs/verification/daily-data-sector-universe-audit-2026-07-29.md`

## 3. Scope

This slice owns:

1. a daily immutable sector-universe snapshot;
2. safe current-identity activation and stale-identity retirement;
3. a durable per-date/per-sector member-sync attempt ledger;
4. member synchronization driven only by the frozen current universe;
5. an exact declared-versus-actual completion gate;
6. adjacent-day name continuity as a secondary integrity gate;
7. phase/table isolation for reduced checks and tests;
8. orchestration summaries that report progress against the frozen universe.

## 4. Non-Goals

- Do not change financial-agent runtime behavior.
- Do not merge `main`, switch 8792, or commit a DuckDB file.
- Do not relax field-null, stock-universe, same-day, cross-day, or report gates.
- Do not treat a copied historical membership snapshot as successful current
  membership synchronization.
- Do not hard-code 407; the denominator comes from the validated daily
  provider snapshot.
- Do not crawl all sectors during unit tests; use deterministic fixtures.

## 5. Data Model

### 5.1 `ops_sector_universe_snapshot_daily`

One durable header per validated provider response. Its identity, source
counts, and capture provenance are immutable; only the lifecycle status may
transition from `candidate` to `published`, `superseded`, or `rejected`:

| Field | Contract |
|---|---|
| `trade_date` | canonical target trading day |
| `snapshot_id` | SHA-256 of sorted canonical snapshot rows |
| `provider_source` | `fupanhui` for this adapter |
| `sector_count` | number of unique declared sector identities |
| `declared_relationship_count` | sum of positive declared member counts |
| `status` | `candidate`, `published`, `superseded`, or `rejected` |
| `captured_at` | timezone-aware capture time |

Primary key: `(trade_date, snapshot_id)`. At most one snapshot per trade date
and provider may be `published`.

The implementation builds canonical rows in memory before it writes a header.
A candidate is publishable only when the response is non-empty; all codes and
identity rows are unique; names are non-empty; member counts are positive
integers; and, when a prior adjacent-day published snapshot exists, normalized
name continuity meets the 95% integrity floor.

Re-observing the same `snapshot_id` is idempotent. A different valid same-day
snapshot never overwrites rows: one transaction inserts its immutable rows,
marks it `published`, and marks the prior published generation `superseded`.
Any downstream receipt and fact must bind the newly published `snapshot_id`.
An invalid or low-continuity candidate is recorded as `rejected` and leaves the
prior published snapshot and active identities unchanged.

### 5.2 `fact_sector_universe_daily`

One immutable row per provider-declared sector within a snapshot generation:

| Field | Contract |
|---|---|
| `trade_date` | canonical target trading day |
| `sector_ts_code` | provider identity; part of primary key |
| `sector_name` | normalized non-empty display name |
| `expected_stock_count` | positive provider-declared distinct member count |
| `provider_source` | `fupanhui` for this adapter |
| `snapshot_id` | immutable snapshot-header foreign key |
| `captured_at` | timezone-aware capture time |

Primary key: `(trade_date, snapshot_id, sector_ts_code)`.

Rows are append-only snapshot generations. Consumers select rows by joining the
single `published` header, never by taking all rows for a date or by guessing
the latest capture timestamp.

### 5.3 `ops_sector_member_sync_daily`

One durable operational receipt per
`(trade_date, snapshot_id, sector_ts_code)`:

| Field | Contract |
|---|---|
| `snapshot_id` | must match the frozen universe snapshot |
| `status` | `pending`, `success`, `empty`, or `error` |
| `expected_stock_count` | copied from the universe row |
| `actual_stock_count` | distinct persisted stock identities, nullable pre-run |
| `attempt_count` | monotonic positive count after an attempt |
| `last_error_code` | stable non-secret category, never raw response text |
| `first_attempted_at` / `last_attempted_at` | timezone-aware timestamps |
| `completed_at` | set only for exact success |

`success` requires `actual_stock_count == expected_stock_count`. An empty or
count-mismatched response is terminal for that attempt but remains eligible for
a bounded retry. It is never silently promoted to success.

Every newly published `fact_sector_stock_daily` row carries its
`sector_universe_snapshot_id`, and its generation-aware identity includes
`(trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code)`.
Retries may replace only rows inside the same snapshot/sector generation;
superseding a snapshot never deletes an older generation. Legacy rows without
that lineage may remain for history, but they cannot satisfy the exact
current-day gate.

## 6. Snapshot-Owned Active Identities

`dim_sector` remains the cross-day lookup/history table. It is not the daily
work queue.

After and only after a complete universe snapshot commits:

1. upsert all current identities and set `last_seen_date=trade_date`;
2. set those identities active;
3. mark previously active identities from the same provider inactive when they
   are absent from the complete snapshot;
4. preserve historical rows and their first/last seen dates.

If list retrieval, validation, hashing, or snapshot commit fails, no active flag
changes. This prevents a partial provider response from retiring valid sectors.

All daily K-line and member consumers load identities from the single published
snapshot joined to `fact_sector_universe_daily`, not from all `dim_sector` rows.

## 7. Starvation-Free Member Synchronization

The member synchronizer starts by ensuring a receipt row exists for every
identity in the frozen snapshot. It selects work with a deterministic fairness
order:

1. `pending` before retriable `empty/error`;
2. lower `attempt_count` first;
3. oldest `last_attempted_at` first;
4. `sector_ts_code` as the stable final key.

`--limit` limits attempts, not the universe and not success rows. Every attempt
updates its receipt even if the provider returns empty or errors, so one bad
sector cannot remain the invisible first page forever.

For each sector:

1. fetch the member detail for the target date;
2. reject a mismatched served date or identity;
3. canonicalize and deduplicate non-empty stock identities;
4. compare the distinct count with `expected_stock_count`;
5. transactionally replace only that sector/date/snapshot generation's fact
   rows, stamp the active `snapshot_id`, and mark its bound receipt success only
   on exact equality;
6. otherwise leave no newly published partial sector fact and record
   `empty/error` with a stable category.

A historical membership copy may remain an explicitly degraded provisional
artifact, but it cannot write a success receipt and cannot pass the release
gate.

## 8. Completion Gate

The production data phase runs sector checks only when the declared table scope
contains the sector tables. Reduced SW-L1 fixtures do not acquire undeclared
sector dependencies.

For a production target date, the sector gate requires:

1. exactly one published universe snapshot and one `snapshot_id`;
2. current `fact_sector_daily` identities equal the snapshot identity set;
3. terminal `success` receipts for every snapshot identity;
4. each receipt's actual count equals its declared count;
5. persisted distinct member count per sector equals the receipt;
6. every current-day member fact used by the gate carries the published
   snapshot ID, and none belongs to an identity outside that snapshot;
7. existing critical field-null checks remain green;
8. adjacent-day normalized sector-name recall is at least 95%.

The exact membership rules are hard failures. Name continuity is also a hard
failure because a mass rename/disappearance can indicate a partial list; its
diagnostic is reported separately so it cannot be mistaken for member
completion.

Output must include the denominator, success receipts, missing/error counts,
declared relationship total, actual relationship total, and snapshot ID.

## 9. Orchestration

`run_review_sync.sync_sector_stocks()` reads the frozen universe and receipt
ledger for its progress denominator. It stops when either:

- all receipts are exact success; or
- its bounded orchestration budget ends.

Budget exhaustion returns `partial` with remaining identities and status
counts. It never reports `0/630` from a mixed historical dimension and never
restarts from an unrecorded first page.

The nightly pipeline may proceed to report generation only after both the exact
member receipt gate and all existing data gates pass.

## 10. Error Handling

- Partial/invalid universe list: fail closed; retain prior active identity
  state; write no complete daily snapshot.
- Member timeout/provider error: record stable error receipt; preserve no new
  partial fact rows for that sector.
- Count mismatch: record `member_count_mismatch`; include expected/actual
  integers; do not publish success.
- Snapshot ID mismatch: retain old receipts as audit history, ignore them for
  completion, and initialize receipts bound to the newly published generation.
- Database transaction error: roll back sector facts and receipt transition
  together.
- Duplicate stock identities: deduplicate before counting, and expose a
  diagnostic count.

No error path logs credentials, cookies, raw provider payloads, or private
headers.

## 11. Test Contract

Deterministic tests must cover:

1. complete snapshot atomically upserts current identities and retires absent
   same-provider identities;
2. failed/partial list retrieval retires nothing;
3. historical dimension identities never enter a current-date work queue;
4. an empty/error first item gets a receipt and does not starve later items;
5. retry ordering is fair and bounded;
6. exact declared/actual equality marks success;
7. empty, duplicate, served-date mismatch, and count mismatch stay non-success;
8. fact rows and receipt transition roll back together;
9. gate fails at 406/407 even when adjacent names are 100%;
10. gate fails on per-sector count mismatch;
11. gate rejects facts outside the snapshot;
12. legacy or superseded-snapshot facts cannot satisfy the current gate;
13. a different valid same-day generation supersedes atomically without
    deleting old universe/member generations or pooling old receipts;
14. name continuity below 95% rejects publication and fails independently;
15. a reduced table scope skips sector-only checks;
16. existing stock coverage and critical-null gates remain unchanged;
17. run-log progress uses snapshot totals and receipt status counts.

One temporary DuckDB integration fixture must reproduce the stale-TI/FP
starvation shape without using the production database.

## 12. Verification and Release Sequence

1. Implement and test only in a clean isolated worktree.
2. Run focused unit/integration suites and existing daily-pipeline gates.
3. Run a read-only migration preview against the production database and record
   the predicted active retirements and current snapshot denominator.
4. Apply schema/data changes through the normal migration/sync entry point; do
   not edit DuckDB manually.
5. Execute one bounded current-date sector sync and retain its receipt summary.
6. Require three consecutive real trading-date nightly runs to pass unattended
   before the data foundation is eligible for canonical cutover. A failed or
   manually repaired night restarts this three-date readiness streak but
   remains visible in the operational ledger.

No database, receipt payload, or log is committed to Git.

# Daily Data Sector-Universe Audit

Date: 2026-07-29

Status: `root_cause_confirmed; implementation_not_started`

## Why this audit exists

An uncommitted change in the dirty primary workspace makes
`check_daily_review_data.py 2026-07-28 --phase data` print `RESULT: COMPLETE` by
replacing exact `dim_sector` coverage with adjacent-day sector-name continuity
and by ignoring sectors that have never had member rows.

The adjacent-name diagnosis correctly identifies one false-positive source,
but the resulting green gate is itself false. It hides an upstream scheduler
starvation bug and a real missing-membership surface.

No repository or database was modified by this audit.

## Reproduced data state

For 2026-07-28:

- `fact_sector_daily`: 407 sectors, all source `fupanhui`, all `.FP` codes;
- adjacent-name continuity from 2026-07-27: 406/406 = 100%;
- `dim_sector`: 630 rows still marked active;
  - 407 `.FP`, all `last_seen_date=2026-07-28`;
  - 223 `.TI`, all `last_seen_date=2026-07-24`;
- `fact_sector_stock_daily`: 17,855 rows across only 117 `.FP` sectors;
- 290 of the 407 current `.FP` sectors have no 2026-07-28 member rows.

The current candidate gate ignores all 290 because none has historical member
rows under its `.FP` code. That is why it reports `COMPLETE` despite the
membership surface covering only 117/407 current sectors.

## Exact starvation mechanism

1. `sync_dim_sector()` upserts the latest sector list but never marks previously
   active rows absent from a successful current snapshot as inactive. The 223
   obsolete `.TI` rows therefore remain active after the provider moved to
   `.FP` identities.
2. `sync_fupanhui_sector_stock_daily._load_sector_dim()` loads all 630 rows,
   without a current-snapshot filter or deterministic progress cursor.
3. `sync_fact_sector_stock_daily(..., only_missing=True, limit=60)` takes the
   first 60 missing rows. Empty/error results are not persisted as attempts, so
   they remain first on the next invocation.
4. `run_review_sync.sync_sector_stocks()` invokes that same limited command up
   to 20 times and uses all 630 `dim_sector` rows as its denominator.

In the current database, the first 60 `SELECT ... FROM dim_sector LIMIT 60`
rows are all stale `.TI` identities, and none has a 2026-07-28 member row.
Consequently every loop retries the same obsolete 60 and never reaches the new
`.FP` universe. This explains the run-log result `0/630 sectors after 20 loops`.

The later fallback copied a 2026-07-24 membership snapshot for 117 `.FP`
sectors and enriched it with 2026-07-28 stock data; it did not prove that all
current sectors were attempted.

## Retrieval availability was independently proved

The current sector-list response is itself an exact coverage contract. A
read-only `list_sectors(2026-07-28)` call returned 407 identities, and every
identity included a positive `stock_count`:

- positive counts: 407/407;
- zero counts: 0;
- minimum declared members: 5;
- maximum declared members: 1,204;
- sum of declared sector-member relationships: 53,316.

Read-only calls to the member endpoint returned:

| Sector | Code | Returned members |
|---|---|---:|
| MLCC | `990001.FP` | 27 |
| 3D打印 | `990002.FP` | 139 |
| 6G概念 | `990003.FP` | 97 |

`6G概念` is one of the 290 sectors currently absent from
`fact_sector_stock_daily`. Its 97-member response disproves “the provider has
no membership data” and confirms that the orchestrator failed to reach it. The
three endpoint counts exactly matched the `stock_count` values declared by the
sector-list snapshot.

## Test evidence

The existing related suite on the dirty primary workspace returned
`5 failed, 19 passed`.

Four failures come from other overlapping uncommitted pipeline changes. One is
directly caused by the proposed gate change:

- `test_data_only_gate_does_not_require_a_report_file` configures a reduced
  table set containing only `fact_sw_l1_daily`; the new unconditional sector
  check now reports `fact_sector_daily` missing. A phase/table-scoped gate must
  not invent dependencies outside its declared table set.

There are no focused tests for current-universe retirement, pagination
starvation, empty-attempt progress, or membership coverage.

## Required root-level design

The corrected design must address the producer and the gate together:

1. **Snapshot-owned active universe.** After a successful complete sector-list
   fetch, atomically mark identities absent from that snapshot inactive, or
   make `last_seen_date == target_trade_date` the explicit current-universe
   predicate. A failed/partial list fetch must never retire rows.
2. **Current-universe consumers.** Sector K-line and member syncs must consume
   the same frozen current-universe identity set, not every historical
   `dim_sector` row.
3. **Durable progress.** Persist per-date/per-sector attempt state
   (`success|empty|error`, attempt count, last error) or an equivalent stable
   cursor, so one empty legacy/valid sector cannot starve every later sector.
4. **Exact membership receipt.** Persist each current identity's declared
   `stock_count` in the frozen list-snapshot receipt. The gate must require a
   terminal success receipt for 407/407 current identities and compare each
   sector's actual distinct stock count with its declared count. A provider
   mismatch is a visible failure, not a reason to lower a global threshold.
   “Never had historical members” is diagnostic metadata, not an exclusion.
5. **Name continuity remains secondary.** Adjacent-day normalized-name
   continuity is useful for detecting mass disappearance, but cannot substitute
   for member-sync completion.
6. **Phase/table scoping.** Reduced fixtures and phase-specific checks only run
   invariants for the tables declared in that scope.

Required tests include stale-identity retirement, partial-list fail-closed
behavior, an empty first page that does not starve later sectors, current
membership coverage failure, code churn with stable names, and reduced-table
phase isolation.

Until these are implemented and an unattended night run is green, the daily
data foundation remains release-blocking. The 2026-07-28 manual `COMPLETE`
result must not be reported as data-pipeline completion.

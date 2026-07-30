# Daily Sector Universe Root Repair — Verification Result

Date: 2026-07-30
Workspace: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Branch: `codex/agent-runtime-root-repair`

Status: Tasks 1-7 implemented and verified. Task 8 Steps 1, 2 and the
copied-database half of Step 3 are complete. **No live provider call and no
production database write has occurred.**

## 1. What Is Verified By Tests Versus By Live Execution

This distinction is the point of this document. Everything in §3 and §4 is
deterministic verification against test fixtures or a disposable copy. Nothing
here establishes that a real provider sync produces an exact universe — that is
Task 8 Step 3's live half and Task 9's three-night streak, both still open.

## 2. Commits

| Task | Commits |
| --- | --- |
| 5 — durable member receipts | `df6427e1`, `41036494` |
| 6 — receipt-driven nightly + report gate | `ca894e07` |
| 7 — exact audit + enforced access guard | `690bb182`, `7d0fecd4` |
| 8 — preview path and lint cleanup | this commit |

Ported product-usability fixes verified alongside: `c5db0df1`, `cdf22502`,
`19ddd99a`, `7f1ac960`, `e841c8cb`, `ee0ceec4`, `75b6e46e`, `78f8ceae`,
`9b13ab01`, `6ab7646c`.

## 3. Task 8 Step 1 — Focused And Adjacent Tests

```
pytest tests/test_sector_member_latency.py tests/test_sector_universe.py
       tests/test_sector_fact_access.py tests/test_pipeline_p0.py
       tests/test_processing_quality_order.py
       tests/test_sector_daily_range_coverage.py
       tests/test_sync_akshare_sw_l1_daily.py intelligence/tests/test_agent.py
  -> 172 passed
ruff (15 files listed in the plan)  -> All checks passed
git diff --check                    -> clean
```

Two pre-existing lint findings were cleared to satisfy the plan's "Ruff passes"
expectation: three genuinely unused imports in `scripts/fast_daily_sync.py`, one
f-string without placeholders, and two `E402` cases where the import must follow
`sys.path.insert` — those carry `# noqa: E402` with the reason rather than being
reordered.

Whole-repository suite: 3,571 passed / 3 skipped / 11 pre-existing
subconscious+userspace environment failures. One run also showed
`test_continuous_episode_citations_survive_run_context_reload` failing; it passes
in isolation and on re-run, so it is order-sensitive and unrelated.

## 4. Task 8 Step 2 — Read-Only Migration Preview

New command `market_feature_store.cli sector-universe-preview`. Opens the target
database `read_only=True`, issues no DDL and no writes, and does not call the
provider. Run against the configured production database:

| Field | Value |
| --- | --- |
| `generation_schema_present` | **false** |
| `premigration_sector_daily_rows` | 95,813 |
| `premigration_member_rows` | 10,599,868 |
| `dim_sector_active` | 630 |
| `published_headers` | n/a (schema absent) |
| `provider_denominator` | not performed — requires an authorized live call |

The production database has never had the generation schema applied, which is
consistent with Tasks 1-7 leaving it untouched. The preview reports that state
explicitly instead of raising, because "has this database been migrated" is the
first question a preview must answer.

## 5. Task 8 Step 3 — Copied-Database Rehearsal

Disposable copy of the 3.0 GB production database. Migration executed through
the normal entry point (`cli init`), never by hand.

| Check | Result |
| --- | --- |
| Migration wall time | 73 s |
| `fact_sector_daily` rows | 95,813 → 95,813 (exact) |
| `fact_sector_stock_daily` rows | 10,599,868 → 10,599,868 (exact) |
| Public names after migration | both `VIEW` |
| Leftover `*_legacy` temp tables | none |
| Physical generation ids present | `legacy` only |
| Sample reconciliation 2026-07-29 | 403 sectors, production = copy |

All 10.6M member rows and 95.8K daily rows moved into the `legacy` generation
with zero loss, and the public read seam returns identical counts.

`predicted_retirements` reads 630 on the freshly migrated copy. That number is
an artifact of `published_headers = 0`: with no published universe the
`NOT EXISTS` clause matches every active identity. It only becomes meaningful
after a snapshot is published. The real stale-identity scale is visible instead
from `dim_sector_active = 630` against 403 sectors actually present on
2026-07-29 — roughly 227 stale identities, which is exactly the population that
Task 6 stopped from entering the completion denominator.

The copy was deleted after verification. No database file is committed.

## 6. Task 7 Access Guard State

```
scripts/check_sector_fact_access.py --root <workspace>
  -> {"records": 283, "violations": 0}, exit 0
```

Enforced invariants: the physical generation tables are reachable only from
`market_feature_store/sector_universe.py` and
`market_feature_store/sector_schema.sql`; the public views are read-only.

The guard caught two violations introduced by Task 5 itself
(`scripts/fast_daily_sync.py` and the member sync touching the generation table
directly). Both were routed through new store methods rather than relaxing the
rule.

## 6b. Live Execution On Production (authorized 2026-07-30)

Production was backed up first to
`/Users/a77/db-backups/market_feature_store.pre-sector-universe-<ts>.duckdb`
(3.0 GB, row counts verified against the source before proceeding).

| Step | Result |
| --- | --- |
| Migration via `cli init` | 51 s; 95,813 and 10,599,868 rows preserved exactly, verified against the backup |
| `sync-sectors` | 403 sectors published, trade date 2026-07-30 |
| Snapshot id | `962a50be5e4fc56def00a0e3ccd4b5234aca44a4eef0829a6dedd4440c2e7877` |
| Declared sectors / relationships | 403 / 52,734 |
| `dim_sector_active` | **630 → 403** — 227 stale identities retired |
| `predicted_retirements` after publish | 0 |
| `sync-sector-daily` | 403 rows written for 2026-07-30 |
| `sync-sector-stocks --limit 10` | 7 success, 3 `member_count_mismatch`, 393 still pending |

`sync-sectors` initially failed closed with `sector identities must be unique`.
Cause: `_normalize_sectors` required sector **names** to be unique, but the design
document only requires "all codes and identity rows are unique; names are
non-empty" and defines `sector_name` as a display name with `sector_ts_code` as
the identity. fupanhui legitimately publishes two sectors sharing one display
name — `990143.FP` 国防军工 (530) and `990144.FP` 国防军工 (136). The
implementation was stricter than the specified contract and blocked the whole
pipeline, so the name-uniqueness check was removed. Code uniqueness and
non-empty names are unchanged. This is an implementation-to-spec correction, not
a weakened gate.

## 6c. The Declared-Versus-Detail Shortfall Is Now Quantified

The ledger's open item — "the provider declares 1,204 members for `990220.FP`
while the observed detail response contains 1,202 unique identities" — is
reproduced and generalised. Read-only probe, evenly spaced 40-sector sample of
the published 403, trade date 2026-07-30:

| delta (unique detail − declared) | sectors |
| --- | --- |
| 0 | 31 |
| −1 | 7 |
| −2 | 1 |
| −4 | 1 |

Exact agreement: **31/40 = 78%**. Every disagreement is negative, magnitude
1–4, and the detail responses contain no duplicates (returned == unique).

`990220.FP` 机器人概念 now reads declared 1205 / detail 1203 — the same sector
and the same −2, with both numbers up by one as the sector grew. The discrepancy
is therefore stable and systematic, not a single stale observation. The shape is
consistent with the detail endpoint omitting a small number of declared members
(suspended, delisted, or newly added and not yet in the detail list) rather than
with corruption.

**The declaration was not reduced and the exact-count admission was not
relaxed.** The consequence is stated plainly: with current provider behaviour
roughly 22% of sectors cannot produce a success receipt, so Task 8 Step 3's
"zero pending/error receipts" and Task 9's streak are unreachable as specified.
Resolving that is a spec-level decision — keep the exact gate and accept that
the nightly never completes; amend the spec to admit a bounded, recorded
negative variance; or find the provider-side cause. It is deliberately left to
the user rather than settled by loosening a gate.

The remaining 393 sectors were not synced. Running them would add roughly 85
more error receipts without changing the decision above.

## 7. Explicitly Still Open

- **No live provider sync.** Task 8 Step 3's live half (`sync-sectors`,
  `sync-sector-daily`, receipt-driven `sync-sector-stocks` against the
  configured production database) has not been run. It needs explicit user
  authorization because it calls the provider and writes production.
- **The 1,204 / 1,202 member discrepancy is undiagnosed.** The receipt
  machinery that would expose which identities disagree is in place, but the
  answer requires one authorized live sync. The declaration was not reduced or
  bypassed.
- **No three-night unattended streak** (Task 9). `data_foundation_cutover_eligible`
  remains false.
- **Production database, `main`, 8792 and credentials are unchanged** by all of
  Tasks 1-8 so far.

## 8. Safety Boundaries Held

No DuckDB file, provider payload, run log, cookie, header or latency JSON is
committed. No manual row edits. No gate was weakened to obtain a green receipt —
the one place where enforcement is narrower than the plan's literal wording
(rejecting `unknown` access) is documented in `7d0fecd4` with the measurement
that showed the literal rule would flag warning text and conservative dynamic
candidates.

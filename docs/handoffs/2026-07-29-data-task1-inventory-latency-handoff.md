# Data Task 1: Sector Access Inventory and Latency Handoff

Date: 2026-07-29

Status: implementation complete; live provider contract remains red

Worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`

Branch: `feat/agent-runtime-backends-verify`

Implementation tip before this handoff commit: `a10c9f07`

## Outcome

Data-plan Task 1 is implemented and independently reviewed. The repository now
has a reproducible pre-migration inventory of every current production reference
to `fact_sector_daily` and `fact_sector_stock_daily`, plus a read-only provider
latency probe that refuses incomplete or stale responses.

The engineering slice is complete, but its live receipt is intentionally not
green: provider sector `990220.FP` (`机器人概念`) declared 1,204 members and
returned 1,202 unique stock identities. The probe returned exit 2. Do not lower
the declared count, discard duplicates silently, or treat the latency receipt as
release readiness.

## What Was Implemented

### 1. Read-only provider workload probe

`scripts/measure_sector_member_latency.py` now:

- chooses deterministic small/median/high/largest sectors and representative
  batches;
- projects full-run wall time from observed batch p50/p95;
- validates served date, provider self-count, declared count, unique member
  identities, and complete batch-code coverage before accepting a sample;
- sanitizes provider failures and removes stale/partial output;
- writes only the explicit private `--output` path.

### 2. Pre-change production access inventory

`scripts/check_sector_fact_access.py` now:

- scans production Python/SQL while excluding tests, runtime artifacts, caches,
  archives, and virtual environments;
- classifies each current table occurrence as `read`, `write`, `ddl`, or
  `unknown`;
- preserves physical line/Unicode-column and runtime occurrence identity;
- handles literal SQL plus bounded string `Add`, static f-string, restricted
  literal `.format()`, `%`/literal-hole candidates, and adjacent string tokens;
- fails closed on syntax errors and unmappable supported candidates;
- remains inventory-only. It is not yet the Task 7 enforcement allowlist.

The bounded expression support is deliberate. It does not execute arbitrary
AST nodes or trace variables. Task 7 must reject `unknown` and direct physical
generation-table access instead of extending this scanner into a general Python
or SQL interpreter.

### 3. Permanent regression coverage

The tests cover deterministic sampling/projection, incomplete provider batches,
served-date and count mismatches, error redaction, stale receipt removal,
SQL statement/comment/quote boundaries, repeated occurrences, Python token
coordinates, Unicode identifier boundaries, dynamic literal holes, syntax
errors, and runtime-directory exclusion.

## Verification Receipt

Independent final verification from the project Python 3.12 environment:

- focused tests: `44 passed`;
- Ruff: `All checks passed`;
- `compileall`: passed;
- `git diff --check`: passed;
- regenerated inventory: byte-identical to the committed JSON;
- final independent release-quality review: `Approved`;
- worktree after code verification: clean;
- production DuckDB, `main`, canonical 8792, and private credentials: untouched.

Committed inventory:

- path: `docs/verification/sector-fact-access-inventory-2026-07-29.json`;
- records: 287;
- modes: 154 read / 15 write / 11 DDL / 107 unknown;
- SHA-256: `700fd42137712e702af44419afb8fef6bc759f3c492286c2b80e899ce963451b`.

Private live diagnostic receipt, not committed:

- path: `/Users/a77/.finance-runtime/verification/sector-member-latency-2026-07-28.json`;
- SHA-256: `3c8ca9fe05e1a56ffa2c15862848d45ea37a8972accd4a2102579960388fc582`;
- provider sectors: 403;
- batch p50 / p95: 12.710s / 30.908s;
- projected 41 batches: 1,267.240s (about 21.1 minutes), inside the
  two-hour observed nightly window;
- individual matches: insurance 5/5, traditional Chinese medicine 68/68,
  memory chips 200/200;
- mismatch: robotics concept 1,202/1,204;
- result: exit 2, not release-green.

The live diagnostic predates the final stricter served-date/self-count batch
validator and was intentionally not rerun as a debugging loop. Its timings are
observed diagnostics; the final implementation would continue to fail closed on
the 1,204/1,202 mismatch.

## Commits in This Slice

- `2299cdf1` — initial inventory and latency probe;
- `91a6f46f` — harden positions, SQL statement context, exclusions, and failure redaction;
- `480b55d0` — map Python string tokens to physical coordinates;
- `06bc5355` — fail closed on provider and inventory gaps;
- `44d4cb18` — validate static references and provider response contracts;
- `98fe8f43` — preserve ordered static SQL occurrences;
- `604eb5b1` — preserve dynamic literal-hole candidates and occurrence identity;
- `a10c9f07` — match holes inside dynamic sector identifiers.

## What Is Not Complete

- No generation-aware sector storage or migration has been implemented yet.
- No snapshot has been published and no durable member receipts exist yet.
- The 1,204/1,202 provider discrepancy is unresolved.
- The exact Task 7 access guard has not been enabled; this artifact is its
  frozen baseline inventory.
- No production database migration, complete live sync, three-night streak,
  runtime work, 8792 cutover, or Self-use day has started.

## Next Execution Order

1. Start data-plan Task 2 in temporary DuckDB only: introduce
   `SectorUniverseStore`, generation tables, canonical published views, and the
   idempotent legacy migration.
2. Keep the provider discrepancy as a typed blocking receipt. Before Task 3/5
   can become live-green, determine whether the two missing identities are
   duplicates, blank codes, or provider count drift; do not change the exact
   denominator to fit observed rows.
3. Adapt every known writer through the deep module before the public fact names
   become views.
4. In Task 7, compare the candidate inventory with this frozen baseline and
   enforce: physical generation names only in the exact module/schema allowlist,
   no writes to public views, and unresolved `unknown` candidates fail closed.
5. Only after Tasks 2-8 and one exact complete live sync may the three-night
   unattended streak begin. Runtime product-canary work remains downstream of
   that data gate.

## Safety Boundaries to Preserve

- Do not merge `main` or switch 8792 without separate user approval.
- Do not commit DuckDB, provider payloads, logs, cookies, headers, keys, caches,
  models, or virtual environments.
- Do not weaken exact equality, cutoff, freshness, EvidenceLedger, or semantic
  gates to make a receipt green.
- Do not turn the inventory scanner into a general-purpose parser; unsupported
  dynamic access must be rejected or explicitly reviewed.

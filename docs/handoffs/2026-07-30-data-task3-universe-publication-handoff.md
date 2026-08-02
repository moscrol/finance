# Data Task 3: Validated Sector Universe Publication Handoff

Date: 2026-07-30

Status: implementation complete; live member-count discrepancy remains blocking

Worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`

Branch: `feat/agent-runtime-backends-verify`

Implementation commit: `3e7dff99`

## Outcome

Task 3 now publishes one validated, immutable provider universe generation and
makes that generation the owner of current `dim_sector` active identities. The
provider adapter no longer writes active flags directly. A successful publish
also creates one pending member receipt per declared sector, preserving the
provider's exact member denominator for Task 5.

Task 2 was independently rechecked before this work began. Its planned focused
suite passed, Ruff and diff checks passed, and no blocking storage/spec mismatch
was found.

## What Was Implemented

### 1. Immutable publication contract

`market_feature_store/sector_universe.py` now exposes:

- frozen `SectorDescriptor` and `PublishedSectorSnapshot` values;
- `SectorUniverseValidationError` for fail-closed provider/schema conditions;
- `SectorUniverseStore.publish_snapshot(...)` as the only publication and
  active-identity write boundary.

The snapshot ID is SHA-256 over sorted, compact canonical rows containing
normalized code, normalized name, positive member count, provider, and trade
date. Ordering, provider case, code case, NFKC whitespace, and replay capture
time cannot change the snapshot identity.

### 2. Atomic lifecycle and identity ownership

One transaction now:

1. checks that the date/provider does not already have multiple published
   headers;
2. inserts immutable candidate header and universe rows;
3. enforces the 95% normalized-name continuity floor against the closest
   published generation;
4. supersedes the prior same-day generation and publishes the candidate;
5. asserts exactly one published same-day header;
6. upserts current identities and retires absent same-provider identities;
7. creates one pending member receipt per declared sector.

Any database failure rolls all seven effects back together. Structural input
errors occur before active flags change. A continuity failure commits only a
`rejected` header and its immutable candidate rows; it creates no member
receipts and changes no active identity.

### 3. Idempotent replay and corruption detection

Re-observing the same canonical snapshot does not duplicate headers, universe
rows, or receipts. It returns the original persisted capture provenance rather
than the later replay time. Before accepting that replay, the store compares
every persisted universe row with the canonical input; a matching header with
corrupted or missing detail rows fails closed.

### 4. Provider adapter ownership transfer

`market_feature_store/sync/sync_fupanhui_sectors.py` now:

- resolves a canonical provider trading day before it calls the list endpoint;
- refuses to replace a missing provider date with `date.today()`;
- converts every list row to `SectorDescriptor`, preserving `stock_count` as
  the exact member denominator and `sw_l1` as local identity enrichment;
- publishes only through `SectorUniverseStore`;
- returns `snapshot_id`, `sector_count`, and
  `declared_relationship_count` alongside its compatibility statistics.

An empty name, duplicate normalized identity, missing/non-integer/non-positive
count, unavailable date, low continuity, or conflicting published state raises
instead of silently skipping rows or retiring identities.

## Verification

- Task 3 plan command: `26 passed, 18 deselected`;
- related Task 2/3 suite: `74 passed`;
- `tests/test_sector_universe.py`: `23 passed`;
- Ruff: passed;
- compileall: passed;
- `git diff --check`: passed;
- full repository: `3480 passed, 3 skipped, 11 failed`.

The 11 full-suite failures are the unchanged environment-path baseline in
`intelligence/tests/test_subconscious.py` and
`intelligence/tests/test_userspace.py`; no sector test failed.

The frozen Task 1 inventory remains byte-identical:

- path: `docs/verification/sector-fact-access-inventory-2026-07-29.json`;
- SHA-256: `700fd42137712e702af44419afb8fef6bc759f3c492286c2b80e899ce963451b`.

No provider live call, production DuckDB write, `main` merge, 8792 switch,
credential access, or knowledge-base change occurred.

## Commits

- `9c4bf2d7` — Task 2 versioned sector storage and legacy migration;
- `3e7dff99` — Task 3 exact daily universe publication.

## What Is Still Red

The private read-only receipt still records `990220.FP` (`机器人概念`) as
1,204 declared members versus 1,202 unique returned identities. Task 3 freezes
1,204 as the denominator; it does not reinterpret or reduce it. Task 5 cannot
produce an exact-success receipt for that sector until the provider discrepancy
is diagnosed as duplicate identities, blank identities, or count drift.

No live snapshot has been published to production. The current work proves the
publication mechanism in temporary DuckDB only.

## Next Execution Order

1. Start Task 4 in temporary DuckDB: add `published_snapshot`,
   `replace_sector_daily`, and `enrich_sector_daily` to the deep module.
2. Prove that public sector-daily reads expose only the published generation
   while legacy and superseded generations remain stored but invisible.
3. Adapt `sync_fupanhui_sector_daily` to request only published identities and
   replace exactly that generation.
4. Adapt the three Feishu enrichment writers to call `enrich_sector_daily` and
   remove their direct table-alter/update paths.
5. Keep foreign identities, served-date mismatches, unmatched enrichment codes,
   and partial batches fail-closed. Do not begin a production migration or live
   sync during Task 4.
6. Continue to Task 5 only after Task 4 is independently green; diagnose the
   1,204/1,202 member discrepancy without changing the declared denominator.

## Safety Boundaries

- Do not merge `main` or switch canonical 8792 without separate user approval.
- Do not write the production DuckDB during Tasks 4-7 before their copied-DB
  release sequence authorizes it.
- Do not commit provider payloads, databases, logs, credentials, caches, models,
  or virtual environments.
- Do not weaken exact equality, generation binding, cutoff, freshness,
  EvidenceLedger, structural, numeric-lineage, or semantic gates.

# Data Root Repair Task 4 Handoff

Date: 2026-07-30

Status: implementation complete; live data/release gates remain red

## 1. Resume Here

- canonical workspace:
  `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`;
- branch: `codex/agent-runtime-root-repair`;
- Task 4 product commit: `e74ca793`;
- canonical progress ledger:
  `docs/handoffs/2026-07-30-agent-runtime-canonical-workspace.md`;
- active plan:
  `docs/superpowers/plans/2026-07-29-daily-sector-universe-root-repair.md`.

Do not resume from `feat/agent-runtime-backends-verify`, the old
`69f9cf17` runtime worktree, the dirty main checkout, or an older handoff that
still calls Task 4 pending.

## 2. What Task 4 Changed

### Generation-bound daily storage

`PublishedSectorSnapshot` now carries the exact published sector identities.
`SectorUniverseStore.published_snapshot()` fails closed unless a date/provider
has exactly one published header whose stored universe count, declared member
sum, and canonical hash all revalidate.

`SectorUniverseStore.replace_sector_daily()` accepts only a complete set whose
codes exactly equal that published snapshot. It replaces only the matching
date/snapshot generation inside one transaction and rejects missing, foreign,
or superseded identities without deleting the existing generation. The public
`fact_sector_daily` view exposes the currently published generation; the
physical generation table retains prior rows for audit.

### Authoritative writer

`sync_fupanhui_sector_daily` now:

- resolves the canonical provider trade date without a local-today fallback;
- requests only the sector codes in that date's published snapshot;
- requires the response mapping to contain exactly those codes;
- persists exactly one point for the requested date and ignores historical
  points returned in the same provider response;
- writes only through `replace_sector_daily` and returns the bound snapshot ID.

Range sync resolves a published snapshot independently for each target date.
Missing publication is a visible failure, not a legacy fallback. A date is
skipped only when its published generation already has the exact row count and
no null gap; post-sync validation is 100%, not a percentage threshold.

### Retired sector Feishu path

Per the user's correction, the following sector-level Feishu producers were
removed rather than migrated:

- `sync_feishu_sector_daily.py`;
- `sync_feishu_sector_marginal.py`;
- `sync_feishu_sector_resonance.py`.

Their three CLI commands and both nightly orchestration entry points were also
removed. Current skills no longer advertise them. Historical nullable columns
and historical run-log entries remain as audit history. This correction is
scoped to sector daily/marginal/resonance ownership; unrelated Feishu paths were
not deleted without proof that their owners are retired.

## 3. Verification Receipt

At `e74ca793`:

- Task 4 focused suite: `51 passed`;
- broader adjacent data-root suite: `131 passed`;
- full repository: `3,488 passed, 3 skipped, 11 failed, 8 warnings`;
- the 11 failures are the already-known local environment/path failures in
  `test_subconscious.py` and `test_userspace.py`; no sector test failed;
- changed-file Ruff, compileall, CLI help, `git diff --check`, and the static
  search for retired sector Feishu production references passed;
- the frozen Task 1 inventory remained byte-identical with SHA-256
  `700fd42137712e702af44419afb8fef6bc759f3c492286c2b80e899ce963451b`.

A wider future-task Ruff invocation exposed seven existing errors in
`scripts/check_daily_review_data.py` and `scripts/fast_daily_sync.py`. They were
not introduced or hidden by Task 4 and must be handled in the Tasks 6-7 slice
that owns those files.

No live provider call, production DuckDB write, main merge, 8792 switch,
credential read/write, knowledge-base write, or KB commit merge occurred.

## 4. Still Red

- `990220.FP` still declares 1,204 members while the observed detail response
  has 1,202 unique identities. The denominator remains 1,204; no exception,
  waiver, or silent truncation was added.
- There has been no exact complete live member sync and no three-night
  unattended streak.
- The runtime candidate is not on canonical 8792.
- Self-use is still 0/10 distinct trading days and 0/5 required workflows.
- The post-numeric-lineage five-case control, 28-case pass rate, Knevo result,
  and final release decision remain unresolved or intentionally frozen.

## 5. Next Single Slice: Task 5

Start only Task 5, "Replace Invisible Missing Work with Durable Member
Receipts":

1. add RED tests for fair receipt selection, served-date/count mismatch, and
   transaction atomicity;
2. make every published sector's member work durable and retryable so one error
   cannot starve later sectors;
3. require exact provider-declared member counts before publishing member rows;
4. adapt `sync_fupanhui_sector_stock_daily` and its CLI to the published
   snapshot/receipt contract;
5. mark `scripts/fast_daily_sync.py` historical-copy output explicitly
   ineligible rather than treating it as canonical publication;
6. diagnose the 1,204/1,202 discrepancy from receipts and provider payload
   semantics without changing the denominator.

Do not mix Tasks 6-8, restart sealed/Knevo debugging, revive sector Feishu, or
touch production data in this slice. Task 5 is complete only when its tests and
static gates pass and the discrepancy remains an honest visible red receipt if
the provider still cannot supply the two missing identities.

# Agent Runtime Canonical Workspace and Progress Ledger

Date: 2026-07-30

Status: canonical start-here ledger; final product goal remains incomplete

## 1. Use This Workspace Only

Canonical development copy:

- path: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`;
- branch: `codex/agent-runtime-root-repair`;
- implementation frontier before this consolidation commit: `ca9a41a9`;
- Git layout: standalone clone with its own `.git` directory;
- `origin`: `https://github.com/linxiaoqi5111-del/finance-workspace-private.git`;
- `legacy-local`: read-only reference to
  `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667`.

The old registered runtime worktree is frozen at `69f9cf17`. It is an ancestor
of the canonical copy, which is 146 commits ahead. Do not implement, review, or
rerun acceptance work from that old worktree.

Older handoffs that name `feat/agent-runtime-backends-verify` are historical
records. Their commits remain useful evidence, but their workspace/branch
instructions are superseded by this section.

## 2. Why Consolidation Was Required

Read-only inventory on 2026-07-30 found:

- 123 worktrees registered in the main repository;
- 36 local branches, 19 not merged into `main`;
- the main checkout on `fix/degrade-disclosure` with 113 dirty/untracked paths;
- two independent repositories using the same branch name while pointing at
  different commits;
- the canonical standalone clone's former `origin` pointing to the old local
  worktree rather than GitHub;
- two prunable metadata entries: `worktrees/.DS_Store` and the missing
  `worktrees/wt-main-check` gitdir.

The branch was renamed to `codex/agent-runtime-root-repair`, the GitHub remote
was restored as `origin`, the old worktree was retained as `legacy-local`, and
the stale upstream was removed. No worktree, branch, user file, or Git history
was deleted.

The two prunable metadata entries and the broader old-worktree/branch set are
cleanup candidates only. Deletion requires a separate, explicit cleanup pass.

## 3. Source-of-Truth Order

When documents disagree, use this order:

1. this canonical workspace/progress ledger;
2. the amended approved specs and active implementation plans;
3. the latest task-specific completion handoff;
4. older handoffs and review notes as historical evidence only.

Before starting a task, check the active plan checkbox and `git log`. A task is
not restarted merely because an older handoff calls it pending.

## 4. Completed Engineering

### 4.1 Adaptive runtime core

The branch contains the provider-neutral continuous/SDK/headless runtime,
model-owned task/research state, bounded repair admission, hard root budgets,
evidence and query ledgers, cutoff propagation, typed degradation, safe
semantic verification, episode progress/SSE replay, and the product-facing Run
projection. The deterministic engineering candidate is complete; this does not
mean the product release gate is complete.

Canonical summary:

- `docs/handoffs/2026-07-29-adaptive-runtime-final-quality-handoff.md`;
- runtime code frontier before the data-root pivot: `c35740e6`.

### 4.2 Retrieval and evidence quality

Phase C established a manifest-fresh Wiki snapshot, true Hybrid retrieval,
per-attempt retrieval telemetry, causal anchor/window guards, and subject-local
valuation evidence admission. The knowledge-base implementation commit
`9053b0c4` remains isolated and is not authorized for cross-repository merge.

Relevant completion records:

- `docs/handoffs/2026-07-29-phase-c-completion-handoff.md`;
- `docs/handoffs/2026-07-29-evidence-telemetry-handoff.md`;
- `docs/verification/phase-c-causal-anchor-guard-2026-07-29.md`;
- `docs/verification/phase-c-valuation-evidence-admission-2026-07-29.md`.

### 4.2b Turn-budget and retrieval-noise P0 fixes (ported 2026-07-30)

Five commits diagnosed against the 29 real `linxiaoqi5111` runs and ported from
the frozen `fix/retrieval-quality-p0` branch. The five touched files were
untouched on this branch since `69f9cf17`, so the cherry-pick was conflict-free.

- `c5db0df1` — owner skills consumed `remaining_seconds` (which includes the
  synthesis reserve) instead of a stage-bounded budget, so a slow/failed skill
  starved final synthesis. Measured failure: a 34s failed `news-impact` skill
  plus 57s of retrieval left synthesis `remaining_budget_ms: 0`, emitting
  `llm_unavailable_template_answer` with zero tokens generated. 6/29 runs
  (21%) degraded this way. Added `stage_remaining_seconds`; the guard clamps
  duration only and still allows a starved skill to start for partial results.
- `cdf22502` — `LLMCallRecord` never stored a failure reason, so the 35% `chat`
  failure rate (23/66 calls, 332s burned, failure p10 12,046ms ≈ median
  12,072ms against success p90 11,612ms) could not be diagnosed. Added
  normalized `reason` capture and a `failure_reasons` tally in the trace, plus
  an opt-in `min_viable_seconds` guard (default off: `timeout` cannot
  distinguish a caller-configured policy from a deadline-clamped remainder).
  The guard is deliberately not wired to a call site yet — the source of the
  12s clamp is unidentified, and the new reason data is the instrument for
  locating it.
- `19ddd99a` — `load_relation` reparsed whole files per call; one query
  fragment reparsed `entity_exposures` (18.6MB) four times. Added an
  mtime+size keyed process cache (KB is rebuilt daily, so `lru_cache` would
  serve stale graphs). Fragment cost 0.66s to 0.21s.
- `7f1ac960` — concept scoring counted substring hits inside a 2000-char JSON
  dump of each concept payload. That tier is a truncation artifact, not a
  semantic relation: it supplied 80–90% of hits on mainline themes (固态电池
  returned MOF材料/全球锂矿/化工; 半导体设备 returned C4化工/CVD金刚石/GPU) and
  rode into LLM context. Restricted matching to concept-name tiers; semantic
  recall stays with the vector layer. Exposure matching was left unchanged —
  strong hits already saturate its top-40.
- `e841c8cb` — empty evidence sections emitted placeholder rows duplicating the
  more specific `gap_lines` guidance. Sections are now omitted when empty, as
  the web-fallback and agent-loop sections already were. Gap honesty is
  unaffected. Real-run impact is 2/29; the larger estimate came from a
  2026-07-09 sample that no longer reflects current behavior.

Verification after the port: focused suites pass; full suite reports 3,499
passed, 3 skipped, and the same 11 pre-existing subconscious/userspace
environment failures. The 11-test increase is exactly the regressions added by
these commits. No production database, credential, 8792, or `main` change.

Not yet done: no real-question acceptance run has exercised these fixes, so the
21% template-degradation rate is fixed in mechanism but unmeasured in outcome.

### 4.3 Evaluation assets and sealed control

The branch contains the 28-case acceptance asset set, 22 scoped Knevo reference
snapshots, fail-closed verdict/observation sidecars, the sealed PIT/Hybrid
fixture, and the same-fixture headless runner. The last five-case Retry 2 was
invalid for three research cases because numeric lineage normalization rejected
valid semantic equivalents. `c35740e6` fixes that shared seam, but no post-fix
Retry 3 has been run.

Therefore:

- there is no valid five-case all-green final artifact;
- the 28-case pass rate remains unknown;
- no Knevo win rate may be claimed;
- App Server v3 has an approved experiment spec, but no App Server product
  adapter or live arm has been authorized;
- sealed/Knevo debugging stays frozen. Only one preregistered Retry 3 may close
  the control after the data/release ordering allows it.

### 4.4 Daily data root repair

Completed on the canonical branch:

- Task 1 — exact production access inventory and read-only latency/provider
  contract probe (`2299cdf1` through `a10c9f07`);
- Task 2 — generation storage, canonical views, idempotent legacy migration,
  and disposable 3.2 GB production-copy rehearsal (`9c4bf2d7`);
- Task 3 — canonical universe hashing, atomic publication/supersession,
  95% name continuity, active identity ownership, and pending receipt creation
  (`3e7dff99`);
- Task 4 — generation-bound sector daily facts, exact target-date/provider
  identity validation, published-generation public reads, and removal of the
  three retired sector-level Feishu producers (`e74ca793`);
- Task 5 — durable member receipts, fair non-starving work selection, exact
  declared-count admission, receipt-driven member sync, and an explicitly
  disqualified legacy fast copy (`df6427e1`, `41036494`);
- Task 6 — `SectorUniverseStore.completion_audit` as the single completion
  formula, receipt-driven nightly polling that returns `partial` instead of a
  false `ok`, and a third report gate built from the same audit (`ca894e07`).

The nightly loop previously compared
`count(distinct sector_ts_code)` from the member facts against
`count(*)` from `dim_sector`. Those denominators are not the same population:
the numerator credited degraded legacy-copy rows and the denominator counted
stale `.TI` identities absent from the day's universe, so a coincidental match
reported `ok` over a real gap.

Task 5 also repaired a break left by Task 4: `fact_sector_stock_daily` became a
view, but the member writer still issued `DELETE`/`INSERT`/`ALTER TABLE`
against it, so that sync path could not run at all. The orphaned `UPSERT_SQL`
and `_ensure_columns` were removed; all ten columns the latter added already
exist in `fact_sector_stock_daily_generation`.

The `1,204/1,202` declaration discrepancy is still open and was not bypassed.

Task-specific records:

- `docs/handoffs/2026-07-29-data-task1-inventory-latency-handoff.md`;
- `docs/handoffs/2026-07-30-data-task3-universe-publication-handoff.md`;
- `docs/handoffs/2026-07-30-data-task4-generation-daily-handoff.md`;
- `docs/superpowers/plans/2026-07-29-daily-sector-universe-root-repair.md`.

The frozen Task 1 inventory remains 287 records with SHA-256
`700fd42137712e702af44419afb8fef6bc759f3c492286c2b80e899ce963451b`.

## 5. Explicitly Not Complete

- The provider still declares 1,204 members for `990220.FP` while the observed
  detail response contains 1,202 unique identities. The denominator was not
  reduced or bypassed.
- Data Tasks 5-8 are incomplete; no exact complete live member sync or
  three-night unattended streak exists.
- The candidate runtime has not been promoted to canonical 8792.
- Self-use remains 0/10 counted trading days and 0/5 required workflows.
- The final release decision and user acceptance have not occurred.
- `main`, production DuckDB, 8792, credentials, and the knowledge-base source
  repositories remain untouched by Tasks 1-4.

## 6. 2026-07-30 Feishu Correction

The user confirmed that the sector-level Feishu daily metrics, marginal ratio,
and multi-period resonance sources are retired. Their presence in the old Task
4 plan was legacy drift, not a current data requirement.

The amended rule is:

- fupanhui is the sole authoritative Task 4 sector-daily producer;
- do not implement `enrich_sector_daily` for an absent producer;
- remove the three retired sector Feishu CLI commands and nightly steps;
- delete the orphaned sector Feishu modules after import removal;
- retain historical enrichment columns as nullable/readable history only;
- do not generalize this correction to unrelated Feishu sources without first
  verifying their current production ownership.

The amendment is recorded in
`docs/superpowers/specs/2026-07-29-daily-sector-universe-root-repair-design.md`
and the active implementation plan. It was implemented in `e74ca793`; the
historical nullable columns remain readable, but no current CLI or nightly path
invokes the retired sector-level Feishu producers.

## 7. Single Forward Sequence

1. Task 5 implementation is complete (`df6427e1`, `41036494`). Still open: the
   1,204/1,202 discrepancy must be diagnosed from live receipts without
   changing the declaration; that needs an authorized provider run.
2. Task 6 implementation is complete (`ca894e07`). Task 7: enforce the exact
   completion/static access
   gates, and remove all unauthorized physical/date-only writer paths.
3. Task 8: copied-DB regression and migration preview, then one authorized
   complete live sync and a three-trading-night unattended streak.
4. Only after the data gate: one candidate runtime product canary on 8799.
5. Only with separate user approval: switch canonical 8792.
6. After switching: collect 10 distinct trading days across the five required
   self-use workflows, then request the user's explicit release acceptance.

## 8. Frozen or Read-Only Tracks

- old `69f9cf17` runtime worktree and all earlier detached canary worktrees;
- dual-lane review-loop harness development;
- repeated five/nine/28-case debugging runs;
- App Server implementation before a valid controlled need is demonstrated;
- Knevo snapshot expansion merely to fill denominators;
- sector-level Feishu ingestion and enrichment.

## 9. Safety Rules

- Do not delete worktrees/branches or prune Git metadata during implementation
  tasks; perform that as a separately reviewed cleanup operation.
- Do not work in the dirty main checkout.
- Do not merge `main`, push, or switch 8792 without explicit user approval.
- Do not commit databases, provider payloads, credentials, logs, model files,
  caches, or virtual environments.
- Do not weaken exact equality, generation binding, cutoff, freshness,
  EvidenceLedger, numeric-lineage, structural, or semantic gates to obtain a
  green receipt.

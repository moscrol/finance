# Teaching Framework Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build reproducible, fail-closed teaching labels for index stages and leader succession in the sidecar DuckDB, with versioned receipts, calibrated readouts, and a CLI.

**Architecture:** Keep canonical facts read-only and write all derived objects into `history_labels.duckdb`. Add a small teaching-framework package that owns parameters, stage predicates, two-clock succession objects, canonical hashes, and receipts; reuse existing `stats.readout`/BH logic. The CLI will build labels, build succession, and render receipts without touching the existing `history_labels` tables.

**Tech Stack:** Python, DuckDB, pytest, ruff, existing `methodology_backtest.store/stats` helpers.

---

### Task 1: Sidecar schema, parameter loading, and immutable receipts

**Files:**
- Modify: `intelligence/services/methodology_backtest/store.py`
- Create: `intelligence/services/teaching_framework/__init__.py`
- Create: `intelligence/services/teaching_framework/params.py`
- Create: `intelligence/services/teaching_framework/receipts.py`
- Test: `intelligence/tests/test_teaching_framework_store.py`

- [x] Add explicit DDL for `history_teaching_labels`, `history_teaching_gaps`, `history_leader_succession`, `history_overtaken`, and `history_teaching_receipts`; use separate `status` and `status_reason`, primary keys, and nullable realized fields.
- [x] Add reset helpers that drop only teaching tables and never `history_labels`, `history_outcomes`, or `history_calendar`.
- [x] Load `methodology/teaching/index_stage_params.v0.1.json`, validate required keys and `HH:MM` time values, canonicalize JSON with sorted keys, and compute the parameter hash.
- [x] Implement canonical row hashing that sorts by primary key and excludes `computed_at`; persist source max date, source row counts, source label version, parameter hash, framework version, coverage summary, and receipt status.
- [x] Test repeated builds with different timestamps produce the same canonical hash, parameter formatting changes do not change the canonical hash, and old receipts remain queryable after a new build.

### Task 2: Index-stage flags and B scalar labels

**Files:**
- Create: `intelligence/services/teaching_framework/flags.py`
- Create: `intelligence/services/teaching_framework/index_stage.py`
- Modify: `intelligence/services/methodology_backtest/store.py`
- Test: `intelligence/tests/test_teaching_framework_flags.py`

- [x] Read the market calendar by `history_calendar.idx`; every previous-day predicate must require adjacent calendar indices, and any required NULL or source gap yields NULL plus a teaching gap row.
- [x] Implement the A flags with explicit NULL/negative-predicate semantics, including MA20 shrink, streak reset, deviation bands, both mainline definitions, and vendor-table dedupe by `(trade_date, sector_ts_code)`.
- [x] Implement `tf.max_boards`, `tf.promotion_rate_total`, and `tf.top100_amount_share` with stock-day dedupe, fixed amount-unit policy, coverage gates, zero-denominator handling, and source traceability.
- [x] Store predicate evidence as structured JSON values rather than a list of flags assumed to equal 1.
- [x] Add fixtures for NULL inputs, missing calendar rows, duplicate theme rows, denominator zero, and vendor coverage gaps.

### Task 3: Stage resolution and transition events

**Files:**
- Modify: `intelligence/services/teaching_framework/index_stage.py`
- Create: `intelligence/services/teaching_framework/stage_rules.py`
- Test: `intelligence/tests/test_teaching_framework_stage.py`

- [x] Encode the complete seven-stage directed graph, self-loops, and reset behavior after `ambiguous`, `no_evidence`, or a data gap.
- [x] Compute E/H scores, resolve ties only through yesterday reachability, and output `ambiguous` or `no_evidence` without guessing.
- [x] Compute `stage_fine` only from same-day or prior-day evidence; emit `unassigned` when required fields are missing.
- [x] Emit each valid stage entry as `turn_up`, `turn_top`, or `turn_down`; test that event counts reconcile with a sequence replay.
- [x] Produce the supplier-stage contingency table while keeping supplier and teaching versions separate.

### Task 4: LeaderSuccession two-clock builder

**Files:**
- Create: `intelligence/services/teaching_framework/coverage.py`
- Create: `intelligence/services/teaching_framework/leader_succession.py`
- Test: `intelligence/tests/test_teaching_framework_succession.py`

- [x] Build a covered-empty versus missing-day map for the limit table and collapse rows by `(trade_date, stock_ts_code)` using the validated `limit_times` conflict policy.
- [x] Implement unique `top(d)`, break detection, candidate windows, next-leader search, and status propagation for tie, field-null, data-gap, and open tail cases.
- [x] Store `context_break` as anchor-time data and `forward/context_birth` as realized data requiring `knowledge_cutoff >= birth_day`; exclude open/hindsight rows from statistics.
- [x] Implement shape tags with a separate lookback window and explicit `unknown` when `open_times`, `first_limit_time`, or `circ_mv` are unavailable; normalize compact HHMMSS timestamps.
- [x] Write overtaken events to the dedicated side table and record event granularity and overlap counts in the receipt.

### Task 5: Baseline statistics and sidecar-aware cohort comparison

**Files:**
- Create: `intelligence/services/teaching_framework/readouts.py`
- Modify: `intelligence/services/river_query.py`
- Test: `intelligence/tests/test_teaching_framework_readouts.py`

- [x] Construct the eligible baseline risk set with the same coverage, dedupe, maturity, and next-leader rules as event nodes; exclude top-less, tied, missing, and open dates.
- [x] Call existing `stats.readout` and `stats.stage_readouts` only; include stage buckets for `ambiguous/no_evidence` according to the explicit receipt policy.
- [x] Extend `cohort_compare` with a sidecar database argument, typed `tf.*` lookup, label-version checks, duplicate-date removal, and explicit missing-value handling without applying `normalize_stage` to teaching values.
- [x] Test baseline counts against hand-built fixtures and verify BH-adjusted cohort outputs.

### Task 6: CLI, receipts, and verification

**Files:**
- Create: `scripts/teaching_framework.py`
- Create: `intelligence/tests/test_teaching_framework_cli.py`
- Create: `docs/verification/2026-09-07-teaching-framework-slice1.md`

- [x] Add `build-labels`, `build-succession`, and `report` commands with explicit source/sidecar paths and optional fixed `--computed-at`.
- [x] Add a deterministic self-test fixture covering gap, tie, open, overtaken, gap-zero, true/false handoff, and future-value perturbation.
- [x] Run targeted pytest/ruff, then the repository-required Python and frontend checks; record exact commands and receipt hashes in the verification document.
- [x] Commit by pathspec only, after checking `.env*`, database files, PDFs, archives, caches, and virtual environments are not staged.

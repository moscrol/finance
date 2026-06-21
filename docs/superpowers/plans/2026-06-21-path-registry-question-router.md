# Path Registry + Question Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic routing layer that classifies user questions before they enter fixed workflows, planner analysis, data-gap handling, or clarification.

**Architecture:** Store known paths in a JSON registry, load them with a typed service, route questions with deterministic rules, and expose the result through `python3 -m intelligence.cli route`.

**Tech Stack:** Python standard library, `unittest`, existing `intelligence.cli` and workflow patterns.

---

### Task 1: Path Registry

**Files:**
- Create: `intelligence/routing/path_registry.json`
- Create: `intelligence/services/path_registry.py`

- [x] Define known paths for daily review, daily ops ledger, morning briefing, sellside ingest, IMA stock ingest, concept/source backfill, front-map, deep-dive, and logic-market matching.
- [x] Add a typed loader returning `PathSpec` objects.

### Task 2: Question Router

**Files:**
- Create: `intelligence/services/question_router.py`
- Create: `intelligence/workflows/route.py`

- [x] Add route types: `known_workflow`, `planner_analysis`, `data_gap`, `clarification_needed`.
- [x] Match registered path triggers.
- [x] Route data gaps through Daily Ops Ledger first.
- [x] Route flexible analysis and bare theme terms through logic-market matching planning.
- [x] Render Markdown and JSON decisions.

### Task 3: CLI

**Files:**
- Modify: `intelligence/cli.py`

- [x] Add `route` subcommand.
- [x] Support `--json`.
- [x] Support `--summary-json`.

### Task 4: Tests

**Files:**
- Create: `tests/test_question_router.py`

- [x] Test explicit known workflow routing.
- [x] Test analysis routing to planner with `logic_market_match`.
- [x] Test data-gap routing to `daily_ops_ledger`, `source_backfill`, and `concept_backfill`.
- [x] Test bare theme routing to planner.


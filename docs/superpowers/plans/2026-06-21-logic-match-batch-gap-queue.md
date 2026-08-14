# Logic Match Batch Gap Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Batch-run logic-market matching over recent theme candidates and produce a prioritized data-gap queue.

**Architecture:** Extend `logic_market_match.py` with batch dataclasses and batch scan helpers; expose through workflow and CLI; register the path in `path_registry.json`.

**Tech Stack:** Python standard library, existing logic-match service, `unittest`.

---

### Task 1: Batch Service

**Files:**
- Modify: `intelligence/services/logic_market_match.py`

- [x] Discover available theme-candidates dates.
- [x] Load top candidates per date.
- [x] Run single-candidate `match_logic_to_market`.
- [x] Generate sorted `gap_queue`.
- [x] Render batch Markdown and JSON.

### Task 2: Workflow and CLI

**Files:**
- Modify: `intelligence/workflows/logic_match.py`
- Modify: `intelligence/cli.py`

- [x] Add `LogicMatchBatchOptions`.
- [x] Add `run_logic_match_batch`.
- [x] Add `python3 -m intelligence.cli logic-match-batch`.
- [x] Support `--dates`, `--recent`, `--top-per-date`, `--out-json`, and `--out-md`.

### Task 3: Router Registry

**Files:**
- Modify: `intelligence/routing/path_registry.json`
- Modify: `intelligence/services/question_router.py`

- [x] Register `logic_match_batch`.
- [x] Include it in data-gap routing.

### Task 4: Tests and Sample Report

**Files:**
- Modify: `tests/test_logic_market_match.py`
- Modify: `tests/test_question_router.py`
- Create: `market_feature_store/exports/logic-match-batch-recent3-top8-20260621.json`
- Create: `market_feature_store/exports/logic-match-batch-recent3-top8-20260621.md`

- [x] Test date discovery.
- [x] Test clean old-logic batch has empty gap queue.
- [x] Test missing knowledge produces prioritized gap queue.
- [x] Generate a real recent-3-days sample report.


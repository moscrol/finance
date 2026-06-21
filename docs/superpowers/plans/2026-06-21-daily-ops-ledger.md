# Daily Ops Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only daily operations ledger that aligns finance daily review outputs with knowledge repo ingest and traceability state.

**Architecture:** Add a standalone finance script that scans both repos through `intelligence.paths.default_paths()`, writes JSON and Markdown reports, and avoids modifying the knowledge vault. Add focused unit tests around date validation, file-status reporting, and next-action generation.

**Tech Stack:** Python standard library, existing `intelligence.paths`, `unittest`.

---

### Task 1: Add Ledger Scanner

**Files:**
- Create: `scripts/build_daily_ops_ledger.py`

- [x] **Step 1: Define immutable path and status helpers**

Use `Path.exists()`, `Path.glob()`, JSON reads with graceful error capture, and explicit `PASS/WARN/FAIL` status rules.

- [x] **Step 2: Scan finance daily review outputs**

Check date-specific expected files in `market_feature_store/exports` and `复盘/daily/<date>`.

- [x] **Step 3: Scan knowledge repo surfaces**

Check `wiki/briefings`, `wiki/raw/ima-stock/ingested/<date>`, sibling folders `未入库`, `已入库`, `待人工确认`, and required relations JSON files.

- [x] **Step 4: Read existing debt audits**

Read missing concept, missing source, and latest IMA stock coverage audit if present.

- [x] **Step 5: Write JSON and Markdown reports**

Write to `market_feature_store/exports/<date>-daily-ops-ledger.{json,md}` by default.

### Task 2: Add Tests

**Files:**
- Create: `tests/test_daily_ops_ledger.py`

- [x] **Step 1: Test date token conversion and expected output names**

Use temporary directories and a fake `ProjectPaths` object.

- [x] **Step 2: Test missing market output next actions**

Create only part of the expected files and assert the ledger reports missing outputs.

- [x] **Step 3: Test knowledge inbox counts**

Create fake `未入库` and `待人工确认` files and assert warnings are produced.

### Task 3: Verify

**Files:**
- Execute: `python3 -m unittest tests.test_daily_ops_ledger`
- Execute: `python3 scripts/build_daily_ops_ledger.py --date 2026-06-21`

- [x] **Step 1: Run unit tests**

Expected: all tests pass.

- [x] **Step 2: Run real ledger scan**

Expected: JSON and Markdown files are written under `market_feature_store/exports`.


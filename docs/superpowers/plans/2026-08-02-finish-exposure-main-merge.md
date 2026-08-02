# Exposure Branch Main Merge Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `diagnosing-bugs` to finish this plan inline. The user requested direct completion; no subagent is used.

**Goal:** Complete the interrupted merge of current `main` into `fix/exposure-ranking-truncation` without changing production or merging the feature branch back to `main`.

**Architecture:** Keep `main`'s canonical generation-table schema and chunked API strategy, retain the feature branch's Python snapshot lifecycle and fail-closed range gate, and validate the combined behavior at the public sync/test seams. Finish with one local merge commit only; do not push or switch the 8792 runtime.

**Tech Stack:** Python, pytest, DuckDB, Ruff, Git.

---

### Task 1: Lock the remaining range-gate behavior

**Files:**
- Modify only if required: `market_feature_store/sync/sync_fupanhui_sector_daily.py`
- Test: `tests/test_sector_daily_range_coverage.py`

- [x] **Step 1: Run the two exact regression tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_sector_daily_range_coverage.py::SectorDailyRangeCoverageTest::test_missing_published_snapshot_is_failure_not_legacy_fallback \
  tests/test_sector_daily_range_coverage.py::SectorDailyRangeCoverageTest::test_partial_api_response_only_marks_covered_dates_synced
```

Expected: `2 passed`; a missing published snapshot never invokes the API, and partial coverage does not mark an uncovered date as synced.

- [x] **Step 2: Inspect the final function for mixed, empty, and all-missing date paths**

Check that every summary field is derived from per-date `sector_counts`, that no post-loop expression depends on a stale scalar `sector_count`, and that `failed_chunks` includes snapshot failures exactly once.

- [x] **Step 3: Run the whole range-coverage module**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_sector_daily_range_coverage.py
```

Expected: all tests pass with no network access.

### Task 2: Verify the resolved sector-universe merge seam

**Files:**
- Verify: `market_feature_store/db.py`
- Verify: `market_feature_store/sector_universe.py`
- Verify: `market_feature_store/schema.sql`
- Verify: `market_feature_store/sync/sync_fupanhui_sector_daily.py`
- Verify: `market_feature_store/sync/sync_fupanhui_sector_stock_daily.py`
- Verify: `scripts/check_sector_fact_access.py`
- Verify: `skills/theme-fermentation-tracer/scripts/selftest.py`
- Test: `tests/test_sector_universe.py`
- Test: `tests/test_pipeline_p0.py`

- [x] **Step 1: Run the focused sector and pipeline regression set**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_sector_universe.py \
  tests/test_sector_daily_range_coverage.py \
  tests/test_pipeline_p0.py \
  tests/test_sync_akshare_sw_l1_daily.py
```

Expected: zero failures; legacy-table migration, published-generation reads, chunked sync, and the independent cross-day quality-gate fix all remain covered.

- [x] **Step 2: Run syntax/import and access-gate checks**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m py_compile \
  market_feature_store/db.py \
  market_feature_store/sector_universe.py \
  market_feature_store/sync/sync_fupanhui_sector_daily.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/check_sector_fact_access.py --root . \
  --output /tmp/sector-fact-access-merge.json
```

Expected: both commands exit 0.

### Task 3: Validate and conclude the merge

**Files:**
- Add: this plan
- Stage: all resolved merge files and the five post-resolution fixes already present in the working tree

- [x] **Step 1: Check merge integrity and prohibited files**

```bash
git diff --check
git diff --cached --check
git status --short
```

Expected: no conflict markers or whitespace errors; no `.env*`, credentials, PDF/ZIP/database, cache, or virtual-environment files are staged.

- [x] **Step 2: Run full regression and Ruff**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check .
```

Expected: no new failure identities relative to the recorded merge baseline; Ruff introduces no new violations.

- [x] **Step 3: Stage final resolutions and create the local merge commit**

```bash
git add --all
git commit
```

Expected: the merge concludes on `fix/exposure-ranking-truncation`; nothing is pushed and `main` is not changed.

- [x] **Step 4: Verify repository and runtime boundaries**

```bash
git status --short
git log -1 --oneline --decorate
curl -fsS http://127.0.0.1:8792/api/health
curl -fsS http://127.0.0.1:8799/api/health
```

Expected: feature worktree clean and both existing services still respond; no runtime restart or cutover occurs.

## Completion receipt

- Range-gate contract: `2 passed`; focused merge regression: `129 passed`.
- Physical-table inventory: `326` records, `0` violations; CLI migration preview is read-only.
- Theme fermentation selftest: `11/11` assertions passed.
- Full pytest: `4005 passed, 13 failed, 3 skipped`; all 13 failure identities match the recorded environment baseline (acceptance board 2, subconscious 8, userspace 3).
- Ruff: all conflict-resolution files pass; repository-wide debt remains the pre-existing `164` findings.
- Merge commit has parents `711f87f8` and `78187ec7`; no push, `main` mutation, runtime restart, or cutover.
- Existing services returned HTTP 200 on `8792` and `8799` after the merge commit.

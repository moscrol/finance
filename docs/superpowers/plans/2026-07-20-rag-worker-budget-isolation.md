# RAG Worker Budget Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a late closed-loop aperture from killing the shared RAG worker when its remaining stage budget is lower than the observed query cost.

**Architecture:** Keep worker timeout semantics fail-closed, but add a request-local budget predictor in `closed_loop_retrieval.py`. The predictor learns the first real retrieval latency and skips later apertures before provider invocation when they cannot fit, recording an auditable gap.

**Tech Stack:** Python dataclasses, monotonic deadlines, pytest monkeypatch.

---

### Task 1: Add a deterministic failing budget-isolation test

**Files:**
- Modify: `intelligence/tests/test_closed_loop_retrieval.py`

- [ ] **Step 1: Write the failing test**

Add a fake monotonic sequence for a 10-second budget whose first retrieval consumes 6 seconds. Assert that the provider is called once, narrow remains `ok`, and broad/counter are recorded as `budget_exhausted`.

- [ ] **Step 2: Run the focused test and verify failure**

Run:
`./.venv-workbench/bin/python -m pytest -q intelligence/tests/test_closed_loop_retrieval.py -k budget_exhausted`

Expected: FAIL because the old implementation invokes broad and counter.

### Task 2: Implement request-local observed-cost gating

**Files:**
- Modify: `intelligence/services/closed_loop_retrieval.py`

- [ ] **Step 1: Add `_AttemptBudget`**

Store `deadline` and `observed_seconds`; `can_start()` compares remaining time with
`max(1.0, observed_seconds * 1.25)`, and `observe()` keeps the maximum measured cost.

- [ ] **Step 2: Share the budget across all apertures**

Measure every provider call with `time.monotonic()`. Before provider invocation, record
`budget_exhausted` and a warning when `can_start()` is false, then return without side effects.

- [ ] **Step 3: Avoid misleading empty-retrieval warnings**

Do not add `"retrieval empty"` when every attempt for an aperture was skipped solely because
of `budget_exhausted`; preserve the explicit budget warning instead.

- [ ] **Step 4: Run focused tests**

Run:
`./.venv-workbench/bin/python -m pytest -q intelligence/tests/test_closed_loop_retrieval.py intelligence/tests/test_p1b_runtime.py`

Expected: PASS.

### Task 3: Regression and runtime verification

**Files:**
- Verify: `intelligence/services/evidence_providers.py`
- Verify: `intelligence/services/rag_worker.py`

- [ ] **Step 1: Run owner/RAG regressions**

Run the closed-loop, P1-B, conversation orchestrator, evidence judge and owner skill tests.

- [ ] **Step 2: Rebuild an index against one stable knowledge-base HEAD**

Use an isolated index directory. After update, assert `rag_index.py check` reports
`stale=0` and a query reports `index_freshness=fresh`.

- [ ] **Step 3: Run sequential workflow smokes**

Run daily, theme, stock, news-impact and watchlist questions against the single 8792 process.
After every run, assert readiness stays ready and the RAG worker remains active.

- [ ] **Step 4: Commit and deploy**

Commit only the two docs, service file and test file on `fix/rag-worker-budget-isolation`, merge
to `main` under the user's existing authorization, create a detached runtime at the merge SHA,
switch the canonical symlink, and verify port 8795 remains stopped.

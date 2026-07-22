# Episode Tool Batch Step-ID and Accumulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the episode tool session the sole owner of stable per-call step IDs and centralize every batch-result projection behind one focused accumulator.

**Architecture:** `EpisodeToolBatchSession.execute()` allocates one monotonic ID per original model call before any validation, then carries that ID through rejected, selected, reordered, completed, errored, empty, and timed-out results. A private `_EpisodeToolAccumulator` owns the mutable transcript/evidence projections and consumes one ordered `ToolBatchResult`, leaving `ContinuousAgentEpisode.run()` responsible only for orchestration and counters.

**Tech Stack:** Python dataclasses, existing `ToolBatchResult`/`ProviderTrace` contracts, pytest behavior tests, Ruff.

---

### Task 1: Session-owned IDs for every call

**Files:**
- Modify: `intelligence/services/episode_tool_batch.py`
- Test: `intelligence/tests/test_episode_tool_batch.py`

- [x] **Step 1: Write the failing public-contract tests**

Add assertions that two rejected calls receive distinct non-empty IDs, valid calls keep original-order IDs despite priority selection, later batches continue the sequence, and a new session restarts at `:1`.

- [x] **Step 2: Run tests to verify RED**

Run: `python3 -m pytest -q intelligence/tests/test_episode_tool_batch.py -k 'step_id or strict_arguments or unauthorized'`

Expected: rejected-call ID assertions fail because rejected results currently carry `""`.

- [x] **Step 3: Allocate IDs before validation**

At the start of `_execute_locked`, build an index-to-ID tuple from original call order and increment `_next_call_sequence` once per call. Pass the assigned value into every `ToolCallResult`, including every validation rejection and budget rejection; dispatch consumes the same mapping.

- [x] **Step 4: Run tests to verify GREEN**

Run the same focused command and expect all selected tests to pass.

### Task 2: One Episode batch accumulator

**Files:**
- Modify: `intelligence/services/agent_episode.py`
- Test: `intelligence/tests/test_agent_episode.py`

- [x] **Step 1: Write the failing Episode behavior test**

Drive one model turn containing two unauthorized calls and assert two disabled gate traces have distinct non-empty session IDs, ordered request/error events are preserved, raw internal exception sentinels remain absent, and no fixed `:episode:gate` ID is reconstructed.

- [x] **Step 2: Run test to verify RED**

Run: `python3 -m pytest -q intelligence/tests/test_agent_episode.py -k 'unauthorized'`

Expected: both gate traces currently share the reconstructed fixed gate ID.

- [x] **Step 3: Add `_EpisodeToolAccumulator.consume()`**

The accumulator owns `messages`, `ledger`, `evidence`, `evidence_hashes`, `traces`, and `gaps`. `consume(batch, context)` emits exactly one request then one result/error per ordered item, projects only public error codes, uses `result.step_id` unchanged, deduplicates evidence once, and returns the rejected-call invalid-action increment.

- [x] **Step 4: Reduce the run loop**

Replace the inline result-consumption block with:

```python
batch = tool_session.execute(...)
tool_calls += batch.executed_count
invalid_actions += accumulator.consume(batch, context=context)
continue
```

- [x] **Step 5: Run tests to verify GREEN**

Run: `python3 -m pytest -q intelligence/tests/test_agent_episode.py`

Expected: all Episode behavior tests pass, including raw-exception sentinel coverage.

### Task 3: Regression and hygiene

**Files:**
- Verify: `intelligence/services/episode_tool_batch.py`
- Verify: `intelligence/services/agent_episode.py`
- Verify: related tests

- [x] **Step 1: Run the required regression set**

Run the four requested suites plus all tests that exercise `query_ledger`.

- [x] **Step 2: Run Ruff and formatting checks**

Run Ruff check/format on the four modified Python files and inspect `git diff --check` plus the final diff.

- [x] **Step 3: Commit the bounded follow-up**

Stage only the plan, two implementation files, and two test files after checking forbidden-file patterns, then commit with `refactor: centralize episode batch consumption`.

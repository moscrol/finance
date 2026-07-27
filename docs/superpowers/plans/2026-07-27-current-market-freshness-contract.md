# Current Market Freshness Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent stale structured market rows from being published as current whenever Workbench has a newer served market snapshot.

**Architecture:** Pass snapshot freshness into the existing ResearchRunContext, derive one cutoff-aware floor inside `episode_tools`, and apply it to every model-facing structured market result. Expose the same mismatch in continuous-runtime readiness without coupling questions to the sync writer.

**Tech Stack:** Python, DuckDB read-only queries, FastAPI readiness, pytest.

---

## File structure

- Modify `intelligence/api/app.py`: resolve/pass runtime dates and expose readiness consistency.
- Modify `intelligence/services/episode_tools.py`: one current-data floor and stale ToolRunResult.
- Modify `intelligence/tests/test_episode_tools.py`: stale current, explicit historical, and frozen-cutoff regression tests.
- Modify `intelligence/tests/test_workbench_api.py`: composition and readiness regression tests.

## Task 1: Lock the model-facing stale-query failure

- [ ] Add a failing integration test with a temporary DuckDB ending
  `2025-06-30` and a context carrying snapshot `2026-07-27`. An unbounded
  `market_daily` FinanceQuery must return zero evidence, a `stale` trace,
  requested date `2026-07-27`, served date `2025-06-30`, and an explicit gap.
- [ ] Run the exact test and verify RED: current code returns one evidence atom
  marked current.
- [ ] Add `_structured_freshness_floor()`, `_is_current_query_stale()` and one
  `_stale_structured_result()` interface in `episode_tools`.
- [ ] Apply it after FinanceQuery execution and verify GREEN.

## Task 2: Preserve historical and frozen-cutoff semantics

- [ ] Add a test proving an explicit `time_range.end=2025-06-30` remains
  available despite a 2026-07-27 snapshot.
- [ ] Add a test proving snapshot 2026-07-27 plus information cutoff 2026-07-24
  requires only 2026-07-24 structured data.
- [ ] Use the same floor for `market_data` and `mainline_context`; remove the
  existing behavior that stamps every atom with `context.latest_data_date`.
- [ ] Run `test_episode_tools.py` and verify all current/historical cases pass.

## Task 3: Feed the floor from the API composition root

- [ ] Add a failing `_build_continuous_turn_adapter` test that supplies a valid
  snapshot contract and expects `today` plus served snapshot date in the
  Adapter.
- [ ] Add a small resolver that reads `validate_market_snapshot_root()` and
  falls back to the DuckDB latest date only when no decision-ready snapshot is
  available.
- [ ] Pass both dates into `ContinuousTurnAdapter`; never derive them from the
  code checkout.

## Task 4: Make readiness expose the same mismatch

- [ ] Add a failing API test with `ASK_CONTINUOUS_RUNTIME=on`, snapshot
  2026-07-16 and DuckDB 2025-06-30; expect `503`,
  `market_data_consistency=false`, and both dates in the bounded response.
- [ ] Add the consistency check to the critical readiness map only for on/canary
  continuous runtime.
- [ ] Update the standard readiness fixture with a matching DuckDB date and
  verify its existing green contract remains unchanged.

## Task 5: Verify and commit

- [ ] Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_workbench_api.py -q

/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  intelligence/api/app.py intelligence/services/episode_tools.py \
  intelligence/tests/test_episode_tools.py intelligence/tests/test_workbench_api.py

git diff --check
```

- [ ] Run the full `intelligence/tests` suite and confirm no new failure beyond
  the known 11 local `subconscious/userspace` environment failures.
- [ ] Commit the isolated slice as `fix: reject stale current market evidence`.

## Self-review

- Every current structured tool uses the same floor and stale result shape.
- Historical and frozen-cutoff queries remain supported.
- No question type, route, prompt, template, budget or evaluator threshold is
  added or changed.
- The sync writer remains outside the user request path.

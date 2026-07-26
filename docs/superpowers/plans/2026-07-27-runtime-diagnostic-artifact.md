# Runtime Diagnostic Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one live benchmark run self-diagnosing without exporting secrets, prompts, internal SQL, physical schema, or private filesystem paths.

**Architecture:** `RuntimeArmResult` remains the benchmark's single public result interface. A bounded `RuntimeDiagnostics` projection is added behind that seam; the runner builds it from the final episode outcome, structural verification result, and root budget. The projection allowlists useful event kinds and recursively redacts sensitive keys and values before serialization, so callers receive enough evidence to distinguish model protocol errors, tool/provider failures, cutoff rejection, verifier gaps, and budget exhaustion without learning internal execution details.

**Tech Stack:** Python dataclasses, immutable JSON-compatible projections, existing `AgentOutcome`/`VerifiedEpisodeOutcome`/`ProviderTrace`, pytest, Ruff.

---

## Public seams under test

1. `RuntimeDiagnostics.from_runtime_state(...)` returns a bounded, JSON-serializable and redacted projection of one completed runtime arm.
2. `RuntimeArmResult.to_dict()` and `from_dict()` preserve diagnostics across artifact round trips.
3. `scripts/run_agent_runtime_benchmark.py` writes the projection for research arms, including structural partial reasons and final root-budget state.

### Task 1: Add the safe diagnostic projection

**Files:**
- Modify: `intelligence/eval/runtime_backend_benchmark.py`
- Modify: `intelligence/tests/test_runtime_backend_benchmark.py`

- [x] **Step 1: Write the failing redaction and round-trip test**

Construct diagnostics with one `tool_request`, one `invalid_action`, one provider trace, gaps, bindings, and a root budget. Include forbidden `api_key`, `sql`, `table`, `messages`, and absolute `path` fields plus an `sk-...` value. Assert the useful fields survive, forbidden keys do not, sensitive values become `[REDACTED]`, event order is preserved, and `RuntimeArmResult.from_dict(arm.to_dict()) == arm`.

- [x] **Step 2: Run the focused test and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_runtime_backend_benchmark.py -q
```

Expected: import or constructor failure because `RuntimeDiagnostics` does not exist.

- [x] **Step 3: Implement the minimal deep module behind the result interface**

Add an immutable `RuntimeDiagnostics` dataclass with:

```python
events: tuple[dict[str, object], ...]
provider_traces: tuple[dict[str, object], ...]
missing_outputs: tuple[str, ...]
mandatory_missing_capabilities: tuple[str, ...]
gaps: tuple[str, ...]
bindings: tuple[dict[str, object], ...]
root_budget: dict[str, object] | None
future_of_cutoff: tuple[dict[str, object], ...]
```

Its factory allowlists `tool_request`, `tool_result`, `tool_error`, `invalid_action`, `finish`, `finalization`, `repair_goal`, `repair_outcome`, and `runtime_result`; bounds strings and collection sizes; removes sensitive keys; redacts secret-looking values; and derives `future_of_cutoff` from provider traces. Add `diagnostics` to `RuntimeArmResult` with an empty default for backward-compatible artifacts.

- [x] **Step 4: Run the test and verify GREEN**

Run the same focused command. Expected: all tests pass.

### Task 2: Wire diagnostics into live benchmark research arms

**Files:**
- Modify: `scripts/run_agent_runtime_benchmark.py`
- Modify: `intelligence/tests/test_run_agent_runtime_benchmark.py`

- [x] **Step 1: Write the failing runner integration test**

Drive `benchmark.main()` through the existing fake runtime seam. Return a partial outcome containing a safe tool request, an invalid action, a `future_of_cutoff` trace, a binding gap, and usage counts. Assert the emitted arm contains:

```python
arm["diagnostics"]["events"][...]
arm["diagnostics"]["missing_outputs"]
arm["diagnostics"]["mandatory_missing_capabilities"]
arm["diagnostics"]["gaps"]
arm["diagnostics"]["root_budget"]["remaining_calls"]
arm["diagnostics"]["future_of_cutoff"]
```

Also assert a secret and an internal SQL string planted in the fake event do not appear anywhere in the serialized artifact.

- [x] **Step 2: Run the integration test and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_run_agent_runtime_benchmark.py -q
```

Expected: `diagnostics` is absent from the arm.

- [x] **Step 3: Build diagnostics after structural verification**

In `_run_research_arm()`, build one `RuntimeDiagnostics` from `final_outcome`, the final structural result, and `context.root_budget.to_dict()`. Keep `artifact_sha256` bound to the full internal outcome for identity, but write only the safe projection. Failure, clarification, and deterministic fast-path arms use empty diagnostics.

- [x] **Step 4: Run integration and contract tests**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_runtime_backend_benchmark.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py -q
```

Expected: all tests pass.

### Task 3: Diagnose the weekly-market smoke before changing runtime policy

**Files:**
- Create: `/Users/a77/.finance-runtime/evals/weekly-market-cause-smoke-2026-07-27-r3.json` (local ignored artifact; never commit)
- Modify after diagnosis: only the smallest product module that the artifact proves responsible
- Modify: the matching public-seam regression test

- [ ] **Step 1: Run Ruff and deterministic regression tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/eval/runtime_backend_benchmark.py \
  scripts/run_agent_runtime_benchmark.py \
  intelligence/tests/test_runtime_backend_benchmark.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_repair_invariant_regression.py \
  intelligence/tests/test_session_invariant_regression.py -q
```

Expected: Ruff passes and 26 invariant tests pass.

- [ ] **Step 2: Re-run only the same failing live case once**

Use the existing `weekly-market-cause-smoke-input.json`, `continuous_glm`, the local finance/wiki roots, and the existing in-memory/Keychain provider injection. Do not run the frozen nine-case suite.

- [ ] **Step 3: Rank and test hypotheses from the diagnostic artifact**

Classify every invalid action as plan parsing, unauthorized/invalid tool request, tool/provider result, finalization schema, or repair failure. Identify which tools consumed the root budget, whether Eastmoney fallback succeeded, the exact structural missing outputs, and whether any cutoff rejection occurred. Change one variable only after the artifact distinguishes the hypotheses.

- [ ] **Step 4: Turn the proven cause into a public-seam failing test, then fix it**

The regression test must reproduce the real failed chain at its public interface. Apply the minimum fix, rerun the test, then rerun the original one-case smoke once to prove the user-visible symptom improved.

- [ ] **Step 5: Commit product code separately from verification documents**

First commit the diagnostics implementation and tests. Commit any subsequently proven runtime fix separately. Finally update the two existing verification documents with exact commands, counts, smoke artifact paths, and explicit non-actions.

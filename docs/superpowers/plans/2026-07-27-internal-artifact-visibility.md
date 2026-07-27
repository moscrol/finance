# Internal Artifact Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep full Episode diagnostics available for trusted local audit while making them unreachable from every public Workbench artifact interface.

**Architecture:** Persist a backward-compatible `public|internal` visibility value in the Run artifact contract. Enforce it at the public Run projection, RunArtifactProvider discovery and direct file-delivery seam; mark only `continuous-episode.json` internal and retain `report.json` as the bounded public projection.

**Tech Stack:** Python dataclasses, FastAPI, pytest/TestClient, existing RunStore and ArtifactRegistry.

---

## File structure

- Modify `intelligence/services/run_store.py`: visibility contract, validation and persistence.
- Modify `intelligence/services/conversation_orchestrator.py`: register the full Episode artifact as internal.
- Modify `intelligence/api/app.py`: omit internal artifacts from public Run payloads and deny direct delivery.
- Modify `intelligence/api/artifacts.py`: omit internal Run artifacts from registry discovery.
- Modify `intelligence/tests/test_run_store.py`: persistence, default compatibility and invalid-value behavior.
- Modify `intelligence/tests/test_workbench_api.py`: public-interface denial and public-artifact compatibility.
- Modify `intelligence/tests/test_conversation_orchestrator.py`: continuous Episode visibility assertion.

## Task 1: Persist one validated visibility contract

- [ ] **Step 1: Write the failing RunStore tests**

Add tests that register `audit.json` with `visibility="internal"`, assert the
private Run record retains that literal, assert an omitted value persists as
`public`, and assert `visibility="secret"` raises `ValueError` without writing
the file.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_run_store.py -q
```

Expected: failure because `add_artifact()` does not accept `visibility`.

- [ ] **Step 3: Implement the minimal contract**

Add `ARTIFACT_VISIBILITIES = {"public", "internal"}`, add
`visibility: str = "public"` to `Artifact`, accept a keyword-only visibility in
`add_artifact()`, validate before writing, and persist the field through
`asdict(artifact)`.

- [ ] **Step 4: Run the RunStore tests and verify GREEN**

Run the Step 2 command. Expected: all `test_run_store.py` tests pass.

## Task 2: Enforce visibility at every public interface

- [ ] **Step 1: Write one failing API tracer test**

Create a normal Run, add `continuous-episode.json` as internal through
`RunStore`, then assert:

```python
assert all(a["path"] != "continuous-episode.json" for a in get_run["artifacts"])
assert direct_internal.status_code == 404
assert direct_run_json.status_code == 404
assert not any("continuous-episode" in a["source_path"] for a in artifact_list)
assert direct_answer.status_code == 200
```

- [ ] **Step 2: Run the tracer and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_workbench_api.py -k internal_artifact -q
```

Expected: internal metadata and content are publicly reachable.

- [ ] **Step 3: Implement minimal enforcement**

In `_public_run_payload()`, retain only artifacts whose missing/default
visibility resolves to `public`. In `get_run_artifact()`, load the Run and serve
only a registered artifact with the exact normalized path, public visibility
and `downloadable=True`; otherwise return 404. In `RunArtifactProvider`, skip
metadata whose visibility is not public.

- [ ] **Step 4: Run the API tracer and adjacent artifact tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_run_store.py -q
```

Expected: all pass, including existing public artifact downloads and traversal
denials.

## Task 3: Mark Episode diagnostics internal and verify the product path

- [ ] **Step 1: Tighten the Conversation Orchestrator assertion**

Extend the existing continuous Episode artifact test to assert:

```python
private_artifact = next(a for a in run.artifacts if a["path"] == "continuous-episode.json")
assert private_artifact["visibility"] == "internal"
assert private_artifact["previewable"] is False
assert private_artifact["downloadable"] is False
```

- [ ] **Step 2: Run the assertion and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_conversation_orchestrator.py \
  -k continuous_episode -q
```

Expected: visibility/default flags do not yet identify the artifact as
internal.

- [ ] **Step 3: Register the artifact as internal**

Pass `visibility="internal"`, `previewable=False` and `downloadable=False` at
the single `continuous-episode.json` registration call. Extend
`RunStore.add_artifact()` with the two existing flag keywords so the persisted
contract and caller intent stay aligned.

- [ ] **Step 4: Run focused and full verification**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_run_store.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_conversation_orchestrator.py -q

/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests -q

git diff --check
```

Expected: focused suites and the clean full suite pass with no new failures;
`git diff --check` is silent.

- [ ] **Step 5: Commit the isolated slice**

```bash
git add intelligence/services/run_store.py \
  intelligence/services/conversation_orchestrator.py \
  intelligence/api/app.py intelligence/api/artifacts.py \
  intelligence/tests/test_run_store.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_conversation_orchestrator.py \
  docs/superpowers/specs/2026-07-27-internal-artifact-visibility-design.md \
  docs/superpowers/plans/2026-07-27-internal-artifact-visibility.md
git commit -m "fix: keep episode diagnostics internal"
```

## Self-review

- Spec coverage: persistence, public projection, registry discovery, direct
  delivery, compatibility and product registration each have a test step.
- Placeholder scan: no TBD/TODO or deferred implementation remains.
- Type consistency: the single `visibility` literal and existing
  `previewable/downloadable` flags flow from `RunStore.add_artifact()` into the
  persisted artifact dictionary used by every public seam.

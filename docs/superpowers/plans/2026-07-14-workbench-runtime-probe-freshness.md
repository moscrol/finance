# Workbench Runtime Probe Freshness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make stock notice preservation lossless off-path, runtime DuckDB provenance fresh and recoverable, and smoke cutoff validation monotonic.

**Architecture:** Keep notice preservation as a pure conditional transform. Model runtime probing as a path-keyed cache plus fingerprinted success entry and leased generation-aware inflight record. Compare validated ISO dates at the smoke protocol boundary and report both observations.

**Tech Stack:** Python 3.12, dataclasses, pathlib/stat, threading Future, pytest, existing TypeScript/Vitest frontend checks.

---

### Task 1: Preserve Unrelated Answer Text Exactly

**Files:**
- Modify: `intelligence/services/answer_model.py`
- Test: `intelligence/tests/test_answer_model.py`

- [ ] **Step 1: Write the failing exact-equality test**

```python
answer = "  原始答案\n\n"
assert preserve_required_system_notices(answer, no_notice_spec) == answer
```

- [ ] **Step 2: Run the focused test and confirm current `.strip()` behavior fails**

Run: `pytest intelligence/tests/test_answer_model.py -k preserve_required_system_notices -q`

- [ ] **Step 3: Return before normalization when the notice is not required**

```python
if NO_TRACEABLE_TARGET_COMPANY_EVIDENCE_NOTICE not in answer_spec.system_notices:
    return answer
text = str(answer or "").strip()
```

- [ ] **Step 4: Re-run the focused tests**

### Task 2: Versioned, Recoverable Runtime Probe

**Files:**
- Modify: `intelligence/services/conversation_orchestrator.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: Add failing tests for DB version change and transient failure recovery**

```python
assert first_cutoff == "2026-07-10"
db_path.write_bytes(b"new-version")
assert second_cutoff == "2026-07-13"
```

- [ ] **Step 2: Add failing concurrency tests for expired lease and old-late/new-fast completion**

```python
assert probe_calls == 2
assert cached_cutoff == "2026-07-13"
```

- [ ] **Step 3: Run focused tests and confirm stale positive cache and permanent inflight failures**

Run: `pytest intelligence/tests/test_conversation_orchestrator.py -k runtime_probe -q`

- [ ] **Step 4: Introduce immutable fingerprint, cache-entry, and inflight-entry records**

```python
@dataclass(frozen=True)
class _RuntimeProbeInflight:
    future: Future[str | None]
    started_at: float
    generation: int
```

- [ ] **Step 5: Validate cache fingerprint and generation ownership before mutation**

```python
if current is not None and current.generation == generation:
    if cutoff is not None and fingerprint is not None:
        _RUNTIME_PROBE_CACHE[key] = cache_entry
    _RUNTIME_PROBE_INFLIGHT.pop(key, None)
future.set_result(cutoff)
```

- [ ] **Step 6: Re-run runtime probe tests**

### Task 3: Enforce Smoke Cutoff Freshness

**Files:**
- Modify: `scripts/smoke_workbench_self_use.py`
- Test: `tests/test_smoke_workbench_self_use.py`

- [ ] **Step 1: Add older/equal/later fixtures and assertions**

```python
assert older_exit_code == 2
assert equal_exit_code == 0
assert later_summary["cutoffs"]["terminal"] == "2026-07-13"
```

- [ ] **Step 2: Run focused smoke tests and confirm the older fixture currently passes**

Run: `pytest tests/test_smoke_workbench_self_use.py -k cutoff -q`

- [ ] **Step 3: Reject terminal dates older than readiness and report both values**

```python
if terminal_cutoff is None or terminal_cutoff < readiness_cutoff:
    raise SmokeProtocolError("run_metadata")
```

- [ ] **Step 4: Re-run smoke tests**

### Task 4: Regression and Single Commit

**Files:** all files above plus existing frontend regression tests.

- [ ] **Step 1: Run expanded Python and frontend test suites**
- [ ] **Step 2: Run Ruff, frontend typecheck/lint, `git diff --check`, and pre-commit**
- [ ] **Step 3: Stage only intended files and create one commit without push or merge**

```bash
git commit -m "fix: refresh runtime probe provenance"
```

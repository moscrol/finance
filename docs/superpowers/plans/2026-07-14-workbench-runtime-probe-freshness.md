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

### Task 5: Include DuckDB WAL in the Version Boundary

**Files:**
- Modify: `intelligence/services/conversation_orchestrator.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: Add a real DuckDB writer/WAL regression test**

```python
writer = duckdb.connect(str(runtime_inputs.market_db_path))
writer.execute("insert into fact_market_daily values (?)", ["2026-07-13"])
wal_path = Path(f"{runtime_inputs.market_db_path}.wal")
assert wal_path.is_file()
assert _runtime_cutoff_with_timeout(runtime_inputs) == "2026-07-13"
```

- [ ] **Step 2: Run the WAL test and confirm the old 07-10 cache is returned**

Run: `pytest intelligence/tests/test_conversation_orchestrator.py -k wal -q`

- [ ] **Step 3: Replace the single-file fingerprint with a DB/WAL composite**

```python
@dataclass(frozen=True)
class _RuntimeDatabaseFingerprint:
    database: _RuntimeFileFingerprint
    wal: _RuntimeFileFingerprint
```

The WAL fingerprint records `exists=False` with nullable stat fields when absent. A stat error returns `None` for the composite. Resolve the WAL from `Path(f"{database.canonical_path}.wal")`.

- [ ] **Step 4: Make probe-time fingerprint changes fail closed**

```python
effective_cutoff = (
    cutoff
    if inflight.fingerprint is not None
    and completed_fingerprint == inflight.fingerprint
    else None
)
inflight.future.set_result(effective_cutoff)
```

- [ ] **Step 5: Re-run the WAL and existing fingerprint tests**

### Task 6: Bound Physical Probe Workers

**Files:**
- Modify: `intelligence/services/conversation_orchestrator.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: Add a short-lease capacity stress test**

```python
monkeypatch.setattr(module, "_RUNTIME_PROBE_SLOTS", BoundedSemaphore(2))
for _ in range(6):
    assert _runtime_cutoff_with_timeout(runtime_inputs) is None
    time.sleep(0.01)
assert probe_calls == 2
assert max_active_workers == 2
```

- [ ] **Step 2: Assert releasing one old worker permits recovery**

```python
release_events[0].set()
assert old_futures[0].result(timeout=0.2) == "2026-07-10"
assert _runtime_cutoff_with_timeout(runtime_inputs) == "2026-07-13"
```

- [ ] **Step 3: Run the capacity test and confirm calls exceed two before the fix**

Run: `pytest intelligence/tests/test_conversation_orchestrator.py -k physical_capacity -q`

- [ ] **Step 4: Acquire a non-blocking semaphore slot before creating inflight state**

```python
probe_slots = _RUNTIME_PROBE_SLOTS
if not probe_slots.acquire(blocking=False):
    return None
```

- [ ] **Step 5: Release the captured semaphore only when the actual worker exits**

```python
def probe_once() -> None:
    try:
        run_probe()
    finally:
        probe_slots.release()
```

- [ ] **Step 6: Run focused, expanded backend, frontend, static, and pre-commit checks**

- [ ] **Step 7: Create one commit without push or merge**

```bash
git commit -m "fix: bound WAL-aware runtime probes"
```

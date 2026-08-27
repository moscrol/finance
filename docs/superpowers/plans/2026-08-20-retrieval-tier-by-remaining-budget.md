# Retrieval Tier by Remaining Budget Implementation Plan

> **Status (2026-08-20):** Implemented on `fix/retrieval-tier-remaining-budget`. Commits `42d715a3` → `5ffa3934`. Tasks 1–4 landed. Spec §11 last box waits for merge.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `kb_rag.retrieve` is given a remaining window under 15 seconds, skip dense/hybrid/rerank and run BM25, recording `fallback_reason="remaining_budget"`.

**Architecture:** One pure function `select_mode_for_remaining` next to `_DENSE_MODES`. `retrieve()` applies it before building the worker command, so every caller (`episode_tools`, `ask.py`, `evidence_providers`, …) gets the same seam. Do not add a runtime strategy module or change batch slot/timeout constants.

**Tech Stack:** Python 3, existing `RetrievalTelemetry`, pytest via `.venv-workbench/bin/python`.

**Worktree:** from latest `gitea/main`, branch `fix/retrieval-tier-remaining-budget`. Do not implement on `feat/reading-rules-baseline-batch1`.

Spec: `docs/superpowers/specs/2026-08-20-retrieval-tier-by-remaining-budget-design.md`

---

### Task 1: Pure selector + failing tests

**Files:**
- Create: `intelligence/tests/test_retrieval_tier_by_remaining_budget.py`
- Modify: `intelligence/services/kb_rag.py` (constants + function only in Task 2)

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from intelligence.services import kb_rag
from intelligence.services.agent_research import _describe_retrieval_degradation


def test_four_seconds_selects_bm25() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 4.0)
    assert mode == "bm25"
    assert reason == "remaining_budget"


def test_incident_grant_selects_bm25() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 11.955)
    assert mode == "bm25"
    assert reason == "remaining_budget"


def test_twenty_seconds_keeps_hybrid() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 20.0)
    assert mode == "hybrid"
    assert reason is None


def test_already_bm25_is_not_labeled_degraded() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("bm25", 4.0)
    assert mode == "bm25"
    assert reason is None
```

`test_four_seconds_selects_bm25` **就是**台账里的变异闸：有人把 `HYBRID_MIN_REMAINING_SECONDS` 改成 `0`、或让函数恒返回 `hybrid`，这一条必须红。不要再写一条「恒 hybrid」的绿测。

- [ ] **Step 2: Run to verify they fail**

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/test_retrieval_tier_by_remaining_budget.py
```

Expected: FAIL with `AttributeError: select_mode_for_remaining` (or import error). Interpreter must be `.venv-workbench/bin/python`.

- [ ] **Step 3: Add the selector**

In `intelligence/services/kb_rag.py`, next to `DEFAULT_RAG_MODE`:

```python
HYBRID_MIN_REMAINING_SECONDS = 15.0
REMAINING_BUDGET_FALLBACK = "remaining_budget"
```

Immediately after `_DENSE_MODES = frozenset({"hybrid", "dense", "rerank"})`:

```python
def select_mode_for_remaining(
    requested: str,
    remaining_seconds: float,
) -> tuple[str, str | None]:
    """Map remaining wall-clock seconds to a retrieval mode. No I/O."""
    requested_mode = str(requested or "")
    if (
        requested_mode in _DENSE_MODES
        and float(remaining_seconds) < HYBRID_MIN_REMAINING_SECONDS
    ):
        return "bm25", REMAINING_BUDGET_FALLBACK
    return requested_mode, None
```

- [ ] **Step 4: Re-run Task 1 tests**

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/test_retrieval_tier_by_remaining_budget.py
```

Expected: the five selector tests PASS. Retrieve tests (Task 2) are not in the file yet.

- [ ] **Step 5: Commit** (pathspec only)

```bash
git commit -m "$(cat <<'EOF'
test: lock remaining-budget retrieval tier selector

EOF
)" -- intelligence/tests/test_retrieval_tier_by_remaining_budget.py intelligence/services/kb_rag.py
```

If the test file-only commit is preferred before implementation exists, commit tests first as red is allowed only if the next commit lands the function in the same session; otherwise land selector+tests together as above.

---

### Task 2: Apply the selector inside `retrieve()` before any dense worker call

**Files:**
- Modify: `intelligence/services/kb_rag.py` (`retrieve`, after telemetry records `requested_mode`)
- Modify: `intelligence/tests/test_retrieval_tier_by_remaining_budget.py`

- [ ] **Step 1: Add retrieve tests that fail on current `retrieve()`**

Append to the test file. Reuse the wiki stub shape from `test_kb_rag.py`:

```python
def _fresh_hit() -> list[dict]:
    return [
        {
            "page_id": "a",
            "file_path": "wiki/concepts/光刻机.md",
            "title": "A",
            "score": 0.9,
            "best_chunk_id": "a::0",
            "content_hash": "hash-a",
            "evidence_text": "A matched chunk",
            "index_source_revision": "abc123",
            "index_freshness": "fresh",
        }
    ]


def _stub_wiki(td: str) -> Path:
    root = Path(td)
    page = root / "wiki" / "concepts" / "光刻机.md"
    script = root / kb_rag.RAG_SCRIPT_REL
    page.parent.mkdir(parents=True)
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    page.write_text("# 光刻机\n\n正文材料。\n", encoding="utf-8")
    (root / ".rag_index").mkdir()
    return root


def test_retrieve_four_seconds_never_invokes_hybrid() -> None:
    proc = mock.Mock(
        returncode=0,
        stdout=json.dumps(_fresh_hit(), ensure_ascii=False),
        stderr="",
    )
    with tempfile.TemporaryDirectory() as td:
        root = _stub_wiki(td)
        with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=True):
            with mock.patch("subprocess.run", return_value=proc) as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=4,
                )
    assert run.call_count == 1
    cmd = run.call_args.args[0]
    assert "--mode" in cmd
    assert cmd[cmd.index("--mode") + 1] == "bm25"
    assert "hybrid" not in cmd[cmd.index("--mode") + 1]
    assert res.ok
    assert res.hits
    assert res.telemetry.requested_mode == "hybrid"
    assert res.telemetry.effective_mode == "bm25"
    assert res.telemetry.fallback_reason == "remaining_budget"
    assert res.telemetry.degraded is True
    note = _describe_retrieval_degradation(res.telemetry)
    assert "remaining_budget" in note


def test_retrieve_twenty_seconds_keeps_hybrid_command() -> None:
    proc = mock.Mock(
        returncode=0,
        stdout=json.dumps(_fresh_hit(), ensure_ascii=False),
        stderr="",
    )
    with tempfile.TemporaryDirectory() as td:
        root = _stub_wiki(td)
        with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=True):
            with mock.patch("subprocess.run", return_value=proc) as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=20,
                )
    cmd = run.call_args.args[0]
    assert cmd[cmd.index("--mode") + 1] == "hybrid"
    assert res.telemetry.fallback_reason != "remaining_budget"
    assert res.telemetry.effective_mode == "hybrid"
```

- [ ] **Step 2: Run; expect 4s retrieve test FAIL** (`--mode hybrid` still sent)

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/test_retrieval_tier_by_remaining_budget.py
```

- [ ] **Step 3: Wire `retrieve()`**

In `retrieve()`, keep `tel.requested_mode = str(mode)` as today. Immediately after the initial `requested_mode` / `tel.requested_mode` assignment, add:

```python
    planned_mode, budget_reason = select_mode_for_remaining(
        requested_mode, float(timeout)
    )
    tel.effective_mode = planned_mode
    tel.mode = planned_mode
    tel.recall_desc = _MODE_RECALL_DESC.get(planned_mode, "")
    if budget_reason:
        tel.fallback_reason = budget_reason
        tel.degraded = True
```

Replace the later `effective_mode = requested_mode` (the line that currently starts the worker-mode block, today around the `dense_disabled_until` check) with:

```python
    effective_mode = planned_mode
```

Capability fallback must use `effective_mode in _DENSE_MODES` (or `planned_mode`), **not** `requested_mode in _DENSE_MODES` after a time-tier already chose BM25. If `tel.fallback_reason` is already `REMAINING_BUDGET_FALLBACK`, do not overwrite it with `dense_dependency_*`.

Do not send a dense/hybrid/rerank worker argv when `planned_mode == "bm25"` due to time.

- [ ] **Step 4: Re-run Task 2 tests — all PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: pick BM25 when retrieve remaining window is under 15s

EOF
)" -- intelligence/services/kb_rag.py intelligence/tests/test_retrieval_tier_by_remaining_budget.py
```

---

### Task 3: Keep capability-fallback tests off the time-tier path

**Files:**
- Modify: `intelligence/tests/test_kb_rag.py`

These tests pass `timeout=5` as a **subprocess ceiling**, not an episode remainder. After Task 2 they would time-tier first and never exercise `dense_dependency_*` / legacy CLI.

- [ ] **Step 1: Change `timeout=5` → `timeout=20` in**

  - `test` that first asserts `"hybrid"` in `run.call_args_list[0]` then BM25 (`dense_dependency_missing`)
  - `test_dense_dependency_failure_marks_next_call_cached_fallback` (both retrieves)
  - `test_legacy_cli_retries_without_evidence_chars`
  - `test_bm25_fallback_still_rejects_stale_hits`
  - `test_unrelated_retriever_error_does_not_fall_back`

- [ ] **Step 2: Fix `test_dense_dependency_failure_skips_fallback_without_budget`**

Keep the intent: try dense, fail, remaining after the fail `< 1s`, do **not** fire a BM25 retry.

Change to `timeout=20` and jump the clock by ≥19s, for example:

```python
with mock.patch(
    "time.monotonic",
    side_effect=[10.0, 29.5, 29.5],
):
    res = kb_rag.retrieve(
        "光刻机",
        root / "wiki",
        mode="dense",
        timeout=20,
    )
```

Assertions stay: `run.call_count == 1`, `effective_mode == "dense"`, `fallback_reason == "dense_dependency_missing"`, warning contains `剩余预算不足`.

- [ ] **Step 3: Run**

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/test_kb_rag.py intelligence/tests/test_retrieval_tier_by_remaining_budget.py intelligence/tests/test_agent_research.py intelligence/tests/test_episode_tool_batch.py
```

Expected: PASS. `test_episode_tool_batch` still rejects a 5th call with `tool_budget_exhausted`.

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
test: give capability-fallback kb_rag fixtures a 20s window

EOF
)" -- intelligence/tests/test_kb_rag.py
```

---

### Task 4: Spec receipt + ruff

**Files:**
- Modify: `docs/superpowers/specs/2026-08-20-retrieval-tier-by-remaining-budget-design.md` (checkboxes in §11 only)

- [ ] **Step 1:** `ruff check intelligence/services/kb_rag.py intelligence/tests/test_retrieval_tier_by_remaining_budget.py intelligence/tests/test_kb_rag.py`

- [ ] **Step 2:** Tick §11 boxes that are done. Do not edit the truth table.

- [ ] **Step 3:** Commit pathspec for the spec checkboxes if the user wants docs in the same branch.

Do **not** change `ASK_TOOL_BATCH_TIMEOUT`, `MAX_BATCH_TOOL_CALLS`, `ToolSpec`, or `followups.py`.

---

## Spec coverage

| Spec | Task |
|---|---|
| 4s / 11.955 / 20s / already-bm25 / mutation | Task 1 |
| `retrieve()` before dense worker; `remaining_budget` telemetry; model-visible note | Task 2 |
| `test_kb_rag.py` timeout=5 fixtures | Task 3 |
| Slot-gate regression | Task 3 pytest includes `test_episode_tool_batch.py` |
| Ban list (no strategy module, no ToolSpec fields) | Tasks 1–2 file list |

# Evidence Search Retrieval Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin a true-Hybrid two-case baseline and expose requested/effective mode, fallback reason, and degraded state for every retrieval attempt returned by `EvidenceSearchResult`.

**Architecture:** Keep `RetrievalAttempt` as the ordered source of truth because it already represents each narrow/broad/counter call. Copy the four immutable mode/fallback facts from `WikiRagResult.telemetry` when an attempt is recorded, then summarize them in the existing `ProviderTrace.detail` for downstream inspector visibility. Preserve all existing freshness, cutoff, status, and evidence projection behavior.

**Tech Stack:** Python 3.12, dataclasses, existing `kb_rag`/closed-loop retrieval/EvidenceSearch modules, pytest, BGE-m3 + RRF Hybrid retrieval.

---

### Task 1: Pin the true-Hybrid pre-change baseline

**Files:**
- Create: `docs/verification/phase-c-true-hybrid-baseline-2026-07-29.json`
- Modify after probe cleanup only: `/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/wiki/relations/access_log.jsonl`

- [ ] **Step 1: Verify interpreter and snapshot identity**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 \
  /Users/a77/knowledge-base-private/.rag_venv/bin/python3 - <<'PY'
import sys
import FlagEmbedding, rank_bm25, yaml, numpy
print(sys.version.split()[0])
print("dense imports: ok")
PY

cd /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness
shasum -a 256 .rag_index/meta.json .rag_index/chunks.jsonl \
  .rag_index/dense.npy .rag_index/bm25_tokens.jsonl.gz
```

Expected: Python `3.12.13`; all imports pass; hashes match the clean receipt
(`3ab0d301...`, `76034c6e...`, `6a012a5c...`, `64549ce...`).

- [ ] **Step 2: Run both cases through the real EvidenceSearch path**

Run from the finance candidate with:

```bash
KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python3 \
RAG_INDEX_DIR=/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/.rag_index \
RAG_BGE_MODEL=/Users/a77/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181 \
RAG_WORKER_ENABLED=1 HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python - <<'PY'
from datetime import date
from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services import entity_anchor, evidence_search, kb_rag
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline

wiki = "/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/wiki"
knowledge = KnowledgeAdapter(wiki_root=wiki)
cutoff = InformationCutoff(date(2026, 7, 24), "requested")
kb_rag.prewarm(wiki, timeout=240)
for case_id, query in (
    ("ruihuatai-valuation", "瑞华泰的合理估值"),
    ("weekly-market-cause", "这一周行情下跌的主要原因是什么"),
):
    kb_rag.clear_result_cache()
    result = evidence_search.EvidenceSearch(
        lambda candidate: kb_rag.retrieve(
            candidate, wiki, k=6, mode="hybrid", timeout=90,
            excerpt_chars=240, budget_query=query, require_fresh=True,
            cache_scope=f"phase-c-true-hybrid:{case_id}",
        ),
        semantic_judge=None,
    ).search(
        query=query,
        anchor=entity_anchor.resolve_entity_anchor(query, knowledge),
        information_cutoff=cutoff,
        deadline=ResearchDeadline.from_timeout(180),
    )
    print(case_id, result.trace.to_dict())
    print([item.source for item in result.evidence])
PY
```

Expected: both cases execute with the explicit dense interpreter and all
returned atoms remain `fresh`. The valuation case must retain `天奈科技` in the
pre-filter baseline if the independently observed ranking is reproducible.

- [ ] **Step 3: Record the baseline artifact and clean generated logs**

Create the JSON receipt with `apply_patch`, recording interpreter path/version,
the four index hashes, cutoff, case queries, elapsed time, attempts, trace, top
evidence paths, and the pre-change limitation that per-attempt mode telemetry is
not yet exposed. Remove only the probe-generated access-log lines with
`apply_patch`, then require:

```bash
git -C /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness status --short
```

Expected: empty output.

- [ ] **Step 4: Validate and commit the baseline**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m json.tool \
  docs/verification/phase-c-true-hybrid-baseline-2026-07-29.json >/dev/null
git add docs/verification/phase-c-true-hybrid-baseline-2026-07-29.json
git commit -m "docs: pin true Hybrid Phase C baseline"
```

### Task 2: Preserve mode/fallback telemetry per retrieval attempt

**Files:**
- Modify: `intelligence/services/closed_loop_retrieval.py`
- Test: `intelligence/tests/test_closed_loop_retrieval.py`

- [ ] **Step 1: Write the failing attempt-telemetry test**

Add a test whose first response uses
`fallback_reason="dense_dependency_missing"` and later responses use
`fallback_reason="dense_dependency_cached_unavailable"`, all with
`requested_mode="hybrid"`, `effective_mode="bm25"`, and `degraded=True`.
Assert:

```python
assert [
    (
        item.requested_mode,
        item.effective_mode,
        item.fallback_reason,
        item.degraded,
    )
    for item in result.attempts
] == [
    ("hybrid", "bm25", "dense_dependency_missing", True),
    ("hybrid", "bm25", "dense_dependency_cached_unavailable", True),
    ("hybrid", "bm25", "dense_dependency_cached_unavailable", True),
]
```

Also assert the same four fields appear in each item returned by
`result.inspector_dict()["attempts"]`.

- [ ] **Step 2: Run the test and observe RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_closed_loop_retrieval.py -q
```

Expected: fail because `RetrievalAttempt` has no mode/fallback fields.

- [ ] **Step 3: Implement the minimal per-attempt fields**

Extend `RetrievalAttempt` with defaults:

```python
requested_mode: str = ""
effective_mode: str = ""
fallback_reason: str = ""
degraded: bool = False
```

When `_run_aperture` records a real response, copy the values from
`response.telemetry`. Leave budget-exhausted attempts at defaults. Add the four
fields to `inspector_dict()` serialization.

- [ ] **Step 4: Run the test and observe GREEN**

Run the command from Step 2. Expected: all closed-loop retrieval tests pass.

- [ ] **Step 5: Commit the attempt ledger slice**

```bash
git add intelligence/services/closed_loop_retrieval.py \
  intelligence/tests/test_closed_loop_retrieval.py
git commit -m "feat: preserve retrieval mode per evidence attempt"
```

### Task 3: Expose attempt modes in the EvidenceSearch provider trace

**Files:**
- Modify: `intelligence/services/evidence_search.py`
- Test: `intelligence/tests/test_evidence_search.py`

- [ ] **Step 1: Write failing fallback and true-Hybrid trace tests**

For the fallback fixture assert `result.attempts` preserves both first-call and
cached reasons, and `result.trace.detail` contains:

```text
retrieval_modes=hybrid->bm25:dense_dependency_missing:degraded,
hybrid->bm25:dense_dependency_cached_unavailable:degraded
```

For a true-Hybrid fixture assert every attempt is
`hybrid -> hybrid`, fallback is empty, degraded is false, and trace detail
contains `retrieval_modes=hybrid->hybrid`.

- [ ] **Step 2: Run the tests and observe RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_evidence_search.py -q
```

Expected: attempt assertions may pass after Task 2, but trace detail assertions
fail because `_trace_detail` does not report retrieval modes.

- [ ] **Step 3: Add deterministic trace aggregation**

Update `_trace_detail` to deduplicate ordered mode signatures from attempts.
Format each as `requested->effective`, append `:<fallback_reason>` when set,
and append `:degraded` when true. Do not change provider success/empty status.

- [ ] **Step 4: Run EvidenceSearch and episode-tool focused tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_episode_tools.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit the trace slice**

```bash
git add intelligence/services/evidence_search.py \
  intelligence/tests/test_evidence_search.py
git commit -m "feat: expose evidence retrieval degradation"
```

### Task 4: Re-run true Hybrid with the new telemetry and hand off

**Files:**
- Create: `docs/verification/phase-c-evidence-telemetry-2026-07-29.md`
- Create: `docs/handoffs/2026-07-29-evidence-telemetry-handoff.md`

- [ ] **Step 1: Re-run the Task 1 two-case command**

Require every executed attempt to report `requested_mode=hybrid`,
`effective_mode=hybrid`, empty fallback reason, and `degraded=false`. If any
attempt differs, mark the run invalid rather than calling it true Hybrid.

- [ ] **Step 2: Remove generated access-log lines and verify isolation**

Use `git diff -- wiki/relations/access_log.jsonl` to identify only the new probe
lines, remove them with `apply_patch`, and require the KB clone to be clean.
Confirm original KB remains `main@883815c9` with 0 dirty indexed page entries.

- [ ] **Step 3: Run proportional regression**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_kb_rag.py \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/services/closed_loop_retrieval.py \
  intelligence/services/evidence_search.py \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_evidence_search.py
git diff --check
```

Record the exact interpreter for every pass count.

- [ ] **Step 4: Write verification and handoff**

The verification must distinguish the pre-change true-Hybrid quality baseline
from the post-change telemetry proof. The handoff must keep causal anchor guard
and valuation filtering as the next separate slices, preserving `天奈科技` as
the known Hybrid contamination case.

- [ ] **Step 5: Commit the final evidence**

```bash
git add docs/verification/phase-c-evidence-telemetry-2026-07-29.md \
  docs/handoffs/2026-07-29-evidence-telemetry-handoff.md
git commit -m "docs: hand off evidence retrieval telemetry"
```

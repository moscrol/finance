# Phase C Freshness Seam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make manifest-matching format-2 indexes reach `fresh` through the real finance runtime, then pin the clean snapshot, capability dry-run, and bounded Phase C replay artifacts.

**Architecture:** Implement the freshness policy in the knowledge-base CLI seam, with the Wiki root explicitly supplied to manifest calculation. Keep content freshness separate from Git/build provenance, then validate the resulting hits through the existing finance `kb_rag.require_fresh` boundary.

**Tech Stack:** Python 3.12, pytest/unittest, existing Hybrid RAG store and CLI, existing finance runtime/evidence-search tooling, Git isolated clone.

---

### Task 1: Isolated knowledge-base implementation branch

**Files:**
- Create working copy: `/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness`

- [ ] **Step 1: Clone only committed source state**

```bash
git clone --shared /Users/a77/knowledge-base-private /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness
git -C /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness checkout -b fix/manifest-freshness-cli 883815c9
```

- [ ] **Step 2: Verify isolation**

```bash
git -C /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness status --short
git -C /Users/a77/knowledge-base-private status --short
```

Expected: isolated clone clean; original status byte-for-byte unchanged.

### Task 2: Manifest-first freshness — red to green

**Files:**
- Modify: `/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/scripts/rag_freshness.py`
- Modify: `/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/scripts/rag_index.py`
- Modify: `/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/tests/test_rag_index_freshness.py`

- [ ] **Step 1: Add failing manifest behavior tests**

Add public-seam tests proving:

```python
status, diagnostics = check_index_freshness(
    meta,
    repo=repo,
    vault_root=vault,
    page_type_dirs=("entities", "concepts"),
    max_age_days=7,
)
assert status == "fresh"
assert "index was built from dirty source" in diagnostics
```

The fixture must have a matching format-2 manifest, a differing Git provenance,
and `source_dirty=True`. Add separate literal expectations for changed manifest
(`stale`), legacy/missing manifest (`unknown`), and expired age (`stale`).

- [ ] **Step 2: Run the focused tests and observe RED**

```bash
python -m pytest tests/test_rag_index_freshness.py -q
```

Expected: new tests fail because `vault_root` is unsupported and Git/dirty state
still controls effective freshness.

- [ ] **Step 3: Implement the minimal freshness policy**

Extend `check_index_freshness` with explicit `vault_root`. For format-2 manifest
metadata, compute effective content state from the same manifest implementation
used by `RagStore.index_freshness(vault_root)`. Preserve Git/source-dirty text in
the returned diagnostics, but only manifest mismatch and age may produce stale;
manifest uncertainty produces unknown.

Update `rag_index._freshness` and `cmd_query` so the loaded store and `_vault()`
participate in that decision. Do not set stale policy to ignore.

- [ ] **Step 4: Run focused tests and observe GREEN**

```bash
python -m pytest tests/test_rag_index_freshness.py skills/lib/rag/tests/test_include_raw_freshness.py skills/lib/rag/tests/test_retrieval_provenance.py -q
```

Expected: all pass.

- [ ] **Step 5: Add CLI public-seam regression**

Use a temporary format-2 index and Wiki fixture to invoke `cmd_query` with
default fail policy. Assert fresh hits are emitted; change one indexed file and
assert exit code `3`.

- [ ] **Step 6: Commit the KB slice**

```bash
git add scripts/rag_freshness.py scripts/rag_index.py tests/test_rag_index_freshness.py
git commit -m "fix: use manifest freshness for RAG queries"
```

### Task 3: Clean snapshot receipt

**Files:**
- Create under runtime worktree: `docs/verification/phase-c-clean-rag-snapshot-2026-07-29.md`
- Create outside Git: `/private/tmp/phase-c-clean-rag-index/`

- [ ] **Step 1: Copy the current BGE-m3 index into the isolated snapshot area**

```bash
cp -R /Users/a77/knowledge-base-private/.rag_index /Users/a77/finance-workspace-private/tmp/phase-c-clean-rag-index
```

- [ ] **Step 2: Run a clean incremental refresh**

Run the isolated CLI with the isolated clean Wiki and copied index. Require
`reused=104611`, `embedded=0`, `removed=0`, `source_dirty=false`, and the same
manifest revision. If those conditions are not met, stop and report the exact
delta rather than building a substitute index.

- [ ] **Step 3: Pin hashes and three freshness layers**

Record artifact SHA-256 hashes, `rag_index.py check`, CLI JSON freshness, and a
finance `kb_rag.retrieve(require_fresh=True)` probe against the exact root/index.

- [ ] **Step 4: Commit the receipt**

```bash
git add docs/verification/phase-c-clean-rag-snapshot-2026-07-29.md
git commit -m "docs: pin clean Phase C RAG snapshot"
```

### Task 4: Capability dry-run and bounded replay

**Files:**
- Create: `docs/verification/phase-c-capability-dry-run-2026-07-29.json`
- Create: `docs/verification/phase-c-evidence-search-replay-2026-07-29.json`
- Create: `docs/verification/phase-c-evidence-search-replay-hybrid-2026-07-29.json`
- Create/modify: runtime verification document in the candidate worktree

- [ ] **Step 1: Generate current capability dry-run**

Run the candidate revision's benchmark dry-run command (no provider or tool
execution):

```bash
python3 scripts/run_agent_runtime_benchmark.py \
  --dry-run --backend sdk_gpt \
  --questions-file /Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json \
  --output docs/verification/phase-c-capability-dry-run-2026-07-29.json
```

The external evals directory is not a required write target for this slice;
the candidate-worktree artifact is the committed receipt. Assert the contract
is non-null and record whether `evidence_search` is actually allowed for
valuation and weekly-cause cases.

- [ ] **Step 2: Replay 瑞华泰 valuation through evidence_search**

Pin root/index receipt identifiers and record latency, candidates, filters, and
returned atoms. No LLM benchmark is required.

- [ ] **Step 3: Replay weekly-cause query through evidence_search**

Use the same receipt and record the same telemetry. Separate premise correction,
market-internal mechanism, unique external catalyst, and honest unavailability.

- [ ] **Step 4: Classify gaps without adding tools/routes**

Write one evidence-backed classification for each query. Do not tune verifier
thresholds or add unrestricted Wiki grep.

### Task 5: Completion verification and handoff

**Files:**
- Create: `docs/verification/phase-c-retrieval-contract-2026-07-29.md`
- Create: `docs/handoffs/2026-07-29-phase-c-completion-handoff.md`

- [ ] **Step 1: Run proportional gates**

Run KB focused/full tests affected by the change, finance focused retrieval and
benchmark-contract tests, Ruff where configured, and `git diff --check` in both
repositories.

- [ ] **Step 2: Audit every goal requirement**

Check isolation, runtime fresh, receipt, dry-run, both replays, gap
classification, and untouched main/8792/8799/28-case/App Server boundaries.

- [ ] **Step 3: Commit the final evidence and handoff**

```bash
git add docs/verification/phase-c-retrieval-contract-2026-07-29.md docs/handoffs/2026-07-29-phase-c-completion-handoff.md
git commit -m "docs: hand off completed Phase C retrieval diagnosis"
```

## Execution record (2026-07-29)

Tasks 1–4 are complete on the isolated runtime branch. The formal KB clone is
`/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness`
(`fix/manifest-freshness-cli`, code `9053b0c4`), and the candidate runtime tip
is `d92b554a`. The clean receipt, capability dry-run, deterministic replay,
and production-mode replay are committed under `docs/verification/`.

The final verification and handoff in Task 5 are now written in the candidate
worktree and will be committed as the final evidence slice. The KB clone's
generated access-log probe entries were removed before its clean-status check;
no source Wiki or canonical runtime was modified by this work.

### Final execution checklist

- [x] Isolated KB implementation and manifest-first freshness tests.
- [x] Clean snapshot receipt and exact artifact hashes.
- [x] Capability dry-run with non-null contracts.
- [x] Bounded valuation and weekly-cause evidence replays.
- [x] Gap classification, focused gates, full-suite baseline accounting, and
  final verification/handoff.

# Memory Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make durable memory promotion a fail-closed, provenance-checked decision instead of allowing a model draft or volatile market fact to become timeless prior.

**Architecture:** `MemoryGate` is a pure deep module at the write seam. It evaluates a typed candidate against existing append-only checkpoint/verdict and correction records, returning a machine-readable `PromotionDecision`; it does not write files or invent provenance. Existing legacy `judgments.jsonl` records remain readable for compatibility but are not treated as newly validated promotions.

**Tech Stack:** Frozen Python dataclasses, existing `checkpoints`/`corrections` record shapes, stdlib, pytest, Ruff.

---

## Public seam under test

```python
decision = MemoryGate().decide(
    candidate,
    checkpoints=checkpoints,
    verdicts=verdicts,
    corrections=corrections,
)
```

The returned `PromotionDecision` contains `eligible`, `target_layer`, `reason`,
and a provenance object. It never contains current prices, prompt text, or
unverified model reasoning as evidence.

### Task 1: Add the pure fail-closed gate

**Files:**
- Create: `intelligence/services/memory_gate.py`
- Create: `intelligence/tests/test_memory_gate.py`

- [x] **Step 1: Write RED candidate/decision tests**

```python
assert gate.decide(
    MemoryCandidate("lesson-1", "decision_lesson", "估值判断方法", checkpoint_id="c1"),
    checkpoints=({"id": "c1", "claim": "..."},),
    verdicts=({"id": "c1", "verdict": "hit"},),
    corrections=(),
).eligible is True

assert gate.decide(
    MemoryCandidate("fact-1", "volatile_fact", "今天收盘 123"),
    checkpoints=(), verdicts=(), corrections=(),
).eligible is False
```

Also cover miss/partial as valid reviewed learning, unverifiable as rejected,
unknown checkpoint, missing correction provenance, duplicate terminal verdict
selection, and candidate content that tries to carry a price/date as timeless
memory. No test writes a ledger.

- [x] **Step 2: Run RED**

- [x] **Step 3: Implement immutable values and the decision table**

Allowed promotion kinds:

- `decision_lesson`: checkpoint exists and latest terminal verdict is `hit`,
  `partial`, or `miss`;
- `user_correction`: candidate references an exact correction record (`ts` plus
  correction text match);
- `user_preference`: same explicit correction provenance requirement.

Always reject `volatile_fact` and unproven `model_judgment`. Reject any missing
or ambiguous provenance. The gate may approve a lesson from a `miss` because a
failed forecast is durable information about what not to repeat; it must record
the verdict in provenance.

- [x] **Step 4: Run GREEN, Ruff, and commit**

### Task 2: Expose the gate at the durable-write seam without breaking legacy reads

**Files:**
- Modify: `intelligence/services/judgments.py`
- Modify: `intelligence/services/corrections.py`
- Modify: `intelligence/services/user_memory.py`
- Modify: `intelligence/tests/test_judgments.py`
- Modify: `intelligence/tests/test_corrections.py`
- Modify: `intelligence/tests/test_user_memory.py`

- [x] **Step 1: Write RED validated-write tests**

Add explicit `record_validated_judgment(...)` and
`record_validated_preference(...)` adapters that require an already approved
`PromotionDecision`; a raw `record_judgment(...)` call remains legacy-compatible
and is marked `promotion_status="legacy_unverified"` only when callers opt in
to the new metadata.

- [x] **Step 2: Run RED**

- [x] **Step 3: Implement write adapters**

The adapters reject an ineligible decision, persist only the candidate content
plus sanitized provenance (`checkpoint_id/verdict` or `correction_ts`), and
never persist provider prompts, SQL, evidence body, or current volatile values.

- [x] **Step 4: Run GREEN and commit**

### Task 3: Verify the memory milestone

**Files:**
- Create: `docs/verification/memory-gate-2026-07-27.md`
- Modify: `docs/superpowers/plans/2026-07-27-memory-gate.md`

- [x] **Step 1: Run gate, ledger, user-memory, and permanent invariant suites**

- [x] **Step 2: Record that old legacy records remain readable but cannot claim new validated provenance**

- [x] **Step 3: Commit the verification receipt separately**

No live nine-case run, no MemoryGate prompt injection, no 8792 switch, no
`main` merge, and no review-harness expansion.

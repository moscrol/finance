# Acceptance Observation Sidecars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load hash-bound semantic truth and blind experience sidecars without modifying frozen
acceptance evidence.

**Architecture:** A pure loader validates artifact provenance and returns per-case projections;
the verdict module consumes a projection, and the existing board adds explicit opt-in paths.

**Tech Stack:** Python dataclasses, JSON/SHA-256, argparse, pytest.

---

### Task 1: Define and verify artifact integrity

**Files:**
- Create: `intelligence/eval/acceptance_observations.py`
- Create: `intelligence/tests/test_acceptance_observations.py`

- [ ] Write a failing test for a valid self-hashed truth artifact.
- [ ] Implement canonical self-excluding artifact hashing and immutable result types.
- [ ] Add RED/GREEN tests for source-run, case, overlay, and self-hash mutation.
- [ ] Reject unknown artifact kind, missing evaluator/rubric provenance, and unknown case IDs.

### Task 2: Validate axis payloads

**Files:**
- Modify: `intelligence/eval/acceptance_observations.py`
- Modify: `intelligence/tests/test_acceptance_observations.py`

- [ ] RED/GREEN truth rule IDs, states, reasons, and evidence references.
- [ ] RED/GREEN experience eligibility and `workbench/reference/tie` labels.
- [ ] Prove truth payloads cannot carry experience labels and vice versa.

### Task 3: Feed validated observations into verdicts

**Files:**
- Modify: `intelligence/eval/acceptance_verdict.py`
- Modify: `intelligence/tests/test_acceptance_verdict.py`

- [ ] Add an explicit `observations` argument to `evaluate_case`.
- [ ] Prove a semantic observation resolves `pass_rule` from unjudgeable to pass.
- [ ] Prove an external pass cannot erase another deterministic failed rule.
- [ ] Prove an experience label never changes truth.

### Task 4: Wire explicit board paths

**Files:**
- Modify: `intelligence/eval/acceptance.py`
- Modify: `intelligence/tests/test_acceptance_board.py`

- [ ] Add `--truth-observations` and `--experience-labels` only to `board`.
- [ ] Validate both against the exact selected run before rendering.
- [ ] Keep current output byte-semantics unchanged when neither path is supplied.
- [ ] Fail before the table on any provenance mismatch.

### Task 5: Verify and hand off

**Files:**
- Create: `docs/verification/acceptance-observation-sidecars-2026-07-29.md`
- Create: `docs/handoffs/2026-07-29-acceptance-observation-sidecars-completion.md`

- [ ] Run focused acceptance tests, Ruff, JSON/hash probes, and relevant full regression.
- [ ] Verify canonical cases, runs, and reference snapshots are unchanged.
- [ ] Record that no semantic/blind label was invented and continue the active final goal.

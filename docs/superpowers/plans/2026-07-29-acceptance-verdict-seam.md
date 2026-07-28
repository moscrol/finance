# Acceptance Verdict Seam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile the frozen 28-case acceptance contracts into deterministic, fail-closed,
three-axis verdicts and expose them on the existing board without running live questions.

**Architecture:** A pure `acceptance_verdict` module owns typed contracts, observations, and
aggregation. `acceptance.py` remains the JSON/CLI adapter. An additive verdict overlay records
which prose rules are structurally covered and which require a later semantic observation.

**Tech Stack:** Python dataclasses/enums, JSON, pytest, existing `agent_eval` types.

---

### Task 1: Lock the four-state verdict interface

**Files:**
- Create: `intelligence/eval/acceptance_verdict.py`
- Test: `intelligence/tests/test_acceptance_verdict.py`

- [ ] **Step 1: Write failing public-interface tests**

Import the public verdict types, `compile_case_contract`, and `evaluate_case`. Assert that a
missing run produces `not_run` on operational and truth axes while experience remains
`unjudgeable`.

- [ ] **Step 2: Run the single test and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_acceptance_verdict.py::test_missing_run_is_not_run_on_operational_and_truth_axes -q
```

Expected: import failure because `acceptance_verdict.py` does not exist.

- [ ] **Step 3: Implement immutable types and no-run evaluation**

Use frozen dataclasses and string enums. `CaseVerdict.to_dict()` serializes all three axes
without deriving experience from truth.

- [ ] **Step 4: Run the test and verify GREEN**

Expected: `1 passed`.

### Task 2: Compile contracts without losing fields

**Files:**
- Modify: `intelligence/eval/acceptance_verdict.py`
- Create: `intelligence/eval/cases/acceptance_verdict_contracts.json`
- Modify: `intelligence/tests/test_acceptance_verdict.py`

- [ ] **Step 1: Add RED tests for all 28 cases**

Assert overlay IDs equal canonical case IDs, all cases compile, and unknown verdict-bearing
fields appear in contract diagnostics instead of being silently discarded.

- [ ] **Step 2: Run those tests and verify RED**

Expected: overlay/compiler missing.

- [ ] **Step 3: Implement generic compiled rule types**

Compile facts, refusal, forbidden phrases, cutoff, citation integrity, answer sets,
inconsistency disclosure, falsifiability, multi-turn consistency, inherited golden cases, and
the prose rule. Preserve informational fields without treating them as verdict inputs.

- [ ] **Step 4: Add the 28-entry additive overlay**

Every case declares either `structured` coverage with only generic text requirements, or
`semantic_required` with a reason. Do not encode an expected full answer.

- [ ] **Step 5: Run compiler tests and verify GREEN**

Expected: all 28 compile; canonical cases and snapshots remain byte-identical.

### Task 3: Evaluate operational state independently

**Files:**
- Modify: `intelligence/eval/acceptance_verdict.py`
- Modify: `intelligence/tests/test_acceptance_verdict.py`

- [ ] **Step 1: Add one RED matrix test**

Cover no run, blocked reason, timeout/error, completed with degradation, and clean completed.
Assert truth is not automatically failed by an operational error and not automatically passed
by `completed`.

- [ ] **Step 2: Run the matrix and verify RED**

- [ ] **Step 3: Implement operational classification**

Return `not_run`, `blocked`, `failed`, `degraded`, or `completed`, preserving original errors.

- [ ] **Step 4: Run the matrix and verify GREEN**

### Task 4: Implement deterministic truth rules vertically

**Files:**
- Modify: `intelligence/eval/acceptance_verdict.py`
- Modify: `intelligence/tests/test_acceptance_verdict.py`

- [ ] **Step 1: RED/GREEN refusal and forbidden phrases**

Test explicit no-data, vague evidence-gap, and forbidden fabricated text. Implement generic
unavailability matching plus exact forbidden phrase checks.

- [ ] **Step 2: RED/GREEN fact tolerances**

Test absolute/percentage tolerance boundaries, string facts, and missing observations. Numeric
extraction normalizes commas and percent signs. Malformed input is unjudgeable.

- [ ] **Step 3: RED/GREEN cutoff safety**

Test a structured citation after cutoff as fail and all citations on/before cutoff as pass.
Without citations, ambiguous prose remains unjudgeable.

- [ ] **Step 4: RED/GREEN citation integrity**

Extract `[S#]/[G#]/[R#]/[W#]/[E#]` from answers and evidence labels. Any cited-but-unminted tag
fails. No cited tags only passes this rule, never unrelated prose rules.

- [ ] **Step 5: RED/GREEN conservative semantic rules**

Implement generic required phrases, inconsistency language, falsifiability as a condition plus
numeric threshold, and multi-turn context-loss detection. Exact-set exclusion and inherited
golden rules remain unjudgeable without their typed observations.

- [ ] **Step 6: Run the focused test file**

Expected: all verdict tests pass.

### Task 5: Calibrate against frozen historical runs

**Files:**
- Modify: `intelligence/tests/test_acceptance_verdict.py`
- Modify: `intelligence/eval/cases/acceptance_verdict_contracts.json` only if a coverage claim is
  proven unsound; never tune expected facts or answers.

- [ ] **Step 1: Add historical RED fixtures from committed JSON**

Assert rule-level results for C1, C7, C9, and C10 from `20260727T032229Z.json`. C9 overall
remains unjudgeable even if citation integrity passes.

- [ ] **Step 2: Run and inspect exact disagreements**

Fix only generic evaluator defects or downgrade coverage. Do not add a question-specific
parser.

- [ ] **Step 3: Reach GREEN and freeze calibration expectations**

Expected: stable results on both committed historical run files.

### Task 6: Expose the three axes on the existing board

**Files:**
- Modify: `intelligence/eval/acceptance.py`
- Modify: `intelligence/tests/test_acceptance_board.py`

- [ ] **Step 1: Add a RED board-output test**

Patch `latest_run()` and assert separate `运行`, `真值`, and `体验` columns plus separate
pass/fail/unjudgeable/not-run counts. Answered turns must not be labeled as passes.

- [ ] **Step 2: Run the test and verify RED**

- [ ] **Step 3: Wire the pure module into `cmd_board`**

Load the overlay once, compile each case, evaluate its run, and render the three axes.
Experience remains `未标注` until an external blind label exists.

- [ ] **Step 4: Run board tests and read-only CLI smoke**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_acceptance_board.py intelligence/tests/test_acceptance_verdict.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m intelligence.eval.acceptance board
```

Expected: tests pass; board has separate denominators and no aggregate release claim.

### Task 7: Regression, documentation, and handoff

**Files:**
- Create: `docs/verification/acceptance-verdict-seam-2026-07-29.md`
- Create: `docs/handoffs/2026-07-29-acceptance-verdict-seam-completion.md`
- Modify: `docs/superpowers/plans/2026-07-29-acceptance-verdict-seam.md`

- [ ] **Step 1: Run focused and relevant regression**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_acceptance_verdict.py \
  intelligence/tests/test_acceptance_board.py \
  intelligence/tests/test_agent_eval.py -q
```

Then run full `intelligence/tests` with documented environment overrides removed. Record the
interpreter and counts; do not weaken tests.

- [ ] **Step 2: Run hygiene checks**

```bash
git diff --check
git status --short
```

Reject secrets, databases, indexes, logs, caches, and virtualenvs.

- [ ] **Step 3: Write verification and handoff**

Record commits, calibration output, verdict coverage, remaining semantic/experience gaps, and
the next final-goal action. State explicitly that this milestone is not final completion.

- [ ] **Step 4: Commit the completed slice**

Commit docs separately from implementation where practical. Do not merge `main`, switch 8792,
or merge KB `9053b0c4`.

# Grounded Synthesis Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: execute this plan task-by-task in the current session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure the frozen grounded chain, enforce deterministic synthesis health, implement the evidence-selected architecture repair, and audit the repaired behavior across harnesses.

**Architecture:** A clean release branch owns four staged changes: frozen-input replay, structured health gate, measured product repair, and normalized cross-harness audit. Production prompt builders and validators remain the single source of truth; no replay-only prompt or semantic shortcut is introduced.

**Tech Stack:** Python 3.12, argparse, dataclasses, pytest, existing Workbench LLM provider adapters, JSON/JSONL trace artifacts.

**Interpreter:** The virtual environment is an untracked directory in the source
worktree, so isolated worktrees reuse
`/Users/a77/finance-workspace-private/.venv-workbench/bin/python` while keeping
their own directory as cwd. This loads release-branch code with the verified
dependency environment.

---

### Task 1: Frozen artifact deserialization and replay contract

**Files:**
- Create: `intelligence/eval/grounded_replay.py`
- Create: `intelligence/tests/test_grounded_replay.py`

- [ ] **Step 1: Write failing round-trip loader tests**

Construct an `AnswerSpec`, serialize it with `to_dict()`, load it through
`_answer_spec_from_payload()`, and assert the second `to_dict()` is identical.
Cover `ClaimStatus`, `CompanyTier`, `EvidenceRef`, `QualityIssue`,
`StageArtifact.from_dict()`, and `EvidenceAtom.from_dict()`.

- [ ] **Step 2: Run the loader test and observe the missing module failure**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_grounded_replay.py -q
```

Expected: collection fails because `intelligence.eval.grounded_replay` does not
exist.

- [ ] **Step 3: Implement strict frozen-input loaders**

Add helpers that reject non-object JSON, missing required fields, invalid enum
values, malformed nested records, and empty questions. Reconstruct
`DecisionBrief` directly from its eight fields and verify the serialized form is
stable.

- [ ] **Step 4: Add failing composer replay tests**

Monkeypatch `llm_refine.synthesize_messages` with a fake `SynthesisResult`. Assert
that composer replay uses:

```python
llm_refine.build_grounded_composer_messages(
    question,
    decision_brief.to_prompt_block(),
    answer_model.grounded_claim_registry_block(
        answer_spec,
        query=question,
        max_chars=12_000,
    ),
    required_outputs=answer_spec.prompt_constraints,
)
```

Assert `max_tokens=2400`, `max_chars=16000`, explicit deadline/grant, input
hashes, `completion_tokens is None`, and output persistence only to `--out`.

- [ ] **Step 5: Implement composer replay and artifact serialization**

Use a `ReplayArtifact` dataclass with stable JSON output. Classify deadline
exhaustion as `timeout`, provider/config errors as `failed`, and successful
natural completion as `completed`. Include the preregistered composer prediction
and the observed range verdict.

- [ ] **Step 6: Add failing judge replay tests**

Cover successful composer input, missing/failed composer artifact, deterministic
repair failure, provider override, judge JSON parsing, and sentence-count
validation.

- [ ] **Step 7: Implement judge replay**

Canonicalize/rebind composer claim IDs, run deterministic validation and repair,
build messages with `build_grounding_judge_messages`, and parse with
`parse_grounding_judge_report`. Never send an invalid candidate to the provider.

- [ ] **Step 8: Run focused tests**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_grounded_replay.py -q
```

Expected: all replay tests pass.

- [ ] **Step 9: Commit replay code and tests**

Stage only the new replay module and tests, scan staged paths for forbidden file
types and secret-like values, then commit:

```bash
git commit -m "feat(eval): add frozen grounded replay"
```

### Task 2: Run the T1 measurement

**Files:**
- Create: `intelligence/eval/measurements/2026-08-03-grounded-composer-replay.json`
- Create when composer completes: `intelligence/eval/measurements/2026-08-03-grounding-judge-replay.json`
- Modify: `docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`

- [ ] **Step 1: Run composer once with a 115-second grant**

Run from the release worktree with explicit Keychain user and output path. Do not
run the brief phase and do not retry with a larger grant.

- [ ] **Step 2: While composer is active, execute Task 3 in a separate shell**

This uses the network wait productively without changing the measurement process.

- [ ] **Step 3: If composer completed, run judge once with a 115-second grant**

Use the composer measurement artifact as the only candidate input. If composer
timed out or failed validation, record judge as `blocked_by_composer` without a
provider call.

- [ ] **Step 4: Verify measurement integrity**

Recompute input hashes, assert output JSON parses, assert no credential-shaped
keys or values are present, and compare observed composer time to the 110–180s
prediction.

- [ ] **Step 5: Update M2 residual uncertainty**

Record the natural completion value or `>115s` lower bound, the judge sample or
its explicit blocker, revision, input hashes, and the no-retry rule. Preserve the
settled PRIMARY/H5 conclusion.

- [ ] **Step 6: Commit measurement artifacts and M2 update**

```bash
git commit -m "docs(eval): record grounded replay measurements"
```

### Task 3: Add the fail-closed synthesis-health gate

**Files:**
- Modify: `intelligence/eval/synthesis_health.py`
- Modify: `intelligence/tests/test_synthesis_health.py`

- [ ] **Step 1: Freeze legacy CLI output in a test**

Create a temporary one-turn artifact and assert `main([path])` prints the exact
current report and returns `0`.

- [ ] **Step 2: Write failing gate tests**

Add cases for full-pass success, threshold failure, unknown blocking, unreadable
input, a run with zero completed turns, mixed good+missing inputs, and invalid
ratios (`nan`, infinity, below zero, above one).

- [ ] **Step 3: Run tests and confirm the new cases fail**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_synthesis_health.py -q
```

- [ ] **Step 4: Implement structured analysis and gate evaluation**

Introduce immutable per-run and aggregate analysis records. Keep `render(paths)`
as a compatibility wrapper. Add `--gate`, `--min-full-pass`, and
`--fail-on-unknown`; reject gate-only flags without `--gate`. Default the gate
threshold to `1.0`.

- [ ] **Step 5: Run unit tests and frozen local acceptance receipts**

Run focused pytest, then point the CLI at the pre/post A4 artifacts in the source
worktree and assert both return `1` under `--gate --min-full-pass 1.0`.

- [ ] **Step 6: Commit the gate**

```bash
git commit -m "feat(eval): enforce synthesis health gate"
```

### Task 4: Select and implement the T3 architecture

**Files:**
- Modify: `intelligence/services/answer_model.py`
- Modify: `intelligence/services/ask_synthesis.py`
- Modify: `intelligence/tests/test_answer_model.py`
- Modify when budget behavior changes: `intelligence/tests/test_synthesis_phase_observability.py`
- Modify: `docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`

- [ ] **Step 1: Inspect the frozen A4 registry**

Resolve the pre/post artifact run IDs and count `company:`, `chain:`, and
`exposure:` claim IDs without reading unrelated knowledge-base files. Record the
count in the architecture note.

- [ ] **Step 2: Write deterministic DecisionBrief tests**

Assert `direct_answer` comes from the leading summary/verified claim, support and
counter/gap IDs remain valid registry IDs, `core_tension` uses an explicit
deterministic template, and every company-family claim appears in
`chain_mapping`.

- [ ] **Step 3: Implement `build_deterministic_decision_brief()`**

Keep the function pure and bounded. It must return a valid eight-field
`DecisionBrief` or `None` when no support claim exists. It must not invent facts,
companies, dates, or numbers.

- [ ] **Step 4: Replace the brief provider call in the grounded path**

Record the brief phase as deterministic with near-zero elapsed time, then feed
the result to the unchanged composer prompt. Preserve fail-closed behavior when
no valid deterministic brief can be built.

- [ ] **Step 5: Apply the measured budget branch**

Use the decision table in the design document. If the measured two-phase path
does not fit 120 seconds with 20% slack, add an explicit deep-mode timeout rather
than silently changing standard mode. Freeze the selected value in code and test
that every child deadline remains bounded by its root.

- [ ] **Step 6: Run focused and regression tests**

Run grounded composer, synthesis phase observability, replay, and health-gate
tests. Then run the repository's relevant broader intelligence test group.

- [ ] **Step 7: Commit the architecture repair**

```bash
git commit -m "fix(ask): unblock grounded synthesis chain"
```

### Task 5: Validate one post-fix A4 canary

**Files:**
- Create: `intelligence/eval/measurements/2026-08-03-a4-post-release-fix.json`
- Modify: `docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`

- [ ] **Step 1: Pre-register revision, mode, budget, and success criteria**

Success requires deterministic brief, composer completion, judge presence, no
template fallback, and compliance with the declared mode budget. Top-level
`completed` alone is insufficient.

- [ ] **Step 2: Run A4 exactly once**

Do not run A1–A10. Capture phase telemetry and synthesis-health classification.

- [ ] **Step 3: Evaluate with the new gate**

Run `synthesis_health --gate --min-full-pass 1.0 --fail-on-unknown` against the
canary artifact and record its exit code.

- [ ] **Step 4: Commit the canary receipt and report update**

```bash
git commit -m "docs(eval): verify grounded synthesis release"
```

### Task 6: Normalize and run the cross-harness audit

**Files:**
- Modify: `docs/trace-profile.md`
- Create: `intelligence/eval/normalize_harness_trace.py`
- Create: `intelligence/tests/test_normalize_harness_trace.py`
- Create: `docs/verification/2026-08-03-cross-harness-shared-layer-audit.md`
- Create: `intelligence/eval/measurements/2026-08-03-cross-harness/`

- [ ] **Step 1: Define the seven-step mapping and provenance flag**

Document exact Codex rollout and self-built span/event mappings. Unknown events
remain `unmapped`; they are never guessed into a semantic step.

- [ ] **Step 2: Test and implement deterministic normalization**

Use minimal JSONL fixtures for both harness types. Emit normalized rows with
`step`, `native_or_normalized`, source event identity, timestamp, and redacted
summary.

- [ ] **Step 3: Pre-register five or six comparison tasks**

Select tasks with existing evidence that Codex performs well and the self-built
path previously degraded. Freeze task text, date/cutoff, model identity, and
success contract before running either side.

- [ ] **Step 4: Run each task once per harness**

Store raw trace references and normalized output. Do not tune prompts between
paired runs.

- [ ] **Step 5: Compute first divergence**

For every pair, record `pre_divergence_equivalence`,
`first_divergence_step`, evidence, primary/secondary findings, and whether the
result bears on SDK choice.

- [ ] **Step 6: Commit normalizer, tests, receipts, and report**

```bash
git commit -m "docs(eval): audit shared layer across harnesses"
```

### Task 7: Final verification and handoff

**Files:**
- Modify: `.agent-memory/20_projects/finance-workspace-private.md`
- Modify if a cross-project principle is stable: `.agent-memory/10_knowledge/<focused-note>.md`

- [ ] **Step 1: Run focused and broad verification**

Run all changed-module tests, formatting/lint checks used by the repository, and
the broad intelligence test suite. Separate known host baseline failures from new
failures with before/after evidence.

- [ ] **Step 2: Inspect staged risk files**

Reject `.env*`, credentials, PDFs, archives, databases, SQLite/DuckDB files,
PowerPoint files, caches, virtual environments, and macOS metadata. Search staged
content for secret-like keys and tokens.

- [ ] **Step 3: Write back durable decisions**

Add one project-level handoff entry covering the replay measurement, gate
contract, chosen architecture, canary result, and cross-harness conclusion. Add a
knowledge note only if the method generalizes beyond this project.

- [ ] **Step 4: Commit and push the release branch**

Push `fix/grounded-synthesis-release` without merging `main` or touching the
launchd runtime pointer.

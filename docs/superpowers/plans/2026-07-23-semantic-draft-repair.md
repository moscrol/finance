# Semantic Draft-Only Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace over-broad semantic `FINAL_JSON` regeneration with one compact draft-only repair that cannot alter evidence or bindings.

**Architecture:** `EpisodeFinalizer` exposes one no-tools `repair_draft()` model call whose input is the frozen draft plus judge feedback and whose output is exactly `{"draft":"..."}`. `SemanticEpisodeVerifier` copies the original outcome's evidence, bindings, gaps, and status into the repaired outcome, reruns structural verification, then performs the single allowed rejudge.

**Tech Stack:** Python dataclasses, existing `AgentModelClient`, strict JSON parsing, pytest, Ruff.

---

### Task 1: Freeze truth-plane state during semantic repair

**Files:**
- Modify: `intelligence/services/episode_finalizer.py`
- Modify: `intelligence/services/episode_semantic_verifier.py`
- Test: `intelligence/tests/test_episode_finalizer.py`
- Test: `intelligence/tests/test_episode_semantic_verifier.py`

- [ ] **Step 1: Write failing finalizer contract tests**

Add a recording model test that calls:

```python
EpisodeFinalizer(model).repair_draft(
    task_frame=frame,
    context=context,
    draft="市场下跌。政策变化导致了下跌。",
    rejected_sentences=("政策变化导致了下跌。",),
    judge_issues=("因果证据不足",),
)
```

Assert the request exposes no tools, contains `draft`, rejected sentences,
judge issues, and required-output descriptions, and contains neither evidence
records nor bindings. Assert the returned `ModelTurn` is not blessed or parsed
inside the finalizer.

- [ ] **Step 2: Run the finalizer test and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_finalizer.py -k repair_draft
```

Expected: fail because `EpisodeFinalizer.repair_draft` does not exist.

- [ ] **Step 3: Write failing semantic repair tests**

At the public `SemanticEpisodeVerifier.verify()` seam, inject a rejecting first
judge, a finalizer whose `repair_draft()` returns a revised JSON draft, and a
passing second judge. Assert:

```python
assert result.status == "completed"
assert result.judge_status == "repaired"
assert result.verified.outcome.evidence == original.evidence
assert result.verified.outcome.bindings == original.bindings
assert result.verified.outcome.gaps == original.gaps
assert result.verified.outcome.status == original.status
assert len(judge.calls) == 2
```

Add malformed, surrounding-prose, tool-call, provider-error, and empty-draft
cases; each must remain `partial` and must not expose the raw rejected draft.

- [ ] **Step 4: Run the semantic tests and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_semantic_verifier.py -k draft_repair
```

Expected: fail because the verifier still expects regenerated `FINAL_JSON`.

- [ ] **Step 5: Implement the compact no-tools repair call**

In `EpisodeFinalizer`, replace the semantic full-envelope repair with:

```python
def repair_draft(
    self,
    *,
    task_frame: TaskFrame,
    context: ResearchRunContext,
    draft: str,
    rejected_sentences: tuple[str, ...],
    judge_issues: tuple[str, ...],
) -> ModelTurn:
    ...
```

The system prompt must forbid new facts, numbers, evidence, hashes, and
bindings; it may only delete, narrow, or qualify rejected language. The user
payload contains `task_frame`, required-output descriptions, `draft`,
`rejected_sentences`, and `judge_issues`. Invoke the existing model once with
`tools=[]` and the remaining root deadline.

- [ ] **Step 6: Parse and re-verify without changing truth state**

In `SemanticEpisodeVerifier`, accept one bare JSON object or exactly one JSON
code fence with the exact schema `{"draft": <non-empty string>}`. Rebuild:

```python
AgentOutcome(
    task_frame_hash=original.task_frame_hash,
    status=original.status,
    draft=revised_draft,
    evidence=original.evidence,
    traces=original.traces,
    gaps=original.gaps,
    stop_reason="semantic_repair",
    events=original.events,
    bindings=original.bindings,
    usage=original.usage,
)
```

Run `verify_episode_outcome()` and then exactly one rejudge. Never publish the
revised draft unless both structural and semantic checks permit it.

- [ ] **Step 7: Run focused regression and static checks**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_finalizer.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_api.py
uvx ruff check intelligence/services/episode_finalizer.py \
  intelligence/services/episode_semantic_verifier.py \
  intelligence/tests/test_episode_finalizer.py \
  intelligence/tests/test_episode_semantic_verifier.py
git diff --check
```

Expected: all tests pass; Ruff and diff check are clean.

- [ ] **Step 8: Commit the implementation**

```bash
git add intelligence/services/episode_finalizer.py \
  intelligence/services/episode_semantic_verifier.py \
  intelligence/tests/test_episode_finalizer.py \
  intelligence/tests/test_episode_semantic_verifier.py
git commit -m "fix: narrow semantic repair to draft wording"
```

### Task 2: Re-run the real GLM acceptance loop

**Files:**
- Modify: `docs/verification/continuous-agent-production-candidate-2026-07-23.md`

- [ ] **Step 1: Rebuild a clean detached canary**

Create a detached worktree from the implementation commit, set
`ASK_CONTINUOUS_RUNTIME=canary`, inject the GLM key only from Keychain, and
leave canonical 8792 untouched.

- [ ] **Step 2: Re-run the original red case**

Run `昨天的反弹能持续多久` through the Conversation API and strict SSE client.
Require a non-empty task-relevant answer, two valid snapshots, no secret/public
leaks, zero duplicate queries, and semantic status `passed` or `repaired`.

- [ ] **Step 3: Continue the fixed five-case and pressure acceptance**

Run all five fixed questions individually and then in one process. Record every
answer and failure without rerun-selecting only successes.

### Task 3: Calibrate fact grounding versus requested analytical judgment

The first clean `a3cece8d` canary completed structurally with six provider
attempts, six tool calls, zero duplicate queries, and a successful compact
repair, but the rejudge still rejected it. The artifact exposed two independent
causes:

1. current structured market atoms inherited no block-level `source_date` when
   an individual rendered line contained no literal date;
2. the semantic judge required a requested forecast conclusion to already
   exist verbatim in evidence, making duration/upside/valuation questions
   impossible to answer even when their premises were grounded.

- [ ] **Step 1: Write RED tests for structured as-of propagation**

Add an optional block-level source date to `block_lines_to_evidence()` and test
that the market/mainline wrappers pass the current context date to every atom.
Embedded historical dates remain content, not the source snapshot identity.

- [ ] **Step 2: Write RED tests for a typed semantic-claim policy**

Through the public verifier seam, assert the judge request distinguishes:

- observed facts and factual numbers, which require direct evidence;
- explicitly labelled analytical judgments, which may be derived from bound
  premises;
- user-requested duration/upside/valuation ranges, which may be presented as
  conditional estimates rather than source facts;
- external causes, historical probabilities, and precise trigger thresholds,
  which still require direct support.

- [ ] **Step 3: Tighten repair obligations**

The compact repair must delete every issue-named unsupported fact/threshold
rather than rephrasing it as “the evidence says”. For an explicitly requested
forecast it may retain one clearly labelled base-case estimate, but its reasons
must come only from unrejected premises and it must preserve uncertainty.

- [ ] **Step 4: Re-run focused regression and the preserved canary**

First replay the preserved artifact against the revised judge contract to test
the hypothesis cheaply. Then rebuild a clean detached runtime and rerun the
original question exactly once before continuing the remaining four cases.

# Agent Runtime Reliability and Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the isolated Continuous/SDK/headless runtime comparison reliable for factual, counterfactual, and methodology questions without weakening evidence gates.

**Architecture:** Keep `AgentRuntime.run()` as the only execution seam. Add grounding mode to the existing research contract, enforce a shared SDK budget ledger around the existing `ResearchDeadline`, and expose private stop reasons in benchmark artifacts. Public Run/SSE/UI projections remain unchanged.

**Tech Stack:** Python 3.12, dataclasses, OpenAI Agents SDK, pytest, existing frozen finance benchmark and FastAPI Run/SSE protocol.

---

### Task 1: Make benchmark failures diagnosable

**Files:**
- Modify: `intelligence/eval/runtime_backend_benchmark.py`
- Modify: `scripts/run_agent_runtime_benchmark.py`
- Test: `intelligence/tests/test_runtime_backend_benchmark.py`
- Test: `intelligence/tests/test_run_agent_runtime_benchmark.py`

- [ ] **Step 1: Write the failing test**

Add assertions that a runtime arm serializes `stop_reason` and
`effective_timeout_seconds`, and that an SDK timeout is not represented only by
`runtime_invalid_actions`.

- [ ] **Step 2: Run the focused tests and confirm red**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_runtime_backend_benchmark.py intelligence/tests/test_run_agent_runtime_benchmark.py
```

Expected: the new fields are absent from the result and the assertion fails.

- [ ] **Step 3: Implement the minimal result fields**

Add optional `stop_reason` and `effective_timeout_seconds` fields to
`RuntimeArmResult`. Populate them from `AgentOutcome.stop_reason` and the
measured runtime context. Preserve backward-compatible deserialization for old
artifacts.

- [ ] **Step 4: Run the focused tests and confirm green**

Run the same command. Expected: all focused benchmark tests pass.

- [ ] **Step 5: Commit**

```bash
git add intelligence/eval/runtime_backend_benchmark.py scripts/run_agent_runtime_benchmark.py intelligence/tests/test_runtime_backend_benchmark.py intelligence/tests/test_run_agent_runtime_benchmark.py
git commit -m "test: expose runtime benchmark stop reasons"
```

### Task 2: Enforce SDK tool/finalization/verifier budget separation

**Files:**
- Modify: `intelligence/services/openai_agents_runtime.py`
- Modify: `intelligence/services/research_contract.py` only if a named verifier reserve is needed
- Test: `intelligence/tests/test_openai_agents_runtime.py`

- [ ] **Step 1: Write the failing budget tests**

Add fake SDK runner tests that assert the request timeout is less than the root
deadline by the verifier reserve, and that a tool request after the research
stage closes returns `research_stage_closed` without adding a public evidence
gap.

- [ ] **Step 2: Run focused tests and confirm red**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_openai_agents_runtime.py -k 'budget or stage or deadline'
```

Expected: current code passes the full remaining deadline and records the
rejected stage call as a normal failure, so the new assertions fail.

- [ ] **Step 3: Implement the minimal budget ledger**

Use `ResearchDeadline.stage_timeout()` for tool reservation and derive an
explicit verifier reserve from the existing semantic judge timeout. Pass only
the remaining runtime-finalization window to `Runner.run`. In `_AgentsRunState`,
return a natural-language stage-closed observation after the tool window and do
not append it to `gaps`; continue enforcing max steps, duplicate queries, and
cancellation exactly as before.

- [ ] **Step 4: Run focused tests and confirm green**

Run the focused command, then the full SDK adapter tests. Expected: all pass;
the fake runner still receives a terminal turn and the public outcome remains
complete when all slots are fulfilled.

- [ ] **Step 5: Commit**

```bash
git add intelligence/services/openai_agents_runtime.py intelligence/tests/test_openai_agents_runtime.py
git commit -m "fix: reserve verifier budget in sdk runtime"
```

### Task 3: Add explicit grounding modes to the research contract

**Files:**
- Modify: `intelligence/services/research_contract.py`
- Modify: `intelligence/services/agent_runtime.py`
- Modify: `intelligence/services/episode_protocol.py`
- Modify: `intelligence/services/episode_factory.py`
- Modify: `intelligence/services/episode_verifier.py`
- Modify: `intelligence/services/episode_semantic_verifier.py`
- Test: `intelligence/tests/test_episode_protocol.py`
- Test: `intelligence/tests/test_episode_verifier.py`
- Test: `intelligence/tests/test_episode_semantic_verifier.py`

- [ ] **Step 1: Write the failing contract tests**

Add one `model_reasoning` contract whose completed binding has no evidence
hashes and one `user_premise` contract with a conditional draft. Assert both
are structurally complete, while an `evidence` output without a hash remains a
gap. Assert serialized prompt input includes the mode and finish JSON includes
`basis`.

- [ ] **Step 2: Run focused tests and confirm red**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_protocol.py intelligence/tests/test_episode_verifier.py -k 'grounding or premise or reasoning'
```

Expected: `OutputEvidenceBinding` rejects empty non-evidence bindings and the
verifier marks them missing.

- [ ] **Step 3: Implement the minimal mode-aware value objects**

Add `GroundingMode`, `RequiredOutput.grounding_mode`, and
`OutputEvidenceBinding.basis` with backward-compatible defaults. Validate basis
against the required output in the shared finish parser and structural
verifier. Keep evidence hash validation active whenever hashes are present.

- [ ] **Step 4: Project task semantics into modes**

In `episode_factory.py`, map existing `TaskFrame` decision-method patterns to
`model_reasoning` and counterfactual patterns to `user_premise`; leave market,
company, date, and causal evidence outputs as `evidence`. Do not create a new
route row. Add mode details to the semantic judge request and update its prompt
to reject current facts in non-evidence slots.

- [ ] **Step 5: Run focused tests and confirm green**

Run the two focused test files, then all episode verifier tests.

- [ ] **Step 6: Commit**

```bash
git add intelligence/services/research_contract.py intelligence/services/agent_runtime.py intelligence/services/episode_protocol.py intelligence/services/episode_factory.py intelligence/services/episode_verifier.py intelligence/services/episode_semantic_verifier.py intelligence/tests/test_episode_protocol.py intelligence/tests/test_episode_verifier.py intelligence/tests/test_episode_semantic_verifier.py
git commit -m "feat: distinguish evidence and reasoning grounding"
```

### Task 4: Preserve semantic repair language consistency

**Files:**
- Modify: `intelligence/services/episode_semantic_verifier.py`
- Test: `intelligence/tests/test_episode_semantic_verifier.py`

- [ ] **Step 1: Write the failing test**

Give deletion-only repair a draft containing “依据有三点” followed by three
ordered items, reject the middle item, and assert the public answer says two
items or removes the stale count rather than saying three.

- [ ] **Step 2: Run focused test and confirm red**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_semantic_verifier.py -k 'count or enumeration or repair'
```

- [ ] **Step 3: Implement deterministic count cleanup**

After deletion and list renumbering, reconcile only explicit count phrases whose
integer equals the original contiguous list count. Replace the count with the
surviving count or remove the phrase when no safe replacement exists. Do not
rewrite facts or infer new items.

- [ ] **Step 4: Run focused tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_semantic_verifier.py -k 'count or enumeration or repair'
git add intelligence/services/episode_semantic_verifier.py intelligence/tests/test_episode_semantic_verifier.py
git commit -m "fix: keep semantic repair counts consistent"
```

### Task 5: Full verification and isolated runtime acceptance

**Files:**
- Modify: `docs/verification/agent-runtime-backends-2026-07-25.md`
- Modify: `.agent-memory/20_projects/finance-workspace-private.md`
- Artifact: `/Users/a77/.finance-runtime/evals/agent-runtime-backends-2026-07-25-gpt-keychain.json`

- [ ] **Step 1: Run focused and full backend tests**

Run the focused tests from Tasks 1-4, then the full backend suite with
`FORESIGHT_USERS_DIR`, `SUBCONSCIOUS_VAULT`, and `AGENT_MEMORY_VAULT` cleared.

- [ ] **Step 2: Run the same nine-case benchmark**

Use the saved Keychain account `linxiaoqi5111`, the finance root
`/Users/a77/finance-workspace-private`, and the existing knowledge wiki. Do not
count provider outage artifacts as model results.

- [ ] **Step 3: Verify the acceptance gates**

Require per-arm stop reasons, current data date `2026-07-24`, no duplicate
queries, no public control-plane leakage, method/counterfactual completion
without fake evidence, and preserved deterministic technical output.

- [ ] **Step 4: Run UI/Run/SSE smoke on the isolated candidate**

Confirm one terminal SSE run, correct report date, bound evidence inspector,
and no secrets in artifacts. Keep 8792 untouched.

- [ ] **Step 5: Update verification and project memory**

Record exact revision, test counts, benchmark summary, remaining GPT/headless
limits, and whether the candidate is suitable for daily use. Do not claim
Codex/Knevo parity unless the same frozen cases provide evidence.

- [ ] **Step 6: Commit documentation only after all gates pass**

```bash
git add docs/verification/agent-runtime-backends-2026-07-25.md .agent-memory/20_projects/finance-workspace-private.md
git commit -m "docs: record unified runtime reliability acceptance"
```

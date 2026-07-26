# Deep Sub-Research Branches Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an approved deep `ResearchPlan` run at most three explicit, read-only sub-research branches without allowing a branch to close the primary plan's gaps, publish an answer, mint budget, or fork another branch.

**Architecture:** `ResearchPlan.branch_goals` is the only model-owned branch request. `SubResearchCoordinator` validates and runs those goals through an injected branch worker while all calls consume the parent's root ledger through bounded child views. Each worker receives a `BranchEvidenceSink` exposing only `append()` and `snapshot()`; the primary episode imports evidence and traces, then alone decides the final answer.

**Tech Stack:** Python frozen dataclasses, existing `AgentModelClient`, `ContinuousAgentEpisode`, `ResearchToolRegistry`, `EvidenceLedger`, `RootBudgetLedger`, `ThreadPoolExecutor`, pytest, Ruff.

---

## Public seams under test

1. `EvidenceLedger.branch_sink(branch_id)` returns a narrow interface with no coverage/gap mutators and records branch ownership for every accepted evidence hash.
2. `parse_research_plan()` accepts zero to three explicit `branch_goals`; old plans without the optional field remain valid.
3. `SubResearchCoordinator.run()` executes only approved deep requests, caps concurrency at three, shares one parent budget, and returns evidence/traces without a publishable answer.
4. `ContinuousAgentEpisode.run()` emits ordered branch events, gives results back to the same primary message history, and remains the only final-answer owner.

### Task 1: Add the branch-facing EvidenceLedger facade

**Files:**
- Modify: `intelligence/services/evidence_ledger.py`
- Create: `intelligence/tests/test_branch_evidence_sink.py`

- [ ] **Step 1: Write RED interface tests**

```python
sink = EvidenceLedger(information_cutoff=date(2026, 7, 24)).branch_sink("branch-1")
assert sink.append(evidence) == ("hash-1",)
assert sink.snapshot().evidence_branch_owners == (("hash-1", "branch-1"),)
assert not hasattr(sink, "close_gap")
assert not hasattr(sink, "open_gap")
assert not hasattr(sink, "mark_output_covered")
```

Also prove blank branch IDs fail, future evidence is rejected, duplicates are idempotent, and `supports` metadata does not mark a primary output covered.

- [ ] **Step 2: Run RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_branch_evidence_sink.py -q
```

Expected: `EvidenceLedger` has no `branch_sink`.

- [ ] **Step 3: Implement the narrow interface**

```python
@dataclass(frozen=True)
class BranchEvidenceSink:
    _ledger: EvidenceLedger
    branch_id: str

    def append(self, evidence: AgentEvidence | Iterable[AgentEvidence]) -> tuple[str, ...]:
        return self._ledger._append_from_branch(self.branch_id, evidence)

    def snapshot(self) -> EvidenceLedgerSnapshot:
        return self._ledger.snapshot()
```

`EvidenceLedger._append_from_branch()` uses the existing cutoff/dedup logic,
records `(content_hash, branch_id)`, and never accepts `covered_outputs` or gap
arguments. `EvidenceLedgerSnapshot` gains `evidence_branch_owners`.

- [ ] **Step 4: Run GREEN, permanent invariants, Ruff, and commit**

### Task 2: Make branch goals explicit model-owned plan state

**Files:**
- Modify: `intelligence/services/research_plan.py`
- Modify: `intelligence/services/episode_protocol.py`
- Modify: `intelligence/tests/test_research_plan.py`

- [ ] **Step 1: Write RED compatibility and cap tests**

```python
assert parse_research_plan(old_plan_json).branch_goals == ()
assert parse_research_plan(plan_with_two_goals).branch_goals == (
    "核验公司兑现", "查找反方驱动",
)
with pytest.raises(ValueError):
    parse_research_plan(plan_with_four_goals)
```

Reject blank/duplicate/overlong goals. `plan_to_public_dict()` must expose the
bounded goals; plan revision may not replace an already published goal with a
different goal under the same revision.

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Add `branch_goals: tuple[str, ...] = ()` as an optional closed-plan field**

The prompt states that branch goals are proposals only, require approved deep
mode, cannot select permissions or budgets, and are capped at three.

- [ ] **Step 4: Run GREEN and commit**

### Task 3: Add one root-budgeted SubResearchCoordinator

**Files:**
- Create: `intelligence/services/sub_research.py`
- Create: `intelligence/tests/test_sub_research.py`
- Modify: `intelligence/services/research_contract.py`

- [ ] **Step 1: Write RED coordinator tests**

```python
result = coordinator.run(
    goals=("核验兑现", "查反方"),
    task_frame=frame,
    context=deep_context,
    registry=registry,
    evidence_sink_factory=ledger.branch_sink,
)
assert len(result.branches) == 2
assert parent_root.remaining_calls == initial_remaining - result.tool_calls
assert all(not hasattr(branch, "answer") for branch in result.branches)
```

Prove quick mode runs zero branches, four goals are refused, duplicate goals
run once, cancellation stops unpublished work, a branch cannot promote caps or
grant itself calls, and one branch failure does not erase another branch's
evidence.

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement the deep module**

```python
@dataclass(frozen=True)
class BranchResult:
    branch_id: str
    goal: str
    status: Literal["completed", "partial", "failed"]
    evidence: tuple[AgentEvidence, ...]
    traces: tuple[ProviderTrace, ...]
    gaps: tuple[str, ...]
    tool_calls: int
    error: str = ""

class SubResearchWorker(Protocol):
    def run(self, request: BranchRequest) -> BranchResult: ...

class SubResearchCoordinator:
    def run(self, *, goals, task_frame, context, registry, evidence_sink_factory) -> SubResearchResult: ...
```

The coordinator owns validation, at-most-three concurrency, child budget views,
event-safe result values, and failure isolation. The worker owns only the model
loop inside one goal. Child budget views delegate consumption to the same root
ledger, refuse `grant()`/`promote_caps()`, and expose only their allocated call
and time slice.

- [ ] **Step 4: Add a Continuous branch worker**

The production adapter reuses the injected `AgentModelClient` and authorized
read-only registry. It runs a derived no-output episode, discards draft text,
and returns only evidence, traces, gaps, and usage. It forces child quick mode
so a branch cannot recursively request deep promotion.

- [ ] **Step 5: Run GREEN, Ruff, and commit**

### Task 4: Wire branches into the same primary Episode

**Files:**
- Modify: `intelligence/services/agent_episode.py`
- Modify: `intelligence/services/glm_agent_runtime.py`
- Modify: `intelligence/eval/runtime_backend_benchmark.py`
- Modify: `intelligence/tests/test_agent_episode.py`
- Modify: `intelligence/tests/test_glm_agent_runtime.py`
- Modify: `intelligence/tests/test_runtime_backend_benchmark.py`

- [ ] **Step 1: Write RED same-history tests**

Assert `plan -> mode_decision -> branch_started -> branch_completed` ordering,
one event per goal, max three, imported evidence visible to the next primary
model turn, original initial messages remain an exact prefix, and only the
primary finish enters `AgentOutcome.draft`.

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Inject the coordinator after an approved first plan**

Run branches only when `ModeDecision.effective_mode == "deep"` and the plan has
goals. Append one sanitized `SUB_RESEARCH_RESULTS` user observation after all
branch results; never add branch hidden reasoning or draft prose. Merge evidence
through `BranchEvidenceSink`, traces through the primary accumulator, and usage
through the shared root ledger.

- [ ] **Step 4: Export sanitized branch events**

Allow `branch_started`, `branch_completed`, and `branch_failed` in diagnostics;
keep prompt/messages/internal exceptions redacted.

- [ ] **Step 5: Run GREEN and commit**

### Task 5: Verify the branch milestone

**Files:**
- Modify: `docs/superpowers/plans/2026-07-27-deep-sub-research-branches.md`
- Create: `docs/verification/deep-sub-research-branches-2026-07-27.md`

- [ ] **Step 1: Run focused suites and all 26 permanent invariants**

- [ ] **Step 2: Run one deterministic full suite; record the known local path baseline separately**

- [ ] **Step 3: Record non-actions**

No live nine-case run, no MemoryGate, no UI cutover, no 8792 switch, no `main`
merge, and no review-harness changes.

- [ ] **Step 4: Commit the verification receipt separately**

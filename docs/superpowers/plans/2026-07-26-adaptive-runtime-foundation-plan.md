# Adaptive Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Move long-tail research from a route-shaped contract to a model-owned plan with one bounded `RepairGoal` feedback edge, while preserving deterministic fast paths and all truth/permission gates.

**Architecture:** Introduce a thin `UserTask` projection for user semantics, an observable `ResearchPlan` in the continuous episode, and a deep `RepairCoordinator` that converts verifier/retrieval gaps into same-episode goals without prescribing queries. Existing `TaskFrame`, `ResearchRunContext`, `AgentRuntime`, `ResearchToolRegistry`, structural verifier, semantic verifier, and Run/SSE contracts remain compatibility seams until later plans migrate their consumers.

**Tech Stack:** Python 3.12, dataclasses, provider-neutral `AgentRuntime`, GLM/OpenAI-compatible model adapters, pytest, existing JSON/event contracts, no new database or model dependency.

---

## Scope and Slice Gates

This plan has one product slice: **model-owned planning and bounded same-episode
repair**. It does not add FinanceQuery, sub-agents, memory writeback, or canonical
8792 migration. Each task produces a focused commit and a review request. The
producer must not start the next task until the matching light verdict is `PASS`.

This foundation establishes the information-cutoff value and enforces it on the
continuous runtime's common tool registry plus closed-loop knowledge retrieval.
It is not yet all-provider production coverage: legacy `ask.py` and
`evidence_providers.py` callers do not consistently supply the cutoff, and
undated Graph/L3/KB observations cannot be deterministically classified. The
next `FinanceQuery + EvidenceSearch` slice must close those gaps before the new
runtime may own data-bearing production traffic. All future adapters must reuse
this contract instead of creating provider-local cutoffs.

`latest_data_date` and `source_trade_date` remain provider freshness fields; they
must never lower the global cutoff. For example, a Friday market snapshot must
not hide Saturday or Sunday news when the run's runtime date is the weekend.

The live nine-case suite is forbidden during these tasks. Use scripted models,
cached observations, focused tests, and at most one failing single-case live
replay after the slice is frozen.

## File Map

- Create: `intelligence/services/user_task.py` — thin user-semantic value object
  and provenance types.
- Create: `intelligence/services/research_plan.py` — validated observable plan,
  hypotheses, answer elements, and repair goal values.
- Create: `intelligence/services/repair_coordinator.py` — progress comparison,
  bounded repair-cycle policy, and conversion from verifier coverage to goal.
- Modify: `intelligence/services/agent_runtime.py` — provider-neutral plan and
  plan-event contracts; no provider payloads cross the seam.
- Modify: `intelligence/services/research_contract.py` and
  `episode_factory.py` — immutable cutoff in the root run context.
- Modify: `intelligence/services/research_tool_registry.py` and
  `closed_loop_retrieval.py` — pre-observation cutoff enforcement for continuous
  runtime tools and dated knowledge retrieval.
- Modify: `intelligence/services/provider_observability.py`, `agent_research.py`,
  and `kb_rag.py` — requested/served date lineage and source-date propagation.
- Modify: `intelligence/services/episode_protocol.py` — plan instruction and
  JSON parsing helpers without imposing a fixed research sequence.
- Modify: `intelligence/services/agent_episode.py` — record/validate plan,
  expose repair goals, and continue in the same message history.
- Modify: `intelligence/services/continuous_turn_adapter.py` — keep public
  projection stable while preserving plan/repair state in the private artifact.
- Modify: `intelligence/services/episode_verifier.py` — expose structured
  missing outputs and mandatory capability gaps instead of only strings.
- Modify: `intelligence/services/episode_semantic_verifier.py` — return
  repair-eligible rejected claims without publishing a replacement template.
- Test: `intelligence/tests/test_user_task.py`
- Test: `intelligence/tests/test_information_cutoff.py`
- Test: `intelligence/tests/test_research_plan.py`
- Test: `intelligence/tests/test_repair_coordinator.py`
- Test: `intelligence/tests/test_agent_episode.py`
- Test: `intelligence/tests/test_episode_verifier.py`
- Test: `intelligence/tests/test_continuous_turn_adapter.py`

---

### Task 1: Add the thin UserTask seam

**Files:**
- Create: `intelligence/services/user_task.py`
- Modify: `intelligence/services/research_contract.py`
- Modify: `intelligence/services/episode_factory.py`
- Modify: `intelligence/services/research_tool_registry.py`
- Modify: `intelligence/services/closed_loop_retrieval.py`
- Modify: `intelligence/services/provider_observability.py`
- Modify: `intelligence/services/agent_research.py`
- Modify: `intelligence/services/kb_rag.py`
- Modify: `intelligence/services/task_frame.py` — expose an explicit lazy
  compatibility projection to `UserTask`; do not add routing or presentation
  decisions to this method.
- Test: `intelligence/tests/test_user_task.py`
- Test: `intelligence/tests/test_information_cutoff.py`

- [ ] **Step 1: Write failing value-object tests**

Add tests proving:

```python
def test_user_task_preserves_raw_question_and_resolution_provenance():
    task = UserTask(
        raw_question="目前市场的主线是什么？",
        conversation_context="",
        subjects=(),
        market_scope=ResolvedValue("A股", "product_default"),
        time_window=None,
        assumptions=("按A股市场理解",),
        ambiguities=(),
        user_premises=(),
        task_id="task-1",
    )
    assert task.raw_question == "目前市场的主线是什么？"
    assert task.market_scope.source == "product_default"
    assert task.to_dict()["task_id"] == "task-1"


def test_user_task_rejects_unknown_resolution_source():
    with pytest.raises(ValueError, match="resolution source"):
        ResolvedValue("A股", "guessed")
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_user_task.py
```

Expected: collection fails because `user_task.py` and `UserTask` do not exist.

- [ ] **Step 3: Implement the narrow value objects**

`user_task.py` must define only:

```python
RESOLUTION_SOURCES = frozenset({
    "explicit", "inherited", "product_default", "inferred",
})

@dataclass(frozen=True)
class ResolvedValue:
    value: str
    source: str

    def __post_init__(self) -> None:
        value = self.value.strip()
        if not value:
            raise ValueError("resolved value must be non-empty")
        if self.source not in RESOLUTION_SOURCES:
            raise ValueError("unsupported resolution source")
        object.__setattr__(self, "value", value)

@dataclass(frozen=True)
class UserTask:
    raw_question: str
    conversation_context: str
    subjects: tuple[ResolvedValue, ...]
    market_scope: ResolvedValue | None
    time_window: Mapping[str, object] | None
    assumptions: tuple[str, ...]
    ambiguities: tuple[str, ...]
    user_premises: tuple[str, ...]
    task_id: str
```

Validate JSON-safe fields, trim/deduplicate strings, preserve the raw question,
and provide `to_dict()` plus `from_task_frame(frame, context)`. The projection
must copy subject/market/time provenance from existing fields and label an
inferred A-share default as `product_default`; it must not infer a new topic.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the command from Step 2. Expected: all UserTask tests pass.

Also run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_information_cutoff.py
```

The cutoff tests must prove the composition root freezes one value, every
continuous-registry observation drops source-dated future evidence, closed-loop
retrieval rejects a high-scoring future hit before bucketing, ProviderTrace
round-trips requested/served dates, and forecast dates inside article text do
not masquerade as publication dates. They must not claim coverage for legacy
providers or undated observations.

- [ ] **Step 5: Commit and request review**

```bash
git add intelligence/services/user_task.py \
  intelligence/services/research_contract.py \
  intelligence/services/episode_factory.py \
  intelligence/services/research_tool_registry.py \
  intelligence/services/closed_loop_retrieval.py \
  intelligence/services/provider_observability.py \
  intelligence/services/agent_research.py \
  intelligence/services/kb_rag.py \
  intelligence/services/task_frame.py \
  intelligence/tests/test_user_task.py \
  intelligence/tests/test_information_cutoff.py
git commit -m "feat: add user task and information cutoff seam"
```

Write a review request naming the commit and both focused tests. It must verify
the continuous runtime's common registry filter, list legacy/undated boundaries,
and avoid claiming that each provider independently implements cutoff logic. Do
not modify the producer worktree while the reviewer checks it.

---

### Task 2: Add observable model-owned ResearchPlan

**Files:**
- Create: `intelligence/services/research_plan.py`
- Modify: `intelligence/services/agent_runtime.py:100-170, 270-360`
- Modify: `intelligence/services/episode_protocol.py:70-185`
- Modify: `intelligence/services/agent_episode.py:216-470`
- Test: `intelligence/tests/test_research_plan.py`
- Test: `intelligence/tests/test_agent_episode.py`

- [ ] **Step 1: Write failing plan protocol tests**

Test the provider-neutral plan contract through the episode seam:

```python
def test_first_model_turn_can_publish_a_plan_without_granting_tools():
    turn = ModelTurn(
        content=json.dumps({
            "kind": "PLAN",
            "task_summary": "判断市场主线并给出反方",
            "answer_elements": ["direct_assessment", "counterpoint"],
            "hypotheses": ["半导体可能是持续主线"],
            "evidence_needs": ["同日主线与持续性"],
            "candidate_actions": ["market_snapshot", "news_search"],
            "open_gaps": ["缺少反方证据"],
            "requested_mode": "quick",
            "revision": 1,
        }, ensure_ascii=False),
        tool_calls=(), provider_name="scripted",
    )
    plan = parse_research_plan(turn.content)
    assert plan.answer_elements == ("direct_assessment", "counterpoint")
    assert plan.candidate_actions == ("market_snapshot", "news_search")
    assert plan.open_gaps == ("缺少反方证据",)
    assert plan.requested_mode == "quick"


def test_plan_revision_must_increase_and_preserve_task_identity():
    first = parse_research_plan(plan_json(revision=1))
    second = parse_research_plan(plan_json(revision=2))
    assert second.revision > first.revision
    with pytest.raises(ValueError, match="revision"):
        validate_plan_revision(second, first, original_task_id="task-1", current_task_id="task-1")
    with pytest.raises(ValueError, match="task identity"):
        validate_plan_revision(first, second, original_task_id="task-1", current_task_id="task-2")
```

Also assert that malformed/unknown plan fields are rejected, the original
`TaskFrame` hash stays unchanged, and a plan-only first turn does not count as a
tool call or permit an unauthorized tool.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_research_plan.py \
  intelligence/tests/test_agent_episode.py -k 'plan or task_frame_hash'
```

Expected: import or assertion failures because plan parsing and plan events do
not exist.

- [ ] **Step 3: Implement provider-neutral plan types**

`research_plan.py` defines validated frozen values:

```python
ResearchMode = Literal["quick", "deep"]

@dataclass(frozen=True)
class ResearchPlan:
    task_summary: str
    answer_elements: tuple[str, ...]
    hypotheses: tuple[str, ...]
    evidence_needs: tuple[str, ...]
    candidate_actions: tuple[str, ...]
    open_gaps: tuple[str, ...]
    requested_mode: ResearchMode
    revision: int = 1

@dataclass(frozen=True)
class PlanParseResult:
    plan: ResearchPlan | None
    error: str = ""

def parse_research_plan(content: str) -> ResearchPlan: ...
def plan_to_public_dict(plan: ResearchPlan) -> dict[str, object]: ...
```

The parser accepts one JSON object with `kind=PLAN`, bounded string lengths,
deduplicated arrays, 1-8 answer elements, 1-4 hypotheses, 0-8 candidate
actions, 0-8 open gaps, a positive integer `revision`, and quick/deep only.
`validate_plan_revision(previous, current, original_task_id=...,
current_task_id=...)` requires a strictly larger revision and the same original
task identity. It never accepts tools,
evidence hashes, budgets, completion status, or factual claims as plan
authority.

Extend the provider-neutral event ledger with a `plan` event payload and an
optional `plan` field on `AgentOutcome`. Keep provider adapters returning the
existing `ModelTurn`; no GLM/OpenAI object crosses the seam.

- [ ] **Step 4: Update the episode instruction and state machine**

In `episode_protocol.py`, tell the model that its first planning turn may emit
`PLAN` JSON or directly call an authorized tool when the task is trivial. The
plan is observable guidance, not proof or completion. Do not enumerate a fixed
sequence of tools.

In `agent_episode.py`:

1. Parse a valid `PLAN` content before processing tool calls.
2. Record a `plan` event and retain the latest revision in the outcome.
3. On malformed plan content, append a same-episode repair instruction once;
   do not fall back to a route template.
4. Continue passing the original task and all raw tool observations unchanged.
5. Keep `validate_episode_finish()` as the only terminal envelope parser.

Existing scripted models that start with a tool call remain compatible. This is
important for the current backend A/B and prevents a protocol migration from
changing the control arm before the plan tests are green.

- [ ] **Step 5: Run focused tests and existing episode tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_research_plan.py \
  intelligence/tests/test_agent_episode.py
```

Expected: all plan and episode tests pass; no existing episode behavior changes
outside the new optional plan event.

- [ ] **Step 6: Commit and request review**

```bash
git add intelligence/services/research_plan.py \
  intelligence/services/agent_runtime.py \
  intelligence/services/episode_protocol.py \
  intelligence/services/agent_episode.py \
  intelligence/tests/test_research_plan.py \
  intelligence/tests/test_agent_episode.py
git commit -m "feat: record model-owned research plans"
```

The review request must require proof that `PLAN` is not an alternate route,
cannot grant tools/budget, and does not weaken invalid-action accounting.

The authoritative plan shape is the one in the design specification: it must
include `answer_elements`, `hypotheses`, `evidence_needs`, `candidate_actions`,
and `open_gaps`, plus a monotonic `revision`. If implementation narrows that
shape, the design must be amended in a separate docs-only review before code is
written; the two documents may not silently diverge.

---

### Task 3: Implement RepairGoal and same-episode re-entry

**Files:**
- Create: `intelligence/services/repair_coordinator.py`
- Modify: `intelligence/services/episode_verifier.py:35-260`
- Modify: `intelligence/services/episode_semantic_verifier.py` at its public
  result dataclass and gate return path
- Modify: `intelligence/services/agent_episode.py:420-570`
- Modify: `intelligence/services/continuous_turn_adapter.py:500-550`
- Modify: `intelligence/services/agent_runtime.py` — expose a provider-neutral
  `EpisodeSession` continuation seam; `run()` alone is not sufficient because
  verifiers execute after it returns.
- Create: `intelligence/services/episode_session.py` — provider-neutral session
  protocol and lifecycle result used by every production runtime adapter.
- Modify: `intelligence/services/research_contract.py` — add the singleton
  `RootBudgetLedger` interface and distinguish initial allocation from the
  immutable quick/deep hard cap.
- Create: `intelligence/services/evidence_ledger.py` — canonical append-only
  evidence snapshot interface for this runtime; it must not become a second
  user decision ledger.
- Test: `intelligence/tests/test_repair_coordinator.py`
- Test: `intelligence/tests/test_episode_verifier.py`
- Test: `intelligence/tests/test_continuous_turn_adapter.py`
- Test: `intelligence/tests/test_episode_session.py`
- Test: `intelligence/tests/test_evidence_ledger.py`

The continuation seam is executable and provider-neutral:

```python
class EpisodeSession(Protocol):
    episode_id: str
    outcome: AgentOutcome

    def resume(self, goal: RepairGoal) -> AgentOutcome: ...

class AgentRuntime(Protocol):
    def start(self, task: UserTask, *, context: ResearchRunContext) -> EpisodeSession: ...
```

`AgentRuntime.start()` is called exactly once for a production run. The
returned session owns the original provider history, episode/event ledger,
EvidenceLedger, QueryLedger, usage ledger, authorized tool registry, and root
deadline. `resume()` appends the repair instruction to that session and returns
the updated outcome; it may not call `start()` or `run()` internally. Terminal,
cancelled, provider-error, and exhausted-budget outcomes all remain observable
through `outcome` and preserve the same `episode_id`. Continuous, SDK, and
headless adapters must implement this interface before they can own production
traffic; an adapter that cannot do so remains benchmark-only.

- [ ] **Step 1: Write failing repair tests**

Cover three independent sources of a goal:

```python
def test_missing_required_output_becomes_repair_goal():
    goal = repair_goal_from_coverage(
        missing_outputs=("counterpoint",),
        missing_capabilities=("news_search",),
        rejected_claims=(),
        attempted_actions=("market_data:A股",),
        previous_progress=ProgressSnapshot(
            before_evidence_ids=(), after_evidence_ids=("e1",),
            before_covered_outputs=(), after_covered_outputs=("direct_assessment",),
            before_open_gaps=("counterpoint",), after_open_gaps=("counterpoint",),
            independent_source_families=("market",),
        ),
        remaining_calls=3,
        remaining_seconds=42.0,
    )
    assert goal.missing_answer_elements == ("counterpoint",)
    assert not hasattr(goal, "next_query")
```

Add episode tests proving an empty tool observation causes a new model turn in
the same history, the new turn sees the failed observation and repair goal, and
the executor still rejects an unauthorized or duplicate call. Add a monotonic
test proving a no-progress cycle does not increase the budget. Add a
`test_progress_snapshot_is_ledger_derived` fixture that compares two immutable
EvidenceLedger snapshots, and a root-budget test proving an accepted grant
decrements the one ledger while a second ledger or a grant above the hard cap
is rejected.

- [ ] **Step 2: Run repair tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_repair_coordinator.py \
  intelligence/tests/test_episode_verifier.py -k 'repair or gap or missing'

/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_session.py \
  intelligence/tests/test_evidence_ledger.py -k 'session or snapshot or budget'
```

Expected: failures because coverage is represented only as strings and no
repair re-entry state exists.

- [ ] **Step 3: Implement structured coverage and RepairGoal**

`repair_coordinator.py` owns:

```python
@dataclass(frozen=True)
class CoverageDelta:
    new_evidence: int
    narrowed_gaps: int
    newly_supported_outputs: int

@dataclass(frozen=True)
class ProgressSnapshot:
    before_evidence_ids: tuple[str, ...]
    after_evidence_ids: tuple[str, ...]
    before_covered_outputs: tuple[str, ...]
    after_covered_outputs: tuple[str, ...]
    before_open_gaps: tuple[str, ...]
    after_open_gaps: tuple[str, ...]
    independent_source_families: tuple[str, ...]

    @property
    def effective_new_evidence(self) -> int: ...

    @property
    def coverage_delta(self) -> CoverageDelta: ...

@dataclass(frozen=True)
class BudgetGrant:
    grant_id: str
    episode_id: str
    cycle: int
    calls_granted: int
    seconds_granted: float

class RootBudgetLedger(Protocol):
    """The only mutable budget authority for an episode."""

    initial_calls: int
    hard_calls_cap: int
    initial_seconds: float
    hard_seconds_cap: float
    remaining_calls: int
    remaining_seconds: float

    def grant(self, grant: BudgetGrant) -> bool: ...

    def consume_call(self, *, seconds: float) -> None: ...

@dataclass(frozen=True)
class RepairGoal:
    episode_id: str
    repair_goal_id: str
    cycle: int
    missing_answer_elements: tuple[str, ...]
    unsupported_claims: tuple[str, ...]
    missing_evidence_modes: tuple[str, ...]
    attempted_actions: tuple[str, ...]
    evidence_progress: CoverageDelta
    remaining_calls: int
    remaining_seconds: float

def build_repair_goal(...): RepairGoal
def progress_from_ledger(before: EvidenceLedgerSnapshot, after: EvidenceLedgerSnapshot) -> ProgressSnapshot
def should_reenter(progress: ProgressSnapshot, *, cycle: int, max_cycles: int) -> bool
def grant_for_progress(goal: RepairGoal, progress: ProgressSnapshot, *, root_budget: RootBudgetLedger) -> BudgetGrant | None
```

`ProgressSnapshot` is produced by comparing append-only EvidenceLedger snapshots;
callers may not pass precomputed integer deltas as truth. The ledger builder
counts only cutoff-valid, nonduplicate, non-same-family evidence bound to an
uncovered output or active hypothesis. A progress predicate is true only when
effective new evidence is at least one and coverage delta is at least one. A
successful grant uses:

```text
calls = min(4, max(1, uncovered_output_count + missing_evidence_mode_count))
seconds = min(30, calls * 8)
```

The grant is atomically reserved through `RootBudgetLedger.grant()`; it cannot
reset consumed calls or extend the hard mode cap. Initial allocation is the
number of calls available before repair, while the hard cap is the maximum
across the entire episode. All repair sources share the one quick/deep cycle
pool. The module never constructs a query or selects a tool. It returns `False` when
the cycle cap is reached, the deadline is below the configured minimum, or the
latest attempt made no progress. Tests must assert the exact event sequence:
`gate_failure -> repair_goal -> model_action(new id) -> observation -> verify`.

Extend `VerifiedEpisodeOutcome` with machine-readable `missing_outputs` and
`mandatory_missing_capabilities`, preserving its existing `issues` strings for
compatibility. Extend semantic result with rejected claim indexes and
repair-eligible required output IDs. These fields must flow into the private
artifact and not the public answer.

- [ ] **Step 4: Re-enter the same episode**

After a structural or semantic failure and before deterministic span redaction:

1. Build a `RepairGoal` from missing outputs, missing capabilities, rejected
   claims, attempted actions, evidence delta, and remaining deadline.
2. If `should_reenter()` is true, call the provider-neutral
   `EpisodeSession.resume(repair_goal)` continuation. `EpisodeSession` owns the
   original history, `episode_id`, event ledger, EvidenceLedger, QueryLedger,
   usage ledger, and root deadline; it must not call `AgentRuntime.run()` a
   second time. The resume operation appends one user-role message containing
   the goal and instruction: preserve the original task, choose a new
   model-owned action, and do not repeat normalized queries.
3. Expose the same current authorized tools; do not add a tool because the
   verifier asked for one. The capability contract remains the hard boundary.
4. Record `repair_goal` and `repair_reentry` events; keep all previous
   observations in the same messages and ledger.
5. Re-run the terminal parser and verifiers on the resulting draft through the
   same session; the test must fail if a second history, QueryLedger, or budget
   ledger is created.
6. Only if re-entry is exhausted may optional unsupported spans be removed. If
   removing them would lose a required output, return question-specific
   partial/gap.

The root deadline and usage ledger remain singletons; repair does not reset
`tool_calls`, `llm_calls`, query ledger, or invalid-action counts.

- [ ] **Step 5: Run focused and adapter tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_repair_coordinator.py \
  intelligence/tests/test_episode_verifier.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_episode_session.py \
  intelligence/tests/test_evidence_ledger.py -k 'repair or gap or partial or session or snapshot or budget'
```

Expected: all focused tests pass and existing invalid-action/gate assertions
remain unchanged.

- [ ] **Step 6: Commit and request review**

```bash
git add intelligence/services/repair_coordinator.py \
  intelligence/services/episode_verifier.py \
  intelligence/services/episode_semantic_verifier.py \
  intelligence/services/agent_episode.py \
  intelligence/services/continuous_turn_adapter.py \
  intelligence/services/agent_runtime.py \
  intelligence/services/episode_session.py \
  intelligence/services/research_contract.py \
  intelligence/services/evidence_ledger.py \
  intelligence/tests/test_repair_coordinator.py \
  intelligence/tests/test_episode_verifier.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_episode_session.py \
  intelligence/tests/test_evidence_ledger.py
git commit -m "feat: reenter research episodes for verified gaps"
```

This is a hard architecture review gate. The reviewer must prove that a repair
executes a new model-owned action and is not merely a renamed fallback.
The review request must also prove one `AgentRuntime.start()`, one session
identity, `EpisodeSession.resume()` without a second run, EvidenceLedger-derived
progress, atomic `RootBudgetLedger` reservation, and unchanged invalid-action
accounting.

---

## Slice Acceptance

The foundation slice is accepted only when all of these are true:

- `UserTask` preserves raw wording and provenance without becoming a second
  semantic object that competes with TaskFrame.
- The first model plan is observable, bounded, and cannot grant tools, facts,
  budgets, or completion.
- At least one empty/insufficient observation causes a same-episode repair turn
  with the original task and raw observation still present.
- No repair can repeat a normalized query, exceed the root budget, or turn
  `partial` into `completed` without evidence.
- Existing deterministic fast paths and all benchmark invalid-action gates pass.
- `git diff --check` and focused tests pass for every slice.
- The branch contains no secret, database, cache, or benchmark output.

After this foundation plan is approved by the reviewer, the next independent
plan is `FinanceQuery + EvidenceSearch`; it will add typed structured retrieval
without changing this slice's ownership interfaces.

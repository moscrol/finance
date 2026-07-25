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
- Test: `intelligence/tests/test_research_plan.py`
- Test: `intelligence/tests/test_repair_coordinator.py`
- Test: `intelligence/tests/test_agent_episode.py`
- Test: `intelligence/tests/test_episode_verifier.py`
- Test: `intelligence/tests/test_continuous_turn_adapter.py`

---

### Task 1: Add the thin UserTask seam

**Files:**
- Create: `intelligence/services/user_task.py`
- Test: `intelligence/tests/test_user_task.py`
- Modify: `intelligence/services/task_frame.py:81-168` only to add an explicit
  compatibility projection; do not remove current fields in this task.

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

- [ ] **Step 5: Commit and request review**

```bash
git add intelligence/services/user_task.py \
  intelligence/services/task_frame.py \
  intelligence/tests/test_user_task.py
git commit -m "feat: add thin user task seam"
```

Write a review request naming the commit and `test_user_task.py`; do not modify
the producer worktree while the reviewer checks it.

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
            "requested_mode": "quick",
        }, ensure_ascii=False),
        tool_calls=(), provider_name="scripted",
    )
    plan = parse_research_plan(turn.content)
    assert plan.answer_elements == ("direct_assessment", "counterpoint")
    assert plan.requested_mode == "quick"
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
deduplicated arrays, 1-8 answer elements, 1-4 hypotheses, and quick/deep only.
It never accepts tools, evidence hashes, budgets, completion status, or factual
claims as plan authority.

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

---

### Task 3: Implement RepairGoal and same-episode re-entry

**Files:**
- Create: `intelligence/services/repair_coordinator.py`
- Modify: `intelligence/services/episode_verifier.py:35-260`
- Modify: `intelligence/services/episode_semantic_verifier.py` at its public
  result dataclass and gate return path
- Modify: `intelligence/services/agent_episode.py:420-570`
- Modify: `intelligence/services/continuous_turn_adapter.py:500-550`
- Test: `intelligence/tests/test_repair_coordinator.py`
- Test: `intelligence/tests/test_episode_verifier.py`
- Test: `intelligence/tests/test_continuous_turn_adapter.py`

- [ ] **Step 1: Write failing repair tests**

Cover three independent sources of a goal:

```python
def test_missing_required_output_becomes_repair_goal():
    goal = repair_goal_from_coverage(
        missing_outputs=("counterpoint",),
        missing_capabilities=("news_search",),
        rejected_claims=(),
        attempted_actions=("market_data:A股",),
        previous_progress=CoverageDelta(0, 0, 0),
        remaining_calls=3,
        remaining_seconds=42.0,
    )
    assert goal.missing_answer_elements == ("counterpoint",)
    assert goal.next_query is None
```

Add episode tests proving an empty tool observation causes a new model turn in
the same history, the new turn sees the failed observation and repair goal, and
the executor still rejects an unauthorized or duplicate call. Add a monotonic
test proving a no-progress cycle does not increase the budget.

- [ ] **Step 2: Run repair tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_repair_coordinator.py \
  intelligence/tests/test_episode_verifier.py -k 'repair or gap or missing'
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
class RepairGoal:
    missing_answer_elements: tuple[str, ...]
    unsupported_claims: tuple[str, ...]
    missing_evidence_modes: tuple[str, ...]
    attempted_actions: tuple[str, ...]
    evidence_progress: CoverageDelta
    remaining_calls: int
    remaining_seconds: float

def build_repair_goal(...): RepairGoal
def should_reenter(previous: CoverageDelta, current: CoverageDelta, *, cycle: int, max_cycles: int) -> bool
```

The module never constructs a query or selects a tool. It returns `False` when
the cycle cap is reached, the deadline is below the configured minimum, or the
latest attempt made no progress.

Extend `VerifiedEpisodeOutcome` with machine-readable `missing_outputs` and
`mandatory_missing_capabilities`, preserving its existing `issues` strings for
compatibility. Extend semantic result with rejected claim indexes and
repair-eligible required output IDs. These fields must flow into the private
artifact and not the public answer.

- [ ] **Step 4: Re-enter the same episode**

After a structural or semantic failure and before deterministic span redaction:

1. Build a `RepairGoal` from missing outputs, missing capabilities, rejected
   claims, attempted actions, evidence delta, and remaining deadline.
2. If `should_reenter()` is true, append one user-role message containing the
   goal and instruction: preserve the original task, choose a new model-owned
   action, and do not repeat normalized queries.
3. Expose the same current authorized tools; do not add a tool because the
   verifier asked for one. The capability contract remains the hard boundary.
4. Record `repair_goal` and `repair_reentry` events; keep all previous
   observations in the same messages and ledger.
5. Re-run the terminal parser and verifiers on the resulting draft.
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
  intelligence/tests/test_continuous_turn_adapter.py -k 'repair or gap or partial'
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
  intelligence/tests/test_repair_coordinator.py \
  intelligence/tests/test_episode_verifier.py \
  intelligence/tests/test_continuous_turn_adapter.py
git commit -m "feat: reenter research episodes for verified gaps"
```

This is a hard architecture review gate. The reviewer must prove that a repair
executes a new model-owned action and is not merely a renamed fallback.

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


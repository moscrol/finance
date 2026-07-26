# Adaptive Mode Governor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Honor the model's first-plan request for deep research without giving the model direct budget authority, while keeping quick research bounded and auditable.

**Architecture:** A new deep `ModeGovernor` module owns one interface: `decide(plan, signals) -> ModeDecision`, plus `apply(context, decision) -> ResearchRunContext`. The model owns `ResearchPlan.requested_mode`; observable signals and user mode are code-owned inputs. Approval atomically upgrades the existing root ledger and returns a longer deep context with the same episode, task, cutoff, tools, evidence ledger, and message history. The episode records one `mode_decision` event and never rebuilds the model conversation.

**Tech Stack:** Frozen Python dataclasses, existing `ResearchPlan`, `ResearchPolicy`, `ResearchRunContext`, `InMemoryRootBudgetLedger`, pytest, Ruff.

---

## Scope split

This plan implements only adaptive mode ownership and same-Episode budget promotion. Separate plans will cover:

1. max-three read-only sub-research branches and the branch-facing append-only evidence facade;
2. public Run/SSE progress projection and `continuous_glm` token accounting;
3. `MemoryGate` and checkpoint/verdict-backed promotion.

The existing asynchronous `RunStore`, supervisor, cancellation, reconnect replay, and terminal claim are reused unchanged.

## Public seams under test

1. `ModeGovernor.decide()` approves or denies a deep request from explicit observable signals without inspecting route names or choosing research actions.
2. `ModeGovernor.apply()` upgrades one existing context atomically, preserves episode identity and cutoff, and cannot exceed the 24-call/240-second product cap.
3. `ContinuousAgentEpisode.run()` records exactly one mode decision after the first valid plan and uses the promoted context for subsequent tool calls and resumable repair state.

### Task 1: Add the pure ModeGovernor decision contract

**Files:**
- Create: `intelligence/services/mode_governor.py`
- Create: `intelligence/tests/test_mode_governor.py`

- [x] **Step 1: Write failing decision-table tests**

Cover these independent cases:

```python
assert governor.decide(deep_plan, ModeSignals(evidence_domains=("盘面", "新闻"))).effective_mode == "deep"
assert governor.decide(deep_plan, ModeSignals(user_mode="quick", evidence_domains=("盘面", "新闻"))).effective_mode == "quick"
assert governor.decide(deep_plan, ModeSignals()).reason == "no_observable_deep_condition"
assert governor.decide(quick_plan, ModeSignals(evidence_domains=("盘面", "新闻"))).effective_mode == "quick"
assert governor.decide(quick_plan, ModeSignals(user_mode="deep")).effective_mode == "deep"
```

Also assert dependency/deadline denial, comparison entities, uncovered answer elements, and explicit complexity flags. No test may mention a route or `question_type`.

- [x] **Step 2: Run RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_mode_governor.py -q
```

Expected: import failure because the module does not exist.

- [x] **Step 3: Implement the immutable decision values**

Create:

```python
UserMode = Literal["auto", "quick", "deep"]
EffectiveMode = Literal["quick", "deep"]
ComplexityFlag = Literal[
    "causal_attribution",
    "valuation",
    "counterfactual",
    "historical_analogy",
    "supply_chain_mapping",
]

@dataclass(frozen=True)
class ModeSignals:
    user_mode: UserMode = "auto"
    independent_entities: int = 0
    evidence_domains: tuple[str, ...] = ()
    complexity_flags: tuple[ComplexityFlag, ...] = ()
    uncovered_answer_elements: int = 0
    dependencies_available: bool = True
    deep_deadline_available: bool = True

@dataclass(frozen=True)
class ModeDecision:
    requested_mode: EffectiveMode
    effective_mode: EffectiveMode
    approved: bool
    reason: str
    observable_conditions: tuple[str, ...]
    research_tier: Literal["standard", "deep"]
    tool_call_cap: int
    target_seconds: float
    max_repair_cycles: int
    max_branches: int
```

`ModeGovernor.decide()` applies this order: explicit quick denial; dependency/deadline denial; explicit user deep approval; model quick remains quick; model deep requires at least one observable condition. Quick maps to existing `standard` policy (90 seconds, hard cap 8); deep maps to `deep` (240 seconds, hard cap 24). It never edits the plan.

- [x] **Step 4: Run GREEN and Ruff**

### Task 2: Make root-budget promotion an explicit atomic authority

**Files:**
- Modify: `intelligence/services/research_contract.py`
- Modify: `intelligence/services/mode_governor.py`
- Modify: `intelligence/tests/test_mode_governor.py`
- Modify: `intelligence/tests/test_research_contract.py`

- [x] **Step 1: Write failing promotion invariant tests**

Create a standard context and prove:

```python
promoted = governor.apply(context, approved_deep_decision)
assert promoted.contract is context.contract
assert promoted.information_cutoff == context.information_cutoff
assert promoted.root_budget is context.root_budget
assert promoted.policy.tier == "deep"
assert promoted.root_budget.hard_calls_cap == 24
assert promoted.root_budget.remaining_calls == 24
assert promoted.root_budget.hard_seconds_cap == 240.0
assert promoted.deadline.remaining() > context.deadline.remaining()
```

Then prove duplicate application is idempotent, denied/quick decisions change nothing, foreign episode IDs cannot promote, caps cannot be lowered, and no promotion exceeds 24 calls/240 seconds.

- [x] **Step 2: Run RED**

Expected: the root ledger has no promotion interface and standard hard caps remain 8/90.

- [x] **Step 3: Add the minimum promotion interface**

Extend `RootBudgetLedger` with:

```python
def promote_caps(
    self,
    *,
    episode_id: str,
    promotion_id: str,
    hard_calls_cap: int,
    hard_seconds_cap: float,
) -> bool: ...
```

`InMemoryRootBudgetLedger.promote_caps()` is locked, episode-bound, idempotent by `promotion_id`, increase-only, and rejects caps above 24/240. After raising caps, `ModeGovernor.apply()` uses one normal `BudgetGrant` to allocate only the difference between the already allocated standard budget and the deep budget. It returns `replace(context, policy=deep_policy, deadline=extended_deadline)`; it never mints a second ledger.

- [x] **Step 4: Run GREEN, permanent invariants, and Ruff**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_mode_governor.py \
  intelligence/tests/test_research_contract.py \
  intelligence/tests/test_repair_invariant_regression.py \
  intelligence/tests/test_session_invariant_regression.py -q
```

### Task 3: Wire one mode decision into the same Episode

**Files:**
- Modify: `intelligence/services/agent_episode.py`
- Modify: `intelligence/services/glm_agent_runtime.py`
- Modify: `intelligence/tests/test_agent_episode.py`
- Modify: `intelligence/tests/test_glm_agent_runtime.py`

- [x] **Step 1: Write failing same-history promotion tests**

Use a scripted model that emits a valid deep `PLAN`, then enough distinct tool calls to exceed the standard six-call allocation, then a valid finish. Assert:

- the seventh call executes only after an approved `mode_decision`;
- the event immediately follows the first `plan` event and appears exactly once;
- every subsequent model call retains the original messages and observations;
- `AgentOutcome.plan.requested_mode == "deep"`;
- the continuation state's context is the promoted context;
- a model deep request with no observable condition stays at quick/standard bounds;
- explicit user quick mode cannot be overridden by the model.

- [x] **Step 2: Run RED**

Expected: `requested_mode` is recorded but ignored and the seventh call cannot execute.

- [x] **Step 3: Inject ModeGovernor without adding a route planner**

Add optional constructor dependencies:

```python
mode_governor: ModeGovernor | None = None
mode_signals: Callable[[TaskFrame, ResearchPlan], ModeSignals] | None = None
```

The default signal projection uses only observable plan/task facts:

- count of distinct comparison entities already resolved on the task;
- distinct `ResearchPlan.evidence_needs`;
- number of currently open plan gaps/answer elements.

It does not use `question_type`, route tables, fixed tool order, or query text keywords. After the first valid plan, call the governor once, replace the local context with `apply(...)`, update the mutable continuation state's context, and append `mode_decision` to the ledger. Plan revisions do not receive another promotion decision.

The loop keeps a fixed absolute safety range based on the deep policy but continues to finalize from the current context policy and remaining root budget. Quick mode therefore does not gain extra calls merely because the loop can represent deep mode.

- [x] **Step 4: Run GREEN and adjacent episode suites**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_mode_governor.py \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_glm_agent_runtime.py \
  intelligence/tests/test_episode_session.py \
  intelligence/tests/test_continuous_turn_adapter.py -q
```

### Task 4: Export mode decisions through existing diagnostics

**Files:**
- Modify: `intelligence/eval/runtime_backend_benchmark.py`
- Modify: `intelligence/tests/test_runtime_backend_benchmark.py`

- [x] **Step 1: Write a failing diagnostic projection test**

Add a `mode_decision` event with approved mode, reason, observable conditions, and caps. Assert it survives the safe projection while task text, prompts, and internal policy objects do not.

- [x] **Step 2: Add `mode_decision` to the diagnostic event allowlist**

No new benchmark schema or artifact type is created.

- [x] **Step 3: Run GREEN, Ruff, and `git diff --check`**

### Task 5: Verify and document the adaptive-mode milestone

**Files:**
- Modify: `docs/superpowers/plans/2026-07-27-adaptive-mode-governor.md`
- Create: `docs/verification/adaptive-mode-governor-2026-07-27.md`

- [x] **Step 1: Run focused and full deterministic suites**

Record exact counts and preserve the known userspace/subconscious baseline separately.

- [x] **Step 2: Record non-actions**

The receipt must state: no sub-research branches yet, no MemoryGate yet, no frozen nine-case run, no 8792 switch, no `main` merge, and no review-harness changes.

- [x] **Step 3: Commit product code separately from the verification receipt**

# Product Runtime and Self-Use Root Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the clean `openai/gpt-5.6-sol` candidate complete the five real product workflows under one sealed standard/deep runtime profile and make only matching real product runs eligible for the ten-trading-day Self-use Gate.

**Architecture:** Extract required-output/evidence-plan derivation into a pure deep module, then produce one immutable `ReleaseLatencyAdmission` before the continuous adapter is constructed. The admission tightens both the adapter and the outer supervisor from the same run start; one shared 40-second child deadline bounds the entire semantic chain. A sealed `ReleaseExecutionProfile` propagates through private artifacts, reports, SSE, and version-2 self-use events, while typed-query and valuation fixes remain generic and fail closed.

**Tech Stack:** Python 3.12, FastAPI, DuckDB, OpenAI Agents SDK-compatible runtime, pytest, Ruff, RunStore/SSE artifacts, macOS Keychain provider configuration.

**Approved spec:** `docs/superpowers/specs/2026-07-29-product-runtime-self-use-root-repair-design.md`

**Execution order:** Finish data-plan Tasks 1-8 before starting this plan. Runtime
Tasks 1-9 may proceed while the calendar-bound data Task 9 accumulates its
three-night streak. Do not execute this plan's Task 10 product canary until that
streak is green.

**Non-execution guards:** Do not run an App Server arm, the 28-question board,
Knevo comparison, or another sealed-five debugging retry as part of Tasks 1-9.
Do not merge `main`, switch 8792, or start the ten-day campaign before the
pre-registered product canary and cutover approval gates say to do so.

---

## File Structure

- Create `intelligence/services/episode_contract_inputs.py`: pure required-output, evidence-plan, and capability derivation shared by admission and context construction.
- Create `intelligence/services/release_execution.py`: immutable latency admission, behavior fingerprint, release profile, and self-use policy projection.
- Modify `intelligence/services/episode_factory.py`: consume `EpisodeContractInputs` instead of privately deriving the same data.
- Modify `intelligence/services/research_contract.py`: set standard/deep hard tool caps to 8/24 without changing quick.
- Modify `intelligence/services/continuous_turn_adapter.py`: require admitted tier/allocations and reuse one semantic child deadline.
- Modify `intelligence/services/episode_semantic_verifier.py`: accept an explicitly sealed judge provider and forbid ambient substitution in release mode.
- Modify `intelligence/services/conversation_orchestrator.py`: build the continuous adapter from the already frozen `TaskFrame` and `TurnControlResult`.
- Modify `intelligence/api/app.py`: tighten the per-run supervisor timer and cancellation deadline from the admission result.
- Modify `intelligence/api/structured_reports.py`: persist non-secret release-profile identity and answer truth.
- Modify `intelligence/services/finance_query.py`: normalize scalar `in` values and canonical A-share stock codes before validation/fingerprinting.
- Modify `intelligence/services/valuation_estimate.py`: model current local price separately from dated valuation ratios.
- Modify `intelligence/services/ask_blocks.py`: compose a cutoff-safe local price anchor without treating missing ratios as present.
- Modify `intelligence/services/episode_tools.py`: expose the separated price/ratio evidence contract.
- Modify `intelligence/services/self_use_maturity.py`: version-2 events, release policy binding, profile filtering, and deterministic duplicate semantics.
- Modify `intelligence/cli.py`: load the active release policy for record/status/approval commands.
- Modify `scripts/smoke_workbench_self_use.py`: verify profile-bound eligibility without creating a real campaign event.
- Create `intelligence/tests/test_episode_contract_inputs.py`.
- Create `intelligence/tests/test_release_execution.py`.
- Modify `intelligence/tests/test_episode_factory.py`.
- Modify `intelligence/tests/test_continuous_turn_adapter.py`.
- Modify `intelligence/tests/test_workbench_api.py`.
- Modify `intelligence/tests/test_workbench_conversation_integration.py`.
- Modify `intelligence/tests/test_finance_query.py`.
- Modify `intelligence/tests/test_episode_tools.py`.
- Modify `intelligence/tests/test_valuation_estimate.py`.
- Modify `intelligence/tests/test_self_use_maturity.py`.
- Modify `intelligence/tests/test_self_use_cli.py`.
- Modify `intelligence/tests/test_smoke_workbench_self_use.py`.
- Create `docs/verification/product-runtime-self-use-root-repair-result-2026-07-29.md`.
- Create after all deterministic gates pass: `docs/verification/8792-cutover-candidate-2026-07-29.md`.

## Interface Decision

The core interface is:

```python
inputs = derive_episode_contract_inputs(frame, capabilities=control.capabilities)
admission = admit_release_latency(frame, control, inputs, explicit_tier=None)
profile = build_release_execution_profile(repo_root, backend, provider, admission_policy)
```

`ReleaseLatencyAdmission` contains `tier`, `research_seconds`, `tool_cap`,
`semantic_seconds`, `total_seconds`, and stable reasons. No caller passes a bare
timeout or tier after this module is installed.

### Task 1: Extract Contract Inputs Before Any Tier Is Chosen

**Files:**
- Create: `intelligence/services/episode_contract_inputs.py`
- Create: `intelligence/tests/test_episode_contract_inputs.py`
- Modify: `intelligence/services/episode_factory.py`
- Modify: `intelligence/tests/test_episode_factory.py`

- [ ] **Step 1: Write failing tests for the pure derivation**

```python
from intelligence.services.episode_contract_inputs import derive_episode_contract_inputs
from intelligence.services.turn_control_core import TurnControlCore


def _control(question: str):
    return TurnControlCore().control(
        question,
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )


def test_valuation_inputs_expand_outputs_and_require_two_data_domains():
    control = _control("瑞华泰的合理估值")
    result = derive_episode_contract_inputs(
        control.task_frame,
        capabilities=("market_data", "financial_data", "evidence_search"),
    )
    assert result.required_output_ids == (
        "valuation_assessment",
        "scenario_range",
        "evidence_boundary",
        "financial_business_anchor",
        "invalidation_conditions",
    )
    assert result.evidence_plan.profile == "valuation_current_anchor"
    assert {item.capability for item in result.evidence_plan.requirements} >= {
        "market_data",
        "financial_data",
    }


def test_market_cause_inputs_are_time_aligned_without_building_context():
    control = _control("这一周行情下跌的主要原因是什么")
    result = derive_episode_contract_inputs(control.task_frame, capabilities=None)
    assert result.evidence_plan.profile == "time_aligned_market_causal"
    assert result.required_output_ids == control.task_frame.required_outputs
```

- [ ] **Step 2: Run tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_contract_inputs.py
```

Expected: collection fails because the module does not exist.

- [ ] **Step 3: Move the existing derivation behind one immutable interface**

Create:

```python
from __future__ import annotations

from dataclasses import dataclass

from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.task_frame import TaskFrame


@dataclass(frozen=True)
class EpisodeContractInputs:
    required_output_ids: tuple[str, ...]
    evidence_plan: EvidencePlan
    capabilities: tuple[str, ...]


def derive_episode_contract_inputs(
    frame: TaskFrame,
    *,
    capabilities: tuple[str, ...] | None,
) -> EpisodeContractInputs:
    authorized = _authorized_capabilities(frame, capabilities)
    return EpisodeContractInputs(
        required_output_ids=_required_output_ids(frame),
        evidence_plan=_episode_evidence_plan(frame),
        capabilities=authorized,
    )
```

Move `_authorized_capabilities`, `_episode_evidence_plan`,
`_required_output_ids`, `_VALUATION_REQUIRED_OUTPUTS`,
`_MODEL_OWNED_READ_CAPABILITIES`, and the market-cause/valuation evidence-plan
rules from `episode_factory.py` into this module without changing their current
logic. Export only `EpisodeContractInputs` and
`derive_episode_contract_inputs`.

- [ ] **Step 4: Make `build_episode_context` consume the pure result**

Add an optional `contract_inputs` argument. When absent, derive once; when
present, verify the capability tuple and use it directly. Remove its private
second derivation.

- [ ] **Step 5: Run existing and new tests, then commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_contract_inputs.py \
  intelligence/tests/test_episode_factory.py \
  intelligence/tests/test_episode_tools.py -k 'valuation or market_cause'
git add intelligence/services/episode_contract_inputs.py \
  intelligence/services/episode_factory.py \
  intelligence/tests/test_episode_contract_inputs.py \
  intelligence/tests/test_episode_factory.py
git commit -m "refactor: expose pure episode contract inputs"
```

### Task 2: Define the Release Admission and Sealed Profile

**Files:**
- Create: `intelligence/services/release_execution.py`
- Create: `intelligence/tests/test_release_execution.py`
- Modify: `intelligence/services/research_contract.py`
- Modify: `intelligence/tests/test_episode_factory.py`

- [ ] **Step 1: Write failing admission/profile tests**

```python
from dataclasses import replace

from intelligence.services.episode_contract_inputs import EpisodeContractInputs
from intelligence.services.evidence_capabilities import EvidencePlan, EvidenceRequirement
from intelligence.services.release_execution import (
    RUNTIME_BEHAVIOR_PATHS,
    ReleaseBudget,
    admit_release_latency,
    build_runtime_behavior_fingerprint,
    release_budget,
)
from intelligence.services.turn_control_core import TurnControlCore


def _two_domain_plan() -> EvidencePlan:
    return EvidencePlan(
        profile="test_multi_domain",
        requirements=(
            EvidenceRequirement("A", "market_data", True, "current", "市场"),
            EvidenceRequirement("B", "news_search", True, "current", "新闻"),
        ),
        freshness="current",
    )


def _release_control():
    return TurnControlCore().control(
        "目前市场怎么看",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )


def _seed_behavior_tree(root):
    for relative in RUNTIME_BEHAVIOR_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stable", encoding="utf-8")
    (root / "docs").mkdir()


def test_standard_and_deep_profiles_match_the_approved_budget_table():
    assert release_budget("standard") == ReleaseBudget("standard", 90.0, 8, 40.0, 130.0)
    assert release_budget("deep") == ReleaseBudget("deep", 240.0, 24, 40.0, 280.0)


def test_explicit_quick_locks_standard_but_complex_auto_promotes():
    control = _release_control()
    inputs = EpisodeContractInputs(
        required_output_ids=("direct_assessment",),
        evidence_plan=_two_domain_plan(),
        capabilities=("market_data", "news_search"),
    )
    assert admit_release_latency(control.task_frame, control, inputs, explicit_tier="quick").tier == "standard"
    complex_inputs = replace(
        inputs,
        required_output_ids=("a", "b", "c", "d", "e"),
        evidence_plan=_two_domain_plan(),
    )
    assert admit_release_latency(control.task_frame, control, complex_inputs).tier == "deep"


def test_profile_id_ignores_docs_but_changes_with_behavior_file(tmp_path):
    _seed_behavior_tree(tmp_path)
    first = build_runtime_behavior_fingerprint(tmp_path)
    (tmp_path / "docs" / "note.md").write_text("changed", encoding="utf-8")
    assert build_runtime_behavior_fingerprint(tmp_path) == first
    (tmp_path / "intelligence/services/continuous_turn_adapter.py").write_text("changed", encoding="utf-8")
    assert build_runtime_behavior_fingerprint(tmp_path) != first
```

- [ ] **Step 2: Run tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_release_execution.py
```

Expected: FAIL because the release module does not exist.

- [ ] **Step 3: Implement immutable budgets, admission, and profile identity**

```python
@dataclass(frozen=True)
class ReleaseBudget:
    tier: Literal["standard", "deep"]
    research_seconds: float
    tool_cap: int
    semantic_seconds: float
    total_seconds: float


@dataclass(frozen=True)
class ReleaseLatencyAdmission:
    budget: ReleaseBudget
    reasons: tuple[str, ...]

    @property
    def tier(self) -> str:
        return self.budget.tier


_BUDGETS = {
    "standard": ReleaseBudget("standard", 90.0, 8, 40.0, 130.0),
    "deep": ReleaseBudget("deep", 240.0, 24, 40.0, 280.0),
}


def release_budget(tier: str) -> ReleaseBudget:
    normalized = str(tier).strip().lower()
    if normalized not in _BUDGETS:
        raise ValueError(f"unsupported release tier: {tier}")
    return _BUDGETS[normalized]


def admit_release_latency(frame, control, inputs, *, explicit_tier=None):
    if explicit_tier not in {None, "quick", "standard", "deep"}:
        raise ValueError(f"unsupported explicit release tier: {explicit_tier}")
    if explicit_tier in {"quick", "standard"}:
        return ReleaseLatencyAdmission(_BUDGETS["standard"], ("explicit_standard",))
    if explicit_tier == "deep":
        return ReleaseLatencyAdmission(_BUDGETS["deep"], ("explicit_deep",))
    domains = {item.capability for item in inputs.evidence_plan.requirements}
    reasons = []
    if len(inputs.required_output_ids) >= 5 and len(domains) >= 2:
        reasons.append("multi_output_multi_domain")
    if _independent_entity_count(frame) >= 2:
        reasons.append("multi_entity")
    if _approved_multi_branch_signal(frame, control):
        reasons.append("mode_governor_multi_branch")
    tier = "deep" if reasons else "standard"
    return ReleaseLatencyAdmission(_BUDGETS[tier], tuple(reasons or ("default_standard",)))
```

`_independent_entity_count` counts unique canonical A-share codes and distinct
comparison/tracking subjects; `_approved_multi_branch_signal` consumes existing
code-owned question type/control signals only. It must not match benchmark text
or case IDs.

Implement `ReleaseExecutionProfile` with canonical JSON hashing over backend,
provider, model, runtime behavior fingerprint, both budgets, verifier identity,
and evidence/cutoff contract versions. Hash only the explicit deployable source
manifest plus `intelligence/api/requirements.txt`; exclude docs, tests, logs,
credentials, user data, and Git commit metadata.

Use this explicit behavior manifest so a docs-only commit cannot reset the
campaign and a runtime-bearing change cannot escape it:

```python
RUNTIME_BEHAVIOR_PATHS = (
    "intelligence/api/app.py",
    "intelligence/api/requirements.txt",
    "intelligence/api/structured_reports.py",
    "intelligence/services/continuous_turn_adapter.py",
    "intelligence/services/conversation_orchestrator.py",
    "intelligence/services/episode_contract_inputs.py",
    "intelligence/services/episode_factory.py",
    "intelligence/services/episode_semantic_verifier.py",
    "intelligence/services/episode_tools.py",
    "intelligence/services/finance_query.py",
    "intelligence/services/openai_agents_runtime.py",
    "intelligence/services/release_execution.py",
    "intelligence/services/research_contract.py",
    "intelligence/services/self_use_maturity.py",
    "intelligence/services/valuation_estimate.py",
)


def build_runtime_behavior_fingerprint(repo_root: Path) -> str:
    digest = hashlib.sha256()
    for relative in RUNTIME_BEHAVIOR_PATHS:
        path = repo_root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
```

- [ ] **Step 4: Raise only standard/deep research tool caps**

Change `ResearchPolicy.for_tier` to quick `3/30`, standard `8/90`, and deep
`24/240`. Preserve synthesis values because `sdk_gpt` explicitly injects
`0.0`; do not add a third reserve.

- [ ] **Step 5: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_release_execution.py \
  intelligence/tests/test_episode_factory.py \
  intelligence/tests/test_agent_episode.py
git add intelligence/services/release_execution.py \
  intelligence/services/research_contract.py \
  intelligence/tests/test_release_execution.py \
  intelligence/tests/test_episode_factory.py
git commit -m "feat: define sealed release execution profile"
```

### Task 3: Thread One Admission Through Adapter and Supervisor Limits

**Files:**
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/services/continuous_turn_adapter.py`
- Modify: `intelligence/tests/test_workbench_api.py`
- Modify: `intelligence/tests/test_workbench_conversation_integration.py`
- Modify: `intelligence/tests/test_continuous_turn_adapter.py`

- [ ] **Step 1: Write failing deadline/tier tests**

Add tests proving:

```python
def _prepared_turn(frame, control):
    return SimpleNamespace(
        task_frame=frame,
        control=control,
        contract_inputs=derive_episode_contract_inputs(
            frame,
            capabilities=control.capabilities,
        ),
    )


def _admission(prepared):
    return admit_release_latency(
        prepared.task_frame,
        prepared.control,
        prepared.contract_inputs,
    )


def test_deep_admission_exists_before_supervisor_deadline(monkeypatch):
    order = []
    frame = _frame(
        question_type="market_cause",
        required_outputs=("a", "b", "c", "d", "e"),
    )
    control = _control(frame, capabilities=("market_data", "news_search"))
    prepared = _prepared_turn(frame, control)
    admission = _admission(prepared)
    assert admission.tier == "deep"
    supervisor = app_module.RunSupervisor()
    monkeypatch.setattr(
        supervisor,
        "_submit",
        lambda *_args, **kwargs: order.append(("deadline", kwargs["timeout_sec"])),
    )
    supervisor.submit_conversation(
        SimpleNamespace(user_id="tester"),
        "run-1",
        repo_root=Path("."),
        conversation_store=SimpleNamespace(),
        conversation_id="conversation-1",
        assistant_message_id="message-1",
        query=frame.raw_question,
        skill_mode="auto",
        selected_skill_ids=[],
        perspective_mode="neutral",
        selected_perspective_ids=[],
        prepared_turn=prepared,
        admission=admission,
        llm_providers=(),
    )
    assert order == [("deadline", 280.0)]


def test_adapter_receives_the_same_pre_admitted_tier_and_total(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        app_module,
        "_build_continuous_turn_adapter",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(),
    )
    frame = _frame(question_type="market_cause", required_outputs=("a", "b", "c", "d", "e"))
    prepared = _prepared_turn(frame, _control(frame, capabilities=("market_data", "news_search")))
    admission = _admission(prepared)
    app_module._build_admitted_continuous_turn_adapter(
        prepared_turn=prepared,
        admission=admission,
        providers=(),
        run_id="run-1",
        assistant_message_id="message-1",
        deadline_expires_at=1_280.0,
    )
    assert captured["tier"] == "deep"
    assert captured["timeout"] == 280.0
    assert captured["deadline_expires_at"] == 1_280.0
    assert captured["contract_inputs"] == prepared.contract_inputs


def test_changing_only_adapter_timeout_cannot_escape_shorter_cancellation_deadline(monkeypatch):
    now = 2_000.0
    monkeypatch.setattr(continuous_turn_adapter.time, "monotonic", lambda: now)
    adapter = ContinuousTurnAdapter(
        runtime=object(),
        semantic_verifier=SimpleNamespace(verify=lambda **_kwargs: None),
        mode="on",
        timeout=280.0,
        deadline_expires_at=now + 130.0,
        tier="deep",
    )
    assert adapter._remaining_timeout() == 130.0
```

Use the existing `_frame` and `_control` helpers and import `Path`,
`SimpleNamespace`, plus `ContinuousTurnAdapter`; add
`_build_admitted_continuous_turn_adapter` with the exact interface exercised
above.

- [ ] **Step 2: Run tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_api.py -k 'deadline or admission'
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_conversation_integration.py -k continuous
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_continuous_turn_adapter.py -k tier
```

Expected: FAIL because turn preparation/admission do not exist before
`RunSupervisor` creates its fixed deadline.

- [ ] **Step 3: Extract and freeze turn preparation before submission**

Extract the current conversation-context, inherited-intent, controller,
`TaskFrame`, `TurnIntent`, and `TurnControlResult` block into
`TurnOrchestrator.prepare_turn(...) -> PreparedContinuousTurn`. The prepared
value includes the frozen frame/control plus `EpisodeContractInputs`.
`run_turn(..., prepared_turn=...)` consumes that value and must not call the
controller or derive contract inputs again. Preserve the existing injected
controller test seam.

```python
@dataclass(frozen=True)
class PreparedContinuousTurn:
    decision: TurnDecision
    task_frame: TaskFrame
    turn_intent: TurnIntent
    control: TurnControlResult
    conversation_context: str
    contract_inputs: EpisodeContractInputs

    def __post_init__(self) -> None:
        if self.control.task_frame.task_frame_hash != self.task_frame.task_frame_hash:
            raise ValueError("prepared turn frame/control mismatch")
```

- [ ] **Step 4: Admit before creating the supervisor deadline**

The conversation endpoint prepares the turn under the same explicit provider
override, derives admission, and only then calls
`RunSupervisor.submit_conversation`. If preparation fails, persist a stable
preflight failure without creating a research deadline. This makes the
130/280-second table apply to the continuous execution rather than silently
losing controller time.

- [ ] **Step 5: Make the supervisor accept the selected per-run total**

Add required `admission` and `prepared_turn` arguments to conversation submit.
`RunSupervisor._submit` accepts `timeout_sec`; it creates its timer and
`CancellationSignal.deadline_expires_at` from that exact selected total, capped
at 280. Non-conversation callers retain their existing timeout behavior.

- [ ] **Step 6: Build the adapter from the same frozen values**

The worker passes prepared turn, admitted tier, selected total `timeout`, exact
supervisor `deadline_expires_at`, and the already derived `contract_inputs` to
the adapter. The adapter computes the unchanged
`verification_reserve=min(40, root_timeout/3)`; standard receives 90 research
seconds and deep receives 240. A mismatch between prepared inputs and frame hash
fails closed.

- [ ] **Step 7: Run focused tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_workbench_conversation_integration.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_episode_factory.py
git add intelligence/services/conversation_orchestrator.py intelligence/api/app.py \
  intelligence/services/continuous_turn_adapter.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_workbench_conversation_integration.py \
  intelligence/tests/test_continuous_turn_adapter.py
git commit -m "feat: apply contract-derived runtime deadlines"
```

### Task 4: Bound and Seal the Entire Semantic Chain

**Files:**
- Modify: `intelligence/services/continuous_turn_adapter.py`
- Modify: `intelligence/services/episode_semantic_verifier.py`
- Modify: `intelligence/tests/test_continuous_turn_adapter.py`
- Modify: `intelligence/tests/test_episode_semantic_verifier.py`

- [ ] **Step 1: Write failing aggregate-deadline tests**

Use a fake verifier that records deadline object identity and advances a fake
clock across initial judge, transport retry, deletion rejudge, and semantic
re-entry. Assert every invocation receives the same child and no invocation
starts after its absolute expiry.

```python
assert len({id(deadline) for deadline in verifier.deadlines}) == 1
assert verifier.deadlines[0].expires_at == pytest.approx(first_semantic_at + 40.0)
assert all(call_started <= verifier.deadlines[0].expires_at for call_started in verifier.call_times)
```

Also assert research finishing at 30 seconds still yields at most a 40-second
semantic child, not the root remainder.

- [ ] **Step 2: Run tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_continuous_turn_adapter.py -k semantic_deadline
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_semantic_verifier.py -k 'attempt or rejudge'
```

Expected: FAIL because the root deadline is currently passed directly and re-entry has no shared child.

- [ ] **Step 3: Create and reuse one semantic child**

Create `semantic_deadline = root_deadline.bounded_stage(verification_reserve)`
immediately before the first semantic call. Pass it to every verifier call and
to semantic-triggered repair delivery. Change every semantic-loop expiry check
from the root to this child. Never recreate it on re-entry.

- [ ] **Step 4: Seal judge provider selection**

Add an explicit `judge_provider` constructor argument. In release mode,
`SemanticEpisodeVerifier` uses only that provider/primary judge and never calls
ambient `llm_refine.judge_provider()`. Preserve ambient discovery only for
non-release legacy callers. Record correlated composer/judge identity.

- [ ] **Step 5: Preserve the two distinct retry contracts**

Keep up to three typed transient transport attempts inside one `_run_judge`
round and up to three deterministic deletion/rejudge rounds outside it. Both
consume the same child. Initial unavailable/malformed remains partial;
monotonic release remains limited to a fully reviewed draft plus exact deletion
and a typed release-safe optional-rejudge failure.

- [ ] **Step 6: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_episode_semantic_verifier.py
git add intelligence/services/continuous_turn_adapter.py \
  intelligence/services/episode_semantic_verifier.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_episode_semantic_verifier.py
git commit -m "fix: bound the complete semantic verification chain"
```

### Task 5: Normalize Typed Finance Filters Without Relaxing Validation

**Files:**
- Modify: `intelligence/services/finance_query.py`
- Modify: `intelligence/services/episode_tools.py`
- Modify: `intelligence/tests/test_finance_query.py`
- Modify: `intelligence/tests/test_episode_tools.py`

- [ ] **Step 1: Write failing scalar-`in` and stock-code tests**

```python
def _stock_arguments(value):
    return {
        "dataset": "stock_daily",
        "metrics": ["close"],
        "dimensions": ["stock_code"],
        "filters": [{"field": "stock_code", "op": "in", "value": value}],
    }


@pytest.mark.parametrize("value", ["688323", 688323])
def test_scalar_in_becomes_one_canonical_stock_code(value):
    spec = FinanceQuerySpec.from_arguments(_stock_arguments(value))
    assert spec.filters[0].value == ("688323.SH",)


@pytest.mark.parametrize("value", [None, {}, [], [["688323"]]])
def test_invalid_in_values_remain_rejected(value):
    with pytest.raises(FinanceQueryValidationError):
        FinanceQuerySpec.from_arguments(_stock_arguments(value))


def test_directional_exchange_mapping_covers_sh_sz_bj():
    assert canonical_a_share_code("688323") == "688323.SH"
    assert canonical_a_share_code("300750") == "300750.SZ"
    assert canonical_a_share_code("830879") == "830879.BJ"


def test_matching_entity_anchor_wins_over_ambiguous_bare_code():
    spec = FinanceQuerySpec.from_arguments(
        _stock_arguments("000001"),
        stock_code_anchor="000001.SH",
    )
    assert spec.filters[0].value == ("000001.SH",)
```

- [ ] **Step 2: Run tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_finance_query.py -k 'scalar or canonical or invalid_in'
```

Expected: scalar `in` raises `in filter requires an array` or remains uncanonicalized.

- [ ] **Step 3: Normalize once before validation and fingerprinting**

Add optional `stock_code_anchor` to `FinanceQuerySpec.from_arguments`. In
`_parse_filters`, for `op == 'in'`, turn a scalar string/number into a
one-item tuple, preserve flat non-empty arrays, and reject null/object/nested/
empty values. Canonicalize only `stock_code` values matching exactly six digits
or an existing `.SH/.SZ/.BJ` suffix. Use Shanghai prefixes `6/9`, Beijing
prefixes `4/8`, and Shenzhen otherwise. Do not guess names or arbitrary text.
When the provided anchor has the same six-digit body, preserve its validated
suffix; never replace a different code with the anchor.

- [ ] **Step 4: Prove normalized fingerprints deduplicate the repaired action**

Assert scalar `688323` and array `["688323.SH"]` compile to the same bound
parameter and SQL fingerprint. Other operators retain scalar semantics.
Pass the already resolved `subject_anchor.ticker` from the episode finance-query
runner into `FinanceQuerySpec.from_arguments`; do not resolve the entity again.

- [ ] **Step 5: Run full finance-query tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_finance_query.py \
  intelligence/tests/test_episode_tools.py -k finance_query
git add intelligence/services/finance_query.py intelligence/services/episode_tools.py \
  intelligence/tests/test_finance_query.py intelligence/tests/test_episode_tools.py
git commit -m "fix: normalize typed finance query filters"
```

### Task 6: Separate Current Local Price from Valuation Ratios

**Files:**
- Modify: `intelligence/services/valuation_estimate.py`
- Modify: `intelligence/services/ask_blocks.py`
- Modify: `intelligence/services/episode_tools.py`
- Modify: `intelligence/tests/test_valuation_estimate.py`
- Modify: `intelligence/tests/test_episode_tools.py`
- Modify: `intelligence/tests/test_ask_compose.py`

- [ ] **Step 1: Write failing evidence-separation tests**

```python
def _valuation_db(tmp_path):
    path = tmp_path / "valuation.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create table fact_stock_daily(trade_date date, stock_ts_code text, stock_name text, close double, pre_close double, pct_chg double, amount double)")
    con.execute("create table fact_sector_stock_daily(trade_date date, sector_ts_code text, sector_name text, stock_ts_code text, stock_name text, amount double, total_mcap_yi double)")
    con.execute("insert into fact_stock_daily values ('2026-07-28','688323.SH','瑞华泰',27.50,27.00,1.85,350000000)")
    con.execute("insert into fact_sector_stock_daily values ('2026-07-28','S1','新材料','688323.SH','瑞华泰',350000000,null)")
    con.close()
    return path


def test_fresh_local_price_survives_missing_valuation_ratios(tmp_path):
    market_db = _valuation_db(tmp_path)
    block = _valuation_block_for_llm(
        "瑞华泰 688323",
        "瑞华泰",
        market_db,
        fetcher=lambda *_args, **_kwargs: None,
        as_of="2026-07-28",
    )
    assert "当前价格锚：688323.SH" in block
    assert "收盘" in block and "2026-07-28" in block
    assert "PE(TTM) 缺" in block
    assert "PB 缺" in block
    assert "总市值 缺" in block


def test_stale_ratio_snapshot_cannot_borrow_fresh_price_date():
    combined = combine_price_and_valuation(
        price=LocalPriceAnchor("688323.SH", 27.50, "2026-07-28"),
        valuation=ValuationSnapshot("688323.SH", "瑞华泰", pb=4.3, source_date="2026-07-24"),
        freshness_floor="2026-07-28",
    )
    assert combined.current_price == 27.50
    assert combined.pb is None
```

- [ ] **Step 2: Run tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_valuation_estimate.py \
  intelligence/tests/test_episode_tools.py -k valuation
```

Expected: local price disappears when the external valuation snapshot is absent.

- [ ] **Step 3: Add separate evidence types and merge logic**

Add `LocalPriceAnchor(ts_code, name, close, pre_close, return_pct, amount,
source_date, source)` and keep `ValuationSnapshot.source_date` exclusively for
market cap/PE/PB. Query the latest cutoff-safe `fact_stock_daily` row for the
canonical entity code. Merge only fields whose own dates satisfy cutoff and
freshness; never copy the price date onto ratios.

- [ ] **Step 4: Render honest separate blocks**

The valuation block always renders the local price anchor when available, then
renders each ratio or an explicit gap. Scenario range remains ineligible when
the required ratio/capital inputs are absent. Update episode evidence titles so
the price and ratio dates remain independently traceable.

- [ ] **Step 5: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_valuation_estimate.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_ask_compose.py -k valuation
git add intelligence/services/valuation_estimate.py intelligence/services/ask_blocks.py \
  intelligence/services/episode_tools.py intelligence/tests/test_valuation_estimate.py \
  intelligence/tests/test_episode_tools.py intelligence/tests/test_ask_compose.py
git commit -m "feat: separate price and valuation evidence"
```

### Task 7: Propagate the Release Profile Through Report and SSE Truth

**Files:**
- Modify: `intelligence/services/continuous_turn_adapter.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/api/structured_reports.py`
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/tests/test_workbench_api.py`
- Modify: `intelligence/tests/test_workbench_conversation_integration.py`

- [ ] **Step 1: Write failing profile-propagation tests**

Assert the same non-secret `profile_id`, backend, provider, model, admitted tier,
and behavior fingerprint appear in the private episode artifact, final
`report.json`, and `report.complete` SSE payload. Assert no endpoint, key,
credential hash, raw prompt, or provider response appears publicly.

- [ ] **Step 2: Run tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_api.py -k profile
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_conversation_integration.py -k profile
```

Expected: report schema contains only provider/model and no release profile.

- [ ] **Step 3: Add profile identity to the runtime result and report**

Extend `ContinuousTurnResult` with `release_profile_id`, `runtime_backend`, and
`research_tier`. Pass the immutable profile into adapter construction. Extend
`complete_report` with a `runtime_profile` mapping restricted to non-secret
fields and ensure `_redact_object` is applied before storage and SSE emission.

- [ ] **Step 4: Preserve transport/answer distinction**

Keep RunStore terminal completion separate from `report.answer_status`. Only a
verified runtime result writes answer status `complete`; degraded/partial stays
partial even when transport completed normally.

- [ ] **Step 5: Run tests, leak scans, and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_workbench_conversation_integration.py \
  intelligence/tests/test_continuous_turn_adapter.py
git add intelligence/services/continuous_turn_adapter.py \
  intelligence/services/conversation_orchestrator.py intelligence/api/structured_reports.py \
  intelligence/api/app.py intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_workbench_conversation_integration.py
git commit -m "feat: propagate sealed runtime profile"
```

### Task 8: Version and Bind the Self-Use Ledger to the Active Profile

**Files:**
- Modify: `intelligence/services/self_use_maturity.py`
- Modify: `intelligence/cli.py`
- Modify: `scripts/smoke_workbench_self_use.py`
- Modify: `intelligence/tests/test_self_use_maturity.py`
- Modify: `intelligence/tests/test_self_use_cli.py`
- Modify: `intelligence/tests/test_smoke_workbench_self_use.py`

- [ ] **Step 1: Write failing version-2 and policy tests**

```python
def _policy():
    return SelfUseReleasePolicy(
        profile_id="profile-gpt",
        backend="sdk_gpt",
        provider="openai",
        model="gpt-5.6-sol",
    )


def _v2_event(*, run_id, useful, trade_date=None):
    return SelfUseEvent(
        trade_date=trade_date or TRADING_DAYS[0],
        workflow="daily_market",
        outcome="success",
        manual_rescue=False,
        severe_fact_error=False,
        useful=useful,
        run_id=run_id,
        release_profile_id="profile-gpt",
        schema_version=2,
    )


def test_v1_event_is_readable_but_not_eligible_for_profile():
    old = SelfUseEvent.from_dict({
        "trade_date": TRADING_DAYS[0],
        "workflow": "daily_market",
        "outcome": "success",
        "manual_rescue": False,
        "severe_fact_error": False,
        "useful": True,
        "run_id": "legacy-run",
        "recorded_at": "2026-07-20T20:00:00+08:00",
        "schema_version": 1,
    })
    policy = _policy()
    result = evaluate_maturity([old], trading_days=TRADING_DAYS, release_policy=policy)
    assert "minimum_trade_dates" in result.blockers
    assert result.metrics["ineligible_profile_events"] == 1


def test_same_run_is_idempotent_but_two_runs_same_day_both_affect_rates():
    policy = _policy()
    first = _v2_event(run_id="run-a", useful=True)
    duplicate = replace(first, useful=False)
    second = _v2_event(run_id="run-b", useful=False)
    result = evaluate_maturity([first, duplicate, second], trading_days=TRADING_DAYS, release_policy=policy)
    assert result.metrics["event_count"] == 2
    assert result.metrics["distinct_trade_dates"] == 1
    assert result.metrics["useful_rate"] == 0.5
```

Also test rejection of GLM, wrong backend/model/profile, partial answer status,
missing SSE profile evidence, no run ID, and report/event trade-date mismatch.

- [ ] **Step 2: Run tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_self_use_maturity.py \
  intelligence/tests/test_self_use_cli.py
```

Expected: schema version 2 and release-profile policy do not exist.

- [ ] **Step 3: Implement version-2 events and policy binding**

Add `SelfUseReleasePolicy(profile_id, backend, provider, model)`,
`release_profile_id`, `SelfUseEvent.from_dict`, and schema version 2. Load version-1 rows into an
auditable legacy representation but exclude them from an active campaign.
Replace permanent provider constants with `SelfUseReleasePolicy` projected from
`ReleaseExecutionProfile`. Verify report and SSE `profile_id/backend/provider/
model`, `llm.used`, completed answer truth, exact `as_of == trade_date`, and no
template/severe-integrity degrade before append.

- [ ] **Step 4: Preserve deterministic event/day semantics**

Keep first event for an identical `(run_id, trade_date, workflow)`. Retain
different run IDs on the same trading day and include all in event-level rates;
count the date once. Require ten consecutive canonical trading dates, all five
workflows, >=95% success, >=80% useful, <=5% manual rescue, zero severe fact
errors, then explicit approval bound to profile-aware fingerprint.

- [ ] **Step 5: Wire CLI and smoke without fabricating campaign events**

CLI record/status/approve loads the active sealed profile. Smoke uses a
temporary ledger and never writes the real user's campaign file. Public
bootstrap exposes aggregate counts only.

- [ ] **Step 6: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_self_use_maturity.py \
  intelligence/tests/test_self_use_cli.py \
  intelligence/tests/test_smoke_workbench_self_use.py \
  intelligence/tests/test_workbench_api.py -k self_use
git add intelligence/services/self_use_maturity.py intelligence/cli.py \
  scripts/smoke_workbench_self_use.py intelligence/tests/test_self_use_maturity.py \
  intelligence/tests/test_self_use_cli.py intelligence/tests/test_smoke_workbench_self_use.py
git commit -m "feat: bind self-use to release profile"
```

### Task 9: Run Combined Deterministic Gates and Freeze One Candidate

**Files:**
- Create: `docs/verification/product-runtime-self-use-root-repair-result-2026-07-29.md`

- [ ] **Step 1: Run the complete focused regression**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_contract_inputs.py \
  intelligence/tests/test_release_execution.py \
  intelligence/tests/test_episode_factory.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_finance_query.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_valuation_estimate.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_workbench_conversation_integration.py \
  intelligence/tests/test_self_use_maturity.py \
  intelligence/tests/test_self_use_cli.py \
  intelligence/tests/test_smoke_workbench_self_use.py
```

Expected: PASS; no skipped release-critical assertion.

- [ ] **Step 2: Run style, diff, secret, and public-control scans**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  intelligence/services/episode_contract_inputs.py \
  intelligence/services/release_execution.py \
  intelligence/services/episode_factory.py \
  intelligence/services/continuous_turn_adapter.py \
  intelligence/services/episode_semantic_verifier.py \
  intelligence/services/finance_query.py \
  intelligence/services/valuation_estimate.py \
  intelligence/services/self_use_maturity.py \
  intelligence/api/app.py intelligence/api/structured_reports.py
git diff --check
```

Run the exact leak-regression tests:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_continuous_turn_adapter.py \
  -k 'public_projection or secret or private_artifact_records_runtime_backend'
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_api.py \
  -k 'secret or health_reports_selected_sdk'
```

Expected: all selected tests pass and no sentinel reaches a public projection.

- [ ] **Step 3: Freeze the clean behavior/profile receipt**

Require a clean worktree. Record commit, behavior fingerprint, profile ID,
backend `sdk_gpt`, provider/model `openai/gpt-5.6-sol`, standard/deep budgets,
semantic judge identity, data exact-gate receipt, and True Hybrid readiness.

- [ ] **Step 4: Commit the deterministic result ledger**

```bash
git add docs/verification/product-runtime-self-use-root-repair-result-2026-07-29.md
git commit -m "docs: verify product runtime root repair"
```

### Task 10: Execute One Pre-Registered Five-Workflow Product Canary

**Files:**
- Read only: `/Users/a77/.finance-runtime/evals/candidate-ca190b07-gpt-five-workflow-preregistration-2026-07-29.json`
- Create outside Git: one new immutable canary artifact directory under `/Users/a77/.finance-runtime/evals/`.
- Modify after run: `docs/verification/product-runtime-self-use-root-repair-result-2026-07-29.md`

- [ ] **Step 1: Verify prerequisites without starting a workflow**

Require: clean frozen revision; profile ID matches the receipt; exact data gate
and three-night streak green; production data and True Hybrid roots ready;
Keychain `openai/gpt-5.6-sol` loads without exposing a key; 8792 unchanged.

- [ ] **Step 2: Copy the five frozen prompts to a new preregistration receipt**

Keep prompt text and workflow mapping unchanged. Record new candidate revision,
profile ID, data snapshot ID, roots, provider/model/backend, and five unique
output paths before starting 8799. Pin SHA-256.

- [ ] **Step 3: Start temporary 8799 and execute each workflow exactly once**

Use isolated users, production data roots, True Hybrid RAG, saved Keychain
provider, and the frozen candidate. Do not tune or rerun a failed workflow on
the same revision. Stop 8799 after the fifth terminal result.

- [ ] **Step 4: Evaluate product truth, not transport truth**

Every case must have `report.status=completed`, `answer_status=complete`, the
sealed profile ID, expected admitted tier, current cutoff, citations/evidence,
zero secret/control leaks, and a user-facing answer rather than a gap fallback.
Record tool calls, evidence count, semantic elapsed time, total latency, and
degradation reasons.

- [ ] **Step 5: Make the release decision once**

If all five pass, mark `five_workflow_gate=true`. If any fail, record the shared
root blocker and freeze the canary line; do not begin another per-question
debugging loop.

- [ ] **Step 6: Commit only the result-ledger update**

```bash
git add docs/verification/product-runtime-self-use-root-repair-result-2026-07-29.md
git commit -m "docs: record five-workflow release canary"
```

### Task 11: Prepare but Do Not Execute the 8792 Cutover

**Files:**
- Create: `docs/verification/8792-cutover-candidate-2026-07-29.md`

- [ ] **Step 1: Record atomic cutover and rollback identities**

Include current 8792 PID/revision/profile, candidate revision/profile, config
diff, readiness command, smoke command, rollback command, expected user/data
roots, and proof that no DB/index/key is part of the code change.

- [ ] **Step 2: Verify the cutover receipt against the frozen candidate**

Recompute behavior fingerprint/profile ID and require equality with the canary.
Any candidate code/config change invalidates the receipt and five-workflow gate.

- [ ] **Step 3: Commit the receipt without switching 8792**

```bash
git add docs/verification/8792-cutover-candidate-2026-07-29.md
git commit -m "docs: prepare atomic 8792 cutover"
```

Stop here until explicit user approval to switch canonical 8792. Approval of
this implementation plan is not cutover approval.

### Task 12: Run the Real Ten-Trading-Day Self-Use Campaign After Cutover

**Files:**
- Private append-only ledger: `intelligence/users/<user>/self-use/events.jsonl`.
- Private approval record: `intelligence/users/<user>/self-use/approval.json`.
- Modify summary only: `docs/verification/product-runtime-self-use-root-repair-result-2026-07-29.md`.

- [ ] **Step 1: Start the campaign only after the approved atomic cutover**

Record the active profile ID and first canonical trading date. Do not backfill
canaries, benchmarks, historical runs, or pre-cutover events.

- [ ] **Step 2: Use all five workflows over at least ten consecutive trading dates**

Every counting event binds a real RunStore run, completed report/answer, matching
SSE/profile, exact `as_of`, and explicit usefulness/manual-rescue/fact-error
fields. Same-run duplicates stay idempotent; different real runs remain.

- [ ] **Step 3: Evaluate after every real event without auto-approving**

The status command must show distinct dates, covered workflows, success rate,
usefulness rate, manual-rescue rate, severe fact errors, blockers, and active
profile ID. Any profile change starts a new campaign; old events remain audit
history.

- [ ] **Step 4: Request the user's final product judgment only after mechanical green**

Mechanical green requires ten consecutive trading dates, 5/5 workflows,
>=95% success, >=80% useful, <=5% manual rescue, zero severe fact errors, and
no profile mismatch. The user's approval is a final veto gate and cannot
override a blocker.

- [ ] **Step 5: Commit only an aggregate completion statement after approval**

Do not commit private events, notes, run IDs, or approval payload. The public
result ledger may record aggregate metrics, active profile ID, approval state,
and completion date.

## Completion Gate

This plan is complete only when:

1. standard/deep admission is derived from frozen task structure;
2. tier, adapter timeout, and supervisor deadline cannot diverge;
3. the full semantic chain shares one 40-second child;
4. the judge identity is sealed and observable;
5. scalar `in` and SH/SZ/BJ codes normalize safely while invalid inputs remain rejected;
6. current price and valuation ratios retain separate dates and gaps;
7. the five frozen product workflows pass exactly once on one clean candidate;
8. 8792 changes only after separate explicit approval and has a tested rollback;
9. the active profile accumulates ten consecutive real trading dates and all five workflows;
10. mechanical maturity and explicit user approval both pass;
11. no key, DuckDB, index, log, model, cache, user event ledger, or virtual environment enters Git.

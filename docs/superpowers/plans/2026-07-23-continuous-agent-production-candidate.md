# Continuous Agent Production Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the verified GLM Continuous Agent Runtime sidecar into a semantically grounded, failure-tolerant candidate that runs through the real Workbench Conversation API on an isolated canary port.

**Architecture:** Keep the provider-neutral `AgentRuntime.run()` interface. Deepen its implementation behind `ToolBatchExecutor`, `EpisodeFinalizer`, and `SemanticEpisodeVerifier`, then connect one `ContinuousTurnAdapter` to the existing conversation persistence/SSE seam. Deterministic fast paths stay outside the model loop; legacy synthesis never rewrites an Episode-owned answer.

**Tech Stack:** Python 3.11 dataclasses/protocols, `contextvars`, bounded `ThreadPoolExecutor`, existing `ResearchToolRegistry`, `QueryLedger`, `ResearchDeadline`, `llm_refine` provider adapters and grounding judge, FastAPI Conversation API, pytest, real GLM 5.2 canary.

---

## File map

- Create `intelligence/services/episode_policy.py`: one source for tool scheduling priority and semantic-gate mode.
- Create `intelligence/services/episode_tool_batch.py`: validate, schedule, concurrently execute, and normalize one model tool-call batch.
- Modify `intelligence/services/agent_episode.py`: retain only the continuous loop; consume ordered batch results and delegate recovery.
- Modify `intelligence/services/agent_runtime.py`: expose the single public evidence projection used by all Episode modules.
- Create `intelligence/services/episode_finalizer.py`: one bounded compact-evidence recovery and targeted repair path.
- Modify `intelligence/services/glm_agent_runtime.py`: make provider-chain attempts explicit at the runtime seam and inject finalizer/verifier dependencies.
- Modify `intelligence/services/llm_settings.py`: return a single BYOK provider or a built-in provider tuple without leaking secrets.
- Create `intelligence/services/episode_semantic_verifier.py`: semantic claim/evidence judge, one repair, one rejudge, fail-closed public projection.
- Create `intelligence/services/continuous_turn_adapter.py`: compose TaskFrame, context, registry, runtime and verified public result without importing legacy answer owners.
- Modify `intelligence/services/conversation_orchestrator.py`: call the adapter immediately after the canonical TaskFrame/control decision and persist its result directly.
- Modify `intelligence/api/app.py`: pass provider tuples to the worker and expose runtime mode/provenance without changing public secrets.
- Modify `scripts/run_agent_episode_ab.py`: record structural/semantic status and pressure-run reliability.
- Add focused tests for every new seam plus Conversation API canary tests.
- Add `docs/verification/continuous-agent-production-candidate-2026-07-23.md`: final requirement-by-requirement evidence.

## Task 1: Schedule and execute a tool batch safely

**Files:**
- Create: `intelligence/services/episode_policy.py`
- Create: `intelligence/services/episode_tool_batch.py`
- Create: `intelligence/tests/test_episode_tool_batch.py`

- [ ] **Step 1: Write failing behavior tests at the batch interface**

Define a fixture registry with `web_search`, `kb_search`, and `market_data` runners. Tests must call only `ToolBatchExecutor.execute()` and assert observable results:

```python
def test_valuation_mandatory_market_call_starts_before_slow_search() -> None:
    started: list[str] = []
    release = threading.Event()

    def slow_web(query, ctx):
        started.append("web_search")
        release.wait(0.3)
        return [], "web", _trace("web_search")

    def market(query, ctx):
        started.append("market_data")
        release.set()
        return [_evidence("market_data", "current anchor")], "market", _trace("market_data")

    result = ToolBatchExecutor(max_workers=2).execute(
        (
            _call("1", "web_search", "瑞华泰 估值"),
            _call("2", "market_data", "瑞华泰 最新估值"),
        ),
        registry=_registry(web_search=slow_web, market_data=market),
        context=_valuation_context(max_steps=2),
        remaining_slots=2,
    )
    assert "market_data" in started[:2]
    assert [item.call.call_id for item in result.items] == ["1", "2"]
    assert result.executed_count == 2
```

Add independent tests named
`test_two_independent_read_only_tools_overlap_in_wall_clock_time`,
`test_each_worker_has_a_distinct_copied_context_with_one_shared_query_ledger`,
`test_duplicate_and_unauthorized_calls_never_reach_runners`,
`test_calls_beyond_budget_are_rejected_after_mandatory_priority_selection`, and
`test_exception_timeout_and_empty_result_keep_original_call_order`. The first
uses a two-party barrier and asserts both runners enter before either is
released. The context test stores `id(query_ledger.current_query_ledger())` and
`id(contextvars.copy_context())` from each runner: ledger IDs must match and
entered Context IDs must differ. The gate tests use runner counters fixed at
zero for rejected calls. The error-order test releases call 2 first and asserts
returned call IDs are still `("1", "2", "3")` with statuses
`("timeout", "error", "empty")`.

Use fixed events/barriers, not a fragile assertion on exact milliseconds, to
prove concurrency. Assert that the returned tuple remains in original model
order even when completion order is reversed.

- [ ] **Step 2: Run the new tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_tool_batch.py
```

Expected: import failure because `episode_tool_batch` does not exist.

- [ ] **Step 3: Add one centralized scheduling policy**

Implement in `episode_policy.py`:

```python
_QUESTION_TOOL_PRIORITY = {
    "valuation_estimate": (
        "market_data", "l3_lookup", "evidence_lookup",
        "kb_search", "graph_lookup", "news_search", "web_search",
    ),
}

def tool_priority(question_type: str, mandatory: tuple[str, ...]) -> tuple[str, ...]:
    ordered = [*mandatory, *_QUESTION_TOOL_PRIORITY.get(question_type, ())]
    return tuple(dict.fromkeys(item for item in ordered if item))
```

Do not add another question classifier. This function consumes the canonical
`ResearchTaskContract.question_type` and mandatory capability tuple.

- [ ] **Step 4: Implement the deep batch module**

Define immutable result types:

```python
@dataclass(frozen=True)
class ToolCallResult:
    call: ModelToolCall
    status: Literal["success", "empty", "rejected", "timeout", "error"]
    observation: ToolObservation | None = None
    error: str = ""

@dataclass(frozen=True)
class ToolBatchResult:
    items: tuple[ToolCallResult, ...]
    executed_count: int
    normalized_queries: tuple[tuple[str, str], ...]
```

`ToolBatchExecutor.execute()` must:

1. resolve authorized definitions and validate each call;
2. normalize/dedupe against an executor-owned episode set;
3. select up to `remaining_slots` by mandatory/question priority;
4. submit each selected call with a fresh `contextvars.copy_context()`;
5. use `wait(futures, timeout=context.deadline.stage_timeout(30.0))`;
6. cancel not-started futures and call `shutdown(wait=False, cancel_futures=True)`;
7. map results back to original indices.

The executor owns its episode-level `seen_queries`; callers do not maintain a
second set.

- [ ] **Step 5: Run focused tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_tool_batch.py intelligence/tests/test_query_ledger.py intelligence/tests/test_generic_research_owner.py
git add intelligence/services/episode_policy.py intelligence/services/episode_tool_batch.py intelligence/tests/test_episode_tool_batch.py
git commit -m "feat: execute episode tools concurrently"
```

Expected: all selected tests pass.

## Task 2: Replace inline serial execution and deepen the Episode loop

**Files:**
- Modify: `intelligence/services/agent_runtime.py`
- Modify: `intelligence/services/agent_episode.py`
- Modify: `intelligence/tests/test_agent_episode.py`

- [ ] **Step 1: Add a failing transcript-order integration test**

Use one scripted model turn with two calls whose runners complete in reverse
order. Assert the second model input is:

```python
tool_messages = second_messages[3:5]
assert [item["tool_call_id"] for item in tool_messages] == ["call-1", "call-2"]
assert json.loads(tool_messages[0]["content"])["tool"] == "web_search"
assert json.loads(tool_messages[1]["content"])["tool"] == "market_data"
```

Also assert tool/evidence events have contiguous sequence numbers and the same
TaskFrame hash.

- [ ] **Step 2: Run the focused test and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_agent_episode.py -k "batch or order"
```

Expected: the current serial loop cannot demonstrate reverse-completion with
ordered batch assembly.

- [ ] **Step 3: Export one public evidence projection**

Rename `agent_runtime._public_evidence` to `public_agent_evidence` and export it
through `__all__`. Preserve the exact JSON-safe field set. Replace the duplicate
static projection in `ContinuousAgentEpisode` with this function.

- [ ] **Step 4: Inject and consume `ToolBatchExecutor`**

Change the constructor to:

```python
def __init__(
    self,
    model: AgentModelClient,
    *,
    llm_timeout: float = DEFAULT_LLM_TIMEOUT,
    tool_executor: ToolBatchExecutor | None = None,
    finalizer: EpisodeFinalizer | None = None,
) -> None:
```

Replace the whole inline `for call in turn.tool_calls` runner block with one
batch call. Append each ordered result through a single helper that updates
messages, ledger, evidence, gaps, traces, and usage. Delete `seen_queries` from
the loop and delete duplicate `_public_evidence`.

- [ ] **Step 5: Run Episode and runtime regressions**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_agent_runtime.py \
  intelligence/tests/test_episode_tool_batch.py \
  intelligence/tests/test_episode_verifier.py
```

- [ ] **Step 6: Commit the replacement**

```bash
git add intelligence/services/agent_runtime.py intelligence/services/agent_episode.py intelligence/tests/test_agent_episode.py
git commit -m "refactor: deepen continuous episode tool seam"
```

## Task 3: Add one bounded compact finalization recovery

**Files:**
- Create: `intelligence/services/episode_finalizer.py`
- Create: `intelligence/tests/test_episode_finalizer.py`
- Modify: `intelligence/services/agent_episode.py`
- Modify: `intelligence/tests/test_agent_episode.py`

- [ ] **Step 1: Write failing finalizer tests**

Test the public recovery interface with a recording model:

```python
def test_recovery_contains_task_required_outputs_and_existing_evidence_only() -> None:
    turn = EpisodeFinalizer(recording_model).recover(
        task_frame=_frame(),
        context=_context(),
        evidence=(_evidence("market_data", "close=100", hash="h1"),),
        gaps=("missing news",),
        failure_reason="invalid_model_finish",
    )
    sent = recording_model.calls[0]
    assert sent["tools"] == []
    assert "h1" in json.dumps(sent["messages"], ensure_ascii=False)
    assert "h2" not in json.dumps(sent["messages"], ensure_ascii=False)
    assert turn.tool_calls == ()
```

Add tests proving exactly one attempt, no invocation before evidence exists,
deadline enforcement, and rejection of recovered unknown hashes by the normal
finish parser.

- [ ] **Step 2: Run and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_finalizer.py
```

- [ ] **Step 3: Implement compact recovery**

Build two messages only: a strict recovery system prompt and one JSON user
payload containing `task_frame`, `required_outputs`, `evidence`, `gaps`, data
dates, and `failure_reason`. Call `model.complete` once with the two messages,
an empty tools list, and the remaining synthesis timeout. Do not parse or bless
the response inside the module.

Add `repair()` on the same module for semantic rejection. Its payload adds only
numbered rejected sentences and judge issues; it still receives the same
evidence registry and exposes no tools.

- [ ] **Step 4: Invoke recovery at the four specified terminal failures**

In `ContinuousAgentEpisode`, attempt recovery only when evidence is non-empty
and the normal finalization encounters:

- exception/provider error;
- invalid/empty finish after normal repair allowance;
- tool call after finalization was closed;
- synthesis deadline still has at least one second.

Record `finalization_recovery_started`, one recovery `model_turn`, and its
outcome. Never call recovery recursively.

- [ ] **Step 5: Run and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_finalizer.py \
  intelligence/tests/test_agent_episode.py
git add intelligence/services/episode_finalizer.py intelligence/services/agent_episode.py intelligence/tests/test_episode_finalizer.py intelligence/tests/test_agent_episode.py
git commit -m "feat: recover episode finalization once"
```

## Task 4: Preserve an explicit provider chain at the runtime seam

**Files:**
- Modify: `intelligence/services/llm_settings.py`
- Modify: `intelligence/services/glm_agent_runtime.py`
- Modify: `intelligence/tests/test_llm_settings.py`
- Modify: `intelligence/tests/test_glm_agent_runtime.py`

- [ ] **Step 1: Write RED tests for provider composition**

The principal test scripts a transient failure from `glm`, then a valid message
from `openai`:

```python
def test_runtime_falls_through_transient_primary_failure_and_counts_attempts() -> None:
    client = GLMModelClient(
        providers=(_provider("glm"), _provider("openai")),
        complete_fn=_provider_script(
            glm=(None, "TimeoutError"),
            openai=({"content": "ok", "tool_calls": []}, ""),
        ),
    )
    turn = client.complete(messages=[{"role": "user", "content": "q"}], tools=[], timeout=5)
    assert turn.provider_name == "openai"
    assert turn.provider_attempts == 2
    assert turn.content == "ok"
```

Add `test_byok_runtime_provider_chain_contains_only_user_provider` and assert
the tuple equals `(byok,)`; add
`test_builtin_runtime_provider_chain_preserves_detected_order` and assert the
tuple names equal `("zhipu", "openai")`; add
`test_runtime_does_not_retry_same_provider_after_auth_failure` and assert its
per-provider call counter equals one before the next provider is attempted.

- [ ] **Step 2: Run and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_llm_settings.py intelligence/tests/test_glm_agent_runtime.py
```

- [ ] **Step 3: Add `runtime_providers_for()`**

```python
def runtime_providers_for(self, user_id: str) -> tuple[LLMProvider, ...]:
    byok = self.byok_provider(user_id)
    if byok is not None:
        return (byok,)
    return llm_refine.detect_providers()
```

`describe()` continues to return names/models only, never keys or base URLs.

- [ ] **Step 4: Make the runtime client consume an explicit tuple**

The model client iterates injected providers under
`llm_refine.provider_override(provider)`, always forwarding the same messages,
tools, temperature zero, thinking-disabled profile, and remaining deadline.
Reuse `chat_with_tools`; do not copy its HTTP implementation. Aggregate
physical attempts in the returned `ModelTurn` and add a private provider trace
per failed/successful adapter attempt.

Keep `GLMModelClient` as a compatibility name while making its implementation
provider-neutral. No GPT package dependency is introduced.

- [ ] **Step 5: Run fallback and budget regressions, then commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_llm_settings.py \
  intelligence/tests/test_glm_agent_runtime.py \
  intelligence/tests/test_llm_provider_fallback.py \
  intelligence/tests/test_p1b_runtime.py
git add intelligence/services/llm_settings.py intelligence/services/glm_agent_runtime.py intelligence/tests/test_llm_settings.py intelligence/tests/test_glm_agent_runtime.py
git commit -m "feat: preserve episode provider fallback chain"
```

## Task 5: Gate public completion with semantic grounding

**Files:**
- Create: `intelligence/services/episode_semantic_verifier.py`
- Create: `intelligence/tests/test_episode_semantic_verifier.py`
- Modify: `intelligence/services/episode_verifier.py`
- Modify: `intelligence/services/episode_finalizer.py`

- [ ] **Step 1: Write RED tests at the semantic verifier interface**

The principal test uses a structurally completed outcome and a rejecting judge:

```python
def test_unsupported_causality_is_rejected_and_cannot_stay_completed() -> None:
    verifier = SemanticEpisodeVerifier(
        judge_fn=_judge(False, rejected=(2,), issues=("因果证据不足",)),
        finalizer=_failed_repair(),
    )
    result = verifier.verify(
        frame=_frame(),
        structurally_verified=_structural_complete(
            "市场下跌。政策变化导致了下跌。"
        ),
        deadline=_deadline(),
    )
    assert result.status == "partial"
    assert result.judge_status == "rejected"
    assert "政策变化导致了下跌" not in result.public_answer
```

Add a parameterized test whose judge rejects subject swap, stale-current claim,
and fabricated number, asserting all three downgrade. Add a recording finalizer
test asserting exactly one repair and two total judge calls. Add judge-outage,
structural-partial, and public-sanitization tests; their assertions are,
respectively, `status == "partial" and raw_draft not in public_answer`, no
status upgrade, and absence of the fixture's hash/tool/provider sentinel text.

The fake judge output uses the existing strict shape:

```json
{"passed": false, "rejected_sentence_indexes": [2], "issues": ["因果证据不足"]}
```

- [ ] **Step 2: Run and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_semantic_verifier.py
```

- [ ] **Step 3: Implement judge input and strict parsing**

Build a private evidence registry from `public_agent_evidence`, output bindings,
and numbered answer sentences. Use `llm_refine.judge_provider()` when present;
otherwise use the injected primary judge client and record
`correlated_judge=True`. Parse with `answer_model.parse_grounding_judge_report`.

Define:

```python
@dataclass(frozen=True)
class SemanticEpisodeOutcome:
    verified: VerifiedEpisodeOutcome
    status: Literal["completed", "partial", "failed"]
    public_answer: str
    judge_status: Literal["passed", "repaired", "rejected", "unavailable"]
    issues: tuple[str, ...]
    correlated_judge: bool
```

- [ ] **Step 4: Add one repair/rejudge and fail-closed projection**

Only structurally completed outcomes enter the judge. On rejection,
deterministically remove the exact numbered source spans rejected by the
judge, preserving all accepted text and Markdown layout verbatim. Rebuild the
outcome with the original evidence, bindings, gaps, status, events, traces,
and usage unchanged, re-run the structural verifier, then judge once more.
The repair cannot mint wording, evidence hashes, alter binding ownership, or
upgrade status. If any step is unavailable/invalid/rejected, return `partial`
and a short question-specific evidence-gap answer assembled from the TaskFrame
and verified completion gaps. Preserve rejected drafts only in the private
outcome/artifact.

- [ ] **Step 5: Run and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_episode_verifier.py \
  intelligence/tests/test_answer_model.py -k grounding
git add intelligence/services/episode_semantic_verifier.py intelligence/services/episode_verifier.py intelligence/services/episode_finalizer.py intelligence/tests/test_episode_semantic_verifier.py
git commit -m "feat: gate episode answers semantically"
```

## Task 6: Compose one continuous turn adapter

**Files:**
- Create: `intelligence/services/continuous_turn_adapter.py`
- Create: `intelligence/tests/test_continuous_turn_adapter.py`
- Modify: `intelligence/services/episode_factory.py`
- Modify: `intelligence/services/episode_tools.py`

- [ ] **Step 1: Write RED adapter tests**

Exercise only `ContinuousTurnAdapter.handle()` with injected runtime, verifier,
and registry factory. The first test is:

```python
def test_off_mode_always_declines_without_running_anything() -> None:
    runtime = _RuntimeThatRaisesIfCalled()
    result = ContinuousTurnAdapter(runtime=runtime, mode="off").handle(
        frame=_frame(), control=_research_control()
    )
    assert result.handled is False
```

Add `test_canary_requires_isolated_runtime_identifier` and assert a missing ID
declines; `test_clarification_returns_without_registry_or_model` and assert
zero dependency calls; `test_market_technical_uses_zero_llm_fast_path` and
assert `llm_calls == 0`; `test_long_tail_runs_episode_then_structural_and_semantic_gates`
and assert the call log is `("runtime", "structural", "semantic")`;
`test_episode_owned_answer_is_not_passed_to_legacy_presenter` with a presenter
that raises if called; and `test_valuation_contract_requires_current_anchor_and_assumptions`
with explicit required-output/capability assertions.

- [ ] **Step 2: Run and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_continuous_turn_adapter.py
```

- [ ] **Step 3: Implement mode and result contracts**

Use:

```python
RuntimeMode = Literal["off", "canary", "on"]

@dataclass(frozen=True)
class ContinuousTurnResult:
    handled: bool
    status: Literal["completed", "degraded", "failed"]
    answer: str
    as_of: str | None
    citations: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]
    private_artifact: dict[str, object] | None
    events: tuple[dict[str, object], ...]
```

`canary` handles a turn only when both `ASK_CONTINUOUS_RUNTIME=canary` and a
non-empty `CONTINUOUS_RUNTIME_CANARY_ID` are present. `off` declines. `on` is
implemented but not used on 8792 without the release gate.

- [ ] **Step 4: Strengthen the valuation contract without routing again**

In `episode_factory.py`, for `valuation_estimate`, require the existing output
IDs `valuation_assessment`, `scenario_range`, `evidence_boundary`, and
`invalidation_conditions`; require `market_data` in mandatory capabilities.
Do not create a new valuation route or tool implementation. The existing
valuation block remains the source.

- [ ] **Step 5: Compose the runtime and gates**

The adapter accepts the already canonical TaskFrame/control result, builds one
context/registry, runs fast path or runtime, then structural and semantic gates.
Its citation projection uses evidence title/source/date only. It returns one
private JSON artifact containing events, traces, raw outcome, and both verifier
reports.

- [ ] **Step 6: Run and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_episode_factory.py \
  intelligence/tests/test_episode_tools.py
git add intelligence/services/continuous_turn_adapter.py intelligence/services/episode_factory.py intelligence/services/episode_tools.py intelligence/tests/test_continuous_turn_adapter.py
git commit -m "feat: compose continuous research turns"
```

## Task 7: Wire the adapter into the real Conversation API

**Files:**
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: Write RED integration tests**

Add an orchestrator test with an injected handled result and legacy dependencies
that raise if invoked:

```python
def test_continuous_handled_turn_persists_answer_without_skill_router_or_legacy_ask(tmp_path) -> None:
    orchestrator, stores = _orchestrator(
        tmp_path,
        continuous_adapter=_handled_adapter(answer="直接回答"),
        route_skills_fn=_raises,
        answer_query_fn=_raises,
    )
    result = _run(orchestrator, stores)
    assert result.content == "直接回答"
    assert stores.message().content == "直接回答"
    assert stores.artifact("continuous-episode.json") is not None
```

Add a decline test asserting the existing legacy answer fixture is unchanged; a
degraded test asserting the run/message carry a degrade and never claim the
semantic gate passed; and a public-SSE test asserting the private fixture
sentinels `evidence_hash`, `provider_attempt`, and `system_prompt` are absent.

Add API tests proving the worker receives a provider tuple, BYOK stays single,
health/provenance reports runtime mode/canary ID but no provider credentials,
and cancellation terminalizes the same message/run IDs.

- [ ] **Step 2: Run and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_conversation_orchestrator.py -k continuous \
  intelligence/tests/test_workbench_api.py -k "continuous or provider_chain"
```

- [ ] **Step 3: Add the adapter at the canonical TaskFrame seam**

Inject `continuous_turn_adapter` into `TurnOrchestrator`. In
`_run_turn_ledgered`, call it after `task_frame`, `turn_intent`, report metadata,
and controller trace are frozen, but before knowledge/skill/owner routing. If it
declines, execute the current code unchanged. If it handles:

1. emit high-level public progress events;
2. persist citations, answer text, private `continuous-episode.json`, and report;
3. persist TaskFrame/TurnIntent and provider traces privately;
4. revise the assistant message once;
5. finish the run and return `TurnResult` without entering any legacy owner,
   `AnswerSpec`, synthesis, or fallback.

- [ ] **Step 4: Preserve provider tuples through the worker**

Change `RunSupervisor.submit_conversation` and `_run_conversation_turn` to
accept `llm_providers: tuple[LLMProvider, ...]`. The legacy orchestrator uses
the first provider under its existing override; the continuous adapter receives
the full tuple. The POST handler obtains it from
`llm_settings.runtime_providers_for(user_id)`.

- [ ] **Step 5: Run broad conversation/API regressions and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_llm_settings.py
git add intelligence/services/conversation_orchestrator.py intelligence/api/app.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_api.py
git commit -m "feat: add continuous runtime conversation canary"
```

## Task 8: Extend A/B and run the isolated GLM UI canary

**Files:**
- Modify: `scripts/run_agent_episode_ab.py`
- Modify: `intelligence/tests/test_agent_episode_ab.py`
- Modify: `intelligence/tests/test_capability_monotonicity.py`
- Create: `docs/verification/continuous-agent-production-candidate-2026-07-23.md`

- [ ] **Step 1: Add RED artifact-schema tests**

Require each Episode arm to record:

```python
{
    "structural_status": "completed|partial|failed",
    "semantic_status": "passed|repaired|rejected|unavailable",
    "provider_attempts": 0,
    "tool_calls": 0,
    "duplicate_queries": 0,
    "runtime_mode": "canary",
    "runtime_revision": "candidate-sha",
}
```

Assert the evaluator treats a semantically rejected/unavailable `completed`
answer as a regression.

- [ ] **Step 2: Implement the artifact fields and run scripted tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_episode_ab.py \
  intelligence/tests/test_capability_monotonicity.py
```

- [ ] **Step 3: Commit scripted evaluation support**

```bash
git add scripts/run_agent_episode_ab.py intelligence/tests/test_agent_episode_ab.py intelligence/tests/test_capability_monotonicity.py
git commit -m "test: extend continuous runtime acceptance artifacts"
```

- [ ] **Step 4: Launch an isolated canary**

Create a clean detached runtime from the candidate commit under
`/Users/a77/.finance-runtime/`, configure:

```text
ASK_CONTINUOUS_RUNTIME=canary
CONTINUOUS_RUNTIME_CANARY_ID=<candidate-sha>
FINANCE_WS=/Users/a77/finance-workspace-private
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki
FORESIGHT_BUILTIN_LLM_MODEL=glm-5.2
```

Inject the GLM key from Keychain at process start without printing or writing
it. Bind a noncanonical localhost port. Do not modify the 8792 LaunchAgent or
`/Users/a77/finance-workspace-runtime` symlink.

- [ ] **Step 5: Run the five questions through the Conversation API**

For each case, create a conversation, POST the message, consume SSE to a
terminal event, and save the public answer/private artifact:

```text
昨天的反弹能持续多久
科创50你认为反弹空间有多少
瑞华泰的合理估值
这一周行情下跌的主要原因是什么
目前市场的主线是什么
```

Then run all five sequentially in the same canary process. Confirm every answer
is non-empty and task-relevant or contains a specific evidence gap, the
valuation case has a current anchor or honest external-data failure, semantic
status never contradicts public terminal state, and the technical case remains
zero-LLM.

- [ ] **Step 6: Write the verification report**

Record candidate SHA, runtime paths/port, unchanged canonical 8792 identity,
commands, test totals, answer excerpts, latencies, LLM/provider attempts, tool
calls, duplicate count, structural/semantic verdicts, failures, and artifact
hashes. Do not hide provider burst failures or rerun-select only successful
answers.

## Task 9: Full regression, review, and handoff

**Files:**
- Modify: `docs/verification/continuous-agent-production-candidate-2026-07-23.md`
- Modify: `/Users/a77/agent-memory/20_projects/finance-workspace-private.md`

- [ ] **Step 1: Run focused and complete suites**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_tool_batch.py \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_episode_finalizer.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_glm_agent_runtime.py \
  intelligence/tests/test_episode_verifier.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_api.py

/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests
```

Compare every complete-suite failure to the fixed branch baseline. No changed
module may be excused by an unrelated historical failure.

- [ ] **Step 2: Run two-axis review**

Review from fixed point `25855601`:

- spec compliance against all ten sections of
  `2026-07-23-continuous-agent-production-candidate-design.md`;
- code quality for concurrency safety, deadline leaks, context propagation,
  secret/public projection, fail-open semantics, duplicate policy, and shallow
  wrappers.

Fix all blocking findings and rerun affected tests.

- [ ] **Step 3: Perform the completion audit**

Create a seven-row requirement table. Every row must cite current source files,
tests, and real runtime artifacts. Mark missing or indirect evidence as not
complete and continue implementation rather than lowering the requirement.

- [ ] **Step 4: Commit verification and memory**

```bash
git add docs/verification/continuous-agent-production-candidate-2026-07-23.md
git commit -m "docs: verify continuous agent production candidate"
```

Append the branch SHA, test totals, canary port/runtime, A/B result, semantic
gate status, known external credential limitation, and next release gate to the
project memory. Run `vault_lint.py`; do not modify unrelated historical errors.

- [ ] **Step 5: Stop at the release gate**

Leave the implementation branch and canonical 8792 unchanged until the user
reviews the canary answers and explicitly approves merge plus atomic cutover.
Provide the canary local URL and rollback-ready release instructions.

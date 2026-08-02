# GLM Continuous Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a provider-neutral continuous research episode driven by GLM, reusing the repository's read-only finance tools and grounded completion gates without switching the canonical 8792 runtime.

**Architecture:** `TurnControlCore` freezes one immutable `TaskFrame` and selects clarification, deterministic fast path, or a long-tail episode. `ContinuousAgentEpisode` keeps the original assistant actions and raw tool observations in one message history, while `ResearchToolRegistry` enforces tool authorization, deadlines, and traceability. `GLMAgentRuntime` is only a provider adapter; an episode verifier binds required outputs to collected evidence before the result can be compared with the bare model and legacy Workbench.

**Tech Stack:** Python 3.11 dataclasses and protocols, existing OpenAI-compatible `llm_refine.chat_with_tools`, `ResearchToolRegistry`, `ResearchTaskContract`, `ProviderTrace`, pytest, existing capability-monotonicity evaluator.

---

## File Structure

- Modify `intelligence/services/task_frame.py`: preserve all route-table question types in the semantic frame and define their required outputs.
- Modify `intelligence/services/evidence_capabilities.py`: project a `TaskFrame` into the new runtime's tool-capability namespace.
- Finish `intelligence/services/turn_control_core.py`: provide one control result and prevent legacy lane/capability downgrades.
- Modify `intelligence/tests/test_turn_control_core.py`: pin clarification, knowledge, follow-up, route-key, and capability-floor behavior.
- Create `intelligence/services/agent_runtime.py`: provider-neutral model-turn, episode-event, output-binding, usage, outcome, and runtime protocols.
- Create `intelligence/tests/test_agent_runtime.py`: validate immutable hashes and serialization boundaries.
- Modify `intelligence/services/research_tool_registry.py`: expose typed authorized tool definitions without leaking runner implementations.
- Modify `intelligence/tests/test_generic_research_owner.py`: cover tool-definition authorization alongside existing registry behavior.
- Create `intelligence/services/agent_episode.py`: implement the continuous model/tool loop and deterministic failure policy.
- Create `intelligence/tests/test_agent_episode.py`: scripted-model tests for continuity, repair, authorization, dedupe, deadline, and completion claims.
- Create `intelligence/services/glm_agent_runtime.py`: adapt `llm_refine.chat_with_tools` into the provider-neutral model client/runtime.
- Create `intelligence/tests/test_glm_agent_runtime.py`: verify provider objects do not cross the boundary and the full message history is forwarded unchanged.
- Create `intelligence/services/episode_verifier.py`: bind episode output declarations to actual evidence and reuse the existing `CompletionReport` vocabulary.
- Create `intelligence/tests/test_episode_verifier.py`: fail closed on missing, unknown, or semantically unverified bindings.
- Create `intelligence/services/episode_factory.py`: construct a research contract and run context from `TaskFrame` without importing the legacy orchestrator.
- Create `intelligence/tests/test_episode_factory.py`: verify the five target questions receive the right outputs, tools, tier, and immutable hash.
- Create `scripts/run_agent_episode_ab.py`: run bare-model and GLM-episode arms and optionally ingest a saved canonical-8792 answer as the current arm.
- Modify `intelligence/tests/test_capability_monotonicity.py`: verify A/B artifacts are accepted by the fixed three-arm quality gate.
- Create `docs/verification/glm-continuous-agent-runtime-2026-07-22.md`: record scripted verification first and real-GLM results second.

### Task 1: Close the Turn Control Seam

**Files:**
- Modify: `intelligence/services/task_frame.py`
- Modify: `intelligence/services/evidence_capabilities.py`
- Modify: `intelligence/services/turn_control_core.py`
- Modify: `intelligence/tests/test_turn_control_core.py`
- Test: `intelligence/tests/test_task_frame.py`
- Test: `intelligence/tests/test_turn_controller.py`

- [ ] **Step 1: Write failing tests for the six known seam defects**

Add tests that assert stable knowledge is `non_research`, clarification forces `needs_retrieval=False`, a financial frame gets non-empty runtime capabilities even when a fake legacy controller returns chat, route keys are `chat`/`clarify` at terminal lanes, a real pending `TurnIntent` preserves and resolves its frame, and the route-table types `quick_fact`, `theme_track`, `kol_review`, `comparison_analog`, and `trade_advice` do not collapse to `general_finance_qa`.

```python
def test_clarification_never_executes_retrieval() -> None:
    result = TurnControlCore().control("这个反弹还能持续多久")
    assert result.execution_route == "clarify"
    assert result.terminal_kind == "clarification"
    assert result.needs_retrieval is False
    assert result.capabilities == ()


def test_financial_frame_supplies_runtime_capability_floor() -> None:
    frame = _financial_frame()
    result = TurnControlCore(legacy_decide=_chat_decision(frame)).control(
        frame.raw_question
    )
    assert result.terminal_kind == "research"
    assert {"market_data", "news_search"}.issubset(result.capabilities)
```

- [ ] **Step 2: Run the focused tests and confirm the expected failures**

Run:

```bash
pytest -q intelligence/tests/test_turn_control_core.py intelligence/tests/test_task_frame.py intelligence/tests/test_turn_controller.py
```

Expected: new assertions fail because clarification currently inherits the frame retrieval floor, `route_id` uses `frame.question_type`, and runtime capabilities are not projected.

- [ ] **Step 3: Add the runtime capability projection**

In `evidence_capabilities.py`, add one public projection in the new registry namespace. It must union the evidence plan with the frame-policy floor and return no tools for stable/model-reasoning questions.

```python
_RUNTIME_CAPABILITY_FLOOR = {
    "current_market_scenarios": ("market_data", "mainline_context", "news_search", "web_search"),
    "time_aligned_market_causal": ("market_data", "news_search", "web_search"),
    "company_valuation_evidence": ("market_data", "kb_search", "evidence_lookup", "web_search"),
    "company_multi_layer_evidence": ("kb_search", "graph_lookup", "evidence_lookup", "web_search"),
    "theme_multi_layer_evidence": ("kb_search", "graph_lookup", "news_search", "web_search"),
}


def runtime_capabilities_for_frame(frame: TaskFrame) -> tuple[str, ...]:
    if not task_frame_requires_retrieval(frame):
        return ()
    plan = resolve_evidence_plan(
        frame.raw_question,
        question_type=frame.question_type,
        freshness="current",
    )
    return tuple(dict.fromkeys((
        *_RUNTIME_CAPABILITY_FLOOR.get(frame.evidence_policy, ("kb_search", "web_search")),
        *(item.capability for item in plan.requirements),
    )))
```

- [ ] **Step 4: Preserve the missing route-table semantic types**

Extend `_POLICY_BY_QUESTION_TYPE` and `_default_required_outputs` in `task_frame.py` with explicit policies/outputs for the five route-table types. Do not invent new execution owners here; this file only describes what the user asked.

```python
"quick_fact": "current_fact_evidence",
"theme_track": "theme_tracking_evidence",
"kol_review": "source_critique_evidence",
"comparison_analog": "comparable_multi_source_evidence",
"trade_advice": "conditional_thesis_evidence",
```

- [ ] **Step 5: Make `TurnControlCore` the only terminal-policy adapter**

Rename `route_id` to `execution_route`; use `chat`, `meta`, or `clarify` for terminal routes and the decision/frame question type for research. Compute clarification first and return zero retrieval/capabilities for it. For research, union legacy metadata with `runtime_capabilities_for_frame(frame)`. Keep `previous_intent` as the real legacy follow-up input; `previous_frame` is only an explicit test/sidecar fallback when the decision has no frame.

```python
if terminal_kind == "clarification":
    needs_retrieval = False
    capabilities = ()
elif terminal_kind == "non_research":
    needs_retrieval = False
    capabilities = ()
else:
    needs_retrieval = True
    capabilities = runtime_capabilities_for_frame(frame)
```

Move the default `decide_turn` import inside `__init__` so the new core depends on an injected port and does not create a future import cycle.

- [ ] **Step 6: Run the focused tests**

Run:

```bash
pytest -q intelligence/tests/test_turn_control_core.py intelligence/tests/test_task_frame.py intelligence/tests/test_turn_controller.py
```

Expected: all tests pass.

- [ ] **Step 7: Commit the seam**

```bash
git add intelligence/services/task_frame.py intelligence/services/evidence_capabilities.py intelligence/services/turn_control_core.py intelligence/tests/test_turn_control_core.py intelligence/tests/test_task_frame.py intelligence/tests/test_turn_controller.py
git commit -m "fix: close continuous runtime control seam"
```

### Task 2: Define the Provider-Neutral Runtime Contract

**Files:**
- Create: `intelligence/services/agent_runtime.py`
- Create: `intelligence/tests/test_agent_runtime.py`

- [ ] **Step 1: Write failing contract tests**

```python
def test_agent_outcome_rejects_changed_task_frame_hash() -> None:
    with pytest.raises(ValueError, match="task frame hash"):
        AgentOutcome(
            task_frame_hash="changed",
            status="completed",
            draft="answer",
            evidence=(), traces=(), gaps=(), stop_reason="model_finish",
            events=(EpisodeEvent(1, "task", {"task_frame_hash": "original"}),),
            bindings=(), usage=AgentUsage(),
        )


def test_model_turn_contains_no_provider_object() -> None:
    turn = ModelTurn(content="done", tool_calls=(), provider_name="glm", error="")
    assert set(turn.to_dict()) == {"content", "tool_calls", "provider_name", "error"}
```

- [ ] **Step 2: Run the tests and confirm import failure**

Run: `pytest -q intelligence/tests/test_agent_runtime.py`

Expected: FAIL because `agent_runtime` does not exist.

- [ ] **Step 3: Implement the immutable data contracts and protocols**

Define:

```python
EpisodeStatus = Literal["completed", "partial", "clarification", "failed"]

@dataclass(frozen=True)
class ModelToolCall:
    call_id: str
    name: str
    arguments: dict[str, object]

@dataclass(frozen=True)
class ModelTurn:
    content: str
    tool_calls: tuple[ModelToolCall, ...]
    provider_name: str = ""
    error: str = ""

class AgentModelClient(Protocol):
    def complete(self, *, messages: list[dict[str, object]], tools: list[dict[str, object]], timeout: float) -> ModelTurn: ...

@dataclass(frozen=True)
class OutputEvidenceBinding:
    output_id: str
    evidence_hashes: tuple[str, ...]
    gap: str = ""

@dataclass(frozen=True)
class EpisodeEvent:
    sequence: int
    kind: str
    payload: dict[str, object]

@dataclass(frozen=True)
class AgentUsage:
    llm_calls: int = 0
    tool_calls: int = 0
    invalid_actions: int = 0

@dataclass(frozen=True)
class AgentOutcome:
    task_frame_hash: str
    status: EpisodeStatus
    draft: str
    evidence: tuple[AgentEvidence, ...]
    traces: tuple[ProviderTrace, ...]
    gaps: tuple[str, ...]
    stop_reason: str
    events: tuple[EpisodeEvent, ...]
    bindings: tuple[OutputEvidenceBinding, ...]
    usage: AgentUsage

class AgentRuntime(Protocol):
    def run(self, *, task_frame: TaskFrame, context: ResearchRunContext, registry: ResearchToolRegistry) -> AgentOutcome: ...
```

`AgentOutcome.__post_init__` must ensure the first task event carries the same non-empty hash and sequence numbers are contiguous. `to_dict()` returns only JSON-safe primitives.

- [ ] **Step 4: Run the contract tests**

Run: `pytest -q intelligence/tests/test_agent_runtime.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add intelligence/services/agent_runtime.py intelligence/tests/test_agent_runtime.py
git commit -m "feat: define provider neutral agent runtime"
```

### Task 3: Expose Authorized Finance Tool Definitions

**Files:**
- Modify: `intelligence/services/research_tool_registry.py`
- Modify: `intelligence/tests/test_generic_research_owner.py`

- [ ] **Step 1: Add a failing authorization/schema test**

```python
def test_registry_definitions_only_expose_contract_capabilities() -> None:
    registry = ResearchToolRegistry((_spec("market_data"), _spec("web_search")))
    definitions = registry.tool_definitions(("market_data",))
    assert [item["function"]["name"] for item in definitions] == ["market_data"]
    assert definitions[0]["function"]["parameters"]["required"] == ["query"]
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q intelligence/tests/test_generic_research_owner.py -k tool_definitions`

Expected: FAIL because `tool_definitions` is absent.

- [ ] **Step 3: Implement `authorized_specs` and `tool_definitions`**

```python
def authorized_specs(self, allowed: tuple[str, ...]) -> tuple[ToolSpec, ...]:
    allowed_set = set(allowed)
    return tuple(
        spec for spec in self._specs.values()
        if not allowed_set or spec.capability in allowed_set
    )

def tool_definitions(self, allowed: tuple[str, ...]) -> list[dict[str, object]]:
    return [{
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    } for spec in self.authorized_specs(allowed)]
```

- [ ] **Step 4: Run the registry and generic-owner tests**

Run: `pytest -q intelligence/tests/test_generic_research_owner.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add intelligence/services/research_tool_registry.py intelligence/tests/test_generic_research_owner.py
git commit -m "feat: expose authorized research tool schemas"
```

### Task 4: Implement the Continuous Agent Episode

**Files:**
- Create: `intelligence/services/agent_episode.py`
- Create: `intelligence/tests/test_agent_episode.py`

- [ ] **Step 1: Write the continuity test first**

Use a scripted `AgentModelClient`: turn one calls `market_data`; turn two returns a final draft and output bindings. The second recorded model input must contain the exact first assistant tool-call message and the raw `TOOL_RESULT` observation, not a rebuilt summary.

```python
assert second_messages[:2] == first_messages[:2]
assert second_messages[2]["role"] == "assistant"
assert second_messages[2]["tool_calls"][0]["function"]["name"] == "market_data"
assert second_messages[3]["role"] == "tool"
assert "raw market observation" in second_messages[3]["content"]
```

- [ ] **Step 2: Add failing tests for repair and hard limits**

Cover these cases independently:

```python
def test_unknown_tool_error_returns_to_same_episode(): ...
def test_duplicate_normalized_query_is_rejected_without_runner_call(): ...
def test_tool_exception_is_recorded_and_model_can_continue(): ...
def test_one_invalid_finish_gets_one_repair_turn(): ...
def test_exhaustion_returns_partial_with_explicit_gap(): ...
def test_task_frame_hash_is_identical_in_every_event(): ...
```

- [ ] **Step 3: Run and confirm module import failure**

Run: `pytest -q intelligence/tests/test_agent_episode.py`

Expected: FAIL because `agent_episode` does not exist.

- [ ] **Step 4: Implement one persistent message ledger**

`ContinuousAgentEpisode.run()` creates `messages` once, appends to the same list after every turn, and never calls `agent_research._research_state_block`.

```python
messages: list[dict[str, object]] = [
    {"role": "system", "content": self._system_prompt(task_frame, context, registry)},
    {"role": "user", "content": self._task_prompt(task_frame, context.contract)},
]
for step in range(1, context.policy.max_steps + 1):
    turn = self._model.complete(
        messages=list(messages),
        tools=registry.tool_definitions(context.contract.allowed_capabilities),
        timeout=context.deadline.stage_timeout(self._llm_timeout),
    )
```

The system prompt must say: answer the immutable task, call only supplied tools, cite stable evidence hashes in `FINAL_JSON`, report gaps, and never claim an uncovered required output. It must not prescribe headings, line counts, or prose templates.

- [ ] **Step 5: Implement native tool-call dispatch and raw observations**

Append the normalized assistant message first. For each tool call, require a non-empty string `query`; reject unknown/unauthorized tools and duplicate `(tool, normalize_query(query))` keys without executing them. Successful tool content is JSON containing `observation`, public evidence fields, `evidence_hashes`, and gaps. Append it with `role="tool"` and the original `tool_call_id`.

```python
messages.append(_assistant_message(turn))
messages.append({
    "role": "tool",
    "tool_call_id": call.call_id,
    "content": json.dumps(public_observation, ensure_ascii=False),
})
```

Every success/failure also appends an `EpisodeEvent`. Tool exceptions create a synthetic error `ProviderTrace` if the registry did not return one; they do not switch pipelines.

- [ ] **Step 6: Implement terminal `FINAL_JSON` parsing**

When the model emits no tool call, parse exactly one object from content:

```json
{
  "status": "completed",
  "draft": "直接、自然的研究回答",
  "gaps": [],
  "bindings": [
    {"output_id": "duration_assessment", "evidence_hashes": ["abc123"]}
  ]
}
```

Validate status, non-empty draft for `completed`, unique required-output IDs, and hashes that exist in collected evidence. An invalid first finish appends a repair instruction to the same history; a second invalid finish returns `partial` with `invalid_model_finish`.

- [ ] **Step 7: Implement deterministic stopping**

If the model is unavailable before evidence, return `failed`; after evidence, return `partial`. Deadline/step exhaustion returns `partial`, preserves evidence/traces, and adds `研究预算已耗尽，仍有必需输出未覆盖`. Do not call any legacy template or presenter.

- [ ] **Step 8: Run the episode tests**

Run: `pytest -q intelligence/tests/test_agent_episode.py`

Expected: PASS, including the exact second-turn history assertion.

- [ ] **Step 9: Commit**

```bash
git add intelligence/services/agent_episode.py intelligence/tests/test_agent_episode.py
git commit -m "feat: add continuous finance agent episode"
```

### Task 5: Add the GLM Provider Adapter

**Files:**
- Create: `intelligence/services/glm_agent_runtime.py`
- Create: `intelligence/tests/test_glm_agent_runtime.py`

- [ ] **Step 1: Write failing adapter tests**

Patch `llm_refine.chat_with_tools` to return an OpenAI-compatible assistant message. Assert conversion of provider name, tool call ID/name/arguments, and error handling. Also assert the exact message list object contents reach the second provider call.

```python
raw = {"content": None, "tool_calls": [{
    "id": "call-1", "type": "function",
    "function": {"name": "market_data", "arguments": '{"query":"A股"}'},
}]}
```

- [ ] **Step 2: Run and confirm import failure**

Run: `pytest -q intelligence/tests/test_glm_agent_runtime.py`

Expected: FAIL because `glm_agent_runtime` does not exist.

- [ ] **Step 3: Implement `GLMModelClient` and `GLMAgentRuntime`**

`GLMModelClient.complete()` calls `chat_with_tools(..., model_override=self.model, temperature=0.0, tool_choice="auto")`, converts raw provider/tool-call data into `ModelTurn`, and converts malformed argument JSON into a model-turn error. It never returns `LLMProvider` itself.

`GLMAgentRuntime.run()` is a thin composition root:

```python
class GLMAgentRuntime:
    def __init__(self, model: str | None = None, complete_fn=None) -> None:
        self._episode = ContinuousAgentEpisode(GLMModelClient(model, complete_fn))

    def run(self, *, task_frame, context, registry) -> AgentOutcome:
        return self._episode.run(task_frame=task_frame, context=context, registry=registry)
```

- [ ] **Step 4: Run adapter plus episode tests**

Run:

```bash
pytest -q intelligence/tests/test_glm_agent_runtime.py intelligence/tests/test_agent_episode.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add intelligence/services/glm_agent_runtime.py intelligence/tests/test_glm_agent_runtime.py
git commit -m "feat: adapt glm to continuous agent runtime"
```

### Task 6: Build Contracts and Verify Episode Completion

**Files:**
- Create: `intelligence/services/episode_factory.py`
- Create: `intelligence/services/episode_verifier.py`
- Create: `intelligence/tests/test_episode_factory.py`
- Create: `intelligence/tests/test_episode_verifier.py`

- [ ] **Step 1: Write failing factory tests for the five acceptance questions**

Parametrize the target questions and assert that `TurnControlCore -> build_episode_context` preserves `task_frame_hash`, produces at least one required output, and authorizes only registry capability names. Specific checks:

```python
("昨天的反弹能持续多久", {"market_data", "news_search"}, "duration_assessment"),
("科创50你认为反弹空间有多少", {"market_data"}, "technical_levels"),
("瑞华泰的合理估值", {"market_data", "evidence_lookup"}, "valuation_assessment"),
("这一周行情下跌的主要原因是什么", {"market_data", "news_search"}, "causal_chain"),
("目前市场的主线是什么", {"market_data", "mainline_context"}, "direct_assessment"),
```

- [ ] **Step 2: Implement `build_episode_context`**

Construct `ResearchTaskContract` directly from `TaskFrame`; do not import private helpers from `conversation_orchestrator.py`. Required outputs come from `frame.required_outputs`; their `evidence_types` are the authorized capabilities. `resolve_evidence_plan` supplies mandatory evidence products. `ResearchPolicy.for_tier(tier)` owns both the deadline and step budget, so budget is calculated once.

```python
policy = ResearchPolicy.for_tier(tier)
contract = ResearchTaskContract(
    task_id=task_id,
    question=frame.raw_question,
    subject=frame.subject,
    subject_kind=frame.subject_kind,
    question_type=frame.question_type,
    required_outputs=tuple(
        RequiredOutput(item, item, capabilities, True)
        for item in frame.required_outputs
    ),
    allowed_capabilities=capabilities,
    research_tier=tier,
    freshness="current",
    timeframe=frame.timeframe,
    evidence_plan=resolve_evidence_plan(...),
    task_frame_hash=frame.task_frame_hash,
)
```

- [ ] **Step 3: Write failing verifier tests**

Assert completed is rejected when: a required output is absent; an evidence hash is unknown; a binding points at a tool outside that required output's evidence types; or the draft is empty. Assert an explicit gap yields `partial`, never fake `completed`.

- [ ] **Step 4: Implement deterministic binding verification**

Build `CompletionReport`/`OutputStatus` using only actual `AgentEvidence.content_hash` values. A required output is `fulfilled` only when it has at least one valid binding; otherwise it is `missing`. The report may downgrade `AgentOutcome.status` but may never upgrade it.

```python
verified_status = (
    "completed"
    if outcome.status == "completed" and all_required_fulfilled and outcome.draft.strip()
    else "partial"
)
```

Return `VerifiedEpisodeOutcome(outcome, completion, verified_status)`. This is the shared grounded exit for the sidecar; semantic claim judging/presentation remains a later integration gate and is not bypassed.

- [ ] **Step 5: Run factory and verifier tests**

Run:

```bash
pytest -q intelligence/tests/test_episode_factory.py intelligence/tests/test_episode_verifier.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add intelligence/services/episode_factory.py intelligence/services/episode_verifier.py intelligence/tests/test_episode_factory.py intelligence/tests/test_episode_verifier.py
git commit -m "feat: verify continuous episode fulfillment"
```

### Task 7: Add a Non-Production A/B Runner

**Files:**
- Create: `scripts/run_agent_episode_ab.py`
- Create: `intelligence/tests/test_agent_episode_ab.py`
- Modify: `intelligence/tests/test_capability_monotonicity.py`
- Modify: `intelligence/tests/fixtures/capability_monotonicity_cases.json`

- [ ] **Step 1: Write failing CLI tests with fake model and tool factories**

The script must support `--dry-run` (build task/control/contracts only), `--questions-file`, `--output`, and optional `--current-results` containing saved canonical-8792 answers. It must refuse to label a missing legacy answer as a current-arm result.

```python
code = episode_ab.main([
    "--dry-run",
    "--questions-file", str(cases),
    "--output", str(output),
])
assert code == 0
assert payload["runtime_switched"] is False
assert payload["cases"][0]["task_frame_hash"]
```

- [ ] **Step 2: Run and confirm import failure**

Run: `pytest -q intelligence/tests/test_agent_episode_ab.py`

Expected: FAIL because the runner does not exist.

- [ ] **Step 3: Implement the sidecar runner**

The live path performs:

1. `TurnControlCore.control(question)`;
2. clarification/fast-path cases are recorded but not sent to the episode;
3. `build_episode_context(...)`;
4. existing `agent_research.build_default_tools(...)` plus existing market/graph/evidence runner injection;
5. `GLMAgentRuntime.run(...)`;
6. `verify_episode_outcome(...)`;
7. JSON artifact with answer, evidence hashes, traces, gaps, latency, LLM/tool counts, and stop reason.

Do not call or mutate canonical 8792. `--current-results` only reads a previously exported answer file. Never load secrets from a file; provider configuration stays in the existing environment/keychain path.

- [ ] **Step 4: Extend the fixed A/B question fixture**

Ensure the three-arm evaluation includes all five target questions from the design spec. Keep the fixed 0.2 monotonicity margin and the rule that the bare arm has zero tool calls.

- [ ] **Step 5: Run CLI/evaluator tests**

Run:

```bash
pytest -q intelligence/tests/test_agent_episode_ab.py intelligence/tests/test_capability_monotonicity.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_agent_episode_ab.py intelligence/tests/test_agent_episode_ab.py intelligence/tests/test_capability_monotonicity.py intelligence/tests/fixtures/capability_monotonicity_cases.json
git commit -m "test: add continuous runtime ab harness"
```

### Task 8: Verify Scripted Runtime, Then Run Isolated Real GLM A/B

**Files:**
- Create: `docs/verification/glm-continuous-agent-runtime-2026-07-22.md`
- Modify: `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` only after code/test verification succeeds.

- [ ] **Step 1: Run all focused tests**

Run:

```bash
pytest -q \
  intelligence/tests/test_turn_control_core.py \
  intelligence/tests/test_task_frame.py \
  intelligence/tests/test_turn_controller.py \
  intelligence/tests/test_agent_runtime.py \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_glm_agent_runtime.py \
  intelligence/tests/test_episode_factory.py \
  intelligence/tests/test_episode_verifier.py \
  intelligence/tests/test_agent_episode_ab.py \
  intelligence/tests/test_generic_research_owner.py \
  intelligence/tests/test_capability_monotonicity.py
```

Expected: PASS.

- [ ] **Step 2: Run the broader intelligence test suite**

Run: `pytest -q intelligence/tests`

Expected: no new failures compared with the documented baseline; classify any known machine-path failures separately instead of hiding them.

- [ ] **Step 3: Generate the dry-run artifact**

Run:

```bash
python3 scripts/run_agent_episode_ab.py \
  --dry-run \
  --questions-file intelligence/tests/fixtures/capability_monotonicity_cases.json \
  --output /tmp/glm-agent-episode-dry-run.json
```

Expected: five cases, immutable frame hashes, authorized tools, `runtime_switched=false`, and no LLM/tool execution.

- [ ] **Step 4: Run the real GLM episode sidecar**

Use the existing environment/keychain-backed GLM configuration and write only to `/tmp`:

```bash
python3 scripts/run_agent_episode_ab.py \
  --questions-file intelligence/tests/fixtures/capability_monotonicity_cases.json \
  --output /tmp/glm-agent-episode-live.json
```

Expected: every research case ends `completed` or honest `partial`; no unrelated template, no unknown evidence hash, no duplicate executed query, and second-turn histories exist for tool-using cases. If provider credentials are unavailable, record the run as blocked by environment rather than fabricating a live result.

- [ ] **Step 5: Compare with saved bare/current arms**

Export the same five canonical-8792 answers without changing the running service, then pass them as `--current-results`. Score the resulting three-arm records through `scripts/capability_monotonicity.py`. The episode arm must not breach the existing bare-model capability floor.

- [ ] **Step 6: Write the verification report**

Record commit, commands, case-by-case task alignment, evidence relevance/freshness, required-output coverage, unsupported claims, duplicate retrieval, latency, tool/LLM counts, and whether the continuity hypothesis was supported. State explicitly that 8792 was not switched and `main` was not merged.

- [ ] **Step 7: Run code review against the design commit**

Use `$code-review` with base `7bc8dcff`; resolve all P0/P1 findings, rerun affected tests, and include lower-priority accepted debt in the verification report.

- [ ] **Step 8: Commit verification and project handoff**

```bash
git add docs/verification/glm-continuous-agent-runtime-2026-07-22.md
git commit -m "docs: verify glm continuous agent runtime"
```

Update project memory with the branch tip, test counts, A/B result, known limits, and the explicit next decision: keep sidecar, canary selected long-tail traffic, or reject the hypothesis. Do not merge `main` or switch 8792 without separate user approval.

## Self-Review Results

- Spec coverage: control semantics, provider-neutral contract, continuous observable history, tool authorization, duplicate/deadline enforcement, failure behavior, completion verification, five A/B cases, and no-production-switch rule each map to a task above.
- Scope boundary: GPT/Agents SDK, context compaction, arbitrary shell access, UI/SSE integration, canary routing, and canonical cutover remain explicitly outside this first GLM baseline.
- Type consistency: `task_frame_hash`, `execution_route`, `ModelTurn`, `OutputEvidenceBinding`, `AgentOutcome`, `ResearchRunContext`, and `VerifiedEpisodeOutcome` use the same names across tasks.
- Placeholder scan: implementation steps specify concrete types, schemas, commands, and expected outcomes; no `TBD`, `TODO`, or implicit “similar tests” remain.

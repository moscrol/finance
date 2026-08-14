# Agent Runtime Backends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify Continuous Episode, OpenAI Agents SDK, and Codex headless runtime arms behind the existing `AgentRuntime` seam, with shared finance tools, evidence verification, evaluation inputs, and Workbench protocol.

**Architecture:** Keep `ContinuousTurnAdapter` as the product adapter and `AgentRuntime.run` returning `AgentOutcome` as the only execution seam. Extract the shared episode prompt/finish protocol, implement SDK and headless adapters, select them only in the composition root, and compare them through one benchmark artifact and the existing structural/semantic verifier chain.

**Tech Stack:** Python 3.12, dataclasses, OpenAI Agents SDK, OpenAI Responses/Chat Completions adapters, Codex CLI JSONL, Python standard-library loopback HTTP, FastAPI, pytest, React/Vitest/Playwright.

---

## Working rules

- Worktree: `/Users/a77/.codex/worktrees/finance-task-fulfillment`
- Branch: `feat/agent-runtime-backends`
- Do not merge `main`, switch canonical 8792, or change
  `/Users/a77/finance-workspace-runtime`.
- Use `/Users/a77/finance-workspace-private/.venv-workbench/bin/python` for tests.
- Clear `FORESIGHT_USERS_DIR`, `FORESIGHT_USER`, `SUBCONSCIOUS_VAULT`, and
  `AGENT_MEMORY_VAULT` before full Python tests.
- Never print, persist, or commit API keys or Keychain values.
- Commit after every task only when its focused tests pass.

## File responsibility map

- `episode_protocol.py`: one shared prompt, task input, finish schema, and finish validator.
- `agent_episode.py`: current self-built loop; it delegates protocol work after Task 1.
- `agent_runtime_factory.py`: explicit backend composition and readiness metadata.
- `headless_tool_gateway.py`: run-scoped loopback transport over the canonical registry.
- `codex_headless_runtime.py`: Codex subprocess, JSONL audit, shared outcome conversion.
- `openai_agents_runtime.py`: Agents SDK runner, generated function tools, shared outcome conversion.
- `runtime_backend_benchmark.py`: provider-neutral benchmark types and acceptance summaries.
- `run_agent_runtime_benchmark.py`: real arm execution and atomic artifact writing.
- `app.py`: selects one configured runtime while preserving the existing Run/SSE/UI path.

## Task 1: Extract the shared episode protocol without changing behavior

**Files:**
- Create: `intelligence/services/episode_protocol.py`
- Modify: `intelligence/services/agent_episode.py:220-245`
- Modify: `intelligence/services/agent_episode.py:450-485`
- Modify: `intelligence/services/agent_episode.py:760-790`
- Modify: `intelligence/services/agent_episode.py:884-1208`
- Test: `intelligence/tests/test_episode_protocol.py`
- Test: `intelligence/tests/test_agent_episode.py`

- [ ] **Step 1: Write failing protocol parity tests**

```python
from intelligence.services.episode_protocol import (
    EpisodeFinish,
    build_episode_input,
    build_episode_instructions,
    finish_json_schema,
    validate_episode_finish,
)


def test_finish_schema_is_closed_and_requires_all_fields() -> None:
    schema = finish_json_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"status", "draft", "gaps", "bindings"}


def test_validate_finish_rejects_unknown_evidence_hash(
    episode_context,
    episode_evidence,
) -> None:
    value = {
        "status": "completed",
        "draft": "当前判断有直接依据。",
        "gaps": [],
        "bindings": [
            {
                "output_id": episode_context.contract.required_outputs[0].output_id,
                "evidence_hashes": ["unknown-hash"],
                "gap": "",
            }
        ],
    }
    with pytest.raises(ValueError, match="unknown evidence hash"):
        validate_episode_finish(
            value,
            context=episode_context,
            evidence=episode_evidence,
        )


def test_episode_finish_is_an_immutable_value() -> None:
    finish = EpisodeFinish("partial", "判断", ("缺新闻",), ())
    assert finish.status == "partial"
    with pytest.raises(dataclasses.FrozenInstanceError):
        finish.status = "completed"  # type: ignore[misc]
```

- [ ] **Step 2: Run the new tests and confirm import failure**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_protocol.py
```

Expected: collection fails because `intelligence.services.episode_protocol` does not exist.

- [ ] **Step 3: Implement the shared value and interface**

```python
@dataclass(frozen=True)
class EpisodeFinish:
    status: EpisodeStatus
    draft: str
    gaps: tuple[str, ...]
    bindings: tuple[OutputEvidenceBinding, ...]


def finish_json_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["completed", "partial"]},
            "draft": {"type": "string"},
            "gaps": {"type": "array", "items": {"type": "string"}},
            "bindings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "output_id": {"type": "string"},
                        "evidence_hashes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "gap": {"type": "string"},
                    },
                    "required": ["output_id", "evidence_hashes", "gap"],
                },
            },
        },
        "required": ["status", "draft", "gaps", "bindings"],
    }
```

Move the existing `_system_prompt`, `_task_prompt`, `_parse_json_object`,
`_normalize_natural_language_layout`, `_recover_finish_with_raw_draft`, and
finish-binding validation into this module. `validate_episode_finish` accepts a
decoded object or JSON string and returns `EpisodeFinish`; it retains all current
valuation evidence floors and required-output substance checks.

- [ ] **Step 4: Change Continuous Episode to call the shared module**

```python
messages = [
    {
        "role": "system",
        "content": build_episode_instructions(task_frame, context, registry),
    },
    {
        "role": "user",
        "content": build_episode_input(task_frame, context),
    },
]

finish = validate_episode_finish(
    turn.content,
    context=context,
    evidence=tuple(accumulator.evidence),
)
status, draft = finish.status, finish.draft
final_gaps, bindings = finish.gaps, finish.bindings
```

- [ ] **Step 5: Run focused parity tests**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_protocol.py \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_glm_agent_runtime.py
```

Expected: all pass; no prompt, finish, evidence-floor, or recovery regression.

- [ ] **Step 6: Commit Task 1**

```bash
git add intelligence/services/episode_protocol.py \
  intelligence/services/agent_episode.py \
  intelligence/tests/test_episode_protocol.py
git commit -m "refactor: share agent episode protocol"
```

## Task 2: Add explicit runtime identity and composition

**Files:**
- Create: `intelligence/services/agent_runtime_factory.py`
- Modify: `intelligence/services/continuous_turn_adapter.py:75-145`
- Modify: `intelligence/services/continuous_turn_adapter.py:500-558`
- Test: `intelligence/tests/test_agent_runtime_factory.py`
- Test: `intelligence/tests/test_continuous_turn_adapter.py`

- [ ] **Step 1: Write failing factory and artifact tests**

```python
def test_default_factory_preserves_continuous_glm(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_RUNTIME_BACKEND", raising=False)
    selection = resolve_runtime_backend()
    assert selection.name == "continuous_glm"
    assert selection.benchmark_only is False


def test_unknown_backend_fails_without_fallback(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "mystery")
    with pytest.raises(RuntimeError, match="unsupported agent runtime backend"):
        resolve_runtime_backend()


def test_private_artifact_records_explicit_backend(continuous_adapter_fixture) -> None:
    adapter = continuous_adapter_fixture(runtime_name="sdk_glm")
    result = adapter.handle(frame=adapter.frame, control=adapter.control)
    assert result.private_artifact["runtime_backend"] == "sdk_glm"
    assert "sdk_glm" not in result.answer
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_runtime_factory.py \
  intelligence/tests/test_continuous_turn_adapter.py -k 'backend or runtime_identity'
```

Expected: import/signature failures for the missing factory and `runtime_name`.

- [ ] **Step 3: Implement the frozen selection value**

```python
RuntimeBackendName = Literal[
    "continuous_glm",
    "sdk_glm",
    "sdk_gpt",
    "codex_headless",
]


@dataclass(frozen=True)
class RuntimeBackendSelection:
    name: RuntimeBackendName
    benchmark_only: bool


def resolve_runtime_backend(value: str | None = None) -> RuntimeBackendSelection:
    raw = str(value or os.environ.get("AGENT_RUNTIME_BACKEND") or "continuous_glm")
    name = raw.strip().lower()
    if name not in _SUPPORTED:
        raise RuntimeError(f"unsupported agent runtime backend: {name}")
    return RuntimeBackendSelection(
        cast(RuntimeBackendName, name),
        benchmark_only=name == "codex_headless",
    )
```

The creation function accepts injected provider/client dependencies so unit
tests never need credentials. Import SDK/headless modules only inside their
selected branches.

- [ ] **Step 4: Add `runtime_name` to `ContinuousTurnAdapter` composition metadata**

```python
def __init__(
    self,
    *,
    runtime: AgentRuntime,
    semantic_verifier: SemanticVerifier,
    runtime_name: str = "continuous_glm",
) -> None:
    cleaned_name = runtime_name.strip()
    if not cleaned_name:
        raise ValueError("runtime_name must be non-empty")
    self._runtime_name = cleaned_name
```

Add `"runtime_backend": self._runtime_name` to deterministic and episode private
artifacts only. Do not add it to `AgentOutcome` or public answer text.

- [ ] **Step 5: Run focused tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_runtime_factory.py \
  intelligence/tests/test_continuous_turn_adapter.py
git add intelligence/services/agent_runtime_factory.py \
  intelligence/services/continuous_turn_adapter.py \
  intelligence/tests/test_agent_runtime_factory.py \
  intelligence/tests/test_continuous_turn_adapter.py
git commit -m "feat: add explicit agent runtime selection"
```

Expected: all focused tests pass; default behavior remains `continuous_glm`.

## Task 3: Add provider-neutral runtime benchmark records

**Files:**
- Create: `intelligence/eval/runtime_backend_benchmark.py`
- Test: `intelligence/tests/test_runtime_backend_benchmark.py`
- Reuse: `intelligence/eval/capability_monotonicity.py`

- [ ] **Step 1: Write failing immutable-record tests**

```python
def test_runtime_arm_round_trip() -> None:
    arm = RuntimeArmResult(
        case_id="mainline",
        backend="continuous_glm",
        model="glm-5.2",
        answer="当前主线是医药。",
        status="completed",
        structural_status="completed",
        semantic_status="passed",
        task_alignment_score=1.0,
        latency_seconds=10.2,
        provider_attempts=2,
        llm_calls=2,
        tool_calls=3,
        duplicate_queries=0,
        input_tokens=None,
        output_tokens=None,
        protocol_issues=(),
        artifact_sha256="a" * 64,
    )
    assert RuntimeArmResult.from_dict(arm.to_dict()) == arm


def test_summary_requires_every_declared_backend() -> None:
    with pytest.raises(ValueError, match="missing backend results"):
        summarize_runtime_benchmark(
            cases=(case_fixture(),),
            results=(arm_fixture("continuous_glm"),),
            expected_backends=("continuous_glm", "sdk_glm", "codex_headless"),
        )
```

- [ ] **Step 2: Verify import failure**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_runtime_backend_benchmark.py
```

Expected: missing module failure.

- [ ] **Step 3: Implement generic types and summary**

```python
@dataclass(frozen=True)
class RuntimeArmResult:
    case_id: str
    backend: str
    model: str
    answer: str
    status: str
    structural_status: str
    semantic_status: str
    task_alignment_score: float
    latency_seconds: float
    provider_attempts: int
    llm_calls: int
    tool_calls: int
    duplicate_queries: int
    input_tokens: int | None
    output_tokens: int | None
    protocol_issues: tuple[str, ...]
    artifact_sha256: str
```

Validate finite/non-negative metrics, SHA-256 shape, known statuses, unique
`(case_id, backend)` pairs, and complete arm coverage. Reuse
`TaskCapabilityScore`, `directness_score`, `task_coverage_score`,
`grounding_score`, and `control_plane_leak_score`; do not change the historical
`CapabilityRunResult.arm` enum.

- [ ] **Step 4: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_runtime_backend_benchmark.py \
  intelligence/tests/test_capability_monotonicity.py
git add intelligence/eval/runtime_backend_benchmark.py \
  intelligence/tests/test_runtime_backend_benchmark.py
git commit -m "feat: add runtime backend benchmark contract"
```

Expected: new and historical benchmark tests pass.

## Task 4: Implement the run-scoped headless finance tool gateway

**Files:**
- Create: `intelligence/services/headless_tool_gateway.py`
- Test: `intelligence/tests/test_headless_tool_gateway.py`

- [ ] **Step 1: Write failing authorization, budget, and evidence tests**

```python
def test_gateway_executes_only_authorized_registry_tool(gateway_fixture) -> None:
    with gateway_fixture() as gateway:
        result = gateway.call("market_data", "A股最近五日")
        assert result["status"] == "success"
        assert result["evidence_hashes"] == ["market-hash"]
        assert gateway.evidence[0].content_hash == "market-hash"


def test_gateway_rejects_duplicate_query_without_second_execution(
    gateway_fixture,
) -> None:
    with gateway_fixture(max_steps=3) as gateway:
        gateway.call("market_data", "A股最近五日")
        duplicate = gateway.call("market_data", "  A股最近五日  ")
        assert duplicate["status"] == "rejected"
        assert duplicate["error"] == "duplicate_query"
        assert gateway.executed_count == 1


def test_gateway_rejects_after_budget(gateway_fixture) -> None:
    with gateway_fixture(max_steps=1) as gateway:
        gateway.call("market_data", "市场")
        rejected = gateway.call("news_search", "市场新闻")
        assert rejected["error"] == "tool_budget_exhausted"
```

- [ ] **Step 2: Confirm missing module failure**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py
```

- [ ] **Step 3: Implement a loopback-only context manager**

```python
@dataclass(frozen=True)
class HeadlessGatewaySnapshot:
    evidence: tuple[AgentEvidence, ...]
    traces: tuple[ProviderTrace, ...]
    events: tuple[EpisodeEvent, ...]
    executed_count: int
    duplicate_queries: int


class HeadlessToolGateway:
    def __init__(
        self,
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._registry = registry
        self._context = context
        self._is_cancelled = is_cancelled or (lambda: False)
        self._bearer = secrets.token_urlsafe(32)
        self._lock = threading.Lock()
        self._seen: set[tuple[str, str]] = set()
```

Bind `ThreadingHTTPServer(("127.0.0.1", 0), handler)`. Accept only
`POST /tool/<authorized-name>`, require `Authorization: Bearer <run-token>`, parse
`{"query": "A股最近五日"}`, and delegate to `ResearchToolRegistry.execute`. Hold the
state lock while reserving a unique step and budget; execute outside the lock;
publish evidence/traces only if the run is still active and before deadline.

- [ ] **Step 4: Generate a secret-free wrapper command**

The context manager writes an executable under its temporary run directory. Its
body reads endpoint/token from environment and uses `urllib.request`; command
arguments are `tool-name` and `query`. The wrapper never echoes environment
values. Tests assert that response bodies and `HeadlessGatewaySnapshot` contain
no bearer.

- [ ] **Step 5: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_episode_tool_batch.py \
  intelligence/tests/test_p1b_runtime.py -k \
  'query_ledger or registry or gateway or tool_batch'
git add intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_headless_tool_gateway.py
git commit -m "feat: add headless finance tool gateway"
```

Expected: authorization, budget, duplicate, deadline, cancellation, redaction,
and cleanup tests pass.

## Task 5: Implement the Codex headless benchmark adapter

**Files:**
- Create: `intelligence/services/codex_headless_runtime.py`
- Test: `intelligence/tests/test_codex_headless_runtime.py`

- [ ] **Step 1: Write failing fake-process acceptance tests**

```python
def test_headless_runtime_returns_shared_agent_outcome(
    fake_codex_process,
    task_frame,
    research_context,
    research_registry,
) -> None:
    runtime = CodexHeadlessRuntime(
        command_runner=fake_codex_process.valid_finish,
        model="gpt-5.6",
    )
    outcome = runtime.run(
        task_frame=task_frame,
        context=research_context,
        registry=research_registry,
    )
    assert outcome.task_frame_hash == task_frame.task_frame_hash
    assert outcome.status == "completed"
    assert outcome.bindings[0].evidence_hashes == ("market-hash",)


def test_headless_runtime_rejects_non_gateway_command(
    fake_codex_process,
    task_frame,
    research_context,
    research_registry,
) -> None:
    runtime = CodexHeadlessRuntime(
        command_runner=fake_codex_process.with_command("ls -la"),
    )
    outcome = runtime.run(
        task_frame=task_frame,
        context=research_context,
        registry=research_registry,
    )
    assert outcome.status != "completed"
    assert "unauthorized_headless_action" in outcome.gaps
```

- [ ] **Step 2: Confirm import failure**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_codex_headless_runtime.py
```

- [ ] **Step 3: Implement command construction and JSONL parsing**

```python
args = [
    self._codex_bin,
    "exec",
    "--json",
    "--ephemeral",
    "--sandbox",
    "read-only",
    "--ignore-user-config",
    "--skip-git-repo-check",
    "--output-schema",
    str(schema_path),
    "-m",
    self._model,
    "-C",
    str(run_dir),
    prompt,
]
```

Parse one JSON object per stdout line. Accept documented lifecycle types and
extract final agent JSON, token usage, thread ID, command text, exit status, and
error events. Authorized command text must begin with the exact generated
gateway wrapper path after shell tokenization. Reject Web-search, MCP, file
change, and other command items.

- [ ] **Step 4: Convert gateway state and finish into `AgentOutcome`**

Call `validate_episode_finish`, combine the gateway evidence/traces/events, add
the task event first, and return `AgentUsage` with model turns from JSONL usage
and executed finance tools from the gateway. On timeout, non-zero exit, invalid
JSONL, or unauthorized action, return partial/failed with collected evidence and
a stable stop reason.

- [ ] **Step 5: Run fake adapter tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_episode_verifier.py \
  intelligence/tests/test_episode_semantic_verifier.py
```

Expected: valid, malformed, timeout, unauthorized-action, and process-cleanup
cases pass without invoking real Codex.

- [ ] **Step 6: Run one real read-only Codex smoke**

Run a single fixture through an isolated script/test marker with:

```bash
RUN_CODEX_HEADLESS_LIVE=1 \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s \
  intelligence/tests/test_codex_headless_runtime.py::test_real_codex_headless_smoke
```

The opt-in test writes `/tmp/codex-headless-smoke.json`. Expected: the artifact
contains `runtime_backend=codex_headless`, a non-empty answer or
question-specific partial answer, structural/semantic status, Codex CLI/model
identity, gateway evidence, zero unauthorized actions, and no credential text.
An explicit `CODEX_HEADLESS_MODEL` is added only after a separate readiness
probe succeeds for the installed CLI and current ChatGPT account.

- [ ] **Step 7: Commit Task 5**

```bash
git add intelligence/services/codex_headless_runtime.py \
  intelligence/tests/test_codex_headless_runtime.py
git commit -m "feat: add Codex headless benchmark runtime"
```

## Task 6: Add the OpenAI Agents SDK adapter

**Files:**
- Modify: `intelligence/api/requirements.txt`
- Create: `intelligence/services/openai_agents_runtime.py`
- Test: `intelligence/tests/test_openai_agents_runtime.py`

- [ ] **Step 1: Install and record the SDK dependency**

Add one requirement line:

```text
openai-agents==0.18.3
```

Install into the shared Workbench environment and record the resolved version:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pip install \
  'openai-agents==0.18.3'
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pip show \
  openai-agents openai | sed -n '1,60p'
```

Expected: both distributions are installed and `openai-agents` resolves to
`0.18.3`, the version confirmed by `pip index versions` when this plan was
written. If installation reports a dependency conflict, stop before editing
runtime code and record the exact resolver conflict in the task log.

- [ ] **Step 2: Write failing fake-runner tests**

```python
def test_sdk_runtime_exposes_only_authorized_tools(
    fake_sdk_runner,
    task_frame,
    research_context,
    research_registry,
) -> None:
    runtime = OpenAIAgentsRuntime(runner=fake_sdk_runner)
    runtime.run(
        task_frame=task_frame,
        context=research_context,
        registry=research_registry,
    )
    assert fake_sdk_runner.tool_names == set(
        spec.name
        for spec in research_registry.authorized_specs(
            research_context.contract.allowed_capabilities
        )
    )


def test_sdk_runtime_enforces_finance_tool_budget(
    fake_sdk_runner,
    task_frame,
    one_step_research_context,
    research_registry,
) -> None:
    fake_sdk_runner.request_tools("market_data", "news_search")
    outcome = OpenAIAgentsRuntime(runner=fake_sdk_runner).run(
        task_frame=task_frame,
        context=one_step_research_context,
        registry=research_registry,
    )
    assert outcome.usage.tool_calls == 1
    assert "tool_budget_exhausted" in outcome.gaps
```

The `one_step_research_context` fixture constructs a `ResearchPolicy` with
`max_steps=1` and the same contract/deadline as `research_context`.

- [ ] **Step 3: Confirm failures before implementation**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_openai_agents_runtime.py
```

- [ ] **Step 4: Implement SDK-local run state and generated tools**

```python
@dataclass
class AgentsRunState:
    task_frame: TaskFrame
    research_context: ResearchRunContext
    registry: ResearchToolRegistry
    evidence: list[AgentEvidence] = field(default_factory=list)
    traces: list[ProviderTrace] = field(default_factory=list)
    events: list[EpisodeEvent] = field(default_factory=list)
    seen_queries: set[tuple[str, str]] = field(default_factory=set)
    successful_episode_tools: set[str] = field(default_factory=set)
    executed_tools: int = 0
    invalid_actions: int = 0
    next_sequence: int = 2
    lock: threading.Lock = field(default_factory=threading.Lock)
```

Generate one `FunctionTool` per authorized `ToolSpec`. Each callback validates
`query`, atomically reserves budget/query/snapshot identity, executes
`registry.execute`, records evidence/traces/events, and returns a JSON object
containing public observation, evidence hashes, gaps, and status. Configure local
function-tool concurrency to one for this baseline.

- [ ] **Step 5: Implement `sdk_glm` and `sdk_gpt` model factories**

```python
def build_glm_sdk_model(*, api_key: str, base_url: str, model: str):
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return OpenAIChatCompletionsModel(model=model, openai_client=client)


def build_gpt_sdk_model(model: str = "gpt-5.6-sol") -> str:
    return model
```

GLM settings use temperature zero, one local tool at a time, and
`extra_body={"thinking": {"type": "disabled"}}`; SDK trace export is disabled.
GPT uses the Responses path, `Reasoning(effort="high")`, verbosity medium,
parallel tool emission disabled for the first baseline, and `store=False`.

- [ ] **Step 6: Implement runner result conversion**

Use `build_episode_instructions` and `build_episode_input`. For GLM, parse final
JSON text; for GPT, allow the SDK structured output generated from the shared
schema. In both cases call `validate_episode_finish`, build one `AgentOutcome`,
and never call a fallback runtime.

- [ ] **Step 7: Run offline SDK tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_openai_agents_runtime.py \
  intelligence/tests/test_agent_runtime.py \
  intelligence/tests/test_episode_verifier.py
```

Expected: provider factories, tool allowlist, budget, duplicate-query, partial
finish, invalid output, cancellation, deadline, and outcome tests pass.

- [ ] **Step 8: Run a live `sdk_glm` smoke without printing the key**

```bash
FORESIGHT_BUILTIN_LLM_API_KEY="$(security find-generic-password \
  -a a77 -s finance-workbench-glm -w)" \
FORESIGHT_BUILTIN_LLM_BASE_URL="https://open.bigmodel.cn/api/coding/paas/v4" \
FORESIGHT_BUILTIN_LLM_MODEL="glm-5.2" \
AGENT_RUNTIME_BACKEND="sdk_glm" \
RUN_OPENAI_AGENTS_LIVE=1 \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s \
  intelligence/tests/test_openai_agents_runtime.py::test_real_sdk_glm_smoke
```

The opt-in test writes `/tmp/sdk-glm-smoke.json`. Expected: the shared verifier
runs, the artifact contains no secret, and no legacy runtime fallback appears.

- [ ] **Step 9: Commit Task 6**

```bash
git add intelligence/api/requirements.txt \
  intelligence/services/openai_agents_runtime.py \
  intelligence/tests/test_openai_agents_runtime.py
git commit -m "feat: add OpenAI Agents SDK runtime"
```

## Task 7: Wire explicit backends into the Workbench composition root

**Files:**
- Modify: `intelligence/services/agent_runtime_factory.py`
- Modify: `intelligence/api/app.py:100-160`
- Modify: `intelligence/api/app.py:1177-1280`
- Test: `intelligence/tests/test_workbench_api.py`
- Test: `intelligence/tests/test_workbench_conversation_integration.py`

- [ ] **Step 1: Write failing readiness and no-fallback tests**

```python
def test_health_reports_selected_runtime_backend(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "sdk_glm")
    monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_API_KEY", "test-glm-key")
    with TestClient(app_module.create_app(repo_root=tmp_path)) as client:
        health = client.get("/api/health").json()
    assert health["runtime"]["agent_runtime"]["backend"] == "sdk_glm"
    assert health["runtime"]["agent_runtime"]["ready"] is True
    assert "test-glm-key" not in json.dumps(health)


def test_missing_gpt_key_fails_sdk_gpt_readiness(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "sdk_gpt")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app_module.create_app(repo_root=tmp_path)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["runtime"]["agent_runtime"]["ready"] is False
    assert response.json()["runtime"]["agent_runtime"]["reason"] == (
        "openai_api_key_missing"
    )
```

- [ ] **Step 2: Verify focused failures**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_api.py -k 'agent_runtime or sdk_gpt'
```

- [ ] **Step 3: Build the selected runtime once per turn**

Replace the hard-coded `GLMModelClient -> GLMAgentRuntime` block in
`_build_continuous_turn_adapter` with a factory call. Pass the returned runtime
and label into `ContinuousTurnAdapter`. Keep the semantic verifier explicit and
shared; for each model backend, construct a compatible judge client but do not
let the runtime publish without semantic verification.

- [ ] **Step 4: Add secret-free readiness metadata**

```python
"agent_runtime": {
    "backend": selection.name,
    "ready": runtime_readiness.ready,
    "reason": runtime_readiness.reason,
    "model": runtime_readiness.model,
    "credential_available": runtime_readiness.credential_available,
    "benchmark_only": selection.benchmark_only,
}
```

No endpoint returns a key, base-url credential parameter, headless bearer, or
provider object.

- [ ] **Step 5: Run API and conversation tests, then commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_workbench_conversation_integration.py \
  intelligence/tests/test_conversation_orchestrator.py
git add intelligence/services/agent_runtime_factory.py \
  intelligence/api/app.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_workbench_conversation_integration.py
git commit -m "feat: compose selectable agent runtimes"
```

Expected: default tests remain on Continuous Episode; explicit SDK/headless
fixtures traverse the same conversation and Run protocol.

## Task 8: Build the frozen multi-backend benchmark runner

**Files:**
- Create: `intelligence/tests/fixtures/runtime_backend_cases.json`
- Create: `scripts/run_agent_runtime_benchmark.py`
- Test: `intelligence/tests/test_run_agent_runtime_benchmark.py`

- [ ] **Step 1: Add the frozen nine-case fixture**

The JSON contains the existing five cases plus these runtime cases:

```json
{
  "id": "theme-comparison",
  "question": "低空经济和商业航天，未来一个月哪个更可能成为A股主线，为什么",
  "as_of": "2026-07-24",
  "tier": "standard",
  "timeout": 180.0,
  "required_outputs": ["comparison_conclusion", "supporting_evidence", "counterpoint", "invalidation_conditions"]
}
```

```json
{
  "id": "counterfactual-mainline",
  "question": "如果电力板块涨停家数很多但成交占比和核心股承接下降，还能算主线吗",
  "as_of": "2026-07-24",
  "tier": "standard",
  "timeout": 180.0,
  "required_outputs": ["direct_assessment", "causal_chain", "counterpoint", "verification_conditions"]
}
```

```json
{
  "id": "unfamiliar-methodology",
  "question": "一个没有历史胜率的新题材，应该如何判断它是主线候选还是一天噪音",
  "as_of": "2026-07-24",
  "tier": "standard",
  "timeout": 180.0,
  "required_outputs": ["method", "evidence_hierarchy", "failure_modes", "verification_path"]
}
```

```json
{
  "id": "contextual-follow-up",
  "question": "那它什么时候算失效",
  "conversation_context": [
    {"role": "user", "content": "昨天的反弹能持续多久"},
    {"role": "assistant", "content": "基准判断是短周期修复。"}
  ],
  "as_of": "2026-07-24",
  "tier": "standard",
  "timeout": 180.0,
  "required_outputs": ["invalidation_conditions", "supporting_evidence"]
}
```

- [ ] **Step 2: Write failing dry-run and atomic-artifact tests**

```python
def test_dry_run_freezes_one_task_frame_per_case_and_all_backends(tmp_path) -> None:
    output = tmp_path / "plan.json"
    code = benchmark.main([
        "--dry-run",
        "--backend", "continuous_glm",
        "--backend", "sdk_glm",
        "--backend", "codex_headless",
        "--questions-file", str(FIXTURE),
        "--output", str(output),
    ])
    assert code == 0
    payload = json.loads(output.read_text())
    assert payload["expected_backends"] == [
        "continuous_glm", "sdk_glm", "codex_headless"
    ]
    assert all(case["task_frame_hash"] for case in payload["cases"])
```

- [ ] **Step 3: Implement the runner around existing composition helpers**

For each case, run `TurnControlCore` once to freeze the frame. For each backend,
create a fresh `ResearchRunContext` and registry from the same frame/capabilities,
invoke the selected `AgentRuntime`, then run `verify_episode_outcome` and
`SemanticEpisodeVerifier`. Record raw/private artifacts separately from the
public benchmark JSON; write the summary atomically with `_atomic_write_json`.

- [ ] **Step 4: Add no-cross-arm and deterministic-fast-path assertions**

The runner must not pass an earlier arm's answer into a later arm. For
`index-rebound-space`, assert every backend record has
`execution_kind=deterministic_fast_path`, zero runtime LLM calls, and the same
answer hash.

- [ ] **Step 5: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_run_agent_runtime_benchmark.py \
  intelligence/tests/test_runtime_backend_benchmark.py \
  intelligence/tests/test_agent_episode_ab.py
git add intelligence/tests/fixtures/runtime_backend_cases.json \
  scripts/run_agent_runtime_benchmark.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py
git commit -m "feat: add three-runtime benchmark runner"
```

## Task 9: Verify isolated Workbench Run/SSE/UI behavior

**Files:**
- Modify: `docs/workbench/local-site.md`
- Create: `docs/verification/agent-runtime-backends-2026-07-25.md`
- Verify: existing frontend tests and built assets

- [ ] **Step 1: Run the full focused backend suite**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_protocol.py \
  intelligence/tests/test_agent_runtime_factory.py \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_openai_agents_runtime.py \
  intelligence/tests/test_runtime_backend_benchmark.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py \
  intelligence/tests/test_workbench_conversation_integration.py
```

Expected: all pass.

- [ ] **Step 2: Build clean detached runtimes for isolated ports**

Create clean detached runtime directories from the current candidate commit.
Launch:

- 8795 control: `AGENT_RUNTIME_BACKEND=continuous_glm`;
- 8796 SDK: `AGENT_RUNTIME_BACKEND=sdk_glm`;
- 8797 reference: `AGENT_RUNTIME_BACKEND=codex_headless` and explicit benchmark enable flag.

Inject the GLM key from Keychain only in the launch command environment. Do not
write it to a plist, shell script, log, or report.

- [ ] **Step 3: Verify health provenance on all three ports**

```bash
for port in 8795 8796 8797; do
  curl -fsS "http://127.0.0.1:$port/api/health" | jq \
    '{status, revision:.runtime.source_revision, dirty:.runtime.source_dirty, backend:.runtime.agent_runtime}'
done
```

Expected: healthy, identical clean revision/data root, and distinct explicit
backend labels. 8797 must report `benchmark_only=true`.

- [ ] **Step 4: Run one Conversation API/SSE case on each port**

Submit the same `目前市场的主线是什么` message, consume SSE through terminal
state, then inspect Run and answer artifacts. Assert:

- one terminal event;
- the same TaskFrame hash and required outputs;
- backend-specific private identity only;
- structural and semantic verifier artifacts exist;
- no control-plane text appears in the answer;
- UI report opens and renders answer, citations, and run details.

- [ ] **Step 5: Run frontend validation**

```bash
cd frontend
pnpm test --run
pnpm lint
pnpm typecheck
pnpm build
```

Expected: all pass. Use browser inspection for the three real runs; do not infer
UI correctness from API JSON alone.

- [ ] **Step 6: Document run commands and commit**

Add backend environment variables, benchmark-only warning, credential rules,
and rollback instructions to `docs/workbench/local-site.md`. Begin the
verification report with exact commits, ports, PIDs, code/data roots, dependency
versions, and focused test results.

```bash
git add docs/workbench/local-site.md \
  docs/verification/agent-runtime-backends-2026-07-25.md
git commit -m "docs: verify isolated agent runtime backends"
```

## Task 10: Run real A/B, blind-review answers, and complete the audit

**Files:**
- Create under gitignored runtime artifact root: one raw benchmark JSON and one blinded answer packet
- Modify: `docs/verification/agent-runtime-backends-2026-07-25.md`
- Modify: `/Users/a77/agent-memory/20_projects/finance-workspace-private.md`

- [ ] **Step 1: Run the same fixture through all available arms**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/run_agent_runtime_benchmark.py \
  --backend continuous_glm \
  --backend sdk_glm \
  --backend codex_headless \
  --questions-file intelligence/tests/fixtures/runtime_backend_cases.json \
  --output /Users/a77/.finance-runtime/evals/agent-runtime-backends-2026-07-25.json
```

When `OPENAI_API_KEY` is available, run a second frozen artifact adding
`--backend sdk_gpt`; do not change fixture, prompts, timeouts, or scoring between
the two runs.

- [ ] **Step 2: Validate artifact completeness before reading answers**

Run the benchmark validator and assert every `(case, backend)` record has answer
or question-specific partial text, status, structural/semantic status, task
alignment, latency, attempts, tools, duplicate count, protocol issues, and SHA.
Reject the artifact if an arm silently fell back or a non-fast-path arm has no
runtime identity.

- [ ] **Step 3: Generate a blinded review packet**

Randomly map backend names to A/B/C per case with a saved seed. Include question,
conversation context, public answer, citations, and data cutoff. Exclude runtime
name, model, latency, internal traces, and execution order from the reviewer
packet.

- [ ] **Step 4: Read and score every core answer**

Score 0-4 for directness, completeness, analytical synthesis, uncertainty,
usefulness, and naturalness. Record pairwise winner and a one-sentence reason.
Flag any answer that is technically verified but does not answer the question.
Do not use the deterministic scorer as a substitute for this pass.

- [ ] **Step 5: Complete the requirement-by-requirement report**

The report table must cover:

- three runtime implementations;
- same tool whitelist and budgets;
- same structural and semantic verifier;
- same evaluation set;
- same Run/SSE/UI protocol;
- real answer quality;
- latency/calls/tokens/cost where available;
- security and control-plane leakage;
- full Python/frontend regression;
- `main`, 8792, and canonical symlink unchanged.

Classify each as proved, contradicted, incomplete, or missing. Recommend a
production backend only from proved evidence; list what still separates it from
Codex headless.

- [ ] **Step 6: Run full regression**

```bash
env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER \
  -u SUBCONSCIOUS_VAULT -u AGENT_MEMORY_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
cd frontend && pnpm test --run && pnpm lint && pnpm typecheck && pnpm build
```

Expected: Python and frontend suites pass with no new failure. Record exact
counts and pre-existing exclusions in the report.

- [ ] **Step 7: Record project-level handoff and commit**

Append only the stable architecture decision, candidate commit, runtime ports,
test totals, benchmark conclusion, and remaining production gate to the project
memory. Do not paste answer transcripts or secrets.

```bash
git add docs/verification/agent-runtime-backends-2026-07-25.md
git commit -m "docs: conclude agent runtime backend evaluation"
git status --short
git log --oneline --decorate -12
```

Expected: repository worktree is clean; branch is not merged or pushed unless
the user separately requests it; 8792 and canonical runtime remain untouched.

## Final completion gate

Do not claim the objective complete until Task 10 proves every design-spec item.
An unavailable `sdk_gpt` live run is an incomplete objective, even if `sdk_glm`
and headless are green. Continue with all independent work while the credential
is unavailable, then run the frozen GPT arm without changing the experiment.

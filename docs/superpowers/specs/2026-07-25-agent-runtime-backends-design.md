# Agent Runtime Backends Design

Date: 2026-07-25  
Status: approved direction; implementation pending  
Base: `fix/agent-harness-monotonicity@8270768159fa464fb79c61d60f6d2a31335b8706`  
Implementation branch: `feat/agent-runtime-backends`

## 1. Objective

Build and compare three execution implementations for the Finance Workbench:

1. the existing self-built Continuous Episode using the current GLM-compatible
   provider;
2. an OpenAI Agents SDK runtime, first exercised against the same GLM model and
   later against an OpenAI GPT model;
3. a Codex headless runtime used only as a quality-reference arm.

All three implementations must consume the same immutable task semantics,
authorized finance tools, deadlines, evidence requirements, structural verifier,
semantic verifier, Run artifacts, SSE events, and Workbench UI projection. The
comparison must distinguish runtime or harness effects from model effects and
must include human review of the actual answers.

This work remains isolated. It does not merge into `main`, change canonical 8792,
or make Codex headless a production dependency.

## 2. First-principles problem statement

The product question is not whether a provider can return valid JSON. It is
whether a stronger execution harness improves the probability that the user's
real task is answered while preserving the repository's truth and permission
constraints.

The experiment therefore freezes five independent variables:

- **task semantics**: one `TaskFrame` and one `task_frame_hash`;
- **capability surface**: one `ResearchToolRegistry` allowlist;
- **resource limits**: one `ResearchRunContext`, deadline, and tool-call budget;
- **truth boundary**: one structural verifier followed by one semantic verifier;
- **product boundary**: one `ContinuousTurnResult` and one Run/SSE/UI projection.

Only the model runtime is allowed to vary. A runtime may own its internal model
conversation and tool-call transport, but it may not rewrite the task, add tools,
raise budgets, bypass evidence bindings, or publish directly to the UI.

## 3. Existing assets and authoritative seams

The current branch already contains the correct external seam:

```python
class AgentRuntime(Protocol):
    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> AgentOutcome: ...
```

Authoritative modules:

- `intelligence/services/task_frame.py`: immutable user-task semantics;
- `intelligence/services/research_contract.py`: deadline, policy, required
  outputs, and capability authorization;
- `intelligence/services/research_tool_registry.py`: typed read-only finance
  tools and evidence-producing execution;
- `intelligence/services/agent_runtime.py`: provider-neutral model turns,
  events, evidence bindings, usage, and `AgentOutcome`;
- `intelligence/services/continuous_turn_adapter.py`: deterministic fast-path
  selection, runtime invocation, shared structural/semantic verification, and
  public projection;
- `intelligence/services/episode_verifier.py`: structural task/evidence gate;
- `intelligence/services/episode_semantic_verifier.py`: sentence-level semantic
  grounding and bounded repair;
- `intelligence/services/episode_tools.py`: the canonical registry composition;
- `intelligence/services/glm_agent_runtime.py` and
  `intelligence/services/agent_episode.py`: current Continuous Episode adapter
  and implementation.

No `AgentRuntimeBackend`, `RuntimeRequest`, or `RuntimeOutcome` wrapper will be
added. Such a wrapper would repeat the existing interface and create a second
place for deadlines, traces, and task identity to diverge.

## 4. Alternatives considered

### 4.1 Replace Continuous Episode directly with Agents SDK

This has the smallest visible product surface, but it confounds runtime and model
changes, removes the GLM control arm, and makes rollback or causal comparison
difficult. Rejected.

### 4.2 Keep one `AgentRuntime` seam with three adapters

Selected. Each adapter owns provider-specific execution but returns the same
`AgentOutcome`. Existing deterministic routes, verifiers, and UI remain outside
the varying implementation. This creates a real seam because three adapters will
exercise it.

### 4.3 Use Codex headless as the production backend

This is closest to the interactive Codex experience, but it couples the product
to local Codex authentication, CLI lifecycle, subscription policy, and a broad
coding-agent tool surface. It is useful as a reference implementation, not as
the shipped finance runtime. Rejected for production and retained for benchmark
use only.

## 5. Target architecture

```text
TurnControlCore
  -> clarification
  -> deterministic fast path (unchanged, zero LLM where applicable)
  -> ContinuousTurnAdapter
       -> AgentRuntime.run(TaskFrame, ResearchRunContext, ResearchToolRegistry)
            -> ContinuousEpisodeRuntime
            -> OpenAIAgentsRuntime
            -> CodexHeadlessRuntime [benchmark only]
       -> AgentOutcome
       -> verify_episode_outcome
       -> SemanticEpisodeVerifier
       -> ContinuousTurnResult
       -> existing Orchestrator / Run artifact / SSE / UI
```

`ContinuousTurnAdapter` remains the sole product adapter. Runtime selection is a
composition-root concern, not a routing decision made by the LLM or route table.

## 6. Shared episode protocol

The existing Continuous Episode embeds its instructions, task input, finish JSON
shape, and finish validation inside `ContinuousAgentEpisode`. Reusing those
private methods from new adapters would couple them to one implementation;
copying them would create contract drift.

Create `intelligence/services/episode_protocol.py` as a deep module with this
small interface:

```python
@dataclass(frozen=True)
class EpisodeFinish:
    status: Literal["completed", "partial"]
    draft: str
    gaps: tuple[str, ...]
    bindings: tuple[OutputEvidenceBinding, ...]

def build_episode_instructions(
    task_frame: TaskFrame,
    context: ResearchRunContext,
    registry: ResearchToolRegistry,
) -> str: ...

def build_episode_input(
    task_frame: TaskFrame,
    context: ResearchRunContext,
) -> str: ...

def finish_json_schema() -> dict[str, object]: ...

def validate_episode_finish(
    value: object,
    *,
    context: ResearchRunContext,
    evidence: tuple[AgentEvidence, ...],
) -> EpisodeFinish: ...
```

The implementation hides valuation-specific evidence floors, required-output
substance checks, evidence-hash validation, normalization, and JSON schema
details. Continuous Episode, Agents SDK, and Codex headless all use this module.

The protocol describes outcomes and invariants, not a prescribed sequence of
research steps. It retains the current outcome-first prompt, tool descriptions,
evidence restrictions, and stopping conditions while leaving query choice and
iteration to the runtime.

## 7. Adapter A: Continuous Episode control arm

The current `GLMAgentRuntime` remains behaviorally unchanged and satisfies
`AgentRuntime`. It is the control arm for both regression and causal comparison.

Only two refactors are allowed in this adapter:

- replace private prompt construction with `episode_protocol` calls;
- replace private finish parsing with `validate_episode_finish`.

Tests must prove byte-equivalent prompt/task inputs and equivalent finish
acceptance before the extraction is accepted. Runtime loop ownership, parallel
tool batching, recovery, and GLM provider behavior are not rewritten in this
phase.

## 8. Adapter B: OpenAI Agents SDK

### 8.1 Purpose

`OpenAIAgentsRuntime` tests whether a maintained agent runner improves tool-loop
continuity, state handling, lifecycle observability, and recovery compared with
the self-built loop.

The official SDK provides a runner-managed model/tool loop, function tools,
streaming, context injection, sessions, guardrails, and tracing. This phase uses
only the runner, function tools, local context, hooks, and structured output.
Handoffs, multi-agent delegation, durable sessions, hosted tools, shell, and
computer use remain disabled.

### 8.2 Two provider modes, one SDK adapter

The adapter supports two explicit model configurations:

1. **`sdk_glm` experimental control**
   - use `AsyncOpenAI` with the existing GLM OpenAI-compatible base URL and
     Keychain-injected key;
   - use `OpenAIChatCompletionsModel` with model `glm-5.2`;
   - disable OpenAI trace export because there is no OpenAI API key;
   - preserve temperature zero and the provider-specific disabled-thinking body;
   - purpose: vary the harness while keeping the model approximately fixed.
2. **`sdk_gpt` candidate production arm**
   - use the OpenAI Responses path;
   - default explicit model `gpt-5.6-sol`, configurable by environment;
   - start at `reasoning.effort="high"`, record it in the private artifact, and
     do not raise it until representative evals justify the change;
   - use `store=False` for the initial isolated run and do not add persisted
     cross-turn reasoning;
   - purpose: measure the combined SDK plus GPT capability after the harness
     experiment is understood.

The current environment has a usable GLM Keychain item but no
`OPENAI_API_KEY`. Therefore implementation and offline GPT adapter tests can
complete immediately; live GPT SDK A/B requires a separately injected OpenAI
credential. No secret is written to the repository or artifact.

### 8.3 Tool adaptation

Function tools are generated only from
`registry.authorized_specs(context.contract.allowed_capabilities)`. Every tool
has exactly one public argument, `query: str`, matching the existing registry.

An SDK-local run state owns:

- the immutable `TaskFrame` and `ResearchRunContext` references;
- the registry reference;
- collected `AgentEvidence` and `ProviderTrace` values;
- normalized query and episode-snapshot deduplication;
- reserved and completed tool-call counts;
- ordered `EpisodeEvent` values;
- cancellation and deadline checks.

The SDK may schedule callbacks, but the host state atomically enforces the same
`max_steps`, capability allowlist, duplicate-query rule, episode-snapshot rule,
and deadline as Continuous Episode. Tool errors are returned to the same SDK run
as observations. They do not trigger a legacy pipeline.

The first live baseline sets local function-tool concurrency to one to avoid
introducing a second, unverified budget scheduler. A later experiment may enable
bounded SDK concurrency only after tests prove atomic budget reservation,
deterministic event ordering, ContextVar propagation, and QueryLedger behavior.

### 8.4 Structured completion

Both provider modes use the shared finish schema and always run
`validate_episode_finish` before constructing `AgentOutcome`. The first
`sdk_glm` baseline asks for the JSON envelope in instructions and parses the
returned text, matching the existing Continuous Episode contract; an
OpenAI-compatible provider is not assumed to implement strict structured
outputs merely because it implements Chat Completions. `sdk_gpt` may use the
SDK `output_type` generated from the same schema after an offline capability
test proves the transport supports it. This is a transport optimization, not a
different outcome contract.

SDK guardrails may reject malformed protocol output, but they never replace the
finance structural or semantic verifier.

`max_turns` is a model-turn safety fuse, not the finance tool budget. The finance
budget remains `ResearchPolicy.max_steps`; deadline expiration or budget
exhaustion produces a partial outcome with explicit gaps.

### 8.5 Tracing

SDK hooks project lifecycle events into the repository's `EpisodeEvent` and
`ProviderTrace` forms. Raw SDK/OpenAI objects and hidden reasoning never cross
the `AgentRuntime` seam. Sensitive model or tool payload tracing is disabled by
default. OpenAI trace IDs may be recorded as secret-free identifiers when an
OpenAI credential is configured.

## 9. Adapter C: Codex headless quality reference

### 9.1 Isolation

`CodexHeadlessRuntime` runs `codex exec` in a newly created temporary directory,
not in the finance repository. It uses:

```text
codex exec
  --json
  --ephemeral
  --sandbox read-only
  --ignore-user-config
  --skip-git-repo-check
  --output-schema <shared-finish-schema>
  [-m <readiness-proven-codex-model>]
```

The default model is the Codex account's supported CLI default. An explicit
`CODEX_HEADLESS_MODEL` may be used for reproducible benchmarks only after a
readiness probe proves that the installed CLI and current ChatGPT account both
support it. The exact CLI version, requested model or account-default label,
and reasoning effort are recorded in the private artifact. This distinction is
required because the current local CLI rejects the API model slug `gpt-5.6`
under ChatGPT account authentication even though the API documentation lists
GPT-5.6 as the current API flagship.

The adapter consumes JSONL events, not human-formatted terminal output. It
captures the thread ID, model usage, tool/command lifecycle, terminal state,
and final structured response. A child-process timeout is bounded by the same
root deadline, with a termination grace period.

### 9.2 Finance tool gateway

The headless process must not inspect the repository or database directly.
The parent adapter starts a loopback-only, run-scoped tool gateway backed by the
same in-memory `ResearchToolRegistry` and `ResearchRunContext`.

The temporary directory contains one generated wrapper executable that:

- accepts only an authorized tool name and one query;
- reads the random loopback endpoint and ephemeral bearer from environment;
- sends a request to the parent gateway;
- prints only the public observation, evidence hashes, gaps, and error status.

The parent gateway owns authorization, normalized-query deduplication,
episode-snapshot deduplication, step count, deadline checks, evidence, traces,
and ordered events. The ephemeral bearer is never written to the Run artifact
or final answer.

This transport is deliberately not a second finance implementation. The gateway
delegates to `ResearchToolRegistry.execute()` and returns its `ToolObservation`.

### 9.3 Tool-surface audit

Codex still has a general shell tool. The adapter therefore audits every JSONL
item. An accepted run may execute only the generated finance wrapper command.
Built-in Web search, arbitrary shell commands, file reads, MCP calls, or edits
produce a protocol issue and prevent `completed` acceptance.

This creates hard enforcement at the adapter and verifier boundaries rather
than relying only on prompt obedience. Even if the model mentions an unsupported
fact, the shared finish validator and semantic verifier cannot upgrade it into
accepted evidence.

### 9.4 Product boundary

Headless remains disabled in the normal Workbench composition root unless an
explicit benchmark-only flag is present. It is never selected by user intent,
route table, or automatic provider fallback. Headless failure returns its own
partial or failed outcome; it cannot fall through to another runtime and make
the A/B result ambiguous.

## 10. Runtime composition and identity

Create `intelligence/services/agent_runtime_factory.py`. Its interface accepts
an explicit backend name and already-resolved provider configuration, then
returns an `AgentRuntime` plus a secret-free runtime label.

Supported labels:

- `continuous_glm`;
- `sdk_glm`;
- `sdk_gpt`;
- `codex_headless`.

Production defaults remain unchanged. `continuous_glm` is selected unless an
isolated process explicitly sets `AGENT_RUNTIME_BACKEND`. Unknown or unavailable
backends fail startup readiness; they do not silently fall back.

`ContinuousTurnAdapter` receives the runtime label as composition metadata and
records it in private artifacts and metrics. It does not add a method to the
`AgentRuntime` interface and does not expose the label in answer prose.

For real A/B, run separate isolated processes:

- current 8795: `continuous_glm` control;
- isolated 8796: `sdk_glm`, then `sdk_gpt` when credentials exist;
- isolated 8797: `codex_headless` benchmark.

The health endpoint reports backend, source revision, dirty state, code root,
finance data root, model label, and credential availability as booleans. It
never returns credentials.

## 11. Budget, state, and trace invariants

Every backend must satisfy these invariants:

1. `task_frame_hash` is identical at runtime entry, every episode event, outcome,
   structural verification, and public artifact.
2. `ResearchPolicy.max_steps` counts executed finance tool calls, not model turns,
   SDK callbacks, subprocess commands, retries, or verifier calls.
3. One root deadline is allocated once by `ContinuousTurnAdapter`; a backend may
   consume but never recreate or extend it.
4. Verification reserve remains outside runtime research consumption.
5. A normalized `(tool, query)` is executed once per run; episode-snapshot tools
   succeed at most once.
6. `ProviderTrace` values originate from the canonical registry execution. SDK
   and headless lifecycle events are additional runtime events, not substitute
   provider traces.
7. Evidence hashes originate only from `AgentEvidence` returned by authorized
   finance tools.
8. A runtime cannot mark an output completed merely because its model emitted a
   final response. Completion is decided after shared structural and semantic
   verification.
9. Cancellation is monotonic: once cancelled, no later result may be published.
10. A backend failure never invokes another backend inside the same recorded arm.

## 12. Run, SSE, and UI contract

The existing public path remains:

```text
AgentOutcome
  -> ContinuousTurnResult
  -> TurnOrchestrator
  -> Answer artifact / Report artifact
  -> RunStore
  -> SSE
  -> existing React message and run-detail views
```

No backend writes a UI message, report, or RunStore record directly. Public
progress remains sparse and outcome-oriented. Backend-specific details appear
only in the existing advanced/private artifact projection after redaction.

The first phase does not add a runtime dropdown. Separate ports make the
comparison explicit and prevent a user-visible control from becoming a hidden
routing source before the experiment selects a production backend.

## 13. Benchmark and evaluation design

### 13.1 Frozen input set

Retain the five historical regression cases:

- `昨天的反弹能持续多久`;
- `科创50你认为反弹空间有多少`;
- `瑞华泰的合理估值`;
- `这一周行情下跌的主要原因是什么`;
- `目前市场的主线是什么`.

The 科创50 case is expected to stay on the deterministic fast path and proves
that a runtime backend cannot steal a head-route task. Add at least four genuine
runtime cases covering comparison, counterfactual reasoning, unfamiliar
methodology, and contextual follow-up. Each case freezes conversation context,
as-of date, tier, timeout, and expected task-level outputs.

### 13.2 Generic arm schema

The existing `ThreeArmRecord` is historically fixed to
`bare/current/episode`; changing its enum would alter old evidence. Add a new
generic benchmark record rather than weakening that contract:

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

The benchmark runner iterates an explicit backend list, constructs a fresh
context and registry for each arm, and writes one atomic JSON artifact. It never
changes 8792 or reads answers from another arm during execution.

### 13.3 Evaluation dimensions

Machine checks:

- stable task-frame and contract hashes;
- required-output fulfillment;
- structural and semantic status consistency;
- unsupported numeric or causal claims;
- control-plane leakage;
- evidence freshness and relevance;
- duplicate queries and unauthorized tools;
- template signature similarity;
- latency, LLM attempts, tool calls, and token usage;
- deterministic fast-path invariance.

Human blind review:

- directness: does the first paragraph answer the user's real question?;
- completeness: are the requested judgment and reasons present?;
- analytical quality: does the answer synthesize rather than list evidence?;
- uncertainty handling: are gaps precise without replacing the answer?;
- usefulness: are continuation, invalidation, or verification conditions usable?;
- naturalness: does it read like one competent analyst rather than a template?;
- preference: pairwise winner and reason, with backend names hidden.

Tests and verifier status are necessary but cannot substitute for reading every
answer in the core set.

### 13.4 Acceptance gates

An SDK backend is a production candidate only if all are true:

- zero unauthorized tool or control-plane leakage failures;
- zero verifier-accepted unsupported precise claims in the reviewed core set;
- no answer is downgraded to an unrelated template;
- all non-fast-path cases produce a direct judgment or a question-specific,
  evidence-backed partial answer;
- median human task score is not below `continuous_glm` by more than 0.05 on the
  normalized scale;
- pairwise preference is at least tied with `continuous_glm`;
- p95 latency and token/call cost are reported, not hidden;
- the full existing Workbench test suite and frontend checks remain green.

Codex headless has no production gate. It supplies a reference score and a gap
analysis: which answer qualities the SDK or Continuous runtime still fails to
match.

## 14. Error handling

- Missing SDK package: selected SDK backend fails readiness with a specific
  dependency error; other explicitly selected arms are unaffected.
- Missing OpenAI key: `sdk_gpt` fails readiness; `sdk_glm` and headless remain
  independently runnable.
- Provider timeout: return partial/failed with collected evidence; do not invoke
  another backend.
- SDK `MaxTurnsExceeded`: translate to partial with current evidence and a model
  turn-limit gap.
- Invalid structured finish: allow one protocol repair within the existing
  deadline, then return partial.
- Headless process timeout: terminate, wait a bounded grace period, kill if
  needed, and preserve collected gateway evidence.
- Headless non-zero exit or malformed JSONL: record protocol failure and stderr
  tail after secret redaction.
- Unauthorized headless action: reject completed status even if the prose is
  good.
- Semantic verifier unavailable: preserve the existing fail-closed projection;
  a stronger runtime cannot bypass truth verification.

## 15. Security and privacy

- No API key, Keychain value, bearer, auth file, or raw provider object is
  committed or written to Run artifacts.
- The headless gateway binds only to `127.0.0.1`, uses a per-run random bearer,
  rejects unknown methods/tools, and shuts down after the subprocess.
- Codex runs in a temporary directory with read-only sandbox and ephemeral
  session persistence.
- SDK tracing excludes sensitive model/tool payloads by default. Non-OpenAI GLM
  mode disables OpenAI trace export.
- All private artifacts pass the existing redaction function before storage or
  UI projection.
- No backend exposes filesystem write, arbitrary SQL, shell, computer use, or
  external mutation to the finance model.

## 16. Dependency strategy

Add `openai-agents` to the Workbench API runtime dependency set only when the SDK
adapter is implemented. Pin `openai-agents==0.18.3`, the current package version
confirmed during planning, and record the resolved SDK/OpenAI versions in the
isolated runtime. Do not vendor the SDK.

The headless adapter uses the installed Codex CLI and Python standard library;
it does not add an MCP or subprocess framework dependency. CLI availability and
minimum supported behavior are checked at readiness.

Official design references:

- OpenAI Agents SDK overview:
  <https://openai.github.io/openai-agents-python/>;
- runner lifecycle, tools, state, and concurrency:
  <https://openai.github.io/openai-agents-python/running_agents/>;
- provider and OpenAI-compatible model configuration:
  <https://openai.github.io/openai-agents-python/models/>;
- current OpenAI model guidance:
  <https://developers.openai.com/api/docs/guides/latest-model>;
- Codex non-interactive execution:
  <https://learn.chatgpt.com/docs/non-interactive-mode>.

## 17. File map

Create:

- `intelligence/services/episode_protocol.py` — shared instructions, input,
  finish schema, and validation;
- `intelligence/services/openai_agents_runtime.py` — Agents SDK adapter;
- `intelligence/services/codex_headless_runtime.py` — headless subprocess adapter
  and JSONL audit;
- `intelligence/services/headless_tool_gateway.py` — loopback run-scoped finance
  tool gateway;
- `intelligence/services/agent_runtime_factory.py` — explicit composition;
- `intelligence/eval/runtime_backend_benchmark.py` — generic arm artifact and
  comparison logic;
- `scripts/run_agent_runtime_benchmark.py` — isolated real benchmark runner;
- focused tests matching each new module.

Modify:

- `intelligence/services/agent_episode.py` — consume shared episode protocol;
- `intelligence/services/continuous_turn_adapter.py` — record explicit backend
  identity without changing the `AgentRuntime` seam;
- `intelligence/api/app.py` — compose an explicitly configured backend and expose
  secret-free readiness;
- `intelligence/api/requirements.txt` — add the SDK runtime dependency;
- `intelligence/eval/capability_monotonicity.py` only to reuse scoring helpers,
  not to change the historical arm enum;
- Workbench documentation and verification reports.

## 18. Implementation sequence

1. Extract and regression-test `episode_protocol` without behavioral change.
2. Add the generic benchmark artifact and fake runtime tests.
3. Implement and test the headless tool gateway.
4. Implement Codex headless adapter with a fake CLI, then run one real read-only
   smoke using saved Codex authentication.
5. Add Agents SDK dependency and implement the adapter against fake model/tools.
6. Run `sdk_glm` with the existing Keychain-injected provider.
7. Wire explicit backend composition and readiness; keep default unchanged.
8. Start isolated 8796/8797 runtimes and run API/SSE/UI smoke.
9. Run the frozen multi-case benchmark and blinded human review.
10. When an OpenAI API key is available, run `sdk_gpt` on the same artifact
    contract without changing prompts, tools, or evals.
11. Publish a requirement-by-requirement verification report and recommend a
    production backend. Any merge or 8792 cutover requires separate user
    approval.

## 19. Non-goals and deletions

This phase intentionally does not add:

- new question types, route-table rows, or deterministic intent keywords;
- a second evidence store, retrieval implementation, or verifier;
- multi-agent supervisors, handoffs, role swarms, or agent-as-tool delegation;
- long-term SDK Session state or persisted reasoning across Workbench turns;
- a public backend selector;
- automatic runtime fallback;
- a production dependency on Codex headless;
- arbitrary shell, file write, hosted Web search, or computer-use tools.

It also does not preserve shallow duplication introduced during implementation.
If prompt, finish validation, tool authorization, or benchmark scoring appears in
two runtime adapters, it must be moved back behind the existing shared seam or
the new `episode_protocol` deep module before acceptance.

## 20. Completion evidence

The objective is complete only when current-state evidence proves all of the
following:

- all three runtime implementations exist and return `AgentOutcome`;
- all three use the same frozen TaskFrame, contract, registry authorization,
  deadlines, and verifier chain;
- API/Run/SSE/UI smoke succeeds for each isolated backend;
- the real benchmark artifact contains every required arm and case;
- actual answers have been manually reviewed and scored blind;
- latency, attempts, tools, tokens where available, protocol issues, and artifact
  hashes are present;
- the verification report identifies the quality winner and remaining gaps;
- existing full Python and frontend validation pass;
- `main`, canonical 8792, and the canonical runtime symlink remain unchanged.

Passing unit tests alone, successfully calling an SDK, or producing a valid JSON
answer is not sufficient proof.

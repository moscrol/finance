# Continuous Agent Production Candidate Design

Date: 2026-07-23
Status: approved direction; written specification awaiting user review

## 1. Objective

Turn the verified GLM continuous-agent sidecar into an isolated Workbench UI
candidate that can answer long-tail A-share research questions without losing
the base model's task understanding. The candidate must keep one continuous
episode, use the repository's existing read-only finance tools, prioritize
mandatory structured evidence, recover from a failed finalization once, and
fail closed at both structural and semantic grounding gates.

The implementation is complete only when the seven remaining optimization
items are implemented and verified:

1. independent read-only tool calls execute concurrently without breaking the
   ordered transcript, turn-scoped ledgers, deadlines, or authorization;
2. finalization has one bounded compact-evidence recovery path;
3. the runtime supports an ordered provider chain and honestly reports every
   physical provider attempt;
4. a semantic grounding judge gates public completion after structural
   evidence verification;
5. the candidate runs through the real Conversation API and UI on an isolated
   canary port;
6. valuation runs prioritize market and financial anchors over weak RAG/Web
   context;
7. the current episode implementation is deepened into focused modules without
   changing the small `AgentRuntime.run()` interface.

## 2. Constraints and non-goals

- Deterministic fast paths, including `market_technical`, remain outside the
  model loop and must not become slower.
- Tools are read-only. No shell, arbitrary SQL, filesystem mutation, write API,
  or outbound business action is exposed.
- The original `TaskFrame` and its hash are immutable for the full turn.
- Raw observations remain in the episode ledger. Compact recovery is an
  emergency finalization input, not the new normal history format.
- The public answer must not expose evidence hashes, tool protocol, control
  fields, prompt text, or provider diagnostics.
- A user-selected BYOK provider is not silently mixed with another provider.
  Built-in mode may use the configured provider chain in deterministic order.
- No real GPT request is required until an OpenAI-compatible credential is
  supplied. This phase must nevertheless implement and test the provider-chain
  seam so adding GPT is configuration rather than an architecture change.
- Merging `main` and switching canonical 8792 remain explicit human release
  gates. The implementation and isolated UI canary may finish before them.
- This is not a general coding agent, shell agent, multi-agent supervisor, or
  hidden chain-of-thought store.

## 3. Alternatives

### A. Patch all behavior into `agent_episode.py`

This minimizes the initial diff but makes the existing 694-line file own
concurrency, scheduling, recovery, provider policy, verification, and public
presentation. It would recreate the same shallow orchestration problem the
runtime is intended to remove.

### B. Deepen the runtime behind focused internal seams

Selected. Keep `AgentRuntime.run()` as the external interface and put complex
behavior behind three internal modules: `ToolBatchExecutor`,
`EpisodeFinalizer`, and `SemanticEpisodeVerifier`. Callers learn no new
workflow; tests exercise behavior through these small interfaces.

### C. Re-enter the legacy `AnswerSpec` and Grounded Presenter pipeline

This reuses the most code but reintroduces the lossy projections, marker
contract, whole-answer fallback, and template behavior already identified as
the capability regression. It is rejected for the continuous path.

## 4. Target architecture

```text
Conversation API / same Workbench UI
  -> ContinuousTurnAdapter (off | canary | on)
       -> TurnControlCore
            -> clarification
            -> deterministic fast path
            -> ContinuousAgentRuntime.run()
                 -> ContinuousAgentEpisode
                      -> ToolBatchExecutor
                      -> EpisodeFinalizer
                 -> structural episode verifier
                 -> SemanticEpisodeVerifier
                      -> accepted public draft
                      -> one targeted repair + rejudge
                      -> fail-closed evidence-gap answer
       -> existing RunStore / ConversationStore / SSE projection
```

`ContinuousTurnAdapter` is a strangler adapter, not another intent router. It
consumes the one `TurnControlCore` decision and either handles the turn or
declines it. It must not reinterpret the question, select a skill, or send an
Episode answer back through the legacy synthesis pipeline.

## 5. Deep modules and interfaces

### 5.1 `ToolBatchExecutor`

Public interface:

```python
class ToolBatchExecutor:
    def execute(
        self,
        calls: tuple[ModelToolCall, ...],
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        remaining_slots: int,
    ) -> ToolBatchResult: ...
```

The module owns validation, authorization, normalized-query deduplication,
mandatory-capability priority, bounded thread execution, timeout conversion,
and result normalization. The result contains one ordered item per original
model call. `ContinuousAgentEpisode` only appends those items to its messages
and ledgers.

Execution rules:

- Validate all calls before dispatch. Unknown tools, bad arguments, duplicates,
  and over-budget calls become deterministic result items and never reach a
  runner.
- Select valid calls within the remaining tool budget by priority, not model
  array position. Mandatory contract capabilities come first. For valuation,
  `market_data` is first, followed by official/company evidence, local KB, then
  Web context.
- Dispatch independent selected calls concurrently with at most four workers.
  Each worker receives its own `contextvars.copy_context()` so the same
  thread-safe turn `QueryLedger` and LLM call ledger remain visible.
- Never enter the same copied `Context` in two threads. Create one copy per
  submitted call.
- Collect execution results independently, then return them in the model's
  original call order. Evidence, tool messages, and event sequence therefore
  remain deterministic and regression-testable.
- A batch deadline marks unfinished calls as timeout, cancels futures that have
  not started, and does not wait indefinitely during executor shutdown. Tool
  runners must still observe the shared `ResearchDeadline`.
- A failed or empty tool result is an observation for the same episode; it does
  not trigger a legacy fallback pipeline.

### 5.2 `EpisodeFinalizer`

Public interface:

```python
class EpisodeFinalizer:
    def recover(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        gaps: tuple[str, ...],
        failure_reason: str,
    ) -> ModelTurn: ...
```

The normal final answer still comes from the continuous message history. This
module runs only when tools have produced evidence and the normal finalization
returns an exception, provider error, empty/invalid envelope, or a tool call
during the closed finalization phase.

Recovery rules:

- Exactly one recovery attempt per episode; no recursive retry.
- No tools are exposed.
- Input contains the immutable task, required outputs, compact public evidence
  records with their existing hashes, known gaps, data dates, and the original
  failure reason. It contains no hidden reasoning and mints no evidence.
- The recovered `FINAL_JSON` passes the same parser and structural verifier as
  the normal answer. Recovery cannot upgrade a missing output to completed
  without an existing evidence hash.
- If the attempt fails, return an honest partial outcome. Never render an
  unrelated template or the unverified raw draft.

### 5.3 Provider-chain model client

The provider-neutral `AgentModelClient.complete()` interface remains unchanged.
An ordered chain adapter owns provider failover. Every provider receives the
same messages, tools, model settings, and remaining deadline. A successful
message stops the chain; transient transport failure, timeout, empty response,
or invalid provider envelope advances to the next configured adapter while
budget remains. Authentication and deterministic 4xx configuration failures
are recorded but are not repeatedly retried against the same provider.

Physical attempts are accumulated in `ModelTurn.provider_attempts`, Episode
usage, and provider traces. Built-in mode obtains a deterministic tuple from
configured providers. BYOK mode returns only the selected provider unless the
user explicitly configures a chain in a later product feature.

The current `llm_refine.chat_with_tools()` fallback is reused rather than
duplicated. The new code makes the chain explicit at the runtime composition
seam and prevents an outer single-provider override from accidentally
collapsing it.

### 5.4 `SemanticEpisodeVerifier`

Public interface:

```python
class SemanticEpisodeVerifier:
    def verify(
        self,
        *,
        frame: TaskFrame,
        structurally_verified: VerifiedEpisodeOutcome,
        deadline: ResearchDeadline,
    ) -> SemanticEpisodeOutcome: ...
```

The judge receives the original question, numbered public-answer sentences,
required-output bindings, and an evidence registry built only from the
Episode's collected `AgentEvidence`. It checks subject identity, temporal
alignment, fact-versus-hypothesis status, unsupported causality, numerical
support, and cross-topic contamination. It returns strict JSON with
`passed`, rejected sentence indexes, and issues.

Gate behavior:

1. Structural verification runs first and may only preserve or downgrade.
2. A structurally completed draft cannot become publicly completed until the
   semantic judge passes.
3. Rejected sentences trigger one deterministic **span redaction**, followed
   by one rejudge. Only the exact numbered spans rejected by the judge are
   removed; accepted text and Markdown layout remain verbatim. The original
   evidence, bindings, gaps, completion status, events, traces, and usage are
   copied unchanged into the repaired outcome before structural recheck. No
   model receives wording authority during semantic repair.
4. Invalid/unavailable judge output in canary/on mode fails closed to partial.
   The public response is a short deterministic evidence-gap answer; the
   unverified draft remains in private artifacts for inspection.
5. Semantic verification never upgrades structural status and never adds
   evidence.

The semantic gate distinguishes claim types instead of treating every sentence
as a quoted source fact. Observed facts, dates, factual numbers, external
causes, and claimed historical probabilities need direct evidence. A clearly
labelled analytical judgment may be derived from already-bound premises. When
the user explicitly asks for duration, upside, valuation, or another forecast,
the answer may give a conditional base-case range as an analyst estimate; it
must not claim that the source itself supplied the forecast, invent supporting
statistics, or introduce unsupported trigger thresholds. This preserves the
hard truth plane without making analytical tasks structurally unanswerable.

Structured evidence blocks carry one snapshot identity. Their block-level
as-of date is propagated to every evidence atom, while historical dates inside
individual lines remain part of the content. The verifier must not infer that a
current snapshot is stale merely because a summary line omitted a repeated date
literal.

The repair seam is deliberately non-generative. An initial 2026-07-23 canary
first rejected full-envelope regeneration because it resent roughly 18K
characters, timed out, and could mint new threshold language. A smaller
draft-only model repair was then tested. The real run exposed a hard budget
contradiction: the 30-second verification reserve had to cover a 15-second
judge, a 20-second repair, and a 15-second rejudge. The repair consumed the
remaining budget and made rejudge impossible. Raising the reserve or root
timeout would trade correctness for user-visible latency.

Deterministic redaction therefore supersedes the draft-only model call. It
cannot introduce a paraphrased unsupported claim, needs no extra generation
budget, and leaves enough time for the required second judge. Redaction uses
source spans rather than sentence re-joining, so headings, lists, and blank
lines are preserved. If a rejected span contains the direct answer, removing
it is intentional fail-closed behavior; if no useful draft remains, the public
projection becomes the question-specific evidence-gap answer. A malformed,
unavailable, or re-rejected result also fails closed.

Judge execution reuses the repository's independent `LLM_JUDGE_*` provider
selection when configured. Without it, canary may use the primary model but
must record that correlated-judge limitation in the artifact.

## 6. Valuation evidence scheduling

Valuation is treated as a research contract, not a new route. Its mandatory
minimum is:

1. subject/code identity;
2. current price or market-cap/valuation snapshot with date;
3. at least one financial or business anchor;
4. explicit valuation method and assumptions;
5. scenario range or an honest statement that a numeric range is impossible;
6. invalidation and missing-data boundary.

When the model requests several tools in one turn, `market_data` and official
or structured company evidence are scheduled before weak contextual search.
They also start concurrently with slower KB/Web calls, so a slow search cannot
consume their opportunity to run. A completed numeric valuation requires the
current anchor and assumptions to be bound to collected evidence. Otherwise it
is partial even if the prose sounds confident.

## 7. Conversation API and isolated UI canary

Runtime mode is controlled by `ASK_CONTINUOUS_RUNTIME=off|canary|on`:

- `off` is the default and preserves the canonical behavior;
- `canary` enables the path only when the isolated runtime also sets a canary
  identifier, preventing accidental activation in canonical 8792;
- `on` is reserved for a later approved cutover.

The isolated canary launches the same backend and built frontend on another
localhost port. No separate demo UI is created. Long-tail research and the
preserved deterministic fast path run through the normal conversation message,
SSE, persistence, cancellation, and artifact endpoints.

The adapter emits public progress events such as understanding the task,
checking structured data, collecting sources, verifying the draft, and
finalizing. Raw hashes, prompt text, query-ledger keys, provider exceptions,
and tool protocol remain private artifacts. Terminal state maps as follows:

- semantically verified complete -> completed;
- honest partial or semantic gate failure -> degraded with a useful answer or
  explicit evidence gap;
- no answer and no evidence -> failed;
- clarification -> completed clarification without retrieval.

The legacy path remains callable for the same fixed A/B cases until the canary
passes. An Episode-owned answer is persisted directly and is never rewritten
by a legacy owner or presenter.

## 8. Code deepening and deletion

The implementation will reduce `agent_episode.py` to the continuous control
loop. It will move batch execution and finalization policy into their deep
modules, use the single public evidence projection from `agent_runtime.py`, and
centralize question-type scheduling policy in one episode-policy table.

Old inline serial-tool execution, duplicate `_public_evidence`, and duplicated
finalization-recovery branches are deleted after replacement tests pass. The
work does not refactor unrelated legacy owners or rewrite all historical
question-type strings.

## 9. Test seams and acceptance evidence

Tests exercise public behavior at four agreed seams:

### Tool batch seam

- mandatory valuation tools start even when listed after slow search calls;
- at least two independent runners overlap in wall-clock time;
- copied contexts share the same turn QueryLedger without `RuntimeError`;
- duplicate, unauthorized, timeout, exception, and over-budget results remain
  ordered and deterministic;
- transcript tool messages preserve original call order.

### Finalizer/provider seam

- normal continuous finalization remains the first path;
- compact recovery runs exactly once and cannot call tools or invent hashes;
- a scripted two-provider chain falls through after a transient failure and
  counts both physical attempts;
- BYOK composition does not silently append a built-in provider;
- total deadline and LLM call budget remain hard.

### Verifier seam

- unsupported causality, subject swaps, stale-current claims, and fabricated
  numbers are rejected;
- targeted repair is rejudged once;
- judge outage cannot produce public `completed`;
- passed semantics cannot upgrade a structural partial;
- public projection contains no internal evidence or provider identifiers.

### Conversation API seam

- `off` leaves existing behavior unchanged;
- isolated `canary` runs a long-tail turn through the continuous adapter;
- deterministic technical questions remain zero-LLM fast paths;
- cancellation and hard deadlines terminalize cleanly;
- answer, citations/evidence boundary, events, artifacts, and runtime provenance
  persist under the same run/message IDs.

Real GLM acceptance repeats the five fixed questions individually and as a
single-process pressure batch. Required evidence includes latency, physical LLM
attempts, tool calls, terminal outcome, semantic-gate status, task-alignment
score, and answer text. The candidate must:

- pass the bare-model capability floor on all five isolated cases;
- return a non-empty, relevant answer or explicit task-specific gap for all
  five pressure cases;
- give the valuation case a current structured anchor, or explicitly document
  the external-data failure without unrelated retrieval contamination;
- show no duplicate retrieval caused by concurrent execution;
- keep the technical fast path under its existing latency/LLM-call envelope;
- pass focused, API, and complete `intelligence/tests` regression suites with
  no new failures relative to the fixed baseline.

## 10. Release gates

Implementation completion and production release are separate claims.

The candidate is implementation-complete when all modules, tests, real-GLM
isolated UI canary, pressure report, code review, and project-memory handoff are
present on the task branch. It is not production-released until the user
reviews the canary answers and explicitly approves both:

1. merging the task branch into `main`;
2. atomically switching canonical 8792 with the documented rollback path.

If no GPT credential exists, the report marks live GPT A/B as pending external
configuration, not as a code gap. The provider-chain fake-adapter tests and GLM
canary remain required and must be green.

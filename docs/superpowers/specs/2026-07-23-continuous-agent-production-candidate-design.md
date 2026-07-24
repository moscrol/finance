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
                      -> at most two targeted repairs + bounded rejudges
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
- The compact view is capped at twelve evidence records, selected round-robin
  across the tools that produced them, with each detail excerpt capped at 360
  characters. The full evidence ledger remains in the Episode artifact. The
  recovery draft is capped by instruction at 1,200 Chinese characters so the
  provider spends its bounded call on a direct answer rather than reprinting
  the ledger.
- Normal continuous finalization uses a softer 1,000-Chinese-character
  transport budget. This is not a title, paragraph, or line-count template:
  the model keeps wording and layout authority, but must prioritize the direct
  judgment, decisive evidence, uncertainty, and continuation/invalidation
  conditions so the provider can finish one valid envelope before timeout.
- The composition root gives the shared finalizer the same provider-call cap
  as normal Episode turns (currently 75 seconds), still clipped by the one
  root `ResearchDeadline`. This removes an accidental 20-second recovery-only
  timeout without minting a second wall-clock budget.
- The recovered `FINAL_JSON` passes the same parser and structural verifier as
  the normal answer. Recovery cannot upgrade a missing output to completed
  without an existing evidence hash.
- If the attempt fails, return an honest partial outcome. Never render an
  unrelated template or the unverified raw draft.
- The Workbench composition root injects the same task-shaped synthesis
  reserve used by the isolated A/B runner. Under the 120-second turn budget, a
  standard balanced task receives a 90-second Episode window with 60 seconds
  reserved inside it for normal finalization, while 30 seconds remain outside
  the Episode for semantic verification. The allocation changes ownership,
  not the total deadline.
- Budget policy is injected into `ContinuousTurnAdapter`; the provider-neutral
  adapter does not import GLM-specific policy. This prevents the UI and
  evaluation runner from silently constructing different `ResearchRunContext`
  values.

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
support, and cross-topic contamination. The primary model adapter is offered
one no-side-effect `submit_grounding_report` function whose schema contains
only `passed`, rejected sentence indexes, and issues. Exactly one schema-valid
function call is accepted. Some OpenAI-compatible adapters return explanatory
sibling text alongside a valid call; that text is ignored and can never enter
the judge result or public answer. Strict JSON content remains a fallback for
adapters without function calling; unknown, multiple, or malformed calls fail
closed. This is a structured transport, not a research tool or a new model
permission.

The evidence registry sent to this judge is a semantic projection, not a
second copy of the complete Episode ledger. It includes only hashes referenced
by required-output bindings and aliases them locally as `E1...En`. It preserves
the evidence text, tool, date, tier, non-default freshness, and any non-empty
support/contradiction/independence metadata; bindings use the same aliases.
Source URLs, duplicate titles, repeated capability allowlists, raw hashes, and
empty metadata stay in the immutable audit ledger rather than consuming judge
attention. This bounds latency without hiding any evidence that is legally
capable of supporting the public answer.

The final JSON parser normalizes model-emitted literal newline escapes only in
the natural-language `draft` field. This keeps Markdown layout and
sentence-level verification aligned without weakening the surrounding JSON,
binding, or evidence-hash contract. A semantic repair is also monotonic over
visible required-output markers: if deleting rejected sentences removes a
required answer slot that was present before repair, the result is partial
rather than a misleading completed answer.

Numeric-condition matching accepts only deterministic rounding of a bound
observation at the precision shown in the answer, with unit compatibility and
explicit currency-unit conversion. A sentence saying “缩约 17%” may therefore
match bound evidence `-17.27%`, and `2.19 万亿元` may match `21949.97 亿元`;
an unrelated `3800 点` trigger does not match `3876.777 点`. This prevents
rounding false positives without turning the gate into a broad numeric
tolerance.

Tool availability remains task-shaped. A `market_forecast` duration/scenario
turn receives current structured market and same-day mainline tools; it does
not receive causal news/web tools merely because it is long-tail. A
`market_cause` turn retains time-aligned news and web capabilities. This keeps
the model in control of research while preventing optional, stale commentary
from consuming the episode budget or being mistaken for a current forecast
premise. The immutable TaskFrame evidence policy is the single owner of this
tool surface: mapped legacy controller aliases are used only when the frame has
no runtime capability plan and may not be unioned into an existing plan. The
finalization contract additionally requires every retained exact
number to have its direct evidence hash in the corresponding output binding;
otherwise the model must omit that number.

Gate behavior:

1. Structural verification runs first and may only preserve or downgrade.
2. A structurally completed draft cannot become publicly completed until the
   semantic judge passes.
3. Rejected sentences trigger deterministic **span redaction**, followed by a
   bounded rejudge. If that rejudge identifies a different unsupported span,
   one second deletion-only repair and final rejudge are allowed. Only exact
   numbered spans rejected by a completed judge report are removed; accepted
   text and Markdown layout remain verbatim. A final completed judge report may
   authorize terminal deletion of its rejected spans without a fourth model
   call. The original evidence, bindings, gaps, completion status, events,
   traces, and usage are copied unchanged before every structural recheck. No
   model receives wording authority during semantic repair. Repair may not
   delete a visible required-output marker and still report completion.
4. If no completed first judge report exists, invalid/unavailable judge output
   in canary/on mode fails closed to partial. After a completed report has
   reviewed the whole draft and identified exact rejected spans, however, a
   later optional rejudge may preserve the already-reviewed remainder after
   deterministic deletion and structural re-verification only when it either
   exhausts the shared root deadline or ends in a strictly classified
   transient transport/provider failure. That terminal result is recorded as
   `repaired`; it cannot add or paraphrase text, mint evidence, restore a
   rejected span, or upgrade a structural partial. This is monotonic recovery
   after an already completed whole-draft review, not fail-open acceptance of
   an unreviewed draft. `_JudgeCall` carries explicit
   `root_deadline_exhausted` and `transient_provider_failure` identities;
   checking the wall clock or matching the public reason string is
   insufficient. Release-grade transient classification is limited to
   anchored HTTP 429/5xx status or explicit timeout/connection exception
   identities. Authentication, 4xx configuration, model/endpoint,
   malformed/empty-envelope, and tool-call failures remain fail-closed. A late
   valid rejection is retained and its exact spans are still deleted before
   any release.
5. Semantic verification never upgrades structural status and never adds
   evidence.
6. The semantic gate may retry its correlated primary judge once after any
   classified retryable failure. It may spend one final third attempt only
   when the first two failures both carry typed release-grade identity
   (anchored HTTP 429/5xx or an explicit timeout/connection exception). Each
   attempt is capped at 25 seconds and consumes the same root verification
   deadline; no retry extends that deadline. Empty response and free-text
   transport hints may be retried once but are not release-grade transients.
   Authentication, configuration, budget,
   cancellation, malformed-envelope, and tool-call failures are not retried or
   released. Raw provider diagnostics remain private and are reduced to stable
   reason codes plus private typed failure flags. Root-deadline identity is
   always preserved separately from the cumulative retry-chain release flag:
   a real deadline remains observable as a deadline, but cannot unlock the
   monotonic-release exception after any non-release-grade failure.
7. A deterministic preflight rejects a numeric condition when its full
   quantity/range does not occur in evidence bound to the answer. It redacts
   those spans before the first model judge and remains active after every
   report as defense in depth. A correlated judge therefore cannot pass a newly
   invented support level, breadth threshold, or secondary forecast window,
   and known-bad spans do not consume a judge/rejudge cycle. Dates, list labels,
   the one clearly labelled base-case estimate requested by the user, and
   numeric anchors present in bound evidence are unaffected.

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
cannot introduce a paraphrased unsupported claim and consumes no repair-model
budget. Up to three judge reports share the existing root verification
deadline; no extra reserve or wall-clock extension is minted for the second
repair. A missing first report still fails closed. If a later optional rejudge
exhausts the shared root deadline or returns a release-grade transient failure
only after one completed whole-draft report and exact monotonic redaction, the
reviewed remainder may be released as `repaired`; malformed output,
configuration errors, invalid tool calls, empty responses, and other
unavailable states remain fail-closed. Redaction uses source spans rather than
sentence re-joining, so
headings, lists, and blank lines are preserved. If a rejected span contains
the direct answer, removing it is intentional fail-closed behavior; if no
useful draft remains, the public projection becomes the question-specific
evidence-gap answer. A malformed, configuration-invalid, or otherwise
unresolved result also fails closed; only the explicitly bounded later
shared-deadline/transient cases above have the monotonic-release exception.

Gate-local transient retry is intentionally owned here rather than inside
`GLMModelClient`. The provider-chain adapter retains its one-attempt-per-
configured-adapter contract; the semantic gate, as a critical acceptance
boundary, decides whether spending one retry is justified and permits a third
attempt only for two consecutive typed release-grade failures. A real
2026-07-23 GLM canary showed that the original 17.7K-character judge request
timed out deterministically at the old 10-second cap. Bound-only evidence
aliases and numeric preflight reduced the same request to roughly 8K
characters; the per-attempt cap is therefore 25 seconds while the existing
30-second root verification reserve remains unchanged. Retry or rejudge uses
only the actual remaining root time and fails closed when it is exhausted.

Judge execution reuses the repository's independent `LLM_JUDGE_*` provider
selection when configured. Without it, canary may use the primary model but
must record that correlated-judge limitation in the artifact.

The semantic verifier owns text acceptance, not citation presentation. It
returns only the accepted/sanitized draft. `ContinuousTurnAdapter` is the sole
public citation owner and projects the bound evidence as structured
`citations`; the verifier must not append the same ledger to answer text. This
keeps prose concise and prevents two presentation layers from rendering the
same sources differently.

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
- semantically verified honest partial -> transport `completed` with
  `business_status=partial`, a useful answer or explicit task-specific
  evidence gap, and no runtime degrade;
- semantic gate failure or runtime/provider failure -> degraded with only the
  safely verified remainder or an explicit evidence gap;
- no answer and no evidence -> failed;
- clarification -> completed clarification without retrieval.

`partial` is a first-class business result, not an infrastructure failure.
The transport remains terminally completed so clients do not mistake an
honest evidence boundary for an interrupted run. Structural and semantic
verification may preserve or downgrade this status, but never upgrade it.

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
- a model-judge pass cannot preserve a novel numeric condition absent from
  bound evidence, while dates and evidence-backed numeric anchors remain;
- targeted repair is deletion-only, bounded to two repair rounds, and every
  newly exposed draft is rejudged when the shared root deadline permits;
- judge outage before any completed whole-draft report cannot produce public
  `completed`; only shared-deadline exhaustion or a typed release-grade
  transient failure on an optional rejudge may preserve the remainder already
  reviewed and monotonically redacted from a completed prior report;
- passed semantics cannot upgrade a structural partial;
- public projection contains no internal evidence or provider identifiers and
  does not duplicate the adapter-owned structured citation ledger.

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

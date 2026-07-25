# Adaptive Finance Agent Runtime Design

Date: 2026-07-26
Status: approved direction, written specification awaiting user review
Implementation branch: `feat/agent-runtime-backends-verify`
Current isolated candidate: `a887d1be` on port 8799

## 1. Product Objective

Build one Finance Workbench runtime that approaches the interactive quality of
Codex while exceeding Knevo on A-share evidence quality, structured local data,
auditability, and persistent decision learning.

The product must combine three strengths rather than copy any one system:

1. **Codex-style agency**: the model owns task decomposition, hypotheses,
   query construction, tool sequence, recovery, and the research stop decision.
2. **Workbench finance discipline**: code owns read-only permissions, canonical
   data semantics, budgets, evidence lineage, temporal consistency, and final
   acceptance.
3. **Knevo-style research discipline and product experience**: positive,
   broad, and counter retrieval; evidence bucketing; explicit alternatives;
   decision tracking; asynchronous deep research; and inspectable progress.

Success is not "the pipeline returned valid JSON." Success is that an
unfamiliar long-tail finance question receives a direct, useful answer whose
claims are supported, whose uncertainty is explicit, and whose research path
can recover from an initial miss without adding a new route or skill.

## 2. Superseded Decisions

This specification supersedes the following parts of earlier designs for the
long-tail research lane:

- `question_type -> evidence_policy -> required_outputs -> capability set` may
  no longer prescribe the long-tail research plan before the model runs.
- A semantic or task-fulfillment failure may no longer be resolved primarily by
  deleting requested content and publishing a template gap.
- A successful fixed snapshot may no longer be treated as proof that the user
  task is complete.
- The existence of a continuous message loop may no longer be used as evidence
  that the model owns research decisions.
- `ASK_CONTINUOUS_RUNTIME=off` remains a rollback control during migration, but
  the target architecture is one default runtime, not two permanent answer
  systems.

The following earlier decisions remain authoritative:

- deterministic fast paths for exact technical calculations and fixed daily
  workflows;
- the provider-neutral `AgentRuntime` seam and its Continuous, OpenAI Agents
  SDK, and benchmark-only Codex headless adapters;
- one continuous observable episode history with raw public tool observations;
- read-only finance tools, hard deadlines, call budgets, query deduplication,
  evidence hashes, ProviderTrace, structural verification, semantic grounding,
  Run artifacts, SSE, and the existing Workbench UI projection;
- no hidden chain-of-thought persistence;
- no `main` merge or canonical 8792 cutover without explicit user approval.

## 3. First-Principles Ownership

Exactly one module owns each decision.

| Decision | Owner | Non-owner constraints |
|---|---|---|
| What the user literally asked | `UserTask` | Never rewritten by a route or provider |
| Entity/date/market resolution | deterministic resolver | Must record explicit/inherited/default/inferred provenance |
| Whether a blocking clarification is necessary | `AmbiguityResolver` | At most one high-information question |
| Fast path, quick episode, or proposed deep upgrade | `ModeGovernor` | Model proposes deep; code checks budget and observable complexity |
| Research decomposition and hypotheses | primary model in `ResearchEpisode` | Must preserve the original task |
| Needed answer elements | primary model in `ResearchEpisode` | Task-fulfillment verifier checks them against the user request |
| Tool choice, query, ordering, retry, and stop | primary model in `ResearchEpisode` | Registry enforces authorization, deadline, and cost |
| SQL, table access, metrics, and source semantics | `FinanceQuery` | Model selects semantic fields; module compiles safe queries |
| Evidence identity, lineage, dates, conflicts, and independence | `EvidenceLedger` | Model may interpret but may not mint evidence |
| Whether a gap may receive another bounded attempt | `RepairCoordinator` | Code checks only an explicit progress predicate and root budget |
| Whether content may be published | structural/semantic/task verifier | May reject or request repair; may not invent facts |
| Final judgment and natural wording | primary model | Must pass the exit verifiers |
| Promotion into durable memory | `MemoryGate` | Only validated outcomes or explicit user corrections qualify |

The key rule is: **the model owns research strategy; code owns execution safety
and publication truth.**

## 4. Target Architecture

```text
User message + conversation context
  -> UserTaskInterpreter
       -> ClarificationRequest [only if answer-changing ambiguity]
       -> DeterministicFastPath [technical levels / exact facts / fixed workflow]
       -> Quick ResearchEpisode
            -> model-owned ResearchPlan
            -> ModeGovernor [optional deep-upgrade request]
            -> ResearchToolRegistry
                 -> FinanceQuery
                 -> EvidenceSearch
                 -> News/Web/Graph/L3 adapters
            -> EvidenceLedger + ResearchState
            -> CoverageEvaluator
            -> RepairCoordinator -> same ResearchEpisode
            -> structural + semantic + task verifier
            -> public answer
       -> Deep ResearchEpisode
            -> optional max-3 read-only sub-research branches
            -> shared EvidenceLedger
            -> same repair and verification path
  -> DecisionLedger
  -> MemoryGate after validation/correction
```

The existing `ContinuousTurnAdapter` remains the product adapter during
migration. Its target role becomes composition and public projection only. It
must stop deciding long-tail semantics or silently declining to the legacy
answer pipeline after the new runtime is accepted.

## 5. Core Interfaces

### 5.1 `UserTask`

`UserTask` replaces the plan-shaped long-tail use of `TaskFrame`. During
migration, the current `TaskFrame` may remain as a compatibility projection,
but only the fields below are authoritative:

```python
@dataclass(frozen=True)
class UserTask:
    raw_question: str
    conversation_context: str
    subjects: tuple[ResolvedSubject, ...]
    market_scope: ResolvedValue
    time_window: ResolvedTimeWindow | None
    assumptions: tuple[str, ...]
    ambiguities: tuple[TaskAmbiguity, ...]
    user_premises: tuple[str, ...]
    task_id: str
```

It does not contain a long-tail `question_type`, fixed `required_outputs`, an
evidence plan, an answer owner, a tool list, or a presentation template.

#### Information cutoff

The execution contract carries one immutable information cutoff. It is distinct
from the user's analysis window: a forecast may discuss a future period while
all supporting facts must be known no later than this cutoff.

```python
@dataclass(frozen=True)
class InformationCutoff:
    as_of_date: date
    source: Literal["requested", "latest_available", "runtime_default"]
```

`ResearchRunContext.information_cutoff` is the sole authoritative value. The
composition root derives it once from the explicit requested/as-of date or the
runtime date; the model cannot change it. A provider's `latest_data_date` or
`source_trade_date` is served-data freshness metadata, not a global information
cutoff, so a stale Friday market snapshot must not hide weekend news. Every FinanceQuery, EvidenceSearch,
News/Web/Graph/L3 adapter receives the same cutoff and filters before returning
an observation. A later document, row, or news item is rejected and recorded as
`future_of_cutoff`; it must never reach model context. `ProviderTrace` records
both requested and served dates.

Deterministic resolution remains valuable for stock codes, index aliases,
trading dates, explicit markets, and conversational references. A product
default such as A-share must be labelled `product_default`, not user-provided.

### 5.2 `ResearchPlan`

The primary model creates and updates an explicit, observable plan inside the
same episode:

```python
@dataclass(frozen=True)
class ResearchPlan:
    task_summary: str
    answer_elements: tuple[AnswerElement, ...]
    hypotheses: tuple[Hypothesis, ...]
    evidence_needs: tuple[EvidenceNeed, ...]
    candidate_actions: tuple[ResearchAction, ...]
    open_gaps: tuple[str, ...]
    requested_mode: Literal["quick", "deep"]
```

This is not hidden reasoning. It is a compact work contract that can be shown
as UI progress and audited. The model may revise it after observations. Code
validates shape, authorization, and budget but does not substitute a route plan.

### 5.3 `ResearchState` and `EvidenceLedger`

One episode owns one mutable research state and one append-only evidence
ledger. They preserve:

- original task and plan revisions;
- tool requests, normalized queries, raw public observations, errors, and gaps;
- evidence atoms with source, date, content hash, provider trace, and freshness;
- source-family identity so two excerpts from one report do not count as two
  independent sources;
- hypothesis support, contradiction, and unresolved status;
- coverage changes and remaining budget;
- sub-research branch ownership without duplicating evidence.

The ledger is the audit truth. The model sees the public observations needed
for the current decision; the UI and benchmark receive a bounded projection.

### 5.4 `RepairGoal`

All failed coverage paths converge on one interface:

```python
@dataclass(frozen=True)
class RepairGoal:
    episode_id: str
    repair_goal_id: str
    cycle: int
    missing_answer_elements: tuple[str, ...]
    unsupported_claims: tuple[str, ...]
    missing_evidence_modes: tuple[str, ...]
    attempted_actions: tuple[AttemptSummary, ...]
    evidence_progress: CoverageDelta
    remaining_calls: int
    remaining_seconds: float
```

`RepairGoal` describes what remains missing and what has already failed. It
must not prescribe the next query. The same primary model decides whether to
rewrite a query, choose another tool, request a sub-research branch, narrow the
claim, or stop with an honest gap.

The repair budget is bounded:

- quick mode: at most one repair cycle;
- deep mode: at most three repair cycles;
- no extension when the latest cycle added no new evidence and narrowed no gap;
- no repair may exceed the root deadline or mint a second budget ledger.

All repair sources share this one cycle pool. A retrieval empty result,
task-fulfillment gap, semantic rejection, and budget-near-exhaustion do not each
receive hidden retries. A granted repair must emit the same `episode_id` and a
new `repair_goal_id`, then produce a new primary-model action before it can
count as a successful repair cycle. If the model immediately stops, the result
is an honest partial and the cycle is unused.

## 6. Adaptive Quick and Deep Modes

The selected product policy is adaptive dual speed.

### Quick mode

- target wall time: 60-90 seconds;
- initial tool-call ceiling: 8;
- no sub-research branches;
- one verifier-triggered repair cycle;
- produce a direct answer or a question-specific partial, never an unrelated
  fallback template.

### Deep mode

- target wall time: up to 3-5 minutes;
- initial total tool-call ceiling: 24 across the primary and all branches;
- at most three concurrent read-only sub-research branches;
- at most three verifier-triggered repair cycles;
- asynchronous Run lifecycle with immediate acknowledgement and continuous SSE
  progress;
- completion is delivered into the same conversation without requiring the
  user to poll manually.

These are initial product caps, not Knevo thresholds copied as truth. Evaluation
may lower or raise them after measuring marginal answer quality per call.

### Upgrade authority

The model may request deep mode after producing its first plan. `ModeGovernor`
approves only when at least one observable condition holds:

- multiple independent entities or comparison branches;
- multiple evidence domains are necessary for the requested judgment;
- the task requires causal attribution, valuation, counterfactual stress,
  historical analogy, or supply-chain mapping beyond quick-mode capacity;
- the first evidence pass leaves a material answer element uncovered;
- the user explicitly selects deep research.

The governor may deny promotion when the user selected quick mode, credentials
or data dependencies are unavailable, or the deep deadline cannot be honored.
It records the reason but does not rewrite the research plan.

## 7. `FinanceQuery`: Model-Owned Structured Retrieval

The production tool is a typed semantic query interface, not unrestricted SQL.

```python
@dataclass(frozen=True)
class FinanceQuerySpec:
    dataset: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    filters: tuple[QueryFilter, ...]
    time_range: TimeRange | None
    group_by: tuple[str, ...]
    order_by: tuple[Order, ...]
    limit: int
```

The model decides what to measure, compare, filter, and aggregate. The module
hides the physical DuckDB tables and compiles the spec through a metric
registry into parameterized, read-only SQL.

The compiler receives `ResearchRunContext.information_cutoff` separately from
the model spec and injects `date <= cutoff.as_of_date` into every dataset that
has a time dimension. Datasets without a time dimension must declare that fact
in the metric registry. A query that omits or conflicts with the cutoff is
rejected before execution; the model never gets to choose a later as-of date.

Hard guarantees:

- read-only DuckDB connection;
- registered datasets, metrics, dimensions, operators, and joins only;
- bound parameters for all values;
- statement timeout and cancellation;
- row and byte limits;
- query plan and physical SQL stored privately for audit, never shown in the
  public answer;
- every returned row or aggregate converted into evidence atoms with as-of
  date and source identity.

Existing `market_data`, `financial_data`, and `mainline_context` snapshots stay
available during migration but must expose honest no-argument snapshot
interfaces. They may not accept a fake query parameter that is discarded.

### Benchmark-only raw SQL

A separate `readonly_sql` adapter is permitted only in an isolated benchmark
profile to measure the model capability ceiling. It is never enabled in the
production registry. It accepts one `SELECT` or `WITH` statement, applies a
statement parser, table allowlist, timeout, and result cap, and runs against a
read-only database copy or connection.

This separates hypothesis testing from the production security contract.

## 8. Evidence Search and Knevo Discipline

Knevo mechanisms are reused according to the layer they belong in; they are
not pasted wholesale into the system prompt.

### Reuse as a deep retrieval module

The existing `closed_loop_retrieval.py` becomes an `EvidenceSearch` adapter.
It preserves:

- narrow retrieval anchored to the subject;
- broad retrieval using terms learned from relevant narrow hits;
- counter retrieval for contradiction and alternatives;
- conclusion, clue, counter-clue, and discarded buckets;
- attempt budgets and traceable query history.

The model decides when this compound search is useful and supplies the task or
hypothesis anchor. The module returns both evidence and a coverage report. An
empty aperture becomes a `RepairGoal`, not just a warning. Its interface
requires the immutable cutoff:

```python
EvidenceSearch.search(
    *,
    query: str,
    anchor: EntityAnchor | None,
    information_cutoff: InformationCutoff,
    deadline: ResearchDeadline,
) -> EvidenceSearchResult
```

The adapter applies the cutoff inside each provider call/result filter, not
only in the final evidence label. A deterministic negative test must prove a
high-scoring future document never appears in the model observation.

### Enforce in evidence state or verifier

- subject and time-window alignment;
- source-family independence;
- freshness and evidence tier;
- positive/counter coverage;
- monotonicity under evidence removal;
- facts versus user premises versus model reasoning;
- unsupported numeric thresholds and causal links.

### Leave to model judgment

- hypothesis formation;
- which broad relationship or alternative matters;
- sensitivity analysis and whether an assumption flip changes the decision;
- the final ranking, alternative path, and natural explanation.

Knevo's observed confidence thresholds, memory-count mappings, and tool-count
rules remain hypotheses until local ablation tests show monotonic quality gains.
They are not hard-coded because Knevo's own evidence-ablation experiment showed
non-monotonic confidence behavior.

## 9. Sub-Research Branches

Deep mode may create branches only when the primary plan contains separable
work. Examples include:

- two companies in a comparison;
- industry evidence versus company financial realization;
- supporting explanation versus counter-explanation;
- several independent supply-chain layers.

Each branch receives:

- the immutable `UserTask`;
- one bounded branch goal;
- a subset of authorized read-only tools;
- a child deadline and call allocation from the same root budget;
- access to the shared EvidenceLedger through an append-only interface.

Branches cannot publish answers, spawn more branches, write durable memory, or
change the primary plan. The primary model synthesizes and decides.

## 10. Verification and Recovery

The exit path remains layered:

1. structural protocol validation;
2. task-fulfillment validation against the original user request and current
   model-owned answer elements;
3. factual, temporal, numeric, and causal grounding;
4. public projection and leakage checks.

The normative transition is:

```text
gate failure
  -> RepairGoal(episode_id, repair_goal_id, cycle)
  -> same episode appends goal and failed observation
  -> primary model emits a new ModelAction
  -> new observation enters the same ledger
  -> structural/task/semantic verification runs again
```

The review receipt must be able to assert these event types and IDs in order.
The model may choose to stop after seeing the goal; that is a partial outcome,
not a successful repair. Deterministic span redaction is allowed only for
optional unsupported detail after all required
answer elements remain fulfilled. If redaction would remove a requested
element, the episode must re-enter research or return a clear partial.

The verifier never upgrades an answer, invents evidence, writes the next
query, or replaces the answer with a topic template.

## 11. Memory and Decision Learning

The selected memory policy has three layers:

1. **Ephemeral episode state**: raw observations, hypotheses, and gaps for the
   current run.
2. **Decision ledger**: reuse the existing user-state canonical writers
   `intelligence/users/<id>/checkpoints.jsonl` and `verdicts.jsonl` for dated
   judgments, assumptions, alternatives, validation windows, and falsification
   criteria. The ledger map remains the source of truth; this runtime does not
   create a parallel `decision_ledger.jsonl`.
3. **Durable experience**: only market-validated lessons, stable user
   preferences, or explicit user corrections.

Prices, news, current rankings, temporary company facts, and unverified model
judgments never become timeless memory. Durable experience is a prior for
future planning, not current-world evidence. `MemoryGate` emits a
machine-readable `PromotionDecision` whose provenance must reference a
checkpoint verdict (`hit`, `miss`, or reviewed `partial`) or an explicit
correction record. A volatile-fact rejection is a first-class negative test.

## 12. UI and Product Experience

Quick mode behaves like a normal conversational answer. Deep mode behaves like
an asynchronous research job within the same conversation.

Public progress events describe user-relevant work, for example:

- aligning the task and deciding research depth;
- checking structured market or company data;
- testing the main explanation and alternatives;
- filling a material evidence gap;
- verifying the final answer.

The main answer never exposes tool names, SQL, hashes, provider errors, table
names, or internal contracts. An expandable inspector may show sanitized tool
calls, sources, dates, branch progress, and why a gap remained.

One Run emits exactly one terminal SSE event. Deep mode remains cancellable and
must persist enough public state for reconnect and completion delivery.

## 13. Strangler Migration

The code currently defaults `ASK_CONTINUOUS_RUNTIME` to `off`; therefore the new
runtime is not yet the product's default owner. Migration is explicit:

### Phase 0: specification and deterministic tests

- freeze the ownership interfaces in this document;
- add interface-level tests for UserTask, ResearchPlan, FinanceQuery,
  RepairGoal, and mode promotion;
- do not rerun the nine-case live suite during implementation.

### Phase 1: decision seam inside the isolated runtime

- keep deterministic fast paths;
- replace long-tail plan-shaped TaskFrame projection with UserTask;
- let the model create ResearchPlan and answer elements;
- preserve the current TaskFrame only as a compatibility artifact.

### Phase 2: retrieval freedom and recovery

- add FinanceQuery and the benchmark-only SQL adapter;
- adapt existing closed-loop retrieval as EvidenceSearch;
- parameterize or honestly retype the three fixed snapshots;
- implement RepairGoal re-entry for retrieval, verifier, and budget gaps;
- export missing answer elements and per-tool traces into benchmark artifacts.
- enforce one `ResearchRunContext.information_cutoff` through every provider;
  future rows/documents must be rejected before model context.

### Phase 3: adaptive deep mode

- add ModeGovernor and asynchronous deep Run lifecycle;
- add max-three sub-research branches;
- add three-layer memory writeback;
- expose useful progress and inspector events.

### Phase 4: isolated evaluation

- use unit and contract tests for the development loop;
- use one failing case or a minimal case pair for live diagnosis;
- run the frozen benchmark exactly once after a revision is frozen;
- compare Continuous GLM, SDK GLM/GPT, and a genuinely freer benchmark-only
  Codex profile without silently changing finance truth gates;
- keep 8792 untouched.

### Phase 5: canonical canary

Only after user approval:

- run by user/canary ID on canonical infrastructure;
- observe task alignment, repair success, latency, cost, and regressions;
- move to `on` only after canary acceptance;
- retain rollback to the previous revision, not a silent per-turn legacy answer
  fallback.

### Phase 6: deletion

After the new runtime is default and stable, the following executable trigger
must be satisfied before deletion:

- at least 500 representative long-tail runs over 14 calendar days on the
  approved canary population;
- no P0 truth, permission, task-fulfillment, or temporal regression;
- P1 regression rate no higher than the frozen legacy baseline plus 1 percentage
  point;
- deterministic and frontend suites green on the same revision;
- rollback revision and run-store migration snapshot verified;
- two consecutive daily audit summaries show no unresolved repair-loop or
  control-plane leakage finding.

Only after this trigger and explicit release approval:

- remove duplicate long-tail classifiers, required-lens builders, retrieval
  planners, and output contracts from the legacy answer pipeline;
- retain only explicit deterministic workflows and their domain modules;
- move reusable data access behind tools and reusable publication rules behind
  verifiers;
- remove `ASK_CONTINUOUS_RUNTIME` after the rollback window closes.

The deletion test is mandatory: if deleting an old module merely causes its
logic to reappear in several callers, migration is incomplete. If the logic is
now hidden behind one deep interface, the module can be retired.

## 14. Evaluation and Acceptance

### 14.1 Development discipline

- unit tests prove permissions, budgets, compilation, state continuity, repair,
  and verifier behavior;
- one live failing case proves a behavioral fix;
- cached observations support deterministic replay;
- the frozen suite is a release gate, never the development loop.

### 14.2 Agent autonomy metrics

- percentage of long-tail runs whose plan and answer elements were created by
  the model rather than a route table;
- percentage of structured queries whose metrics, dimensions, filters, and
  time range came from the model plan;
- query-rewrite recovery rate after empty/error observations;
- verifier-repair success rate;
- duplicate and invalid action rates;
- stop efficiency: useful evidence gained per call and unnecessary calls after
  sufficient coverage.

The code-owned progress predicate for budget grants is:

```text
effective_new_evidence = evidence that is valid for the cutoff, not duplicate,
  not same-source, not rejected, and bound to an uncovered answer element or
  active hypothesis;
coverage_delta = newly_fulfilled_outputs + newly_narrowed_gaps
  + newly_supported_or_contradicted_hypotheses;
progress = effective_new_evidence >= 1 AND coverage_delta >= 1;
```

`BudgetGrant` is atomic in the root ledger. For a progress-positive repair,
`calls_granted = min(4, max(1, uncovered_output_count + missing_evidence_mode_count))`
and `seconds_granted = min(30, calls_granted * 8)`, both clipped by the root
deadline and remaining mode cap. No progress means zero grant. This formula is
tested for duplicate, same-family, future, irrelevant, and genuine coverage
cases; it is not a global budget bump.

### 14.3 Finance quality metrics

- task alignment and direct-answer rate;
- claim-level citation and date coverage;
- subject/time mismatch and irrelevant evidence rates;
- unsupported numeric, causal, and certainty claims;
- independent-source and counter-evidence coverage where material;
- monotonic response to evidence ablation;
- template similarity and control-plane leakage;
- freshness of structured market and company evidence.

### 14.4 Product targets

Before claiming "Codex-like":

- blind reviewers prefer or tie the Workbench answer against the Codex
  reference on at least half of representative long-tail tasks;
- no material regression in evidence discipline or current-data freshness;
- quick-mode median remains within the selected 60-90 second experience;
- deep mode acknowledges immediately, streams meaningful progress, and usually
  completes within five minutes.

Before claiming "stronger than Knevo" for A-share research:

- blind preference is at least 60% on a representative A-share task set;
- Workbench wins the structured-data, citation, freshness, source-lineage, and
  decision-replay dimensions without losing directness or natural language;
- differentiating capabilities such as JS-rendered source access, North
  Exchange coverage, customer/supplier relationship evidence, and scheduled
  monitoring have their own verified acceptance cases;
- no claim of superiority is made from the current nine-case engineering set.

The representative suite must expand beyond nine cases and include unfamiliar
methodology, counterfactuals, multi-entity comparisons, valuations, causal
questions, relationship research, current-market judgments, and intentionally
missing evidence. It is frozen only for release evaluation.

## 15. Error Handling and Safety

- malformed plans receive one same-episode protocol repair, not a legacy
  fallback;
- unauthorized tools and invalid query fields return explicit observations to
  the model while hard execution remains blocked;
- provider empty/error/timeout states remain distinguishable in traces;
- branch failure does not cancel independent successful branches;
- all call, time, and branch budgets descend from one root ledger;
- cancellation prevents late publication;
- no secret, database, cache, raw benchmark artifact, or private memory enters
  Git;
- no write-capable tool is exposed in the research runtime;
- no canonical runtime switch or `main` merge occurs without explicit user
  approval.

## 16. Rejected Approaches

### Keep adding deterministic routes and fixed tools

Rejected because each unfamiliar question requires another rule and the model
cannot exceed the pipeline's predefined views.

### Put all Knevo rules in the system prompt

Rejected because it consumes attention, repeats knowledge already enforceable
in code, and creates template behavior. Prompts explain goals and available
actions; evidence state and exit modules enforce truth.

### Enable unrestricted SQL in production

Rejected because it exposes physical schema and metric ambiguity, increases
injection and resource risk, and makes tests depend on generated SQL syntax.
Retained only as an isolated capability benchmark.

### Raise every run to 25-30 calls

Rejected because autonomy without useful tool granularity creates expensive
loops. Budgets expand adaptively after the model produces a concrete plan and
the governor observes real complexity or coverage gaps.

### Make Codex/Claude headless the production core

Rejected because it couples the product to local authentication, subscription
policy, CLI lifecycle, and a broad external harness. It remains a quality
reference while the production runtime stays provider-replaceable.

### Keep two permanent answer systems

Rejected because every bug and capability would require duplicate fixes. The
strangler exists to replace the legacy long-tail path, not preserve it forever.

## 17. Completion Definition

This design is complete only when:

1. long-tail tasks are represented by UserTask rather than a precompiled route
   plan;
2. the model owns ResearchPlan, queries, repairs, and stopping;
3. FinanceQuery exposes flexible structured data without unrestricted
   production SQL;
4. gaps can re-enter the same Episode under bounded repair policy;
5. quick/deep promotion and optional sub-research branches follow the selected
   policy;
6. the three-layer memory gate is active;
7. all runtime adapters share the same truth and permission contract;
8. the isolated UI/Run/SSE candidate passes representative evaluation;
9. the user separately approves any canonical 8792 canary and `main` merge;
10. the legacy long-tail answer pipeline is deleted after the rollback window.

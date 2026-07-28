# Adaptive Finance Runtime × Codex App Server Canonical Handoff

Date: 2026-07-28
Status: active; core implementation mostly complete; live release gate not green
Branch: `feat/agent-runtime-backends-verify`
Committed HEAD: `f0742f72`
Isolated working copy: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Isolated acceptance asset: `eval/acceptance-board@8279b2bd`
Canonical 8792 / `main`: unchanged

This is the canonical entry point for the next agent. It combines the product
objective, the Adaptive Runtime work, the current production-parity WIP, and the
Codex App Server ceiling experiment. Older handoffs remain evidence, but must
not be treated as a newer source of status.

## 1. Thirty-second summary

The goal is not to make five benchmark questions pass and it is not to clone
Codex Code one component at a time. The goal is a provider-replaceable finance
Workbench that feels as capable as interactive Codex on unfamiliar questions,
while being better than Knevo on A-share data, evidence lineage, point-in-time
correctness, auditability, and memory.

The selected ownership rule is:

> The model owns research strategy; code owns execution safety and publication
> truth.

The Adaptive Runtime has already implemented most of the provider-neutral
product foundation. Its latest clean five-case SDK-GPT artifact is only 3/5,
however, because the benchmark bypassed the product's Adapter-owned delivery
repair. A two-file uncommitted fix is in progress and currently red because its
fake Episode fixture is incomplete.

Separately, the user approved a small native Codex App Server experiment to
measure the quality ceiling of the full Codex generic harness plus this repo's
domain harness. The direction is approved, but the first App Server spec has an
independent `CHANGES_REQUIRED` review. It must not be implemented or run until
the experiment is made point-in-time safe, config-isolated, preregistered, and
evidence-auditable.

The next agent should first finish the two-file benchmark parity WIP and restore
a clean branch. It must then integrate—not rebuild—the isolated 28-case
acceptance-board assets. Before implementing App Server, run a controlled
headless budget/stage-gate differential and inspect knowledge-tool
discoverability. The existing headless control is prematurely stage-closed, so
comparing App Server directly against it would confound generic-harness quality
with a self-imposed time handicap. Do not start by rerunning either the whole
five-question canary or all 28 product cases.

## 2. Final product objective

Build a vertical financial research product with all of the following:

1. **Codex-like agency**
   - Understand the literal user ask before routing or retrieving.
   - Ask one concise clarification only when ambiguity materially changes the
     answer; otherwise use the default A-share assumption.
   - Let the model decompose an unfamiliar task, form hypotheses, select tools,
     rewrite failed queries, decide whether evidence is sufficient, and stop.
   - Preserve one continuous Episode history across tool use and bounded
     verifier repair instead of rebuilding a lossy prompt at every step.

2. **A-share truth discipline stronger than a generic agent**
   - Use local structured market/company data, Wiki, graph, official evidence,
     and public search through typed read-only tools.
   - Enforce subject identity, information cutoff, freshness, source lineage,
     evidence independence, contradictions, and numeric traceability.
   - Fail honestly when evidence is missing; never turn a provider timeout or
     an old snapshot into a confident market judgment.

3. **Product-grade execution**
   - One root call/time/branch budget, cancellation, streaming progress,
     private diagnostic artifacts, memory gates, and auditable Runs.
   - Fast deterministic workflows may remain for truly stable operations, but
     long-tail research must not depend on adding another route, question type,
     output template, or hard-coded retrieval plan.
   - Runtime backends remain replaceable: GLM is the current test provider; GPT
     and other models can use the same contracts later.

4. **Measurable success**
   - Before claiming “Codex-like”, blinded reviewers should prefer or tie the
     Workbench against a Codex reference on at least half of representative
     long-tail tasks, with no freshness or evidence regression.
   - Before claiming “stronger than Knevo”, integrate the already-built
     `eval/acceptance-board@8279b2bd`: 28 product cases and 22 frozen Knevo
     snapshots with answer hashes, collection route, asked-at time, credits,
     and visible tool traces where available. Do not build a second suite.
   - Complete the missing scoring seam. The existing board captures real API
     traces and reports answered/degraded/failed, but intentionally does not yet
     compile `expect_facts`, `pass_rule`, and blind-reference judgments into a
     `passed` verdict.
   - Score Knevo comparison on two separate axes. **Truth** covers subject/time
     alignment, cutoff compliance, numeric traceability, citations, freshness,
     contradictions, and honest gaps. **Experience** covers directness, time to
     a usable answer, number of required follow-ups, irrelevant retrieval,
     readability, and decision usefulness. A truth violation cannot be offset
     by fluent prose.
   - Keep `aggregate_gate=0.0` observational until the first valid baseline and
     rubric calibration exist. Then preregister a non-zero threshold before the
     broader scored run; do not tune the gate to the observed answers.
   - Five frozen engineering cases are a runtime-seam release canary. The 28
     acceptance cases, executed through the real Conversation API path, are the
     primary product-readiness denominator. Neither alone proves superiority.

5. **Explicit latency modes**
   - Fast answers and deep research are different product contracts, not one
     90-second constant.
   - Quick/standard mode should answer or honestly narrow the task within the
     selected 60–90 second experience.
   - Deep mode should acknowledge immediately, stream meaningful research
     progress, and may use a multi-minute envelope when the question genuinely
     needs broader evidence.
   - The model may propose deep research; `ModeGovernor` admits it from
     observable complexity, user intent, and root budget. A question type alone
     must not force every run into the slow lane.

## 3. Root-cause model and architecture principle

The historical failure was not “too few tools” or simply “too few routes”. The
Workbench repeatedly compressed the user's ask, observations, and model state
into fixed task/output contracts. It then used templates and prompt rules to
compensate for the lost reasoning continuity. That made the harness subtract
capability from the base model.

Interactive Codex works better because two harnesses compose:

- the **generic harness** supplies continuous context, tool-call iteration,
  recovery, permissions, context management, and stopping;
- the repo's **domain harness** supplies `AGENTS.md`, skills, finance tools,
  data semantics, evidence rules, cutoffs, and publication gates.

The product should combine those strengths without outsourcing its truth model
or becoming dependent on local Codex authentication.

A second, now-proven problem sits below that architecture hypothesis: the
headless reference lane can close research before the model has finished an
otherwise valid tool sequence. This is a control-policy defect, not evidence
that a generic runtime is unnecessary. The two hypotheses must be tested in
order:

1. Does removing the premature stage gate make the existing headless harness
   good enough?
2. After a fair budget, does native App Server still add material quality from
   continuous generic harness and natural repo discovery?

```text
raw user ask
    |
    v
UserTask + minimal ambiguity handling
    |
    v
continuous model Episode
  plan -> tool -> observe -> revise -> bounded repair -> finish
    |                     |
    |                     +--> model owns research decisions
    v
typed finance tools + EvidenceLedger
  permissions / safe query compilation / PIT cutoff / lineage / root budget
    |
    v
structural + semantic publication verification
    |
    v
public answer + citations + SSE progress + private diagnostics
```

### Ownership boundary

| Model owns | Code owns |
|---|---|
| User-intent interpretation and material clarification | Default market assumption and explicit ambiguity policy |
| ResearchPlan, hypotheses, comparison axes, query selection | Tool permissions and typed input validation |
| Tool order, query rewrites, interpretation, natural-language answer | `FinanceQuery` compilation, resource limits, and no unrestricted production SQL |
| Whether another useful research action is worth proposing | Root budget and progress-positive `RepairAdmission` |
| Wording, structure, caveats, and stopping proposal | Evidence identity, cutoff, freshness, citations, contradictions, and final release gate |

Reusable principle: tools, memory, and verifiers must be **capability
monotonic**. They should add information or block false publication; they must
not replace the model's basic ability to understand and answer an unfamiliar
question.

## 4. Exact working state and safety boundary

### Development copy

- Path: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
- Branch: `feat/agent-runtime-backends-verify`
- HEAD: `f0742f72` (`docs: design codex app server ceiling benchmark`)
- This is an isolated full working copy with its own `.git`, not the dirty
  primary workspace and not the older formal runtime copy.

### Uncommitted WIP — preserve it

Only these two files are modified:

- `scripts/run_agent_runtime_benchmark.py`
- `intelligence/tests/test_run_agent_runtime_benchmark.py`

Do not reset, overwrite, or recreate this work from the older
`/Users/a77/.finance-runtime/agent-runtime-backends-c4673667` copy. That older
copy remains at `69f9cf17` and does not contain commits through `f0742f72`.

### Out of scope without new user approval

- Do not merge `main`.
- Do not switch or restart canonical 8792.
- Do not treat 8799 as canonical or overwrite its state.
- Do not delete the legacy answer path yet.
- Do not commit `.env*`, credentials, databases, private memory, benchmark
  artifacts, caches, or user data.
- The primary workspace `/Users/a77/finance-workspace-private` is heavily dirty
  with unrelated user/agent work. It is not a safe development tree.

## 5. What has already been built

### 5.1 Model-owned task and research state

- `UserTask` replaces the precompiled long-tail route as the semantic task
  representation.
- The model creates and revises `ResearchPlan` instead of receiving a fixed
  retrieval plan and answer outline.
- A continuous `EpisodeSession` preserves model turns, tool observations,
  repairs, and finalization in the same history.
- `RepairGoal` re-enters that Episode after a typed gap or invalid finish.
- `ModeGovernor` supports quick/deep promotion from observable complexity;
  deep mode is not assigned to every task by question type.
- Optional sub-research branches are bounded and are not spawned by default.

### 5.2 Provider-neutral runtime seams

- Continuous GLM, OpenAI Agents SDK with GLM/GPT, and benchmark-only Codex
  headless backends share the same task, tool, budget, cutoff, and verification
  contracts.
- Runtime-specific transport failures remain typed rather than silently falling
  back to another backend.
- `ContinuousTurnAdapter` is the single product owner for resumable execution,
  same-Episode delivery repair, structural verification, semantic verification,
  and public projection.

### 5.3 Finance retrieval and evidence

- `FinanceQuery` exposes semantic datasets and fields without arbitrary
  production SQL.
- `EvidenceSearch` and the research registry expose bounded market, mainline,
  valuation, financial, knowledge, graph, official-evidence, news, and web
  capabilities.
- Entity anchors let valuation and financial tools resolve company name plus
  security code once at the shared registry seam.
- `EvidenceLedger` tracks source identity, date, cutoff validity, independence,
  duplicate content, output bindings, gaps, and coverage deltas.
- One registry-owned effective cutoff drives execution, future filtering,
  `ProviderTrace`, and `QueryLedger`; historical questions cannot silently use
  current news.
- Current market/valuation evidence is rejected when its served date is stale,
  future-dated, missing where required, or mismatched with the data root.

### 5.4 Reliability and bounded repair

- `RootBudgetLedger` accounts for calls, seconds, branches, duplicate grants,
  and the root deadline.
- Repair admission is centralized in `RepairCoordinator`; no evidence/coverage
  progress means no extra budget.
- SDK timeout delivery may receive one tool-closed, zero-tool-call completion
  attempt when useful evidence already exists.
- Duplicate tool content does not re-enter the model as new evidence.
- Mandatory capability progress and remaining tool budget are model-visible.
- Slow research is closed early enough to reserve answer-delivery and semantic
  verification time.
- Semantic provider retries share one bounded deadline; transient semantic
  outage may preserve a structurally valid grounded draft as an explicit
  partial, while auth/format/contract failures still fail closed.

### 5.5 Product surface and safety

- RunStore, SSE, React progress, cancellation, and reconnect replay use real
  Episode events rather than a synthetic four-step animation.
- Public progress is sanitized; TaskFrame, route hashes, raw Episode diagnostics,
  and internal artifacts do not leak into the UI.
- `MemoryGate` separates session context, private durable memory, and reusable
  project knowledge.
- Code root and finance data root are explicit; the earlier “all data is 7/1”
  issue was caused by composing a clean code tree with the wrong data root.

## 6. What has actually been verified

### Deterministic verification

Before the present two-file WIP, the latest committed delivery/deadline batch
reported:

```text
OpenAI Agents runtime: 28 passed, 1 skipped
Semantic verifier: 144 passed
Focused composition: 540 passed, 1 skipped
Executable intelligence suite: 2919 passed, 1 skipped
```

Older reports with 11 `subconscious/userspace` failures were traced to production
environment-path overrides leaking into isolated tests. Unsetting those
overrides made the executable suite green; no gate was loosened.

Do not report the current working copy as green. The new production-parity test
is intentionally red until its Episode fixture is repaired.

### Latest clean live SDK-GPT artifact

Artifact (outside Git):

`/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-28-7e91f74b.json`

SHA-256:

`312504c80ff9c320f9812b7bd855a5de4ad6c741fd436c9128c651a45ce9a639`

| Case | Result | Latency | Tools | Interpretation |
|---|---:|---:|---:|---|
| `rebound-duration` | completed/repaired | 54.5s | 1 | Useful and grounded |
| `ruihuatai-valuation` | partial/`sdk_timeout` | 60.0s | 2 | Mandatory evidence succeeded; answer was not delivered |
| `weekly-market-cause` | partial/`sdk_timeout` | 60.0s | 5 | Mandatory evidence succeeded; optional empty news checks consumed the tail |
| `current-mainline` | completed/passed | 56.5s | 2 | Freshness and semantic deadline fixes worked |
| `unfamiliar-methodology` | completed/passed | 36.0s | 0 | Generic reasoning path worked |

The gate is false: 3/5 completed and two protocol/delivery failures. This is
release evidence, not a development score to optimize question by question.

### Eight historical headless artifacts: what they do and do not prove

An independent audit correctly observed the following completion counts:

```text
0d260bda  2/5    3b3befc7  3/5    4a2fb783  2/5    4b9730a3  4/5
9487df3a  3/5    b45c4d7b  2/5    c8222ea9  1/5    e179b15c  3/5
```

It also correctly observed:

- `unfamiliar-methodology`, the zero-tool reasoning case, completed 8/8;
- `weekly-market-cause` completed 0/8;
- several otherwise sensible research chains were denied a new tool with
  `research_stage_closed`.

But these are **not eight repeated samples of the same code**. Each artifact's
`source_revision` is the eight-character identifier in its filename. The
revisions include changes such as:

```text
0d260bda expose live headless research budget
4a2fb783 promote causal headless cases to deep mode
4b9730a3 align headless reasoning with research tier
9487df3a reserve headless finalization window
b45c4d7b reserve enough time for grounded finalization
3b3befc7 give headless semantic judge a full reserve
c8222ea9 share headless provider with semantic verifier
e179b15c debit headless tools against root budget
```

Therefore the 1/5–4/5 range cannot be called pure model variance. Code, time
policy, and verifier composition changed between runs.

The weekly case also did not fail identically eight times:

- 4/8 traces contain explicit `research_stage_closed`;
- 2/8 additional traces completed all six allowed calls and then ended in
  `headless_timeout`;
- 1/8 timed out after four calls rather than hitting the call cap; its fourth,
  empty `evidence_search` reduced the recorded research remainder from about
  44.9 to 18.7 seconds;
- 1/8 was rejected by the headless protocol before any tool call;
- one promoted run had 180 effective seconds and 10 successful calls, then its
  eleventh request was rejected by `research_stage_closed`;
- none of the eight produced a formally completed weekly result.

Under a broad definition, seven of eight runs were constrained by a stage gate,
call cap, or wall-clock deadline. Budget is therefore the dominant experimental
confound. The mechanisms are not interchangeable, however: removing only the
stage floor does not test the six-call cap, and raising only the call cap does
not test the wall-clock deadline.

The 180-second trace does not prove that more budget is ineffective. It reveals
what happens after budget expands: the model issued six `news_search` requests
(five completed and the final one stage-closed) and four `finance_query`
requests. Extra time increased repeated same-tool research without producing a
completed causal attribution. Duplicate strategy and evidence gain per call
must therefore be observed alongside budget.

### Exact current headless budget pathology

For the current standard benchmark path:

```text
ResearchPolicy.standard = 90 seconds / 6 tool calls / 20-second base reserve
benchmark headless override = 30-second synthesis reserve
Codex command timeout = 90 - 30 = about 60 seconds
HeadlessToolGateway finalization floor = 65% of 60 = about 39 seconds
new tools rejected once remaining research time <= 39 seconds
```

In practice, the model gets only about 21 seconds of the 60-second command
window before the gateway can return `research_stage_closed`. The outer
30-second synthesis reserve and the gateway's 39-second floor overlap, creating
a double reservation. This is more severe than simply saying “90 seconds is
short”.

The fix must not be guessed by setting production to 600 seconds and 30 calls.
First isolate the stage gate at the same total budget; then test a larger
diagnostic ceiling only if needed.

### Completion status is not the same as answer usefulness

At least one historical weekly answer correctly did all of the following:

- corrected the false premise: the full week rose 0.47%, while Friday fell
  1.61%;
- cited breadth and turnover deterioration;
- described an evidence-bounded risk-appetite/position-reduction mechanism;
- refused to invent a unique external catalyst.

It was still recorded as `partial`. The strict contract is useful for release
truth, but a binary completed count alone understates user-perceived quality.
Future comparisons must report both typed contract status and blind answer
quality.

The reverse inconsistency also exists. `unfamiliar-methodology` completed 8/8,
but its recorded `task_alignment_score` alternated between 0.25 and 1.0. A
completed envelope is not a stable quality score; contract completion, task
alignment, and blind usefulness remain separate dimensions.

### Knowledge discoverability is a real question, but the tool is not absent

The current headless prompt explicitly prohibits file reads and runs Codex in a
temporary directory. It can see finance knowledge only through the registered
gateway. Native App Server would naturally discover repo files, which is a real
experience difference.

However, the Workbench already has an `evidence_search` capability backed by
closed-loop Hybrid RAG (narrow, broad, counter; BM25/vector/rerank depending on
index availability). A fresh dry-run of the current `f0742f72` working copy
authorizes it for the market, valuation, causal, and mainline cases. That is a
current-code observation, not a fact contained in the pinned `e179b15c`
baseline: the baseline has `contract=null` and cannot prove its historical
allowed-capability set. After Phase A, generate and pin a clean dry-run receipt
before using capability authorization as an experimental premise.

For `ruihuatai-valuation`, seven traces reached tools and all seven selected the
same pair—`market_data` plus `financial_data`, with order occasionally reversed.
Four of the seven completed. The useful answer already contained PB, market
capitalization, revenue growth, gross margin, and the correct judgment that
negative TTM PE makes PB more suitable. This stability makes simple “the model
did not notice a knowledge tool” less likely than either deliberate sufficiency
judgment or disagreement between model completion and the release contract.

Do not blindly add an unrestricted wiki grep tool. First distinguish:

1. the current clean contract did not actually expose the capability;
2. the model deliberately considered market plus financial evidence sufficient;
3. the mandatory evidence plan or finish hint caused early stopping;
4. the Hybrid index omitted the relevant Wiki pages/chunks;
5. retrieval found pages but semantic/cutoff filtering rejected them;
6. the tool was too slow for the remaining research window;
7. the tools and answer were already useful, but `required_outputs` or verifier
   completion disagreed with the model's valid stopping judgment.

The only historical weekly trace that selected `evidence_search`
(`9487df3a`) observed its remaining research time fall from 44.891 to 18.706
seconds: about 26.2 seconds for one empty retrieval, roughly three times the
usual 8-second inter-tool interval. Tool latency is therefore an observed Phase
C factor, not merely a hypothesis. Because these are independent Episodes, do
not claim the model learned this cost across runs; the defensible claim is that
one such call consumed most of that run's remaining decision window.

Two knowledge roots are currently in play and must not be treated as aliases:

```text
/Users/a77/知识库                  git HEAD 6e1185de; .rag_index
/Users/a77/knowledge-base-private  git HEAD 883815c9; .rag_index + .rag_index_full
```

All eight headless artifacts record `/Users/a77/知识库/wiki`. The current
瑞华泰 entity page and latest-logic-card files have identical SHA-256 in both
roots, but `relations/evidence_index.json`, Git revision, index inventory, and
modification times differ. Current equality of two files cannot prove that the
07-27 benchmark queried equivalent snapshots. Phase C must select, PIT-freeze,
and hash one canonical Wiki plus index before replay.

## 7. Current WIP: benchmark must exercise the product path

### Proven defect

The benchmark called:

```text
runtime.run() -> benchmark-owned structural verify -> semantic verify
```

The product calls:

```text
runtime.start() -> ContinuousTurnAdapter
  -> timeout/invalid-finish RepairGoal
  -> same EpisodeSession delivery repair
  -> structural + semantic verification
```

Therefore the live release runner skipped the component that owns the already
tested SDK delivery repair. This explains how focused tests could be green
while the official five-case artifact still exposed raw timeouts.

### Existing uncommitted implementation

The WIP already:

- adds a semantic capture wrapper;
- composes research benchmark arms through `ContinuousTurnAdapter`;
- reaches one `resume()` call in the public CLI regression.

The remaining red is a fake-fixture contract defect:

- the fake exposes only one evidence capability;
- `current-mainline` requires `market_data + mainline_context`;
- all three required outputs must be bound;
- every `CallbackEpisodeSession.resume()` must append a `model_turn` after
  `repair_goal` and `repair_reentry`.

### Exact completion steps

1. Repair only the fake fixture with both mandatory evidence capabilities,
   complete bindings, and the required resumed model turn.
2. Run:

   ```bash
   env -u FORESIGHT_USERS_DIR \
     /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
     intelligence/tests/test_run_agent_runtime_benchmark.py \
     -k production_adapter_delivery_repair
   ```

3. Run the complete benchmark test file and preserve compatibility for fake or
   legacy runtimes that implement only one-shot `run()`.
4. Add the separate typed-accounting regression:
   - `sdk_timeout` -> `invalid_actions == 0`;
   - `sdk_invalid_finish` -> `invalid_actions == 1`.
5. Run focused benchmark/runtime/Adapter suites, then the executable full
   `intelligence/tests` suite.
6. Review for duplicate repair loops, gate relaxation, question-specific
   branches, multiple semantic-verifier owners, and risk files.
7. Commit the product-parity fix separately. Only a clean revision may produce
   the next live artifact.

Do not increase the timeout, ignore protocol issues, or synthesize an answer
directly from evidence. Those approaches hide the skipped composition root.

## 8. Why Codex App Server is being evaluated

The current SDK lane provides a model/tool loop, but it does not automatically
reproduce the complete behavior of the interactive Codex product. App Server is
the supported process interface to the Codex runtime: it exposes Codex threads,
turns, items, tool events, usage, interruption, and server-to-client requests
over JSON-RPC.

The approved Option A is a **capability-ceiling benchmark**, not a production
migration:

- run the same frozen questions through the native Codex runtime;
- let Codex naturally discover this repo's instructions, skills, and read-only
  query helpers;
- compare it primarily with the already-frozen Codex headless artifact;
- use the result to decide whether a bounded App Server adapter and finance-tool
  bridge are worth building.

This experiment tests the combined value of continuous generic harness plus
naturally discoverable domain harness. It does not by itself prove which
individual system-prompt or tool feature caused a gain.

It also must not be compared only with the current constrained headless lane.
App Server has no Workbench `research_stage_closed` gate or six-tool cap, so it
would likely win some cases by receiving more research time even if its generic
harness added no other value. The primary control must be a preregistered,
fair-budget headless artifact produced after the budget differential below.

### Current App Server status

- Direction: approved by the user.
- First design: committed at
  `docs/superpowers/specs/2026-07-28-codex-app-server-ceiling-benchmark-design.md`.
- Independent review: `CHANGES_REQUIRED`.
- Implementation: not started.
- Live App Server five-case run: not performed.

No agent may treat the design's header `approved option A` as permission to run
the current experiment unchanged.

## 9. Mandatory App Server spec corrections

All of the following belong in the revised spec and its acceptance tests.

### P0: experimental validity and safety

1. **Physical point-in-time data root**
   - All five cases use `as_of=2026-07-24`, while the live DuckDB contains data
     through 2026-07-27.
   - A prompt instruction and a fake `currentTime/read` response are not enough:
     shell/Python can still read future rows.
   - Use a physically isolated PIT snapshot/data root capped at the case cutoff,
     plus a post-run lookahead audit. `currentTime/read` should also return the
     case cutoff for consistency.

2. **Isolated Codex configuration**
   - App Server has no assumed `--ignore-user-config` switch.
   - Do not inherit global low reasoning effort, custom providers, MCP servers,
     plugins, notifications, or sensitive config fields.
   - Use a dedicated minimal `CODEX_HOME` or an equivalently strict tested
     overlay. Record only a sanitized effective-config fingerprint.

3. **Controlled filesystem discovery**
   - `readOnly` blocks writes; it does not prove that reads are restricted to
     `cwd`.
   - Run against a clean detached instruction/code root plus the PIT data root,
     not the dirty primary workspace or unrelated worktrees/memory.
   - Define acceptance as zero writes to repository/private data. Record expected
     App Server state writes separately with before/after fingerprints.

4. **Pre-registered artifacts and decision rule**
   - Pin every baseline path and SHA-256 before viewing App Server answers.
   - Pre-register the rubric and pass threshold; randomize backend labels and
     use an independent reviewer.
   - Suggested minimum: App Server wins directness on at least 4/5 cases, with
     zero lookahead and zero untraceable material numeric claims.

### P1: comparability and evidence discipline

5. **Primary control is Codex headless**
   - Same Codex binary/model gives the most informative comparison of harness
     ownership.
   - Use the fair-budget, same-revision headless control produced by the
     preregistered budget differential, not one of the evolving 0d260bda–e179b15c
     artifacts as if it were an identical replicate.
   - GLM and SDK-GPT change both model and harness, so they are background
     references only.
   - Record that the existing headless lane ran from a temporary directory and
     saw finance capabilities through its gateway rather than natural repo
     discovery; this is a variable to interpret, not hide.

6. **Explicit standard-tier mapping**
   - Every frozen case is `tier=standard`.
   - Map `standard -> medium` explicitly in `turn/start`; do not inherit a
     global `low` setting.

7. **Structured source traceability**
   - Require parsable `sources[]` entries with source/file/table identity and
     date range.
   - Independently sample material numeric claims and verify that each can be
     traced to a cutoff-valid source.
   - Fluent unsupported prose must lose the evidence dimension.

8. **Reuse existing redaction and artifact hashing**
   - Reuse `_sanitize_diagnostic_value` and the existing path/secret rules.
   - Drop reasoning items and agent-message deltas; do not persist hidden
     reasoning, secrets, raw local paths, or full tool payloads.
   - Define the artifact SHA-256 over the payload with its own hash field
     excluded, matching the existing `_artifact_hash` convention.

### Protocol and operational correctness

9. **Typed overload/error handling**
   - Handle JSON-RPC transport `-32001` if the observed binary emits it, but do
     not assume it is the only overload signal.
   - Classify terminal `TurnError.codexErrorInfo`, including
     `serverOverloaded`, `usageLimitExceeded`, `unauthorized`,
     `contextWindowExceeded`, and `internalServerError`.
   - Retry overload once with bounded backoff; never blindly retry usage-limit
     or authentication failures.

10. **One server-request dispatcher**
    - Explicitly handle or immediately reject all observed server-to-client
      requests, including `currentTime/read`, approvals, tool calls,
      `requestUserInput`, MCP elicitation, auth-token refresh, and attestation.
    - Unsupported requests must receive a typed rejection, not hang until the
      case timeout.

11. **Own process only**
    - Spawn a dedicated stdio child process.
    - Do not connect to desktop/shared daemons, proxies, or an already-running
      App Server instance.

12. **Quota and state radius**
    - Record sanitized account/rate-limit state before and after the run.
    - Stop at the pre-registered quota threshold so the experiment does not
      consume the user's interactive allowance unexpectedly.
    - Fingerprint repository, PIT data, Codex binary, isolated config, and
      allowed App Server state before and after.

13. **Instruction-conflict observation**
    - Repo instructions contain write-oriented correction, memory, and Git
      workflow rules that conflict with a read-only experiment.
    - Keep the experiment non-interactive and deny writes, but record attempted
      writes/retries as an observed domain-harness interference metric.

## 10. Frozen cases and preregistered comparison material

Question file:

`/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json`

All five cases use `as_of=2026-07-24` and `tier=standard`:

- `rebound-duration`
- `ruihuatai-valuation`
- `weekly-market-cause`
- `current-mainline`
- `unfamiliar-methodology`

Primary Codex headless baseline:

`/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-headless-2026-07-27-e179b15c.json`

SHA-256:

`cb7e0d1ad81b989e0c3b00d7d2af33d59a31073e1fd39e82beb0644a479d8b40`

Current SDK-GPT background baseline:

`/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-28-7e91f74b.json`

SHA-256:

`312504c80ff9c320f9812b7bd855a5de4ad6c741fd436c9128c651a45ce9a639`

Before the App Server run, the revised spec must additionally pin the exact PIT
snapshot hash, clean instruction-root revision, Codex binary version, isolated
config fingerprint, output path, blinded comparison path, and reviewer rubric.

### Product acceptance board already exists on an isolated branch

Do not build a second product evaluation suite. The following assets exist only
on branch `eval/acceptance-board`, tip
`8279b2bd67faf0e8a2adc570dadaa8482c973b53` (2026-07-27 14:24 +08:00):

- `intelligence/eval/acceptance.py`;
- `intelligence/eval/cases/acceptance_cases.json`;
- `intelligence/tests/test_acceptance_board.py`;
- 22 `intelligence/eval/cases/reference_snapshots/*.knevo.json` files;
- two real-path trace runs under `intelligence/eval/runs/`;
- Knevo methodology notes q13/q14/q15 and the updated question bank.

The branch is not contained in `main` or `feat/agent-runtime-backends-verify`.
Its merge base with the current runtime line is `0430d544`; the acceptance
branch is 10 commits ahead of that base while the runtime branch has advanced
hundreds of commits. Integrate the evaluation assets deliberately after Phase
A; do not assume the primary workspace contains them and do not merge to
`main`.

Git addressing in this isolated copy is non-obvious and mandatory:

- commit objects `f03b66e5` through `8279b2bd` are already present and resolve
  with `git cat-file` / `git ls-tree`;
- there is **no** local `refs/heads/eval/acceptance-board` here;
- this copy's `origin` points to the older runtime copy
  `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667`, not the primary
  workspace that owns the branch ref.

Therefore use commit SHA `8279b2bd` and its parent range to read or integrate
the assets. Do not address them by branch name, add another remote, or fetch
from the current `origin`.

### The 28 product cases

The case distribution is:

```text
high_freq  10
mid_freq    8
long_tail  10
total      28
```

They cover daily market answers, mainline/stage/sentiment, theme and company
research, multi-table/time-series questions, valuation, future/non-trading
dates, empty/nonexistent tables, unit anomalies, data contradictions, strict
definitions, cutoff leakage, citations, and multi-turn consistency.

Cases may contain exact facts plus tolerances, `must_mention`,
`expect_refusal`, `forbid_phrases`, `forbid_future_data`, known-data-bug
annotations, follow-ups, and a human-readable `pass_rule`. For example A1 pins
turnover, limit-up/down counts, and index change with numeric tolerances; C1
requires an explicit no-data response and forbids invented market numbers.

The product path is part of the contract:

```text
ASK_CONTINUOUS_RUNTIME=on
POST /api/conversations
POST /api/conversations/{id}/messages
poll public messages to terminal status
read /api/runs/{run_id}/context and /trace
```

Unit tests, dry-runs, direct provider calls, benchmark-only arms, and detached
answer generation do not count toward the 28-case product pass rate.

### Current board implementation boundary

`acceptance.py` currently provides:

- deployment preflight for health, code/data roots, dependencies, runtime, and
  LLM configuration;
- real Conversation API execution with multi-turn continuity;
- Run evidence/trace collection;
- immutable external-reference freezing with provenance and SHA-256;
- a board that classifies not-run, no-output, degraded, and answered-awaiting-
  judgment.

It **does not yet produce pass/fail verdicts**. Its source explicitly says that
deterministic `agent_eval` gates and blind reference review must supply the
final pass count. `acceptance_cases.json.aggregate_gate` is intentionally 0.0.

The probe depends on these current public shapes and must fail visibly if they
drift:

```text
POST /api/conversations
POST /api/conversations/{id}/messages
GET  /api/conversations/{id}/messages?user=...
GET  /api/runs/{run_id}/context -> evidence[], gaps[]
GET  /api/runs/{run_id}/trace   -> [{name: ...}]
message -> status, content, run_id, invoked_skill_ids, citations, degrades
```

An earlier probe incorrectly read `tools_called` from the message body, where
that field does not exist, and silently recorded zero tools for every run.
Current compatibility work must read the real public message/Run fields; a
missing field is schema drift to report and test, not permission to substitute
an empty list.

The two stored runs are evidence, not a scored baseline:

- `20260727T025642Z.json`: one case / one answered turn;
- `20260727T032229Z.json`: ten long-tail cases / twelve answered turns;
- both passed preflight at runtime revision `17e0b21a`, backend `sdk_gpt`;
- neither run nor its cases contain a `passed` field.

Therefore the current 28-case pass rate is **unknown**, not 0 and not the number
of completed message envelopes. The scoring compiler and blinded review seam
must be completed before a baseline percentage is reported.

### Frozen Knevo reference coverage

The branch contains 22/28 Knevo snapshots collected via `cdp_readback` from the
user's signed-in Chrome. A snapshot records `asked_at`, answer hash, conversation
identity, the original prompt, credits where available, and visible tool-call
traces in `source_meta.tool_calls`.

The six cases without a Knevo snapshot are:

```text
A8-market-stage
A9-sentiment-contradiction
B6-sellside-distillation
C3-empty-table
C4-unit-anomaly
C8-nonexistent-table
```

These omissions are mostly intentional: several questions use local-only
definitions, known dirty tables, or internal ingest semantics for which Knevo
is not an oracle. Workbench product acceptance still uses all 28 cases. Knevo
comparison uses only cases and dimensions for which the individual snapshot is
eligible; do not blindly divide every cross-product score by 22.

The snapshot metadata already documents material limitations:

- A2/C7 contain hindsight and cannot validate historical forecast correctness;
- A5/A6/A10 reconstruct historical structure from later/partial material and
  are useful mainly for narrative structure;
- project-defined terms such as “双红”, stage-day, and internal ingest labels
  must not become external-agent vocabulary tests;
- `must_mention` is a Workbench product-language check, not a cross-agent
  literal-word gate;
- Knevo's strongest reference role is methodology, retrieval breadth, and
  answer organization, while local structured tables remain the oracle for
  project-defined historical cross-sections.

Existing older pilots remain useful context:

- `docs/learning/knevo-distill/ab/AB-001-knevo.md`;
- `docs/learning/knevo-distill/ab/AB-002-knevo.md`;
- `docs/learning/knevo-distill/ab-ledger.md`;
- `docs/learning/knevo-vs-workbench-技能包对比台账.md`.

The 28-case board and its 22 snapshots supersede the plan to create a new Knevo
suite from scratch. They do not eliminate the need to normalize truth and
experience scores or to complete the missing verdict pipeline.

### Codex reference status

The acceptance branch planned full 28-case Codex references through
`codex_exec`, but its recorded 2026-07-27 sidecar route was unavailable. Recheck
current state rather than repeating that stale diagnosis:

- use the full binary path, not `PATH` assumptions;
- use the user-selected `gpt-5.6-sol`, not the branch's older example model;
- keep reference answers PIT-safe and record binary/model/config/cutoff
  provenance;
- do not regenerate a reference after seeing the Workbench answer.

Codex references are comparative quality material. Only the real Conversation
API run counts as the Workbench product result.

Observed local binary at design time:

```text
/Applications/ChatGPT.app/Contents/Resources/codex
codex-cli 0.146.0-alpha.3.1
```

Re-verify rather than assume these values at execution time.

## 11. Ordered optimization strategy

### Phase A — close current production-parity WIP

1. Fix the fake Episode fixture; do not change product behavior merely to make
   the fake pass.
2. Add typed timeout-versus-invalid-action accounting.
3. Run focused and executable full tests.
4. Commit a single benchmark-parity concern and restore a clean tree.

Exit criterion: the release benchmark and Workbench both exercise the same
Adapter-owned repair/verification path.

### Phase A.5 — integrate the existing acceptance-board assets

After Phase A is committed and the tree is clean:

1. Create an integration point from the current runtime branch; do not work in
   the dirty primary workspace and do not merge `main`.
2. Port or cherry-pick the ten ordered commits by SHA range
   `f03b66e5^..8279b2bd`; do not use the absent branch ref or fetch from the old
   runtime `origin`. Review the small compatibility surface against the current
   API/Run schema.
3. Preserve all frozen answers, hashes, `asked_at`, collection routes, snapshot
   caveats, and the two historical trace runs unchanged.
4. Run `test_acceptance_board.py` plus current API/Run-store tests.
5. Verify `board` can read the imported historical runs without claiming they
   have pass verdicts.
6. Add a pinned provenance note recording acceptance source branch/tip and the
   resulting integration commit.

Do not run all 28 questions during integration. The purpose is to make the
existing evaluation asset available to the runtime branch, not to consume model
quota before the budget and retrieval seams are fixed.

Exit criterion: the current runtime line has one canonical 28-case definition,
22 immutable Knevo snapshots, and a working real-path trace board without
duplicating or rewriting the suite.

### Phase B — isolate the headless budget/stage-gate confound

Do not change global `ResearchPolicy` constants as the first experiment. Add a
benchmark-only, typed budget profile or dependency-injection seam so production
defaults remain unchanged and the artifact records the exact profile.

Run a sequential differential on three diagnostic cases:

- `rebound-duration`: stage/time constrained forecast;
- `weekly-market-cause`: stage/call constrained causal research with repeated
  same-tool behavior;
- `ruihuatai-valuation`: stable two-tool answer that separates research budget
  from completion/verifier disagreement.

The observed inter-result interval is roughly 8 seconds. With a 90-second total,
30-second reserve, and normal model delivery time, a 12-call cell cannot be
reliably exercised. Do not pretend `90s/12 calls` isolates the call cap when the
wall clock reaches terminal first.

Use four preregistered profiles whose pairwise comparisons are physically
exercisable:

| Profile | Total | Calls | Gateway floor | Pairwise purpose |
|---|---:|---:|---:|---|
| A control | 90s | 6 | current 0.65 | current behavior |
| B floor ablation | 90s | 6 | dynamic 0.65 off; minimal delivery buffer only | A→B isolates premature floor |
| C long / capped | `T_long` | 6 | minimal delivery buffer only | B→C isolates additional wall-clock room while call cap stays fixed |
| D long / expanded | `T_long` | 12 | minimal delivery buffer only | C→D isolates the six-call cap at the same longer wall clock |

Derive and preregister `T_long` from observed p90 inter-call latency, initial
model latency, 12 calls, and a final-delivery buffer. The current evidence says
150 seconds is the minimum plausible envelope; use 180 seconds if the derived
budget is not safely below 150. The purpose is to make the D cell capable of
actually reaching call 7–12, not to recommend 180 seconds as the standard
product SLA.

If D still times out before the intended cell is exercised, mark the ablation
invalid rather than interpreting it as a quality failure. A 240-second/12-call
deep profile or 600-second/30-call capability ceiling may be used only as a
pre-registered second stage.

Use the same source revision, binary, model, PIT data, prompt, and verifier.
Pre-register the profiles and artifact paths. Because model output is
stochastic, a single result is directional only; use one bounded confirmation
run only when the first pair changes the decision. Do not fall back to endless
five-case reruns.

Measure:

- whether the next intended tool was admitted;
- useful evidence gained per call;
- repeated same-tool request rate, repeated-query/content rate, and unique
  evidence hashes per call;
- formal bindings and contract status;
- blind directness/usefulness;
- latency and unsupported claims;
- whether the model continued researching after evidence was already
  sufficient.

Decision:

| Result | Interpretation |
|---|---|
| B improves over A | Floor/double-reserve is causal |
| C improves over B with both capped at 6 calls | Wall-clock envelope matters before call-count freedom |
| D improves over C | Six-call cap is independently causal |
| D increases repeated calls but not unique evidence/quality | Tool-result quality or finish/progress judgment is primary |
| D cannot physically exercise calls 7–12 | Experiment is invalid; enlarge only the diagnostic envelope |
| Only the explicit deep profile helps | Product needs a quick/deep latency policy; App Server is not the root fix |
| Valuation remains useful but flips completed/partial | Contract/verifier completion is misaligned with answer quality |
| No profile materially improves answer quality | Generic harness/repo discovery remains a stronger App Server hypothesis |

Exit criterion: App Server no longer receives an unearned advantage from the
control lane's double reserve.

### Phase C — diagnose retrieval discoverability and causal-contract fit

Before adding a new wiki tool:

1. Select the canonical Wiki root; prove it is not an alias of the alternative;
   record Git revision, index path/freshness, key-file hashes, and a PIT snapshot.
2. After Phase A is clean, generate a pinned dry-run artifact that records
   contract capabilities; do not infer them from `e179b15c.contract=null`.
3. Replay `evidence_search` directly for 瑞华泰 and the weekly causal queries
   against that exact PIT Wiki/index.
4. Record index identity/freshness, candidate pages, cutoff filtering,
   semantic filtering, latency, and final evidence atoms.
5. Check why valuation consistently stopped after market plus financial data:
   valid sufficiency, mandatory-plan finish hint, remaining time, or verifier
   disagreement. Tool discoverability is no longer the default hypothesis.
6. For weekly cause, separate four outcomes:
   - premise correction;
   - market-internal mechanism;
   - unique external catalyst;
   - honest unavailability of direct catalyst evidence.
7. Keep the verifier strict about unique causal claims, but allow a useful
   premise-correcting mechanism answer to be scored separately from “fully
   attributed external cause”.

Exit criterion: the team knows whether the gap is tool selection, index recall,
result quality, cutoff filtering, or an impossible/overloaded completion
contract.

### Parallel evaluation track — complete verdicts, do not rebuild cases

This track starts after Phase A.5. It does not block Phase B/C diagnosis, but it
blocks product-readiness and superiority claims:

1. Compile deterministic case fields (`expect_facts`, tolerances,
   `expect_refusal`, forbidden phrases/future data, multi-turn consistency) into
   typed per-case verdict inputs. Reuse `agent_eval` where semantics genuinely
   match; do not force a generic rule onto local-only definitions.
2. Keep operational status separate from quality status:
   - transport/preflight/run terminal state;
   - deterministic truth verdict;
   - blind experience/reference verdict.
3. Use the 22 frozen Knevo snapshots only according to each snapshot's
   `use_as`, leakage rule, and caveats. Preserve six missing comparisons rather
   than purchasing low-value answers merely to fill a denominator.
4. Blind labels and score truth versus experience separately. Literal
   `must_mention` remains a Workbench product requirement, not an external-agent
   failure by itself.
5. Keep `aggregate_gate=0.0` while validating the evaluator against historical
   traces and references. Once the rubric is stable, preregister a non-zero gate
   before the first scored 28-case run.
6. After Phase B/C shared-seam fixes, execute the 28 cases once through the real
   Conversation API, tiered if necessary for quota, and publish one immutable
   board. Do not tune individual questions between tiers.

Exit criterion: Workbench has a reproducible 28-case product pass rate, and the
eligible Knevo/Codex subsets have separate truth and experience comparisons.

### Phase D — make the App Server experiment trustworthy

1. Revise the App Server spec for the 13 findings above.
2. Re-review the written spec before implementation.
3. Create a TDD implementation plan only after the spec passes.

Exit criterion: the experiment cannot win by reading the future, inheriting a
different model/config, choosing a favorable baseline, or emitting unsupported
numbers.

### Phase E — implement the ceiling runner, not a product migration

Implement two deep modules:

- `AppServerProcess`: stdio JSON-RPC lifecycle, request correlation, event
  routing, server-request dispatch, interruption, typed errors, and sanitation;
- `AppServerBenchmarkRunner`: frozen cases, PIT roots, preregistered state,
  artifacts, and blinded comparison input.

Test transport and failure states with fixtures. Do not add routing, finance
planning, answer rewriting, or a second repair loop to this runner.

### Phase F — run one controlled five-case experiment

- Run App Server once after preregistration.
- Do not rerun GLM, SDK-GPT, or headless.
- Do not tune against individual question outputs.
- Perform the independent blinded comparison and source/lookahead audit.

Decision after the experiment:

| Observation | Next action |
|---|---|
| App Server clearly improves directness and repo use without truth regression | Design Phase G bounded integration |
| App Server improves prose but loses evidence discipline | Keep the runtime candidate, but attach EvidenceLedger/verifier before any canary |
| App Server does not materially improve | Stop runtime expansion; diagnose tool discoverability, data semantics, and domain-instruction interference |
| App Server is operationally unsafe/unreliable | Retain it only as a benchmark reference; continue the provider-neutral SDK lane |

### Phase G — only if the ceiling experiment wins

Design, do not immediately ship, a `CodexAppServerRuntime` behind the existing
`AgentRuntime` seam:

- expose only bounded read-only finance capabilities through `dynamicTools` or
  an MCP/tool bridge;
- reconnect tool results to the shared EvidenceLedger, cutoff, root budget, and
  publication verifiers;
- preserve model-owned planning and natural-language composition;
- keep the provider-neutral Adaptive Runtime as the product control plane;
- add a feature flag, isolated canary, rollback path, and blind evaluation.

This is how to combine Codex's generic harness with the existing domain harness.
It is not a direct replacement of the product with a local subscription-bound
Codex process.

### Phase H — product release and legacy deletion

Only after representative blind evaluation, freshness/evidence gates, a user-
approved canonical canary, and the rollback window:

- switch a bounded share of 8792 traffic;
- monitor quick/deep latency, directness, invalid actions, duplicate research,
  cutoff violations, and unsupported claims;
- expand the representative suite beyond five/nine engineering questions;
- delete the legacy long-tail pipeline only after the design's Phase 6 trigger
  is satisfied.

No current result authorizes Phase H.

## 12. Progress accounting

Do not collapse these dimensions into one misleading percentage:

| Dimension | Honest status |
|---|---|
| Adaptive Runtime architecture and deterministic contracts | Approximately 90%; §17 product foundations are implemented, while canonical canary and legacy deletion are intentionally pending |
| Latest clean five-case SDK-GPT live release gate | 3/5 completed = 60%; not release-green |
| Benchmark production-parity repair | Design complete; red proof and initial wiring complete; about 40% implementation, currently uncommitted/red |
| 28-case product acceptance board | Implemented on isolated `eval/acceptance-board@8279b2bd`; not integrated into the runtime branch; 22 Knevo snapshots and 12 answered turns exist; pass verdict compiler and baseline pass rate are still missing |
| Headless budget/stage-gate diagnosis | Historical evidence proves a double-reserve confound; controlled same-revision ablation not yet implemented or run |
| Retrieval discoverability/causal-contract diagnosis | Existing Hybrid RAG capability identified; direct replay and selection/coverage audit pending |
| Knevo comparison | 22 provenance-rich snapshots exist on the isolated acceptance branch; their eligibility is case/dimension-specific and no normalized truth/experience aggregate exists yet |
| Codex App Server ceiling experiment | Direction approved and first spec written; now blocked on budget-control validity plus independent spec review; implementation and live run 0% |
| Canonical 8792 rollout | 0%; intentionally untouched |
| Final “Codex-like and stronger than Knevo” product claim | Not yet demonstrated; requires broader blind evaluation and canonical operating evidence |

If a single sentence is required: the engineering foundation is advanced, but
the product-quality hypothesis is still unproven. Do not report “90% complete”
without immediately stating that live release, App Server validation, canonical
rollout, and legacy deletion remain open.

## 13. Anti-drift rules for the next agent

1. Do not turn a failing example into a new question route, skill, fixed output
   schema, or template.
2. Do not repeatedly run the frozen five questions while developing. Use unit,
   integration, replay, and one targeted live canary to prove a shared seam.
3. Do not weaken structural/semantic gates, citation checks, freshness, or
   protocol accounting to make an artifact green.
4. Do not give arbitrary SQL to the production model. Flexible finance access
   belongs behind typed semantic query tools.
5. Do not grant a constant repair budget. Grants must descend from the root and
   require effective new evidence plus coverage progress.
6. Do not spawn sub-agents for every question by default.
7. Do not add more review-harness machinery. Findings become permanent tests;
   independent architecture review happens at meaningful seams, not every
   commit.
8. Do not use the dirty primary workspace, current live DuckDB, global Codex
   config, or a shared App Server process for the ceiling experiment.
9. Do not ask the user for credentials during offline development. Credentialed
   live work occurs only at the final, preregistered gate.
10. Do not merge `main`, switch 8792, or delete legacy code without explicit
    user approval.
11. Do not create another acceptance suite or overwrite frozen references. Port
    `eval/acceptance-board@8279b2bd` after Phase A.
12. Do not report the two historical acceptance runs as 0% or passed. They have
    answers and traces but no `passed` verdict field.
13. Do not use all 22 Knevo snapshots as ground truth. Apply each snapshot's
    cutoff, `use_as`, local-definition, and reconstruction caveats.

## 14. First actions for the next agent

```bash
cd /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
git status --short
git branch --show-current
git rev-parse --short=8 HEAD
```

Expected starting state:

```text
 M intelligence/tests/test_run_agent_runtime_benchmark.py
 M scripts/run_agent_runtime_benchmark.py
feat/agent-runtime-backends-verify
f0742f72
```

Then:

1. Read this handoff.
2. Read the current WIP diff; do not start from the older runtime copy.
3. Finish Section 7 and restore a clean, tested branch.
4. Integrate `eval/acceptance-board@8279b2bd` as Phase A.5 without running all
   28 cases or merging `main`.
5. Run the Section 11 Phase B budget/stage-gate differential.
6. Run the bounded retrieval/contract diagnosis in Phase C.
7. Complete the acceptance verdict seam, then run the real 28-case product
   board once after shared-seam fixes.
8. Revise the App Server design against Section 9 using the fair-budget control.
9. Obtain a spec-level review before writing App Server code.

## 15. Canonical references

- Product architecture:
  `docs/superpowers/specs/2026-07-26-adaptive-finance-agent-runtime-design.md`
- Completion audit:
  `docs/verification/adaptive-runtime-completion-audit-2026-07-27.md`
- Latest production-parity diagnosis:
  `docs/handoffs/2026-07-28-runtime-production-parity-handoff.md`
- Benchmark parity design:
  `docs/superpowers/specs/2026-07-28-runtime-benchmark-production-parity-design.md`
- Benchmark parity implementation plan:
  `docs/superpowers/plans/2026-07-28-runtime-benchmark-production-parity.md`
- First App Server design, currently requiring revision:
  `docs/superpowers/specs/2026-07-28-codex-app-server-ceiling-benchmark-design.md`
- Latest frozen SDK-GPT evaluation:
  `docs/verification/sdk-delivery-and-semantic-deadline-2026-07-28.md`
- Isolated product acceptance source:
  `eval/acceptance-board@8279b2bd`
- Acceptance runner on that branch:
  `eval/acceptance-board:intelligence/eval/acceptance.py`
- Canonical 28-case definition on that branch:
  `eval/acceptance-board:intelligence/eval/cases/acceptance_cases.json`
- Frozen reference directory on that branch:
  `eval/acceptance-board:intelligence/eval/cases/reference_snapshots/`
- Acceptance tests on that branch:
  `eval/acceptance-board:intelligence/tests/test_acceptance_board.py`

## 16. Final handoff statement

The team has not wasted its prior work. The Adaptive Runtime is the domain and
product control plane: typed finance tools, evidence state, budgets, cutoffs,
verification, progress, cancellation, memory, and UI remain valuable regardless
of model provider. Codex App Server is being evaluated as a generic execution
harness that may improve model autonomy; it does not replace those finance
contracts.

The immediate job is to make the benchmark truthful, remove the headless budget
confound, and identify whether the remaining gap is tool selection/index recall
or generic harness quality. Only then can the App Server experiment be
scientifically valid. Evidence from that sequence—not a higher score produced
by a larger hidden budget—should decide whether to integrate App Server,
improve the existing SDK lane, or shift attention to data semantics and domain
contracts.

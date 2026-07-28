# SDK Delivery and Semantic Deadline Design

Date: 2026-07-28
Status: approved by the user's instruction to execute the diagnosed optimization
Implementation branch: `feat/agent-runtime-backends-verify`

## Problem

The clean `8f417fe2` five-case live artifact proves that cutoff, provider, and
outer-budget fixes work, but three shared execution seams still fail:

1. the SDK episode can spend its entire 60-second root allocation on model/tool
   research and leave no time for the model's final response;
2. successful mandatory capabilities are visible as separate tool results, but
   the model receives no explicit transition saying that the minimum evidence
   contract is complete and should be bound into the answer;
3. the semantic judge can spend a full per-attempt timeout repeatedly, turning
   a transient provider failure into a 90-second unavailable result even when
   the candidate answer is structurally complete.

The live trace is the regression oracle, not the debugging loop: valuation and
weekly-cause both obtained their mandatory tools and then exhausted the SDK
window on optional research; current-mainline produced a useful complete draft
but semantic verification consumed the outer window.

## Selected design

### Runtime-owned delivery reserve

The SDK keeps one continuous model episode, but the runtime gives tool use an
absolute close time earlier than the SDK request timeout. The reserve is
dynamic and bounded: 25% of the SDK run window, with a small-task floor and a
20-second ceiling. A 60-second standard research allocation therefore keeps
15 seconds for the same model invocation to produce the terminal JSON.

After the tool close time, every tool returns the existing typed
`research_stage_closed` result plus the instruction to answer from current
evidence. This closure is control state, not a public evidence gap. The model
still owns query selection and may use optional tools before the boundary.

### Mandatory evidence completion signal

`_AgentsRunState` tracks successful capabilities, not only episode-scoped tool
names. A capability becomes successful only when a tool observation contributes
at least one evidence item. After every successful observation, the public tool
result includes:

- the still-missing mandatory capabilities;
- `mandatory_evidence_complete=true` only when the set is empty;
- a finish hint telling the model to bind the returned evidence and deliver an
  answer, while allowing a genuinely useful optional check before the delivery
  boundary.

The structural verifier remains unchanged. A final answer that fails to bind
mandatory evidence still fails closed.

### Deadline-aware semantic attempts

One semantic-verifier invocation owns one fixed deadline. The first attempt is
allocated enough time to be useful; a retry is admitted only for typed,
release-safe transient failures and only when a minimum retry slice remains.
The per-attempt timeout is calculated from the remaining shared window rather
than repeatedly requesting the configured 25-second maximum. A third attempt
is removed from the normal path because it cannot fit the production verifier
window without starving release classification.

No semantic predicate is relaxed. Authentication, malformed output, contract
errors, and weak/untyped failures remain fail-closed.

## Interfaces and seams

- SDK behavior seam: `OpenAIAgentsRuntime.run()` as observed through model-visible
  tool results and the terminal `AgentOutcome`.
- Capability source of truth: `ResearchTaskContract.evidence_plan` plus each
  authorized `ToolSpec.capability`.
- Semantic behavior seam: `EpisodeSemanticVerifier.verify()` as observed through
  its status, issues, and provider attempt count under a fixed deadline.

Tests use scripted providers and a fake monotonic clock only at system
boundaries. They do not call private helpers directly.

## Acceptance

1. A scripted valuation-style episode receives a completion hint after
   `market_data` and `financial_data` both return evidence.
2. Before all mandatory capabilities succeed, the hint is absent and the
   missing set is exact.
3. Optional tool requests after the delivery boundary return
   `research_stage_closed`, do not add a public gap, and the episode can still
   return valid terminal JSON.
4. The structural verifier continues to reject a final answer that does not
   bind mandatory evidence.
5. A typed transient semantic failure may retry within the shared deadline;
   repeated attempts cannot consume the entire outer window.
6. Focused, adapter/orchestrator, and executable full suites pass before one
   new five-case live benchmark is allowed.

## Rejected approaches

1. Increase the global timeout: hides tool wandering and raises tail latency.
2. Close tools immediately after mandatory evidence: removes useful model
   discretion for contradiction checks and optional supporting evidence.
3. Treat successful tool calls as equivalent to completed answer bindings:
   bypasses the verifier and can publish unsupported prose.
4. Remove semantic verification when the draft looks good: weakens the release
   contract exactly where transient provider behavior is hardest to reason about.

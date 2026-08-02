# Agent Runtime Reliability and Grounding Design

Date: 2026-07-25  
Status: approved incremental design for the unified runtime goal  
Base: `feat/agent-runtime-backends-verify@6cb050c0`

## Objective

Make the isolated Workbench runtime useful for long-tail finance questions while
preserving the existing truth, evidence, permission, and UI contracts. The
change must improve the probability of answering the user's task; it must not
turn every sentence into a database claim or let the model bypass evidence for
observed facts.

## Evidence from the current benchmark

The live GPT nine-case run used 28 model calls, 27 tool calls, 98,873 input
tokens, and a 90-second median latency. Only the deterministic technical case
and one market-mainline case completed. Six arms were reported only as
`runtime_invalid_actions`, because the benchmark discarded the runtime's
specific stop reason. The SDK runtime passes the entire remaining deadline to
the Agents SDK and does not use the stage timeout reserved for finalization and
semantic review. This causes a stronger model to consume the verifier budget.

The same run also showed that methodology and counterfactual questions are
forced into research contracts whose required outputs normally need evidence.
That is a contract error: a method can be grounded in model reasoning and a
counterfactual can be grounded in the user's premise, while any new current
fact or number still requires evidence.

## Selected architecture

Keep the existing deep external seam:

```text
TaskFrame + ResearchRunContext + ResearchToolRegistry
  -> AgentRuntime.run()
  -> AgentOutcome
  -> structural verifier
  -> semantic verifier
  -> Run/SSE/UI projection
```

Do not add a second runtime wrapper or a second router. The runtime owns one
continuous model/tool episode; the host owns the deadline and the final truth
gates.

### 1. Runtime budget ledger

`ResearchDeadline` remains the single wall-clock source. The SDK adapter will
use three derived windows without changing the total budget:

- research/tool window: `stage_timeout(...)`; once it closes, tools return a
  non-factual `research_stage_closed` observation and the model must finalize;
- runtime finalization window: enough time for the SDK to produce the terminal
  envelope;
- verifier window: a small explicit reserve for structural/semantic review.

The expected behavior is deletion-safe: closing the tool window must not add a
false evidence gap when all required outputs are already fulfilled. A genuine
budget exhaustion that prevents an output remains a visible gap.

The SDK's effective timeout and stop reason are recorded in the private
benchmark artifact. They are never rendered in the public answer.

### 2. Grounding modes

`RequiredOutput` declares one grounding mode:

- `evidence`: current/historical facts, numbers, dates, company data, or causal
  observations must bind to collected evidence;
- `user_premise`: a conditional answer may reason from the premise explicitly
  supplied by the user, but cannot introduce an unbound current fact;
- `model_reasoning`: a method, framework, trade-off, or failure-mode answer may
  be generated from general reasoning without fake evidence.

`OutputEvidenceBinding` carries the model-selected `basis`. The structural
verifier checks that the basis matches the contract. Evidence mode requires
valid evidence hashes; the other two modes may use no hashes, but any hashes
provided are still validated. A `gap` remains the only valid representation of
an unanswered required slot.

Task semantics already identify decision-method and counterfactual patterns in
`TaskFrame`; the episode factory will project those patterns into grounding
modes without creating a new route table. The semantic judge receives the mode
alongside each output and continues to reject factual claims that lack direct
evidence.

### 3. Semantic repair and observability

Deletion-only semantic repair remains the only repair operation. Ordered and
circled list labels are renumbered after deletion. A small deterministic
consistency check removes stale count phrases such as “依据有三点” when the
repaired answer contains fewer items; it does not rewrite facts or add prose.

Benchmark results include `stop_reason`, `effective_timeout_seconds`, and
`grounding_modes` privately. Public projections remain unchanged.

## Alternatives rejected

1. Lowering evidence gates globally: rejected because it would allow unbound
   current facts and weaken the finance truth contract.
2. Adding a route for every long-tail shape: rejected because it recreates the
   route explosion that caused the original template behavior.
3. Treating the user premise as synthetic evidence: rejected because it would
   make a user hypothesis look like an observed market fact.

## Acceptance criteria

- SDK benchmark no longer reports opaque `runtime_invalid_actions`; every arm
  has a specific stop reason.
- A standard SDK run leaves verifier time after tool/finalization work.
- A method question can complete without a fake evidence citation.
- A counterfactual can complete from its user premise while unbound numeric
  current facts remain rejected.
- Semantic deletion never leaves a contradictory list count.
- Existing evidence-bound financial questions, deterministic technical path,
  UI/Run/SSE protocol, and secret handling retain their regression coverage.
- Three runtime arms remain isolated; `main` and 8792 are untouched.

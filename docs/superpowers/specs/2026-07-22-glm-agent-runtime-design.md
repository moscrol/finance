# GLM Continuous Agent Runtime Design

Date: 2026-07-22
Status: approved direction, implementation pending

## 1. Objective

Build a replaceable, continuous agent runtime for long-tail finance research.
The first implementation uses the existing GLM completion provider. It must
preserve the user's task, assistant actions, tool calls, raw tool observations,
evidence references, and explicit gaps inside one episode.

The runtime is successful when a long-tail question can be researched without
passing through the legacy `question_type -> owner -> fixed retrieval ->
template fallback` chain, while retaining the repository's permissions,
budgets, evidence ledger, provider trace, and final verification assets.

## 2. Non-goals

This phase does not:

- add GPT or an OpenAI Agents SDK dependency;
- launch Codex or Claude headless;
- replace deterministic fast paths such as quote lookup, market technical
  calculation, or daily review workflows;
- switch the 8792 runtime;
- merge the task branch into `main`;
- implement a general-purpose coding or shell agent;
- persist hidden chain-of-thought;
- build multi-agent supervisor/worker scheduling.

## 3. Alternatives Considered

### A. Continue patching the legacy orchestrator

This has the smallest immediate diff but leaves multiple execution owners and
lossy state projections in place. It remains appropriate only for deterministic
fast paths and critical production fixes.

### B. Replace the full Workbench

This would provide a clean architecture but discards mature finance data,
tools, evidence controls, UI events, and tests. The migration risk is too high.

### C. Add a strangler runtime beside the legacy path

Selected. A small runtime protocol and a continuous GLM episode can run beside
the existing orchestrator. Both paths can execute the same task and share the
same tool and verifier contracts. Migration occurs only after A/B evaluation.

## 4. Architecture

```text
Workbench control plane
  -> TurnControlCore
       -> clarification
       -> deterministic fast path (legacy)
       -> research episode
            -> AgentRuntime protocol
                 -> GLMEpisodeRuntime (phase 1)
                 -> LegacyRuntime adapter
                 -> future SDK/headless adapters
            -> ResearchToolRegistry
            -> Evidence/ProviderTrace ledger
            -> ResearchOutcome
            -> shared verifier (later integration step)
```

`TurnControlCore` is a thin execution-channel selector. It must not invent a
second question type, rewrite the task, or prescribe the research plan.

## 5. Stable Runtime Contract

The runtime boundary is provider-neutral:

```python
class AgentRuntime(Protocol):
    def run(
        self,
        task_frame: TaskFrame,
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        session_id: str,
    ) -> AgentOutcome: ...
```

`AgentOutcome` contains:

- immutable `task_frame_hash`;
- terminal state: `completed`, `partial`, `clarification`, or `failed`;
- final natural-language draft, if available;
- collected `AgentEvidence` and `ProviderTrace` values;
- explicit gaps and stop reason;
- ordered observable episode events;
- tool and LLM usage counters.

Provider-specific response objects must not cross this boundary.

## 6. Continuous Episode State

One `AgentEpisode` owns one research turn. It keeps an ordered event ledger:

1. original user task and `TaskFrame`;
2. assistant action JSON;
3. tool call request;
4. raw public tool observation plus stable evidence identifiers;
5. tool error or timeout;
6. explicit hypothesis/gap update;
7. completion decision and final draft.

Every GLM call receives the same continuous observable message history. The
runtime must not reconstruct each call from an independent compressed summary.
Hidden chain-of-thought is neither requested nor stored. Important reasoning is
represented through explicit hypotheses, action reasons, and gaps.

When a context budget is later required, raw observations remain in the
external ledger and can be reopened by identifier. Compaction is not part of
the initial implementation.

## 7. Tool Boundary

The first runtime reuses `ResearchToolRegistry` and existing read-only runners.
The model sees typed, high-signal tools rather than provider internals.

Initial eligible capabilities are:

- `market_data`;
- `mainline_context`;
- `kb_search`;
- `graph_lookup`;
- `evidence_lookup`;
- `news_search`;
- `web_search`;
- `l3_lookup` when explicitly enabled by the run context.

The registry enforces capability allowlists. Query deduplication, deadlines,
provider fallbacks, and evidence hashing remain deterministic code concerns.
Arbitrary shell, filesystem writes, SQL generation, or outbound mutations are
not exposed.

## 8. Control Semantics

Exactly one component owns each decision:

- `TaskFrame`: what the user asked;
- `TurnControlCore`: clarification, fast path, or research episode;
- `AgentEpisode`: research actions and stop decision;
- tool registry: authorization and execution;
- verifier: factual and task-completion acceptance;
- presenter: natural wording only.

Legacy `question_type` and route rows may supply compatibility metadata for a
fast path. They cannot downgrade a research-required `TaskFrame` to chat or
remove required capabilities.

## 9. Failure Handling

- Invalid model action: record the invalid event and allow one repair turn.
- Unknown or unauthorized tool: return a tool error to the same episode; do not
  silently switch to another pipeline.
- Empty result: preserve it as an observation and allow query rewriting.
- Repeated normalized query: reject deterministically and ask the same episode
  to choose another action.
- Tool exception: record a `ProviderTrace` error and continue while budget
  remains.
- Deadline or step exhaustion: return `partial` with collected evidence and
  explicit gaps.
- Model unavailable: return `failed` or `partial`; do not emit an unrelated
  answer template.

## 10. Testing and Evaluation

### Unit tests

- the second model turn includes the first assistant action and raw tool result;
- a financial `TaskFrame` cannot be downgraded to zero retrieval;
- clarification performs no retrieval;
- tool authorization and duplicate-query gates are enforced;
- tool failures remain in the same episode;
- completion cannot claim success while required outputs are uncovered;
- `task_frame_hash` remains constant throughout the episode.

### Focused A/B cases

- `昨天的反弹能持续多久`;
- `科创50你认为反弹空间有多少`;
- `瑞华泰的合理估值`;
- `这一周行情下跌的主要原因是什么`;
- `目前市场的主线是什么`.

Compare the legacy and episode paths on task alignment, evidence relevance,
freshness, required-output coverage, unsupported claims, template similarity,
duplicate retrieval, latency, and tool/LLM usage.

### Initial acceptance

- all focused unit tests pass with a scripted GLM-compatible completion;
- existing TaskFrame/controller tests remain green;
- no production consumer is switched until the real-GLM isolated A/B report is
  reviewed;
- the episode path may not score below the bare-model capability floor on the
  existing monotonicity evaluation.

## 11. Migration

1. Complete and review `TurnControlCore` as a sidecar.
2. Add the provider-neutral runtime types and continuous episode implementation.
3. Adapt existing finance tools without duplicating provider implementations.
4. Run scripted tests, then an isolated real-GLM A/B runtime.
5. Integrate the shared verifier and presenter.
6. Route only selected long-tail canary traffic to the episode path.
7. Add GPT/Agents SDK and headless adapters after the GLM baseline is measured.

The legacy orchestrator remains available until the episode path passes the
task-level acceptance suite.

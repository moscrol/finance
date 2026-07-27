# Current Market Freshness Contract Design

Date: 2026-07-27
Status: approved by continuation of the release-blocker handoff
Implementation branch: `feat/agent-runtime-backends-verify`

## Problem

Workbench readiness and Overview use `market_snapshot`, while the continuous
Episode's `market_data`, `mainline_context`, and `finance_query` tools read
`db/market_feature_store.duckdb`. The composition root does not pass the
snapshot served date into `ContinuousTurnAdapter`. If the snapshot is current
but DuckDB sync lags, the runtime can be reported ready and old daily rows can
be marked `freshness=current` and described as the latest market.

The captured 8799 failure had snapshot date `2026-07-27` and maximum published
evidence date `2025-06-30`. The canonical DB was synchronized later at 23:45;
that operational update removes the immediate data lag but does not close the
architectural bypass.

## Selected design

The snapshot served date is provider freshness metadata, not the information
cutoff. The composition root resolves it once for each Adapter and passes it as
`latest_data_date`; it also passes the runtime calendar date as `today`.

The Episode Registry computes one immutable structured freshness floor:

```text
expected_structured_date = min(snapshot_served_date, information_cutoff)
```

This preserves frozen historical evaluation: a 2026-07-24 cutoff never demands
2026-07-27 rows even when the local snapshot is newer. For live current tasks,
the floor equals the latest served snapshot date.

Before publishing model-visible evidence:

- `market_data` and `mainline_context` compare the DuckDB maximum market date
  with the floor;
- `finance_query` compares its actual `served_date` with the floor unless the
  model explicitly requested a historical `time_range.end` earlier than the
  floor;
- a stale result returns zero evidence, `ProviderTrace.status=stale`, both
  requested and served dates, and a task-specific gap;
- source dates always come from the serving provider, never from the fresher
  snapshot label.

When the continuous runtime is on/canary, readiness additionally requires the
DuckDB market date to be at least the snapshot served date. The response
reports both dates and the consistency result. Other runtimes retain the
existing readiness behavior during migration, while the shared Episode gate
still protects any invocation that receives a freshness floor.

## Alternatives rejected

1. Force a DuckDB sync before every answer: couples user latency and
   availability to an external write pipeline and still needs a read-time
   safety gate.
2. Read only `market_snapshot/latest.json`: supplies a current single-day
   picture but cannot answer multi-day duration, causal, relative-strength, or
   valuation-window questions.
3. Let the model see stale rows with a warning: unsafe because it already called
   those rows “latest”; freshness is a truth property owned by code.

## Interface and ownership

- The API composition root owns resolving the snapshot served date.
- `ResearchRunContext` carries snapshot metadata and the immutable cutoff.
- `episode_tools` owns the deep freshness decision used by every structured
  model-facing tool.
- FinanceQuery remains a general historical query engine; only the Episode
  adapter applies the current-task floor.
- Readiness exposes the same two dates but does not implement a second policy.

## Acceptance

1. The Adapter receives runtime `today` and snapshot served date.
2. With snapshot 2026-07-27 and DB 2025-06-30, current market_data and
   FinanceQuery publish zero evidence with a stale trace.
3. An explicit historical query ending 2025-06-30 still succeeds.
4. A frozen 2026-07-24 cutoff uses 2026-07-24 as the floor even when the local
   snapshot is 2026-07-27.
5. When dates match, existing current-market evidence remains unchanged.
6. Continuous-runtime readiness is not ready when snapshot is newer than DB.


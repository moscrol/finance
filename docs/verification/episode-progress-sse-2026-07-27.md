# Episode Progress / SSE Verification — 2026-07-27

## Scope and safety

- Branch: `feat/agent-runtime-backends-verify`
- Candidate started from: `b91681ca`
- Canonical 8792: untouched
- `main`: not merged
- Review harness: frozen and untouched
- Frozen nine-case benchmark: not run

This slice replaces post-hoc synthetic progress with append-time Episode events,
persists them to the existing Run trace and SSE replay store, and renders the
latest real public stage in the pending answer. It does not change answer
ownership, evidence gates, provider selection, budgets, or terminal-event
semantics.

## Delivered behavior

1. `episode_progress.py` is the single public projection module. It ignores
   every raw event payload value and emits fixed stage/message pairs only.
2. `ContinuousAgentEpisode` observes its append-only ledger immediately; the
   first event is observable before the first model call. Branch and repair
   events use the same sink.
3. `GLMAgentRuntime`, `ContinuousTurnAdapter`, and the FastAPI composition root
   share one Run publisher. Cancellation stops later progress appends.
4. Each public progress item is written to both `trace.jsonl` and replayable
   `trace.step` SSE. Duplicate identities are idempotent.
5. A configured live sink suppresses the old fixed post-hoc four-step sequence;
   direct adapters without a sink retain compatibility behavior.
6. React keeps live steps in `LiveMessageState.progress`, upserts by `step_id`,
   and shows the latest stage before answer publication.
7. Public trace projection now removes controller/retrieval payloads and the
   control keys `task_frame_hash`, `turn_intent`, `research_plan`,
   `pending_task_frame`, and `legacy_query_envelope`. Private trace/artifacts
   retain the full diagnostics.
8. The production composition root suppresses the adapter's duplicate
   `understanding` milestone because the controller already emitted the same
   public stage before runtime entry.

## Deterministic verification

Focused backend suite:

```text
280 passed
```

It covered Episode order/timing, branch events, repair events, adapter phase
milestones, cancellation, RunStore replay, app composition, public projection,
and existing terminal ownership.

Full `test_workbench_api.py` after public-projection hardening:

```text
87 passed
```

Python lint:

```text
ruff: All checks passed
```

Frontend:

```text
Vitest: 65 passed
ESLint: passed
TypeScript typecheck: passed
Vite production build: passed
```

## Isolated Run/SSE/UI smoke

Runtime:

```text
127.0.0.1:8799
ASK_CONTINUOUS_RUNTIME=on
AGENT_RUNTIME_BACKEND=continuous_glm
FINANCE_WS=/Users/a77/finance-workspace-private
```

The port was stopped after verification. Canonical 8792 was not changed.

Representative deterministic fast-path Run:

```text
run_20260727_035958_191199
question: 科创50的支撑点位在哪
data cutoff: 2026-07-24
```

Observed assertions:

- first public progress preceded the first `answer.snapshot`;
- SSE contained exactly one terminal `event: run`;
- reconnect from `Last-Event-ID: report:start` replayed one progress event and
  one terminal event;
- public stream leak scan found zero occurrences of `task_frame_hash`,
  `turn_controller`, SQL, provider assignments, raw model messages, or route
  payloads;
- public trace for the final smoke contained one stage only:
  `understanding / completed / 已完成问题理解与任务对齐。`;
- final answer used the 2026-07-24 structured technical calculation and was
  not rewritten by a generic template.

Browser verification on the same isolated candidate confirmed:

- the final answer rendered normally;
- Run details showed `理解问题` rather than internal stage names;
- the fast path no longer displayed duplicate `理解问题` rows;
- the browser console contained no errors.

## Honest boundary

The shell used for this verification did not have the local OpenAI-compatible
route credential, so no new live long-tail model call was made in this slice.
Continuous long-tail timing, branch, repair, verification, and UI reduction are
covered by deterministic scripted-provider tests. The next live model signal is
the single frozen representative benchmark at the release frontier, followed by
the independent Claude review requested by the user; it must not be replaced by
repeated nine-case development runs.

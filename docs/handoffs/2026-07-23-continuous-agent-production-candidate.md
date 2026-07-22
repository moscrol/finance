# Continuous Agent Production Candidate Handoff

Date: 2026-07-23

## 1. Active objective

Complete every item in the approved Continuous Agent production-candidate
optimization list:

1. concurrent read-only tool execution with valuation/mandatory priority;
2. one compact finalization recovery;
3. explicit provider fallback chain;
4. semantic grounding gate and one targeted repair;
5. real Conversation API / same-UI isolated canary;
6. production-grade valuation evidence scheduling;
7. deepened Episode modules, full regression, review, report, and memory.

Implementation completion does **not** authorize merging `main` or switching
canonical 8792. Those remain separate user approval gates.

## 2. Repository state

```text
Repository worktree: /Users/a77/.codex/worktrees/finance-task-fulfillment
Branch:              fix/agent-harness-monotonicity
Last completed code: 2995cb8a fix: enforce absolute tool publish cutoff
Canonical 8792:      untouched by this phase
Main merge/push:     not performed
```

The worktree is intentionally dirty because Task 2 was interrupted for this
handoff. Do not discard or overwrite these changes:

```text
 M intelligence/services/agent_episode.py
 M intelligence/services/agent_runtime.py
 M intelligence/tests/test_agent_episode.py
```

The handoff document itself is committed separately after the completed Task 1
code; use `git log -1 --oneline` to identify that documentation-only commit.

## 3. Authoritative design and plan

- Design:
  `docs/superpowers/specs/2026-07-23-continuous-agent-production-candidate-design.md`
  (`1e6c44d3`)
- TDD implementation plan:
  `docs/superpowers/plans/2026-07-23-continuous-agent-production-candidate.md`
  (`9d25b115`)
- Previous GLM sidecar verification:
  `docs/verification/glm-continuous-agent-runtime-2026-07-22.md`

The user approved continuing the full list. Do not restart brainstorming or
redesign the architecture unless current evidence contradicts the spec.

## 4. Completed work

### Baseline continuous runtime

The branch already contains the provider-neutral runtime, immutable TaskFrame,
continuous Episode, GLM adapter, existing finance tool registry, L3 runner,
structural verifier, deterministic market-technical fast path, three-arm A/B,
and five-question GLM sidecar report. Key tip before this production batch was
`25855601`.

### Task 1 — ToolBatchExecutor: complete and double-reviewed

Commits:

```text
b8ba37e3 feat: execute episode tools concurrently
70299fb5 fix: isolate episode tool batch sessions
1a65aefe fix: preserve tool deadline snapshot
7da7efd6 fix: bound tool execution and ledger publication
2995cb8a fix: enforce absolute tool publish cutoff
```

Implemented:

- `episode_policy.py` centralizes mandatory/question tool priority; valuation
  order starts with `market_data`.
- `ToolBatchExecutor` is a stateless factory;
  `EpisodeToolBatchSession` owns per-Episode dedupe and monotonic step IDs.
- Calls are prevalidated, selected by mandatory capability priority, executed
  concurrently, and returned in the model's original call order.
- A module-level eight-worker pool bounds global tool threads; a single batch
  submits at most four tasks. Tests can inject a smaller executor.
- `contextvars.copy_context()` propagates the same turn QueryLedger to workers.
- QueryLedger now uses subscriber-aware single-flight publication: one timed-out
  guarded consumer cannot suppress a still-active consumer.
- `QueryPublishGuard` has an absolute monotonic cutoff shared with `wait()`;
  results attempting to publish after the deadline cannot mutate the ledger.
- Strict query-only arguments, duplicate call IDs, duplicate normalized queries,
  budget rejection, exception, TimeoutError, zero-deadline, timeout snapshot,
  cross-session isolation, cross-batch monotonic IDs, and resource caps are
  tested.

Final review evidence:

- spec review: approved;
- quality review: approved, zero Critical/Important;
- focused suite at final review: 109 passed; Ruff passed.

Accepted semantic boundary: a query legitimately published before the absolute
cutoff remains a valid ledger record even if the outer executor Future is
marked done just after the cutoff. Publication after the cutoff is forbidden.

## 5. Task 2 WIP — do not restart

Task 2 is “Replace inline serial execution and deepen the Episode loop.” An
implementation agent completed the main edit but was interrupted before final
self-review/commit.

Current uncommitted behavior:

- `agent_runtime._public_evidence` is renamed/exported as
  `public_agent_evidence`; `AgentOutcome.to_dict()` uses it.
- `ContinuousAgentEpisode` accepts a `ToolBatchExecutor` factory and creates a
  fresh `new_session()` **inside every `run()`**. Do not move the session to the
  runtime instance; that would leak dedupe across turns.
- the old inline serial `registry.execute()` loop and local `seen_queries` are
  removed;
- one `session.execute()` returns ordered results;
- `tool_calls += batch.executed_count` happens exactly once;
- rejected calls increment `invalid_actions` but do not increment tool calls;
- timeout/error are recorded as legal `ProviderTrace(status="request_error")`
  with stable public details `tool_timeout` / `tool_exception`; raw exception
  text is not sent to the model/public answer;
- successful/empty results preserve original evidence, trace, gaps, and ordered
  tool messages;
- duplicate public evidence projection in `agent_episode.py` is deleted;
- tests cover overlapping reverse-completion runners and original tool-message
  order.

Current focused test command is green:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_agent_runtime.py \
  intelligence/tests/test_episode_tool_batch.py \
  intelligence/tests/test_episode_verifier.py
```

Result at handoff: `55 passed in 0.63s`.

### Exact next actions for Task 2

1. Inspect the current diff; do not rewrite it from the plan.
2. Confirm all old direct `registry.execute`, `seen_queries`, and duplicate
   `_public_evidence` paths are gone.
3. Confirm `step_id` values come from the batch/session result rather than being
   reconstructed with a second counter. The current WIP reconstructs step IDs
   from `previous_tool_calls + executed_index`; this is the main point that still
   needs scrutiny because Task 1 already owns monotonic step IDs. Prefer adding
   `step_id` to `ToolCallResult` if necessary rather than creating two owners.
4. Assert every batch item emits `tool_request` before its result/error message,
   and the ordered transcript matches the model call array.
5. Assert timeout/error public messages do not include a fixture exception
   sentinel.
6. Run focused tests plus Ruff/format/diff check.
7. Commit the three WIP files only with:

```bash
git add intelligence/services/agent_episode.py \
  intelligence/services/agent_runtime.py \
  intelligence/tests/test_agent_episode.py
git commit -m "refactor: deepen continuous episode tool seam"
```

8. Run a fresh Task 2 spec-compliance review, then a fresh code-quality review.
   Fix and re-review every Critical/Important issue before Task 3.

## 6. Remaining tasks after Task 2

Follow the committed implementation plan exactly:

- Task 3: `EpisodeFinalizer` — one no-tools compact recovery; integrate only at
  specified finalization failures; same parser/verifier; no invented hashes.
- Task 4: explicit provider tuple — BYOK stays single; built-in preserves
  detected order; same messages/settings/deadline; physical attempts counted.
- Task 5: `SemanticEpisodeVerifier` — structural first, semantic judge second,
  one targeted repair/rejudge, judge unavailable fails closed to partial.
- Task 6: `ContinuousTurnAdapter` — off/canary/on; valuation contract requires
  current anchor and assumptions; Episode answer never re-enters legacy
  presenter.
- Task 7: integrate immediately after canonical TaskFrame/control decision in
  `TurnOrchestrator`; persist same message/run/SSE/artifacts; full provider tuple
  only reaches continuous path; legacy uses first provider.
- Task 8: extend A/B artifact schema; launch isolated same-UI GLM canary; run
  five questions individually and sequential pressure batch.
- Task 9: focused/full regression, two-axis review, seven-row completion audit,
  verification report, project-memory writeback, local URL and release gate.

Each implementation task uses a fresh implementer followed by spec review and
code-quality review. Do not parallelize code edits in the shared worktree.

## 7. GLM and runtime environment

Never print or write the key. At process start only:

```bash
FORESIGHT_BUILTIN_LLM_API_KEY="$(security find-generic-password -a a77 -s finance-workbench-glm -w)"
```

Known environment:

```text
FORESIGHT_BUILTIN_LLM_MODEL=glm-5.2
FORESIGHT_BUILTIN_LLM_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
FINANCE_WS=/Users/a77/finance-workspace-private
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki
KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python
RAG_INDEX_DIR=/Users/a77/knowledge-base-private/.rag_index
PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
PYTHONPATH=/Users/a77/.codex/worktrees/finance-task-fulfillment
```

Canonical 8792 currently points to the pre-candidate runtime and was started on
2026-07-20. Do not change its LaunchAgent or runtime symlink. At the last audit,
that canonical runtime also contained unrelated dirty moneyflow files; preserve
them.

## 8. Test baseline and completion rules

Before this production batch, complete `intelligence/tests` was:

```text
2091 passed, 11 failed
```

The 11 failures were pre-existing `test_subconscious.py` / `test_userspace.py`
local-path pollution. Re-run the full suite after all implementation changes and
compare every failure to the fixed baseline; do not use that baseline to excuse
failures in changed modules.

The active objective remains incomplete. Do not call the goal complete until
all seven optimization items, real GLM isolated Conversation-API/UI canary,
pressure run, full regression, reviews, report, and memory handoff are proven.
Do not claim production release until the user separately approves merge and
canonical 8792 cutover.

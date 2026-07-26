# Episode Progress SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream truthful, sanitized Episode progress into the existing Run/SSE/UI path while research is still executing, without changing answer ownership or terminal-event semantics.

**Architecture:** Add one deep `episode_progress` module whose interface accepts internal `EpisodeEvent` values and emits only fixed, user-safe progress stages. A per-Run publisher persists each projected event to both `trace.jsonl` and the replayable SSE store. `ContinuousAgentEpisode` exposes one optional event sink; the GLM composition root connects it to the projector, while `ContinuousTurnAdapter` publishes the non-Episode verification milestones through the same sink. The React stream reducer consumes the existing public `trace.step` event and shows the latest real stage in the pending assistant message.

**Tech Stack:** Python frozen dataclasses, existing `EpisodeEvent`, `RunStore`, FastAPI SSE protocol, React/TypeScript, pytest, Vitest.

---

## File structure

- Create `intelligence/services/episode_progress.py`: safe event projection and idempotent Run/SSE publisher.
- Modify `intelligence/services/agent_episode.py`: emit each append-only Episode event to an optional observer.
- Modify `intelligence/services/glm_agent_runtime.py`: pass the observer into the continuous Episode.
- Modify `intelligence/services/continuous_turn_adapter.py`: publish understanding/verification/finalization milestones and suppress post-hoc synthetic progress when a live sink exists.
- Modify `intelligence/api/app.py`: construct one publisher per Run and wire it to the runtime and adapter.
- Modify `intelligence/webapp/src/types.ts`, `streamEvents.ts`, and `components/MessageBubble.tsx`: retain live trace steps and display the latest stage.
- Add focused tests beside each public seam; do not run the nine-case live benchmark in this slice.

## Task 1: Safe progress projection and persistence

**Files:**
- Create: `intelligence/services/episode_progress.py`
- Create: `intelligence/tests/test_episode_progress.py`

- [ ] **Step 1: Write a failing projection test**

```python
def test_projector_never_exposes_control_plane_payload() -> None:
    event = EpisodeEvent(3, "tool_request", {
        "tool": "finance_query",
        "query": "SELECT secret FROM hidden_table",
        "provider": "private-provider",
        "prompt": "internal prompt",
    })
    progress = project_episode_progress(event)
    assert progress is not None
    serialized = json.dumps(progress.to_dict(), ensure_ascii=False)
    assert "finance_query" not in serialized
    assert "SELECT" not in serialized
    assert "private-provider" not in serialized
    assert "internal prompt" not in serialized
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.venv-workbench/bin/python -m pytest intelligence/tests/test_episode_progress.py -q`

Expected: collection fails because `episode_progress` does not exist.

- [ ] **Step 3: Implement the minimal public projection**

Create a frozen `EpisodeProgress(key, stage, message, status)` value. Map only `plan`, `mode_decision`, `tool_request`, `tool_result`, `tool_error`, `branch_started`, `branch_completed`, `branch_failed`, `repair_goal`, `finalization`, `finalization_recovery_started`, and `finish` to constant user-facing messages. Ignore model turns and every raw payload value. Keys may contain only the Episode sequence and an allowlisted kind.

- [ ] **Step 4: Write publisher behavior tests**

```python
def test_publisher_persists_replayable_trace_and_stops_after_cancel(tmp_path) -> None:
    cancelled = Event()
    store, run = make_running_store(tmp_path)
    publisher = RunEpisodeProgressPublisher(
        run_store=store,
        run_id=run.run_id,
        conversation_id="conv-1",
        message_id="msg-1",
        is_cancelled=cancelled.is_set,
    )
    publisher.publish(EpisodeProgress("episode:1:plan", "planning", "已形成研究计划。", "completed"))
    cancelled.set()
    publisher.publish(EpisodeProgress("episode:2:tool_request", "research", "正在核对所需资料。", "running"))
    assert [step["step_id"] for step in store.load_trace(run.run_id)] == ["continuous:episode:1:plan"]
    replay = store.load_stream_events(run.run_id)
    assert [event["event_type"] for event in replay] == ["trace.step"]
```

- [ ] **Step 5: Implement the idempotent publisher and verify GREEN**

The publisher owns an in-process lock and published-key set. For each accepted event it calls `RunStore.append_step()` and then `append_stream_event(event_type="trace.step")`; it checks cancellation inside the lock and never persists the Episode payload. Duplicate keys are no-ops.

Run: `.venv-workbench/bin/python -m pytest intelligence/tests/test_episode_progress.py intelligence/tests/test_run_store.py -q`

Expected: all pass.

- [ ] **Step 6: Commit the deep module**

```bash
git add intelligence/services/episode_progress.py intelligence/tests/test_episode_progress.py
git commit -m "feat: persist safe episode progress"
```

## Task 2: Wire real Episode events through the runtime

**Files:**
- Modify: `intelligence/services/agent_episode.py`
- Modify: `intelligence/services/glm_agent_runtime.py`
- Modify: `intelligence/services/continuous_turn_adapter.py`
- Modify: `intelligence/api/app.py`
- Test: `intelligence/tests/test_agent_episode.py`
- Test: `intelligence/tests/test_continuous_turn_adapter.py`
- Test: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: Write a failing Episode timing test**

Use a recording model whose first `complete()` call asserts that the sink has already observed the task-alignment milestone. After a scripted plan/tool/final run, assert the sink order contains `plan`, `tool_request`, `tool_result`, and `finalization`. Assert branch and repair fixtures expose their existing `branch_*` and `repair_goal` events through the same sink.

- [ ] **Step 2: Run the Episode test and verify RED**

Run: `.venv-workbench/bin/python -m pytest intelligence/tests/test_agent_episode.py -k "progress_sink" -q`

Expected: `ContinuousAgentEpisode` does not accept `event_sink`.

- [ ] **Step 3: Add the optional append observer**

`_EpisodeLedger.add()` calls the observer immediately after appending the immutable event. Observer exceptions are isolated from research execution. `ContinuousAgentEpisode` and `GLMAgentRuntime` accept the optional observer and otherwise preserve existing behavior.

- [ ] **Step 4: Write adapter/app integration tests**

Prove that `_build_continuous_turn_adapter()` writes the first progress event before the blocking model returns, that verification produces a later public milestone, and that a configured live sink makes `ContinuousTurnResult.events == ()`. Existing direct adapter tests without a sink must retain the old post-hoc compatibility events.

- [ ] **Step 5: Wire one publisher per Run**

Pass `run_store`, `conversation_id`, and `event_id_prefix` into `_build_continuous_turn_adapter()`. Construct one `RunEpisodeProgressPublisher`; feed projected Episode events from `GLMAgentRuntime` and adapter-owned `understanding`, `verification`, and `finalizing` milestones into that same publisher. The publisher cancellation predicate is the existing `CancellationSignal.is_set`.

- [ ] **Step 6: Verify runtime and protocol invariants**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_glm_agent_runtime.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_run_store.py -q
```

Expected: all focused tests pass; existing terminal SSE assertions still report exactly one terminal `run` event.

- [ ] **Step 7: Commit runtime wiring**

```bash
git add intelligence/services/agent_episode.py intelligence/services/glm_agent_runtime.py intelligence/services/continuous_turn_adapter.py intelligence/api/app.py intelligence/tests
git commit -m "feat: stream live continuous episode progress"
```

## Task 3: Display real progress in the pending answer

**Files:**
- Modify: `intelligence/webapp/src/types.ts`
- Modify: `intelligence/webapp/src/streamEvents.ts`
- Modify: `intelligence/webapp/src/components/MessageBubble.tsx`
- Test: `intelligence/webapp/src/streamEvents.test.ts`
- Test: `intelligence/webapp/src/components/components.test.tsx`

- [ ] **Step 1: Write a failing reducer test**

Apply two replayed `trace.step` envelopes to `LiveMessageState`. Assert steps are deduplicated by `step_id`, remain ordered, and the last public output summary is available to the message renderer. Assert mismatched conversation/run/message identities remain ignored.

- [ ] **Step 2: Run Vitest and verify RED**

Run: `pnpm --dir intelligence/webapp test -- --run streamEvents.test.ts`

Expected: `LiveMessageState` has no live trace field.

- [ ] **Step 3: Implement live trace consumption and display**

Add `progress: TraceStep[]` to `LiveMessageState`; accept only structurally valid `trace.step` payloads and upsert by `step_id`. While the answer body is empty, `MessageBubble` shows the latest sanitized `output_summary`, falling back to the existing generic text only when no real progress exists.

- [ ] **Step 4: Run frontend quality gates**

Run:

```bash
pnpm --dir intelligence/webapp test -- --run
pnpm --dir intelligence/webapp lint
pnpm --dir intelligence/webapp typecheck
pnpm --dir intelligence/webapp build
```

Expected: all pass.

- [ ] **Step 5: Run the focused backend suite and one isolated UI smoke**

Do not run the nine-case benchmark. Start only the isolated candidate, submit one representative long-tail question, and verify: the first `trace.step` arrives before the answer; reconnect replays it; cancellation stops later progress; exactly one terminal `run` event exists; no query, tool/provider name, SQL, hash, prompt, or raw message appears in public progress.

- [ ] **Step 6: Commit UI support and verification note**

```bash
git add intelligence/webapp docs/verification
git commit -m "feat: show live research progress"
```

## Alignment and scope checks

- Claude `ALIGNMENT.md` dependency is preserved: `missing_outputs` and verifier repair reasons are already exported and remain the source for same-Episode `RepairGoal`; progress merely makes that recovery visible.
- ProviderTrace, cutoff rejection, token usage, root-budget identity, branch evidence facade, and MemoryGate remain separate truth/control modules and are not copied into progress messages.
- Review harness files are frozen and out of scope.
- No canonical 8792 switch, `main` merge, legacy deletion, or nine-case benchmark occurs in this plan.

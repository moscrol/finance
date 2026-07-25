# Unified Agent Runtime Finalization Handoff

Date: 2026-07-25
Status: in progress, do not merge `main`, do not switch canonical 8792

## 2026-07-26 Update

- Comparison semantics and Chinese month-horizon fixes are implemented.
- The dynamic per-round tool surface is implemented: successful episode
  snapshots disappear from the next model tool menu, and the final tool
  observation carries a structured `remaining_tool_calls` budget.
- The hard batch executor still rejects malicious or stale calls.
- Focused runtime regression: `401 passed, 1 skipped`.
- Live comparison replay:
  `/Users/a77/.finance-runtime/evals/repro-theme-comparison-dynamic-tools.json`.
  Both GLM arms have zero protocol issues and the single-case gate passes.
- The next step is no longer implementation. Freeze one commit, run the
  nine-case GLM suite once as the final revision gate, then continue with
  GPT/headless, UI/SSE, and full regression.

## Workspace Anchor

- Worktree: `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667`
- Branch: `feat/agent-runtime-backends-verify`
- Committed tip before the current uncommitted fix: `ce5b6291`
- Current worktree has three intentional modified files:
  - `intelligence/services/query_understanding.py`
  - `intelligence/services/task_frame.py`
  - `intelligence/tests/test_turn_control_core.py`
- `git diff --check` passes.
- Do not discard these changes. They are the RED -> GREEN fix for the comparison-contract contamination described below.

## Final Goal And Progress

Final goal: a locally usable vertical finance Agent that preserves base-model reasoning, uses a continuous tool loop, applies finance evidence/verifier constraints at the exit, supports replaceable GLM/GPT/headless backends, and passes real UI/SSE plus frozen benchmark acceptance without touching 8792 until explicit approval.

Estimated overall progress: **80%**.

- Runtime/backends implementation: 100%
- TaskFrame/grounding/verifier architecture: about 90%
- GLM live quality gate: about 85%
- GPT/headless current-revision comparison: about 55%
- Real UI/SSE, full regression, docs and release decision: about 65%

The remaining 20% is not feature volume; it contains the highest-risk acceptance work. Do not report completion before the dynamic tool-budget seam, current-revision nine-case runs, UI E2E, and full regression are green.

## Already Completed Before This Session

Committed through `ce5b6291`:

- Replaceable `continuous_glm`, `sdk_glm`, `sdk_gpt`, and benchmark-only `codex_headless` runtimes.
- Shared TaskFrame, ResearchRunContext, read-only tool registry, structural verifier, semantic verifier, Run/SSE/UI protocol.
- `RequiredOutput.grounding_mode` and binding `basis`: `evidence`, `user_premise`, `model_reasoning`.
- Methodology and counterfactual cases run with one LLM call and zero tools.
- Empty capability tuple means no tools; `None` means no filter.
- SDK reserves verifier budget and supports no-evidence JSON recovery when the contract permits reasoning.
- Latest focused suite from the previous session: `302 passed, 2 skipped`.
- Earlier full suite: `2564 passed, 11 failed, 2 skipped`; the 11 failures were existing local `subconscious/userspace` path pollution and must still be rerun on the final revision.

## Diagnosis Completed In This Session

### 1. SDK Ruihuatai semantic failure was transient

Old artifact:

`/Users/a77/.finance-runtime/evals/agent-runtime-ce5b6291-2026-07-25.json`

It showed `sdk_glm/ruihuatai-valuation` as structural completed but semantic unavailable.

Single-case rerun on the same revision:

`/Users/a77/.finance-runtime/evals/repro-ruihuatai-sdk-ce5b6291.json`

Result: `completed`, structural `completed`, semantic `repaired`, 60.7s, 15 citations, no protocol issue. Do not loosen the verifier or expand timeout for the old one-off failure.

### 2. Comparison question had control-plane contract contamination

Question:

`低空经济和商业航天，未来一个月哪个更可能成为A股主线，为什么`

The old control path classified it as single-theme `theme_analysis`, retained only `商业航天` as subject, lost the month timeframe, then unioned theme defaults with comparison outputs. The unwanted required output `chain_mapping` made an otherwise useful direct comparison structurally partial.

The current uncommitted fix:

- Recognizes `X 和 Y，哪个更...` as comparison semantics.
- Parses Chinese `未来一个月/两个月` timeframe.
- Makes explicit decision outputs override coarse route defaults instead of unioning both contracts.
- Keeps the subject `None` rather than falsely selecting one side; the raw question remains the canonical pair.
- Keeps current-market capabilities through the evidence planner: `market_data`, `mainline_context`, and `news_search` are still available.

Regression test:

`test_comparative_mainline_decision_overrides_single_theme_defaults`

RED before the fix: `execution_route == theme_analysis`.
GREEN after the fix: focused run `56 passed`.

### 3. Remaining GLM gate failure is a stale dynamic tool surface

Post-fix live artifact:

`/Users/a77/.finance-runtime/evals/repro-theme-comparison-fixed.json`

Both backends now receive:

- question type `comparison`
- timeframe `未来一个月`
- exactly four required outputs: conclusion, evidence, counterpoint, invalidation
- current market/mainline tools

Both public answers are direct and useful. `sdk_glm` has no protocol issue. `continuous_glm` still reports recoverable invalid actions.

An event-level replay proved the exact cause:

- First model round used four of six tool slots.
- Second round still saw the original static tool menu and no explicit remaining-slot count.
- It requested six tools while only two slots remained.
- Two calls were rejected as `tool_budget_exhausted`.
- Two repeated `market_data` calls were rejected as `episode_snapshot_already_collected`.
- The final answer still passed the semantic judge, but the benchmark correctly exposed `runtime_invalid_actions`.

This is a harness defect, not a route, retrieval, or base-model capability defect.

## Completed Implementation Slice

The dynamic per-round tool surface below was completed on 2026-07-26. Invalid
actions were not hidden from the gate.

1. Add a public session query on `EpisodeToolBatchSession` for successfully collected episode-scoped tools, or return the currently callable authorized specs.
2. Before every model turn in `ContinuousAgentEpisode`, rebuild tool definitions:
   - remove successful episode-scoped tools such as `market_data` and `mainline_context`;
   - expose no more tools than the remaining tool-call slots can support where practical;
   - append a compact budget state message with the exact remaining tool-call count.
3. Keep `EpisodeToolBatchSession.execute()` fail-closed. Dynamic exposure improves planning but the executor remains the hard policy boundary.
4. Add tests before implementation at these public seams:
   - a collected episode snapshot disappears from the next tool surface;
   - the second model turn sees the correct remaining-slot count;
   - a compliant model produces zero invalid actions and a valid final answer;
   - malicious/invalid over-request is still rejected by the executor.
5. Rerun the exact comparison case on both GLM backends. The Continuous arm must have no `tool_budget_exhausted` or `episode_snapshot_already_collected` protocol issue.

Do not solve this by weakening `summarize_runtime_benchmark()` or ignoring `invalid_actions`. The reusable architecture principle is: soft planning should see the current permission/budget surface; hard enforcement remains in the executor.

## Acceptance Sequence After The Fix

1. Rerun all nine frozen cases for `continuous_glm` and `sdk_glm` on the final revision.
2. Rerun all nine `sdk_gpt` cases using `--keychain-user linxiaoqi5111`; never read or print the credential.
3. Attempt `codex_headless` on the same revision. Record `headless_usage_limit` as an external blocked arm if it persists; never silently fall back.
4. Start a clean isolated runtime on an unused port, preferably 8798 if free. Do not touch 8792.
5. Real UI/Conversation/Run/SSE checks:
   - current market mainline
   - unfamiliar methodology
   - counterfactual mainline
   - Ruihuatai valuation
   - theme comparison
6. Assert one terminal SSE event, fresh 2026-07-24-or-later data, citations, no control-plane leakage, and no template gap replacing a usable answer.
7. Run full backend and frontend regression.
8. Update `docs/verification/agent-runtime-backends-2026-07-25.md` and `/Users/a77/agent-memory/20_projects/finance-workspace-private.md`.
9. Commit the branch and leave it clean. Wait for explicit user approval before merge or 8792 cutover.

## Commands

Focused test already green:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_turn_control_core.py::test_comparative_mainline_decision_overrides_single_theme_defaults \
  intelligence/tests/test_task_frame.py::test_task_frame_preserves_explicit_long_tail_output_shape \
  intelligence/tests/test_query_understanding.py
```

Full Python regression:

```bash
env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER \
  -u SUBCONSCIOUS_VAULT -u AGENT_MEMORY_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
```

Frontend regression:

```bash
cd intelligence/webapp
pnpm test --run
pnpm lint
pnpm typecheck
pnpm build
```

## Safety

- Do not merge `main` without explicit approval.
- Do not switch canonical 8792.
- Do not commit `.env*`, secrets, databases, caches, benchmark artifacts, or runtime output.
- Keep benchmark artifacts under `/Users/a77/.finance-runtime/evals/`.
- Load the GLM key only from macOS Keychain service `finance-workbench-glm`, account `a77`, without printing it.

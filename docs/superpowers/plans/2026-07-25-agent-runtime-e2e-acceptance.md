# Agent Runtime E2E Acceptance Implementation Plan

> **For agentic workers:** Continue inline from `feat/agent-runtime-backends`; keep the same frozen nine-case fixture and do not switch canonical 8792.

**Goal:** Decide with reproducible evidence whether `sdk_glm` should replace `continuous_glm` as the Workbench production candidate while recording `codex_headless` as a benchmark-only reference.

**Architecture:** Exercise all available backends through the same `TaskFrame`, finance-tool registry, budget ledger, structural verifier, semantic verifier, Conversation/Run/SSE protocol, and UI. Separate runtime capability failures from acceptance-contract gaps so a weak answer is not misdiagnosed as a model problem.

**Tech Stack:** Python, FastAPI, OpenAI Agents SDK, GLM OpenAI-compatible API, Codex CLI headless mode, SSE, React/Vite/pnpm, pytest.

---

## Frozen Scope

- Branch: `feat/agent-runtime-backends`
- Candidate revision at start: `c798cd5521a3`
- Code runtime: `/Users/a77/.finance-runtime/agent-runtime-backends-c798cd55`
- Finance data root: `/Users/a77/finance-workspace-private`
- Control: `continuous_glm` on 8795
- Candidate: `sdk_glm` on 8796
- Reference: `codex_headless` on 8797, benchmark-only
- Canonical 8792, `main`, and the canonical runtime symlink remain unchanged.
- Missing Codex quota or `OPENAI_API_KEY` is recorded as an external blocked arm; it does not justify changing the frozen fixture or silently falling back.

## Task 1: Verify Runtime Provenance and UI Protocol

**Files:**
- Verify: `intelligence/api/app.py`
- Verify: `intelligence/services/continuous_turn_adapter.py`
- Modify: `docs/verification/agent-runtime-backends-2026-07-25.md`

- [ ] Query `/api/health` on 8795, 8796, and 8797 and assert the same clean revision, the same finance data root, and distinct backend names.
- [ ] Submit the frozen mainline question through the real 8796 browser UI.
- [ ] Query the resulting Conversation, Run, report, trace, and SSE event replay.
- [ ] Assert exactly one terminal `event: run`, no provider/backend/control-plane labels in the public answer, and rendered citations plus run details.
- [ ] Capture one desktop screenshot and close the browser automation session.

Commands:

```bash
for port in 8795 8796 8797; do
  curl -fsS "http://127.0.0.1:${port}/api/health" | jq \
    '{status, revision:.runtime.source_revision, dirty:.runtime.source_dirty, agent_runtime:.runtime.agent_runtime, finance_root:.runtime.finance_root}'
done
```

Expected: `dirty=false`, revision `c798cd55...`, 8797 has `benchmark_only=true`, and no port silently reports another backend.

## Task 2: Run the Frozen Nine-Case Comparison

**Files:**
- Read: `intelligence/tests/fixtures/runtime_backend_cases.json`
- Execute: `scripts/run_agent_runtime_benchmark.py`
- Create outside Git: `/Users/a77/.finance-runtime/evals/agent-runtime-backends-2026-07-25.json`

- [ ] Run `continuous_glm` and `sdk_glm` against all nine cases without changing prompts, dates, budgets, or required outputs.
- [ ] Attempt `codex_headless` with the same fixture and record `headless_usage_limit` if the account quota still blocks it.
- [ ] Validate that every available `(case, backend)` record has status, answer or question-specific gap, runtime identity, verifier status, latency, attempts, tools, duplicate count, protocol issues, and artifact SHA.
- [ ] Reject any artifact containing silent fallback or cross-arm answer reuse.
- [ ] Keep deterministic fast-path answers identical with zero runtime LLM calls.

Command:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/run_agent_runtime_benchmark.py \
  --backend continuous_glm \
  --backend sdk_glm \
  --questions-file intelligence/tests/fixtures/runtime_backend_cases.json \
  --output /Users/a77/.finance-runtime/evals/agent-runtime-backends-2026-07-25.json
```

Expected: 18 complete arm records or explicit question-specific partial records; no missing matrix cell.

## Task 3: Blind Review and Contract-Gap Diagnosis

**Files:**
- Create outside Git: `/Users/a77/.finance-runtime/evals/agent-runtime-backends-2026-07-25-blind.json`
- Modify: `docs/verification/agent-runtime-backends-2026-07-25.md`

- [ ] Use a saved deterministic seed to map backend names to A/B independently per case.
- [ ] Exclude backend, model, latency, trace, and execution order from the review packet.
- [ ] Score each answer 0-4 for directness, completeness, analytical synthesis, uncertainty calibration, usefulness, and naturalness.
- [ ] Record a pairwise winner and one-sentence reason for every non-fast-path case.
- [ ] Classify each failure as runtime execution, evidence availability, verifier behavior, or `TaskFrame.required_outputs` contract gap.
- [ ] Do not add a new route in this phase; propose TaskFrame contract changes only when the frozen artifact proves the runtime never received the required goal.

Expected: a backend recommendation is based on answer quality, not merely transport success or verifier pass rate.

## Task 4: Full Regression and Defect Repair

**Files:**
- Test: `intelligence/tests/`
- Test: `intelligence/webapp/`
- Modify only files implicated by a reproducible acceptance failure.

- [ ] Run focused runtime, verifier, Conversation, and benchmark tests.
- [ ] Run the full Python suite with user-specific environment overrides removed.
- [ ] Run frontend unit tests, lint, typecheck, and production build.
- [ ] For each newly discovered defect, add a failing regression test before the minimal fix.
- [ ] Re-run the affected E2E case after each fix; do not infer semantic quality from unit tests alone.

Commands:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_protocol.py \
  intelligence/tests/test_agent_runtime_factory.py \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_openai_agents_runtime.py \
  intelligence/tests/test_runtime_backend_benchmark.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py \
  intelligence/tests/test_workbench_conversation_integration.py

env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER \
  -u SUBCONSCIOUS_VAULT -u AGENT_MEMORY_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q

cd intelligence/webapp
pnpm test --run
pnpm lint
pnpm typecheck
pnpm build
```

Expected: no new Python failure and all frontend gates pass.

## Task 5: Production-Candidate Decision and Handoff

**Files:**
- Modify: `docs/workbench/local-site.md`
- Create/Modify: `docs/verification/agent-runtime-backends-2026-07-25.md`
- Modify: `/Users/a77/agent-memory/20_projects/finance-workspace-private.md`

- [ ] Document explicit backend selection, credential injection, benchmark-only headless constraints, and rollback behavior.
- [ ] Mark each design requirement `proved`, `contradicted`, `incomplete`, or `blocked`.
- [ ] State whether 8796 is recommended as the production candidate and why.
- [ ] List remaining differences from Codex headless and whether each is runtime, model, tool, or contract related.
- [ ] Record only stable decisions and test totals in project memory.
- [ ] Commit the verification artifacts, leave the branch clean, and wait for explicit approval before merge or 8792 cutover.

Completion gate: the phase is complete only after UI/SSE evidence, the real nine-case comparison, human blind review, and full regression are all recorded. `sdk_gpt` remains a separately blocked arm until an OpenAI credential is available; it is not silently treated as tested.

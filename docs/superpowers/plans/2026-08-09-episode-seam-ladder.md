# Episode Seam Ladder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or inline execution task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible, single-arm Episode assembly ladder that incrementally exposes market research capabilities and separately records offline component evidence and opt-in current-production relay smoke receipts.

**Architecture:** A new runner composes existing `TurnControlCore`, `build_episode_context`, `build_episode_registry`, `GLMAgentRuntime`, and both verifier boundaries. It derives each stage's contract and registry from the canonical source control result without changing task outputs; its only experiment variable is the capability surface. Offline mode supplies a scripted model and fixture-local read-only runners while retaining the real Episode and registry execution loop. Live mode explicitly opts into the resolved production provider and writes receipts outside Git.

**Tech Stack:** Python 3.11, pytest, dataclasses, existing Finance Workbench Episode runtime and ResearchToolRegistry.

---

## File Structure

- Create `scripts/run_episode_seam_ladder.py`: stage definitions, fixture parsing, stage contract/registry derivation, offline scripted components, live preflight, artifact writing, and CLI.
- Create `intelligence/tests/fixtures/episode_seam_ladder_cases.json`: three 2026-08-07 market cases with stage floors.
- Create `intelligence/tests/test_episode_seam_ladder.py`: artifact, contract/registry, no-side-effect, success, and failure-classification regression tests.
- Create `docs/verification/2026-08-09-episode-seam-ladder.md`: commands run and actual offline/live receipts, only after implementation evidence exists.

## Task 1: Freeze The Ladder Input And Stage Surface

**Files:**
- Create: `intelligence/tests/fixtures/episode_seam_ladder_cases.json`
- Create: `intelligence/tests/test_episode_seam_ladder.py`
- Create: `scripts/run_episode_seam_ladder.py`

- [ ] **Step 1: Write fixture parsing and stage-surface tests**

Test three valid cases (`next-session-index` at S1, `current-mainline` at S2, `weekly-market-cause` at S3), reject duplicate ids / unknown stage floors, and assert S0 has no enabled capability, S1 has only `market_data`, S2 adds `mainline_context`, and S3 adds `news_search` and `evidence_search`.

Add one test that locks the measured routing/evidence-plan facts each floor depends on, so a later question-text edit cannot silently move a case below its legal floor:

```python
@pytest.mark.parametrize(
    "case_id, question_type, mandatory, floor",
    [
        ("next-session-index", "market_forecast", ("market_data",), "S1"),
        ("current-mainline", "market_watch", ("market_data", "mainline_context"), "S2"),
        ("weekly-market-cause", "market_cause", ("market_data", "news_search"), "S3"),
    ],
)
def test_fixture_floor_matches_production_evidence_plan(
    case_id, question_type, mandatory, floor
):
    ...
```

`ResearchTaskContract.__post_init__` rejects a contract whose `evidence_plan` mandatory capabilities are not a subset of `allowed_capabilities`, so a case placed below this floor fails at contract construction and never reaches a model or tool. That is a fixture design error, not a seam finding.

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_seam_ladder.py
```

Expected: collection fails because `scripts.run_episode_seam_ladder` does not exist.

- [ ] **Step 3: Implement immutable case and stage definitions**

Define validated frozen dataclasses for fixture cases and stage definitions. Use explicit tuples:

```python
STAGES = (
    Stage("S0", "planning", ()),
    Stage("S1", "market-data", ("market_data",)),
    Stage("S2", "mainline-context", ("market_data", "mainline_context")),
    Stage("S3", "causal-evidence", ("market_data", "mainline_context", "news_search", "evidence_search")),
)
```

Fixture parsing must require `id`, `question`, `as_of`, `tier`, `timeout`, and `expected_stage_floor`, and must reject unknown floors and non-positive timeouts.

- [ ] **Step 4: Run focused tests and commit**

Run the Task 1 tests. Commit only the fixture, runner, and focused test file:

```bash
git add scripts/run_episode_seam_ladder.py intelligence/tests/fixtures/episode_seam_ladder_cases.json intelligence/tests/test_episode_seam_ladder.py
git commit --only scripts/run_episode_seam_ladder.py intelligence/tests/fixtures/episode_seam_ladder_cases.json intelligence/tests/test_episode_seam_ladder.py -m "test: add episode seam ladder stages"
```

## Task 2: Derive A Stage-Scoped Contract And Registry

**Files:**
- Modify: `scripts/run_episode_seam_ladder.py`
- Modify: `intelligence/tests/test_episode_seam_ladder.py`

- [ ] **Step 1: Write failing stage-derivation tests**

Construct a source `ResearchRunContext` using production `build_episode_context`, build a real registry, derive S1, and assert:

```python
assert stage_context.contract.required_outputs == source.contract.required_outputs
assert stage_context.contract.allowed_capabilities == ("market_data",)
assert stage_registry.names() == ("market_data",)
assert all(
    spec.capability in stage_context.contract.allowed_capabilities
    for spec in stage_registry.authorized_specs()
)
```

Add an S3 assertion that every schema tool name resolves through the stage registry to one of S3's capabilities. Add a test showing a model request for an absent tool is classified as `contract_or_verifier`, not silently executed.

- [ ] **Step 2: Run focused tests and confirm failure**

Run the new test selectors. Expected: missing stage context/registry builder.

- [ ] **Step 3: Implement stage derivation without copying tool declarations**

Call production `build_episode_context` first. Derive a context with `dataclasses.replace`: replace only its contract's `allowed_capabilities` with the ordered intersection of source capabilities and stage capabilities. Preserve the same task id, required outputs, evidence plan, deadline, policy, cutoff, and hash.

Before constructing the replacement contract, reject a stage whose mandatory evidence-plan capabilities are not a subset of the stage intersection. Return an explicit planning/`contract_or_verifier` result rather than weakening required outputs or evidence plan.

Build the complete registry through `build_episode_registry`, then retain `authorized_specs(stage_context.contract.allowed_capabilities)` in a new `ResearchToolRegistry`. Do not duplicate the default metadata table or tool runners.

- [ ] **Step 4: Run focused tests and commit**

Run the focused test module. Commit only the runner and its tests:

```bash
git add scripts/run_episode_seam_ladder.py intelligence/tests/test_episode_seam_ladder.py
git commit --only scripts/run_episode_seam_ladder.py intelligence/tests/test_episode_seam_ladder.py -m "feat: derive episode seam stage contracts"
```

## Task 3: Implement Offline Real-Loop Execution And Receipts

**Files:**
- Modify: `scripts/run_episode_seam_ladder.py`
- Modify: `intelligence/tests/test_episode_seam_ladder.py`

- [ ] **Step 1: Write failing offline execution tests**

Provide a scripted model sequence `PLAN -> allowed tool call -> FINAL_JSON` and fixture-local runners returning deterministic `AgentEvidence` hashes. Assert an S1 result contains:

```python
assert result["execution_kind"] == "continuous_episode"
assert result["structural_status"] == "completed"
assert result["semantic_status"] == "passed"
assert result["tool_calls"] == 1
assert result["evidence_hashes"]
assert result["failure_class"] == ""
```

Also assert the model saw only stage registry schemas and that `tool_request` / `tool_result` events are present. Test S0 never builds runtime or invokes model/tool factories.

- [ ] **Step 2: Run focused tests and confirm failure**

Run the test module. Expected: missing runner execution path.

- [ ] **Step 3: Implement offline component composition**

Use `GLMAgentRuntime(client=scripted_model)` to run the real Episode loop. Construct fixture-local `ToolSpec` runners only through the same stage filtering mechanism; their output is deterministic evidence and `ProviderTrace`, while `ResearchToolRegistry.execute` remains real. Run `verify_episode_outcome`; use a deterministic semantic verifier that returns a valid `SemanticEpisodeOutcome` only from the structural output.

Record source context/contract, stage id, enabled capabilities, schema tool names, execution events, evidence hashes, usage, structural/semantic status, precheck payload, and blank failure fields. Reuse `smoke_workbench_self_use._atomic_write_json` for write safety.

- [ ] **Step 4: Add artifact shape and failure classification tests**

Assert offline artifact has `artifact_kind="episode_seam_ladder"`, UTC timestamp, fixture SHA-256, `runtime.provider="scripted"`, and source revision. Add separate scripted provider exception, tool exception, and bad binding tests asserting `provider_or_budget`, `tool_or_data`, and `contract_or_verifier` respectively.

- [ ] **Step 5: Run focused tests and commit**

Run the test module and commit only the runner and its test module.

## Task 4: Add Opt-In Live Mode And Preflight

**Files:**
- Modify: `scripts/run_episode_seam_ladder.py`
- Modify: `intelligence/tests/test_episode_seam_ladder.py`

- [ ] **Step 1: Write failing live-safety tests**

Assert default invocation is offline and no real provider factory is called. Assert `--live` requires an output path below `/Users/a77/.finance-runtime/seam-ladder/`, and preflight records a `preflight` failure without building a runtime when continuous mode is not `on`, market data date predates fixture `as_of`, or provider chain is empty.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run the test module. Expected: CLI lacks live guard/preflight.

- [ ] **Step 3: Implement explicit live mode**

Add `--live` and `--output`; default output only in offline mode. In live mode require output under the fixed external receipt root, load resolved providers with `llm_refine.detect_providers()`, record only provider name/model (never endpoint or credentials), verify `ASK_CONTINUOUS_RUNTIME=on`, and determine latest market date through the same market-date helper used by product code.

Run only S1 `next-session-index` and S3 `weekly-market-cause`; use production `GLMModelClient`, `GLMAgentRuntime`, `SemanticEpisodeVerifier`, and `EpisodeFinalizer`. Map timeout/provider failures to `provider_or_budget`; do not make live results a process-wide pass/fail merge gate.

- [ ] **Step 4: Run focused tests and commit**

Run the focused tests and commit only the runner/test changes.

## Task 5: Verify And Record Evidence

**Files:**
- Create: `docs/verification/2026-08-09-episode-seam-ladder.md`

- [ ] **Step 1: Run static and offline verification**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_seam_ladder.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/run_episode_seam_ladder.py --output /tmp/episode-seam-ladder-offline.json
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/layer_audit.py
```

Inspect the offline receipt: S0 has no execution; each expected stage/case has continuous episode evidence; no schema tool maps outside the enabled capability surface.

- [ ] **Step 2: Run opt-in live smoke only if preflight is ready**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/run_episode_seam_ladder.py --live --output /Users/a77/.finance-runtime/seam-ladder/<UTC timestamp>-<revision>.json
```

If preflight fails or provider times out, preserve the external receipt and record it as environment evidence, not a code regression. Do not retry automatically.

- [ ] **Step 3: Write a concise verification record and commit**

Record source revision, test counts, artifact locations, whether live was attempted, and the failure-class conclusion. Do not commit external receipt files. Commit only the verification markdown after evidence is available.

- [ ] **Step 4: Run final scoped verification**

Run focused pytest, `ruff check` on the new runner/test, `git diff --check`, and `scripts/layer_audit.py`.

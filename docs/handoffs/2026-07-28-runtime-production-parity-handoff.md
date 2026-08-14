# Adaptive Runtime Production-Parity Handoff

Date: 2026-07-28
Branch: `feat/agent-runtime-backends-verify`
Committed HEAD: `6ef50166674bf07d796772f9f56793f583cd67be`
Worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Status: `offline_core_green; live_3_of_5; benchmark_parity_wip_red`

## Safety boundary

- `main`, 8792, and 8799 were not modified or switched.
- Formal runtime `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667`
  remains at `69f9cf17`; do not fast-forward it yet.
- No secret, environment file, database, or benchmark artifact was committed.
- The primary workspace is dirty and must not be used for development.

## Completed and committed

### Runtime budget/cutoff hardening

The earlier batch through `8f417fe2` completed:

- native Security.framework Keychain reads;
- immutable cutoff in model input;
- cutoff-aware market/mainline/valuation data selection;
- current-task historical query authorization;
- SDK versus GLM reserve separation.

Verification before live: focused 189 passed, adapter/orchestrator 179 passed,
executable full suite 2916 passed and 1 skipped.

### Delivery and semantic deadline seams

Product commits:

- `b81d1f11`: model-visible mandatory capability progress and
  `mandatory_evidence_complete + finish_hint` after real evidence success;
- `c42454e4`: dynamic SDK delivery reserve; a 60-second run closes tools after
  about 45 seconds and returns typed `research_stage_closed` without a public
  gap;
- `7e91f74b`: semantic provider attempts share at most 30 seconds, default
  `15 + 7.5 + 7.5`, while retaining the existing third release-safe retry.

The structural and semantic pass predicates were not loosened. Offline results:

```text
OpenAI Agents runtime: 28 passed, 1 skipped
Semantic verifier: 144 passed
Focused composition: 540 passed, 1 skipped
Executable intelligence suite: 2919 passed, 1 skipped
```

Verification: `docs/verification/sdk-delivery-and-semantic-deadline-2026-07-28.md`.

## Frozen live result

Artifact:

`/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-28-7e91f74b.json`

Provenance is trustworthy: revision `7e91f74b`, `source_dirty=false`, Keychain
credential, five cases, no canonical runtime switch.

Results:

| Case | Result | Latency | Tools | Finding |
|---|---:|---:|---:|---|
| rebound-duration | completed/repaired | 54.5s | 1 | useful answer |
| ruihuatai-valuation | partial/sdk_timeout | 60.0s | 2 | both mandatory tools succeeded; no final binding |
| weekly-market-cause | partial/sdk_timeout | 60.0s | 5 | mandatory evidence completed; continued two empty news checks; no final binding |
| current-mainline | completed/passed | 56.5s | 2 | semantic window fix worked; no 90s tail |
| unfamiliar-methodology | completed/passed | 36.0s | 0 | model reasoning path healthy |

The hard gate is false: 3/5 completed, two protocol issues.

## Newly proven root cause

`scripts/run_agent_runtime_benchmark.py::_run_research_arm()` directly calls:

```text
runtime.run() -> verify_episode_outcome() -> semantic.verify()
```

Production uses:

```text
runtime.start() -> ContinuousTurnAdapter
  -> timeout/invalid-finish RepairGoal
  -> same EpisodeSession delivery repair
  -> structural + semantic verification
```

The benchmark therefore bypasses the component that owns the already-tested
tool-closed delivery repair. This is the architectural reason unit/integration
tests were green while the live release artifact still returned raw SDK
timeouts. Approved specs already say `ContinuousTurnAdapter` is the sole product
adapter and the benchmark is a production-candidate release gate.

Design and plan are committed in `6ef50166`:

- `docs/superpowers/specs/2026-07-28-runtime-benchmark-production-parity-design.md`
- `docs/superpowers/plans/2026-07-28-runtime-benchmark-production-parity.md`

## Uncommitted WIP — do not assume green

The isolated worktree intentionally contains two modified files:

- `scripts/run_agent_runtime_benchmark.py`
- `intelligence/tests/test_run_agent_runtime_benchmark.py`

Current WIP adds a semantic capture wrapper and composes the benchmark through
`ContinuousTurnAdapter`. The public CLI red test initially proved the bug:

```text
resume_calls == 0
```

After the partial implementation it now reaches the Adapter repair seam:

```text
resume_calls == 1
arm.status == failed
issue == production adapter did not reach semantic verification
```

The remaining failure is in the new fake fixture, not yet evidence that the
Adapter composition is wrong. `CallbackEpisodeSession` requires every resume
to append a `model_turn` event; the fake currently appends only `repair_goal`
and `repair_reentry`. It also supplies only one evidence capability, while the
current-mainline contract has three required outputs and mandatory
`market_data + mainline_context`.

## Exact next steps

1. Repair only the fake CLI fixture:
   - provide both mandatory capability evidence;
   - bind all three current-mainline required outputs;
   - append a `model_turn` after `repair_reentry`;
   - preserve the initial event prefix.
2. Re-run only:

   ```bash
   env -u FORESIGHT_USERS_DIR \
     /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
     intelligence/tests/test_run_agent_runtime_benchmark.py \
     -k production_adapter_delivery_repair
   ```

3. If green, run the complete benchmark test file and inspect regressions from
   existing fake runtimes that implement only `run()`; the Adapter must retain
   its one-shot compatibility path.
4. Add the separate red test that `sdk_timeout` has `invalid_actions == 0` while
   `sdk_invalid_finish` remains 1. Implement typed accounting without changing
   timeout status/gap/stop reason.
5. Run focused benchmark/runtime/Adapter suites, then the executable full
   intelligence suite. Review specifically for:
   - no copied repair loop in benchmark;
   - no verifier/gate relaxation;
   - no question-specific branch;
   - one semantic verifier owner;
   - no risk files.
6. Freeze a new clean revision. Only then run the five-case live gate once from
   the Terminal-authorized Keychain process. Do not use the frozen suite as the
   development loop.

## Progress accounting

- Core adaptive runtime implementation: about 90% complete.
- Current delivery/semantic optimization implementation and offline validation:
  100% complete.
- Formal live acceptance: 3/5 cases, therefore 60%, not release-ready.
- Benchmark production-parity repair: design complete; red test and initial
  wiring complete; implementation approximately 40% and currently uncommitted.

The formal candidate must not be fast-forwarded until the new production-parity
artifact is 5/5 and independently reviewed.

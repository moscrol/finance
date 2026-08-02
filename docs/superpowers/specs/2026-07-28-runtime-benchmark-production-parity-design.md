# Runtime Benchmark Production-Parity Design

Date: 2026-07-28
Status: approved under the existing Adaptive Runtime objective
Implementation branch: `feat/agent-runtime-backends-verify`

## Problem

The frozen `7e91f74b` live artifact returned three completed cases and two SDK
timeouts. Both failed cases had already collected mandatory evidence, and the
valuation case stopped optional research exactly as designed. Neither trace
contained `repair_goal` or `repair_reentry`.

The cause is a composition mismatch. The product contract names
`ContinuousTurnAdapter` as the sole product adapter and gives it ownership of
same-episode repair and shared structural/semantic verification. The benchmark
instead calls `runtime.run()` directly and then invokes both verifiers itself.
It therefore cannot exercise the already-implemented timeout delivery repair.

This is why unit/integration tests passed while the release artifact remained
red: the E2E runner skipped the component under test.

## Selected design

Production-candidate benchmark arms run through `ContinuousTurnAdapter` with
the already-frozen context, registry, runtime, semantic verifier, deadline, and
backend label. A small capture wrapper records the final
`SemanticEpisodeOutcome` so the existing `RuntimeArmResult` and diagnostics can
still be built from typed objects.

The adapter remains the only owner of:

- `runtime.start()` versus one-shot `run()` selection;
- `sdk_timeout`/invalid-finish delivery repair;
- repair grants and cycle caps;
- structural verification and semantic re-verification;
- final public projection.

The benchmark does not implement its own repair loop and does not relax any
gate. Deterministic fast paths remain unchanged. A backend without a resumable
session still follows the adapter's one-shot fallback and receives no invented
repair capability.

## Failure accounting

`AgentUsage.invalid_actions` represents invalid protocol/model actions, such as
malformed terminal output. A host/provider deadline is not an invalid action.
`sdk_timeout` therefore remains a typed stop reason and partial status, but it
does not increment `invalid_actions`. If delivery repair succeeds, the final
completed outcome no longer carries a false protocol violation. If repair does
not succeed, status/structural/semantic gates still fail closed.

## Interfaces and tests

- Public evaluation seam: benchmark CLI artifact.
- Product composition seam: `ContinuousTurnAdapter.handle()`.
- Runtime seam: `EpisodeSession.resume(RepairGoal)`.

A scripted CLI case returns timeout plus evidence from the initial session,
then returns a valid bound answer from a zero-tool resume. The test must fail on
the current direct runner and pass only when the artifact contains a completed
arm with repair events and zero protocol issues.

## Acceptance

1. The benchmark invokes `runtime.start()` for a resumable SDK runtime.
2. Timeout evidence enters exactly one tool-closed delivery repair.
3. The final arm is built from the repaired and semantically verified outcome.
4. `sdk_timeout` alone does not count as an invalid action; invalid finish does.
5. Existing benchmark schema, cutoff, citation, secret, and hard-gate rules are
   unchanged.
6. Focused and executable full suites pass before one new frozen live run.

## Rejected approaches

1. Copy Adapter repair into the benchmark: creates a second product runtime.
2. Increase the five-case timeout: hides the skipped composition root.
3. Ignore protocol issues in the summary: weakens the gate instead of fixing
   failure identity.
4. Auto-complete from evidence without another model call: bypasses answer
   composition and semantic verification.

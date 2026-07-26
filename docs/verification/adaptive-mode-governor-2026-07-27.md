# Adaptive Mode Governor Verification

Date: 2026-07-27  
Branch: `feat/agent-runtime-backends-verify`  
Product commit: `34b9d4b0`

## Result

The first valid model-owned `ResearchPlan` now receives exactly one governed
quick/deep decision in the same `ContinuousAgentEpisode`. An approved deep
request promotes the existing episode ledger rather than minting a second
budget authority. Denied promotion leaves standard bounds unchanged.

The event order is observable as `plan -> mode_decision`. The decision records
requested/effective mode, approval reason, observable conditions, tier, tool
cap, time target, repair-cycle cap, and branch cap. Prompts and model messages
remain excluded from the safe diagnostic projection.

## Invariants proved

- explicit user quick mode cannot be overridden by a model deep request;
- model deep requires an observable complexity condition unless the user
  explicitly selected deep;
- missing dependencies or deadline authority fail closed to quick;
- promotion is episode-bound, increase-only, idempotent, and capped at 24
  calls / 240 seconds;
- the original contract, information cutoff, root-ledger identity, episode
  history, and continuation state survive promotion;
- quick runs do not inherit deep budget merely because the loop can represent
  the deep maximum;
- the seventh tool call executes only after an approved promotion;
- no route name, `question_type`, keyword intent table, or fixed tool order is
  used to make the mode decision.

## Deterministic verification

Focused cross-module command:

```text
195 passed in 0.57s
```

This includes ModeGovernor, episode/runtime integration, continuation,
adapter, diagnostic, and all 26 permanent repair/session invariant guards.

Full `intelligence/tests` command:

```text
2794 passed, 2 skipped, 11 failed in 100.81s
```

All 11 failures are the existing local `subconscious/userspace` path-isolation
baseline: the tests patch repository-local user paths while the machine's
shared Agent Memory environment remains authoritative. No failure touches the
adaptive mode files or changed seams.

Ruff passed for all changed Python files and `git diff --check` passed.

## Deliberate non-actions

- no sub-research branch implementation in this milestone;
- no branch-facing EvidenceLedger facade yet;
- no `MemoryGate` yet;
- no frozen nine-case live benchmark run;
- no canonical 8792 switch;
- no `main` merge;
- no review-harness modification;
- no Claude review request before the complete target milestone.

## Alignment note

`/Users/a77/.finance-runtime/agent-review-loop/ALIGNMENT.md` remains binding.
The review harness stays frozen. Its permanent invariant tests are green, and
the final review contract can now inspect the mode decision without accessing
prompts or hidden model state. Phase 2 partial reasons, per-tool traces,
cutoff rejection records, and repair identifiers were completed before this
milestone and remain covered by the existing runtime diagnostics.

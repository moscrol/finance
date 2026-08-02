# Repair admission deepening

Date: 2026-07-27
Branch: `feat/agent-runtime-backends-verify`
Scope: make the repair policy a deep coordinator seam without changing its
budget formulas or Episode semantics.

## Before

`ContinuousTurnAdapter._resume_for_gap()` constructed a `RepairGoal`, chose
between `grant_for_progress()` and `grant_for_delivery_repair()`, rewrote the
goal with the grant, and then called the Episode session. The coordinator
contained the policy pieces but not one decision interface.

## After

`repair_coordinator.admit_repair()` returns an immutable
`RepairAdmission(goal, grant, delivery_only)`. It owns the existing tier cap,
progress predicate, root-budget grant, and delivery-repair fallback. The
Adapter now only executes `admission.goal` and verifies the returned outcome.
The primary model still owns the next tool/query; the coordinator never mints
a query or chooses a tool.

## Verification

- New seam regression:
  `test_admit_repair_returns_one_execution_ready_delivery_admission`.
- Repair coordinator + adapter + SDK runtime focused set: `105 passed, 1
  skipped`.
- Full intelligence suite is required before this slice is committed.
- No changes to routes, skills, budgets, verifier thresholds, 8792, or `main`.

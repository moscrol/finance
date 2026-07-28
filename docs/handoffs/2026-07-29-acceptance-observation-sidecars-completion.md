# Acceptance Observation Sidecars Completion Handoff

Date: 2026-07-29
Milestone status: complete
Final Adaptive Finance Agent Runtime goal: active, not complete

## Start here

```text
worktree: /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
branch: feat/agent-runtime-backends-verify
design/plan: 4dc941f7
implementation: 8126bbf7
```

Do not stop at this handoff. Do not merge `main`, switch 8792, merge KB `9053b0c4`, run the
28-case board repeatedly, or implement App Server before the fair-control gate.

## What is now true

- Truth and experience observations can be added without changing frozen runs, case contracts,
  or reference answers.
- A sidecar is bound to the exact run, cases, overlay, evaluator, rubric, and its own canonical
  hash.
- Truth observations may address only rules the deterministic evaluator declares external.
- Experience labels require a separate sealed pair manifest, independent reviewer, exact Knevo
  snapshot hash, and case-specific eligible dimensions.
- Deterministic truth failure always outranks an external semantic pass.
- The board is byte-compatible without explicit sidecars and fails closed on mismatched ones.
- All 28 Knevo cases now have typed eligibility records: 22 snapshots are accounted for and six
  remain explicitly missing.

No semantic or blind label was invented in this milestone.

## Verification

```text
focused acceptance surfaces: 56 passed
Ruff / diff / JSON-hash probes: passed
full intelligence suite: 2993 passed, 14 failed, 2 skipped
```

The 14 full-suite failures are the unchanged managed-sandbox loopback-bind baseline. Detailed
evidence is in `docs/verification/acceptance-observation-sidecars-2026-07-29.md`.

## Immediate final-goal sequence

1. Run one non-frozen, non-financial minimal `gpt-5.6-sol` readiness probe. It may establish
   provider availability only; it may not be counted as an acceptance result.
2. Recheck the preregistered `CC_EXEC_PORT=28080` local route. If absent, record the external
   block and continue offline work; do not replace it with subprocess or dry-run output.
3. If the route is available, execute A→B→C→D exactly as preregistered and freeze each artifact.
4. Use real semantic observations only with explicit rubric and source provenance. Experience
   labels still require an actually independent blind reviewer and sealed pair manifest.
5. Apply the App Server v2 decision rule. Implement the adapter only if the fair profile-D
   control leaves a material generic-harness gap.
6. Run the 28-case Conversation API board once only after shared-seam fixes and a non-zero
   threshold are preregistered; then construct same-format Knevo truth/experience comparisons.
7. Mark the final goal complete only when the candidate is release-ready with no cutoff,
   freshness, evidence-lineage, invalid-action, or semantic-verifier weakening.

## Current external observation

During verification, a process briefly appeared as listening on port 28080, but a direct
`/api/ping` immediately afterward received connection refused and no ambient `CC_EXEC_TOKEN`
was present. This is not evidence that the route is ready. Recheck once at execution time; do
not loop on it or expose credentials.

## Boundaries

- Model remains `gpt-5.6-sol`.
- Credentials remain ambient and must never be printed, copied, or committed.
- The frozen A/B/C/D source revision and input hash must match the preregistration or execution
  stops before A.
- Historical completed/partial states, message counts, and the `1/7` judgeable subset are not a
  product pass rate.
- App Server v2 is an approved experiment design, not yet an authorized implementation result.

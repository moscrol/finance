# Acceptance Verdict Seam Completion Handoff

Date: 2026-07-29
Milestone status: complete
Final Adaptive Finance Agent Runtime goal: active, not complete

## Start here

```text
worktree: /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
branch: feat/agent-runtime-backends-verify
design/plan: 77f7bb5a
implementation: b77e84ec
```

Do not use this milestone as permission to merge `main`, switch 8792, merge KB `9053b0c4`,
run all 28 live cases, or implement App Server before its decision gate.

## What is now true

The acceptance board no longer treats runtime status, answer count, truth, and user preference
as one number. The new deep module provides:

- a compiled, additive contract for every one of the 28 frozen cases;
- separate operational, truth, and experience verdicts;
- `pass/fail/unjudgeable/not_run` truth semantics;
- rule-level evidence and reasons;
- typed input slots for later semantic, exact-set, inherited-golden, and blind-experience
  observations;
- a CLI board that prints separate denominators and labels `1/7` as a judgeable-subset rate,
  not a 28-case pass rate.

The canonical questions and 22 Knevo snapshots remain byte-identical. No live case was run.

## Historical result, correctly scoped

Latest committed historical run:

```text
operational: 18 not run / 7 degraded / 3 completed
truth:       18 not run / 1 pass / 6 fail / 3 unjudgeable
experience:  28 unlabeled
```

This does not establish present product quality because the run is old, covers only ten
long-tail cases, and predates the freshness/causal/valuation repairs. Its value is evaluator
calibration: the compiler distinguishes real deterministic failures from missing judgment.

## Verification

- Focused: `67 passed`.
- Full: `2981 passed, 14 failed, 2 skipped`.
- All 14 failures are the pre-existing managed-sandbox prohibition on loopback `socket.bind()`;
  none touches the verdict code.
- Ruff, JSON parsing, compileall, and diff whitespace checks pass.

Detailed evidence:

- `docs/verification/acceptance-verdict-seam-2026-07-29.md`
- `docs/superpowers/specs/2026-07-29-acceptance-verdict-seam-design.md`
- `docs/superpowers/plans/2026-07-29-acceptance-verdict-seam.md`

## Next final-goal sequence

1. Preserve the frozen A/B/C/D budget preregistration. Do not substitute subprocess or dry-run
   results for the unavailable `CC_EXEC_PORT=28080` route.
2. Restore a legal live route for the three-case budget ablation and `gpt-5.6-sol` semantic
   judge, or record the external block while continuing offline work.
3. Revise the existing Codex App Server ceiling spec against all 13 recorded findings. Spec
   revision is allowed offline; App Server implementation remains conditional on the fair
   budget result.
4. Define provenance-rich semantic observation and blind-experience artifact schemas that feed
   the typed verdict slots without altering frozen runs.
5. Apply Knevo `use_as`, leakage, local-definition, and reconstruction caveats per case; never
   divide every comparison by 22.
6. Only after shared-seam fixes and a preregistered non-zero threshold, run the real 28-case
   Conversation API board once and freeze it.
7. Build App Server only if the fair-budget ceiling test still demonstrates a generic-harness
   gap, then preserve EvidenceLedger, cutoff, root budget, and publication verifiers around it.
8. Release/canary/8792/legacy deletion remain user-authorized terminal actions, not automatic
   consequences of this handoff.

## Stop condition

Do not stop because this file exists. Stop only when the active final goal's objective is
actually achieved: fair comparison, restored semantic judgment, justified App Server decision,
truth/experience Knevo comparison, and a release-ready candidate with no gate weakening or
future-data leakage.

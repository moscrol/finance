# Adaptive Runtime Final Quality Handoff

Date: 2026-07-29
Status: **deterministic engineering candidate complete; final product evaluation goal remains active**
Worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Branch: `feat/agent-runtime-backends-verify`

## Executive summary

The adaptive finance runtime now has three previously missing deterministic
boundaries on the pinned true-Hybrid path:

1. index freshness is judged from verified manifest content identity in the
   isolated KB candidate;
2. weekly causal retrieval cannot promote first-hit company/topic noise and
   cannot report success without target-window support plus counter-evidence;
3. valuation retrieval cannot present bare cross-entity Wiki co-occurrence as
   model evidence or let a model tool query replace the TaskFrame-owned subject.

This is not a claim that the complete product has shipped. The candidate branch
has not been merged to `main`, canonical 8792 has not been switched, the live
semantic judge lacks a configured provider, and the wider 28-case/Knevo product
evaluation has not been run.

## Acceptance measurement update

The final-goal work after this handoff added three measurement controls:

```text
77f7bb5a / b77e84ec / 6a6d1744  three-axis acceptance verdict seam
4dc941f7 / 8126bbf7              hash-bound observation sidecars
2753fe1b                         first App Server ceiling experiment v2 spec
```

The historical 10-case artifact is now reported as 18 not-run, 7 degraded, and
3 completed operationally; 18 not-run, 1 pass, 6 fail, and 3 unjudgeable on
truth; and 28 unlabeled on experience. `1/7` is only the judgeable historical
subset, never a 28-case product pass rate.

All 28 Knevo cases now have typed reference eligibility. Twenty-two snapshots
exist and six are explicitly missing; aliases and hindsight/reconstruction or
local-definition caveats do not enlarge the denominator. No semantic or blind
label has been invented.

Observation sidecars are bound to the exact run, case file, verdict overlay,
evaluator, rubric, and their own hash. Blind labels additionally bind a sealed
pair manifest, exact reference snapshot, independent reviewer, and eligible
dimensions. Deterministic hard failures cannot be overwritten.

## Live control transport correction

The first attempted A/B/C/D run on 2026-07-29 did not test budgets: all twelve cells called the
authorized wrapper, but nested Codex `read-only` sandboxing denied its loopback connection, so
every arm stopped with zero tool calls. The shared local-exec seam is now fixed with an
ephemeral-cwd-only `workspace-write` sandbox, explicit network access, and global temp roots
excluded. Finance and Wiki roots remain read-only. See
`docs/verification/headless-local-exec-loopback-seam-2026-07-29.md`.

Those first four artifacts remain invalid failure receipts. The fair experiment requires a
new preregistration amendment and new artifact paths pinned to the fix commit.

That amendment is now `docs/verification/headless-budget-ablation-preregistration-v2-2026-07-29.md`.
It pins source `da614908`, preserves every original treatment and decision rule, and assigns
new v2 artifact paths so the invalid receipts cannot be overwritten.

The v2 run is now complete. Profile D is valid with seven observed calls. Pairwise interpretation
rejects floor removal as an improvement, identifies 180-second wall-clock room as the primary
cross-case factor, and finds the six-call cap secondary. Longer profiles expose repeated
capability use and persistent news/evidence-search failures. Detailed evidence is in
`docs/verification/headless-budget-ablation-v2-results-2026-07-29.md`.

## Delivered code

### Causal slice

```text
44a36566 fix: distinguish skipped retrieval attempts
c74d61ce fix: keep unanchored causal retrieval query-only
12726e9a fix: require causal evidence window coverage
68974ca6 fix: apply causal evidence policy in episodes
2703ff7c docs: hand off causal anchor guard
```

The true-Hybrid weekly replay now returns honest `empty`: nine old hits were
window-rejected, no 2026-07-20..24 evidence entered the observation, and all
executed attempts remained `hybrid->hybrid`.

### Valuation slice

```text
6223cd7d docs: design valuation evidence admission
d6827606 docs: plan valuation evidence admission
e4bcc3f3 fix: admit only subject-local valuation evidence
c57ad73a fix: enforce valuation evidence admission in episodes
4cd36122 fix: bind valuation admission to task subject
```

The final 瑞华泰 true-Hybrid replay projects seven subject-local evidence atoms.
天奈科技 and 方邦股份 are absent from model evidence and semantic-judge input;
explicit non-valuation relationships remain auditable clues.

## Verification ledger

- Causal proportional gate: `240 passed` before the valuation slice.
- Final proportional gate: `246 passed`; Ruff and diff checks pass.
- Final full suite: `2958 passed, 24 failed, 2 skipped`; all 24 are reproduced
  environment-baseline failures (14 sandbox socket binds, 10 userspace override),
  none on changed surfaces.
- Final code review: Standards 0 hard violations; Spec PASS after two found
  defects were fixed with regressions.
- KB candidate clean at `9053b0c4`; original KB remains `main@883815c9`, indexed
  page dirs 0 dirty.

Detailed evidence:

- `docs/verification/phase-c-causal-anchor-guard-2026-07-29.md`;
- `docs/verification/phase-c-valuation-evidence-admission-2026-07-29.md`.

## Progress, without a misleading single percentage

| Layer | Status | Meaning |
|---|---|---|
| Runtime architecture and contracts | complete for candidate | same-Episode repair, dynamic/root budget, tool registry, cutoff, telemetry and evidence ledger are implemented |
| Fresh/causal/valuation deterministic seams | complete for fixed cases | all have tests plus pinned true-Hybrid replay |
| Changed-surface regression | green | 246/246 |
| Full local regression | baseline-limited | 2958 pass; 24 known environment failures |
| Live semantic evidence judge | provider ready; benchmark labels pending | direct non-financial `gpt-5.6-sol` probe succeeded; sidecar/benchmark semantic judgments are not yet collected |
| Budget-neutral representative evaluation | complete | corrected v2 A/B/C/D ran from clean `da614908`; D valid at 7 calls; wall-clock primary, call cap secondary |
| Acceptance measurement seam | complete | operational/truth/experience verdicts and hash-bound external observations are implemented |
| Knevo reference accounting | complete; labels pending | all 28 cases typed; 22 snapshots present, 6 missing; no uniform denominator |
| Wider 28-case acceptance / Knevo comparison | not ready | current Workbench run and independent semantic/blind labels remain incomplete |
| App Server ceiling design | v3 under independent review | second review found five P0/five P1; v3 now requires sealed no-gold export, same-fixture five-case D, closed capability radius, fixed projections, and claim ledger |
| Canonical rollout | not started | no main merge or 8792 switch authorized |

If one number is required, the isolated engineering candidate is roughly **90%**
complete, while end-to-end product release is roughly **70%** because comparative
evaluation and rollout are deliberately unstarted. Earlier 70–80% estimates mixed
these two denominators; this table is the canonical progress model going forward.

## Experiment decision

### Do not build App Server until v3 PASS and a same-fixture five-case control

The valid three-case D run diagnoses headless budget behavior but is not the App
Server control: it used live roots, covered only three cases, and did not freeze
the same published-answer projection. App Server could otherwise win from gold
leakage, a different information set, extra native tools, or projection choice.

App Server becomes justified only if a sealed, no-gold, same-PIT five-case
headless comparison still shows materially worse answer autonomy after all v3
isolation and lineage gates pass.

### Do not run 28 cases now

The three-case A/B/C/D diagnostic is complete. The smallest next quality
experiment is a five-case same-fixture profile-D control plus one App Server
ceiling run under the sealed v3 contract. Running 28 cases before that would
spend more provider budget without resolving the runtime decision.

### Do not claim a Knevo win rate

There is no complete same-format Knevo artifact set. Build matched artifacts and
score truth dimensions separately from experience dimensions before publishing
any percentage.

## Next executable gate

The next executable sequence is:

1. obtain an independent PASS on the v3 App Server design;
2. build the sealed instruction export and physical PIT fixture;
3. run a new five-case profile-D headless baseline on that exact view;
4. only then implement and run the bounded App Server ceiling adapter;
5. apply the common live evidence judge and blind published-answer comparison;
6. collect same-format Knevo outputs before any competitive claim.

This next gate is experimental/provider work, not unfinished deterministic code.

## Boundaries

- Do not merge `9053b0c4` without explicit cross-repo authorization.
- Do not merge this branch to `main` or switch 8792 without explicit approval.
- Do not treat 24 environment failures as newly introduced regressions.
- Do not persist API keys, access logs, indexes, model weights, venvs, databases,
  or generated evaluation secrets.
- Do not interpret `completed`, message count, or missing `passed` fields as a
  user-perceived pass rate.

## Shared-memory writeback

The project-level writeback was prepared but could not be appended to
`.agent-memory/20_projects/finance-workspace-private.md`: that path is a symlink
to `/Users/a77/agent-memory`, outside this task's writable sandbox. This handoff
is the canonical fallback record required by the writeback playbook. The one-line
memory summary to append later is:

```text
2026-07-29 · codex · Adaptive Runtime manifest freshness、周因果 query-only+
目标周/反证门、估值 subject-local admission 已在 true-Hybrid 固定重放闭合；
3-case 预算消融已完成；下一步先让 App Server v3 spec 过独立审查，再做
同一 sealed export/PIT 的 5-case D control；不合并 main/9053b0c4，
不切 8792，无同格式 Knevo artifact 前不报胜率。
```

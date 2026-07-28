# Adaptive Runtime Final Quality Handoff

Date: 2026-07-29
Status: **current engineering quality goal complete; broader product evaluation and canonical rollout remain separate gates**
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
| Live semantic evidence judge | externally blocked | no environment-configured provider; deterministic capture ordering passes |
| Budget-neutral representative evaluation | pending | preregistered three-case A/B/C/D ablation has not run |
| Wider 28-case acceptance / Knevo comparison | not ready | denominator and same-format opponent artifacts remain incomplete |
| Canonical rollout | not started | no main merge or 8792 switch authorized |

If one number is required, the isolated engineering candidate is roughly **90%**
complete, while end-to-end product release is roughly **70%** because comparative
evaluation and rollout are deliberately unstarted. Earlier 70–80% estimates mixed
these two denominators; this table is the canonical progress model going forward.

## Experiment decision

### Do not build App Server now

The last two true-Hybrid failures were repaired inside deterministic evidence
admission and delivery contracts. Changing runtime now would reintroduce the
confounding-variable problem: App Server could appear better merely because it
does not inherit the current headless time/call gates.

App Server becomes justified only if a budget-neutral headless comparison still
shows materially worse answer autonomy after the preregistered ablation.

### Do not run 28 cases now

The smallest next experiment is the already preregistered three-case A/B/C/D
budget ablation (`rebound-duration`, `weekly-market-cause`,
`ruihuatai-valuation`). It separates finalization floor, wall-clock, and call-cap
effects and records repeated-tool rate. Running 28 cases before that would spend
more provider budget without identifying the cause.

### Do not claim a Knevo win rate

There is no complete same-format Knevo artifact set. Build matched artifacts and
score truth dimensions separately from experience dimensions before publishing
any percentage.

## Next executable gate

When a provider is available without interactive Keychain prompts:

1. run the preregistered three-case A/B/C/D budget ablation, not 28 cases;
2. run the live evidence judge on the already admitted valuation candidates;
3. compare answer quality blind to status fields;
4. build an App Server ceiling adapter only if the budget-neutral headless result
   remains materially below interactive Codex;
5. collect same-format Knevo outputs before any competitive claim.

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
下一步先做 3-case 预算消融，再决定 App Server；不合并 main/9053b0c4，
不切 8792，无同格式 Knevo artifact 前不报胜率。
```

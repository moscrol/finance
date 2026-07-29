# Same-Fixture Five-Case Headless Retry 2 Preregistration

Date: 2026-07-29
Status: preregistered before retry-2 dry-run or live execution

## Why This Retry Is Allowed

Retry 1 was invalid at the runner-owned public projection boundary after the
model and product verifier returned. It did not produce four auditable arms and
did not physically exercise the profile-D validity observation in the sealed
artifact. Retry 2 tests only the numeric-lineage projection fix; it is not a
second sample selected after an answer-quality failure.

## Frozen Delta

- Invalid execution revision: `f4c0f541ec96ae69703f82d42187e5701d829e03`
- Retry executable baseline: `c732388053adf6dbd6f7e4dfb3858326527f2a5f`
- Allowed code delta: `scripts/run_agent_runtime_benchmark.py` plus its focused
  test file only
- Execution HEAD rule: a clean docs-only descendant containing this receipt

All other experiment inputs remain fixed:

- Questions: `bec6d6944ced127166bd41cb80a09a9f9fb0d816e45cee3be13a900bda2966fe`
- Fixture input: `2c5d5c75dc945f647e937dc2e29468ba9a471000ea679305442eb844be2810d2`
- Fixture manifest: `7f689bb57a36737070431d7f5bd4fa43a59a190070ebb0e3fc194ea1a5cd7b1c`
- Fixture pointer: `b6044583e3e421b4a3d9636845e7281de11266327f1f93e2e1b8074a3074affb`
- Finance DB: `ba68ed5d0590096c892f9c5537018bac148109988a6ee6d5cf0973be18a3df98`
- Wiki manifest: `dc111a1335be75e31124a527d40ad8e2c3e05b3aed077509c8e29e3c0c7e79ef`
- Hybrid manifest: `4f38ec58731daf1259b1c8d1c53aa4089b913df877c495fee0fdcb56ba794151`
- Tool surface: `4a72c427890f471fb1cebcd0edb426876d631a5f8f445961b68756ad033f9337`
- Environment policy: `80256fcc83def5860fa07e60ccdea9fe3d0943de7e845ef8bbe8a20e4ef45e3a`
- Provider identity: `9eeb1747acbddec586134c4439a3505e3c33d9fe7deace92c21b67002ed2a35f`
- Credential instance: `c09f5d619ebcb3cd06364fff1619ec391060572e87c667fe9f757e146cd2d8b7`
- Model/reasoning: `gpt-5.6-sol` / medium
- Profile: `d_long_expanded` = 180 seconds, 12 calls, 30-second synthesis
  reserve, zero gateway floor
- Case order: `rebound-duration`, `ruihuatai-valuation`,
  `weekly-market-cause`, `current-mainline`, `unfamiliar-methodology`

## Unique Outputs

- Dry-run: `/Users/a77/.finance-runtime/evals/headless-five-case-same-fixture-d-retry2-dry-run-2026-07-29.json`
- Live: `/Users/a77/.finance-runtime/evals/headless-five-case-same-fixture-d-retry2-2026-07-29.json`

Run exactly one dry-run and one live batch. Do not inspect per-case answers
between cases. A further retry is allowed only for a newly demonstrated shared
infrastructure/projection defect, with a new immutable receipt and unique path.

## Unchanged Validity Rules

The batch is operationally valid only if all frozen hashes match, all five cases
run once in order, the source tree is clean, no live/future/mutated/unauthorized
root is used, blind projections validate, and at least one case reaches seven
observed tool calls. Otherwise it is invalid rather than a quality failure.
`completed` alone is not a product pass; truth and experience remain separate
axes.

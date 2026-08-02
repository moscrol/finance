# Same-Fixture Five-Case Headless Retry 1 Preregistration

Date: 2026-07-29
Status: preregistered before retry dry-run or live execution

## Why A Retry Is Allowed

Attempt 1 was invalid before the research cases could be projected or the
profile-D call budget could be exercised. Retry 1 tests the shared evidence-ID
versus content-hash fix only. It is not a second sample selected after a quality
failure.

## Frozen Delta

- Previous execution revision: `b1b4ff4f1c670e35581b83b2b86e5584fad8e2cd`
- Retry executable baseline: `f4c0f541ec96ae69703f82d42187e5701d829e03`
- Allowed code delta: only the two projection/test files named in the attempt-1
  receipt
- Execution HEAD rule: clean docs-only descendant containing this retry
  preregistration and the attempt-1 receipt

All other preregistered inputs remain byte-identical:

- Questions: `bec6d6944ced127166bd41cb80a09a9f9fb0d816e45cee3be13a900bda2966fe`
- Fixture input: `b0edcbcc07b05ac04e8e1a80c21bea951e6115a79f7cbee19de03fb360aed03c`
- Fixture manifest: `1db1c2d6c21a3e463deba4372fdd122df1ee5b8be3e19a5f037ce219b230aa81`
- Fixture pointer file: `4ed8bc56c6a6df987a2d21b37aa1b7877a76507835da86eb95fa8ea5896becdc`
- Provider identity: `9eeb1747acbddec586134c4439a3505e3c33d9fe7deace92c21b67002ed2a35f`
- Credential instance: `c09f5d619ebcb3cd06364fff1619ec391060572e87c667fe9f757e146cd2d8b7`
- Tool surface: `4a72c427890f471fb1cebcd0edb426876d631a5f8f445961b68756ad033f9337`
- Environment policy: `80256fcc83def5860fa07e60ccdea9fe3d0943de7e845ef8bbe8a20e4ef45e3a`
- Model/reasoning: `gpt-5.6-sol` / medium
- Profile: `d_long_expanded` = 180 seconds, 12 calls, 30-second synthesis reserve, zero gateway floor
- Case order: `rebound-duration`, `ruihuatai-valuation`, `weekly-market-cause`, `current-mainline`, `unfamiliar-methodology`

## Retry Outputs

- Dry-run: `/Users/a77/.finance-runtime/evals/headless-five-case-same-fixture-d-retry1-dry-run-2026-07-29.json`
- Live: `/Users/a77/.finance-runtime/evals/headless-five-case-same-fixture-d-retry1-2026-07-29.json`

Run one dry-run and one live batch. Do not inspect answers between cases.

## Unchanged Validity Rules

Retry 1 is operationally valid only if source and all frozen hashes match, five
cases run once in order, no external/live/future/mutated/unauthorized action is
observed, all blind projection hashes validate, and at least one case reaches
seven observed tool calls. Otherwise it remains invalid rather than becoming a
quality failure. `completed` alone is not a product pass.

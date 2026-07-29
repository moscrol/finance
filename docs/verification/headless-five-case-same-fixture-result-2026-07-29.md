# Same-Fixture Five-Case Headless Result

Date: 2026-07-29
Status: attempt 1 invalid; retry 1 preregistered

## Attempt 1

- Source revision: `b1b4ff4f1c670e35581b83b2b86e5584fad8e2cd`
- Artifact SHA-256: `f75c47e2c1708cc9e1133939474e489416e06bb1e113d5c1e2ab74f1351e1b57`
- Fixture manifest: `1db1c2d6c21a3e463deba4372fdd122df1ee5b8be3e19a5f037ce219b230aa81`
- Provider identity: `9eeb1747acbddec586134c4439a3505e3c33d9fe7deace92c21b67002ed2a35f`
- Batch/process exit: completed and artifact written
- Benchmark gate: failed
- Budget validity: `invalid_not_physically_exercised`
- Maximum observed tool calls: 0, below the preregistered minimum of 7

Four research cases failed at the same shared projection boundary with:

```text
ValueError:runtime source content_hash must be lowercase SHA-256
```

`unfamiliar-methodology`, the only zero-tool case, completed. This does not make
the batch 1/5: the four research cases did not receive a quality verdict, and
the profile-D budget was never physically exercised.

## Root Cause And Bounded Fix

Upstream `AgentEvidence.content_hash` is an evidence identity and is not always
a 64-character SHA-256. The public `RuntimeSource.content_hash` contract is a
content-integrity SHA-256. Attempt 1 passed the first value directly into the
second contract, conflating two identities.

Commit `f4c0f541ec96ae69703f82d42187e5701d829e03` keeps the original evidence ID
for binding and deduplication, while deriving a canonical SHA-256 from the
evidence ID plus tool, title, detail, source, source date, and evidence tier for
the public source projection. It does not pad the old ID or relax the SHA-256
validator.

The fix changes only:

- `scripts/run_agent_runtime_benchmark.py`
- `intelligence/tests/test_run_agent_runtime_benchmark.py`

Regression: `56 passed, 1 skipped`; Ruff and `git diff --check` passed. No
question, case contract, tool route, budget, fixture, provider, verifier, or
acceptance rule changed after observing attempt 1.

## Interpretation Boundary

Attempt 1 is retained as an infrastructure/protocol failure receipt. Its answer
text is not scored, does not enter the 28-case board, and cannot support a
headless-versus-App-Server conclusion. Retry 1 is a new preregistered experiment
with a unique artifact path.

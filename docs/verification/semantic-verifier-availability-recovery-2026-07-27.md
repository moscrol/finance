# Semantic verifier availability recovery

Date: 2026-07-27  
Branch: `feat/agent-runtime-backends-verify`  
Scope: one shared semantic-verifier projection seam; no route, skill,
template, evaluator threshold, or global budget change.

## Failure reproduced

Run `run_20260727_225549_654677` had:

- structural status `completed`;
- 14 unique evidence atoms and five output bindings;
- semantic status `unavailable` with issue `semantic judge deadline exhausted`;
- a private outcome containing a direct, evidence-bounded draft.

`SemanticEpisodeVerifier.verify()` nevertheless replaced that draft with
`_gap_answer()`. The public result therefore said evidence was missing even
though the missing fact was verifier availability, not research coverage.

## Contract change

When the first semantic judge call is classified as a release-safe transient
provider failure or deadline exhaustion, `_transient_failure_candidate()` may
project the structurally trusted draft with a visible warning. It remains:

- `status=partial` and `judge_status=unavailable`;
- a degraded adapter result, never `completed`;
- limited to a structurally completed result or an explicit evidence-gap
  partial that already has at least one fulfilled output;
- sanitized through the same public projection used by a passed judge;
- accompanied by `结构化证据绑定已通过边界校验，但语义核验因瞬时服务问题未完成`.

Authentication/configuration errors, malformed judge output, contract/hash
failures, and other non-transient failures still use the generic fail-closed
gap. The verifier is not bypassed; the unavailable state is made explicit.

## Verification

- Red/green regression:
  `test_transient_semantic_judge_failure_preserves_structural_candidate`.
- Semantic verifier + adapter: `200 passed`.
- Clean full intelligence suite: `2930 passed, 2 skipped`.
- Ruff and `git diff --check`: passed.
- No live five-case rerun, no 8792 switch, and no `main` merge.

This is a shared seam fix. It improves truthful degradation for any long-tail
task whose evidence is structurally complete; it does not add a market-cause
special case.

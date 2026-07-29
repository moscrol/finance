# Sealed Post-Cutoff Result Corpus Verification

Date: 2026-07-29
Status: frozen evaluator input

## Purpose

The first real sealed-instruction diagnostic treated every sentence in six
engineering handoffs as a `post_cutoff_result`. That produced 179 deterministic
findings, all in the post-cutoff class, even though most matching sentences were
generic implementation descriptions rather than future benchmark outcomes.

The replacement evaluator input is:

```text
intelligence/eval/cases/ceiling_post_cutoff_results_2026-07-29.txt
SHA-256 61cf49280fae1fd57aea895a872b23207d277506bc37bf233bc2f9894fdf5218
```

It contains only eight verified post-cutoff result statements. Historical
candidate and published answers remain independently covered by the eight full
headless artifacts passed through `--prior-artifact`; this file does not replace
or summarize those artifacts.

## Source provenance

The result statements were distilled from these immutable local sources:

```text
c481313bef9f1596e8f86bd90744e94c25435bb276fcc89f1d996bb5040ce6bf  docs/handoffs/2026-07-28-adaptive-finance-runtime-canonical-handoff.md
e2a37f077b03953bcaba107a8d14fe11d7678cd27bb009b982fcf39ddd493999  docs/handoffs/2026-07-28-codex-execution-brief.md
79286ed1485139f5e4d2e7a7dd0a2a2c3161738100e4ccb0ece54253a8841075  docs/handoffs/2026-07-29-adaptive-runtime-final-quality-handoff.md
05528864f82d8aaad1a5e92969e13994dcc4eb863841f1a614653fd3f15d20bb  docs/handoffs/2026-07-29-codex-execution-brief-leak-rule.md
0844d5fa8b94915870b6700ee8e2a2bc2bfd7a9cfc6118e1cd9435fd3e722678  docs/verification/headless-budget-ablation-v2-results-2026-07-29.md
161287e7721b25d939d56a5ef24d30b1268c342339d92296ef1c5db19a02d575  docs/verification/phase-c-retrieval-contract-2026-07-29.md
```

## Boundary

- `question`, `reference_answer`, `required_output`, `direct_target`,
  `prior_answer`, and the eight distilled `post_cutoff_result` statements remain
  fail-closed.
- No post-cutoff exception was added.
- No deterministic threshold was changed.
- The change narrows source classification, not matching strictness: ordinary
  engineering prose is no longer mislabeled as benchmark result prose.
- If this corrected corpus still rejects the export, the surviving finding is
  reported and not routed around.

The full first diagnostic remains private at:

```text
/Users/a77/.finance-runtime/app-server-ceiling/2026-07-24/ef790e0b1ab4a492-leak-diagnostic.json
diagnostic SHA-256 6ee477b61db644bec2c9c490652ebcfdf299a39f610a5f402c644cc539b82926
```

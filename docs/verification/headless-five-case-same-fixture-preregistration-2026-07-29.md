# Same-Fixture Five-Case Headless Preregistration

Date: 2026-07-29
Status: preregistered before dry-run or live execution

## Frozen Inputs

- Executable code baseline: `595618bb896cb6b662bc1d63dccf081b38cb3bbe`
- Execution HEAD rule: clean descendant of the baseline containing only this
  docs-only preregistration/fixture receipt commit before execution
- Questions SHA-256: `bec6d6944ced127166bd41cb80a09a9f9fb0d816e45cee3be13a900bda2966fe`
- Fixture input: `b0edcbcc07b05ac04e8e1a80c21bea951e6115a79f7cbee19de03fb360aed03c`
- Fixture manifest: `1db1c2d6c21a3e463deba4372fdd122df1ee5b8be3e19a5f037ce219b230aa81`
- Fixture pointer file SHA-256: `4ed8bc56c6a6df987a2d21b37aa1b7877a76507835da86eb95fa8ea5896becdc`
- Cutoff: 2026-07-24
- Tool surface: `4a72c427890f471fb1cebcd0edb426876d631a5f8f445961b68756ad033f9337`

The five authorized tool lists, in order, are:

1. `rebound-duration`: `market_data`, `mainline_context`, `finance_query`, `evidence_search`
2. `ruihuatai-valuation`: `kb_search`, `evidence_lookup`, `market_data`, `financial_data`, `finance_query`, `evidence_search`
3. `weekly-market-cause`: `market_data`, `finance_query`, `evidence_search`
4. `current-mainline`: `market_data`, `mainline_context`, `finance_query`, `evidence_search`
5. `unfamiliar-methodology`: no tools

## Runtime Contract

- Backend: `codex_headless`
- Model: `gpt-5.6-sol`
- Reasoning: medium
- Transport: subprocess plus private mailbox
- Profile: `d_long_expanded`
- Total wall clock per case: 180 seconds
- Maximum tool calls per case: 12
- Synthesis reserve: 30 seconds
- Gateway floor ratio: 0
- External network/search/valuation/financial providers: disabled
- Live finance/Wiki roots: forbidden
- Instruction copy mutation: invalidates the case

Provider access is an explicit projection from the configured provider file;
Codex runs with `--ignore-user-config`. Only provider identity is imported. Tool
children do not inherit the bearer token. Frozen provider identity:

- Base URL: `https://x.ailzd.com/v1`
- Wire API: `responses`
- Model: `gpt-5.6-sol`
- Provider identity: `9eeb1747acbddec586134c4439a3505e3c33d9fe7deace92c21b67002ed2a35f`
- Credential instance: `c09f5d619ebcb3cd06364fff1619ec391060572e87c667fe9f757e146cd2d8b7`

No credential value may enter Git, command-child environment, logs, or result
artifacts.

## Execution

Run exactly one dry-run for contract/provenance inspection, then one live batch
containing all five cases in the frozen order. Do not inspect answers between
cases.

- Dry-run output: `/Users/a77/.finance-runtime/evals/headless-five-case-same-fixture-d-dry-run-2026-07-29.json`
- Live output: `/Users/a77/.finance-runtime/evals/headless-five-case-same-fixture-d-2026-07-29.json`

Each arm must bind `published_answer`, `claims`, and `sources` into a blind
projection with a JSON pointer and SHA-256.

## Validity And Reporting

The batch is operationally valid only if all of the following hold:

- source tree is clean and differs from the executable baseline only by the
  preregistration/fixture receipt docs;
- pointer, fixture, question, provider, environment-policy, and tool-surface
  hashes match this preregistration;
- all five cases run exactly once, in order, on `gpt-5.6-sol`;
- no external tool, live root, future-dated evidence, instruction mutation, or
  unauthorized shell command is observed;
- every blind projection hash validates;
- at least one case reaches seven observed tool calls.

If the final condition is not exercised, the profile-D experiment is invalid,
not a quality failure. A `completed` transport or research status is not a
product pass. Answer quality must be judged later from truth and experience
dimensions without changing these rules.

# SDK-GPT E2E Frontier Handoff

Date: 2026-07-27
Status: active; not release-green

## Scope and safety

- Worktree: `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667`
- Branch: `feat/agent-runtime-backends-verify`
- Verified state through: `c85d7c2e docs: record causal runtime seam verification`
- Resolve the current branch HEAD with `git rev-parse HEAD`; handoff-only
  documentation commits do not change the verified product state below.
- Product-code tip: `ed2e1d89 fix: unify SDK delivery repair admission`
- Working tree: clean
- `main` and canonical `8792`: untouched
- Do not run the tracked nine-case development suite as a debugging loop.
- Next live action is exactly one `weekly-market-cause` causal canary. The
  frozen suite remains a later release gate, not a debugging loop.

## What is complete

### Causal canary root-seam repair

Commits `86c9d483`, `1b7d4bdb`, and `ed2e1d89` close the failure observed in
`run_20260727_213048_327023` without adding a route, skill, or answer template:

- only evidence hashes new to the Episode are returned to the model;
- duplicate provider content is an explicit `duplicate_evidence` observation;
- repair admission is counted even when a repair times out;
- invalid finish, timeout delivery, structural gaps, and semantic gaps now use
  one Adapter-owned `RepairGoal` pool;
- tool-closed delivery is zero-call, at most 30 seconds, and admitted once;
- deep tool-enabled repair may still continue when its ledger shows real new
  coverage;
- default GPT delivery uses low reasoning, while explicit caller settings are
  preserved.

Verification receipt:
`docs/verification/sdk-gpt-causal-seam-hardening-2026-07-27.md`.

### Provider Schema seam

The `sdk_gpt → OpenAI Agents FunctionTool` boundary now has a provider-only
projection in `intelligence/services/openai_agents_runtime.py`:

- recursively removes `uniqueItems` for `sdk_gpt` only;
- turns description-only scalar nodes into `type: string` for the narrow gateway
  schema subset;
- leaves the provider-neutral registry and `FinanceQuery` validation unchanged;
- keeps `sdk_glm` behavior unchanged.

Commits: `875ed509`, `17e0b21a`.

### Tool-loop and query guidance slice

`07fc62a7` adds two bounded improvements:

- `sdk_gpt` instructions explicitly require at most one tool call per model
  response, so the next decision can observe the previous tool result;
- `finance_query` exposes dataset-specific semantic field hints and includes a
  retry hint after an invalid field error.

This is not yet loaded by the running 8799 process.

### Cross-dataset query repair

`04849c78` incorporates the independent Claude acceptance finding that several
real semantic fields were rejected only because the model placed them on the
wrong dataset:

- invalid-query observations now map every misplaced field to its registered
  `dataset.role` instead of listing only the already-wrong dataset;
- a query spanning datasets is explicitly split into sequential queries, which
  composes with the single-tool-per-turn boundary above;
- a date incorrectly placed in `filters` is redirected to
  `time_range.start/time_range.end`;
- focused FinanceQuery/episode/SDK coverage is `50 passed, 1 skipped`.

This is not yet loaded by the running 8799 process.

### Provider-enforced single-tool turns

`afc0be6e` closes the gateway behavior gap that prompt instructions and
`parallel_tool_calls=False` could not enforce:

- only the first function call from each `sdk_gpt` model response reaches the
  OpenAI Agents SDK tool executor;
- later calls in the same provider response are dropped before execution, so
  the next model turn must observe the first raw tool result before deciding;
- the projection is provider-local and leaves `sdk_glm` batch behavior intact;
- `batched_tool_calls_dropped` is preserved in the SDK result and runtime event
  for private diagnosis instead of being silently hidden.

The red-capable SDK integration test reproduced the real failure pattern with
two calls in one model response: before the fix both executed; after the fix
only the first executes and exactly one tool observation enters the next model
turn. This is not yet loaded by the running 8799 process.

### Keychain prompt protection

`b18eee60` adds a per-process negative cache in
`intelligence/services/llm_settings.py`: a failed or missing Keychain load is
not retried on every `/api/llm/config` read. Explicit session configuration
still overrides the failed load.

This is not yet loaded by the running 8799 process.

### Deterministic verification

- Latest focused runtime slice: `83 passed, 1 skipped`.
- Clean full backend suite: `2919 passed, 2 skipped`.
- Ruff and `git diff --check` pass for the latest slice.

## Current 8799 runtime

8799 now serves the repaired candidate with a session-only provider:

```text
live revision: 4550ce5d
product-code tip: ed2e1d89
backend: sdk_gpt
provider: configured in process memory
ready: true
session_only: true
credential_persisted: false
finance_root: /Users/a77/finance-workspace-private
market_snapshot: true
```

The repaired code, correct finance root, market snapshot, and provider are all
active. Persistence remains off; a restart will clear the credential. Never
print or copy it.

## Live evidence

### Passed: current mainline

Run: `run_20260727_104513_771561`

- `business_status/research_status/answer_status = complete`
- `sdk_gpt`, 3 LLM calls, 2 tool calls, 15 evidence atoms
- duplicate queries: 0; invalid actions: 0; warnings: none
- direct answer identified semiconductor as the current mainline, separated AI
  computing as a diverging secondary direction, and supplied dated evidence,
  continuation signals, invalidation conditions, and market risk.

### Passed: weekly market cause after shared-seam repair

Run: `run_20260727_223000_947509`

Conversation: `conv_0da5b95bce964e09ab6fe455817dfd21`

- UI and Conversation message status: completed;
- answer corrected the premise (`+0.47%` for the week; `-1.61%` on 07-24)
  before explaining the actual down day;
- fourteen evidence atoms, fourteen unique hashes, all dated `2026-07-24`;
- five required outputs all bound;
- two LLM calls, four tool calls, one bounded invalid action;
- one `duplicate_evidence` observation was not reintroduced as fresh evidence;
- `repair_attempts=1`, `repair_cycles=1`, semantic status `repaired`;
- news cutoff filtering rejected future candidates and no future evidence
  entered the final ledger.

This closes the targeted causal frontier. Full receipt:
`docs/verification/sdk-gpt-causal-seam-hardening-2026-07-27.md`.

### Historical failed weekly-market-cause run

Run: `run_20260727_104727_609711`

- `business/research/answer_status = partial`
- `sdk_timeout`; 1 LLM request, 6 tool calls, 1 invalid action
- duplicate queries: 0
- three `finance_query` calls mixed fields from incompatible datasets;
  the model did not observe each error before emitting the next call;
- final answer correctly fail-closed to an evidence-gap response, but did not
  answer the causal question.

This was the key SDK runtime seam. It is superseded by the green 8799 run above
and must not be used as the current quality verdict.

### Earlier transport failures

Run: `run_20260727_101922_456622` failed before any tool call because the
gateway rejected `uniqueItems` and then a description-only scalar schema. Those
two failures motivated `875ed509` and `17e0b21a`; do not use this run as a
quality result for the current code.

## Unfinished work

1. Keep 8799 running while the current session credential is needed; restart
   only when loading a newer revision.
2. If the release process continues, freeze the current revision and run the
   representative suite once. Do not use it as a debugging loop.
3. Run the independent review gate against that frozen revision and artifact.
4. Solve Keychain fresh-process reuse separately. The negative cache only stops
   repeated prompts; it does not make a blocked ACL readable.
5. No merge to `main`, no 8792 cutover, and no release-green claim until the
   frozen frontier and review gate pass.

## Useful checks

```bash
git status --short && git branch --show-current
curl -fsS http://127.0.0.1:8799/api/health
curl -fsS http://127.0.0.1:8799/api/llm/config
```

The last two responses must be inspected only through redacted fields. Never
read, print, or place the model credential in a command, log, artifact, or Git
file.

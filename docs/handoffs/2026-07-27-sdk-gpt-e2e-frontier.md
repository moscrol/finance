# SDK-GPT E2E Frontier Handoff

Date: 2026-07-27
Status: active; not release-green

## Scope and safety

- Worktree: `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667`
- Branch: `feat/agent-runtime-backends-verify`
- HEAD: `07fc62a7 fix: keep sdk tool turns observable`
- Working tree: clean
- `main` and canonical `8792`: untouched
- Do not run the tracked nine-case development suite as a debugging loop.
- Next live order is: `current-mainline` → `weekly-market-cause` → frozen five.

## What is complete

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

### Keychain prompt protection

`b18eee60` adds a per-process negative cache in
`intelligence/services/llm_settings.py`: a failed or missing Keychain load is
not retried on every `/api/llm/config` read. Explicit session configuration
still overrides the failed load.

This is not yet loaded by the running 8799 process.

### Deterministic verification

- Latest focused slice: `69 passed, 1 skipped`.
- Earlier full backend suite: `2869 passed, 2 skipped`; 11 failures are the
  pre-existing `subconscious/userspace` machine-path baseline failures.
- Ruff and `git diff --check` pass for the latest slice.

## Current 8799 runtime

8799 is intentionally left running without a restart so the current session
credential is not lost:

```text
live revision: 17e0b21a
backend: sdk_gpt
provider: openai / gpt-5.6-sol
ready: true
session_only: true
credential_persisted: false
finance_root: /Users/a77/finance-workspace-private
market_snapshot: true
```

The latest commits (`b18eee60`, `07fc62a7`) require a restart before they can
be tested in 8799. Do not restart casually: the fresh process still cannot
reliably reload the saved Keychain item and the user may need to configure a
session credential again. Never print or copy the credential.

## Live evidence

### Passed: current mainline

Run: `run_20260727_104513_771561`

- `business_status/research_status/answer_status = complete`
- `sdk_gpt`, 3 LLM calls, 2 tool calls, 15 evidence atoms
- duplicate queries: 0; invalid actions: 0; warnings: none
- direct answer identified semiconductor as the current mainline, separated AI
  computing as a diverging secondary direction, and supplied dated evidence,
  continuation signals, invalidation conditions, and market risk.

### Failed release frontier: weekly market cause

Run: `run_20260727_104727_609711`

- `business/research/answer_status = partial`
- `sdk_timeout`; 1 LLM request, 6 tool calls, 1 invalid action
- duplicate queries: 0
- three `finance_query` calls mixed fields from incompatible datasets;
  the model did not observe each error before emitting the next call;
- final answer correctly fail-closed to an evidence-gap response, but did not
  answer the causal question.

This is the key remaining SDK runtime seam: `parallel_tool_calls=False` did not
produce the desired single-observation loop at the current gateway. The latest
instruction guard and field hints are intended to test this, not yet proven.

### Earlier transport failures

Run: `run_20260727_101922_456622` failed before any tool call because the
gateway rejected `uniqueItems` and then a description-only scalar schema. Those
two failures motivated `875ed509` and `17e0b21a`; do not use this run as a
quality result for the current code.

## Unfinished work

1. Restart 8799 on `07fc62a7`; first check health and redacted LLM readiness.
2. Verify the current session/provider setup without exposing credentials.
3. Re-run the two directed Conversation cases, one at a time.
4. If weekly-cause still emits multiple calls in one response, test the
   Responses-vs-Chat-Completions adapter seam or implement a bounded host-side
   one-tool turn loop. Do not silently raise the budget.
5. Solve Keychain fresh-process reuse separately. The negative cache only stops
   repeated prompts; it does not make a blocked ACL readable.
6. Only after both directed cases pass or return an honest, evidence-grounded
   partial should the frozen five-case release frontier run.
7. No merge to `main`, no 8792 cutover, and no release-green claim until the
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

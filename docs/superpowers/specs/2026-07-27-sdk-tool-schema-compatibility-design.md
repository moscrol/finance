# SDK Tool Schema Compatibility Design

Date: 2026-07-27

Status: approved (option A)

## Problem

The 8799 Conversation path reaches the `sdk_gpt` continuous Episode with the
correct TaskFrame and session provider, but the first upstream call fails before
any finance tool can run:

```text
Invalid schema for function 'finance_query':
('properties', 'metrics'), 'uniqueItems' is not permitted
```

`FinanceQuery` intentionally uses `uniqueItems` as a provider-neutral domain
hint. The OpenAI-compatible gateway used by the current GPT candidate accepts a
smaller function-tool JSON Schema subset. Provider compatibility must not force
the domain contract or the local argument validator to become weaker.

## Decision

Normalize tool schemas at the OpenAI Agents SDK boundary for `sdk_gpt` only.
The adapter recursively removes the unsupported annotation keyword
`uniqueItems` before constructing `FunctionTool`. It does not mutate the
registry-owned `ToolSpec`, change tool arguments, or alter the runtime's local
validation and execution policy.

The data flow becomes:

```text
ResearchToolRegistry ToolSpec (provider-neutral, immutable)
  -> AgentsSdkTool detached copy
  -> sdk_gpt compatibility projection (drop uniqueItems recursively)
  -> FunctionTool.params_json_schema
  -> provider

Model tool arguments
  -> ResearchToolRegistry.prepare_arguments
  -> existing semantic validation / normalization
  -> read-only tool execution
```

## Alternatives rejected

1. Change `FinanceQuery` itself to remove uniqueness semantics. This couples a
   domain contract to one provider and affects Continuous, GLM, headless, and
   deterministic tests.
2. Build a broad JSON Schema allowlist now. That is more future-proof but has a
   larger semantic-loss surface than the one observed incompatibility warrants.
3. Disable `finance_query` for GPT. This would make the candidate pass transport
   checks while removing a mandatory long-tail capability.

## Invariants

- Only `sdk_gpt` receives the compatibility projection; `sdk_glm` behavior is
  unchanged.
- The input mapping is detached and remains byte-for-byte unchanged.
- Only the key `uniqueItems` is removed, at any nesting depth.
- Local tool argument validation remains authoritative.
- No route, budget, verifier, evidence, or answer contract is relaxed.
- Provider failure remains fail-closed and visible.

## Verification

1. Unit regression proves nested `uniqueItems` is removed for `sdk_gpt`, is
   retained for `sdk_glm`, and the source schema is not mutated.
2. Existing SDK/runtime and FinanceQuery suites remain green.
3. The 8799 Conversation E2E no longer stops with
   `sdk_upstream_unavailable`; at least one real tool call occurs.
4. `current-mainline` must return a dated direct judgment, supporting evidence,
   and risk/validation conditions.
5. Only after that passes, run `weekly-market-cause`, then the frozen five-case
   release set.

## Non-goals

- No generic route additions.
- No legacy-pipeline rewrite in this slice.
- No canonical 8792 switch or `main` merge.
- No extraction, logging, or copying of the provider credential.

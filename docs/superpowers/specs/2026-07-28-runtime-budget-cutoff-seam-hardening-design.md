# Runtime Budget and Cutoff Seam Hardening Design

Date: 2026-07-28
Status: approved by the user's instruction to execute the diagnosed optimization
Implementation branch: `feat/agent-runtime-backends-verify`

## Problem

The frozen five-case SDK-GPT benchmark at revision `69f9cf17` completed all
arms but passed only one. The methodology case completed without tools, while
all four finance cases exhausted a 30-second research ledger. The finance
failures share three seams rather than four question-specific routes:

1. SDK runtimes inherit GLM's internal-finalizer reserve even though SDK model
   turns already research and draft in one episode.
2. `ResearchRunContext.information_cutoff` is enforced by code but omitted from
   the immutable model input.
3. structured providers select their newest row and rely on a later
   `future_of_cutoff` filter instead of selecting the newest row at or before
   the cutoff.

A fourth issue lets the model authorize its own old `time_range` for a current
task. A fifth operational issue reads Keychain through a subprocess with a
three-second timeout, shorter than normal macOS authorization interaction.

## Selected design

### Backend-owned reserve policy

The composition root chooses the reserve policy once:

- `continuous_glm` keeps `GLMAgentRuntime.synthesis_reserve_for_task` because
  it has a distinct GLM finalizer inside the runtime;
- `sdk_gpt`, `sdk_glm`, and `codex_headless` reserve 30 seconds for the shared
  semantic verifier and give the remaining standard budget to the continuous
  research episode;
- the API Adapter passes an explicit zero inner reserve to non-GLM runtimes;
  its outer verifier reserve remains the only production semantic reserve.

This is not a global timeout increase. The tier hard cap remains unchanged.

### One immutable cutoff in model and tools

`build_episode_input()` serializes `information_cutoff` alongside `today` and
`latest_data_date`. Its rule states that no requested or cited fact may exceed
that cutoff.

Structured block builders accept an optional `as_of` and select:

```text
MAX(trade_date) WHERE trade_date <= as_of
```

The selected provider date is carried into evidence and traces. A later filter
remains defense in depth, not the primary historical-selection mechanism.

Valuation snapshots newer than the cutoff are not relabeled. The provider
falls back to the local price and market-cap anchor at or before the cutoff and
reports PE/PB as missing when historical multiples are unavailable. When the
known live-snapshot date is newer than the cutoff, the realtime request is
skipped rather than spending tool budget on evidence that must be discarded.

### User-owned historical authorization

The user task, not a model-generated `FinanceQuerySpec`, authorizes a historical
window. Explicit dated/historical tasks may query below the current freshness
floor. A current task that asks for a far older range receives a rejected tool
result with a retry instruction to query near the cutoff.

### Native Keychain read

`MacOSKeychainBackend.load()` uses `SecItemCopyMatching` and copies the returned
`CFData` bytes through CoreFoundation. It never places secrets in argv, has no
arbitrary three-second timeout, releases every native reference, and preserves
the current sanitized error contract.

## Interfaces and seams

- Benchmark reserve seam: `_fresh_context(case, control, backend, ...)`.
- Production reserve seam: the API composition root constructing
  `ContinuousTurnAdapter`.
- Model contract seam: `build_episode_input(frame, context)`.
- Structured as-of seam: optional `as_of` on market, mainline, and valuation
  block builders, consumed by `build_episode_registry`.
- Historical authorization seam: `TaskFrame` plus the immutable cutoff;
  `FinanceQuery` remains a general historical engine.
- Secret storage seam: `KeychainBackend.load(service, account)`.

## Error handling

- Missing data at or before cutoff returns an explicit gap, never a newer row.
- Unsupported model-selected history on a current task is rejected before the
  database query so the episode can retry without spending a useless call.
- Native Keychain item-not-found returns `None`; all other native errors remain
  sanitized and never include payload bytes.

## Acceptance

1. A standard SDK benchmark context has a 30-second verifier reserve and more
   than 59 seconds of research time; continuous GLM retains its existing
   reserve.
2. Episode input contains the exact immutable cutoff.
3. With both 2026-07-24 and 2026-07-27 rows, a frozen 2026-07-24 episode serves
   and cites 2026-07-24 market and mainline data.
4. A future valuation snapshot is not published in the frozen episode; the
   local 2026-07-24 market-cap anchor is used when available.
5. A current task cannot choose a 2025 window; an explicitly historical user
   task still can.
6. Keychain load does not call `/usr/bin/security` or depend on a three-second
   subprocess timeout.
7. Deterministic replay and focused/full regression suites pass before one new
   live five-case benchmark is allowed.

## Rejected approaches

1. Increase every timeout: preserves the duplicate reserve and raises latency.
2. Keep latest-row providers and retry after `future_of_cutoff`: wastes calls
   and makes correctness depend on the model noticing a code-owned constraint.
3. Trust any model-supplied historical range: lets the model redefine the user
   task and mislabel old evidence as current.
4. Relabel a newer valuation snapshot with the cutoff date: violates source
   provenance and the fail-closed contract.

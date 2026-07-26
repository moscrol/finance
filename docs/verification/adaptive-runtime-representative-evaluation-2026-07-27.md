# Adaptive Runtime Representative Evaluation

Date: 2026-07-27

Status: `quality_not_green_external_runtime_jitter`

## Frozen release candidate

| Field | Value |
| --- | --- |
| Source revision (live artifact) | `e179b15cda...` |
| Current branch tip | `d686bb9e` |
| Source dirty | `false` |
| Branch | `feat/agent-runtime-backends-verify` |
| Canonical 8792 | untouched |
| `main` | not merged |
| Market data date | `2026-07-24` |

The local dry-run artifact is:

```text
/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27-dry-run.json
```

It records the exact source revision, five planned cases, the explicit
`sdk_gpt` backend, and zero acceptance-contract gaps.

## Representative input

The ignored local five-case file projects existing frozen questions without
changing their cutoff, tier, timeout, or required outputs:

1. `rebound-duration` — current-market prediction;
2. `ruihuatai-valuation` — company valuation;
3. `weekly-market-cause` — causal attribution;
4. `current-mainline` — current-market judgment;
5. `unfamiliar-methodology` — non-skill methodology long tail.

All five compile to research tasks. The unfamiliar methodology case uses the
general-finance research path rather than a fabricated skill route.

## Deterministic verification

Provider tolerance and benchmark contracts:

```text
64 passed, 1 skipped (focused current-tip suite)
```

Credential, runtime-benchmark, and Workbench API regression after the bounded
Keychain read fix plus fail-closed benchmark/provider wiring:

```text
2868 passed, 2 skipped, 11 baseline failures (full intelligence/tests)
Ruff passed
git diff --check passed
```

The benchmark summary gate now treats any arm with `status=failed` (including
`model_unavailable`) as a failed release result. The saved session provider is
also injected into Continuous/SDK arms and their semantic verifier; it is not
read from a global environment variable.

The existing release-candidate evidence remains valid for the same branch
history:

- focused Episode/runtime suite: 282 passed;
- core independent-review invariants: 70 passed;
- Workbench API: 87 passed;
- frontend: 65 Vitest tests, ESLint, TypeScript, and Vite build passed;
- isolated progress/UI smoke: public progress precedes the answer, reconnect
  replays progress, one terminal Run is emitted, and control-plane leakage is
  zero.

## Live evaluation result

The Keychain preflight blocker was fixed by isolating the official `security`
command behind a hard timeout. The frozen five-case suite then executed through
the Codex headless provider. The latest live artifact is:

```text
/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-headless-2026-07-27-e179b15c.json
```

The source was clean and per-tool ProviderTrace, cutoff, token, root-budget and
repair diagnostics were exported. Standard cases used medium reasoning, a
60-second research window, a 30-second semantic-verifier reserve, and a dynamic
finalization floor. Two of five cases still hit the headless process boundary
(`rebound-duration` and `weekly-market-cause`); the other three reached
structured/semantic acceptance or an honest partial. Separate targeted smokes
for current-mainline and weekly-cause passed with direct, evidence-bounded
answers. The remaining variance is provider/runtime tail latency, not a route or
evidence-seam failure.

The current candidate was additionally booted on isolated port 8799 at
`d686bb9e`: health reported a clean revision and distinct code/data roots, and
the deterministic 科创50 technical-level request completed with a dated,
numeric, invalidation-bounded answer. The long-tail provider lane was not
claimed green because the fresh process could not access the persisted Keychain
record without macOS authorization; no secret was copied or printed.

## Claude `ALIGNMENT.md` reconciliation

The supplemental review does not change the approved runtime ownership model.
Its product-relevant additions are already represented in the candidate:

- same-Episode verifier repair consumes explicit `missing_outputs` from a
  structural partial;
- per-tool ProviderTrace, cutoff rejection, token usage, and repair provenance
  are exported to the private benchmark diagnostics;
- safe progress is projected separately to public SSE, so TaskFrame, queries,
  providers, prompts, raw model messages, and private evidence payloads do not
  enter the display plane;
- deep budget, branch facade, MemoryGate, immutable task floor, and root-ledger
  identity invariants are covered by permanent tests;
- review-harness development remains frozen.

The one additional release-evidence gap found in this slice was benchmark
provenance. The runner now records `source_revision` and `source_dirty`, so a
future live result cannot be detached from the code that produced it.

## Release conclusion

Result: `not_release_green`.

The architecture and deterministic gates are in place, and the headless
reference now preserves structured-tool freedom, root-budget accounting,
cutoff/traces, and grounded semantic verification. However, the representative
five-case live run is not fully green under the current provider's tail latency.
Do not switch 8792, merge `main`, or claim Codex/Knevo parity. The next release
action is a provider-stability/latency decision (or a fresh clean-provider
five-case run), not another route or prompt layer.

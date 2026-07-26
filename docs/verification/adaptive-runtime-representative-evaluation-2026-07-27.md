# Adaptive Runtime Representative Evaluation

Date: 2026-07-27

Status: `blocked_by_external_runtime`

## Frozen release candidate

| Field | Value |
| --- | --- |
| Source revision | `bffdc537425f406b3c12831ba9ec7b5ca800322d` |
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
77 passed
```

Credential, runtime-benchmark, and Workbench API regression after the bounded
Keychain read fix:

```text
125 passed
Ruff passed
git diff --check passed
```

The existing release-candidate evidence remains valid for the same branch
history:

- focused Episode/runtime suite: 282 passed;
- core independent-review invariants: 70 passed;
- Workbench API: 87 passed;
- frontend: 65 Vitest tests, ESLint, TypeScript, and Vite build passed;
- isolated progress/UI smoke: public progress precedes the answer, reconnect
  replays progress, one terminal Run is emitted, and control-plane leakage is
  zero.

## Live preflight result

The saved provider exists in macOS Keychain and the already-running 8798
process remains ready because it holds the provider in memory. A new process,
however, requires macOS Keychain authorization before the credential payload is
released.

Before the fix, both the benchmark and a minimal Keychain probe remained stuck
for more than ten seconds and left live Python processes behind. The credential
reader now isolates the official macOS `security` command behind a three-second
timeout. The same release preflight now returns deterministically:

```text
returncode: 2
elapsed: 3317 ms
reason: saved Keychain provider unavailable
```

No benchmark case, model call, tool call, semantic judge, or verifier repair was
executed. Therefore this is an infrastructure blocker, not a failed answer and
not a model-quality result. No backend fallback was used.

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

Result: `blocked_by_external_runtime`.

The architecture and deterministic release gates are ready for the one-time
five-case live evaluation, but answer quality on the final revision is not yet
proven. The blocker is a one-time macOS Keychain authorization for a new Python
process. Do not ask Claude for final quality review, switch 8792, merge `main`,
or claim Codex/Knevo parity until the frozen live artifact exists.

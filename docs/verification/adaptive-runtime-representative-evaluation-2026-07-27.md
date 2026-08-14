# Adaptive Runtime Representative Evaluation

Date: 2026-07-27

Status: `needs_product_fix_and_valid_frozen_gate`

## Candidate and scope

| Field | Value |
| --- | --- |
| Runtime source revision | `4550ce5dd52f4fcc2386fefa54e47a3acb11ce6b` |
| Runtime source dirty | `false` |
| Product-code tip | `ed2e1d89` |
| Documentation HEAD after the run | `07cbcef9` |
| Branch | `feat/agent-runtime-backends-verify` |
| Backend / model | `sdk_gpt` / `gpt-5.6-sol` |
| Credential scope | 8799 process memory only |
| Market snapshot date | `2026-07-27` |
| Canonical 8792 / `main` | untouched / not merged |

The private bounded aggregate is:

```text
/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-8799-2026-07-27-4550ce5d.json
```

The five questions were each executed exactly once and serially through the
real 8799 Conversation API. They are valid current-date self-use evidence, but
they are **not** the exact frozen benchmark required by the release plan. The
tracked cases freeze `as_of=2026-07-24`; the Conversation API derives its
information cutoff from the runtime date, `2026-07-27`. The standalone runner
cannot reuse a provider that exists only in another process's memory. Copying
the secret, inspecting process memory, restarting 8799, or silently substituting
another backend was not allowed.

Accordingly, the previous strict frozen artifacts remain historical evidence;
this run must not be represented as a green frozen release gate.

## Exactly-once self-use results

| Case | Run | Latency | Structural / semantic | LLM / tools / evidence | Product quality |
| --- | --- | ---: | --- | --- | --- |
| rebound duration | `run_20260727_225243_461799` | 70.286s | partial / repaired | 2 / 4 / 20 | unacceptable |
| Ruihuatai valuation | `run_20260727_225448_468016` | 36.858s | failed / unavailable | 1 / 5 / 0 | honest partial |
| weekly market cause | `run_20260727_225549_654677` | 120.242s | completed / unavailable | 2 / 3 / 14 | unacceptable |
| current mainline | `run_20260727_225827_149735` | 96.987s | partial / passed | 2 / 5 / 49 | useful |
| unfamiliar methodology | `run_20260727_230029_462078` | 31.828s | completed / passed | 1 / 0 / 0 | useful |

Aggregate: 2 useful, 1 honest partial, 2 unacceptable. Strict product pass rate
is 40%. Median latency is 70.286 seconds and maximum latency is 120.242
seconds. The five runs used 8 model calls, 17 tool calls, 4 invalid actions and
3 admitted repairs. They produced 83 evidence atoms with 83 unique hashes,
zero duplicate queries, zero future-of-cutoff publications, zero secret-scan
hits and zero public SSE control-plane scan hits.

## Product findings

### P0: current-data capability mismatch

The rebound answer is direct and well structured, but calls `2025-06-30` the
latest available date while the same runtime reports a fresh market snapshot at
`2026-07-27`. `agent:market_data` returned empty and FinanceQuery then served an
older time-series table. This violates the freshness objective even though the
old rows are individually traceable. The fix belongs at the data-capability
contract: a current-market task must reconcile snapshot and time-series
freshness before the model sees either, rather than adding another route.

### P0: verifier availability erases a grounded answer

The weekly-cause Episode contains a direct, structurally complete draft with
14 unique, bound evidence atoms and an explicit competing explanation. The
semantic judge exhausted its deadline, after which the public answer became a
generic evidence-gap sentence. Truth must remain fail-closed, but verifier
availability must have a reserved, observable recovery path; a judge timeout
cannot silently turn a good research result into a template. This is a shared
verification/repair seam, not a weekly-cause special case.

### P0: valuation capability returns no usable evidence

The valuation run correctly refused to invent a number, but `market_data`,
`financial_data`, two FinanceQuery attempts and KB search produced zero usable
evidence before `sdk_timeout`. This is honest but not useful. The next fix must
make company identity, financial anchors and market valuation anchors reachable
through the semantic query/tool contract; do not add a Ruihuatai route.

### Positive evidence

The current-mainline answer directly identifies an electronic-hardware line,
quantifies internal breadth, separates a secondary line, and states continuation
and downgrade conditions. The unfamiliar methodology case uses zero tools and
still gives an actionable method, evidence hierarchy, failure modes and
verification path. This proves that the model can retain useful base-model
capability when the harness does not force irrelevant retrieval.

## Independent review

The review fixed point is `main...07cbcef9`; the approved source is
`docs/superpowers/specs/2026-07-26-adaptive-finance-agent-runtime-design.md`.

### Standards

Result: `CHANGES_REQUIRED`.

- High: `conversation_orchestrator.py:3426` registers the complete
  `continuous-episode.json` as previewable and downloadable. It contains the
  internal contract, queries, provider traces, hashes and locators.
  `run_store.py:154` and `app.py:2092` do not enforce an internal visibility
  class. This violates the bounded-public-projection rule. Add an
  `internal` visibility contract enforced by the API; publish a separate
  redacted projection to the UI.
- Medium, judgement call (Shotgun Surgery): repair admission is still split
  between `continuous_turn_adapter.py:799`, `repair_coordinator.py`, and the SDK
  runtime. `RepairCoordinator` should return one `RepairAdmission(kind, goal,
  grant)` and the adapter should only execute it.

No new credential/risk-file violation, root-budget escape, Episode-continuity
break or public SSE leakage was found.

### Spec

Result: `CHANGES_REQUIRED`.

- P0: the five Conversation API summaries do not preserve the exact frozen
  cutoff/budget contract. They are self-use evidence, not the planned benchmark
  artifact. A valid release gate still needs one runner-equivalent execution on
  a clean revision with the frozen `2026-07-24` cutoff.
- P0: only mainline and methodology are useful; valuation has zero evidence,
  weekly cause publishes a generic gap despite 14 bound atoms, and rebound uses
  2025 data. This violates the freshness/directness targets in spec sections
  14.3 and 14.4.
- P1: the prior verification note was stale. This document supersedes it with
  the current five-run evidence and an explicit three-way conclusion.

No higher-priority scope creep was found.

Review summary: Standards has 2 findings (worst: private diagnostic artifact
exposure); Spec has 3 findings (worst: invalid frozen-release evidence plus 40%
strict product usefulness).

## Release conclusion

Conclusion: `needs_product_fix_and_valid_frozen_gate`.

Core architecture, deterministic tests, Continuous Episode, model-owned tools,
repair accounting, evidence lineage, SSE and the UI candidate are implemented.
However, the product is not release-green. Resolve the three shared product
seams and the internal-artifact visibility issue, then run one valid frozen
gate through a provider mechanism that preserves the exact cutoff and revision.

Do not merge `main`, switch canonical 8792, claim Codex/Knevo parity, or delete
the legacy long-tail path from this result.

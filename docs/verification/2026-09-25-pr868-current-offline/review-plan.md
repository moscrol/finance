# New Review Proposal, Not Authorization

## Identity

- Candidate: `fb41cebdaa6a186c14bd402f0f2dd83705f64421`.
- Base: `fe9fdbfd70a637efc5bcf0cfecf74080a8d6a90c`.
- Inputs: base + combined handoff `23536eb9aea1ab43551185537715a0c7365df242` (tested ancestor adbe).
- Interpreter: `/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`.
- Engineering state is exclusively `attempt02/engineering.json` and its exact leaf receipts, not this proposal.
- This file is not executable, not an authorization record, and does not enable any model request.

## Why a Fresh Review

During this run, the owner separately obtained authorization and completed the C3-only batch against f261/base033 using its different interpreter. Its spec report is PASS for C3 only; the host accepts C3 with unit-level limits and reports an older-batch aggregate C1-C7. This does not close quality-axis limits or certify fb41. That batch used 18 new requests, cumulative 333/354 according to its host audit; this session cannot consume its remaining allowance. Pinned main fe9 changes all five llm_refine payload construction paths and RAG recovery/transport. The candidate also incorporates #910 sandbox/delivery fixes and #911 observation-driven author tests. Old reports remain historical and cannot be rebound by substituting SHA strings.

After admission, main advanced to 4db9a42b6 only in two documentation files. The running candidate stays fb41/basefe9. The owner C3 report allows 0.6 seconds scheduling tolerance, although the three host reruns observed ~0.805-0.810 seconds inside the original tighter bound; do not describe its probe assertions as enforcing the original 0.2-second tolerance. This proposed fresh review retains 0.2 seconds.

This proposal is a new two-axis review, not continuation of next/c3c7/c3. No old completed stage, probe verdict, authorization, or allowance is copied. Previous failure shapes can be disclosed as context and interface warnings; the reviewer must inspect the candidate and generate fresh observations. Supplying author fixtures makes the review informed, not blind.

## Scope to Verify

| Claim | Required new observation |
| --- | --- |
| C1 | Whole-call absolute deadline, response-body trickle, cancellation, and stalled-parent worker termination, with trigger events. |
| C2 | Five actual HTTP call sites forward shared deadline; both streaming paths forward cancellation. Include active `LLM_COMPAT_PAYLOAD`, introduced by new main. |
| C3 | Timely positive control; late 0.8-second judge budget with ~2.9-second body; one request, failed/timeout, report absent, unavailable true, actual root consumption. Tolerance stays 0.2 seconds. |
| C4 | Distinct 10-second call slice and 0.5-second shared deadline; show stop before endpoint completion. A spy alone does not establish deadline behavior. |
| C5 | Zero budget has zero request and zero reservation; distinguish root exhaustion, judge-window exhaustion, and prior dispatched failure. |
| C6 | Worker startup counted in budget; assert inclusion and worker termination, not historical benchmark durations. |
| C7 | Exact candidate/interpreter/dependencies/scope receipt binding, dirty/different revision rejection, complete output, failed logging pipelines, and receipt-vs-basetemp containment. Preserve remaining limits by name. |

Review additional changed admission/protocol surfaces under their existing scope: protected .git contents and Keychain remain denied; only required metadata is admitted; interpreter override is absolute without dependency bypass; in-tool explore path validation rejects invalid paths before completion; controller identity/completion cannot be forged; budgets are not replenished after rejected delivery. Research conformance tests are scripted author evidence, not natural financial acceptance. The two axes must each report their actual coverage; a claim verified by one axis cannot silently replace another axis's unverified entry.

## Interface Warnings From Author Replay

- Transport observers accept `(event, **fields)`. `list.append` itself cannot handle header status or close return-code fields.
- `case.exc_class=None`, timeout asked 0 and attempt index 1 can describe the final, undispatched window-exhaustion slot. The preceding real request's exception is in `last_dispatched_failure`; it must not be overwritten or reported as another billed call.
- `attempt02/c3-corrected.log` is an author replay with a visible prior failed assertion at the parent root. It does not repair a sealed review verdict.
- Logs must include request and headers events. Early startup failure does not count as exercising body cancellation.

## Budget Proposal

Subject to explicit new user approval and successful engineering admission:

- GLM through the existing review route; no production model/configuration changes.
- Two serial axes. Per-axis hard ceiling: gateway 4 + explore 17 + execute 17 + report 1 = 39 requests.
- Total proposed new ceiling: 78 requests. No automatic batch retries, no transfers across axes, no extension from an old remainder.
- Stage correction is permitted only within its own existing allowance. Reserved final delivery has no additional retry.
- Any failed admission, invalid required control, missing terminal receipt, or exhausted allowance stops the batch with original artifacts retained.
- Controller COMPLETE means content was delivered, not substantive PASS. Host audit must check findings, claims, limits and raw observations before accepting any review conclusion.

No execution wrapper or approved authorization file is created by this proposal. After approval, construct a fresh run root from the current tested controller, rebind all candidate/base/inputs/interpreter references, hash its inputs, and run zero-model sandbox/preflight controls before admitting GLM. Do not launch the historical repair generator output unchanged.

## Still Outside This Proposal

L6 natural financial sessions, actual sources/subresearch/counterevidence quality, main merge, 8792 deployment, production databases, live identity, and release authorization remain separate. Passing either review axis does not authorize them. Future main movement requires an explicit applicability assessment and fresh integration evidence; this candidate is not automatically advanced again.

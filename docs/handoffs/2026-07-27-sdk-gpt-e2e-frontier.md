# SDK-GPT Adaptive Runtime Handoff

Date: 2026-07-27

Status: `implementation_complete; release_blocked`

## Exact state

- Worktree: `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667`
- Branch: `feat/agent-runtime-backends-verify`
- Branch HEAD before this handoff edit: `07cbcef9`
- Running 8799 revision: `4550ce5d`
- Verified product-code tip: `ed2e1d89`
- Working tree was clean before the verification/handoff document updates.
- 8799: `sdk_gpt`, `gpt-5.6-sol`, ready, source dirty false.
- Provider credential exists only in 8799 process memory. Do not restart 8799,
  inspect process memory/environment, print, copy, or persist the value.
- `main` and canonical 8792 are untouched. Do not merge or switch without the
  user's explicit approval.

## Progress with fixed denominators

Do not report one mixed percentage.

1. **Core architecture implementation: 100%.** Continuous Episode, model-owned
   planning/tool choice, FinanceQuery, quick/deep governor, sub-research,
   EvidenceLedger, same-Episode repair, MemoryGate, SDK/GLM/headless adapters,
   structural/semantic verification, SSE/UI and diagnostics are implemented.
2. **Deterministic/offline verification: 100%.** Latest clean full suite is
   `2919 passed, 2 skipped`; the causal shared-seam canary is green.
3. **Current-date five-case self-use quality: 40% strict useful rate.** Two are
   useful, one is an honest partial, two are unacceptable.
4. **Approved design §17: 7/10 completion items, or 70%.** Items 1-7 are built;
   item 8 (representative isolated acceptance) is not green; item 9 (canonical
   approval) and item 10 (legacy deletion after stability window) are
   deliberately not started.
5. **Canonical rollout: 0% by authorization, not by engineering delay.**

This explains why an earlier “70-80%” appeared stationary: it mixed completed
implementation with a release gate that still fails and with two future phases
that are not yet authorized.

## Completed product work

- One continuous observable Agent Episode preserves model/tool history.
- The model owns long-tail decomposition, query construction, tool order,
  recovery and stop decisions; code owns permissions, budgets and publication.
- Duplicate observations are not reintroduced as fresh evidence.
- Invalid finish, timeout delivery and verifier gaps share one bounded repair
  pool; repair counters reflect actual admissions.
- Tool-closed delivery is zero-call and capped; deep repair may continue only
  on real coverage progress.
- Information cutoff is enforced in structured/news evidence adapters and
  future candidates are recorded rather than published.
- Current mainline and unfamiliar-methodology live answers show that the model
  can answer directly without a new skill route.
- Causal canary `run_20260727_223000_947509` corrected the user's premise,
  bound 14 unique evidence atoms and completed a same-Episode repair.

## Exactly-once current-date self-use suite

Private aggregate:

```text
/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-8799-2026-07-27-4550ce5d.json
```

Runs:

- rebound: `run_20260727_225243_461799` — unacceptable; stale 2025 time-series
  was described as latest despite a 2026-07-27 market snapshot;
- valuation: `run_20260727_225448_468016` — honest partial; all valuation
  evidence capabilities returned empty/error and no value was invented;
- weekly cause: `run_20260727_225549_654677` — unacceptable; a structurally
  complete 14-evidence answer existed, but semantic-judge timeout replaced it
  with a generic gap;
- current mainline: `run_20260727_225827_149735` — useful;
- unfamiliar methodology: `run_20260727_230029_462078` — useful with zero tool
  calls, demonstrating preserved base-model reasoning.

These runs are real product evidence, not the formal frozen gate. The
Conversation API used the 2026-07-27 runtime cutoff, while the tracked release
cases freeze 2026-07-24. Do not rename or report them as the frozen benchmark.

Full receipt:
`docs/verification/adaptive-runtime-representative-evaluation-2026-07-27.md`.

## Independent review

Both axes returned `CHANGES_REQUIRED` against `main...07cbcef9`.

### Standards blocker

`continuous-episode.json` is registered as previewable/downloadable, while it
contains internal contract, query, trace, hash and locator data. Add an
API-enforced `internal` visibility class and expose only a separate redacted UI
projection. Public SSE itself passed the leakage scan.

Repair admission ownership is also split across the adapter, coordinator and
SDK runtime. This is a medium design smell; make `RepairCoordinator` return one
admission result and keep the adapter execution-only.

### Spec blockers

- The current five runs do not satisfy the exact frozen cutoff contract.
- Current data is inconsistent between market snapshot and time-series tools.
- Valuation tool coverage is insufficient.
- Semantic-judge timeout could erase a grounded direct answer (fixed in the
  current candidate branch; awaiting the next frozen live canary).

## Next execution order

Do not add a question-specific route, template, skill or global budget bump.

1. **P0 internal artifact visibility** — completed in `29ee3847`.
2. **P0 current-data capability contract** — completed in `f2eecb4e`; current
   structured tools now reject stale rows against the snapshot/cutoff floor and
   readiness exposes the same cross-source mismatch.
3. **P0 verifier availability recovery** — implemented in the current candidate
   slice; transient judge deadline/provider failures now preserve a visibly
   degraded, structurally grounded candidate while non-transient failures stay
   fail-closed. Verification receipt:
   `docs/verification/semantic-verifier-availability-recovery-2026-07-27.md`.
4. **P0 valuation evidence reachability** — completed in the current candidate
   slice: the shared `entity_anchor` now supplies ticker-aware subject input to
   valuation and financial tools. The generic fixture and canonical tool-only
   replay both pass; no Ruihuatai-specific route was added. Receipt:
   `docs/verification/valuation-evidence-reachability-2026-07-27.md`.
5. **P1 repair admission deepening** — centralize `RepairAdmission` in
   `RepairCoordinator` after the release blockers are closed.
6. Run focused tests and one live failing canary per shared seam. Then freeze a
   clean revision and execute the representative suite **once** through an
   in-process or securely reusable provider mechanism that preserves revision,
   cutoff, budget and required outputs.
7. Only after a green independent review and frozen gate may the user decide on
   `main` merge / 8792 canary. Legacy deletion still requires 500 runs, 14 days
   and explicit approval.

## Safety and operations

- Keep tmux session `candidate8799` alive while the session credential is
  needed.
- Do not rerun the five/nine cases as a debugging loop.
- Do not loosen evaluator thresholds in response to failures.
- Do not expose the full private Episode artifact in the product UI.
- The current OpenAI credential was previously visible during browser DOM
  troubleshooting. After the current 8799 session is no longer needed, rotate
  it rather than trying to persist this value.

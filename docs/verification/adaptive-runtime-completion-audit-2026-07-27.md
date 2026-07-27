# Adaptive Finance Agent Runtime Completion Audit

Date: 2026-07-27

Branch: `feat/agent-runtime-backends-verify`

Current branch tip: `efe928bd` (documentation-only follow-up)

Latest product-code tip: `d686bb9e`

Canonical 8792 and `main`: untouched.

## Requirement-by-requirement status

| Approved design §17 requirement | Status | Current evidence |
|---|---|---|
| Long-tail tasks use `UserTask`, not a precompiled route plan | complete | `intelligence/services/user_task.py`, task-floor and projection tests |
| Model owns `ResearchPlan`, queries, repairs, and stopping | complete | `research_plan.py`, Episode model-turn tests, dynamic tool order tests |
| `FinanceQuery` provides structured data without unrestricted production SQL | complete | FinanceQuery focused suite; semantic dataset schemas and read-only resource caps |
| Gaps re-enter the same Episode under bounded repair | complete | `test_real_episode_rewrites_typed_query_error_and_repairs_in_same_history`; 6 focused integration/tool tests passed |
| Quick/deep promotion and bounded sub-research branches | complete | ModeGovernor, branch coordinator, and branch budget suites/reports |
| Three-layer `MemoryGate` is active | complete | MemoryGate focused suite and verification receipt |
| Runtime adapters share truth/permission/cutoff/verifier contract | complete | Continuous/SDK/headless adapters, cutoff, provider trace, and invariant suites |
| Isolated UI/Run/SSE candidate passes deterministic acceptance | complete | candidate 8799 health/fast-path smoke; SSE/UI focused and frontend suites |
| Canonical canary is separately approved | pending by design | requires explicit user approval; 8792 is intentionally untouched |
| Legacy long-tail pipeline is deleted after rollback window | not eligible yet | requires Phase 6 trigger: 500 representative runs over 14 days, regression thresholds, and approved canary |

## Release gate

The implementation and deterministic contract gates are green, but the final
representative live gate is not green yet.

- Full `intelligence/tests`: `2868 passed, 2 skipped, 11 known baseline failures`.
- The 11 failures are existing `subconscious/userspace` machine-path
  contamination and are outside the adaptive runtime modules.
- The benchmark summary now fails closed for every `status=failed` arm;
  re-evaluating the prior five-arm unavailable artifact gives
  `passed=false`, `protocol_failure_count=5`.
- The current candidate was rechecked after an explicit data-root restart:
  `FINANCE_WS=/Users/a77/finance-workspace-private` yields
  `market_snapshot=true`, and `/api/workbench/overview` serves
  `as_of_date=2026-07-24`. The prior 2026-06-04 display came from the candidate
  process inheriting the historical default data root, not from the current
  data set.
- The SDK-GPT candidate still cannot load the saved provider in a fresh
  process: macOS Keychain access for account `linxiaoqi5111` remains
  unauthorized and the new process reports `openai_api_key_missing`. This is a
  bounded external authorization/configuration blocker; no key was read,
  copied, printed, or committed.
- Port 8798 is not evidence for this candidate: it is still running revision
  `e0b82890`, although its already-running process reports an in-memory provider.

## Non-actions

- No secret was printed, copied, exported, or committed.
- No `main` merge.
- No canonical 8792 switch or restart.
- No verifier threshold was loosened.
- No additional route, skill, or review harness was added.

## Completion decision

Current decision: `implementation_complete_live_release_pending`.

The remaining action is one fresh-provider authorization (or a new explicit
provider submission), followed by exactly one frozen five-case live run. The
goal must remain active until that evidence exists; implementation green is not
the same as release green.

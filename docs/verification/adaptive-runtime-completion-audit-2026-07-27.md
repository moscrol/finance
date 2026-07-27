# Adaptive Finance Agent Runtime Completion Audit

Date: 2026-07-27

Branch: `feat/agent-runtime-backends-verify`

Current branch tip before this documentation update: `bc774893`

Latest product-code tip: `4caf0bff`

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

- Full `intelligence/tests` under a clean test environment:
  `2915 passed, 2 skipped`.
- The previously reported 11 `subconscious/userspace` failures were reproduced
  only when the developer shell injected production `FORESIGHT_USERS_DIR`,
  `SUBCONSCIOUS_VAULT`, and `AGENT_MEMORY_VAULT` into isolation tests. Unsetting
  those three production overrides makes the full suite green; no test or
  product threshold was relaxed.
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

## Offline hardening after the bounded-timeout canary

The external provider credential is no longer a development-loop blocker. Live
provider checks are deferred until the final canary; all independent work
continues offline.

| Commit | Shared seam hardened | Verification |
|---|---|---|
| `606a71a6` | Evidence already collected before an SDK timeout can enter one tool-closed delivery repair; background executor failures terminalize the Run and pending message | focused delivery-repair and supervisor tests |
| `11be2d81` | Explicit dates in a news query can only narrow the episode cutoff | market-news and AgentToolContext tests |
| `56230b74` | SDK tool and repair events stream before runtime completion through the same safe Episode progress projection | runtime ordering, API wiring, payload-redaction tests |
| `f9b30850` | Causal web evidence is also constrained to the market window | web future-filter regression |
| `4caf0bff` | One registry-owned effective cutoff now drives tool execution, future filtering, ProviderTrace, and QueryLedger; historical windows and yearless Chinese dates are preserved | `265 passed, 1 skipped` focused combination |
| `bc774893` | Historical web proof uses task window `2026-07-05` while the database is at `2026-07-24` | dedicated non-same-day regression |

Independent two-axis review initially found one legacy `None`-cutoff crash,
duplicated cutoff enforcement, a historical-window mismatch, and missing
yearless web dates. The product defects were fixed in `4caf0bff`; Standards
re-review passed. The remaining Spec finding was a missing historical-web proof,
closed by `bc774893`. No route, skill, output template, or verifier threshold was
added or loosened.

## Non-actions

- No secret was printed, copied, exported, or committed.
- No `main` merge.
- No canonical 8792 switch or restart.
- No verifier threshold was loosened.
- No additional route, skill, or review harness was added.

## Completion decision

Current decision: `implementation_complete_live_release_pending`.

The remaining external action is one fresh-provider authorization (or a new
explicit provider submission), followed first by exactly one frozen causal
canary: `这一周行情下跌的主要原因是什么`. Wider representative evaluation only
runs after that shared-seam canary is green; it is not used as a repeated
development loop. The goal remains active until live evidence exists because
implementation green is not the same as release green.

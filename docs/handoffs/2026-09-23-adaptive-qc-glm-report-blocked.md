# 2026-09-23: #75 switches from K3 to existing GLM

## Background

The two earlier K3 attempts ended without independent verdicts. The user corrected the resulting model lock: K3 unavailable may use existing GLM; both can be writers. This authorizes model substitution, not weaker evidence, production reconfiguration, natural-finance resends, merge or deployment.

Candidate remains `31f1b40dd788d36c71da249d59fb769c50d7cd30`, baseline `9a02279863733c9b9f60fd92fcc7e840fa83f878`. Historical full gates and 45P keep their original revision identities.

## Discovery Order

1. Recorded the correction and updated the shared preference card. Existing pi fomo configuration recognized `glm-5.3`, but its local port 54340 was not listening.
2. Checked the existing Workbench launcher configuration without starting it. Its official GLM endpoint and Keychain credential were available. The `FORESIGHT_LLM_KEYCHAIN=0` value is a feature flag, not a service name; the actual credential command references `finance-workbench-glm`. The private resolver follows that existing command and never persists the key.
3. Created `~/.finance-runtime/reviews/pr868-glm-qc-20260923-1707/`, reused the owned clean locked candidate as read-only source, and isolated Spec/Quality work areas. No previous K3 review output was provided to GLM.
4. Adapted the private relay to official HTTPS and `glm-5.3`, preserving temperature and removing K3-specific credential assumptions. Both offline tool sandboxes and the fake-server adapter check passed.
5. Real GLM admission passed: one small request plus a three-request pi read/write/final roundtrip, about 20.13 seconds.
6. Spec explore delivered probes and a terminal report, but ran tests early, overwrote scratch probes, and inaccurately reported a C4 test as unexecuted. Preserved tool requests/outputs, materialized original probe versions, and supplied exact same-axis evidence to a fresh execute session. No host-authored probe fixes.
7. Execute delivered provisional accounting: 3 passed and 3 failed probe runs, failures attributed by that model to probe bugs; author tests zero. Raw failures and classifications remain distinct. Several shell commands ended in `echo`, so wrapper exit0 must not be confused with captured child exit1.
8. Fresh report session's request 23 received upstream HTTP200 but did not finish within 120.021 seconds. Pi recorded `terminated`; no valid final report. Stopped without Quality model calls or automatic retry. Host closure is `BLOCKED_REPORT_TRANSPORT_DEADLINE`, not a product verdict.
9. Archived 403 exact copies, scanned for the actual key and credential patterns, and verified all 469 copies across the new archive and both old K3 archives. Candidate clean, request counters reconciled, owned processes exited, private port 19899 released.

## Decisions

| Option | Assessment | Decision |
|---|---|---|
| Wait only for K3 | Converts a temporary transport choice into a task constraint; contradicts user correction | Rejected |
| Restart fomo or production | Unnecessary shared-service side effects when an existing direct route is configured | Rejected |
| Existing official GLM route in a private review harness | Preserves production, identity and evidence isolation | Used |
| Apply K3 parameter stripping and Plus checks to GLM | Provider-specific assumptions are not universal constraints | Rejected |
| Silently repair summaries or overwritten probes | Would erase evidence and mix host authorship into independent probes | Rejected; kept originals and explicit provenance |
| Count wrapper exit0 as green or replace final verdict with execute summary | Confuses transport/execution with review quality | Rejected |
| Retry failed final request or extend budgets automatically | Current batch still requires stopping when a stage has no valid final output | Rejected; stopped batch retained |

## Evidence And Limits

Canonical report: `docs/verification/2026-09-23-adaptive-qc-glm/README.md` and `report.json`.

73 GLM admissions/dispatches: 4 gateway, 23 explore, 23 execute, 23 report; 72 streams completed, one failed. These are not billing receipts. Earlier K3 17+1 attempts remain unchanged. The execute report is provisional; no independent Spec or Quality final verdict exists. C3/C5/C6 behavior and author tests were not covered. Missing EXPLORE.md/EXECUTE.md were not fabricated: the terminal REPORT.md artifacts were explicitly used instead.

L6 remains NOT_PASSED at actual 1/1/0. No new financial questions, current-head full gates, main union tests, merge or deployment. A single GLM batch does not establish comparative model speed or reliability; `pi thinking=off` also does not establish the server's reasoning mode.

## Next Work

K3/GLM substitution is now an explicit continuing policy, including writers. A new review attempt should have a new root, a concise report evidence index, explicit missing-claim coverage, correct child/wrapper status accounting and a finite budget; do not append a final verdict to this failed run. Natural acceptance requires its own authorization, not filling in old Q3. The PR stays WIP until independent review, natural quality, current gates and user approval are actually available.

The private adapter, bridge and sealing scripts are archived as reproducible text snapshots, not promoted into production `scripts/` or a reusable registry: the final report workflow did not validate end-to-end, and the process deviations still require work. No harness-reference changes were made. The reusable policy is in shared preferences, the workorder and project lessons, not an unverified second runtime implementation.

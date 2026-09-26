# #75 / PR #868: GLM substitution and partial independent execution

## Status

**Host closure: `BLOCKED_REPORT_TRANSPORT_DEADLINE`. This is not an independent Spec or Quality verdict.**

User correction: K3 unavailable may switch to existing GLM; both can be writers. Model selection is replaceable, while identity, evidence isolation, quality standards and finite budgets remain. The earlier K3 failures are historical evidence, not a permanent prohibition on GLM.

The GLM route passed a real small request and pi read/write/final roundtrip. Spec explore and execute delivered artifacts. Spec report's final request received upstream HTTP 200 but failed to finish within 120 seconds; pi recorded `terminated` and no valid final report. Quality was not started under the batch stop rule. No automatic retry, natural finance question, merge or deployment occurred.

## Identity And Route

- Candidate: `31f1b40dd788d36c71da249d59fb769c50d7cd30`; baseline: `9a02279863733c9b9f60fd92fcc7e840fa83f878`.
- Existing owned, locked, detached candidate: `/Users/a77/.finance-runtime/reviews/pr868-k3-qc-20260923-1607/candidate/finance-workspace-private`. It remained clean and read-only; old K3 review outputs were not supplied to GLM.
- New evidence root: `/Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1707/`.
- Requested model/provider: `glm-5.3` / private pi registration `glm-direct-review`.
- Route: private loopback `19899` to existing official `https://open.bigmodel.cn/api/coding/paas/v4`, standard HTTPS verification. Existing launcher Keychain credential was resolved in memory, never written into tool environments or archived files. Production configuration and service were not changed.
- The configured fomo port `54340` had no listener. No request was sent to it, and it was not restarted. A stopped local proxy was not treated as proof that GLM was unavailable.
- The GLM adapter preserved temperature and did not apply K3-specific Plus credential checks or parameter stripping. `pi thinking=off` follows existing model metadata; it does not prove that server-side reasoning was disabled.
- Limits: 120 seconds/request, 600 seconds/stage, 24 requests/stage, 4 gateway requests/axis, 8192 output tokens, concurrency 1, no automatic retry. Maximum planned batch admission count 152; actual count 73.

## Actual Execution

| Axis / Stage | Model Requests | Result |
|---|---:|---|
| Spec gateway | 4 | PASS: tiny request plus 3 pi requests, 2 tool executions, copied random content matched; 20.13 seconds |
| Spec explore | 23 | Terminal report and probes delivered; process deviations below |
| Spec execute | 23 | Terminal report delivered; provisional probe accounting below |
| Spec report | 23 | 22 completed; final request failed after 120.021 seconds despite upstream HTTP 200; no valid final report |
| Quality gateway / explore / execute / report | 0 | NOT_RUN |
| Author tests | 0 | NOT_RUN |
| Natural finance questions | 0 | NOT_RUN |

Total admissions and dispatches: **73**. Completed streams: **72**. Failed streams: **1**. All counters reconcile, active requests are zero, every shim shutdown completed and private port 19899 was released. These are request/transport records, not a supplier billing receipt. The previous K3 batches' 17 + 1 attempts remain separate.

## Provisional Probe Evidence

The execute model reported **3 passed / 3 failed probe runs**, separate from the intentional failing control and zero author tests. These are provisional execution findings, not a final independent verdict:

- Current C1 stream probe: shared 1.5-second deadline interrupted reading at about 1.50 seconds; worker return code 124 was observed after a 0.4-second observation delay.
- C1 stalled-parent probe: worker exited 124 while the parent stopped reading for 2 seconds; resuming produced a deadline failure.
- New C4 v2 probe: 0.5-second budget was rejected before HTTP; with 1.5-second shared budget and a 2.9-second fake response, the wrapper stopped at about 1.51 seconds.
- Three failed original/variant runs were classified by the execute model as probe bugs: instantaneous worker-death expectation; expecting a request below the preflight minimum; mutually inconsistent fixture-hit counts. Preserve the failures and that attribution separately. The report phase did not deliver the final review of these classifications.

C3/C5/C6 lack independent behavioral coverage; C2 is primarily static; C7 concerns only historical receipt identity, not new full gates. Historical full-suite evidence still belongs to `7ad61a0d3`; earlier 45P evidence still belongs to `2f4b5f089` / `2c61ff825`. Nothing is re-signed to this documentation head or current main.

## Process Deviations

1. Spec explore ran probes despite the phase instruction and overwrote scratch probes. Initial write contents were materialized from original tool requests, with provenance, and the execute session reran them. The host did not author or alter probe code.
2. Explore's final report said C4 had not run, but its `021-bash` output proves an assertion failure. That summary was not accepted as a receipt; execute explicitly recorded the contradiction.
3. Execute appended `echo EXIT=$?` to several shell commands. Tool wrapper exit status is therefore 0 even when the immediately captured child status is 1. In particular, the positive control produced `AssertionError` and child `EXIT_CODE=1`, **not tool exit 1**. Do not collapse these two statuses or count the wrapper as green.
4. `work/EXPLORE.md` and `work/EXECUTE.md` were not written before closeout. Existing terminal `REPORT.md` files were explicitly used as prior-phase artifacts; missing files were not forged. Host bridges copied only same-axis reports and raw tool records, excluding model reasoning and the other axis.

Transport success, process exit 0, or `execution.complete=true` does not certify review completeness. The final report failure was correctly retained as blocked.

## Archive And Verification

- `report.json`: host index and stop state; not a replacement for independent review.
- `raw/spec/{explore,execute}/REPORT.md`: original terminal reports, including their errors and limitations.
- `raw/*/*/commands/`: original tool requests, full outputs and recorded wrapper results. Archived `.txt` output files are byte-identical copies of private `.log` files.
- `artifacts/spec/`: current and original materialized probes; Python snapshots have `.txt` suffixes and are evidence, not production modules.
- `tooling/`: private harness snapshots, credential resolver source without secrets, prompt amendments, bridging and sealing scripts.
- `archive-manifest.json`: **403** source/copy hashes; verified byte-for-byte. Across the two earlier K3 archives and this one, **469** copies matched their private originals.
- `private-manifest.json` and `key-scan.json`: private evidence inventory and exact-key plus bearer/sk/JWT pattern scan. No hits. Model event streams remain private and are not copied into the repository.
- Both offline tool sandboxes passed. The local fake-server adapter check verified model admission, official routing, parameter preservation, accounting and shutdown; it made zero model requests.

## Next Boundary

K3 and existing GLM are both authorized choices for subsequent writing/review work; do not wait only for K3. This stopped batch is not resumed or relabeled. A follow-up should use a new evidence root and a compact, source-linked report input, explicitly address missing claim coverage and the phase/exit-code issues, and freeze a finite remaining budget before new calls. The private adapter is not promoted to a general production runner while its end-to-end reporting workflow remains unvalidated.

L6 remains `NOT_PASSED` at actual 1/1/0. Do not append Q3 or resend old questions. PR remains WIP; current-head full gates, current-main union validation, completed independent review, natural-quality acceptance and explicit merge authorization are still separate requirements.

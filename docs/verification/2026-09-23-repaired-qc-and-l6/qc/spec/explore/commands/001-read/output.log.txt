# PR #868 / #72 Claim Set

Source: PR #868 description C1-C7, frozen for candidate ac11027fa75ee6a988ab90ab81e0329159964643. These are author assertions to verify, not reviewer findings.

- C1: llm_http_transport.urlopen(request, timeout, deadline, is_cancelled) applies a monotonic absolute deadline to an entire HTTP call including streaming reads. Parent read/write checks and worker Timer -> os._exit(124) enforce termination even with slow/trickling input or a stalled parent.
- C2: All five llm_refine HTTP call sites use _open_deadline_http_response, passing deadline and, on streaming paths, cancellation. No bypass. Examine upstream origins of timeout and shared deadline separately; same-valued fixture parameters cannot prove forwarding. Deadline has no asserted slice() API.
- C3: A late semantic judge payload (0.8s budget, upstream roughly 2.9s) is recorded failed/timeout, report_received=False, unavailable=True; payload is not accepted, root remaining time reflects elapsed wall clock.
- C4: Wrapper forwards the shared research deadline, not only the per-call timeout. A 10s slice and 0.5s shared deadline must stop before the roughly 2.9s fixture finishes. Missing forwarding must be detectable by a behavioral probe.
- C5: Zero budget means no HTTP request and no reservation; distinguish exhausted root from exhausted judge subwindow.
- C6: Each HTTP call starts an isolated Python subprocess; startup is part of the granted budget. Historical startup durations are observations, not a performance guarantee. Verify inclusion, not those benchmark numbers.
- C7: Historical engineering receipts belong only to clean revision 7ad61a0d3fd9ee63abe2089a4049a0a1b4a8bc16. The current candidate includes a main merge and product fixes, NOT a docs-only delta. Historical receipts do not cover this candidate and cannot be relabeled as current or independent test counts.

Scope limits: broader adaptive-loop behavior and financial answer correctness are not claims covered by #72. The previous L6 natural acceptance did not pass, and this engineering review cannot promote it. The repaired-candidate changes listed below are in scope for correctness findings. No merge/deployment authority.

Inputs alongside this file: author-summary.json and author-pytest-receipt.json are unmodified copies from the historical gate; code-tip-to-candidate.diffstat.txt is host-generated git evidence. Do not treat their existence as proving C1-C6.

Additional repaired-candidate correctness scope (findings, not extra C claim IDs):
- Currency field units in episode_semantic_verifier.py must accept equivalent rounding while rejecting wrong currency scale, non-money fields and unbound evidence.
- pi_review_protocol.mjs and prepare_pi_review_repair.py bind stage/axis/revision/baseline in the controller. Reviewer identity injection, including matching identities, is forbidden. Request/deadline/one-closeout limits are unchanged.
- adaptive_l6_batch.py and prepare_adaptive_l6_runner.py must not submit a next question before an exact-Episode source audit PASS. Missing, failing, late and malformed audits must stop. Synthetic PASS is not a natural financial verdict.
- Offline CLI and archived-input fixture tests need files denied by this review sandbox. Do not weaken the sandbox. Distinguish unrun author tests from independent small probes.

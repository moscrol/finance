# PR #868 / #72 Claim Set

Source: PR #868 description C1-C7, frozen for candidate e7a6cb412865fdd189cf51a17f93622fa3d4fe55. These are author assertions to verify, not reviewer findings.

- C1: llm_http_transport.urlopen(request, timeout, deadline, is_cancelled) applies a monotonic absolute deadline to an entire HTTP call including streaming reads. Parent read/write checks and worker Timer -> os._exit(124) enforce termination even with slow/trickling input or a stalled parent.
- C2: All five llm_refine HTTP call sites use _open_deadline_http_response, passing deadline and, on streaming paths, cancellation. No bypass. Examine upstream origins of timeout and shared deadline separately; same-valued fixture parameters cannot prove forwarding. Deadline has no asserted slice() API.
- C3: A late semantic judge payload (0.8s budget, upstream roughly 2.9s) is recorded failed/timeout, report_received=False, unavailable=True; payload is not accepted, root remaining time reflects elapsed wall clock.
- C4: Wrapper forwards the shared research deadline, not only the per-call timeout. A 10s slice and 0.5s shared deadline must stop before the roughly 2.9s fixture finishes. Missing forwarding must be detectable by a behavioral probe.
- C5: Zero budget means no HTTP request and no reservation; distinguish exhausted root from exhausted judge subwindow.
- C6: Each HTTP call starts an isolated Python subprocess; startup is part of the granted budget. Historical startup durations are observations, not a performance guarantee. Verify inclusion, not those benchmark numbers.
- C7: Each engineering receipt belongs only to its recorded clean revision. The current e7 candidate has its own full engineering receipt in engineering-history.json; earlier c315 failures and prefix coverage failure remain separate. Current delta only persists logs and guards evidence storage; no RAG/coverage root-cause fix is claimed. Author runs cannot be relabeled as independent reviewer test counts.

Scope limits: broader adaptive-loop behavior and financial answer correctness are not claims covered by #72. The previous L6 natural acceptance did not pass, and this engineering review cannot promote it. Additional repaired-candidate scope below is in scope for findings. No merge/deployment authority.

Inputs alongside this file: author-summary.json and author-pytest-receipt.json are unmodified copies from the historical gate; code-tip-to-candidate.diffstat.txt is host-generated git evidence. Do not treat their existence as proving C1-C6.

Additional correctness scope, not additional C claim IDs:
- Currency field units in episode_semantic_verifier.py: equivalent rounding accepted; wrong currency scale, non-money fields and unbound evidence rejected.
- Controller owns stage/axis/revision/baseline in pi_review_protocol.mjs and prepare_pi_review_repair.py; any reviewer identity injection is forbidden.
- adaptive_l6_batch.py and prepare_adaptive_l6_runner.py require exact-Episode source audit PASS before next question. Missing, late, failing or malformed audit stops.
- diagnose_llm_timeout.py must fail strict checks if target request/response phase is not reached, even when wall time is under budget. Transport stage events include process spawn and request send.
- prepare_adaptive_l6.py and retrieval_readiness_worker.py require valid unique final model/encoding result, shape (1,1024), not just exit 0. Offline and 120s budget unchanged.
- probe_stalled_cancellation.py now arms its 0.3s cancellation timer only after headers; verifies read duration <1s and cancel-to-stop <0.7s, while original request deadline remains 10s. Review this test-fixture change separately from production transport.
- Cancellation waits for __enter__ on the lazy response context, not construction of the context manager; the slow-opener regression delays context entry.
- prepare_adaptive_l6_runner.validate_deadline_admission recomputes every strict scenario for timing and target coverage, binds clean current candidate identity, and rejects wrong/missing budgets before sidecar creation.
- Sandbox protected-content restrictions stay fixed; metadata-only access permits pytest collection on the original candidate. Literal /usr/bin/security execution is now also denied and tested with help only. No copied source/test runs count as candidate tests.
- run_main_gate.sh persists full pytest output in the unique receipt directory, rejects tee/tail failure or missing output, and refuses receipt storage within disposable basetemp. It must not hide pytest failure behind successful logging.
- Historical RAG and shared-window coverage failures are disclosed in engineering-history.json. A fresh complete author run is not proof that their unknown root causes were fixed. Independently assess the remaining risk.
Keep reviewer behavioral probes small: explicitly cover C3 late judge, C5 exhausted root and subwindow, C6 startup time inclusion, C2 each of five call paths, and actual cancellation. Report missing coverage honestly. Do not inherit prior reviewer conclusions.

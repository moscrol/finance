# Spec K3 operator QC — BLOCKED, not independent signoff

Candidate `47530e20fe5c3195e50ce429b31898d57918e413`; historical base `728f327160bbd2485cb635e7ef09d040d718d7b5`.

One actual K3 session: 40 request admissions / 40 completed assistant messages, 42 tool calls, 1187.020 seconds, exit 75. The admission hook refused the next request; no REPORT.md or reviewer verdict.json was created. No operator retry or budget increase. `execution.json.stop_reason=null` reflects that the outer watchdog did not stop it; it is NOT successful completion. `stderr.log` contains the admission refusal.

## Evidence retained and limited claims

- Spec receipt `formal-receipts/20260921T041749Z-47530e20-2312ed82d8a6.json`: 90 passed / 1 skipped, exit_status 0. Tool trace 040 matches the console (100.50 seconds).
- Spec receipt `formal-receipts/20260921T041836Z-47530e20-03899aeeb7c4.json`: 105 passed, exit_status 0. Trace 041 matches console (37.04 seconds).
- Combined supplementary formal tests: **195 passed / 1 skipped**. These are focused tests run by K3, not a completed Spec verdict or a new full engineering gate. Test commands piped to tail, so their tool success bit only establishes pipeline completion; counts/pytest status are additionally established from the actual receipts. No full stdout was saved for these two commands.
- A1 establishes real clean shell-gate control. A2's first draft forgot to commit the intentionally failing test and was rejected as dirty, not a code failure. A2r committed it and observed correct failure/readback exit 1.
- A3r has an accepted unmodified synthetic receipt and separate identity rejections, including wrong/missing/malformed tree and allow-dirty foreign tree. A3b exercises explicit baseline comparison, including old baseline revision. These mutations are synthetic proof fixtures, not production execution receipts.
- A7r initially failed Ruff on the probe's own combined import. Trace 022 repaired only the synthetic test: actual nested collect-only returned gate exit 0 and exactly one added parent receipt. The same command then mislabeled its clean receipt as dirty; later trace 023 used the actual dirty receipt and observed rejection/allow-dirty control. Trace 024 fixes the earlier revision-confounded process-exit probe and obtains exit 4 vs 0.
- Board probe initially ran git lock outside its synthetic repository; corrected command, synthetic tree naming, and section-parser errors were kept in events. Trace 031 directly prints correct clean vs doc-dirty grouping. Do not count the earlier misleading Boolean strings as board defects.
- Backfill C uses the author's synthetic fixture builder but reviewer-authored cases. Initial nonexistent import and wrong patch target were fixture errors. C's `!!!ALLOWED` lines modify protected rows BETWEEN child invocations, not DURING one call; child snapshots compare within an invocation. External baseline acceptance probe D2/D3 rejects the same between-run changes. This is not an established bypass of the end-to-end contract.
- D's first run lacked a fixture directory. D4 mutates shared child report files; later D6 therefore has mixed causes. Preserve but do not count that as an isolated baseline-hash test. The legitimate D1 control and D2/D3 rejections precede contamination. D1's 37 checks are assertion rows inside one acceptance scenario, not 37 independent reviewer scenarios.
- The final Ruff command included `scripts/run_main_gate.sh` as Python. Operator reproduced **197 errors solely from the shell input** and independently checked the Python list: exit 0. This is apparatus misuse, not 197 candidate code defects. Original output preserved; no rewrite to green.

## Scope / hygiene limitations

Checkout and author candidate clean and unchanged at start/end; this does not prove no transient edit-and-revert. Tool trace shows source reads and isolated synthetic writes; no production DB action, application endpoint, credential access, or extra provider request in model tools.

**One output boundary violation:** trace 022 redirected to `/tmp/a7.log`, outside its authorized evidence directory. Operator preserved its bytes at `operator-qc/spec-outside-output-a7.log`; did not remove the original. Mechanical audit's `path_or_trace_violations=[]` checked direct write-tool paths only and DOES NOT certify shell writes. Synthetic repos were locally reset/deleted/recreated by reviewer scripts inside its own evidence root; earlier traces remain, but first binary fixture incarnations are not all retained.

No real concurrent two-gate scenario in completed Spec evidence; missing coverage stays unaccepted. The remote-tracking main changed during Spec (actual before/after in execution.json); this review is never latest-main integration validation. Quality is the already-authorized separate axis, not a Spec retry, and receives no Spec findings.

## Pre-seal addendum (does not replace the above partial conclusion)

The formal receipt directory also contains `20260921T041747Z-47530e20-1a04228dcb87.json`, with zero executed tests. It is preserved but excluded from passing evidence; the two real run receipts still sum to 195P/1S. An operator collector initially assumed only two non-latest files and failed its count assertion; the original diagnostic is retained separately. No strict gate acceptance of that zero-execution receipt is established.

Of 34 Spec bash calls, 16 omitted an explicit tool timeout (indices in `preseal-observation.json`), violating the per-command <=120s instruction despite the outer global deadline remaining in force. No specified timeout exceeded 120s. This further limits apparatus-compliance claims; it is not a candidate source defect.

**Operator status: BLOCKED / partial evidence only. No model-authored final verdict exists; operator QC cannot manufacture one. No merge/deploy/backfill approval.**

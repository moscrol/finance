# Quality K3 operator QC — incomplete review; confirmed receipt-ownership defect

Frozen candidate `47530e20fe5c3195e50ce429b31898d57918e413`, historical base `728f327160bbd2485cb635e7ef09d040d718d7b5`. This is **operator QC**, not a replacement model-authored Quality verdict.

## Process versus review outcome

One actual `mirasim-kimi/kimi-k3` session completed 40 provider admissions, 40 assistant messages and 42 tool calls in 933.388 seconds. Exit 75; next request refused. No retry or budget increase. `stop_reason=null` means the outer watchdog did not kill it, not success. The reviewer created `REPORT.md` / `verdict.json` early, but never updated their `BLOCKED / in_progress / NOT_TESTED` placeholders. They remain byte-identical original evidence, **not a final report**. The instruction to stop expanding by request 28 and reserve conclusion time was not followed; early file creation did not solve finalization.

## Confirmed finding O-K3-001 (high / P1): PID is not pytest invocation identity

- Locations in candidate: `conftest.py:183-188` claims `FWP_TEST_RECEIPT_OWNER_PID`; `conftest.py:306-311` permits the matching PID to write. `scripts/main_gate_receipt.py:34-35` requires a target string but execution mode does not bind it to the requested outer invocation; `scripts/run_main_gate.sh:70-85` reads the immutable file after checking the outer process exit.
- Requirement R1 says nested pytest must not claim the parent's path. A subprocess has a different PID and is excluded. A nested **same-process `pytest.main()` invocation has the same PID**, finishes first and writes the parent's unique path. The real outer invocation then gets `File exists`; the warning does not fail pytest. Inner and outer exit 0, same tree/revision/interpreter, so the gate accepts the inner receipt as the outer run's proof.
- Quality trace `030-result.txt`, command in `quality-tool-trace.json` #30, and `quality-k3/logs/b4_nested_inproc.log`: outer target `tests/test_nested_inproc.py` has 1 passing test; receipt records `tests_inner/` and 2 passing tests; **gate exit 0**. This is a real invocation, not hand-edited receipt JSON. The original receipt file was later removed as part of reviewer fixture reuse; its console/readback survives. Do not imply the first binary fixture or receipt file is still present.
- Control: trace #29 / `b3_nested_subproc.log` correctly records outer target and 1 pass for actual nested subprocess pytest. Concurrent shell controls in trace #27 also remain correct.
- Operator independently corroborated using a fresh tiny repository and exact copies of candidate `conftest.py`, shell gate, helper **and `test-environment.json`** (the Quality fixture had a reduced test-environment file). No candidate code edits, no extra model. See `operator-qc/reproduce_inprocess_receipt.py`, `inprocess-reproduction.json`, and `inprocess-reproduction/{subprocess-control,inprocess-negative}/`. Both toy gates exit 0; subprocess control records outer target / 1 pass, same-process negative records inner target / 2 passes while outer stdout says 1 pass and `File exists`. Unique receipts, command/exit JSON, shell stdout/stderr and textual fixture are retained. Synthetic revision `57a553fe...` is **not** candidate revision.
- Impact: wrong scope and test counts can be accepted as run evidence. **Not demonstrated:** acceptance of a failing outer process; actual process-exit matching remains a separate guard. This does not by itself rewrite the earlier v3 author test totals or prove the historical full run was affected.
- Attribution: the candidate's added PID owner mechanism demonstrably leaves same-process reentrancy uncovered. The defect is present at v3 and concerns #814 receipt ownership, not the later `cdf6647cf` receipt-only tree-check change specifically. No old-base behavioral comparison was executed; do not call it a newly introduced old-base regression.
- Repair direction only, not implemented: bind write ownership to the outer pytest **invocation/config lifecycle**, not PID alone; nested instances must not write, sequential top-level invocations must reacquire correctly. Retain subprocess/concurrent controls and add same-process regression. Merely checking target can miss reentrant same-target runs; a reliable invocation owner is primary.

## Accepted partial observations (not blanket requirement signoff)

| Surface | Observed evidence | Operator qualification |
|---|---|---|
| Helper validation | `probe_a_receipt_edges.py`, `logs/probe_a_results.json`: **39 subprocess parameter cases**, including valid pass/fail controls, counts/types, status/failure consistency, missing/malformed inputs, identity, allow-dirty, actual process exit and baseline comparison | Expected return codes corroborated. These are crafted JSON cases, not 39 independent end-to-end scenarios. |
| Concurrent shells | Trace #27, `b2_run{1,2}.log/.rc`: concurrently launched background gates share one root, both exit 0 with different immutable paths; targets/counts remain 2 vs 1 as requested | Real concurrent launches; not exhaustive interleaving coverage. Earlier receipt files removed by later fixture setup; logs retained. |
| Nested subprocess | Trace #29, gate exit 0, one outer receipt / 1 pass | PASS for this control only; same-process counterexample is FAIL. |
| IO / Git / signals | #32: read-only receipt root exit 4; fake Git that always fails exit 4; non-repo exit 4. #33: SIGTERM exit 4 | Forced conditions reached. Fake Git fails early revision query, not a specifically isolated late status-query failure. |
| Drift | #35, `b9b_drift.log`: before `eae2c251`, after `4c684bf1`, test 1 pass but gate exit 4 | Valid corrected drift probe; initial #33/34 is fixture error, not proof of commit-drift detection. |
| Dirty / receipt-only | #36/#37: dirty default exit 2; allow-dirty exit 0 with dirty receipt; readback default exit 4, explicit allow-dirty exit 0 | Local diagnostic mode, not merge permission. |
| Immutable file | #37: preexisting sentinel unchanged, write warning; fresh-path control writes receipt | Direct pytest remains exit 0 by design; this alone does not prove every gate write failure is closed. |
| Board | #40/#41: corrected synthetic fixture yields missing/prunable and locked entries in unknown bucket; clean/dirty patch-equivalent flags distinct | Toy names classify as `other`, not `dev-worktree`; no valid clean-dev deletion-candidate bucket test. No pinned-main-during-scan mutation. Partial only. |
| 302132 | Source was read (traces #9–15), no reviewer-authored dynamic backfill/publish probe completed | F1/F2/F3 dynamic checks NOT_TESTED on Quality. Spec's separate partial probes cannot become Quality signoff. |

Quality ran no formal candidate test suite. Synthetic test counts are not added to Spec's 195 passed / 1 skipped or the historical full engineering run.

## Preserved apparatus failures / evidence limits

1. B1 first gate exited 4 because the reviewer inherited `FWP_TEST_RECEIPT=0`; #24 repeated without enabling it. #25 diagnosed, #26 explicitly enabled it and passed. Red originals remain; this is not a candidate defect.
2. B9's first attempt used malformed `git -c user.name k3` instead of `user.name=k3`; test failed and left staged dirt. `b9_drift.log` preserves that; #35 corrected the toy command and genuinely changed revision. Toy reset/clean was inside evidence only.
3. Board creation deleted a toy worktree directory without removing its Git registration, so re-add initially failed. #40 pruned this **synthetic repo only**, then established locked/missing conditions. No real worktree cleanup.
4. Shell tools often returned their last command's success, so `tool_failures=[]` does not prove every command passed. Gate exits are in traces or `.rc`, and helper cases record actual `subprocess.returncode`.
5. Complete shell stdout logs are preserved, but the gate itself retains pytest's **last 15 lines**. Do not call these full pytest transcripts. Earlier toy receipt directories were removed/recreated; keep this limitation despite final textual fixtures being archived.
6. Of 36 Quality bash calls, **16 omitted an explicit tool timeout**, contrary to the <=120s per-command instruction (mostly source reads/diagnostics). The global 1200s watchdog and request cap still applied. No defined timeout exceeded 120s. This is a contract-compliance limitation, not candidate code failure.
7. Direct write tools and inspected shell commands stayed within the Quality evidence root for writes; no other-axis reads, credential access, application endpoint, production DB write or shared source Git mutation was observed. This is trace review, **not OS-sandbox enforcement** or proof against transient edits. Candidate/author start and end were clean and unchanged.

## Conclusion

**Independent Quality completion: BLOCKED. Operator code disposition: CHANGES_REQUIRED for O-K3-001.** These are separate facts. Do not rewrite the reviewer placeholder as a final rejection/approval. Spec also exhausted its cap without a report. Full independent acceptance is incomplete, and the confirmed defect is sufficient to withhold approval. No source fix, merge, deployment, production backfill or extra model session occurred in this QC.

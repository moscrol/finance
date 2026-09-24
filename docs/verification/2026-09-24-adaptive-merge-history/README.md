# PR #868: completed failure history, 2026-09-24

This archive preserves completed or explicitly stopped work. It does not certify the later candidate `c315cfdaa96a5b18cedb060b09ddc92ec2a14559`, replace an independent verdict, or authorize push, merge or deployment.

## Engineering

| Candidate | Outcome | Evidence |
| --- | --- | --- |
| `5e6974d3946f48c4f27c8847830d1a17c0529b41` | Full Python: 15324 passed, 1 failed, 85 skipped, 2 xfailed; collected 15412. Ruff, frontend and five registry/ledger leaves passed. Overall RED. | `engineering-5e6974d39/gates.json`, `pytest.json`, frontend receipt and logs |
| `ce379288595b5a809aea14cd02671acf10d0278c` | ABORTED_SUPERSEDED during Python after further probe/admission fixes. No completed pytest receipt; remaining leaves not run. | `superseded-ce3792885/interruption.json`, `python.log.txt` |

Interpreter throughout: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`. The original full-run failure was `tests/test_stalled_cancellation_probe.py::test_stalled_read_cancellation_is_prompt[synthesis_stream]`. Its first repair, `9bdac5799`, armed the cancellation timer after constructing a response context manager. That construction was lazy: it did not observe response headers. A later local 75P/1F run exposed the remaining race; an unchanged diagnostic rerun was 76P, not a repair or replacement of the failure.

The stronger regression delays entry into the context, not construction of it. It failed on all three old probe paths. `c315cfdaa` moves the timer inside the entered response context. Related tests then passed 111/111. These are targeted author observations, not a complete gate for that revision. The original logs are retained.

The superseded full gate received SIGINT, but did not terminate within 120 seconds. After checking the owned process identity again, SIGTERM ended it and its resource tracker. Its shell reported signal 15 and absence of a terminal pytest receipt. Neither progress dots nor the prior focused tests count as a full result.

## Independent Review

| Batch | Original Outcome | Accounting |
| --- | --- | --- |
| `pr868-glm-qc-20260924-0015` | BLOCKED_PROVIDER_OR_ROUNDTRIP: copied nonce omitted final LF; no review stages admitted. | 3 model requests |
| `pr868-glm-qc-20260924-0024` | Spec: BLOCKED_INCOMPLETE_EVIDENCE. Quality: CHANGES_REQUIRED. Host overall: BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE. | 71 model requests; cumulative 74 including the prior gateway |

Controllers completing their stages did not close the behavioral review:

- Both axes actually ran the intentional failing control with exit 1. Both original-path author pytest attempts ended with exit 2 because the sandbox denied ancestor metadata.
- Both later observed 10 passed / 25 deselected using copied tests. `copied-test-audit.json` confirms identical test-file bytes, but not the original collection/configuration context. They are not accepted as original-candidate runs.
- Spec's three behavioral probe invocations failed during imports, before behavioral assertions. It also retried the same probe beyond the prescribed single corrected variant. No independent behavior pass is inferred.
- Quality ran two probe scripts: one passed and one failed. Raw output is 13 passed / 2 failed subcases (5+8, not the report's 12); this differs from the script-invocation denominator. C3/C5 remained unexecuted.
- Original reports and per-command request/result/output files are preserved. Host comments do not amend either reviewer verdict.

## Offline Diagnosis

The sandbox red/green sequence used the original candidate test path. Allowing only ancestor metadata removed one failure but still hit candidate `.agents` metadata. Adding candidate metadata allowed the selected 10 tests to pass. Four protected content reads remained denied: candidate documentation, `.git`, credential configuration and the other review batch's report. This is host infrastructure evidence, not independent review.

The Quality slow-stream fixture declared `Content-Length: 12` while sending 100 bytes. It also expected multiple line-iterator callbacks without sending line endings. Three separate host copies produced:

| Fixture | Exit |
| --- | --- |
| Original bytes | 1 |
| Correct length only | 1 |
| Correct length and line framing | 0 |

The original reviewer file SHA-256 remained `3cce5e4038adb6055225b98466a278a4fd94705e57b36d41e8570496cafb8f48`. These results support classifying the observed failures as fixture defects; they do not fill independent coverage or prove broader transport correctness.

## L6 Admission

`pr868-l6-20260924-0026` is BLOCKED_PREFLIGHT_COVERAGE. The strict module invocation exited 1 with no deadline overrun but four `target_phase_not_exercised` gaps: `headers_then_body`, `tools_stream_partial_line`, `judge_window_stalls`, `judge_late_report`. Its earlier direct-file import failure is retained separately.

There were zero natural submissions, zero real model requests, no frozen data, no retrieval readiness run and no sidecar. Mechanical currency regression and fake-upstream proxy checks passed only in their own categories. Old natural NOT_PASSED outcomes remain unchanged.

The formal generated live runner was subsequently found to check only deadline violations, not coverage gaps. The outer invocation had prevented submission in this batch. `c315cfdaa` binds the final entry to a complete, current, clean strict receipt and recomputes both coverage and timing. That later change is not retroactive validation of this batch.

## Storage And Boundaries

`archive-manifest.json` maps each of the 208 archived artifacts to its original path, original SHA-256 and stored SHA-256. Eight originals with whitespace rejected by Git's format gate use reversible base64 JSON envelopes; decoded bytes were checked against the originals. No original was trimmed or rewritten. `copied-test-audit.json` is a newly derived host audit, not an original reviewer artifact.

Private model reasoning, credentials, copied repositories, virtual environments and databases are not included. Local full evidence remains under `/Users/a77/.finance-runtime/reviews/`. Cleanup removed only completed-run generated pytest temporary fixtures, not source, receipts or review evidence. Production port 8792 was not mutated; no seven-field production-identity comparison is claimed for these preflight-only batches.

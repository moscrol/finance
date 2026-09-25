# Host validation of review-a probe defects

Original K3 files, report, first-red JUnit and command records remain unchanged under review-a. Copies here are host-modified probes and cannot replace independent reviewer acceptance.

Observed first-red causes: C1 tree fence supplied object() without phase; C2 copied recursively frozen mappingproxy using deepcopy. The K3 report inaccurately grouped the C1 error with mappingproxy errors and stated exploration stopped before request 24; request admissions show 31 exploration requests followed by a report request due to the time boundary.

The vacuous `internal_locator is not None or True` assertion in C2 is rejected and replaced with an exact evidence roundtrip assertion. No product code changes.

Results (`verification.json`): baseline-2 17P, C1 withdrawal 1 named failure/16P, restored 17P; strengthened baseline-3 17P, C2 withdrawal 1 named DID NOT RAISE/16P, restored-3 17P. Original K3 report hash and candidate identity remain unchanged.

Rejected intermediate runs remain on disk: baseline-1 failed before tests because the host omitted a writable TMPDIR under the sandbox; mutation-c2 changed only the error text while another protection still rejected the payload. The stronger C2 counterexample changes admitted and presented titles consistently, so withdrawing the digest check actually permits tampered data. These are host witnesses, not independent approval.

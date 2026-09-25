# Execute Stage — PR813 QC (revision ae3f812e1c1e142953b657ba41f30fce23e7c14a, candidate integrated from main 1751e21e0fd30642e0b223604b64b30e38c46f41)

## Positive control
Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/positive_control.py`
Raw result: exit code 1, traceback ending `AssertionError: intentional probe_bug control`.
Observed: as expected (intentional probe_bug).

## Direct pytest invocation (single run, JUnit authoritative)
Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workbench-private/.venv-workbench/bin/python -B -m pytest -q <three probe files> --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work -p no:cacheprovider --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probe-results-all.xml --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/tmp/reviewer`

Raw output tail: `2 failed, 23 passed in 11.33s`, exit code 1.

Counts (transcribed from raw pytest output / probe-results-all.xml):
- executed: 25
- passed: 23
- failed: 2
- errors: 0
- skipped: 0

Failing cases (both host-authored, test_production_contract.py):
1. test_real_date_parent_rehearsal_and_numeric_contract — subprocess rehearse_302132_backfill.py exited 1 with `ValueError: rehearsal requires a clean committed checkout`.
2. test_low_space_refuses_before_database_copies — rehearsal.run raised `ValueError: rehearsal requires a clean committed checkout` before reaching the low-space check.

Per-file (from raw output class markers): test_seeded_c3.py 7 passed; test_earlier_fixture_adapter.py 3 passed; test_production_contract.py 13 passed / 2 failed (15 host-authored cases).

C6 note (disclosure only, per instruction): this batch did not include the three copied author test body invocations; the C6 host-authored regression witnesses are part of the supplied probe set as described in provenance. No standalone author pytest invocation was run in this stage.

## Supplied provenance
- Probe files (supplied evidence, not newly authored; unedited, no wrappers, no reruns):
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probes/test_seeded_c3.py (7 prior-reviewer cases, host fixture fixes)
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probes/test_earlier_fixture_adapter.py (3 prior-reviewer cases, host fixture fixes; 10 combined, not 10 each)
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probes/test_production_contract.py (15 host-authored cases: real-date CLI apply/verify/rollback, source refusals, preflight, OS scope witnesses, host receipt consistency)
- JUnit XML: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probe-results-all.xml
- Real-date fixture: verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar, not full production.
- Host full-copy rehearsal at /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/inputs/host-rehearsal is audit-only (not reviewer execution).
- No production access, credentials, network, deployment, or git mutation. Writing confined to quality/work.

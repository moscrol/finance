# EXECUTE receipt — PR813 QC, revision ae3f812e1c1e142953b657ba41f30fce23e7c14a

## Positive control
Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-18/quality/work/positive_control.py`
Observed: exit code 1, `AssertionError: intentional probe_bug control` — matches expected intentional failure.

## Pytest batch (single invocation)
Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q .../test_seeded_c3.py .../test_earlier_fixture_adapter.py .../test_production_contract.py --rootdir=.../work -p no:cacheprovider --junitxml=.../probe-results-all.xml --basetemp=.../tmp/reviewer`

Raw tail: `25 passed in 36.40s` — JUnit XML at /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-18/quality/work/probe-results-all.xml is authoritative.

Counts (transcribed from raw output): executed 25, passed 25, failed 0, errors 0, skipped 0.
Breakdown: test_seeded_c3.py 7 + test_earlier_fixture_adapter.py 3 (combined 10 prior-reviewer cases with host fixture fixes) + test_production_contract.py 15 host-authored cases = 25.

## Supplied provenance
- Supplied pytest entrypoints (not newly authored by this reviewer):
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-18/quality/work/probes/test_seeded_c3.py (7 cases)
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-18/quality/work/probes/test_earlier_fixture_adapter.py (3 cases)
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-18/quality/work/probes/test_production_contract.py (15 host-authored cases: real-date CLI apply/verify/rollback, source refusals, preflight, OS scope witnesses, host receipt consistency)
- C6: three copied author test bodies run twice (candidate and external scope-mutant) inside three host-authored regression witnesses — six body invocations total; no standalone author pytest invocation.
- Real-date fixture: verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar, not full production.
- Host full-copy rehearsal at /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-18/quality/inputs/host-rehearsal is audit-only.
- Candidate: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-18/candidate; integration of main 1751e21e0fd30642e0b223604b64b30e38c46f41.

## Limits
- No claims adjudicated in this stage; execute receipt only.
- Engineering receipts still running are not a QC fact.

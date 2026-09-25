# EXECUTE Receipt — PR813 QC, Revision ae3f812e1c1e142953b657ba41f30fce23e7c14a

## Positive control
- Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-16/quality/work/positive_control.py`
- Result: exit code 1, `AssertionError: intentional probe_bug control` — as expected.

## Probe batch (single invocation, no rerun)
- Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q <three probe files> --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-16/quality/work -p no:cacheprovider --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-16/quality/work/probe-results-all.xml --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-16/quality/work/tmp/reviewer`
- Raw output: `25 passed in 34.97s` (all dots, [100%])
- Counts (from raw output; JUnit XML authoritative): executed 25, passed 25, failed 0, errors 0, skipped 0.

## Supplied provenance
- Supplied pytest entrypoints (not reviewer-authored):
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-16/quality/work/probes/test_seeded_c3.py (prior-reviewer, 10 cases)
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-16/quality/work/probes/test_earlier_fixture_adapter.py (prior-reviewer, 10 cases)
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-16/quality/work/probes/test_production_contract.py (host-authored, 15 cases)
- C6 executes three copied author test bodies twice (candidate and external scope-mutant) inside three host-authored regression witnesses: six author body invocations total, no standalone author pytest invocation.
- Real-date fixture contains verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar; not full production data.
- Host full-copy rehearsal in /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-16/quality/inputs/host-rehearsal is audit-only.
- Integration baseline: main 1751e21e0fd30642e0b223604b64b30e38c46f41.

## Notes
- No supplied tests edited; no wrappers added; no reruns; no network/production/git access.

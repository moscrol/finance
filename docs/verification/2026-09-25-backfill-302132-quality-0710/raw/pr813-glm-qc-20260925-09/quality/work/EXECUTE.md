# EXECUTE log — PR #813 C3 bounded QC (revision 3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59)

## Positive control (first bash)
Command (exact):
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/positive_control.py`
Result: exit code 1, traceback ending `AssertionError: intentional probe_bug control`. Raw files: execute/001-bash/*.

## Syntax check
`python -B -m py_compile` on both supplied test files: clean, no output.

## Supplied pytest run (direct, single command, exact required args)
- pytest 8.3.5, rootdir=.../quality/work, both supplied test paths, --junitxml=.../probe-results-supplied.xml, --basetemp=.../tmp/supplied
- Outcome: **collected 0 items / 2 collection ERRORS**, exit code 2, session interrupted.
- Both errors are `PermissionError: [Errno 1] Operation not permitted: '/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate/tests/test_repair_backfill_stock_history.py'`.
- Cause: both supplied suites (probe_c3_acceptance_v2.py via test_seeded_c3.py, and test_new_c3_v1.py via test_earlier_fixture_adapter.py) hardcode `CAND = .../pr813-glm-qc-20260925-06/candidate`, a prior review's directory. This session's sandbox permits reads only under the `-09` review root (confirmed separately: `ls .../pr813-glm-qc-20260925-06/candidate/scripts` → "Operation not permitted").
- Per contract, supplied files were not modified; no helper files or wrapper scripts were created; no author tests run.

## Counts observed from this run
- Supplied suites: 0 passed, 0 failed, 2 collection errors (10 test items never executed: 7 seeded + 3 adapter).
- Author tests: 0 run by reviewer.

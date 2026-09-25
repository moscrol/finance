# EXECUTE — C3 quality review (PR #813, rev 3c5b3c9a, baseline 4cc15e70)

## Positive control
First bash call (raw logs in execute/001-bash/): exact command
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B .../quality/work/positive_control.py`
exit code 1, traceback text `intentional probe_bug control`. Control observed.

## Supplied probes
- Syntax check: py_compile of both supplied test files — OK (no output).
- Direct pytest run (no wrapper, both supplied paths, required rootdir/junitxml/basetemp):
  10 passed, 0 failed, 0 errors in 16.94s.
  - test_seeded_c3.py: 7/7 passed (6 outside-window mutation cases + baseline_pass)
  - test_earlier_fixture_adapter.py: 3/3 passed (earlier_than_window, null_column, baseline_with_earlier_row_pass)
- XML: work/probe-results-supplied.xml (preserved).

## Findings
- All 7 prior C3 assertions verified: the actual external acceptance entry
  (candidate verify_302132_backfill_acceptance.py, not only the helper) rejects amount,
  timestamp, delete, insert, duplicate (clone-only PK removal disclosed), and other_stock
  mutations outside the window, and passes on the unmodified baseline.
- All 3 new assertions with the host-only pre-window fixture adapter verified, including
  a real pre-window row added to both baseline and clone with rebound receipt hashes;
  baseline with the earlier row still passes. Clone-only PK removal disclosed in duplicate case.

## Limits
- No author tests executed (author_test_counts all zero by contract).
- Production-shaped 64/39/161 counts remain a separate limitation; not directly observed here.
- Synthetic DuckDB inside work only; no production/vendor/network access.
- Supplied probes are prior reviewer assertions plus host fixture repairs; provenance is
  prior-reviewer assertions, re-executed fresh in this session — not prior verdicts.

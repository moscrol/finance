# EXECUTE — PR #813 C3 (rev 3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59, baseline 4cc15e703f81bce8abadee00f68caacdb0c72b4d)

## Positive control (first bash, controller-enforced)
Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B .../quality/work/positive_control.py`
Result: exit code 1, `AssertionError: intentional probe_bug control` — observed in session output and raw execute/001-bash logs.

## Syntax check
`ast.parse` OK on both supplied probe files (test_seeded_c3.py, test_earlier_fixture_adapter.py).

## Supplied probe run
Single pytest command, both supplied files, rootdir=work, fresh XML `probe-results-supplied.xml`, basetemp `work/tmp/supplied`.
Result: **10 passed, 0 failed, 0 errors** in 13.56s.
- test_seeded_c3.py: 7 passed (outside-window mutations amount/timestamp/delete/insert/duplicate/other_stock fail acceptance; baseline passes)
- test_earlier_fixture_adapter.py: 3 passed (earlier-than-window and null-column mutations fail; baseline with real pre-window row passes)

Both suites drive the actual external acceptance entry (scripts/verify_302132_backfill_acceptance.py), not only a helper. Duplicate cases disclose clone-only PK removal.

## Probe provenance
Probes are prior reviewer assertions plus host fixture repairs (receipt-path/OTHER-date repair in test_seeded_c3.py; host-only fixture repair adding a real pre-window row to both baseline and clone and rebinding receipt hashes in test_earlier_fixture_adapter.py). Executed fresh in this session; supplied evidence, not new authoring.

## Counts
- reviewer_probe_counts: passed=10, failed=0, errors=0
- author_test_counts: passed=0, failed=0, errors=0 (none run, per instruction)
- supplied_probe_counts: files=2, cases=10, all passed

## Findings
- All outside-window mutation probes are correctly rejected by the candidate's acceptance verification; baseline passes.
- Pre-window row adapter confirms candidate behavior with realistic earlier data.

## Limits
- Production-shaped 64/39/161 counts remain a separate limitation unless directly observed; not observed here.
- No git/network/live vendors/production DB; synthetic DuckDB in work only.

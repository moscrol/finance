```json
{
  "author_test_counts": {
    "errors": 0,
    "executed": 0,
    "failed": 0,
    "passed": 0,
    "skipped": 0
  },
  "claims": [
    {
      "evidence": "Out of scope for this C3-only quality axis.",
      "id": "C1",
      "status": "out_of_scope"
    },
    {
      "evidence": "Out of scope for this C3-only quality axis.",
      "id": "C2",
      "status": "out_of_scope"
    },
    {
      "evidence": "All 7 prior C3 assertions and all 3 prior new assertions executed fresh in this session against the actual external acceptance entry (candidate scripts/verify_302132_backfill_acceptance.py): 10 passed / 0 failed / 0 errors (execute/003-bash, probe-results-supplied.xml). Outside-window amount, timestamp, delete, insert, duplicate (clone-only PK removal disclosed), other_stock, earlier_than_window, and null_column mutations all rejected with verdict FAIL and target_outside_window_allcols / fact_other_stocks_allcols in failed checks; unmodified baseline and baseline with added pre-window row both PASS. However, the production-shaped 64/39/161 numeric behavior was not directly observed in this bounded synthetic review, so C3 as a whole remains not_verified.",
      "id": "C3",
      "status": "not_verified"
    },
    {
      "evidence": "Out of scope for this C3-only quality axis.",
      "id": "C4",
      "status": "out_of_scope"
    },
    {
      "evidence": "Out of scope for this C3-only quality axis.",
      "id": "C5",
      "status": "out_of_scope"
    },
    {
      "evidence": "Out of scope for this C3-only quality axis.",
      "id": "C6",
      "status": "out_of_scope"
    },
    {
      "evidence": "Out of scope for this C3-only quality axis.",
      "id": "C7",
      "status": "out_of_scope"
    }
  ],
  "findings": [],
  "limits": [
    "Production-shaped 64/39/161 counts were not directly observed; C3 remains not_verified on that numeric limitation.",
    "No author tests executed; author_test_counts all zero by contract.",
    "Synthetic DuckDB inside work only; no production, vendor, network, or credential access.",
    "Supplied probes are prior reviewer assertions plus host fixture repairs (receipt-path/OTHER-date repair; pre-window fixture adapter with rebound receipt hashes), re-executed fresh in this session — supplied evidence, not prior verdicts; duplicate case discloses clone-only PK removal.",
    "No deployment, merge, approval, or production access requested or performed."
  ],
  "positive_control": {
    "classification": "probe_bug",
    "evidence": "execute/001-bash/request.json shows the exact command OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/positive_control.py; execute/001-bash/result.json shows exitCode 1; execute/001-bash/output.log shows the traceback with 'intentional probe_bug control'.",
    "status": "OBSERVED_EXPECTED_FAILURE"
  },
  "probe_provenance": "test_seeded_c3.py: seven prior-reviewer C3 assertions with receipt-path/OTHER-date host fixture repairs (adapts probe_c3_acceptance_v2.py, fixture setup derived from author _build_e2e_artifacts but assertions are the reviewer's own). test_earlier_fixture_adapter.py: three prior new assertions with a host-only fixture repair adding a real pre-window row to both baseline and clone and rebinding receipt hashes. Both suites invoke the actual external acceptance entry (candidate scripts/verify_302132_backfill_acceptance.py), not merely a helper; duplicate cases disclose clone-only PK removal. Supplied probes are prior reviewer assertions plus host fixture repairs, not prior verdicts; executed fresh in this session; supplied files unmodified.",
  "reviewer_probe_counts": {
    "errors": 0,
    "executed": 10,
    "failed": 0,
    "passed": 10,
    "skipped": 0
  },
  "supplied_probe_counts": {
    "errors": 0,
    "executed": 10,
    "failed": 0,
    "passed": 10,
    "skipped": 0
  },
  "supplied_xml": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probe-results-supplied.xml",
  "verdict": "PASS_WITH_LIMITS",
  "complete": true,
  "stage": "report",
  "axis": "quality",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}
```

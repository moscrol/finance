```json
{
  "author_test_counts": {
    "executed": 0,
    "failed": 0,
    "skipped": 0,
    "passed": 0,
    "note": "C6 copied author test bodies (six invocations across candidate and scope-mutant inside three host-authored regression witnesses) are part of the supplied probe set; no standalone author pytest invocation was run in this stage"
  },
  "findings": [
    {
      "detail": "Both failures raise ValueError: rehearsal requires a clean committed checkout at rehearse_302132_backfill.py:78 (candidate/scripts/review_probes/rehearse_302132_backfill.py), aborting before the low-space check in the second case; no correction or rerun performed per rules",
      "evidence": "Raw pytest traceback; JUnit /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probe-results-all.xml",
      "id": "F1",
      "severity": "major",
      "title": "Two host-authored real-date rehearsal cases failed: clean-checkout guard fires in review sandbox"
    }
  ],
  "limits": [
    "Any failing case rules out PASS_WITH_LIMITS for this batch (2 failed)",
    "Batch failed; no rerun permitted",
    "Real-date fixture is partial (302132.SZ, sentinel 000001.SZ, market calendar), not full production",
    "Host full-copy rehearsal at /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/inputs/host-rehearsal is audit-only, not reviewer execution",
    "C7 code binding separate from engineering readiness; engineering receipts are not reviewer execution"
  ],
  "positive_control": {
    "command": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workbench-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/positive_control.py",
    "expected": "exit 1 with intentional probe_bug text",
    "observed": "exit code 1; AssertionError: intentional probe_bug control",
    "status": "as_expected"
  },
  "probe_provenance": {
    "candidate": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/candidate",
    "claims": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/inputs/claims.md",
    "fixture_scope": "verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar, not full production",
    "host_rehearsal_audit_only": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/inputs/host-rehearsal",
    "integration_main": "1751e21e0fd30642e0b223604b64b30e38c46f41",
    "revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
    "supplied_evidence_not_reviewer_authored": true
  },
  "reviewer_probe_counts": {
    "errors": 0,
    "executed": 25,
    "failed": 2,
    "passed": 23,
    "skipped": 0
  },
  "supplied_probe_counts": {
    "per_file": {
      "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probes/test_earlier_fixture_adapter.py": {
        "errors": 0,
        "executed": 3,
        "failed": 0,
        "passed": 3,
        "skipped": 0
      },
      "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probes/test_production_contract.py": {
        "errors": 0,
        "executed": 15,
        "failed": 2,
        "passed": 13,
        "skipped": 0
      },
      "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probes/test_seeded_c3.py": {
        "errors": 0,
        "executed": 7,
        "failed": 0,
        "passed": 7,
        "skipped": 0
      }
    },
    "prior_reviewer_cases_combined": 10
  },
  "supplied_xml": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probe-results-all.xml",
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probes/test_seeded_c3.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probes/test_earlier_fixture_adapter.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-20/quality/work/probes/test_production_contract.py"
  ],
  "complete": true,
  "stage": "execute",
  "axis": "quality",
  "revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
  "baseline": "1751e21e0fd30642e0b223604b64b30e38c46f41"
}
```

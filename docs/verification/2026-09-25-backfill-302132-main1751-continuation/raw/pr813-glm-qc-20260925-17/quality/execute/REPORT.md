```json
{
  "author_test_counts": {
    "errors": 0,
    "executed": 6,
    "failed": 0,
    "passed": 6,
    "skipped": 0
  },
  "findings": [
    "Positive control behaved as designed: AssertionError 'intentional probe_bug control', exit code 1.",
    "All 25 supplied probe cases passed in a single direct pytest invocation (42.58s): 7 (test_seeded_c3.py) + 3 (test_earlier_fixture_adapter.py) + 15 (test_production_contract.py).",
    "C6: three copied author test bodies each invoked twice (candidate and external scope-mutant) inside three host-authored regression witnesses — six author body invocations, all passing; no standalone author pytest invocation performed.",
    "JUnit XML written to /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/probe-results-all.xml; authoritative counts: 25 passed, 0 failed, 0 errors, 0 skipped.",
    "No supplied tests were edited, no wrappers added, no reruns after failure (no failures occurred)."
  ],
  "limits": [
    "Real-date fixture contains verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar only, not full production data.",
    "Host full-copy rehearsal in /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/inputs/host-rehearsal is audit-only and not treated as executed evidence.",
    "Engineering receipts still running are not a QC fact; C7 code binding is separate from full engineering readiness.",
    "Claims evaluation (C1-C7 statuses/verdict) is deferred to the report stage; this stage is an execution receipt only."
  ],
  "positive_control": {
    "command": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/positive_control.py",
    "evidence": "AssertionError: intentional probe_bug control traceback; exit code 1 (raw, as required)",
    "expected": "exit 1 with intentional probe_bug text",
    "observed": "exit_code=1, error_text='intentional probe_bug control'",
    "status": "as_expected"
  },
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/probes/test_seeded_c3.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/probes/test_earlier_fixture_adapter.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/probes/test_production_contract.py"
  ],
  "probe_provenance": {
    "author_test_bodies": "Three copied author test bodies from PR813, executed twice each (candidate scope and external scope-mutant) inside three host-authored regression witnesses in test_production_contract.py; six body invocations total, disclosed separately; no standalone author pytest invocation.",
    "candidate": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/candidate",
    "claims_input": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/inputs/claims.md",
    "host_rehearsal": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/inputs/host-rehearsal (audit-only)",
    "main_integration": "1751e21e0fd30642e0b223604b64b30e38c46f41",
    "real_date_fixture": "Verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar; not full production.",
    "revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
    "supplied_evidence_note": "Probes are supplied prior-reviewer and host-authored evidence with host fixture fixes; not newly authored by this reviewer; not edited; no wrappers; single invocation; no reruns."
  },
  "reviewer_probe_counts": {
    "errors": 0,
    "executed": 22,
    "failed": 0,
    "passed": 22,
    "skipped": 0
  },
  "supplied_probe_counts": {
    "combined": {
      "errors": 0,
      "executed": 10,
      "failed": 0,
      "passed": 10,
      "skipped": 0
    },
    "host_authored": {
      "errors": 0,
      "executed": 15,
      "failed": 0,
      "passed": 15,
      "skipped": 0
    },
    "prior_reviewer": {
      "errors": 0,
      "executed": 10,
      "failed": 0,
      "passed": 10,
      "skipped": 0
    }
  },
  "supplied_xml": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/probe-results-all.xml",
  "complete": true,
  "stage": "execute",
  "axis": "quality",
  "revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
  "baseline": "1751e21e0fd30642e0b223604b64b30e38c46f41"
}
```

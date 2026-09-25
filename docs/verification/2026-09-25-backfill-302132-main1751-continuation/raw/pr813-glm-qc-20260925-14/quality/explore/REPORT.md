```json
{
  "claims_examined": [
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C7"
  ],
  "limits": [
    "No tests or positive control observed yet."
  ],
  "next_stage_command": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-14/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-14/quality/work/probes/test_earlier_fixture_adapter.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-14/quality/work/probes/test_production_contract.py --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-14/quality/work -p no:cacheprovider --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-14/quality/work/probe-results-all.xml --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-14/quality/work/tmp/reviewer",
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-14/quality/work/probes/test_seeded_c3.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-14/quality/work/probes/test_earlier_fixture_adapter.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-14/quality/work/probes/test_production_contract.py"
  ],
  "provenance": "All tests supplied. 10 prior-reviewer assertions plus 14 host-authored tests. No execution in explore.",
  "complete": true,
  "stage": "explore",
  "axis": "quality",
  "revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
  "baseline": "1751e21e0fd30642e0b223604b64b30e38c46f41"
}
```

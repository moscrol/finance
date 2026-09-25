# EXECUTE Receipt — PR813 QC (revision ae3f812e1c1e142953b657ba41f30fce23e7c14a)

## Positive control
Command: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/positive_control.py
Observed: AssertionError: intentional probe_bug control; exit code 1. Expected intentional failure confirmed.

## Probe batch (single direct invocation)
Command: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q <three supplied probe entrypoints> --rootdir=.../quality/work -p no:cacheprovider --junitxml=.../quality/work/probe-results-all.xml --basetemp=.../quality/work/tmp/reviewer
Raw output: 25 passed in 42.58s (25 dots, [100%])
JUnit XML: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/probe-results-all.xml (authoritative)

Counts:
- executed: 25
- passed: 25
- failed: 0
- errors: 0
- skipped: 0

Breakdown:
- test_seeded_c3.py: 7 supplied prior-reviewer cases (with host fixture fixes)
- test_earlier_fixture_adapter.py: 3 supplied prior-reviewer cases (with host fixture fixes)
- test_production_contract.py: 15 host-authored cases (real-date CLI apply/verify/rollback, source refusals, preflight, OS scope witnesses, host receipt consistency)
- C6: three copied author test bodies invoked twice each (candidate and external scope-mutant) inside three host-authored regression witnesses — six body invocations total, disclosed separately; no standalone author pytest invocation.

## Supplied provenance
- Entrypoints (supplied evidence, not newly authored; not edited, no wrappers, no reruns):
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/probes/test_seeded_c3.py
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/probes/test_earlier_fixture_adapter.py
  - /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/work/probes/test_production_contract.py
- Candidate: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/candidate (revision ae3f812e1c1e142953b657ba41f30fce23e7c14a; clean integration of main 1751e21e0fd30642e0b223604b64b30e38c46f41)
- Real-date fixture: verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar; not full production data.
- Host full-copy rehearsal at /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/inputs/host-rehearsal is audit-only; not treated as executed evidence here.
- Claims input: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-17/quality/inputs/claims.md (claims evaluation deferred to report stage).

## Notes / limits
- Single pytest invocation; no retries; no rerun of failed cases (none failed).
- Numeric counts transcribed from raw pytest output and JUnit XML; JUnit is authoritative.
- Engineering receipts still running are not a QC fact; C7 code binding evaluated separately in report stage.

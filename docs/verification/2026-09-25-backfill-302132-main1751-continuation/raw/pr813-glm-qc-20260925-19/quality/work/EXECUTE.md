# EXECUTE Receipt — PR813 QC (revision ae3f812e1c1e142953b657ba41f30fce23e7c14a)

## Positive control
Command: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/positive_control.py
Observed: exit code 1, AssertionError "intentional probe_bug control" — as expected.

## Direct pytest batch (single invocation)
Command (as specified) run once; no rerun.
Raw output: `.........................  [100%]` — 25 passed in 17.02s
JUnit: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probe-results-all.xml

Counts (from raw output / JUnit):
- executed: 25
- passed: 25
- failed: 0
- errors: 0
- skipped: 0

## Supplied provenance
- test_seeded_c3.py: 7 prior-reviewer cases (host fixture fixes)
- test_earlier_fixture_adapter.py: 3 prior-reviewer cases (host fixture fixes)
- Combined prior-reviewer cases: 10 (not 10 each)
- test_production_contract.py: 15 host-authored cases (real-date CLI apply/verify/rollback, source refusals, preflight, OS scope witnesses, host receipt consistency)
- C6: three copied author test bodies each run twice (candidate + external scope-mutant) inside three host-authored regression witnesses → six body invocations, disclosed separately; no standalone author pytest invocation.
- Supplied evidence only; no newly authored tests by this reviewer. Supplied tests unedited; no wrappers added; no failed pytest rerun.

## Notes / limits
- Real-date fixture contains verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar, not full production.
- Host full-copy rehearsal (inputs/host-rehearsal) is audit-only; not reviewer execution.
- Numeric values above come from execution only.
- This is the execution receipt stage; claim evaluation deferred to report stage.

# QC probe C3 (PR #813) — acceptance oracle for outside-window rows

## Scope
Only C3. Challenge the actual external acceptance entry
`candidate/scripts/verify_302132_backfill_acceptance.py::main -> _data_checks`
(not just writer `_accept`).

## Probe
`work/probes/probe_c3_acceptance.py` (single pytest file). Reuses fixture helper
`tests/test_repair_backfill_stock_history.py::_build_e2e_artifacts` (synthetic
DuckDB, module-level import via importlib spec_from_file_location, registered in
sys.modules before exec_module) and its `_run_acceptance` command shape. ALL
assertions are the reviewer's own; author test bodies are not executed and author
result claims are not reused.

Mutations applied to an OUTSIDE-window row (date 2026-09-22 inserted into BOTH
baseline and clone first, receipts' backup sha updated — same mechanics as the
author fixture):
- `none` → baseline must PASS (rc=0, verdict PASS, failed==[])
- `amount` (+1), `timestamp` (updated_at change), `delete`, `insert` (2026-09-23
  duplicate of same stock), `duplicate` (exact copy of 2026-09-22 row in clone
  only — needs PK dropped via clone-only `CREATE TABLE AS SELECT` rebuild;
  DISCLOSED: this removes the PK constraint so a true duplicate can exist; the
  real DB PK would itself block duplicates, so this is an adversarial oracle
  probe, not a realistic production state), `other_stock` (amount mutation on
  000001.SZ row) → each must FAIL with rc=2, structured FAIL JSON, and the
  specific data check (`target_outside_window_allcols` or
  `fact_other_stocks_allcols`) in `failed`.

## Commands (exact)
- Execute:
  `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py -q --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.xml`
- Positive control (intentional control): same file with
  `--control=positive` via env `QC_POSITIVE_CONTROL=1` (a deliberately broken
  expectation asserts a FAIL check that actually passes) — must FAIL, proving
  the harness can detect green-when-should-be-red.

## Known limits
- Synthetic fixture only; no production copy run (not authorized).
- Author's `window 64 rows / technical39 / window161` specific counts are the
  real-revision shape; synthetic fixture has different calendar, so those
  numeric counts are not independently reproduced here.
- Duplicate-multiplicity probe requires removing PK in the clone only.

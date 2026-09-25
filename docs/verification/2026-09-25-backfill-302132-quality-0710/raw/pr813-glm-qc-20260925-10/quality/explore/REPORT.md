```json
{
  "claims_examined": [
    "C3: Acceptance oracle evaluates retained rows (row count = expected_total_rows - authorized keyset count) inside the authorized window with full-column equality via SELECT * ORDER BY trade_date comparison; target rows outside the window and other stocks retain ALL columns via bidirectional EXCEPT ALL (xa fwd/rev) multiset semantics on the full column list derived from PRAGMA table_info — lines 540-728 of scripts/verify_302132_backfill_acceptance.py",
    "C3: Mutation detection beyond row counts — amount is checked in the keyset full-field oracle (abs(r[8]-amt)<1e-9 with Decimal re-derivation from frozen parquet/baseline source), deletion/insertion asymmetry is caught by bidirectional EXCEPT ALL multiset diffs, timestamps by protected-slice all-column comparisons including calculated_at and updated_at (retained rows via SELECT *); keyset_fullfield_oracle additionally requires len(rows)==len(write_keys)",
    "C3 window-after-apply counts (64 rows; close/pct_chg/amount each 64 nonnull; technical 39; window 161): the script checks window_golden_triples, technical_exact_set (cal64[25:] = technical 39 if calendar in-window has 64 dates), expected_window_counts/expected_technical_count binding, and pinned 09-11 values; the 64/39/161 production-shaped counts are NOT hardcoded in the script — they derive from spec and the baseline market calendar, so their direct observation is deferred to the supplied probes/artifacts and remains a stated limitation",
    "C1, C2, C4, C5, C6, C7: out_of_scope for this C3-only axis"
  ],
  "limits": [
    "No bash execution, no file writes, no new assertions, and no test runs occurred in this explore stage",
    "The supplied probe files were intentionally NOT read in this stage; their paths and provenance are fixed inputs carried forward to execute",
    "The production-shaped 64/39/161 counts were not directly observed here; they remain a separate limitation unless observed during execute",
    "Positive control gate requires the exact first execute command (OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .../python -B .../positive_control.py) with exit code 1 and probe_bug text; not yet performed",
    "All claims except C3 are out_of_scope per axis isolation"
  ],
  "next_stage_commands": [
    {
      "bash": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/positive_control.py",
      "purpose": "mandatory first execute command; must exit 1 with probe_bug text"
    },
    {
      "bash": "/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_earlier_fixture_adapter.py",
      "purpose": "execute the ten supplied probe cases (7 seeded C3 + 3 earlier fixture-adapter) against the external acceptance entry in a fresh synthetic DuckDB work root; do not modify supplied files"
    }
  ],
  "positive_control": "planned and not yet executed; mandatory exact first command for execute stage per controller contract",
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_seeded_c3.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_earlier_fixture_adapter.py"
  ],
  "probe_provenance": "test_seeded_c3.py: seven prior-reviewer C3 assertions with receipt-path/OTHER-date host fixture repairs. test_earlier_fixture_adapter.py: three prior new assertions with a host-only fixture repair adding a real pre-window row to both baseline and clone and rebinding receipt hashes. Both suites invoke the actual external acceptance entry (candidate scripts/verify_302132_backfill_acceptance.py), not merely a helper; duplicate cases disclose clone-only PK removal. Supplied probes are prior reviewer assertions plus host fixture repairs, not prior verdicts; they must be executed fresh in this session with provenance kept explicit. Supplied files must not be modified.",
  "statement": "Explore only: read claims.md, source-map.md, and the candidate's precise _data_checks implementation; no tests ran in this stage",
  "complete": true,
  "stage": "explore",
  "axis": "quality",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}
```

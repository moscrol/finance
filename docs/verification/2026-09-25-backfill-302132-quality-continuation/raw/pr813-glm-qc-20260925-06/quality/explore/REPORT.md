```json
{
  "claims_examined": {
    "absent_claims_map": "candidate/claims/source-map (and .md) not found; C3 verification scope taken directly from _data_checks implementation and its docstring claims",
    "c3_data_contract_checks": [
      "fact_other_stocks_allcols (bidirectional EXCEPT ALL, all columns)",
      "retained_rows_full_column_identical (in-window non-key rows incl. updated_at, count == expected_total_rows - |write_keys|)",
      "target_outside_window_allcols",
      "hithink_source_untouched / hithink_adjustment_untouched (whole-table bidirectional)",
      "parallel_source_md5_binding (recomputed from prod. baseline, bound to both receipts' child reports)",
      "keyset_fullfield_oracle (parallel rows read from prod. baseline, parquet rows from frozen file; OHLC/pre_close/pct_chg/amount/turnover==None/volume/source-label recomputed with Decimal quantization; expected_retained == spec.expected_total_rows - len(write_keys))",
      "technical_protected_allcols / window_protected_allcols",
      "window_golden_triples + expected_window_counts_match_golden",
      "technical_exact_set (cal64[25:]) + expected_technical_count_matches_calendar",
      "pinned_technical_target_day / pinned_windows_target_day",
      "market_daily_untouched"
    ]
  },
  "gating": "data checks only run when preflight_ok and args_ok and schema_ok and spec is dict; exceptions funnel into data_checks_error structured FAIL (rc=2); final verdict rc 0/2; production sha checked before and after (TOCTOU)",
  "notes_on_prior_c3_focus": "retained-row definition (write_keys = gap_parallel | gap_parquet | shell_date) is the central C3 lever; pre-window rows (before window_start) are covered only by target_outside_window_allcols; oracle reads source rows from prod. baseline (input-independence discipline)",
  "file": "candidate/scripts/verify_302132_backfill_acceptance.py, _data_checks (lines ~567-732), read in full alongside main() and _validate_receipt",
  "imprecision_risks": [
    "cal bounded below by hardcoded '2026-06-01' in market-calendar query — limits golden-triple derivation if window_start predates that bound",
    "src dict uses first-wins on duplicate trade_date (UNION ALL collision between parallel and parquet sources silently favors parallel rows)",
    "pre_close/pct oracle tolerance 1e-9 on floats after Decimal quantize; turnover hard-required None in keyset rows"
  ],
  "target_checks_location": "candidate/scripts/verify_302132_backfill_acceptance.py::_data_checks; gate at main() spec_ok branch",
  "tests_ran": false,
  "limits": [
    "claims/source-map absent at both attempted paths; claim list reconstructed from code docstring and implementation, not an author-supplied map",
    "No execution this stage: no bash, no probes run, no fixtures built; nothing verified empirically",
    "Files beyond the acceptance script not enumerated/read (stage restricted to _data_checks and claims map)",
    "Only C3 in scope; the production-shaped 64/39/161 counts remain a separate limitation unless directly observed"
  ],
  "next_stage_commands": [
    {
      "cmd": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/positive_control.py",
      "note": "mandatory first bash call in execute stage; expected exit 1 with probe_bug text",
      "seq": 1
    },
    {
      "cmd": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest --junitxml=<work>/execute/xml/test_seeded_c3.xml <work>/probes/test_seeded_c3.py",
      "note": "seven prior C3 assertions with receipt-path/OTHER-date fixture repair; uses actual external acceptance entry",
      "seq": 2
    },
    {
      "cmd": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest --junitxml=<work>/execute/xml/test_earlier_fixture_adapter.xml <work>/probes/test_earlier_fixture_adapter.py",
      "note": "three prior new assertions; host-only fixture repair adds real pre-window row to baseline and clone and rebinds receipt hashes; supplied evidence, not new authoring",
      "seq": 3
    }
  ],
  "probe_files": [
    {
      "path": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/probes/test_seeded_c3.py",
      "provenance": "prior reviewer C3 assertions + host fixture repair (receipt-path/OTHER-date); 7 cases; drives the actual external acceptance entry (scripts/verify_302132_backfill_acceptance.py), not only helpers; duplicate cases disclose clone-only PK removal"
    },
    {
      "path": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/probes/test_earlier_fixture_adapter.py",
      "provenance": "prior new assertions + host-only fixture repair adding a real pre-window row to both baseline and clone and rebinding receipt hashes; 3 cases; supplied evidence, not new authoring; also uses actual external acceptance entry"
    }
  ],
  "stage_scope": "C3 only; revision 3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59 vs baseline 4cc15e703f81bce8abadee00f68caacdb0c72b4d; current main d21707ca6c71e4e39194b01ef9549bc893595d3f not integrated",
  "complete": true,
  "stage": "explore",
  "axis": "quality",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}
```

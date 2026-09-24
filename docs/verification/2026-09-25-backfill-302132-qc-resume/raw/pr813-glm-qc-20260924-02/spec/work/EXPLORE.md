# EXPLORE.md — C2/C3 spec review probe plan (rev 3c5b3c9a, base 4cc15e70)

Scope: C2 (source guard upper bound, adjusted filtering, invalid/partial refusal) and C3
(oracle/source consistency arithmetic). C1/C4/C5/C6/C7 out_of_scope; no whole-candidate approval.

Source regions read (candidate/market_feature_store/sync/repair_backfill_stock_history.py):
- `_guard` 239-381 (live_parallel bounded by max(spec.gap_parallel); adjusted='none' filter;
  partial-state fail-closed; parquet sha check; src date-set == calendar checks)
- `_oracle_pct/_oracle_amount/_oracle_volume` 209-223, `_accept` 593-722 (oracle recompute, retained
  rows multiset via full-tuple comparison)
- tests fixture/spec (_fixture 71-162, _spec 165-217) read for fixture conventions only; assertions below are my own.

Probe: work/probes/test_guard.py — synthetic DuckDB (20-day calendar, code 999999.SZ):
1. later valid parallel history at a date > max(gap_parallel) must NOT cause false refusal (mode=apply)
   and retained snapshot contains only pre-existing main rows.
2. extra adjusted='qfq' rows (window gap date and beyond upper bound) are inert for the guard.
3. gap date present ONLY as qfq (missing 'none') refuses — adjusted filtering must not mask a gap.
4. missing gap_parallel source date refuses (partial state).
5. wrong parquet_sha256 refuses before any read.
6. C3 pure-oracle checks: half-up (not banker's) rounding, pre_close quantized before division,
   amount/volume scaling edges.

Exact command (one direct bash call, no chaining):
cd /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-02/spec/work && \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest probes/test_guard.py \
--confcutdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-02/spec/work \
-p no:cacheprovider \
--basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-02/spec/work/tmp/pytest -q

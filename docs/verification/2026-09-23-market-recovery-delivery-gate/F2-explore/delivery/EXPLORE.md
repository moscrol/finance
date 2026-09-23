# F2 explore — candidate 4dd5e66601084962697c5d78e9f6bb58eefc14c8

Scope probed: `compute_limit_stats_local(..., recovery_members=...)` refusal path in
`market_feature_store/sync/compute_local_stats.py`, and the pure `sector_coverage`
contract it delegates to. No author verdicts were supplied; no PASS declared.

## Probe design
Fresh `duckdb.connect(":memory:")` + `init_db(con)`; every call passes `con=con`.
Fixtures seed a published universe snapshot (`ops_sector_universe_snapshot_daily`
`status='published'` + `fact_sector_universe_daily` expected counts) and member
projection through `fact_sector_stock_daily_generation` keyed by that snapshot id,
per the documented VIEW behavior. Real candidate functions only; author tests not imported.

- **Valid control** — 1 sector, 2 declared members, both with canonical bars; M1
  closes at the 10% limit (`pre_close=10 -> close=11`), M2 flat, plus an outside-sector
  bar with a valid close. Asserts `action=="written"`,
  `denominator_basis=="frozen_identity"`, `market_limit_up==1`, and
  `ratio_denominator==2` (frozen identity, not observed rows). Confirms the path
  actually writes, so the adversarial refusal is meaningful rather than vacuous.
- **Adversarial (core subclaim)** — an **outside-sector** bar consumed by market
  counts carries an invalid close, parametrized `None, -1.0, 0.0, NaN, +inf`.
  Each of the four derived tables is pre-seeded with a `local:` row for TD; the call
  must raise `ValueError` and leave all four tables byte-for-byte unchanged
  (`COUNT` still 1). This directly tests "including outside-sector bars" and
  "refuse before changing any of four derived tables".
- **Adversarial (missing bar)** — declared member M2 has no `fact_stock_daily` bar;
  same pre-seed/unchanged assertion.

## What is tested
- Missing canonical member bar refuses before write.
- NULL / zero / negative / NaN / +inf canonical close refuses before write, even
  when the offending bar lies outside every declared sector.
- Refusal is non-destructive: no `DELETE FROM <derived>` fired (pre-seeded local
  rows survive), and no partial write.
- Valid control writes with the frozen-identity denominator.

## Untested subclaims (honest)
- `-inf` and other exotic invalid values not explicitly parametrized (only `+inf`).
- `recovery_nontrading` interaction beyond the value-error gate; the
  "nontrading identity has a stock bar" branch and `recovery_nontrading without
  recovery_members` guard are not exercised.
- Surplus/extra member rows and unknown-missing tolerance inside `sector_coverage`
  (surplus observed members, count-only mismatch) are not probed.
- Default daily path (no `recovery_members`), concurrency/atomicity across
  processes, and other `source`/force interactions are out of scope by the claim.
- Whether the four tables were untouched is verified via row counts of local
  sentinels, not a full checksum of pre-existing foreign rows.
- The probe has not been executed in this phase; results are not a verdict.

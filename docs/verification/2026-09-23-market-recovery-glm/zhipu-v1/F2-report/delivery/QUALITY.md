# F2 Quality Notes — candidate 50330cf (independent review)

## Verdict: PASS_WITH_LIMITS

The refusal core of F2 behaved exactly as claimed under independent, sandboxed,
in-memory DuckDB probes: every invalid canonical close variant (NULL, NaN, +inf,
-inf, 0.0, negative) on both a declared member and an outside-sector bar consumed
by market counts, plus a missing member bar and a nontrading identity with a bar,
raised `ValueError` with all four derived tables bit-for-bit equal at the logical
row level on both the target date 2026-09-03 and a distinct non-target date
2026-09-02. The frozen-denominator controls succeeded (`ratio_denominator=2`,
`denominator_basis='frozen_identity'`, written `total_count=(2,)` with a proven
nontrading identity kept in scope).

## Why limits, not plain PASS

1. **Temporal wording**: "refuse before changing" is verified as identical final
   logical rows; static reading shows all checks precede `BEGIN TRANSACTION`
   (compute_local_stats.py:228-252 vs :254-258), but the probe cannot distinguish
   "never touched" from "changed then rolled back".
2. **Partial claim coverage**: default daily path, other fields, and concurrency
   are out of scope by the claim itself and remain unexecuted by me; several
   `recovery_coverage` refusal branches (duplicate/malformed codes, sector-set
   mismatch, expected-count disagreement, surplus observed members) were not hit
   by my fixtures.
3. **Fixture breadth**: one sector, three instruments, one trade date topology.

## Harness integrity

- Positive control `test_intentional_red_probe_bug` (`assert 1 == 2`) failed as
  designed (exit 1) → classified **probe_bug**: it validates the runner's failure
  detection and is not a product defect.
- `inputs_unchanged: true`, `driver_unchanged: true`, no deadline hit, revision
  identical before/after execution.

## Risks / residual concerns

- Seeded rows use `source='local:seed'`; the foreign-row skip path was therefore
  never taken — a skip-instead-of-raise regression on this fixture would have
  failed loudly, which is the intended fail-loud design.
- Author tests (75 passed) are cited as counts only and add no independent
  certification weight here.
- The "refuse before write" guarantee for rows not seeded in the fixture (e.g.
  other tables outside the four) is outside F2's four-table scope.

## Scope of certification

Fixed revision 50330cf4fa435292bbd555ccc817e62ca5cc45b4 only. Main has advanced;
no merge admission, no full-repo acceptance, no production acceptance.

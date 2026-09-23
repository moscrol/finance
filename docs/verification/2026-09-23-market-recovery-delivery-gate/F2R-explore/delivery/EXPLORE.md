# F2 explore notes — candidate 4dd5e66

## What this probe does
Real candidate path only: `compute_limit_stats_local(TD, con=con, recovery_members=...)`
plus `init_db`. No author tests imported; fresh `duckdb.connect(":memory:")` per test,
explicit `con=`. Four derived tables captured as **full-row snapshots** (`ORDER BY ALL`)
before/after each refusing call, so count-only equality cannot mask value mutation.

## Cases
| # | Case | Assertion |
|---|------|-----------|
| 1 | Control: frozen members [M1,M2], both bars present, one limit-up | `action=written`, `denominator_basis=frozen_identity`, `ratio_denominator=2`, `market_limit_up=1` |
| 2 | Control: M2 declared, no bar, no projection, declared nontrading | `action=written`, `ratio_denominator=2`, `observed_count=1`, `nontrading_codes=[M2]` |
| 3 | Adversarial: OUT-of-sector bar close in {NULL, -1, 0, NaN, +inf}, OUT not a declared member | `ValueError`; all four tables byte-identical to pre-call snapshot |
| 4 | Adversarial: declared member M2 has no canonical bar | `ValueError`; tables untouched |
| 5 | Adversarial: nontrading declared for identity M1 that has a live bar | `ValueError`; tables untouched |

Case 3 is the key adversarial: the invalid-close scan in the candidate iterates **all**
`today` bars (not just projected members), which is what the claim requires for
"outside-sector bars consumed by market counts".

## Fixture note (prior failure cause)
The earlier artifact crashed at setup: `INSERT INTO fact_stock_daily VALUES` with 9
values into the now-14-column table. Fixed by naming columns explicitly. That was a
fixture defect, not a behavior finding — no behavioral conclusion is carried over.

## Untested / not claimed
- Missing bar for an outside-sector stock that is **not** a projected member is
  undetectable (no identity listing); claim scope for "missing canonical member bars"
  is only the projected member set. This probe does not exercise that gap.
- No execution has happened; **no PASS is declared**. Refusal-only subclaims depend on
  the host run actually raising and on snapshot equality.
- `force=True`, default daily path, concurrency, and write-time `ROLLBACK` semantics are
  out of scope (claim says default/other fields/concurrency out of scope).
- `recovery_coverage.market_breadth` / `sector_coverage` internals exercised only
  indirectly through case 2; authentic "dated evidence" for nontrading is trusted from the
  caller, not verifiable here.
- Success-path value contents of the four tables are checked only via case 1/2
  counters; no deep row-content assertion on written rows.
- No negative/zero `pre_close`, no NaN `amount`, no duplicate/malformed member codes.

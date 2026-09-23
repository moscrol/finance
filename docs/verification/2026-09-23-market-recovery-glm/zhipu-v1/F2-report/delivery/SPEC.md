# F2 Review Specification — candidate 50330cf (compute_limit_stats_local explicit recovery path)

## Claim under review
With explicit `recovery_members`, `compute_limit_stats_local` must refuse (raise)
before changing any of `fact_theme_limit_heat_daily`, `fact_theme_limit_stock_daily`,
`fact_limit_advance_daily`, `fact_leader_height_daily` when:

- a sector member has no canonical `fact_stock_daily` bar, or
- any canonical close is NULL / NaN / +inf / -inf / zero / negative — including
  bars outside the declared sectors that market-wide counts consume.

The frozen denominator must keep proven nontrading identities (declared members
absent from bars, explained by dated `recovery_nontrading` evidence, remain in the
ratio denominator). Default daily behavior, other fields and concurrency are out
of scope.

## Mechanism verified (candidate revision 50330cf)
| Guard | Location | Scope |
|---|---|---|
| missing member bar | compute_local_stats.py:228-231 | members projected but absent from `today` bars |
| invalid close | compute_local_stats.py:233-236 | **all** of today's bars (`r[3] is None or not isfinite or <= 0`) — covers outside-sector bars consumed by market counts |
| nontrading identity with a bar | compute_local_stats.py:247-248 | `set(recovery_nontrading) & bar_codes` |
| exact-partition coverage | recovery_coverage.py:60-86 via `sector_coverage` | no tolerance; ratio_denominator = declared scope size |

All guards execute before `BEGIN TRANSACTION` and the per-table `DELETE`s
(compute_local_stats.py:254-258). `sec["total"] = coverage[sector]["ratio_denominator"]`
(:251-252) is the frozen-denominator mechanism; `partition_scope` keeps suspended
identities inside the denominator (recovery_coverage.py:33-38, 83-86).

## Independent probe (immutable, sandboxed, in-memory DuckDB)
Fixture: `duckdb.connect(":memory:")` + `init_db(con)`; published snapshot `snap-1`
on TD=2026-09-03 (sector `801010.SH`, expected_stock_count=2, members 600001.SH /
600002.SH); bars M1 close 11.0 (limit-up), M2 parametrized, OUT 600003.SH
parametrized (outside every sector); pre-existing `local:seed` rows in all four
derived tables on both 2026-09-03 and distinct non-target date 2026-09-02.

Executed cases (16 test items, 16 passed, 0 failed/errored/skipped, exit 0):
1. Valid control: written, `denominator_basis='frozen_identity'`, `market_limit_up==1`,
   coverage ratio_denominator=2 / observed_count=2.
2. Nontrading control: M2 declared, no bar, not projected, declared
   `recovery_nontrading=(M2,)` → written, ratio_denominator=2, observed_count=1,
   `nontrading_codes==[M2]`, heat `total_count==(2,)`.
3-14. Invalid close ∈ {NULL, -1.0, 0.0, NaN, +inf, **-inf**} on **outside-sector**
   OUT bar and on **declared member** M2 → `ValueError` + full logical row equality
   (`SELECT * ORDER BY ALL`, both seeded dates) before/after.
15. Projected member with no canonical bar → `ValueError` + row equality.
16. Nontrading identity with a live bar → `ValueError` + row equality.

Positive control: `test_intentional_red_probe_bug` (`assert 1 == 2`) failed as
designed → classified **probe_bug** (validates failure detection; not a product bug).

## Verdict
**PASS_WITH_LIMITS** — the refusal/untouchability core of F2 and the frozen
nontrading denominator were independently executed and passed; the strict temporal
reading of "before changing" is certified only as final logical row equality
(consistent with, but not proven by execution of, the pre-transaction guard order),
and the claim's out-of-scope areas plus several secondary refusal branches remain
unexecuted. Certification applies to the fixed revision only; no merge, full-repo,
or production acceptance is implied.

# F2 EXPLORE notes — independent review of candidate 50330cf (stage: explore, NOT executed)

No verdict is expressed here. I read the packet once; the probe above is my immutable
artifact for the next host phase to execute. Everything below about runtime behavior is
expectation from static reading, not observation.

## Claim read
F2: when `compute_limit_stats_local` is called with explicit `recovery_members`,
(a) a sector member with no canonical `fact_stock_daily` bar, or (b) any invalid
canonical close (NULL, NaN, +inf, -inf, zero, negative) — including bars outside the
declared sectors that market-wide counts consume — must refuse (raise) before any of
the four derived tables (`fact_theme_limit_heat_daily`, `fact_theme_limit_stock_daily`,
`fact_limit_advance_daily`, `fact_leader_height_daily`) changes; and the frozen
denominator keeps proven nontrading identities. Default daily behavior, other fields,
and concurrency are out of scope.

## Static reading of the candidate (not a verdict)
- All F2 refusals sit **before** `BEGIN TRANSACTION` / the per-table `DELETE`s:
  missing-bar check (compute_local_stats.py:229-231), invalid-close check over **all**
  today's bars, which is exactly how outside-sector bars are covered (:233-236),
  nontrading-identity-with-bar check (:247-248), and `sector_coverage` refusals
  (recovery_coverage.py:60-86, exact partition, no tolerance).
- `sec["total"] = coverage[sector]["ratio_denominator"]` (= `len(scope)`, declared
  identities) is the frozen-denominator mechanism; nontrading identities stay in scope
  via `partition_scope(suspended=scope & stopped)`.
- Seeded rows use `source='local:seed'`, so `_has_foreign_rows` (source NOT LIKE
  'local:%') does not trigger the skip path; if the candidate skipped instead of
  raising, `pytest.raises(ValueError)` fails loudly.

## Fixture (exact columns and dates seeded)
- Connection: `duckdb.connect(":memory:")` + `init_db(con)`; `con=con` always passed.
- Dates: target `TD = 2026-09-03`; distinct non-target `OTHER = 2026-09-02` seeded in
  all four derived tables so cross-date damage or value mutation is visible.
- `ops_sector_universe_snapshot_daily` (all 7 cols): TD, `snap-1`, provider `test`,
  sector_count 1, declared_relationship_count 2, status `published`, captured_at (tz).
- `fact_sector_universe_daily` (all 7 cols): TD/snap-1/`801010.SH`/"Sec",
  expected_stock_count **2**.
- `fact_sector_stock_daily_generation` (cols: trade_date, sector_universe_snapshot_id,
  sector_ts_code, sector_name, stock_ts_code, amount=1000.0): members 600001.SH,
  600002.SH (M2 omitted only in the nontrading control).
- `fact_stock_daily` (cols: trade_date, stock_ts_code, stock_name='A', close,
  pre_close=10.0, amount=1000.0, source='test', updated_at): M1 close 11.0 (limit-up),
  M2 close parametrized, OUT 600003.SH close parametrized (outside all sectors).
- Derived-table seeds, on both TD and OTHER: heat (trade_date, sector_ts_code='seed',
  dimension='s', scope='s', total_count=5, source='local:seed'); detail (trade_date,
  sector_ts_code='seed', stock_ts_code='seedstock', price=1.5, source='local:seed');
  advance (trade_date, stock_ts_code='seedstock', boards=2, source='local:seed');
  leader (trade_date, height=3, source='local:seed').

## Cases the probe executes (16 test items)
1. Valid control: written, `denominator_basis='frozen_identity'`, `market_limit_up==1`,
   coverage ratio_denominator=2 / observed_count=2.
2. Nontrading control: M2 declared, no bar, not projected, declared
   `recovery_nontrading=(M2,)` → written; ratio_denominator=2, observed_count=1,
   `nontrading_codes==[M2]`, heat `total_count==(2,)` (frozen identity denominator).
3-8. OUT (outside-sector, consumed by market counts) close ∈ {NULL, -1.0, 0.0, NaN,
   +inf, -inf} → ValueError + full-row equality across both seeded dates.
9-14. Declared member M2 close ∈ same six invalid values → ValueError + full-row
   equality (explicitly includes **negative infinity** and member-side invalidity).
15. M2 projected as member with no canonical bar → ValueError + full-row equality.
16. Nontrading identity M1 that has a live bar → ValueError + full-row equality.

"Full-row equality" = `SELECT *` per table `ORDER BY ALL`, compared as Python tuples
before vs after: DuckDB **logical** row equality. It certifies final-state
preservation only; it cannot distinguish "never touched" from "changed then rolled
back", and it implies nothing about physical bytes on disk, unseen parameter cases,
or concurrent access.

## Honest untested subclaims (gaps in this probe)
- Default daily path (`recovery_members=None`) unchanged — out of scope, untested.
- `recovery_nontrading` without `recovery_members` guard (ValueError at :190-191).
- `recovery_coverage` refusal branches not hit by my fixtures: malformed/duplicate
  codes (regex), declared sectors ≠ published-universe sector set, observed sector
  outside the universe, expected_stock_count ≠ declared member count, surplus
  observed members, expected non-int/non-positive.
- `force=True` and the foreign-row skip path; ST/new-stock exclusions; 60-day lookback
  streak/`min_boards` ladder; leader tie-break; NaN/±inf behavior inside the SQL
  is_up/is_dn expressions themselves.
- Other output fields of the four tables (market_share, top_stocks_json, fd_amount,
  promotion_rate, sw_l1, detail/ladder/leader rows beyond control success and heat
  total_count) are not asserted.
- Concurrency: no claim. Physical byte preservation: no claim (logical rows only).
- Fixture fragility (fails loudly, cannot false-pass): the probe assumes
  `get_published_snapshot_id` resolves the single published snapshot at TD and that
  the `fact_sector_stock_daily` view exposes `snap-1` generation rows per the packet's
  fixture API.

## Status
Pending host execution of the immutable probe. No PASS/FAIL declared for F2.

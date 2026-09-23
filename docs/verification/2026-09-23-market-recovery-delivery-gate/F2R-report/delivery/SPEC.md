# F2R Verification Spec — Candidate 4dd5e66

## Scope

- **Claim F2**: With explicit `recovery_members`, missing canonical member bars or invalid closes (NULL, NaN, ±infinity, zero, negative) — including outside-sector bars consumed by market counts — must refuse before changing any of four derived tables (`fact_theme_limit_heat_daily`, `fact_theme_limit_stock_daily`, `fact_limit_advance_daily`, `fact_leader_height_daily`). Frozen denominator keeps proven nontrading identities.
- **Out of scope (per claim)**: default daily behavior, other fields, concurrency.
- **Revision under review**: `4dd5e66601084962697c5d78e9f6bb58eefc14c8` (base `27ca084f…`). No production acceptance; no full-repo acceptance.

## Interface Under Test

- `market_feature_store.sync.compute_local_stats.compute_limit_stats_local(trade_date, *, con, force=False, min_boards=2, recovery_members=None, recovery_nontrading=())`
- `market_feature_store.recovery_coverage.sector_coverage` / `partition_scope` (pure contracts)
- Fixture API: `duckdb.connect(":memory:")` + `market_feature_store.db.init_db(con)`; always `con=con`; `fact_sector_stock_daily` is a VIEW written via `_generation` with `sector_universe_snapshot_id`; a published snapshot is required for member projection visibility.

## Refusal-Before-Write Contract (from candidate source)

`compute_local_stats.py` lines 226–252 execute, in order, only when `recovery_members is not None`:

1. L228–231: member codes from the member projection minus codes having a `fact_stock_daily` bar → `ValueError("sector member missing canonical stock bar")`.
2. L233–236: **all** `today` bars (not just projected members) with `close IS NULL OR NOT isfinite(close) OR close <= 0` → `ValueError("invalid canonical stock bar close")`. This is the line that satisfies "outside-sector bars consumed by market counts".
3. L247–248: `recovery_nontrading ∩ bar_codes ≠ ∅` → `ValueError("nontrading identity has a stock bar")`.
4. L249–252: `sector_coverage(...)` exact-partition validation; `sec["total"] = coverage[sector]["ratio_denominator"]` (frozen identity baseline).

All four precede `BEGIN TRANSACTION` (L255) and the four `DELETE`s (L256–258); the `except` path issues `ROLLBACK` (L336–341). Therefore any refusal above leaves the four derived tables untouched.

`recovery_coverage.py`: `_codes` rejects non-string/duplicate/malformed codes; `partition_scope` requires declared = observed ∪ nontrading exactly; `sector_coverage` requires declared sector set == expected set, observed ⊆ declared, `expected == len(scope)` (int, >0), and returns `ratio_denominator = len(scope)` with `nontrading_codes` retained — the frozen denominator keeps proven nontrading identities instead of dropping them.

## Subclaim → Acceptance Criteria → Probe Mapping

| # | Subclaim | Acceptance criterion | Probe case | Result |
|---|----------|----------------------|------------|--------|
| 1 | Missing canonical member bar refuses pre-write | `ValueError`; four tables byte-identical (full-row `ORDER BY ALL` snapshot) | `test_missing_member_bar_refuses_untouched` | PASSED |
| 2 | Invalid close NULL refuses | same | parametrized `[None]` | PASSED |
| 3 | Invalid close NaN refuses | same | `[nan]` | PASSED |
| 4 | Invalid close +∞ refuses | same | `[inf]` | PASSED |
| 5 | Invalid close −∞ refuses | same | **not parametrized** | NOT VERIFIED |
| 6 | Invalid close 0 refuses | same | `[0.0]` | PASSED |
| 7 | Invalid close negative refuses | same | `[-1.0]` | PASSED |
| 8 | Outside-sector bar in scan | OUT not a declared member; its bad bar must trigger refusal | cases 2–7 use OUT | PASSED (except −∞) |
| 9 | Refusal precedes any change to 4 tables | full-row snapshot equality incl. seeded `local:seed` rows | all adversarial cases | PASSED |
| 10 | Frozen denominator keeps nontrading identities | `ratio_denominator=2`, `observed_count=1`, `nontrading_codes=[M2]`, action `written` | `test_control_frozen_denominator_keeps_nontrading` | PASSED |
| 11 | Valid recovery control writes | `action=written`, `denominator_basis=frozen_identity`, `market_limit_up=1` | `test_control_frozen_denominator_writes` | PASSED |
| 12 | Nontrading identity with live bar refuses | `ValueError`; tables untouched | `test_nontrading_identity_with_bar_refuses` | PASSED |

## Fixture Correctness Requirements (learned from prior failure)

- Named-column INSERTs into `fact_stock_daily` (14 columns in the initialized schema); unnamed 9-value INSERT caused the prior BinderException (probe bug, since fixed).
- Seed rows use `source='local:seed'` so `_has_foreign_rows` does not short-circuit into the `skipped-has-foreign-rows` path — refusals observed are attributable to the claimed checks.
- Full-row snapshots (not counts) are mandatory: "row counts alone do not establish unchanged values."

## Verdict Rule Applied

Subclaim 5 (−∞) is enumerated in the claim but was never executed; per protocol, unexecuted ⇒ not_verified ⇒ **PASS_WITH_LIMITS** (no product defect found, so CHANGES_REQUIRED is not warranted; no collection/import errors, so BLOCKED_PROBE does not apply).

# K3 Review Spec — F3 — candidate 4dd5e66601084962697c5d78e9f6bb58eefc14c8

## Claim under review (F3)
> apply_bridge_day must recheck existing target-day rows inside its transaction.
> A stale default plan or second application must refuse unchanged. Only literal
> boolean True authorizes replacing existing target day; truthy non-booleans
> refuse. Other dates remain unchanged. Full input fingerprints, concurrent
> scheduler and mootdx partial flush are out of scope.

- Unit under test: `market_feature_store/sync/bridge_hithink_stock_daily.py::apply_bridge_day` (L252–299)
- Base: 27ca084f9ffcb9d148b749944beca340e5f4fa6c

## Subclaim decomposition and verification mapping

| # | Subclaim | Method | Probe test | Result |
|---|----------|--------|-----------|--------|
| 1 | Recheck of existing target-day rows occurs inside the write transaction, before writes | static (L260 BEGIN → L262 fingerprints → L264 guard) + dynamic | test_stale_default_plan_refuses_and_preserves_rows | PASS |
| 2 | Stale default plan refuses unchanged | dynamic, rollback asserted via byte-equal rows | test_stale_default_plan_refuses_and_preserves_rows | PASS |
| 3 | Second default-policy application refuses unchanged | dynamic | test_literal_true_replaces_... (2nd half) | PASS |
| 4 | Only literal `True` authorizes; truthy non-booleans (1, "yes", [True]) refuse | static (`is not True`, L264) + dynamic parametrized | test_truthy_non_boolean_refuses[1/yes/[True]] | PASS (3/3) |
| 5 | Missing policy key refuses (default-deny) | dynamic | test_plan_without_policy_key_refuses | PASS |
| 6 | Literal True replaces with correct report (deleted_replaced=1, final_rows=2, other_days_unchanged is True) | dynamic control | test_literal_true_replaces_... (1st half) | PASS |
| 7 | Other dates remain unchanged on refuse and replace paths | dynamic, other-day row asserted every test | all 6 tests | PASS |
| 8 | Concurrent scheduler / full fingerprints / mootdx partial flush | — | out of scope per claim | NOT TESTED |

## Fixture & environment
- Fresh `duckdb.connect(":memory:")` + `market_feature_store.db.init_db(con)` per test.
- Fixture state: one other-day row (2026-09-21, 000001.SZ) as the "must not move"
  witness; one pre-existing target-day row (2026-09-22, 600000.SH) as the
  deterministic stand-in for "rows appeared after the plan was built".
- Plans hand-built in the exact 14-column tuple shape `executemany` consumes;
  real `BridgePolicy().as_dict()` used for the default-policy cases.
- Execution: `sandbox-exec` + `python -B -m pytest -q -o addopts= -p no:cacheprovider
  --confcutdir <dir>`; junit XML captured; no production DB.

## Verdict criteria (pre-registered)
- Any probe failure/error → CHANGES_REQUIRED (product) unless attributable to the
  probe harness (probe_bug).
- Collection/import error → BLOCKED_PROBE (not a product bug).
- All in-scope subclaims passing, with out-of-scope or mechanism-internal aspects
  untested → PASS_WITH_LIMITS (never full-repo/production acceptance).

## Actual outcome
- Independent probe: 6 tests, 6 passed, 0 failed, 0 errors, 0 skipped, exit 0.
- Author suite (`tests/test_bridge_hithink_stock_daily.py`, withheld during probe
  design): 28/28 passed, exit 0 — agrees with probe.
- Positive control: intentional red assertion `assert 1 == 2` failed as designed →
  classified **probe_bug**; confirms harness sensitivity.
- No collection/import errors; inputs unchanged after execution; revision stable.

## Verdict: PASS_WITH_LIMITS
All in-scope behavioral subclaims were executed and passed, corroborated by static
review. Limits: transaction-isolation under true concurrency untested (out of
scope; staleness simulated on one connection), drift/gone guard asserted only
end-to-end, post-DELETE rollback path untested, `build_bridge_day` and production
write path unreviewed.

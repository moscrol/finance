# F3 Specification Review — `apply_bridge_day` in-transaction recheck

**Candidate:** 50330cf4fa435292bbd555ccc817e62ca5cc45b4
**Source:** `market_feature_store/sync/bridge_hithink_stock_daily.py` (sha256 `2435c350…c119`, identical to prior revision 4dd5e66…)
**Claim F3:** `apply_bridge_day` must recheck existing target-day rows inside its transaction. A stale default plan or second application must refuse unchanged. Only literal boolean `True` authorizes replacing an existing target day; truthy non-booleans refuse. Other dates remain unchanged. Full input fingerprints, concurrent scheduler and mootdx partial flush are out of scope.

## Requirement decomposition vs. implementation

| # | Required behavior | Implementation locus | Status |
|---|---|---|---|
| R1 | Recheck target-day rows inside the write transaction | `BEGIN TRANSACTION` (L260) → `_day_fingerprints` (L262) → existing-count guard (L263-265) precede `DELETE`/`INSERT` (L266-276); `ROLLBACK` on any exception (L289-291) | Source-verified ordering; dynamically corroborated by refusal-plus-preservation (boundaries not instrumented) |
| R2 | Stale default plan refuses, nothing changes | Guard raises `BridgeRefused` when `existing` and `allow_replace_existing is not True` | Dynamically verified (full 14-col row equality, both dates) |
| R3 | Second application refuses unchanged | Same guard re-armed because the first (authorized) write left target-day rows in place | Dynamically verified after a literal-True replacement |
| R4 | Only literal `True` authorizes replace | `plan.get("policy", {}).get("allow_replace_existing") is not True` — identity test, so `1`, `"yes"`, `[True]`, missing key all refuse | Verified for sampled set {1, "yes", [True]} + missing-key case; `True` authorizes |
| R5 | Other dates remain unchanged | Per-day integer-hash fingerprints before/after; drift/gone detection (L277-283) | Verified for the single seeded other date; guard executed on that dataset |

## Design observations (spec-level)

- The authorization check is an **identity test against the singleton `True`**, which is exactly the "literal boolean only" semantics the claim demands; the same expression also makes a missing `policy` key or missing `allow_replace_existing` key refuse safely (both `.get` defaults are falsy/non-True).
- The recheck is deliberately placed **after `BEGIN`** and uses the same connection's snapshot, so a plan that was valid when built is re-validated against current table state at write time — the stale-plan hazard the claim names.
- The drift fingerprint uses **integer hash sums, not floating-point sums** (documented at L229-239): DuckDB's parallel float aggregation is non-associative and produced 3 different `sum(close)` values in 5 runs per the module comment. This is a sound, order-independent "unchanged" assertion basis and is more sensitive than a scalar sum.
- Post-write invariants (other-day drift, final row count) are enforced **inside the transaction** before `COMMIT`, so a violation rolls back rather than half-committing.
- Scope boundaries respected: `apply_bridge_day` does not handle staging/swap (`run_daily_full_staged` is the caller's job) and `production_ready` stays `False` on the build side.

## Specification gaps / residual risk

1. **Concurrency is neither claimed nor proven.** A second connection inserting target-day rows between the fingerprint read (L262) and `DELETE` (L266) is not addressed by this review's evidence; the claim explicitly puts the concurrent scheduler out of scope, and the probe ran single-connection only.
2. **Rollback of a mid-transaction failure is untested.** No probe injects an exception after `DELETE` or between `executemany` batches; the `except: ROLLBACK` path (L289-291) is verified by reading, not by witnessing a partial write revert.
3. **"Only literal True"** is total by Python semantics of `is`, but the dynamic sample is {1, "yes", [True]}; exotic truthies (e.g. `numpy.bool_(True)`, which is *not* identical to `True`) were not executed.
4. **Other-date protection** was observed on exactly one seeded date (2026-09-21); the internal drift check is well designed but only exercised on a 2-date dataset.
5. The stale-plan input was a **hand-built plan dict** (the exact artifact the claim concerns), not a witnessed `build_bridge_day`-then-stale workflow; the operational path producing staleness is out of this probe's reach.

## Conclusion

The implementation satisfies the F3 specification as scoped: recheck ordering, refuse-by-default, literal-True-only authorization, second-application refusal, and other-date preservation on the tested dataset. Residual risk concentrates in the untested rollback path, sampled truthy values, single other-date observation, and the (out-of-scope) concurrency and fingerprint concerns — hence **PASS_WITH_LIMITS**, not an unqualified PASS.

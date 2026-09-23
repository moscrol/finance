# F3 Review Spec — apply_bridge_day in-transaction recheck

**Candidate:** `50330cf4fa435292bbd555ccc817e62ca5cc45b4` (source sha256 `2435c350…c119`)
**Module:** `market_feature_store/sync/bridge_hithink_stock_daily.py::apply_bridge_day`
**Verdict:** PASS_WITH_LIMITS

## Claim decomposition

| # | Subclaim | Disposition |
|---|---|---|
| 1 | Existing target-day rows are rechecked inside the write transaction | ✅ verified |
| 2 | Stale default plan refuses, rows unchanged | ✅ verified |
| 3 | Second application of a default plan refuses; written rows persist | ✅ verified |
| 4 | Only literal boolean True authorizes replace | ✅ verified (True accepts; {1, "yes", [True]} refuse) |
| 5 | Other dates remain unchanged | ✅ verified |
| 6 | Full input fingerprints / concurrent scheduler / mootdx partial flush | ⬜ out of scope (not tested, per claim) |

## Probe design

- Fresh `duckdb.connect(":memory:")` per test; `market_feature_store.db.init_db(con)`;
  `con=con` always. No production DB touched.
- Real candidate functions only (`apply_bridge_day`, `BridgePolicy`, `BridgeRefused`).
  Author tests never imported. Synthetic plan dicts are the stale-plan artifact under test;
  `build_bridge_day` is intentionally bypassed.
- Seeded data: `fact_stock_daily` OD `2026-09-21` / `000001.SZ` (close 10.0) and TD
  `2026-09-22` / `600000.SH` (close 20.0), full 14-column tuples.
- Executed cases:
  1. stale default plan (`BridgePolicy().as_dict()`) → refuse;
  2. truthy non-booleans `1`, `"yes"`, `[True]` → refuse;
  3. plan missing `"policy"` key → refuse;
  4. literal `True` → replace (`deleted_replaced=1`, `written_rows=final_rows=2`),
     followed by second stale-default application → refuse, written rows persist.
- Assertion strength: full `SELECT *` logical equality on both TD and OD for every
  refusal case, OD equality on the positive control. Compared columns are exactly the 14
  initialized columns: trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg,
  amount, turnover, source, updated_at, open, high, low, volume.

## Execution results (sandboxed, `F3-execute/execution.json`)

- **Independent probe:** 6 tests / 6 passed / 0 failed / 0 errors, exit 0, 2.21s,
  no deadline hit.
- **Positive control:** intentional red assertion `assert 1 == 2` → 1 failure, exit 1.
  Classified **probe_bug** (validates failure detection; not a product defect).
- **Author suite:** 28 tests / 28 passed, exit 0. Content withheld in this phase;
  consistency check only — not evidence for the verdict.
- Revision before/after identical; inputs and driver unchanged; no production access.

## Verified behavior (code anchors)

- L260–265: `BEGIN TRANSACTION` → before-fingerprint → `existing` recheck inside the
  transaction; `plan.get("policy", {}).get("allow_replace_existing") is not True` refuses
  (covers stale default, missing key, and every truthy non-boolean by `is not True`).
- L266–276: `DELETE … RETURNING` + `executemany` insert only for target date.
- L277–287: after-fingerprint drift/gone assertion and final row-count assertion.
- L288–291: `COMMIT`; any exception → `ROLLBACK` and re-raise.
- L293–299: result reports `deleted_replaced`, `written_rows`, `final_rows`,
  `other_days_unchanged`.

## Not verified / limits

- Concurrency: single connection only; no second connection simulated (out of scope, and
  single-connection refusal does not prove isolation).
- Truthy domain sampled {1, "yes", [True]} only.
- Empty-rows refusal branch untested; `build_bridge_day`-side checks (coverage, drift,
  names, absent codes, fingerprints) unexercised.
- Equality is logical SQL value equality; no physical byte-preservation claim.
- No production, full-repo, or merge acceptance implied; only this fixed revision.

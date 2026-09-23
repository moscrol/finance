# EXPLORE notes — K3 / F3 — candidate 4dd5e66601084962697c5d78e9f6bb58eefc14c8

## Verdict
**NOT EXECUTED — no PASS claimed.** Probe is immutable for the next host phase. Static read below is consistent with the claim; only execution can confirm.

## Claim map (F3 → code)
- "Recheck existing target-day rows inside its transaction": `apply_bridge_day` does `BEGIN TRANSACTION` (L260) → `_day_fingerprints` → `before.get(td,(0,))[0]` → refuse if `existing and ... is not True` (L262–265). Recheck is textually inside the transaction. ✓ static.
- "Only literal boolean True authorizes": guard is `plan.get("policy", {}).get("allow_replace_existing") is not True` (L264) — identity check, so `1`, `"yes"`, `[True]`, missing key, or absent `policy` all refuse. ✓ static.
- "Refuse unchanged": refusal raises `BridgeRefused` inside `try`; `except` runs `ROLLBACK` and re-raises (L289–291), so the pre-refusal state (incl. any DELETE that never runs on this path) is preserved. Probe asserts old rows survive byte-for-byte.
- "Other dates remain unchanged": post-write fingerprint diff `drift`/`gone` over all dates `!= td` (L277–283). Probe asserts an other-day row end-to-end.

## Probe design (`probe_f3_apply_bridge_day.py`, ~95 lines, pytest, fresh `:memory:` per test)
Drives the **real** `apply_bridge_day` with hand-built plans in the exact tuple shape its `executemany` consumes (14 cols per initialized schema). Fixture: `db.init_db(con)`, one other-day row (`2026-09-21`), one pre-existing target-day row (`2026-09-22`) = deterministic stand-in for "rows appeared after the plan was built".

1. **Adversarial — stale default plan**: `BridgePolicy().as_dict()` (real policy, `allow_replace_existing=False`) on the occupied day → expect `BridgeRefused`; target-day rows and other-day row unchanged (rollback effective).
2. **Adversarial — truthy non-booleans**: parametrized `1`, `"yes"`, `[True]` → all must refuse with data unchanged (catches a truthiness-regression to `if not ...:`).
3. **Adversarial — missing policy key**: plan without `"policy"` → refuse, unchanged.
4. **Control — literal `True`**: replace succeeds (`deleted_replaced==1`, `final_rows==2`, `other_days_unchanged is True`); old row gone, new rows present, other day intact; then a **second default-policy application refuses** and leaves the first apply's rows untouched.

## Untested subclaims (honest)
- **True concurrency**: no racing-writer/interleaving test (explicitly out of scope: concurrent scheduler). Staleness is simulated by pre-inserted rows, which exercises the recheck logic but not DuckDB isolation semantics.
- **Drift/gone fingerprint guard** (L277–283) cannot be triggered via the public API without an internal bug; only the end-to-end "other day unchanged" property is asserted, not the guard itself.
- `build_bridge_day`'s own existing-row check (L162–169), coverage/drift gates, `preview_stock_calculation`, and real hithink fixtures: **not exercised** (out of claim scope; plans constructed directly).
- Empty-rows refusal (L256), final-count mismatch (L286), name-resolution/turnover/source policies: not exercised.
- Full input fingerprints / mootdx partial flush: out of scope per claim.

## Execution risks / potential findings
- `DELETE ... RETURNING` (L266–269) needs a DuckDB version supporting it; failure would error the control test → real finding, not a probe artifact.
- If DuckDB aborts the tx on the refusal path such that `ROLLBACK` itself raises, the raised type would not be `BridgeRefused` and tests 1–3 fail → real defect signal.
- Assumes `market_feature_store` is importable from candidate root and `market_feature_store.db.init_db(con)` exists per fixture API; no author tests imported.

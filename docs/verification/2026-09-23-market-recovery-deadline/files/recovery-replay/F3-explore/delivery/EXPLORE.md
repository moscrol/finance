# F3 EXPLORE notes — candidate 50330cf4fa435292bbd555ccc817e62ca5cc45b4

## Scope reviewed
`market_feature_store/sync/bridge_hithink_stock_daily.py::apply_bridge_day` (source sha256
2435c350…c119). Claim F3: in-transaction recheck of existing target-day rows; stale default
plan / second application refuses unchanged; only literal boolean True authorizes replace;
other dates unchanged.

## Probe design (immutable, not yet executed — no PASS declared)
- Fresh `duckdb.connect(":memory:")` per test, `market_feature_store.db.init_db(con)`.
- Real candidate functions only: `apply_bridge_day`, `BridgePolicy`, `BridgeRefused`.
  No author tests imported. `build_bridge_day` is intentionally **not** called: synthetic
  plan dicts (`trade_date`, `rows`, optional `policy`) are the exact stale-plan artifact
  the claim is about.
- Seeded dates/rows in `fact_stock_daily`: OD `2026-09-21` / `000001.SZ` (close 10.0) and
  TD `2026-09-22` / `600000.SH` (close 20.0), each a full 14-column tuple.
- Executed cases:
  1. stale default plan (`BridgePolicy().as_dict()`, allow_replace_existing=False) → refuse;
  2. truthy non-booleans `1`, `"yes"`, `[True]` in policy dict → refuse;
  3. plan missing the `"policy"` key entirely → refuse;
  4. literal `True` → replace: `deleted_replaced==1`, `written_rows==final_rows==2`,
     then a second, stale default application refuses and the written rows persist.
- Assertion strength (per expanded scope): full `SELECT *` logical row equality on **both**
  TD and OD for every refusal case, and OD snapshot equality on the positive control.
  Columns compared are exactly the 14 initialized columns: trade_date, stock_ts_code,
  stock_name, close, pre_close, pct_chg, amount, turnover, source, updated_at, open,
  high, low, volume.

## Untested subclaims (honest)
- **Concurrency**: single connection only. A concurrent scheduler inserting target-day rows
  between the fingerprint check and DELETE is not simulated; single-connection refusal does
  not prove transaction isolation (also declared out of scope in the claim).
- **mootdx partial flush / full input fingerprints**: `preview_stock_calculation`,
  `input_fingerprint`, `scope_fingerprint` never exercised; `build_bridge_day`-side checks
  (coverage, universe drift, name resolution, absent codes) untested.
- **Literal-True authorization tested only via policy dict value `True`**; truthy coverage is
  just {1, "yes", [True]} — other non-booleans (e.g. numpy.bool_, 0.5) unseen.
- **Empty-rows refusal branch** ("无 rows") not tested.
- Row equality is DuckDB `fetchall` logical SQL value equality; nothing is inferred about
  physical byte-identical storage. PASS/FAIL awaits host execution of this probe.

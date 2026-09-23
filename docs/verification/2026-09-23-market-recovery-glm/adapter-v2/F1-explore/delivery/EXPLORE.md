# EXPLORE notes — Claim F1, candidate 4dd5e666

## Scope
Source under review: `skills/daily-full-review/scripts/run_review_sync.py` (only file in packet). No author tests/verdicts imported. Probe loads the candidate module directly via `importlib` with `market_feature_store` (`db.connect`, `consumption_registry.PLAN_CHOICES/resolve_plan`) stubbed in `sys.modules` first, so no real DB/network/subprocess is touched. All step execution goes through module-level `run_step` / `_count`, which the probe monkeypatches.

## Subclaim → code mapping
1. **Local plan ordering** — `build_local_plan` (L403-439): `db-lock`, then `hithink[0]` = `hithink-stock-daily` (L418), then canonical `stock-daily` with `hithink_fallback=True` (L419), then remaining hithink steps, then derived consumers (`stitch-sector-stocks`, `sector-daily-local`, `limit-stats-local`, ...). Note: only `hithink-stock-daily` precedes canonical stock-daily; the other three hithink steps come *after* — claim only asserts hithink-stock-daily, consistent.
2. **Fallback chain** — `sync_stock_daily` (L310-344): snapshot step (L314) → short-circuit ok if status ok AND `_count(fact_stock_daily)>0` (L319) → `fill-stock-daily-fallback` (member fallback, L321) → recount (L331) → `bridge-stock-daily` **only when rows==0** (L332-336) → final ok requires last attempt ok AND rows>0 (L338). Bridge gating on emptiness is real, not status-based.
3. **Blocking** — `main` loop (L579-604): `critical` includes `plan=="local" and name=="stock-daily"` (L581); on non-ok it retries up to `--retry-rounds`; still non-ok → append, `_notify`, `write_runlog(..., False, ...)`, `return 1` — downstream steps and `run_release_steps` (L624) never reached.
4. **Attempt records** — retry merge at L591-593: `retry["attempts"] = [*result.attempts, *retry.attempts]`, elapsed accumulated; merged attempts flow into `write_runlog` results.

## Probe design (6 tests, ~120 lines)
- `test_local_plan_orders_hithink_then_stock_daily_then_consumers` — builds plan (pure; lambdas never invoked), asserts index ordering vs 5 derived consumers.
- `test_snapshot_success_short_circuits_control` — **valid control**: snapshot ok + rows>0 ⇒ ok, exactly one attempt, fallback/bridge never called.
- `test_bridge_runs_only_when_canonical_day_empty` — rows 0→0→700 across three `_count` calls ⇒ full chain snapshot→fallback→bridge, attempts recorded in order, final ok.
- `test_bridge_skipped_when_fallback_fills_rows_adversarial` — **adversarial**: snapshot 0 rows, fallback fills 321 ⇒ bridge must NOT run; a greedy implementation would bridge anyway. Result still ok.
- `test_exhausted_stock_daily_retries_block_downstream_and_release` — **adversarial/blocking**: `main()` driven with fake 2-step plan (failing stock-daily + spy downstream), `--retry-rounds 2`. Asserts rc==1, fn called 3× (orig + 2 retries), downstream/release spies at 0, runlog received `gate_ok=False`, and merged attempts `["orig","r1","r2"]` (subclaim 4: records remain available).

## Honestly untested subclaims / limits
- `write_runlog`'s actual file rendering of the `attempts` rows (L504-508) — stubbed; only the records handed to it are asserted.
- `_notify` fire-and-forget behavior — stubbed.
- `run_release_steps` gate internals — only its non-invocation on block is checked, not its pass-path semantics.
- Real CLI argv correctness of each step (subprocess never spawned, per probe constraints).
- Hithink skip contract (`has_api_key` → status "skip", L391-394) and the "skip cannot洗绿" retry branch (L588-590) — not exercised (not core to F1's four subclaims).
- Behavior when fallback fails but rows>0 (bridge skipped, final fail per L337-338) — reasoned from code, not separately probed.
- `plan_step_names`/registry consistency with `consumption_registry.yaml` — registry stubbed, so cross-file consistency unverified.
- Full-plan (`full`/`cheap`) ordering — outside F1.

## Verdict
No PASS declared — probe submitted for next-phase execution. Static reading is consistent with all four F1 subclaims; the probe targets the two riskiest points (bridge-only-when-empty gating; retry-exhaustion blocking with attempt-record retention).

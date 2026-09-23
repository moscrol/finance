# Spec — Claim F1 Review (candidate 50330cf4fa435292bbd555ccc817e62ca5cc45b4)

## Scope
- Source under review (single file): `skills/daily-full-review/scripts/run_review_sync.py` (sha256 `0955f42f…`, identical before/after per recorded provenance).
- Claim F1 decomposition:
  1. Local plan orders `hithink-stock-daily` → canonical `stock-daily` → derived consumers.
  2. Canonical sync attempts snapshot → member fallback → hithink bridge, with bridge gated on canonical-day emptiness (`rows == 0`).
  3. Exhausted stock dependency retries block downstream steps and release.
  4. Attempt records remain available.
  - Probe constraint: no live network or subprocess; all side effects monkeypatched.

## Verified behavior (probe-executed, 5/5 passed)

### S1. Local plan ordering
- `build_local_plan` (L403–439): `hithink[0]` = `hithink-stock-daily` (L418) → `stock-daily` with `hithink_fallback=True` (L419) → remaining hithink steps → consumers.
- Test: builds plan for seeded date `2026-09-23` (lambdas never invoked); asserts index ordering vs 5 derived consumers (`stitch-sector-stocks`, `sector-daily-local`, `limit-stats-local`, `market-overview-local`, `features`). **PASSED.**

### S2. Canonical fallback chain (`sync_stock_daily`, L310–344)
- Chain: `sync-stock-daily-snapshot` (L314) → short-circuit ok iff status ok AND `_count(fact_stock_daily) > 0` (L319) → `fill-stock-daily-fallback` (L321) → `bridge-stock-daily` only when rows == 0 (L331–336) → final ok requires last attempt ok AND rows > 0 (L338).
- Tests (all seeded date `2026-09-23`):
  - Control: snapshot ok + 5000 rows ⇒ single attempt, no fallback/bridge. **PASSED.**
  - Full chain: rows 0→0→700 ⇒ calls `[snapshot, fallback, bridge]`, attempts ordered, final ok. **PASSED.**
  - Adversarial: rows 0→321 ⇒ bridge NOT invoked; a greedy implementation would bridge. **PASSED.**

### S3. Retry-exhaustion blocking (`main`, L579–604)
- `critical = name in HITHINK_STEPS or (plan == "local" and name == "stock-daily")` (L581); non-ok ⇒ in-place retries up to `--retry-rounds`; still non-ok ⇒ append result, `_notify`, `write_runlog(…, False, …)`, `return 1` — downstream steps and `run_release_steps` (L624) unreachable.
- Test: argv `--date 2026-09-23 --plan local --skip-preflight --retry-rounds 2`, failing stock-daily stub, downstream/release spies. **PASSED**: rc==1; 3 invocations (orig+r1+r2); downstream 0; release 0; runlog `gate_ok=False`.

### S4. Attempt records retained
- Retry merge L591–593 (`attempts` concatenation, elapsed accumulation); test asserts `["orig","r1","r2"]` in the results handed to `write_runlog`. **PASSED (up to the write_runlog boundary only).**

## Not verified (out of probe reach, by design or scope)
- `write_runlog` file rendering of attempts rows (stubbed); `_notify` delivery; `run_release_steps` pass-path internals; real CLI argv/subprocess behavior; hithink no-key skip contract and skip-washing guard; `plan_step_names` ↔ `consumption_registry.yaml` consistency; fallback-fails-but-rows>0 case; end-of-run compensation retry loop (L607–616); full/cheap plan ordering.

## Evidence inventory
| Item | Result |
|---|---|
| Independent probe (5 tests, sandboxed, no network/subprocess/DB) | 5 passed, exit 0, no deadline |
| Positive control (`assert 1 == 2`, intentional red) | 1 failed, exit 1 — **probe_bug**, failure detection confirmed |
| Author suite `tests/test_review_sync_hithink_wiring.py` | 28 passed, exit 0 (supporting only; no author verdict provided) |
| Integrity (recorded) | `inputs_unchanged: true`, `driver_unchanged: true`, source sha equal before/after |

## Verdict
**PASS_WITH_LIMITS** — all four F1 components verified at the monkeypatched orchestration level; persistence rendering, gate internals, subprocess-level behavior, and non-F1-plan ordering remain unverified. Certified for the fixed candidate revision only; no merge admission or production acceptance implied.

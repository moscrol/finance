# K3 QUALITY v4 review — progress notes

## Identity (VERIFIED)
- checkout /Users/a77/fwp-wt-ownership-quality-v4-0921 @ 6eb12c1b8a41071fd4af8bee343950fe0b85b221
- tree e99dad14cb946a112d92537289854d914e558936, git status clean
- 12 provenance sha256 all match (conftest, main_gate_receipt, run_main_gate.sh, worktree_board, cli, repair_backfill, verify_302132, 3 test files, test-environment.json, sync_daily_full)
- interpreter: /Users/a77/finance-workspace-private/.venv-workbench/bin/python
- evidence root: /Users/a77/.finance-runtime/reviews/ownership-k3-v4-20260921/quality-k3

## Scope map
- #814 receipt ownership: conftest.py (Config-stash claim + env PID + cleanup), scripts/run_main_gate.sh (per-run gate-*/pytest.json, FWP_TEST_RECEIPT_OWNER_PID="" reset, post-run rev/status recheck), scripts/main_gate_receipt.py (validator)
- #812 board: scripts/worktree_board.py (unknown preservation, locked/prunable, pinned base_sha, dirty=any porcelain precludes prune)
- #813 backfill: market_feature_store/cli.py cmd_repair_backfill_302132, sync/repair_backfill_stock_history.py, scripts/verify_302132_backfill_acceptance.py, parent sync_daily_full.run_daily_full_staged

## Key mechanism readings (done)
- conftest pytest_configure(tryfirst): claims only if FWP_TEST_RECEIPT_PATH set AND FWP_TEST_RECEIPT_OWNER_PID unset/empty; stash=(pid,path); env OWNER_PID=pid; add_cleanup(release_owner) restores only own claim (pop if no previous, else restore previous).
- pytest_sessionfinish: FWP_TEST_RECEIPT=0 → skip; if PATH set and (env owner != pid OR stash != (pid,path)) → skip. Write via _write_test_receipt: O_EXCL "x" mode, uuid12 in default name, latest.json via NamedTemporaryFile+os.replace (atomic, non-authoritative).
- run_main_gate.sh: REPO=git toplevel or exit4; dirty→exit2 unless --allow-dirty; mktemp -d gate-XXXXXXXX per run; pytest env: FWP_TEST_RECEIPT_DIR/PATH + OWNER_PID="" (explicitly cleared); PIPESTATUS[0] captured → --pytest-exit; post-run rev+status recheck → exit4 on drift; missing receipt → exit4 (no latest.json fallback); validator main_gate_receipt.py.
- main_gate_receipt.load_receipt: counts int>=0 (bool rejected via type() is not int), zero-exec rejected, exit_status in (0,1), failed_ids list[str] nonempty strings, len==failed+error and bool consistency with status, target str, dependency_gate_bypassed is False, interpreter==sys.executable. main: revision match, dirty/total unless --allow-dirty, tree match (also receipt-only), pytest-exit match, baseline: dirty rejected, target match, new_red→3, passed nondecreasing.
- worktree_board: resolve_base gitea/main→origin/main→main→"" (no HEAD fallback); collect_rows raises RuntimeError on base/common-dir/worktree-list failure → main rc=1 "未知"; classify_worktree: rev-parse --show-toplevel mismatch→error; cherry fail→(-1,-1,False)+error; rev-list fail→error; status fail→error; locked/prunable parsed from porcelain; format_board: uncertain bucket (error|locked|prunable) separated; prune requires in_main && dev-wt && !dirty (ANY porcelain line); base_sha pinned once per scan, classify uses base_sha.
- repair_backfill_stock_history: _guard (code regex, nonempty gaps, date order, parquet sha256, calendar boundaries, prev_day, gap live state apply/verify/partial, shell all-NULL in apply, pinned 0911 snapshot, no adjustment events on write days, stale inventory == spec in apply, source date sets == calendar, per-day predecessor, finite values, retained snapshot); _apply_main (bf_src temp + md5, INSERT parallel segment, bf_pq, shell UPDATE) — apply only, verify mode skips writes; _rebuild_derived_scoped (bf_tech/bf_win stage, expected-blank check vs rn>=26, verify mode = EXCEPT ALL both directions zero-write, apply = scoped DELETE+INSERT same bounds); _accept (64-date set, 54-key fullfield oracle w/ Decimal, label conservation, retained identical, 0911 pinned, technical 39 exact, window golden triples + counts, 0911 derived pins); run_backfill_child wraps with protected-slice fingerprints before/after (incl calculated_at), binds code revision/dirty.
- cli.cmd_repair_backfill_302132: parent rejects --db (rc2) BEFORE parquet probe; child: target=--db|env, _refuse_production_write_direct, duckdb connect, run_backfill_child, RepairRefused→rc2 no status; report via _guarded_write_json (protected={target,parquet,canonical candidates}); status.json written only after report success; parent: report-path pure-validate pre-swap, probe write/delete own pid file pre-swap, run_daily_full_staged(kind=repair-backfill-302132, pre_swap_backup=True), on swapped: read child report, write execution receipt O_EXCL.
- sync_daily_full._run_daily_full_staged_locked: stale staging/status cleanup, probe_no_active_writer, hold_swap_lock clone + identity recheck, child subprocess env MARKET_FEATURE_STORE_DB=staging + RUN_ID, status.json parse fail→abort, child_rc<0→abort, no status→abort, run_id mismatch→abort, rc not in (0,1)→abort, shape checks, receipt into staging, third-party writer guard (stat mtime/size), in-lock recheck + backup + atomic_swap_into_place / publish_new_into_place (os.link EEXIST).
- verify_302132_backfill_acceptance: arg format checks first, regular-file+samefile preflight, sha before/after, receipt deep schema (_validate_receipt), child report file deep-equal, backup identity, spec cross-run equality, parquet 3-way per run, old receipts, data checks only if all prior ok (else data_checks_executed=False), data_checks_error structured, output O_EXCL, rc 0/2.

## Probe plan (independent)
- A. receipt: synthetic gate repo (copy conftest+scripts) — overlapping parallel gates same receipt root; nested subprocess pytest; nested same-process pytest.main (incl same target different -k); sequential success + configure-failure cleanup; claimed-path switch; inherited PID alone; immutable overwrite (O_EXCL); IO failure (unwritable dir); git failure (no git / not a repo); signal (SIGKILL/SIGINT mid-run); stale latest never reused; drift mid-run.
- B. board: synthetic git repo family — missing root (deleted wt dir), failed git query (fake git shim), parent-repo fallback (wt path inside another repo), locked/prunable, pinned main SHA (fake git logging args), dirty non-code file precludes prune, no-main repo → rc1 unknown.
- C. backfill: tiny synthetic duckdb fixtures — guard rejections (bad code, empty gaps, bad dates, parquet sha mismatch, partial state, shell non-NULL, stale inventory mismatch, source date set mismatch, adjustment event), oracle mismatch detection, protected-slice mutation detection, verify-mode zero-write, apply happy path end-to-end on tiny calendar? (spec is pinned to 302132 constants — happy path needs full 64-day fixture; assess feasibility; maybe monkeypatch spec with tiny window — but _guard uses spec fields, so a custom BackfillSpec with tiny dates could work IF code paths don't hardcode 302132. Check: _guard uses spec.* everywhere; _apply_main uses spec; _rebuild uses spec; _accept uses spec. CODE regex check needs \d{6}.(SZ|SH|BJ). So a tiny synthetic spec is feasible!)
- D. acceptance verifier: synthetic receipts + tiny DBs — good PASS control + mutations (wrong revision, dirty, missing fields, alias samefile, hardlink, bad sha, spec mismatch apply/verify, data mutations).

## Status
- [ ] formal tests run (targeted)
- [ ] probe A receipt
- [ ] probe B board
- [ ] probe C backfill
- [ ] probe D acceptance
- [ ] REPORT.md + verdict.json

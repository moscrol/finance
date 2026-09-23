# PR827 Independent QUALITY Review — nightly deploy closeout (quality axis)

- **Reviewer axis**: quality (independent; author session not consulted; prior failed Quality events not inspected per contract)
- **Candidate**: `b0cf04fb446b8e87cb4a374b63d96b7c92824551` (HEAD of quality-tree, confirmed via `git rev-parse HEAD`, tree clean)
- **Base**: `f783f19c8a01fbe8d0ed70d851df7ed14598c051`
- **Spec applicability**: original Spec PASS is at `2ea6c3db01a062b9c623498df1b60edfbafe582b`; per `spec-applicability.json` the candidate adds only docs. I independently re-hashed the six reviewed files at the candidate SHA: all six SHA256 values are byte-identical to the Spec-reviewed hashes (see `evidence/reviewed-files.sha256`). Spec was **not** rerun at this SHA; this Quality review re-executed tests and an independent rig at `b0cf04fb`.
- **Date**: 2026-09-21, single session, offline. No live launchctl, no collectors, no provider/API calls, no candidate mutation, no real-HOME install.

## Scope confirmation

`git diff --stat f783f19c..HEAD -- scripts intelligence skills tests` shows exactly the six contracted files. `scripts/lib/ops_python.sh` and the four eval plists are not in the diff. Root QC correction verified: the preserved old patch is `market_feature_store/sync/sync_akshare_index_daily.py` (not `run_review_sync.py`) — byte-identical between `/Users/a77/finance-workspace-sync` (HEAD 6382c13b7, patch present as working-tree modification) and `/Users/a77/.finance-runtime/finance-sync-adcda94b5e40`, sha256 `3e3581ec…2808f6` on both sides, matching qc.json. All three `*adcda94b5e40` roots at `adcda94b5e401158f1c3aa51f210e1e8d0f0b713`, clean; `finance-s7-sync` at `418515c0383334558a8dd44a0e741f39085115fa`, clean; staging wrapper `/Users/a77/.local/bin/nightly-review-sync-staged.py` present and untouched by this diff.

## Existing tests (run once, candidate SHA)

```
FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1 .venv-workbench/bin/python -m pytest \
  -p no:cacheprovider --basetemp=quality-k3/work/pytest-base \
  tests/test_eval_launchd_installer.py tests/test_eval_launchd_wiring.py -q
→ 53 passed in 15.56s   (20 installer + 33 wiring; denominator 53/53)
```

## Independent quality rig (own harness, not the author's)

`work/quality_rig.zsh` (sha256 `0d9bb331…f326bd`): real candidate installer executed against a **repo copy** (`git archive HEAD scripts intelligence skills tests`, hash-verified against candidate) with fake HOME and a **state-tracking stub launchctl** (models loaded set; bootstrap fails if already loaded; fault injection via env). Final run: **62/62 assertions PASS** (`evidence/quality-rig.log`, sha256 `5ea29802…a7a49`). Harness history: run 1 had a harness-only bug (arg separator under `set -u`, 26 false FAILs, log overwritten in place — disclosed); run 2 (preserved as `evidence/quality-rig.run2.log`) had one wrong assertion of mine (Q5 expected finalize on-disk unchanged, but copies precede the launchctl phase); run 3 is the canonical 62/62 log. No installer defect was behind any false failure.

### Q0 positive control — scoped install
`--nightly-only`: rc 0; exactly 4 launchctl calls (2 bootout + 2 bootstrap, 0 kickstart); installed sync/finalize plists and s7 wrapper byte-match candidate; s7 wrapper executable; other four jobs' files and loaded state untouched; shared helper untouched; installed sync plist carries the adcda root (2 lines).

### Q1 mid-install fault (required scenario)
Fault: bootstrap of the **second** job (finalize) fails (I/O error injection). Result:
- installer **fails loudly** rc=5 (`set -e`), 4 calls logged, **no rollback attempted** (installer claims none — confirmed);
- **mixed state**: sync loaded-new (installed plist = candidate hash), finalize **not loaded**; both wrappers+plists already copied (copies precede the launchctl phase);
- other four jobs untouched;
- **operator rollback** per release-plan step 6 (bootout both, restore byte-exact backups, bootstrap originals) restores old loaded jobs and old files — verified.

### Q2 copied mutations are caught (required)
All mutations in the repo copy only; candidate untouched.
- **M1** finalize plist Label → wrong value: rc 2, zero launchctl calls, zero file changes.
- **M2** sync plist RunAtLoad → true: rc 2, zero calls, zero changes.
- **M4** s7 wrapper shell-syntax corruption (`if;`): rc≠0, zero calls, zero changes.
- **M3** sync plist `FINANCE_SYNC_CODE_ROOT` → `finance-sync-deadbeef00`: **installer accepts** (rc 0, wrong root installed into fake HOME) — the preflight is syntactic + Label + RunAtLoad only, no semantic root validation. The **real wiring test suite catches it**: `pytest tests/test_eval_launchd_wiring.py` on the mutated copy → `1 failed, 32 passed`, failing test `test_review_sync_plist_source_pins_dedicated_sync_code_root` (`work/rig/m3-pytest.txt`). Layered defense works, but the installer's blind spot is real → issue QUALITY-827-01.

### Q3 dry-run
`--nightly-only --dry-run`: rc 0, zero calls, HOME snapshot byte-identical, launchd-state snapshot identical, no `~/.finance-runtime` created.

### Q4 default full install
rc 0, 12 calls, 6 loaded jobs, "installed 6 jobs" — base contract preserved; also proves the four unchanged eval plists pass the new stricter preflight (Label + explicit RunAtLoad=false).

### Q5 bootout failure swallowed, conflict surfaces loudly
Fault: bootout of sync fails. `2>/dev/null || true` swallows it (line 124); the next bootstrap fails rc 17 (already loaded) → installer aborts **loudly**. Residual state: sync **loaded-old but on-disk-new**, finalize likewise on-disk-new with loaded-old (copies precede launchctl). This loaded≠disk divergence is invisible to disk-only checks — concrete evidence for requirement 6 (post-release verification must read **loaded** values via `launchctl print`). Idempotent rerun converges (rc 0).

### Q6 option handling
`--dry-run --kickstart`, `--kickstart --dry-run`, unknown `--nightly-onyl`: all rc 2, zero calls, zero file changes — order-independent, before side effects.

## Scheduling hazard assessment (actual candidate, not imaginary guarantees)

Both night plists carry **only** `StartCalendarInterval` (18:30 / 20:40); `KeepAlive`, `WatchPaths`, `StartInterval`, `StartOnMount` all ABSENT; `RunAtLoad=false` (plutil-verified). So bootstrap cannot trigger a run, but after a real install launchd **will** fire both jobs at their next calendar times — the release plan's "≥10 minutes until next schedule, otherwise postpone" precondition is the operative control, and it is operator-enforced, not installer-enforced. Wrapper-level hazards unchanged by this diff: nightly lock (`daily-full-review.lock`, rc 75 on contention), weekend skip, `ops_wait_duckdb_unlocked`. The installer itself does not check job idleness or the lock — a bootout during an active run would kill it; the "both jobs idle + lock absent + re-check under lock" preconditions (plan steps 2–3) cover this.

## Release precondition sufficiency (installer claims no transaction — confirmed)

The installer is a sequence of `cp` + per-job bootout/bootstrap; it does not and does not claim to provide a two-job transaction or auto-rollback. Concrete residual risks and their controls:
1. **Mid-install mixed state** (demonstrated Q1): loud failure, bounded blast radius (two jobs), covered by plan step 3 (explicit pre-bootout of both) + step 6 (restore backups, verify loaded old values; BLOCKED-and-report if rollback verification fails). Demonstrated sufficient in the rig.
2. **Loaded≠disk divergence after swallowed bootout failure** (demonstrated Q5): covered by plan step 5 (verify loaded environment/arguments/calendar/RunAtLoad, runs=0) — only if operators actually read loaded values; flagged as issue QUALITY-827-02 (low).
3. **Semantic root mutation** (demonstrated Q3-M3): not caught by installer; caught by wiring tests + plan step 1/5 hash-and-content preflight. Issue QUALITY-827-01 (low).
4. **Calendar firing post-install**: covered by the ≥10-minute margin precondition; normal next scheduled runs use the new roots — explicitly not acceptance evidence (plan boundary concurs).

Controlled-release preconditions (idle jobs, lock, hash preflight, exact clean roots, preserved old patch/L2 files, byte-exact backups with modes, prepared explicit rollback, loaded-value postchecks) are **sufficient** for this supervised two-job plist+wrapper swap. This review does not sign real data recovery, supplier completeness, or night-run acceptance.

## Issues

- **QUALITY-827-01 (low)** — installer preflight has no semantic validation of selected plist payloads (roots, plan, python). A wrong-root mutation installs cleanly (rc 0). Mitigated by wiring tests and operator preflight/post-install content+loaded-value verification; documented here so the gap is not mistaken for installer coverage.
- **QUALITY-827-02 (low)** — `launchctl bootout … || true` (line 124) swallows bootout failure; the failure surfaces one step later as a bootstrap conflict (loud, rc 17) but leaves loaded-old/on-disk-new divergence. Acceptable given mandatory loaded-value postchecks; a disk-only check would miss it.

## Limitations

- Bounded offline review only: no install against the live HOME, no real launchd, no loaded-value (`launchctl print`) verification on the live machine, no live sync, no collector/provider/API execution.
- Stub launchctl models bootout/bootstrap/kickstart faithfully for the tested paths but is not launchd; calendar firing was assessed from plist content, not observed.
- Operator release conditions were assessed for sufficiency and partially simulated (backup/rollback path), not performed; data recovery, supplier completeness, and 18:30/20:40 night-run acceptance are not signed.
- First rig run's log was overwritten in place after a harness-only bug (disclosed); run-2 log preserved (`evidence/quality-rig.run2.log`); canonical log is the 62/62 run.
- Author documentary evidence (docs/, verification logs) not inspected; conclusions rest on code, plist semantics, on-disk roots, and independent execution.

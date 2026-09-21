# PR827 Independent SPEC Review — nightly deploy closeout (8792 → adcda94b5e40)

- **Reviewer axis**: spec (independent; author session not consulted; docs/verification evidence not inspected per contract)
- **Candidate**: `2ea6c3db01a062b9c623498df1b60edfbafe582b` (HEAD of spec-tree, confirmed)
- **Base**: `f783f19c8a01fbe8d0ed70d851df7ed14598c051`
- **Git identity**: `linxiaoqi5111-del <linxiaoqi5111-del@users.noreply.github.com>`, commit dated 2026-09-21 16:05:03 +0800
- **Date of review**: 2026-09-21, single session, offline. No live launchctl, no collectors, no provider/API calls, no candidate mutation.

## Scope confirmation

`git diff --stat f783f19c..HEAD` shows the six contracted source/config/test files plus documentary evidence (docs/, .claude/, verification logs — not inspected). Non-documentary changed files are exactly:

```
intelligence/dream/com.financeworkspace.daily-full-review-finalize.plist
intelligence/dream/com.financeworkspace.daily-full-review-sync.plist
scripts/install_eval_launchd.sh
skills/daily-full-review/scripts/nightly_full_review_s7.sh
tests/test_eval_launchd_installer.py   (NEW file, +181)
tests/test_eval_launchd_wiring.py      (+13/-6)
```

`scripts/lib/ops_python.sh` is **not** in the diff (shared helper not rewritten). The four eval plists are not in the diff.

SHA256 of reviewed files (recorded in `evidence/reviewed-files.sha256`):

| file | sha256 |
|---|---|
| scripts/install_eval_launchd.sh | eef79c318143dc61ca24d61698c14cfa7250d74d74b7d544565ee56de7a063a8 |
| …daily-full-review-sync.plist | 1921f278d3e5fe088f81fa87faba11dc844a024e8b0e25043a9bdaa0e52eabe5 |
| …daily-full-review-finalize.plist | 71fe78623f56129e08f93b183e531ad9fadc9d270f0e07e9d15500f50ee2ecbe |
| nightly_full_review_s7.sh | 02474070d3cda8dd909c81b821502192fce33954fb1a31ee52576df3f4a8aff0 |
| tests/test_eval_launchd_installer.py | 1bcffe354c11a91e74a02f1f18aa1d14f14921a73491d03bda0ee3151156726e |
| tests/test_eval_launchd_wiring.py | 7992d0419bbb07712983b16386565d4a430069d491051e3959bfce4f9e2c4987 |

## Requirement checks (derived independently)

### 1. Additive `--nightly-only`, shared-helper gate
- Installer parses options in an order-independent `while/case` loop; `--nightly-only` slices zsh 1-indexed arrays to `SOURCES[6,7]` (nightly_full_review.sh, nightly_full_review_s7.sh), `PLISTS[5,6]`, `JOBS[5,6]` (sync, finalize). Index arithmetic verified against array definitions.
- Scoped mode requires `cmp -s` repo vs installed `ops_python.sh` **before** any validation/write; drift or missing helper → rc 2, zero writes (rig case A; author cases `shared_helper`, `missing_helper`). Scoped mode never copies the helper at all, so it cannot silently update it.
- **Positive control (own rig, not author's test)**: real installer + fake HOME + recording stub launchctl, `--nightly-only` → exactly 4 changed paths (2 plists + 2 wrappers), 4 launchctl calls (2 bootout + 2 bootstrap), no kickstart, no touch of the other four jobs; installed s7 wrapper byte-matches candidate; installed sync plist carries the adcda root.

### 2. Dry-run / default / kickstart / bad options
- `--dry-run` (alone, and with `--nightly-only` in both orders): rc 0, byte-identical HOME snapshot, no `~/.finance-runtime` created, zero launchctl calls; on a nonexistent HOME, no directory is created (rig B, B2).
- Default full install: 6 jobs, 12 launchctl calls (6 bootout + 6 bootstrap), "installed 6 jobs" (rig G) — base contract preserved.
- `--kickstart` is never implicit: positive control shows zero kickstart calls without the flag; with the flag (both orders) exactly the two night jobs are kickstarted (rig I).
- `--dry-run --kickstart` (both orders) and unknown options → rc 2 before any side effect (rig C, D).

### 3. Prevalidation before any copy; calendar reality
- All selected files are validated before `mkdir`/`cp`: `/bin/zsh -n` per script; `plutil -lint`, `Label == basename`, and `plutil -extract RunAtLoad raw` must equal literal `false` per plist (missing key → extract fails → rejected).
- Counterexamples: selected plist with `RunAtLoad=true` → rc 2, zero writes (rig E); missing selected script → rc≠0 (127 from `zsh -n`), zero writes (rig H); author's 8-fault parametrized case also passes.
- Scoping is exact: a broken **unselected** plist (pit-snapshot `RunAtLoad=true`) does not block `--nightly-only` (rig F) but does block a default full install before writes (rig F2).
- Regression check on the new full-mode preflight: all six existing plists have matching Labels and explicit `RunAtLoad=false`, so the stricter preflight does not break the default path.
- Calendar reality (per contract, not imaginary guarantees): both night plists carry only `StartCalendarInterval` (18:30 / 20:40); no `KeepAlive`, `WatchPaths`, `StartInterval`, `StartOnMount`. `RunAtLoad=false` prevents launch **at bootstrap only**; after a real (non-dry-run) install launchd **will** fire these jobs at their next calendar times. That is intended deployment behavior, but operators must not read RunAtLoad=false as "cannot trigger".

### 4. Plist/S7 semantic deltas vs base (plistlib-level diff, not text diff)
- sync plist: only `FINANCE_CODE_ROOT` (was finance-workspace-runtime) and `FINANCE_SYNC_CODE_ROOT` (was finance-workspace-sync) changed, both → `/Users/a77/.finance-runtime/finance-sync-adcda94b5e40`. Schedule 18:30, `REVIEW_SYNC_PLAN=local`, venv python, data root, log paths, ProgramArguments, WorkingDirectory unchanged.
- finalize plist: only `FINANCE_CODE_ROOT` → `finance-l2-adcda94b5e40`, `FINANCE_GENERATION_CODE_ROOT` → `finance-generation-adcda94b5e40`, `FINANCE_SYNC_CODE_ROOT` → `finance-sync-adcda94b5e40`. Schedule 20:40, plan=local, `FORESIGHT_USER=linxiaoqi5111`, users dir, logs unchanged.
- S7 shell: only the `FINANCE_SYNC_CODE_ROOT` default follows the candidate root. `FINANCE_S7_ROOT` default unchanged (`finance-s7-sync`, on-disk HEAD `418515c0383334558a8dd44a0e741f39085115fa`, clean); staging wrapper default `/Users/a77/.local/bin/nightly-review-sync-staged.py` unchanged on disk (mtime Sep 10). No collector/provider code executed.
- Read-only root verification: all three `*adcda94b5e40` directories exist, `git rev-parse HEAD` = `adcda94b5e401158f1c3aa51f210e1e8d0f0b713`, `git status --porcelain` empty. Old roots (`finance-l2-d433b90788c0`, `finance-generation-387028b846a2`, `finance-workspace-sync`) still present.
- Comment claims spot-verified: `scripts/moneyflow` sources byte-identical between d433b907 and adcda94b (only `__pycache__` noise); `plan=local` is in `PLANS` of `market_feature_store/consumption_registry.py` in all three adcda roots (so no `unknown plan 'local'` rc=2); old sync tree HEAD `6382c13b7` is an ancestor of adcda94b. Nuance: the sync-plist comment's "逐字一致" is loose at whole-file level — `run_review_sync.py` was refactored on main to import `PLAN_CHOICES/resolve_plan` from the registry; the local-plan capability is verifiably preserved, which is the substance of the claim.

### 5. Residual failure risk (installer claims no transaction/rollback — confirmed, no such claim in code)
- No two-job atomicity: a failure between the two bootstraps (e.g., I/O error, launchd refusal) can leave sync loaded-new and finalize booted-out. Bounded by: per-job bootout+`|| true` then bootstrap under `set -e` (loud failure), tiny files, idempotent rerun, and the operator preconditions (both jobs idle, lock absent, hash preflight, backups with hashes/modes, explicit rollback prepared).
- Installer does **not** check root existence/cleanliness, job idleness, or the nightly lock — these remain operator release conditions (verified externally above for this machine, but not enforced in code).
- Controlled-release preconditions are sufficient for a supervised two-job plist+wrapper swap; this review does not sign data recovery or supplier completeness.

### 6. Post-release verification
- Reading **loaded** values (`launchctl print gui/$UID/<job>`) vs disk plists is an operator runbook step; the installer neither performs nor claims it. Out of installer scope; flagged as a required operator step. Other four jobs are not even bootout-ed by scoped install, so their loaded state is untouched. Runtime writes to sync runlog/quality inside the versioned root are pre-existing behavior of the S7 wrapper, not a deployment promise.

## Commands and results

| check | command (abridged) | result |
|---|---|---|
| existing installer tests | `pytest -p no:cacheprovider --basetemp=spec-k3/work/pytest-base tests/test_eval_launchd_installer.py -q` (venv python, FWP_TEST_RECEIPT=0, PYTHONDONTWRITEBYTECODE=1) | **20/20 passed** (3.06s) |
| existing wiring tests | same env, `tests/test_eval_launchd_wiring.py -q` | **33/33 passed** (10.42s) |
| ruff | `ruff check tests/test_eval_launchd_installer.py tests/test_eval_launchd_wiring.py` | All checks passed |
| installer syntax | `/bin/zsh -n scripts/install_eval_launchd.sh` | OK |
| independent rig | `spec-k3/work/independent_rig.sh` (real installer, fake HOME, stub launchctl; positive control + counterexamples A–I) | **21/21 assertions PASS** (`evidence/independent-rig.log`) |
| plist semantic delta | plistlib load of base (`git show f783f19c:…`) vs candidate, key-by-key | only the 5 intended root-role values changed |
| root pins | `git -C <root> rev-parse HEAD` / `status --porcelain` (read-only) | 3× adcda94b5e40…, clean; s7-sync 418515c0…, clean |

Rig initially reported 2 false FAILs caused by my own harness (duplicate filenames in diff output; reused launchctl log across parametrized runs); after fixing the harness (not the installer) all 21 assertions pass. No installer defect was behind either false failure.

## Issues

One low-severity documentary imprecision (see verdict.json): the sync-plist comment's "逐字一致" overstates file-level identity of the old local-plan patch (refactored into consumption_registry on main); functional equivalence is verified, so this is wording, not behavior.

## Limitations

- Bounded offline review only; no real install against the live HOME, no loaded-launchd-value verification, no live sync, no collector/provider execution.
- Author documentary evidence (docs/, verification logs, handoffs) deliberately not inspected; conclusions rest on code, plists, on-disk roots, and independent execution.
- Operator release conditions (idle jobs, lock absent, backups, rollback, post-release `launchctl print` checks) are outside the installer and outside this review's execution; their sufficiency is assessed, not performed.
- Data recovery, supplier completeness, and real night-run acceptance are not signed.

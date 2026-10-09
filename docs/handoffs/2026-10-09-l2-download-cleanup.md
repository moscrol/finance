# L2 Download Cleanup, 2026-10-09

## Authorization and Initial State

The user first requested disk cleanup, then explicitly requested: delete L2 download packages whenever a run finishes. The existing runner deleted packages only after success or an already-complete skip; its exception path deliberately retained them for retry. Six completed attempts had left 31,814,138,727 bytes (29.63 GiB) in the production data root's `state/l2-cache`.

No L2 process was active. Immediate cleanup acquired the same `state/locks/daily-full-review.lock` used by the pipeline, checked open files, and removed only regular archive/download filenames. Removed: `20260921.7z`, `20260922.7z`, `20260923.7z`, `20260924.7z`, `20261008.7z`, `20261009.7z`. Text instructions and candidate lists remained (16 KiB). Production databases, logs, credentials, historical reports and backups were untouched.

## Implementation and Decisions

Source branch: `fix/l2-download-cleanup-1009`, based on the locally observed `origin/main` at `6c1d9f5d4478`; source commit `e47d3308c1619e4506ea180ecfcf4382811a6684`. No remote fetch, push or main merge was performed. The original main checkout was behind and contained unrelated generated changes, so development used a separate worktree.

| Decision | Alternatives | Reason |
| --- | --- | --- |
| Put date-scoped cleanup in an outer finally | Success-only cleanup; retained failed downloads | Exceptions from readiness checks, download, parsing, ledger writes and metadata writes must not bypass cleanup. Failed attempts still fail and retries download again. |
| Handle normal CLI termination through SystemExit | Rely on default SIGTERM behavior | Default process termination does not unwind Python finally blocks. Real-process SIGINT and SIGTERM tests verify cleanup and nonzero exit. |
| Require an eight-digit ASCII day; unlink extraction symlinks | Treat the day as an arbitrary path; follow directory links | Cleanup must stay in the configured cache and never remove linked external contents. |
| Surface directory removal failures | shutil.rmtree(ignore_errors=True) | A permissions failure must not silently appear to have reclaimed disk space. |
| Deploy only this patch on the existing nightly base | Point nightly at current main; modify the existing frozen checkout | Avoid unrelated release changes and retain an intact rollback version. |
| Explicitly keep the old generation root | Let generation inherit the changed global code root | Preserve the existing report-generation deployment. |

The change is limited to `scripts/moneyflow/run_l2_from_share.py` and `tests/test_l2_file_source_quality.py`. Existing `cleanup_local` remains the cleanup owner; no separate generic cleanup tool or periodic sweeper was added. There is no new retention setting to drift from the user's requested policy.

## Local Deployment

The actual finalize LaunchAgent was using `ffe1c60d84da`, not the newer interactive runtime. A separate snapshot was created from that exact base and the source commit was cherry-picked:

- Runtime commit: `08bd011540f096b9bbb9070862163d8bb04eb8ed`.
- Runtime directory: `~/.finance-runtime/finance-l2-cleanup-1009` (detached, worktree locked).
- Diff against the previous nightly base: only the L2 runner and its tests.
- `FINANCE_CODE_ROOT`: new runtime directory.
- `FINANCE_GENERATION_CODE_ROOT`: explicitly pinned to the original `~/.finance-runtime/finance-workspace-ffe1c60d84da`.
- `FINANCE_PYTHON` and `FINANCE_SYNC_CODE_ROOT`: unchanged; the new snapshot's venv also links to the original interpreter.
- Finalize schedule: still 20:40; RunAtLoad remains false.
- Separate sync LaunchAgent: unchanged, verified by SHA-256.

Only the inactive finalize job was unloaded/reloaded. It was not kickstarted. Loaded configuration was read back with `state = not running`, `runs = 0`, and the expected roots. Original plist and deployment receipt are at `~/.finance-runtime/l2-download-cleanup-1009/finalize.before.plist` and `deployment.json`.

## Verification

Receipts are under `~/.finance-runtime/test-receipts/`:

| Run | Result | Receipt |
| --- | --- | --- |
| New expectations against original runner | 16 expected failures, 3 passes | 20261009T133833Z-6c1d9f5d-215421e74995.json |
| Initial fixed L2 suite | 49 passes | 20261009T133935Z-6c1d9f5d-f495dd2289d0.json |
| Expanded L2 and pipeline regressions | 81 passes | 20261009T134246Z-6c1d9f5d-edc176d7667d.json |
| Trading-day and generation-root regressions | 73 passes | 20261009T134329Z-6c1d9f5d-0b84dade67c5.json |
| Clean source commit e47d3308c | 81 passes | 20261009T134631Z-e47d3308-d228c63cefa4.json |
| Clean deployed snapshot 08bd01154, production interpreter | 53 passes | 20261009T134629Z-08bd0115-5d5de86c5c16.json |

One combined six-file attempt exceeded the 45-second tool timeout and has no passing conclusion; the two completed split runs provide the 154-test result. Existing datetime.utcnow deprecation warnings were not changed. Ruff, whitespace checks and commit hooks passed. The source development environment uses the existing locked workbench venv; the original main venv had unrelated httpx version drift and was not modified.

The 17 added cases cover success, already-complete skip, failures at every runner stage, failed ledger writes, KeyboardInterrupt/SystemExit, real-process SIGINT/SIGTERM, date isolation, path rejection, symlink handling and visible cleanup failure. Existing failed-archive and forced-rescan tests now require archive deletion while retaining their database integrity assertions.

After testing ended, identified scratch roots `pytest-1122`, `pytest-1125`, and `pytest-1126` were removed after verifying their test-specific contents and absence of active processes/open files. Test receipts and deployment evidence were retained.

## Limits and Continuation

This is a tested local deployment, not a main-branch merge or full CI certification. No live financial download, production ingestion, model request or scheduled end-to-end run was triggered. The next normal scheduled attempt will exercise the installed code against the actual upstream source. SIGKILL, a power loss, or an inaccessible filesystem can still leave artifacts; normal exception and termination paths are covered.

Future deployment must carry the source patch until normal main integration is approved. Preserve the old `ffe1c60d84da` directory because generation and the interpreter still depend on it. Do not retarget the interactive finance runtime or the sync job as part of this change.

To roll back the finalize configuration, first verify that the job is inactive, then restore the saved plist and reload that one job:

```sh
launchctl bootout gui/501/com.financeworkspace.daily-full-review-finalize
cp -p "$HOME/.finance-runtime/l2-download-cleanup-1009/finalize.before.plist" "$HOME/Library/LaunchAgents/com.financeworkspace.daily-full-review-finalize.plist"
launchctl bootstrap gui/501 "$HOME/Library/LaunchAgents/com.financeworkspace.daily-full-review-finalize.plist"
```

Rollback restores the previous retention behavior; it does not recover deleted download packages. They must be downloaded again when retrying their trade dates.

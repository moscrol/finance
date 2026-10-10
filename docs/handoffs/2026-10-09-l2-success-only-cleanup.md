# L2 Success-Only Cleanup Correction

## Authoritative Requirement

The user clarified: cleanup only after success; do not clean unsuccessful runs. This supersedes the earlier interpretation documented in `2026-10-09-l2-download-cleanup.md` and implemented by source e47d3308c / runtime 08bd01154. Those records are historical, not authorization to resume unconditional cleanup.

The six archives previously deleted under the earlier instruction cannot be recovered by changing code. No further production archive was deleted during this correction, and no re-download or financial run was triggered.

## Corrected Behavior

- A new attempt deletes its archive, partial-download files and extraction directory only after processing and metadata persistence return successfully.
- An already-complete date is eligible for cleanup only after the existing ledger/result validation succeeds.
- Readiness, share access, transfer, download, processing, ledger-write and metadata-write failures retain download artifacts.
- KeyboardInterrupt, SystemExit and real-process SIGINT/SIGTERM retain download artifacts. The special SIGTERM-to-cleanup handler was removed.
- Failure status and original exceptions remain visible. Retrying remains supported, without treating partial results as complete.
- Existing extraction scratch cleanup inside `process_date` is unchanged. This policy concerns retryable archives and partial downloads, not a promise to preserve every extracted scratch file.
- Date/path validation, symlink-safe removal and visible cleanup errors remain in place.

## Decisions

| Selected | Rejected | Reason |
| --- | --- | --- |
| Explicit cleanup on success | Cleanup in finally | Finally also runs on failure, contrary to the clarified policy. |
| Persist success metadata before deletion | Delete immediately after processing, before metadata | A metadata-write exception must not lose the package in that unsuccessful attempt. |
| Temporarily restore the original success-only nightly base | Leave unconditional cleanup deployed while fixing tests | Prevent additional unintended deletion during correction. |
| Advance the dedicated runtime while it had no consumers | Modify the original nightly base or leave uncommitted runtime edits | Preserve the original rollback base and record the corrected runtime in Git. |

## Sequence and Local Deployment

1. Confirmed source and runtime trees were clean; finalize was not running and had zero runs since its prior reload.
2. Switched the inactive finalize job back to the original success-only base `ffe1c60d84da`, preserving all other plist settings.
3. Updated failure-retention tests first. Ten cases failed against unconditional cleanup, demonstrating the unwanted behavior.
4. Changed the runner and verified 81 relevant source tests plus Ruff/whitespace checks.
5. Committed source fix `a0e2742ba`; cherry-picked it onto the dedicated, inactive runtime, producing `f0865392500e289d448f8ecaca6eb92770d23b38`. Named branch `fix/l2-success-runtime-1009` preserves the commit; the active checkout remains detached and locked.
6. Verified the runtime with the original production interpreter: 53 tests passed; its changed files are byte-identical to source.
7. Reloaded the finalize LaunchAgent with `FINANCE_CODE_ROOT=~/.finance-runtime/finance-l2-cleanup-1009`. It remains inactive, RunAtLoad=false, schedule 20:40. Generation and interpreter still use `ffe1c60d84da`; the sync plist hash is unchanged.

Against the original nightly base, only the L2 runner and its test file differ. The original base directory was not edited. The dedicated runtime directory now identifies f08653925 rather than 08bd01154; old test receipts must be interpreted using their recorded commit identity.

## Verification Evidence

Receipts under `~/.finance-runtime/test-receipts/`:

| Scope | Result | Receipt |
| --- | --- | --- |
| Retention expectations against prior implementation | 10 expected failures | 20261009T142444Z-656b5d1e-5ed31e8022da.json |
| Corrected source, four relevant test files | 81 passed | 20261009T142549Z-656b5d1e-6e9d7811590e.json |
| Clean runtime f08653925, production interpreter | 53 passed | 20261009T142814Z-f0865392-5afbc0a966ae.json |

Ruff, whitespace and commit hooks passed. The source receipt predates the code commit and records its dirty working tree; the clean runtime receipt binds the deployed version. Existing datetime deprecation warnings are unrelated.

Current deployment receipt: `~/.finance-runtime/l2-download-cleanup-1009/success-only-deployment.json`. It explicitly supersedes `deployment.json`. The rollback configuration `finalize.before-success-only-deploy.plist` points to the original success-only base; do not use `finalize.before-success-only.plist`, which is forensic evidence of the superseded unconditional-cleanup configuration.

## Remaining Boundaries

No live ingestion, upstream download, production database write, scheduled business run, main merge, push, PR or full-repository CI was performed. Actual failure logs and databases were retained. The next normal scheduled attempt will exercise the current policy against real upstream data.

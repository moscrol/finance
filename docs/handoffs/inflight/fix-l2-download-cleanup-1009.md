## This Branch
Delete L2 download artifacts after every completed attempt, including failures and normal termination. User authorized both immediate cleanup and the new retention policy.

## Decisions
| Selected | Rejected | Reason |
| --- | --- | --- |
| Date-scoped cleanup in finally | Keep failed archives for retry | Six retained archives occupied 29.63 GiB; retry can download again. |
| Patch the existing nightly base ffe1c60d84da | Switch nightly to newer main or edit its frozen tree | Isolate this change from unrelated releases and preserve rollback. |
| Pin generation to its original root | Let generation inherit the new root | Preserve the existing generation deployment. |

Details: ../2026-10-09-l2-download-cleanup.md.

## Current State
Source commit e47d3308c is local on this branch. Nightly snapshot 08bd01154 is installed at ~/.finance-runtime/finance-l2-cleanup-1009 and locked against worktree cleanup. LaunchAgent configuration is loaded, not started. No main merge, push or PR was performed.

## Verified
- Source: 154 related tests passed; clean e47d3308c rerun: 81 passed.
- Installed snapshot, original production interpreter: 53 passed.
- Ruff, diff checks and commit hooks passed.
- Loaded 20:40 finalize job points to the new snapshot; sync configuration unchanged; generation and interpreter still use ffe1c60d84da.
- Six archives removed under the shared pipeline lock: 31,814,138,727 bytes. Cache retained only 16 KiB of text files.

## Boundaries
No live download, production database write, scheduled run or repository-wide CI was executed. SIGINT/SIGTERM are covered; SIGKILL and power loss cannot execute finally. Filesystem cleanup failures surface as errors. Source main is unchanged, so future deployment must retain this patch until it is merged.

## Next Steps
Main integration requires user approval and normal repository gates. Observe the next scheduled L2 attempt without triggering a new financial run. Local deployment receipt and rollback plist: ~/.finance-runtime/l2-download-cleanup-1009/.

## Pitfalls
The main checkout is stale and dirty with other work. It was not edited. Keep ffe1c60d84da: generation and the new snapshot's venv still depend on it. A 45-second expanded test attempt timed out; only the subsequent completed runs support the test claims. This task's identified pytest scratch directories were removed after all its test processes ended.

## This Branch
L2 downloads are cleaned ONLY after confirmed success. The user's latest clarification overrides the earlier interpretation: failed or interrupted attempts retain archives and resumable parts.

## Decisions
| Selected | Rejected | Reason |
| --- | --- | --- |
| Cleanup after processing and metadata writes succeed | Unconditional finally cleanup | An unsuccessful attempt must retain its download for retry. |
| Cleanup on already_complete only after existing data checks pass | Delete based only on exit or elapsed time | Previously completed work is eligible only after ledger/result validation. |
| Keep path/symlink guards and visible cleanup errors | Remove all prior safeguards | Success-only retention does not weaken deletion boundaries. |

Current decision record: ../2026-10-09-l2-success-only-cleanup.md. The earlier l2-download-cleanup snapshot is historical, not the current policy.

## Current State
Source fix a0e2742ba is local on this branch. Deployed runtime f08653925 is at ~/.finance-runtime/finance-l2-cleanup-1009, detached and worktree-locked; named ref fix/l2-success-runtime-1009 also preserves it. The earlier 08bd01154 policy is superseded. LaunchAgent loaded, not started; no main merge, push or PR.

## Verified
- Changed retention expectations caught the old behavior: 10 expected failures.
- Corrected source: 81 related tests passed; runtime f08653925 using the production interpreter: 53 passed.
- Ruff, whitespace and commit hooks passed; deployed runner/tests match source bytes.
- Finalize still runs at 20:40. Generation, interpreter and sync configuration unchanged.
- No production downloads were deleted or financial jobs triggered during this correction.

## Boundaries
No live upstream run or repository-wide CI was performed. Existing extraction scratch cleanup inside process_date is unchanged; the retained retry assets are the downloaded archive and partial-download files. The earlier six deleted archives cannot be restored by this correction and require re-download if needed.

## Next Steps
Observe the next scheduled attempt. Main integration still requires approval and normal gates. Current local receipt: ~/.finance-runtime/l2-download-cleanup-1009/success-only-deployment.json. Use the success-only rollback plist named there, not a configuration that reinstalls 08bd01154.

## Pitfalls
Keep ffe1c60d84da: generation and the interpreter depend on it. The dedicated runtime checkout was advanced only while the job was unloaded from it; use commit identities, not the directory name, when interpreting older receipts. Source main and other worktrees were not modified.

# Conditional controlled release — not yet executed

Authorization: user said 执行 after plan to finish independent review, merge, and switch only two night jobs. No manual data collection, no kickstart, no 8792 switch, no old-root deletion.

Candidate to merge: c097d712f9acfdd258709c7d0de054f978e0159c, based on main f2c3e9e1a24f42ae9b1d5a8cb9e501ababd1330a. Prefer Gitea fast-forward-only merge (repository permits it), keeping the exact tested revision as main, rather than creating an untested merge commit. Recheck remote main/head immediately beforehand. Any intervening main change blocks and requires integration/revalidation, not a forced update.

Prerequisites:
- fixed candidate engineering leaves and scoped Spec→Quality accepted; original review signatures stay on their exact revisions, with review-applicability-final.json proving unchanged installed source/inputs after upstream #830;
- compare original installed six SHA256 values in prior preflight; any drift stops;
- root identities adcda94b5e40 clean, S7 wrapper/helper unchanged, old index and 18 L2/method files remain preserved;
- loaded two jobs idle and lock absent; require at least 10 minutes until the next 18:30/20:40 schedule, otherwise postpone;
- production DB no open writer; backup disk room. We do NOT claim real data validation from this;
- current 8792 health/code identity recorded. Readiness has a preexisting mismatch as of 16:19: snapshot 2026-09-21 vs DB 2026-09-18, HTTP503. It was observed before any deployment. Keep this as an unresolved data effect, not turn it green by unrequested sync.

Execution:
1. Save byte-exact backups/modes/hashes of two plists/two wrappers plus read-only reference copies of shared helper and S7 Python wrapper, loaded state snapshots, old roots/DB stat and unaffected four jobs/8792 configurations. Verify backup hashes. Prepare rollback before invoking installer.
2. Acquire the existing daily-full-review lock with current long-lived deployment-process PID, without deleting a preexisting lock. Re-read jobs idle and installed hashes under lock.
3. Explicitly bootout BOTH selected jobs before copying anything. This compensates operationally for the installer being a sequence of cp calls, not a cross-job transaction. No false atomic/auto-rollback claim. No other job bootout.
4. Invoke the existing reviewed scripts/install_eval_launchd.sh --nightly-only (no kickstart). Do not use a new collector/install implementation. Require successful bootstrap for both.
5. Verify exact installed content, loaded environment/arguments/calendar/RunAtLoad, two jobs not running/runs=0, three root identities. Verify unaffected jobs' configuration and stable PID/run counters where applicable, shared helper/S7 wrapper hashes, 8792 root/revision, old root/patch preservation and DB stat unchanged.
6. On any installer or postcheck failure, bootout only these two jobs and restore original four files with temporary-sibling+os.replace, preserving modes; bootstrap original plists and independently verify loaded old values. If rollback verification fails, report BLOCKED and retain all logs/backups; do not run collection to make it look healthy.
7. Release only our own lock (check PID and contents) in finally; never remove someone else's lock. Leave all original roots and backup copies intact.

Boundary: installing schedules means their NORMAL next scheduled executions use new roots. It does not imply that either job was run or proved successful during this release. Target-day rows/non-NULL prices, reports, L2 and generation results still need subsequent evidence.

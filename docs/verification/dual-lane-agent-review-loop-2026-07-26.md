# Dual-Lane Agent Review Loop Verification

Date: 2026-07-26
Branch: `feat/agent-runtime-backends-verify`
Canonical runtime: untouched

## Result

The Codex Producer and Claude independent Reviewer now coordinate through a
machine-validated schema-2 state store. External review is the only sealing and
release authority. Codex fallback can keep at most two development slices
moving and writes only to `provisional-verdicts/`.

This report covers the first real external falsification cycle. Request
`ARL-0016` reviewed commit `3cd4692fc121b7f96eb89a1d707b439ac17cdcf7`
from dependency commit `46e676dfbe267fa1eee6bc4314f1760742ce27ec`.
Claude returned `CHANGES_REQUIRED`; the Producer gate changed to `FIX` and did
not allow fallback or release.

## What the external review caught

The initial repair-chain reducer sealed every Git ancestor of an externally
passed repair. That was too broad: a milestone older than the repair's
`supersedes` boundary could be counted as sealed even when its artifact was not
part of the repair and it had no external verdict.

The repair candidate centralizes the proof in
`repair_covers_request(repo, repair, candidate)`. Coverage now requires all of:

- the candidate review ID is between the superseded review and the repair;
- the candidate commit is an ancestor of the repair commit;
- every candidate artifact is present in the repair's mechanically enforced
  artifact union.

Both the Producer gate and external worker call this same predicate. An older
uncovered milestone remains unsealed, prevents release, and stays on the
external-review frontier.

The repair also removes four whitespace defects reported by
`git diff --check` and adds the plan-required composed acceptance scenario.

The first repair candidate (`ARL-0017`) received a second
`CHANGES_REQUIRED`. It proved that artifact union alone was insufficient while
the repair request still used the latest dependency as `parent_commit`: an
intermediate provisional commit could be marked covered although its hunks
were outside the reviewer's diff. It also found that a failed repair blocked
the worker from scheduling a newer repair, and that request artifacts did not
have to include every changed path.

The second repair changes the invariant rather than adding another label:

- a repair follows the full transitive `supersedes` chain;
- its review range starts at the original failed request's parent commit;
- its artifact union covers the same full range;
- a repair of a failed repair keeps that original review root;
- the worker ignores an older failed repair only when a newer repair explicitly
  supersedes it;
- schema-3 requests must declare every changed path, while immutable schema-2
  history remains readable under its original contract.

## Deterministic evidence

- Agent-review suites after the second repair: `56 passed`.
- Clean full `intelligence/tests`: `2682 passed, 2 skipped` in 204.32 seconds.
- The composed scenario proves:
  - one provisional slice permits progress;
  - two provisional slices stop further speculation;
  - external `CHANGES_REQUIRED` taints the descendant and forces `FIX`;
  - a milestone repair with the full tainted artifact union can be externally
    passed and clear the bounded debt;
  - the final release request needs an external PASS and both frozen release
    checks;
  - official verdict files contain only the whitelisted external identity;
  - request hashes remain byte-identical;
  - a second worker cannot acquire the external-review lock.
- The narrow-repair regression proves an older milestone with a distinct
  artifact remains unsealed and is selected as the next external frontier.
- The repair-of-repair regression proves a newer repair is scheduled after the
  first repair receives `CHANGES_REQUIRED`, and that both repairs retain the
  original failed request's parent as their external review base.
- The schema-3 regression rejects a request that omits any changed path from
  its declared artifacts.

No deterministic test invokes Claude, Codex, or the nine-case live benchmark.

## Operational evidence

- Mutable state root:
  `/Users/a77/.finance-runtime/agent-review-loop`
- External worker tmux session: `finance-agent-review`
- Fallback worker tmux session: `finance-agent-fallback`
- Bootstrap metadata records the source commit and SHA-256 for the copied
  worker and reviewer prompt.
- Fourteen legacy records were classified without rewriting their request or
  verdict bytes:
  - 3 `LEGACY_SELF_REVIEW`
  - 8 `LEGACY_SUPERSEDED_UNSEALED`
  - 1 `LEGACY_ABANDONED_COMMIT`
  - 1 `LEGACY_EXTERNAL_REVIEW`
  - 1 `LEGACY_BOOTSTRAP_PROVISIONAL`
- `ARL-0016` was automatically consumed in a detached worktree. Its official
  Claude verdict was validated and atomically published; the worktree was
  removed afterward.

## Safety boundary

- No merge to `main`.
- No push or force-push.
- No canonical 8792 cutover or restart.
- No live benchmark.
- No secret, `.env`, PDF, ZIP, DuckDB, DB, SQLite, cache, or virtualenv file was
  added.
- External and fallback workers cannot directly publish each other's authority
  type.

The next request must be a milestone repair that depends on and supersedes
`ARL-0016`, includes `repair:ARL-0016`, and covers every artifact in the
original milestone plus this repair and verification document.

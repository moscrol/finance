# Dual-Lane Agent Review Loop Verification

Date: 2026-07-26
Branch: `feat/agent-runtime-backends-verify`
Canonical runtime: untouched

## Result

The Codex Producer and Claude independent Reviewer now coordinate through a
machine-validated schema-2 state store. External review is the only sealing and
release authority. Codex fallback can keep at most two development slices
moving and writes only to `provisional-verdicts/`.

This report covers the real external falsification chain through `ARL-0021`.
The chain begins at request `ARL-0016` and keeps the original review base
`46e676dfbe267fa1eee6bc4314f1760742ce27ec`. `ARL-0020` reviewed commit
`1aab11a8a160ee9a12609a422ac634c8b9a5aa78`, including the schema-3 deletion
repair and the same-Episode verifier-reentry slice. Claude returned
`CHANGES_REQUIRED`; its superseding `ARL-0021` repair was also reviewed and
returned `CHANGES_REQUIRED`. The Producer did not seal the milestone or allow
release.

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

`ARL-0018` then found two remaining contract gaps: schema-3 could not represent
a file deleted inside the review range, and a repair inherited artifacts but
not every superseded non-repair check. `ARL-0020` closes both gaps:

- a declared artifact may exist at either end of the review range, so deletion
  is reviewable without allowing an unrelated missing path;
- the repair request carries the transitive union of artifacts and non-repair
  required checks from the full supersedes chain;
- undeclared changed paths still invalidate a schema-3 request.

## Same-Episode repair slice

`GLMAgentRuntime.start()` now returns one live `EpisodeSession`. The session
keeps the original provider messages, event ledger, evidence accumulator,
query/tool session, registry, root budget, and deadline. A structural or
semantic verifier gap appends a `RepairGoal` to that same history and calls
`resume()`; the adapter never invokes a second `runtime.run()`.

The repair budget is enforced at execution rather than only shown in the
prompt:

- the exact granted calls cap the repair tool batch;
- the exact granted seconds create a repair-local deadline shared by the model
  action, tool execution, and finalization;
- model and tool wall time debit the live root ledger;
- later cycles read `remaining_calls` and `remaining_seconds` from that live
  ledger;
- cancellation, root-deadline expiry, or `repair_deadline_exhausted` stops
  further repair and semantic-judge cycles;
- structural and semantic repair paths both re-run their corresponding
  verifier before public projection.

The `ARL-0020` verdict also found that the external worker exported writable
authority-state request paths and that process cleanup/backoff was incomplete.
The superseding repair exposes only detached bundle copies, places the reviewer
in its own process group, kills descendants even after the group leader exits,
records launch failures as transport backoff, and starts retry delay when a
long failed review actually finishes.

## ARL-0021 repair findings and current fix-forward candidate

`ARL-0021` verified the seconds-grant, same-Episode semantic repair, process
group, backoff, and detached-bundle fixes, then found three remaining authority
or deadline defects plus two range/artifact issues. The current candidate fixes
them at their owning seams:

- `validate_verdict_file()` now requires the caller's expected review ID;
  gate, worker, and fallback all pass it, and the publisher rechecks the
  validated ID before atomic replace. A valid older verdict can no longer be
  copied into the current frontier's filename.
- External and fallback reviewer environments receive only detached bundle
  paths plus bundle-local scratch. They no longer receive `STATE_ROOT` or
  `PRODUCER_REPO`. The versioned worker default delegates only to the one-shot,
  no-tool adapter path instead of granting `Write`, `acceptEdits`, or broad
  Bash permissions.
- Episode-deadline expiry stops additional research but no longer consumes the
  root verification reserve. Semantic verification still runs against the
  root deadline; actual root expiry remains fail-closed and skips the judge.
- One GLM `EpisodeSession` now exposes the same append-only `EvidenceLedger`
  and its initial snapshot across start and resume. Evidence is appended during
  tool execution; only the structural-verifier projection marks required
  outputs covered. Repair progress no longer closes an evidence-grounded gap
  without a bound evidence hash.
- Initial planning/finalization model wall time, repair model time, and tool
  time all debit the same root seconds ledger. A repair that stops without a
  tool action remains partial, terminates re-entry, and does not increment the
  consumed repair-cycle count.
- A terminal semantic repair records `semantic_verifier_stale=true` when the
  retained semantic verdict predates the final episode state, preventing
  consumers from silently pairing different snapshots.
- Schema-3 accepts an artifact created and deleted entirely inside the review
  range by proving it appeared in the commit history. The safety allowlist now
  also rejects `mcp_config.json`, `feishu_config.json`, and `*.pptx`.
- An external `CHANGES_REQUIRED` remains blocking until an externally passed
  repair seals it; a provisional repair can never override that authority.

## Deterministic evidence

- Exact `ARL-0020` detached preflight:
  - agent-review suites: `58 passed` in 53.66 seconds;
  - Episode/session/repair/verifier/adapter suites: `278 passed` in 1.14 seconds;
  - clean full `intelligence/tests`: `2686 passed, 2 skipped` in 184.31 seconds.
- `ARL-0021` candidate:
  - agent-review suites: `63 passed` in 67.70 seconds;
  - Episode/session/repair/verifier/adapter suites: `285 passed` in 0.72 seconds;
  - clean full `intelligence/tests`: `2698 passed, 2 skipped` in 194.34 seconds.
- Current `ARL-0022` fix-forward candidate:
  - agent-review suites: `72 passed` in 79.85 seconds;
  - Episode/session/repair/verifier/adapter suites: `288 passed` in 0.73 seconds;
  - clean full `intelligence/tests`: `2710 passed, 2 skipped` in 207.89 seconds;
  - Ruff and `git diff --check`: pass.
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
- The deletion regression accepts a declared deleted artifact while continuing
  to reject undeclared additions, edits, and deletions.
- The same-Episode regression proves exact event-prefix preservation,
  `start=1/resume=1/run=0`, live call/seconds accounting, no action after a
  granted deadline expires, semantic-gap re-verification, and bounded repair
  termination.
- Worker lifecycle regressions prove bundle-only request/claim exposure,
  descendant process-group cleanup, transport backoff on launch failure, and
  completion-relative exponential backoff.

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
- `ARL-0016` through `ARL-0021` were consumed in detached worktrees. Official
  Claude verdicts were schema-validated and atomically published; worktrees
  were removed afterward.
- The oversized `ARL-0020` review exposed a reviewer-cost seam. Operational
  recovery separated deterministic preflight from a schema-constrained
  one-shot Claude semantic review. This adapter is held in mutable state for
  the repair review and must be versioned and independently reviewed before a
  release request can rely on it.

## Safety boundary

- No merge to `main`.
- No push or force-push.
- No canonical 8792 cutover or restart.
- No live benchmark.
- No secret, `.env`, PDF, PPTX, ZIP, DuckDB, DB, SQLite, config credential,
  cache, or virtualenv file was added.
- External and fallback workers cannot directly publish each other's authority
  type.

The next request must be a milestone repair that depends on and supersedes
`ARL-0021`, includes `repair:ARL-0021`, retains the original `ARL-0016` parent
as its review base, and declares every changed path through this verification
document. Release remains blocked.

# Codex App Server Spec v2 Independent Review

Date: 2026-07-29
Reviewer: fresh read-only `gpt-5.6-sol` Codex CLI process
Verdict: `CHANGES_REQUIRED`
Reviewed worktree tip: `0b2f5a1c`

## Review provenance

The reviewer was launched as a separate ephemeral process with no write permission
to the worktree. It inspected the v2 design, its verification note, the completed
headless ablation, the canonical handoff corrections, and the exact local App
Server protocol. The raw final review was written outside Git under
`/private/tmp/app-server-v2-independent-review.md`; this file preserves the
actionable verdict without copying private reasoning or runtime logs.

## P0 findings

1. The valid three-case profile-D artifact used live roots and cannot serve as
   the same-fixture five-case App Server control.
2. A full Git checkout exposes questions, required outputs, references, results,
   and post-cutoff history. The experiment needs a curated, leak-scanned export.
3. `dynamicTools=null` does not close apps, browser, computer use, image,
   collaboration, host IPC, Keychain, or descendant-process capabilities.
4. The blind rule requires five cases while the baseline contains three and
   does not freeze the exact answer projection.
5. `sources[]` had no immutable claim-span/evidence-ledger join, so numeric
   lineage could not be deterministically audited.

## P1 findings

1. The schema command omitted mandatory `--out`; the listed
   `ServerRequest.json` hash was malformed.
2. Isolated authentication did not name one permitted non-interactive mechanism.
3. Quota reads were ordered inconsistently and did not guard each attempt.
4. Requested model/tier was not bound to returned execution identity, and
   `fast_mode` was not disabled.
5. A transient retry could reset the 180-second budget.

## Required gate

No App Server implementation or live answer is authorized until a corrected
spec receives a new independent `PASS`. After that PASS, the sealed export/PIT
fixture and a new same-fixture five-case profile-D control must exist before the
App Server runner is implemented or executed.

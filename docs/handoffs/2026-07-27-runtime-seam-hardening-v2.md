# Adaptive Runtime Seam-Hardening Handoff v2

Date: 2026-07-27

Status: `offline_green; live_gate_blocked_by_credential`

## Candidate

- Worktree: `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667`
- Branch: `feat/agent-runtime-backends-verify`
- Candidate tip: `49aeb9a3`
- Previous product tip: `b924014f`
- `main` and canonical `8792`: untouched; no merge or runtime switch performed.
- Existing `8799`: not restarted or modified by this handoff.

## Completed in this slice

1. **Public artifact boundary**
   - Warm `ArtifactRegistry` caches now evict a run artifact when it becomes
     `internal`; it is not resurrected as a public `missing` descriptor.
   - The failed/no-answer orchestrator path now registers
     `continuous-episode.json` as `internal`, non-previewable and
     non-downloadable, matching the success path.

2. **Semantic verifier fail-closed recovery**
   - `_JudgeCall.monotonic_release_safe` now defaults to false.
   - Only typed deadline/transient failures can release a sanitized candidate;
     malformed JSON/tool output cannot be rewritten as a transient timeout.
   - A valid late rejudge still permits deletion-only monotonic release.
   - Independent judge outage preserves `correlated_judge=false`.

3. **Repair budget boundary**
   - Progress repair grants are clipped to both `RepairGoal.remaining_calls`
     and `remaining_seconds`; sub-second/no-call grants are refused.

4. **Valuation freshness and provenance**
   - Eastmoney valuation snapshots carry the provider serving date (`f86`).
   - Valuation evidence embeds and propagates that date through the same
     structured freshness floor as other current-market evidence.
   - Missing/stale valuation serving dates fail closed instead of emitting
     undated current evidence.

5. **Private diagnostic provenance**
   - Continuous Episode private artifacts now persist one redacted
     `research_context` with `information_cutoff`, `today`,
     `latest_data_date`, and `trace_parent_id`, including failure artifacts.

## Verification

- Focused seam suite: `285 passed`.
- Adapter/orchestrator focused suite: `136 passed`.
- Full project venv run: `3257 passed, 3 skipped, 11 failed`.
  The 11 failures are the pre-existing `subconscious/userspace` local-path
  baseline (FORESIGHT/AGENT_MEMORY test-environment overrides), not this slice;
  no new failure appeared in the changed modules.
- Final dry-run artifact:

  `/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27-49aeb9a3-dry-run.json`

  It records `source_revision=49aeb9a3`, `source_dirty=false`, five planned
  cases, and zero acceptance-contract gaps.

## Live gate

The formal five-case live command was attempted once with the correct data
roots and stopped before executing a case because the saved macOS Keychain
provider for `linxiaoqi5111` is unavailable. No key was printed, copied,
persisted, or written to Git. The old 8799 session-only credential was not
inspected or reused. Therefore there is no new live result for this revision;
the previous 40% self-use result remains historical evidence, not a release
gate.

To finish the release gate, save/authorize the provider once in the Workbench
Keychain flow, then run the five-case benchmark exactly once against this clean
tip. If the key remains unavailable, this is an external credential blocker,
not a routing or evidence-quality failure.

## Do not do next

- Do not rerun the five/nine questions as a debugging loop.
- Do not loosen verifier thresholds or add question-specific routes.
- Do not merge `main`, switch `8792`, or delete the legacy path.
- After one valid live artifact exists, run the independent review once against
  the exact artifact revision and decide release readiness from the frozen
  evidence, not from the old 8799 self-use summary.

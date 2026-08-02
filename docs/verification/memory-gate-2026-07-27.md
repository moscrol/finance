# Memory Gate Verification

Date: 2026-07-27  
Branch: `feat/agent-runtime-backends-verify`  
Product commit: `7a9d7c85`

## Result

Durable memory promotion now has one fail-closed `MemoryGate` seam. The gate
does not write files. It returns an immutable `PromotionDecision` only when a
candidate is backed by either:

- an existing checkpoint with a latest terminal `hit`, `partial`, or `miss`
  verdict; or
- one exact explicit correction record matched by timestamp and correction or
  principle text.

`unverifiable`, missing provenance, volatile facts, and naked model judgments
are rejected. A reviewed `miss` may produce a durable lesson because learning
what failed is valid experience, but the stored provenance retains `miss`.

## Replay and channel safety

Every decision binds the normalized candidate content SHA-256. Validated
writers recompute the hash before append, so one approval cannot be replayed
for different content.

Authority is also channel-specific:

- checkpoint decisions may write only validated judgments;
- explicit correction decisions may write only validated preferences or
  corrections;
- cross-channel replay is rejected even when the content is identical.

The persisted promotion metadata contains only candidate ID, reason, content
hash, and checkpoint/verdict or correction timestamp provenance. It excludes
prompts, SQL, provider bodies, evidence excerpts, and current market facts.

## Legacy compatibility

Existing `judgments.jsonl` and `corrections.jsonl` records remain readable and
continue to act as legacy user priors. They are not rewritten, deleted, or
silently labelled as validated. Only new calls through
`record_validated_judgment()` or `record_validated_preference()` may carry a
`promotion` object.

## Verification

```text
49 passed in 0.09s
114 passed in 0.31s
```

The second command includes MemoryGate, judgments, corrections, user-memory,
checkpoint/verdict logic, and all permanent repair/session invariants. Ruff and
`git diff --check` passed.

## Non-actions

- no live benchmark;
- no prompt injection from promotion decisions;
- no automatic generation of memory candidates from every answer;
- no 8792 switch;
- no `main` merge;
- no review-harness changes.

# FinanceQuery and EvidenceSearch Milestone Verification

Date: 2026-07-27

Branch: `feat/agent-runtime-backends-verify`

Product milestone commit: `fe478ae4`

## Result

Phase 2 is complete at the deterministic product seam. The primary model can
submit typed structured queries and closed-loop evidence searches inside one
continuous Episode. Code still owns authorization, root budget, information
cutoff, evidence identity, and publication truth; it no longer reorders valid
model calls by a hidden question-type priority table.

## Focused verification

Command covered FinanceQuery, EvidenceSearch, closed-loop retrieval, tool
batching, episode composition, GLM continuation, OpenAI Agents SDK adapters,
information cutoff, and permanent repair/session invariants.

Result:

```text
243 passed, 1 skipped
Ruff passed
git diff --check passed
```

The skipped case is an existing optional adapter case, not a milestone
failure.

## Full deterministic suite

```text
2761 passed, 2 skipped, 11 failed
```

All 11 failures are the unchanged local-path contamination baseline in
`test_subconscious.py` and `test_userspace.py`: those tests resolve live
`/Users/a77/agent-memory/.foresight` state instead of their patched temporary
user root. No failed test touches FinanceQuery, EvidenceSearch, Episode repair,
tool ordering, cutoff, or the runtime adapters.

## Contract evidence

- Tool schemas are owned by each `ToolSpec`; FinanceQuery publishes a
  dataset-specific `oneOf`, fixed snapshots publish honest empty-object
  schemas, and canonical structured arguments deduplicate independent of key
  order.
- Frozen nested model arguments are restored to ordinary JSON objects/arrays
  once at the Registry boundary. This closes the direct-call-versus-real-model
  tuple/list seam found by the full Episode test.
- Budget clipping preserves the model-submitted order. Permission, remaining
  slots, the four-call batch ceiling, deadline, and cancellation remain hard
  code-owned gates.
- FinanceQuery exposes six semantic datasets, hides physical tables, binds SQL
  values, opens DuckDB read-only, and enforces row, byte, timeout, cancellation,
  and publication limits.
- FinanceQuery validation, timeout, cancellation, limit, and execution failures
  return empty typed observations with repairable gaps. Public observations and
  traces do not expose SQL or physical table names.
- EvidenceSearch preserves narrow/broad/counter attempts and semantic-judge
  rejection. It deduplicates first by non-empty content hash and falls back to
  source path plus chunk only when no hash exists.
- The cutoff negative case records `future_of_cutoff` in `ProviderTrace`, keeps
  the served/requested dates, and proves the future document never enters the
  model observation or evidence ledger.
- Per-tool ProviderTrace is exported in the private artifact. The real scripted
  Episode asserts an invalid FinanceQuery `parse_error`, a later successful
  FinanceQuery, and EvidenceSearch traces independently.
- A structural partial exports `missing_outputs` and the concrete per-output
  gap under `structural_verifier`. It is therefore possible to construct a
  RepairGoal without reverse-engineering prose.
- The real scripted GLM Episode observes a typed field error, rewrites the
  query, calls `finance_query` then `evidence_search` in model order, binds both
  evidence types, receives a verifier-generated RepairGoal, and resumes the
  same provider history.
- Repair events carry `episode_id`, `repair_goal_id`, and `cycle`. Successful
  repair removes resolved gaps from the current `AgentOutcome`; historical
  errors remain auditable in events and traces.

## Boundaries and explicit non-actions

- The nine-case frozen live benchmark was not run.
- No live provider quota was consumed for this deterministic milestone.
- Canonical runtime 8792 was not touched or restarted.
- `main` was not merged or switched.
- `continuous_glm` token accounting remains a later delivery-contract item;
  this milestone verifies tool and repair continuity, not Phase 3 economics.
- The next live signal is one `weekly-market-cause` smoke after S2/S3/S4, not a
  repeated nine-case development loop.

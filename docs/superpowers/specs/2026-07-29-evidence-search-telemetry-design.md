# Evidence Search Retrieval Telemetry Design

Date: 2026-07-29
Status: approved by the user's instruction to execute the reviewed Phase C
handoff when its conclusions hold

## Objective

Create a reproducible true-Hybrid baseline for the two bounded Phase C cases,
then make every underlying retrieval attempt visible through
`EvidenceSearchResult` with four facts:

- requested retrieval mode;
- effective retrieval mode;
- fallback reason;
- whether the attempt degraded.

This slice does not implement the causal anchor guard or valuation filtering.
Those behaviors need the telemetry baseline produced here and remain separate
subprojects.

## Verified premises

- The freshness seam remains green at KB commit `9053b0c4`.
- `/Users/a77/knowledge-base-private/.rag_venv/bin/python3` imports
  `FlagEmbedding`, `rank_bm25`, `yaml`, and `numpy` under Python 3.12.13.
- BAAI/bge-m3 weights are already cached locally.
- The isolated KB clone has no `.rag_venv` or `.venv` because both paths are
  gitignored, so `_resolve_rag_python` otherwise falls back to the finance
  interpreter and can silently degrade Hybrid to BM25.
- A direct true-Hybrid probe still ranks `wiki/entities/天奈科技.md`, proving
  the valuation contamination is not merely a BM25 artifact.

The existing dense venv is a symlink into `/Users/a77/知识库`. It is accepted
only as an explicitly pinned interpreter/package source. Wiki and index paths
remain the isolated private-root clone; the legacy Chinese root is never a
retrieval data source.

## Alternatives considered

### A. Copy only the last `ClosedLoopRetrievalResult.telemetry`

This is the smallest change, but it loses the first-call
`dense_dependency_missing` event when later calls report
`dense_dependency_cached_unavailable`. Rejected because it preserves the
current ambiguity.

### B. Add one aggregate telemetry object to `EvidenceSearchResult`

This makes the final mode visible, but a single fallback reason still cannot
represent different narrow/broad/counter outcomes without inventing an
aggregation policy. Useful as a summary, insufficient as the source of truth.

### C. Extend each `RetrievalAttempt` with immutable mode/fallback fields

Selected. `EvidenceSearchResult` already returns the ordered attempts, so the
attempt is the natural owner of the retrieval decision made for that call.
Existing attempt fields remain compatible through defaults. The provider trace
adds a compact aggregate for downstream inspector visibility, but the ordered
attempts remain authoritative.

## Data model

`closed_loop_retrieval.RetrievalAttempt` gains:

```python
requested_mode: str = ""
effective_mode: str = ""
fallback_reason: str = ""
degraded: bool = False
```

`_run_aperture` copies these fields from each returned
`WikiRagResult.telemetry` at the same point where status and hit count are
recorded. Budget-exhausted attempts keep empty/default retrieval fields because
no retrieval was executed.

`ClosedLoopRetrievalResult.inspector_dict()` includes the four new fields for
each attempt. `EvidenceSearchResult.attempts` therefore exposes the complete
ordered sequence without adding a second telemetry ledger.

`evidence_search._trace_detail()` appends a stable mode summary. A true Hybrid
run is explicit (`hybrid->hybrid`, no fallback, not degraded); a fallback run
records `hybrid->bm25`, its reason, and `degraded=true`. Provider trace status
continues to describe whether evidence was returned; degradation is a separate
observable rather than being conflated with empty/error status.

## Baseline execution

The true-Hybrid replay pins all of the following:

```text
KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python3
Wiki=/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/wiki
Index=/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/.rag_index
cutoff=2026-07-24
require_fresh=true
RAG_WORKER_ENABLED=0
HF_HUB_OFFLINE=1
```

Both `ruihuatai-valuation` and `weekly-market-cause` use the same
narrow/broad/counter `EvidenceSearch` path. The receipt records interpreter,
Python version, index hashes, requested/effective mode per attempt, latency,
queries, and top evidence paths. Generated access-log lines are removed after
the receipt is captured so the isolated KB source tree remains clean.

## Failure behavior

- If the explicit interpreter cannot import the dense stack, the baseline is
  invalid, not a quality failure.
- If telemetry says effective BM25 or degraded, the run is a fallback baseline
  and must not be labelled true Hybrid.
- If index hashes differ from the clean snapshot receipt, stop before comparing
  retrieval quality.
- Empty, timeout, stale, and future-of-cutoff statuses retain their existing
  meanings; the new fields only report how retrieval was attempted.

## Tests

Add focused tests proving:

1. a first-call dense failure appears on the corresponding attempt as
   `hybrid -> bm25`, `dense_dependency_missing`, degraded;
2. cached fallback appears as `dense_dependency_cached_unavailable` and is not
   erased by the evidence projection;
3. true Hybrid appears as `hybrid -> hybrid`, empty fallback, not degraded;
4. inspector serialization and provider trace detail expose the same attempt
   facts;
5. deadline-exhausted attempts remain valid with empty/default mode fields.

Run tests with the exact interpreter path recorded. Finance unit tests use
`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`; live dense
retrieval uses the explicit `KB_RAG_PYTHON` subprocess.

## Non-goals and guardrails

- No merge of KB commit `9053b0c4` into the original knowledge repository.
- No causal anchor or valuation-filter implementation in this slice.
- No 28-case run, App Server work, verifier relaxation, or 8792/8799 change.
- No in-place index rebuild and no retrieval from `/Users/a77/知识库/wiki`.
- No generated access log, virtualenv, model weight, index binary, or secret is
  committed.

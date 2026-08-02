# Phase C Freshness Seam Design

Date: 2026-07-29  
Status: approved direction — manifest-first effective freshness  
Runtime worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`  
Knowledge-base source: `/Users/a77/knowledge-base-private` (read-only original)

## Goal

Make the existing format-2 RAG index usable through the real
`kb_rag.retrieve(require_fresh=True)` path when, and only when, its manifest
matches the selected Wiki snapshot and its age policy is valid. Preserve Git
revision and historical dirty-build state as provenance rather than confusing
them with content freshness.

After that seam is green, pin a clean snapshot receipt, generate the real
runtime capability dry-run, and replay only the bounded 瑞华泰 valuation and
weekly-cause queries.

## Current failure

`scripts/rag_index.py query` currently evaluates freshness from `store.meta`
before loading the retriever. The helper compares `source_git_revision` with the
checked-out `HEAD`; that comparison reports `stale` even though the format-2
manifest matches the current Wiki exactly. Default stale policy then exits with
code `3`.

If the Git mismatch alone is removed, historical `source_dirty=true` produces
`unknown`. The CLI would return hits, but `kb_rag.retrieve(require_fresh=True)`
would reject every hit because freshness is copied from one index-level value
and only `fresh` is admissible.

## Chosen design

Use the format-2 manifest as the effective content-freshness authority:

1. `RagStore.index_freshness(vault_root)` recomputes the exact manifest using
   the index metadata's `include_raw` and `max_files` scope.
2. Index age remains a hard freshness constraint.
3. Git revision mismatch, current Git working-tree state, and historical
   `source_dirty` remain visible provenance diagnostics. They do not override a
   matching manifest because they do not prove content divergence.
4. A missing/legacy manifest remains `unknown`; a mismatched manifest remains
   `stale`. Neither can enter formal runtime evidence.
5. The query CLI receives the real Wiki `vault_root` when computing freshness;
   the same resulting index-level state is emitted on every hit.

This is not a `RAG_STALE_POLICY=ignore` workaround and does not weaken
`require_fresh=True`.

## Alternatives rejected

### Keep Git and `source_dirty` as hard gates

Smallest code change, but it cannot produce runtime `fresh` for content-identical
indexes built from a dirty or different branch. It preserves the false negative.

### Build a new generalized freshness framework

A typed content/provenance/effective report would be attractive long-term, but
it expands this bounded repair into a new subsystem. The current tuple interface
can preserve diagnostics without that refactor.

## Isolation

The original `/Users/a77/knowledge-base-private` working tree remains untouched.
Implementation occurs in a clean local clone/worktree on branch
`fix/manifest-freshness-cli`. No changes are made to finance `main`, canonical
8792/8799, the 28-case suite, or App Server.

## Public seams and tests

The agreed behavior seams are:

1. `scripts.rag_freshness.check_index_freshness(...)`
   - format-2 matching manifest + valid age → `fresh`, even when Git provenance
     differs or historical `source_dirty=true`;
   - mismatched manifest → `stale`;
   - missing/legacy manifest → `unknown`;
   - expired index → `stale`.
2. `scripts/rag_index.py query --json`
   - default fail policy does not early-return for a manifest-fresh index;
   - every returned hit carries `index_freshness=fresh`;
   - stale remains exit code `3`.
3. Finance runtime `kb_rag.retrieve(..., require_fresh=True)`
   - receives at least one bound hit from the pinned clean snapshot;
   - continues to reject stale and unknown fixtures.

Tests are written red-first at these seams. No test may merely call a private
helper and assert its own implementation.

## Clean snapshot receipt

The receipt pins:

- clean KB revision and branch;
- Wiki root and index directory;
- `source_revision`, `source_git_revision`, `source_dirty`, `include_raw`, and
  `max_files`;
- hashes for `meta.json`, `chunks.jsonl`, `dense.npy`, and
  `bm25_tokens.jsonl.gz`;
- block-level `rag_index.py check` result;
- manifest effective freshness;
- CLI query freshness;
- finance runtime `require_fresh=True` result.

If a clean incremental refresh can reuse every vector, it may be used. It must
not substitute a hash-vector index for the BGE-m3 candidate.

## Phase C continuation

Once the receipt is green:

1. generate the current runtime dry-run and pin actual allowed capabilities;
2. replay `evidence_search` for 瑞华泰 valuation and weekly-cause queries against
   the exact receipt root/index;
3. record latency, candidate pages, cutoff filtering, semantic filtering, and
   evidence atoms;
4. classify the remaining gap as index recall, result quality/latency, model
   selection/repetition, cutoff, or completion/verifier disagreement.

## Exit criteria

- Original KB and canonical runtimes unchanged.
- Focused KB freshness/query tests green.
- Finance runtime focused retrieval tests green.
- Clean receipt proves runtime `fresh`, not merely CLI success.
- Capability dry-run and both bounded replay artifacts pinned.
- Final verification and handoff state what remains unproven; no Codex/Knevo or
  28-case claim is made from this slice.

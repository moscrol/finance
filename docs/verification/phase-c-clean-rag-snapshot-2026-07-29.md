# Phase C Clean RAG Snapshot Receipt

Date: 2026-07-29  
Status: **clean snapshot receipt verified**  
Finance candidate runtime: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`  
Knowledge-base clone: `/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness`  
KB branch/commit: `fix/manifest-freshness-cli@9053b0c4137428e9ad9d8b4be3ba475b7377b435`

## What is pinned

```text
KB_VAULT=/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/wiki
RAG_INDEX_DIR=/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/.rag_index
```

No command in this Phase C slice wrote the original
`/Users/a77/knowledge-base-private` repository. At the final audit it is still
on `main@883815c9`; concurrent worktree changes exist in raw/disclosure and
relations paths, while the five indexed page directories remain at 0 dirty
entries. The clean clone is based on private `main@883815c9` and has 0 dirty
entries in those indexed directories. Do not treat the original worktree's
full status as the clean receipt; the clone and the hashes below are the
controlled experiment surface.

## Snapshot metadata

```json
{
  "format_version": 2,
  "built_at": "2026-07-29T01:15:00",
  "model": "bge-m3",
  "num_chunks": 104611,
  "dim": 1024,
  "include_raw": false,
  "max_files": 0,
  "source_revision": "manifest:v1:51ddfe839f262d718b3da6635be711b884f8f0d310f3aa16f5807fa07d294a08",
  "source_git_revision": "883815c9b43658339b6308a6494536d2e71b9ad7",
  "source_dirty": false,
  "source_fingerprint": "d43595e997f0282915ac32cd14f01b0bd354084f9bd3dab8dbe14d73130b8151",
  "source_file_count": 9753,
  "reused_existing_embeddings": true,
  "rebind_source_index_built_at": "2026-07-28T00:53:02"
}
```

The BGE-m3 vectors, chunks, and BM25 token corpus were copied from the verified
candidate index and re-bound to the clean clone's exact source manifest. No
hash-vector substitute was used and no new embeddings were silently claimed.
`reused_existing_embeddings=true` makes this distinction explicit: this is a
clean provenance rebind after an exact content match, not a fresh BGE embedding
build. The original index's historical `source_dirty=true` metadata remains
available in the earlier Phase C report; it was not overwritten in place.

## Artifact hashes

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `.rag_index/meta.json` | 721 | `3ab0d301c7480a8ee12ebb2540a0d03421b722ea193ca0ac1a754289129ac79b` |
| `.rag_index/chunks.jsonl` | 144,779,492 | `76034c6e4e8db169dc5b0963ce3992c1c4482d5e50b901a5178e9c3a32bf7f3c` |
| `.rag_index/dense.npy` | 214,243,456 | `6a012a5c66f18ebdf2da148b911e636aecfdf6291eeab4d583a181c9ef563b10` |
| `.rag_index/bm25_tokens.jsonl.gz` | 53,705,057 | `64549ce54c11e80eb580ff49e0f6b1e2d60a33cdd9c9bfa6e6363f0df9f8314a` |

## Freshness gates

| Gate | Result |
|---|---|
| `rag_index.py check` | `indexed=104611 current=104611 stale=0 (added=0 changed=0 removed=0)` |
| `RagStore.index_freshness(clean_clone/wiki)` | `fresh` |
| CLI `query 瑞华泰 --mode bm25 --k 3 --json` with default `STALE_POLICY=fail` | exit `0`; 3 hits, each `index_freshness=fresh` |
| Finance `kb_rag.retrieve(..., require_fresh=True)` | `ok=true`, 3 hits, telemetry `index_freshness=fresh`, warning empty |

The finance runtime probe used the same clone Wiki and index. It returned the
same three top pages as the direct CLI probe, with content hashes attached and
latency about 12.4 seconds on this machine. This is the end-to-end proof that
the runtime evidence gate now receives `fresh`; it is not inferred from a CLI
exit code alone.

## Focused implementation verification

In the isolated KB clone, the final freshness/retrieval/release/evaluation
focused set:

```text
49 passed
ruff check: passed
git diff --check: passed
```

The implementation commit is `9053b0c4` (`fix: use manifest freshness for RAG
queries`). The finance candidate branch keeps the design/plan and verification
receipts; `main`, 8792/8799, the 28-case suite, the original KB, and App Server
remain outside the implementation surface.

## Boundary

This receipt proves the freshness and retrieval transport seam. It does not yet
prove capability authorization, causal/valuation evidence quality, or Codex/Knevo
parity. Those are the next bounded Phase C steps and must reference these exact
root/index paths and hashes.

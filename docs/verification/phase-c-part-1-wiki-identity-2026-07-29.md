# Phase C Part 1 — Wiki Identity and Index Provenance

Date: 2026-07-29  
Execution branch: `feat/agent-runtime-backends-verify`  
Execution revision: `342be37878d7d8e07dd7ccf7bcb5f1efce0f4079`  
Status: **identity decision complete; clean replay snapshot not yet released**

## Scope

This slice fixes the evidence identity question before any retrieval-quality
experiment:

1. prove whether the two Wiki roots are aliases;
2. record their Git identity, index identity, freshness, and selected file hashes;
3. select one canonical root for the next Phase C slices.

It deliberately did **not** run `evidence_search`, capability dry-run, live
benchmark, App Server code, or any index build/update. All checks below were
read-only.

## Decision

The canonical **root identity** for the next runtime experiments is:

```text
/Users/a77/knowledge-base-private/wiki
```

The canonical **structured index candidate** is:

```text
/Users/a77/knowledge-base-private/.rag_index
```

This is a path decision, not a release claim. The current filesystem/index
pair is content-consistent, but its provenance is dirty and the runtime
freshness seam currently classifies it as stale. It is therefore **not yet a
clean replay-ready PIT snapshot**.

## Root identity evidence

| Root | Filesystem identity | Git identity | Wiki inventory | Working tree |
|---|---|---|---:|---|
| `/Users/a77/知识库/wiki` | device `16777232`, inode `864317` | repo `/Users/a77/知识库`; `6e1185dee2daa9afce78273185e1ef2e7a3d2d24`; branch `briefing/0726-v2` | entities 2,942; concepts 2,296; sources 4,171; raw 10,040 | indexed Wiki paths clean; repo has 2 tracked + 1 untracked entry outside/around the snapshot |
| `/Users/a77/knowledge-base-private/wiki` | device `16777232`, inode `3918171` | repo `/Users/a77/knowledge-base-private`; `883815c9b43658339b6308a6494536d2e71b9ad7`; branch `main` | entities 2,940; concepts 2,296; sources 4,152; raw 10,780 | 2 tracked + 44 untracked entries in the repo; the indexed page set itself matches the structured index |

The device/inode pairs, parent Git repositories, branches, heads, inventories,
and relation-file hashes differ. These are two physical, independently versioned
Wiki roots, not aliases or two views of one directory. Equal hashes for a few
important pages do not change that conclusion.

Selected cross-root hashes:

| Asset | `/Users/a77/知识库/wiki` | `/Users/a77/knowledge-base-private/wiki` |
|---|---|---|
| `scripts/rag_index.py` | `a4bac2700dfc670524cf2d47bc7be2e9490f62ac0abdd13b62e2a76fbfce0240` | same |
| `wiki/entities/瑞华泰.md` | `9c9fb2ec8234758b8ee7f42045acf5272ff9d4cc68c6c1e83ff71ad191a29f4a` | same |
| `wiki/sources/688323_瑞华泰_最新逻辑卡.md` | `c6695d5e778d4918d44e482baa613fff76d2c99b2fe9c74d8d194f99350b63ce` | same |
| `wiki/relations/evidence_index.json` | `4b140719ac8df031a7815aa8821b974f478edef0fa14e7793ef9f2e0d04c3cd9` | `52d9f4356da4e99ef2fbed64fa432b29c367cf3173f46e3cd0f299fba63f875b` |

Both relation files contain 29 occurrences of `瑞华泰`; that is a useful
coverage sanity check, not proof of equivalent snapshots.

## Index identity and freshness

### Structured indexes

| Index | Built | Format / scope | Chunks | Meta SHA-256 | Chunks SHA-256 | Other artifact hashes |
|---|---|---|---:|---|---|---|
| `/Users/a77/知识库/.rag_index` | `2026-07-13T17:30:29` | legacy metadata; `include_raw=true` | 101,042 | `25c06cf72e078f17e1dc3072bf5aa9bdb6a8c841e1104e216809c7b2baf15952` | `31b4f24be449e92d05b2a09ab0a664d0ac9a5a0024f9c686709ef4a8c39f890c` | `dense.npy` `5b7b421cf01991d208f809ff12744b41bb13890a94c0763e4a99136a6bebfe9f`; legacy `bm25.pkl.gz` |
| `/Users/a77/knowledge-base-private/.rag_index` | `2026-07-28T00:53:02` | format 2; chunking/tokenizer v1; `include_raw=false` | 104,611 | `80151a3fcf409e9ab6ba3a787b990a32a8899098919f2d114645da24b7a5e986` | `76034c6e4e8db169dc5b0963ce3992c1c4482d5e50b901a5178e9c3a32bf7f3c` | `dense.npy` `6a012a5c66f18ebdf2da148b911e636aecfdf6291eeab4d583a181c9ef563b10`; `bm25_tokens.jsonl.gz` `64549ce54c11e80eb580ff49e0f6b1e2d60a33cdd9c9bfa6e6363f0df9f8314a`; legacy `bm25.pkl.gz` `ace84f10b0aa53ccc37d12ea39c53021cf928f61770a6a6fc0cc05ee739e079f` |

The private structured index records:

```text
source_revision     manifest:v1:51ddfe839f262d718b3da6635be711b884f8f0d310f3aa16f5807fa07d294a08
source_git_revision 5e4cc9c4d3df58161447cb7f8bf954a275dc5b99
source_dirty        true
source_fingerprint  d43595e997f0282915ac32cd14f01b0bd354084f9bd3dab8dbe14d73130b8151
source_file_count   9753
```

The source Git revision is nine commits ahead of the current private-repo
`HEAD` (`HEAD...5e4cc9c4` = `0 9`), and the indexed source was marked dirty at
build time. This is why the index cannot currently be called a clean Git-pinned
release artifact.

### Content-level check versus formal runtime freshness

The checks expose two different notions of freshness:

| Check | Chinese structured index | Private structured index | Private `.rag_index_full` |
|---|---:|---:|---:|
| chunk/source comparison (`rag_index.py check`) | 36,298 stale chunks (`indexed=101042`, `current=123816`) | **0 stale** (`indexed=104611`, `current=104611`) | 54,928 stale chunks (`indexed=80956`, `current=123716`) |
| manifest freshness (`RagStore.index_freshness`) | unavailable in legacy metadata | **fresh** | unavailable in legacy metadata |
| query CLI freshness (`scripts/rag_freshness.check_index_freshness`) | **stale**: age 14.9d and missing Git revision | **stale**: indexed source changed in Git and index built from dirty source | legacy metadata has no provenance and is older (`2026-06-19`) |

This distinction is the key Phase C finding. The selected private index is
content-consistent with the current Wiki manifest, but `rag_index.py query`
uses the older Git-based freshness helper. `kb_rag.retrieve(...,
require_fresh=True)` then drops every non-`fresh` hit before it can become model
evidence. Therefore a successful content comparison alone does not make the
current runtime replay-ready.

The next slice must make the freshness contract single-source-of-truth (or
explicitly bridge manifest freshness and Git provenance), add regression tests,
and only then replay `evidence_search`. It must not silently weaken the
fail-closed evidence gate.

## Canonical choice rationale

`/Users/a77/knowledge-base-private/wiki` wins as the canonical path because:

1. it is the formal `knowledge-base-private` repository used by the current
   deployment wiring;
2. its structured index is the modern format-2 index with manifest provenance;
3. its current Wiki and index have an exact content-level match;
4. the Chinese-root index is older, legacy metadata, includes raw by default,
   and has 36,298 stale chunks;
5. `.rag_index_full` is a June legacy index with 54,928 stale chunks and no
   provenance fields.

This does **not** mean the private root's dirty working tree is approved for
production. It means all later Phase C questions will use this root once the
freshness seam and a clean snapshot are pinned.

## Exit and non-goals

Part 1 is complete for identity selection. It does not claim:

- capability authorization or a dry-run contract;
- `evidence_search` recall, latency, cutoff, or semantic filtering results;
- a live benchmark result;
- App Server value;
- a 28-case pass rate, Knevo win rate, main merge, or canonical 8792 release.

## Required clean-snapshot gate before replay

Before Phase C Part 2, produce a clean, pinned artifact with all of the
following true:

1. selected root and indexed page-set are explicit;
2. the source Git revision is the exact checked-out revision for the included
   Wiki paths, with `source_dirty=false`;
3. manifest and runtime freshness both report `fresh`;
4. `meta.json`, `chunks.jsonl`, `dense.npy`, and `bm25_tokens.jsonl.gz` hashes
   are recorded;
5. the capability dry-run and subsequent replay reference those exact hashes.

Until then, any evidence result must be labelled exploratory and must not enter
the frozen causal/valuation comparison.

# Phase C Retrieval Contract Verification

Date: 2026-07-29
Status: **Phase C bounded diagnosis complete; not a product-release or
Codex-parity claim**

## Scope and controlled surface

This slice answered one narrow question: can the real finance runtime receive
fresh Wiki evidence from a content-consistent format-2 RAG index, and what
remains after that transport seam is repaired?

All implementation and replay work used isolated copies:

```text
finance candidate:
  /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
  branch feat/agent-runtime-backends-verify
  final tip d92b554a

knowledge-base clone:
  /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness
  branch fix/manifest-freshness-cli
  code 9053b0c4

Wiki:
  /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/wiki
Index:
  /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/.rag_index
Information cutoff:
  2026-07-24
```

The original knowledge-base repository was not a write target. At final audit
it remained `main@883815c9`; its indexed page directories were clean, while
unrelated concurrent raw/disclosure and relations changes existed outside the
controlled clone. No command in this slice wrote those changes.

## 1. Freshness seam: green

The repaired policy makes the content manifest the effective freshness
authority. The Wiki root and the `include_raw`/`max_files` scope are supplied
to the same manifest calculation used by `RagStore.index_freshness`.

- format-2 manifest match and valid age → `fresh`;
- manifest mismatch or expired age → `stale`;
- legacy/missing manifest → `unknown`;
- Git revision and historical `source_dirty` remain diagnostics and no longer
  override a matching content manifest;
- CLI and finance runtime use the same index-level result;
- `require_fresh=True` still rejects `stale` and `unknown`; production did not
  get changed to `RAG_STALE_POLICY=ignore`.

The clean snapshot receipt is
[`phase-c-clean-rag-snapshot-2026-07-29.md`](phase-c-clean-rag-snapshot-2026-07-29.md).
It records `104611` indexed chunks, `source_dirty=false`, exact artifact
hashes, and `reused_existing_embeddings=true`. This is a provenance rebind of
an exact content match, not a silently substituted or newly claimed embedding
build.

Observed gates against that exact root/index:

| Gate | Observed result |
|---|---|
| `rag_index.py check` | `indexed=104611 current=104611 stale=0` |
| `RagStore.index_freshness(wiki)` | `fresh` |
| direct CLI query for `瑞华泰` | exit `0`, 3 hits, all `fresh` |
| finance `kb_rag.retrieve(require_fresh=True)` | `ok=true`, 3 hits, `index_freshness=fresh`, empty warning |

This is the important distinction: the runtime evidence gate now receives
`fresh`; the result is not inferred from a CLI label alone.

## 2. Capability authorization: green for the bounded experiment

The dry-run receipt is
[`phase-c-capability-dry-run-2026-07-29.json`](phase-c-capability-dry-run-2026-07-29.json),
created from clean source revision `b60a759e` with `sdk_gpt` and five frozen
cases. It is a plan-only artifact: no provider call, tool call, live benchmark,
or canonical runtime switch occurred.

The receipt has `case_count=5`, `contract_null=0`, and
`acceptance_contract_gaps=[]`. The contracts explicitly allow
`evidence_search` for both `ruihuatai-valuation` and `weekly-market-cause`.
This replaces the historical `e179b15c` artifact's `contract=null`; historical
absence cannot retroactively authorize a capability.

## 3. Bounded evidence-search replay

The deterministic BM25 replay is pinned in
[`phase-c-evidence-search-replay-2026-07-29.json`](phase-c-evidence-search-replay-2026-07-29.json).
The production-mode request (`requested_retrieval_mode=hybrid`) is pinned in
[`phase-c-evidence-search-replay-hybrid-2026-07-29.json`](phase-c-evidence-search-replay-hybrid-2026-07-29.json).

Both cases used the same closed-loop aperture sequence (`narrow`, `broad`,
`counter`), `require_fresh=true`, and the 2026-07-24 cutoff. Both traces report
`evidence_search` status `success`; every returned evidence atom is `fresh`.
A successful trace here means retrieval transport succeeded, not that the
final answer would pass a semantic judge.

### 瑞华泰估值

- Entity anchor resolved by name to `瑞华泰 / 688323.SH`, concept `PI薄膜`.
- All three apertures completed; 12 evidence atoms were returned.
- The index has useful recall: annual-report baseline, entity page, latest
  logic card, and PI-film concept material were retrieved.
- Near-word and related-company contamination also appeared (`瑞华技术`,
  `天奈科技`, `方邦股份`, and related pages).

Classification: **index recall is present; remaining problem is semantic result
quality/anchor filtering, not an empty Wiki or a freshness rejection**.

### 周度行情因果

- No stable entity or market-week anchor was established.
- The narrow generic query returned an approximate first set containing
  `牧原股份`/猪周期 material.
- The closed loop copied those terms into broad and counter queries, producing
  牧原、温氏、天康 and old猪周期 logic cards.
- The served evidence date was `2026-07-01`, not a direct 2026-07-24 week-level
  causal source.

Classification: **query drift plus topic/corpus coverage mismatch**. This is
not an empty index and not evidence that `evidence_search` was unauthorized.
The repair is to require an explicit causal anchor (or honestly return
unavailability) before expansion; it is not unrestricted Wiki grep or a
freshness relabelling.

## 4. Requested Hybrid versus effective retrieval

The replay requested `hybrid`, but this machine lacks the `FlagEmbedding` dense
dependency. The actual path therefore fell back to BM25. An independent
telemetry probe recorded: `requested_mode=hybrid`, `effective_mode=bm25`,
`fallback_reason=dense_dependency_missing`, `degraded=true`.

Later calls used `dense_dependency_cached_unavailable`; the final
`EvidenceSearchResult` did not carry the cached `effective_mode/degraded`
telemetry even though a separate probe confirmed it. This is a real P1
observability gap. Until dense dependencies are supplied and propagation is
fixed, do not call this a true Hybrid quality result.

The semantic judge was deliberately disabled
(`disabled_deterministic_replay`) to keep this slice reproducible. The replay
does not prove final answer quality, semantic filtering quality, or live model
behavior.

## 5. Verification gates

```text
finance runtime focused tests: 77 passed
KB freshness/retrieval/release/evaluation focused tests: 49 passed
KB Ruff: passed
git diff --check: passed (candidate and KB clone)
```

With `FINANCE_WS=/Users/a77/finance-workspace-private` explicitly set to avoid
multiple-repository auto-discovery, the KB full suite produced:

```text
395 passed, 1 failed
```

The single failure is the pre-existing
`tests/test_file_transaction.py::FileTransactionTest::test_commit_failure_rolls_back_all_targets` baseline failure. Without the environment variable,
collection fails because the clone sees multiple candidate finance worktrees;
that is test-environment discovery, not a freshness regression.

## 6. Boundaries preserved

- No 28-case benchmark was run.
- No App Server code or adapter was implemented.
- No `main` merge, 8792 switch/restart, or 8799 promotion occurred.
- No key, database, PDF, archive, or generated index binary was committed.
- The canonical finance worktree's unrelated dirty files were preserved.
- The original knowledge-base repository was not used as a write target; the
  controlled KB clone is the only implementation surface.

## Verdict

**Phase C freshness and retrieval diagnosis is complete.** The main transport
failure was real and is repaired: the runtime now obtains fresh evidence under
the real `require_fresh=True` gate. Remaining quality gaps are narrowed to
causal query anchoring/drift, semantic contamination, dense-dependency
availability, and fallback telemetry propagation. These are separate from App
Server value and from any 28-case or Knevo score.

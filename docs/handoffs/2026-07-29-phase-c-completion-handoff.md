# Phase C Completion Handoff — Freshness and Retrieval Diagnosis

Date: 2026-07-29
Status: **Phase C bounded scope complete; ready for the next implementation
slice, not ready for production promotion**

## One-sentence handoff

The real runtime freshness gate is now proven green in an isolated
`knowledge-base-private` clone, and the two requested `evidence_search`
replays have separated the remaining problems into causal query drift,
semantic near-word contamination, missing dense Hybrid dependency, and
fallback telemetry loss. Do not restart the nine questions or jump to App
Server; fix these seams first.

## Original objective

Complete Phase C without changing the user's live surfaces:

1. repair the manifest/Git freshness seam in a detached KB copy;
2. prove `require_fresh=True` receives `fresh` through the real finance path;
3. pin a clean snapshot receipt and current capability dry-run;
4. replay valuation and weekly-causal retrieval through bounded
   `evidence_search` apertures;
5. classify the remaining gaps and leave an executable next-step record.

The following remained explicitly out of scope: original KB writes, `main`,
8792/8799 switching, all 28 benchmark cases, App Server implementation, and
Knevo scoring.

## Completed assets and provenance

### Finance candidate

```text
worktree  /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
branch    feat/agent-runtime-backends-verify
```

Relevant commits:

- `f0249d0e` — Phase C freshness seam design;
- `b60a759e` — clean RAG snapshot receipt;
- `f2b7a570` — capability dry-run receipt;
- `80c045ee` — deterministic BM25 replay;
- `d92b554a` — production-mode replay requested as Hybrid;
- `f1d1f9ee` — this completion handoff;
- plus the post-review correction commit that carries the dense-dependency and
  test-ledger fixes described below.

The branch tip advances with each docs commit; read it from `git log` rather than
from a pinned value in this file.

The final verification is
[`phase-c-retrieval-contract-2026-07-29.md`](../verification/phase-c-retrieval-contract-2026-07-29.md).

### Isolated knowledge-base implementation

```text
worktree  /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness
branch    fix/manifest-freshness-cli
code      9053b0c4137428e9ad9d8b4be3ba475b7377b435
source    main@883815c9
```

The code change is deliberately in the KB repository, not copied into the
finance runtime tree. Any production adoption needs a separate cross-repo
review/merge decision. The original `/Users/a77/knowledge-base-private` was
not a write target; current raw/relations changes there are concurrent and
must not be folded into this experiment.

## What is now proven

### Freshness is no longer the blocker

Manifest content identity, not a stale historical Git/build label, determines
effective freshness for a format-2 index. `vault_root` and the index scope
(`include_raw`/`max_files`) are part of the calculation. Git revision and
`source_dirty` remain visible diagnostics.

The exact clean snapshot records:

```text
104611 chunks
format_version=2
source_dirty=false
source_git_revision=883815c9
RagStore.index_freshness= fresh
CLI 瑞华泰= 3 fresh hits
finance require_fresh=True= 3 fresh hits
```

This is a transport/gate proof, not a claim that every returned page is
semantically appropriate.

### Capability authorization is current and explicit

The five-case dry-run has non-null contracts and zero acceptance gaps. Both
`ruihuatai-valuation` and `weekly-market-cause` explicitly allow
`evidence_search`. The old `e179b15c` contract-null artifact is not used as
authorization evidence.

### Retrieval recall is present

瑞华泰 produces 12 fresh atoms across narrow/broad/counter apertures and
retrieves the expected annual-report baseline, entity page, logic card, and
PI-film concept. Therefore “the Wiki is empty” and “freshness rejected every
hit” are falsified for this controlled snapshot.

## Remaining gaps (ordered by engineering leverage)

### P0 — causal closed-loop anchor/drift

The weekly causal case has no reliable anchor. Its first approximate hits seed
company/topic terms into later queries, so the loop reinforces a wrong topic.
The next implementation must either:

- require a market-week/cutoff anchor before broad/counter expansion; or
- stop and return an honest evidence-unavailable result when no anchor exists.

It must not promote the first approximate BM25 hit to a causal premise.

Acceptance should assert that broad/counter queries cannot introduce a new
company/topic entity unless it is supported by an explicit anchor or a
high-confidence deterministic relation.

### P1 — cached fallback telemetry propagation

When Hybrid is requested without dense dependencies, the first call exposes
`dense_dependency_missing`, but later cached fallback calls only expose
`dense_dependency_cached_unavailable` in lower-level telemetry. The final
`EvidenceSearchResult` drops `effective_mode`/`degraded` on those later calls.

Add a typed result field (or equivalent immutable telemetry) and regression
tests so every EvidenceSearch result states requested mode, effective mode,
fallback reason, and degraded status. This prevents a BM25 fallback from being
mistaken for true Hybrid.

### P1 — valuation anchor/semantic filtering

瑞华泰 retrieval has useful recall but also near-word/related-company pages
such as 瑞华技术, 天奈科技, and 方邦股份. Add anchor-aware filtering and a
semantic relevance check that preserves counter-evidence without admitting
same-prefix entities as if they were the target company.

Do not solve this with an unrestricted Wiki grep tool. The evidence ledger,
content hashes, and cutoff fields must remain intact.

### P1 — point the KB clone at the existing dense venv, then rerun quality replay

**Corrected.** The earlier claim that this machine lacks `FlagEmbedding` is
falsified. `/Users/a77/knowledge-base-private/.rag_venv` (Python 3.12.13) imports
`FlagEmbedding`, `rank_bm25`, `yaml`, and `numpy`, and the bge-m3 weights are
already cached locally (4.3G). The `hybrid` request degraded to BM25 because
`kb_rag._resolve_rag_python` (`kb_rag.py:371-380`) falls back to `sys.executable`
when the KB root has no `.rag_venv`/`.venv` — and those are gitignored
(`.gitignore:31-32`), so a clone never has them.

So this is a one-line environment wiring fix, not an install task: set
`KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python3` (or add the
venv inside the clone). True Hybrid has already been reproduced against the pinned
snapshot this way: dense weights loaded, 5 hits, all `fresh`, RRF band
`0.1956 → 0.1779`.

Because this step is now cheap, it should run **before** the semantic-filtering work
— it supplies the correct baseline that P1 filtering must be measured against.
One finding already carries over: `wiki/entities/天奈科技.md` still ranks in true
Hybrid, so the contamination gap is real and not a BM25 artifact.

Caveat: that `.rag_venv` is a symlink into `/Users/a77/知识库`, the legacy repo
barred as a *data* source. Code and index stay isolated in the clone; only the
interpreter comes from there. Prefer an explicit `KB_RAG_PYTHON` over the symlink,
and do not let this reintroduce the Chinese root as a retrieval source.

### P2 — semantic judge replay

The current artifacts intentionally use
`disabled_deterministic_replay`. Once a semantic judge is available, run a
separate comparison on the same frozen inputs. Keep retrieval transport,
semantic acceptance, and user-perceived answer quality as separate metrics.

## Verification ledger

```text
finance focused: 77 passed
KB focused: 49 passed
KB full with explicit FINANCE_WS: 395 passed, 1 pre-existing failure
Ruff: passed
git diff --check: passed
```

These counts do not record the interpreter, so they are not reproducible as written.
Neither obvious candidate on this machine can run the KB suite as-is: `.rag_venv`
has the dense/BM25 stack but no `pytest`; `/usr/bin/python3` has `pytest` but no
`rank_bm25`. Under `/usr/bin/python3`, `tests/test_rag_index_freshness.py` gives
`1 failed, 6 passed`, the failure being `ModuleNotFoundError: rank_bm25` in a
subprocess — an environment gap, not a defect in `9053b0c4`. Record the exact
interpreter path with any future pass count.

The full-suite failure is
`tests/test_file_transaction.py::FileTransactionTest::test_commit_failure_rolls_back_all_targets`, reproduced as a baseline failure and
unrelated to this freshness slice. Without `FINANCE_WS`, collection fails on
multiple candidate worktree discovery; keep the explicit environment setting
in future KB test commands.

## Next execution order

0. **Pin the dense interpreter and capture a true Hybrid baseline.** Set
   `KB_RAG_PYTHON` to the existing dense venv and replay both cases against the
   same receipt hashes and cutoff. This is now an environment variable, not an
   install, so it comes first and gives every later step a correct baseline.
1. **Thread fallback telemetry** through `EvidenceSearchResult`; add tests for
   first-call and cached-call degradation. Do this early: without it you cannot
   tell a true Hybrid run from a silent BM25 fallback, which would invalidate
   the comparisons in steps 2-3.
2. **Implement the causal anchor guard** in a fresh KB/runtime worktree with
   tests first; replay only `weekly-market-cause` bounded apertures.
3. **Fix valuation anchor filtering** and replay the same 瑞华泰 case, measured
   against the step-0 Hybrid baseline rather than the BM25 artifact.
4. **Enable semantic judge replay**, then decide whether a larger benchmark,
   App Server ceiling experiment, or Knevo blind comparison is justified.

Do not run the 28-case suite, build App Server, change freshness gates, or
promote 8792/8799 before steps 0–3 have clean, comparable evidence.

## Boundaries and release status

This handoff does not authorize a merge, deployment, key rotation, App Server
implementation, or benchmark expansion. It is the completion receipt for the
bounded Phase C diagnosis. The next agent should start from this file and the
exact SHA-pinned artifacts, not from a new interpretation of the earlier nine
questions.

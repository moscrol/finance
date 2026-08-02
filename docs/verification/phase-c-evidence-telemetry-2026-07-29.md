# Phase C Evidence Search Telemetry Verification

Date: 2026-07-29
Status: **true-Hybrid baseline and per-attempt retrieval telemetry verified**

## Scope

This slice executed steps 0–1 from the reviewed Phase C correction handoff:

1. run both bounded cases through true Hybrid retrieval;
2. preserve requested/effective mode, fallback reason, and degraded state for
   every narrow/broad/counter attempt in `EvidenceSearchResult`;
3. expose the same facts in the provider trace;
4. prove first-call and cached dense fallback paths with tests.

It did not implement the causal anchor guard or valuation filtering.

## Review correction audit

The review's main correction is valid. The machine has the dense stack and
cached BGE-m3 weights; the earlier BM25 fallback came from interpreter
selection in an isolated clone without a gitignored venv.

One provenance sentence needed correction: the review's CLI probes appended
two generated access-log lines in the isolated clone. Those lines and all later
replay-generated lines were removed with targeted patches. The clone is clean;
code and index artifacts were not changed by the probes.

## Reproducible dense environment

- Finance Python:
  `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`.
- `KB_RAG_PYTHON`:
  `/Users/a77/knowledge-base-private/.rag_venv/bin/python3`, Python 3.12.13.
- Dense venv realpath: `/Users/a77/知识库/.rag_venv/bin/python3`.
- `RAG_BGE_MODEL`:
  `/Users/a77/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181`.
- `RAG_WORKER_ENABLED=1`; `HF_HUB_OFFLINE=1`.

The explicit local model snapshot is required for reproducibility. Using only
the model name caused Hugging Face resolution to touch local HTTP client
configuration and fail on an invalid proxy port before cache resolution. That
is separate from whether `FlagEmbedding` is installed.

The venv realpath lives under the legacy Chinese-root repository. It supplies
only Python/packages; Wiki and index remain the isolated private-root clone.
No retrieval reads `/Users/a77/知识库/wiki`.

## Snapshot identity

| Artifact | SHA-256 |
|---|---|
| `meta.json` | `3ab0d301c7480a8ee12ebb2540a0d03421b722ea193ca0ac1a754289129ac79b` |
| `chunks.jsonl` | `76034c6e4e8db169dc5b0963ce3992c1c4482d5e50b901a5178e9c3a32bf7f3c` |
| `dense.npy` | `6a012a5c66f18ebdf2da148b911e636aecfdf6291eeab4d583a181c9ef563b10` |
| `bm25_tokens.jsonl.gz` | `64549ce54c11e80eb580ff49e0f6b1e2d60a33cdd9c9bfa6e6363f0df9f8314a` |

Pre-change artifact:
[`phase-c-true-hybrid-baseline-2026-07-29.json`](phase-c-true-hybrid-baseline-2026-07-29.json).

The direct probe loaded all 391 weight shards and returned five fresh results
with RRF scores `0.195625 → 0.177903`. `天奈科技` remained fifth.

## Implementation

`RetrievalAttempt` now owns four compatible-default fields:

- `requested_mode`;
- `effective_mode`;
- `fallback_reason`;
- `degraded`.

`closed_loop_retrieval._run_aperture` copies them from the exact
`WikiRagResult.telemetry` that produced each attempt. This preserves the first
`dense_dependency_missing` event and later
`dense_dependency_cached_unavailable` events separately. Budget-exhausted
attempts keep empty/default values because no retrieval executed.

`ClosedLoopRetrievalResult.inspector_dict()` serializes the same fields.
`EvidenceSearch` deduplicates ordered mode signatures into trace detail:

- true Hybrid: `retrieval_modes=hybrid->hybrid`;
- fallback: `hybrid->bm25:dense_dependency_missing:degraded` followed by
  `hybrid->bm25:dense_dependency_cached_unavailable:degraded`.

Provider success/empty status remains about evidence delivery; degradation is
a separate observable and is no longer hidden behind `success`.

## Post-change true-Hybrid replay

The worker loaded the model once (`model_load_count=1`, prewarm 26.035s).

| Case | Attempts | Mode result | Evidence | Latency |
|---|---:|---|---:|---:|
| `ruihuatai-valuation` | 3 | all `hybrid -> hybrid`, no fallback, not degraded | 12 fresh | 11.698s |
| `weekly-market-cause` | 3 | all `hybrid -> hybrid`, no fallback, not degraded | 10 fresh | 13.785s |

Both traces end with `retrieval_modes=hybrid->hybrid`. The comparison is not a
silent BM25 fallback.

## Quality findings after true Hybrid

- 瑞华泰 still returns `天奈科技` and `方邦股份`; entity/semantic contamination
  is real under Hybrid.
- The weekly query drifts from an unanchored generic question into
  semiconductor/optical-fiber terms and older sell-side pages. The topic
  differs from the BM25 pig-cycle branch, but neither establishes a
  2026-07-24 market-week causal anchor.

Ranking mode changes which wrong branch wins; the missing anchor permits the
drift. This is the next P0 seam.

## Tests

Focused tests used the exact finance interpreter above and produced
`90 passed`. They cover `test_kb_rag`, `test_closed_loop_retrieval`,
`test_evidence_search`, `test_episode_tools`, and
`test_run_agent_runtime_benchmark`.

New cases prove first dense failure, next-call cached fallback, per-attempt
propagation, inspector serialization, true-Hybrid projection, and provider
trace aggregation. Ruff and `git diff --check` pass.

The full `intelligence/tests` run used the same interpreter plus
`FORESIGHT_USERS_DIR=/tmp/foresight-users-phase-c` so collection could write a
sandbox-safe SQLite path. It produced `2946 passed, 24 failed, 2 skipped`:

- 14 failures are loopback HTTP tests denied by this sandbox's socket-bind
  policy (`PermissionError: Operation not permitted`);
- 10 are userspace/subconscious tests whose expected default paths are changed
  by the required `FORESIGHT_USERS_DIR` override.

None of the 24 failures touches `kb_rag`, closed-loop retrieval, EvidenceSearch,
episode tools, or the benchmark contract. The 90-test changed surface is green.

## Boundaries and verdict

- KB candidate remains isolated at `fix/manifest-freshness-cli@9053b0c4`.
- No original KB merge/write or index rebuild occurred.
- The isolated KB clone is clean after probe-log removal.
- No model download, 28-case run, App Server work, verifier relaxation,
  `main` merge, or 8792/8799 change occurred.

The telemetry objective is complete. Every attempt now proves which retrieval
mode actually ran and why it degraded, while true Hybrid confirms that causal
drift and valuation contamination are independent of the earlier BM25 fallback.

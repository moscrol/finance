# Phase C Causal Anchor Guard Verification

Date: 2026-07-29
Status: **causal drift and false-success seam closed**

## Scope

This slice fixes the fixed regression:

```text
这一周行情下跌的主要原因是什么
information cutoff: 2026-07-24
target source window: 2026-07-20..2026-07-24
```

It does not claim that the current Wiki contains enough same-week evidence to
answer the question. It makes that absence honest: old or undated retrievals do
not enter the model observation, and a result without target-window support and
counter-evidence cannot report `success`.

## Behavioral change

Four independently reviewable commits implement the guard:

- `44a36566` — adds `RetrievalAttempt.executed`; a skipped budget attempt is no
  longer indistinguishable from a healthy Hybrid attempt.
- `c74d61ce` — adds `query_only` expansion. An unanchored causal query uses the
  raw question, stable market-mechanism suffixes, and stable counter suffixes;
  approximate first-hit entities or concepts are not promoted.
- `12726e9a` — adds the source-window/counter policy, compact `YYYYMMDD` source
  dates, policy coverage, and `partial` provider status.
- `68974ca6` — applies that policy only when the Episode evidence profile is
  `time_aligned_market_causal`.

Default valuation, theme, and company EvidenceSearch callers keep the existing
`anchor_or_hits` expansion behavior.

## Delivery contract

For a causal source window:

| Eligible model evidence | Counter evidence | Provider status |
|---|---:|---|
| none | none | `empty` (or existing `future_of_cutoff` when applicable) |
| target-window support | none | `partial` |
| target-window support | target-window counter | `success` |

Off-window and unknown-date hits remain visible in retrieval attempts and
coverage diagnostics but are filtered before the model observation.

## True-Hybrid replay

Reproduction environment:

```text
finance Python: /Users/a77/finance-workspace-private/.venv-workbench/bin/python
KB_RAG_PYTHON: /Users/a77/knowledge-base-private/.rag_venv/bin/python3
KB Python version: 3.12.13
RAG_BGE_MODEL: /Users/a77/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181
RAG_INDEX_DIR: /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/.rag_index
HF_HUB_OFFLINE=1
RAG_WORKER_ENABLED=1
semantic judge: disabled for deterministic seam replay
```

The worker prewarmed in 35.292 seconds and recorded
`model_load_count=1`. The three-aperture search took 15.674 seconds.

Exact attempts:

```text
narrow  : 这一周行情下跌的主要原因是什么
broad   : 这一周行情下跌的主要原因是什么 市场内部机制 资金 风险偏好
counter : 这一周行情下跌的主要原因是什么 反证 替代解释
```

All three attempts were executed and reported:

```text
requested_mode=hybrid
effective_mode=hybrid
fallback_reason=""
degraded=false
```

Neither later query contains the known BM25 drift branch (`牧原股份` / `猪周期`)
nor the known true-Hybrid drift branch (`半导体` / `光纤光缆`).

The retriever still found old approximate material. The audited result was:

```text
status=empty
conclusion=8
counter=2
discarded=6
target_window=0
target_window_counter=0
window_rejected=9
served_date=2026-06-29
evidence_count=0
gap=尚未找到 2026-07-20 至 2026-07-24 目标窗口内的可用证据
retrieval_modes=hybrid->hybrid
```

This is the intended fail-closed result. Retrieval availability and evidence
eligibility are separate: the system executed true Hybrid successfully, but it
did not pretend that old evidence answered the requested week.

## Regression gates

The following command used the finance Python above:

```text
pytest test_kb_rag.py test_closed_loop_retrieval.py test_evidence_search.py
       test_episode_tools.py test_episode_semantic_verifier.py
       test_run_agent_runtime_benchmark.py
```

Result: `240 passed in 2.02s`.

Ruff passed on all changed service and test files. `git diff --check` passed.

## Snapshot and isolation

The replay used the already approved isolated index identity:

| File | SHA-256 |
|---|---|
| `meta.json` | `3ab0d301c7480a8ee12ebb2540a0d03421b722ea193ca0ac1a754289129ac79b` |
| `chunks.jsonl` | `76034c6e4e8db169dc5b0963ce3992c1c4482d5e50b901a5178e9c3a32bf7f3c` |
| `dense.npy` | `6a012a5c66f18ebdf2da148b911e636aecfdf6291eeab4d583a181c9ef563b10` |
| `bm25_tokens.jsonl.gz` | `64549ce54c11e80eb580ff49e0f6b1e2d60a33cdd9c9bfa6e6363f0df9f8314a` |

Four replay-generated `access_log.jsonl` lines were removed with a targeted
patch. The KB candidate is clean at `9053b0c4`. The original KB remains
`main@883815c9`; the five indexed page directories have zero dirty paths.

No index was rebuilt, no model was downloaded, no API key was used, no 28-case
suite ran, no App Server code changed, and no runtime port or `main` branch was
promoted.

## Remaining frontier

The causal seam is complete, but the same true-Hybrid baseline still returns
`wiki/entities/天奈科技.md` and `wiki/entities/方邦股份.md` for 瑞华泰 valuation.
That is the next deterministic filtering target. Semantic-judge replay follows
only after the deterministic valuation seam is bounded.

# Evidence Search Telemetry Handoff

Date: 2026-07-29
Status: **Step 0 and telemetry slice complete; causal anchor guard is next**

## Outcome

True Hybrid is reproducible and mechanically distinguishable from BM25
fallback. Every narrow/broad/counter attempt in `EvidenceSearchResult` carries
requested mode, effective mode, fallback reason, and degraded state; provider
trace detail exposes the same ordered mode signatures.

The quality diagnosis remains:

- valuation still contains `天奈科技`/`方邦股份` contamination;
- weekly causal retrieval still pivots into a topic inferred from the first
  approximate hit instead of establishing a market-week anchor.

## Working copies and commits

Finance candidate:

```text
/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
branch feat/agent-runtime-backends-verify
```

KB candidate:

```text
/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness
branch fix/manifest-freshness-cli
code 9053b0c4
```

Read the current finance tip from `git log`; do not pin a self-referential docs
commit as a static branch tip.

Relevant commits before the final docs commit:

- `af2c3671` — telemetry design and review provenance correction;
- `fe8051db` — executable implementation plan;
- `2a467da3` — true-Hybrid pre-change baseline;
- `d08613b1` — per-attempt retrieval mode ledger;
- `8db45d7f` — EvidenceSearch trace degradation projection;
- `bc75dbfb` — actual cached fallback regression test.

Verification:
[`phase-c-evidence-telemetry-2026-07-29.md`](../verification/phase-c-evidence-telemetry-2026-07-29.md).

Baseline:
[`phase-c-true-hybrid-baseline-2026-07-29.json`](../verification/phase-c-true-hybrid-baseline-2026-07-29.json).

Verification ledger:

```text
focused changed surface: 90 passed
full intelligence suite: 2946 passed, 24 environment/sandbox failures, 2 skipped
Ruff: passed
git diff --check: passed
```

The 24 full-suite failures split into 14 sandbox-denied loopback socket binds
and 10 userspace/subconscious expectations altered by the sandbox-safe
`FORESIGHT_USERS_DIR` override. None covers the changed retrieval surface.

## Reproduction contract

Set all of these explicitly:

```text
KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python3
RAG_BGE_MODEL=/Users/a77/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181
RAG_INDEX_DIR=/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/.rag_index
HF_HUB_OFFLINE=1
```

For multi-aperture replay, set `RAG_WORKER_ENABLED=1` so the 4.3G model loads
once. Record both the finance test interpreter and KB retrieval interpreter.
After every replay, remove only generated access-log lines and require the KB
clone to be clean.

## Contract now guaranteed

For each executed `RetrievalAttempt`:

- `requested_mode` says what the caller requested;
- `effective_mode` says what actually ran;
- `fallback_reason` explains a mode change;
- `degraded` states whether capability fell below the request.

The ordered attempts distinguish a first dependency failure from cached
degradation. A result can no longer report only `success` while hiding that
Hybrid silently became BM25.

## Next target: causal anchor guard

Create a separate design/plan slice. Do not mix it into telemetry code.

Required behavior:

1. Classify whether the query has an explicit entity, concept, index/market, or
   time-window causal anchor.
2. For generic weekly-market causal questions with no anchor, do not copy
   arbitrary company/topic terms from the first approximate hit into
   broad/counter queries.
3. Allow a new company/topic later only when it comes from an explicit anchor
   or high-confidence deterministic relation.
4. If no safe anchor exists, keep original market/time terms or return an
   honest evidence-unavailable result.
5. Preserve cutoff filtering, fresh-only evidence, counter search, content
   hashes, and per-attempt telemetry.

Primary regression:

```text
这一周行情下跌的主要原因是什么
cutoff=2026-07-24
```

It must reject both known drift branches:

- BM25: 牧原/猪周期;
- true Hybrid: 半导体/光纤光缆 inferred from an approximate old report.

After the causal guard passes, create the valuation-filtering slice using
`天奈科技` as a fixed Hybrid contamination case. Semantic judge replay follows
both deterministic seams.

## Guardrails

- Cross-repo merge of `9053b0c4` remains unauthorized.
- Do not use `/Users/a77/知识库/wiki` as data; its venv is interpreter
  infrastructure only.
- Do not rebuild the large index in place.
- Do not run 28 cases, build App Server, relax gates, or promote 8792/8799
  before causal and valuation seams have bounded evidence.
- Do not commit access logs, weights, venvs, indexes, secrets, databases, or
  unrelated dirty-worktree files.

Original KB remains `main@883815c9` with 0 dirty indexed page directories. The
isolated KB clone is clean. Canonical finance-workspace changes were preserved.

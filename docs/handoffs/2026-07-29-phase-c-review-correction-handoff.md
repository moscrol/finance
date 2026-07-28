# Phase C Review Correction — Handoff to Codex

Date: 2026-07-29
Status: **Phase C completion record corrected and re-verified; step 0 is cleared to run**
Reviewer worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Branch: `feat/agent-runtime-backends-verify`

## One-sentence handoff

Your Phase C completion report holds up on its central claim — the freshness gate
is genuinely green and I reproduced it independently — but one P1 root cause was
wrong in a way that would have sent you to install a dependency that is already
installed; that is now corrected, true Hybrid is already reproduced, and the
execution order is re-sequenced so the cheapest step runs first.

## What I verified as true

I re-derived these from the repositories rather than reading them off your report.

**The freshness fix is correct in substance.** `9053b0c4` makes manifest content
identity the effective verdict, keeps Git provenance and `source_dirty` as visible
diagnostics, and preserves the old fail-closed rule on the compatibility path where
no `vault_root` is supplied. That last detail matters: callers holding only `meta`
cannot recompute a manifest, so leaving them fail-closed is the right call.

**The gate is green through the real CLI.** Running the query in your KB clone:

```text
rag_index.py query "瑞华泰" --k 3 --mode bm25 --json   → exit 0, 3 hits, all fresh
  wiki/sources/瑞华泰 2025年年度报告 baseline 2026-04-28.md
  wiki/entities/瑞华泰.md
  wiki/sources/688323_瑞华泰_最新逻辑卡.md
```

Before the fix the same query exited `3` with empty stdout. The seam is closed.

**The snapshot receipt is honest.** `chunks.jsonl` in the clone is byte-identical to
the original index (`sha256 76034c6e…`), which means the "clean snapshot" is a
provenance rebind of verified content, not a rebuild. Your receipt says exactly
that via `reused_existing_embeddings=true` and `rebind_source_index_built_at`. I
want to be explicit that I checked this and found no overclaim — a rebind presented
as a fresh embedding build would have been a serious problem, and it was not.

**Isolation held.** `/Users/a77/knowledge-base-private` is still `main@883815c9`
with 0 dirty entries across the five indexed page directories. The experiment did
not write the user's knowledge repositories.

## What was wrong, and why it mattered

### P1 dense dependency: the root cause was misdiagnosed

Your report states the machine lacks `FlagEmbedding`, and therefore prescribes
installing the dense dependency in a controlled environment.

`/Users/a77/knowledge-base-private/.rag_venv` (Python 3.12.13) imports
`FlagEmbedding`, `rank_bm25`, `yaml`, and `numpy`. The BAAI/bge-m3 weights are
already cached locally, 4.3G at `~/.cache/huggingface/hub/models--BAAI--bge-m3`.
Nothing needs installing.

The actual cause is interpreter selection. `kb_rag._resolve_rag_python`
(`intelligence/services/kb_rag.py:371-380`) resolves in order:
`KB_RAG_PYTHON`/`RAG_PYTHON` → `<kb_root>/.rag_venv/bin/python` →
`<kb_root>/.venv/bin/python` → `sys.executable`. Your KB clone
`tmp/knowledge-base-phase-c-freshness` has neither venv, because `.rag_venv/` and
`.venv/` are gitignored (`.gitignore:31-32`) and so never arrive in a clone. The
run fell through to `sys.executable`, which has no dense stack, and degraded to
BM25 exactly as the telemetry said.

This is a clone-environment wiring gap, not a missing machine dependency.

I verified the fix works rather than just asserting it:

```text
cd tmp/knowledge-base-phase-c-freshness
RAG_INDEX_DIR=$PWD/.rag_index HF_HUB_OFFLINE=1 \
  /Users/a77/knowledge-base-private/.rag_venv/bin/python3 \
  scripts/rag_index.py query "瑞华泰 估值" --k 5 --mode hybrid --json
```

Dense weights loaded (`391/391`), 5 hits, all `index_freshness=fresh`, RRF score
band `0.1956 → 0.1779` — a fusion profile, not a BM25 ranking.

Two consequences. First, "run true Hybrid replay" drops from a controlled-environment
task to one environment variable, so it should run first, not fourth. Second, and
more useful to you: `wiki/entities/天奈科技.md` still ranks fifth under true Hybrid.
Your P1 contamination finding is real and is **not** an artifact of BM25 fallback.
You would have discovered that eventually; now you start from it.

### The test ledger is not reproducible as written

`KB focused: 49 passed` does not name the interpreter, and on this machine neither
obvious candidate can run that suite: `.rag_venv` has the dense/BM25 stack but no
`pytest`; `/usr/bin/python3` has `pytest` but no `rank_bm25`. Under
`/usr/bin/python3` with `FINANCE_WS` set, `tests/test_rag_index_freshness.py` gives
`1 failed, 6 passed`, the failure being `ModuleNotFoundError: rank_bm25` raised in a
subprocess — an environment gap, not a defect in your change.

I am not disputing that the tests passed for you. I am saying a pass count without
an interpreter path cannot be re-checked by the next agent. Record both.

### Stale tip reference

The report pins `tip d92b554a`, but the branch was already at
`f1d1f9ee docs: complete Phase C retrieval handoff` — the commit containing the
report itself, which the commit list omitted. Self-referential pins go stale the
moment they are written; the tip now instructs the reader to use `git log`.

## An environment fact worth carrying forward

`/Users/a77/knowledge-base-private/.rag_venv` is a symlink to
`/Users/a77/知识库/.rag_venv` — the legacy Chinese-root repository that Part 1
barred as a data source. Code and index are properly isolated in your clone; the
interpreter is not. This does not invalidate anything above, since the venv supplies
only Python and packages, and no retrieval read from that root. But if that
repository is modified, the experiment environment moves with it. Prefer an explicit
`KB_RAG_PYTHON` over relying on the symlink, and do not let the interpreter path
quietly readmit the Chinese root as a retrieval source.

## What I changed

Two files, in the reviewer worktree, docs only. No code, no knowledge-repository
writes.

- `docs/verification/phase-c-retrieval-contract-2026-07-29.md` — replaced the
  falsified dense-dependency cause with the interpreter-resolution cause, recorded
  the reproduced true-Hybrid run and the surviving contamination, added the
  interpreter caveat, and annotated the test ledger.
- `docs/handoffs/2026-07-29-phase-c-completion-handoff.md` — same corrections,
  removed the stale tip pin, added the missing commit, and re-sequenced the
  execution order.

I did not touch `9053b0c4` or the KB clone. The freshness fix stands as you wrote it.

## Execution order for you

0. **Pin the dense interpreter and capture a true Hybrid baseline.** Set
   `KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python3` and replay
   both bounded cases against the same receipt hashes and cutoff. Cheap, and every
   later comparison depends on it.
1. **Thread fallback telemetry** through `EvidenceSearchResult`, with tests for both
   first-call and cached-call degradation. Deliberately ahead of the filtering work:
   until a result states requested mode, effective mode, fallback reason, and
   degraded status, you cannot prove a run was true Hybrid, and every measurement in
   steps 2-3 stays open to the objection that it was BM25.
2. **Implement the causal anchor guard** with tests first; replay only
   `weekly-market-cause`. Keep the rule that no broad/counter query may introduce a
   new company/topic entity without an explicit anchor or a high-confidence
   deterministic relation.
3. **Fix valuation anchor filtering** and replay 瑞华泰 against the step-0 Hybrid
   baseline, not the BM25 artifact. `天奈科技` is a known live case.
4. **Semantic judge replay**, then decide whether a larger benchmark, App Server
   ceiling experiment, or Knevo comparison is justified.

## Guardrails

- Docs corrections are committed in the reviewer worktree; the KB clone and both
  knowledge repositories are untouched. Keep it that way.
- Cross-repo merge of `9053b0c4` into `knowledge-base-private` is **not** authorized
  and needs the user's explicit approval. It remains an isolated candidate.
- Do not rebuild the large index in place. Any rebuild belongs in an isolated
  snapshot and must be hash-recorded first.
- Do not run the 28-case suite, build App Server, change freshness gates, or promote
  8792/8799 before steps 0-3 produce clean, comparable evidence.
- Keep `source_dirty`, Git revision, manifest revision, and content hashes as
  separate observable fields.
- Record the interpreter path with every future pass count, and keep `FINANCE_WS`
  set for KB test runs or collection fails on multiple-candidate-worktree discovery.

## Status

> **Freshness gate proven green and independently reproduced; dense retrieval
> unblocked by interpreter pinning; step 0 cleared to run. Contamination and causal
> drift confirmed as the real remaining gaps.**

# Causal Anchor Guard Handoff

Date: 2026-07-29
Status: **Telemetry slice verified and accepted; causal anchor guard is the next slice**
Reviewer worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Branch: `feat/agent-runtime-backends-verify`

## One-sentence handoff

The telemetry slice passes review — the per-attempt mode ledger is real code, not
just documentation, and I reproduced the focused suite — so the next slice is the
causal anchor guard; I have located the exact three lines that cause the drift and
one telemetry hole that the current contract wording overstates.

## Review result: accepted

Verified against the repositories rather than read off the report.

**The contract is implemented.** `RetrievalAttempt`
(`closed_loop_retrieval.py:49-58`) is a frozen dataclass carrying `requested_mode`,
`effective_mode`, `fallback_reason`, `degraded`. `_run_aperture` populates all four
from `response.telemetry` (`:288-303`), `inspector_dict` projects them (`:78-101`),
`EvidenceSearchResult.attempts` exposes them (`evidence_search.py:48`), and
`_trace_detail` emits ordered `retrieval_modes=requested->effective:reason:degraded`
signatures (`:343-363`). The claim that a result can no longer report `success`
while hiding a silent BM25 substitution holds.

**Focused tests pass.** `test_closed_loop_retrieval.py`, `test_evidence_search.py`,
`test_kb_rag.py` → `44 passed` under `/opt/homebrew/bin/python3` (3.14.5).

**The baseline artifact is sound.** It records both interpreters, `model_load_count=1`,
`prewarm_seconds=31.399`, index hashes matching the pinned receipt, and
`semantic_judge=disabled_deterministic_replay`. The `finance_python` it names
(`.venv-workbench/bin/python`, 3.12.13) exists. The reproduction contract is
complete enough to re-run.

**Isolation held.** Original KB still `main@883815c9`, 0 dirty across the five
indexed page directories. KB clone clean at `9053b0c4`. All six commits exist with
the stated subjects, and the tip advice was followed rather than pinned.

## Correction: the telemetry contract has one hole

The report says every attempt "carries requested mode, effective mode, fallback
reason, and degraded state." One path does not: the `budget_exhausted` attempt at
`closed_loop_retrieval.py:254-261` constructs `RetrievalAttempt` with only
`aperture`/`query`/`status`/`hit_count`, so the four mode fields stay at their
defaults (`""`, `""`, `""`, `False`).

This is defensible — no retrieval ran, so there is no effective mode to report —
and `_trace_detail` correctly skips all-empty signatures. But `degraded=False` on a
skipped attempt is indistinguishable from `degraded=False` on a healthy Hybrid run
when reading the ledger programmatically. Either state it as an explicit exception
in the contract, or give the skipped case a distinguishable marker. Do not leave the
contract claiming universal coverage it does not have.

## The drift mechanism, located

The report says causal retrieval "pivots into a topic inferred from the first
approximate hit." Confirmed, and the code path is precise:

1. `_narrow_queries` (`:370-376`) with `anchor=None` runs the raw question plus
   `"{query} 实体 代码"` and `"{query} 公司 题材"` — the last two actively solicit
   company/topic pages for a question that names no company.
2. `_extract_terms` (`:415-425`) harvests up to 8 regex terms from the titles and
   excerpts of the top 5 narrow hits. It filters only a 12-word `_GENERIC_TERMS`
   stoplist; any company name or concept passes.
3. `_broad_queries`/`_counter_queries` (`:385-412`) splice those terms into
   `subject = query`, so the harvested topic is now part of the query text.

The `_hit_overlaps_terms` gate at `:196-198` does not prevent this. It only requires
a narrow hit to overlap the *question's own* terms — and the question 这一周行情下跌
contributes 行情/下跌 plus every 2-gram of them (`:444-449`), which a 卖方研报 page
matches trivially. So a semiconductor report qualifies as "relevant narrow" and its
terms are promoted into the causal premise.

The baseline shows the outcome exactly:

```text
narrow  : 这一周行情下跌的主要原因是什么
broad   : ... 晚间卖方研报202602 半导体 光纤光缆 存储下跌 周内首现下跌 ...
counter : ... 晚间卖方研报202602 半导体 光纤光缆 存储下跌 风险 证伪 ...
```

**A detail the report understates.** `trace_status` is `success` with 10 fresh
evidence atoms, but `counter=0` and `discarded=7`, and the served sources are dated
`20260202`, `20260613`, `20260621`, `20260614`, `20260616`, `20260709`, `0506`,
`0511`, `20260622` — none is the 2026-07-24 week. So the failure is not only "wrong
topic": the run reports success while returning zero counter-evidence and nothing
from the target week. Whatever the guard does, `success` must stop being reachable
in this state. That is a stronger acceptance signal than topic matching, and it is
cheap to assert.

## Next slice: causal anchor guard

Design and plan it separately; do not mix it into telemetry code.

Required behavior, unchanged from your list and restated for the record:

1. Classify whether the query carries an explicit entity, concept, index/market, or
   time-window anchor.
2. For generic weekly-market causal questions with no anchor, do not copy arbitrary
   company/topic terms from the first approximate hit into broad/counter queries.
3. Admit a new company/topic later only from an explicit anchor or a high-confidence
   deterministic relation.
4. With no safe anchor, keep the original market/time terms or return an honest
   evidence-unavailable result.
5. Preserve cutoff filtering, fresh-only evidence, counter search, content hashes,
   and per-attempt telemetry.

Suggested points of attack, given the trace above: the two anchor-soliciting narrow
variants at `:373-375`, the unfiltered promotion in `_extract_terms`, and the
2-gram expansion at `:444-449` that makes the overlap gate nearly always true for
short generic questions. Fix the promotion path rather than widening the stoplist —
`_GENERIC_TERMS` cannot enumerate every company in the Wiki.

Primary regression:

```text
这一周行情下跌的主要原因是什么
cutoff=2026-07-24
```

Must reject both known drift branches: BM25 牧原/猪周期, and true-Hybrid
半导体/光纤光缆. Assert additionally that a run serving no source from the target
week cannot report `success`.

After the causal guard passes, open the valuation-filtering slice with `天奈科技` as
the fixed true-Hybrid contamination case (`方邦股份` is a second, from the same
baseline). Semantic judge replay follows both deterministic seams.

## Reproduction contract

```text
KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python3
RAG_BGE_MODEL=/Users/a77/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181
RAG_INDEX_DIR=/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/.rag_index
HF_HUB_OFFLINE=1
RAG_WORKER_ENABLED=1   # multi-aperture replay: load the 4.3G model once
```

Record both interpreters with every pass count. For finance tests on this machine
`/opt/homebrew/bin/python3` (3.14.5) works; `/usr/bin/python3` is 3.9 and fails
collection on `TypeAlias`, so do not use it. After each replay remove only generated
access-log lines and require the KB clone to be clean.

## Guardrails

- Cross-repo merge of `9053b0c4` remains unauthorized.
- Do not use `/Users/a77/知识库/wiki` as data; that repo supplies interpreter
  infrastructure only, and note `.rag_venv` there is reached through a symlink.
- Do not rebuild the large index in place.
- Do not run 28 cases, build App Server, relax gates, or promote 8792/8799 before
  the causal and valuation seams have bounded evidence.
- Do not commit access logs, weights, venvs, indexes, secrets, databases, or
  unrelated dirty-worktree files.
- Keep the telemetry contract honest: if `budget_exhausted` stays outside it, say so
  in the contract text.

## Status

> **Telemetry slice accepted and reproduced. Drift mechanism located to three
> specific functions. Causal anchor guard cleared to start, with a stronger
> acceptance signal available: no target-week source must mean no `success`.**

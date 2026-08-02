# Causal Anchor Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent unanchored weekly market-causal retrieval from promoting arbitrary first-hit topics, and require target-window plus counter-evidence coverage before EvidenceSearch can report success.

**Architecture:** Add an explicit execution bit to attempt telemetry, a backward-compatible retrieval expansion policy, and an immutable EvidenceSearch policy for source-window/counter requirements. Wire the causal policy only from `time_aligned_market_causal` Episode contracts; all valuation/theme callers retain current behavior.

**Tech Stack:** Python 3.12, frozen dataclasses, typed Literals, existing closed-loop Hybrid RAG, pytest, BGE-m3/RRF replay.

---

### Task 1: Distinguish non-executed attempts

**Files:**
- Modify: `intelligence/services/closed_loop_retrieval.py`
- Test: `intelligence/tests/test_closed_loop_retrieval.py`

- [ ] **Step 1: Extend the existing budget test with a failing assertion**

In `test_observed_query_cost_skips_apertures_that_cannot_fit_budget`, add:

```python
assert [attempt.executed for attempt in result.attempts] == [True, False, False]
assert [
    item["executed"] for item in result.inspector_dict()["attempts"]
] == [True, False, False]
```

- [ ] **Step 2: Run RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_closed_loop_retrieval.py -q
```

Expected: `AttributeError` because `RetrievalAttempt.executed` does not exist.

- [ ] **Step 3: Implement the execution marker**

Add `executed: bool = True` to `RetrievalAttempt`; serialize it in
`inspector_dict`; set `executed=False` only in the budget-exhausted constructor.
Real-response constructors retain the default.

- [ ] **Step 4: Run GREEN and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_closed_loop_retrieval.py -q
git add intelligence/services/closed_loop_retrieval.py \
  intelligence/tests/test_closed_loop_retrieval.py
git commit -m "fix: distinguish skipped retrieval attempts"
```

### Task 2: Add query-only closed-loop expansion

**Files:**
- Modify: `intelligence/services/closed_loop_retrieval.py`
- Test: `intelligence/tests/test_closed_loop_retrieval.py`

- [ ] **Step 1: Write the failing drift regression**

Create a retriever whose first result contains `牧原股份 猪周期 半导体 光纤光缆`
and record every query. Run:

```python
result = retrieve_closed_loop(
    "这一周行情下跌的主要原因是什么",
    anchor=None,
    retrieve=retrieve,
    expansion_policy="query_only",
)
```

Assert that narrow runs only the raw question; later queries contain none of
`实体 代码`, `公司 题材`, `牧原股份`, `猪周期`, `半导体`, or `光纤光缆`.
Add a second assertion that an explicit `EntityAnchor("瑞华泰", "688323.SH")`
still produces an anchored ticker query.

- [ ] **Step 2: Run RED**

Use the Task 1 pytest command. Expected: unexpected keyword argument
`expansion_policy`.

- [ ] **Step 3: Implement the typed policy**

Define:

```python
RetrievalExpansionPolicy: TypeAlias = Literal["anchor_or_hits", "query_only"]
```

Add `expansion_policy="anchor_or_hits"` to `retrieve_closed_loop`. When policy
is `query_only` and `anchor is None`:

- `_narrow_queries` returns only `(query,)`;
- broad queries use fixed market-mechanism suffixes:
  `市场内部机制 资金 风险偏好`, `宏观 政策 外部事件`,
  `行业结构 权重板块`;
- counter queries use `反证 替代解释`, `市场内部 外部催化 区分`,
  `数据不支持 证据不足`;
- `_relevance_terms` receives no narrow hits, so no first-hit terms are
  promoted into overlap terms.

Validate the literal and raise `ValueError` for unknown policies.

- [ ] **Step 4: Run GREEN and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_closed_loop_retrieval.py -q
git add intelligence/services/closed_loop_retrieval.py \
  intelligence/tests/test_closed_loop_retrieval.py
git commit -m "fix: keep unanchored causal retrieval query-only"
```

### Task 3: Enforce source-window and counter coverage

**Files:**
- Modify: `intelligence/services/provider_observability.py`
- Modify: `intelligence/services/closed_loop_retrieval.py`
- Modify: `intelligence/services/evidence_search.py`
- Test: `intelligence/tests/test_closed_loop_retrieval.py`
- Test: `intelligence/tests/test_evidence_search.py`

- [ ] **Step 1: Write failing date parsing tests**

Assert:

```python
assert parse_source_date("wiki/sources/晚间卖方研报20260724.md") == date(2026, 7, 24)
assert parse_source_date("wiki/sources/0511卖方观点合集.md") is None
```

Expected RED: compact date is not parsed.

- [ ] **Step 2: Write the three policy-status tests**

Create `EvidenceSearchPolicy` cases for `2026-07-20..2026-07-24`:

1. only `2026-07-09` evidence → no evidence/observation, target-window gap,
   status `empty`;
2. target-window support but no counter → evidence retained, counter gap,
   status `partial`;
3. target-window support and counter → status `success`.

Use `expansion_policy="query_only"` and `require_counter_evidence=True`.

- [ ] **Step 3: Run RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_evidence_search.py -q
```

Expected: missing `EvidenceSearchPolicy`, compact parser, and `partial` status.

- [ ] **Step 4: Implement the policy and projection**

Add `partial` to `ProviderStatus`. Add `EvidenceSearchPolicy` with the exact
fields from the design and default it in `EvidenceSearch.__init__`.

Extend `parse_source_date` with a boundary-safe `YYYYMMDD` regex. Do not infer a
year for `MMDD` names.

Pass the expansion policy into `retrieve_closed_loop`. Before evidence
projection, filter entries to the required source window. Add coverage fields
with defaults:

```python
target_window_count: int = 0
target_window_counter_count: int = 0
window_rejected_count: int = 0
```

Build explicit target-window/counter gaps. Use `success` only with evidence and
zero policy gaps; use `partial` with evidence plus policy gaps; otherwise keep
the existing `future_of_cutoff`/`empty` behavior.

- [ ] **Step 5: Run GREEN and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_evidence_search.py -q
git add intelligence/services/provider_observability.py \
  intelligence/services/closed_loop_retrieval.py \
  intelligence/services/evidence_search.py \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_evidence_search.py
git commit -m "fix: require causal evidence window coverage"
```

### Task 4: Wire the causal policy from Episode composition

**Files:**
- Modify: `intelligence/services/episode_tools.py`
- Test: `intelligence/tests/test_episode_tools.py`

- [ ] **Step 1: Write the failing Episode policy regression**

Build `_market_cause_frame()` at `today/latest_data_date=2026-07-24` with
`evidence_search` authorized. Mock KB retrieval to return fresh hits dated
`2026-07-09` whose titles contain 半导体/光纤光缆. Execute `evidence_search` and
assert:

```python
assert result.trace.status == "empty"
assert result.evidence == ()
assert "2026-07-20" in result.gaps[0]
assert all("半导体" not in attempt_query for attempt_query in seen_queries[1:])
```

- [ ] **Step 2: Run RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_episode_tools.py -q
```

Expected: current registry uses the default EvidenceSearch policy and reports
success/off-window evidence.

- [ ] **Step 3: Compute and pass the target window**

Import `timedelta`. When `market_window_end` exists, compute start from an
explicit date in `frame.timeframe`; otherwise use Monday:

```python
market_window_start = market_news.latest_explicit_query_date(
    frame.timeframe or "",
    reference_date=context.information_cutoff.as_of_date,
)
if market_window_start is None:
    market_window_start = market_window_end - timedelta(
        days=market_window_end.weekday()
    )
```

Build `EvidenceSearchPolicy(expansion_policy="query_only",
required_source_start=market_window_start,
required_source_end=market_window_end,
require_counter_evidence=True)` and pass it only for
`time_aligned_market_causal` contracts.

- [ ] **Step 4: Run GREEN and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_closed_loop_retrieval.py -q
git add intelligence/services/episode_tools.py \
  intelligence/tests/test_episode_tools.py
git commit -m "fix: apply causal evidence policy in episodes"
```

### Task 5: True-Hybrid replay and handoff

**Files:**
- Create: `docs/verification/phase-c-causal-anchor-guard-2026-07-29.md`
- Create: `docs/handoffs/2026-07-29-causal-anchor-guard-completion.md`

- [ ] **Step 1: Replay the fixed case with the pinned environment**

Use the exact interpreter/model/index contract from
`2026-07-29-causal-anchor-guard-handoff.md`, `RAG_WORKER_ENABLED=1`, cutoff
`2026-07-24`, and the Episode causal policy. Require:

- no forbidden first-hit topic in later queries;
- no off-window/undated evidence in the observation;
- no `success` without target-window evidence and counter-evidence;
- all executed attempts remain `hybrid -> hybrid` without degradation.

- [ ] **Step 2: Clean generated access logs and audit isolation**

Remove only new probe lines with `apply_patch`. Require the KB clone clean and
original KB at `main@883815c9` with 0 dirty indexed page directories.

- [ ] **Step 3: Run proportional gates**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_kb_rag.py \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/services/provider_observability.py \
  intelligence/services/closed_loop_retrieval.py \
  intelligence/services/evidence_search.py \
  intelligence/services/episode_tools.py \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_episode_tools.py
git diff --check
```

- [ ] **Step 4: Write and commit the completion evidence**

Document the behavioral delta, exact replay queries/status/gaps, test
interpreter, isolation, remaining valuation contamination, and next final goal.

```bash
git add docs/verification/phase-c-causal-anchor-guard-2026-07-29.md \
  docs/handoffs/2026-07-29-causal-anchor-guard-completion.md
git commit -m "docs: hand off causal anchor guard"
```

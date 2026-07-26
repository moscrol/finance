# Runtime Contract and Provider Tolerance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three remaining pre-Phase-3 seams: a model plan cannot shrink the immutable user task, the legacy agent loop can honor a 24-call deep ceiling, and Eastmoney news search tolerates natural-language and compound model queries.

**Architecture:** `ResearchTaskContract.required_outputs` remains the code-owned minimum answer set; `ResearchPlan.answer_elements` is a model-owned superset that may only grow across revisions. The legacy agent-loop environment cap is raised without changing its default. Eastmoney keeps strict title relevance, but one logical provider call may retry a bounded list of simpler keywords only after an honest empty result; provider errors do not trigger retry storms and all attempted queries remain in one trace.

**Tech Stack:** Python dataclasses, deterministic text normalization, existing QueryLedger and ProviderTrace, pytest, Ruff.

---

## Public seams under test

1. `validate_plan_answer_elements()` and `validate_plan_revision()` enforce the immutable task floor and monotonic revisions.
2. `agent_research.max_steps()` accepts a configured deep ceiling of 24 while retaining the default of 4 and rejecting values outside 1-24.
3. `market_news.fetch_eastmoney_news_result()` accepts a natural question, performs bounded empty-result fallback, merges by URL/title, and reports attempted keywords in its trace.

### Task 1: Make model-owned answer elements monotonic above the task floor

**Files:**
- Modify: `intelligence/services/research_plan.py`
- Modify: `intelligence/services/agent_episode.py`
- Modify: `intelligence/tests/test_research_plan.py`
- Modify: `intelligence/tests/test_agent_episode.py`

- [ ] **Step 1: Write failing contract and revision tests**

Add tests proving that an initial plan missing `counterpoint` is rejected when the immutable contract requires it, a revision may add an element, and a revision may not remove an existing element.

```python
validate_plan_answer_elements(
    plan,
    required_answer_elements=("direct_assessment", "counterpoint"),
)

with pytest.raises(ValueError, match="remove answer elements"):
    validate_plan_revision(first, shrunk, original_task_id="t", current_task_id="t")
```

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_research_plan.py \
  intelligence/tests/test_agent_episode.py -q
```

Expected: the new public validator is absent and revision shrink is accepted.

- [ ] **Step 3: Implement the immutable floor and monotonic revision rule**

`validate_plan_answer_elements()` compares normalized exact output IDs from the immutable contract. `validate_plan_revision()` keeps the task-identity and revision checks, then rejects `previous.answer_elements - current.answer_elements`. In `ContinuousAgentEpisode`, validate every parsed plan against `context.contract.required_outputs` before recording it; a bad plan uses the existing same-Episode protocol-repair turn and receives no tool or budget authority.

- [ ] **Step 4: Run tests, Ruff, and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_research_plan.py \
  intelligence/tests/test_agent_episode.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/services/research_plan.py intelligence/services/agent_episode.py \
  intelligence/tests/test_research_plan.py intelligence/tests/test_agent_episode.py
git commit -m "fix: keep research plans above the task floor"
```

### Task 2: Remove the legacy eight-call deep ceiling

**Files:**
- Modify: `intelligence/services/agent_research.py`
- Modify: `intelligence/tests/test_agent_research.py`

- [ ] **Step 1: Write a failing configured-budget boundary test**

```python
monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "24")
assert agent_research.max_steps() == 24
monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "25")
assert agent_research.max_steps() == 24
```

Also assert unset/invalid values retain `DEFAULT_MAX_STEPS == 4` and zero clamps to one.

- [ ] **Step 2: Run the test and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_agent_research.py -q
```

Expected: the configured value 24 is silently reduced to 8.

- [ ] **Step 3: Replace the hidden literal with the root hard ceiling**

Add `MAX_CONFIGURED_STEPS = 24` and clamp the environment value to 1-24. Do not change the default, auto-enable deep mode, or create another budget ledger.

- [ ] **Step 4: Run tests, Ruff, and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_agent_research.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/services/agent_research.py intelligence/tests/test_agent_research.py
git commit -m "fix: allow deep agent research budget"
```

### Task 3: Make Eastmoney tolerate natural and compound queries

**Files:**
- Modify: `intelligence/services/market_news.py`
- Modify: `intelligence/tests/test_market_news.py`

- [ ] **Step 1: Write failing provider-tolerance tests**

Patch `_fetch_eastmoney_news_uncached` at the public wrapper seam. Prove that `上周A股下跌原因` tries the original query, then simpler candidates until `A股` succeeds; `低空经济 商业航天` merges distinct single-keyword results; duplicate URL/title entries collapse; a request/parse error stops immediately; total attempts are bounded and the trace lists them.

```python
result = fetch_eastmoney_news_result("上周A股下跌原因", timeout=2.0)
assert calls[:2] == ["上周A股下跌原因", "A股下跌"]
assert "A股" in calls
assert result.trace.status == "fallback_success"
```

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_market_news.py -q
```

Expected: only the exact compound query is attempted.

- [ ] **Step 3: Add bounded empty-result fallback inside one provider call**

Create a deterministic candidate generator with at most three fallback terms. It removes time/question scaffolding, preserves named market/entity/theme anchors, strips common direction/reason suffixes for an atomic subject, and splits explicit whitespace/conjunction compounds. The wrapper retries only `status == "empty"`, shares the caller's total timeout across attempts, merges with `merge_news_items`, and returns one ProviderTrace with status `fallback_success`, `empty`, or the original provider error. Keep the low-level title-contains-keyword hard filter unchanged.

- [ ] **Step 4: Run focused and adjacent tests, Ruff, and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_market_news.py \
  intelligence/tests/test_agent_research.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/services/market_news.py intelligence/tests/test_market_news.py
git commit -m "fix: tolerate natural news provider queries"
```

### Task 4: Verify the pre-Phase-3 slice

**Files:**
- Modify: `docs/superpowers/plans/2026-07-27-runtime-contract-and-provider-tolerance.md`
- Create: `docs/verification/runtime-contract-provider-tolerance-2026-07-27.md`

- [ ] **Step 1: Run the focused cross-module suite**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_research_plan.py \
  intelligence/tests/test_agent_research.py \
  intelligence/tests/test_market_news.py \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_continuous_turn_adapter.py -q
```

- [ ] **Step 2: Run Ruff and `git diff --check`**

- [ ] **Step 3: Record exact counts, query attempts, trace states, and non-actions**

The receipt must explicitly state that no frozen nine-case benchmark, 8792 switch, or `main` merge occurred. Mark checkboxes only from observed results.

- [ ] **Step 4: Commit the receipt**

```bash
git commit -m "docs: verify runtime contract and provider tolerance"
```

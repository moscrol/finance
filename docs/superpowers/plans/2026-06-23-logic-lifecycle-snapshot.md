# Logic Lifecycle Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight lifecycle snapshot layer so daily agent can show whether a market logic is new, waking up, warming, accelerating, diverging, declining, or exiting.

**Architecture:** Create an independent lifecycle service that reads recent `theme-candidates` exports plus the current daily-agent row and research-judge result. Daily agent enriches rows with lifecycle snapshots, then renders lifecycle stage and stage-change reason in Markdown/HTML.

**Tech Stack:** Python stdlib, existing `intelligence.workflows.daily_agent`, existing theme-candidates JSON exports, `unittest`.

---

### Task 1: Lifecycle Service

**Files:**
- Create: `intelligence/services/logic_lifecycle.py`
- Test: `tests/test_logic_lifecycle.py`

- [ ] Add failing tests for three cases: first appearance -> `新出现`; repeated old material with rising priority -> `升温验证`; repeated but falling priority/stock count -> `衰退观察`.
- [ ] Implement `build_lifecycle_snapshot(row, history_rows)` and `build_lifecycle_for_decision(decision, history_by_theme)`.
- [ ] Keep output in Chinese fields: `生命周期阶段`, `阶段变化`, `变化原因`, `观察窗口`, `连续出现天数`, `priority变化`, `强势股变化`, `下一步`.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_logic_lifecycle -v`.

### Task 2: Daily Agent Integration

**Files:**
- Modify: `intelligence/workflows/daily_agent.py`
- Modify: `tests/test_daily_agent.py`

- [ ] Build recent theme-candidates history from selected dates before rendering the decision.
- [ ] Enrich each non-placeholder row with `logic_lifecycle`.
- [ ] Render lifecycle stage in section rows and evidence cards.
- [ ] Add assertions that daily-agent JSON/Markdown/HTML contain `生命周期`.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_daily_agent tests.test_logic_lifecycle -v`.

### Task 3: Verification and PR Update

**Files:**
- Existing changed files only.

- [ ] Run full focused suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_research_judge tests.test_daily_agent tests.test_daily_review_agent_entry tests.test_cockpit_agent_entry tests.test_paths tests.test_question_router tests.test_logic_lifecycle -v`.
- [ ] Compile touched modules.
- [ ] Commit and push to PR #88.

# Daily Research Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build P2 daily research task queues on top of lifecycle snapshots and evidence judgment.

**Architecture:** Add a focused `research_queue` service that classifies daily agent rows into four human action buckets. Wire the service into `daily_agent` report generation and render the queues in Markdown and HTML.

**Tech Stack:** Python standard library, existing `unittest` tests, existing daily agent Markdown/HTML renderer.

---

### Task 1: Research Queue Service

**Files:**
- Create: `intelligence/services/research_queue.py`
- Test: `tests/test_research_queue.py`

- [ ] Write failing tests for four task buckets and data-gap skip.
- [ ] Implement `build_research_queue(decision)`.
- [ ] Sort each queue by `priority_score` descending.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_research_queue -v`.

### Task 2: Daily Agent Integration

**Files:**
- Modify: `intelligence/workflows/daily_agent.py`
- Modify: `tests/test_daily_agent.py`

- [ ] Add failing assertions for `report["research_queue"]`.
- [ ] Render `## 今日研究任务队列` in Markdown.
- [ ] Render a human-readable task queue section in HTML.
- [ ] Add research queue summary to `next_actions`.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_daily_agent tests.test_research_queue -v`.

### Task 3: Verification and PR Update

**Files:**
- Update generated `2026-06-11-daily-agent` JSON/Markdown/HTML outputs.
- Update `/Users/a77/Desktop/金融agent执行清单.md`.

- [ ] Run `python3 -m intelligence.cli agent-daily --date 2026-06-11 --kb-wiki '/Users/a77/Desktop/c c/知识库/wiki' --semantic-rag-top-n 3 --wiki-rag-k 3`.
- [ ] Run `python3 scripts/render_review_workbench.py && python3 scripts/render_cockpit.py --knowledge-root '/Users/a77/Desktop/c c/知识库'`.
- [ ] Run focused regression with `tests.test_research_judge tests.test_daily_agent tests.test_daily_review_agent_entry tests.test_cockpit_agent_entry tests.test_paths tests.test_question_router tests.test_logic_lifecycle tests.test_research_queue`.
- [ ] Compile touched modules.
- [ ] Commit and push to PR #88.

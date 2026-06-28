# Market Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add P3 short-term L4 market validation summaries to daily agent.

**Architecture:** Add `intelligence/services/market_validation.py` to read current and recent `theme-candidates` rows and compute deterministic Chinese validation summaries. Wire the summary into `daily_agent` JSON, Markdown, and HTML without changing research queue ownership.

**Tech Stack:** Python standard library, existing `unittest`, existing `theme-candidates` exports.

---

### Task 1: Market Validation Service

**Files:**
- Create: `intelligence/services/market_validation.py`
- Test: `tests/test_market_validation.py`

- [ ] Write failing tests for strong, medium, weak, and marginal-change summaries.
- [ ] Implement `build_market_validation_snapshot(current, history_rows)`.
- [ ] Implement `load_market_validation_context(exports_dir, dates, current_date, top_per_date)`.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_market_validation -v`.

### Task 2: Daily Agent Integration

**Files:**
- Modify: `intelligence/workflows/daily_agent.py`
- Modify: `tests/test_daily_agent.py`

- [ ] Add failing assertions for `market_validation` in report rows, Markdown, and HTML.
- [ ] Enrich daily decision rows with `market_validation`.
- [ ] Render market validation in section rows and evidence cards.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_daily_agent tests.test_market_validation -v`.

### Task 3: Verification and PR Update

**Files:**
- Update generated `2026-06-11-daily-agent` JSON/Markdown/HTML outputs.
- Update `/Users/a77/Desktop/金融agent执行清单.md`.

- [ ] Run `python3 -m intelligence.cli agent-daily --date 2026-06-11 --kb-wiki '/Users/a77/Desktop/c c/知识库/wiki' --semantic-rag-top-n 3 --wiki-rag-k 3`.
- [ ] Run `python3 scripts/render_review_workbench.py && python3 scripts/render_cockpit.py --knowledge-root '/Users/a77/Desktop/c c/知识库'`.
- [ ] Run focused regression with P0/P1/P2/P3 tests.
- [ ] Compile touched modules.
- [ ] Commit and push to PR #88.

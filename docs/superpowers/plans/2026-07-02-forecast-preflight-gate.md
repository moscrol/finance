# Forecast Preflight Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a preflight gate so market forecast / review generation checks daily-agent lifecycle and research gaps before producing a formal复盘.

**Architecture:** Add a focused `forecast_preflight` service that consumes existing `daily-agent.json` / `research_queue` output and returns `ready`, `needs_deepdive`, or `missing_daily_agent`. Wire the gate into `answer_orchestrator` planning text so market forecast routes know to run this check before generation.

**Tech Stack:** Python standard library, existing daily-agent JSON schema, `unittest`.

---

### Task 1: Forecast Preflight Service

**Files:**
- Create: `intelligence/services/forecast_preflight.py`
- Test: `intelligence/tests/test_forecast_preflight.py`

- [ ] Write tests for blocking IMA and official-evidence gaps.
- [ ] Implement `build_forecast_preflight(report_or_queue, source_artifact=None, allow_draft=True)`.
- [ ] Return machine-readable blocking items and a prompt block for answer composition.

### Task 2: Orchestrator Hook

**Files:**
- Modify: `intelligence/services/answer_orchestrator.py`
- Test: `intelligence/tests/test_answer_orchestrator.py`

- [ ] Add market forecast retrieval / quality-gate language requiring `forecast_preflight`.
- [ ] Add tests that market forecast plans mention the preflight gate and DeepDive first.

### Task 3: Verification

**Commands:**
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest intelligence.tests.test_forecast_preflight intelligence.tests.test_answer_orchestrator -v`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_research_queue tests.test_daily_agent -v`

# Overnight Hybrid Forecast Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a `market_forecast` question names overnight / US / overseas markets, authorize `news_search` and `web_search` so the continuous episode can verify the user premise. Pure A-share forecasts stay local-only.

**Architecture:** Add overnight-external markers inside `resolve_evidence_plan`. `runtime_capabilities_for_frame` already unions the evidence-plan capabilities with the policy floor, so the existing `current_market_scenarios` floor stays `market_data + mainline_context`. Do not re-register tools, do not change verification, do not change `memory_gate`, do not open news/web for every forecast.

**Tech Stack:** Python, pytest, existing `TurnControlCore` + `evidence_capabilities` seams.

**Spec:** `docs/learning/spec-continuous-depth-gap-r1.md` R2 P0-A (branch `spec/continuous-depth-gap-r1`).

**Seams under test:** `resolve_evidence_plan` and `runtime_capabilities_for_frame` via `TurnControlCore().control()`. No private helpers.

---

### Task 1: Failing authorization tests

**Files:**
- Modify: `intelligence/tests/test_evidence_capabilities.py`
- Modify: `intelligence/tests/test_turn_control_core.py`

- [ ] **Step 1: Write the failing tests**

Add to `test_evidence_capabilities.py`:

```python
_FIFTH_ROUND_OVERNIGHT = (
    "基于周二的盘面数据，你认为主线是什么。"
    "今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会"
)


def test_overnight_hybrid_forecast_adds_news_and_web_requirements():
    plan = resolve_evidence_plan(
        _FIFTH_ROUND_OVERNIGHT,
        question_type="market_forecast",
    )
    assert plan.profile == "market_forecast"
    assert plan.mandatory_provider_names == ("MARKET_DAILY",)
    assert "news_search" in plan.optional_provider_names or any(
        item.capability == "news_search" for item in plan.requirements
    )
    assert any(item.capability == "news_search" for item in plan.requirements)
    assert any(item.capability == "web_search" for item in plan.requirements)


def test_tonight_review_without_external_marker_stays_local_forecast():
    plan = resolve_evidence_plan(
        "今晚复盘，你认为明天盘面会怎么走",
        question_type="market_forecast",
    )
    assert {item.capability for item in plan.requirements} == {
        "market_data",
        "mainline_context",
    }
```

Add to `test_turn_control_core.py`:

```python
def test_overnight_hybrid_forecast_runtime_authorizes_news_and_web() -> None:
    result = TurnControlCore().control(
        "基于周二的盘面数据，你认为主线是什么。"
        "今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会"
    )

    capabilities = runtime_capabilities_for_frame(result.task_frame)

    assert result.task_frame.question_type == "market_forecast"
    assert "market_data" in capabilities
    assert "mainline_context" in capabilities
    assert "news_search" in capabilities
    assert "web_search" in capabilities
```

Keep `test_market_forecast_runtime_uses_current_structure_without_causal_web_tools` unchanged.

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_evidence_capabilities.py::test_overnight_hybrid_forecast_adds_news_and_web_requirements intelligence/tests/test_turn_control_core.py::test_overnight_hybrid_forecast_runtime_authorizes_news_and_web -q`

Expected: FAIL because `market_forecast` still only plans `MARKET_DAILY` + D4.

---

### Task 2: Minimal plan-layer change

**Files:**
- Modify: `intelligence/services/evidence_capabilities.py`

- [ ] **Step 3: Write minimal implementation**

Add overnight markers and, only for `question_type == "market_forecast"`, append optional W7 + WEB requirements when the query matches.

Do not change `_RUNTIME_CAPABILITY_FLOOR["current_market_scenarios"]`.
Do not change `route_table`.
Do not change `build_default_tools`.

- [ ] **Step 4: Run the new tests and the local-only regression**

Run: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_evidence_capabilities.py intelligence/tests/test_turn_control_core.py::test_market_forecast_runtime_uses_current_structure_without_causal_web_tools intelligence/tests/test_turn_control_core.py::test_overnight_hybrid_forecast_runtime_authorizes_news_and_web intelligence/tests/test_turn_control_core.py::test_market_cause_runtime_keeps_time_aligned_news_and_web_tools -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intelligence/services/evidence_capabilities.py intelligence/tests/test_evidence_capabilities.py intelligence/tests/test_turn_control_core.py docs/superpowers/plans/2026-08-19-overnight-forecast-auth.md
git commit -m "feat(episode): authorize news/web on overnight-hybrid market forecasts"
```

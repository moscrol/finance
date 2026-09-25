from __future__ import annotations

from intelligence.services.research_task_planner import plan_task


def _complete(payload: str):
    def complete(_messages, **_kwargs):
        return payload, "test", ""

    return complete


def test_planner_accepts_only_bounded_text_items() -> None:
    result = plan_task(
        "明天市场是反弹还是继续下跌？",
        contract=type("Contract", (), {"question_type": "market_forecast", "subject": "A股市场"})(),
        complete_fn=_complete(
            '{"subquestions":["看指数趋势", {"tools":["web_search"]}, "看资金"],'
            '"hypotheses":["反弹条件", "反弹条件", "继续走弱条件"]}'
        ),
    )
    assert result.source == "llm"
    assert result.subquestions == ("看指数趋势", "看资金")
    assert result.hypotheses == ("反弹条件", "继续走弱条件")


def test_planner_clamps_legal_json_to_contract_limits() -> None:
    result = plan_task(
        "明天市场是反弹还是继续下跌？",
        contract=type("Contract", (), {"question_type": "market_forecast", "subject": "A股市场"})(),
        complete_fn=_complete(
            '{"subquestions":["q1","q2","q3","q4","q5","q6"],'
            '"hypotheses":["h1","h2","h3","h4","h5"]}'
        ),
    )

    assert result.source == "llm"
    assert result.subquestions == ("q1", "q2", "q3", "q4", "q5")
    assert result.hypotheses == ("h1", "h2", "h3", "h4")


def test_invalid_planner_json_uses_forecast_rule_fallback() -> None:
    result = plan_task(
        "明天市场怎么看",
        contract=type("Contract", (), {"question_type": "market_forecast", "subject": "A股市场"})(),
        complete_fn=_complete("not-json"),
    )
    assert result.source == "rules"
    assert any("反弹" in item for item in result.hypotheses)
    assert len(result.subquestions) <= 5
    assert len(result.hypotheses) <= 4


def test_planner_schema_failure_uses_rule_fallback() -> None:
    result = plan_task(
        "明天市场怎么看",
        contract=type("Contract", (), {"question_type": "market_forecast", "subject": "A股市场"})(),
        complete_fn=_complete('{"subquestions":{"tool":"web_search"},"hypotheses":[]}'),
    )

    assert result.source == "rules"
    assert result.reason == "planner_empty_plan"


def test_planner_ignores_control_fields_and_preserves_contract() -> None:
    """Planner 只能提供检索顺序，不能变更已经确定的研究契约。"""

    contract = type(
        "Contract",
        (),
        {
            "question_type": "market_forecast",
            "subject": "A股市场",
            "allowed_capabilities": ("market_data", "web_search"),
            "research_tier": "quick",
            "required_outputs": ("rebound_case", "decline_case", "invalidation"),
        },
    )()
    original = (
        contract.allowed_capabilities,
        contract.research_tier,
        contract.required_outputs,
    )

    result = plan_task(
        "明天市场怎么看",
        contract=contract,
        complete_fn=_complete(
            '{"subquestions":["先看盘面"],"hypotheses":["反弹条件"],'
            '"allowed_capabilities":["l3_lookup"],"research_tier":"deep",'
            '"required_outputs":[],"tools":["web_search"]}'
        ),
    )

    assert result.source == "llm"
    assert result.subquestions == ("先看盘面",)
    assert result.hypotheses == ("反弹条件",)
    assert (
        contract.allowed_capabilities,
        contract.research_tier,
        contract.required_outputs,
    ) == original
    assert set(result.to_dict()) == {"subquestions", "hypotheses", "source", "reason"}

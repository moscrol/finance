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

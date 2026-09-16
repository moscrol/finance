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


# ——————————————————————————————————————————— 参与者约束试验（q17 Q6 回灌，候选三）
def _plan(question: str, **attrs: object):
    """走规则支：不给 complete_fn，LLM 路径自然不可用。

    断言只看 ``subquestions``，不看 ``reason``——无 key 时 ``reason`` 被「planner
    unavailable」占用，拿它判分支会测到环境而不是逻辑。
    """
    contract = type("Contract", (), {"question_type": "", "subject": "", **attrs})()
    return plan_task(question, contract=contract, complete_fn=None)


def test_authority_questions_ask_who_decides_before_asking_the_tape() -> None:
    joined = "\n".join(_plan("发改委会不会批复这个扩产项目").subquestions)

    assert "由谁决定" in joined
    assert "公开约束" in joined
    assert "哪几种可行动作" in joined
    assert "能区分这几种可能" in joined
    # 边界：没有公开依据就保持为假设，不补内部动机。
    assert "不补内部动机" in joined


def test_changing_only_the_decision_surface_changes_the_downstream_questions() -> None:
    """判据：两句只换决策面（审批 vs 招标），下游研究问题必须跟着换主体。"""
    approval = _plan("这个项目等主管部门批复吗")
    tender = _plan("甲方改成最低价中标后还能拿下这个订单吗")

    assert "主管部门" in "\n".join(approval.subquestions + approval.hypotheses)
    assert "招标方或采购方" in "\n".join(tender.subquestions + tender.hypotheses)
    assert approval.subquestions != tender.subquestions


def test_narrative_policy_words_alone_do_not_trigger_the_trial() -> None:
    """词表刻意窄：叙事级「政策利好」不是「有人拍板」，不该改检索顺序。"""
    joined = "\n".join(_plan("政策利好下光伏板块怎么看").subquestions)

    assert "由谁决定" not in joined
    assert "哪些事实能直接回答问题？" in joined


def test_existing_branches_still_win() -> None:
    """试验只接管 forecast/comparison 没接走的问句，不抢它们的规划。"""
    forecast = "\n".join(_plan("明天扩产链会不会反弹", question_type="market_forecast").subquestions)
    comparison = "\n".join(_plan("对比两家公司的中标情况", question_type="comparison").subquestions)

    assert "支持反弹/正向情景的证据和触发条件是什么？" in forecast
    assert "由谁决定" not in forecast
    assert "比较对象和口径是什么？" in comparison
    assert "由谁决定" not in comparison

"""残差题的 Knevo 形检索下限：授权地板 + 窄槽位。

公开缝只有两个：``runtime_capabilities_for_frame(TaskFrame)`` 和
``build_episode_context``。测试必须显式构造 ``question_type=general_finance_qa``，
不能依赖 TurnController 把某句口语分类成残差——命中路径吸收后（如 #72 的
outlook → forecast）那条句子会变成另一张菜单，地板断言会假绿或假红。
"""

from __future__ import annotations

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.evidence_capabilities import runtime_capabilities_for_frame
from intelligence.services.task_frame import TaskFrame, task_frame_requires_retrieval


def _frame(
    question: str,
    *,
    question_type: str = "general_finance_qa",
    evidence_policy: str = "general_finance_evidence",
    required_outputs: tuple[str, ...] = ("direct_answer", "evidence_boundary"),
) -> TaskFrame:
    return TaskFrame(
        raw_question=question,
        user_goal="形成直接判断",
        question_type=question_type,
        subject="已验证主体",
        subject_kind="unknown",
        market_scope="A股",
        timeframe="最新可用日期",
        required_outputs=required_outputs,
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy=evidence_policy,
        confidence=0.5,
    )


def test_financial_residual_runtime_includes_knevo_shaped_floor() -> None:
    """已经需要检索的残差题，授权里必须同时有行情、新闻、用户先验，并保留 kb+web。

    「你觉得a股明天会怎么走」会被 is_current_market_query 额外并入盘面 plan，
    改地板之前就已经有 market_data / news_search。必须再钉一道**没有**当期
    盘面 plan 的金融残差，否则只测到了 plan 合并，测不到 policy 地板。
    """

    for question in ("你觉得a股明天会怎么走", "超纯应材估值怎么看"):
        frame = _frame(question)
        assert task_frame_requires_retrieval(frame) is True
        capabilities = runtime_capabilities_for_frame(frame)
        assert {
            "market_data",
            "news_search",
            "memory_lookup",
            "kb_search",
            "web_search",
        }.issubset(set(capabilities)), question


def test_non_financial_residual_keeps_empty_runtime() -> None:
    """通用默认产出不是研究信号：笑话和天气题不得被三件套地板拖进检索。"""

    for question in ("给我讲个笑话", "今天天气如何"):
        frame = _frame(question)
        assert task_frame_requires_retrieval(frame) is False
        assert runtime_capabilities_for_frame(frame) == ()
        context = build_episode_context(
            frame,
            task_id=f"residual-chat-guard-{question}",
        )
        output_ids = {item.output_id for item in context.contract.required_outputs}
        assert "prime_quote" not in output_ids
        assert "prime_news" not in output_ids
        assert "prime_memory" not in output_ids
        assert context.contract.allowed_capabilities == () or set(
            context.contract.allowed_capabilities
        ).issubset({"finance_query", "evidence_search"})


def test_residual_episode_contract_opens_narrow_prime_slots() -> None:
    """能力定稿后才开槽；行情/新闻槽收窄到单工具，先验槽可选且 user_premise。"""

    frame = _frame("超纯应材估值怎么看")
    context = build_episode_context(frame, task_id="residual-prime-slots")
    slots = {item.output_id: item for item in context.contract.required_outputs}

    assert "prime_quote" in slots
    assert "prime_news" in slots
    assert "prime_memory" in slots

    assert slots["prime_quote"].evidence_types == ("market_data",)
    assert slots["prime_quote"].required is True
    assert slots["prime_quote"].grounding_mode == "evidence"

    assert slots["prime_news"].evidence_types == ("news_search",)
    assert slots["prime_news"].required is True
    assert slots["prime_news"].grounding_mode == "evidence"

    assert slots["prime_memory"].evidence_types == ("memory_lookup",)
    assert slots["prime_memory"].required is False
    assert slots["prime_memory"].grounding_mode == "user_premise"


def test_market_forecast_runtime_menu_is_unchanged() -> None:
    """Hit-path 菜单不动：残差地板不得泄漏进 forecast。"""

    frame = _frame(
        "昨天的反弹能持续多久",
        question_type="market_forecast",
        evidence_policy="current_market_scenarios",
        required_outputs=("duration_assessment", "evidence_boundary"),
    )
    assert runtime_capabilities_for_frame(frame) == (
        "market_data",
        "mainline_context",
    )
    context = build_episode_context(frame, task_id="forecast-no-primes")
    output_ids = {item.output_id for item in context.contract.required_outputs}
    assert "prime_quote" not in output_ids
    assert "prime_news" not in output_ids
    assert "prime_memory" not in output_ids


def test_prime_slots_do_not_inject_without_matching_tools() -> None:
    """有格子没工具是半截状态：调用方若抽掉某能力，对应 prime 不得出现。"""

    frame = _frame("超纯应材估值怎么看")
    context = build_episode_context(
        frame,
        task_id="residual-prime-gated",
        capabilities=("kb_search", "web_search"),
    )
    output_ids = {item.output_id for item in context.contract.required_outputs}
    assert "prime_quote" not in output_ids
    assert "prime_news" not in output_ids
    assert "prime_memory" not in output_ids

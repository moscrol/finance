"""Composer 必须看得见自己被按什么标准验收。

brief/compose 的 prompt 里此前只有「用户问题 + claim registry」。TaskFrame 的
required_outputs 一个字都没进去，而 task_fulfillment 又逐条按它判、判不过就把整份
答案换成「请补充数据源或稍后重试」——模型是在一张它看不见的评分表上被打分。

`AnswerSpec.prompt_constraints` 这个字段早就存在，专项 owner 也一直在填
（research_owner 的 output_contract），只有 GenericResearchOwner 这条路是空的，
而 grounded composer 又从不读它。两处都补上。
"""
from __future__ import annotations

from intelligence.services import llm_refine

REQUIRED = (
    "direct_assessment：针对预测窗口的直接判断，并明确当前基准情景",
    "invalidation：使当前判断失效的反证或关键监测指标",
)


def _user_content(messages: list[dict]) -> str:
    return next(m["content"] for m in messages if m["role"] == "user")


def test_decision_brief_prompt_lists_the_required_outputs() -> None:
    content = _user_content(
        llm_refine.build_decision_brief_messages(
            "你觉得a股明天会怎么走",
            "{}",
            required_outputs=REQUIRED,
        )
    )

    assert "direct_assessment" in content
    assert "invalidation：使当前判断失效的反证或关键监测指标" in content


def test_composer_prompt_lists_the_required_outputs() -> None:
    content = _user_content(
        llm_refine.build_grounded_composer_messages(
            "你觉得a股明天会怎么走",
            "brief",
            "{}",
            required_outputs=REQUIRED,
        )
    )

    assert "direct_assessment" in content
    assert "invalidation" in content


def test_the_requirement_carries_its_source_constraint() -> None:
    """只说「必须写到」而不说来源约束，等于鼓励为了凑齐而编。"""
    content = _user_content(
        llm_refine.build_grounded_composer_messages(
            "你觉得a股明天会怎么走",
            "brief",
            "{}",
            required_outputs=REQUIRED,
        )
    )

    assert "只能用 claim registry 里的事实来覆盖" in content
    assert "不要为了凑齐而编" in content


def test_no_contract_keeps_the_previous_prompt() -> None:
    """没有契约的调用方行为不变。"""
    for messages in (
        llm_refine.build_decision_brief_messages("问题", "{}"),
        llm_refine.build_grounded_composer_messages("问题", "brief", "{}"),
    ):
        assert "本轮必须覆盖的输出" not in _user_content(messages)

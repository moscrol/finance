"""1a7363c4 独立 QC N1–N6 原始输入及配对边界；不替代新提交复审。"""
import pytest

from intelligence.services.user_task import classify_top_level_regions as classify


def test_n1_closed_quote_enclosing_fence_keeps_relaxation_protected():
    regions = classify("「\n```\nx\n```\n\n可以查真实数据。\n\n」")
    assert regions.classification == "no_constraint_confirmed"
    assert regions.instructions == ()


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_closed_quote_owns_unclosed_inner_fence(fence):
    regions = classify(f"「材料原文\n{fence}\n不要联网。\n」")
    assert regions.classification == "no_constraint_confirmed"
    assert regions.instructions == ()


def test_n2_numbered_report_heading_does_not_bypass_review():
    regions = classify(
        "1. 行业空间说明\n甲公司去年总收入20亿元，相关业务收入2亿元，处于行业扩产周期。\n"
        "不要联网。\n2. 风险说明\n客户验收周期不确定。"
    )
    assert regions.classification == "boundary_uncertain"
    assert regions.instructions == ()
    assert regions.sub_questions == ()


@pytest.mark.parametrize("prefix", ["本轮", "本轮请", "请本轮", "这次", "此次"])
def test_n3_prefixed_prohibition_uses_same_detector_in_all_roles(prefix):
    operation = prefix + "不要联网。"
    assert classify("材料如下：\n" + operation).classification == "boundary_uncertain"
    assert classify(operation).classification == "constraint_confirmed"
    assert classify("「" + operation + "」").classification == "no_constraint_confirmed"


@pytest.mark.parametrize("gap", [" ", "  ", "\t"])
def test_n4_whitespace_after_hypothesis_does_not_remove_a_axis(gap):
    regions = classify(f"假设{gap}甲公司明年订单翻倍，结合当前行情分析。")
    assert [(s.kind, s.scope) for s in regions.instructions] == [
        ("premise_declaration", "message"), ("constraint_b", "message"),
    ]
    assert regions.instructions[0].text == f"假设{gap}甲公司明年订单翻倍"


def test_n5_blank_line_inside_closed_quote_is_not_question_boundary():
    first = "请计算比例。\n「总收入10亿元。\n\n业务收入2亿元。」"
    regions = classify("1. " + first + "\n\n2. 哪些风险未确认？")
    assert regions.sub_questions == (first, "哪些风险未确认？")


def test_n6_question_scoped_b_requires_message_material_only():
    regions = classify("1. 请不要联网。")
    assert regions.classification == "boundary_uncertain"
    assert "question_scoped_data_scope" in regions.uncertain_reasons
    assert regions.instructions[0].scope == "q1"
    allowed = classify("只依据材料回答。\n\n1. 请不要联网。")
    assert allowed.classification == "constraint_confirmed"
    relaxed = classify("只依据材料回答。可以查真实数据。\n\n1. 请不要联网。")
    assert relaxed.classification == "boundary_uncertain"


def test_indented_question_qualification_stays_in_question():
    regions = classify("1. 请计算比例。\n  结果保留两位小数。\n\n2. 哪些风险未确认？")
    assert regions.sub_questions == ("请计算比例。\n结果保留两位小数。", "哪些风险未确认？")


def test_indented_question_prohibition_is_not_upgraded_to_message():
    regions = classify("1. 请计算比例。\n  不要联网。\n\n2. 哪些风险未确认？")
    assert regions.classification == "boundary_uncertain"
    assert [(s.kind, s.scope) for s in regions.instructions] == [("constraint_b", "q1")]

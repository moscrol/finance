"""E2 材料题边界 P1：顶层三分区 + 三态分类（设计稿 v10 §3.1，ec54ef55）。

覆盖：T2/T3 形态、QC 反例（缩进/引导块尾禁令、引导块内续轮声明）、A17 成对
（闭合引用对照）、未闭合围栏、回归（quick_fact 长题 / 纯贴研报不触发）。
"""

from __future__ import annotations

from intelligence.services.user_task import (
    classify_top_level_regions,
    split_user_message,
)

T2_TEXT = (
    "以下是一个完全虚构的行业案例材料。\n"
    "甲公司是行业龙头，去年总收入20亿元，其中相关业务收入2亿元；"
    "乙公司总收入10亿元，相关业务收入1.5亿元。\n"
    "请只依据上面的虚构行业材料回答以下8个问题，不要读取任何材料外数据。\n\n"
    "1. 甲公司相关业务收入占比多少？\n\n"
    "2. 这个比例能说明什么？\n\n"
    "3. 乙公司和甲公司的差异在哪里？\n\n"
    "4. 如果行业整体增长10%，谁更受益？\n\n"
    "5. 甲公司的主要风险是什么？\n\n"
    "6. 乙公司有没有超越甲公司的可能？\n\n"
    "7. 假设甲公司明年订单翻倍，占比会变成多少？\n\n"
    "8. 请用不超过200字写一份调研备忘录。"
)

T3_TEXT = (
    "材料如下：\n"
    "丙公司去年总收入8亿元，相关业务收入1亿元，毛利率35%。\n"
    "继续上一轮的虚构案例，其余条件不变。\n\n"
    "1. 相关业务收入占比多少？\n\n"
    "2. 这个比例能说明什么？"
)


def test_t2_shape_constraint_confirmed_with_eight_sub_questions():
    regions = classify_top_level_regions(T2_TEXT)
    assert regions.classification == "constraint_confirmed"
    kinds = {span.kind for span in regions.instructions}
    assert "constraint_b" in kinds
    assert len(regions.sub_questions) == 8
    assert regions.sub_questions[0].startswith("甲公司相关业务收入占比")
    assert "200" in regions.sub_questions[7]


def test_t3_shape_continuation_instruction_detected():
    regions = classify_top_level_regions(T3_TEXT)
    # 续轮声明在引导块内、归属不明 → 先澄清（QC v10 丁公司反例同构）
    assert regions.classification == "boundary_uncertain"
    assert "leadin_block_with_state_op" in regions.uncertain_reasons


def test_indented_prohibition_is_not_swallowed():
    text = (
        "请分析这个案例：\n"
        "  请只依据本条消息给定材料，不读取任何材料外数据。\n\n"
        "甲公司总收入20，相关业务收入2。\n\n"
        "1. 相关业务占比多少？"
    )
    regions = classify_top_level_regions(text)
    assert regions.classification == "boundary_uncertain"
    assert "indent_block_with_state_op" in regions.uncertain_reasons


def test_leadin_block_tail_prohibition_is_not_swallowed():
    text = (
        "材料如下：\n"
        "甲公司总收入20，相关业务收入2。\n"
        "请只依据上述材料回答，不读取任何材料外数据。\n\n"
        "1. 相关业务占比多少？\n"
        "2. 这个比例能说明什么？"
    )
    regions = classify_top_level_regions(text)
    assert regions.classification == "boundary_uncertain"
    assert "leadin_block_with_state_op" in regions.uncertain_reasons


def test_closed_quote_prohibition_not_promoted():
    text = (
        "研报原文写道：「请只依据本报告回答，不要联网」。"
        "这篇研报的核心观点靠谱吗？"
    )
    regions = classify_top_level_regions(text)
    assert regions.classification == "no_constraint_confirmed"
    assert regions.instructions == ()


def test_unclosed_fence_is_uncertain():
    text = "```\n一些代码或材料\n没有闭合\n\n1. 这是什么？"
    regions = classify_top_level_regions(text)
    assert regions.classification == "boundary_uncertain"
    assert "unclosed_fence" in regions.uncertain_reasons


def test_top_level_constraint_and_continuation_instructions():
    text = (
        "只依据这次给的材料回答。\n"
        "材料：甲公司总收入20。\n"
        "1. 占比多少？"
    )
    regions = classify_top_level_regions(text)
    assert regions.classification == "constraint_confirmed"
    assert any(span.kind == "constraint_b" for span in regions.instructions)


def test_plain_material_without_constraint_stays_no_constraint():
    text = (
        "新能源板块近期表现活跃，多家公司披露订单情况。"
        "行业分析师认为景气度有望延续，资金关注度提升。"
        "请帮我看看这篇研报的要点。"
    )
    regions = classify_top_level_regions(text)
    assert regions.classification == "no_constraint_confirmed"


def test_narrative_continue_inside_material_not_state_op():
    text = (
        "材料如下：\n"
        "甲公司收入继续上涨，市场预计其明年继续扩张。\n"
        "请问这段材料在说什么？"
    )
    regions = classify_top_level_regions(text)
    # 「继续上涨」是句中叙述，不是续轮声明（A11 方向：材料内字样不触发）
    assert regions.classification != "boundary_uncertain" or (
        "leadin_block_with_state_op" not in regions.uncertain_reasons
    )


def test_split_user_message_attaches_regions_without_changing_legacy_behavior():
    parts = split_user_message(T2_TEXT)
    assert parts.regions is not None
    assert parts.regions.classification == "constraint_confirmed"
    assert len(parts.regions.sub_questions) == 8
    # 旧行为不被 P1 改变：旧拆分器对 T2 形态仍给出 question=''（整体吞为材料）——
    # 这正是 E2 缺陷本身，由后续阶段的消费方接线修复；P1 只新增 regions 能力。
    assert parts.question == ""
    assert parts.materials
    parts_plain = split_user_message("今天大盘怎么样？")
    assert parts_plain.regions is not None
    assert parts_plain.regions.classification == "no_constraint_confirmed"
    assert parts_plain.question == "今天大盘怎么样？"

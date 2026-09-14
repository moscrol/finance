"""E2 材料题边界 P1v2：顶层三分区 + 三态分类（设计稿 v10 §3.1，QC 退修 R1-R6）。

测试分两层：
- 原始 T2/T3 冻结题面（从仓内冻结证据加载，不用转述——P1v1 用转述正是漏检温床）；
- 六类退修各自的最小合成探针（R1 句内第二句 / R2 字符级引号 / R3 识别一致性 /
  R4 长文 / R5 强保护不复核 / R6 多行题文与题级归属）+ 回归（A11 纯贴研报等）。
"""

from __future__ import annotations

from pathlib import Path

from intelligence.services.user_task import (
    classify_top_level_regions,
    split_user_message,
)

EVIDENCE_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok"
)
T2_REAL = (EVIDENCE_DIR / "t2-question.txt").read_text(encoding="utf-8")
T3_REAL = (EVIDENCE_DIR / "t3-question.txt").read_text(encoding="utf-8")


# ── 原始题面（冻结证据）──────────────────────────────────────────


def test_real_t2_constraint_confirmed_with_eight_questions():
    regions = classify_top_level_regions(T2_REAL)
    assert regions.classification == "constraint_confirmed"
    assert regions.uncertain_reasons == ()
    msg = [s for s in regions.instructions if s.scope == "message"]
    kinds = {s.kind for s in msg}
    assert "premise_declaration" in kinds  # 完全虚构声明
    assert "constraint_b" in kinds  # 请只依据给定材料分析（行内第二句，R1）
    assert len(regions.sub_questions) == 8


def test_real_t2_question_text_intact_and_multiline():
    regions = classify_top_level_regions(T2_REAL)
    q1 = regions.sub_questions[0]
    assert "中间还需要" in q1 and "哪些环节" in q1  # 多行题文被吸收（R6）
    # 题 2 含引号：整行不得被跳过，且存储文本保留引号原文（R2）
    q2 = regions.sub_questions[1]
    assert "「" in q2 or "“" in q2
    assert "排序" in q2


def test_real_t2_question_scoped_premise_marks():
    regions = classify_top_level_regions(T2_REAL)
    scoped = {s.scope for s in regions.instructions if s.scope != "message"}
    assert "q8" in scoped  # 「如果只能先深入研究一家公司」题级假设（R6）


def test_real_t3_continuation_at_message_scope():
    regions = classify_top_level_regions(T3_REAL)
    assert regions.classification == "constraint_confirmed"
    assert regions.uncertain_reasons == ()
    cont = [s for s in regions.instructions if s.kind == "continuation"]
    assert cont and all(s.scope == "message" for s in cont)
    assert any("继续" in s.text or "其余条件不变" in s.text for s in cont)
    assert len(regions.sub_questions) == 8
    scoped = {s.scope for s in regions.instructions if s.scope != "message"}
    assert "q7" in scoped  # 「假设我们的升级条件是」题级假设


# ── R1：句级识别（行内第二句、放宽形态）──────────────────────────


def test_r1_second_sentence_in_same_line_detected():
    text = "以下是完全虚构的研究案例，不对应现实公司。请只依据给定材料分析，不联网补现实事实。\n\n1. 占比多少？"
    regions = classify_top_level_regions(text)
    assert regions.classification == "constraint_confirmed"
    kinds = {s.kind for s in regions.instructions}
    assert kinds >= {"premise_declaration", "constraint_b"}


def test_r1_relaxation_form_detected():
    text = "可以查真实数据。\n\n甲公司总收入20。\n\n1. 占比多少？"
    regions = classify_top_level_regions(text)
    assert any(s.kind == "constraint_b" for s in regions.instructions)


# ── R2：字符级引号保护（不扩张到整行）────────────────────────────


def test_r2_quoted_question_line_not_skipped():
    text = (
        "请只依据给定材料回答。\n\n"
        "甲公司总收入20。\n\n"
        "1. 占比多少？\n\n"
        "2. 如果甲公司也想讲「相关业务】的故事，最容易拿哪个业务说事？\n\n"
        "3. 谁更受益？"
    )
    regions = classify_top_level_regions(text)
    assert len(regions.sub_questions) == 3
    assert "「" in regions.sub_questions[1]


def test_r2_prohibition_outside_quote_not_swallowed():
    regions = classify_top_level_regions("只依据「甲公司」的材料回答。")
    assert regions.classification == "constraint_confirmed"
    spans = [s for s in regions.instructions if s.kind == "constraint_b"]
    assert spans and "「甲公司」" in spans[0].text  # 存储保留原文


# ── R3：两处识别共用同一探测行为───────────────────────────────────


def test_r3_continuation_at_top_level_detected():
    text = "本轮其余条件不变。\n\n1. 占比多少？"
    regions = classify_top_level_regions(text)
    assert any(s.kind == "continuation" for s in regions.instructions)


def test_r3_same_continuation_inside_leadin_block_is_uncertain():
    text = "材料如下：\n丁公司去年总收入8。\n本轮其余条件不变。\n\n1. 占比多少？"
    regions = classify_top_level_regions(text)
    assert regions.classification == "boundary_uncertain"
    assert "leadin_block_with_state_op" in regions.uncertain_reasons


def test_r3_same_continuation_indented_is_uncertain():
    text = "请分析这个案例：\n  本轮其余条件不变。\n\n甲公司总收入20。\n\n1. 占比多少？"
    regions = classify_top_level_regions(text)
    assert regions.classification == "boundary_uncertain"


# ── R4：长文（无引导行的长粘贴）───────────────────────────────────


def test_r4_embedded_prohibition_in_long_paste_not_upgraded():
    text = (
        "新能源板块景气度持续上行，多家公司披露新增订单。\n"
        "不要联网，只依据本报告。\n"
        "风险提示：行业竞争加剧。"
    )
    regions = classify_top_level_regions(text)
    # 检出状态操作但归属不明 → uncertain（不静默升级为约束，也不静默忽略）；
    # 消费方在 boundary_uncertain 下不得执行任何状态操作（设计稿三态禁令）。
    assert regions.classification == "boundary_uncertain"
    assert "adjacent_state_op" in regions.uncertain_reasons


def test_r4_research_numbered_sections_not_question_group():
    text = (
        "行业深度报告\n\n"
        "1. 行业概览\n\n"
        "行业高增长主要由渗透率提升驱动，预计明年延续。\n\n"
        "2. 公司分析\n\n"
        "龙头公司订单充足，盈利能力稳定。"
    )
    regions = classify_top_level_regions(text)
    assert regions.classification == "no_constraint_confirmed"
    assert regions.sub_questions == ()


# ── R5：强保护不被内容复核重新解释────────────────────────────────


def test_r5_fence_inside_leadin_not_re_reviewed():
    text = "材料如下：\n```\n不要联网，只依据本报告。\n```\n\n1. 这段在说什么？"
    regions = classify_top_level_regions(text)
    assert regions.classification == "no_constraint_confirmed"
    assert regions.uncertain_reasons == ()


def test_r5_quote_inside_leadin_not_re_reviewed():
    text = "材料如下：\n研报写道：「请只依据本报告回答，不要联网」。\n\n1. 这段在说什么？"
    regions = classify_top_level_regions(text)
    assert regions.classification == "no_constraint_confirmed"
    assert regions.uncertain_reasons == ()


# ── R6：多行题文与题级归属─────────────────────────────────────────


def test_r6_multiline_question_absorbs_short_continuation():
    text = (
        "请只依据给定材料回答。\n\n"
        "甲公司总收入20。\n\n"
        "1. 这个比例说明什么？\n请结合材料回答。\n\n"
        "2. 差异在哪？"
    )
    regions = classify_top_level_regions(text)
    assert len(regions.sub_questions) == 2
    assert "请结合材料回答" in regions.sub_questions[0]


def test_r6_in_question_hypothesis_scoped_to_question():
    text = (
        "请只依据给定材料回答。\n\n"
        "甲公司总收入20。\n\n"
        "1. 假设订单翻倍，占比会变成多少？\n\n"
        "2. 差异在哪？"
    )
    regions = classify_top_level_regions(text)
    q1_spans = [s for s in regions.instructions if s.scope == "q1"]
    assert q1_spans and q1_spans[0].kind == "premise_declaration"
    assert "假设" in q1_spans[0].text
    # 不得升级为 message 级
    assert not any(
        s.scope == "message" and "假设" in s.text for s in regions.instructions
    )


# ── 回归（P1v1 已覆盖的形态不得回退）─────────────────────────────


def test_regression_leadin_tail_prohibition_uncertain():
    text = (
        "材料如下：\n"
        "甲公司总收入20，相关业务收入2。\n"
        "请只依据上述材料回答，不读取任何材料外数据。\n\n"
        "1. 相关业务占比多少？\n\n"
        "2. 这个比例能说明什么？"
    )
    regions = classify_top_level_regions(text)
    assert regions.classification == "boundary_uncertain"
    assert "leadin_block_with_state_op" in regions.uncertain_reasons


def test_regression_closed_quote_prohibition_not_promoted():
    text = "研报原文写道：「请只依据本报告回答，不要联网」。这篇研报的核心观点靠谱吗？"
    regions = classify_top_level_regions(text)
    assert regions.classification == "no_constraint_confirmed"
    assert regions.instructions == ()


def test_regression_unclosed_fence_is_uncertain():
    regions = classify_top_level_regions("```\n一些代码或材料\n没有闭合\n\n1. 这是什么？")
    assert regions.classification == "boundary_uncertain"
    assert "unclosed_fence" in regions.uncertain_reasons


def test_regression_narrative_continue_inside_material_not_state_op():
    text = "材料如下：\n甲公司收入继续上涨，市场预计其明年继续扩张。\n请问这段材料在说什么？"
    regions = classify_top_level_regions(text)
    assert regions.classification == "no_constraint_confirmed"


def test_regression_plain_question_passthrough():
    regions = classify_top_level_regions("今天大盘怎么样？")
    assert regions.classification == "no_constraint_confirmed"
    assert regions.sub_questions == ()


def test_split_user_message_attaches_regions_without_changing_legacy_behavior():
    parts = split_user_message(T2_REAL)
    assert parts.regions is not None
    assert parts.regions.classification == "constraint_confirmed"
    assert len(parts.regions.sub_questions) == 8
    # 旧行为不被 P1 改变（消费方接线在后续阶段）
    parts_plain = split_user_message("今天大盘怎么样？")
    assert parts_plain.regions is not None
    assert parts_plain.classification == "no_constraint_confirmed"
    assert not parts_plain.boundary_uncertain
    assert parts_plain.question == "今天大盘怎么样？"

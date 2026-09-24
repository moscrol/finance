"""D1 QC 六类反例的相邻组合；不替代 P2–P7 产品验收。"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from intelligence.services.user_task import classify_top_level_regions, find_state_ops

ROOT = Path(__file__).resolve().parents[2]


def test_original_independent_review_matrix():
    """冻结审查脚本原样入仓，防止返修时只挑通过的例子。"""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/e2_boundary_review_probe.py"), "--repo", str(ROOT)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["failed"] == 0
    assert report["passed"] == 46


@pytest.mark.parametrize("outer", [("「", "」"), ("『", "』"), ('"', '"'), ("“", "”")])
@pytest.mark.parametrize("inner", ["「", "『", '"', "“"])
def test_closed_outer_quote_is_opaque_to_other_quote_types(outer, inner):
    if inner == outer[0]:
        pytest.skip("同类嵌套由独立测试验证，不能拿一个闭符伪装双层闭合")
    text = f"{outer[0]}他说{inner}\n不要联网。{outer[1]}\n\n可以查真实数据。"
    regions = classify_top_level_regions(text)
    assert regions.classification == "constraint_confirmed"
    assert [(s.kind, s.text) for s in regions.instructions] == [("constraint_b", "可以查真实数据")]


def test_nested_same_quote_pair_and_escaped_delimiter():
    text = '「外层「不要联网。」仍在外层」\n\n只依据\\"甲公司\\"材料回答。'
    regions = classify_top_level_regions(text)
    assert regions.uncertain_reasons == ()
    assert len(regions.instructions) == 1
    assert regions.instructions[0].text == '只依据\\"甲公司\\"材料回答'


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_fenced_quote_close_cannot_complete_an_outer_opener(fence):
    text = f"他说「不要联网。\n{fence}\n」\n{fence}\n\n可以查真实数据。"
    regions = classify_top_level_regions(text)
    assert regions.classification == "boundary_uncertain"
    assert "unclosed_quote_with_state_op" in regions.uncertain_reasons


@pytest.mark.parametrize("operation", [
    "不要联网。", "本轮其余条件不变。", "可以查真实数据。",
    "这些公司是虚构的。", "假设甲公司明年订单翻倍，结合当前行情分析。",
])
def test_same_state_operation_respects_three_boundary_roles(operation):
    prefix = "材料如下：\n甲公司去年总收入20亿元，相关业务收入2亿元。"
    assert classify_top_level_regions(prefix + "\n" + operation).classification == "boundary_uncertain"
    assert classify_top_level_regions(prefix + "\n\n" + operation).classification == "constraint_confirmed"
    protected = classify_top_level_regions(prefix + "\n「" + operation + "」")
    assert protected.classification == "no_constraint_confirmed"
    assert protected.instructions == ()


def test_a8_has_both_axes_and_original_fragment_text():
    regions = classify_top_level_regions("假设甲公司明年订单翻倍，结合当前行情分析。")
    assert [(s.kind, s.text, s.scope) for s in regions.instructions] == [
        ("premise_declaration", "假设甲公司明年订单翻倍", "message"),
        ("constraint_b", "结合当前行情分析", "message"),
    ]
    assert len(find_state_ops("假设甲公司明年订单翻倍，结合最新行情分析。")) == 2


def test_multiple_long_and_quoted_question_continuations_are_exact():
    body = (
        "请计算比例。\n"
        "分子来自甲公司今年交付安排，分母来自去年相关业务收入，不能混用总收入口径。\n"
        "「甲公司总收入20亿元，相关业务收入2亿元。」\n"
        "结果请列出完整计算公式与来源，并说明这个数字不代表新增利润或收入增长率。"
    )
    regions = classify_top_level_regions("1. " + body + "\n\n2. 哪些风险未确认？")
    assert regions.sub_questions == (body, "哪些风险未确认？")


def test_mixed_long_material_not_reclaimed_as_question_instructions():
    text = (
        "甲公司是行业龙头，去年总收入20亿元，其中相关业务收入2亿元；乙公司总收入10亿元。\n"
        "1. 行业空间说明\n只依据本报告回答，不读取材料外数据。\n"
        "2. 风险说明\n行业竞争加剧，客户验收周期仍存不确定性。"
    )
    regions = classify_top_level_regions(text)
    assert regions.classification == "boundary_uncertain"
    assert "long_block_with_state_op" in regions.uncertain_reasons
    assert regions.instructions == ()
    assert regions.sub_questions == ()

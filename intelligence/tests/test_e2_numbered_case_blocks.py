"""编号题内的案例引导行是题文，不得提前被弱材料候选吞掉。"""
from pathlib import Path

import pytest

from intelligence.services.user_task import classify_top_level_regions, split_user_message


@pytest.mark.parametrize("heading", ["有两个后续案例：", "对比以下资料：", "材料如下："])
def test_numbered_question_keeps_case_body_and_next_number(heading):
    body = (
        f"{heading}\n"
        "案例甲：订单落地但股价下跌。\n"
        "案例乙：订单未落地但股价上涨。\n"
        "这两次应分别怎样评价事实判断、解释逻辑和价格结果？"
    )
    text = f"只依据以下材料回答。\n\n6. 请设计验证方案。\n\n7. {body}\n\n8. 请写方法卡。"
    parts = split_user_message(text)
    assert parts.regions.question_ids == ("q6", "q7", "q8")
    assert parts.sub_questions == ("请设计验证方案。", body, "请写方法卡。")
    assert body in parts.question
    assert parts.classification == "constraint_confirmed"


def test_question_case_body_state_operation_stays_question_scoped():
    regions = classify_top_level_regions(
        "只依据以下材料回答。\n\n"
        "1. 有一个案例：\n假设订单翻倍。\n请说明风险。\n\n2. 请写结论。"
    )
    assert regions.question_ids == ("q1", "q2")
    assert [(s.kind, s.scope) for s in regions.instructions] == [
        ("constraint_b", "message"), ("premise_declaration", "q1"),
    ]


@pytest.mark.parametrize("container", ["材料如下：\n{}", "「{}」", "```\n{}\n```"])
def test_report_case_blocks_do_not_gain_instruction_authority(container):
    block = "1. 有两个案例：\n不要联网。\n行业情况如下。\n\n2. 公司分析\n盈利较好。"
    regions = classify_top_level_regions(container.format(block))
    assert regions.sub_questions == ()
    assert not regions.instructions
    if container.startswith("材料"):
        assert regions.classification == "boundary_uncertain"
    else:
        assert regions.classification == "no_constraint_confirmed"


def test_frozen_three_packs_keep_all_original_numbered_questions():
    root = Path(__file__).parent / "fixtures/e2_three_packs"
    for path in sorted(root.glob("q*-question.txt")):
        parts = split_user_message(path.read_text(encoding="utf-8"))
        assert parts.regions.question_ids == tuple(f"q{i}" for i in range(1, 9)), path.name
        assert parts.classification == "constraint_confirmed", path.name
    assert len(list(root.glob("q*-question.txt"))) == 3
